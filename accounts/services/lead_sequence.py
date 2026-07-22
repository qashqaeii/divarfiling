"""Scheduler توالی سه‌مرحله‌ای جذب سرنخ."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from accounts.models import CampaignEnrollment, CampaignStep, LeadCampaign
from accounts.services.lead_campaign_send import send_step_message


def due_enrollments_for_step(campaign: LeadCampaign, step: CampaignStep):
    now = timezone.now()
    qs = CampaignEnrollment.objects.filter(
        campaign=campaign,
        status=CampaignEnrollment.Status.ACTIVE,
        current_step_number__lt=step.step_number,
    ).select_related('lead', 'assigned_variant')

    if step.step_number == 1:
        return qs.filter(current_step_number=0)

    # بعد از پیام قبلی: enrolled_at یا last_message_at + delay
    delay = timedelta(days=step.delay_days)
    return qs.filter(
        Q(last_message_at__lte=now - delay)
        | Q(last_message_at__isnull=True, enrolled_at__lte=now - delay),
        current_step_number=step.step_number - 1,
    )


def run_acquisition_sequence(
    *,
    campaign_id: Optional[int] = None,
    limit_per_step: int = 200,
    request=None,
) -> dict:
    campaigns = LeadCampaign.objects.filter(
        kind=LeadCampaign.Kind.ACQUISITION,
        status__in=(LeadCampaign.Status.PILOT, LeadCampaign.Status.ACTIVE),
    )
    if campaign_id:
        campaigns = campaigns.filter(pk=campaign_id)

    report = []
    for campaign in campaigns:
        steps = list(campaign.steps.filter(is_active=True).order_by('step_number'))
        camp_stats = {'campaign_id': campaign.pk, 'steps': {}}
        for step in steps:
            due = list(due_enrollments_for_step(campaign, step)[:limit_per_step])
            accepted = failed = skipped = 0
            for enroll in due:
                msg = send_step_message(enrollment=enroll, step=step, request=request)
                if msg.status == msg.Status.PROVIDER_ACCEPTED:
                    accepted += 1
                elif msg.status == msg.Status.FAILED:
                    failed += 1
                else:
                    skipped += 1
            camp_stats['steps'][step.step_number] = {
                'due': len(due),
                'accepted': accepted,
                'failed': failed,
                'skipped': skipped,
            }
        report.append(camp_stats)
    return {'campaigns': report}
