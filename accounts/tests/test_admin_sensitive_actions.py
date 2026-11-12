"""Phase 01A: authorization for high-impact admin actions and safe redirects."""
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.admin_views import _card_transfer_redirect
from accounts.services.admin_action_permissions import (
    can_review_card_transfer,
    can_send_admin_sms,
)

User = get_user_model()


class AdminSensitiveActionPermissionTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='sensitive_staff', phone='09128000111', password='x',
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='sensitive_owner', phone='09128000112', password='x',
            is_staff=True, is_superuser=True,
        )
        self.viewer = User.objects.create_user(
            username='sensitive_viewer', phone='09128000113', password='x',
        )
        self.client.force_login(self.staff)

    def grant(self, *perms):
        for app_label, codename in perms:
            permission = Permission.objects.get(
                content_type__app_label=app_label, codename=codename,
            )
            self.staff.user_permissions.add(permission)

    def test_financial_permission_requires_both_explicit_model_roles(self):
        self.assertFalse(can_review_card_transfer(self.staff))
        self.grant(('shop', 'change_cardtransfersubmission'))
        self.assertFalse(can_review_card_transfer(self.staff))
        self.grant(('shop', 'change_order'))
        self.assertTrue(can_review_card_transfer(self.staff))
        self.assertTrue(can_review_card_transfer(self.owner))
        self.assertFalse(can_review_card_transfer(self.viewer))

    def test_financial_post_denied_before_order_or_fulfillment_lookup(self):
        for route in ('admin_panel_card_transfer_approve', 'admin_panel_card_transfer_reject'):
            url = reverse(route, args=[987654])
            with self.subTest(route=route):
                with patch('shop.services.order_fulfillment.approve_card_transfer') as approve:
                    with patch('shop.services.order_fulfillment.reject_card_transfer') as reject:
                        response = self.client.post(url, {'admin_note': 'test'})
                self.assertEqual(response.status_code, 403)
                approve.assert_not_called()
                reject.assert_not_called()

    def test_delegated_reviewer_reaches_lookup_after_explicit_grants(self):
        self.grant(
            ('shop', 'change_cardtransfersubmission'),
            ('shop', 'change_order'),
        )
        url = reverse('admin_panel_card_transfer_approve', args=[987654])
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_sms_send_requires_two_grants_not_merely_staff(self):
        self.assertFalse(can_send_admin_sms(self.staff))
        self.grant(('accounts', 'change_marketingcampaign'))
        self.assertFalse(can_send_admin_sms(self.staff))
        self.grant(('accounts', 'add_smsmessagelog'))
        self.assertTrue(can_send_admin_sms(self.staff))
        self.assertTrue(can_send_admin_sms(self.owner))
        self.assertFalse(can_send_admin_sms(self.viewer))

    def test_android_send_denied_without_creating_campaign(self):
        with patch('accounts.admin_views.create_campaign_draft') as create:
            response = self.client.post(
                reverse('admin_panel_android_sms_send'),
                {'confirm_send': '1', 'selected_phones': ['09121110000']},
            )
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_marketing_send_denied_without_creating_campaign(self):
        with patch('accounts.admin_views.create_campaign_draft') as create:
            response = self.client.post(
                reverse('admin_panel_marketing'),
                {'confirm_send': '1', 'selected_phones': ['09121110000']},
            )
        self.assertEqual(response.status_code, 403)
        create.assert_not_called()

    def test_android_phone_preview_denied(self):
        with patch('accounts.admin_views.preview_segment') as preview:
            response = self.client.get(reverse('admin_panel_android_sms_preview'))
        self.assertEqual(response.status_code, 403)
        preview.assert_not_called()

    def test_sensitive_assistant_endpoints_deny_unprivileged_staff(self):
        protected = (
            ('admin_panel_assistant_send', 'send_insight_campaign'),
            ('admin_panel_assistant_automation', 'toggle_automation_rule'),
            ('admin_panel_assistant_automation_run', 'run_automation_rule_now'),
            ('admin_panel_assistant_automation_settings', 'update_automation_rule_settings'),
            ('admin_panel_assistant_automation_test_send', 'send_automation_test_message'),
        )
        for name, service in protected:
            with self.subTest(name=name):
                with patch('accounts.admin_views.' + service) as fn:
                    response = self.client.post(
                        reverse(name),
                        json.dumps({'confirm_send': '1', 'rule_key': 'license_expiring_3d'}),
                        content_type='application/json',
                    )
                self.assertEqual(response.status_code, 403)
                fn.assert_not_called()

    def test_phonebook_sync_denied_before_remote_call(self):
        with patch('accounts.admin_views.sync_users_to_phonebook') as sync:
            response = self.client.post(reverse('admin_panel_phonebook_sync'))
        self.assertEqual(response.status_code, 403)
        sync.assert_not_called()

    def test_plain_staff_sees_readonly_financial_actions(self):
        response = self.client.get(reverse('admin_panel_sales'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="card-transfer-approve-modal"')

    def test_allowed_sms_operator_can_reach_form_validation(self):
        self.grant(
            ('accounts', 'change_marketingcampaign'),
            ('accounts', 'add_smsmessagelog'),
        )
        response = self.client.post(
            reverse('admin_panel_android_sms_send'),
            {'confirm_send': '0'},
        )
        self.assertEqual(response.status_code, 302)


class CardTransferSafeRedirectTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_external_protocol_relative_next_rejected(self):
        request = self.factory.post(
            '/accounts/admin-panel/card-transfers/1/approve/',
            {'next': '//evil.example/collect'},
        )
        response = _card_transfer_redirect(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin_panel_sales') + '#sales-card-transfers')

    def test_internal_next_allowed(self):
        relative = reverse('admin_panel_sales') + '?days=7#sales-card-transfers'
        request = self.factory.post(
            '/accounts/admin-panel/card-transfers/1/approve/',
            {'next': relative},
        )
        response = _card_transfer_redirect(request)
        self.assertEqual(response.url, relative)
