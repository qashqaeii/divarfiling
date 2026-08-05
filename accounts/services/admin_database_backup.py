"""بک‌آپ دیتابیس برای پنل مدیریت — PostgreSQL، SQLite یا dumpdata."""
from __future__ import annotations

import gzip
import io
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

logger = logging.getLogger(__name__)


class DatabaseBackupError(Exception):
    def __init__(self, message: str, *, code: str = 'backup_failed'):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class DatabaseBackupResult:
    filename: str
    content_type: str
    method: str
    content: Optional[bytes] = None
    file_path: Optional[Path] = None

    @property
    def size_bytes(self) -> int:
        if self.content is not None:
            return len(self.content)
        if self.file_path and self.file_path.is_file():
            return self.file_path.stat().st_size
        return 0


def _timestamp() -> str:
    return timezone.now().strftime('%Y%m%d_%H%M%S')


def _engine_label(engine: str) -> str:
    if 'postgresql' in engine:
        return 'PostgreSQL'
    if 'sqlite' in engine:
        return 'SQLite'
    return engine.rsplit('.', maxsplit=1)[-1]


def get_database_backup_info() -> Dict[str, Any]:
    """متادیتای بک‌آپ برای نمایش در پنل."""
    db = settings.DATABASES['default']
    engine = db.get('ENGINE', '')
    is_postgres = 'postgresql' in engine
    is_sqlite = 'sqlite' in engine
    pg_dump_path = shutil.which('pg_dump')

    if is_postgres:
        default_format = 'pg_dump' if pg_dump_path else 'dumpdata'
        default_label = 'SQL (pg_dump)' if pg_dump_path else 'JSON (dumpdata)'
    elif is_sqlite:
        default_format = 'sqlite'
        default_label = 'فایل SQLite'
    else:
        default_format = 'dumpdata'
        default_label = 'JSON (dumpdata)'

    return {
        'engine': engine,
        'engine_label': _engine_label(engine),
        'database_name': str(db.get('NAME', '')),
        'pg_dump_available': bool(pg_dump_path),
        'default_format': default_format,
        'default_label': default_label,
        'supports_custom_dump': is_postgres and bool(pg_dump_path),
    }


def iter_backup_file_chunks(
    result: DatabaseBackupResult,
    *,
    chunk_size: int = 1024 * 256,
) -> Iterator[bytes]:
    """خواند chunkای فایل بک‌آپ و در پایان فایل موقت را حذف می‌کند."""
    if result.content is not None:
        for offset in range(0, len(result.content), chunk_size):
            yield result.content[offset:offset + chunk_size]
        return

    path = result.file_path
    if not path or not path.is_file():
        return

    try:
        with path.open('rb') as handle:
            while True:
                chunk = handle.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.warning('Could not delete temp backup file: %s', path)


def _dumpdata_backup() -> DatabaseBackupResult:
    buffer = io.StringIO()
    try:
        call_command(
            'dumpdata',
            exclude=['contenttypes', 'auth.permission'],
            natural_foreign=True,
            natural_primary=True,
            indent=2,
            stdout=buffer,
        )
    except Exception as exc:
        logger.exception('dumpdata backup failed')
        raise DatabaseBackupError(
            f'بک‌آپ JSON ناموفق بود: {exc}',
            code='dumpdata_failed',
        ) from exc

    raw = buffer.getvalue().encode('utf-8')
    if not raw:
        raise DatabaseBackupError('خروجی dumpdata خالی بود.', code='dumpdata_empty')

    compressed = gzip.compress(raw)
    stamp = _timestamp()
    return DatabaseBackupResult(
        content=compressed,
        filename=f'divarfiling-dumpdata-{stamp}.json.gz',
        content_type='application/gzip',
        method='dumpdata',
    )


