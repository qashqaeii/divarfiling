"""Revert {% icon %} / {% star_icon %} back to Font Awesome markup."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

LUCIDE_TO_FA = {
    'phone-call': 'fa-phone',
    'phone': 'fa-phone',
    'mail': 'fa-envelope',
    'user-round': 'fa-user',
    'user': 'fa-user',
    'house': 'fa-home',
    'home': 'fa-home',
    'layers': 'fa-layer-group',
    'layout-dashboard': 'fa-layer-group',
    'log-out': 'fa-arrow-right-from-bracket',
    'menu': 'fa-bars',
    'x': 'fa-times',
    'trending-up': 'fa-chart-line',
    'bar-chart-3': 'fa-chart-bar',
    'line-chart': 'fa-chart-line',
    'search': 'fa-search',
    'bot': 'fa-robot',
    'building-2': 'fa-building',
    'headset': 'fa-headset',
    'chevron-left': 'fa-chevron-left',
    'chevron-right': 'fa-chevron-right',
    'chevron-down': 'fa-chevron-down',
    'calendar': 'fa-calendar',
    'calendar-days': 'fa-calendar-day',
    'clock': 'fa-clock',
    'eye': 'fa-eye',
    'list': 'fa-list',
    'newspaper': 'fa-newspaper',
    'book-open': 'fa-book-open',
    'pen-line': 'fa-pen-nib',
    'arrow-left': 'fa-arrow-left',
    'arrow-right': 'fa-arrow-right',
    'plus': 'fa-plus',
    'minus': 'fa-minus',
    'check': 'fa-check',
    'circle-check': 'fa-check-circle',
    'circle-alert': 'fa-exclamation-circle',
    'circle-x': 'fa-times-circle',
    'triangle-alert': 'fa-exclamation-triangle',
    'info': 'fa-info-circle',
    'circle-help': 'fa-question-circle',
    'question-circle': 'fa-question-circle',
    'lock': 'fa-lock',
    'key': 'fa-key',
    'gem': 'fa-gem',
    'gift': 'fa-gift',
    'database': 'fa-database',
    'folder-open': 'fa-folder-open',
    'folder-tree': 'fa-folder-tree',
    'bell': 'fa-bell',
    'pie-chart': 'fa-chart-pie',
    'users-round': 'fa-users',
    'users': 'fa-users',
    'git-compare': 'fa-code-compare',
    'wand-sparkles': 'fa-wand-magic-sparkles',
    'settings-2': 'fa-gear',
    'moon': 'fa-moon',
    'sun': 'fa-sun',
    'map-pin': 'fa-map-marker-alt',
    'map': 'fa-map',
    'upload': 'fa-upload',
    'cloud-upload': 'fa-cloud-upload-alt',
    'download': 'fa-download',
    'copy': 'fa-copy',
    'trash-2': 'fa-trash',
    'pencil': 'fa-pen',
    'pen': 'fa-pen',
    'filter': 'fa-filter',
    'table': 'fa-table',
    'banknote': 'fa-money-bill-wave',
    'ruler': 'fa-ruler-combined',
    'arrow-left-right': 'fa-exchange-alt',
    'handshake': 'fa-handshake',
    'shopping-bag': 'fa-shopping-bag',
    'shopping-cart': 'fa-shopping-cart',
    'wallet': 'fa-wallet',
    'network': 'fa-chart-network',
    'link': 'fa-link',
    'loader-circle': 'fa-spinner fa-spin',
    'sparkles': 'fa-sparkles',
    'target': 'fa-bullseye',
    'shield': 'fa-shield-halved',
    'heart': 'fa-heart',
    'lightbulb': 'fa-lightbulb',
    'rocket': 'fa-rocket',
    'star': 'fa-star',
    'send': 'fa-paper-plane',
    'message-circle': 'fa-comment-dots',
    'message-square': 'fa-comment',
    'scale': 'fa-scale-balanced',
    'monitor': 'fa-desktop',
    'cpu': 'fa-microchip',
    'zap': 'fa-bolt',
    'book': 'fa-book',
    'receipt': 'fa-receipt',
    'instagram': 'fab fa-instagram',
    'external-link': 'fa-external-link-alt',
    'file-spreadsheet': 'fa-file-excel',
    'contact': 'fa-address-book',
    'door-open': 'fa-door-open',
    'sticky-note': 'fa-sticky-note',
    'list-checks': 'fa-list-check',
    'refresh-cw': 'fa-arrows-rotate',
    'message-square-text': 'fa-sms',
    'user-plus': 'fa-user-plus',
    'user-cog': 'fa-user-cog',
    'user-pen': 'fa-user-edit',
    'user-lock': 'fa-user-lock',
    'shield-user': 'fa-user-shield',
    'circle-user': 'fa-user-circle',
    'coins': 'fa-coins',
    'ellipsis': 'fa-ellipsis-h',
    'sliders-horizontal': 'fa-sliders-h',
    'align-right': 'fa-align-right',
    'square-pen': 'fa-pen-to-square',
    'box': 'fa-box',
    'car': 'fa-car',
    'archive': 'fa-archive',
    'arrow-up-down': 'fa-arrows-alt-v',
    'percent': 'fa-percent',
    'calculator': 'fa-calculator',
    'layout-grid': 'fa-th-large',
    'columns-3': 'fa-table-columns',
    'infinity': 'fa-infinity',
    'image': 'fa-image',
    'images': 'fa-images',
    'hammer': 'fa-hammer',
    'tree-pine': 'fa-tree',
    'factory': 'fa-industry',
    'wheat': 'fa-wheat-awn',
    'wifi': 'fa-wifi',
    'file-text': 'fa-file-lines',
    'fingerprint': 'fa-fingerprint',
    'id-card': 'fa-address-card',
    'gauge': 'fa-gauge-high',
    'file-output': 'fa-file-export',
    'store': 'fa-store',
    'eye-off': 'fa-eye-slash',
    'mail-check': 'fa-envelope-circle-check',
    'check-check': 'fa-check-double',
    'mails': 'fa-mail-bulk',
    'laptop': 'fa-laptop-house',
    'mouse-pointer': 'fa-mouse-pointer',
    'building': 'fa-building',
}

ICON_TAG = re.compile(
    r'\{%\s*icon\s+("([^"]+)"|(\w+(?:\.\w+)+))\s*(?:size=\d+\s*)?(?:class_name="[^"]*"\s*)?%\}',
    re.I,
)

STAR_FILLED = re.compile(
    r'\{%\s*if\s+([^%]+?)\s*%\}\{%\s*star_icon\s+filled=True[^%]*%\}\{%\s*else\s*%\}\{%\s*star_icon\s+filled=False[^%]*%\}\{%\s*endif\s*%\}',
    re.I,
)

STAR_SIMPLE_FILLED = re.compile(
    r'\{%\s*star_icon\s+filled=True[^%]*%\}',
    re.I,
)
STAR_SIMPLE_EMPTY = re.compile(
    r'\{%\s*star_icon\s+filled=False[^%]*%\}',
    re.I,
)


def fa_icon(lucide_name: str) -> str:
    if lucide_name.startswith('fa-') or lucide_name.startswith('fab '):
        return lucide_name
    fa = LUCIDE_TO_FA.get(lucide_name, f'fa-{lucide_name.replace("-", "-")}')
    prefix = 'fab' if fa.startswith('fab ') else 'fas'
    cls = fa.replace('fab ', '')
    spin = ' fa-spin' if 'fa-spin' in cls else ''
    cls = cls.replace(' fa-spin', '')
    return f'<i class="{prefix} {cls}{spin}" aria-hidden="true"></i>'


def replace_icon_tag(m: re.Match) -> str:
    quoted = m.group(2)
    var = m.group(3)
    if quoted:
        return fa_icon(quoted)
    return f'<i class="fas {{{{ {var} }}}}" aria-hidden="true"></i>'


def process_text(text: str) -> str:
    text = ICON_TAG.sub(replace_icon_tag, text)
    text = STAR_SIMPLE_FILLED.sub('<i class="fas fa-star star-filled" aria-hidden="true"></i>', text)
    text = STAR_SIMPLE_EMPTY.sub('<i class="far fa-star star-empty" aria-hidden="true"></i>', text)
    text = re.sub(
        r'\{%\s*load\s+icon_tags\s*%\}\n?',
        '',
        text,
    )
    return text


def main():
    changed = 0
    for path in (ROOT / 'templates').rglob('*.html'):
        original = path.read_text(encoding='utf-8')
        updated = process_text(original)
        if updated != original:
            path.write_text(updated, encoding='utf-8')
            print('reverted', path.relative_to(ROOT))
            changed += 1
    print(f'Done. {changed} files.')


if __name__ == '__main__':
    main()
