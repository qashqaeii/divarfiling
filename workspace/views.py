"""ویوهای workspace."""
import json
import os
import tempfile
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, TemplateView, UpdateView

from workspace.services.filing_video import get_filing_video_context
from workspace.constants import SUPPORTED_UPLOAD_EXTENSIONS, TABLE_COLUMNS_DEFAULT
from workspace.forms import (
    CompareForm, DatasetRenameForm, DatasetUploadForm,
    ListingEditForm, ListingMetaForm, ReminderForm, WorkspaceSettingsForm,
)
from workspace.services.columns import consultant_q
from workspace.services.price_history import dedupe_price_history
from workspace.services.property_images import deduplicate_divar_image_urls, normalize_external_image_url
from workspace.mixins import DatasetOwnerMixin, LicenseRequiredMixin, WorkspaceLoginMixin, get_or_create_settings
from workspace.services.access import BOT_LOCKED_FEATURES, get_bot_product_buy_url, has_active_bot_license
from workspace.constants import DEAL_TYPES, LISTING_ROLES
from workspace.models import (
    CRMProperty, Customer, Dataset, Listing, ListingMeta, ListingPublicShare,
    PriceHistory, Reminder, WorkspaceSettings,
)
from workspace.services.listing_public_share import (
    get_or_create_listing_share, public_share_url,
)
from workspace.services.crm_scope import can_edit_customer, customer_for_user, customers_qs
from workspace.services.crm import (
    add_listing_to_personal_files, build_customer_whatsapp_text, build_dashboard_charts,
    customers_linked_to_token, get_communication_stats, get_crm_property_by_token,
    get_dashboard_stats, get_overdue_contacts, get_pipeline_data, get_recent_contacts,
    get_recent_properties, get_upcoming_reminders, guess_deal_type_from_listing,
    link_listing_to_customer, primary_owner_contact, upsert_property_owner,
)
from workspace.services.analyzer import (
    benchmark_listing, build_analysis_dashboard, compute_outliers_report, compute_statistics,
    filter_outliers, generate_consultant_guide, listings_to_dataframe,
)
from workspace.services.analyze_ui import build_l2_ui, build_l3_ui
from workspace.services.market_agent import resolve_report_confidence
from workspace.services.charts import build_all_charts, map_markers
from workspace.services.compare import compare_datasets
from workspace.services.export import export_csv_response, export_json_response
from workspace.services.folder_import import (
    build_dataset_name, group_import_results, is_importable_file, parse_output_relative_path,
)
from workspace.services.importer import import_dataset, import_message
from workspace.services.display import (
    build_listing_display_data, format_field_rows, format_sections,
    format_supplementary_fields, format_supplementary_groups, location_accuracy_for_map,
    transaction_profile,
)
from workspace.services.features import extract_listing_features
from workspace.services.listing_features import (
    build_listing_amenity_dossier_items,
    build_listing_feature_profile,
)
from workspace.services.listing_map import build_listing_map_marker
from workspace.services.listing_edit import (
    apply_listing_edit_post, listing_edit_payload,
    owner_name_from_listing, owner_phone_from_listing,
)
from workspace.services.filters import (
    active_filter_count, advanced_filter_count, apply_advertiser_signal_filter,
    apply_amenity_filters, apply_listing_filters, apply_value_filter,
    get_neighborhoods, needs_advertiser_signal_filter,
    get_neighborhoods_qs, parse_filter_params, sort_queryset,
)
from workspace.services.formatting import format_toman
from workspace.services.valuation import (
    analyze_market, compute_expected_values, enrich_dataframe, value_verdict,
)
from workspace.constants import CRM_STATUSES


# ─── Home ───────────────────────────────────────────────────────────────────

class WorkspaceHomeView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        today = timezone.now().date()
        datasets_qs = Dataset.objects.filter(user=user, is_active=True)

        ctx['data_stats'] = {
            'datasets': datasets_qs.count(),
            'listings': Listing.objects.filter(dataset__user=user, dataset__is_active=True).count(),
            'sale': datasets_qs.filter(transaction_type__icontains='فروش').count(),
            'rent': datasets_qs.filter(transaction_type__icontains='اجاره').count(),
        }
        ctx['crm_stats'] = get_dashboard_stats(user)
        ctx['charts_json'] = json.dumps(build_dashboard_charts(user), ensure_ascii=False)
        ctx['active_dataset'] = datasets_qs.order_by('-last_opened_at', '-created_at').first()
        ctx['recent_datasets'] = (
            datasets_qs.annotate(listing_count=Count('listings'))
            .order_by('-last_opened_at', '-created_at')[:8]
        )
        pipeline = get_pipeline_data(user, per_column=3)
        ctx['pipeline'] = pipeline
        ctx['pipeline_max'] = max((col['count'] for col in pipeline), default=1) or 1
        ctx['recent_properties'] = get_recent_properties(user, 4)
        ctx['upcoming_reminders'] = get_upcoming_reminders(user, 6)
        ctx['recent_contacts'] = get_recent_contacts(user, 5)
        ctx['due_contacts'] = customers_qs(user).filter(
            next_follow_up=today,
            status__in=['جدید', 'در حال پیگیری'],
        ).order_by('next_follow_up')[:6]
        ctx['overdue_contacts'] = get_overdue_contacts(user, 8)
        ctx['communication_stats'] = get_communication_stats(user)
        ctx['crm_statuses'] = CRM_STATUSES
        ctx['settings'] = get_or_create_settings(user)
        ctx['has_bot_license'] = has_active_bot_license(user)
        ctx['open_modal'] = self.request.GET.get('open', '')
        return ctx


# ─── Datasets ───────────────────────────────────────────────────────────────

def _dataset_base_qs(user):
    return Dataset.objects.filter(user=user, is_active=True).annotate(
        listing_count=Count('listings'),
    )


def _apply_dataset_filters(qs, request):
    q = request.GET.get('q', '').strip()
    tx = request.GET.get('tx', '').strip()
    city = request.GET.get('city', '').strip()
    fmt = request.GET.get('format', '').strip()

    if q:
        qs = qs.filter(
            Q(name__icontains=q) | Q(original_filename__icontains=q) |
            Q(city__icontains=q) | Q(district__icontains=q) |
            Q(subcategory__icontains=q) | Q(transaction_type__icontains=q),
        )
    if tx == 'sale':
        qs = qs.filter(transaction_type__icontains='فروش')
    elif tx == 'rent':
        qs = qs.filter(transaction_type__icontains='اجاره')
    elif tx == 'mixed':
        qs = qs.filter(transaction_type='ترکیبی')
    if city:
        qs = qs.filter(city=city)
    if fmt in ('xlsx', 'csv', 'json'):
        qs = qs.filter(file_format=fmt)
    return qs


def _soft_delete_datasets(qs) -> int:
    """حذف نرم فایل — آگهی‌های وابسته هم پاک می‌شوند تا آپلود مجدد درست کار کند."""
    dataset_ids = list(qs.values_list('pk', flat=True))
    if not dataset_ids:
        return 0
    with transaction.atomic():
        Listing.objects.filter(dataset_id__in=dataset_ids).delete()
        return qs.update(is_active=False)


def _dataset_filter_params(request):
    return {k: request.GET.get(k, '').strip() for k in ('q', 'tx', 'city', 'format', 'view')}


def _dataset_filter_qs(request):
    """Query string for filters only — view mode is set explicitly on toggle/pagination links."""
    params = {k: v for k, v in _dataset_filter_params(request).items() if v and k != 'view'}
    return urlencode(params) if params else ''


def _dataset_page_query(request):
    filters = _dataset_filter_params(request)
    params = {k: v for k, v in filters.items() if v and k != 'view'}
    view = filters.get('view') or 'auto'
    if view not in ('table', 'auto'):
        params['view'] = view
    return params


