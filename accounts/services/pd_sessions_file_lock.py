"""قفل بین‌پردازه‌ای برای تغییرات sessions/index در phone-detector (مستقل از LocMemCache)."""
from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, TypeVar

from accounts.services.phone_detector_lines import resolve_phone_detector_dir

logger = logging.getLogger(__name__)

PD_LOCK_FILENAME = '.lac_pd_sessions.lock'
DEFAULT_MUTATION_WAIT = 90.0

T = TypeVar('T')


class PdSessionsFileLock:
    """قفل انحصاری با فایل — create exclusive روی sessions/.lac_pd_sessions.lock."""

    def __init__(self) -> None:
        self._fd: int | None = None
        self._path: Path | None = None

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
                return True
            except FileExistsError:
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