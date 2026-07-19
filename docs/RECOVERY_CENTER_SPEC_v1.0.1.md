# Recovery Center Spec v1.0.1

**Status:** Locked — Week 3 production controls baseline  
**Product:** DivarFiling SaaS  
**Layer:** Decision Intelligence → Recovery Intelligence

## 1. Purpose

Transform the existing Recovery engine (`pending_recovery`, `pending_recovery_live`) into a **data product** — not only an admin page. JSON API must be reusable for future Agency dashboards, AI assistant, and benchmarks.

## 2. Recovery Funnel

| Key | Label FA | Source |
|-----|----------|--------|
| `pricing_viewed` | بازدید قیمت | `PlanFunnelEvent.pricing_view` |
| `checkout_started` | شروع Checkout | `PlanFunnelEvent.checkout_view` |
| `checkout_abandoned` | رها کردن Checkout | `PlanFunnelEvent.checkout_abandon` |
| `recovery_eligible` | واجد Recovery (now) | `resolve_pending_recovery_audience().stats.would_send` |
| `sms_accepted` | SMS پذیرفته | `MarketingAutomationActionLog` production sends |
| `sms_delivered` | SMS تحویل | `delivered` or accepted + `SmsMessageLog.sent` |
| `returned_checkout` | بازگشت Checkout | Phase 2 — placeholder |
| `recovered_paid` | پرداخت بازیابی | Phase 2 — Strict attribution |
| `activated` | فعال‌سازی | Phase 2+ |

Production SMS excludes: `test:*` idempotency keys, `test_provider_accepted`, test redirect metadata.

## 3. Attribution Rules (Phase 2)

### 3.1 Strict (Executive KPI)

Match when ALL:

1. `ActionLog.flow_key = pending_recovery`
2. Production send (not test)
3. `Order.status = paid`
4. Same `user_id` (or `phone_hash` if user null)
5. Same `product_id`
6. `payment_time > sms_time`
7. `payment_time <= sms_time + 72h`
8. No paid order for same user+product **before** `sms_time`
9. **Rule 11 — Primary:** `paid_order_id == ActionLog.order_id` (same abandon order)

### 3.2 Assisted (analytics only, not executive KPI)

**Rule 11 — Fallback:** if primary fails:

- Same user + same product
- Paid within 72h after SMS
- Linked via same `checkout_abandon` idempotency / funnel journey
- No prior paid before SMS

Stored as `attribution_model: assisted` — visible in Explorer toggle only.

### 3.3 Influenced

Research model only — not in v1 dashboards.

## 4. JSON API

```json
{
  "schema_version": "recovery_center_v1",
  "generated_at": "2026-07-19T12:00:00+03:30",
  "data_freshness": {
    "last_event_at": "...",
    "last_recovery_run_at": "..."
  },
  "period": { "days": 30, "since": "...", "until": "..." },
  "funnel": { ... },
  "journey": [ ... ],
  "health": { ... },
  "data_quality": { ... },
  "explorer": { ... }
}
```

## 5. UI Tabs

1. **Funnel** — stages + executive KPIs (Recovered/Revenue = null + tooltip until Phase 2)
2. **Journey** — Step 1 / Step 1 Late / Step 2 performance
3. **Health** — cron proxy, flags, provider, queue, errors, **data quality**
4. **Explorer** — paginated ActionLog rows, read-only

## 6. Roadmap

| Week | Deliverable |
|------|-------------|
| 0 | This spec v1.0.1 |
| 1 | Recovery Center MVP |
| 2 | `recovery_attribution.py` (strict + assisted) |
| 3 | Production cron + daily cap + Health v2 |
| 4 | Plan Conversion integration |

## 7. Out of Scope

Manual send UI, Marketing campaign link, template builder, AI, engine refactor.

---

## 8. Week 2 — Attribution (Implemented)

- Model: `RecoveryAttribution` (immutable after matched/no_match)
- Service: `accounts/services/recovery_attribution.py`
- Rules: `strict_v1`, `assisted_v1` with `rule_version` on each row
- Executive KPI: Strict + matched only
- Backfill: last 30 days on dashboard load + `backfill_attributions()`
- JSON schema: `recovery_center_v1.1`

---

## 9. Week 3 — Production Controls (Implemented)

### 9.1 Daily SMS Guard

- Setting: `RECOVERY_MAX_SMS_PER_DAY` (default `5`; `0` = unlimited / guard off)
- Counts **production** sends only (`provider_accepted`, not test redirect / `test:` keys)
- Day boundary: local timezone (Asia/Tehran)
- Enforced in `run_pending_recovery_live()` before provider call
- Skip reason: `daily_cap_reached` in `skip_breakdown`
- Works with per-run cap: `effective_max = min(RECOVERY_LIVE_MAX_SENDS_PER_RUN, daily_remaining)`

### 9.2 Health Panel v2

JSON + UI fields:

| Block | Contents |
|-------|----------|
| `last_dry_run` | Last `MarketingAutomationRun` mode=dry_run |
| `last_live_run` | Last mode=live |
| `daily_sms_guard` | sent_today, max_per_day, remaining, cap_reached, resets_at_label (Jalali) |
| `attribution_health` | pending_30d, strict_matched_30d, duplicate_strict_30d |
| `recovery_engine` | + `max_sends_per_run` |

JSON schema: `recovery_center_v1.2`

### 9.3 Production Cron

See `django/docs/RECOVERY_CRON.md`.

Recommended conservative start:

```bash
0 */4 * * * cd /path/to/django && python manage.py run_pending_recovery --live --confirm-live --max-sends 1
```

Required env (production):

- `PENDING_RECOVERY_FLOW_ENABLED=True`
- `RECOVERY_LIVE_SEND_ENABLED=True`
- `RECOVERY_LIVE_TEST_ONLY=False` (only after admin test)
- `RECOVERY_LIVE_MAX_SENDS_PER_RUN=1`
- `RECOVERY_MAX_SMS_PER_DAY=3` (or 5)
