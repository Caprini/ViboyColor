# Script de análisis de logs de rendimiento para Step 0308
# Analiza los logs generados por el emulador con monitor [PERFORMANCE-TRACE] mejorado

param(
    [string]$LogFile = "perf_step_0308.log"
)

Write-Host "=== Análisis de Rendimiento - Step 0308 ===" -ForegroundColor Cyan
Write-Host ""

# Verificar que el archivo existe
if (-not (Test-Path $LogFile)) {
    Write-Host "ERROR: Archivo de log no encontrado: $LogFile" -ForegroundColor Red
    Write-Host "Ejecuta primero: python main.py roms/pkmn.gb > perf_step_0308.log 2>&1" -ForegroundColor Yellow
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

# Extraer tiempos por componente (si están disponibles)
Write-Host "=== Análisis de Componentes (últimos 5 registros) ===" -ForegroundColor Cyan
Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Select-Object -Last 5 | ForEach-Object {
    $line = $_.Line
    if ($line -match "Snapshot: ([\d.]+)ms") {
        Write-Host "  Snapshot: $($matches[1])ms" -ForegroundColor Gray
    }
    if ($line -match "Render: ([\d.]+)ms") {
        Write-Host "  Render: $($matches[1])ms" -ForegroundColor Gray
    }
    if ($line -match "Hash: ([\d.]+)ms") {
        Write-Host "  Hash: $($matches[1])ms" -ForegroundColor Gray
    }
}
Write-Host ""

# Comparación con FPS anterior (21.8 del Step 0306, 16.7 del Step 0307)
$fpsStep0306 = 21.8
$fpsStep0307 = 16.7
$mejoraVs0306 = $stats.Average - $fpsStep0306
$mejoraVs0307 = $stats.Average - $fpsStep0307
$mejoraPorcentual0306 = ($mejoraVs0306 / $fpsStep0306) * 100
$mejoraPorcentual0307 = ($mejoraVs0307 / $fpsStep0307) * 100

Write-Host "=== Comparación con Steps Anteriores ===" -ForegroundColor Cyan
Write-Host "FPS Step 0306 (baseline): $fpsStep0306" -ForegroundColor Gray
Write-Host "FPS Step 0307 (regresión): $fpsStep0307" -ForegroundColor Red
Write-Host "FPS Actual (Step 0308):    $($stats.Average.ToString('F2'))" -ForegroundColor Green
Write-Host ""
Write-Host "Mejora vs Step 0306:      $($mejoraVs0306.ToString('F2')) FPS ($($mejoraPorcentual0306.ToString('F2'))%)" -ForegroundColor $(if ($mejoraVs0306 -gt 0) { "Green" } else { "Red" })
Write-Host "Mejora vs Step 0307:      $($mejoraVs0307.ToString('F2')) FPS ($($mejoraPorcentual0307.ToString('F2'))%)" -ForegroundColor $(if ($mejoraVs0307 -gt 0) { "Green" } else { "Red" })
Write-Host ""

# Evaluación
Write-Host "=== Evaluación ===" -ForegroundColor Cyan
if ($stats.Average -ge 55) {
    Write-Host "✅ EXCELENTE: FPS >= 55 (objetivo alcanzado)" -ForegroundColor Green
} elseif ($stats.Average -ge 40) {
    Write-Host "⚠️  BUENO: FPS >= 40 (mejora significativa)" -ForegroundColor Yellow
} elseif ($stats.Average -gt $fpsStep0306) {
    Write-Host "✅ MEJORA: FPS mejoró vs Step 0306 (baseline)" -ForegroundColor Green
} elseif ($stats.Average -gt $fpsStep0307) {
    Write-Host "⚠️  RECUPERACIÓN: FPS mejoró vs Step 0307 pero aún bajo baseline" -ForegroundColor Yellow
} else {
    Write-Host "❌ PROBLEMA: FPS no mejoró o empeoró" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Análisis completado ===" -ForegroundColor Cyan

