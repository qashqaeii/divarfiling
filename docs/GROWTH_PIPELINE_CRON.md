# Growth Pipeline Production Cron

Unified runner for Lead Acquisition drip, User Activation, Pending Recovery, and License Renewal.

## Command

```bash
cd /path/to/django
python manage.py run_growth_pipeline --limit 200
```

Useful flags:

| Flag | Effect |
|------|--------|
| `--backfill` | Build/update `GrowthJourney` from leads & users first |
| `--skip-acquisition` | Skip cold-lead steps 2–3 |
| `--skip-activation` | Skip registered-user nurture SMS |
| `--skip-recovery` | Skip pending-order recovery dry-run |
| `--skip-renewal` | Skip license expiry scan |
| `--renewal-live` | Actually send license renewal SMS (default dry-run) |
| `--recovery-live` | Live recovery send (needs Recovery kill switches) |

## Recommended Crontab

Every 2–4 hours (Tehran ops; Django uses timezone-aware delays):

```cron
0 */2 * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_growth_pipeline --limit 200 >> /var/log/growth-pipeline.log 2>&1
```

One-time backfill after deploy:

```bash
python manage.py run_growth_pipeline --backfill --skip-recovery --skip-renewal --limit 5000
```

Nightly license renewal dry-run visibility:

```cron
30 7 * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_growth_pipeline --skip-acquisition --skip-activation --skip-recovery >> /var/log/growth-renewal-dry.log 2>&1
```

Enable live renewal only after dry-run looks clean:

```cron
0 10 * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_growth_pipeline --skip-acquisition --skip-activation --skip-recovery --renewal-live --limit 50 >> /var/log/growth-renewal-live.log 2>&1
```

## Settings

| Setting | Default | Meaning |
|---------|---------|---------|
| `LICENSE_RENEWAL_FLOW_ENABLED` | `True` | Master switch for renewal live sends |
| `LICENSE_RENEWAL_WITHIN_DAYS` | `7` | Active licenses expiring within N days |
| `LICENSE_RENEWAL_CHURN_AFTER_DAYS` | `3` | Days after expiry before churn SMS |
| `LICENSE_RENEWAL_LANDING_URL` | pricing URL | Link in renewal SMS |

Recovery still uses its own flags (`PENDING_RECOVERY_FLOW_ENABLED`, `RECOVERY_LIVE_SEND_ENABLED`, …) — see `RECOVERY_CRON.md`.

## Pipeline stages

`cold_lead → engaged → registered → activated / nurture_unpaid → pending_checkout → customer → expiring_soon → renewed | churn_risk`

Shared suppression (`accounts.services.growth_suppression.is_send_allowed`) prevents double SMS across acquisition, activation, recovery, and renewal.

## Monitoring

- Admin → **پایپلاین رشد** (`/accounts/admin-panel/marketing/growth/`)
- Cache key `growth_pipeline_last_run` (48h) stores last command report
- Acquisition-only legacy command still works: `run_lead_acquisition_sequence`
