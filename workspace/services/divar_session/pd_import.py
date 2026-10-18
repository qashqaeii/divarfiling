"""بارگذاری ماژول‌های phone-detector بدون Engine سراسری."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.conf import settings


class PhoneDetectorImportError(RuntimeError):
    pass


def resolve_phone_detector_dir() -> Path | None:
    raw = (getattr(settings, 'PHONE_DETECTOR_DIR', None) or '').strip()
    candidates: list[Path] = []
    if raw:
        candidates.append(Path(raw).expanduser())
    base = Path(getattr(settings, 'BASE_DIR', Path.cwd()))
    candidates.extend([
        base.parent / 'phone-detector',
        Path('/root/phone-detector'),
    ])
    for path in candidates:
        try:
            resolved = path.resolve()
        except OSError:
            continue
        if resolved.is_dir() and (resolved / 'main.py').is_file():
            return resolved
    return None


def ensure_phone_detector_path() -> Path:
    pd = resolve_phone_detector_dir()
    if not pd:
        raise PhoneDetectorImportError(
            'phone-detector یافت نشد — PHONE_DETECTOR_DIR را تنظیم کنید.',
        )
    if str(pd) not in sys.path:
        sys.path.insert(0, str(pd))
    return pd


@lru_cache(maxsize=1)
def load_pd_main() -> Any:
    ensure_phone_detector_path()
    import main as pd_main  # noqa: WPS433

    return pd_main
