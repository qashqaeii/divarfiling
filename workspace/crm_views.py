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
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from workspace.constants import (
    AGENCY_ROLES, CRM_PRIORITIES, CRM_PROPERTIES, CRM_SOURCES, CRM_STATUSES, CRM_TYPES,
    DEAL_STAGES, DEFAULT_STAGNANT_DAYS, LEAD_ROUTING_CHOICES, LOST_REASONS, MESSAGE_PLACEHOLDERS,
    MESSAGE_TEMPLATE_CATEGORIES, PROPERTY_ADVERTISER_TYPES, PROPERTY_DEAL_MODES, PROPERTY_PUBLISH_STATUSES,
    PROPERTY_TX_STATUSES, QUICK_ACTIVITY_TYPES, TYPE_PROFILES, VISIT_OUTCOMES, WEBHOOK_EVENTS,
    WEBHOOK_EVENT_LABELS,
)
from workspace.services.property_images import (
    MAX_PROPERTY_IMAGES, parse_images_payload, store_property_image,
)
from workspace.forms import (
    ActivityForm, CRMAutomationRuleForm, CRMDealForm, CRMMessageTemplateForm,
    CRMPropertyForm, CRMPropertyImportForm, CRMReminderForm, ConvertLeadForm,
    CustomerDocumentForm, CustomerForm, CustomerImportForm, FollowUpForm,
    PropertyLinkForm, PropertyVisitForm, QuickLeadForm,
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
    create_agency, get_team_inbox, invite_member_by_phone,
    member_display, regenerate_api_key, remove_member, request_join_agency,
    respond_membership_request, role_label, set_commission_splits, sync_agency_member_records,
    transfer_customer, update_agency_settings, update_member_role,
)
from workspace.services.crm_agency_analytics import (
    get_command_center_stats, get_member_performance_row, get_team_goals_progress,
    get_team_performance,
)
from workspace.services.crm_scope import (
    agency_members, can_edit_customer, can_edit_property, can_manage_team,
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
    apply_property_suggestions, build_customer_whatsapp_text, build_dashboard_charts,
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
    apply_deal_commission, create_deal, filter_deals, get_deal_pipeline,
    get_deal_stats, update_deal_stage,
)
from workspace.services.crm_deal_stages import (
    get_user_deal_stages, is_valid_deal_stage, save_user_deal_stages,
)
from workspace.services.crm_deal_checklist import (
    checklist_progress, ensure_deal_checklist, toggle_checklist_item,
)
from workspace.services.crm_matching import MATCH_TYPES, get_customer_matches
from workspace.constants import LEAD_TYPES
from workspace.services.crm_match_notifications import is_match_eligible
from workspace.services.crm_import import (
    import_contacts_from_file, import_column_specs, import_template_excel_response, import_template_headers,
)
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
    return {
        'contacts': customers_qs(user).count(),
        'properties': properties_qs(user).count(),
        'reminders': reminders_qs(user).filter(is_done=False).count(),
        'today': count_today_queue(user),
        'deals': deals_qs(user).exclude(
            stage__in=['بسته‌شده', 'از دست رفته'],
        ).count(),
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
        ctx['can_share_resources'] = bool(get_membership(user))
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
        return ctx

    def post(self, request):
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

    def get_queryset(self):
        return filter_contacts(self.request.user, self.request.GET)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        cqs = customers_qs(user)
        ctx['stats'] = {
            'total': cqs.count(),
            'new': cqs.filter(status='جدید').count(),
            'in_progress': cqs.filter(status='در حال پیگیری').count(),
            'due_today': cqs.filter(next_follow_up=today).count(),
        }
        ctx['customer_form'] = ctx.get('customer_form', CustomerForm())
        ctx['open_modal'] = self.request.GET.get('open', ctx.get('open_modal', ''))
        ctx['crm_types'] = CRM_TYPES
        ctx['crm_statuses'] = CRM_STATUSES
        ctx['crm_priorities'] = CRM_PRIORITIES
        ctx['crm_sources'] = CRM_SOURCES
        ctx['type_profiles_json'] = json.dumps(TYPE_PROFILES, ensure_ascii=False)
        ctx['crm_section'] = 'contacts'
        ctx['filter_qs'] = urlencode({
            k: v for k, v in self.request.GET.items()
            if k not in ('view', 'page', 'open') and v
        })
        ctx['view_mode'] = self.request.GET.get('view', 'table')
        ctx['pipeline'] = get_pipeline_data(self.request.user, per_column=50)
        ctx['pipeline_interactive'] = True
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
        ctx['bulk_statuses'] = CRM_STATUSES
        ctx['saved_filters'] = list_saved_filters(user, 'contacts')
        ctx['saved_filter_scope'] = 'contacts'
        ctx['saved_filter_base'] = reverse('workspace:crm_contacts')
        ctx['saved_filter_params'] = current_params_from_request(self.request, 'contacts')
        ctx['saved_filter_can_save'] = bool(ctx['saved_filter_params'])
        ctx['match_eligible_types'] = MATCH_TYPES | LEAD_TYPES
        ctx['today'] = today
        ctx.update(_contact_areas_context(user))
        return ctx


class CustomerQuickCreateView(LoginRequiredMixin, View):
    """ثبت سریع سرنخ."""

    def post(self, request):
        form = QuickLeadForm(request.POST)
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
            update_customer_status(customer, new_status)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({
            'ok': True,
            'status': new_status,
            'customer_id': customer.pk,
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
        match_count = len(matches.get('crm_matches', [])) + len(matches.get('divar_matches', []))

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

        from workspace.templatetags.crm_tags import crm_avatar_hue, crm_initials, crm_status_dot

        return JsonResponse({
            'id': customer.pk,
            'name': customer.name,
            'company_name': customer.company_name or '',
            'initials': crm_initials(customer.name),
            'avatar_hue': crm_avatar_hue(customer.name),
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
            listing = listings_by_token.get(cl.token)
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
        ctx['whatsapp_text'] = build_customer_whatsapp_text(c)
        from workspace.services.contact_channels import contact_channels_for_display
        ctx['contact_messaging_channels'] = contact_channels_for_display(
            c, message=ctx['whatsapp_text'],
        )
        ctx['crm_section'] = 'contacts'
        divar_enabled = has_active_bot_license(self.request.user)
        match_data = get_customer_matches(c, self.request.user, divar_enabled=divar_enabled)
        from workspace.services.property_suggestion_share import enrich_match_data_links
        ctx['match_data'] = enrich_match_data_links(self.request.user, self.request, match_data)
        ctx['match_data_json'] = json.dumps(ctx['match_data'], ensure_ascii=False)
        ctx['suggestion_text'] = self.request.session.pop('crm_last_suggestion_text', '')
        ctx['active_tab'] = self.request.GET.get('tab', '')
        ctx['suggested'] = self.request.GET.get('suggested', '')
        ctx['deals'] = c.deals.select_related('property').all()[:10]
        ctx['visits'] = c.visits.select_related('property').all()[:20]
        ctx['visit_form'] = PropertyVisitForm(user=self.request.user)
        ctx['deal_form'] = CRMDealForm(user=self.request.user, initial={'customer': c})
        ctx['duplicate_candidates'] = find_duplicates_for_customer_strict(c)
        ctx['visit_outcomes'] = VISIT_OUTCOMES
        ctx['message_templates'] = list_templates(self.request.user)
        ctx['is_customer_owner'] = is_customer_owner(self.request.user, c)
        ctx['customer_shares'] = list_shares_for_customer(c) if ctx['is_customer_owner'] else []
        ctx['customer_is_shared'] = not ctx['is_customer_owner'] and c.user_id != self.request.user.id
        ctx['customer_share'] = (
            share_for_customer_recipient(self.request.user, c) if ctx['customer_is_shared'] else None
        )
        ctx['crm_statuses'] = CRM_STATUSES
        ctx.update(_contact_areas_context(self.request.user))
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
            form = CRMDealForm(request.POST, user=request.user)
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


class CustomerExportView(LoginRequiredMixin, View):
    def get(self, request):
        return export_customers_excel_response(request.user, request.GET)


class CRMReminderListView(CRMContextMixin, LoginRequiredMixin, ListView):
    model = Reminder
    template_name = 'workspace/crm/reminders/list.html'
    context_object_name = 'reminders'
    paginate_by = 20

    def get_queryset(self):
        show = self.request.GET.get('show', 'active')
        qs = reminders_qs(self.request.user).select_related('customer')
        if show == 'done':
            return qs.filter(is_done=True).order_by('-due_at')
        if show == 'all':
            return qs.order_by('due_at')
        return qs.filter(is_done=False).order_by('due_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        qs = reminders_qs(user)
        now = timezone.now()
        ctx['show'] = self.request.GET.get('show', 'active')
        ctx['stats'] = {
            'active': qs.filter(is_done=False).count(),
            'done': qs.filter(is_done=True).count(),
            'overdue': qs.filter(is_done=False, due_at__lt=now).count(),
            'today': qs.filter(is_done=False, due_at__date=timezone.localdate()).count(),
        }
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
        if not reminder:
            messages.error(request, 'یادآور یافت نشد.')
            nxt = request.POST.get('next')
            return redirect(nxt if nxt else reverse('workspace:crm_reminders'))
        was_done = reminder.is_done
        reminder.is_done = not reminder.is_done
        reminder.save(update_fields=['is_done'])
        if not was_done and reminder.is_done and reminder.recurrence:
            advance_recurring_reminder(reminder)
        messages.success(request, 'وضعیت یادآور به‌روز شد.')
        nxt = request.POST.get('next')
        return redirect(nxt if nxt else reverse('workspace:crm_reminders'))


class CRMPropertyExportView(LoginRequiredMixin, View):
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

    def get_queryset(self):
        return filter_properties(self.request.user, self.request.GET).annotate(
            contact_count=Count('contact_links', distinct=True),
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        props = properties_qs(user)
        filtered = filter_properties(user, self.request.GET)
        ctx['stats'] = {
            'total': props.count(),
            'sale': props.filter(deal_mode='فروش').count(),
            'rent': props.filter(deal_mode__in=['رهن و اجاره', 'اجاره']).count(),
            'active': props.filter(transaction_status='فعال').count(),
            'published': props.filter(publish_status='منتشرشده').count(),
        }
        ctx['filtered_count'] = filtered.count()
        ctx['property_form'] = ctx.get('property_form', CRMPropertyForm())
        ctx['open_drawer'] = self.request.GET.get('drawer', '')
        ctx['deal_modes'] = PROPERTY_DEAL_MODES
        ctx['tx_statuses'] = PROPERTY_TX_STATUSES
        ctx['property_types'] = CRM_PROPERTIES
        ctx['publish_statuses'] = PROPERTY_PUBLISH_STATUSES
        ctx['crm_section'] = 'properties'
        ctx['view_mode'] = self.request.GET.get('view', 'grid')
        ctx['sort'] = self.request.GET.get('sort', '-updated_at')
        ctx['filter_qs'] = urlencode({
            k: v for k, v in self.request.GET.items()
            if k not in ('view', 'page', 'drawer') and v
        })
        ctx['has_filters'] = any(self.request.GET.get(k) for k in (
            'q', 'deal_mode', 'transaction_status', 'property_type', 'publish_status', 'city', 'sort',
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
        from workspace.services.property_public_share import build_property_amenity_dossier_items
        for prop in ctx.get('properties') or []:
            prop.card_amenities = build_property_amenity_dossier_items(prop)
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
        return JsonResponse({
            'ok': True,
            'transaction_status': new_status,
            'property_id': prop.pk,
        })


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
        return redirect(f"{reverse('workspace:crm_properties')}?drawer=property")

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
        source_listing = resolve_listing_for_property(self.request.user, p)
        ctx['source_listing'] = source_listing
        if source_listing:
            feat = extract_listing_features(source_listing)
            ctx['feature_profile'] = build_listing_feature_profile(source_listing, feat)
            ctx['listing_highlights'] = feat.get('highlights') or []
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
        if ctx.get('is_property_owner') and not ctx.get('property_is_deleted'):
            from workspace.services.property_public_share import (
                get_or_create_property_share,
                property_public_share_url,
            )
            pub_share = get_or_create_property_share(self.request.user, p)
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
            lead_form = QuickLeadForm(request.POST)
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
                from workspace.services.crm import log_activity
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
        self.object = form.save()
        raw_images = self.request.POST.get('property_images_json')
        if raw_images is not None:
            images = parse_images_payload(raw_images)
            if images != (self.object.images or []):
                self.object.images = images
                self.object.save(update_fields=['images', 'updated_at'])
        if 'phone' in form.changed_data or 'owner_name' in form.changed_data:
            upsert_property_owner(
                self.request.user,
                phone=self.object.phone,
                name=self.object.owner_name,
                crm_property=self.object,
                source='سایر',
            )
        if (
            'tenant_phone' in form.changed_data
            or 'tenant_name' in form.changed_data
            or 'is_vacant' in form.changed_data
            or 'deal_mode' in form.changed_data
        ):
            upsert_property_tenant(
                self.request.user,
                phone=self.object.tenant_phone,
                name=self.object.tenant_name,
                crm_property=self.object,
                source='سایر',
            )
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

        prop.latitude = lat
        prop.longitude = lng
        update_fields = ['latitude', 'longitude', 'updated_at']
        if prop.nearby_pois:
            prop.nearby_pois = {}
            update_fields.append('nearby_pois')
        prop.save(update_fields=update_fields)
        return JsonResponse({
            'ok': True,
            'latitude': lat,
            'longitude': lng,
            'map_navigation': build_map_navigation(lat, lng),
        })


class CRMPropertyNearbyPoisView(LoginRequiredMixin, View):
    """دریافت و ذخیره امکانات اطراف فایل شخصی — on-demand."""

    def post(self, request, property_id):
        from workspace.services.nearby_pois import NearbyPoiError, fetch_and_save_nearby_pois

        prop = property_for_user(request.user, property_id)
        if not prop:
            return JsonResponse({'ok': False, 'error': 'ملک یافت نشد.'}, status=404)

        share_ctx = build_property_share_context(request.user, prop)
        if share_ctx.mask_sensitive:
            return JsonResponse({'ok': False, 'error': 'دسترسی ندارید.'}, status=403)

        force_refresh = False
        if request.META.get('CONTENT_TYPE', '').startswith('application/json'):
            try:
                payload = json.loads(request.body.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
            force_refresh = bool(payload.get('refresh'))

        try:
            data = fetch_and_save_nearby_pois(prop, request.user, force_refresh=force_refresh)
        except NearbyPoiError as exc:
            return JsonResponse({
                'ok': False,
                'code': exc.code,
                'error': exc.message,
            }, status=exc.status)
        return JsonResponse(data)


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

class CRMDealListView(CRMContextMixin, LoginRequiredMixin, ListView):
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
        ctx['deal_stages_json'] = json.dumps(ctx['deal_stages'], ensure_ascii=False)
        ctx['view_mode'] = self.request.GET.get('view', 'table')
        ctx['pipeline'] = get_deal_pipeline(self.request.user, per_column=30)
        ctx['pipeline_interactive'] = True
        ctx['deal_form'] = ctx.get('deal_form', CRMDealForm(user=self.request.user))
        ctx['deal_stage_url_template'] = reverse(
            'workspace:crm_deal_stage', kwargs={'deal_id': 0},
        ).replace('/0/', '/{id}/')
        ctx['crm_section'] = 'deals'
        ctx['filter_qs'] = self.request.GET.urlencode()
        ctx['today'] = timezone.localdate()
        ctx['saved_filters'] = list_saved_filters(self.request.user, 'deals')
        ctx['saved_filter_scope'] = 'deals'
        ctx['saved_filter_base'] = reverse('workspace:crm_deals')
        ctx['saved_filter_params'] = current_params_from_request(self.request, 'deals')
        ctx['saved_filter_can_save'] = bool(ctx['saved_filter_params'])
        return ctx


class CRMDealCreateView(LoginRequiredMixin, View):
    def post(self, request):
        form = CRMDealForm(request.POST, user=request.user)
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


class CRMDealDetailView(CRMContextMixin, LoginRequiredMixin, DetailView):
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


class CRMDealUpdateView(LoginRequiredMixin, UpdateView):
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


class CRMDealStageUpdateView(LoginRequiredMixin, View):
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


class CRMDealStagesView(LoginRequiredMixin, View):
    """مدیریت مراحل سفارشی pipeline — B2."""

    def get(self, request):
        stages = get_user_deal_stages(request.user)
        return JsonResponse({'ok': True, 'stages': stages})

    def post(self, request):
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'ok': False, 'error': 'درخواست نامعتبر'}, status=400)
        try:
            stages = save_user_deal_stages(request.user, payload.get('stages') or [])
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
        return JsonResponse({'ok': True, 'stages': stages})


class CRMDealChecklistView(LoginRequiredMixin, View):
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


class CustomerBulkActionView(LoginRequiredMixin, View):
    def post(self, request):
        ids = request.POST.getlist('ids') or request.POST.get('ids', '').split(',')
        ids = [i.strip() for i in ids if str(i).strip().isdigit()]
        action = request.POST.get('bulk_action', '')
        nxt = request.POST.get('next') or reverse('workspace:crm_contacts')

        if not ids:
            messages.warning(request, 'مخاطبی انتخاب نشده است.')
            return redirect(nxt)

        qs = customers_qs(request.user).filter(pk__in=ids)
        count = qs.count()

        if action == 'delete':
            qs.delete()
            messages.success(request, f'{count} مخاطب حذف شد.')
        elif action == 'status' and request.POST.get('status') in CRM_STATUSES:
            new_status = request.POST['status']
            for c in qs:
                update_customer_status(c, new_status)
            messages.success(request, f'وضعیت {count} مخاطب به «{new_status}» تغییر کرد.')
        elif action == 'archive':
            for c in qs:
                update_customer_status(c, 'بایگانی')
            messages.success(request, f'{count} مخاطب بایگانی شد.')
        elif action == 'tag':
            tag = request.POST.get('tag', '').strip()
            if tag:
                for c in qs:
                    tags = set(t.strip() for t in (c.tags or '').split(',') if t.strip())
                    tags.add(tag)
                    c.tags = ', '.join(sorted(tags))
                    c.save(update_fields=['tags', 'updated_at'])
                messages.success(request, f'برچسب به {count} مخاطب اضافه شد.')
        else:
            messages.error(request, 'عملیات نامعتبر است.')
        return redirect(nxt)


class CustomerImportTemplateView(LoginRequiredMixin, View):
    def get(self, request):
        return import_template_excel_response()


class CustomerImportView(LoginRequiredMixin, View):
    def post(self, request):
        form = CustomerImportForm(request.POST, request.FILES)
        nxt = request.POST.get('next') or reverse('workspace:crm_contacts')
        if form.is_valid():
            created, skipped, errors = import_contacts_from_file(request.user, form.cleaned_data['file'])
            if errors:
                for err in errors[:3]:
                    messages.error(request, err)
            if created:
                messages.success(request, f'{created} مخاطب import شد ({skipped} رد شد).')
            elif not errors:
                messages.info(request, f'مخاطب جدیدی یافت نشد ({skipped} رد شد).')
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

        ctx = super().get_context_data(**kwargs)
        today_j = jdatetime.date.today()
        try:
            jyear = int(self.request.GET.get('jy', self.request.GET.get('year', today_j.year)))
            jmonth = int(self.request.GET.get('jm', self.request.GET.get('month', today_j.month)))
        except (TypeError, ValueError):
            jyear, jmonth = today_j.year, today_j.month
        ctx['calendar'] = get_calendar_month(self.request.user, jyear, jmonth)
        ctx['crm_section'] = 'calendar'
        return ctx


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
    """هدایت مسیرهای اشتباه مثل /crm/team/undefined به صفحه اصلی تیم."""

    def get(self, request, bad_path=''):
        return redirect(f"{reverse('workspace:crm_team')}?tab=sync")

    def post(self, request, bad_path=''):
        return redirect(f"{reverse('workspace:crm_team')}?tab=sync")


class CRMTeamApiKeyRegenerateView(LoginRequiredMixin, View):
    def post(self, request):
        try:
            key = regenerate_api_key(request.user)
        except ValueError as exc:
            return JsonResponse({'ok': False, 'error': str(exc)}, status=403)
        return JsonResponse({'ok': True, 'key': key})


class CRMTeamReportCSVView(LoginRequiredMixin, View):
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
    """داشبورد تمام‌صفحه TV — فقط خواندنی."""
    template_name = 'workspace/crm/team/tv.html'

    def dispatch(self, request, *args, **kwargs):
        membership = get_membership(request.user)
        agency = membership.agency if membership else None
        if not agency:
            messages.error(request, 'ابتدا به یک آژانس بپیوندید.')
            return redirect('workspace:crm_team')
        if not is_agency_feature_enabled('tv_mode', agency):
            messages.error(request, 'حالت TV برای این آژانس فعال نیست.')
            return redirect('workspace:crm_team')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['crm_section'] = 'team-tv'
        ctx['tv_payload'] = get_tv_dashboard_payload(self.request.user, use_cache=False)
        optional = ('chart', 'goals', 'activity', 'schedule', 'announcements', 'alerts')
        ctx['tv_widgets'] = [w for w in ctx['tv_payload'].get('allowed_widgets', []) if w in optional]
        ctx['api_crm_team_tv_url'] = reverse('workspace:api_crm_team_tv')
        ctx['crm_team_url'] = reverse('workspace:crm_team')
        return ctx


class CRMTeamView(CRMContextMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/team/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['crm_section'] = 'team'
        ctx['crm_team_url'] = reverse('workspace:crm_team')
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
        ctx['crm_team_tv_url'] = reverse('workspace:crm_team_tv')
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
            ctx['member_rows'] = [
                {
                    'member': m,
                    'perf': (
                        perf_by_member.get(m.pk) or perf_by_user.get(m.user_id) or {}
                    ) if can_view_perf or m.user_id == user.id else {},
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
            tab = 'command' if (agency and can_manage_team(user)) else 'overview'
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
        if agency and can_manage_team(user):
            from licenses.services.management import build_license_dashboard
            ctx['license_dashboard'] = build_license_dashboard(user)
        else:
            ctx['license_dashboard'] = None
        return ctx

    def post(self, request):
        action = request.POST.get('action', '')
        tab = request.POST.get('tab') or request.GET.get('tab', 'overview')
        try:
            if action == 'create_agency':
                create_agency(request.user, request.POST.get('name', ''))
                messages.success(request, 'آژانس ایجاد شد و داده‌های شما متصل شد.')
            elif action == 'invite_member':
                invite_member_by_phone(
                    request.user,
                    request.POST.get('phone', ''),
                    request.POST.get('role', 'advisor'),
                )
                messages.success(request, 'دعوت ارسال شد — منتظر تأیید کاربر باشید.')
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
        return redirect(f"{reverse('workspace:crm_team')}?tab={tab}")


class CRMTeamAssignView(LoginRequiredMixin, View):
    def post(self, request, customer_id):
        customer = customer_for_user(request.user, customer_id)
        if not customer:
            return JsonResponse({'ok': False, 'error': 'مخاطب یافت نشد'}, status=404)
        if not is_customer_owner(request.user, customer):
            return JsonResponse({'ok': False, 'error': 'فقط مالک می‌تواند به اشتراک بگذارد'}, status=403)
        try:
            assign_customer(request.user, customer, int(request.POST.get('member_id', 0)))
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


class CRMDealCommissionSplitView(LoginRequiredMixin, View):
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


class CRMSyncExportView(LoginRequiredMixin, View):
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

