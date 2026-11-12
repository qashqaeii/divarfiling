# DivarFiling Admin Premium V2 — Execution Ledger

**Repository:** `qashqaeii/divarfiling` / `main`
**Baseline revision:** `b6b49f7662def152cadb81de3d0a0a212f39a16f`
**Coverage:** 23 sidebar destinations, nested routes, dialogs and APIs, plus Django Admin workflows.

## Operating contract

- For each `continue`, start from the latest `main` and this ledger, and implement the next coherent, dependency-aware slice.
- Each slice must consider domain logic, data correctness, authorization, error handling, IA, premium RTL UX, mobile behaviour and performance — never only surface styling.
- Preserve existing working functionality. Apply the smallest safe coherent change, with focused regression tests and a single atomic commit.
- Test with a disposable database. Never mutate Production records, send SMS, deploy, or run a data migration without separate authorization.
- Run `python manage.py check` and relevant Django tests when an executable runtime is available; otherwise explicitly report them as unexecuted.
- On completion, report only the result, modified scope, test status, commit SHA, remaining risk and next slice.

## Roadmap (in priority order)

| ID | Scope | Done when | State |
|---|---|---|---|
| 00 | Baseline map, deterministic bugs, sensitive permissions | Confirmed regressions fixed and tests added | 00A committed; 00B prepared; runtime verification open |
| 01 | Revenue/licensing data fidelity and access control | Payment, fulfilment and renewals reconcile in test fixtures; access policy audited | Pending |
| 02 | Shared premium RTL design system and navigation architecture | Shared UI primitives; predictable navigation; accessible/responsive | Pending |
| 03 | Action-first command center | Reliable KPI hierarchy, prioritized queues, direct drilldowns | Pending |
| 04 | Sales/orders/payment workflows | Single auditable payment-to-entitlement flow and failure recovery | Pending |
| 05 | Licenses, renewals and device seats | Transparent lifecycle and safe entitlement operations | Pending |
| 06 | Unified user 360° | Journey across orders, devices, usage and support | Pending |
| 07 | Support, operations, activity and forum | Triage queues, moderation, health and incident tracking | Pending |
| 08 | Growth, funnels, cohorts and plan conversion | Reconciled denominators and actionable drilldowns | Pending |
| 09 | Marketing, recovery and lead acquisition | Safe automation, attribution, suppression and send limits | Pending |
| 10 | Management assistant and AI | Explainable suggestions and controlled, logged actions | Pending |
| 11 | Windows, Android and CRM analytics | Trustworthy platform metrics and friendly data tables | Pending |
| 12 | Articles, academy and systematic publishing | Quality gates, clean content lifecycle, publishing controls | Pending |
| 13 | Affiliates, exports and ancillary admin features | Financial integrity, scoped exports and consistent UI | Pending |
| 14 | Final mobile, security, performance and regression sweep | All reviewed critical flows tested, no unresolved P0 issues | Pending |

## Phase 00A: confirmed issues and changes

1. `admin_forum.html` used `admin_content` instead of the actual base template's `admin_panel_content`; render a useful forum overview and direct superusers to moderation records.
2. Forum sidebar link did not expand the Operations group.
3. Articles and Systematic Publishing shared one active sidebar ID.
4. Full DB backup endpoint permitted any `is_staff` user. Restrict it to active staff superusers and remove the download UI for other staff. This protects the endpoint itself, not just the button.
5. Add regression tests for the forum page, navigation state, superuser access and staff denial. Do not change orders, entitlements, migrations or user data.

## Phase 00B: export authorization and KPI semantics

- `AdminExportView` no longer trusts `is_staff` alone: each registered report is authorized by its category and required Django model-view permissions, with default-deny for the finance and AI analytics categories. `users_management` is superuser-only.
- Order exports require `shop.view_order` AND `accounts.view_user`; licence exports require `licenses.view_license` AND `accounts.view_user`; support requires `workspace.view_ticket` and `accounts.view_user`; growth journeys require `accounts.view_growthjourney` and `accounts.view_user`. Plain staff cannot export any personal reports. Staff with only user-view permission receive only user-scoped exports.
- The authorization check runs before report construction; successful export HTTP responses have private/no-store and no-sniff headers. Export links are hidden on Sales, Users and Licenses centers when unauthorized. Reports catalog is filtered before executing row-count queries to reduce needless exposure and load.
- CSV and XLSX writers treat formula-like user text as plain text (formula-injection protection); numeric money remains numeric.
- `new_users` export rows and catalog count now use the same calendar-day boundary as `_new_users_for_period`, instead of a rolling 24-hour interval.
- Added permission, endpoint-denial, CSV/XLSX safety and calendar-day KPI contract regression tests. Updated existing view tests for the new export policy.
- No database migrations, SMS, payments, production writes or deployments.

### Security/operations policy to follow up

- The export authorization only protects `admin-panel/export/<key>/`; other staff JSON endpoints, e.g. user-management details, still need independent role review.
- Financial mutations such as approve/reject card transfer, withdrawal approvals and SMS send must receive their own action-level permission design in phase 01.
- Assign model-view permissions deliberately to delegated staff; this change intentionally changes access to exports for plain staff.
- `new_users` and sales KPIs have alignment tests, but the full timezone definition and paid-order/fulfilment reconciliation still require a disposable database integration run.

## Known gaps and next work (01)

- Finalize the role matrix for remaining sensitive endpoints (user JSON, card-transfer approval, marketing/SMS, withdrawals, forum and service rollout).
- Audit paid-order, licence fulfilment and renewal invariants with representative database fixtures.
- Review redirection and exceptions at moderation and backup operations; audit unauthorized access logs.
- Complete the route/action inventory and the dependency-based P0 list before redesigning information hierarchy.
- Run focused tests with dependencies and a disposable DB; add suitable CI only after understanding the target test settings.

**Execution limitation:** GitHub connector reads and commits source but cannot execute the Django test suite. The available local container cannot access GitHub over the network and has no Django installed. This is explicitly **not** a passing runtime/CI result. Suggested validation:

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_export_security accounts.tests.test_admin_exports_center accounts.tests.test_admin_panel_phase1 accounts.tests.test_admin_sales_center accounts.tests.test_admin_licenses_center accounts.tests.test_admin_panel_shell accounts.tests.test_admin_database_backup --keepdb
```

Use an isolated local/staging PostgreSQL test database; do not point these tests at Production.
