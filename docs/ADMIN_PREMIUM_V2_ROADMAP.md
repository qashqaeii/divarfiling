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
| 01 | Revenue/licensing data fidelity and access control | Payment, fulfilment and renewals reconcile in test fixtures; access policy audited | 01A–01C committed; 01D sensitive admin access guarded; runtime validation remains OPEN |
| 02 | Shared premium RTL design system and navigation architecture | Shared UI primitives; predictable navigation; accessible/responsive | 02A–02B committed; 02C functional table/filter fixes prepared; runtime/browser QA remains open |
| 03 | Action-first command center | Reliable KPI hierarchy, prioritized queues, direct drilldowns | 03A command decision integrity prepared; remaining Command UX and integration QA open |
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

## Phase 01A — financial decisions and outbound-message permission boundaries

- `can_review_card_transfer`: active staff superuser OR delegated staff holding BOTH `shop.change_cardtransfersubmission` and `shop.change_order`; all other staff are denied before querying the receipt.
- `can_send_admin_sms`: active staff superuser OR delegated staff holding BOTH `accounts.change_marketingcampaign` and `accounts.add_smsmessagelog`. Applies to Marketing POST, Android update SMS POST/recipient-preview, Phonebook sync, Management Assistant send, automation toggle/manual run/configuration/test SMS. All permissions use Django's existing model permissions; no migration is needed.
- Action buttons and modals in Sales/Support, send controls on Android/Marketing, and mutation controls on Management Assistant reflect the same restrictions. Read-only managers retain a useful analytics view rather than receiving misleading working buttons.
- Direct Excel links in Sales, Support, Android and card-transfer review are only shown if the same per-report export role grants access; the endpoint remains the authoritative check.
- Card-transfer `next` URLs are verified as same-host safe paths to block open external redirects (`//evil.example`).
- Added negative/positive permission and redirect tests plus updated the previously staff-permissive view test fixtures. Existing service-level card-transfer tests assert atomic payment/fulfilment behavior and retry safety, but are not yet run in this environment.
- This slice performs no SMS sends, payment approvals, database writes, migrations or production deployments.

### Phase 01A verification contract

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_sensitive_actions accounts.tests.test_admin_management_assistant accounts.tests.test_admin_android_center accounts.tests.test_admin_support_center accounts.tests.test_marketing shop.tests.test_card_transfer_workflow --keepdb
```

Expected: nonprivileged staff receives HTTP 403 on sensitive POSTs; delegated/owner operators reach handler validation; finance approval remains idempotent; check all read-only screens for hidden actions and consistent RTL layout. **Do not claim this test suite passed until run against an isolated DB.**

## Phase 01B — local dates, multi-license renewals, safe payment reconciliation

- All command-center calendar-day and "today" KPI date ranges use `timezone.localdate()`, not the UTC date from `timezone.now().date()`. The overview's uptime day calculation also uses the business-local day.
- Formal renewal classification now includes both `Order.renewal_license` (legacy/single-key) and any `OrderRenewalItem` (multi-key). An `Exists` predicate avoids multiplying order counts when one order renews multiple keys. The licensing center and global summary use one helper.
- Gateway mismatch recovery only attempts Zibal verification for Zibal-method transactions. Legacy `CARD-...` transaction IDs are excluded even if their method was miscoded.
- The gateway reconciliation queue is processed oldest-first and handles one payment-state update failure without abandoning other transactions. A separate fulfilment error cannot retroactively hide a repaired paid-state mismatch; later reconciliation handles pending fulfilment.
- Six regression tests cover Tehran midnight across UTC boundaries, paid-order KPI dates, multi- and single-key renewal classification, payment-method filtering, partial failure isolation and fulfillment failure accounting.
- No production records, SMS, external payment verification, migrations or deployments were run; tests were added but not executed in this connector-only environment.

### Phase 01B test commands (isolated database only)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_financial_integrity accounts.tests.test_admin_licenses_center accounts.tests.test_admin_panel_phase1 accounts.tests.test_admin_sales_center shop.tests.test_payment shop.tests.test_card_transfer_workflow --keepdb
```

Treat any passing static source checks as different from Django test execution. Payment reconciliation paths must not be exercised against live gateways in tests; patched gateway calls are used in added tests.

## Phase 01C — administrator integrity diagnostics and identity boundaries

