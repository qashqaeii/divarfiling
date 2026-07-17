"""Executive insights + decision cards + recommendations + predictive scores."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.services.plan_bi import EMPTY_MSG, MIN_SAMPLE, delta_pct, pct, safe_div
from licenses.models import License
from shop.models import Order


def build_executive_insights(
    *,
    summary: dict,
    prev_summary: dict,
    plan_rows: list[dict],
    activation_funnel: dict,
    upgrade_stats: dict,
) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []

    cur_rev = summary.get('paid_revenue', 0)
    prev_rev = prev_summary.get('paid_revenue', 0)
    d = delta_pct(cur_rev, prev_rev)
    if d is not None and (cur_rev > 0 or prev_rev > 0):
        direction = 'رشد' if d >= 0 else 'افت'
        insights.append({
            'severity': 'ok' if d >= 0 else 'warn',
            'title': f'درآمد نسبت به دوره قبل {abs(d)}٪ {direction}',
            'body': f'درآمد این دوره {cur_rev:,} تومان در برابر {prev_rev:,} تومان دوره قبل.',
            'metric': d,
            'delta_pct': d,
        })

    if plan_rows:
        top = max(plan_rows, key=lambda r: r['revenue'])
        if top['revenue'] > 0:
            insights.append({
                'severity': 'warn' if top['revenue_share'] >= 70 else 'ok',
                'title': f"{top['revenue_share']}٪ درآمد از «{top['short_label']}»",
                'body': (
                    'درآمد بیش از حد وابسته به یک پلن است؛ تنوع فروش را بررسی کنید.'
                    if top['revenue_share'] >= 70
                    else f"سهم غالب فروش متعلق به {top['short_label']} است."
                ),
                'metric': top['revenue_share'],
            })

        zero_plans = [r for r in plan_rows if r['purchases'] == 0]
        for zp in zero_plans[:2]:
            insights.append({
                'severity': 'critical' if zp['plan_type'] == 'yearly' else 'medium',
                'title': f"هیچ فروشی برای «{zp['short_label']}» ثبت نشده",
                'body': 'پیشنهاد می‌شود روی این پلن کمپین یا اصلاح قیمت/پیام تمرکز شود.',
                'metric': 0,
            })

    # فقط وقتی خریدار پلن روزانه (یک‌روزه) در دوره هست — «۷ روز» پلن نیست، پنجره تشخیص است
    if upgrade_stats.get('available') and upgrade_stats.get('daily_buyers', 0) > 0:
        rate = upgrade_stats.get('upgrade_rate', 0)
        insights.append({
            'severity': 'warn' if rate < 15 else 'ok',
            'title': f"نرخ ارتقا روزانه→ماهانه {rate}٪",
            'body': (
                f"از {upgrade_stats.get('daily_buyers', 0)} خریدار پلن یک‌روزه؛ "
                + (
                    'پایین‌تر از حد انتظار است؛ یادآور پس از خرید روزانه پیشنهاد می‌شود.'
                    if rate < 15 else
                    'نرخ ارتقا در محدوده قابل قبول است.'
                )
            ),
            'metric': rate,
        })

    drop = activation_funnel.get('biggest_dropoff')
    if drop and drop.get('key') != 'upgraded' and drop.get('dropoff', 0) >= 40:
        insights.append({
            'severity': 'critical',
            'title': f"بیشترین ریزش در «{drop['label']}» ({drop['dropoff']}٪)",
            'body': 'این مرحله اولویت بهینه‌سازی قیف است.',
            'metric': drop['dropoff'],
        })

    # Keep top 7 by severity
    order = {'critical': 0, 'warn': 1, 'medium': 2, 'ok': 3, 'neutral': 4}
    insights.sort(key=lambda i: order.get(i['severity'], 9))
    return insights[:7]


def build_decision_cards(
    *,
    summary: dict,
    prev_summary: dict,
    plan_rows: list[dict],
    activation_funnel: dict,
    upgrade_stats: dict,
    buyers: dict,
) -> list[dict[str, Any]]:
    cards = []

    if plan_rows:
        best = max(plan_rows, key=lambda r: r['purchases'])
        worst = min(plan_rows, key=lambda r: (r['purchases'], -r['price']))
        top_rev = max(plan_rows, key=lambda r: r['revenue'])
        cards.append({
            'key': 'best_plan',
            'title': 'بهترین پلن فروش',
            'value': best['short_label'],
            'metric': best['purchases'],
            'delta': delta_pct(best['purchases'], 0),
            'status': 'ok' if best['purchases'] else 'neutral',
            'hint': f"{best['purchases']} فروش · {best['revenue']:,} ت",
        })
        cards.append({
            'key': 'weakest_plan',
            'title': 'ضعیف‌ترین پلن',
            'value': worst['short_label'],
            'metric': worst['purchases'],
            'delta': None,
            'status': 'critical' if worst['purchases'] == 0 else 'warn',
            'hint': 'بدون فروش' if worst['purchases'] == 0 else f"{worst['purchases']} فروش",
        })
        cards.append({
            'key': 'top_revenue',
            'title': 'بیشترین درآمد',
            'value': f"{top_rev['revenue']:,} ت",
            'metric': top_rev['revenue'],
            'delta': None,
            'status': 'ok',
            'hint': top_rev['short_label'],
        })

    drop = activation_funnel.get('biggest_dropoff')
    cards.append({
        'key': 'biggest_drop',
        'title': 'بیشترین ریزش قیف',
        'value': f"{drop['dropoff']}٪" if drop else EMPTY_MSG,
        'metric': drop['dropoff'] if drop else None,
        'delta': None,
        'status': 'critical' if drop and drop['dropoff'] >= 50 else ('warn' if drop else 'neutral'),
        'hint': drop['label'] if drop else EMPTY_MSG,
        'available': bool(drop),
    })

    cards.append({
        'key': 'upgrade_opportunity',
        'title': 'بهترین فرصت ارتقا',
        'value': f"{upgrade_stats.get('upgrade_rate', 0)}٪" if upgrade_stats.get('available') else EMPTY_MSG,
        'metric': upgrade_stats.get('upgrade_rate'),
        'delta': None,
        'status': 'warn' if upgrade_stats.get('available') and upgrade_stats.get('upgrade_rate', 0) < 15 else 'ok',
        'hint': (
            f"{upgrade_stats.get('upgrade_count', 0)} از {upgrade_stats.get('daily_buyers', 0)} خریدار روزانه"
            if upgrade_stats.get('available') else EMPTY_MSG
        ),
        'available': upgrade_stats.get('available', False),
    })

    # Churn risk: licenses expiring in 7d without newer paid order
    now = timezone.now()
    expiring = License.objects.filter(
        status='active',
        expires_at__gte=now,
        expires_at__lte=now + timedelta(days=7),
    ).select_related('order', 'order__user')
    risk_count = 0
    for lic in expiring[:500]:
        uid = lic.order.user_id if lic.order_id else None
        if not uid:
            continue
        has_newer = Order.objects.filter(
            user_id=uid, status='paid',
        ).annotate(
            effective_paid=Coalesce('paid_at', 'created_at'),
        ).filter(effective_paid__gt=lic.expires_at - timedelta(days=30)).exclude(
            id=lic.order_id,
        ).exists()
        if not has_newer:
            risk_count += 1

    cards.append({
        'key': 'churn_risk',
        'title': 'ریسک از دست دادن مشتری',
        'value': str(risk_count),
        'metric': risk_count,
        'delta': None,
        'status': 'critical' if risk_count >= 5 else ('warn' if risk_count else 'ok'),
        'hint': 'لایسنس فعال با انقضای ≤۷ روز بدون تمدید',
    })

    arpu = safe_div(summary.get('paid_revenue', 0), summary.get('unique_buyers', 0))
    prev_arpu = safe_div(prev_summary.get('paid_revenue', 0), prev_summary.get('unique_buyers', 0))
    cards.append({
        'key': 'arpu',
        'title': 'ارزش هر مشتری (ARPU)',
        'value': f"{arpu:,} ت" if summary.get('unique_buyers') else EMPTY_MSG,
        'metric': arpu,
        'delta': delta_pct(arpu, prev_arpu),
        'status': 'ok',
        'hint': 'درآمد ÷ خریداران یکتا در دوره',
        'available': bool(summary.get('unique_buyers')),
    })

    avg_up_h = upgrade_stats.get('avg_upgrade_hours')
    cards.append({
        'key': 'avg_upgrade_time',
        'title': 'میانگین زمان ارتقا',
        'value': f"{avg_up_h} ساعت" if avg_up_h is not None else EMPTY_MSG,
        'metric': avg_up_h,
        'delta': None,
        'status': 'neutral' if avg_up_h is None else 'ok',
        'hint': 'از خرید روزانه تا ماهانه',
        'available': avg_up_h is not None,
    })

    cards.append({
        'key': 'avg_time_to_purchase',
        'title': 'میانگین زمان خرید',
        'value': EMPTY_MSG,
        'metric': None,
        'delta': None,
        'status': 'neutral',
        'hint': 'نیاز به join نشست ناشناس→خرید (هنوز پوشش کافی نیست)',
        'available': False,
    })

    rev_delta = delta_pct(summary.get('paid_revenue', 0), prev_summary.get('paid_revenue', 0))
    cards.append({
        'key': 'revenue_trend',
        'title': 'روند درآمد دوره',
        'value': f"{summary.get('paid_revenue', 0):,} ت",
        'metric': summary.get('paid_revenue', 0),
        'delta': rev_delta,
        'status': 'ok' if (rev_delta or 0) >= 0 else 'warn',
        'hint': 'مقایسه با دوره قبلی هم‌طول',
    })

    return cards


def build_recommendations(
    *,
    summary: dict,
    plan_rows: list[dict],
    activation_funnel: dict,
    upgrade_stats: dict,
    behavior: dict,
    decision_cards: list[dict],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    churn = next((c for c in decision_cards if c['key'] == 'churn_risk'), None)
    if churn and (churn.get('metric') or 0) > 0:
        sev = 'critical' if churn['metric'] >= 5 else 'medium'
        recs.append({
            'severity': sev,
            'title': f"{churn['metric']} لایسنس تا ۷ روز دیگر منقضی می‌شود",
            'body': 'کمپین تمدید فوری پیشنهاد می‌شود.',
            'action_hint': 'ساخت کمپین SMS تمدید از پنل بازاریابی',
        })

    for r in plan_rows:
        if r['purchases'] == 0:
            recs.append({
                'severity': 'critical' if r['plan_type'] == 'yearly' else 'medium',
                'title': f"پلن «{r['short_label']}» بدون فروش",
                'body': 'قیمت، جایگاه در صفحه قیمت، یا پیشنهاد ارزش را بازبینی کنید.',
                'action_hint': 'A/B پیام فروش یا تخفیف محدود',
            })

    drop = activation_funnel.get('biggest_dropoff')
    if drop and drop.get('dropoff', 0) >= 50:
        recs.append({
            'severity': 'critical',
            'title': f"ریزش بالای قیف در «{drop['label']}»",
            'body': 'این مرحله را اولویت بهینه‌سازی UX و پیام قرار دهید.',
            'action_hint': 'بررسی صفحه Checkout / فعال‌سازی',
        })

    if (
        upgrade_stats.get('available')
        and upgrade_stats.get('daily_buyers', 0) > 0
        and upgrade_stats.get('upgrade_rate', 0) < 12
    ):
        recs.append({
            'severity': 'medium',
            'title': 'نرخ ارتقا روزانه→ماهانه پایین است',
            'body': 'یادآور روز ۲ و روز ۵ پس از خرید پلن یک‌روزه پیشنهاد می‌شود.',
            'action_hint': 'اتوماسیون nurture ارتقا',
        })

    # CRM users renew better - from correlations
    for c in behavior.get('correlations') or []:
        if c.get('available') and 'CRM' in c.get('title', '') and (c.get('ltv_ratio') or 0) >= 1.3:
            recs.append({
                'severity': 'low',
                'title': 'کاربران CRM ارزش بالاتری دارند',
                'body': c.get('body', ''),
                'action_hint': 'هل دادن خریداران جدید به ساخت اولین مخاطب CRM',
            })
            break

    if summary.get('checkout_views', 0) > 0 and summary.get('paid_count', 0) == 0:
        recs.append({
            'severity': 'critical',
            'title': 'Checkout بدون پرداخت موفق در دوره',
            'body': 'موانع پرداخت یا اعتماد را بررسی کنید.',
            'action_hint': 'بررسی سفارش‌های failed و pending',
        })

    if not recs:
        recs.append({
            'severity': 'low',
            'title': 'وضعیت پایدار',
            'body': 'هشدار بحرانی فعالی نیست؛ روی رشد پلن‌های کم‌فروش تمرکز کنید.',
            'action_hint': 'مرور ماتریس پلن‌ها',
        })

    order = {'critical': 0, 'medium': 1, 'low': 2}
    recs.sort(key=lambda r: order.get(r['severity'], 9))
    return recs[:8]


def build_predictive_scores(
    *,
    summary: dict,
    buyers: dict,
    behavior: dict,
    upgrade_stats: dict,
) -> dict[str, Any]:
    n = buyers.get('unique_buyers', 0)
    if n < MIN_SAMPLE:
        return {
            'available': False,
            'display': EMPTY_MSG,
            'scores': [],
            'note': f'برای امتیازدهی حداقل {MIN_SAMPLE} خریدار یکتا لازم است',
        }

    features = {f['key']: f for f in behavior.get('features') or [] if f.get('available')}

    def rate(key, default=0.0):
        f = features.get(key)
        return float(f['rate']) if f and f.get('rate') is not None else default

    crm_r = rate('crm')
    ds_r = rate('dataset')
    ret30 = rate('return_30d')
    up_r = upgrade_stats.get('upgrade_rate') or rate('upgraded')

    # Simple 0-100 scores
    renewal_prob = min(100, round(0.35 * ret30 + 0.35 * crm_r + 0.30 * ds_r))
    upgrade_prob = min(100, round(up_r * 2 if up_r < 40 else 40 + up_r))
    churn_risk = min(100, round(100 - (0.4 * ret30 + 0.3 * crm_r + 0.3 * ds_r)))
    health = min(100, round(0.25 * ds_r + 0.25 * crm_r + 0.25 * ret30 + 0.25 * rate('activated')))
    upsell = min(100, round(0.5 * (100 - up_r) * 0.4 + 0.3 * crm_r + 0.3 * ds_r))

    scores = [
        {'key': 'renewal', 'label': 'احتمال تمدید', 'score': renewal_prob, 'status': 'ok' if renewal_prob >= 40 else 'warn'},
        {'key': 'upgrade', 'label': 'احتمال ارتقا', 'score': upgrade_prob, 'status': 'ok' if upgrade_prob >= 25 else 'warn'},
        {'key': 'churn', 'label': 'ریسک ریزش', 'score': churn_risk, 'status': 'critical' if churn_risk >= 60 else 'warn'},
        {'key': 'health', 'label': 'سلامت مشتری', 'score': health, 'status': 'ok' if health >= 45 else 'warn'},
        {'key': 'upsell', 'label': 'فرصت فروش مجدد', 'score': upsell, 'status': 'ok'},
    ]
    return {
        'available': True,
        'sample_size': n,
        'scores': scores,
        'note': 'امتیازها Rule-based هستند و جایگزین مدل ML نیستند.',
    }
