# Script de análisis de logs de rendimiento para Step 0310
# Analiza los logs generados por el emulador con limitador de FPS verificado
# Incluye análisis de [FPS-LIMITER], [SYNC-CHECK] y [PERFORMANCE-TRACE]

param(
    [string]$LogFile = "perf_step_0310.log"
)

Write-Host "=== Análisis de Verificación del Limitador de FPS - Step 0310 ===" -ForegroundColor Cyan
Write-Host ""

# Verificar que el archivo existe
if (-not (Test-Path $LogFile)) {
    Write-Host "ERROR: Archivo de log no encontrado: $LogFile" -ForegroundColor Red
    Write-Host "Ejecuta primero: python main.py roms/pkmn.gb > perf_step_0310.log 2>&1" -ForegroundColor Yellow
    exit 1
}

Write-Host "Archivo de log: $LogFile" -ForegroundColor Green
$fileSize = (Get-Item $LogFile).Length / 1KB
Write-Host "Tamaño del archivo: $([math]::Round($fileSize, 2)) KB" -ForegroundColor Gray
Write-Host ""

# ============================================================================
# 1. ANÁLISIS DE [FPS-LIMITER]
# ============================================================================
Write-Host "=== 1. Análisis de [FPS-LIMITER] ===" -ForegroundColor Cyan

$fpsLimiterCount = (Select-String -Path $LogFile -Pattern "\[FPS-LIMITER\]" | Measure-Object).Count
Write-Host "Registros [FPS-LIMITER] encontrados: $fpsLimiterCount" -ForegroundColor Cyan

if ($fpsLimiterCount -eq 0) {
    Write-Host "ADVERTENCIA: No se encontraron registros [FPS-LIMITER]" -ForegroundColor Yellow
    Write-Host "Verifica que el limitador esté activo en viboy.py" -ForegroundColor Yellow
} else {
    # Mostrar primeros 5 registros
    Write-Host ""
    Write-Host "Primeros 5 registros:" -ForegroundColor Gray
    Select-String -Path $LogFile -Pattern "\[FPS-LIMITER\]" | Select-Object -First 5 | ForEach-Object {
        Write-Host "  $($_.Line)" -ForegroundColor Gray
    }
    
    # Mostrar últimos 5 registros
    Write-Host ""
    Write-Host "Últimos 5 registros:" -ForegroundColor Gray
    Select-String -Path $LogFile -Pattern "\[FPS-LIMITER\]" | Select-Object -Last 5 | ForEach-Object {
        Write-Host "  $($_.Line)" -ForegroundColor Gray
    }
    
    # Extraer valores de tick_time y calcular estadísticas
    Write-Host ""
    Write-Host "Estadísticas de Tick Time:" -ForegroundColor Cyan
    $tickTimes = Select-String -Path $LogFile -Pattern "Tick time: ([\d.]+)ms" | ForEach-Object {
        if ($_.Matches.Groups.Count -gt 1) {
            [double]$_.Matches.Groups[1].Value
        }
    }
    
    if ($tickTimes.Count -gt 0) {
        # Excluir el primer valor (siempre es alto por inicialización) y valores anómalos (>100ms)
        $tickTimesFiltered = $tickTimes | Where-Object { $_ -le 100 }
        
        if ($tickTimesFiltered.Count -gt 0) {
            $tickStats = $tickTimesFiltered | Measure-Object -Average -Maximum -Minimum
            Write-Host "  Tick Time Promedio: $($tickStats.Average.ToString('F2'))ms (excluyendo inicialización)" -ForegroundColor Green
            Write-Host "  Tick Time Mínimo:   $($tickStats.Minimum.ToString('F2'))ms" -ForegroundColor Yellow
            Write-Host "  Tick Time Máximo:   $($tickStats.Maximum.ToString('F2'))ms" -ForegroundColor Green
            Write-Host "  Target (60 FPS):    16.67ms" -ForegroundColor Gray
            Write-Host "  Valores analizados: $($tickTimesFiltered.Count) de $($tickTimes.Count) (excluidos valores >100ms)" -ForegroundColor Gray
            
            # Evaluación
            Write-Host ""
            $targetTickTime = 16.67
            $diff = [math]::Abs($tickStats.Average - $targetTickTime)
            if ($diff -le 2.0) {
                Write-Host "  ✅ EXCELENTE: Tick time promedio está dentro de ±2ms del target" -ForegroundColor Green
            } elseif ($diff -le 5.0) {
                Write-Host "  ⚠️  ACEPTABLE: Tick time promedio está dentro de ±5ms del target" -ForegroundColor Yellow
            } else {
                Write-Host "  ❌ PROBLEMA: Tick time promedio está fuera del rango aceptable" -ForegroundColor Red
            }
        } else {
            Write-Host "  ERROR: No se encontraron valores válidos de tick_time (todos >100ms)" -ForegroundColor Red
        }
    } else {
        Write-Host "  ERROR: No se pudieron extraer valores de tick_time" -ForegroundColor Red
    }
}
Write-Host ""

