"""ویوهای CRM حرفه‌ای."""
import json
import logging
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from workspace.constants import (
    AGENCY_ROLES, CRM_PRIORITIES, CRM_PROPERTIES, CRM_SOURCES, CRM_STATUSES, CRM_STATUSES_UI, CRM_TYPES,
    DEAL_FOLLOWUP_TYPES, DEAL_NEXT_ACTION_TYPES, DEAL_STAGES, DEFAULT_STAGNANT_DAYS,
    LEAD_ROUTING_CHOICES, LOST_REASONS, MESSAGE_PLACEHOLDERS,
    MESSAGE_TEMPLATE_CATEGORIES, PROPERTY_ADVERTISER_TYPES, PROPERTY_DEAL_MODES, PROPERTY_PUBLISH_STATUSES,
    PROPERTY_TX_STATUSES, QUICK_ACTIVITY_TYPES, TYPE_PROFILES, VISIT_OUTCOMES, WEBHOOK_EVENTS,
    WEBHOOK_EVENT_LABELS, LEASE_DEADLINE_TYPES,
)
from workspace.services.property_images import (
    MAX_PROPERTY_IMAGES, parse_images_payload, store_property_image,
)
from workspace.export_security import ExportSecurityMixin
from workspace.mixins_agency import AgencyHubAccessMixin, AgencyTeamHubRequiredMixin
from workspace.mixins_crm_rbac import (
    CRMDealsAccessMixin,
    CRMFinanceDashboardAccessMixin,
)
from workspace.forms import (
    ActivityForm, CRMAutomationRuleForm, CRMDealCreateForm, CRMDealForm, CRMMessageTemplateForm,
    CRMPropertyForm, CRMPropertyImportForm, CRMReminderForm, ConvertLeadForm,
    CustomerDocumentForm, CustomerForm, CustomerImportForm, FollowUpForm,
    PropertyDealCreateForm, PropertyLinkForm, PropertyVisitForm, QuickLeadForm,
)
from workspace.models import (
    CRMAgency, CRMAgencyAuditLog, CRMAgencyMember, CRMAgencyMembershipRequest, CRMAgencyTeamGoal,
    CRMAgencyWebhook, CRMAutomationRule, CRMDeal, CRMSyncLog,
    CRMDealCommissionSplit, CRMMessageTemplate, CRMProperty, CRMSavedFilter, Customer,
    CustomerActivity, CustomerDocument, CustomerListing, CustomerTransferLog,
    Listing, PropertyContact, PropertyVisit, Reminder,
)
from workspace.services.crm_agency import (
    assign_customer, assign_lead_to_member, bulk_assign_leads, cancel_membership_request,
    create_agency, get_team_inbox,
    member_display, regenerate_api_key, remove_member, request_join_agency,
    respond_membership_request, role_label, set_commission_splits, sync_agency_member_records,
    transfer_customer, update_agency_settings, update_member_role,
)
from workspace.services.crm_agency_analytics import (
    get_command_center_stats, get_member_performance_row, get_team_goals_progress,
    get_team_performance,
)
from workspace.services.crm_scope import (
    agency_members, can_create_property_deal, can_edit_customer, can_edit_property, can_manage_team,
    can_operate_team_leads, can_view_team_inbox, can_view_team_performance,
    customer_for_user,
    customers_qs, deal_for_user, deals_qs, get_agency, get_membership,
    is_customer_owner, is_property_owner, manager_assigned_customers_qs, properties_qs,
    property_for_user, reminders_qs, team_inbox_qs,
)
from workspace.services.crm_sharing import (
    list_shares_for_customer, list_shares_for_property, revoke_share, share_customer, share_property,
    share_for_customer_recipient,
)
from workspace.services.crm_property_share import (
    build_property_share_context, list_outgoing_property_shares, location_display, share_mode_label,
)
from workspace.services.crm_sync import export_crm_payload, import_crm_payload, record_sync_log
from workspace.services.crm_webhooks import create_lead_from_api, dispatch_webhook, test_webhook, verify_api_key
from workspace.services.crm_audit import log_agency_audit, build_audit_timeline
from workspace.services.crm_agency_features import is_agency_feature_enabled
from workspace.services.crm_agency_tv import get_tv_dashboard_payload, TV_WIDGETS, _agency_logo_url
from workspace.services.crm_agency_messages import unread_message_count
from workspace.services.crm_agency_announcements import unread_announcement_count
from workspace.services.display import to_jalali_display
from workspace.services.jalali_input import (
    format_jalali_date, jalali_month_bounds_display, jalali_quarter_ahead_display,
    parse_goal_period_strings, to_persian_digits,
)
from workspace.services.listing_features import feature_highlights_for_listing, build_listing_feature_profile

logger = logging.getLogger(__name__)

_CRM_LEAD_API_RATE_LIMIT = 60
_CRM_LEAD_API_RATE_WINDOW = 300


def _crm_lead_api_rate_limit_exceeded(client_ip: str) -> bool:
    if not client_ip:
        return False
    cache_key = f'crm_lead_rl:{client_ip}'
    attempts = cache.get(cache_key, 0)
    if attempts >= _CRM_LEAD_API_RATE_LIMIT:
        return True
    cache.set(cache_key, attempts + 1, _CRM_LEAD_API_RATE_WINDOW)
    return False
from workspace.services.features import extract_listing_features
from workspace.services.crm import (
    resolve_listing_for_property,
    apply_contact_suggestions, apply_property_suggestions, build_customer_whatsapp_text,
    build_dashboard_charts,
    complete_follow_up, complete_property_follow_up, convert_lead, export_customers_excel_response,
    export_properties_csv_response, export_properties_excel_response, filter_contacts,
    filter_properties, get_communication_stats, get_dashboard_stats,
    get_overdue_contacts, get_pipeline_data, get_property_pipeline, get_recent_contacts,
    get_recent_properties, get_upcoming_reminders, global_search,
    link_customer_property, log_activity, log_phone_call, log_status_change,
    advance_recurring_reminder, primary_owner_contact, property_advanced_filter_count,
    property_follow_up_state, recent_activities,
    schedule_follow_up, schedule_property_follow_up, set_next_follow_up, sync_follow_up_from_reminder,
    update_customer_status, update_property_transaction_status, reorder_property_pipeline,
    upsert_property_owner, upsert_property_tenant,
)
from workspace.services.crm_analytics import (
    get_conversion_funnel, get_stagnant_contacts, stagnant_count,
)
from workspace.services.crm_automation import (
    AUTOMATION_PRESETS, count_rule_matches, ensure_default_rules,
    run_automation_for_user, run_single_rule,
)
from workspace.services.crm_calendar import get_calendar_month, get_due_notifications
from workspace.services.crm_templates import (
    ensure_default_templates, list_templates, render_message_template, templates_by_category,
)
from workspace.services.crm_deals import (
    apply_deal_commission, create_deal, filter_deals, find_duplicate_active_deal,
    get_property_active_deals, get_property_deal_parties_context, infer_deal_kind_from_property, property_deals_qs,
    search_customers_for_property_deal, serialize_property_deal_customer,
    suggest_deal_title, update_deal_stage,
    get_deal_pipeline, get_deal_stats,
)
from workspace.services.crm_deal_finance import (
    apply_deal_finance, finance_dashboard, get_finance_defaults,
    save_finance_defaults, serialize_deal_finance,
)
from workspace.services.crm_deal_stages import (
    apply_stage_preset, get_user_deal_stage_defs, get_user_deal_stages,
    is_valid_deal_stage, reset_user_deal_stages, save_user_deal_stage_defs,
    serialize_stages_payload, stage_meta_map,
)
from workspace.services.crm_deal_checklist import (
    checklist_progress, ensure_deal_checklist, toggle_checklist_item,
)
from workspace.services.crm_deal_followup import (
    _follow_up_next_action_payload, complete_next_action, create_follow_up, get_deal_timeline,
    parse_next_action_payload, serialize_next_action, set_next_action, clear_next_action,
)
from workspace.services.crm_matching import (
    MATCH_TYPES,
    get_customer_matches,
    get_property_contact_matches,
    normalize_matching_tolerance_percent,
)
from workspace.constants import LEAD_TYPES
from workspace.services.crm_match_notifications import is_match_eligible
from workspace.services.crm_import import (
    build_import_errors_csv,
    import_column_specs,
    import_contacts_from_file_result,
    import_template_excel_response,
    import_template_headers,
)
from workspace.services.crm_redirect import append_query_param, safe_crm_next_url
from workspace.services.crm_property_import import (
    import_properties_from_file, property_import_column_specs,
    property_import_template_excel_response, property_import_template_headers,
)
from workspace.services.crm_merge import (
    find_duplicate_groups, find_duplicates_for_customer_strict, merge_customers,
)
from workspace.services.crm_saved_filters import (
    build_filter_url, current_params_from_request, delete_filter,
    list_saved_filters, save_filter, serialize_filter, toggle_pin,
)
from workspace.services.crm_today import count_today_queue, get_today_queue
from workspace.services.access import has_active_bot_license


def _crm_nav_counts(user):
    membership = get_membership(user)
    team_messages = 0
    team_announcements = 0
    if membership and is_agency_feature_enabled('messages', membership.agency):
        team_messages = unread_message_count(user)
    if membership and is_agency_feature_enabled('announcements', membership.agency):
        team_announcements = unread_announcement_count(user)
    _items, today_stats = get_today_queue(user)
    contracts_action = 0
    try:
        from contracts.services.dashboard import contract_dashboard_stats
        contracts_action = contract_dashboard_stats(user).get('needs_action', 0)
    except Exception:
        contracts_action = 0
    return {
        'contacts': customers_qs(user).count(),
        'properties': properties_qs(user).count(),
        'reminders': reminders_qs(user).filter(is_done=False).count(),
        'today': today_stats['total'],
        'today_overdue': today_stats['overdue'],
        'today_due': today_stats['today'],
        'deals': deals_qs(user).exclude(
            stage__in=['بسته‌شده', 'از دست رفته'],
        ).count(),
        'contracts': contracts_action,
        'team_messages': team_messages,
        'team_announcements': team_announcements,
        'team_hub_unread': team_messages + team_announcements,
    }


def _contact_areas_context(user):
    from workspace.services.filters import get_user_dataset_neighborhoods

    neighborhoods = get_user_dataset_neighborhoods(user)
    return {
        'dataset_neighborhoods': neighborhoods,
        'dataset_neighborhoods_json': json.dumps(neighborhoods, ensure_ascii=False),
    }


class CRMContextMixin:
    def get_context_data(self, **kwargs):
        from workspace.services.crm_video import get_crm_video_context

        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        membership = get_membership(user)
        ctx['crm_video'] = get_crm_video_context()
        ctx['open_modal'] = self.request.GET.get('open', ctx.get('open_modal', ''))
        ctx['crm_nav_counts'] = _crm_nav_counts(user)
        ctx['has_bot_license'] = has_active_bot_license(user)
        ctx['crm_membership'] = membership
        ctx['crm_agency'] = membership.agency if membership else None
        ctx['can_manage_team'] = can_manage_team(user)
        ctx['can_view_team_performance'] = can_view_team_performance(user)
        ctx['can_assign_contacts'] = can_manage_team(user)
        from workspace.services.agency_entitlement import can_share_team_resources

        ctx['can_share_team_resources'] = can_share_team_resources(user)
        ctx['can_share_resources'] = ctx['can_share_team_resources']
        if membership:
            ctx['agency_members'] = list(agency_members(membership.agency))
        else:
            ctx['agency_members'] = []
        return ctx


class CRMDashboardView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/dashboard.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        stats = get_dashboard_stats(user)
        pipeline = get_pipeline_data(user, per_column=5)
        pipe_max = max((col['count'] for col in pipeline), default=1) or 1

        ctx['stats'] = stats
        ctx['charts_json'] = json.dumps([build_dashboard_charts(user)[0]], ensure_ascii=False)
        ctx['recent_activities'] = recent_activities(user, 10)
        ctx['pipeline'] = pipeline
        ctx['pipeline_max'] = pipe_max
        ctx['due_contacts'] = customers_qs(user).filter(
            next_follow_up=today,
            status__in=['جدید', 'در حال پیگیری'],
        ).order_by('next_follow_up')[:6]
        ctx['overdue_contacts'] = get_overdue_contacts(user, 8)
        ctx['upcoming_reminders'] = get_upcoming_reminders(user, 6)
        ctx['recent_properties'] = get_recent_properties(user, 5)
        ctx['recent_contacts'] = get_recent_contacts(user, 6)
        ctx['communication_stats'] = get_communication_stats(user)
        ctx['crm_statuses'] = CRM_STATUSES
        ctx['crm_section'] = 'dashboard'
        ctx['today_count'] = count_today_queue(user)
        ctx['quick_lead_form'] = QuickLeadForm()
        ctx['crm_sources'] = CRM_SOURCES
        run_automation_for_user(user)
        ctx['conversion_funnel'] = get_conversion_funnel(user)
        ctx['stagnant_contacts'] = get_stagnant_contacts(user, DEFAULT_STAGNANT_DAYS, 6)
        ctx['stagnant_count'] = stagnant_count(user, DEFAULT_STAGNANT_DAYS)
        return ctx


class CRMTodayView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    """صف کار روزانه — پیگیری‌ها و یادآورها."""
    template_name = 'workspace/crm/today.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items, stats = get_today_queue(self.request.user)
        ctx['queue_items'] = items
        ctx['queue_stats'] = stats
        ctx['crm_section'] = 'today'
        ctx['quick_lead_form'] = QuickLeadForm()
        ctx['crm_sources'] = CRM_SOURCES
        from workspace.services.crm_smart_command import inject_smart_command_context

        inject_smart_command_context(ctx, self.request, 'today')
        ctx['reminder_form'] = ctx.get('reminder_form', CRMReminderForm())
        ctx['crm_customers'] = customers_qs(self.request.user).order_by('name')[:200]
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        if not items and stats.get('total', 0) == 0:
            from workspace.academy.context_helpers import inject_academy_context
            inject_academy_context(ctx, self.request.user, 'today_empty')
        return ctx

    def post(self, request):
        if request.POST.get('reminder_create') == '1':
            form = CRMReminderForm(request.POST)
            if form.is_valid():
                reminder = form.save(commit=False)
                reminder.user = request.user
                customer_id = request.POST.get('customer_id')
                if customer_id:
                    linked = customer_for_user(request.user, int(customer_id))
                    if not linked or not can_edit_customer(request.user, linked):
                        messages.error(request, 'مخاطب انتخاب‌شده یافت نشد.')
                        ctx = self.get_context_data()
                        ctx['reminder_form'] = form
                        ctx['open_drawer'] = 'reminder'
                        return render(request, self.template_name, ctx)
                    reminder.customer = linked
                reminder.save()
                messages.success(request, 'یادآور ثبت شد.')
                return redirect('workspace:crm_today')
            ctx = self.get_context_data()
            ctx['reminder_form'] = form
            ctx['open_drawer'] = 'reminder'
            for errors in form.errors.values():
                for err in errors:
                    messages.error(request, str(err))
            return render(request, self.template_name, ctx)

        action = request.POST.get('action', '')
        customer_id = request.POST.get('customer_id')
        reminder_id = request.POST.get('reminder_id')
        nxt = request.POST.get('next') or reverse('workspace:crm_today')

        if action == 'complete_followup' and customer_id:
            customer = customer_for_user(request.user, int(customer_id))
            if not customer:
                messages.error(request, 'مخاطب یافت نشد.')
            elif not can_edit_customer(request.user, customer):
                messages.error(request, 'این مخاطب فقط برای مشاهده به اشتراک گذاشته شده است.')
            elif complete_follow_up(customer, request.POST.get('note', '')):
                messages.success(request, f'پیگیری «{customer.name}» انجام شد.')
            else:
                messages.warning(request, 'پیگیری فعالی برای بستن وجود ندارد.')
        elif action == 'toggle_reminder' and reminder_id:
            reminder = reminders_qs(request.user).filter(pk=reminder_id).first()
            if not reminder:
                messages.error(request, 'یادآور یافت نشد.')
            else:
                was_done = reminder.is_done
                reminder.is_done = not reminder.is_done
                reminder.save(update_fields=['is_done'])
                if not was_done and reminder.is_done and reminder.recurrence:
                    advance_recurring_reminder(reminder)
                messages.success(request, 'یادآور به‌روز شد.')
        elif action == 'log_call' and customer_id:
            customer = customer_for_user(request.user, int(customer_id))
            if not customer:
                messages.error(request, 'مخاطب یافت نشد.')
            elif not can_edit_customer(request.user, customer):
                messages.error(request, 'این مخاطب فقط برای مشاهده به اشتراک گذاشته شده است.')
            else:
                log_phone_call(customer, 'تماس از صف کار امروز')
                messages.success(request, 'تماس ثبت شد.')

        return redirect(nxt)


class CustomerListView(CRMContextMixin, LoginRequiredMixin, ListView):
    model = Customer
    template_name = 'workspace/crm/contacts/list.html'
    context_object_name = 'customers'
    paginate_by = 25

    def get_paginate_by(self, queryset):
        if self.request.GET.get('view') == 'pipeline':
            from workspace.services.crm_contact_archive import (
                ARCHIVE_SCOPE_ALL,
                ARCHIVE_SCOPE_ARCHIVED,
            )
            archive_scope = (self.request.GET.get('archive_scope') or 'active').strip().lower()
            if archive_scope in (ARCHIVE_SCOPE_ARCHIVED, ARCHIVE_SCOPE_ALL):
                return self.paginate_by
            return None
        return self.paginate_by

    def render_to_response(self, context, **response_kwargs):
        from workspace.services.crm_contact_archive import (
            ARCHIVE_SCOPE_ACTIVE,
            ARCHIVE_SCOPE_ALL,
            ARCHIVE_SCOPE_ARCHIVED,
        )
        archive_scope = (self.request.GET.get('archive_scope') or ARCHIVE_SCOPE_ACTIVE).strip().lower()
        view_mode = context.get('view_mode') or self.request.GET.get('view', 'table')
        if archive_scope in (ARCHIVE_SCOPE_ARCHIVED, ARCHIVE_SCOPE_ALL):
            view_mode = 'table'
        if self.request.GET.get('partial') == '1' and view_mode != 'pipeline':
            page_obj = context.get('page_obj')
            html = render_to_string(
                'workspace/crm/contacts/_contact_table_rows.html',
                context,
                request=self.request,
            )
            return JsonResponse({
                'html': html,
                'has_next': bool(page_obj and page_obj.has_next()),
                'next_page': page_obj.next_page_number() if page_obj and page_obj.has_next() else None,
            })
        return super().render_to_response(context, **response_kwargs)

    def get_queryset(self):
        batch_param = (self.request.GET.get('import_batch') or '').strip()
        if batch_param:
            from workspace.services.crm_import_batch import resolve_import_batch_qs_ids

            ids, _meta = resolve_import_batch_qs_ids(self.request.user.id, batch_param)
            if ids is not None:
                return (
                    customers_qs(self.request.user)
                    .filter(pk__in=ids)
                    .order_by('-created_at')
                )
        return filter_contacts(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.GET.get('partial') == '1':
            ctx['match_eligible_types'] = MATCH_TYPES | LEAD_TYPES
            ctx['today'] = timezone.now().date()
            return ctx
        user = self.request.user
        today = timezone.now().date()
        from workspace.services.crm_contact_archive import (
            ARCHIVE_SCOPE_ACTIVE,
            ARCHIVE_SCOPE_ALL,
            ARCHIVE_SCOPE_ARCHIVED,
            archived_contacts_q,
        )

        cqs = customers_qs(user)
        active_cqs = cqs.exclude(archived_contacts_q())
        archived_cqs = cqs.filter(archived_contacts_q())
        archive_scope = (self.request.GET.get('archive_scope') or ARCHIVE_SCOPE_ACTIVE).strip().lower()
        ctx['archive_scope'] = archive_scope

        def _tab_qs(scope: str) -> str:
            pairs = {
                k: v for k, v in self.request.GET.items()
                if k not in ('page', 'partial', 'archive_scope') and v
            }
            if scope != ARCHIVE_SCOPE_ACTIVE:
                pairs['archive_scope'] = scope
            return urlencode(pairs)

        ctx['archive_tab_qs'] = {
            ARCHIVE_SCOPE_ACTIVE: _tab_qs(ARCHIVE_SCOPE_ACTIVE),
            ARCHIVE_SCOPE_ARCHIVED: _tab_qs(ARCHIVE_SCOPE_ARCHIVED),
            ARCHIVE_SCOPE_ALL: _tab_qs(ARCHIVE_SCOPE_ALL),
        }
        ctx['stats'] = {
            'total': active_cqs.count(),
            'archived': archived_cqs.count(),
            'all': cqs.count(),
            'new': active_cqs.filter(status='جدید').count(),
            'in_progress': active_cqs.filter(status='در حال پیگیری').count(),
            'due_today': active_cqs.filter(next_follow_up=today).count(),
        }
        ctx['customer_form'] = ctx.get('customer_form', CustomerForm())
        ctx['open_modal'] = self.request.GET.get('open', ctx.get('open_modal', ''))
        ctx['crm_types'] = CRM_TYPES
        ctx['crm_statuses'] = CRM_STATUSES_UI
        ctx['crm_statuses_all'] = CRM_STATUSES
        ctx['crm_priorities'] = CRM_PRIORITIES
        ctx['crm_sources'] = CRM_SOURCES
        ctx['type_profiles_json'] = json.dumps(TYPE_PROFILES, ensure_ascii=False)
        ctx['lease_deadline_types_json'] = json.dumps(sorted(LEASE_DEADLINE_TYPES), ensure_ascii=False)
        ctx['crm_section'] = 'contacts'
        ctx['filter_qs'] = urlencode({
            k: v for k, v in self.request.GET.items()
            if k not in ('view', 'page', 'open', 'partial', 'import_batch') and v
        })
        batch_param = (self.request.GET.get('import_batch') or '').strip()
        if batch_param:
            from workspace.services.crm_import_batch import get_import_batch
            batch = get_import_batch(user.id, batch_param)
            if batch:
                ctx['import_batch_meta'] = batch
                ctx['import_batch_id'] = batch_param
        ctx['show_import_errors_download'] = bool(self.request.session.get('crm_import_error_report'))
        if archive_scope in (ARCHIVE_SCOPE_ARCHIVED, ARCHIVE_SCOPE_ALL):
            ctx['view_mode'] = 'table'
            ctx['pipeline'] = []
            ctx['pipeline_interactive'] = False
        else:
            ctx['view_mode'] = self.request.GET.get('view', 'table')
            ctx['pipeline'] = get_pipeline_data(self.request.user, per_column=50)
            ctx['pipeline_interactive'] = True
        from workspace.services.crm_contact_archive import COMMUNICATION_STATUSES
        ctx['bulk_restore_statuses'] = COMMUNICATION_STATUSES
        ctx['quick_lead_form'] = ctx.get('quick_lead_form', QuickLeadForm())
        ctx['status_update_url_template'] = reverse(
            'workspace:crm_contact_status', kwargs={'customer_id': 0},
        ).replace('/0/', '/{id}/')
        ctx['duplicate_groups'] = find_duplicate_groups(self.request.user)[:5]
        ctx['import_form'] = ctx.get('import_form', CustomerImportForm())
        ctx['import_headers'] = import_template_headers()
        ctx['import_column_specs'] = import_column_specs()
        ctx['import_allowed_values'] = {
            'types': list(CRM_TYPES),
            'statuses': list(CRM_STATUSES),
            'priorities': list(CRM_PRIORITIES),
            'sources': list(CRM_SOURCES),
        }
        ctx['bulk_statuses'] = CRM_STATUSES_UI
        ctx['saved_filters'] = list_saved_filters(user, 'contacts')
        ctx['saved_filter_scope'] = 'contacts'
        ctx['saved_filter_base'] = reverse('workspace:crm_contacts')
        ctx['saved_filter_params'] = current_params_from_request(self.request, 'contacts')
        ctx['saved_filter_can_save'] = bool(ctx['saved_filter_params'])
        ctx['match_eligible_types'] = MATCH_TYPES | LEAD_TYPES
        ctx['today'] = today
        ctx.update(_contact_areas_context(user))
        from workspace.services.crm_smart_command import inject_smart_command_context

        inject_smart_command_context(ctx, self.request, 'contacts')
        if ctx['stats']['total'] == 0:
            from workspace.academy.context_helpers import inject_academy_context
            inject_academy_context(ctx, user, 'contacts_empty')
        return ctx


class CustomerQuickCreateView(LoginRequiredMixin, View):
    """ثبت سریع سرنخ."""

    def post(self, request):
        form = QuickLeadForm(request.POST, user=request.user)
        if form.is_valid():
            customer = form.save(user=request.user)
            log_activity(customer, 'یادداشت', content='سرنخ سریع ثبت شد.', title='ثبت سرنخ')
            messages.success(request, f'سرنخ «{customer.name}» ثبت شد.')
            nxt = request.POST.get('next') or reverse('workspace:crm_contacts')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'ok': True,
                    'id': customer.id,
                    'name': customer.name,
                    'url': reverse('workspace:crm_detail', kwargs={'customer_id': customer.id}),
                })
            return redirect(nxt)
        messages.error(request, 'ثبت سرنخ انجام نشد. نام الزامی است.')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        view = CustomerListView()
        view.setup(request)
        view.object_list = view.get_queryset()
        ctx = view.get_context_data(object_list=view.object_list)
        ctx['quick_lead_form'] = form
        ctx['open_modal'] = 'drawer-quick-lead'
        return render(request, 'workspace/crm/contacts/list.html', ctx)


