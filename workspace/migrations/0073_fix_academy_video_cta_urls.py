"""اصلاح URLهای CTA آکادمی بدون پاک‌سازی curriculum."""
from django.db import migrations


def fix_academy_cta_urls(apps, schema_editor):
    AcademyVideo = apps.get_model('workspace', 'AcademyVideo')
    from workspace.academy.cta import normalize_stored_action_url

    legacy_broken = ('/shop/', '/shop')
    for video in AcademyVideo.objects.exclude(action_url='').only('id', 'slug', 'action_url'):
        current = (video.action_url or '').strip()
        if current not in legacy_broken and current == normalize_stored_action_url(current):
            continue
        target = normalize_stored_action_url(current)
        if target and target != current:
            AcademyVideo.objects.filter(pk=video.pk).update(action_url=target)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('workspace', '0072_academyvideo_description'),
    ]

    operations = [
        migrations.RunPython(fix_academy_cta_urls, noop_reverse),
    ]
