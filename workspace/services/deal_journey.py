"""Contextual Deal Journey — قدم بعدی و راهنمای مرحله."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.urls import reverse

from contracts.services.routing import contract_manage_url, contract_wizard_url, contracts_dashboard_url
from workspace.models import CRMDeal
from workspace.services.crm_deal_stages import is_lost_stage, is_terminal_stage, is_won_stage
from workspace.services.crm_deals import is_deal_stale


def _stage_kind(stage: str) -> str:
    s = (stage or '').strip()
    if is_won_stage(s):
        return 'won'
    if is_lost_stage(s):
        return 'lost'
    if 'سرنخ' in s:
        return 'lead'
    if 'تماس' in s:
        return 'contact'
    if 'بازدید' in s:
        return 'visit'
    if 'پیشنهاد' in s:
        return 'proposal'
    if 'پیش' in s and 'قرارداد' in s:
        return 'pre_contract'
    if s == 'قرارداد' or (s.endswith('قرارداد') and 'پیش' not in s):
        return 'contract'
    if 'مذاکره' in s:
        return 'negotiate'
    return 'active'


def _contract_cta(deal: CRMDeal, contracts: list) -> Optional[Dict[str, Any]]:
    if not contracts:
        return None
    draft = next((c for c in contracts if c.status == 'draft'), None)
    pending = next(
        (c for c in contracts if c.status in (
            'sent', 'viewed', 'partially_accepted', 'fully_accepted', 'ready',
        )),
        None,
    )
    finalized = next((c for c in contracts if c.status == 'finalized'), None)
    if pending:
        return {
            'label': 'مشاهده وضعیت تأیید',
            'desc': f'قرارداد {pending.internal_number} در انتظار تأیید طرفین است.',
            'url': contract_manage_url(pending),
            'icon': 'fa-hourglass-half',
            'kind': 'primary',
        }
    if draft:
        return {
            'label': 'ادامه قرارداد',
            'desc': f'پیش‌نویس {draft.internal_number} — تکمیل و ارسال.',
            'url': contract_wizard_url(draft),
            'icon': 'fa-file-pen',
            'kind': 'primary',
        }
    if finalized:
        return {
            'label': 'مشاهده قرارداد نهایی',
            'desc': f'قرارداد {finalized.internal_number} نهایی شده است.',
            'url': contract_manage_url(finalized),
            'icon': 'fa-file-circle-check',
            'kind': 'secondary',
        }
    return None


def build_deal_journey_context(
    deal: CRMDeal,
    *,
    user,
    next_action: Optional[Dict[str, Any]],
    checklist_progress: Dict[str, Any],
    contracts: list,
    contracts_count: int,
) -> Dict[str, Any]:
    """Hero NBA و اقدامات contextual برای صفحه معامله."""
    kind = _stage_kind(deal.stage)
    customer = deal.customer
    phone = getattr(customer, 'phone', '') if customer else ''
    contract_cta = _contract_cta(deal, contracts)
    stale = is_deal_stale(deal)

    primary: Dict[str, Any] = {}
    secondary: List[Dict[str, Any]] = []
    headline = 'قدم بعدی'
    subline = ''

    if next_action and next_action.get('is_overdue'):
        headline = 'پیگیری عقب‌افتاده'
        subline = 'این اقدام باید زودتر انجام می‌شد.'
        primary = {
            'label': next_action.get('label') or 'تکمیل اقدام بعدی',
            'desc': next_action.get('note') or next_action.get('schedule_label') or '',
            'action': 'complete_next_action',
            'icon': next_action.get('icon') or 'fa-clock',
            'kind': 'danger',
        }
        secondary.append({
            'label': 'ویرایش اقدام',
            'action': 'drawer-next-action',
            'icon': 'fa-pen',
        })
    elif kind == 'won':
        headline = 'معامله بسته شد'
        subline = 'تبریک — پرونده با موفقیت بسته شده است.'
        primary = {
            'label': 'مشاهده خلاصه مالی',
            'action': 'drawer-finance',
            'icon': 'fa-coins',
            'kind': 'success',
        }
    elif kind == 'lost':
        headline = 'معامله از دست رفته'
        subline = deal.lost_reason or 'می‌توانید یادداشت‌ها را مرور کنید.'
        primary = {
            'label': 'مشاهده تاریخچه',
            'url': f'?tab=activity',
            'icon': 'fa-clock-rotate-left',
            'kind': 'muted',
        }
    elif kind == 'contract' or (kind == 'pre_contract' and contracts_count):
        if contract_cta:
            headline = 'قرارداد'
            subline = contract_cta.get('desc', '')
            primary = {
                'label': contract_cta['label'],
                'url': contract_cta.get('url'),
                'icon': contract_cta.get('icon', 'fa-file-signature'),
                'kind': contract_cta.get('kind', 'primary'),
            }
        elif kind == 'contract':
            headline = 'زمان قرارداد'
            subline = 'برای این معامله هنوز قرارداد دیجیتال ثبت نشده است.'
            primary = {
                'label': 'ایجاد قرارداد',
                'action': 'create_contract',
                'icon': 'fa-file-signature',
                'kind': 'primary',
            }
        else:
            headline = 'پیش از قرارداد'
            subline = 'مدارک را تکمیل کنید تا آماده قرارداد شوید.'
            primary = {
                'label': 'تکمیل مدارک',
                'url': '?tab=documents',
                'icon': 'fa-clipboard-check',
                'kind': 'primary',
            }
    elif kind == 'visit':
        headline = 'بازدید'
        subline = 'نتیجه بازدید را ثبت کنید یا بازدید بعدی را هماهنگ کنید.'
        primary = {
            'label': 'ثبت نتیجه بازدید',
            'action': 'drawer-followup',
            'icon': 'fa-door-open',
            'kind': 'primary',
        }
        secondary.append({'label': 'برنامه‌ریزی بازدید', 'action': 'drawer-next-action', 'icon': 'fa-calendar'})
    elif kind == 'proposal':
        headline = 'پیشنهاد'
        subline = 'پیشنهاد قیمت یا شرایط را ثبت یا به‌روز کنید.'
        primary = {
            'label': 'ثبت / ویرایش پیشنهاد',
            'action': 'drawer-followup',
            'icon': 'fa-hand-holding-dollar',
            'kind': 'primary',
        }
    elif kind == 'lead' or kind == 'contact':
        headline = 'تماس با مخاطب'
        subline = 'اولین گام: ارتباط با مخاطب و ثبت نتیجه.'
        if phone:
            primary = {
                'label': 'تماس با مخاطب',
                'action': 'call',
                'icon': 'fa-phone',
                'kind': 'primary',
            }
        else:
            primary = {
                'label': 'ثبت پیگیری تماس',
                'action': 'drawer-followup',
                'icon': 'fa-phone',
                'kind': 'primary',
            }
        secondary.append({'label': 'ثبت پیگیری', 'action': 'drawer-followup', 'icon': 'fa-comment-dots'})
        secondary.append({'label': 'اقدام بعدی', 'action': 'drawer-next-action', 'icon': 'fa-bolt'})
    elif next_action:
        headline = 'اقدام بعدی'
        subline = next_action.get('schedule_label') or ''
        primary = {
            'label': next_action.get('label') or 'انجام اقدام',
            'desc': next_action.get('note') or '',
            'action': 'complete_next_action',
            'icon': next_action.get('icon') or 'fa-bolt',
            'kind': 'primary',
        }
        secondary.append({'label': 'ویرایش', 'action': 'drawer-next-action', 'icon': 'fa-pen'})
    else:
        headline = 'پیگیری معامله'
        subline = 'اقدام بعدی تعیین نشده — قدم بعدی را مشخص کنید.'
        primary = {
            'label': 'تعیین اقدام بعدی',
            'action': 'drawer-next-action',
            'icon': 'fa-bolt',
            'kind': 'primary',
        }
        secondary.append({'label': 'ثبت پیگیری', 'action': 'drawer-followup', 'icon': 'fa-comment-dots'})

    if stale and not is_terminal_stage(deal.stage):
        secondary.insert(0, {
            'label': 'معامله کهنه — پیگیری کنید',
            'action': 'drawer-followup',
            'icon': 'fa-hourglass-end',
            'warn': True,
        })

    if contracts_count and kind not in ('contract', 'won', 'lost') and not contract_cta:
        secondary.append({
            'label': f'{contracts_count} قرارداد مرتبط',
            'url': contracts_dashboard_url(deal=deal.pk),
            'icon': 'fa-file-signature',
        })

    return {
        'headline': headline,
        'subline': subline,
        'primary': primary,
        'secondary': secondary,
        'stage_kind': kind,
        'is_stale': stale,
        'contracts_url': contracts_dashboard_url(deal=deal.pk),
        'create_contract_url': reverse('workspace:contract_create', kwargs={'deal_id': deal.pk}),
    }
