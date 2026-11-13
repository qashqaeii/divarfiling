"""Phase 01D: privileged lead operations and affiliate settlement admin boundaries."""
import json
from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.admin.models import LogEntry
from django.core.exceptions import PermissionDenied
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from affiliates.models import Wallet, WalletTransaction, Withdrawal
from accounts.services.admin_action_permissions import can_send_admin_sms

User = get_user_model()


class LeadOperatorAccessTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username='lead_readonly', phone='09123781101', password='x', is_staff=True,
        )
        self.owner = User.objects.create_user(
            username='lead_owner', phone='09123781102', password='x',
            is_staff=True, is_superuser=True,
        )
        self.client.force_login(self.staff)

    def grant(self, app_label, codename):
        permission = Permission.objects.get(
            content_type__app_label=app_label, codename=codename,
        )
        self.staff.user_permissions.add(permission)

    def test_readonly_staff_cannot_send_or_modify_lead_campaign(self):
        url = reverse('admin_panel_lead_acquisition')
        with patch('accounts.lead_acquisition_views.send_campaign_step') as sender:
            response = self.client.post(url, {
                'action': 'send_step', 'campaign_id': '10', 'step_number': '1',
            })
        self.assertEqual(response.status_code, 403)
        sender.assert_not_called()

        with patch('accounts.lead_acquisition_views.create_acquisition_campaign') as creator:
            response = self.client.post(url, {
                'action': 'create_campaign', 'name': 'unapproved',
            })
        self.assertEqual(response.status_code, 403)
        creator.assert_not_called()

    def test_readonly_staff_blocked_on_send_and_sensitive_session_apis(self):
        for name in (
            'admin_panel_lead_send_progress_start',
            'admin_panel_lead_send_progress_tick',
            'admin_panel_lead_bulk_templates',
            'admin_panel_divar_sessions_json',
            'admin_panel_lead_automation_lines_json',
        ):
            with self.subTest(endpoint=name):
                url = reverse(name)
                response = self.client.post(
                    url, data=json.dumps({'campaign_ids': [1], 'action': 'grant_consent'}),
                    content_type='application/json',
                )
                self.assertEqual(response.status_code, 403)
        for name in ('admin_panel_divar_sessions_json', 'admin_panel_lead_automation_lines_json'):
            with self.subTest(endpoint=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 403)

    def test_readonly_staff_can_still_see_lead_overview(self):
        response = self.client.get(reverse('admin_panel_lead_acquisition'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'مشاهده گزارش‌ها مجاز است')

    def test_delegate_requires_both_existing_sms_permissions(self):
        self.assertFalse(can_send_admin_sms(self.staff))
        self.grant('accounts', 'change_marketingcampaign')
        self.assertFalse(can_send_admin_sms(self.staff))
        self.grant('accounts', 'add_smsmessagelog')
        self.assertTrue(can_send_admin_sms(self.staff))
        self.assertEqual(
            self.client.post(reverse('admin_panel_lead_send_progress_start'), data=json.dumps({}),
                             content_type='application/json').status_code,
            400,
        )

    def test_owner_gets_send_operator_ui_without_readonly_banner(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('admin_panel_lead_acquisition'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'مشاهده گزارش‌ها مجاز است')


class AffiliateSettlementAdminPermissionsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='withdraw_owner', phone='09123781111', password='x',
            is_staff=True, is_superuser=True,
        )
        self.staff = User.objects.create_user(
            username='withdraw_staff', phone='09123781112', password='x',
            is_staff=True,
        )
        self.partner = User.objects.create_user(
            username='withdraw_partner', phone='09123781113', password='x',
        )
        self.wallet = Wallet.objects.create(
            user=self.partner, balance=Decimal('50000'),
        )
        self.withdrawal = Withdrawal.objects.create(
            wallet=self.wallet, amount=Decimal('10000'),
            status='pending',
            bank_account='IR0000000000', bank_name='Test bank',
            account_holder='Test holder',
        )

    def grant(self, app_label, codename):
        permission = Permission.objects.get(
            content_type__app_label=app_label, codename=codename,
        )
        self.staff.user_permissions.add(permission)

    def test_staff_with_generic_change_permission_cannot_settle(self):
        self.grant('affiliates', 'view_withdrawal')
        self.grant('affiliates', 'change_withdrawal')
        self.grant('affiliates', 'change_wallet')
        self.client.force_login(self.staff)
        changelist = reverse('admin:affiliates_withdrawal_changelist')
        response = self.client.post(changelist, {
            'action': 'approve_withdrawals',
            '_selected_action': [str(self.withdrawal.pk)],
            'index': '0',
        })
        self.assertNotEqual(response.status_code, 500)
        self.withdrawal.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'pending')
        self.assertEqual(self.wallet.balance, Decimal('50000'))
        self.assertFalse(WalletTransaction.objects.filter(wallet=self.wallet).exists())

    def test_direct_action_without_owner_role_is_forbidden(self):
        model_admin = admin.site._registry[Withdrawal]
        request = RequestFactory().post('/admin/affiliates/withdrawal/')
        request.user = self.staff
        with self.assertRaises(PermissionDenied):
            model_admin.approve_withdrawals(
                request, Withdrawal.objects.filter(pk=self.withdrawal.pk),
            )

    def test_owner_can_approve_once_and_action_is_audited(self):
        self.client.force_login(self.owner)
        url = reverse('admin:affiliates_withdrawal_changelist')
        payload = {
            'action': 'approve_withdrawals',
            '_selected_action': [str(self.withdrawal.pk)],
            'index': '0',
        }
        first = self.client.post(url, payload)
        self.assertEqual(first.status_code, 302)
        second = self.client.post(url, payload)
        self.assertEqual(second.status_code, 302)
        self.withdrawal.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'approved')
        self.assertEqual(self.wallet.balance, Decimal('40000'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                wallet=self.wallet, transaction_type='debit',
            ).count(),
            1,
        )
        self.assertEqual(
            LogEntry.objects.filter(
                user=self.owner, object_id=str(self.withdrawal.pk),
            ).count(),
            1,
        )

    def test_owner_cannot_bypass_withdrawal_transition_through_change_form(self):
        self.client.force_login(self.owner)
        url = reverse('admin:affiliates_withdrawal_change', args=[self.withdrawal.pk])
        response = self.client.post(url, {
            'notes': '',
            'admin_notes': 'Reviewed',
            'status': 'completed',
            'amount': '1',
            '_save': 'Save',
        })
        self.assertEqual(response.status_code, 302)
        self.withdrawal.refresh_from_db()
        self.assertEqual(self.withdrawal.status, 'pending')
        self.assertEqual(self.withdrawal.amount, Decimal('10000'))