- Add `admin_integrity_diagnostics.py` to describe four *read-only*, all-time anomaly cohorts in the sales center: paid without `paid_at`, paid/new-key orders marked fulfilled with fewer issued licenses than requested, Zibal transaction paid but order still unpaid (excluding `CARD-` IDs), and paid orders with pending/partial/failed fulfillment.
- Use a correlated issued-license count and `Exists` for renewal items to catch under-issued multi-seat purchases and avoid false positives for multi-key renewals; legacy single-key renewals are explicitly excluded from the new-key cohort. Warning categories can overlap; the UI does not present their sum as unique affected orders.
- The sales dashboard shows a concise anomaly overview only to authorized financial readers. A selected warning reveals at most five order rows, with an order-specific Django Admin link only for users holding `shop.view_order`. There is no diagnosis POST, gateway call, automatic retry, license issuance, or migration.
- New `can_view_financial_integrity` permission: active superusers or staff holding ALL THREE `shop.view_order`, `licenses.view_license` and `accounts.view_user`.
- User-management list and individual detail JSON APIs now require active staff superusers or delegated staff holding ALL of `accounts.view_user`, `shop.view_order` and `licenses.view_license`. Deny *before* querying any personal data; successful responses are private/no-store. The Users page keeps aggregates, but hides personally identifiable tables, the full dossier drawer and its JS when unauthorized; direct output links also respect export rules.
- Add ten scenario tests for authorization, no-cache, view isolation, four financial diagnostic cohorts, card-transfer exclusion, invalid filters and read-only previews; align existing authorized test fixtures. Tests are not executed by the GitHub connector.

### Phase 01C verification (isolated database)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_integrity_diagnostics accounts.tests.test_admin_users_management accounts.tests.test_admin_users_center accounts.tests.test_admin_sales_center accounts.tests.test_admin_panel_phase1 accounts.tests.test_admin_financial_integrity --keepdb
```

**Expected:** staff without dossier permissions sees KPI-only users center and receives HTTP 403 from both personal JSON endpoints; fully authorized roles see records; integrity previews are bounded and never mutate payment or entitlement state.

## Phase 01D — privileged admin operations (targeted security slice)

- Preserve existing read-only lead-acquisition overview for staff. **All** lead-center POST mutations (imports, edits, campaign sends, scheduling/automation, template changes) now check the existing `can_send_admin_sms` role before the dispatch. The main campaign detail POST is protected too.
- The async send-start, send-tick and bulk-template endpoints, plus personal Divar session/PhoneDetector line endpoints, use a single `LeadSmsOperatorRequiredMixin`. For the latter sensitive session/line endpoints, GET data is operator-only as well. Public click tracking and aggregate funnel JSON were not changed.
- The lead pages display a concise read-only notice to staff who lack a delegated SMS operator role. Full disablement/streamlined presentation will be handled in the design-system UX phases, not through a second arbitrary CSS redesign now.
- Lock financial Django Admin mutation privileges for `AffiliateSale`, `AffiliatePayout`, `Wallet`, `WalletTransaction`, and `Withdrawal` to authenticated active staff superusers; delegated viewers retain Django view permissions. Generic model change permissions **alone** cannot approve payouts.
- Withdrawal requests cannot be created/deleted by Django Admin. Existing wallet, amount, recipient/bank fields and withdrawal state are immutable via the change form; state transitions must go through the predefined owner-only admin actions, which now log successful changes with `ModelAdmin.log_change`.
- Added nine focused regression cases for lead operator denies and grants, protected automation/session routes, read-only page, blocked withdrawal action, superuser settle idempotency/audit history, and prevention of forged withdrawal state form changes.
- Existing lead view tests with intentionally triggered bulk operations were updated to use the superuser fixture; view-only staff can still browse.
- The existing forum moderation views already use `ForumModerateRequiredMixin` and `user_can_moderate_forum`. They were **not** rewritten in this slice.
- **Deferred risk:** `Withdrawal.approve()/complete()` and `Wallet.deduct_balance()` still have concurrency/atomicity weaknesses in the model layer. Touching that financial ledger without an executable, isolated PostgreSQL test environment would be unsafe. This must be covered by a dedicated transactional test/migration-safe fix before permitting concurrent payout workers or deploying new automatic settlement operations.
- Source editing/commit is not proof of a passing Django suite. No production payments, SMS, license grants, migrations or deployments occurred.

### Validation commands (disposable database only)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_lead_finance_permissions accounts.tests.test_lead_acquisition accounts.tests.test_automation_message_templates accounts.tests.test_admin_affiliates_center affiliates.tests.test_referral_flow --keepdb
```

## Phase 02A — one shared premium shell foundation (no page rewrites)

