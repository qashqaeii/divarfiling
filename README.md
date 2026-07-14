# Divar Bot Sales System

A Django-based e-commerce platform for selling and distributing Divar bot editions.

## Features

- RTL and Persian UI with a Glassmorphism theme
- Online payments via Zibal gateway
- Single-machine licensing with hardware activation
- Affiliate program
- User and admin dashboards
- Blog and articles
- License activation API

## Installation

### Prerequisites

- Python 3.9 or newer
- pip
- virtualenv (recommended)

### Setup steps

1. Create a virtual environment:

```bash
python -m venv venv
```

2. Activate the virtual environment:

**Windows (CMD):**
```cmd
venv\Scripts\activate
```

**Windows (PowerShell):**
```powershell
venv\Scripts\Activate.ps1
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

**Local Windows note:** If you use File Explorer or a GUI on Windows, open CMD or PowerShell in the project folder and run one of the activation commands above.

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Create a superuser:

```bash
python manage.py createsuperuser
```

6. Start the development server:

```bash
python manage.py runserver
```

After you replace the real `Robot.zip` bundle:

```bash
cd django
python manage.py sync_bot_product
```

## Configuration

### Environment variables

Production: `cp env_template.txt .env` — Development: `cp .env.example .env`

```env
DATABASE_NAME=divarfilingDb
DATABASE_USER=divarfilingAdmin
SITE_URL=https://divarfiling.ir
ZIBAL_CALLBACK_URL=https://divarfiling.ir/payment/callback/
EMAIL_HOST=mail.divarfiling.ir
DEFAULT_FROM_EMAIL=noreply@divarfiling.ir
```

### Zibal settings

1. Log in to the Zibal dashboard
2. Copy your Merchant ID
3. Set the callback URL to: `https://divarfiling.ir/payment/callback/`

## Project structure

```
django/
├── divar_shop/          # Main project settings
├── accounts/            # User management
├── shop/                # Store and products
├── licenses/            # Licensing system
├── affiliates/          # Affiliate program
├── blog/                # Blog and articles
├── templates/           # HTML templates
├── static/              # Static assets (CSS, JS)
└── media/               # Uploaded media files
```

## License API

### Activate a license

```bash
POST /api/licenses/activate/
Content-Type: application/json

{
    "license_key": "XXXX-XXXX-XXXX-XXXX",
    "hardware_fingerprint": "machine-id-or-fingerprint"
}
```

### Validate a license

```bash
POST /api/licenses/validate/
Content-Type: application/json

{
    "license_key": "XXXX-XXXX-XXXX-XXXX",
    "hardware_fingerprint": "machine-id-or-fingerprint"
}
```

## Documentation

For more details, see `django-info.txt`.

## Support

Contact us for support or to report issues.

## License

All rights reserved.