class CustomerStatusUpdateView(LoginRequiredMixin, View):
    """تغییر وضعیت مخاطب — pipeline تعاملی."""

    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not can_edit_customer(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند وضعیت را تغییر دهد'}, status=403)
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            new_status = (payload.get('status') or '').strip()
        else:
            new_status = (request.POST.get('status') or '').strip()

        if new_status not in CRM_STATUSES:
            return JsonResponse({'ok': False, 'error': 'وضعیت نامعتبر'}, status=400)
        try:
            update_customer_status(customer, new_status, user=request.user)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        customer.refresh_from_db()
        from workspace.services.crm_contact_archive import contact_display_status, is_contact_archived

        return JsonResponse({
            'ok': True,
            'status': customer.status,
            'display_status': contact_display_status(customer),
            'archived': is_contact_archived(customer),
            'customer_id': customer.pk,
        })


class CRMContactArchiveView(LoginRequiredMixin, View):
    """بایگانی تک‌مخاطب."""

    def post(self, request, customer_id):
        from workspace.services.crm_contact_archive import archive_contact, is_contact_archived

        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        try:
            archive_contact(
                request.user,
                customer,
                reason=(payload.get('reason') or ''),
                archive_note=(payload.get('note') or ''),
                reactivation_due_jalali=(payload.get('reactivation_due_jalali') or ''),
            )
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        customer.refresh_from_db()
        return JsonResponse({
            'ok': True,
            'archived': is_contact_archived(customer),
            'customer_id': customer.pk,
        })


class CRMContactRestoreView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        from workspace.services.crm_contact_archive import (
            contact_display_status,
            is_contact_archived,
            restore_contact,
        )

        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        try:
            restore_contact(
                request.user,
                customer,
                restore_status=(payload.get('restore_status') or request.POST.get('restore_status') or ''),
            )
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        customer.refresh_from_db()
        return JsonResponse({
            'ok': True,
            'archived': is_contact_archived(customer),
            'status': customer.status,
            'display_status': contact_display_status(customer),
            'customer_id': customer.pk,
        })


class CRMContactBulkArchiveView(LoginRequiredMixin, View):
    def post(self, request):
        from workspace.services.crm_contact_archive import bulk_archive_contacts, bulk_restore_contacts

        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            ids = payload.get('contact_ids') or payload.get('ids') or []
            action = (payload.get('action') or 'archive').strip().lower()
            reason = (payload.get('reason') or '').strip()
            restore_status = (payload.get('restore_status') or '').strip()
        else:
            ids = request.POST.getlist('contact_ids') or request.POST.get('ids', '').split(',')
            action = (request.POST.get('action') or 'archive').strip().lower()
            reason = (request.POST.get('reason') or '').strip()
            restore_status = (request.POST.get('restore_status') or '').strip()

        if action == 'restore':
            result = bulk_restore_contacts(request.user, ids, restore_status=restore_status)
            ok_count = result.get('restored', 0)
            label = 'بازگردانی'
        else:
            result = bulk_archive_contacts(request.user, ids, reason=reason)
            ok_count = result.get('archived', 0)
            label = 'بایگانی'

        if ok_count == 0:
            return JsonResponse({
                'ok': False,
                'error': f'مخاطبی برای {label} انتخاب نشده یا دسترسی ندارید.',
                **result,
            }, status=400)
        return JsonResponse({
            'ok': True,
            'message': f'{ok_count} مخاطب {label} شد.',
            **result,
        })


def _parse_match_page_params(request) -> dict:
    def _page(name: str, fallback: int = 1) -> int:
        try:
            return max(1, int(request.GET.get(name, fallback) or fallback))
        except (TypeError, ValueError):
            return fallback

    base = _page('page', 1)
    return {
        'crm_page': _page('crm_page', base),
        'divar_page': _page('divar_page', base),
    }


def _contact_matches_panel_context(user, customer, request, *, rebuild_index: bool = False):
    """Context برای رندر پنل پیشنهاد ملک."""
    divar_enabled = has_active_bot_license(user)
    page_kw = _parse_match_page_params(request) if request is not None else {'crm_page': 1, 'divar_page': 1}
    match_data = get_customer_matches(
        customer, user,
        divar_enabled=divar_enabled,
        rebuild_index=rebuild_index,
        **page_kw,
    )
    from workspace.services.property_suggestion_share import enrich_match_data_links
    match_data = enrich_match_data_links(user, request, match_data)
    return {
        'match_data': match_data,
        'customer': customer,
        'has_bot_license': divar_enabled,
        'suggested': False,
        'suggestion_text': '',
        'match_eligible': is_match_eligible(customer),
        'can_edit_customer': can_edit_customer(user, customer),
    }


class CustomerMatchesMoreView(LoginRequiredMixin, View):
    """بارگذاری صفحه بعدی پیشنهادها — CRM یا Divar."""

    def get(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        source = (request.GET.get('source') or '').strip()
        if source not in ('crm', 'divar'):
            return JsonResponse({'ok': False, 'error': 'منبع نامعتبر'}, status=400)
        try:
            page = max(1, int(request.GET.get('page', 2) or 2))
        except (TypeError, ValueError):
            page = 2
        divar_enabled = has_active_bot_license(request.user)
        if source == 'divar' and not divar_enabled:
            return JsonResponse({'ok': False, 'error': 'لایسنس فایلینگ دیوار فعال نیست'}, status=403)

        kw = {'crm_page': 1, 'divar_page': 1}
        if source == 'crm':
            kw['crm_page'] = page
        else:
            kw['divar_page'] = page
        data = get_customer_matches(
            customer, request.user,
            divar_enabled=divar_enabled,
            **kw,
        )
        group_id = (request.GET.get('group') or '').strip()
        if group_id in ('acquisition', 'supply') and data.get('is_builder'):
            group = next(
                (g for g in (data.get('match_groups') or []) if g.get('id') == group_id),
                None,
            )
            if not group:
                return JsonResponse({'ok': False, 'error': 'گروه نامعتبر'}, status=400)
            matches = group.get('crm_matches') if source == 'crm' else group.get('divar_matches')
            has_more = bool(
                group.get('crm_has_more') if source == 'crm' else group.get('divar_has_more')
            )
            total_count = int(
                group.get('crm_total_count') if source == 'crm' else group.get('divar_total_count') or 0
            )
        else:
            matches = data.get('crm_matches') if source == 'crm' else data.get('divar_matches')
            has_more = bool(data.get('crm_has_more') if source == 'crm' else data.get('divar_has_more'))
            total_count = int(
                data.get('crm_total_count' if source == 'crm' else 'divar_total_count') or 0
            )
        cards_html = ''.join(
            render_to_string(
                'workspace/crm/includes/match_card.html',
                {'m': m, 'source': source},
                request=request,
            )
            for m in (matches or [])
        )
        return JsonResponse({
            'ok': True,
            'source': source,
            'html': cards_html,
            'has_more': has_more,
            'next_page': page + 1,
            'total_count': total_count,
        })


class PropertyContactMatchesMoreView(LoginRequiredMixin, View):
    """صفحه بعدی پیشنهاد مخاطب برای فایل شخصی."""

    def get(self, request, property_id):
        from workspace.services.crm_scope import can_edit_property, property_for_user

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'فایل یافت نشد'}, status=404)
        if not can_edit_property(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست'}, status=403)
        try:
            page = max(1, int(request.GET.get('page', 2) or 2))
        except (TypeError, ValueError):
            page = 2
        data = get_property_contact_matches(prop, request.user, page=page)
        cards_html = ''.join(
            render_to_string(
                'workspace/crm/includes/contact_match_card.html',
                {'m': m},
                request=request,
            )
            for m in (data.get('matches') or [])
        )
        return JsonResponse({
            'ok': True,
            'html': cards_html,
            'has_more': bool(data.get('has_more')),
            'next_page': page + 1,
            'total_count': int(data.get('total_count') or 0),
        })


class ContactAreasSearchView(LoginRequiredMixin, View):
    """جست‌وجوی محله‌های فایلینگ برای انتخابگر مخاطب."""

    def get(self, request):
        from workspace.services.filters import get_user_dataset_neighborhoods

        q = (request.GET.get('q') or '').strip()
        try:
            offset = max(0, int(request.GET.get('offset', 0) or 0))
        except (TypeError, ValueError):
            offset = 0
        limit = 80
        items = get_user_dataset_neighborhoods(
            request.user, search=q, offset=offset, limit=limit,
        )
        return JsonResponse({
            'ok': True,
            'items': items,
            'offset': offset,
            'has_more': len(items) >= limit,
        })


class CustomerMatchingToleranceView(LoginRequiredMixin, View):
    """ذخیره انعطاف‌پذیری تطبیق و بازمحاسبه پیشنهادها."""

    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not can_edit_customer(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'امکان ویرایش این مخاطب را ندارید'}, status=403)
        if not request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)

        raw = payload.get('matching_tolerance_percent')
        try:
            pct = normalize_matching_tolerance_percent(raw)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        customer.matching_tolerance_percent = pct
        customer.save(update_fields=['matching_tolerance_percent', 'updated_at'])

        panel_ctx = _contact_matches_panel_context(
            request.user, customer, request, rebuild_index=True,
        )
        match_data = panel_ctx['match_data']
        from workspace.templatetags.crm_tags import crm_match_tab_count
        matches_html = render_to_string(
            'workspace/crm/includes/matches_panel.html',
            panel_ctx,
            request=request,
        )
        return JsonResponse({
            'ok': True,
            'matching_tolerance_percent': pct,
            'match_tab_count': crm_match_tab_count(match_data),
            'total_count': int(match_data.get('total_count') or 0),
            'matches_html': matches_html,
        })


class CustomerPanelView(LoginRequiredMixin, View):
    """پنل کناری — خلاصه مخاطب."""

    def get(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        today = timezone.now().date()
        fu = customer.next_follow_up
        if fu is None:
            follow_state = 'none'
        elif fu < today:
            follow_state = 'overdue'
        elif fu == today:
            follow_state = 'today'
        else:
            follow_state = 'upcoming'

        matches = get_customer_matches(
            customer, request.user,
            divar_enabled=has_active_bot_license(request.user),
        )
        match_count = int(matches.get('total_count') or 0)

        activities = [
            {
                'activity_type': row['activity_type'],
                'title': row['title'],
                'content': row['content'],
                'created_at': to_persian_digits(
                    to_jalali_display(timezone.localtime(row['created_at']))
                ),
            }
            for row in customer.activities.order_by('-created_at')[:5].values(
                'activity_type', 'title', 'content', 'created_at',
            )
        ]

        phone_wa = ''
        if customer.phone and len(customer.phone) >= 10:
            phone_wa = customer.phone.lstrip('0')
            if phone_wa.startswith('98'):
                phone_wa = phone_wa[2:]

        from accounts.avatar_catalog import resolve_contact_avatar_display
        from workspace.templatetags.crm_tags import crm_avatar_hue, crm_initials, crm_status_dot

        contact_avatar = resolve_contact_avatar_display(customer, request=request)
        panel_avatar_url = contact_avatar['photo_url'] or ''

        return JsonResponse({
            'id': customer.pk,
            'name': customer.name,
            'company_name': customer.company_name or '',
            'initials': crm_initials(customer.name),
            'avatar_hue': crm_avatar_hue(customer.name),
            'avatar_url': panel_avatar_url,
            'status_dot': crm_status_dot(customer.status),
            'phone': customer.phone,
            'email': customer.email,
            'customer_type': customer.customer_type,
            'status': customer.status,
            'priority': customer.priority,
            'source': customer.source,
            'next_follow_up': to_persian_digits(format_jalali_date(fu)) if fu else '',
            'follow_state': follow_state,
            'notes': (customer.notes or '')[:280],
            'areas': customer.areas or '',
            'budget_label': _panel_budget_label(customer),
            'detail_url': reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk}),
            'edit_url': f"{reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk})}?drawer=edit",
            'matches_url': f"{reverse('workspace:crm_detail', kwargs={'customer_id': customer.pk})}?tab=matches",
            'match_eligible': is_match_eligible(customer),
            'whatsapp_url': f'https://wa.me/98{phone_wa}' if phone_wa else '',
            'tel_url': f'tel:{customer.phone}' if customer.phone else '',
            'match_count': match_count,
            'activities': activities,
        })


def _panel_budget_label(customer: Customer) -> str:
    from workspace.services.formatting import format_toman

    if customer.budget_min or customer.budget_max:
        lo = format_toman(customer.budget_min) if customer.budget_min else '—'
        hi = format_toman(customer.budget_max) if customer.budget_max else '—'
        return f'{lo} تا {hi}'
    if customer.rent_min or customer.rent_max:
        lo = format_toman(customer.rent_min) if customer.rent_min else '—'
        hi = format_toman(customer.rent_max) if customer.rent_max else '—'
        return f'اجاره {lo} تا {hi}'
    return ''


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'workspace/crm/contacts/list.html'
    success_url = reverse_lazy('workspace:crm_contacts')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('workspace:crm_contacts')}?open=drawer-contact")

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.agency = get_agency(self.request.user)
        self.object = form.save()
        log_activity(self.object, 'یادداشت', content='مخاطب جدید ثبت شد.', title='ثبت مخاطب')
        messages.success(self.request, f'مخاطب «{self.object.name}» با موفقیت ثبت شد.')
        return redirect('workspace:crm_contacts')

    def form_invalid(self, form):
        messages.error(
            self.request,
            'ثبت مخاطب انجام نشد. لطفاً خطاهای فرم را بررسی کنید.',
        )
        view = CustomerListView()
        view.setup(self.request)
        view.object_list = view.get_queryset()
        ctx = view.get_context_data(object_list=view.object_list)
        ctx['customer_form'] = form
        ctx['open_modal'] = 'drawer-contact'
        return render(self.request, self.template_name, ctx)


