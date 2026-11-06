"""آمار خلاصه مرکز توسعه."""
from product_hub.models import (
    BugReport,
    FeatureRequest,
    ProductFeature,
    ProductRelease,
)


def get_hub_stats():
    latest = (
        ProductRelease.objects.filter(is_published=True)
        .order_by('-released_at')
        .first()
    )
    feature_qs = ProductFeature.objects.filter(is_published=True)
    return {
        'latest_version': latest.version if latest else '—',
        'latest_released_at': latest.released_at if latest else None,
        'latest_title': latest.title if latest else '',
        'features_active': feature_qs.filter(status='active').count(),
        'features_in_progress': feature_qs.filter(status='in_progress').count(),
        'features_planned': feature_qs.filter(status='planned').count(),
        'features_beta': feature_qs.filter(status='beta').count(),
        'features_total': feature_qs.count(),
        'requests_total': FeatureRequest.objects.filter(is_public=True).count(),
        'requests_open': FeatureRequest.objects.filter(
            is_public=True,
        ).exclude(status__in=('completed', 'rejected')).count(),
        'bugs_resolved': BugReport.objects.filter(status='resolved').count(),
        'bugs_open': BugReport.objects.exclude(status='resolved').count(),
    }


def build_hub_kpi_stats(stats: dict | None = None) -> dict:
    """آمار fl-kpi-pro برای مرکز توسعه — کلیدهای پایه get_hub_stats حفظ می‌شود."""
    base = stats if stats is not None else get_hub_stats()
    total = int(base.get('features_total') or 0)
    active = int(base.get('features_active') or 0)
    in_progress = int(base.get('features_in_progress') or 0)
    planned = int(base.get('features_planned') or 0)
    beta = int(base.get('features_beta') or 0)
    requests_open = int(base.get('requests_open') or 0)
    requests_total = int(base.get('requests_total') or 0)
    bugs_open = int(base.get('bugs_open') or 0)
    bugs_resolved = int(base.get('bugs_resolved') or 0)
    bugs_total = bugs_open + bugs_resolved

    def _share(part: int, denom: int) -> int:
        if not denom:
            return 0
        return int(round((part / denom) * 100))

    mix_segments = []
    for key, label, count in (
        ('active', 'فعال', active),
        ('beta', 'آزمایشی', beta),
        ('in_progress', 'در ساخت', in_progress),
        ('planned', 'به‌زودی', planned),
    ):
        if count <= 0:
            continue
        mix_segments.append({
            'key': key,
            'label': label,
            'count': count,
            'pct': _share(count, total),
        })

    if total:
        hero_bits = []
        if active:
            hero_bits.append(f'{active} فعال')
        if beta:
            hero_bits.append(f'{beta} آزمایشی')
        if in_progress:
            hero_bits.append(f'{in_progress} در ساخت')
        if planned:
            hero_bits.append(f'{planned} به‌زودی')
        hero_meta = ' · '.join(hero_bits) if hero_bits else 'بدون قابلیت منتشرشده'
    else:
        hero_meta = 'هنوز قابلیتی منتشر نشده'

    if in_progress:
        progress_meta = f'{_share(in_progress, total)}٪ قابلیت‌ها در حال ساخت‌اند'
    elif total:
        progress_meta = 'الان چیزی در ساخت نیست'
    else:
        progress_meta = 'نقشه راه هنوز خالی است'

    if requests_open:
        requests_meta = f'{requests_open} پیشنهاد در صف بررسی/توسعه'
    elif requests_total:
        requests_meta = 'همه پیشنهادها بسته شده‌اند'
    else:
        requests_meta = 'اولین پیشنهاد را ثبت کنید'

    if bugs_open:
        bugs_meta = f'{bugs_open} مشکل باز · {bugs_resolved} رفع‌شده'
    elif bugs_resolved:
        bugs_meta = f'همه مشکلات رفع شده‌اند ({bugs_resolved})'
    else:
        bugs_meta = 'هنوز گزارشی ثبت نشده'

    return {
        **base,
        'mix_segments': mix_segments,
        'hero_meta': hero_meta,
        'progress_share': _share(in_progress, total),
        'progress_meta': progress_meta,
        'requests_share': _share(requests_open, requests_total),
        'requests_meta': requests_meta,
        'bugs_share': _share(bugs_open, bugs_total) if bugs_total else 0,
        'bugs_meta': bugs_meta,
    }


def get_roadmap_data():
    features = ProductFeature.objects.filter(is_published=True)
    return {
        'in_progress': list(features.filter(status='in_progress')),
        'planned': list(features.filter(status='planned')),
        'popular_ideas': list(FeatureRequest.objects.filter(
            is_public=True,
            status__in=('approved', 'in_development', 'submitted', 'reviewing'),
        ).order_by('-votes_count', '-created_at')[:12]),
    }


def get_manage_stats():
    return {
        'requests_pending': FeatureRequest.objects.filter(
            status__in=('submitted', 'reviewing'),
        ).count(),
        'requests_dev': FeatureRequest.objects.filter(status='in_development').count(),
        'bugs_open': BugReport.objects.exclude(status='resolved').count(),
        'bugs_critical': BugReport.objects.filter(
            severity='critical',
        ).exclude(status='resolved').count(),
        'releases': ProductRelease.objects.count(),
        'features': ProductFeature.objects.count(),
    }
