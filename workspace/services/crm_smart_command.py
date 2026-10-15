"""کانتکست UI فرمان هوشمند — contextual per CRM page."""
from __future__ import annotations

from typing import Any, Dict, List

from django.conf import settings
from django.urls import reverse


def _examples(items: List[tuple]) -> List[Dict[str, str]]:
    return [{'label': label, 'text': text} for label, text in items]


SMART_COMMAND_PROFILES: Dict[str, Dict[str, Any]] = {
    'today': {
        'allowed_intent': 'create_reminder',
        'context': 'today',
        'title': 'ثبت سریع یادآوری',
        'subtitle': 'زمان و مخاطب را در یک جمله بنویسید یا بگویید',
        'spark_icon': 'fa-bell',
        'placeholder': 'مثلاً: فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم',
        'wrong_intent_message': 'این بخش برای ثبت یادآوری است.',
        'enable_contact_resolve': True,
        'examples': _examples([
            ('تماس با مخاطب', 'فردا ساعت ۱۰ یادم بنداز به احمدی زنگ بزنم'),
            ('پیگیری فایل', 'پس‌فردا ظهر پیگیری فایل پونک'),
        ]),
    },
    'contacts': {
        'allowed_intent': 'create_contact',
        'context': 'contacts',
        'title': 'ثبت سریع مخاطب',
        'subtitle': 'نام، شماره و نیاز مشتری را در یک جمله وارد کنید',
        'placeholder': 'مثلاً: احمدی، 0912...، خریدار پونک با بودجه تا ۱۲ میلیارد',
        'wrong_intent_message': 'این بخش برای ثبت مخاطب است.',
        'enable_contact_resolve': False,
        'spark_icon': 'fa-user-plus',
        'examples': _examples([
            ('ذخیره با شماره', 'احمدی رو با شماره ۰۹۱۲۱۲۳۴۵۶۷ ذخیره کن'),
            ('سرنخ محله', 'یه مشتری دارم حسینی دنبال پونکه'),
            ('بازه متراژ', 'رضایی خریدار ۸۰ تا ۱۰۰ متره'),
        ]),
    },
    'properties': {
        'allowed_intent': 'create_personal_property',
        'context': 'properties',
        'title': 'ثبت سریع فایل',
        'subtitle': 'محله، متراژ و قیمت را در یک جمله بنویسید',
        'placeholder': 'مثلاً: پونک، ۱۲۰ متر، دو خواب، فروش ۱۲ میلیارد',
        'wrong_intent_message': 'این بخش برای ثبت فایل شخصی است.',
        'enable_contact_resolve': False,
        'spark_icon': 'fa-building',
        'examples': _examples([
            ('فروش', 'پونک ۱۲۰ متر دو خواب فروش ۱۲ میلیارد'),
            ('اجاره', 'صادقیه ۸۰ متر، ۵۰۰ میلیون ودیعه و ۲۵ میلیون اجاره'),
            ('امکانات', 'جنت‌آباد ۹۰ متر، پارکینگ و آسانسور'),
        ]),
    },
}


def inject_smart_command_context(ctx: Dict[str, Any], request, profile: str) -> None:
    from ai_workspace.constants import FEATURE_NL_COMMAND, is_ai_enabled, is_feature_enabled
    from ai_workspace.services.quota import feature_quota_dict
    from workspace.services.access import get_bot_product_buy_url

    user = request.user
    enabled = is_ai_enabled() and is_feature_enabled(FEATURE_NL_COMMAND, user)
    ctx['smart_command'] = {'enabled': False}
    if not enabled:
        return

    spec = dict(SMART_COMMAND_PROFILES.get(profile) or {})
    if not spec:
        return
    spec.setdefault('spark_icon', 'fa-sparkles')

    primary_model = (getattr(settings, 'ARVAN_AI_MODEL', '') or '').strip()
    spec.update({
        'enabled': True,
        'urls': {
            'parse': reverse('workspace:ai_workspace:nl_parse'),
            'confirm': reverse('workspace:ai_workspace:nl_confirm'),
            'resolve_contact': reverse('workspace:ai_workspace:nl_resolve_contact'),
        },
        'nav': {
            'today': reverse('workspace:crm_today'),
            'contacts': reverse('workspace:crm_contacts'),
            'properties': reverse('workspace:crm_properties'),
        },
        'edit_url': reverse('workspace:reminder_create') if profile == 'today' else '',
        'quota': feature_quota_dict(user, FEATURE_NL_COMMAND),
        'ai_default': primary_model or 'Arvan AI',
        'upgrade_url': get_bot_product_buy_url(),
    })
    ctx['smart_command'] = spec
    ctx['nl_command_enabled'] = True
