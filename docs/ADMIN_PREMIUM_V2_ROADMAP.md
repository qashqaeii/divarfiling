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
| 00 | Baseline map, deterministic bugs, sensitive permissions | Confirmed regressions fixed and tests added | 00A prepared |
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

## Known gaps and next work (00B)

- Audit staff role matrix and plan granular permissions for export endpoints and sensitive managerial operations without breaking support workflows.
- Audit dashboard KPI semantics against paid-order data and licence fulfilment events; build explicit cross-module invariants.
- Review redirection and exceptions at moderation and backup operations.
- Document all 23 view modules and the admin-only tools in a dependency matrix, prioritize P0.
- Run focused tests in an environment with Django, Python dependencies and a disposable database; this repository has no preconfigured `.github/workflows/` CI.

**Execution limitation:** The linked GitHub tool can read and atomically commit source, but cannot execute the Django test suite; static source assertions are not equivalent to runtime tests.