class CustomerDetailView(CRMContextMixin, LoginRequiredMixin, DetailView):
    model = Customer
    template_name = 'workspace/crm/contacts/detail.html'
    context_object_name = 'customer'
    pk_url_kwarg = 'customer_id'

    def get_queryset(self):
        return customers_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        c = self.object
        ctx['activities'] = c.activities.select_related('property').all()[:50]
        ctx['property_links'] = c.property_links.select_related('property').all()
        ctx['linked_listings'] = c.linked_listings.select_related('crm_property').all()
        link_tokens = [lk.token for lk in ctx['linked_listings'] if lk.token]
        listings_by_token = {
            lst.token: lst
            for lst in Listing.objects.filter(
                dataset__user=self.request.user,
                token__in=link_tokens,
            ).select_related('dataset')
        }
        ctx['linked_listing_highlights'] = {
            token: feature_highlights_for_listing(lst, limit=3)
            for token, lst in listings_by_token.items()
        }
        from workspace.services.property_suggestion_share import (
            public_share_url_for_listing,
            public_share_url_for_property,
        )
        for link in ctx['property_links']:
            share_url = ''
            if link.property_id:
                try:
                    share_url = public_share_url_for_property(
                        self.request.user, self.request, link.property,
                    )
                except Exception:
                    share_url = ''
            link.public_share_url = share_url
        for cl in ctx['linked_listings']:
            share_url = ''
            filing_url = ''
            listing = listings_by_token.get(cl.token)
            if listing is not None:
                filing_url = reverse(
                    'workspace:listing_detail',
                    kwargs={'dataset_id': listing.dataset_id, 'listing_id': listing.pk},
                )
            elif cl.crm_property_id:
                filing_url = reverse(
                    'workspace:crm_property_detail',
                    kwargs={'property_id': cl.crm_property_id},
                )
            try:
                if listing is not None:
                    share_url = public_share_url_for_listing(
                        self.request.user, self.request, listing,
                    )
                elif cl.crm_property_id:
                    share_url = public_share_url_for_property(
                        self.request.user, self.request, cl.crm_property,
                    )
            except Exception:
                share_url = ''
            cl.public_share_url = share_url
            cl.filing_url = filing_url
        ctx['reminders'] = c.reminders.filter(is_done=False).order_by('due_at')
        ctx['documents'] = c.documents.all()
        ctx['customer_form'] = CustomerForm(instance=c)
        ctx['activity_form'] = ActivityForm()
        ctx['activity_quick_types'] = QUICK_ACTIVITY_TYPES
        ctx['followup_form'] = FollowUpForm()
        ctx['reminder_form'] = CRMReminderForm()
        today = timezone.now().date()
        fu = c.next_follow_up
        if fu is None:
            ctx['follow_up_state'] = 'none'
        elif fu < today:
            ctx['follow_up_state'] = 'overdue'
        elif fu == today:
            ctx['follow_up_state'] = 'today'
        else:
            ctx['follow_up_state'] = 'upcoming'
        ctx['follow_up_logs'] = c.activities.filter(activity_type='پیگیری')[:8]
        ctx['document_form'] = CustomerDocumentForm()
        ctx['convert_form'] = ConvertLeadForm(c)
        ctx['property_link_form'] = PropertyLinkForm()
        ctx['user_properties'] = properties_qs(self.request.user).order_by('-updated_at')[:100]
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        ctx['type_profiles_json'] = json.dumps(TYPE_PROFILES, ensure_ascii=False)
        ctx['lease_deadline_types_json'] = json.dumps(sorted(LEASE_DEADLINE_TYPES), ensure_ascii=False)
        ctx['whatsapp_text'] = build_customer_whatsapp_text(c)
        from workspace.services.contact_channels import contact_channels_for_display
        ctx['contact_messaging_channels'] = contact_channels_for_display(
            c, message=ctx['whatsapp_text'],
        )
        ctx['crm_section'] = 'contacts'
        divar_enabled = has_active_bot_license(self.request.user)
        ctx.update(_contact_matches_panel_context(self.request.user, c, self.request))
        ctx['match_data_json'] = json.dumps(ctx['match_data'], ensure_ascii=False)
        ctx['match_eligible'] = is_match_eligible(c)
        ctx['can_edit_customer'] = can_edit_customer(self.request.user, c)
        ctx['suggestion_text'] = self.request.session.pop('crm_last_suggestion_text', '')
        ctx['active_tab'] = self.request.GET.get('tab', '')
        ctx['suggested'] = self.request.GET.get('suggested', '')
        ctx['deals'] = c.deals.select_related('property').all()[:10]
        ctx['visits'] = c.visits.select_related('property').all()[:20]
        ctx['visit_form'] = PropertyVisitForm(user=self.request.user)
        ctx['deal_form'] = CRMDealCreateForm(user=self.request.user, initial={'customer': c})
        ctx['deal_create_form'] = ctx['deal_form']
        ctx['duplicate_candidates'] = find_duplicates_for_customer_strict(c)
        ctx['visit_outcomes'] = VISIT_OUTCOMES
        ctx['message_templates'] = list_templates(self.request.user)
        ctx['is_customer_owner'] = is_customer_owner(self.request.user, c)
        ctx['customer_shares'] = list_shares_for_customer(c) if ctx['is_customer_owner'] else []
        ctx['customer_is_shared'] = not ctx['is_customer_owner'] and c.user_id != self.request.user.id
        ctx['customer_share'] = (
            share_for_customer_recipient(self.request.user, c) if ctx['customer_is_shared'] else None
        )
        from workspace.services.crm_contact_archive import (
            ARCHIVE_REASON_CHOICES,
            COMMUNICATION_STATUSES,
            contact_display_status,
            contact_last_communication_status,
            is_contact_archived,
            lease_deadline_reactivation_suggestion,
            open_reminders_count,
        )

        ctx['contact_is_archived'] = is_contact_archived(c)
        ctx['contact_display_status'] = contact_display_status(c)
        ctx['contact_last_communication_status'] = contact_last_communication_status(c)
        ctx['contact_open_reminders_count'] = open_reminders_count(self.request.user, c)
        has_lease_suggestion, lease_suggestion_jalali = lease_deadline_reactivation_suggestion(c)
        ctx['contact_lease_reactivation_suggestion'] = lease_suggestion_jalali if has_lease_suggestion else ''
        ctx['contact_archive_reasons'] = ARCHIVE_REASON_CHOICES
        ctx['crm_statuses'] = COMMUNICATION_STATUSES if ctx['contact_is_archived'] else CRM_STATUSES_UI
        ctx['crm_statuses_restore'] = COMMUNICATION_STATUSES
        ctx.update(_contact_areas_context(self.request.user))
        from workspace.services.contact_nba import build_contact_workflow
        workflow = build_contact_workflow(
            customer=c,
            follow_up_state=ctx['follow_up_state'],
            activities=ctx['activities'],
            match_data=ctx.get('match_data'),
            property_links=ctx['property_links'],
            linked_listings=ctx['linked_listings'],
            visits=ctx['visits'],
            deals=ctx['deals'],
            can_edit=bool(ctx['can_edit_customer']) and not ctx['customer_is_shared'],
        )
        ctx['contact_nba'] = workflow['nba']
        ctx['contact_summary'] = workflow['summary']
        ctx['after_call_prompt'] = (
            (
                self.request.GET.get('after_call') == '1'
                or self.request.session.get('crm_after_call_id') == c.pk
            )
            and bool(ctx['can_edit_customer'])
            and not ctx['customer_is_shared']
        )
        if ctx['after_call_prompt'] and self.request.session.get('crm_after_call_id') == c.pk:
            self.request.session.pop('crm_after_call_id', None)
        from workspace.services.agency_space_ui_context import apply_agency_space_crm_context
        from workspace.services.agency_space_provenance import provenance_for_customer
        apply_agency_space_crm_context(ctx, self.request.user, customer=c)
        ctx['agency_space_copy_provenance'] = provenance_for_customer(c, self.request.user)
        return ctx

    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            messages.error(request, 'مخاطب یافت نشد.')
            return redirect('workspace:crm_contacts')
        if not can_edit_customer(request.user, customer):
            messages.error(request, 'این مخاطب فقط برای مشاهده به اشتراک گذاشته شده — امکان ویرایش ندارید.')
            return redirect('workspace:crm_detail', customer_id=customer_id)
        action = request.POST.get('action', '')
        redirect_url = reverse('workspace:crm_detail', kwargs={'customer_id': customer_id})

        if action == 'add_activity':
            form = ActivityForm(request.POST)
            if form.is_valid():
                title = (form.cleaned_data.get('title') or '').strip()
                content = (form.cleaned_data.get('content') or '').strip()
                if not content:
                    content = title or form.cleaned_data['activity_type']
                log_activity(
                    customer,
                    form.cleaned_data['activity_type'],
                    content,
                    title=title,
                    duration_minutes=form.cleaned_data.get('duration_minutes'),
                )
                follow_date = form.cleaned_data.get('next_follow_up')
                if follow_date:
                    set_next_follow_up(customer, follow_date)
                messages.success(request, 'فعالیت ثبت شد.')
                redirect_url += '?tab=timeline'
            else:
                self.object = customer
                ctx = self.get_context_data(object=customer)
                ctx['activity_form'] = form
                ctx['open_drawer'] = 'activity'
                ctx['active_tab'] = 'timeline'
                for errors in form.errors.values():
                    for err in errors:
                        messages.error(request, str(err))
                return render(request, self.template_name, ctx)

        elif action == 'schedule_followup':
            form = FollowUpForm(request.POST)
            if form.is_valid():
                schedule_follow_up(
                    customer,
                    form.cleaned_data['next_follow_up'],
                    form.cleaned_data.get('note', ''),
                )
                messages.success(request, 'پیگیری ثبت شد.')
            else:
                for err in form.errors.get('next_follow_up', form.non_field_errors()):
                    messages.error(request, str(err))
                redirect_url += '?drawer=followup'

        elif action == 'quick_followup':
            try:
                days = int(request.POST.get('days', 1))
            except (TypeError, ValueError):
                days = 1
            days = max(1, min(days, 365))
            follow_date = timezone.now().date() + timedelta(days=days)
            schedule_follow_up(customer, follow_date)
            messages.success(request, f'پیگیری برای {days} روز دیگر ثبت شد.')

        elif action == 'complete_followup':
            if complete_follow_up(customer, request.POST.get('note', '')):
                messages.success(request, 'پیگیری انجام‌شده علامت خورد.')
            else:
                messages.warning(request, 'پیگیری فعالی برای بستن وجود ندارد.')

        elif action == 'add_reminder':
            form = CRMReminderForm(request.POST)
            if form.is_valid():
                reminder = form.save(commit=False)
                reminder.user = request.user
                reminder.customer = customer
                reminder.save()
                sync_follow_up_from_reminder(customer, reminder)
                log_activity(customer, 'یادآور', content=reminder.title, title='یادآور جدید')
                messages.success(request, 'یادآور ثبت شد.')
            else:
                err = next(iter(form.errors.values()), ['فرم یادآور نامعتبر است.'])[0]
                messages.error(request, str(err))
                redirect_url += '?drawer=reminder'

        elif action == 'add_document':
            form = CustomerDocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.user = request.user
                doc.customer = customer
                doc.save()
                log_activity(customer, 'یادداشت', content=f'مدرک: {doc.title}', title='آپلود مدرک')
                messages.success(request, 'مدرک آپلود شد.')

        elif action == 'link_property':
            form = PropertyLinkForm(request.POST)
            prop_id = request.POST.get('property_id')
            if form.is_valid() and prop_id:
                prop = property_for_user(request.user, int(prop_id))
                if not prop:
                    messages.error(request, 'ملک یافت نشد.')
                elif not can_edit_customer(request.user, customer):
                    messages.error(request, 'امکان ویرایش این مخاطب را ندارید.')
                else:
                    link_customer_property(
                        customer, prop,
                        form.cleaned_data['role'],
                        form.cleaned_data['deal_type'],
                        interest_level=form.cleaned_data.get('interest_level', ''),
                        is_primary=form.cleaned_data.get('is_primary', False),
                        notes=form.cleaned_data.get('notes', ''),
                    )
                    messages.success(request, 'ملک به مخاطب پیوند شد.')

        elif action == 'convert_lead':
            form = ConvertLeadForm(customer, request.POST)
            if form.is_valid():
                convert_lead(customer, form.cleaned_data['new_type'])
                messages.success(request, f'مخاطب به {form.cleaned_data["new_type"]} تبدیل شد.')

        elif action == 'unlink_property':
            link_id = request.POST.get('link_id')
            link = get_object_or_404(PropertyContact, pk=link_id, customer=customer)
            title = link.property.title
            link.delete()
            log_activity(customer, 'املاک', content=f'حذف پیوند: {title}')
            messages.success(request, 'پیوند حذف شد.')

        elif action == 'unlink_listing':
            listing_id = request.POST.get('listing_id')
            link = get_object_or_404(CustomerListing, pk=listing_id, customer=customer)
            title = link.title or link.token
            link.delete()
            log_activity(customer, 'املاک', content=f'حذف آگهی مرتبط: {title}', token=link.token)
            messages.success(request, 'پیوند آگهی حذف شد.')

        elif action == 'add_visit':
            form = PropertyVisitForm(request.POST, user=request.user)
            if form.is_valid():
                visit = form.save(commit=False)
                visit.user = request.user
                visit.customer = customer
                visit.save()
                prop_title = visit.property.title if visit.property else (visit.listing_title or visit.listing_token)
                log_activity(
                    customer, 'بازدید',
                    content=f'{visit.outcome} — {prop_title}' + (f' ({visit.reject_reason})' if visit.reject_reason else ''),
                    title='ثبت بازدید',
                    property_obj=visit.property,
                    metadata={'visit_id': visit.pk, 'outcome': visit.outcome},
                )
                messages.success(request, 'بازدید ثبت شد.')
                redirect_url += '?tab=visits'
            else:
                self.object = customer
                ctx = self.get_context_data(object=customer)
                ctx['visit_form'] = form
                ctx['open_drawer'] = 'visit'
                ctx['active_tab'] = 'visits'
                for errors in form.errors.values():
                    for err in errors:
                        messages.error(request, str(err))
                return render(request, self.template_name, ctx)

        elif action == 'add_deal':
            form = CRMDealCreateForm(request.POST, user=request.user)
            if form.is_valid():
                deal = form.save()
                apply_deal_commission(deal)
                messages.success(request, f'معامله «{deal.title}» ثبت شد.')
                return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
            messages.error(request, 'ثبت معامله انجام نشد.')

        elif action == 'log_call':
            try:
                days = int(request.POST.get('schedule_days', 0))
            except (TypeError, ValueError):
                days = 0
            log_phone_call(
                customer,
                request.POST.get('note', ''),
                schedule_days=days if days > 0 else None,
            )
            messages.success(request, 'تماس ثبت شد.')
            if days <= 0:
                request.session['crm_after_call_id'] = customer.pk
                redirect_url += '?after_call=1'

        elif action == 'merge_customer':
            secondary_id = request.POST.get('merge_with_id')
            if secondary_id:
                secondary = customer_for_user(request.user, int(secondary_id))
                if not secondary or not can_edit_customer(request.user, secondary):
                    messages.error(request, 'مخاطب دوم یافت نشد یا قابل ادغام نیست.')
                else:
                    try:
                        merge_customers(customer, secondary)
                        messages.success(request, f'مخاطب با «{secondary.name}» ادغام شد.')
                    except ValueError as exc:
                        messages.error(request, str(exc))
            else:
                messages.warning(request, 'مخاطب دوم انتخاب نشده است.')

        elif action == 'suggest_properties':
            raw = request.POST.get('matches_json', '[]')
            try:
                selected = json.loads(raw)
            except json.JSONDecodeError:
                selected = []
            if not selected:
                messages.warning(request, 'حداقل یک ملک انتخاب کنید.')
            else:
                divar_enabled = has_active_bot_license(request.user)
                if not divar_enabled:
                    selected = [m for m in selected if m.get('source') != 'divar']
                if not selected:
                    messages.info(request, 'تطبیق فایلینگ دیوار نیاز به لایسنس فعال دارد.')
                    redirect_url += '?tab=matches'
                    return redirect(redirect_url)
                text, linked = apply_property_suggestions(
                    customer, request.user, selected,
                    note=request.POST.get('suggest_note', ''),
                    request=request,
                    divar_enabled=divar_enabled,
                )
                if linked:
                    request.session['crm_last_suggestion_text'] = text
                    messages.success(
                        request,
                        f'{linked} ملک پیشنهاد و به پرونده مخاطب پیوند شد.',
                    )
                    redirect_url += '?tab=properties&suggested=1'
                else:
                    messages.error(
                        request,
                        'ثبت پیشنهاد انجام نشد — ملک‌های انتخاب‌شده در دسترس شما نیستند.',
                    )
                    redirect_url += '?tab=matches'

        return redirect(redirect_url)


