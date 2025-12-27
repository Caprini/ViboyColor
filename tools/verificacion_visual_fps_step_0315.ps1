# Script de Verificación Visual y Análisis de FPS - Step 0315
# Este script ejecuta el emulador y captura logs para análisis de FPS

param(
    [string]$RomPath = "roms/pkmn.gb",
    [int]$DurationSeconds = 30
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación Visual y Análisis de FPS" -ForegroundColor Cyan
Write-Host "Step 0315" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que la ROM existe
if (-not (Test-Path $RomPath)) {
    Write-Host "ERROR: ROM no encontrada: $RomPath" -ForegroundColor Red
    exit 1
}

Write-Host "ROM: $RomPath" -ForegroundColor Green
Write-Host "Duración: $DurationSeconds segundos" -ForegroundColor Green
Write-Host ""

# Crear directorio de logs si no existe
$logDir = "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

$logFile = "$logDir/fps_analysis_step_0315.log"
Write-Host "Ejecutando emulador y capturando logs..." -ForegroundColor Yellow
Write-Host "Logs se guardarán en: $logFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "⚠️  IMPORTANTE: Observa la ventana del emulador durante la ejecución" -ForegroundColor Yellow
Write-Host "   - ¿Se muestran tiles visibles?" -ForegroundColor Yellow
Write-Host "   - ¿Hay pantalla blanca?" -ForegroundColor Yellow
Write-Host "   - ¿Se ven patrones reconocibles?" -ForegroundColor Yellow
Write-Host "   - ¿La imagen es estable?" -ForegroundColor Yellow
Write-Host ""
Write-Host "Presiona Ctrl+C para detener antes de $DurationSeconds segundos" -ForegroundColor Yellow
Write-Host ""

# Ejecutar emulador y redirigir salida a archivo
# Usar Start-Process con timeout para limitar la duración
$job = Start-Job -ScriptBlock {
    param($rom, $log)
    python main.py $rom > $log 2>&1
} -ArgumentList $RomPath, $logFile

# Esperar o cancelar después de DurationSeconds
$timeout = $false
try {
    Wait-Job -Job $job -Timeout $DurationSeconds | Out-Null
    if ($job.State -eq "Running") {
        Write-Host "Timeout alcanzado ($DurationSeconds segundos). Deteniendo..." -ForegroundColor Yellow
        Stop-Job -Job $job
        $timeout = $true
    }
} catch {
    Write-Host "Emulador detenido por el usuario o error" -ForegroundColor Yellow
    Stop-Job -Job $job -ErrorAction SilentlyContinue
}

# Esperar a que el job termine completamente
Wait-Job -Job $job | Out-Null
Remove-Job -Job $job

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Análisis de Logs" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Analizar logs (solo muestras)
if (Test-Path $logFile) {
    Write-Host "📊 Análisis de FPS:" -ForegroundColor Green
    $fpsLines = Select-String -Path $logFile -Pattern "FPS:|\[PERFORMANCE-TRACE\]|\[FPS-LIMITER\]" | Select-Object -First 20 -Last 10
    if ($fpsLines) {
        $fpsLines | ForEach-Object { Write-Host $_.Line }
    } else {
        Write-Host "   No se encontraron líneas de FPS" -ForegroundColor Yellow
    }
    Write-Host ""
    
    Write-Host "⚠️  Errores y Warnings:" -ForegroundColor Yellow
    $errorLines = Select-String -Path $logFile -Pattern "ERROR|WARNING|Exception" | Select-Object -First 20
    if ($errorLines) {
        $errorLines | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
    } else {
        Write-Host "   No se encontraron errores" -ForegroundColor Green
    }
    Write-Host ""
    
    Write-Host "⏱️  Tiempo de Frame:" -ForegroundColor Green
    $frameTimeLines = Select-String -Path $logFile -Pattern "Frame time|tick_time" | Select-Object -First 10
    if ($frameTimeLines) {
        $frameTimeLines | ForEach-Object { Write-Host $_.Line }
    } else {
        Write-Host "   No se encontraron líneas de tiempo de frame" -ForegroundColor Yellow
    }
    Write-Host ""
    
    Write-Host "✅ Logs completos guardados en: $logFile" -ForegroundColor Green
    Write-Host "   Revisa el archivo para análisis detallado" -ForegroundColor Green
} else {
    Write-Host "❌ ERROR: No se generó el archivo de log" -ForegroundColor Red
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Próximos Pasos:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "1. Completa VERIFICACION_RENDERIZADO_STEP_0312.md con tus observaciones visuales" -ForegroundColor Yellow
Write-Host "2. Revisa ANALISIS_FPS_BAJO_STEP_0315.md para documentar hallazgos" -ForegroundColor Yellow
Write-Host ""

