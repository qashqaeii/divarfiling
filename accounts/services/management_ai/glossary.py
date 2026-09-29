"""Product terminology and section playbooks for Management AI prompts."""
from __future__ import annotations

GLOSSARY_BLOCK = """
TERMINOLOGY (mandatory Persian product language):
- license / licenses → «لایسنس» (never: پروانه، پروانه فعالیت، مجوز فعالیت، پروانه کسب)
- CRM → CRM (keep Latin)
- retention → نرخ بازگشت / نگهداشت (match admin KPI wording)
- activation → فعال‌سازی
- renewal → تمدید (only when backend classifies as renewal; new key purchase by returning user is NOT renewal unless snapshot says so)
- churn → ریزش
- conversion → نرخ تبدیل
- Prefer labels already used in the admin panel snapshot metrics and facts.
""".strip()

_SECTION_PLAYBOOKS = {
    'users': """
USERS analysis order: Acquisition → Activation → Retention → License conversion.
Cross-check: users_new_period + signup_growth_rate + retention_d7/d30 + users_without_license + users_active_current.
If signups exist but retention is low and users_without_license is high, do NOT recommend more acquisition first — focus post-signup journey.
""",
    'licenses': """
LICENSES order: licenses_new_period → licenses_active → licenses_expiring_7d → licenses_expired → renewals_period → renewal_rate_period → renewal_revenue → churn-risk facts.
Distinguish new license sales from renewal. Use renewal_breakdown when present; do not call repurchase «تمدید» unless formal_renewals or facts say so.
""",
    'crm': """
CRM order: eligible/adoption → crm_active_users_period → non-users → abandoned users (facts) → contacts/deals → reminders.
Never compare overdue_reminders (stock backlog) with reminders_created_period (flow in selected days) as direct cohort comparison unless metric_semantics allow it.
""",
    'sales': """
SALES: revenue_range + paid_orders_range + AOV + conversion_rate + pending/failed payment metrics; relate revenue to orders before recommending pricing changes.
""",
    'executive': """
EXECUTIVE: only cross-section KPIs provided; synthesize top risks/actions across users/sales/licenses/crm without inventing detail missing from snapshot.
""",
}


def section_playbook(section: str) -> str:
    return _SECTION_PLAYBOOKS.get(section, '').strip()
