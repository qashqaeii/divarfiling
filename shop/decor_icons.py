"""Decorative PNG icons in static/icons — shared with mobile app."""

from __future__ import annotations

DECOR_ICONS: dict[str, str] = {
    # Navigation & shell
    'house': 'house.png',
    'folder': 'folder.png',
    'users': 'users.png',
    'handshake': 'handshake.png',
    'settings': 'settings.png',
    # Actions & status
    'bell': 'bell.png',
    'calendar': 'calendar.png',
    'database': 'database.png',
    'building': 'building.png',
    'tag': 'tag.png',
    'zap': 'zap.png',
    'search': 'search.png',
    'timer': 'timer.png',
    'list_todo': 'list_todo.png',
    'user': 'user.png',
    'trending_up': 'trending_up.png',
    'filter': 'filter.png',
    # Property amenities
    'car': 'car.png',
    'storage': 'storage.png',
    'elevator': 'elevator.png',
    # Contact & links
    'phone': 'phone.png',
    'external_link': 'external_link.png',
    'copy': 'copy.png',
    'file_edit': 'file_edit.png',
    # Tools & analytics
    'calculator': 'calculator.png',
    'rotate_ccw': 'rotate_ccw.png',
    'scale': 'scale.png',
    'percent': 'percent.png',
    'bar_chart': 'bar_chart.png',
    'layout_grid': 'layout_grid.png',
    # Legacy / marketing
    'clipboard_list': 'clipboard_list.png',
    'coins': 'coins.png',
    'download': 'download.png',
    'file_text': 'file_text.png',
    'layers': 'layers.png',
    'map_pin': 'map_pin.png',
    'rocket': 'rocket.png',
    'ruler': 'ruler.png',
    'share_2': 'share_2.png',
    'sparkles': 'sparkles.png',
    'sticky_note': 'sticky_note.png',
    'upload': 'upload.png',
    # Sidebar utilities & CRM extras
    'automation': 'automation.png',
    'message_template': 'message_template.png',
    'team': 'team.png',
    'help_center': 'help_center.png',
    'api_docs': 'api_documentation.png',
    'theme_switch': 'theme_switch.png',
}

CRM_ILLUSTRATIONS: dict[str, str] = {
    'contacts': 'crm_illustration_contacts.png',
    'today': 'crm_illustration_today.png',
    'deals': 'crm_illustration_deals.png',
    'properties': 'crm_illustration_properties.png',
}

ICON_SIZES: dict[str, int] = {
    'inline': 18,   # buttons
    'xs': 16,
    'nav': 20,      # sidebar
    'sm': 20,
    'metric': 24,   # dashboard cards / KPI
    'md': 28,
    'lg': 36,
    'xl': 44,
    'hero': 56,
}