def _dataset_stats(user):
    base = _dataset_base_qs(user)
    agg = base.aggregate(files=Count('id'), listings=Sum('listing_count'))
    return {
        'files': agg['files'] or 0,
        'listings': agg['listings'] or 0,
        'sale': base.filter(transaction_type__icontains='فروش').count(),
        'rent': base.filter(transaction_type__icontains='اجاره').count(),
    }


def _attach_dataset_covers(datasets):
    """اولین تصویر موجود هر دیتاست را برای کارت کاور ست می‌کند."""
    items = list(datasets)
    ids = [ds.pk for ds in items]
    for ds in items:
        ds.cover_image = ''
    if not ids:
        return items

    covers = {}
    rows = (
        Listing.objects.filter(dataset_id__in=ids)
        .exclude(images=[])
        .order_by('dataset_id', 'id')
        .values_list('dataset_id', 'images')
    )
    for dataset_id, images in rows:
        if dataset_id in covers:
            continue
        if not images:
            continue
        urls = deduplicate_divar_image_urls(
            [normalize_external_image_url(u) for u in images if u],
        )
        if urls:
            covers[dataset_id] = urls[0]

    for ds in items:
        ds.cover_image = covers.get(ds.pk, '')
    return items


def _dataset_list_context(request, extra=None):
    qs = _apply_dataset_filters(
        _dataset_base_qs(request.user),
        request,
    ).order_by('-last_opened_at', '-created_at')
    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    _attach_dataset_covers(page_obj.object_list)
    filters = _dataset_filter_params(request)
    upload_batch = request.session.pop('upload_batch', None)
    ctx = {
        'datasets': page_obj,
        'page_obj': page_obj,
        'open_modal': request.GET.get('open', ''),
        'upload_batch': upload_batch,
        'stats': _dataset_stats(request.user),
        'cities': _dataset_base_qs(request.user).exclude(city='').values_list(
            'city', flat=True,
        ).distinct().order_by('city'),
        'filters': filters,
        'filter_qs': _dataset_filter_qs(request),
        'has_filters': any(filters.get(k) for k in ('q', 'tx', 'city', 'format')),
        'view_mode': filters.get('view') or 'auto',
        'page_query': _dataset_page_query(request),
        'filing_video': get_filing_video_context(),
    }
    if extra:
        ctx.update(extra)
    return ctx


class DatasetListView(LicenseRequiredMixin, ListView):
    model = Dataset
    template_name = 'workspace/datasets/list.html'
    context_object_name = 'datasets'
    paginate_by = 25

    def get_queryset(self):
        return _apply_dataset_filters(
            _dataset_base_qs(self.request.user),
            self.request,
        ).order_by('-last_opened_at', '-created_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filters = _dataset_filter_params(self.request)
        upload_batch = self.request.session.pop('upload_batch', None)
        page_obj = ctx.get('page_obj')
        if page_obj is not None:
            _attach_dataset_covers(page_obj.object_list)
        ctx.update({
            'open_modal': self.request.GET.get('open', ctx.get('open_modal', '')),
            'upload_batch': upload_batch,
            'stats': _dataset_stats(self.request.user),
            'cities': _dataset_base_qs(self.request.user).exclude(city='').values_list(
                'city', flat=True,
            ).distinct().order_by('city'),
            'filters': filters,
            'filter_qs': _dataset_filter_qs(self.request),
            'has_filters': any(filters.get(k) for k in ('q', 'tx', 'city', 'format')),
            'view_mode': filters.get('view') or 'auto',
            'page_query': _dataset_page_query(self.request),
            'filing_video': get_filing_video_context(),
        })
        return ctx


class DatasetUploadView(LicenseRequiredMixin, View):
    def get(self, request):
        return redirect(f"{reverse('workspace:dataset_list')}?open=modal-upload")

    def post(self, request):
        form = DatasetUploadForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, 'فایل معتبر انتخاب کنید.')
            ctx = _dataset_list_context(request, {
                'ws_upload_form': form,
                'open_modal': 'modal-upload',
            })
            return render(request, 'workspace/datasets/list.html', ctx)

        uploaded = form.cleaned_data['file']
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in SUPPORTED_UPLOAD_EXTENSIONS:
            messages.error(request, f'فرمت {ext} پشتیبانی نمی‌شود.')
            ctx = _dataset_list_context(request, {
                'ws_upload_form': form,
                'open_modal': 'modal-upload',
            })
            return render(request, 'workspace/datasets/list.html', ctx)

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            result = import_dataset(
                user=request.user,
                file_path=tmp_path,
                original_filename=uploaded.name,
                name=form.cleaned_data.get('name') or None,
            )
            level, msg = import_message(result)
            getattr(messages, level)(request, msg)
            return redirect('workspace:dataset_detail', dataset_id=result.dataset.pk)
        except Exception as e:
            messages.error(request, f'خطا در وارد کردن فایل: {e}')
            ctx = _dataset_list_context(request, {
                'ws_upload_form': form,
                'open_modal': 'modal-upload',
            })
            return render(request, 'workspace/datasets/list.html', ctx)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _upload_xhr(request) -> bool:
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def _upload_json_ok(request, redirect_url: str, **extra):
    if _upload_xhr(request):
        return JsonResponse({'ok': True, 'redirect': redirect_url, **extra})
    return None


def _upload_json_err(request, message: str, status: int = 400):
    if _upload_xhr(request):
        return JsonResponse({'ok': False, 'error': message}, status=status)
    return None


class DatasetBulkUploadView(LicenseRequiredMixin, View):
    """آپلود پوشه output — چند فایل با تفکیک استان/شهر/منطقه."""

    def get(self, request):
        return redirect(f"{reverse('workspace:dataset_list')}?open=modal-upload")

    def post(self, request):
        upload_url = f"{reverse('workspace:dataset_list')}?open=modal-upload"
        result_url = f"{reverse('workspace:dataset_list')}?open=modal-batch-result"

        try:
            return self._handle_bulk_upload(request, upload_url, result_url)
        except Exception as exc:
            if resp := _upload_json_err(request, f'خطای غیرمنتظره: {exc}', status=500):
                return resp
            messages.error(request, f'خطا در آپلود پوشه: {exc}')
            return redirect(upload_url)

    def _handle_bulk_upload(self, request, upload_url: str, result_url: str):
        files = request.FILES.getlist('files')
        if not files:
            if resp := _upload_json_err(request, 'هیچ فایلی انتخاب نشده است.'):
                return resp
            messages.error(request, 'هیچ فایلی انتخاب نشده است.')
            return redirect(upload_url)

        try:
            relative_paths = json.loads(request.POST.get('relative_paths', '[]'))
        except (json.JSONDecodeError, TypeError):
            relative_paths = []

        if relative_paths and len(relative_paths) != len(files):
            messages.warning(
                request,
                'تعداد مسیرها با فایل‌های ارسالی هم‌خوان نیست — ممکن است بخشی از فایل‌ها وارد نشوند.',
            )

        imported: list = []
        errors: list = []
        skipped = 0
        total_added = 0
        updated_files = 0
        new_files = 0
        reactivated_files = 0

        for idx, uploaded in enumerate(files):
            if idx < len(relative_paths) and relative_paths[idx]:
                rel_path = str(relative_paths[idx]).replace('\\', '/')
            else:
                rel_path = (uploaded.name or '').replace('\\', '/')
            if not is_importable_file(rel_path):
                skipped += 1
                continue

            ext = os.path.splitext(rel_path)[1].lower()
            path_info = parse_output_relative_path(rel_path)

            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                for chunk in uploaded.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            try:
                result = import_dataset(
                    user=request.user,
                    file_path=tmp_path,
                    original_filename=os.path.basename(rel_path),
                    path_info=path_info,
                )
                total_added += result.added_count
                if result.reactivated:
                    reactivated_files += 1
                elif result.is_update:
                    updated_files += 1
                else:
                    new_files += 1
                ds = result.dataset
                ds_md = ds.metadata or {}
                display_name = ds.name
                if not result.is_update and path_info:
                    display_name = build_dataset_name(path_info, os.path.basename(rel_path))
                imported.append({
                    'id': str(ds.pk),
                    'name': display_name,
                    'province': ds_md.get('province') or path_info.get('province', ''),
                    'city': ds.city or path_info.get('city', ''),
                    'district': ds.district or path_info.get('district', ''),
                    'subcategory': ds.subcategory,
                    'transaction_type': ds.transaction_type,
                    'count': result.added_count,
                    'skipped': result.skipped_count,
                    'total_in_file': result.total_in_file,
                    'is_update': result.is_update,
                    'reactivated': result.reactivated,
                    'path': path_info.get('relative_path', rel_path),
                })
            except Exception as e:
                errors.append({'path': rel_path, 'error': str(e)})
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        if not imported and not errors:
            msg = f'فایل داده‌ای یافت نشد ({skipped} فایل نادیده گرفته شد).'
            if resp := _upload_json_err(request, msg):
                return resp
            messages.warning(request, msg)
            return redirect(upload_url)

        if not imported and errors:
            messages.error(
                request,
                f'هیچ فایلی وارد نشد — {len(errors)} خطا. جزئیات را در مودال نتیجه ببینید.',
            )

        request.session['upload_batch'] = {
            'imported': imported,
            'errors': errors,
            'skipped': skipped,
            'groups': group_import_results(imported),
            'total_files': len(imported),
            'total_added': total_added,
            'new_files': new_files,
            'updated_files': updated_files,
            'reactivated_files': reactivated_files,
        }

        if errors:
            messages.warning(
                request,
                f'{len(imported)} فایل پردازش شد ({new_files} جدید، {updated_files} به‌روز)، '
                f'{total_added:,} آگهی جدید، {len(errors)} خطا.',
            )
        elif new_files and not total_added:
            messages.success(
                request,
                f'{new_files} فایل جدید اضافه شد.',
            )
        elif updated_files and not new_files and not total_added:
            messages.warning(
                request,
                f'{updated_files} فایل قبلاً وجود داشت — داده جدیدی یافت نشد.',
            )
        elif updated_files and not new_files:
            messages.info(
                request,
                f'{updated_files} فایل به‌روز — {total_added:,} آگهی جدید.',
            )
        elif updated_files:
            messages.success(
                request,
                f'{new_files} فایل جدید و {updated_files} به‌روز — {total_added:,} آگهی جدید.',
            )
        else:
            messages.success(
                request,
                f'{len(imported)} فایل جدید — {total_added:,} آگهی.',
            )

        if resp := _upload_json_ok(
            request,
            result_url,
            imported=len(imported),
            errors=len(errors),
            added=total_added,
        ):
            return resp
        return redirect(result_url)