class CustomerUpdateView(LoginRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'workspace/crm/contacts/detail.html'
    pk_url_kwarg = 'customer_id'

    def get_queryset(self):
        return customers_qs(self.request.user).filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect(
            f"{reverse('workspace:crm_detail', kwargs={'customer_id': self.object.pk})}?drawer=edit"
        )

    def form_valid(self, form):
        old_status = Customer.objects.get(pk=self.object.pk).status
        self.object = form.save()
        log_status_change(self.object, old_status, self.object.status)
        messages.success(self.request, 'اطلاعات به‌روز شد.')
        return redirect('workspace:crm_detail', customer_id=self.object.pk)

    def form_invalid(self, form):
        self.object = self.get_object()
        view = CustomerDetailView()
        view.setup(self.request, customer_id=self.object.pk)
        view.object = self.object
        ctx = view.get_context_data(object=self.object)
        ctx['customer_form'] = form
        ctx['open_drawer'] = 'edit'
        return render(self.request, self.template_name, ctx)


class CustomerDeleteView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer or not can_edit_customer(request.user, customer):
            messages.error(request, 'مخاطب یافت نشد یا امکان حذف ندارید.')
            return redirect('workspace:crm_contacts')
        name = customer.name
        customer.delete()
        messages.success(request, f'مخاطب «{name}» حذف شد.')
        return redirect('workspace:crm_contacts')


class CustomerExportView(ExportSecurityMixin, LoginRequiredMixin, View):
    def get(self, request):
        return export_customers_excel_response(request.user, request.GET)


def _crm_reminder_stats_for_user(user):
    qs = reminders_qs(user)
    now = timezone.now()
    return {
        'active': qs.filter(is_done=False).count(),
        'done': qs.filter(is_done=True).count(),
        'overdue': qs.filter(is_done=False, due_at__lt=now).count(),
        'today': qs.filter(is_done=False, due_at__date=timezone.localdate()).count(),
    }


class CRMReminderListView(CRMContextMixin, LoginRequiredMixin, ListView):
    model = Reminder
    template_name = 'workspace/crm/reminders/list.html'
    context_object_name = 'reminders'
    paginate_by = 20

    def get_queryset(self):
        show = self.request.GET.get('show', 'active')
        qs = reminders_qs(self.request.user).select_related('customer', 'property')
        if show == 'done':
            return qs.filter(is_done=True).order_by('-due_at')
        if show == 'all':
            return qs.order_by('due_at')
        return qs.filter(is_done=False).order_by('due_at')

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('partial') == '1':
            page_obj = context.get('page_obj')
            html = render_to_string(
                'workspace/crm/reminders/_timeline_items.html',
                {'reminders': context.get('reminders')},
                request=self.request,
            )
            return JsonResponse({
                'html': html,
                'has_next': bool(page_obj and page_obj.has_next()),
                'next_page': page_obj.next_page_number() if page_obj and page_obj.has_next() else None,
            })
        return super().render_to_response(context, **response_kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['show'] = self.request.GET.get('show', 'active')
        ctx['stats'] = _crm_reminder_stats_for_user(user)
        ctx['reminder_form'] = ctx.get('reminder_form', CRMReminderForm())
        ctx['crm_customers'] = customers_qs(user).order_by('name')[:200]
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        ctx['crm_section'] = 'reminders'
        ctx['now'] = timezone.now()
        return ctx

    def post(self, request):
        form = CRMReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            customer_id = request.POST.get('customer_id')
            if customer_id:
                linked = customer_for_user(request.user, int(customer_id))
                if not linked or not can_edit_customer(request.user, linked):
                    messages.error(request, 'مخاطب انتخاب‌شده یافت نشد.')
                    self.object_list = self.get_queryset()
                    ctx = self.get_context_data(object_list=self.object_list)
                    ctx['reminder_form'] = form
                    ctx['open_drawer'] = 'reminder'
                    return render(request, self.template_name, ctx)
                reminder.customer = linked
            reminder.save()
            messages.success(request, 'یادآور ثبت شد.')
            return redirect('workspace:crm_reminders')
        self.object_list = self.get_queryset()
        ctx = self.get_context_data(object_list=self.object_list)
        ctx['reminder_form'] = form
        ctx['open_drawer'] = 'reminder'
        for errors in form.errors.values():
            for err in errors:
                messages.error(request, str(err))
        return render(request, self.template_name, ctx)


class CRMReminderToggleView(LoginRequiredMixin, View):
    def post(self, request, reminder_id):
        reminder = reminders_qs(request.user).filter(pk=reminder_id).first()
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if not reminder:
            if is_ajax:
                return JsonResponse({'ok': False, 'error': 'یادآور یافت نشد.'}, status=404)
            messages.error(request, 'یادآور یافت نشد.')
            nxt = request.POST.get('next')
            return redirect(nxt if nxt else reverse('workspace:crm_reminders'))
        was_done = reminder.is_done
        reminder.is_done = not reminder.is_done
        reminder.save(update_fields=['is_done'])
        if not was_done and reminder.is_done and reminder.recurrence:
            advance_recurring_reminder(reminder)
        if is_ajax:
            return JsonResponse({
                'ok': True,
                'reminder_id': reminder.pk,
                'is_done': reminder.is_done,
                'stats': _crm_reminder_stats_for_user(request.user),
            })
        messages.success(request, 'وضعیت یادآور به‌روز شد.')
        nxt = request.POST.get('next')
        return redirect(nxt if nxt else reverse('workspace:crm_reminders'))


class CRMPropertyExportView(ExportSecurityMixin, LoginRequiredMixin, View):
    def get(self, request):
        fmt = request.GET.get('format', 'xlsx').lower()
        if fmt == 'csv':
            return export_properties_csv_response(request.user, request.GET)
        return export_properties_excel_response(request.user, request.GET)


class CRMPropertyListView(CRMContextMixin, LoginRequiredMixin, ListView):
    model = CRMProperty
    template_name = 'workspace/crm/properties/list.html'
    context_object_name = 'properties'
    paginate_by = 20

    def get_paginate_by(self, queryset):
        if self.request.GET.get('view') == 'pipeline':
            return None
        return self.paginate_by

    def render_to_response(self, context, **response_kwargs):
        if self.request.GET.get('partial') == '1' and context.get('view_mode') != 'pipeline':
            page_obj = context.get('page_obj')
            view_mode = context.get('view_mode') or 'grid'
            template = (
                'workspace/crm/properties/_property_table_rows.html'
                if view_mode == 'table'
                else 'workspace/crm/properties/_property_cards.html'
            )
            html = render_to_string(template, context, request=self.request)
            return JsonResponse({
                'html': html,
                'has_next': bool(page_obj and page_obj.has_next()),
                'next_page': page_obj.next_page_number() if page_obj and page_obj.has_next() else None,
            })
        return super().render_to_response(context, **response_kwargs)

    def get_queryset(self):
        from django.db.models import Prefetch
        from workspace.models import CRMPropertyFolderItem
        return filter_properties(self.request.user, self.request.GET).annotate(
            contact_count=Count('contact_links', distinct=True),
        ).prefetch_related(
            Prefetch(
                'folder_items',
                queryset=CRMPropertyFolderItem.objects.select_related('folder'),
            ),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx['view_mode'] = self.request.GET.get('view', 'grid')
        from workspace.services.crm_property_folders import (
            FOLDER_COLORS, FOLDER_ICONS, folders_for_property, list_property_folders, serialize_folder,
        )
        from workspace.services.crm_property_cabinets import (
            list_property_cabinets,
            serialize_cabinet,
            unassigned_folder_count,
        )
        from workspace.services.property_public_share import build_property_amenity_dossier_items
        ctx['active_cabinet_id'] = self.request.GET.get('cabinet_id', '')
        cabinet_filter = ctx['active_cabinet_id'] or None
        ctx['property_folders'] = list_property_folders(user, cabinet_id=cabinet_filter)
        ctx['property_folders_json'] = json.dumps(
            [serialize_folder(f) for f in ctx['property_folders']],
            ensure_ascii=False,
        )
        ctx['property_cabinets'] = list_property_cabinets(user)
        ctx['property_cabinets_json'] = json.dumps(
            [serialize_cabinet(c) for c in ctx['property_cabinets']],
            ensure_ascii=False,
        )
        ctx['unassigned_folder_count'] = unassigned_folder_count(user)
        for prop in ctx.get('properties') or []:
            prop.card_amenities = build_property_amenity_dossier_items(prop)
            prop.folder_badges = folders_for_property(prop)
        if self.request.GET.get('partial') == '1':
            return ctx
        from workspace.services.crm_property_archive import (
            ARCHIVE_SCOPE_ACTIVE,
            ARCHIVE_SCOPE_ALL,
            ARCHIVE_SCOPE_ARCHIVED,
            archived_properties_q,
        )

        props = properties_qs(user)
        filtered = filter_properties(user, self.request.GET)
        active_props = props.exclude(archived_properties_q())
        archived_props = props.filter(archived_properties_q())
        archive_scope = (self.request.GET.get('archive_scope') or ARCHIVE_SCOPE_ACTIVE).strip().lower()
        ctx['archive_scope'] = archive_scope

        def _tab_qs(scope: str) -> str:
            pairs = {
                k: v for k, v in self.request.GET.items()
                if k not in ('page', 'partial', 'archive_scope') and v
            }
            if scope != ARCHIVE_SCOPE_ACTIVE:
                pairs['archive_scope'] = scope
            return urlencode(pairs)

        ctx['archive_tab_qs'] = {
            ARCHIVE_SCOPE_ACTIVE: _tab_qs(ARCHIVE_SCOPE_ACTIVE),
            ARCHIVE_SCOPE_ARCHIVED: _tab_qs(ARCHIVE_SCOPE_ARCHIVED),
            ARCHIVE_SCOPE_ALL: _tab_qs(ARCHIVE_SCOPE_ALL),
        }
        ctx['stats'] = {
            'total': active_props.count(),
            'archived': archived_props.count(),
            'sale': active_props.filter(deal_mode='فروش').count(),
            'rent': active_props.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).count(),
            'active': active_props.filter(transaction_status='فعال').count(),
            'published': active_props.filter(publish_status='منتشرشده').count(),
        }
        ctx['filtered_count'] = filtered.count()
        ctx['property_form'] = ctx.get('property_form', CRMPropertyForm())
        ctx['open_drawer'] = ctx.get('open_drawer', '')
        ctx['deal_modes'] = PROPERTY_DEAL_MODES
        from workspace.constants import PROPERTY_TX_STATUSES_UI
        ctx['tx_statuses'] = PROPERTY_TX_STATUSES_UI
        ctx['property_types'] = CRM_PROPERTIES
        ctx['publish_statuses'] = PROPERTY_PUBLISH_STATUSES
        ctx['crm_section'] = 'properties'
        ctx['sort'] = self.request.GET.get('sort', '-updated_at')
        ctx['filter_qs'] = urlencode({
            k: v for k, v in self.request.GET.items()
            if k not in ('view', 'page', 'drawer', 'partial') and v
        })
        ctx['has_filters'] = any(self.request.GET.get(k) for k in (
            'q', 'deal_mode', 'transaction_status', 'property_type', 'publish_status', 'city', 'sort',
            'folder_id', 'cabinet_id', 'archive_scope',
            'parking', 'storage', 'elevator', 'rooms',
            'area_min', 'area_max', 'price_min', 'price_max',
            'year_min', 'year_max', 'age_max',
        ))
        ctx['advanced_filter_count'] = property_advanced_filter_count(self.request.GET)
        ctx['filters_open'] = bool(ctx['advanced_filter_count']) or self.request.GET.get('adv') == '1'
        ctx['pipeline'] = get_property_pipeline(user, self.request.GET, per_column=60)
        ctx['pipeline_interactive'] = True
        ctx['tx_status_url_template'] = reverse(
            'workspace:crm_property_status', kwargs={'property_id': 0},
        ).replace('/0/', '/{id}/')
        ctx['pipeline_reorder_url'] = reverse('workspace:crm_property_pipeline_order')
        ctx['saved_filters'] = list_saved_filters(user, 'properties')
        ctx['saved_filter_scope'] = 'properties'
        ctx['saved_filter_base'] = reverse('workspace:crm_properties')
        ctx['saved_filter_params'] = current_params_from_request(self.request, 'properties')
        ctx['saved_filter_can_save'] = bool(ctx['saved_filter_params'])
        ctx['active_folder_id'] = self.request.GET.get('folder_id', '')
        ctx['folder_colors'] = FOLDER_COLORS
        ctx['folder_icons'] = FOLDER_ICONS
        ctx['cabinet_colors'] = FOLDER_COLORS
        ctx['cabinet_icons'] = FOLDER_ICONS
        ctx['property_import_form'] = ctx.get('property_import_form', CRMPropertyImportForm())
        ctx['property_import_headers'] = property_import_template_headers()
        ctx['property_import_column_specs'] = property_import_column_specs()
        ctx['property_import_allowed_values'] = {
            'property_types': list(CRM_PROPERTIES),
            'deal_modes': list(PROPERTY_DEAL_MODES),
            'tx_statuses': list(PROPERTY_TX_STATUSES),
            'publish_statuses': list(PROPERTY_PUBLISH_STATUSES),
            'advertiser_types': list(PROPERTY_ADVERTISER_TYPES),
        }
        ctx['open_modal'] = ctx.get('open_modal', self.request.GET.get('open', ''))
        from workspace.services.crm_map import crm_map_filter_querystring
        ctx['map_filter_qs'] = crm_map_filter_querystring(self.request.GET)
        if ctx['stats']['total'] == 0 and not ctx.get('has_filters'):
            from workspace.academy.context_helpers import inject_academy_context
            inject_academy_context(ctx, user, 'properties_empty')
        from workspace.services.crm_smart_command import inject_smart_command_context

        inject_smart_command_context(ctx, self.request, 'properties')
        return ctx


class CRMPropertyMapView(LoginRequiredMixin, TemplateView):
    """نقشه فایل‌های شخصی — همان Map Pro فایلینگ با منبع CRMProperty."""

    template_name = 'workspace/map/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from workspace.services.crm_map import build_crm_properties_map_context
        ctx.update(build_crm_properties_map_context(self.request))
        return ctx


class CRMPropertyStatusUpdateView(LoginRequiredMixin, View):
    """تغییر وضعیت معامله ملک — کانبان A8."""

    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
        if not can_edit_property(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند وضعیت را تغییر دهد'}, status=403)
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            new_status = (payload.get('transaction_status') or payload.get('status') or '').strip()
        else:
            new_status = (request.POST.get('transaction_status') or request.POST.get('status') or '').strip()

        if new_status not in PROPERTY_TX_STATUSES:
            return JsonResponse({'ok': False, 'error': 'وضعیت نامعتبر'}, status=400)
        try:
            update_property_transaction_status(prop, new_status, user=request.user)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)

        prop.refresh_from_db()
        from workspace.services.crm_property_archive import is_property_archived
        return JsonResponse({
            'ok': True,
            'transaction_status': prop.transaction_status,
            'archived': is_property_archived(prop),
            'property_id': prop.pk,
            'suggest_rental_reminder': False,
            'suggested_due_jalali': '',
        })


class CRMPropertyArchiveView(LoginRequiredMixin, View):
    """بایگانی تک‌فایل — با گزینه‌های تمدید اجاره."""

    def post(self, request, property_id):
        from workspace.services.crm_property_archive import archive_property, is_property_archived
        from workspace.services.crm_property_rental_renewal import (
            parse_contract_end_jalali,
            property_is_rental,
            upsert_renewal_schedule,
            renewal_followup_date,
        )
        from workspace.services.jalali_input import format_jalali_date

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)

        tracking_warning = ''
        reminder_id = None
        skip_date = bool(payload.get('skip_contract_end'))
        create_reminder = bool(payload.get('create_reminder', True))
        contract_raw = (payload.get('contract_end_jalali') or '').strip()
        try:
            from django.db import transaction

            with transaction.atomic():
                prop = property_for_user(request.user, property_id)
                if not prop:
                    return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
                contract_end = None
                if property_is_rental(prop):
                    if skip_date or not contract_raw:
                        tracking_warning = 'پیگیری تمدید اجاره برای سال بعد تنظیم نشده است.'
                    else:
                        contract_end = parse_contract_end_jalali(contract_raw)
                archive_property(request.user, prop, reason=(payload.get('reason') or ''))
                if property_is_rental(prop) and contract_end is not None:
                    reminder = upsert_renewal_schedule(
                        request.user, prop, contract_end, create_reminder=create_reminder,
                    )
                    reminder_id = reminder.pk if reminder else None
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        prop.refresh_from_db()
        follow_jalali = ''
        if prop.rental_contract_end_date:
            follow_jalali = format_jalali_date(renewal_followup_date(prop.rental_contract_end_date))
        return JsonResponse({
            'ok': True,
            'archived': is_property_archived(prop),
            'property_id': prop.pk,
            'tracking_warning': tracking_warning,
            'reminder_id': reminder_id,
            'followup_jalali': follow_jalali,
        })


class CRMPropertyRentalReminderView(LoginRequiredMixin, View):
    """ثبت/به‌روزرسانی سررسید تمدید اجاره و یادآور مرتبط."""

    def post(self, request, property_id):
        from workspace.services.crm_property_archive import is_property_archived
        from workspace.services.crm_property_rental_renewal import (
            parse_contract_end_jalali,
            property_is_rental,
            upsert_renewal_schedule,
            renewal_followup_date,
        )
        from workspace.services.jalali_input import format_jalali_date

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
        if not can_edit_property(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید'}, status=403)
        if not property_is_rental(prop):
            return JsonResponse({'ok': False, 'error': 'فقط برای فایل‌های اجاره‌ای'}, status=400)

        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)

        contract_raw = (payload.get('contract_end_jalali') or payload.get('due_jalali') or '').strip()
        create_reminder = bool(payload.get('create_reminder', True))
        if not contract_raw:
            return JsonResponse({'ok': False, 'error': 'تاریخ پایان قرارداد الزامی است'}, status=400)

        try:
            contract_end = parse_contract_end_jalali(contract_raw)
            reminder = upsert_renewal_schedule(
                request.user, prop, contract_end, create_reminder=create_reminder,
            )
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

        follow = renewal_followup_date(contract_end)
        return JsonResponse({
            'ok': True,
            'reminder_id': reminder.pk if reminder else None,
            'contract_end_jalali': format_jalali_date(contract_end),
            'followup_jalali': format_jalali_date(follow),
            'archived': is_property_archived(prop),
        })


class CRMPropertyBulkArchiveView(LoginRequiredMixin, View):
    """بایگانی / بازگردانی گروهی فایل‌های شخصی."""

    def post(self, request):
        from workspace.services.crm_property_archive import (
            bulk_archive_properties,
            bulk_restore_properties,
        )

        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            ids = payload.get('property_ids') or payload.get('ids') or []
            action = (payload.get('action') or 'archive').strip().lower()
            reason = (payload.get('reason') or '').strip()
        else:
            ids = request.POST.getlist('property_ids') or request.POST.get('ids', '').split(',')
            action = (request.POST.get('action') or 'archive').strip().lower()
            reason = (request.POST.get('reason') or '').strip()

        if action == 'restore':
            result = bulk_restore_properties(request.user, ids)
            ok_count = result.get('restored', 0)
            label = 'بازگردانی'
        else:
            result = bulk_archive_properties(request.user, ids, reason=reason)
            ok_count = result.get('archived', 0)
            label = 'بایگانی'

        if ok_count == 0:
            return JsonResponse({
                'ok': False,
                'error': f'فایلی برای {label} انتخاب نشده یا دسترسی ندارید.',
                **result,
            }, status=400)
        return JsonResponse({
            'ok': True,
            'message': f'{ok_count} فایل {label} شد.',
            **result,
        })


class CRMPropertyRestoreView(LoginRequiredMixin, View):
    def post(self, request, property_id):
        from workspace.services.crm_property_archive import restore_property

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
        try:
            restore_property(request.user, prop)
        except PermissionError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        prop.refresh_from_db()
        return JsonResponse({'ok': True, 'property_id': prop.pk, 'transaction_status': prop.transaction_status})


class CRMPropertyPipelineOrderView(LoginRequiredMixin, View):
    """تغییر ترتیب فایل‌ها در یک ستون کانبان."""

    def post(self, request):
        if not request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        status = (payload.get('transaction_status') or '').strip()
        ordered_ids = payload.get('ordered_ids') or []
        if not isinstance(ordered_ids, list):
            return JsonResponse({'ok': False, 'error': 'لیست ترتیب نامعتبر است'}, status=400)
        try:
            reorder_property_pipeline(request.user, status, ordered_ids)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMPropertyCreateView(LoginRequiredMixin, CreateView):
    model = CRMProperty
    form_class = CRMPropertyForm
    template_name = 'workspace/crm/properties/list.html'

    def get(self, request, *args, **kwargs):
        return redirect('workspace:crm_properties')

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.agency = get_agency(self.request.user)
        self.object = form.save()
        images = list(self.object.images or [])
        raw_images = self.request.POST.get('property_images_json')
        if raw_images is not None:
            images = parse_images_payload(raw_images)
        for uploaded in self.request.FILES.getlist('property_image_files'):
            if len(images) >= MAX_PROPERTY_IMAGES:
                break
            try:
                images.append(store_property_image(self.request.user, self.object, uploaded))
            except ValueError as exc:
                messages.warning(self.request, str(exc))
        if images != (self.object.images or []):
            self.object.images = images[:MAX_PROPERTY_IMAGES]
            self.object.save(update_fields=['images', 'updated_at'])
        if self.object.phone or self.object.owner_name:
            upsert_property_owner(
                self.request.user,
                phone=self.object.phone,
                name=self.object.owner_name,
                crm_property=self.object,
                source='سایر',
            )
        upsert_property_tenant(
            self.request.user,
            phone=self.object.tenant_phone,
            name=self.object.tenant_name,
            crm_property=self.object,
            source='سایر',
        )
        messages.success(self.request, 'ملک ثبت شد.')
        return redirect('workspace:crm_property_detail', property_id=self.object.pk)

    def form_invalid(self, form):
        list_view = CRMPropertyListView()
        list_view.setup(self.request)
        list_view.object_list = list_view.get_queryset()
        ctx = list_view.get_context_data(object_list=list_view.object_list)
        ctx['property_form'] = form
        ctx['open_drawer'] = 'property'
        return render(self.request, self.template_name, ctx)


class CRMPropertyDetailView(CRMContextMixin, LoginRequiredMixin, DetailView):
    model = CRMProperty
    template_name = 'workspace/crm/properties/detail.html'
    context_object_name = 'property'
    pk_url_kwarg = 'property_id'

    def get_object(self, queryset=None):
        prop = property_for_user(self.request.user, self.kwargs[self.pk_url_kwarg])
        if not prop:
            from django.http import Http404
            raise Http404('ملک یافت نشد.')
        return prop

    def get_queryset(self):
        return properties_qs(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p = self.object
        ctx['property_is_deleted'] = p.deleted_at is not None
        if ctx['property_is_deleted']:
            ctx['contact_links'] = []
            ctx['activities'] = []
            ctx['documents'] = []
            ctx['is_property_owner'] = is_property_owner(self.request.user, p)
            share_ctx = build_property_share_context(self.request.user, p)
            ctx['property_share'] = share_ctx.share
            ctx['property_owner_user'] = p.user
            ctx['can_edit_property'] = False
            ctx['mask_sensitive'] = False
            ctx['property_is_shared'] = share_ctx.is_recipient
            ctx['is_confidential_share'] = False
            ctx['is_collaborative_share'] = False
            ctx['property_shares'] = []
            ctx['property_location_display'] = ''
            ctx['feature_profile'] = {'has_details': False, 'groups': [], 'core': [], 'detail_count': 0}
            ctx['listing_highlights'] = []
            ctx['dossier_amenities'] = []
            ctx['source_listing'] = None
            ctx['supplementary_groups'] = []
            ctx['supplementary_fields'] = []
            ctx['property_form'] = CRMPropertyForm(instance=p)
            ctx['document_form'] = CustomerDocumentForm()
            ctx['open_drawer'] = ''
            ctx['crm_section'] = 'properties'
            ctx['show_property_map'] = False
            ctx['property_map_locked'] = False
            ctx['can_edit_map_location'] = False
            ctx['listing_map_marker'] = None
            ctx['map_navigation'] = None
            ctx['location_accuracy'] = None
            ctx['property_map_has_coords'] = False
            ctx['default_map_center'] = None
            from workspace.constants import PROPERTY_TX_STATUSES_UI
            ctx['property_tx_statuses'] = PROPERTY_TX_STATUSES_UI
            return ctx
        ctx['contact_links'] = p.contact_links.select_related('customer').all()
        ctx['activities'] = CustomerActivity.objects.filter(property=p).select_related('customer')[:30]
        ctx['documents'] = p.documents.all()
        ctx['property_form'] = CRMPropertyForm(instance=p)
        ctx['document_form'] = CustomerDocumentForm()
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        ctx['crm_section'] = 'properties'
        ctx['feature_profile'] = {'has_details': False, 'groups': [], 'core': [], 'detail_count': 0}
        ctx['listing_highlights'] = []
        ctx['dossier_amenities'] = []
        ctx['supplementary_groups'] = []
        ctx['supplementary_fields'] = []
        source_listing = resolve_listing_for_property(self.request.user, p)
        ctx['source_listing'] = source_listing
        if source_listing:
            feat = extract_listing_features(source_listing)
            ctx['feature_profile'] = build_listing_feature_profile(source_listing, feat)
            ctx['listing_highlights'] = feat.get('highlights') or []
            from workspace.services.display import (
                build_listing_display_data,
                format_sections,
                format_supplementary_fields,
                format_supplementary_groups,
                transaction_profile,
            )
            listing_tx = transaction_profile(p.deal_mode)
            listing_data = build_listing_display_data(
                source_listing, feat, transaction_type=listing_tx.get('mode') or p.deal_mode,
            )
            listing_sections = format_sections(listing_data, listing_tx)
            listing_sections.pop('سایر', None)
            ctx['supplementary_fields'] = format_supplementary_fields(
                listing_data, listing_tx, listing_sections,
            )
            ctx['supplementary_groups'] = format_supplementary_groups(
                listing_data, listing_tx, listing_sections,
            )
        from workspace.services.property_public_share import build_property_amenity_dossier_items
        ctx['dossier_amenities'] = build_property_amenity_dossier_items(p)
        ctx['is_property_owner'] = is_property_owner(self.request.user, p)
        share_ctx = build_property_share_context(self.request.user, p)
        ctx['property_share_ctx'] = share_ctx
        ctx['property_share'] = share_ctx.share
        ctx['share_mode'] = share_ctx.share_mode
        ctx['is_confidential_share'] = share_ctx.is_confidential
        ctx['is_collaborative_share'] = share_ctx.is_collaborative
        ctx['can_edit_property'] = share_ctx.can_edit
        ctx['mask_sensitive'] = share_ctx.mask_sensitive
        ctx['property_owner_user'] = share_ctx.owner_user
        ctx['property_location_display'] = location_display(p, mask=share_ctx.mask_sensitive)
        ctx['property_shares'] = list_outgoing_property_shares(p) if share_ctx.is_owner else []
        ctx['property_is_shared'] = share_ctx.is_recipient
        ctx['owner_phone'] = p.phone or ''
        ctx['owner_name'] = p.owner_name or ''
        ctx['owner_contact'] = None if share_ctx.mask_sensitive else primary_owner_contact(crm_property=p)
        if share_ctx.mask_sensitive:
            ctx['contact_links'] = []
            ctx['activities'] = []
            ctx['documents'] = []
            ctx['owner_phone'] = ''
            ctx['owner_name'] = ''
        if ctx.get('can_edit_property'):
            ctx['property_link_form'] = PropertyLinkForm()
            ctx['quick_lead_form'] = QuickLeadForm()
            ctx['user_contacts'] = customers_qs(self.request.user).order_by('-updated_at')[:200]
            ctx['crm_sources'] = CRM_SOURCES
        if not share_ctx.mask_sensitive:
            today = timezone.now().date()
            ctx['followup_form'] = FollowUpForm()
            ctx['follow_up_state'] = property_follow_up_state(p, today)
            ctx['follow_up_logs'] = (
                CustomerActivity.objects.filter(property=p, activity_type='پیگیری')
                .select_related('customer')[:8]
            )
        ctx['active_tab'] = self.request.GET.get('tab', '')
        ctx['contact_match_data'] = {
            'eligible': False,
            'matches': [],
            'total_count': 0,
            'message': '',
            'deal_label': '',
        }
        ctx['contact_suggestion_text'] = ''
        ctx['contact_suggestion_items'] = []
        ctx['contact_suggested'] = self.request.GET.get('suggested') == '1'
        from workspace.constants import PROPERTY_TX_STATUSES_UI
        ctx['property_tx_statuses'] = PROPERTY_TX_STATUSES_UI
        can_suggest_contacts = (
            bool(ctx.get('can_edit_property'))
            and not ctx.get('property_is_deleted')
            and not ctx.get('mask_sensitive')
        )
        ctx['can_suggest_contacts'] = can_suggest_contacts
        if can_suggest_contacts:
            ctx['contact_match_data'] = get_property_contact_matches(p, self.request.user)
            session_payload = self.request.session.pop('crm_last_contact_suggestions', None)
            if isinstance(session_payload, dict):
                ctx['contact_suggestion_text'] = session_payload.get('whatsapp_text') or ''
                ctx['contact_suggestion_items'] = session_payload.get('suggestions') or []
            else:
                # سازگاری با کلید قدیمی
                ctx['contact_suggestion_text'] = self.request.session.pop(
                    'crm_last_contact_suggestion_text', '',
                )
        ctx['public_property_share'] = None
        ctx['public_property_share_url'] = ''
        ctx['can_show_property_public_share'] = False
        ctx['public_share_nearby_meta'] = {
            'has_coords': False,
            'has_data': False,
            'can_enable': False,
        }
        if not ctx.get('property_is_deleted') and not ctx.get('mask_sensitive'):
            from workspace.services.crm_matching_access import can_create_property_public_link
            from workspace.services.property_public_share import (
                get_or_create_property_share,
                property_public_share_url,
            )
            pub_share = None
            if can_create_property_public_link(self.request.user, p):
                try:
                    pub_share = get_or_create_property_share(self.request.user, p)
                except Exception:
                    logger.exception('property_public_share_create_failed property_id=%s', p.pk)
            if pub_share:
                ctx['public_property_share'] = pub_share
                ctx['public_property_share_url'] = property_public_share_url(self.request, pub_share)
                from workspace.services.public_share_common import share_profile_context
                profile = share_profile_context(
                    self.request.user, pub_share,
                    title=p.title or '',
                    share_url=ctx['public_property_share_url'],
                )
                ctx['consultant_name'] = profile['consultant_name']
                ctx['consultant_phone'] = profile['consultant_phone']
                ctx['share_profile'] = profile
                from workspace.services.nearby_pois import property_share_nearby_meta
                ctx['public_share_nearby_meta'] = property_share_nearby_meta(p)
                ctx['can_show_property_public_share'] = True

        from workspace.services.crm_property_folders import FOLDER_COLORS, FOLDER_ICONS, list_property_folders
        ctx['property_folders'] = list_property_folders(self.request.user)
        ctx['property_folder_ids'] = list(p.folder_items.values_list('folder_id', flat=True))
        ctx['folder_colors'] = FOLDER_COLORS
        ctx['folder_icons'] = FOLDER_ICONS

        # نقشه موقعیت — انتهای صفحه جزئیات
        mask = bool(ctx.get('mask_sensitive'))
        can_edit_map = bool(ctx.get('can_edit_property')) and not mask
        ctx['can_edit_map_location'] = can_edit_map
        if mask:
            ctx['show_property_map'] = False
            ctx['property_map_locked'] = True
            ctx['listing_map_marker'] = None
            ctx['map_navigation'] = None
            ctx['location_accuracy'] = None
            ctx['property_map_has_coords'] = False
            ctx['default_map_center'] = None
        else:
            from workspace.services.listing_map import build_crm_property_map_context
            platform_url = reverse(
                'workspace:crm_property_detail', kwargs={'property_id': p.pk},
            )
            map_ctx = build_crm_property_map_context(p, platform_url=platform_url)
            ctx['property_map_locked'] = False
            ctx['property_map_has_coords'] = map_ctx['has_coords']
            ctx['show_property_map'] = map_ctx['has_coords'] or can_edit_map
            ctx['listing_map_marker'] = map_ctx['listing_map_marker']
            ctx['map_navigation'] = map_ctx['map_navigation']
            ctx['location_accuracy'] = map_ctx['location_accuracy']
            ctx['default_map_center'] = map_ctx['default_map_center']
            if can_edit_map:
                ctx['property_location_url'] = reverse(
                    'workspace:crm_property_location', kwargs={'property_id': p.pk},
                )
        if not mask and not ctx.get('property_is_deleted'):
            from workspace.services.nearby_pois import nearby_pois_page_context
            ctx['show_nearby_pois'] = True
            ctx['nearby_pois_ctx'] = nearby_pois_page_context(p)
            ctx['nearby_pois_url'] = reverse(
                'workspace:crm_property_nearby_pois', kwargs={'property_id': p.pk},
            )
        else:
            ctx['show_nearby_pois'] = False
            ctx['nearby_pois_ctx'] = {}
            ctx['nearby_pois_url'] = ''
        if ctx.get('can_edit_property') and source_listing and not ctx.get('property_is_deleted'):
            from workspace.services.divar_session.ui_context import divar_contact_page_context

            ctx.update(divar_contact_page_context(self.request, source_listing))
        else:
            ctx.setdefault('divar_contact_enabled', False)
            ctx.setdefault('divar_contact_status', {})
        from ai_workspace.constants import (
            DEFAULT_LISTING_SUMMARY_STYLE,
            DEFAULT_LISTING_SUMMARY_TONE,
            FEATURE_LISTING_SUMMARY,
            LISTING_SUMMARY_STYLE_CHOICES,
            LISTING_SUMMARY_TONE_CHOICES,
            is_ai_enabled,
            is_feature_enabled,
        )
        from ai_workspace.services.quota import feature_quota_dict
        ctx['ai_listing_summary_enabled'] = (
            is_ai_enabled()
            and is_feature_enabled(FEATURE_LISTING_SUMMARY, self.request.user)
        )
        if ctx['ai_listing_summary_enabled']:
            ctx['ai_listing_summary_quota'] = feature_quota_dict(
                self.request.user, FEATURE_LISTING_SUMMARY,
            )
            ctx['ai_listing_summary_tone_options'] = LISTING_SUMMARY_TONE_CHOICES
            ctx['ai_listing_summary_style_options'] = LISTING_SUMMARY_STYLE_CHOICES
            ctx['ai_listing_summary_default_tone'] = DEFAULT_LISTING_SUMMARY_TONE
            ctx['ai_listing_summary_default_style'] = DEFAULT_LISTING_SUMMARY_STYLE
        from workspace.services.agency_space_ui_context import apply_agency_space_crm_context
        from workspace.services.agency_space_provenance import provenance_for_property
        apply_agency_space_crm_context(ctx, self.request.user, property=p)
        ctx['agency_space_copy_provenance'] = provenance_for_property(p, self.request.user)
        if not ctx.get('property_is_deleted') and not ctx.get('mask_sensitive'):
            can_deal = can_create_property_deal(self.request.user, p)
            ctx['can_create_deal'] = can_deal
            if can_deal:
                kind = infer_deal_kind_from_property(p)
                from workspace.services.crm_deal_stages import get_user_deal_stage_defs
                stage_defs = get_user_deal_stage_defs(self.request.user)
                ctx['property_deals'] = list(
                    property_deals_qs(self.request.user, p).order_by('-updated_at')[:3],
                )
                ctx['property_deals_total'] = property_deals_qs(self.request.user, p).count()
                ctx['property_active_deals'] = list(get_property_active_deals(self.request.user, p)[:5])
                ctx['property_deal_form'] = PropertyDealCreateForm(
                    user=self.request.user,
                    property_obj=p,
                )
                ctx['property_deal_kind'] = kind
                ctx['property_deal_suggested_title'] = suggest_deal_title(p, None, kind)
                ctx['property_deal_parties'] = get_property_deal_parties_context(p, kind)
                ctx['property_deal_stage_probs'] = {
                    d['name']: int(d.get('probability') or 50) for d in stage_defs
                }
            else:
                ctx['property_deals'] = []
                ctx['property_deals_total'] = 0
                ctx['property_active_deals'] = []
        from workspace.services.crm_property_archive import is_property_archived
        from workspace.services.crm_property_rental_renewal import (
            build_renewal_panel,
            property_is_rental,
            suggest_contract_end_one_year_after,
        )
        from workspace.services.jalali_input import format_jalali_date

        ctx['property_is_archived'] = is_property_archived(p)
        ctx['property_is_rental'] = property_is_rental(p)
        ctx['rental_renewal'] = build_renewal_panel(self.request.user, p)
        if property_is_rental(p):
            if p.rental_contract_end_date:
                ctx['rental_contract_end_suggested_jalali'] = format_jalali_date(p.rental_contract_end_date)
            else:
                ctx['rental_contract_end_suggested_jalali'] = format_jalali_date(
                    suggest_contract_end_one_year_after(),
                )
        else:
            ctx['rental_contract_end_suggested_jalali'] = ''
        return ctx

    def _detail_redirect(self, property_id, *, tab='contacts', drawer=''):
        url = reverse('workspace:crm_property_detail', kwargs={'property_id': property_id})
        qs = []
        if tab:
            qs.append(f'tab={tab}')
        if drawer:
            qs.append(f'drawer={drawer}')
        if qs:
            url += '?' + '&'.join(qs)
        return url

    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop:
            messages.error(request, 'ملک یافت نشد.')
            return redirect('workspace:crm_properties')
        if not can_edit_property(request.user, prop):
            messages.error(request, 'این ملک فقط برای مشاهده به اشتراک گذاشته شده است.')
            return redirect('workspace:crm_property_detail', property_id=property_id)
        action = request.POST.get('action', '')
        redirect_url = self._detail_redirect(property_id)
        if action == 'save_owner':
            phone = (request.POST.get('owner_phone') or '').strip()
            name = (request.POST.get('owner_name') or '').strip()
            customer = upsert_property_owner(
                request.user,
                phone=phone,
                name=name,
                crm_property=prop,
                source='سایر',
            )
            if phone and customer:
                messages.success(request, f'مالک «{customer.name}» ذخیره و به مخاطبین پیوند شد.')
            elif phone:
                messages.success(request, 'اطلاعات مالک ذخیره شد.')
            else:
                messages.success(request, 'شماره مالک پاک شد.')
            return redirect('workspace:crm_property_detail', property_id=property_id)
        if action == 'add_document':
            form = CustomerDocumentForm(request.POST, request.FILES)
            if form.is_valid():
                doc = form.save(commit=False)
                doc.user = request.user
                doc.property = prop
                doc.save()
                messages.success(request, 'مدرک آپلود شد.')
            redirect_url = self._detail_redirect(property_id, tab='docs')
        elif action == 'create_link_contact':
            lead_form = QuickLeadForm(request.POST, user=request.user)
            link_form = PropertyLinkForm(request.POST)
            if lead_form.is_valid() and link_form.is_valid():
                customer = lead_form.save(user=request.user)
                link_customer_property(
                    customer, prop,
                    link_form.cleaned_data['role'],
                    link_form.cleaned_data['deal_type'],
                    interest_level=link_form.cleaned_data.get('interest_level', ''),
                    is_primary=link_form.cleaned_data.get('is_primary', False),
                    notes=link_form.cleaned_data.get('notes', ''),
                )
                log_activity(customer, 'یادداشت', content=f'ثبت از صفحه ملک و پیوند به «{prop.title}»', title='ثبت مخاطب')
                messages.success(request, f'مخاطب «{customer.name}» ثبت و به ملک پیوند شد.')
            else:
                messages.error(request, 'ثبت مخاطب انجام نشد. فیلدهای الزامی را بررسی کنید.')
                return redirect(self._detail_redirect(property_id, tab='contacts', drawer='create-contact'))
        elif action == 'link_contact':
            link_form = PropertyLinkForm(request.POST)
            customer_id = request.POST.get('customer_id')
            if link_form.is_valid() and customer_id:
                customer = customer_for_user(request.user, int(customer_id))
                if not customer:
                    messages.error(request, 'مخاطب یافت نشد.')
                elif not can_edit_customer(request.user, customer):
                    messages.error(request, 'امکان پیوند این مخاطب را ندارید.')
                else:
                    link_customer_property(
                        customer, prop,
                        link_form.cleaned_data['role'],
                        link_form.cleaned_data['deal_type'],
                        interest_level=link_form.cleaned_data.get('interest_level', ''),
                        is_primary=link_form.cleaned_data.get('is_primary', False),
                        notes=link_form.cleaned_data.get('notes', ''),
                    )
                    messages.success(request, f'«{customer.name}» به ملک پیوند شد.')
            else:
                messages.error(request, 'پیوند انجام نشد. مخاطب و نقش را انتخاب کنید.')
                return redirect(self._detail_redirect(property_id, tab='contacts', drawer='link-contact'))
        elif action == 'unlink_contact':
            link_id = request.POST.get('link_id')
            link = prop.contact_links.filter(pk=link_id).select_related('customer').first()
            if not link:
                messages.error(request, 'پیوند یافت نشد.')
            else:
                name = link.customer.name
                log_activity(
                    link.customer,
                    'املاک',
                    content=f'حذف پیوند از ملک: {prop.title}',
                    property_obj=prop,
                )
                link.delete()
                messages.success(request, f'پیوند «{name}» حذف شد.')
            return redirect(self._detail_redirect(property_id, tab='contacts'))
        elif action == 'suggest_contacts':
            raw = request.POST.get('matches_json', '[]')
            try:
                selected = json.loads(raw)
            except json.JSONDecodeError:
                selected = []
            customer_ids = []
            if isinstance(selected, list):
                for item in selected:
                    if isinstance(item, dict) and item.get('customer_id'):
                        customer_ids.append(item['customer_id'])
                    elif isinstance(item, (int, str)):
                        customer_ids.append(item)
            if not customer_ids:
                messages.warning(request, 'حداقل یک مخاطب انتخاب کنید.')
                return redirect(self._detail_redirect(property_id, tab='suggest-contacts'))
            result = apply_contact_suggestions(
                prop,
                request.user,
                customer_ids,
                note=request.POST.get('suggest_note', ''),
                request=request,
            )
            linked = int(result.get('linked_count') or 0)
            if linked:
                request.session['crm_last_contact_suggestions'] = {
                    'whatsapp_text': result.get('whatsapp_text') or '',
                    'suggestions': result.get('suggestions') or [],
                    'count': linked,
                }
                messages.success(
                    request,
                    f'{linked} مخاطب پیشنهاد و به فایل پیوند شد.',
                )
                return redirect(self._detail_redirect(property_id, tab='contacts') + '&suggested=1')
            messages.error(request, 'ثبت پیشنهاد انجام نشد — مخاطبان انتخاب‌شده در دسترس نیستند.')
            return redirect(self._detail_redirect(property_id, tab='suggest-contacts'))
        elif action == 'schedule_followup':
            form = FollowUpForm(request.POST)
            if form.is_valid():
                schedule_property_follow_up(
                    request.user,
                    prop,
                    form.cleaned_data['next_follow_up'],
                    form.cleaned_data.get('note', ''),
                )
                messages.success(request, 'پیگیری فایل ثبت شد.')
            else:
                for err in form.errors.get('next_follow_up', form.non_field_errors()):
                    messages.error(request, str(err))
                return redirect(self._detail_redirect(property_id, drawer='followup'))
        elif action == 'quick_followup':
            try:
                days = int(request.POST.get('days', 1))
            except (TypeError, ValueError):
                days = 1
            days = max(1, min(days, 365))
            follow_date = timezone.now().date() + timedelta(days=days)
            schedule_property_follow_up(request.user, prop, follow_date)
            messages.success(request, f'پیگیری برای {days} روز دیگر ثبت شد.')
        elif action == 'complete_followup':
            if complete_property_follow_up(request.user, prop, request.POST.get('note', '')):
                messages.success(request, 'پیگیری انجام‌شده علامت خورد.')
            else:
                messages.warning(request, 'پیگیری فعالی برای بستن وجود ندارد.')
        return redirect(redirect_url)


def _property_deal_access_or_404(user, property_id):
    prop = property_for_user(user, property_id)
    if not prop or not can_create_property_deal(user, prop):
        return None
    return prop


class CRMPropertyDealCreateView(LoginRequiredMixin, View):
    """ثبت معامله از صفحه فایل شخصی."""

    def post(self, request, property_id):
        prop = _property_deal_access_or_404(request.user, property_id)
        if not prop:
            messages.error(request, 'دسترسی به این ملک برای ثبت معامله وجود ندارد.')
            return redirect('workspace:crm_properties')
        form = PropertyDealCreateForm(request.POST, user=request.user, property_obj=prop)
        if form.is_valid():
            deal = form.save()
            apply_deal_commission(deal)
            detail_url = reverse('workspace:crm_deal_detail', kwargs={'deal_id': deal.pk})
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': True, 'redirect': detail_url, 'deal_id': deal.pk})
            messages.success(request, 'معامله با موفقیت ثبت شد.')
            return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            dup = None
            customer_raw = request.POST.get('customer')
            customer_obj = None
            if customer_raw:
                try:
                    customer_obj = customer_for_user(request.user, int(customer_raw))
                except (TypeError, ValueError):
                    customer_obj = None
            for err in form.non_field_errors():
                if getattr(err, 'code', '') == 'duplicate_active_deal':
                    dup = find_duplicate_active_deal(request.user, prop, customer_obj)
            errors = {k: [str(e) for e in v] for k, v in form.errors.items()}
            payload = {'ok': False, 'errors': errors}
            if dup:
                payload['duplicate'] = {
                    'id': dup.pk,
                    'title': dup.title,
                    'stage': dup.stage,
                    'url': reverse('workspace:crm_deal_detail', kwargs={'deal_id': dup.pk}),
                }
            return JsonResponse(payload, status=400)
        messages.error(request, 'ثبت معامله انجام نشد. فیلدها را بررسی کنید.')
        for err in form.non_field_errors():
            messages.error(request, str(err))
        return redirect(
            reverse('workspace:crm_property_detail', kwargs={'property_id': prop.pk})
            + '?drawer=property-deal',
        )


class CRMPropertyDealCustomerSearchView(LoginRequiredMixin, View):
    def get(self, request, property_id):
        prop = _property_deal_access_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید'}, status=403)
        q = request.GET.get('q', '').strip()
        results = search_customers_for_property_deal(request.user, prop, q)
        return JsonResponse({'ok': True, 'results': results})


class CRMPropertyDealDuplicateCheckView(LoginRequiredMixin, View):
    def get(self, request, property_id):
        prop = _property_deal_access_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید'}, status=403)
        try:
            customer_id = int(request.GET.get('customer_id', 0))
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'مخاطب نامعتبر'}, status=400)
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        dup = find_duplicate_active_deal(request.user, prop, customer)
        if not dup:
            return JsonResponse({'ok': True, 'duplicate': None})
        return JsonResponse({
            'ok': True,
            'duplicate': {
                'id': dup.pk,
                'title': dup.title,
                'stage': dup.stage,
                'url': reverse('workspace:crm_deal_detail', kwargs={'deal_id': dup.pk}),
            },
        })