- Add `static/css/mizkar-admin-v2-foundations.css` **after** existing module styles in the common shell. A single scoped token layer aligns the light/dark palette, surface hierarchy, action colors, data density, header, sidebar, KPI cards, data tables, focus states and mobile layout across all 23 management entry pages without individually editing business dashboards.
- Add a keyboard-accessible skip link and a real focusable `#admin-main` target; keep one semantic `main` per management page.
- Give all 23 sidebar destinations stable `aria-current="page"` on the actual server-selected link, plus explicit `aria-controls` for each of the six collapsible groups.
- Fix the global time-window navigation: changing `days` preserves other query arguments such as `audit`, `focus`, search filters and repeated query keys. Switching to `all` drops `compare` by design.
- Remove the obsolete dashboard scroll handler which incorrectly re-marked *other pages* as active sidebar links; the current destination is now server-authoritative. The mobile drawer handles Tab wrapping, Escape, focus restoration, and `aria-expanded` synchronisation.
- Provide focus-visible outlines, 44px touch targets for the mobile drawer, color semantics in dark mode, reduced-motion support and forced-colors navigation affordances.
- Add five focused tests for range-link preservation, sidebar semantics, key pages' shared asset loading and CSS/JS accessibility hooks.
- No business KPI implementation, payment, license, database, SMS, model migration, or Production deployment changed. Avoid cosmetic churn in dashboard templates until shared components are validated.

### Phase 02A validation

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_premium_v2_foundations accounts.tests.test_admin_panel_shell accounts.tests.test_admin_sales_center accounts.tests.test_admin_users_center --keepdb
```

Browser QA needed at 390px, 768px, 1024px and desktop widths in light/dark themes: open/close the menu by click, Tab, Shift+Tab and Escape; switch date range with `audit`/search filters; verify exactly one active sidebar destination. The GitHub connector cannot execute the Django suite or interact with a browser.

## Phase 02B — information hierarchy and shared KPI component on four hubs

- **Command, Sales, Users, Licenses** now share `admin_prime_kpi_card.html` for the same value/delta/status/empty/sparkline contract, preserving existing chart IDs and API datasets. The server renders real KPI values as fallback; it never shows a fake zero for unavailable cohort data.
- Keep the deliberate first-screen sequence: current pulse → priority action queue / revenue or activity trend → period KPIs → deeper diagnostics, tables and exports. A shared CSS layout makes actionable queues appear **before** large charts on one-column/mobile screens without duplicating HTML.
- Sales financial-integrity anomalies move from a four-card block **above** today's stats into an accessible, collapsible details section **after** the top-line KPIs. A subtle drilldown remains beside the action queue only when warnings exist. Targeted `audit` queries or hash deep links automatically open the details.
- Use one *stable, shared* priority sort for Sales, Users and Licenses: critical first, then high, medium, and opportunities, breaking ties by affected count. Command was already priority-sorted; no duplicate implementation.
- On read-only Users dashboards, remove search buttons/action destinations pointing to protected personal tables. Aggregate pulse remains visible but is rendered as a non-clickable metric if its destination requires the dossier role.
- The action-queue badge explicitly represents the number of **issue categories**, not the total number of affected records; each row still shows its own affected count. Center pulse subtitles use Persian wording rather than unexplained “Snapshot”.
- Add eight regression scenarios for deterministic priority sorting, SSR KPI fallback and pending states, CSS mobile order, four-center shared components, folded Sales audit, and read-only Users navigation.
- No changes to financial calculations, campaign sending, data migrations, live operations, or production deployment.

### Phase 02B validation (isolated database)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_premium_v2_hierarchy accounts.tests.test_admin_premium_v2_foundations accounts.tests.test_admin_sales_center accounts.tests.test_admin_users_center accounts.tests.test_admin_licenses_center accounts.tests.test_admin_integrity_diagnostics --keepdb
```

**Open gate:** Browser QA at mobile/tablet/desktop widths, RTL focus, anchor-to-expanded financial audit, and the accumulated Django suite. Static assertions and source validation are not evidence that Django passed.

## Phase 02C — operational table filters and recoverable AJAX UX

- Correct a confirmed backend/frontend mismatch in the user-management table: the UI sends `license=yes/no`, `windows=downloaded/activated/launched`, and `android/datasets/crm/paid=yes/no` but the backend previously recognized different values. Both canonical UI values and legacy API filter values now work, with Windows options matching distinct annotated facts.
- Improve AJAX list behavior without changing its API: stale response guards, stable filter reset, explicit loading/result/error status, a retry action for failures, proper one-page pager hiding, and empty-state reset. A filter change clears any waiting search debounce to avoid resurrecting stale results.
- Harden user detail drawer error handling, asynchronous close behavior, focus return, Escape and Tab confinement, plus accessible dialog semantics. The drawer never resurrects a stale response after being closed.
- License center table links to Excel exports are now permission-aware, and its "Users without license" cross-page drilldown only appears when the manager has access to the destination. The latest renewal table classifies multi-key renewal items as formal renewals rather than incorrectly labeling them a new key.
- Sales fulfillment table now offers the Django Admin order list link only to users with `shop.view_order`; internal route resolution replaces a fragile hard-coded URL.
- User table includes a live-result status, filter-reset control and explicit search label, styled by the existing shared Premium V2 stylesheet without changing the layout of every page.
- Nine Django test cases are added for live UI/backend filter contracts (including compound queries and legacy filters), non-privileged export links, renewal labels, and retry/focus code hooks.
- No database migrations, production writes, payments, SMS, or new dashboard-only decorative widgets.

