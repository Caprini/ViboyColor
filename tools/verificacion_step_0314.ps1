# Script de Verificación Step 0314 - Corrección de Direccionamiento de Tiles
# Ejecuta el emulador y captura logs relevantes sin saturar el contexto

Write-Host "=== Verificación Step 0314 ===" -ForegroundColor Cyan
Write-Host "Ejecutando emulador por 30 segundos..." -ForegroundColor Yellow
Write-Host "Presiona Ctrl+C después de 30 segundos para detener" -ForegroundColor Yellow
Write-Host ""

# Ejecutar emulador redirigiendo salida a archivo
$logFile = "logs\verificacion_step_0314_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

try {
    # Iniciar proceso en background con timeout
    $job = Start-Job -ScriptBlock {
        param($rom)
        Set-Location $using:PWD
        python main.py $rom 2>&1
    } -ArgumentList "roms/pkmn.gb"

    # Esperar 30 segundos
    Start-Sleep -Seconds 30

    # Detener el proceso
    Stop-Job -Job $job
    Remove-Job -Job $job -Force
    
    Write-Host "Emulador detenido después de 30 segundos" -ForegroundColor Green
} catch {
    Write-Host "Error al ejecutar emulador: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Análisis de Logs ===" -ForegroundColor Cyan
Write-Host "Buscando logs relevantes..." -ForegroundColor Yellow
Write-Host ""

# Buscar logs de LCDC
$lcdcLogs = Get-Content -Path $logFile -ErrorAction SilentlyContinue | Select-String -Pattern "\[LOAD-TEST-TILES\].*LCDC" | Select-Object -First 5
if ($lcdcLogs) {
    Write-Host "✅ Logs de LCDC encontrados:" -ForegroundColor Green
    $lcdcLogs | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "⚠️ No se encontraron logs de LCDC" -ForegroundColor Yellow
}

Write-Host ""

# Buscar logs de BG Data Base
$bgBaseLogs = Get-Content -Path $logFile -ErrorAction SilentlyContinue | Select-String -Pattern "\[TILEMAP-INSPECT\].*BG Data Base" | Select-Object -First 5
if ($bgBaseLogs) {
    Write-Host "✅ Logs de BG Data Base encontrados:" -ForegroundColor Green
    $bgBaseLogs | ForEach-Object { Write-Host "  $_" }
} else {
    Write-Host "⚠️ No se encontraron logs de BG Data Base" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Verificación Visual Requerida ===" -ForegroundColor Cyan
Write-Host "Por favor, verifica visualmente:" -ForegroundColor Yellow
Write-Host "  1. ¿Se muestran tiles en pantalla? (no pantalla blanca)" -ForegroundColor White
Write-Host "  2. ¿Se ve el patrón de checkerboard? (Tile 1)" -ForegroundColor White
Write-Host "  3. ¿Se ven líneas horizontales? (Tile 2)" -ForegroundColor White
Write-Host "  4. ¿Se ven líneas verticales? (Tile 3)" -ForegroundColor White
Write-Host ""
Write-Host "Log completo guardado en: $logFile" -ForegroundColor Cyan

