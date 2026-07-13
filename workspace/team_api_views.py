"""REST API مدیریت تیم CRM."""
from __future__ import annotations

import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.views import View

from workspace.models import CRMAgencyMember, CRMAgencyTeamGoal, CRMAgencyWebhook
from workspace.services.crm_agency import (
    bulk_assign_leads, get_team_inbox, invite_member_by_phone,
    regenerate_api_key, remove_member, update_agency_settings, update_member_role,
)
from workspace.services.crm_agency_analytics import (
    export_team_performance_csv, get_team_performance,
)
from workspace.services.jalali_input import parse_goal_period_strings
from workspace.services.crm_scope import agency_members, can_manage_team, can_operate_team_leads, get_membership
from workspace.services.crm_sync import export_crm_payload, import_crm_payload, record_sync_log
from workspace.services.crm_webhooks import test_webhook


class _TeamAPIBase(LoginRequiredMixin, View):
    def _deny(self, msg='دسترسی مجاز نیست', code=403):
        return JsonResponse({'ok': False, 'error': msg}, status=code)

    def _agency(self):
        m = get_membership(self.request.user)
        return m.agency if m else None


class TeamMembersAPIView(_TeamAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency:
            return self._deny('آژانس یافت نشد', 404)
        members = [
            {
                'id': m.pk,
                'user_id': m.user_id,
                'name': m.user.get_full_name() or m.user.phone or m.user.username,
                'role': m.role,
                'title': m.title,
            }
            for m in agency_members(agency)
        ]
        return JsonResponse({'ok': True, 'members': members})

    def post(self, request):
        if not can_manage_team(request.user):
            return self._deny()
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            invite_member_by_phone(request.user, payload.get('phone', ''), payload.get('role', 'advisor'))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class TeamMemberDetailAPIView(_TeamAPIBase):
    def patch(self, request, member_id):
        if not can_manage_team(request.user):
            return self._deny()
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            if payload.get('action') == 'remove':
                remove_member(request.user, member_id)
            else:
                update_member_role(request.user, member_id, payload.get('role', ''))
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class TeamInboxAPIView(_TeamAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency or not can_operate_team_leads(request.user):
            return self._deny()
        rows = [
            {
                'id': c.pk,
                'name': c.name,
                'phone': c.phone,
                'source': c.source,
                'created_at': c.created_at.isoformat(),
            }
            for c in get_team_inbox(agency)[:100]
        ]
        return JsonResponse({'ok': True, 'leads': rows})

    def post(self, request):
        if not can_operate_team_leads(request.user):
            return self._deny()
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            member_id = int(payload.get('member_id', 0))
            ids = payload.get('customer_ids') or []
            count = bulk_assign_leads(request.user, [int(i) for i in ids], member_id)
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'assigned': count})


class TeamPerformanceAPIView(_TeamAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency or not can_manage_team(request.user):
            return self._deny()
        days = int(request.GET.get('days', 30))
        data = get_team_performance(agency, days=days)
        return JsonResponse({'ok': True, 'performance': {
            'days': data['days'],
            'totals': data['totals'],
            'members': [
                {
                    'rank': r.get('rank'),
                    'name': r['name'],
                    'role': r['role'],
                    'contacts': r['contacts'],
                    'calls': r['calls'],
                    'visits': r['visits'],
                    'deals_closed': r['deals_closed'],
                    'score_pct': r.get('score_pct', 0),
                }
                for r in data['members']
            ],
        }})


class TeamApiKeyRegenerateAPIView(_TeamAPIBase):
    def post(self, request):
        try:
            key = regenerate_api_key(request.user)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        return JsonResponse({'ok': True, 'key': key})


class TeamSyncExportAPIView(_TeamAPIBase):
    def get(self, request):
        if not can_manage_team(request.user):
            return self._deny()
        agency_scope = request.GET.get('scope') == 'agency'
        payload = export_crm_payload(request.user, agency_scope=agency_scope)
        record_sync_log(request.user, 'export', {
            'contacts': len(payload.get('contacts') or []),
            'properties': len(payload.get('properties') or []),
            'deals': len(payload.get('deals') or []),
        })
        return JsonResponse(payload, json_dumps_params={'ensure_ascii': False})


class TeamSyncImportAPIView(_TeamAPIBase):
    def post(self, request):
        if not can_manage_team(request.user):
            return self._deny()
        dry_run = request.GET.get('dry_run') == '1'
        try:
            payload = json.loads(request.body.decode('utf-8'))
            stats = import_crm_payload(request.user, payload, dry_run=dry_run)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'فایل نامعتبر'}, status=400)
        sync_type = 'dry_run' if dry_run else 'import'
        record_sync_log(request.user, sync_type, stats)
        return JsonResponse({'ok': True, 'stats': stats, 'dry_run': dry_run})


class TeamSettingsAPIView(_TeamAPIBase):
    def patch(self, request):
        if not can_manage_team(request.user):
            return self._deny()
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            agency = update_agency_settings(
                request.user,
                name=payload.get('name', ''),
                lead_routing_policy=payload.get('lead_routing_policy', ''),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({
            'ok': True,
            'agency': {
                'name': agency.name,
                'slug': agency.slug,
                'lead_routing_policy': agency.lead_routing_policy,
            },
        })


class TeamReportCSVView(_TeamAPIBase):
    def get(self, request):
        agency = self._agency()
        if not agency or not can_manage_team(request.user):
            return self._deny()
        days = int(request.GET.get('days', 30))
        csv_text = export_team_performance_csv(agency, days=days)
        resp = HttpResponse(csv_text, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="team-performance.csv"'
        return resp


class TeamGoalsAPIView(_TeamAPIBase):
    def post(self, request):
        if not can_manage_team(request.user):
            return self._deny()
        agency = self._agency()
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
            member_id = payload.get('member_id')
            member = None
            if member_id:
                member = CRMAgencyMember.objects.get(pk=member_id, agency=agency, is_active=True)
            period_start, period_end = parse_goal_period_strings(
                str(payload.get('period_start', '')),
                str(payload.get('period_end', '')),
            )
            goal = CRMAgencyTeamGoal.objects.create(
                agency=agency,
                member=member,
                metric=payload.get('metric', 'calls'),
                target_value=int(payload.get('target_value', 0)),
                period_start=period_start,
                period_end=period_end,
            )
        except (json.JSONDecodeError, ValueError, CRMAgencyMember.DoesNotExist) as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'goal_id': goal.pk})


class TeamWebhookTestAPIView(_TeamAPIBase):
    def post(self, request, webhook_id):
        if not can_manage_team(request.user):
            return self._deny()
        agency = self._agency()
        hook = CRMAgencyWebhook.objects.filter(pk=webhook_id, agency=agency).first()
        if not hook:
            return JsonResponse({'ok': False, 'error': 'وب‌هوک یافت نشد'}, status=404)
        ok, msg = test_webhook(hook)
        return JsonResponse({'ok': ok, 'message': msg})
