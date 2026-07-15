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