class DatasetDetailView(DatasetOwnerMixin, TemplateView):
    template_name = 'workspace/datasets/detail.html'
    paginate_by = 50

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = self.get_dataset()
        dataset.touch()

        filters = parse_filter_params(self.request)
        tx = transaction_profile(dataset.transaction_type)
        default_sort = '-deposit' if tx['is_rent'] and not tx['is_mixed'] else '-price'
        sort = filters.get('sort') or default_sort
        filters['sort'] = sort

        qs = apply_listing_filters(dataset.listings.all(), filters, self.request.user)
        if filters.get('duplicates') == '1':
            dup_tokens = (
                dataset.listings.values('token')
                .annotate(c=Count('token'))
                .filter(c__gt=1)
                .values_list('token', flat=True)
            )
            qs = qs.filter(token__in=dup_tokens)

        all_listings = list(dataset.listings.all())
        mode = 'rent' if tx['is_rent'] and not tx['show_price'] else 'sale'
        enriched = compute_expected_values(enrich_dataframe(all_listings), mode=mode)
        value_map = {}
        for _, r in enriched.iterrows():
            score = r.get('value_score')
            if score is None:
                continue
            try:
                if score != score:
                    continue
            except TypeError:
                pass
            value_map[int(r['listing_id'])] = float(score)

        needs_post = any(filters.get(k) for k in (
            'rooms', 'elevator', 'parking', 'storage', 'year_min', 'year_max', 'value',
        )) or needs_advertiser_signal_filter(filters)
        if needs_post:
            filtered = list(qs)
            if needs_advertiser_signal_filter(filters):
                filtered = apply_advertiser_signal_filter(filtered, filters['consultant'])
            filtered = apply_amenity_filters(filtered, filters)
            filtered = apply_value_filter(filtered, value_map, filters.get('value', ''))
            qs_ids = [x.pk for x in filtered]
            qs = dataset.listings.filter(pk__in=qs_ids)
            if sort.lstrip('-') in ('elevator', 'parking', 'storage', 'build_year', 'value_score'):
                pass
            qs = sort_queryset(qs, sort, default_sort)
            paginator = Paginator(qs, self.paginate_by)
        else:
            qs = sort_queryset(qs, sort, default_sort)
            paginator = Paginator(qs, self.paginate_by)

        page = self.request.GET.get('page', 1)
        ctx['page_obj'] = paginator.get_page(page)
        ctx['listings'] = ctx['page_obj']
        ctx['columns'] = dataset.columns[:12] if dataset.columns else TABLE_COLUMNS_DEFAULT
        ctx['filters'] = filters
        ctx['filter_count'] = active_filter_count(filters)
        ctx['advanced_filter_count'] = advanced_filter_count(filters)
        ctx['filters_open'] = self.request.GET.get('filters_open') == '1'
        ctx['neighborhoods'] = get_neighborhoods(dataset)
        ctx['total_count'] = dataset.listings.count()
        ctx['filtered_count'] = paginator.count
        ctx['value_map'] = value_map
        ctx['listing_features'] = {
            lst.pk: extract_listing_features(lst) for lst in ctx['listings']
        }
        ctx['listings_edit_data'] = {
            str(lst.pk): listing_edit_payload(lst, ctx['listing_features'].get(lst.pk))
            for lst in ctx['listings']
        }
        listing_view = self.request.GET.get('view', '').strip()
        if listing_view not in ('table', 'grid'):
            listing_view = 'auto'
        ctx['listing_view_mode'] = listing_view
        base_filter = {
            k: v for k, v in filters.items()
            if v not in ('', None) and k != 'sort'
        }
        ctx['filter_qs_noview'] = urlencode(base_filter)
        if listing_view in ('table', 'grid'):
            base_filter['view'] = listing_view
        ctx['filter_qs'] = urlencode(base_filter)
        ctx['page_query'] = {
            k: str(v) for k, v in filters.items()
            if v not in ('', None)
        }
        if listing_view in ('table', 'grid'):
            ctx['page_query']['view'] = listing_view
        ctx['rename_form'] = DatasetRenameForm(instance=dataset)
        ctx['open_modal'] = self.request.GET.get('open', '')
        page_tokens = [lst.token for lst in ctx['listings']]
        metas = ListingMeta.objects.filter(
            user=self.request.user, token__in=page_tokens,
        )
        ctx['listing_metas'] = {m.token: m for m in metas}
        personal_props = CRMProperty.objects.filter(
            user=self.request.user, token__in=page_tokens,
        )
        ctx['personal_files_map'] = {p.token: p for p in personal_props}
        ctx['tx'] = tx
        all_qs = dataset.listings.all()
        from workspace.services.advertiser_signal import count_listings_by_advertiser_display
        adv_counts = count_listings_by_advertiser_display(all_qs)
        ctx['genuine_personal_count'] = adv_counts['genuine_personal']
        ctx['disguised_consultant_count'] = adv_counts['disguised_consultant']
        ctx['consultant_count'] = adv_counts['consultant']
        ctx['personal_other_count'] = adv_counts['personal_other']
        ctx['personal_count'] = (
            adv_counts['personal_other']
            + adv_counts['genuine_personal']
            + adv_counts['disguised_consultant']
        )
        total = ctx['total_count']
        if not total:
            ctx['genuine_personal_count'] = 0
            ctx['disguised_consultant_count'] = 0
            ctx['consultant_count'] = 0
            ctx['personal_other_count'] = 0
            ctx['personal_count'] = 0
        filtered = ctx['filtered_count']
        consultant = ctx['consultant_count']
        ctx['consultant_pct'] = round(consultant * 100 / total) if total else 0
        ctx['genuine_personal_pct'] = round(ctx['genuine_personal_count'] * 100 / total) if total else 0
        ctx['disguised_consultant_pct'] = round(ctx['disguised_consultant_count'] * 100 / total) if total else 0
        ctx['personal_other_pct'] = round(ctx['personal_other_count'] * 100 / total) if total else 0
        ctx['personal_pct'] = round(ctx['personal_count'] * 100 / total) if total else 0
        ctx['filter_pct'] = round(filtered * 100 / total) if total else 100
        ctx['is_listing_filtered'] = filtered < total or ctx['filter_count'] > 0
        ctx['listing_edit_form'] = ListingEditForm()
        ctx['filing_video'] = get_filing_video_context()
        ctx['filter_reset_url'] = reverse('workspace:dataset_detail', args=[dataset.id])
        ctx['show_dataset_column'] = False
        return ctx


