"""Executive insights + decision cards + recommendations + predictive scores."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.services.plan_bi import EMPTY_MSG, MIN_SAMPLE, comparison_status, delta_pct, safe_div
from licenses.models import License
from shop.models import Order


def build_executive_insights(
    *,
    summary: dict,
    prev_summary: dict,
    plan_rows: list[dict],
    activation_funnel: dict,
    purchase_funnel: dict,
    upgrade_stats: dict,
) -> list[dict[str, Any]]:
    insights: list[dict[str, Any]] = []

    cur_rev = summary.get('paid_revenue', 0)
    prev_rev = prev_summary.get('paid_revenue', 0)
    d = delta_pct(cur_rev, prev_rev)
    status = comparison_status(cur_rev, prev_rev)
    if status == 'new_activity':
        insights.append({
            'severity': 'ok',
            'title': 'شروع فروش در این دوره',
            'body': 'دوره قبل فروش ثبت نشده؛ درصد رشد قابل اتکا نیست.',
            'metric': None,
            'delta_pct': None,
            'comparison_status': status,
        })
    elif d is not None and (cur_rev > 0 or prev_rev > 0):
        direction = 'رشد' if d >= 0 else 'افت'
        insights.append({
            'severity': 'ok' if d >= 0 else 'warn',
            'title': f'درآمد نسبت به دوره قبل {abs(d)}٪ {direction}',
            'body': f'درآمد این دوره {cur_rev:,} تومان در برابر {prev_rev:,} تومان دوره قبل.',
            'metric': d,
            'delta_pct': d,
            'comparison_status': status,
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
                'severity': 'medium',
                'title': f"بدون فروش در دوره برای «{zp['short_label']}»",
                'body': 'پیشنهاد می‌شود روی این پلن کمپین یا اصلاح قیمت/پیام تمرکز شود.',
                'metric': 0,
            })

    if upgrade_stats.get('available') and upgrade_stats.get('daily_buyers', 0) > 0:
        rate = upgrade_stats.get('upgrade_rate')
        if rate is not None:
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

    drop = activation_funnel.get('biggest_dropoff') or purchase_funnel.get('biggest_dropoff')
    if drop and drop.get('dropoff', 0) >= 40:
        insights.append({
            'severity': 'critical',
            'title': f"بیشترین ریزش در «{drop['label']}» ({drop['dropoff']}٪)",
            'body': 'این مرحله اولویت بهینه‌سازی قیف است.',
            'metric': drop['dropoff'],
        })

    if not summary.get('funnel_conversions_available', True):
        insights.append({
            'severity': 'warn',
            'title': 'نرخ تبدیل قیف خرید موقتاً غیرفعال',
            'body': summary.get('data_quality', {}).get('coverage_message') or EMPTY_MSG,
            'metric': None,
        })

    order = {'critical': 0, 'warn': 1, 'medium': 2, 'ok': 3, 'neutral': 4}
    insights.sort(key=lambda i: order.get(i['severity'], 9))
    return insights[:7]


def build_decision_cards(
    *,
    summary: dict,
    prev_summary: dict,
    plan_rows: list[dict],
    activation_funnel: dict,
    purchase_funnel: dict,
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
            'delta': None,
            'comparison_status': 'new_activity' if best['purchases'] else 'no_activity',
            'status': 'ok' if best['purchases'] else 'neutral',
            'hint': f"{best['purchases']} فروش · {best['revenue']:,} ت",
        })
        cards.append({
            'key': 'weakest_plan',
            'title': 'ضعیف‌ترین پلن',
            'value': worst['short_label'],
            'metric': worst['purchases'],
            'delta': None,
            'status': 'warn' if worst['purchases'] == 0 else 'warn',
            'hint': 'بدون فروش در دوره' if worst['purchases'] == 0 else f"{worst['purchases']} فروش",
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
        'title': 'بیشترین ریزش قیف فعال‌سازی',
        'value': f"{drop['dropoff']}٪" if drop else EMPTY_MSG,
        'metric': drop['dropoff'] if drop else None,
        'delta': None,
        'status': 'critical' if drop and drop['dropoff'] >= 50 else ('warn' if drop else 'neutral'),
        'hint': drop['label'] if drop else EMPTY_MSG,
        'available': bool(drop),
    })

    cards.append({
        'key': 'upgrade_opportunity',
        'title': 'فرصت ارتقا (Outcome)',
        'value': f"{upgrade_stats.get('upgrade_rate')}٪" if upgrade_stats.get('available') and upgrade_stats.get('upgrade_rate') is not None else EMPTY_MSG,
        'metric': upgrade_stats.get('upgrade_rate'),
        'delta': None,
        'status': 'warn' if upgrade_stats.get('available') and (upgrade_stats.get('upgrade_rate') or 0) < 15 else 'ok',
        'hint': (
            f"{upgrade_stats.get('upgrade_count', 0)} از {upgrade_stats.get('daily_buyers', 0)} خریدار روزانه"
            if upgrade_stats.get('available') else EMPTY_MSG
        ),
        'available': upgrade_stats.get('available', False),
    })

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
    arpu_delta = delta_pct(arpu, prev_arpu)
    arpu_cmp = comparison_status(arpu, prev_arpu)
    cards.append({
        'key': 'arpu',
        'title': 'ارزش هر مشتری (ARPU دوره)',
        'value': f"{arpu:,} ت" if summary.get('unique_buyers') else EMPTY_MSG,
        'metric': arpu,
        'delta': arpu_delta,
        'comparison_status': arpu_cmp,
        'delta_label': 'شروع فروش در این دوره' if arpu_cmp == 'new_activity' else None,
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

    overall = summary.get('overall_conversion')
    cards.append({
        'key': 'overall_conversion',
        'title': 'نرخ تبدیل کلی',
        'value': f'{overall}٪' if overall is not None else EMPTY_MSG,
        'metric': overall,
        'delta': None,
        'status': 'neutral' if overall is None else 'ok',
        'hint': 'فقط با پوشش Tracking کافی',
        'available': overall is not None,
    })

    rev_delta = delta_pct(summary.get('paid_revenue', 0), prev_summary.get('paid_revenue', 0))
    rev_cmp = comparison_status(summary.get('paid_revenue', 0), prev_summary.get('paid_revenue', 0))
    cards.append({
        'key': 'revenue_trend',
        'title': 'روند درآمد دوره',
        'value': f"{summary.get('paid_revenue', 0):,} ت",
        'metric': summary.get('paid_revenue', 0),
        'delta': rev_delta,
        'comparison_status': rev_cmp,
        'delta_label': 'دوره قبل فروش ثبت نشده' if rev_cmp == 'new_activity' else None,
        'status': 'ok' if rev_cmp in ('up', 'flat', 'new_activity') else 'warn',
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
            # سالانه بدون view کافی → info/medium نه critical
            sev = 'medium'
            if r['plan_type'] == 'yearly' and not r.get('conversion_available'):
                sev = 'info'
            recs.append({
                'severity': sev,
                'title': f"پلن «{r['short_label']}» بدون فروش در دوره",
                'body': 'قیمت، جایگاه در صفحه قیمت، یا پیشنهاد ارزش را بازبینی کنید.',
                'action_hint': 'A/B پیام فروش یا تخفیف محدود',
            })

    drop = activation_funnel.get('biggest_dropoff')
    if drop and drop.get('dropoff', 0) >= 50:
        key = drop.get('key', '')
        if key == 'first_crm_use':
            action = (
                'ساده‌سازی معرفی CRM بعد از اولین Dataset؛ CTA ساخت اولین مخاطب؛ '
                'راهنمای کوتاه داخل محصول؛ Template آماده ثبت مشتری؛ اتصال فایل مناسب به مخاطب'
            )
            body = 'ریزش در ورود به CRM است — مسیر onboarding مخاطب را کوتاه کنید.'
        elif key == 'license_activated':
            action = 'بررسی راهنمای فعال‌سازی لایسنس و پشتیبانی نصب'
            body = 'کاربران پس از خرید لایسنس را فعال نمی‌کنند.'
        elif key == 'first_extract_or_dataset':
            action = 'CTA استخراج اول / ساخت دیتاست بلافاصله پس از فعال‌سازی'
            body = 'شکاف بین فعال‌سازی و اولین استخراج را کم کنید.'
        elif key == 'app_first_launch':
            action = 'بهبود پوشش Tracking اولین اجرا و راهنمای نصب اپ'
            body = 'ممکن است Tracking ناقص باشد یا کاربران اپ را باز نکرده باشند.'
        else:
            action = f'بهینه‌سازی مرحله «{drop["label"]}»'
            body = 'این مرحله را اولویت بهینه‌سازی UX قرار دهید.'
        recs.append({
            'severity': 'critical',
            'title': f"ریزش بالای قیف در «{drop['label']}»",
            'body': body,
            'action_hint': action,
        })

    if (
        upgrade_stats.get('available')
        and upgrade_stats.get('daily_buyers', 0) > 0
        and (upgrade_stats.get('upgrade_rate') or 0) < 12
    ):
        recs.append({
            'severity': 'medium',
            'title': 'نرخ ارتقا روزانه→ماهانه پایین است',
            'body': 'یادآور روز ۲ و روز ۵ پس از خرید پلن یک‌روزه پیشنهاد می‌شود.',
            'action_hint': 'اتوماسیون nurture ارتقا',
        })

    for c in behavior.get('correlations') or []:
        if c.get('available') and 'CRM' in c.get('title', '') and (c.get('ltv_ratio') or 0) >= 1.3:
            recs.append({
                'severity': 'low',
                'title': 'مشاهده: کاربران CRM ارزش بالاتری دارند',
                'body': c.get('body', ''),
                'action_hint': (
                    'ساده‌سازی معرفی CRM بعد از اولین Dataset؛ نمایش CTA ساخت اولین مخاطب؛ '
                    'Template آماده ثبت مشتری'
                ),
            })
            break

    if summary.get('checkout_views', 0) > 0 and summary.get('paid_count', 0) == 0:
        recs.append({
            'severity': 'critical',
            'title': 'Checkout بدون پرداخت موفق در دوره',
            'body': 'موانع پرداخت یا اعتماد را بررسی کنید.',
            'action_hint': 'بررسی سفارش‌های failed و pending_stale',
        })

    if not recs:
        recs.append({
            'severity': 'low',
            'title': 'وضعیت پایدار',
            'body': 'هشدار بحرانی فعالی نیست؛ روی رشد پلن‌های کم‌فروش تمرکز کنید.',
            'action_hint': 'مرور ماتریس پلن‌ها',
        })

    order = {'critical': 0, 'medium': 1, 'info': 2, 'low': 3}
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
            'confidence': 'low',
            'sample_size': n,
        }

    features = {f['key']: f for f in behavior.get('features') or [] if f.get('available')}

    def rate(key, default=0.0):
        f = features.get(key)
        return float(f['rate']) if f and f.get('rate') is not None else default

    crm_r = rate('crm')
    ds_r = rate('dataset')
    ret30 = rate('return_30d')
    act_r = rate('activated')
    up_r = upgrade_stats.get('upgrade_rate') if upgrade_stats.get('available') else None
    up_r = float(up_r) if up_r is not None else rate('upgraded')

    renewal = min(100, round(0.35 * ret30 + 0.35 * crm_r + 0.30 * ds_r))
    upgrade = min(100, round(up_r * 2 if up_r < 40 else 40 + up_r))
    churn = min(100, round(100 - (0.4 * ret30 + 0.3 * crm_r + 0.3 * ds_r)))
    health = min(100, round(0.25 * ds_r + 0.25 * crm_r + 0.25 * ret30 + 0.25 * act_r))
    upsell = min(100, round(0.5 * (100 - up_r) * 0.4 + 0.3 * crm_r + 0.3 * ds_r))

    def score_obj(key, label, score, *, definition, positive, negative, weights):
        return {
            'key': key,
            'label': label,
            'score': score,
            'status': 'ok' if score >= 40 else 'warn',
            'definition': definition,
            'rule_breakdown': weights,
            'positive_factors': positive,
            'negative_factors': negative,
            'confidence': 'low' if n < 30 else ('medium' if n < 100 else 'sufficient'),
            'sample_size': n,
        }

    scores = [
        score_obj(
            'renewal',
            'Renewal Readiness Score',
            renewal,
            definition='شاخص آمادگی تمدید مبتنی بر Return ۳۰روز، CRM و Dataset (Rule-based، نه احتمال کالیبره)',
            positive=[f'Return30={ret30}%', f'CRM={crm_r}%', f'Dataset={ds_r}%'],
            negative=[] if renewal >= 40 else ['سیگنال بازگشت/CRM پایین'],
            weights={'return_30d': 0.35, 'crm': 0.35, 'dataset': 0.30},
        ),
        score_obj(
            'upgrade',
            'Upgrade Readiness Score',
            upgrade,
            definition='شاخص آمادگی ارتقا روزانه→ماهانه بر اساس نرخ ارتقای مشاهده‌شده',
            positive=[f'upgrade_rate={up_r}%'],
            negative=[] if upgrade >= 25 else ['نرخ ارتقا پایین'],
            weights={'upgrade_rate_scaled': 1.0},
        ),
        score_obj(
            'churn',
            'Churn Risk Indicator',
            churn,
            definition='شاخص ریسک ریزش = معکوس ترکیب Return/CRM/Dataset',
            positive=[],
            negative=[f'low_return={ret30}%', f'low_crm={crm_r}%'] if churn >= 60 else [],
            weights={'return_30d': -0.4, 'crm': -0.3, 'dataset': -0.3},
        ),
        score_obj(
            'health',
            'Customer Health Index',
            health,
            definition='میانگین وزن‌دار Dataset، CRM، Return30، Activation',
            positive=[f'Dataset={ds_r}%', f'CRM={crm_r}%', f'Return30={ret30}%', f'Activated={act_r}%'],
            negative=[],
            weights={'dataset': 0.25, 'crm': 0.25, 'return_30d': 0.25, 'activated': 0.25},
        ),
        score_obj(
            'upsell',
            'Upsell Opportunity Index',
            upsell,
            definition='فرصت فروش مجدد بر اساس فاصله از ارتقا + سیگنال استفاده',
            positive=[f'CRM={crm_r}%', f'Dataset={ds_r}%'],
            negative=[],
            weights={'inverse_upgrade': 0.4, 'crm': 0.3, 'dataset': 0.3},
        ),
    ]
    return {
        'available': True,
        'sample_size': n,
        'confidence': 'low' if n < 30 else ('medium' if n < 100 else 'sufficient'),
        'scores': scores,
        'note': 'این‌ها شاخص Rule-based هستند، نه Probability کالیبره‌شده.',
    }