# ============================================================================
# 2. ANÁLISIS DE [SYNC-CHECK]
# ============================================================================
Write-Host "=== 2. Análisis de [SYNC-CHECK] ===" -ForegroundColor Cyan

$syncCheckCount = (Select-String -Path $LogFile -Pattern "\[SYNC-CHECK\]" | Measure-Object).Count
Write-Host "Registros [SYNC-CHECK] encontrados: $syncCheckCount" -ForegroundColor Cyan

if ($syncCheckCount -eq 0) {
    Write-Host "ADVERTENCIA: No se encontraron registros [SYNC-CHECK]" -ForegroundColor Yellow
    Write-Host "Esto es normal si la ejecución duró menos de 1 minuto" -ForegroundColor Yellow
} else {
    # Mostrar todos los registros (deben ser pocos, solo cada minuto)
    Write-Host ""
    Write-Host "Todos los registros:" -ForegroundColor Gray
    Select-String -Path $LogFile -Pattern "\[SYNC-CHECK\]" | ForEach-Object {
        Write-Host "  $($_.Line)" -ForegroundColor Gray
    }
    
    # Extraer valores de drift y calcular estadísticas
    Write-Host ""
    Write-Host "Estadísticas de Drift:" -ForegroundColor Cyan
    $drifts = Select-String -Path $LogFile -Pattern "Drift: (-?\d+\.?\d*)" | ForEach-Object {
        if ($_.Matches.Groups.Count -gt 1) {
            [double]$_.Matches.Groups[1].Value
        }
    }
    
    if ($drifts.Count -gt 0) {
        $driftStats = $drifts | Measure-Object -Average -Maximum -Minimum
        Write-Host "  Drift Promedio: $($driftStats.Average.ToString('F2')) frames" -ForegroundColor Green
        Write-Host "  Drift Máximo:   $($driftStats.Maximum.ToString('F2')) frames" -ForegroundColor Yellow
        Write-Host "  Drift Mínimo:   $($driftStats.Minimum.ToString('F2')) frames" -ForegroundColor Green
        Write-Host "  Target:         0 frames (±10 frames aceptable)" -ForegroundColor Gray
        
        # Evaluación
        Write-Host ""
        $avgDriftAbs = [math]::Abs($driftStats.Average)
        if ($avgDriftAbs -le 10.0) {
            Write-Host "  ✅ EXCELENTE: Drift promedio está dentro del rango aceptable (±10 frames)" -ForegroundColor Green
        } elseif ($avgDriftAbs -le 30.0) {
            Write-Host "  ⚠️  ACEPTABLE: Drift promedio está dentro de ±30 frames (0.5 segundos)" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ PROBLEMA: Drift promedio es significativo (>30 frames)" -ForegroundColor Red
        }
        
        $maxDriftAbs = [math]::Abs($driftStats.Maximum)
        if ($maxDriftAbs -gt 30.0) {
            Write-Host "  ⚠️  ADVERTENCIA: Drift máximo excede ±30 frames" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ERROR: No se pudieron extraer valores de drift" -ForegroundColor Red
    }
}
Write-Host ""

# ============================================================================
# 3. ANÁLISIS DE [PERFORMANCE-TRACE]
# ============================================================================
Write-Host "=== 3. Análisis de [PERFORMANCE-TRACE] ===" -ForegroundColor Cyan

$traceCount = (Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Measure-Object).Count
Write-Host "Registros [PERFORMANCE-TRACE] encontrados: $traceCount" -ForegroundColor Cyan

if ($traceCount -eq 0) {
    Write-Host "ADVERTENCIA: No se encontraron registros [PERFORMANCE-TRACE]" -ForegroundColor Yellow
    Write-Host "Verifica que el monitor esté activado en renderer.py" -ForegroundColor Yellow
} else {
    # Mostrar primeros 5 registros
    Write-Host ""
    Write-Host "Primeros 5 registros:" -ForegroundColor Gray
    Select-String -Path $LogFile -Pattern "\[PERFORMANCE-TRACE\]" | Select-Object -First 5 | ForEach-Object {
        Write-Host "  $($_.Line)" -ForegroundColor Gray
    }
    
    # Extraer valores de FPS (limited) y calcular estadísticas
    Write-Host ""
    Write-Host "Estadísticas de FPS (Limited):" -ForegroundColor Cyan
    $fpsLimitedValues = Select-String -Path $LogFile -Pattern "FPS \(limited\): ([\d.]+)" | ForEach-Object {
        if ($_.Matches.Groups.Count -gt 1) {
            [double]$_.Matches.Groups[1].Value
        }
    }
    
    if ($fpsLimitedValues.Count -gt 0) {
        $fpsLimitedStats = $fpsLimitedValues | Measure-Object -Average -Maximum -Minimum
        Write-Host "  FPS (Limited) Promedio: $($fpsLimitedStats.Average.ToString('F2'))" -ForegroundColor Green
        Write-Host "  FPS (Limited) Mínimo:   $($fpsLimitedStats.Minimum.ToString('F2'))" -ForegroundColor Yellow
        Write-Host "  FPS (Limited) Máximo:   $($fpsLimitedStats.Maximum.ToString('F2'))" -ForegroundColor Green
        Write-Host "  Target:                 60.0 FPS" -ForegroundColor Gray
        
        # Evaluación
        Write-Host ""
        $targetFPS = 60.0
        $diff = [math]::Abs($fpsLimitedStats.Average - $targetFPS)
        if ($diff -le 5.0) {
            Write-Host "  ✅ EXCELENTE: FPS limitado promedio está dentro de ±5 FPS del target" -ForegroundColor Green
        } elseif ($diff -le 10.0) {
            Write-Host "  ⚠️  ACEPTABLE: FPS limitado promedio está dentro de ±10 FPS del target" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ PROBLEMA: FPS limitado promedio está fuera del rango aceptable" -ForegroundColor Red
        }
        
        # Comparación con Step 0308 (sin limitador, 300+ FPS)
        Write-Host ""
        Write-Host "Comparación con Step 0308 (sin limitador):" -ForegroundColor Cyan
        Write-Host "  Step 0308: ~306 FPS (sin limitación)" -ForegroundColor Gray
        Write-Host "  Step 0310: $($fpsLimitedStats.Average.ToString('F2')) FPS (con limitación)" -ForegroundColor Green
        $reduccion = 306.0 - $fpsLimitedStats.Average
        $reduccionPorcentual = ($reduccion / 306.0) * 100
        Write-Host "  Reducción: $($reduccion.ToString('F2')) FPS ($($reduccionPorcentual.ToString('F2'))%)" -ForegroundColor Green
        if ($fpsLimitedStats.Average -lt 100) {
            Write-Host "  ✅ CONFIRMADO: El limitador está funcionando (FPS reducido significativamente)" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  ADVERTENCIA: El limitador puede no estar funcionando correctamente" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ADVERTENCIA: No se encontraron valores de FPS (limited)" -ForegroundColor Yellow
        Write-Host "  Intentando extraer FPS general..." -ForegroundColor Yellow
        
        # Fallback: extraer FPS general
        $fpsValues = Select-String -Path $LogFile -Pattern "FPS: (\d+\.?\d*)" | ForEach-Object {
            if ($_.Matches.Groups.Count -gt 1) {
                [double]$_.Matches.Groups[1].Value
            }
        }
        
        if ($fpsValues.Count -gt 0) {
            $fpsStats = $fpsValues | Measure-Object -Average -Maximum -Minimum
            Write-Host "  FPS Promedio: $($fpsStats.Average.ToString('F2'))" -ForegroundColor Green
            Write-Host "  FPS Mínimo:   $($fpsStats.Minimum.ToString('F2'))" -ForegroundColor Yellow
            Write-Host "  FPS Máximo:   $($fpsStats.Maximum.ToString('F2'))" -ForegroundColor Green
        }
    }
}
Write-Host ""

# ============================================================================
# 4. EVALUACIÓN INTEGRADA
# ============================================================================
Write-Host "=== 4. Evaluación Integrada ===" -ForegroundColor Cyan

$evaluacionExitosa = $true
$problemas = @()

# Verificar tick_time
if ($tickTimes.Count -gt 0) {
    $targetTickTime = 16.67
    $diff = [math]::Abs($tickStats.Average - $targetTickTime)
    if ($diff -gt 5.0) {
        $evaluacionExitosa = $false
        $problemas += "Tick time promedio ($($tickStats.Average.ToString('F2'))ms) está fuera del rango aceptable (±5ms)"
    }
} else {
    $evaluacionExitosa = $false
    $problemas += "No se encontraron registros de tick_time"
}

# Verificar drift
if ($drifts.Count -gt 0) {
    $avgDriftAbs = [math]::Abs($driftStats.Average)
    if ($avgDriftAbs -gt 30.0) {
        $evaluacionExitosa = $false
        $problemas += "Drift promedio ($($driftStats.Average.ToString('F2')) frames) es significativo (>30 frames)"
    }
}

# Verificar FPS limitado
if ($fpsLimitedValues.Count -gt 0) {
    $targetFPS = 60.0
    $diff = [math]::Abs($fpsLimitedStats.Average - $targetFPS)
    if ($diff -gt 10.0) {
        $evaluacionExitosa = $false
        $problemas += "FPS limitado promedio ($($fpsLimitedStats.Average.ToString('F2'))) está fuera del rango aceptable (±10 FPS)"
    }
} else {
    $evaluacionExitosa = $false
    $problemas += "No se encontraron valores de FPS limitado"
}

# Resultado final
Write-Host ""
if ($evaluacionExitosa) {
    Write-Host "✅ ÉXITO: El limitador de FPS está funcionando correctamente" -ForegroundColor Green
    Write-Host ""
    Write-Host "Resumen:" -ForegroundColor Cyan
    if ($tickTimes.Count -gt 0) {
        Write-Host "  - Tick time: $($tickStats.Average.ToString('F2'))ms (target: 16.67ms)" -ForegroundColor Green
    }
    if ($drifts.Count -gt 0) {
        Write-Host "  - Drift: $($driftStats.Average.ToString('F2')) frames (target: 0 frames)" -ForegroundColor Green
    }
    if ($fpsLimitedValues.Count -gt 0) {
        Write-Host "  - FPS limitado: $($fpsLimitedStats.Average.ToString('F2')) FPS (target: 60 FPS)" -ForegroundColor Green
    }
} else {
    Write-Host "⚠️  PARCIAL o ❌ FALLO: Se detectaron problemas con el limitador de FPS" -ForegroundColor $(if ($problemas.Count -eq 1) { "Yellow" } else { "Red" })
    Write-Host ""
    Write-Host "Problemas detectados:" -ForegroundColor Cyan
    foreach ($problema in $problemas) {
        Write-Host "  - $problema" -ForegroundColor Red
    }
}
Write-Host ""

Write-Host "=== Análisis completado ===" -ForegroundColor Cyan