def _parse_dataset_ids_param(request):
    """پشتیبانی از dataset_ids=id1,id2 و همچنین چند پارامتر تکراری."""
    ids = []
    seen = set()
    for item in request.GET.getlist('dataset_ids'):
        for part in str(item or '').split(','):
            part = part.strip()
            if part and part not in seen:
                seen.add(part)
                ids.append(part)
    return ids


def _merged_transaction_profile(datasets) -> dict:
    modes = {transaction_profile(d.transaction_type)['mode'] for d in datasets}
    if not modes:
        return transaction_profile('فروش')
    if 'ترکیبی' in modes or ({'فروش', 'اجاره'} <= modes):
        return transaction_profile('ترکیبی')
    if len(modes) == 1:
        return transaction_profile(next(iter(modes)))
    return transaction_profile('ترکیبی')


def _value_map_for_datasets(datasets) -> dict:
    value_map = {}
    for ds in datasets:
        tx = transaction_profile(ds.transaction_type)
        mode = 'rent' if tx['is_rent'] and not tx['show_price'] else 'sale'
        all_listings = list(ds.listings.all())
        if not all_listings:
            continue
        enriched = compute_expected_values(enrich_dataframe(all_listings), mode=mode)
        for _, r in enriched.iterrows():
            score = r.get('value_score')
            if score is None:
                continue
            try:
                if score != score:
                    continue
            except TypeError:
                pass
            value_map[int(r['listing_id'])] = float(score)
    return value_map


class MultiDatasetListingsView(LicenseRequiredMixin, TemplateView):
    """مرور یکپارچه آگهی‌های چند مجموعه‌داده انتخاب‌شده."""

    template_name = 'workspace/listings/multi.html'
    paginate_by = 50
    max_datasets = 30

    def get(self, request, *args, **kwargs):
        ids = _parse_dataset_ids_param(request)
        if not ids:
            messages.warning(request, 'هیچ فایلی برای مشاهده آگهی‌ها انتخاب نشده است.')
            return redirect('workspace:dataset_list')
        if len(ids) > self.max_datasets:
            messages.warning(
                request,
                f'حداکثر {self.max_datasets} فایل را می‌توانید همزمان ببینید.',
            )
            ids = ids[: self.max_datasets]
        datasets = list(
            Dataset.objects.filter(user=request.user, is_active=True, pk__in=ids)
            .order_by('-last_opened_at', '-created_at')
        )
        if not datasets:
            messages.error(request, 'فایل‌های انتخاب‌شده یافت نشد.')
            return redirect('workspace:dataset_list')
        # حفظ ترتیب انتخاب کاربر تا حد ممکن
        by_id = {str(d.id): d for d in datasets}
        ordered = [by_id[i] for i in ids if i in by_id]
        self.datasets = ordered or datasets
        self.dataset_ids_param = ','.join(str(d.id) for d in self.datasets)
        for ds in self.datasets[:5]:
            ds.touch()
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        datasets = self.datasets
        base_qs = Listing.objects.filter(dataset__in=datasets).select_related('dataset')

        filters = parse_filter_params(self.request)
        tx = _merged_transaction_profile(datasets)
        default_sort = '-deposit' if tx['is_rent'] and not tx['is_mixed'] else '-price'
        sort = filters.get('sort') or default_sort
        filters['sort'] = sort

        qs = apply_listing_filters(base_qs, filters, self.request.user)
        if filters.get('duplicates') == '1':
            dup_tokens = (
                base_qs.values('token')
                .annotate(c=Count('token'))
                .filter(c__gt=1)
                .values_list('token', flat=True)
            )
            qs = qs.filter(token__in=dup_tokens)

        value_map = _value_map_for_datasets(datasets)

        needs_post = any(filters.get(k) for k in (
            'rooms', 'elevator', 'parking', 'storage', 'year_min', 'year_max', 'value',
        )) or needs_advertiser_signal_filter(filters)
        if needs_post:
            filtered = list(qs)
            if needs_advertiser_signal_filter(filters):
                filtered = apply_advertiser_signal_filter(filtered, filters['consultant'])
            filtered = apply_amenity_filters(filtered, filters)
            filtered = apply_value_filter(filtered, value_map, filters.get('value', ''))
            qs_ids = [x.pk for x in filtered]
            qs = base_qs.filter(pk__in=qs_ids)
            qs = sort_queryset(qs, sort, default_sort)
            paginator = Paginator(qs, self.paginate_by)
        else:
            qs = sort_queryset(qs, sort, default_sort)
            paginator = Paginator(qs, self.paginate_by)

        page = self.request.GET.get('page', 1)
        ctx['page_obj'] = paginator.get_page(page)
        ctx['listings'] = ctx['page_obj']
        ctx['datasets'] = datasets
        ctx['dataset_ids_param'] = self.dataset_ids_param
        ctx['dataset_count'] = len(datasets)
        ctx['filters'] = filters
        ctx['filter_count'] = active_filter_count(filters)
        ctx['advanced_filter_count'] = advanced_filter_count(filters)
        ctx['filters_open'] = self.request.GET.get('filters_open') == '1'
        ctx['neighborhoods'] = get_neighborhoods_qs(base_qs)
        ctx['total_count'] = base_qs.count()
        ctx['filtered_count'] = paginator.count
        ctx['value_map'] = value_map
        ctx['listing_features'] = {
            lst.pk: extract_listing_features(lst) for lst in ctx['listings']
        }
        ctx['listings_edit_data'] = {
            str(lst.pk): listing_edit_payload(lst, ctx['listing_features'].get(lst.pk))
            for lst in ctx['listings']
        }
        filter_pairs = [('dataset_ids', self.dataset_ids_param)]
        filter_pairs.extend(
            (k, str(v)) for k, v in filters.items()
            if v not in ('', None) and k != 'sort'
        )
        listing_view = self.request.GET.get('view', '').strip()
        if listing_view not in ('table', 'grid'):
            listing_view = 'auto'
        ctx['listing_view_mode'] = listing_view
        ctx['filter_qs_noview'] = urlencode(filter_pairs)
        if listing_view in ('table', 'grid'):
            filter_pairs = list(filter_pairs) + [('view', listing_view)]
        ctx['filter_qs'] = urlencode(filter_pairs)
        ctx['page_query'] = {
            'dataset_ids': self.dataset_ids_param,
            **{
                k: str(v) for k, v in filters.items()
                if v not in ('', None)
            },
        }
        if listing_view in ('table', 'grid'):
            ctx['page_query']['view'] = listing_view
        page_tokens = [lst.token for lst in ctx['listings']]
        metas = ListingMeta.objects.filter(
            user=self.request.user, token__in=page_tokens,
        )
        ctx['listing_metas'] = {m.token: m for m in metas}
        personal_props = CRMProperty.objects.filter(
            user=self.request.user, token__in=page_tokens,
        )
        ctx['personal_files_map'] = {p.token: p for p in personal_props}
        ctx['tx'] = tx
        from workspace.services.advertiser_signal import count_listings_by_advertiser_display
        adv_counts = count_listings_by_advertiser_display(
            Listing.objects.filter(dataset__in=datasets)
        )
        ctx['genuine_personal_count'] = adv_counts['genuine_personal']
        ctx['disguised_consultant_count'] = adv_counts['disguised_consultant']
        ctx['consultant_count'] = adv_counts['consultant']
        ctx['personal_other_count'] = adv_counts['personal_other']
        ctx['personal_count'] = (
            adv_counts['personal_other']
            + adv_counts['genuine_personal']
            + adv_counts['disguised_consultant']
        )
        total = ctx['total_count']
        if not total:
            ctx['genuine_personal_count'] = 0
            ctx['disguised_consultant_count'] = 0
            ctx['consultant_count'] = 0
            ctx['personal_other_count'] = 0
            ctx['personal_count'] = 0
        filtered = ctx['filtered_count']
        consultant = ctx['consultant_count']
        ctx['consultant_pct'] = round(consultant * 100 / total) if total else 0
        ctx['genuine_personal_pct'] = round(ctx['genuine_personal_count'] * 100 / total) if total else 0
        ctx['disguised_consultant_pct'] = round(ctx['disguised_consultant_count'] * 100 / total) if total else 0
        ctx['personal_other_pct'] = round(ctx['personal_other_count'] * 100 / total) if total else 0
        ctx['personal_pct'] = round(ctx['personal_count'] * 100 / total) if total else 0
        ctx['filter_pct'] = round(filtered * 100 / total) if total else 100
        ctx['is_listing_filtered'] = filtered < total or ctx['filter_count'] > 0
        ctx['listing_edit_form'] = ListingEditForm()
        ctx['filter_reset_url'] = (
            reverse('workspace:multi_listings') + '?dataset_ids=' + self.dataset_ids_param
        )
        ctx['filter_form_action'] = reverse('workspace:multi_listings')
        ctx['show_dataset_column'] = True
        # سازگاری با includeهایی که هنوز dataset می‌خواهند (مثلاً لینک خالی)
        ctx['dataset'] = datasets[0]
        return ctx