### Phase 02C verification (disposable DB)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_premium_v2_tables accounts.tests.test_admin_users_management accounts.tests.test_admin_users_center accounts.tests.test_admin_licenses_center accounts.tests.test_admin_sales_center accounts.tests.test_admin_premium_v2_hierarchy --keepdb
```

**Release gate:** Validate AJAX search, filters, reset, pagination, 403/500 retry, detail drawer and all exports in a browser at mobile and desktop widths; run the Django suite in an isolated database. The connected GitHub tools do not execute these tests.

## Phase 03A — actionable Command Center, accurate queue metrics

- Queue age and count now come from **one aggregate query** instead of two. For nullable message/payment dates, `created_at` is used as a fallback rather than falsely showing “unknown age” or selecting only a newer ticket.
- Alert semantics corrected: a **low SMS balance is a monetary warning, not N affected cases**. The money amount stays in description, the numeric case badge is not rendered, and the CTA becomes “بررسی اعتبار” instead of promising an unsupported top-up action.
- Queue sorting delegates to `prioritize_management_actions` already introduced in 02B; no parallel ranking policy or duplicate rules. Withdrawal CTA says “مشاهده” rather than implying any staff member can approve payouts.
- Command first-screen queue subtitle now conveys *the number of critical/high issue categories*, with a safe empty-state description. No new graphs, notifications, financial mutations or database queries were introduced to create a decorative module.
- Paid-order Excel and the Users/Licenses summary exports respect the exact report authorization policy; non-authorized staff receive ordinary navigation links rather than misleading downloads.
- Owner-only Django Admin shortcut is hidden from delegated staff in Command header and modules, and its unrelated “pending issues” count badge is removed.
- Nine regression tests cover aged tickets lacking last-message timestamps, null paid timestamps, financial-vs-case-count distinction for SMS, deterministic queue links, owner/delegate navigation and authorization, and truthful decision text.
- No changes to actual payment, license, SMS delivery, source event states, database migrations or Production deployment.

### Phase 03A validation (isolated DB, still required)

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_command_center_decisions accounts.tests.test_admin_dashboard accounts.tests.test_admin_panel_phase1 accounts.tests.test_admin_premium_v2_hierarchy accounts.tests.test_admin_export_security --keepdb
```

A browser check must verify responsive Command queue, the no-count SMS alert, RTL focus, authorized download links, drilldowns into the original queues, and light/dark variants. Source-level checks are **not** a green Django/CI result.

## Remaining gates before phase 03B

- Execute the accumulated phase 00–01 Django suites in isolated staging, with real PostgreSQL test DB. Resolve failures once from evidence; avoid speculative edit/revert cycles.
- Audit existing affiliate payout concurrency and run proper DB transaction tests before activating concurrent settlement; no new auto-payout feature was added here.
- Remaining platform privileged operations (forum moderation input limits and service-rollout toggles) should be handled as real, reproducible defects when their module phases arrive.
- Stage 03B next: prioritize any remaining real Command Center regressions from full Django/browser QA and integrate only if reproducible; then proceed to operations and support workflows.



- Continue with remaining privileged operations: affiliate withdrawals in Django Admin, lead-acquisition sends, forum moderation, feature rollout, and role-aware audit logs. User 360° JSON authorization was scoped in 01C.
- Run the new read-only anomaly report against staging fixtures and verified legacy data; compare counts with raw records before treating production data as trustworthy.
- Review redirection and exceptions at moderation and backup operations; audit unauthorized access logs.
- Complete all 23 screen route/action inventory; document current UX and role permission matrix before shared design-system rollout.
- Run focused tests with dependencies and a disposable DB; add suitable CI only after understanding the target test settings.

**Execution limitation:** GitHub connector reads and commits source but cannot execute the Django test suite. The available local container cannot access GitHub over the network and has no Django installed. This is explicitly **not** a passing runtime/CI result. Suggested validation:

```bash
python manage.py check
python manage.py test accounts.tests.test_admin_export_security accounts.tests.test_admin_exports_center accounts.tests.test_admin_panel_phase1 accounts.tests.test_admin_sales_center accounts.tests.test_admin_licenses_center accounts.tests.test_admin_panel_shell accounts.tests.test_admin_database_backup --keepdb
```

Use an isolated local/staging PostgreSQL test database; do not point these tests at Production.
