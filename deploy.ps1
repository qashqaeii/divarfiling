# Deploy سریع: لوکال → سرور
# استفاده:
#   .\deploy.ps1              # فقط template + static (سریع‌ترین)
#   .\deploy.ps1 -Code        # + کد Python (apps)
#   .\deploy.ps1 -Full        # همه چیز به‌جز venv و cache
#   .\deploy.ps1 -NoRestart    # فقط کپی، بدون restart

param(
    [switch]$Code,
    [switch]$Full,
    [switch]$NoRestart
)

$ErrorActionPreference = "Stop"

# ─── تنظیمات سرور (یک‌بار ویرایش کنید) ───
$SERVER     = "root@62.60.204.73"
$REMOTE_DIR = "/root/DivarFiling"
$LOCAL_DIR  = $PSScriptRoot

Write-Host ""
Write-Host "=== Deploy DivarFiling ===" -ForegroundColor Cyan
Write-Host "Local : $LOCAL_DIR"
Write-Host "Remote: ${SERVER}:${REMOTE_DIR}"
Write-Host ""

function Sync-Item {
    param([string]$RelativePath)
    $localPath = Join-Path $LOCAL_DIR $RelativePath
    if (-not (Test-Path $localPath)) {
        Write-Host "  skip (not found): $RelativePath" -ForegroundColor DarkGray
        return
    }
    $remotePath = "${SERVER}:${REMOTE_DIR}/$($RelativePath -replace '\\','/')"
    Write-Host "  -> $RelativePath" -ForegroundColor Green
    scp -r $localPath $remotePath
    if ($LASTEXITCODE -ne 0) { throw "scp failed: $RelativePath" }
}

# ─── ۱. کپی فایل‌ها ───
Write-Host "[1/2] Syncing files..." -ForegroundColor Yellow

# همیشه: template و static (بیشتر تغییرات شما اینجاست)
Sync-Item "templates"
Sync-Item "static"

if ($Code -or $Full) {
    @(
        "shop", "workspace", "accounts", "blog", "affiliates", "licenses",
        "divar_shop", "manage.py", "requirements.txt", "gunicorn_config.py"
    ) | ForEach-Object { Sync-Item $_ }
}

if ($Full) {
    @(
        "nginx_divar_shop.conf", "nginx_divar_shop.http.conf",
        "divar_shop.service", "files"
    ) | ForEach-Object { Sync-Item $_ }
}

# ─── ۲. دستورات روی سرور ───
if (-not $NoRestart) {
    Write-Host ""
    Write-Host "[2/2] Restarting on server..." -ForegroundColor Yellow

    $remoteCmd = @"
cd $REMOTE_DIR && source venv/bin/activate && python manage.py collectstatic --noinput && sudo systemctl restart divar_shop && sudo systemctl reload nginx && echo 'OK: deploy complete'
"@

    ssh $SERVER $remoteCmd
    if ($LASTEXITCODE -ne 0) { throw "remote commands failed" }
}

Write-Host ""
Write-Host "Done! Check: https://divarfiling.ir" -ForegroundColor Green
Write-Host ""