class CRMPropertyDealQuickCustomerView(LoginRequiredMixin, View):
    """ساخت سریع مخاطب از فرم ثبت معامله."""

    def post(self, request, property_id):
        prop = _property_deal_access_or_404(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید'}, status=403)
        form = QuickLeadForm(request.POST, user=request.user)
        if not form.is_valid():
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        customer = form.save(user=request.user)
        deal_kind = (request.POST.get('deal_kind') or infer_deal_kind_from_property(prop)).strip()
        from workspace.services.crm_deals import customer_type_for_deal_kind
        ctype = (request.POST.get('customer_type') or '').strip()
        customer.customer_type = ctype or customer_type_for_deal_kind(deal_kind)
        customer.save(update_fields=['customer_type', 'updated_at'])
        log_activity(customer, 'یادداشت', content='مخاطب سریع از ثبت معامله فایل شخصی', title='ثبت مخاطب')
        return JsonResponse({
            'ok': True,
            'customer': serialize_property_deal_customer(customer),
        })


class CRMPropertyUpdateView(LoginRequiredMixin, UpdateView):
    model = CRMProperty
    form_class = CRMPropertyForm
    template_name = 'workspace/crm/properties/detail.html'
    pk_url_kwarg = 'property_id'

    def get_queryset(self):
        return properties_qs(self.request.user)

    def get_object(self, queryset=None):
        prop = property_for_user(self.request.user, self.kwargs[self.pk_url_kwarg])
        if not prop or not can_edit_property(self.request.user, prop):
            from django.http import Http404
            raise Http404
        return prop

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return redirect(
            f"{reverse('workspace:crm_property_detail', kwargs={'property_id': self.object.pk})}?drawer=edit"
        )

    def form_valid(self, form):
        old_lat = self.object.latitude
        old_lng = self.object.longitude
        self.object = form.save()
        raw_images = self.request.POST.get('property_images_json')
        if raw_images is not None:
            images = parse_images_payload(raw_images)
            if images != (self.object.images or []):
                self.object.images = images
                self.object.save(update_fields=['images', 'updated_at'])
        if self.object.phone or self.object.owner_name:
            upsert_property_owner(
                self.request.user,
                phone=self.object.phone,
                name=self.object.owner_name,
                crm_property=self.object,
                source='سایر',
            )
        upsert_property_tenant(
            self.request.user,
            phone=self.object.tenant_phone,
            name=self.object.tenant_name,
            crm_property=self.object,
            source='سایر',
        )
        if (old_lat, old_lng) != (self.object.latitude, self.object.longitude):
            from workspace.services.nearby_pois import (
                clear_nearby_pois,
                mark_property_manual_location,
                should_clear_nearby_pois_on_location_change,
            )

            mark_property_manual_location(self.object)
            if should_clear_nearby_pois_on_location_change(
                old_lat, old_lng, self.object.latitude, self.object.longitude,
            ):
                clear_nearby_pois(self.object)
        messages.success(self.request, 'ملک به‌روز شد.')
        return redirect('workspace:crm_property_detail', property_id=self.object.pk)


class CRMPropertyImagesView(LoginRequiredMixin, View):
    """آپلود فوری تصویر برای فایل شخصی."""

    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop or not can_edit_property(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)
        uploaded = request.FILES.get('image')
        if not uploaded:
            return JsonResponse({'ok': False, 'error': 'فایلی انتخاب نشده است.'}, status=400)
        images = list(prop.images or [])
        if len(images) >= MAX_PROPERTY_IMAGES:
            return JsonResponse(
                {'ok': False, 'error': f'حداکثر {MAX_PROPERTY_IMAGES} تصویر مجاز است.'},
                status=400,
            )
        try:
            url = store_property_image(request.user, prop, uploaded)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        images.append(url)
        prop.images = images
        prop.save(update_fields=['images', 'updated_at'])
        return JsonResponse({'ok': True, 'url': url, 'images': prop.images})


class CRMPropertyLocationUpdateView(LoginRequiredMixin, View):
    """ذخیره مختصات نقشه فایل شخصی از روی نقشه تعاملی."""

    def post(self, request, property_id):
        from workspace.services.listing_map import parse_map_coordinates
        from workspace.services.public_share_common import build_map_navigation

        prop = property_for_user(request.user, property_id)
        if not prop or not can_edit_property(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)

        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            raw_lat = payload.get('latitude')
            raw_lng = payload.get('longitude')
        else:
            raw_lat = request.POST.get('latitude')
            raw_lng = request.POST.get('longitude')

        lat, lng, error = parse_map_coordinates(raw_lat, raw_lng)
        if error:
            return JsonResponse({'ok': False, 'error': error}, status=400)

        old_lat, old_lng = prop.latitude, prop.longitude
        prop.latitude = lat
        prop.longitude = lng
        from workspace.services.nearby_pois import mark_property_manual_location

        mark_property_manual_location(prop)
        prop.save(update_fields=['latitude', 'longitude', 'updated_at'])

        from workspace.services.nearby_pois import (
            clear_nearby_pois,
            should_clear_nearby_pois_on_location_change,
        )
        if should_clear_nearby_pois_on_location_change(old_lat, old_lng, lat, lng):
            clear_nearby_pois(prop)

        return JsonResponse({
            'ok': True,
            'latitude': lat,
            'longitude': lng,
            'map_navigation': build_map_navigation(lat, lng),
            'accessibility_status': '',
        })


class CRMPropertyNearbyPoisView(LoginRequiredMixin, View):
    """دریافت و ذخیره امکانات اطراف فایل شخصی — on-demand."""

    def get(self, request, property_id):
        from workspace.services.nearby_pois import property_accessibility_status_payload

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد.'}, status=404)

        share_ctx = build_property_share_context(request.user, prop)
        if share_ctx.mask_sensitive:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)

        return JsonResponse(property_accessibility_status_payload(prop))

    def post(self, request, property_id):
        from workspace.services.nearby_pois import (
            NearbyPoiError,
            api_response_payload,
            get_stored_nearby_pois_payload,
            property_accessibility_status_payload,
            refresh_property_accessibilities,
        )

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد.'}, status=404)

        share_ctx = build_property_share_context(request.user, prop)
        if share_ctx.mask_sensitive:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)

        force_refresh = False
        client_elements = None
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            force_refresh = bool(payload.get('refresh'))
            if 'elements' in payload:
                client_elements = payload.get('elements')

        if client_elements is not None:
            try:
                data = refresh_property_accessibilities(
                    prop,
                    request.user,
                    force_refresh=True,
                    elements=client_elements,
                )
            except NearbyPoiError as exc:
                body = {
                    'ok': False,
                    'code': exc.code,
                    'error': exc.message,
                }
                return JsonResponse(body, status=exc.status)
            return JsonResponse(data)

        if not force_refresh:
            cached = get_stored_nearby_pois_payload(prop)
            if cached:
                return JsonResponse(api_response_payload(cached, cached=True))

        try:
            body = refresh_property_accessibilities(
                prop,
                request.user,
                force_refresh=force_refresh or not bool(get_stored_nearby_pois_payload(prop)),
            )
        except NearbyPoiError as exc:
            body = {
                'ok': False,
                'code': exc.code,
                'error': exc.message,
                'error_message': exc.message,
                'status': 'failed',
            }
            if exc.code in ('service_unavailable', 'service_busy'):
                from workspace.services.nearby_pois import (
                    overpass_client_fallback,
                    resolve_property_location,
                )
                loc = resolve_property_location(prop)
                if loc.get('usable'):
                    body['fallback'] = overpass_client_fallback(loc['lat'], loc['lng'])
            return JsonResponse(body, status=exc.status)
        return JsonResponse(body)


class CRMPropertyDuplicateView(LoginRequiredMixin, View):
    """کپی فایل شخصی — JSON برای Web UI."""

    def post(self, request, property_id):
        from workspace.services.crm_property_duplicate import duplicate_property
        try:
            new_prop = duplicate_property(request.user, property_id)
        except PermissionError:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        edit_url = reverse('workspace:crm_property_edit', kwargs={'property_id': new_prop.pk})
        return JsonResponse({
            'ok': True,
            'property': {'id': new_prop.pk, 'title': new_prop.title},
            'redirect_url': edit_url,
        })


class CRMPropertyDeleteView(LoginRequiredMixin, View):
    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop or not can_edit_property(request.user, prop):
            messages.error(request, 'ملک یافت نشد یا امکان حذف ندارید.')
            return redirect('workspace:crm_properties')
        title = prop.title
        from django.utils import timezone
        prop.deleted_at = timezone.now()
        prop.save(update_fields=['deleted_at'])
        messages.success(request, f'ملک «{title}» حذف شد.')
        return redirect('workspace:crm_properties')


class CRMPropertyBulkDeleteView(LoginRequiredMixin, View):
    """حذف گروهی فایل‌های شخصی با تأیید دومرحله‌ای در UI."""

    def post(self, request):
        from workspace.services.crm import bulk_soft_delete_properties

        ids = []
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            ids = payload.get('property_ids') or payload.get('ids') or []
        else:
            ids = request.POST.getlist('property_ids') or request.POST.get('ids', '').split(',')

        result = bulk_soft_delete_properties(request.user, ids)
        if result['deleted'] == 0:
            return JsonResponse({
                'ok': False,
                'error': 'فایلی برای حذف انتخاب نشده یا دسترسی حذف ندارید.',
                **result,
            }, status=400)
        return JsonResponse({
            'ok': True,
            'message': f'{result["deleted"]} فایل حذف شد.',
            **result,
        })


class CRMPropertyPublicShareManageView(LoginRequiredMixin, View):
    """مدیریت لینک عمومی اشتراک فایل شخصی با مشتری."""

    def get(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop or not is_property_owner(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)
        from workspace.services.property_public_share import (
            get_or_create_property_share,
            property_public_share_url,
        )
        from workspace.services.public_share_common import share_profile_context
        share = get_or_create_property_share(request.user, prop)
        url = property_public_share_url(request, share)
        profile = share_profile_context(
            request.user, share, title=prop.title or '', share_url=url,
        )
        from workspace.services.nearby_pois import property_share_nearby_meta
        nearby_meta = property_share_nearby_meta(prop)
        return JsonResponse({
            'ok': True,
            'share_url': url,
            'share_token': share.share_token,
            'view_count': share.view_count,
            'consultant_name': profile['consultant_name'],
            'consultant_phone': profile['consultant_phone'],
            'welcome_message': profile['welcome_message'],
            'welcome_is_custom': profile['welcome_is_custom'],
            'default_share_message': profile['default_share_message'],
            'share_message_rendered': profile['share_message_rendered'],
            'social_links': profile['social_links'],
            'show_divar_link': share.show_divar_link,
            'show_full_address': share.show_full_address,
            'show_internal_notes': share.show_internal_notes,
            'approximate_location': share.approximate_location,
            'approximate_location_radius_m': share.approximate_location_radius_m,
            'show_nearby_pois': share.show_nearby_pois,
            'nearby_pois_meta': nearby_meta,
            'is_active': share.is_active,
        })

    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop or not is_property_owner(request.user, prop):
            messages.error(request, 'دسترسی ندارید.')
            return redirect('workspace:crm_property_detail', property_id=property_id)
        from workspace.services.property_public_share import (
            get_or_create_property_share,
            property_public_share_url,
        )
        from workspace.services.public_share_common import (
            apply_share_form_extras,
            clamp_approx_radius_m,
            normalize_consultant_fields_for_save,
        )
        share = get_or_create_property_share(request.user, prop)
        name, phone = normalize_consultant_fields_for_save(
            request.user,
            request.POST.get('consultant_name') or '',
            request.POST.get('consultant_phone') or '',
        )
        share.consultant_name = name
        share.consultant_phone = phone
        apply_share_form_extras(request.user, request.POST, share, files=request.FILES)
        share.show_divar_link = request.POST.get('show_divar_link') in ('1', 'true', 'on')
        share.show_full_address = request.POST.get('show_full_address') in ('1', 'true', 'on')
        share.show_internal_notes = request.POST.get('show_internal_notes') in ('1', 'true', 'on')
        share.approximate_location = request.POST.get('approximate_location') in ('1', 'true', 'on')
        if 'approximate_location_radius_m' in request.POST:
            share.approximate_location_radius_m = clamp_approx_radius_m(
                request.POST.get('approximate_location_radius_m'),
            )
        from workspace.services.nearby_pois import validate_share_show_nearby_pois
        want_nearby = request.POST.get('show_nearby_pois') in ('1', 'true', 'on')
        nearby_err = validate_share_show_nearby_pois(prop, enable=want_nearby)
        if nearby_err:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': nearby_err}, status=400)
            messages.error(request, nearby_err)
            return redirect('workspace:crm_property_detail', property_id=property_id)
        share.show_nearby_pois = want_nearby
        share.is_active = request.POST.get('is_active') in ('1', 'true', 'on')
        share.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'share_url': property_public_share_url(request, share),
                'message': 'تنظیمات اشتراک ذخیره شد.',
            })
        messages.success(request, 'تنظیمات لینک اشتراک ذخیره شد.')
        return redirect('workspace:crm_property_detail', property_id=prop.pk)


