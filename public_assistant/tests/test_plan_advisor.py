"""مشاوره خرید اشتراک — قیمت زنده، intent و سناریوهای ارزیابی."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings

from public_assistant.models import PublicChatMessage, PublicChatSession
from public_assistant.services.chat import answer_question
from public_assistant.services.plan_advisor import (
    AGENCY_TEAM_COUNT_QUESTION,
    compose_subscription_answer,
)
from public_assistant.services.plan_answer_guard import reconcile_subscription_answer
from public_assistant.services.plan_intent import analyze_subscription_query
from public_assistant.services.plan_intent import extract_team_size
from public_assistant.services.public_plans import catalog_context_for_llm
from public_assistant.services.public_plans import (
    compare_personal_duration_savings,
    format_price,
    load_public_plan_catalog,
    public_plan_quote,
)
from shop.models import LicensePlan, Product
from shop.services.plan_pricing import calculate_plan_pricing

User = get_user_model()


def _plain_amount_digits(text: str) -> str:
    return text.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹', '0123456789')).replace('٬', '').replace(',', '')


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
        self.assertIn('990000', _plain_amount_digits(ans))

    def test_trial_paid_price(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('پلن آزمایشی خریدنی چقدر است؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('250000', _plain_amount_digits(ans))

    def test_agency_four_quarterly_total_8_5m(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('ما ۴ مشاور داریم سه ماهه چقدر می‌شود؟')
        ans = compose_subscription_answer(ctx, cat)
        plan = cat.agency_by_type('quarterly')
        quote = public_plan_quote(cat, plan, quantity=4)
        self.assertEqual(quote['final_price'], Decimal('8500000'))
        self.assertIn('8500000', _plain_amount_digits(ans))
        self.assertIn('15', ans)

    def test_agency_four_monthly_total_3_366m_not_8_5m(self):
        cat = self.catalog()
        q = 'برای ۴ مشاور، پلن ماهانه چقدر است؟'
        ctx = analyze_subscription_query(q)
        self.assertEqual(ctx.duration, 'monthly')
        self.assertEqual(ctx.team_size, 4)
        plan = cat.agency_by_type('monthly')
        quote = public_plan_quote(cat, plan, quantity=4, strict=True)
        self.assertEqual(quote['effective_unit_price'], Decimal('841500'))
        self.assertEqual(quote['final_price'], Decimal('3366000'))
        ans = compose_subscription_answer(ctx, cat)
        self.assertNotIn('8500000', _plain_amount_digits(ans))
        self.assertIn('3366000', _plain_amount_digits(ans))
        self.assertIn('841500', _plain_amount_digits(ans))
        self.assertIn('15', ans)

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_four_monthly_wrong_8_5m_replaced(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (
            'جمع سفارش **۸٬۵۰۰٬۰۰۰ تومان** برای چهار مشاور ماهانه.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        session = PublicChatSession.objects.create(ip_hash='m4-month')
        out = answer_question(session=session, message='برای ۴ مشاور، پلن ماهانه چقدر است؟')
        self.assertNotIn('8500000', _plain_amount_digits(out['answer']))
        self.assertIn('3366000', _plain_amount_digits(out['answer']))
        self.assertIn('15', out['answer'])

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
        self.assertIn('2500000', _plain_amount_digits(ans))
        self.assertTrue('ارزان‌تر' in ans or 'صرفه‌جویی' in ans)

    def test_property_price_not_subscription(self):
        ctx = analyze_subscription_query('قیمت این ملک چقدر است؟')
        self.assertTrue(ctx.is_property_listing)
        self.assertFalse(ctx.is_subscription)

    def test_matching_budget_not_subscription(self):
        q = (
            'اگر مشتری بودجه ۱۰ میلیارد داشته باشد و یک فایل ۱۰ میلیارد و ۵۰۰ میلیون '
            'قیمت داشته باشد آیا سیستم ممکن است آن را پیشنهاد کند؟'
        )
        ctx = analyze_subscription_query(q)
        self.assertFalse(ctx.is_subscription)
        self.assertTrue(ctx.is_property_listing)

    def test_listing_price_update_not_subscription_anchor(self):
        q = (
            'وقتی یک آگهی از دیوار استخراج می‌کنم و بعداً صاحب آگهی قیمت یا مشخصات ملک را '
            'تغییر می‌دهد، آیا فایلینگ دیوار به‌روزرسانی می‌کند؟'
        )
        ctx = analyze_subscription_query(q)
        self.assertFalse(ctx.is_subscription)
        self.assertFalse(ctx.wants_comparison)

    def test_listing_update_not_plan_compare(self):
        q = (
            'وقتی یک آگهی از دیوار استخراج می‌کنم و بعداً صاحب آگهی قیمت یا مشخصات ملک را '
            'تغییر می‌دهد آیا فایلینگ دیوار اطلاعات را به‌روزرسانی می‌کند؟'
        )
        ctx = analyze_subscription_query(q)
        self.assertFalse(ctx.is_subscription)

    def test_48_files_not_team_size(self):
        self.assertIsNone(extract_team_size('۴۸ فایل پیشنهادی برای مخاطب'))

    def test_share_file_not_subscription(self):
        ctx = analyze_subscription_query('چطور لینک اشتراک فایل برای مشتری بفرستم؟')
        self.assertFalse(ctx.is_subscription)

    def test_filing_subscription_is_subscription(self):
        for q in (
            'قیمت اشتراک فایلینگ دیوار چنده؟',
            'اشتراک ماهانه برای مدیریت فایل‌هام می‌خوام.',
            'پلن مناسب کار با فایل‌های دیوار کدومه؟',
        ):
            ctx = analyze_subscription_query(q)
            self.assertTrue(ctx.is_subscription, msg=q)

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
        self.assertIn('۱٬۱۰۰٬۰۰۰', ans)

    def test_format_price_exact_toman(self):
        cases = (
            (250_000, '۲۵۰٬۰۰۰ تومان'),
            (990_000, '۹۹۰٬۰۰۰ تومان'),
            (2_500_000, '۲٬۵۰۰٬۰۰۰ تومان'),
            (2_970_000, '۲٬۹۷۰٬۰۰۰ تومان'),
            (3_366_000, '۳٬۳۶۶٬۰۰۰ تومان'),
            (841_500, '۸۴۱٬۵۰۰ تومان'),
            (4_752_000, '۴٬۷۵۲٬۰۰۰ تومان'),
            (8_500_000, '۸٬۵۰۰٬۰۰۰ تومان'),
        )
        for amount, expected in cases:
            self.assertEqual(format_price(amount), expected)
            self.assertEqual(format_price(Decimal(amount)), expected)

    def test_extract_team_size_persian_patterns(self):
        samples = (
            ('ما یه آژانس با ۴ تا مشاور داریم', 4),
            ('۴ نفر مشاور', 4),
            ('آژانس ما ۴ تا مشاور داره', 4),
            ('ما چهار نفریم', 4),
            ('تعدادمون شده ۶ نفر', 6),
            ('از ۴ نفر شدیم ۶ نفر', 6),
        )
        for text, expected in samples:
            self.assertEqual(extract_team_size(text), expected, msg=text)

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_fail_uses_live_fallback(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (None, 'mock', 'mock', 1, None, None)
        session = PublicChatSession.objects.create(ip_hash='fb-plan')
        out = answer_question(session=session, message='قیمت اشتراک ماهانه چقدر است؟')
        self.assertTrue(out['ok'])
        self.assertTrue(out.get('from_fallback'))
        self.assertIn('990000', _plain_amount_digits(out['answer']))

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
        self.assertIn('8000000', _plain_amount_digits(ans))

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
        cat = self.catalog()
        block = catalog_context_for_llm(cat)
        self.assertIn('آژانس', block)
        self.assertIn('شخصی', block)

    def test_multi_turn_six_quarterly_after_four_monthly(self):
        session = PublicChatSession.objects.create(ip_hash='mt-64')
        PublicChatMessage.objects.create(
            session=session,
            role=PublicChatMessage.ROLE_USER,
            content='برای ۴ مشاور ماهانه چقدر؟',
        )
        ctx = analyze_subscription_query('حالا ۶ نفر شدیم، سه‌ماهه چقدر؟', session)
        self.assertEqual(ctx.team_size, 6)
        self.assertEqual(ctx.duration, 'quarterly')
        cat = self.catalog()
        ans = compose_subscription_answer(ctx, cat)
        plan = cat.agency_by_type('quarterly')
        quote = public_plan_quote(cat, plan, quantity=6, strict=True)
        self.assertEqual(quote['final_price'], Decimal('12000000'))
        self.assertIn('6', ans)

    def test_duration_switch_yearly_then_monthly(self):
        session = PublicChatSession.objects.create(ip_hash='dur-sw')
        PublicChatMessage.objects.create(
            session=session,
            role=PublicChatMessage.ROLE_USER,
            content='برای ۳ مشاور سالانه چقدر؟',
        )
        ctx = analyze_subscription_query('ماهانه چقدر می‌شود؟', session)
        self.assertEqual(ctx.team_size, 3)
        self.assertEqual(ctx.duration, 'monthly')

    def test_topic_change_clears_team_size(self):
        session = PublicChatSession.objects.create(ip_hash='topic-br')
        PublicChatMessage.objects.create(
            session=session,
            role=PublicChatMessage.ROLE_USER,
            content='ما ۴ مشاور داریم',
        )
        PublicChatMessage.objects.create(
            session=session,
            role=PublicChatMessage.ROLE_USER,
            content='چطور مخاطب ثبت کنم؟',
        )
        ctx = analyze_subscription_query('سالانه چقدر؟', session)
        self.assertIsNone(ctx.team_size)

    def test_agency_price_without_count_asks(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('قیمت پلن آژانس سه‌ماهه')
        self.assertTrue(ctx.needs_team_count)
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn(AGENCY_TEAM_COUNT_QUESTION, ans)

    def test_over_max_no_clamped_quote_in_context(self):
        cat = self.catalog()
        block = catalog_context_for_llm(cat, team_size=30, duration='quarterly')
        self.assertIn('30', block)
        self.assertNotIn('جمع مبلغ پایه سفارش', block)

    def test_quarterly_not_cheaper_when_prices_equal(self):
        self.plans['personal_quarterly'].price = 990_000 * 3
        self.plans['personal_quarterly'].save(update_fields=['price'])
        cat = self.catalog()
        ctx = analyze_subscription_query('سه‌ماهه بهتره یا ماهانه؟')
        ans = compose_subscription_answer(ctx, cat)
        self.assertIn('به‌صرفه‌تر نیست', ans)

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_wrong_price_replaced(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (
            'قیمت ماهانه **۵ میلیون تومان** است.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        session = PublicChatSession.objects.create(ip_hash='llm-wrong')
        out = answer_question(session=session, message='قیمت اشتراک ماهانه چقدر است؟')
        self.assertIn('990000', _plain_amount_digits(out['answer']))
        self.assertNotIn('۵ میلیون', out['answer'])

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_wrong_discount_replaced(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (
            'برای ۴ مشاور تخفیف **۲۰٪** و جمع **۱۰ میلیون**.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        session = PublicChatSession.objects.create(ip_hash='llm-disc')
        out = answer_question(
            session=session,
            message='ما ۴ مشاور داریم سه ماهه چقدر می‌شود؟',
        )
        self.assertIn('15', out['answer'])
        self.assertIn('8500000', _plain_amount_digits(out['answer']))

    @patch('public_assistant.services.chat.llm.complete')
    def test_llm_ok_answer_kept_when_no_conflict(self, mock_complete):
        call_command('sync_public_knowledge')
        good = 'برای شروع، [محصولات و اشتراک](/products/) و راهنمای لایسنس کمک بگیرید.'
        mock_complete.return_value = (good, 'mock', 'mock', 1, 1, 1)
        session = PublicChatSession.objects.create(ip_hash='llm-ok')
        out = answer_question(session=session, message='چطور اشتراک بخرم؟')
        self.assertIn('[محصولات و اشتراک](/products/)', out['answer'])

    @patch('public_assistant.services.chat.llm.complete')
    def test_no_catalog_strips_kb_prices(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (
            'پلن ماهانه ۹۹۰ هزار تومان است.',
            'mock',
            'mock',
            1,
            1,
            1,
        )
        with patch('public_assistant.services.chat.load_public_plan_catalog', return_value=None):
            session = PublicChatSession.objects.create(ip_hash='no-cat')
            out = answer_question(session=session, message='قیمت اشتراک ماهانه؟')
        self.assertIn('buy', out['answer'])
        self.assertNotIn('990', out['answer'].replace(',', ''))

    def test_reconcile_unit(self):
        cat = self.catalog()
        ctx = analyze_subscription_query('قیمت ماهانه اشتراک')
        bad = 'هزینه: ۵ میلیون تومان'
        fixed = reconcile_subscription_answer(bad, ctx, cat)
        self.assertIn('990000', _plain_amount_digits(fixed))

    def test_multi_turn_agency_pricing_chain(self):
        session = PublicChatSession.objects.create(ip_hash='mt-chain')
        cat = self.catalog()
        steps = [
            (
                'ما ۴ مشاور داریم، ماهانه چقدر؟',
                4,
                'monthly',
                Decimal('3366000'),
            ),
            (
                'حالا سه‌ماهه چقدر؟',
                4,
                'quarterly',
                Decimal('8500000'),
            ),
            (
                'اگر ۶ نفر بشیم چی؟',
                6,
                'quarterly',
                Decimal('12000000'),
            ),
            (
                'سالانه حساب کن',
                6,
                'yearly',
                Decimal('38400000'),
            ),
        ]
        for msg, team, duration, expected_total in steps:
            PublicChatMessage.objects.create(
                session=session,
                role=PublicChatMessage.ROLE_USER,
                content=msg,
            )
            ctx = analyze_subscription_query(msg, session)
            self.assertEqual(ctx.team_size, team, msg=msg)
            self.assertEqual(ctx.duration, duration, msg=msg)
            plan = cat.agency_by_type(duration)
            quote = public_plan_quote(cat, plan, quantity=team, strict=True)
            self.assertEqual(quote['final_price'], expected_total, msg=msg)
            compose_subscription_answer(ctx, cat)

    def test_guard_keeps_seven_days_and_two_devices(self):
        from public_assistant.services.plan_answer_guard import (
            extract_money_amounts,
            reconcile_subscription_answer,
            should_replace_llm_financials,
        )

        cat = self.catalog()
        ctx = analyze_subscription_query('قیمت ماهانه اشتراک')
        llm = 'پلن ۷ روزه و ۲ دستگاه فعال؛ قیمت ماهانه ۹۹۰ هزار تومان.'
        self.assertFalse(should_replace_llm_financials(llm, ctx, cat))
        kept = reconcile_subscription_answer(llm, ctx, cat)
        self.assertEqual(kept, llm)
        self.assertIn(990_000, extract_money_amounts(llm))
        self.assertNotIn(extract_money_amounts('۷ روز و ۲ دستگاه'), {7, 2})

    def test_guard_persian_digits_price_conflict(self):
        from public_assistant.services.plan_answer_guard import reconcile_subscription_answer

        cat = self.catalog()
        ctx = analyze_subscription_query('۴ مشاور ماهانه قیمت')
        bad = 'جمع: ۸٬۵۰۰٬۰۰۰ تومان'
        fixed = reconcile_subscription_answer(bad, ctx, cat)
        self.assertIn('۳٬۳۶۶٬۰۰۰', fixed)

    def _five_production_questions(self):
        return (
            (
                'سلام، من تازه کار مشاور املاک رو شروع کردم و فعلاً '
                'تنها کار می‌کنم. به نظرت کدوم اشتراک فایلینگ دیوار '
                'بیشتر به دردم می‌خوره و چرا؟'
            ),
            (
                'فرق اشتراک یک‌ماهه، سه‌ماهه و یک‌ساله چیه؟ '
                'امکاناتشون فرق داره؟ اگه بخوام حداقل سه ماه '
                'استفاده کنم، کدوم به‌صرفه‌تره؟'
            ),
            (
                'ما یه آژانس با ۴ تا مشاور داریم. اگه اشتراک '
                'ماهانه بخریم، با تخفیف آژانس برای هر نفر چقدر '
                'درمیاد و جمع کل چقدر میشه؟'
            ),
            (
                'حالا فرض کن تعداد مشاورهای ما ۶ نفر شده '
                'و اشتراک سه‌ماهه می‌خوایم. قیمت هر لایسنس، '
                'درصد تخفیف و مبلغ کل رو حساب کن.'
            ),
            (
                'شنیدم فایلینگ دیوار ۷ روز اشتراک رایگان میده، '
                'ولی یه پلن آزمایشی ۲۵۰ هزار تومنی هم داره. '
                'فرق این دو تا چیه؟ من چطور می‌تونم ازشون '
                'استفاده کنم؟'
            ),
        )

    def _assert_q1(self, ans: str):
        self.assertIn('شخصی', ans)
        self.assertIn('۹۹۰٬۰۰۰', ans)
        self.assertIn('۲٬۵۰۰٬۰۰۰', ans)

    def _assert_q2(self, ans: str):
        for token in ('۹۹۰٬۰۰۰', '۲٬۵۰۰٬۰۰۰', '۸٬۰۰۰٬۰۰۰', '۲٬۹۷۰٬۰۰۰', '۴۷۰٬۰۰۰'):
            self.assertIn(token, ans)
        self.assertNotIn('۳٬۰۰۰٬۰۰۰', ans)
        self.assertNotIn('3 میلیون', ans)

    def _assert_q3(self, ans: str):
        self.assertIn('۴', ans)
        self.assertIn('۸۴۱٬۵۰۰', ans)
        self.assertIn('۳٬۳۶۶٬۰۰۰', ans)
        self.assertIn('15', ans)
        self.assertNotIn('تازه مشاوره', ans)

    def _assert_q4(self, ans: str):
        self.assertTrue('۶' in ans or '6' in ans)
        self.assertIn('۲٬۵۰۰٬۰۰۰', ans)
        self.assertIn('۲٬۰۰۰٬۰۰۰', ans)
        self.assertIn('۱۲٬۰۰۰٬۰۰۰', ans)
        self.assertIn('20', ans)

    def _assert_q5(self, ans: str):
        self.assertIn('هدیه', ans)
        self.assertIn('۲۵۰٬۰۰۰', ans)
        self.assertIn('آزمایشی', ans)
        self.assertNotIn('جمع مبلغ پایه سفارش', ans)
        self.assertNotIn('۸۴۱٬۵۰۰', ans)

    def test_production_five_question_python_path(self):
        session = PublicChatSession.objects.create(ip_hash='prod-5-py')
        questions = self._five_production_questions()
        checks = (self._assert_q1, self._assert_q2, self._assert_q3, self._assert_q4, self._assert_q5)
        for msg, check in zip(questions, checks):
            PublicChatMessage.objects.create(
                session=session,
                role=PublicChatMessage.ROLE_USER,
                content=msg,
            )
            ctx = analyze_subscription_query(msg, session)
            ans = compose_subscription_answer(ctx, self.catalog())
            check(ans)

    @patch('public_assistant.services.chat.llm.complete')
    def test_production_five_question_llm_fallback(self, mock_complete):
        call_command('sync_public_knowledge')
        mock_complete.return_value = (None, 'mock', 'mock', 1, None, None)
        session = PublicChatSession.objects.create(ip_hash='prod-5-fb')
        for msg, check in zip(
            self._five_production_questions(),
            (self._assert_q1, self._assert_q2, self._assert_q3, self._assert_q4, self._assert_q5),
        ):
            out = answer_question(session=session, message=msg)
            check(out['answer'])

    @patch('public_assistant.services.chat.llm.complete')
    def test_production_five_question_llm_wrong_prices(self, mock_complete):
        call_command('sync_public_knowledge')
        session = PublicChatSession.objects.create(ip_hash='prod-5-bad')
        wrong = (
            'پلن ماهانه ۱ میلیون تومان و سه‌ماهه ۳ میلیون.',
            '۳× ماهانه ۳ میلیون؛ سه‌ماهه ۲ میلیون.',
            '۴ مشاور: هر نفر ۹۹۰ هزار؛ جمع ۴ میلیون.',
            '۶ مشاور سه‌ماهه: جمع ۱۲ میلیون؛ هر نفر ۲٫۵ میلیون.',
            'برای ۶ مشاور ماهانه جمع ۵ میلیون تومان است.',
        )
        checks = (self._assert_q1, self._assert_q2, self._assert_q3, self._assert_q4, self._assert_q5)
        for msg, bad, check in zip(self._five_production_questions(), wrong, checks):
            mock_complete.return_value = (bad, 'mock', 'mock', 1, 1, 1)
            out = answer_question(session=session, message=msg)
            check(out['answer'])

    @patch('public_assistant.services.chat.llm.complete')
    def test_production_five_question_llm_ok_kept_when_matching(self, mock_complete):
        call_command('sync_public_knowledge')
        session = PublicChatSession.objects.create(ip_hash='prod-5-ok')
        cat = self.catalog()
        from public_assistant.services.public_copy import finalize_public_answer

        for msg in self._five_production_questions():
            good = finalize_public_answer(
                compose_subscription_answer(analyze_subscription_query(msg, session), cat)
            )
            mock_complete.return_value = (good, 'mock', 'mock', 1, 1, 1)
            out = answer_question(session=session, message=msg)
            self.assertEqual(out['answer'], good)


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
