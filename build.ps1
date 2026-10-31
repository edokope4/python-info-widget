# Compila Info Widget con PyInstaller y deja el .exe en .\dist
# Uso:  .\build.ps1
# Requisitos: Python 3.10+ y pip

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> Instalando dependencias..." -ForegroundColor Cyan
python -m pip install -r requirements.txt

Write-Host "==> Limpiando builds anteriores..." -ForegroundColor Cyan
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
Get-ChildItem -Filter "*.spec" -ErrorAction SilentlyContinue | Remove-Item -Force

Write-Host "==> Compilando con PyInstaller (salida: dist\)..." -ForegroundColor Cyan
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onefile `
    --name "InfoWidget" `
    --distpath "dist" `
    --workpath "build" `
    --specpath "." `
    --paths "." `
    --hidden-import "services" `
    --hidden-import "services.system_metrics" `
    --hidden-import "services.weather" `
    --hidden-import "services.boostr" `
    --hidden-import "services.settings" `
    --hidden-import "ui" `
    --hidden-import "ui.widget" `
    --hidden-import "ui.config_dialog" `
    main.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: PyInstaller falló." -ForegroundColor Red
    exit $LASTEXITCODE
}

$exe = Join-Path (Resolve-Path "dist") "InfoWidget.exe"
Write-Host ""
Write-Host "Listo. Ejecutable:" -ForegroundColor Green
Write-Host "  $exe"
Write-Host ""
Write-Host "Para probar:  .\dist\InfoWidget.exe"