def _sqlite_file_backup() -> DatabaseBackupResult:
    db_path = Path(settings.DATABASES['default']['NAME'])
    if not db_path.is_file():
        raise DatabaseBackupError('فایل SQLite یافت نشد.')

    tmp = tempfile.NamedTemporaryFile(prefix='divarfiling-sqlite-backup-', suffix='.sqlite3', delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        shutil.copy2(db_path, tmp_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise DatabaseBackupError(f'کپی فایل SQLite ناموفق بود: {exc}') from exc

    stamp = _timestamp()
    return DatabaseBackupResult(
        file_path=tmp_path,
        filename=f'divarfiling-sqlite-{stamp}.sqlite3',
        content_type='application/x-sqlite3',
        method='sqlite_copy',
    )


def _pg_dump_env() -> dict[str, str]:
    env = os.environ.copy()
    password = settings.DATABASES['default'].get('PASSWORD')
    if password:
        env['PGPASSWORD'] = str(password)
    return env


def _pg_dump_base_cmd(pg_dump: str) -> list[str]:
    db = settings.DATABASES['default']
    return [
        pg_dump,
        '-h', str(db.get('HOST') or 'localhost'),
        '-p', str(db.get('PORT') or 5432),
        '-U', str(db.get('USER') or 'postgres'),
        '-d', str(db['NAME']),
        '--no-owner',
        '--no-acl',
    ]


def _run_pg_dump(*, custom_format: bool) -> DatabaseBackupResult:
    pg_dump = shutil.which('pg_dump')
    if not pg_dump:
        raise DatabaseBackupError(
            'ابزار pg_dump در PATH سرور یافت نشد. از فرمت JSON استفاده کنید.',
            code='pg_dump_missing',
        )

    stamp = _timestamp()
    suffix = '.dump' if custom_format else '.sql'
    filename = f'divarfiling-postgres-{stamp}{suffix}'
    content_type = 'application/octet-stream' if custom_format else 'application/sql'
    method = 'pg_dump_custom' if custom_format else 'pg_dump_plain'

    tmp = tempfile.NamedTemporaryFile(prefix='divarfiling-backup-', suffix=suffix, delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    cmd = _pg_dump_base_cmd(pg_dump)
    if custom_format:
        cmd.extend(['-F', 'c', '-f', str(tmp_path)])
    else:
        cmd.extend(['-F', 'p', '-f', str(tmp_path)])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            env=_pg_dump_env(),
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        tmp_path.unlink(missing_ok=True)
        raise DatabaseBackupError('زمان بک‌آپ PostgreSQL تمام شد (بیش از ۱۰ دقیقه).') from exc
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        logger.exception('pg_dump subprocess failed')
        raise DatabaseBackupError(f'اجرای pg_dump ممکن نشد: {exc}', code='pg_dump_os_error') from exc

    if proc.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        stderr = (proc.stderr or b'').decode('utf-8', errors='replace').strip()
        detail = stderr[:400] if stderr else f'کد خروج: {proc.returncode}'
        raise DatabaseBackupError(f'pg_dump ناموفق بود: {detail}')

    if not tmp_path.is_file() or tmp_path.stat().st_size == 0:
        tmp_path.unlink(missing_ok=True)
        raise DatabaseBackupError('خروجی pg_dump خالی بود.')

    return DatabaseBackupResult(
        file_path=tmp_path,
        filename=filename,
        content_type=content_type,
        method=method,
    )


def create_database_backup(*, fmt: str = 'auto') -> DatabaseBackupResult:
    """
    fmt:
      auto — بهترین روش بر اساس موتور DB
      pg_dump — SQL ساده PostgreSQL
      custom — فرمت custom PostgreSQL (pg_restore)
      dumpdata — JSON فشرده Django
      sqlite — کپی فایل SQLite
    """
    db = settings.DATABASES['default']
    engine = db.get('ENGINE', '')
    fmt = (fmt or 'auto').lower().strip()

    if fmt == 'dumpdata':
        return _dumpdata_backup()

    if fmt == 'sqlite':
        if 'sqlite' not in engine:
            raise DatabaseBackupError('بک‌آپ فایل SQLite فقط برای SQLite در دسترس است.')
        return _sqlite_file_backup()

    if fmt == 'custom':
        if 'postgresql' not in engine:
            raise DatabaseBackupError('فرمت custom فقط برای PostgreSQL در دسترس است.')
        return _run_pg_dump(custom_format=True)

    if fmt == 'pg_dump':
        if 'postgresql' not in engine:
            raise DatabaseBackupError('pg_dump فقط برای PostgreSQL در دسترس است.')
        return _run_pg_dump(custom_format=False)

    # auto
    if 'postgresql' in engine:
        try:
            return _run_pg_dump(custom_format=False)
        except DatabaseBackupError as exc:
            logger.warning('pg_dump auto fallback to dumpdata: %s', exc.message)
            return _dumpdata_backup()

    if 'sqlite' in engine:
        try:
            return _sqlite_file_backup()
        except DatabaseBackupError:
            return _dumpdata_backup()

    return _dumpdata_backup()
