"""قفل بین‌پردازه‌ای برای تغییرات sessions/index در phone-detector (مستقل از LocMemCache)."""
from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, TypeVar

from accounts.services.phone_detector_lines import resolve_phone_detector_dir

logger = logging.getLogger(__name__)

PD_LOCK_FILENAME = '.lac_pd_sessions.lock'
DEFAULT_MUTATION_WAIT = 90.0
_STALE_LOCK_AGE_WHEN_PID_UNKNOWN = 600.0

T = TypeVar('T')


def _import_pd_lock_sync():
    """همان شمارنده reentrant در lac_sessions_lock (phone-detector)."""
    pd = resolve_phone_detector_dir()
    if not pd:
        return None
    pd_str = str(pd.resolve())
    if pd_str not in sys.path:
        sys.path.insert(0, pd_str)
    try:
        import lac_sessions_lock  # type: ignore[import-not-found]

        return lac_sessions_lock
    except ImportError:
        return None


def _pd_mutation_lock_held() -> bool:
    mod = _import_pd_lock_sync()
    if mod is None:
        return False
    return bool(mod.mutation_lock_held())


def _pd_bump_mutation_depth(delta: int) -> None:
    mod = _import_pd_lock_sync()
    if mod is None:
        return
    mod.bump_mutation_depth(delta)


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == 'nt':
        synchronize = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(synchronize, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _read_lock_pid(path: Path) -> int | None:
    try:
        raw = path.read_text(encoding='ascii').strip()
        if not raw:
            return None
        return int(raw.split()[0])
    except (OSError, ValueError):
        return None


def try_reclaim_stale_lock(path: Path) -> bool:
    """حذف قفل یتیم — فقط اگر PID مرده باشد یا فایل بسیار قدیمی و بدون PID معتبر."""
    if not path.is_file():
        return False
    pid = _read_lock_pid(path)
    if pid is not None:
        if pid == os.getpid() and _pd_mutation_lock_held():
            return False
        if _pid_alive(pid):
            return False
    else:
        try:
            age = time.time() - path.stat().st_mtime
        except OSError:
            return False
        if age < _STALE_LOCK_AGE_WHEN_PID_UNKNOWN:
            return False
    try:
        path.unlink()
        logger.warning('Reclaimed stale PD sessions lock at %s (pid=%s)', path, pid)
        return True
    except OSError:
        return False


class PdSessionsFileLock:
    """قفل انحصاری با فایل — create exclusive روی sessions/.lac_pd_sessions.lock."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._path: Path | None = None
        self._owns_bump = False

    def _lock_path(self) -> Path | None:
        pd = resolve_phone_detector_dir()
        if not pd:
            return None
        root = pd / 'sessions'
        root.mkdir(parents=True, exist_ok=True)
        return root / PD_LOCK_FILENAME

    def acquire(self, *, wait_seconds: float = 0.0) -> bool:
        path = self._lock_path()
        if not path:
            return False
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while True:
            try:
                self._fd = os.open(
                    str(path),
                    os.O_CREAT | os.O_EXCL | os.O_RDWR,
                )
                os.write(self._fd, f'{os.getpid()}\n'.encode('ascii'))
                self._path = path
                _pd_bump_mutation_depth(1)
                self._owns_bump = True
                return True
            except FileExistsError:
                try_reclaim_stale_lock(path)
                if time.monotonic() >= deadline:
                    return False
                time.sleep(0.12)
            except OSError:
                logger.warning('pd file lock open failed', exc_info=True)
                return False

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        if self._owns_bump:
            _pd_bump_mutation_depth(-1)
            self._owns_bump = False
        if self._path and self._path.is_file():
            try:
                self._path.unlink()
            except OSError:
                logger.debug('pd lock unlink failed', exc_info=True)
        self._path = None


@contextmanager
def pd_sessions_mutation_lock(*, wait_seconds: float = 0.0) -> Iterator[bool]:
    lock = PdSessionsFileLock()
    acquired = lock.acquire(wait_seconds=wait_seconds)
    try:
        yield acquired
    finally:
        if acquired:
            lock.release()


def run_pd_sessions_mutation(
    fn: Callable[..., T],
    /,
    *args,
    wait_seconds: float = DEFAULT_MUTATION_WAIT,
    **kwargs,
) -> T:
    """اجرای تابعی که index/sessions را تغییر می‌دهد — تحت قفل فایل."""
    with pd_sessions_mutation_lock(wait_seconds=wait_seconds) as acquired:
        if not acquired:
            raise RuntimeError('pd_sessions_file_lock_busy')
        return fn(*args, **kwargs)