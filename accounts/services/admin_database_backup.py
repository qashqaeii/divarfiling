"""بک‌آپ دیتابیس برای پنل مدیریت — PostgreSQL، SQLite یا dumpdata."""
from __future__ import annotations

import gzip
import io
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone


class DatabaseBackupError(Exception):
    def __init__(self, message: str, *, code: str = 'backup_failed'):
        self.message = message
        self.code = code
        super().__init__(message)


@dataclass
class DatabaseBackupResult:
    content: bytes
    filename: str
    content_type: str
    method: str
    size_bytes: int


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


def _dumpdata_backup() -> DatabaseBackupResult:
    buffer = io.StringIO()
    call_command(
        'dumpdata',
        exclude=['contenttypes', 'auth.permission'],
        natural_foreign=True,
        natural_primary=True,
        indent=2,
        stdout=buffer,
    )
    raw = buffer.getvalue().encode('utf-8')
    compressed = gzip.compress(raw)
    stamp = _timestamp()
    return DatabaseBackupResult(
        content=compressed,
        filename=f'divarfiling-dumpdata-{stamp}.json.gz',
        content_type='application/gzip',
        method='dumpdata',
        size_bytes=len(compressed),
    )


def _sqlite_file_backup() -> DatabaseBackupResult:
    db_path = Path(settings.DATABASES['default']['NAME'])
    if not db_path.is_file():
        raise DatabaseBackupError('فایل SQLite یافت نشد.')

    content = db_path.read_bytes()
    stamp = _timestamp()
    return DatabaseBackupResult(
        content=content,
        filename=f'divarfiling-sqlite-{stamp}.sqlite3',
        content_type='application/x-sqlite3',
        method='sqlite_copy',
        size_bytes=len(content),
    )


def _run_pg_dump(*, custom_format: bool) -> DatabaseBackupResult:
    db = settings.DATABASES['default']
    pg_dump = shutil.which('pg_dump')
    if not pg_dump:
        raise DatabaseBackupError(
            'ابزار pg_dump در PATH سرور یافت نشد. از فرمت JSON استفاده کنید.',
            code='pg_dump_missing',
        )

    env = os.environ.copy()
    password = db.get('PASSWORD')
    if password:
        env['PGPASSWORD'] = str(password)

    stamp = _timestamp()
    if custom_format:
        filename = f'divarfiling-postgres-{stamp}.dump'
        cmd = [
            pg_dump,
            '-h', db.get('HOST') or 'localhost',
            '-p', str(db.get('PORT') or 5432),
            '-U', db.get('USER') or 'postgres',
            '-d', db['NAME'],
            '-F', 'c',
            '-f', '-',
            '--no-owner',
            '--no-acl',
        ]
        content_type = 'application/octet-stream'
        method = 'pg_dump_custom'
    else:
        filename = f'divarfiling-postgres-{stamp}.sql'
        cmd = [
            pg_dump,
            '-h', db.get('HOST') or 'localhost',
            '-p', str(db.get('PORT') or 5432),
            '-U', db.get('USER') or 'postgres',
            '-d', db['NAME'],
            '--no-owner',
            '--no-acl',
        ]
        content_type = 'application/sql'
        method = 'pg_dump_plain'

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            env=env,
            timeout=600,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise DatabaseBackupError('زمان بک‌آپ PostgreSQL تمام شد (بیش از ۱۰ دقیقه).') from exc

    if proc.returncode != 0:
        stderr = (proc.stderr or b'').decode('utf-8', errors='replace').strip()
        detail = stderr[:400] if stderr else f'کد خروج: {proc.returncode}'
        raise DatabaseBackupError(f'pg_dump ناموفق بود: {detail}')

    content = proc.stdout or b''
    if not content:
        raise DatabaseBackupError('خروجی pg_dump خالی بود.')

    return DatabaseBackupResult(
        content=content,
        filename=filename,
        content_type=content_type,
        method=method,
        size_bytes=len(content),
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
        except DatabaseBackupError:
            return _dumpdata_backup()

    if 'sqlite' in engine:
        try:
            return _sqlite_file_backup()
        except DatabaseBackupError:
            return _dumpdata_backup()

    return _dumpdata_backup()
