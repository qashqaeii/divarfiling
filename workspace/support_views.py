"""Viewهای تیکت پشتیبانی workspace."""
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, ListView, TemplateView, View

from workspace.forms import TicketCreateForm, TicketReplyForm
from workspace.mixins import WorkspaceLoginMixin
from workspace.models import Ticket
from workspace.services.support_tickets import (
    add_user_reply,
    close_ticket,
    create_ticket,
    filter_user_tickets,
    get_user_ticket_stats,
    mark_ticket_read_by_user,
    reopen_ticket,
)
from workspace.support_constants import TICKET_PRIORITY_CHOICES, TICKET_STATUS_CHOICES


def _user_ticket(user, ticket_id):
    return get_object_or_404(Ticket, pk=ticket_id, user=user)


class SupportTicketListView(WorkspaceLoginMixin, ListView):
    template_name = 'workspace/support/list.html'
    context_object_name = 'tickets'
    paginate_by = 15

    def get_queryset(self):
        return filter_user_tickets(
            self.request.user,
            status=self.request.GET.get('status', '').strip(),
            priority=self.request.GET.get('priority', '').strip(),
            q=self.request.GET.get('q', '').strip(),
        )

    def get_context_data(self, **kwargs):
        ticket_form = kwargs.pop('ticket_form', None)
        ctx = super().get_context_data(**kwargs)
        ctx['stats'] = get_user_ticket_stats(self.request.user)
        ctx['status_filter'] = self.request.GET.get('status', '').strip()
        ctx['priority_filter'] = self.request.GET.get('priority', '').strip()
        ctx['search_q'] = self.request.GET.get('q', '').strip()
        ctx['status_choices'] = TICKET_STATUS_CHOICES
        ctx['priority_choices'] = TICKET_PRIORITY_CHOICES
        ctx['ticket_form'] = ticket_form or TicketCreateForm()
        ctx['open_modal'] = self.request.GET.get('open', ctx.get('open_modal', ''))
        return ctx


class SupportTicketCreateView(WorkspaceLoginMixin, FormView):
    template_name = 'workspace/support/create.html'
    form_class = TicketCreateForm
    success_url = reverse_lazy('workspace:support_list')

    def form_valid(self, form):
        ticket = create_ticket(
            user=self.request.user,
            subject=form.cleaned_data['subject'],
            category=form.cleaned_data['category'],
            priority=form.cleaned_data['priority'],
            body=form.cleaned_data['body'],
            attachment=form.cleaned_data.get('attachment'),
        )
        messages.success(
            self.request,
            f'تیکت {ticket.ticket_number} با موفقیت ثبت شد. به‌زودی پاسخ می‌دهیم.',
        )
        self.success_url = reverse('workspace:support_detail', kwargs={'ticket_id': ticket.pk})
        return super().form_valid(form)

    def form_invalid(self, form):
        if self.request.POST.get('source') == 'modal':
            list_view = SupportTicketListView()
            list_view.request = self.request
            list_view.args = self.args
            list_view.kwargs = {}
            list_view.object_list = list_view.get_queryset()
            ctx = list_view.get_context_data(ticket_form=form)
            ctx['open_modal'] = 'modal-ticket-create'
            return TemplateResponse(self.request, list_view.template_name, ctx)
        return super().form_invalid(form)


class SupportTicketDetailView(WorkspaceLoginMixin, TemplateView):
    template_name = 'workspace/support/detail.html'

    def get_ticket(self):
        if not hasattr(self, '_ticket'):
            self._ticket = _user_ticket(self.request.user, self.kwargs['ticket_id'])
        return self._ticket

    def get(self, request, *args, **kwargs):
        ticket = self.get_ticket()
        mark_ticket_read_by_user(ticket)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ticket = self.get_ticket()
        ctx['ticket'] = ticket
        ctx['messages_list'] = (
            ticket.messages.filter(is_internal=False)
            .select_related('author')
            .prefetch_related('attachments')
        )
        ctx['reply_form'] = TicketReplyForm()
        ctx['attachments'] = ticket.attachments.select_related('message')
        return ctx


class SupportTicketReplyView(WorkspaceLoginMixin, View):
    http_method_names = ['post']

    def post(self, request, ticket_id):
        ticket = _user_ticket(request.user, ticket_id)
        form = TicketReplyForm(request.POST, request.FILES)
        if not form.is_valid():
            for err in form.errors.values():
                messages.error(request, err.as_data()[0].message if err else 'خطا در ارسال پیام.')
            return redirect('workspace:support_detail', ticket_id=ticket.pk)
        if ticket.is_closed:
            messages.warning(request, 'این تیکت بسته شده است. برای ادامه، ابتدا آن را باز کنید.')
            return redirect('workspace:support_detail', ticket_id=ticket.pk)
        try:
            add_user_reply(
                ticket=ticket,
                user=request.user,
                body=form.cleaned_data['body'],
                attachment=form.cleaned_data.get('attachment'),
            )
            messages.success(request, 'پیام شما ارسال شد.')
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect('workspace:support_detail', ticket_id=ticket.pk)


class SupportTicketCloseView(WorkspaceLoginMixin, View):
    http_method_names = ['post']

    def post(self, request, ticket_id):
        ticket = _user_ticket(request.user, ticket_id)
        if ticket.is_closed:
            messages.info(request, 'این تیکت قبلاً بسته شده است.')
        else:
            close_ticket(ticket=ticket, by_user=request.user, staff=False)
            messages.success(request, 'تیکت بسته شد.')
        return redirect('workspace:support_detail', ticket_id=ticket.pk)


class SupportTicketReopenView(WorkspaceLoginMixin, View):
    http_method_names = ['post']

    def post(self, request, ticket_id):
        ticket = _user_ticket(request.user, ticket_id)
        if not ticket.is_closed:
            messages.info(request, 'این تیکت در حال حاضر باز است.')
        else:
            reopen_ticket(ticket=ticket)
            messages.success(request, 'تیکت مجدداً باز شد.')
        return redirect('workspace:support_detail', ticket_id=ticket.pk)
