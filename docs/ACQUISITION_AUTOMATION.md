# Acquisition Automation — Deployment

Automated lead collection: **phone-detector** → **Lead Acquisition Center** → SMS pilot.

## Components

| Piece | Role |
|-------|------|
| `run_acquisition_automation` | Cron — queues due campaigns (every 15 min) |
| `phone-detector/automation/worker.py` | Long-running worker — runs extraction + ingest |
| `accounts/services/acquisition_automation.py` | Orchestration + `ingest_acquisition_run()` |

## Setup

1. Apply migration:

```bash
cd django
python manage.py migrate accounts
```

2. Create a campaign in Django Admin → **کمپین اتوماسیون جذب**:

| Field | Example |
|-------|---------|
| name | تهران · ونک · فروش |
| city | تهران |
| districts | `["ونک"]` |
| category | apartment-sell |
| limit_per_run | 30 |
| interval_hours | 6 |
| is_active | ✓ |
| auto_create_campaign | ✓ |
| auto_enroll_pilot | ✓ |

3. Ensure phone-detector sessions exist (`phone-detector/sessions/`).

## Deploy phone-detector on server

The **divarfiling** git repo contains only Django. `phone-detector` is a separate
directory (monorepo: `DIVAR-SCRAPER/phone-detector`). Deploy it once:

```bash
# From your dev machine (adjust paths/host):
scp -r phone-detector root@212.80.29.56:/root/phone-detector

# On server — install deps in the same venv as Django:
cd /root/DivarFiling
source venv/bin/activate
pip install -r /root/phone-detector/requirements.txt
playwright install chromium

# Copy Divar sessions from local (or re-login on server):
# scp -r phone-detector/sessions root@212.80.29.56:/root/phone-detector/sessions

# .env
PHONE_DETECTOR_DIR=/root/phone-detector
```

Verify:

```bash
ls /root/phone-detector/engine.py
ls /root/phone-detector/automation/worker.py
ls /root/phone-detector/sessions/index.json
```

## Cron (scheduler)

```cron
*/15 * * * * cd /var/www/divarfiling/django && /var/www/divarfiling/venv/bin/python manage.py run_acquisition_automation >> /var/log/acquisition-scheduler.log 2>&1
```

## systemd worker

Option A — from Django (recommended on server where repo root is `~/DivarFiling`):

`/etc/systemd/system/divar-acquisition-worker.service`:

```ini
[Unit]
Description=Divar Filing — Acquisition Automation Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/DivarFiling
Environment=DJANGO_SETTINGS_MODULE=divar_shop.settings
Environment=PHONE_DETECTOR_DIR=/root/phone-detector
EnvironmentFile=/root/DivarFiling/.env
ExecStart=/root/DivarFiling/venv/bin/python manage.py run_acquisition_worker
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

Option B — standalone module (monorepo layout):

```ini
WorkingDirectory=/var/www/divarfiling/phone-detector
Environment=PYTHONPATH=/var/www/divarfiling/django:/var/www/divarfiling/phone-detector
Environment=DIVARFILING_DJANGO_DIR=/var/www/divarfiling/django
Environment=PHONE_DETECTOR_DIR=/var/www/divarfiling/phone-detector
ExecStart=/var/www/divarfiling/venv/bin/python -m automation.worker
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now divar-acquisition-worker
sudo systemctl status divar-acquisition-worker
```

## Local dev

Terminal 1 — Django:

```bash
cd django
python manage.py runserver
```

Terminal 2 — worker (one-shot):

```bash
cd phone-detector
set PYTHONPATH=..\django;.
python -m automation.worker --once
```

Queue a run:

```bash
cd django
python manage.py run_acquisition_automation
```

## Flow

```
AcquisitionAutomationCampaign (due)
  → AcquisitionRun (queued)
  → worker → PhoneDetectorEngine
  → JSON
  → ingest_acquisition_run()
  → lead_import.py → MarketingLead → LeadCampaign → enroll_pilot
  → run_growth_pipeline (existing cron) sends SMS
```

## Notes

- Only **one run at a time** (Redis lock + DB check).
- **No Playwright** in automation — `browser_hip=False`, first captcha stops the run.
- On rate limit / HIP: run status `rate_limited`, partial leads still ingested if any phones were collected.
- Next run delayed by `max(ACQUISITION_COOLDOWN_HOURS, campaign.interval_hours)`.
- Session files remain in **phone-detector** — Django does not own sessions.
