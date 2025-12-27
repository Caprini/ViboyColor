# Script de Verificación de Compatibilidad GB/GBC - Step 0315
# Este script prueba múltiples ROMs de GB y GBC

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación de Compatibilidad GB/GBC" -ForegroundColor Cyan
Write-Host "Step 0315" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ROMs a probar
$romsGB = @(
    "roms/pkmn.gb",
    "roms/tetris.gb"
)

$romsGBC = @(
    "roms/mario.gbc",
    "roms/tetris_dx.gbc"
)

$results = @()

# Función para probar una ROM
function Test-Rom {
    param(
        [string]$RomPath,
        [string]$Type
    )
    
    Write-Host "Probando: $RomPath ($Type)" -ForegroundColor Yellow
    
    if (-not (Test-Path $RomPath)) {
        Write-Host "  ❌ ROM no encontrada" -ForegroundColor Red
        return @{
            Rom = $RomPath
            Type = $Type
            Status = "No encontrada"
            Loads = $false
            Renders = $false
            Errors = @()
        }
    }
    
    # Ejecutar emulador por 5 segundos para verificar carga y renderizado
    $logFile = "logs/compat_$(Split-Path $RomPath -Leaf).log"
    $job = Start-Job -ScriptBlock {
        param($rom, $log)
        python main.py $rom > $log 2>&1
    } -ArgumentList $RomPath, $logFile
    
    # Esperar 5 segundos
    try {
        Wait-Job -Job $job -Timeout 5 | Out-Null
        if ($job.State -eq "Running") {
            Stop-Job -Job $job
        }
    } catch {
        Stop-Job -Job $job -ErrorAction SilentlyContinue
    }
    
    Wait-Job -Job $job | Out-Null
    Remove-Job -Job $job
    
    # Analizar logs
    $loads = $false
    $renders = $false
    $errors = @()
    
    if (Test-Path $logFile) {
        # Verificar si cargó correctamente (buscar mensajes de carga exitosa)
        $loadLines = Select-String -Path $logFile -Pattern "Cartucho cargado|Sistema listo|CPU inicializada"
        if ($loadLines) {
            $loads = $true
        }
        
        # Verificar si hay errores
        $errorLines = Select-String -Path $logFile -Pattern "ERROR|Exception|Traceback" | Select-Object -First 10
        if ($errorLines) {
            $errors = $errorLines | ForEach-Object { $_.Line }
        }
        
        # Verificar si renderiza (buscar mensajes de renderizado)
        $renderLines = Select-String -Path $logFile -Pattern "render|framebuffer|tile"
        if ($renderLines) {
            $renders = $true
        }
    }
    
    $status = if ($loads -and -not $errors) { "Funciona" } elseif ($loads) { "Parcial" } else { "No funciona" }
    
    Write-Host "  Estado: $status" -ForegroundColor $(if ($status -eq "Funciona") { "Green" } elseif ($status -eq "Parcial") { "Yellow" } else { "Red" })
    if ($loads) { Write-Host "  ✅ Carga: OK" -ForegroundColor Green }
    if ($renders) { Write-Host "  ✅ Renderizado: OK" -ForegroundColor Green }
    if ($errors.Count -gt 0) { Write-Host "  ⚠️  Errores: $($errors.Count)" -ForegroundColor Yellow }
    
    return @{
        Rom = $RomPath
        Type = $Type
        Status = $status
        Loads = $loads
        Renders = $renders
        Errors = $errors
    }
}

# Probar ROMs GB
Write-Host "📦 Probando ROMs GB (DMG):" -ForegroundColor Cyan
Write-Host ""
foreach ($rom in $romsGB) {
    $result = Test-Rom -RomPath $rom -Type "GB"
    $results += $result
    Write-Host ""
}

# Probar ROMs GBC
Write-Host "📦 Probando ROMs GBC:" -ForegroundColor Cyan
Write-Host ""
foreach ($rom in $romsGBC) {
    $result = Test-Rom -RomPath $rom -Type "GBC"
    $results += $result
    Write-Host ""
}

# Resumen
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Resumen de Compatibilidad" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$gbResults = $results | Where-Object { $_.Type -eq "GB" }
$gbcResults = $results | Where-Object { $_.Type -eq "GBC" }

Write-Host "ROMs GB probadas: $($gbResults.Count)" -ForegroundColor Green
$gbWorking = ($gbResults | Where-Object { $_.Status -eq "Funciona" }).Count
Write-Host "  Funcionan: $gbWorking" -ForegroundColor $(if ($gbWorking -eq $gbResults.Count) { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "ROMs GBC probadas: $($gbcResults.Count)" -ForegroundColor Green
$gbcWorking = ($gbcResults | Where-Object { $_.Status -eq "Funciona" }).Count
Write-Host "  Funcionan: $gbcWorking" -ForegroundColor $(if ($gbcWorking -eq $gbcResults.Count) { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "✅ Resultados detallados guardados para documentación" -ForegroundColor Green
Write-Host "   Completa COMPATIBILIDAD_GB_GBC_STEP_0315.md con estos resultados" -ForegroundColor Yellow
Write-Host ""

