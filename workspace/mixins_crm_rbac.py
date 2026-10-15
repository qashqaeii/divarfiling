"""Mixins محدودیت CRM هنگام agency_rbac_v2 — بدون اثر وقتی flag خاموش است."""
from __future__ import annotations

from workspace.services.crm_rbac_guard import (
    assert_crm_contracts_access_allowed,
    assert_crm_deals_access_allowed,
    assert_crm_finance_dashboard_allowed,
)


class CRMDealsAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        assert_crm_deals_access_allowed(request.user)
        return super().dispatch(request, *args, **kwargs)


class CRMContractsAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        assert_crm_contracts_access_allowed(request.user)
        return super().dispatch(request, *args, **kwargs)


class CRMFinanceDashboardAccessMixin:
    def dispatch(self, request, *args, **kwargs):
        assert_crm_finance_dashboard_allowed(request.user)
        return super().dispatch(request, *args, **kwargs)
