# Script para ejecutar verificación del limitador de FPS - Step 0310
# Ejecuta el emulador durante 2 minutos y analiza los logs automáticamente

param(
    [int]$DurationSeconds = 120,
    [string]$RomFile = "roms/pkmn.gb",
    [string]$LogFile = "perf_step_0310.log"
)

Write-Host "=== Ejecución de Verificación del Limitador de FPS - Step 0310 ===" -ForegroundColor Cyan
Write-Host ""

# Verificar que existe la ROM
if (-not (Test-Path $RomFile)) {
    Write-Host "ERROR: Archivo ROM no encontrado: $RomFile" -ForegroundColor Red
    exit 1
}

Write-Host "ROM: $RomFile" -ForegroundColor Green
Write-Host "Duración: $DurationSeconds segundos (2 minutos)" -ForegroundColor Green
Write-Host "Log de salida: $LogFile" -ForegroundColor Green
Write-Host ""

# Limpiar log anterior si existe
if (Test-Path $LogFile) {
    Remove-Item $LogFile -Force
    Write-Host "Log anterior eliminado" -ForegroundColor Gray
}

Write-Host "Iniciando emulador..." -ForegroundColor Cyan
Write-Host "El emulador se ejecutará durante $DurationSeconds segundos" -ForegroundColor Yellow
Write-Host "Presiona Ctrl+C para detener antes del tiempo programado" -ForegroundColor Yellow
Write-Host ""

# Ejecutar emulador con timeout
$startTime = Get-Date
# Usar redirección de PowerShell para combinar stdout y stderr
$process = Start-Process -FilePath "python" -ArgumentList "main.py", $RomFile -NoNewWindow -PassThru -RedirectStandardOutput $LogFile -RedirectStandardError "${LogFile}.err"

try {
    # Esperar el tiempo especificado o hasta que el proceso termine
    $process.WaitForExit($DurationSeconds * 1000)
    
    # Si el proceso sigue ejecutándose, terminarlo
    if (-not $process.HasExited) {
        Write-Host ""
        Write-Host "Tiempo de ejecución completado. Deteniendo emulador..." -ForegroundColor Yellow
        $process.Kill()
        $process.WaitForExit(5000)
    }
} catch {
    Write-Host "Error durante la ejecución: $_" -ForegroundColor Red
    if (-not $process.HasExited) {
        $process.Kill()
    }
}

$endTime = Get-Date
$elapsed = ($endTime - $startTime).TotalSeconds

Write-Host ""
Write-Host "Ejecución completada" -ForegroundColor Green
Write-Host "Tiempo transcurrido: $([math]::Round($elapsed, 1)) segundos" -ForegroundColor Gray
Write-Host ""

# Verificar que el log se creó
if (-not (Test-Path $LogFile)) {
    Write-Host "ERROR: No se creó el archivo de log" -ForegroundColor Red
    exit 1
}

# Combinar stderr con stdout si existe
if (Test-Path "${LogFile}.err") {
    Add-Content -Path $LogFile -Value (Get-Content "${LogFile}.err")
    Remove-Item "${LogFile}.err" -Force
}

$logSize = (Get-Item $LogFile).Length / 1KB
Write-Host "Tamaño del log: $([math]::Round($logSize, 2)) KB" -ForegroundColor Gray
Write-Host ""

# Mostrar primeras líneas del log para verificar que hay contenido
Write-Host "Primeras 10 líneas del log:" -ForegroundColor Cyan
Get-Content $LogFile | Select-Object -First 10 | ForEach-Object {
    Write-Host "  $_" -ForegroundColor Gray
}
Write-Host ""

# Ejecutar análisis automático
Write-Host "Ejecutando análisis automático..." -ForegroundColor Cyan
Write-Host ""
& ".\tools\analizar_perf_step_0310.ps1" -LogFile $LogFile

Write-Host ""
Write-Host "=== Verificación completada ===" -ForegroundColor Cyan
Write-Host "Revisa el archivo $LogFile para más detalles" -ForegroundColor Gray

