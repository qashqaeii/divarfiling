"""تست AI Editorial v2 — بخش‌ها، batch و معیار کیفیت."""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from blog.services.market_article_ai_editorial import (
    _deterministic_tie_seed,
    batch_segments_by_section,
    build_editorial_context,
    changed_text_ratio,
    compute_editorial_quality,
    map_text_segment_sections,
    section_eligible_for_editorial,
    select_editorial_angle,
)
from blog.services.market_article_ai_polish import (
    BATCH_PLAN_VERSION,
    batch_text_segments,
    split_html_parts,
    text_segment_payload,
)
from blog.services.market_article_pipeline import build_preview
from blog.tests.test_market_articles import _seed_dataset

User = get_user_model()


@override_settings(MARKET_ARTICLE_SKIP_MAP_TILES=True, MARKET_ARTICLE_SKIP_ACCESS=True)
class EditorialV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='ed_u', password='x', phone='09120007001')
        self.staff = User.objects.create_user(
            username='ed_admin', password='x', phone='09120007002', is_staff=True,
        )
        self.ds = _seed_dataset(self.user, n=160, city='تهران', district='جیحون')

    def test_plan_version_is_section_batching(self):
        self.assertEqual(BATCH_PLAN_VERSION, 3)

    def test_protected_sections_skipped(self):
        self.assertFalse(section_eligible_for_editorial('market-kpis'))
        self.assertFalse(section_eligible_for_editorial('price-per-sqm'))
        self.assertTrue(section_eligible_for_editorial('executive-summary'))
        self.assertFalse(section_eligible_for_editorial(''))
        self.assertFalse(section_eligible_for_editorial('unknown-widget'))

    def test_nested_section_aside_mapping(self):
        html = (
            '<section id="outer">'
            'OUT'
            '<aside id="inner-aside">IN</aside>'
            'BACK'
            '</section>'
        )
        parts = split_html_parts(html)
        mapping = map_text_segment_sections(parts)
        texts = {i: c for i, (k, c) in enumerate(parts) if k == 'text' and c.strip()}
        for idx, text in texts.items():
            if text == 'OUT':
                self.assertEqual(mapping.get(idx), 'outer')
            elif text == 'IN':
                self.assertEqual(mapping.get(idx), 'inner-aside')
            elif text == 'BACK':
                self.assertEqual(mapping.get(idx), 'outer')

    def test_mismatched_close_does_not_pop_wrong_container(self):
        html = '<section id="a"><aside id="b">X</section></aside>'
        parts = split_html_parts(html)
        mapping = map_text_segment_sections(parts)
        text_idx = next(i for i, (k, c) in enumerate(parts) if k == 'text')
        self.assertEqual(mapping.get(text_idx), 'b')

    def test_deterministic_tie_seed_stable(self):
        run = build_preview(self.ds, self.staff)
        ctx = build_editorial_context(run)
        self.assertEqual(_deterministic_tie_seed(run, ctx), _deterministic_tie_seed(run, ctx))

    def test_editorial_score_prefers_cliche_removal_over_noise(self):
        run = build_preview(self.ds, self.staff)
        before = (
            '<div class="mk-market">'
            '<section id="executive-summary">'
            '<p>در این گزارش، بازار فروش آپارتمان بررسی شده است.</p>'
            '</section></div>'
        )
        after_good = before.replace(
            'در این گزارش، بازار فروش آپارتمان بررسی شده است.',
            'اگر برای خرید در این محله برنامه دارید، اول محدوده قیمت را مشخص کنید.',
        )
        after_noisy = (
            '<div class="mk-market">'
            '<section id="executive-summary">'
            '<p>در این گزارش، بازار فروش آپارتمان بررسی شده است. '
            + ('تغییر ' * 80)
            + '</p></section></div>'
        )
        base = dict(
            run=run,
            original_html=before,
            original_title='t',
            originals_by_id={},
            polished_map={},
            eligible_segment_ids=set(),
            batch_logs=[],
            editorial_angle='pricing_range',
        )
        good = compute_editorial_quality(
            **base,
            polished_html=after_good,
            new_title='t2',
        )
        noisy = compute_editorial_quality(**base, polished_html=after_noisy, new_title='t')
        self.assertTrue(good['intro_cliche_removed'])
        self.assertTrue(noisy['intro_cliche_remaining'])
        self.assertGreater(good['editorial_quality_score'], noisy['editorial_quality_score'])

    def test_section_batches_fewer_than_micro_segments(self):
        run = build_preview(self.ds, self.staff)
        parts = split_html_parts(run.content_html)
        segs = text_segment_payload(parts)
        section_map = map_text_segment_sections(parts)
        enriched = []
        for seg in segs:
            sid = section_map.get(int(seg['id']), '')
            if section_eligible_for_editorial(sid):
                enriched.append({**seg, 'section_id': sid})
        v2 = batch_text_segments(enriched, plan_version=2)
        v3 = batch_text_segments(enriched, plan_version=3)
        self.assertGreater(len(v2), len(v3))

    def test_batch_by_section_groups_same_section(self):
        segments = [
            {'id': 1, 'text': 'a', 'section_id': 'verdict'},
            {'id': 2, 'text': 'b', 'section_id': 'verdict'},
            {'id': 3, 'text': 'c', 'section_id': 'negotiation'},
        ]
        batches = batch_segments_by_section(segments, max_segments=10, max_chars=5000)
        self.assertEqual(len(batches), 2)
        self.assertEqual(len(batches[0]), 2)

    def test_changed_text_ratio_detects_rewrite(self):
        before = 'در این گزارش بازار فروش بررسی شده است.'
        after = 'اگر دنبال خرید در این محله هستید، اول محدوده قیمت را بشناسید.'
        self.assertGreater(changed_text_ratio(before, after), 0.35)

    def test_editorial_angle_stable_for_run(self):
        run = build_preview(self.ds, self.staff)
        a1 = select_editorial_angle(run)
        a2 = select_editorial_angle(run)
        self.assertEqual(a1, a2)