class CRMGlobalSearchView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get('q', '').strip()
        if len(q) < 2:
            return JsonResponse({'contacts': [], 'properties': []})
        result = global_search(request.user, q)
        return JsonResponse({
            'contacts': [
                {'id': c.id, 'name': c.name, 'phone': c.phone, 'type': c.customer_type,
                 'url': reverse('workspace:crm_detail', kwargs={'customer_id': c.id})}
                for c in result['contacts']
            ],
            'properties': [
                {'id': p.id, 'title': p.title, 'city': p.city, 'deal_mode': p.deal_mode,
                 'url': reverse('workspace:crm_property_detail', kwargs={'property_id': p.id})}
                for p in result['properties']
            ],
        })


class CRMListRedirectView(LoginRequiredMixin, View):
    def get(self, request):
        return redirect('workspace:crm_dashboard')


# ── فاز ۲: معاملات ───────────────────────────────────────────────────────────

class CRMDealListView(CRMDealsAccessMixin, CRMContextMixin, LoginRequiredMixin, ListView):
    model = CRMDeal
    template_name = 'workspace/crm/deals/list.html'
    context_object_name = 'deals'
    paginate_by = 20

    def get_queryset(self):
        return filter_deals(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['stats'] = get_deal_stats(self.request.user)
        ctx['deal_stages'] = get_user_deal_stages(self.request.user)
        ctx['deal_stage_defs'] = get_user_deal_stage_defs(self.request.user)
        ctx['deal_stage_meta'] = stage_meta_map(self.request.user)
        ctx['deal_stages_json'] = json.dumps(ctx['deal_stage_defs'], ensure_ascii=False)
        ctx['deal_stages_payload'] = serialize_stages_payload(self.request.user)
        ctx['view_mode'] = self.request.GET.get('view', 'table')
        ctx['pipeline'] = get_deal_pipeline(self.request.user, per_column=30)
        ctx['pipeline_interactive'] = True
        ctx['deal_form'] = ctx.get('deal_form', CRMDealForm(user=self.request.user))
        ctx['deal_create_form'] = CRMDealCreateForm(user=self.request.user)
        ctx['deal_next_action_types'] = DEAL_NEXT_ACTION_TYPES
        ctx['deal_followup_types'] = DEAL_FOLLOWUP_TYPES
        ctx['deal_next_action_types'] = DEAL_NEXT_ACTION_TYPES
        ctx['deal_stage_url_template'] = reverse(
            'workspace:crm_deal_stage', kwargs={'deal_id': 0},
        ).replace('/0/', '/{id}/')
        ctx['crm_section'] = 'deals'
        ctx['filter_qs'] = self.request.GET.urlencode()
        ctx['today'] = timezone.localdate()
        ctx['lost_reasons'] = LOST_REASONS
        ctx['saved_filters'] = list_saved_filters(self.request.user, 'deals')
        ctx['saved_filter_scope'] = 'deals'
        ctx['saved_filter_base'] = reverse('workspace:crm_deals')
        ctx['saved_filter_params'] = current_params_from_request(self.request, 'deals')
        ctx['saved_filter_can_save'] = bool(ctx['saved_filter_params'])
        return ctx


class CRMDealCreateView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def post(self, request):
        form = CRMDealCreateForm(request.POST, user=request.user)
        if form.is_valid():
            deal = form.save()
            apply_deal_commission(deal)
            messages.success(request, 'معامله ثبت شد.')
            nxt = request.POST.get('next')
            if nxt:
                return redirect(nxt)
            return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
        messages.error(request, 'ثبت معامله انجام نشد.')
        return redirect(request.POST.get('next') or reverse('workspace:crm_deals'))


class CRMDealDetailView(CRMDealsAccessMixin, CRMContextMixin, LoginRequiredMixin, DetailView):
    model = CRMDeal
    template_name = 'workspace/crm/deals/detail.html'
    context_object_name = 'deal'
    pk_url_kwarg = 'deal_id'

    def get_queryset(self):
        return deals_qs(self.request.user).select_related('customer', 'property')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        d = self.object
        stages = get_user_deal_stages(self.request.user)
        ensure_deal_checklist(d)
        ctx['deal_form'] = CRMDealForm(user=self.request.user, instance=d)
        ctx['deal_stages'] = stages
        ctx['deal_stage_defs'] = get_user_deal_stage_defs(self.request.user)
        ctx['deal_stage_meta'] = stage_meta_map(self.request.user)
        ctx['deal_stage_index'] = stages.index(d.stage) if d.stage in stages else 0
        ctx['checklist'] = d.checklist or []
        ctx['checklist_progress'] = checklist_progress(ctx['checklist'])
        ctx['lost_reasons'] = LOST_REASONS
        ctx['crm_section'] = 'deals'
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        if d.value and d.probability:
            ctx['weighted_value'] = int(d.value * d.probability / 100)
        else:
            ctx['weighted_value'] = None
        ctx['commission_splits'] = list(
            d.commission_splits.select_related('member__user').order_by('-percent')
        )
        ctx['finance'] = serialize_deal_finance(d)
        ctx['finance_defaults'] = get_finance_defaults(self.request.user)
        ctx['next_action'] = serialize_next_action(d)
        ctx['deal_next_action_types'] = DEAL_NEXT_ACTION_TYPES
        ctx['deal_followup_types'] = DEAL_FOLLOWUP_TYPES
        timeline = get_deal_timeline(d, limit=12, offset=0)
        ctx['deal_timeline'] = timeline['items']
        ctx['deal_timeline_has_more'] = timeline['has_more']
        ctx['deal_timeline_total'] = timeline['total']
        if d.customer_id and d.customer.phone:
            ctx['deal_customer_phone'] = d.customer.phone
        from contracts.services.routing import contracts_dashboard_url
        from contracts.services.scope import contract_for_deal
        deal_contracts_qs = contract_for_deal(self.request.user, d.pk)
        ctx['deal_contracts'] = list(deal_contracts_qs[:3])
        ctx['deal_contracts_count'] = deal_contracts_qs.count()
        ctx['deal_contracts_url'] = contracts_dashboard_url(deal=d.pk)
        ctx['deal_contract_summary'] = {
            'total': ctx['deal_contracts_count'],
            'finalized': deal_contracts_qs.filter(status='finalized').count(),
            'draft': deal_contracts_qs.filter(status='draft').count(),
            'pending': deal_contracts_qs.filter(
                status__in=('sent', 'viewed', 'partially_accepted', 'fully_accepted'),
            ).count(),
        }
        from workspace.services.access import has_active_bot_license
        ctx['contracts_locked'] = not has_active_bot_license(self.request.user)
        ctx['show_contract_stage_cta'] = (
            d.stage == 'قرارداد'
            and not deal_contracts_qs.exists()
            and d.stage not in ('بسته‌شده', 'از دست رفته')
            and has_active_bot_license(self.request.user)
        )
        ctx['deal_journey_tab'] = self.request.GET.get('tab', 'overview')
        from workspace.services.deal_journey import build_deal_journey_context
        ctx['deal_journey'] = build_deal_journey_context(
            d,
            user=self.request.user,
            next_action=ctx['next_action'],
            checklist_progress=ctx['checklist_progress'],
            contracts=list(deal_contracts_qs[:5]),
            contracts_count=ctx['deal_contracts_count'],
        )
        ctx['deal_stage_url'] = reverse('workspace:crm_deal_stage', kwargs={'deal_id': d.pk})
        return ctx

    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return redirect('workspace:crm_deals')
        action = request.POST.get('action', '')
        if action == 'update_stage':
            stage = request.POST.get('stage', '').strip()
            if is_valid_deal_stage(request.user, stage):
                update_deal_stage(deal, stage, lost_reason=request.POST.get('lost_reason', ''))
                messages.success(request, 'مرحله معامله به‌روز شد.')
        elif action == 'delete':
            title = deal.title
            deal.delete()
            messages.success(request, f'معامله «{title}» حذف شد.')
            return redirect('workspace:crm_deals')
        return redirect('workspace:crm_deal_detail', deal_id=deal_id)


class CRMDealUpdateView(CRMDealsAccessMixin, LoginRequiredMixin, UpdateView):
    model = CRMDeal
    form_class = CRMDealForm
    template_name = 'workspace/crm/deals/detail.html'
    pk_url_kwarg = 'deal_id'
    context_object_name = 'deal'

    def get_queryset(self):
        return deals_qs(self.request.user).select_related('customer', 'property')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def _edit_redirect(self, deal_id):
        return redirect(
            f"{reverse('workspace:crm_deal_detail', kwargs={'deal_id': deal_id})}?drawer=edit"
        )

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return self._edit_redirect(self.object.pk)

    def form_valid(self, form):
        self.object = form.save()
        apply_deal_commission(self.object)
        messages.success(self.request, 'معامله به‌روز شد.')
        return redirect('workspace:crm_deal_detail', deal_id=self.object.pk)

    def form_invalid(self, form):
        # Never re-render detail.html here — UpdateView lacks DetailView context
        # (deal_stages, deal_form, …) and used to 500 on {% url 'crm_detail' '' %}.
        messages.error(self.request, 'ذخیره انجام نشد. لطفاً فیلدها را بررسی کنید.')
        for field, errors in form.errors.items():
            if field == '__all__':
                for error in errors:
                    messages.error(self.request, error)
                continue
            label = form.fields[field].label if field in form.fields else field
            for error in errors:
                messages.error(self.request, f'{label}: {error}')
        deal_id = self.kwargs.get(self.pk_url_kwarg) or getattr(self.object, 'pk', None)
        return self._edit_redirect(deal_id)


class CRMDealStageUpdateView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            stage = (payload.get('stage') or '').strip()
            lost_reason = payload.get('lost_reason', '')
        else:
            stage = (request.POST.get('stage') or '').strip()
            lost_reason = request.POST.get('lost_reason', '')
        if stage not in get_user_deal_stages(request.user):
            return JsonResponse({'ok': False, 'error': 'مرحله نامعتبر'}, status=400)
        try:
            update_deal_stage(deal, stage, lost_reason=lost_reason)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'stage': stage, 'deal_id': deal.pk})


class CRMDealStagesView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    """مدیریت مراحل سفارشی pipeline."""

    def get(self, request):
        return JsonResponse({'ok': True, **serialize_stages_payload(request.user)})

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        try:
            if payload.get('reset'):
                defs = reset_user_deal_stages(request.user)
            elif payload.get('preset'):
                defs = apply_stage_preset(request.user, str(payload.get('preset')).strip())
            else:
                raw = payload.get('definitions')
                if raw is None:
                    raw = payload.get('stages') or []
                defs = save_user_deal_stage_defs(request.user, raw)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({
            'ok': True,
            'stages': [d['name'] for d in defs],
            'definitions': defs,
        })


class CRMDealChecklistView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    """تغییر وضعیت چک‌لیست معامله — B8."""

    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        item_id = (payload.get('item_id') or '').strip()
        if not item_id:
            return JsonResponse({'ok': False, 'error': 'آیتم نامعتبر'}, status=400)
        try:
            result = toggle_checklist_item(
                deal, item_id,
                done=payload.get('done') if 'done' in payload else None,
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, **result})


class CRMDealFollowUpView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    """ثبت پیگیری سریع معامله."""

    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        follow_type = (payload.get('type') or payload.get('follow_up_type') or '').strip()
        note = (payload.get('note') or payload.get('result') or '').strip()
        if not follow_type:
            return JsonResponse({'ok': False, 'error': 'نوع پیگیری الزامی است'}, status=400)
        na = parse_next_action_payload(_follow_up_next_action_payload(payload))
        follow_up = create_follow_up(
            deal,
            request.user,
            follow_up_type=follow_type,
            note=note,
            next_action_type='' if na.get('clear') else na.get('action_type', ''),
            next_action_at=None if na.get('clear') else na.get('action_at'),
            next_action_note='' if na.get('clear') else na.get('note', ''),
        )
        if na.get('clear'):
            clear_next_action(deal, save=True)
        return JsonResponse({
            'ok': True,
            'follow_up_id': follow_up.pk,
            'next_action': serialize_next_action(deal),
            'timeline_preview': get_deal_timeline(deal, limit=5, offset=0)['items'],
        })


