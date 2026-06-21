# Deploy با rsync — فقط فایل‌های تغییرکرده (سریع‌ترین روش)
# نیاز: WSL نصب باشد (Ubuntu از Microsoft Store)
#
# استفاده:
#   .\deploy-rsync.ps1
#   .\deploy-rsync.ps1 -NoRestart

param([switch]$NoRestart)

$ErrorActionPreference = "Stop"

$SERVER     = "root@62.60.204.73"
$REMOTE_DIR = "/root/DivarFiling"
$LOCAL_WIN  = $PSScriptRoot
$drive = $LOCAL_WIN.Substring(0, 1).ToLower()
$LOCAL_WSL = "/mnt/$drive" + ($LOCAL_WIN.Substring(2) -replace '\\', '/')

Write-Host ""
Write-Host "=== Deploy (rsync) ===" -ForegroundColor Cyan

$excludes = @(
    "--exclude", "venv/",
    "--exclude", "__pycache__/",
    "--exclude", "*.pyc",
    "--exclude", ".env",
    "--exclude", "db.sqlite3",
    "--exclude", "staticfiles/",
    "--exclude", "node_modules/",
    "--exclude", "logs/",
    "--exclude", "media/",
    "--exclude", ".git/"
)

$rsyncArgs = @(
    "-avz", "--progress",
    $excludes
    "$LOCAL_WSL/",
    "${SERVER}:${REMOTE_DIR}/"
)

Write-Host "[1/2] rsync (only changed files)..." -ForegroundColor Yellow
wsl rsync @rsyncArgs
if ($LASTEXITCODE -ne 0) { throw "rsync failed" }

if (-not $NoRestart) {
    Write-Host ""
    Write-Host "[2/2] Restarting..." -ForegroundColor Yellow
    ssh $SERVER "cd $REMOTE_DIR && source venv/bin/activate && python manage.py collectstatic --noinput && sudo systemctl restart divar_shop && sudo systemctl reload nginx"
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