class DatasetBulkDeleteView(LicenseRequiredMixin, View):
    """حذف نرم دسته‌جمعی فایل‌ها."""

    def post(self, request):
        raw_ids = request.POST.getlist('ids')
        if not raw_ids:
            messages.error(request, 'هیچ فایلی انتخاب نشده است.')
            return redirect('workspace:dataset_list')

        qs = Dataset.objects.filter(user=request.user, is_active=True, pk__in=raw_ids)
        count = qs.count()
        if not count:
            messages.warning(request, 'فایل انتخاب‌شده‌ای یافت نشد.')
            return redirect('workspace:dataset_list')

        _soft_delete_datasets(qs)
        messages.success(request, f'{count:,} فایل و آگهی‌هایش حذف شد.')
        return redirect('workspace:dataset_list')


class DatasetDeleteView(DatasetOwnerMixin, View):
    """حذف نرم — فقط POST (از مودال تأیید)."""

    def get(self, request, dataset_id):
        return redirect('workspace:dataset_list')

    def post(self, request, dataset_id):
        dataset = self.get_dataset()
        _soft_delete_datasets(Dataset.objects.filter(pk=dataset.pk))
        messages.success(request, f'مجموعه‌داده «{dataset.name}» و آگهی‌هایش حذف شد.')
        return redirect('workspace:dataset_list')


class DatasetRenameView(DatasetOwnerMixin, UpdateView):
    model = Dataset
    form_class = DatasetRenameForm
    pk_url_kwarg = 'dataset_id'

    def get_queryset(self):
        return Dataset.objects.filter(user=self.request.user)

    def get(self, request, *args, **kwargs):
        dataset = self.get_dataset()
        return redirect(f"{reverse('workspace:dataset_detail', kwargs={'dataset_id': dataset.pk})}?open=modal-rename")

    def get_success_url(self):
        return reverse('workspace:dataset_detail', kwargs={'dataset_id': self.object.pk})

    def form_invalid(self, form):
        dataset = self.get_dataset()
        view = DatasetDetailView()
        view.request = self.request
        view.kwargs = {'dataset_id': dataset.pk}
        ctx = view.get_context_data()
        ctx['rename_form'] = form
        ctx['open_modal'] = 'modal-rename'
        return render(self.request, 'workspace/datasets/detail.html', ctx)


class DatasetExportView(DatasetOwnerMixin, View):
    def get(self, request, dataset_id):
        dataset = self.get_dataset()
        fmt = request.GET.get('format', 'csv')
        listings = dataset.listings.all()
        filename = f'{dataset.name}.{fmt}'
        if fmt == 'json':
            return export_json_response(listings, filename)
        return export_csv_response(listings, filename)


# ─── Listing Detail ───────────────────────────────────────────────────────────

