"""شناسایی قابلیت‌های سطح بالا در نرم‌افزار ویندوز از کد src/."""
from __future__ import annotations

import re
from pathlib import Path

_PANEL_RE = re.compile(r'def _feat_build_(\w+)_panel')
_TAB_RE = re.compile(r'def _feat_build_(\w+)_tab')


def collect_windows_surface(src_dir: Path) -> dict:
    if not src_dir.is_dir():
        return {'available': False, 'note': 'windows_src_not_found', 'panels': [], 'tabs': [], 'files': []}

    features_file = src_dir / 'app_features.py'
    panels: list[str] = []
    tabs: list[str] = []
    if features_file.is_file():
        text = features_file.read_text(encoding='utf-8')
        panels = sorted(set(_PANEL_RE.findall(text)))
        tabs = sorted(set(_TAB_RE.findall(text)))

    key_files = [
        'divar_gui.py',
        'export_divar_items.py',
        'app_features.py',
        'license_client.py',
        'app_storage.py',
        'app_crm.py',
    ]
    present = [f for f in key_files if (src_dir / f).is_file()]

    return {
        'available': True,
        'note': 'inferred_from_src_layout',
        'panels': panels,
        'tabs': tabs,
        'files': present,
        'source_ref': 'src/app_features.py',
    }
