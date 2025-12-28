# Script de análisis de logs de rendimiento para Step 0307
# Analiza los logs generados por el emulador con monitor [PERFORMANCE-TRACE]

param(
    [string]$LogFile = "perf_step_0307.log"
)

Write-Host "=== Análisis de Rendimiento - Step 0307 ===" -ForegroundColor Cyan
Write-Host ""

# Verificar que el archivo existe
if (-not (Test-Path $LogFile)) {
    Write-Host "ERROR: Archivo de log no encontrado: $LogFile" -ForegroundColor Red
    Write-Host "Ejecuta primero: python main.py roms/pkmn.gb > perf_step_0307.log 2>&1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Archivo de log: $LogFile" -ForegroundColor Green
Write-Host ""

# Contar registros [PERFORMANCE-TRACE]
$traceCount = (Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Measure-Object).Count
Write-Host "Registros [PERFORMANCE-TRACE] encontrados: $traceCount" -ForegroundColor Cyan
Write-Host ""

if ($traceCount -eq 0) {
    Write-Host "ADVERTENCIA: No se encontraron registros [PERFORMANCE-TRACE]" -ForegroundColor Yellow
    Write-Host "Verifica que el monitor esté activado en renderer.py" -ForegroundColor Yellow
    exit 1
}

# Mostrar primeros 10 registros
Write-Host "=== Primeros 10 registros ===" -ForegroundColor Cyan
Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Select-Object -First 10 | ForEach-Object {
    Write-Host $_.Line
}
Write-Host ""

# Mostrar últimos 10 registros
Write-Host "=== Últimos 10 registros ===" -ForegroundColor Cyan
Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Select-Object -Last 10 | ForEach-Object {
    Write-Host $_.Line
}
Write-Host ""

# Extraer valores de FPS y calcular estadísticas
Write-Host "=== Estadísticas de FPS ===" -ForegroundColor Cyan
$fpsValues = Select-String -Path $LogFile -Pattern "FPS: (\d+\.?\d*)" | ForEach-Object {
    if ($_.Matches.Groups.Count -gt 1) {
        [double]$_.Matches.Groups[1].Value
    }
}

if ($fpsValues.Count -eq 0) {
    Write-Host "ERROR: No se encontraron valores de FPS en el log" -ForegroundColor Red
    Write-Host "Verifica que el formato del log sea correcto" -ForegroundColor Yellow
    exit 1
}

$stats = $fpsValues | Measure-Object -Average -Maximum -Minimum
Write-Host "FPS Promedio: $($stats.Average.ToString('F2'))" -ForegroundColor Green
Write-Host "FPS Mínimo:  $($stats.Minimum.ToString('F2'))" -ForegroundColor Yellow
Write-Host "FPS Máximo:  $($stats.Maximum.ToString('F2'))" -ForegroundColor Green
Write-Host ""

# Comparación con FPS anterior (21.8 del Step 0306)
$fpsAnterior = 21.8
$mejora = $stats.Average - $fpsAnterior
$mejoraPorcentual = ($mejora / $fpsAnterior) * 100

Write-Host "=== Comparación con Step 0306 ===" -ForegroundColor Cyan
Write-Host "FPS Anterior (Step 0306): $fpsAnterior" -ForegroundColor Gray
Write-Host "FPS Actual (Step 0307):    $($stats.Average.ToString('F2'))" -ForegroundColor Green
Write-Host "Mejora:                    $($mejora.ToString('F2')) FPS ($($mejoraPorcentual.ToString('F2'))%)" -ForegroundColor $(if ($mejora -gt 0) { "Green" } else { "Red" })
Write-Host ""

# Evaluación
Write-Host "=== Evaluación ===" -ForegroundColor Cyan
if ($stats.Average -ge 55) {
    Write-Host "✅ EXCELENTE: FPS >= 55 (objetivo alcanzado)" -ForegroundColor Green
} elseif ($stats.Average -ge 40) {
    Write-Host "⚠️  BUENO: FPS >= 40 (mejora significativa)" -ForegroundColor Yellow
} elseif ($stats.Average -gt $fpsAnterior) {
    Write-Host "⚠️  MEJORA: FPS mejoró pero aún bajo objetivo" -ForegroundColor Yellow
} else {
    Write-Host "❌ PROBLEMA: FPS no mejoró o empeoró" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Análisis completado ===" -ForegroundColor Cyan

