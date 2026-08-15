"""DB connection helpers for long-running processes (workers, background threads)."""
from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

from django.db import close_old_connections, connections
from django.db.utils import DatabaseError, InterfaceError, OperationalError

logger = logging.getLogger(__name__)

T = TypeVar('T')

_STALE_DB_ERRORS = (InterfaceError, OperationalError)


def reset_db_connections() -> None:
    """Force-close all DB connections; next ORM call opens a fresh socket."""
    close_old_connections()
    connections.close_all()


def run_db_with_retry(
    operation: Callable[[], T],
    *,
    retries: int = 3,
    delay_seconds: float = 0.35,
    label: str = 'db',
) -> T:
    last_error: BaseException | None = None
    for attempt in range(1, retries + 1):
        reset_db_connections()
        try:
            return operation()
        except _STALE_DB_ERRORS as exc:
            last_error = exc
            logger.warning(
                '%s: stale DB connection (attempt %s/%s): %s',
                label,
                attempt,
                retries,
                exc,
            )
            connections.close_all()
            if attempt >= retries:
                break
            time.sleep(delay_seconds * attempt)
        except DatabaseError:
            raise
    assert last_error is not None
    raise last_error
