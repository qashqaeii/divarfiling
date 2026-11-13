# Admin Premium V3 — UI/UX-only execution ledger

This ledger is separate from the existing V2 backend/security roadmap. No backend, business logic, database, payment, license issuance, or API changes are authorized.

## Design direction
Approved reference: right-hand navy sidebar, purple #5B4FCF selection, clean white header, quiet pastel metric cards, actual-data chart and action queue, accessible RTL desktop/mobile and dark mode. Preserve existing route names, permissions, chart canvas IDs and JavaScript behavior. Do not invent metrics or write new tests.

## Stage status

| Stage | Page | Status | Commit |
|---|---|---|---|
| 01 | نمای کلی | In progress — first visual pass committed; browser/Django validation pending | [a2d19bff](https://github.com/qashqaeii/divarfiling/commit/a2d19bff84508f6572164a19b5908b203c4664c3) |
| 02 | دستیار مدیریت | In progress — UI presentation pass committed; runtime/browser QA pending | [pending stage-02 commit](#2026-11-13--stage-02-ui-pass) |
| 03 | فروش و درآمد | In progress — UI pass committed; browser/Django validation pending | [stage 03 UI pass](#2026-11-13--stage-03-ui-pass) |
| 04 | رشد | In progress — UI presentation pass committed; browser/Django validation pending | [stage 04 UI pass](#2026-11-13--stage-04-ui-pass) |
| 05 | بازاریابی | In progress — UI presentation pass committed; runtime/browser QA pending | [stage 05 UI pass](#2026-11-13--stage-05-ui-pass) |
| 06 | بازیابی | In progress — presentation pass committed; runtime/browser QA pending | [stage 06 UI pass](#2026-11-13--stage-06-ui-pass) |
| 07 | تبدیل پلن | Not started | — |
| 08 | جذب سرنخ | Not started | — |
| 09 | کاربران | Not started | — |
| 10 | لایسنس | Not started | — |
| 11 | CRM | Not started | — |
| 12 | عملیات | Not started | — |
| 13 | پشتیبانی | Not started | — |
| 14 | فعالیت | Not started | — |
| 15 | تالار گفتگو | Not started | — |
| 16 | ویندوز | Not started | — |
| 17 | اندروید | Not started | — |
| 18 | هوش مصنوعی | Not started | — |
| 19 | مقالات | Not started | — |
| 20 | آکادمی | Not started | — |
| 21 | انتشار سیستماتیک | Not started | — |
| 22 | همکاری در فروش | Not started | — |
| 23 | خروجی‌ها | Not started | — |

### 2026-11-13 — Stage 01 first pass
Commit a2d19bff84508f6572164a19b5908b203c4664c3 changes:
- templates/accounts/admin_dashboard.html: overview-only intro, real-data KPI hero, chart and action queue, service health indicators, existing deep-dive sections preserved.
- templates/accounts/partials/admin_panel_sidebar.html: nav display label «نمای کلی» (internal key unchanged).
- templates/accounts/partials/admin_panel_header.html: breadcrumb label.
- static/css/mizkar-admin-overview-v3.css: isolated desktop/mobile/dark-mode styling and reduced-motion/focus states.

Source-level checks: matching Django block/endblock counts, preservation of chart-revenue-analytics, ecc-glance, ecc-charts and ecc-summary anchors. GitHub commit confirmed on main. No Django execution, browser screenshot QA or deployment was performed.

### Next step
Complete stage 01 through visual/runtime QA if an environment becomes available, and inspect missing sections from the mockup (recent orders and plan breakdown require existing view context; do not add backend fields under UI-only scope). Only mark Stage 01 complete after all accessible subparts are addressed; then move to Stage 02.

### 2026-11-13 — Stage 02 UI pass
- `templates/accounts/admin_management_assistant.html`: added a concise executive heading, accessibility state for the active navigation tab and a scoped V3 stylesheet link. Existing permissions, data bindings, modals, form IDs and JavaScript hooks preserved.
- `static/css/mizkar-admin-assistant-v3.css`: aligned summary KPI cards, recommendations, automation tables/mobile cards, history, send/automation dialogs, form controls and dark/mobile variants with the approved design language.
- Source-only structural inspection; no Django runtime or browser QA. Stage 02 remains **in progress** until visual/runtime validation. Stage 01 also remains pending visual/runtime validation and additional widgets needing backend context; no backend changes authorized.

### 2026-11-13 — Stage 03 UI pass
- `templates/accounts/admin_sales_center.html`: added executive intro and in-page shortcuts; kept existing chart canvas IDs, payment permissions, review modals, table IDs, export links and data bindings; improved chart accessibility.
- `static/css/mizkar-admin-sales-v3.css`: sales-scoped responsive light/dark styles for KPIs, revenue chart, action queue, audits, sales mix, order tables, card transfer review and modals.
- Source-only structural inspection. No Python, backend, API, business logic or JavaScript changed. No Django runtime or browser QA performed. Stage 03 remains in progress; stages 01 and 02 also await visual/runtime validation. Next: Growth stage 04 after validation where possible.

### 2026-11-13 — Stage 04 UI pass
- `templates/accounts/admin_growth_pipeline.html`: concise growth introduction and same-page shortcuts, accessible selected-stage state and growth breadcrumb; preserved all existing forms, POST actions, CSRF, export URLs, event-table data, chart canvas IDs and guide-modal JS hooks.
- `static/css/mizkar-admin-growth-v3.css`: growth-scoped visual system for six KPI cards, five charts, stage board, recent events, detail table, action toolbar, guide modal, responsive mobile and dark theme; uses real context data only.
- Source-only structural review. No Python, API, business logic, JS or database changed. No new tests. Django runtime/browser QA not executed; stage remains in progress pending visual and functional verification.

### 2026-11-13 — Stage 05 UI pass
- `templates/accounts/admin_marketing.html`: compact executive introduction and scoped V3 stylesheet; all original campaign wizard steps, form methods, CSRF, chart IDs, tabs, segment controls, SMS permissions, data bindings and JS hooks remain in place.
- `templates/accounts/admin_marketing_detail.html`: reuse marketing V3 styles and correct two existing navigation anchor destinations (`#map-compose`, `#map-history`) to match the actual section IDs. Recipient filtering behavior remains unchanged.
- `static/css/mizkar-admin-marketing-v3.css`: responsive premium RTL presentation for KPI grid, segment cards, campaign wizard, templates, automations, phonebook, history, charts, recipient table and dark theme; reduced-motion and focus-visible affordances.
- Source-only inspection; Django runtime and browser QA not executed. Stage 05 remains in progress pending verification. No Python, business logic, API, data, SMS send, JS or new tests.

### 2026-11-13 — Stage 06 UI pass
- `templates/accounts/admin_recovery_center.html`: added a compact executive intro and a scoped recovery V3 stylesheet; preserved all existing period filters, tabs, JSON/export URLs, strict attribution labels, metrics, table bindings, data script and JS hooks.
- `static/css/mizkar-admin-recovery-v3.css`: responsive RTL visual polish for KPI grid, range selection, four tab views, recovery funnel, SMS journey table, health cards, data-quality warnings and explorer pagination, with dark-mode, focus and reduced-motion support.
- Source-only structural inspection; no Django runtime or browser QA performed. Stage 06 remains in progress pending validation; stages 01–05 also await QA. No Python, business logic, API, data, SMS send, JavaScript or new tests changed.
