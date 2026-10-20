"""مشاوره خرید اشتراک — قیمت زنده، intent و سناریوهای ارزیابی."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.models import PublicChatMessage, PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.plan_advisor import compose_subscription_answer
from public_assistant.services.plan_intent import analyze_subscription_query
from public_assistant.services.public_plans import (
    compare_personal_duration_savings,
    load_public_plan_catalog,
    public_plan_quote,
)
from shop.models import LicensePlan, Product
from shop.services.plan_pricing import calculate_plan_pricing

User = get_user_model()


def create_bot_catalog_product(slug: str = 'divar-extraction-bot-advisor-test') -> tuple[Product, dict]:
    """همان ساختار قیمت‌های مرجع bot_catalog — مستقل از production."""
    product = Product.objects.create(
        title='ربات تست مشاور',
        slug=slug,
        description='test',
        is_active=True,
    )
    plans: dict[str, LicensePlan] = {}
    specs = [
        ('trial', 'daily', 250_000, 7, False, 0),
        ('personal_monthly', 'monthly', 990_000, 30, False, 1),
        ('personal_quarterly', 'quarterly', 2_500_000, 90, False, 2),
        ('personal_yearly', 'yearly', 8_000_000, 365, False, 3),
        ('agency_monthly', 'monthly', 990_000, 30, True, 4),
        ('agency_quarterly', 'quarterly', 2_500_000, 90, True, 5),
        ('agency_yearly', 'yearly', 8_000_000, 365, True, 6),
    ]
    for key, plan_type, price, days, bulk, order in specs:
        plans[key] = LicensePlan.objects.create(
            product=product,
            name=f'تست {key}',
            plan_type=plan_type,
            price=price,
            compare_at_price=10_000_000 if plan_type == 'yearly' and not bulk else None,
            duration_days=days,
            max_activations=2,
            allow_bulk_purchase=bulk,
            min_quantity=2 if bulk else 1,
            max_quantity=25 if bulk else 1,
            is_active=True,
            order=order,
        )
    return product, plans


@override_settings(PUBLIC_ASSISTANT_ENABLED=True)
class PlanAdvisorCatalogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='plan-advisor', password='x')
        self.product, self.plans = create_bot_catalog_product()
        # دستیار از slug ثابت bot استفاده می‌کند — برای تست patch می‌کنیم
        self._product_patcher = patch(
            'public_assistant.services.public_plans.get_bot_product',
            return_value=self.product,
        )
        self._product_patcher.start()
        self._buy_url_patcher = patch(
            'public_assistant.services.public_plans.get_bot_product_buy_url',
            side_effect=lambda plan_id=None: f'/buy-test/{plan_id or ""}',
        )
        self._buy_url_patcher.start()

    def tearDown(self):
        self._buy_url_patcher.stop()
        self._product_patcher.stop()

    def catalog(self):
        cat = load_public_plan_catalog()
        self.assertIsNotNone(cat)
        return cat

    def test_personal_monthly_price_in_answer(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('لایسنس ماهانه چند است؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('990', ans.replace(',', '').replace('٬', ''))

    def test_trial_paid_price(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('پلن آزمایشی خریدنی چقدر است؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('250', ans.replace(',', ''))

    def test_agency_four_quarterly_total_8_5m(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('ما ۴ مشاور داریم سه ماهه چقدر می‌شود؟')
        ans = compose_subscription_answer(ctx, cat)
        plan = cat.agency_by_type('quarterly')
        quote = public_plan_quote(cat, plan, quantity=4)
        self.assertEqual(quote['final_price'], Decimal('8500000'))
        self.assertIn('8', ans)
        self.assertIn('15', ans)

    def test_agency_discount_tiers(self):
        plan = self.plans['agency_monthly']
        for qty, total in (
            (2, Decimal('1782000')),
            (3, Decimal('2524500')),
            (5, Decimal('4207500')),
            (6, Decimal('4752000')),
            (10, Decimal('7920000')),
            (11, Decimal('8167500')),
            (25, Decimal('18562500')),
        ):
            p = calculate_plan_pricing(plan, self.product, self.user, quantity=qty)
            self.assertEqual(p['final_price'], total, msg=f'qty={qty}')

    def test_agency_boundaries_one_and_twenty_six(self):
        cat = self.catalog()
        ctx_one = analyze_subscription_query('آژانس برای ۱ نفر')
        ans_one = compose_subscription_answer(ctx_one, cat)
        self.assertIn('شخصی', ans_one)
        ctx26 = analyze_subscription_query('برای ۲۶ مشاور سالانه')
        ans26 = compose_subscription_answer(ctx26, cat)
        self.assertIn('25', ans26)

    def test_compare_quarterly_savings(self):
        cat = self.catalog()
        savings = compare_personal_duration_savings(cat)
        q = next(s for s in savings if s['plan_type'] == 'quarterly')
        self.assertEqual(q['baseline_total'], 990_000 * 3)
        self.assertEqual(q['bundle_price'], 2_500_000)
        self.assertEqual(q['savings'], 470_000)

    def test_solo_recommendation(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('من تنها کار می‌کنم کدام اشتراک بهتر است؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('شخصی', ans)

    def test_newbie_recommendation(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('من تازه شروع کردم کدوم پلن رو بخرم؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('یک‌ماهه', ans)

    def test_monthly_vs_quarterly_compare(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('سه‌ماهه بهتره یا ماهانه؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('2', ans)
        self.assertIn('صرفه‌جویی', ans)

    def test_property_price_not_subscription(self):
        ctx = analyze_subscription_query('قیمت این ملک چقدر است؟')
        self.assertTrue(ctx.is_property_listing)
        self.assertFalse(ctx.is_subscription)

    def test_share_file_not_subscription(self):
        ctx = analyze_subscription_query('لینک اشتراک فایل برای مشتری')
        self.assertFalse(ctx.is_subscription)

    def test_followup_team_size_in_session(self):
        session = PublicChatSession.objects.create(ip_hash='followup-plan')
        PublicChatMessage.objects.create(
            session=session,
            role=PublicChatMessage.ROLE_USER,
            content='ما ۵ نفریم',
        )
        ctx = analyze_subscription_query('سالانه چقدر؟', session)
        self.assertEqual(ctx.team_size, 5)
        self.assertEqual(ctx.duration, 'yearly')

    def test_features_crm_ai(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('آیا در پلن ماهانه CRM و هوش مصنوعی هم هست؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('CRM', ans)

    def test_inactive_plan_excluded(self):
        self.plans['personal_monthly'].is_active = False
        self.plans['personal_monthly'].save(update_fields=['is_active'])
        cat = self.catalog()
        self.assertIsNone(cat.personal_by_type('monthly'))

    def test_price_change_reflected(self):
        self.plans['personal_monthly'].price = 1_100_000
        self.plans['personal_monthly'].save(update_fields=['price'])
        cat = self.catalog()
        ctx = analyze_subscription_query('قیمت ماهانه')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('1 میلیون', ans)

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_fail_uses_live_fallback(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (None, 'mock', 'mock', 1, None, None)
        session = PublicChatSession.objects.create(ip_hash='fb-plan')
        out = answer_question(session=session, message='قیمت اشتراک ماهانه چقدر است؟')
        self.assertTrue(out['ok'])
        self.assertTrue(out.get('from_fallback'))
        self.assertIn('990', out['answer'].replace(',', ''))

    def test_answer_no_internal_leaks(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('برای ۴ مشاور سه ماهه')
        ans = compose_subscription_answer(ctx, cat)
        self.assertNotIn('calculate_plan_pricing', ans)
        self.assertNotIn('LicensePlan', ans)

    def test_welcome_gift_vs_trial(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('هفت روز رایگان با پلن آزمایشی چه فرقی دارد؟')
        self.assertTrue(ctx.wants_welcome_gift or ctx.wants_trial_info)

    def test_personal_yearly_price(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('یک‌ساله شخصی چقدر است؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('8', ans.replace(',', ''))

    def test_agency_two_monthly(self):
        cat = self.catalog()
        plan = cat.agency_by_type('monthly')
        quote = public_plan_quote(cat, plan, quantity=2)
        self.assertEqual(quote['final_price'], Decimal('1782000'))

    def test_agency_ten_quarterly(self):
        cat = self.catalog()
        plan = cat.agency_by_type('quarterly')
        quote = public_plan_quote(cat, plan, quantity=10)
        self.assertEqual(quote['effective_unit_price'], Decimal('2000000'))

    def test_all_agency_durations_listed_in_context(self):
        from public_assistant.services.public_plans import catalog_context_for_llm

        cat = self.catalog()
        block = catalog_context_for_llm(cat)
        self.assertIn('آژانس', block)
        self.assertIn('شخصی', block)


class PlanAdvisorIntentMatrixTests(TestCase):
    """سناریوهای intent — بدون نیاز به کاتالوگ."""

    def test_subscription_phrases(self):
        samples = (
            'چه پلن‌هایی دارید؟',
            'یک‌ساله چقدر می‌شود؟',
            'برای ۱۰ مشاور پلن سالانه',
            'اگر اشتراک تمام شود چه اتفاقی می‌افتد؟',
        )
        for q in samples:
            ctx = analyze_subscription_query(q)
            self.assertTrue(ctx.is_subscription, msg=q)
