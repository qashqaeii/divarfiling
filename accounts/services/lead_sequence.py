"""Scheduler توالی جذب و فعال‌سازی سرنخ."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.db.models import Q
from django.utils import timezone

from accounts.models import CampaignEnrollment, CampaignStep, GrowthJourney, LeadCampaign
from accounts.services.lead_campaign_send import send_step_message


def due_enrollments_for_step(campaign: LeadCampaign, step: CampaignStep):
    now = timezone.now()
    qs = CampaignEnrollment.objects.filter(
        campaign=campaign,
        status=CampaignEnrollment.Status.ACTIVE,
        current_step_number__lt=step.step_number,
    ).select_related('lead', 'assigned_variant', 'user', 'campaign')

    if step.step_number == 1:
        return qs.filter(current_step_number=0)

    delay = timedelta(days=step.delay_days)
    return qs.filter(
        Q(last_message_at__lte=now - delay)
        | Q(last_message_at__isnull=True, enrolled_at__lte=now - delay),
        current_step_number=step.step_number - 1,
    )


def _run_kind_sequence(
    *,
    kind: str,
    campaign_id: Optional[int] = None,
    limit_per_step: int = 200,
    request=None,
) -> dict:
    campaigns = LeadCampaign.objects.filter(
        kind=kind,
        status__in=(LeadCampaign.Status.PILOT, LeadCampaign.Status.ACTIVE),
    )
    if campaign_id:
        campaigns = campaigns.filter(pk=campaign_id)

    report = []
    for campaign in campaigns:
        steps = list(campaign.steps.filter(is_active=True).order_by('step_number'))
        camp_stats = {'campaign_id': campaign.pk, 'kind': kind, 'steps': {}}
        for step in steps:
            due = list(due_enrollments_for_step(campaign, step)[:limit_per_step])
            accepted = failed = skipped = 0
            for enroll in due:
                msg = send_step_message(enrollment=enroll, step=step, request=request)
                if msg.status == msg.Status.PROVIDER_ACCEPTED:
                    accepted += 1
                    if (
                        kind == LeadCampaign.Kind.ACTIVATION
                        and step.step_number >= 2
                        and enroll.lead_id
                    ):
                        _mark_nurture_unpaid(enroll)
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


def _mark_nurture_unpaid(enrollment: CampaignEnrollment) -> None:
    try:
        from accounts.services.growth_journey import transition
        transition(
            phone=enrollment.lead.phone_normalized,
            lead=enrollment.lead,
            user=enrollment.user,
            event_type='no_purchase_window',
            stage=GrowthJourney.Stage.NURTURE_UNPAID,
            metadata={'activation_step': enrollment.current_step_number},
        )
    except Exception:
        pass


def run_acquisition_sequence(
    *,
    campaign_id: Optional[int] = None,
    limit_per_step: int = 200,
    request=None,
) -> dict:
    return _run_kind_sequence(
        kind=LeadCampaign.Kind.ACQUISITION,
        campaign_id=campaign_id,
        limit_per_step=limit_per_step,
        request=request,
    )


def run_activation_sequence(
    *,
    campaign_id: Optional[int] = None,
    limit_per_step: int = 200,
    request=None,
) -> dict:
    from accounts.services.user_activation import get_or_create_default_activation_campaign
    get_or_create_default_activation_campaign()
    return _run_kind_sequence(
        kind=LeadCampaign.Kind.ACTIVATION,
        campaign_id=campaign_id,
        limit_per_step=limit_per_step,
        request=request,
    )