class CRMDealNextActionView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def patch(self, request, deal_id):
        return self._handle(request, deal_id)

    def post(self, request, deal_id):
        return self._handle(request, deal_id)

    def _handle(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        na = parse_next_action_payload(payload)
        if na.get('clear') or (not na.get('action_type') and not na.get('action_at')):
            clear_next_action(deal, save=True)
        else:
            set_next_action(
                deal,
                action_type=na.get('action_type', ''),
                action_at=na.get('action_at'),
                note=na.get('note', ''),
                save=True,
            )
        return JsonResponse({'ok': True, 'next_action': serialize_next_action(deal)})


class CRMDealCompleteNextActionView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = {}
        note = (payload.get('note') or payload.get('result') or '').strip()
        follow_up = complete_next_action(deal, request.user, result_note=note)
        if not follow_up:
            return JsonResponse({'ok': False, 'error': 'اقدام بعدی تعیین نشده'}, status=400)
        return JsonResponse({
            'ok': True,
            'next_action': serialize_next_action(deal),
            'timeline_preview': get_deal_timeline(deal, limit=5, offset=0)['items'],
        })


class CRMDealTimelineView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def get(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            limit = min(int(request.GET.get('limit', 30)), 50)
            offset = max(int(request.GET.get('offset', 0)), 0)
        except (TypeError, ValueError):
            limit, offset = 30, 0
        return JsonResponse({'ok': True, **get_deal_timeline(deal, limit=limit, offset=offset)})


class CRMDealFinanceDashboardView(
    CRMFinanceDashboardAccessMixin, CRMContextMixin, LoginRequiredMixin, TemplateView,
):
    template_name = 'workspace/crm/deals/finance.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        period = (self.request.GET.get('period') or 'month').strip()
        ctx['finance'] = finance_dashboard(self.request.user, period)
        ctx['crm_section'] = 'deals-finance'
        ctx['period'] = ctx['finance']['period']
        return ctx


class CRMDealFinanceSettingsView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def get(self, request):
        return JsonResponse({'ok': True, 'defaults': get_finance_defaults(request.user)})

    def post(self, request):
        payload = {}
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        else:
            payload = request.POST.dict()
        defaults = save_finance_defaults(request.user, payload.get('defaults') if isinstance(payload.get('defaults'), dict) else payload)
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            return JsonResponse({'ok': True, 'defaults': defaults})
        messages.success(request, 'پیش‌فرض کمیسیون ذخیره شد.')
        nxt = request.POST.get('next') or reverse('workspace:crm_deals_finance')
        return redirect(nxt)


class CRMDealFinanceUpdateView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
            messages.error(request, 'معامله یافت نشد.')
            return redirect('workspace:crm_deals')
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        else:
            payload = {
                'deal_kind': request.POST.get('deal_kind'),
                'commission_mode': request.POST.get('commission_mode'),
                'buyer_commission_rate': request.POST.get('buyer_commission_rate'),
                'seller_commission_rate': request.POST.get('seller_commission_rate'),
                'buyer_commission_amount': request.POST.get('buyer_commission_amount'),
                'seller_commission_amount': request.POST.get('seller_commission_amount'),
                'advisor_share_percent': request.POST.get('advisor_share_percent'),
                'agency_share_percent': request.POST.get('agency_share_percent'),
                'deal_costs': request.POST.get('deal_costs'),
                'received_amount': request.POST.get('received_amount'),
                'payout_status': request.POST.get('payout_status'),
                'payout_notes': request.POST.get('payout_notes'),
            }
            payload = {k: v for k, v in payload.items() if v not in (None, '')}
        try:
            apply_deal_finance(deal, payload, save=True)
        except (TypeError, ValueError) as exc:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
            messages.error(request, 'ذخیره تنظیمات مالی انجام نشد.')
            return redirect('workspace:crm_deal_detail', deal_id=deal.pk)
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            return JsonResponse({'ok': True, 'finance': serialize_deal_finance(deal)})
        messages.success(request, 'تنظیمات مالی معامله ذخیره شد.')
        return redirect('workspace:crm_deal_detail', deal_id=deal.pk)


class CustomerBulkActionView(LoginRequiredMixin, View):
    def post(self, request):
        ids = request.POST.getlist('ids') or request.POST.get('ids', '').split(',')
        ids = [i.strip() for i in ids if str(i).strip().isdigit()]
        action = request.POST.get('bulk_action', '')
        nxt = request.POST.get('next') or reverse('workspace:crm_contacts')

        if not ids:
            messages.warning(request, 'مخاطبی انتخاب نشده است.')
            return redirect(nxt)

        from workspace.services.crm_contact_archive import (
            bulk_archive_contacts,
            bulk_restore_contacts,
        )

        ok_count = 0
        if action == 'delete':
            for c in customers_qs(request.user).filter(pk__in=ids):
                if can_edit_customer(request.user, c):
                    c.delete()
                    ok_count += 1
            messages.success(request, f'{ok_count} مخاطب حذف شد.')
        elif action == 'status' and request.POST.get('status') in CRM_STATUSES_UI:
            new_status = request.POST['status']
            for c in customers_qs(request.user).filter(pk__in=ids):
                if not can_edit_customer(request.user, c):
                    continue
                try:
                    update_customer_status(c, new_status, user=request.user)
                    ok_count += 1
                except ValueError:
                    continue
            messages.success(request, f'وضعیت {ok_count} مخاطب به «{new_status}» تغییر کرد.')
        elif action == 'archive':
            result = bulk_archive_contacts(request.user, ids)
            ok_count = result.get('archived', 0)
            messages.success(request, f'{ok_count} مخاطب بایگانی شد.')
        elif action == 'restore':
            restore_status = (request.POST.get('restore_status') or '').strip()
            result = bulk_restore_contacts(request.user, ids, restore_status=restore_status)
            ok_count = result.get('restored', 0)
            err_count = result.get('errors', 0)
            skip_count = result.get('skipped', 0)
            if ok_count:
                messages.success(request, f'{ok_count} مخاطب از بایگانی بازگردانی شد.')
            if err_count:
                messages.warning(
                    request,
                    f'{err_count} مخاطب بازگردانی نشد. برای رکوردهای قدیمی با وضعیت «بایگانی»، انتخاب مرحله ارتباط الزامی است.',
                )
            if skip_count and not ok_count and not err_count:
                messages.warning(request, 'مخاطب بایگانی‌شده‌ای برای بازگردانی انتخاب نشده است.')
            elif skip_count and ok_count:
                messages.info(request, f'{skip_count} مورد بدون تغییر رد شد.')
        elif action == 'tag':
            tag = request.POST.get('tag', '').strip()
            if tag:
                for c in customers_qs(request.user).filter(pk__in=ids):
                    if not can_edit_customer(request.user, c):
                        continue
                    tags = set(t.strip() for t in (c.tags or '').split(',') if t.strip())
                    tags.add(tag)
                    c.tags = ', '.join(sorted(tags))
                    c.save(update_fields=['tags', 'updated_at'])
                    ok_count += 1
                messages.success(request, f'برچسب به {ok_count} مخاطب اضافه شد.')
        else:
            messages.error(request, 'عملیات نامعتبر است.')
        return redirect(nxt)


class CustomerImportTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        return import_template_excel_response()


class CustomerImportErrorsDownloadView(LoginRequiredMixin, View):
    def get(self, request):
        from django.http import HttpResponse

        payload = request.session.pop('crm_import_error_report', None)
        if not payload:
            messages.info(request, 'گزارش خطای import در دسترس نیست.')
            return redirect(reverse('workspace:crm_contacts'))
        from workspace.services.crm_import import ContactImportResult, ImportRowError

        result = ContactImportResult(
            row_errors=[
                ImportRowError(
                    row_number=item['row'],
                    column=item.get('column') or '',
                    reason=item.get('reason') or '',
                    hint=item.get('hint') or '',
                )
                for item in payload
            ],
        )
        content = build_import_errors_csv(result)
        response = HttpResponse(content, content_type='text/csv; charset=utf-8-sig')
        response['Content-Disposition'] = 'attachment; filename="crm-import-errors.csv"'
        return response


class CustomerImportView(LoginRequiredMixin, View):
    def post(self, request):
        form = CustomerImportForm(request.POST, request.FILES)
        nxt = safe_crm_next_url(request, request.POST.get('next') or '')
        if form.is_valid():
            result = import_contacts_from_file_result(request.user, form.cleaned_data['file'])
            if result.aborted:
                messages.error(request, result.abort_reason or 'Import متوقف شد.')
                return redirect(nxt)
            for err in result.error_messages()[:5]:
                messages.warning(request, err)
            visible = result.visible_created_count(request.user)
            if result.created:
                from workspace.services.crm_import_batch import create_import_batch

                batch_id = create_import_batch(
                    request.user.id,
                    result.created_ids,
                    stats={
                        'created': result.created,
                        'duplicates': result.duplicates,
                        'invalid_rows': result.invalid_rows,
                        'skipped_empty_name': result.skipped_empty_name,
                    },
                )
                request.session['crm_last_import_batch_id'] = batch_id
                summary = (
                    f'{result.created} مخاطب ثبت شد'
                    f' ({result.duplicates} تکراری، {result.skipped_empty_name} بدون نام، '
                    f'{result.invalid_rows} نامعتبر).'
                )
                if visible < result.created:
                    summary += f' {visible} مورد در فهرست شما قابل مشاهده است.'
                messages.success(request, summary)
                nxt = append_query_param(nxt, 'import_batch', batch_id)
            elif not result.error_messages():
                messages.info(
                    request,
                    f'مخاطب جدیدی ثبت نشد ({result.duplicates} تکراری، '
                    f'{result.skipped_empty_name} بدون نام).',
                )
            if result.row_errors:
                request.session['crm_import_error_report'] = [
                    {
                        'row': e.row_number,
                        'column': e.column,
                        'reason': e.reason,
                        'hint': e.hint,
                    }
                    for e in result.row_errors[:500]
                ]
            else:
                request.session.pop('crm_import_error_report', None)
            return redirect(nxt)
        messages.error(request, 'فایل نامعتبر است.')
        view = CustomerListView()
        view.setup(request)
        view.object_list = view.get_queryset()
        ctx = view.get_context_data(object_list=view.object_list)
        ctx['import_form'] = form
        ctx['open_modal'] = 'drawer-import'
        return render(request, 'workspace/crm/contacts/list.html', ctx)


class CRMPropertyImportTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        return property_import_template_excel_response()


class CRMPropertyImportView(LoginRequiredMixin, View):
    def post(self, request):
        form = CRMPropertyImportForm(request.POST, request.FILES)
        nxt = request.POST.get('next') or reverse('workspace:crm_properties')
        if form.is_valid():
            try:
                created, skipped, errors = import_properties_from_file(
                    request.user, form.cleaned_data['file']
                )
            except Exception:
                messages.error(request, 'خواندن یا پردازش فایل ناموفق بود. قالب نمونه را دانلود و دوباره امتحان کنید.')
                return redirect(nxt)
            if errors:
                for err in errors[:3]:
                    messages.error(request, err)
            if created:
                messages.success(request, f'{created} فایل شخصی import شد ({skipped} رد شد).')
            elif not errors:
                messages.info(request, f'ملک جدیدی یافت نشد ({skipped} رد شد).')
            return redirect(nxt)
        messages.error(request, 'فایل نامعتبر است.')
        view = CRMPropertyListView()
        view.setup(request)
        view.object_list = view.get_queryset()
        ctx = view.get_context_data(object_list=view.object_list)
        ctx['property_import_form'] = form
        ctx['open_modal'] = 'drawer-property-import'
        return render(request, 'workspace/crm/properties/list.html', ctx)


class CustomerMergeView(LoginRequiredMixin, View):
    def post(self, request):
        primary_id = request.POST.get('primary_id')
        secondary_id = request.POST.get('secondary_id')
        nxt = request.POST.get('next') or reverse('workspace:crm_contacts')
        if not primary_id or not secondary_id:
            messages.error(request, 'هر دو مخاطب باید انتخاب شوند.')
            return redirect(nxt)
        primary = customer_for_user(request.user, int(primary_id))
        secondary = customer_for_user(request.user, int(secondary_id))
        if not primary or not secondary:
            messages.error(request, 'مخاطبین یافت نشدند.')
            return redirect(nxt)
        if not can_edit_customer(request.user, primary) or not can_edit_customer(request.user, secondary):
            messages.error(request, 'فقط مخاطبین خودتان قابل ادغام هستند.')
            return redirect(nxt)
        try:
            merge_customers(primary, secondary)
            messages.success(request, f'مخاطبین ادغام شدند — پروفایل «{primary.name}»')
            return redirect('workspace:crm_detail', customer_id=primary.pk)
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(nxt)


class CRMTemplatesView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/templates/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ensure_default_templates(user)
        grouped = templates_by_category(user)
        cat_filter = self.request.GET.get('cat', '').strip()
        q = self.request.GET.get('q', '').strip()
        if cat_filter:
            grouped = {cat_filter: grouped.get(cat_filter, [])}
        if q:
            filtered = {}
            for cat, items in grouped.items():
                hits = [
                    t for t in items
                    if q.lower() in t.name.lower() or q.lower() in t.body.lower()
                ]
                if hits:
                    filtered[cat] = hits
            grouped = filtered
        all_templates = list(CRMMessageTemplate.objects.filter(user=user))
        ctx['templates_by_category'] = grouped
        ctx['has_templates'] = any(items for items in grouped.values())
        ctx['template_form'] = ctx.get('template_form', CRMMessageTemplateForm())
        ctx['placeholders'] = MESSAGE_PLACEHOLDERS
        ctx['template_categories'] = MESSAGE_TEMPLATE_CATEGORIES
        ctx['cat_filter'] = cat_filter
        ctx['search_q'] = q
        ctx['stats'] = {
            'total': len(all_templates),
            'whatsapp': sum(1 for t in all_templates if t.channel == 'واتساپ'),
            'sms': sum(1 for t in all_templates if t.channel == 'پیامک'),
            'categories': len({t.category for t in all_templates}),
        }
        ctx['template_edit_payload'] = {
            str(t.pk): {
                'name': t.name,
                'category': t.category,
                'channel': t.channel,
                'body': t.body,
            }
            for t in all_templates
        }
        ctx['crm_section'] = 'templates'
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        return ctx

    def post(self, request):
        action = request.POST.get('action', 'save')
        if action == 'duplicate':
            tpl = get_object_or_404(
                CRMMessageTemplate, pk=request.POST.get('template_id'), user=request.user,
            )
            tpl.pk = None
            tpl.name = f'{tpl.name} (کپی)'
            tpl.is_system = False
            tpl.save()
            messages.success(request, 'کپی قالب ساخته شد.')
            return redirect('workspace:crm_templates')

        if action == 'delete':
            tpl = get_object_or_404(
                CRMMessageTemplate, pk=request.POST.get('template_id'), user=request.user,
            )
            if tpl.is_system:
                messages.warning(request, 'قالب پیش‌فرض سیستم قابل حذف نیست.')
            else:
                tpl.delete()
                messages.success(request, 'قالب حذف شد.')
            return redirect('workspace:crm_templates')

        instance = None
        tpl_id = request.POST.get('template_id')
        if tpl_id:
            instance = get_object_or_404(CRMMessageTemplate, pk=tpl_id, user=request.user)
        form = CRMMessageTemplateForm(request.POST, instance=instance)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.user = request.user
            if not instance:
                tpl.is_system = False
            tpl.save()
            messages.success(request, 'قالب ذخیره شد.')
            return redirect('workspace:crm_templates')
        ctx = self.get_context_data()
        ctx['template_form'] = form
        ctx['open_drawer'] = 'edit'
        return render(request, self.template_name, ctx)


class CRMAutomationView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/automation.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ensure_default_rules(self.request.user)
        rules = list(CRMAutomationRule.objects.filter(user=self.request.user))
        for rule in rules:
            rule.match_count = count_rule_matches(rule)
        ctx['rules'] = rules
        ctx['rules_active_count'] = sum(1 for r in rules if r.is_active)
        ctx['rule_preview'] = {r.id: r.match_count for r in rules}
        ctx['rule_form'] = ctx.get('rule_form', CRMAutomationRuleForm())
        ctx['crm_statuses'] = CRM_STATUSES
        ctx['automation_presets'] = AUTOMATION_PRESETS
        last_runs = [r.last_run_at for r in rules if r.last_run_at]
        ctx['stats'] = {
            'total': len(rules),
            'active': ctx['rules_active_count'],
            'queue': sum(ctx['rule_preview'].get(r.id, 0) for r in rules if r.is_active),
            'last_run': max(last_runs) if last_runs else None,
        }
        ctx['crm_section'] = 'automation'
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        return ctx

    def post(self, request):
        action = request.POST.get('action', 'save')
        if action == 'run':
            affected, rules_run = run_automation_for_user(request.user, min_interval_hours=0)
            messages.info(request, f'اتوماسیون اجرا شد — {affected} مخاطب تحت تأثیر ({rules_run} قانون).')
            return redirect('workspace:crm_automation')

        if action == 'run_rule':
            rule = get_object_or_404(
                CRMAutomationRule, pk=request.POST.get('rule_id'), user=request.user,
            )
            if not rule.is_active:
                messages.warning(request, 'قانون غیرفعال است — ابتدا فعالش کنید.')
            else:
                hits = run_single_rule(rule)
                messages.success(request, f'قانون «{rule.name}» اجرا شد — {hits} مخاطب تحت تأثیر.')
            return redirect('workspace:crm_automation')

        if action == 'toggle':
            rule = get_object_or_404(
                CRMAutomationRule, pk=request.POST.get('rule_id'), user=request.user,
            )
            rule.is_active = not rule.is_active
            rule.save(update_fields=['is_active', 'updated_at'])
            state = 'فعال' if rule.is_active else 'غیرفعال'
            messages.success(request, f'قانون «{rule.name}» {state} شد.')
            return redirect('workspace:crm_automation')

        if action == 'duplicate':
            rule = get_object_or_404(
                CRMAutomationRule, pk=request.POST.get('rule_id'), user=request.user,
            )
            rule.pk = None
            rule.name = f'{rule.name} (کپی)'
            rule.is_active = False
            rule.last_run_at = None
            rule.save()
            messages.success(request, 'کپی قانون ساخته شد.')
            return redirect('workspace:crm_automation')

        if action == 'delete':
            rule = get_object_or_404(
                CRMAutomationRule, pk=request.POST.get('rule_id'), user=request.user,
            )
            rule.delete()
            messages.success(request, 'قانون حذف شد.')
            return redirect('workspace:crm_automation')

        instance = None
        rule_id = request.POST.get('rule_id')
        if rule_id:
            instance = get_object_or_404(CRMAutomationRule, pk=rule_id, user=request.user)
        form = CRMAutomationRuleForm(request.POST, instance=instance)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            messages.success(request, 'قانون ذخیره شد.')
            return redirect('workspace:crm_automation')
        ctx = self.get_context_data()
        ctx['rule_form'] = form
        ctx['open_drawer'] = 'edit'
        return render(request, self.template_name, ctx)


class CRMCalendarView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/calendar.html'

    def get_context_data(self, **kwargs):
        import jdatetime

        from workspace.services.crm_scope import customers_qs

        ctx = super().get_context_data(**kwargs)
        today_j = jdatetime.date.today()
        try:
            jyear = int(self.request.GET.get('jy', self.request.GET.get('year', today_j.year)))
            jmonth = int(self.request.GET.get('jm', self.request.GET.get('month', today_j.month)))
        except (TypeError, ValueError):
            jyear, jmonth = today_j.year, today_j.month
        ctx['calendar'] = get_calendar_month(self.request.user, jyear, jmonth)
        ctx['reminder_form'] = CRMReminderForm()
        ctx['crm_customers'] = customers_qs(self.request.user).order_by('name')[:200]
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        ctx['crm_section'] = 'calendar'
        return ctx

    def post(self, request):
        form = CRMReminderForm(request.POST)
        if form.is_valid():
            reminder = form.save(commit=False)
            reminder.user = request.user
            customer_id = request.POST.get('customer_id')
            if customer_id:
                linked = customer_for_user(request.user, int(customer_id))
                if not linked or not can_edit_customer(request.user, linked):
                    messages.error(request, 'مخاطب انتخاب‌شده یافت نشد.')
                    ctx = self.get_context_data()
                    ctx['reminder_form'] = form
                    ctx['open_drawer'] = 'reminder'
                    return render(request, self.template_name, ctx)
                reminder.customer = linked
            reminder.save()
            messages.success(request, 'یادآور ثبت شد.')
            return redirect('workspace:crm_calendar')
        ctx = self.get_context_data()
        ctx['reminder_form'] = form
        ctx['open_drawer'] = 'reminder'
        for errors in form.errors.values():
            for err in errors:
                messages.error(request, str(err))
        return render(request, self.template_name, ctx)


class CRMNotificationsView(LoginRequiredMixin, View):
    def get(self, request):
        items = get_due_notifications(request.user)
        return JsonResponse({'ok': True, 'items': items})


class CRMMessagePreviewView(LoginRequiredMixin, View):
    def get(self, request, customer_id):
        from urllib.parse import quote

        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        tpl_id = request.GET.get('template_id')
        tpl = get_object_or_404(CRMMessageTemplate, pk=tpl_id, user=request.user)
        text = render_message_template(tpl, customer)
        phone = customer.phone or ''
        phone_wa = phone[1:] if phone.startswith('0') else phone
        wa_url = ''
        if phone_wa:
            wa_url = f'https://wa.me/98{phone_wa}?text={quote(text)}'
        return JsonResponse({'ok': True, 'text': text, 'whatsapp_url': wa_url})


class CRMPropertySharePreviewView(LoginRequiredMixin, View):
    """پیش‌نمایش متن اشتراک املاک انتخاب‌شده — فقط لینک عمومی."""

    def post(self, request, customer_id):
        from workspace.services.crm import build_portfolio_whatsapp_text, log_activity
        from workspace.services.property_suggestion_share import (
            resolve_portfolio_share_items,
            whatsapp_url_for_customer,
        )

        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not can_edit_customer(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'دسترسی ویرایش ندارید'}, status=403)
        try:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                body = json.loads(request.body.decode() or '{}')
            else:
                body = json.loads(request.POST.get('items_json', '[]'))
                body = {'items': body, 'log': request.POST.get('log') == '1'}
        except json.JSONDecodeError:
            return JsonResponse({'ok': False, 'error': 'داده نامعتبر'}, status=400)

        items = body.get('items') or []
        if not isinstance(items, list) or not items:
            return JsonResponse({'ok': False, 'error': 'حداقل یک ملک انتخاب کنید'}, status=400)

        matches = resolve_portfolio_share_items(request.user, customer, items, request)
        if not matches:
            return JsonResponse({'ok': False, 'error': 'ملک معتبری یافت نشد'}, status=400)

        text = build_portfolio_whatsapp_text(customer, matches)
        wa_url = whatsapp_url_for_customer(customer, text)

        if body.get('log'):
            titles = [m.get('title') or 'ملک' for m in matches]
            roles = {(m.get('role') or '').strip() for m in matches}
            roles.discard('')
            is_owner_share = bool(roles) and roles <= {'مالک', 'فروشنده', 'موجر', 'سازنده'}
            log_activity(
                customer,
                'املاک',
                content=f'اشتراک {len(matches)} ملک: ' + '، '.join(titles[:5]),
                title='ارسال فایل مالک' if is_owner_share else 'ارسال پیشنهاد ملک',
                metadata={
                    'suggestion_count': len(matches),
                    'titles': titles,
                    'share_only': True,
                    'roles': sorted(roles),
                },
            )

        return JsonResponse({
            'ok': True,
            'text': text,
            'whatsapp_url': wa_url,
            'count': len(matches),
        })


class CRMPropertyFolderListCreateView(LoginRequiredMixin, View):
    """لیست و ایجاد زونکن فایل شخصی — JSON."""

    def get(self, request):
        from workspace.services.crm_property_folders import list_property_folders, serialize_folder
        cabinet_id = request.GET.get('cabinet_id') or None
        rows = list_property_folders(request.user, cabinet_id=cabinet_id)
        return JsonResponse({
            'ok': True,
            'folders': [serialize_folder(f) for f in rows],
        })

    def post(self, request):
        from workspace.services.crm_property_folders import create_property_folder, serialize_folder
        try:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST
            folder = create_property_folder(
                request.user,
                name=payload.get('name', ''),
                description=payload.get('description', ''),
                color=payload.get('color', ''),
                icon=payload.get('icon', ''),
                is_pinned=bool(payload.get('is_pinned')),
                cabinet_id=payload.get('cabinet_id'),
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'folder': serialize_folder(folder)})


class CRMPropertyFolderDetailView(LoginRequiredMixin, View):
    """ویرایش و حذف زونکن — JSON."""

    def patch(self, request, folder_id):
        from workspace.services.crm_property_folders import serialize_folder, update_property_folder
        try:
            payload = json.loads(request.body.decode('utf-8'))
            folder = update_property_folder(request.user, folder_id, payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'folder': serialize_folder(folder)})

    def delete(self, request, folder_id):
        from workspace.services.crm_property_folders import delete_property_folder
        if not delete_property_folder(request.user, folder_id):
            return JsonResponse({'ok': False, 'error': 'زونکن یافت نشد'}, status=404)
        return JsonResponse({'ok': True})


class CRMPropertyFolderReorderView(LoginRequiredMixin, View):
    """مرتب‌سازی زونکن‌ها — JSON."""

    def post(self, request):
        from workspace.services.crm_property_folders import reorder_property_folders, serialize_folder
        try:
            payload = json.loads(request.body.decode('utf-8'))
            folder_ids = payload.get('folder_ids') or payload.get('order') or []
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        rows = reorder_property_folders(request.user, folder_ids)
        return JsonResponse({
            'ok': True,
            'folders': [serialize_folder(f) for f in rows],
        })


class CRMPropertyFolderMembershipView(LoginRequiredMixin, View):
    """افزودن/حذف ملک در زونکن — JSON."""

    def post(self, request, folder_id, property_id):
        from workspace.services.crm_property_folders import add_property_to_folder, serialize_folder, folder_for_user
        try:
            add_property_to_folder(request.user, folder_id, property_id)
            folder = folder_for_user(request.user, folder_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'folder': serialize_folder(folder) if folder else None})

    def delete(self, request, folder_id, property_id):
        from workspace.services.crm_property_folders import remove_property_from_folder
        try:
            remove_property_from_folder(request.user, folder_id, property_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMPropertyFolderBulkMembershipView(LoginRequiredMixin, View):
    """افزودن گروهی ملک‌ها به زونکن — JSON."""

    def post(self, request, folder_id):
        from workspace.services.crm_property_folders import bulk_add_properties_to_folder
        try:
            payload = json.loads(request.body.decode('utf-8'))
            property_ids = payload.get('property_ids') or payload.get('ids') or []
            result = bulk_add_properties_to_folder(request.user, folder_id, property_ids)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, **result})


class CRMPropertyCabinetListCreateView(LoginRequiredMixin, View):
    """لیست و ایجاد کمد فایل شخصی — JSON."""

    def get(self, request):
        from workspace.services.crm_property_cabinets import list_property_cabinets, serialize_cabinet
        rows = list_property_cabinets(request.user)
        return JsonResponse({
            'ok': True,
            'cabinets': [serialize_cabinet(c) for c in rows],
        })

    def post(self, request):
        from workspace.services.crm_property_cabinets import create_property_cabinet, serialize_cabinet
        try:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST
            cabinet = create_property_cabinet(
                request.user,
                name=payload.get('name', ''),
                description=payload.get('description', ''),
                color=payload.get('color', ''),
                icon=payload.get('icon', ''),
                is_pinned=bool(payload.get('is_pinned')),
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'cabinet': serialize_cabinet(cabinet)})


class CRMPropertyCabinetDetailView(LoginRequiredMixin, View):
    """ویرایش و حذف کمد — JSON."""

    def patch(self, request, cabinet_id):
        from workspace.services.crm_property_cabinets import serialize_cabinet, update_property_cabinet
        try:
            payload = json.loads(request.body.decode('utf-8'))
            cabinet = update_property_cabinet(request.user, cabinet_id, payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'cabinet': serialize_cabinet(cabinet)})

    def delete(self, request, cabinet_id):
        from workspace.services.crm_property_cabinets import delete_property_cabinet
        if not delete_property_cabinet(request.user, cabinet_id):
            return JsonResponse({'ok': False, 'error': 'کمد یافت نشد'}, status=404)
        return JsonResponse({'ok': True})


class CRMPropertyCabinetReorderView(LoginRequiredMixin, View):
    """مرتب‌سازی کمدها — JSON."""

    def post(self, request):
        from workspace.services.crm_property_cabinets import reorder_property_cabinets, serialize_cabinet
        try:
            payload = json.loads(request.body.decode('utf-8'))
            cabinet_ids = payload.get('cabinet_ids') or payload.get('order') or []
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        rows = reorder_property_cabinets(request.user, cabinet_ids)
        return JsonResponse({
            'ok': True,
            'cabinets': [serialize_cabinet(c) for c in rows],
        })


class CRMPropertyCabinetFolderAssignView(LoginRequiredMixin, View):
    """انتساب زونکن به کمد — JSON."""

    def post(self, request, cabinet_id, folder_id):
        from workspace.services.crm_property_cabinets import assign_folder_to_cabinet
        from workspace.services.crm_property_folders import serialize_folder
        try:
            folder = assign_folder_to_cabinet(request.user, folder_id, cabinet_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'folder': serialize_folder(folder)})

    def delete(self, request, cabinet_id, folder_id):
        from workspace.services.crm_property_cabinets import remove_folder_from_cabinet
        from workspace.services.crm_property_folders import folder_for_user, serialize_folder
        folder = folder_for_user(request.user, folder_id)
        if not folder:
            return JsonResponse({'ok': False, 'error': 'زونکن یافت نشد'}, status=404)
        if not folder.cabinet_id or int(folder.cabinet_id) != int(cabinet_id):
            return JsonResponse({'ok': False, 'error': 'زونکن در این کمد نیست'}, status=400)
        try:
            folder = remove_folder_from_cabinet(request.user, folder_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'folder': serialize_folder(folder)})


class CRMSavedFilterListView(LoginRequiredMixin, View):
    """لیست فیلترهای ذخیره‌شده — JSON."""

    def get(self, request):
        scope = (request.GET.get('scope') or '').strip()
        rows = list_saved_filters(request.user, scope) if scope else []
        return JsonResponse({
            'ok': True,
            'filters': [serialize_filter(f) for f in rows],
        })


class CRMSavedFilterCreateView(LoginRequiredMixin, View):
    """ذخیره فیلتر جاری."""

    def post(self, request):
        try:
            if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
                payload = json.loads(request.body.decode('utf-8'))
            else:
                payload = request.POST
            name = (payload.get('name') or '').strip()
            scope = (payload.get('scope') or '').strip()
            params = payload.get('params') or {}
            is_pinned = bool(payload.get('is_pinned'))
            obj = save_filter(
                request.user,
                name=name,
                scope=scope,
                params=params,
                is_pinned=is_pinned,
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'filter': serialize_filter(obj)})


# ── فاز ۴: تیم آژانس ─────────────────────────────────────────────────────────

class CRMTeamBadPathRedirectView(LoginRequiredMixin, View):
    """هدایت مسیرهای اشتباه مثل /crm/team/undefined به Agency Hub."""

    def get(self, request, bad_path=''):
        return redirect('workspace:agency_hub_settings_sync')

    def post(self, request, bad_path=''):
        return redirect('workspace:agency_hub_settings_sync')


class CRMTeamApiKeyRegenerateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            key = regenerate_api_key(request.user)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        return JsonResponse({'ok': True, 'key': key})


