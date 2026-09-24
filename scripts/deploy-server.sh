#!/usr/bin/env bash
# استقرار سریع روی سرور production بعد از push به main
# Usage (روی سرور):
#   cd ~/DivarFiling && bash scripts/deploy-server.sh
#
# اگر git status فایل‌های modified فانتوم نشان می‌دهد، اول:
#   bash scripts/fix-server-git-worktree.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f manage.py ]]; then
  echo "manage.py not found in $ROOT" >&2
  exit 1
fi

if [[ -f venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -f ../venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source ../venv/bin/activate
fi

echo "==> git fetch + merge origin/main"
git fetch origin main
git merge --ff-only origin/main

echo "==> pip (در صورت نیاز)"
pip install -r requirements.txt -q

echo "==> migrate"
python manage.py migrate --noinput

echo "==> collectstatic (JS/CSS جدید)"
python manage.py collectstatic --noinput

echo "==> restart gunicorn"
sudo systemctl restart divar_shop

echo ""
echo "OK: deploy تمام شد. در مرورگر یک بار Ctrl+F5 بزنید."