class ListingDetailView(DatasetOwnerMixin, DetailView):
    model = Listing
    template_name = 'workspace/listings/detail.html'
    context_object_name = 'listing'
    pk_url_kwarg = 'listing_id'

    def get_object(self):
        dataset = self.get_dataset()
        return get_object_or_404(dataset.listings, pk=self.kwargs['listing_id'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        listing = self.object
        meta, _ = ListingMeta.objects.get_or_create(
            user=self.request.user, token=listing.token,
        )
        ctx['meta'] = meta
        ctx['meta_form'] = ListingMetaForm(instance=meta)
        dataset = self.get_dataset()
        tx = transaction_profile(dataset.transaction_type)
        ctx['feat'] = extract_listing_features(listing)
        data = build_listing_display_data(listing, ctx['feat'])
        ctx['tx'] = tx
        sections = format_sections(data, tx)
        sections.pop('سایر', None)
        if listing.latitude and listing.longitude:
            sections.setdefault('مکان', {})
        ctx['sections'] = sections
        ctx['section_rows'] = {
            name: format_field_rows(fields, data) for name, fields in sections.items()
        }
        ctx['location_accuracy'] = location_accuracy_for_map(data)
        ctx['supplementary_fields'] = format_supplementary_fields(data, tx, sections)
        ctx['supplementary_groups'] = format_supplementary_groups(data, tx, sections)
        ctx['feature_profile'] = build_listing_feature_profile(listing, ctx['feat'])
        ctx['dossier_amenities'] = build_listing_amenity_dossier_items(
            listing, ctx['feat'], ctx['feature_profile'],
        )
        ctx['open_modal'] = self.request.GET.get('open', '')
        df = listings_to_dataframe(dataset.listings.all())
        ctx['benchmark'] = benchmark_listing(listing, df, dataset.transaction_type) if len(df) else {}
        raw_history = list(PriceHistory.objects.filter(
            user=self.request.user, token=listing.token,
        ).order_by('-recorded_at')[:50])
        ctx['price_history'] = dedupe_price_history(raw_history)[:15]
        ctx['whatsapp_text'] = self._whatsapp_text(listing, tx)
        ctx['crm_links'] = customers_linked_to_token(self.request.user, listing.token)
        ctx['crm_customers'] = customers_qs(self.request.user).order_by('-updated_at')[:200]
        ctx['crm_listing_roles'] = LISTING_ROLES
        ctx['crm_deal_types'] = DEAL_TYPES
        ctx['crm_default_deal'] = guess_deal_type_from_listing(listing)
        ctx['crm_property'] = get_crm_property_by_token(self.request.user, listing.token)
        ctx['owner_phone'] = owner_phone_from_listing(listing)
        ctx['owner_name'] = owner_name_from_listing(listing)
        if ctx['crm_property']:
            ctx['owner_phone'] = ctx['crm_property'].phone or ctx['owner_phone']
            ctx['owner_name'] = ctx['crm_property'].owner_name or ctx['owner_name']
        ctx['owner_contact'] = primary_owner_contact(
            listing=listing, crm_property=ctx['crm_property'],
        )
        ctx['gallery_images'] = deduplicate_divar_image_urls(
            [normalize_external_image_url(img) for img in (listing.images or []) if img],
        )
        gallery = ctx['gallery_images']
        ctx['listing_map_marker'] = build_listing_map_marker(
            listing,
            tx,
            ctx['feat'],
            data=data,
            location_accuracy=ctx['location_accuracy'],
            thumb=gallery[0] if gallery else '',
            platform_url=reverse(
                'workspace:listing_detail',
                kwargs={'dataset_id': dataset.id, 'listing_id': listing.id},
            ),
            benchmark=ctx['benchmark'],
        )
        share = get_or_create_listing_share(self.request.user, listing)
        ctx['public_share'] = share
        ctx['public_share_url'] = public_share_url(self.request, share)
        from workspace.services.public_share_common import build_map_navigation, share_profile_context
        profile = share_profile_context(
            self.request.user, share,
            title=listing.title or '',
            share_url=ctx['public_share_url'],
        )
        ctx['consultant_name'] = profile['consultant_name']
        ctx['consultant_phone'] = profile['consultant_phone']
        ctx['share_profile'] = profile
        ctx['map_navigation'] = build_map_navigation(listing.latitude, listing.longitude)
        ctx['listings_edit_data'] = {
            str(listing.pk): listing_edit_payload(listing, ctx['feat']),
        }
        return ctx

    def _whatsapp_text(self, listing, tx):
        parts = [listing.title or '']
        if listing.area:
            parts.append(f'متراژ: {listing.area} متر')
        if tx['show_price'] and listing.price:
            parts.append(f'قیمت: {format_toman(listing.price)}')
        if tx['show_deposit'] and listing.deposit:
            parts.append(f'ودیعه: {format_toman(listing.deposit)}')
        if tx['show_rent'] and listing.rent:
            parts.append(f'اجاره: {format_toman(listing.rent)}')
        if listing.neighborhood:
            parts.append(f'محله: {listing.neighborhood}')
        if listing.link:
            parts.append(listing.link)
        return '\n'.join(parts)

    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        action = request.POST.get('action', 'meta')

        if action == 'crm_link':
            customer = customer_for_user(request.user, int(request.POST.get('customer_id') or 0))
            if not customer:
                messages.error(request, 'مخاطب یافت نشد.')
                return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)
            if not can_edit_customer(request.user, customer):
                messages.error(request, 'این مخاطب فقط برای مشاهده به اشتراک گذاشته شده است.')
                return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)
            tx = transaction_profile(dataset.transaction_type)
            link_listing_to_customer(
                customer, listing, tx,
                role=request.POST.get('role', 'پیشنهادی'),
                deal_type=request.POST.get('deal_type', ''),
            )
            messages.success(request, f'آگهی به «{customer.name}» پیوند شد.')
            return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)

        if action == 'save_owner':
            phone = (request.POST.get('owner_phone') or '').strip()
            name = (request.POST.get('owner_name') or '').strip()
            customer = upsert_property_owner(
                request.user,
                phone=phone,
                name=name,
                listing=listing,
                source='دیوار',
            )
            if phone and customer:
                messages.success(request, f'مالک «{customer.name}» ذخیره و به مخاطبین پیوند شد.')
            elif phone:
                messages.success(request, 'اطلاعات مالک ذخیره شد.')
            else:
                messages.success(request, 'شماره مالک پاک شد.')
            return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)

        if action == 'crm_unlink':
            link_id = request.POST.get('link_id')
            link = customers_linked_to_token(request.user, listing.token).filter(pk=link_id).first()
            if not link:
                messages.error(request, 'پیوند یافت نشد.')
            else:
                name = link.customer.name
                link.delete()
                messages.success(request, f'پیوند «{name}» حذف شد.')
            return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)

        meta, _ = ListingMeta.objects.get_or_create(user=request.user, token=listing.token)
        form = ListingMetaForm(request.POST, instance=meta)
        if form.is_valid():
            form.save()
            messages.success(request, 'متادیتا ذخیره شد.')
        return redirect('workspace:listing_detail', dataset_id=dataset_id, listing_id=listing_id)


class ListingShareManageView(DatasetOwnerMixin, View):
    """مدیریت لینک عمومی اشتراک آگهی با مشتری."""

    def get(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        share = get_or_create_listing_share(request.user, listing)
        from workspace.services.public_share_common import share_profile_context
        url = public_share_url(request, share)
        profile = share_profile_context(
            request.user, share, title=listing.title or '', share_url=url,
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
            'approximate_location': share.approximate_location,
            'is_active': share.is_active,
        })

    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        share = get_or_create_listing_share(request.user, listing)
        from workspace.services.public_share_common import (
            apply_share_form_extras,
            normalize_consultant_fields_for_save,
        )
        name, phone = normalize_consultant_fields_for_save(
            request.user,
            request.POST.get('consultant_name') or '',
            request.POST.get('consultant_phone') or '',
        )
        share.consultant_name = name
        share.consultant_phone = phone
        apply_share_form_extras(request.user, request.POST, share, files=request.FILES)
        share.show_divar_link = request.POST.get('show_divar_link') in ('1', 'true', 'on')
        share.approximate_location = request.POST.get('approximate_location') in ('1', 'true', 'on')
        share.is_active = request.POST.get('is_active') in ('1', 'true', 'on')
        share.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'share_url': public_share_url(request, share),
                'message': 'تنظیمات اشتراک ذخیره شد.',
            })
        messages.success(request, 'تنظیمات لینک اشتراک ذخیره شد.')
        return redirect(
            'workspace:listing_detail',
            dataset_id=dataset.pk, listing_id=listing.pk,
        )


class ListingUpdateView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        try:
            apply_listing_edit_post(listing, request.POST)
            listing.save()
            dataset.mark_updated()
            if 'owner_phone' in request.POST or 'owner_name' in request.POST:
                upsert_property_owner(
                    request.user,
                    phone=request.POST.get('owner_phone', ''),
                    name=request.POST.get('owner_name', ''),
                    listing=listing,
                    source='دیوار',
                )
            messages.success(request, 'آگهی به‌روزرسانی شد.')
        except (ValueError, TypeError) as exc:
            messages.error(request, f'ذخیره نشد: {exc}' if str(exc) else 'مقادیر عددی نامعتبر است.')
        nxt = request.POST.get('next') or reverse(
            'workspace:dataset_detail', kwargs={'dataset_id': dataset.pk},
        )
        return redirect(nxt)


class ListingDeleteView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        title = listing.title[:40] if listing.title else listing.token
        listing.delete()
        dataset.sync_row_count()
        messages.success(request, f'آگهی «{title}» حذف شد.')
        return redirect('workspace:dataset_detail', dataset_id=dataset.pk)


class ListingFavoriteToggleView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        meta, _ = ListingMeta.objects.get_or_create(
            user=request.user, token=listing.token,
        )
        meta.is_favorite = not meta.is_favorite
        meta.save(update_fields=['is_favorite', 'updated_at'])
        return redirect(request.POST.get('next') or reverse(
            'workspace:dataset_detail', kwargs={'dataset_id': dataset.pk},
        ))


class ListingAddToPersonalFilesView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        prop, created = add_listing_to_personal_files(request.user, listing)
        if created:
            messages.success(
                request,
                'آگهی به فایل‌های شخصی منتقل شد و از فایلینگ دیوار حذف شد.',
            )
        else:
            messages.info(
                request,
                'این آگهی قبلاً در فایل‌های شخصی بود؛ از فایلینگ دیوار حذف شد.',
            )
        if request.POST.get('redirect') == 'property':
            return redirect('workspace:crm_property_detail', property_id=prop.pk)
        nxt = (request.POST.get('next') or '').strip()
        # آگهی از فایلینگ حذف شده؛ به جزئیات آگهی برنگرد
        if nxt and f'/listings/{listing_id}/' not in nxt:
            return redirect(nxt)
        return redirect('workspace:crm_property_detail', property_id=prop.pk)


