"""تست explainability و feedback تشخیص آگهی‌دهنده."""
from __future__ import annotations

import json

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from workspace.models import AdvertiserSignalFeedback, Dataset, Listing
from workspace.services.advertiser_analysis import (
    CONFIDENCE_LABELS,
    REASON_LABELS,
    analyze_listing_advertiser,
    attach_feedback_state,
    build_public_analysis_payload,
)
from workspace.services.advertiser_feedback import feedback_analytics_summary, save_advertiser_feedback

User = get_user_model()


class AdvertiserAnalysisExplainabilityTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09121110000', password='x', phone='09121110000',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='t.xlsx',
            file_format='xlsx',
        )

    def _listing(self, description: str, **kwargs) -> Listing:
        return Listing.objects.create(
            dataset=self.dataset,
            token=kwargs.get('token', 'tok1'),
            title=kwargs.get('title', 'آگهی تست'),
            description=description,
            business_type=kwargs.get('business_type', 'personal'),
        )

    def test_disguised_luxury_example_explanation(self):
        description = (
            'جهت ارسال فیلم کامل واحد یا هماهنگی جهت بازدید پیام دهید\n'
            'همکاران عزیز لطفاً تماس نگیرید'
        )
        analysis = analyze_listing_advertiser(self._listing(description))
        self.assertEqual(analysis['classification'], 'disguised_consultant')
        self.assertEqual(analysis['confidence'], 'very_high')
        self.assertEqual(analysis['primary_reason'], 'agent_contact_restriction')
        self.assertEqual(
            analysis['primary_reason_label'],
            REASON_LABELS['agent_contact_restriction'],
        )
        self.assertTrue(analysis['primary_signals'])
        joined = ' '.join(analysis['primary_signals'] + analysis['secondary_signals'])
        self.assertIn('همکار', joined)

    def test_genuine_with_owner_claim(self):
        analysis = analyze_listing_advertiser(self._listing('مالک هستم. واحد نوساز.'))
        self.assertEqual(analysis['classification'], 'genuine_personal')
        self.assertTrue(analysis['owner_signals'])
        self.assertIn('مالک', analysis['summary'])

    def test_genuine_without_signals_professional_summary(self):
        analysis = analyze_listing_advertiser(self._listing('واحد تمیز و نوساز.'))
        self.assertEqual(analysis['classification'], 'genuine_personal')
        self.assertIn('بدون نشانه مشاوری', analysis['summary'])

    def test_confidence_mapping_persian(self):
        analysis = analyze_listing_advertiser(
            self._listing('همکاران عزیز لطفاً تماس نگیرید'),
        )
        self.assertEqual(analysis['confidence_label'], CONFIDENCE_LABELS['very_high'])

    def test_qualified_label_for_low_confidence(self):
        analysis = analyze_listing_advertiser(self._listing('واحد تمیز'))
        if analysis['confidence'] in ('low', 'medium'):
            self.assertIn('احتمالاً', analysis['classification_label_qualified'])

    def test_no_raw_reason_codes_in_public_fields(self):
        analysis = analyze_listing_advertiser(
            self._listing('همکاران تماس نگیرید. فایل مشابه موجود.'),
        )
        public = build_public_analysis_payload(analysis)
        dumped = json.dumps(public, ensure_ascii=False)
        self.assertNotIn('agent_contact_restriction', dumped)
        self.assertNotIn('professional_broker_identity', dumped)
        for sig in analysis['primary_signals'] + analysis['secondary_signals']:
            self.assertNotIn('regex', sig.lower())

    def test_critical_reason_priority(self):
        analysis = analyze_listing_advertiser(
            self._listing('بدون واسطه. همکاران تماس نگیرید.'),
        )
        self.assertEqual(analysis['primary_reason'], 'agent_contact_restriction')

    def test_attach_feedback_state(self):
        listing = self._listing('واحد')
        analysis = analyze_listing_advertiser(listing)
        attach_feedback_state(analysis, None)
        self.assertIsNone(analysis['feedback']['submitted'])


class AdvertiserFeedbackTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='09122220000', password='x', phone='09122220000',
        )
        self.other = User.objects.create_user(
            username='other_adv_fb', password='x', phone='09129998877',
        )
        self.dataset = Dataset.objects.create(
            user=self.user,
            name='تست',
            original_filename='t.xlsx',
            file_format='xlsx',
        )
        self.listing = Listing.objects.create(
            dataset=self.dataset,
            token='fb1',
            title='آگهی',
            description='همکاران تماس نگیرید',
            business_type='personal',
        )

    def test_save_correct_feedback(self):
        obj, err = save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
        )
        self.assertIsNone(err)
        self.assertEqual(obj.feedback, 'correct')

    def test_save_incorrect_requires_correction(self):
        obj, err = save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_INCORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
            user_correction='',
        )
        self.assertIsNone(obj)
        self.assertIsNotNone(err)

    def test_duplicate_feedback_updates(self):
        save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
        )
        obj, _ = save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_INCORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
            user_correction='genuine_personal',
        )
        self.assertEqual(
            AdvertiserSignalFeedback.objects.filter(
                user=self.user, listing=self.listing, detector_version=2,
            ).count(),
            1,
        )
        self.assertEqual(obj.feedback, 'incorrect')
        self.assertEqual(obj.user_correction, 'genuine_personal')

    def test_cross_user_isolation(self):
        save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
        )
        self.assertEqual(AdvertiserSignalFeedback.objects.filter(user=self.other).count(), 0)

    def test_feedback_api_endpoint(self):
        self.client.force_login(self.user)
        url = reverse(
            'workspace:listing_advertiser_feedback',
            kwargs={'dataset_id': self.dataset.id, 'listing_id': self.listing.id},
        )
        with patch('workspace.mixins.has_active_bot_license', return_value=True):
            response = self.client.post(
                url,
                data=json.dumps({'feedback': 'correct'}),
                content_type='application/json',
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])

    def test_analytics_summary(self):
        save_advertiser_feedback(
            user=self.user,
            listing=self.listing,
            feedback=AdvertiserSignalFeedback.FEEDBACK_CORRECT,
            predicted_classification='disguised_consultant',
            detector_version=2,
        )
        stats = feedback_analytics_summary()
        self.assertEqual(stats['total'], 1)
        self.assertEqual(stats['correct_count'], 1)
