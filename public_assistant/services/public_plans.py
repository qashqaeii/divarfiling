"""اطلاعات عمومی و زنده پلن‌های فروشگاه — بدون داده حساب کاربر."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from shop.bot_catalog import get_bot_product, get_bot_product_buy_url
from shop.models import LicensePlan, Product
from shop.services.plan_pricing import (
    AGENCY_MAX_QUANTITY,
    AGENCY_MIN_QUANTITY,
    calculate_plan_pricing,
    get_agency_bulk_discount_percent,
)
from workspace.services.formatting import format_toman

PlanSegment = Literal['trial', 'personal', 'agency']

_PLAN_TYPE_LABELS = {
    'daily': 'آزمایشی ۷روزه (خریدنی)',
    'monthly': 'یک‌ماهه',
    'quarterly': 'سه‌ماهه',
    'yearly': 'یک‌ساله',
}


@dataclass(frozen=True)
class PublicPlanInfo:
    id: int
    name: str
    plan_type: str
    segment: PlanSegment
    duration_days: int | None
    price: int
    compare_at_price: int | None
    tagline: str
    feature_texts: list[str]
    max_activations: int
    min_quantity: int
    max_quantity: int
    allow_bulk_purchase: bool
    buy_url: str
    duration_label: str


@dataclass(frozen=True)
class PublicPlanCatalog:
    product_slug: str
    product_title: str
    product_buy_url: str
    trial: PublicPlanInfo | None
    personal: tuple[PublicPlanInfo, ...]
    agency: tuple[PublicPlanInfo, ...]

    def personal_by_type(self, plan_type: str) -> PublicPlanInfo | None:
        for p in self.personal:
            if p.plan_type == plan_type:
                return p
        return None

    def agency_by_type(self, plan_type: str) -> PublicPlanInfo | None:
        for p in self.agency:
            if p.plan_type == plan_type:
                return p
        return None


def _segment_for(plan: LicensePlan) -> PlanSegment:
    if plan.allow_bulk_purchase:
        return 'agency'
    if plan.plan_type == 'daily':
        return 'trial'
    return 'personal'


def _duration_label(plan: LicensePlan) -> str:
    if plan.duration_days:
        return f'{plan.duration_days} روز'
    return _PLAN_TYPE_LABELS.get(plan.plan_type, plan.plan_type)


def _plan_to_info(plan: LicensePlan, product: Product) -> PublicPlanInfo:
    features = [f['text'] for f in plan.normalized_features() if f.get('text')]
    compare = int(plan.compare_at_price) if plan.compare_at_price else None
    return PublicPlanInfo(
        id=plan.id,
        name=plan.name,
        plan_type=plan.plan_type,
        segment=_segment_for(plan),
        duration_days=plan.duration_days,
        price=int(plan.price),
        compare_at_price=compare,
        tagline=(plan.tagline or '').strip(),
        feature_texts=features,
        max_activations=int(plan.max_activations or 1),
        min_quantity=int(plan.min_quantity or 1),
        max_quantity=int(plan.max_quantity or AGENCY_MAX_QUANTITY),
        allow_bulk_purchase=bool(plan.allow_bulk_purchase),
        buy_url=get_bot_product_buy_url(plan.id),
        duration_label=_duration_label(plan),
    )


def load_public_plan_catalog() -> PublicPlanCatalog | None:
    """پلن‌های فعال محصول ربات استخراج — در صورت نبود محصول/پلن، None."""
    product = get_bot_product()
    if not product:
        return None
    plans = list(
        LicensePlan.objects.filter(product=product, is_active=True).order_by('order', 'price')
    )
    if not plans:
        return None

    trial: PublicPlanInfo | None = None
    personal: list[PublicPlanInfo] = []
    agency: list[PublicPlanInfo] = []
    for plan in plans:
        info = _plan_to_info(plan, product)
        if info.segment == 'trial':
            trial = info
        elif info.segment == 'agency':
            agency.append(info)
        else:
            personal.append(info)

    return PublicPlanCatalog(
        product_slug=product.slug,
        product_title=product.title,
        product_buy_url=get_bot_product_buy_url(),
        trial=trial,
        personal=tuple(personal),
        agency=tuple(agency),
    )


def get_plan_model(catalog: PublicPlanCatalog, plan_id: int) -> LicensePlan | None:
    product = get_bot_product()
    if not product:
        return None
    return LicensePlan.objects.filter(pk=plan_id, product=product, is_active=True).first()


def public_plan_quote(
    catalog: PublicPlanCatalog,
    plan_info: PublicPlanInfo,
    *,
    quantity: int = 1,
) -> dict | None:
    """قیمت عمومی بدون کاربر — فقط تخفیف حجمی آژانس."""
    product = get_bot_product()
    if not product:
        return None
    plan = get_plan_model(catalog, plan_info.id)
    if not plan:
        return None
    return calculate_plan_pricing(plan, product, None, request=None, quantity=quantity)


def agency_bulk_note() -> str:
    return (
        'تخفیف حجمی آژانس برای خرید آنلاین ۲ تا ۲۵ لایسنس اعمال می‌شود. '
        'مبلغ نهایی در checkout ممکن است برای کاربران واردشده تحت تأثیر تخفیف خرید مجدد، '
        'معرف یا کد تخفیف باشد — بدون ورود به حساب فقط تخفیف گروهی همین سفارش را قطعی می‌گوییم.'
    )


def compare_personal_duration_savings(catalog: PublicPlanCatalog) -> list[dict]:
    """صرفه‌جویی پلن‌های شخصی نسبت به خرید تک‌ماهه."""
    monthly = catalog.personal_by_type('monthly')
    if not monthly:
        return []
    product = get_bot_product()
    if not product:
        return []
    monthly_plan = get_plan_model(catalog, monthly.id)
    if not monthly_plan:
        return []

    monthly_price = int(monthly.price)
    out: list[dict] = []
    for plan_type, months in (('quarterly', 3), ('yearly', 12)):
        target = catalog.personal_by_type(plan_type)
        if not target:
            continue
        baseline = monthly_price * months
        bundle = int(target.price)
        savings = baseline - bundle
        out.append(
            {
                'plan_type': plan_type,
                'label': _PLAN_TYPE_LABELS.get(plan_type, plan_type),
                'months': months,
                'baseline_total': baseline,
                'bundle_price': bundle,
                'savings': savings,
                'savings_positive': savings > 0,
            }
        )
    return out


def format_price(amount: int | Decimal) -> str:
    return format_toman(int(amount))


def catalog_context_for_llm(
    catalog: PublicPlanCatalog,
    *,
    team_size: int | None = None,
    duration: str | None = None,
) -> str:
    """بلوک متنی معتبر برای پرامپت مدل."""
    lines = [
        '=== داده فروشگاه زنده (معتبر برای قیمت و مدت — اولویت بر دانشنامه) ===',
        f'محصول: {catalog.product_title}',
        f'صفحه خرید: {catalog.product_buy_url}',
        '',
        '--- پلن شخصی (یک مشاور) ---',
    ]
    if catalog.trial:
        lines.append(
            f'- {catalog.trial.name}: {format_price(catalog.trial.price)} — {catalog.trial.duration_label}'
            + (f' — {catalog.trial.tagline}' if catalog.trial.tagline else '')
        )
    for p in catalog.personal:
        promo = ''
        if p.compare_at_price and p.compare_at_price > p.price:
            promo = f' (قیمت خط‌خورده {format_price(p.compare_at_price)})'
        lines.append(
            f'- {p.name} ({p.duration_label}): {format_price(p.price)}{promo}'
            + (f' — {p.tagline}' if p.tagline else '')
        )

    lines.append('')
    lines.append('--- پلن آژانس (چند لایسنس مستقل) ---')
    for p in catalog.agency:
        lines.append(
            f'- {p.name} ({p.duration_label}): قیمت پایه هر لایسنس {format_price(p.price)}'
            f' — خرید {AGENCY_MIN_QUANTITY} تا {AGENCY_MAX_QUANTITY} لایسنس'
        )

    savings = compare_personal_duration_savings(catalog)
    if savings:
        lines.append('')
        lines.append('--- مقایسه اقتصادی شخصی (با قیمت فعلی) ---')
        monthly = catalog.personal_by_type('monthly')
        if monthly:
            lines.append(f'پایه: {monthly.name} = {format_price(monthly.price)}')
        for item in savings:
            if item['savings_positive']:
                lines.append(
                    f'{item["label"]}: {format_price(item["bundle_price"])} '
                    f'در برابر {item["months"]}× ماهانه = {format_price(item["baseline_total"])} '
                    f'→ صرفه‌جویی حدود {format_price(item["savings"])}'
                )
            else:
                lines.append(
                    f'{item["label"]}: {format_price(item["bundle_price"])} '
                    f'(در قیمت فعلی تفاوت معنادار با {item["months"]}× ماهانه نیست)'
                )

    if team_size and team_size >= AGENCY_MIN_QUANTITY:
        dur = duration or 'quarterly'
        agency_plan = catalog.agency_by_type(dur) or (catalog.agency[0] if catalog.agency else None)
        if agency_plan:
            quote = public_plan_quote(catalog, agency_plan, quantity=team_size)
            if quote:
                pct = int(get_agency_bulk_discount_percent(team_size))
                lines.append('')
                lines.append(f'--- محاسبه آژانس برای {team_size} مشاور — {agency_plan.name} ---')
                lines.append(f'قیمت پایه هر لایسنس: {format_price(quote["base_unit_price"])}')
                lines.append(f'تخفیف حجمی: {pct}٪')
                lines.append(f'قیمت هر لایسنس پس از تخفیف: {format_price(quote["effective_unit_price"])}')
                lines.append(f'جمع مبلغ پایه سفارش: {format_price(quote["final_price"])}')
                lines.append(agency_bulk_note())

    lines.append('')
    lines.append(
        'امکانات اصلی (CRM، استخراج، فایلینگ، هوش مصنوعی در سطح محصول) بین پلن‌های زمانی شخصی یکسان است؛ '
        'تفاوت آژانس در چند لایسنس مستقل و مدیریت تیم است.'
    )
    return '\n'.join(lines)
