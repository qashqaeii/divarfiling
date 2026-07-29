"""Resolve advertiser_signal import path for Django deploy and monorepo layouts."""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_advertiser_signal_importable() -> None:
    """
    ماژول advertiser_signal را importable می‌کند.

    اولویت:
    1. django/scraper/advertiser_signal.py (دیپلوی سرور — ریشهٔ پروژه = DivarFiling)
    2. monorepo/src/advertiser_signal.py (توسعهٔ محلی)
    """
    anchor = Path(__file__).resolve()
    # از workspace/services یا scraper فراخوانی می‌شود
    if anchor.parent.name == "scraper":
        candidates = (anchor.parent, anchor.parents[2] / "src")
    else:
        candidates = (anchor.parents[2] / "scraper", anchor.parents[3] / "src")

    for directory in candidates:
        if (directory / "advertiser_signal.py").is_file():
            path = str(directory)
            if path not in sys.path:
                sys.path.insert(0, path)
            return
    raise ModuleNotFoundError(
        "advertiser_signal not found; expected scraper/advertiser_signal.py "
        "or monorepo src/advertiser_signal.py",
    )
