"""ویوهای بخش آژانس — دعوت عمومی، قفل اشتراک، onboarding."""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from accounts.phone_utils import normalize_phone
from workspace.mixins_agency import AgencyHubAccessMixin, AgencyOwnerRequiredMixin
from workspace.services.agency_entitlement import (
    CONSENT_VERSION_CURRENT,
    get_subscription_for_agency,
)
from workspace.services.agency_invitations import (
    _mask_phone,
    accept_agency_invitation,
    decline_agency_invitation,
    get_invitation_by_token,
    invitation_accept_allowed,
)
from workspace.services.agency_onboarding import (
    create_or_link_agency,
    mark_agency_onboarding_complete,
    onboarding_context,
    resolve_onboarding_step,
)
from workspace.services.agency_seats import assign_seat_to_member


class AgencyLockedView(LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/locked.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['agency_buy_url'] = reverse('shop:buy') + '#agency-plans'
        return ctx


class AgencyInviteAcceptView(View):
    template_name = 'workspace/crm/agency/invite_accept.html'

    def get(self, request, token):
        invitation = get_invitation_by_token(token)
        if not invitation:
            return render(request, self.template_name, {
                'error': 'لینک دعوت نامعتبر یا منقضی شده است.',
            })
        ok, msg = invitation_accept_allowed(invitation)
        if not ok and invitation.status == invitation.STATUS_PENDING:
            return render(request, self.template_name, {
                'error': msg,
                'invitation': invitation,
                'agency': invitation.agency,
            })
        if invitation.status != invitation.STATUS_PENDING:
            return render(request, self.template_name, {
                'error': 'این دعوت قبلاً پاسخ داده شده است.',
                'invitation': invitation,
            })
        masked = _mask_phone(invitation.phone)
        user_ok = False
        if request.user.is_authenticated:
            user_phone = normalize_phone(request.user.phone or request.user.username)
            user_ok = user_phone == normalize_phone(invitation.phone)
        return render(request, self.template_name, {
            'invitation': invitation,
            'agency': invitation.agency,
            'inviter_name': invitation.inviter.get_full_name() or invitation.inviter.phone,
            'masked_phone': masked,
            'consent_version': CONSENT_VERSION_CURRENT,
            'token': token,
            'user_authenticated': request.user.is_authenticated,
            'user_phone_matches': user_ok,
        })

    def post(self, request, token):
        invitation = get_invitation_by_token(token)
        if not invitation:
            messages.error(request, 'لینک دعوت نامعتبر است.')
            return redirect('accounts:login')

        if not request.user.is_authenticated:
            messages.info(request, 'برای پاسخ به دعوت ابتدا وارد شوید یا ثبت‌نام کنید.')
            return redirect(f"{reverse('accounts:login')}?next={request.path}")

        action = request.POST.get('action', '')
        if action == 'decline':
            try:
                decline_agency_invitation(invitation, request.user)
                messages.success(request, 'دعوت رد شد.')
                return render(request, self.template_name, {'declined': True, 'invitation': invitation})
            except ValueError as exc:
                messages.error(request, str(exc))

        if action == 'accept':
            consent = request.POST.get('data_consent') == '1'
            try:
                accept_agency_invitation(invitation, request.user, consent_acknowledged=consent)
                messages.success(request, f'به آژانس {invitation.agency.name} پیوستید.')
                return redirect('workspace:crm_team')
            except ValueError as exc:
                messages.error(request, str(exc))

        return self.get(request, token)


class AgencyOnboardingView(AgencyOwnerRequiredMixin, LoginRequiredMixin, TemplateView):
    template_name = 'workspace/crm/agency/onboarding.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ob = onboarding_context(self.request.user)
        step = self.request.GET.get('step')
        if not step:
            step = str(ob['step'])
        from workspace.services.agency_seats import list_available_seats
        ctx.update(ob)
        ctx['step'] = step
        ctx['team_url'] = reverse('workspace:crm_team')
        agency = ob.get('agency')
        ctx['available_seats'] = list_available_seats(self.request.user, agency) if agency else []
        return ctx

    def post(self, request):
        action = request.POST.get('action', '')
        step = request.POST.get('step', '1')

        if action == 'create_agency':
            name = request.POST.get('name', '').strip()
            use_existing = request.POST.get('use_existing') == '1'
            try:
                create_or_link_agency(request.user, name, use_existing=use_existing)
                messages.success(request, 'آژانس آماده شد.')
                return redirect(f"{reverse('workspace:agency_onboarding')}?step=2")
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect(f"{reverse('workspace:agency_onboarding')}?step=1")

        if action == 'invite_phones':
            phones_raw = request.POST.get('phones', '')
            phones = [p.strip() for p in phones_raw.replace(',', '\n').splitlines() if p.strip()]
            from workspace.services.agency_invitations import create_bulk_agency_invitations
            result = create_bulk_agency_invitations(request.user, phones, request=request)
            if result['created']:
                messages.success(request, f'{len(result["created"])} دعوت ارسال شد.')
            for err in result['errors']:
                messages.warning(request, f'{err["phone"]}: {err["error"]}')
            return redirect(f"{reverse('workspace:agency_onboarding')}?step=2")

        if action == 'assign_seat':
            try:
                assign_seat_to_member(
                    request.user,
                    int(request.POST.get('license_id', 0)),
                    int(request.POST.get('member_user_id', 0)),
                )
                messages.success(request, 'لایسنس تخصیص داده شد.')
            except Exception as exc:
                messages.error(request, str(exc))
            return redirect(f"{reverse('workspace:agency_onboarding')}?step=3")

        if action == 'finish':
            ob = onboarding_context(request.user)
            if ob.get('agency'):
                mark_agency_onboarding_complete(ob['agency'])
            return redirect(f"{reverse('workspace:agency_onboarding')}?step=4")

        if action == 'skip_to_dashboard':
            ob = onboarding_context(request.user)
            if ob.get('agency'):
                mark_agency_onboarding_complete(ob['agency'])
            return redirect(f"{reverse('workspace:crm_team')}?tab=members")

        return redirect(f"{reverse('workspace:agency_onboarding')}?step={step}")