class DeleteConsultantsView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id):
        dataset = self.get_dataset()
        qs = consultant_q(dataset.listings.all())
        count = qs.count()
        if count:
            qs.delete()
            dataset.sync_row_count()
            messages.success(request, f'{count:,} آگهی مشاور حذف شد.')
        else:
            messages.info(request, 'آگهی مشاوری برای حذف یافت نشد.')
        return redirect('workspace:dataset_detail', dataset_id=dataset.pk)


class DeleteDisguisedConsultantsView(DatasetOwnerMixin, View):
    def post(self, request, dataset_id):
        from workspace.services.advertiser_signal import disguised_consultant_listing_ids

        dataset = self.get_dataset()
        ids = disguised_consultant_listing_ids(dataset.listings.all())
        if ids:
            dataset.listings.filter(pk__in=ids).delete()
            dataset.sync_row_count()
            messages.success(request, f'{len(ids):,} آگهی مشاور پنهان حذف شد.')
        else:
            messages.info(request, 'آگهی مشاور پنهانی برای حذف یافت نشد.')
        return redirect('workspace:dataset_detail', dataset_id=dataset.pk)


# ─── Analyze ──────────────────────────────────────────────────────────────────

class DatasetAnalyzeView(DatasetOwnerMixin, TemplateView):
    template_name = 'workspace/analyze/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = self.get_dataset()
        listings = list(dataset.listings.all())
        df = listings_to_dataframe(listings)
        lite = len(df) > 200
        df_clean = filter_outliers(df, dataset.transaction_type) if len(df) >= 10 else df

        tx = transaction_profile(dataset.transaction_type)
        stats = compute_statistics(df_clean, dataset.transaction_type)
        ctx['stats'] = stats
        ctx['tx'] = tx
        ctx['outliers'] = compute_outliers_report(df, dataset.transaction_type)
        market = analyze_market(df_clean, dataset.transaction_type)
        ctx['market_stats'] = market.get('stats', {})
        dashboard = build_analysis_dashboard(
            df_clean, stats, market, dataset.transaction_type,
            df_raw=df,
            outliers_report=ctx['outliers'],
            listings=listings,
            dataset_name=dataset.name,
            subcategory=dataset.subcategory or '',
        )
        ctx['area_segments'] = dashboard['area_segments']
        ctx['scenarios'] = dashboard['scenarios']
        ctx['factors'] = dashboard['factors']
        ctx['insights'] = dashboard['insights']
        ctx['market_brief'] = dashboard['market_brief']
        ctx['ui_labels'] = dashboard['ui_labels']
        prof = dashboard['professional']
        confidence = resolve_report_confidence(
            prof, valid_count=len(df_clean), raw_count=len(df),
        )
        prof['confidence'] = confidence
        ctx['report'] = prof
        ctx['analysis_confidence'] = confidence
        ctx['consultant_cards'] = generate_consultant_guide(
            df_clean, stats, dataset.transaction_type, str(dataset.pk),
        )
        ctx['charts'] = build_all_charts(
            df_clean, lite=lite, transaction_type=dataset.transaction_type,
            market_stats=ctx['market_stats'],
            area_segments=ctx['area_segments'],
            report=ctx['report'],
        )
        ctx['charts_json'] = json.dumps(ctx['charts'], ensure_ascii=False)
        ctx['l2'] = build_l2_ui(prof, ctx['charts'], flat_insights=ctx.get('insights'))
        ctx['l3'] = build_l3_ui(prof)
        ctx['lite_mode'] = lite
        ctx['row_count'] = len(df)
        ctx['clean_count'] = len(df_clean)
        ctx['open_modal'] = self.request.GET.get('open', '')
        return ctx


# ─── Map ──────────────────────────────────────────────────────────────────────

class DatasetMapView(DatasetOwnerMixin, TemplateView):
    template_name = 'workspace/map/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dataset = self.get_dataset()
        settings = get_or_create_settings(self.request.user)
        geo_listings = dataset.listings.exclude(
            latitude__isnull=True,
        ).exclude(longitude__isnull=True)
        geo_count = geo_listings.count()
        marker_limit = 2500
        sampled = geo_listings[:marker_limit]
        markers = map_markers(
            sampled,
            transaction_type=dataset.transaction_type,
            dataset_id=dataset.pk,
        )
        ctx['markers'] = markers
        ctx['markers_json'] = json.dumps(markers, ensure_ascii=False)
        tx = transaction_profile(dataset.transaction_type)
        ctx['map_config'] = {
            'map_cluster': settings.map_cluster,
            'focusMaxZoom': 17,
            'clusterDisableZoom': 15,
            'mapModes': True,
            'datasetName': dataset.name,
            'datasetCity': dataset.city or '',
            'is_rent': bool(tx['is_rent'] and not tx['is_sale']),
            'filter_value_label': 'رهن کامل' if (tx['is_rent'] and not tx['is_sale']) else 'قیمت',
            'filterValueLabel': 'رهن کامل' if (tx['is_rent'] and not tx['is_sale']) else 'قیمت',
        }
        ctx['map_config_json'] = json.dumps(ctx['map_config'], ensure_ascii=False)
        ctx['geo_count'] = geo_count
        ctx['markers_shown'] = len(markers)
        ctx['markers_truncated'] = geo_count > marker_limit
        ctx['consultant_count'] = sum(1 for m in markers if m.get('is_consultant'))
        ctx['disguised_consultant_count'] = sum(1 for m in markers if m.get('is_disguised'))
        ctx['genuine_personal_count'] = max(
            0,
            len(markers) - ctx['consultant_count'] - ctx['disguised_consultant_count'],
        )
        # سازگاری عقب‌رو با قالب‌های قدیمی
        ctx['personal_count'] = ctx['genuine_personal_count'] + ctx['disguised_consultant_count']
        ctx['ws_settings'] = settings
        return ctx


# ─── Tools ────────────────────────────────────────────────────────────────────

class ToolsView(LicenseRequiredMixin, TemplateView):
    template_name = 'workspace/tools/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        datasets = list(
            _dataset_base_qs(self.request.user).order_by('-last_opened_at', '-created_at'),
        )
        ctx['datasets'] = datasets

        selected = None
        selected_id = self.request.GET.get('dataset', '').strip()
        if selected_id:
            selected = next((d for d in datasets if str(d.pk) == selected_id), None)
        if not selected and datasets:
            selected = datasets[0]

        from workspace.services.tools import build_market_snapshot

        snapshots = {str(d.pk): build_market_snapshot(d) for d in datasets}
        ctx['selected_dataset'] = selected
        ctx['active_dataset'] = selected
        ctx['market_snapshots'] = snapshots
        ctx['market_snapshot'] = snapshots.get(str(selected.pk)) if selected else None
        ctx['market_snapshots_json'] = json.dumps(snapshots, ensure_ascii=False)
        ctx['market_snapshot_json'] = json.dumps(ctx['market_snapshot'], ensure_ascii=False)
        return ctx


class ToolsMarketToolkitView(DatasetOwnerMixin, View):
    """داده ابزارهای بازار برای یک فایل."""

    def get(self, request, dataset_id):
        from workspace.services.tools_market import build_market_toolkit

        dataset = self.get_dataset()
        return JsonResponse(build_market_toolkit(dataset))


class ToolsEvaluateView(DatasetOwnerMixin, View):
    """ارزیابی آنی آگهی نسبت به بازار فایل."""

    def post(self, request, dataset_id):
        from workspace.services.tools_market import evaluate_listing_market, search_listings

        dataset = self.get_dataset()
        try:
            body = json.loads(request.body.decode() or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'error': 'درخواست نامعتبر است.'}, status=400)

        action = body.get('action', 'evaluate')
        if action == 'search':
            items = search_listings(dataset, body.get('q', ''), limit=12)
            return JsonResponse({'items': items})

        result = evaluate_listing_market(
            dataset,
            listing_id=body.get('listing_id'),
            area=body.get('area'),
            price=body.get('price'),
            deposit=body.get('deposit'),
            rent=body.get('rent'),
            neighborhood=body.get('neighborhood') or None,
        )
        if result.get('error'):
            return JsonResponse(result, status=400)
        return JsonResponse(result)


