"""نقش و مجوز آژانس — RBAC v2 با سازگاری نقش legacy «manager».

تا فعال‌سازی agency_rbac_v2 روی آژانس، تمام توابع has_* به رفتار قبلی (crm_scope / entitlement) برمی‌گردند.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional, Set

from workspace.constants import (
    AGENCY_ROLE_ADVISOR,
    AGENCY_ROLE_MANAGER,
    AGENCY_ROLE_OWNER,
    AGENCY_ROLE_SECRETARY,
)
from workspace.models import CRMAgency, CRMAgencyMember
from workspace.services.crm_agency_features import is_agency_feature_enabled
from django.core.exceptions import PermissionDenied

from workspace.services.crm_scope import (
    can_manage_team,
    can_operate_team_leads,
    can_view_team_inbox,
    get_membership,
)

# ── مجوزهای عملیاتی (مستقل از یکدیگر برای حساسیت مالی/قرارداد) ──
PERM_TEAM_MANAGE = 'team.manage'
PERM_TEAM_INVITE = 'team.invite'
PERM_TEAM_VIEW_PERFORMANCE = 'team.view_performance'
PERM_LICENSES_MANAGE = 'licenses.manage'
PERM_INBOX_VIEW = 'inbox.view'
PERM_INBOX_ASSIGN = 'inbox.assign'
PERM_DEALS_VIEW_TEAM = 'deals.view_team'
PERM_CONTRACTS_VIEW_TEAM = 'contracts.view_team'
PERM_FINANCE_VIEW = 'finance.view'
PERM_REPORTS_SENSITIVE = 'reports.view_sensitive'
PERM_AGENCY_SPACE_VIEW = 'agency_space.view'
PERM_AGENCY_SPACE_PUBLISH = 'agency_space.publish'
PERM_AGENCY_SPACE_MODERATE = 'agency_space.moderate'
PERM_MEMBERS_PERMISSIONS_EDIT = 'members.permissions_edit'
PERM_SETTINGS_MANAGE = 'settings.manage'
PERM_AUDIT_VIEW = 'audit.view'
PERM_HUB_OWNER_DASHBOARD = 'hub.dashboard_owner'
PERM_HUB_SECRETARY_DASHBOARD = 'hub.dashboard_secretary'
PERM_HUB_ADVISOR_DASHBOARD = 'hub.dashboard_advisor'

# فقط مالک اشتراک (can_manage_agency) — هرگز از override قابل واگذاری نیست
OWNER_ENTITLEMENT_PERMISSIONS: FrozenSet[str] = frozenset({
    PERM_LICENSES_MANAGE,
})

# در UI ویرایش مجوز اعضا نمایش/ذخیره نمی‌شوند
NON_ASSIGNABLE_MEMBER_PERMISSIONS: FrozenSet[str] = OWNER_ENTITLEMENT_PERMISSIONS

ALL_PERMISSIONS: FrozenSet[str] = frozenset({
    PERM_TEAM_MANAGE,
    PERM_TEAM_INVITE,
    PERM_TEAM_VIEW_PERFORMANCE,
    PERM_LICENSES_MANAGE,
    PERM_INBOX_VIEW,
    PERM_INBOX_ASSIGN,
    PERM_DEALS_VIEW_TEAM,
    PERM_CONTRACTS_VIEW_TEAM,
    PERM_FINANCE_VIEW,
    PERM_REPORTS_SENSITIVE,
    PERM_AGENCY_SPACE_VIEW,
    PERM_AGENCY_SPACE_PUBLISH,
    PERM_AGENCY_SPACE_MODERATE,
    PERM_MEMBERS_PERMISSIONS_EDIT,
    PERM_SETTINGS_MANAGE,
    PERM_AUDIT_VIEW,
    PERM_HUB_OWNER_DASHBOARD,
    PERM_HUB_SECRETARY_DASHBOARD,
    PERM_HUB_ADVISOR_DASHBOARD,
})

# نقش‌های هدف UI (manager در DB نگه داشته می‌شود؛ در UI به‌عنوان مالکِ عملیاتی نمایش داده نمی‌شود)
NAV_PROFILE_OWNER = 'owner'
NAV_PROFILE_SECRETARY = 'secretary'
NAV_PROFILE_ADVISOR = 'advisor'
NAV_PROFILE_MANAGER_LEGACY = 'manager_legacy'

_OWNER_TEMPLATE: Set[str] = set(ALL_PERMISSIONS)

_SECRETARY_TEMPLATE: Set[str] = {
    PERM_INBOX_VIEW,
    PERM_INBOX_ASSIGN,
    PERM_AGENCY_SPACE_VIEW,
    PERM_HUB_SECRETARY_DASHBOARD,
}

_ADVISOR_TEMPLATE: Set[str] = {
    PERM_AGENCY_SPACE_VIEW,
    PERM_AGENCY_SPACE_PUBLISH,
    PERM_HUB_ADVISOR_DASHBOARD,
}

# legacy manager ≈ مالک عملیاتی بدون لایسنس و بدون ویرایش مجوزهای دیگران
_MANAGER_LEGACY_TEMPLATE: Set[str] = _OWNER_TEMPLATE - {
    PERM_LICENSES_MANAGE,
    PERM_MEMBERS_PERMISSIONS_EDIT,
}

PERMISSION_LABELS: Dict[str, str] = {
    PERM_TEAM_MANAGE: 'مدیریت تیم',
    PERM_TEAM_INVITE: 'دعوت عضو',
    PERM_TEAM_VIEW_PERFORMANCE: 'مشاهده عملکرد تیم',
    PERM_LICENSES_MANAGE: 'مدیریت لایسنس و صندلی',
    PERM_INBOX_VIEW: 'مشاهده صندوق سرنخ',
    PERM_INBOX_ASSIGN: 'ارجاع و تخصیص سرنخ',
    PERM_DEALS_VIEW_TEAM: 'مشاهده معاملات تیم',
    PERM_CONTRACTS_VIEW_TEAM: 'مشاهده قراردادهای تیم',
    PERM_FINANCE_VIEW: 'اطلاعات مالی',
    PERM_REPORTS_SENSITIVE: 'گزارش‌های محرمانه',
    PERM_AGENCY_SPACE_VIEW: 'مشاهده فضای آژانس',
    PERM_AGENCY_SPACE_PUBLISH: 'انتشار در فضای آژانس',
    PERM_AGENCY_SPACE_MODERATE: 'مدیریت انتشار فضای آژانس',
    PERM_MEMBERS_PERMISSIONS_EDIT: 'ویرایش مجوز اعضا',
    PERM_SETTINGS_MANAGE: 'تنظیمات آژانس',
    PERM_AUDIT_VIEW: 'ممیزی و تاریخچه',
}

ROLE_TEMPLATE_LABELS = {
    AGENCY_ROLE_OWNER: 'مالک (الگوی کامل)',
    AGENCY_ROLE_SECRETARY: 'منشی (پذیرش)',
    AGENCY_ROLE_ADVISOR: 'مشاور',
    AGENCY_ROLE_MANAGER: 'مدیر (سازگاری)',
}

ASSIGNABLE_ROLE_CODES = frozenset({AGENCY_ROLE_ADVISOR, AGENCY_ROLE_SECRETARY})


def is_agency_rbac_v2_enabled(agency: Optional[CRMAgency]) -> bool:
    return is_agency_feature_enabled('agency_rbac_v2', agency)


def is_agency_secretary_hub_enabled(agency: Optional[CRMAgency]) -> bool:
    """دسترسی منشی به Hub بدون صندلی — با RBAC v2 همیشه؛ بدون آن فقط با flag آزمایشی."""
    if not agency:
        return False
    if is_agency_rbac_v2_enabled(agency):
        return True
    return is_agency_feature_enabled('agency_secretary_hub', agency)


def rbac_v2_enabled_for_user(user) -> bool:
    m = get_membership(user)
    if not m or not m.is_active:
        return False
    return is_agency_rbac_v2_enabled(m.agency)


def _template_for_stored_role(role: str) -> Set[str]:
    if role == AGENCY_ROLE_OWNER:
        return set(_OWNER_TEMPLATE)
    if role == AGENCY_ROLE_MANAGER:
        return set(_MANAGER_LEGACY_TEMPLATE)
    if role == AGENCY_ROLE_SECRETARY:
        return set(_SECRETARY_TEMPLATE)
    if role == AGENCY_ROLE_ADVISOR:
        return set(_ADVISOR_TEMPLATE)
    return set()


def _apply_overrides(base: Set[str], member: CRMAgencyMember) -> Set[str]:
    overrides = getattr(member, 'permission_overrides', None) or {}
    if not isinstance(overrides, dict):
        return base
    result = set(base)
    for key, val in overrides.items():
        if key not in ALL_PERMISSIONS:
            continue
        if key in NON_ASSIGNABLE_MEMBER_PERMISSIONS:
            continue
        if val is True:
            result.add(key)
        elif val is False:
            result.discard(key)
    return result


def _finalize_effective_permissions(
    user,
    member: CRMAgencyMember,
    perms: Set[str],
) -> Set[str]:
    """حذف مجوزهای مالک اشتراک از اعضایی که entitlement واقعی ندارند."""
    from workspace.services.agency_entitlement import can_manage_agency

    result = set(perms)
    if not can_manage_agency(user, member.agency):
        result -= OWNER_ENTITLEMENT_PERMISSIONS
    return result


def _owner_subscription_grants(user, member: CRMAgencyMember) -> Set[str]:
    from workspace.services.agency_entitlement import can_manage_agency

    extra: Set[str] = set()
    if can_manage_agency(user, member.agency):
        extra |= {PERM_LICENSES_MANAGE, PERM_TEAM_INVITE}
    return extra


def effective_permissions(user, member: Optional[CRMAgencyMember] = None) -> Set[str]:
    """مجوزهای مؤثر — فقط وقتی agency_rbac_v2 فعال است معنای کامل دارد."""
    m = member or get_membership(user)
    if not m or not m.is_active:
        return set()
    if not is_agency_rbac_v2_enabled(m.agency):
        return _legacy_permissions_as_set(user)
    base = _template_for_stored_role(m.role)
    perms = _apply_overrides(base, m)
    if m.role == AGENCY_ROLE_OWNER:
        perms |= _owner_subscription_grants(user, m)
        # مالک اشتراک بدون رکورد owner در تیم همچنان لایسنس دارد
    elif m.role == AGENCY_ROLE_MANAGER:
        perms |= _owner_subscription_grants(user, m) - {PERM_LICENSES_MANAGE}
    # محافظت: مالک آژانس (رکورد owner) همیشه دسترسی مدیریت تیم و تنظیمات را نگه می‌دارد
    if m.role == AGENCY_ROLE_OWNER and m.agency.owner_id == m.user_id:
        perms |= {PERM_TEAM_MANAGE, PERM_SETTINGS_MANAGE, PERM_LICENSES_MANAGE}
    return _finalize_effective_permissions(user, m, perms)


def _legacy_permissions_as_set(user) -> Set[str]:
    """نگاشت رفتار فعلی به مجموعه مجوز برای API یکسان."""
    perms: Set[str] = set()
    if can_manage_team(user):
        perms |= {
            PERM_TEAM_MANAGE,
            PERM_TEAM_VIEW_PERFORMANCE,
            PERM_TEAM_INVITE,
            PERM_SETTINGS_MANAGE,
            PERM_AUDIT_VIEW,
            PERM_AGENCY_SPACE_MODERATE,
            PERM_DEALS_VIEW_TEAM,
            PERM_CONTRACTS_VIEW_TEAM,
            PERM_REPORTS_SENSITIVE,
            PERM_HUB_OWNER_DASHBOARD,
        }
    if can_view_team_inbox(user):
        perms |= {PERM_INBOX_VIEW, PERM_INBOX_ASSIGN}
    from workspace.services.agency_entitlement import can_manage_agency, has_assigned_agency_seat

    if can_manage_agency(user):
        perms |= {PERM_LICENSES_MANAGE, PERM_TEAM_INVITE}
    m = get_membership(user)
    if m and m.role == AGENCY_ROLE_SECRETARY:
        perms |= {PERM_INBOX_VIEW, PERM_INBOX_ASSIGN, PERM_HUB_SECRETARY_DASHBOARD}
    if has_assigned_agency_seat(user):
        perms |= {PERM_HUB_ADVISOR_DASHBOARD, PERM_AGENCY_SPACE_PUBLISH}
    perms.add(PERM_AGENCY_SPACE_VIEW)
    return perms


def validate_invite_role(role: str) -> str:
    role = (role or AGENCY_ROLE_ADVISOR).strip()
    if role not in ASSIGNABLE_ROLE_CODES:
        raise ValueError('نقش دعوت مجاز نیست')
    return role


def validate_role_change(role: str) -> str:
    role = (role or '').strip()
    if role not in ASSIGNABLE_ROLE_CODES:
        raise ValueError('نقش انتخاب‌شده مجاز نیست')
    return role


def assert_agency_permission(user, permission: str, *, message: str = 'دسترسی مجاز نیست') -> None:
    if not has_agency_permission(user, permission):
        raise PermissionDenied(message)


def can_operate_team_inbox(user) -> bool:
    if rbac_v2_enabled_for_user(user):
        return has_agency_permission(user, PERM_INBOX_ASSIGN)
    return can_operate_team_leads(user)


def can_view_team_performance_data(user) -> bool:
    if rbac_v2_enabled_for_user(user):
        return has_agency_permission(user, PERM_TEAM_VIEW_PERFORMANCE)
    return can_manage_team(user)


def permission_choices_for_editor() -> list[tuple[str, str]]:
    return [
        (k, PERMISSION_LABELS[k])
        for k in sorted(PERMISSION_LABELS)
        if k in ALL_PERMISSIONS and k not in NON_ASSIGNABLE_MEMBER_PERMISSIONS
    ]


def has_agency_permission(user, permission: str, *, member: Optional[CRMAgencyMember] = None) -> bool:
    if permission not in ALL_PERMISSIONS:
        return False
    m = member or get_membership(user)
    if not m or not m.is_active:
        return False
    if not is_agency_rbac_v2_enabled(m.agency):
        return permission in _legacy_permissions_as_set(user)
    if permission in OWNER_ENTITLEMENT_PERMISSIONS:
        from workspace.services.agency_entitlement import can_manage_agency

        if not can_manage_agency(user, m.agency):
            return False
    return permission in effective_permissions(user, m)


def resolve_nav_profile(user) -> str:
    """پروفایل ناوبری/داشبورد — بدون تغییر role ذخیره‌شده در DB."""
    from workspace.services.agency_entitlement import can_manage_agency

    m = get_membership(user)
    if not m or not m.is_active:
        return ''
    if not is_agency_rbac_v2_enabled(m.agency):
        if can_manage_agency(user, m.agency) or can_manage_team(user):
            return NAV_PROFILE_OWNER
        if m.role == AGENCY_ROLE_SECRETARY:
            return NAV_PROFILE_SECRETARY
        return NAV_PROFILE_ADVISOR

    if m.role == AGENCY_ROLE_OWNER or can_manage_agency(user, m.agency):
        return NAV_PROFILE_OWNER
    if m.role == AGENCY_ROLE_MANAGER:
        return NAV_PROFILE_MANAGER_LEGACY
    if m.role == AGENCY_ROLE_SECRETARY:
        return NAV_PROFILE_SECRETARY
    return NAV_PROFILE_ADVISOR


def staff_can_access_agency_hub_without_seat(user) -> bool:
    """منشی/مدیر legacy با عضویت فعال — بدون نیاز به seat مشاور."""
    from workspace.services.agency_entitlement import get_subscription_for_agency

    m = get_membership(user)
    if not m or not m.is_active:
        return False
    if m.role == AGENCY_ROLE_SECRETARY:
        if not is_agency_secretary_hub_enabled(m.agency):
            return False
        return get_subscription_for_agency(m.agency) is not None
    if m.role == AGENCY_ROLE_MANAGER:
        if not is_agency_rbac_v2_enabled(m.agency):
            return False
        return get_subscription_for_agency(m.agency) is not None
    if m.role == AGENCY_ROLE_OWNER:
        return True
    return False


def serialize_permissions_for_api(user) -> Dict[str, Any]:
    m = get_membership(user)
    perms = effective_permissions(user, m)
    profile = resolve_nav_profile(user)
    role = m.role if m else ''
    role_labels = dict(CRMAgencyMember._meta.get_field('role').choices)
    rbac_on = bool(m and is_agency_rbac_v2_enabled(m.agency))
    if rbac_on and profile == NAV_PROFILE_ADVISOR:
        can_view_finance = True
    else:
        can_view_finance = has_agency_permission(user, PERM_FINANCE_VIEW, member=m)
    return {
        'role': role,
        'role_label': role_labels.get(role, role),
        'nav_profile': profile,
        'rbac_v2': rbac_on,
        'permissions': sorted(perms),
        'capabilities': {
            'can_manage_team': has_agency_permission(user, PERM_TEAM_MANAGE, member=m),
            'can_manage_licenses': has_agency_permission(user, PERM_LICENSES_MANAGE, member=m),
            'can_view_team_deals': has_agency_permission(user, PERM_DEALS_VIEW_TEAM, member=m),
            'can_view_team_contracts': has_agency_permission(user, PERM_CONTRACTS_VIEW_TEAM, member=m),
            'can_view_finance': can_view_finance,
            'can_view_inbox': has_agency_permission(user, PERM_INBOX_VIEW, member=m),
            'can_assign_inbox': has_agency_permission(user, PERM_INBOX_ASSIGN, member=m),
            'can_operate_inbox': can_operate_team_leads(user) if not rbac_on else (
                PERM_INBOX_ASSIGN in perms
            ),
        },
    }


def summarize_effective_permissions(user, member: Optional[CRMAgencyMember] = None, limit: int = 6) -> list[str]:
    perms = effective_permissions(user, member or get_membership(user))
    labels = [PERMISSION_LABELS.get(p, p) for p in sorted(perms)]
    if len(labels) > limit:
        return labels[:limit] + [f'+{len(labels) - limit} مورد دیگر']
    return labels


def clear_permission_overrides_for_role(member: CRMAgencyMember) -> None:
    member.permission_overrides = {}
    member.save(update_fields=['permission_overrides'])


def apply_member_role_preset(actor, member_id: int, preset: str) -> CRMAgencyMember:
    """اعمال الگوی نقش (منشی / مشاور) — نقش و overrideها بازنشانی می‌شوند."""
    from workspace.services.crm_agency import update_member_role

    preset = (preset or '').strip().lower()
    if preset == 'secretary':
        return update_member_role(actor, member_id, AGENCY_ROLE_SECRETARY)
    if preset == 'advisor':
        return update_member_role(actor, member_id, AGENCY_ROLE_ADVISOR)
    raise ValueError('الگوی نقش نامعتبر است')


def update_member_permission_overrides(
    actor,
    member_id: int,
    overrides: Dict[str, bool],
) -> CRMAgencyMember:
    from workspace.services.crm_audit import log_agency_audit

    if not has_agency_permission(actor, PERM_MEMBERS_PERMISSIONS_EDIT):
        raise ValueError('دسترسی ویرایش مجوز ندارید')
    actor_m = get_membership(actor)
    if not actor_m:
        raise ValueError('آژانس یافت نشد')
    member = CRMAgencyMember.objects.get(pk=member_id, agency=actor_m.agency, is_active=True)
    if member.role == AGENCY_ROLE_OWNER:
        raise ValueError('مجوز مالک قابل شخصی‌سازی نیست')
    clean: Dict[str, bool] = {}
    for k, v in (overrides or {}).items():
        if k in NON_ASSIGNABLE_MEMBER_PERMISSIONS:
            continue
        if k in ALL_PERMISSIONS and isinstance(v, bool):
            clean[k] = v
    member.permission_overrides = clean
    member.save(update_fields=['permission_overrides'])
    log_agency_audit(actor_m.agency, actor, 'member.permissions_updated', {
        'member_id': member.pk,
        'overrides': clean,
    })
    return member