class CRMTeamReportCSVView(ExportSecurityMixin, LoginRequiredMixin, View):
    def get(self, request):
        from django.http import HttpResponse
        from workspace.services.crm_agency_analytics import export_team_performance_csv

        agency = get_agency(request.user)
        if not agency or not can_manage_team(request.user):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست'}, status=403)
        days = int(request.GET.get('days', 30))
        csv_text = export_team_performance_csv(agency, days=days)
        resp = HttpResponse(csv_text, content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = 'attachment; filename="team-performance.csv"'
        return resp


class CRMTeamTVView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    """Legacy route — redirects to Agency Hub TV."""

    def get(self, request, *args, **kwargs):
        return redirect('workspace:agency_hub_tv')


class CRMTeamView(AgencyTeamHubRequiredMixin, CRMContextMixin, LoginRequiredMixin, TemplateView):
    """Legacy compatibility — GET redirects; context/post reused by Agency Hub."""
    template_name = 'workspace/crm/team/index.html'

    def dispatch(self, request, *args, **kwargs):
        from workspace.services.agency_entitlement import can_manage_agency, has_assigned_agency_seat
        from workspace.services.crm_scope import can_manage_team
        if (
            request.user.is_authenticated
            and has_assigned_agency_seat(request.user)
            and not can_manage_agency(request.user)
            and not can_manage_team(request.user)
        ):
            return redirect(reverse('workspace:agency_advisor_member'))
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        from workspace.services.agency_team_routes import redirect_legacy_team_tab
        return redirect_legacy_team_tab(request)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['crm_section'] = 'team'
        ctx['crm_team_url'] = reverse('workspace:agency_team_action')
        ctx['crm_api_key_reveal_url'] = reverse('workspace:docs_api_crm_key')
        ctx['crm_api_key_regenerate_url'] = reverse('workspace:crm_team_api_key_regenerate')
        ctx['crm_team_report_csv_url'] = reverse('workspace:crm_team_report_csv')
        membership = get_membership(self.request.user)
        agency = membership.agency if membership else None
        ctx['agency_roles'] = AGENCY_ROLES
        ctx['webhook_events'] = WEBHOOK_EVENTS
        ctx['webhook_event_labels'] = WEBHOOK_EVENT_LABELS
        user = self.request.user
        perf_days = int(self.request.GET.get('days', 30) or 30)
        if perf_days not in (7, 30, 90):
            perf_days = 30
        ctx['perf_days'] = perf_days
        ctx['lead_routing_choices'] = LEAD_ROUTING_CHOICES
        ctx['can_view_team_inbox'] = can_view_team_inbox(user)
        ctx['can_operate_team_leads'] = can_operate_team_leads(user)
        ctx['agency_feature_messages'] = is_agency_feature_enabled('messages', agency) if agency else False
        ctx['agency_feature_announcements'] = is_agency_feature_enabled('announcements', agency) if agency else False
        ctx['agency_feature_tv'] = is_agency_feature_enabled('tv_mode', agency) if agency else False
        ctx['crm_team_tv_url'] = reverse('workspace:agency_hub_tv')
        goal_start_jalali, goal_end_jalali = jalali_month_bounds_display()
        quarter_start_jalali, quarter_end_jalali = jalali_quarter_ahead_display()
        ctx['goal_period_start_default'] = to_persian_digits(goal_start_jalali)
        ctx['goal_period_end_default'] = to_persian_digits(goal_end_jalali)
        ctx['goal_period_quarter_start'] = to_persian_digits(quarter_start_jalali)
        ctx['goal_period_quarter_end'] = to_persian_digits(quarter_end_jalali)
        if agency:
            sync_agency_member_records(agency)
            ctx['agency_logo_url'] = _agency_logo_url(agency)
            full_performance = get_team_performance(agency, days=perf_days)
            can_view_perf = can_view_team_performance(user)
            ctx['can_view_team_performance'] = can_view_perf
            ctx['performance'] = full_performance if can_view_perf else None
            ctx['my_performance'] = get_member_performance_row(agency, user.id, days=perf_days)
            ctx['command_center'] = get_command_center_stats(agency, days=perf_days) if can_view_perf else None
            ctx['team_goals'] = get_team_goals_progress(agency, days=perf_days) if can_view_perf else []
            ctx['team_inbox'] = list(team_inbox_qs(user)[:50]) if can_view_team_inbox(user) else []
            ctx['assigned_leads'] = list(manager_assigned_customers_qs(user)[:30]) if can_view_team_inbox(user) else []
            ctx['sync_logs'] = list(CRMSyncLog.objects.filter(agency=agency).select_related('user')[:15]) if can_manage_team(user) else []
            audit_logs_qs = CRMAgencyAuditLog.objects.filter(agency=agency).select_related('actor')
            if can_manage_team(user):
                audit_logs = list(audit_logs_qs[:80])
                ctx['audit_logs'] = audit_logs
                ctx['audit_timeline'] = build_audit_timeline(audit_logs)
            else:
                ctx['audit_logs'] = []
                ctx['audit_timeline'] = None
            ctx['webhooks'] = list(CRMAgencyWebhook.objects.filter(agency=agency).order_by('-created_at'))
            transfers_qs = CustomerTransferLog.objects.filter(agency=agency).filter(
                Q(from_user=user) | Q(to_user=user) | Q(transferred_by=user),
            ).select_related(
                'customer', 'from_user', 'to_user', 'transferred_by',
            )
            ctx['recent_transfers'] = transfers_qs[:20]
            ctx['transfer_count'] = transfers_qs.count()
            members_list = list(ctx.get('agency_members') or list(agency_members(agency)))
            perf_by_member = {r['member'].pk: r for r in full_performance['members']}
            perf_by_user = {r['member'].user_id: r for r in full_performance['members']}
            totals = full_performance['totals']
            ctx['team_stats'] = {
                'contacts': totals['contacts'] if can_view_perf else customers_qs(user).count(),
                'properties': totals['properties'] if can_view_perf else properties_qs(user).count(),
                'deals': totals['deals_closed'] if can_view_perf else deals_qs(user).count(),
                'active_deals': totals['active_deals'] if can_view_perf else 0,
                'members': len(members_list),
            }
            allocated_map = {}
            if can_manage_team(user):
                from licenses.services.management import build_agency_license_pool
                pool_early = build_agency_license_pool(agency.owner)
                allocated_map = pool_early.get('assigned_by_user') or {}
                ctx['agency_license_pool'] = pool_early
            ctx['member_rows'] = [
                {
                    'member': m,
                    'perf': (
                        perf_by_member.get(m.pk) or perf_by_user.get(m.user_id) or {}
                    ) if can_view_perf or m.user_id == user.id else {},
                    'allocated_license': allocated_map.get(m.user_id),
                }
                for m in members_list
            ]
            ctx['api_leads_path'] = reverse('workspace:crm_api_leads')
            pending = CRMAgencyMembershipRequest.objects.filter(
                agency=agency, status=CRMAgencyMembershipRequest.STATUS_PENDING,
            ).select_related('user', 'requested_by')
            ctx['pending_invites_sent'] = pending.filter(
                request_type=CRMAgencyMembershipRequest.TYPE_INVITE,
            )
            ctx['pending_join_requests'] = pending.filter(
                request_type=CRMAgencyMembershipRequest.TYPE_JOIN,
            )
            ctx['team_roster_summary'] = {
                'active': len(members_list),
                'pending_invites': ctx['pending_invites_sent'].count(),
                'pending_joins': ctx['pending_join_requests'].count(),
            }
            ctx['my_pending_invites'] = CRMAgencyMembershipRequest.objects.filter(
                user=user,
                request_type=CRMAgencyMembershipRequest.TYPE_INVITE,
                status=CRMAgencyMembershipRequest.STATUS_PENDING,
            ).select_related('agency', 'requested_by')
            ctx['my_pending_join'] = []
            ctx['messages_unread_count'] = unread_message_count(user) if ctx['agency_feature_messages'] else 0
            ctx['announcements_unread_count'] = unread_announcement_count(user) if ctx['agency_feature_announcements'] else 0
            ctx['api_crm_team_messages_url'] = reverse('workspace:api_crm_team_messages')
            ctx['api_crm_team_messages_unread_url'] = reverse('workspace:api_crm_team_messages_unread')
            ctx['api_crm_team_messages_members_url'] = reverse('workspace:api_crm_team_messages_members')
            ctx['api_crm_team_notifications_url'] = reverse('workspace:api_crm_team_notifications')
            ctx['api_crm_team_announcements_url'] = reverse('workspace:api_crm_team_announcements')
        else:
            ctx['agency_logo_url'] = None
            ctx['performance'] = None
            ctx['my_performance'] = None
            ctx['can_view_team_performance'] = False
            ctx['webhooks'] = []
            ctx['recent_transfers'] = []
            ctx['transfer_count'] = 0
            ctx['team_stats'] = None
            ctx['member_rows'] = []
            ctx['team_roster_summary'] = None
            ctx['api_leads_path'] = ''
            ctx['command_center'] = None
            ctx['team_goals'] = []
            ctx['team_inbox'] = []
            ctx['assigned_leads'] = []
            ctx['sync_logs'] = []
            ctx['audit_logs'] = []
            ctx['audit_timeline'] = None
            ctx['messages_unread_count'] = 0
            ctx['announcements_unread_count'] = 0
            ctx['agency_feature_messages'] = False
            ctx['agency_feature_announcements'] = False
            ctx['agency_feature_tv'] = False
            ctx['pending_invites_sent'] = []
            ctx['pending_join_requests'] = []
            ctx['my_pending_invites'] = CRMAgencyMembershipRequest.objects.filter(
                user=user,
                request_type=CRMAgencyMembershipRequest.TYPE_INVITE,
                status=CRMAgencyMembershipRequest.STATUS_PENDING,
            ).select_related('agency', 'requested_by')
            ctx['my_pending_join'] = CRMAgencyMembershipRequest.objects.filter(
                user=user,
                request_type=CRMAgencyMembershipRequest.TYPE_JOIN,
                status=CRMAgencyMembershipRequest.STATUS_PENDING,
            ).select_related('agency')
        tab = self.request.GET.get('tab')
        if not tab:
            from workspace.services.agency_entitlement import can_manage_agency as _can_manage_agency
            if agency and _can_manage_agency(user):
                tab = 'members'
            elif agency and can_manage_team(user):
                tab = 'command'
            else:
                tab = 'overview'
        manager_only = {'sync', 'webhooks', 'transfers', 'command', 'settings', 'audit'}
        if tab in manager_only and not can_manage_team(user):
            tab = 'overview'
        elif tab == 'inbox' and not can_view_team_inbox(user):
            tab = 'overview'
        elif tab == 'messages' and not (agency and is_agency_feature_enabled('messages', agency)):
            tab = 'overview'
        elif tab == 'announcements' and not (agency and is_agency_feature_enabled('announcements', agency)):
            tab = 'overview'
        ctx['tab'] = tab
        from workspace.services.agency_entitlement import (
            agency_hub_access_level,
            can_manage_agency,
        )
        ctx['agency_hub_access_level'] = agency_hub_access_level(user)
        ctx['can_manage_agency'] = can_manage_agency(user)
        if agency and can_manage_agency(user):
            from workspace.constants import AGENCY_ROLES_ASSIGNABLE, AGENCY_ROLES_INVITE
            from workspace.services.agency_members import build_members_dashboard
            from workspace.services.agency_rbac import is_agency_rbac_v2_enabled
            from workspace.services.agency_seats import list_available_seats
            ctx['members_dashboard'] = build_members_dashboard(user, agency)
            ctx['available_seats'] = list_available_seats(user, agency)
            ctx['agency_roles_invite'] = AGENCY_ROLES_INVITE
            ctx['agency_roles_assignable'] = AGENCY_ROLES_ASSIGNABLE
            ctx['agency_rbac_v2'] = is_agency_rbac_v2_enabled(agency)
        else:
            ctx['members_dashboard'] = None
            ctx['available_seats'] = []
        if agency and can_manage_team(user):
            from licenses.services.management import build_license_dashboard
            ctx['license_dashboard'] = build_license_dashboard(user)
            if 'agency_license_pool' not in ctx:
                from licenses.services.management import build_agency_license_pool
                ctx['agency_license_pool'] = build_agency_license_pool(agency.owner)
        else:
            ctx['license_dashboard'] = None
            ctx.setdefault('agency_license_pool', None)
        return ctx

    def post(self, request):
        action = request.POST.get('action', '')
        tab = request.POST.get('tab') or request.GET.get('tab', 'overview')
        try:
            if action == 'create_agency':
                create_agency(request.user, request.POST.get('name', ''))
                messages.success(request, 'آژانس ایجاد شد و داده‌های شما متصل شد.')
            elif action in ('invite_member', 'agency_invite'):
                from workspace.services.agency_invitations import create_agency_invitation
                create_agency_invitation(
                    request.user,
                    request.POST.get('phone', ''),
                    request.POST.get('role', 'advisor'),
                    request=request,
                )
                messages.success(request, 'دعوت SMS ارسال شد.')
            elif action == 'agency_invite_resend':
                from workspace.services.agency_invitations import resend_invitation_sms
                resend_invitation_sms(
                    request.user, int(request.POST.get('invitation_id', 0)), request=request,
                )
                messages.success(request, 'پیامک مجدداً ارسال شد.')
            elif action == 'agency_invite_cancel':
                from workspace.services.agency_invitations import cancel_agency_invitation
                cancel_agency_invitation(request.user, int(request.POST.get('invitation_id', 0)))
                messages.success(request, 'دعوت لغو شد.')
            elif action == 'agency_assign_seat':
                from workspace.services.agency_seats import assign_seat_to_member
                assign_seat_to_member(
                    request.user,
                    int(request.POST.get('license_id', 0)),
                    int(request.POST.get('member_user_id', 0)),
                )
                messages.success(request, 'لایسنس تخصیص داده شد.')
            elif action == 'agency_unassign_seat':
                from workspace.services.agency_seats import unassign_seat
                unassign_seat(request.user, int(request.POST.get('license_id', 0)))
                messages.success(request, 'تخصیص لایسنس لغو شد.')
            elif action == 'agency_remove_member':
                from workspace.services.agency_members import remove_agency_member
                remove_agency_member(request.user, int(request.POST.get('member_id', 0)))
                messages.success(request, 'عضو از آژانس حذف شد.')
            elif action == 'request_join':
                request_join_agency(
                    request.user,
                    request.POST.get('agency_slug', ''),
                    request.POST.get('message', ''),
                )
                messages.success(request, 'درخواست عضویت ارسال شد — منتظر تأیید مدیر آژانس باشید.')
            elif action == 'respond_request':
                accept = request.POST.get('decision') == 'accept'
                respond_membership_request(
                    request.user,
                    int(request.POST.get('request_id', 0)),
                    accept=accept,
                )
                messages.success(request, 'درخواست پذیرفته شد.' if accept else 'درخواست رد شد.')
            elif action == 'cancel_request':
                cancel_membership_request(
                    request.user,
                    int(request.POST.get('request_id', 0)),
                )
                messages.success(request, 'درخواست لغو شد.')
            elif action == 'update_role':
                update_member_role(
                    request.user,
                    int(request.POST.get('member_id', 0)),
                    request.POST.get('role', ''),
                )
                messages.success(request, 'نقش به‌روز شد.')
            elif action == 'agency_apply_role_preset':
                from workspace.services.agency_rbac import apply_member_role_preset

                apply_member_role_preset(
                    request.user,
                    int(request.POST.get('member_id', 0)),
                    request.POST.get('preset', ''),
                )
                messages.success(request, 'الگوی نقش اعمال شد.')
            elif action == 'agency_update_member_permissions':
                from workspace.services.agency_rbac import update_member_permission_overrides

                overrides = {}
                for key in request.POST:
                    if key.startswith('perm_'):
                        perm_key = key[5:]
                        overrides[perm_key] = request.POST.get(key) == '1'
                update_member_permission_overrides(
                    request.user,
                    int(request.POST.get('member_id', 0)),
                    overrides,
                )
                messages.success(request, 'مجوزهای عضو به‌روز شد.')
            elif action == 'remove_member':
                remove_member(request.user, int(request.POST.get('member_id', 0)))
                messages.success(request, 'عضو غیرفعال شد.')
            elif action == 'add_webhook':
                m = get_membership(request.user)
                if not can_manage_team(request.user):
                    raise ValueError('دسترسی ندارید')
                events = request.POST.getlist('events')
                hook = CRMAgencyWebhook.objects.create(
                    agency=m.agency,
                    name=request.POST.get('name', '').strip() or 'وب‌هوک',
                    url=request.POST.get('url', '').strip(),
                    secret=request.POST.get('secret', '').strip(),
                    events=events,
                )
                log_agency_audit(m.agency, request.user, 'webhook.created', {'webhook_id': hook.pk})
                messages.success(request, 'وب‌هوک ثبت شد.')
            elif action == 'delete_webhook':
                m = get_membership(request.user)
                if not can_manage_team(request.user):
                    raise ValueError('دسترسی ندارید')
                hook = get_object_or_404(
                    CRMAgencyWebhook, pk=request.POST.get('webhook_id'), agency=m.agency,
                )
                hook_id = hook.pk
                hook.delete()
                log_agency_audit(m.agency, request.user, 'webhook.deleted', {'webhook_id': hook_id})
                messages.success(request, 'وب‌هوک حذف شد.')
            elif action == 'toggle_webhook':
                m = get_membership(request.user)
                if not can_manage_team(request.user):
                    raise ValueError('دسترسی ندارید')
                hook = get_object_or_404(
                    CRMAgencyWebhook, pk=request.POST.get('webhook_id'), agency=m.agency,
                )
                hook.is_active = not hook.is_active
                hook.save(update_fields=['is_active'])
                messages.success(request, 'وضعیت وب‌هوک به‌روز شد.')
            elif action == 'test_webhook':
                m = get_membership(request.user)
                if not can_manage_team(request.user):
                    raise ValueError('دسترسی ندارید')
                hook = get_object_or_404(
                    CRMAgencyWebhook, pk=request.POST.get('webhook_id'), agency=m.agency,
                )
                ok, msg = test_webhook(hook)
                log_agency_audit(m.agency, request.user, 'webhook.tested', {'webhook_id': hook.pk, 'ok': ok})
                if ok:
                    messages.success(request, 'تست وب‌هوک موفق بود.')
                else:
                    messages.error(request, f'تست وب‌هوک ناموفق: {msg}')
            elif action == 'update_agency':
                update_agency_settings(
                    request.user,
                    name=request.POST.get('name', ''),
                    lead_routing_policy=request.POST.get('lead_routing_policy', ''),
                )
                messages.success(request, 'تنظیمات آژانس ذخیره شد.')
            elif action == 'assign_inbox_lead':
                customer = get_object_or_404(
                    Customer, pk=int(request.POST.get('customer_id', 0)), agency=get_membership(request.user).agency,
                )
                assign_lead_to_member(
                    request.user, customer, int(request.POST.get('member_id', 0)),
                )
                messages.success(request, 'سرنخ تخصیص داده شد.')
            elif action == 'bulk_assign_inbox':
                ids = [int(x) for x in request.POST.getlist('customer_ids') if x.isdigit()]
                count = bulk_assign_leads(request.user, ids, int(request.POST.get('member_id', 0)))
                messages.success(request, f'{count} سرنخ تخصیص داده شد.')
            elif action == 'set_team_goal':
                m = get_membership(request.user)
                if not can_manage_team(request.user):
                    raise ValueError('دسترسی ندارید')
                member = None
                member_id = request.POST.get('member_id', '').strip()
                if member_id:
                    member = CRMAgencyMember.objects.get(pk=int(member_id), agency=m.agency, is_active=True)
                period_start, period_end = parse_goal_period_strings(
                    request.POST.get('period_start', ''),
                    request.POST.get('period_end', ''),
                )
                CRMAgencyTeamGoal.objects.create(
                    agency=m.agency,
                    member=member,
                    metric=request.POST.get('metric', 'calls'),
                    target_value=int(request.POST.get('target_value', 0) or 0),
                    period_start=period_start,
                    period_end=period_end,
                )
                messages.success(request, 'هدف تیم ثبت شد.')
            elif action == 'regenerate_api_key':
                regenerate_api_key(request.user)
                messages.success(request, 'کلید API بازتولید شد.')
        except ValueError as exc:
            messages.error(request, str(exc))
        from workspace.services.agency_team_routes import redirect_after_team_action
        return redirect_after_team_action(tab)


class CRMTeamAssignView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not is_customer_owner(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند به اشتراک بگذارد'}, status=403)
        from workspace.services.agency_entitlement import can_share_team_resources
        if not can_share_team_resources(request.user):
            return JsonResponse(
                {'ok': False, 'error': 'اشتراک با هم‌تیمی فقط برای اعضای آژانس با لایسنس فعال است'},
                status=403,
            )
        try:
            assign_customer(
                request.user,
                customer,
                int(request.POST.get('member_id', 0)),
                share_mode=request.POST.get('share_mode', 'confidential'),
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMTeamTransferView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not is_customer_owner(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند پرونده را منتقل کند'}, status=403)
        try:
            transfer_customer(
                request.user, customer,
                int(request.POST.get('member_id', 0)),
                note=request.POST.get('note', ''),
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMPropertyShareView(LoginRequiredMixin, View):
    def post(self, request, property_id):
        prop = property_for_user(request.user, property_id)
        if not prop or prop.deleted_at:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد'}, status=404)
        if not is_property_owner(request.user, prop):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند به اشتراک بگذارد'}, status=403)
        from workspace.services.agency_entitlement import can_share_team_resources
        if not can_share_team_resources(request.user):
            return JsonResponse(
                {'ok': False, 'error': 'اشتراک با هم‌تیمی فقط برای اعضای آژانس با لایسنس فعال است'},
                status=403,
            )
        try:
            share_property(
                request.user,
                prop,
                int(request.POST.get('member_id', 0)),
                share_mode=request.POST.get('share_mode', 'confidential'),
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMShareRevokeView(LoginRequiredMixin, View):
    def post(self, request, share_id):
        try:
            revoke_share(request.user, share_id)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMDealCommissionSplitView(CRMDealsAccessMixin, LoginRequiredMixin, View):
    def post(self, request, deal_id):
        deal = deal_for_user(request.user, deal_id)
        if not deal:
            return JsonResponse({'ok': False, 'error': 'معامله یافت نشد'}, status=404)
        try:
            payload = json.loads(request.body.decode('utf-8'))
            splits = payload.get('splits') or []
            set_commission_splits(request.user, deal, splits)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True})


class CRMSyncExportView(ExportSecurityMixin, LoginRequiredMixin, View):
    def get(self, request):
        from django.http import JsonResponse as JR
        if not can_manage_team(request.user):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست'}, status=403)
        agency_scope = request.GET.get('scope') == 'agency'
        payload = export_crm_payload(request.user, agency_scope=agency_scope)
        record_sync_log(request.user, 'export', {
            'contacts': len(payload.get('contacts') or []),
            'properties': len(payload.get('properties') or []),
            'deals': len(payload.get('deals') or []),
        })
        return JR(payload, json_dumps_params={'ensure_ascii': False})


class CRMSyncImportView(LoginRequiredMixin, View):
    def post(self, request):
        if not can_manage_team(request.user):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست'}, status=403)
        dry_run = request.GET.get('dry_run') == '1'
        try:
            payload = json.loads(request.body.decode('utf-8'))
            stats = import_crm_payload(request.user, payload, dry_run=dry_run)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'فایل نامعتبر'}, status=400)
        sync_type = 'dry_run' if dry_run else 'import'
        record_sync_log(request.user, sync_type, stats)
        return JsonResponse({'ok': True, 'stats': stats, 'dry_run': dry_run})


@method_decorator(csrf_exempt, name='dispatch')
class CRMInboundLeadAPIView(View):
    """ورود سرنخ از API — C8."""

    def post(self, request):
        client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        if not client_ip:
            client_ip = request.META.get('REMOTE_ADDR', '')
        if _crm_lead_api_rate_limit_exceeded(client_ip):
            return JsonResponse({'ok': False, 'error': 'Too many requests'}, status=429)

        api_key = request.headers.get('X-CRM-API-Key', '')
        agency = CRMAgency.objects.filter(api_key=api_key).select_related('owner').first()
        if not agency or not verify_api_key(agency, api_key):
            logger.warning('CRM lead API unauthorized attempt from %s', client_ip or 'unknown')
            return JsonResponse({'ok': False, 'error': 'Unauthorized'}, status=401)
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'Bad JSON'}, status=400)
        try:
            customer = create_lead_from_api(
                agency,
                owner_user=agency.owner,
                name=payload.get('name', ''),
                phone=payload.get('phone', ''),
                source=payload.get('source', 'API'),
                notes=payload.get('notes', ''),
            )
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'id': customer.pk, 'name': customer.name})


class CRMSavedFilterDeleteView(LoginRequiredMixin, View):
    def post(self, request, filter_id):
        if not delete_filter(request.user, filter_id):
            return JsonResponse({'ok': False, 'error': 'فیلتر یافت نشد'}, status=404)
        return JsonResponse({'ok': True})


class CRMSavedFilterPinView(LoginRequiredMixin, View):
    def post(self, request, filter_id):
        try:
            obj = toggle_pin(request.user, filter_id)
        except CRMSavedFilter.DoesNotExist:
            return JsonResponse({'ok': False, 'error': 'فیلتر یافت نشد'}, status=404)
        return JsonResponse({'ok': True, 'filter': serialize_filter(obj)})

