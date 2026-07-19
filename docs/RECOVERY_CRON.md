# Recovery Production Cron

**Week 3** — controlled live sends with daily cap.

## Prerequisites

1. Recovery Center Health tab shows expected flags.
2. At least one successful **test-only** live run (`--test-only`).
3. Attribution backfill working (`RecoveryAttribution` rows = pending for recent sends).
4. Set production env:

```env
PENDING_RECOVERY_FLOW_ENABLED=True
RECOVERY_LIVE_SEND_ENABLED=True
RECOVERY_LIVE_TEST_ONLY=False
RECOVERY_LIVE_MAX_SENDS_PER_RUN=1
RECOVERY_MAX_SMS_PER_DAY=3
```

Start with `RECOVERY_MAX_SMS_PER_DAY=3`; increase only after one week of clean data.

## Dry Run (safe, schedule optional)

Simulates audience without SMS:

```bash
python manage.py run_pending_recovery --dry-run --simulate-enabled
```

Or with flow enabled (no `--simulate-enabled`):

```bash
python manage.py run_pending_recovery --dry-run
```

## Live Run (manual)

Test redirect to admin phone:

```bash
python manage.py run_pending_recovery --live --confirm-live --test-only --max-sends 1
```

Production send:

```bash
python manage.py run_pending_recovery --live --confirm-live --no-test-only --max-sends 1
```

Command output includes `daily_sms=sent/max`, `remaining`, `cap_reached`, `effective_max_sends`.

## Recommended Crontab

Every 4 hours, max 1 SMS per run (3–5/day cap enforced in app):

```cron
0 */4 * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_pending_recovery --live --confirm-live --max-sends 1 >> /var/log/recovery-cron.log 2>&1
```

Optional nightly dry-run for queue visibility:

```cron
15 6 * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_pending_recovery --dry-run >> /var/log/recovery-dry.log 2>&1
```

## Kill Switches

| Switch | Effect |
|--------|--------|
| `PENDING_RECOVERY_FLOW_ENABLED=False` | Blocks live send (resolver off) |
| `RECOVERY_LIVE_SEND_ENABLED=False` | Blocks live send |
| `RECOVERY_MAX_SMS_PER_DAY=0` | Disables daily guard (not recommended in prod) |

## Monitoring

Recovery Center → **Health**:

- Last Dry Run / Last Live Run timestamps
- Daily SMS bar (`sent / max`)
- Attribution pending vs strict matched
- Errors 24h

After deploy, collect **≥ 7 days** before Plan Conversion integration (Week 4).