# ─── Compare ──────────────────────────────────────────────────────────────────

class CompareView(LicenseRequiredMixin, TemplateView):
    template_name = 'workspace/compare/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['form'] = CompareForm(self.request.user)
        ctx['open_modal'] = self.request.GET.get('open', ctx.get('open_modal', ''))
        return ctx

    def post(self, request):
        form = CompareForm(request.user, request.POST)
        result = None
        open_modal = ''
        if form.is_valid():
            a = form.cleaned_data['dataset_a']
            b = form.cleaned_data['dataset_b']
            if a.pk == b.pk:
                messages.error(request, 'دو فایل متفاوت انتخاب کنید.')
                open_modal = 'modal-compare'
            else:
                result = compare_datasets(a, b)
        else:
            open_modal = 'modal-compare'
        return render(request, self.template_name, {
            'form': form, 'result': result, 'open_modal': open_modal,
        })


# ─── Reminders ────────────────────────────────────────────────────────────────

class ReminderListView(WorkspaceLoginMixin, ListView):
    model = Reminder
    template_name = 'workspace/reminders/list.html'
    context_object_name = 'reminders'

    def get_queryset(self):
        show = self.request.GET.get('show', 'active')
        qs = Reminder.objects.filter(user=self.request.user)
        if show == 'done':
            return qs.filter(is_done=True).order_by('-due_at')
        if show == 'all':
            return qs.order_by('due_at')
        return qs.filter(is_done=False).order_by('due_at')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['show'] = self.request.GET.get('show', 'active')
        ctx['open_modal'] = self.request.GET.get('open', '')
        return ctx


class ReminderToggleView(WorkspaceLoginMixin, View):
    def post(self, request, reminder_id):
        reminder = get_object_or_404(Reminder, pk=reminder_id, user=request.user)
        reminder.is_done = not reminder.is_done
        reminder.save(update_fields=['is_done'])
        status = 'انجام شد' if reminder.is_done else 'فعال شد'
        messages.success(request, f'یادآور {status}.')
        return redirect('workspace:reminder_list')


class ReminderCreateView(WorkspaceLoginMixin, CreateView):
    model = Reminder
    form_class = ReminderForm
    template_name = 'workspace/reminders/list.html'
    success_url = reverse_lazy('workspace:reminder_list')

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('workspace:reminder_list')}?open=modal-reminder")

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, 'یادآور ثبت شد.')
        return super().form_valid(form)

    def form_invalid(self, form):
        view = ReminderListView()
        view.request = self.request
        view.object_list = view.get_queryset()
        ctx = view.get_context_data(object_list=view.object_list)
        ctx['ws_reminder_form'] = form
        ctx['open_modal'] = 'modal-reminder'
        return render(self.request, self.template_name, ctx)


# ─── Settings & Help ──────────────────────────────────────────────────────────

class WorkspaceSettingsView(WorkspaceLoginMixin, UpdateView):
    model = WorkspaceSettings
    form_class = WorkspaceSettingsForm
    success_url = reverse_lazy('workspace:home')

    def get_object(self):
        return get_or_create_settings(self.request.user)

    def get(self, request, *args, **kwargs):
        return redirect(f"{reverse('workspace:home')}?open=modal-settings")

    def form_valid(self, form):
        from workspace.services.public_share_common import (
            agency_social_links_from_post,
            social_links_from_post,
        )

        obj = form.save(commit=False)
        post = self.request.POST

        if post.get('clear_consultant_photo') in ('1', 'true', 'on') and not form.cleaned_data.get('consultant_photo'):
            if obj.consultant_photo:
                obj.consultant_photo.delete(save=False)
            obj.consultant_photo = None
        if post.get('clear_business_card_image') in ('1', 'true', 'on') and not form.cleaned_data.get('business_card_image'):
            if obj.business_card_image:
                obj.business_card_image.delete(save=False)
            obj.business_card_image = None

        obj.social_links = social_links_from_post(post)
        obj.agency_social_links = agency_social_links_from_post(post)
        obj.save()
        messages.success(self.request, 'تنظیمات ذخیره شد.')
        return redirect(self.get_success_url())

    def form_invalid(self, form):
        view = WorkspaceHomeView()
        view.request = self.request
        ctx = view.get_context_data()
        ctx['ws_settings_form'] = form
        ctx['open_modal'] = 'modal-settings'
        messages.error(self.request, 'خطا در ذخیره تنظیمات.')
        return render(self.request, 'workspace/home.html', ctx)


class HelpView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/help.html'

    def get_context_data(self, **kwargs):
        from workspace.services.crm_video import get_crm_video_context
        from workspace.help_content import workspace_help_content
        ctx = super().get_context_data(**kwargs)
        ctx['help'] = workspace_help_content()
        ctx['crm_video'] = get_crm_video_context()
        return ctx


class ApiDocsView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/docs_api.html'

    def get_context_data(self, **kwargs):
        from workspace.api_docs_content import workspace_api_docs
        from workspace.services.crm_scope import can_manage_team, get_agency

        ctx = super().get_context_data(**kwargs)
        agency = get_agency(self.request.user)
        can_manage = can_manage_team(self.request.user)
        has_crm_key = bool(agency and can_manage and agency.api_key)
        ctx['api_docs'] = workspace_api_docs(has_crm_api_key=has_crm_key)
        ctx['can_manage_crm_api'] = can_manage
        ctx['has_crm_api_key'] = has_crm_key
        return ctx


class CrmApiKeyRevealView(WorkspaceLoginMixin, View):
    """Reveal CRM agency API key only on authenticated POST (not embedded in page HTML)."""

    http_method_names = ['post']

    def post(self, request):
        from workspace.services.crm_scope import can_manage_team, get_agency

        if not can_manage_team(request.user):
            return JsonResponse({'ok': False, 'error': 'دسترسی مجاز نیست.'}, status=403)
        agency = get_agency(request.user)
        if not agency or not agency.api_key:
            return JsonResponse({'ok': False, 'error': 'کلید API یافت نشد.'}, status=404)
        return JsonResponse({'ok': True, 'key': agency.api_key})


class BotUpgradeView(WorkspaceLoginMixin, TemplateView):
    """صفحه ارتقا — امکانات ربات برای کاربران بدون لایسنس."""
    template_name = 'workspace/upgrade.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and has_active_bot_license(request.user):
            next_url = request.GET.get('next', '').strip()
            if next_url and next_url.startswith('/workspace'):
                return redirect(next_url)
            return redirect('workspace:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        feature_key = self.request.GET.get('feature', '').strip()
        ctx['feature'] = BOT_LOCKED_FEATURES.get(feature_key)
        ctx['feature_key'] = feature_key
        ctx['bot_features'] = BOT_LOCKED_FEATURES
        ctx['bot_buy_url'] = get_bot_product_buy_url()
        ctx['next_url'] = self.request.GET.get('next', '')
        return ctx


# ─── API ──────────────────────────────────────────────────────────────────────

class BenchmarkAPIView(DatasetOwnerMixin, View):
    def get(self, request, dataset_id, listing_id):
        dataset = self.get_dataset()
        listing = get_object_or_404(dataset.listings, pk=listing_id)
        df = listings_to_dataframe(dataset.listings.all())
        result = benchmark_listing(listing, df)
        return JsonResponse(result)


class OnboardingCompleteView(WorkspaceLoginMixin, View):
    """ثبت اتمام یا رد تور آموزشی میزکار."""

    def post(self, request):
        settings_obj = get_or_create_settings(request.user)
        if not settings_obj.onboarding_completed:
            settings_obj.onboarding_completed = True
            settings_obj.save(update_fields=['onboarding_completed', 'updated_at'])
        return JsonResponse({'ok': True})
