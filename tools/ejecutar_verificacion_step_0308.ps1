# Script para ejecutar verificación de rendimiento Step 0308 con múltiples ROMs
# Ejecuta cada ROM durante 2 minutos y analiza los resultados

param(
    [int]$DuracionSegundos = 120  # 2 minutos por defecto
)

$roms = @(
    @{Nombre="pkmn.gb"; Archivo="roms/pkmn.gb"; Log="perf_step_0308_pkmn.log"},
    @{Nombre="tetris.gb"; Archivo="roms/tetris.gb"; Log="perf_step_0308_tetris.log"},
    @{Nombre="mario.gbc"; Archivo="roms/mario.gbc"; Log="perf_step_0308_mario.log"}
)

Write-Host "=== Verificación Step 0308 - Rendimiento ===" -ForegroundColor Cyan
Write-Host "Duración por ROM: $DuracionSegundos segundos (2 minutos)" -ForegroundColor Yellow
Write-Host ""

foreach ($rom in $roms) {
    Write-Host "Ejecutando: $($rom.Nombre)..." -ForegroundColor Green
    
    # Verificar que la ROM existe
    if (-not (Test-Path $rom.Archivo)) {
        Write-Host "  ⚠️  ROM no encontrada: $($rom.Archivo)" -ForegroundColor Yellow
        continue
    }
    
    # Ejecutar emulador en background
    $job = Start-Job -ScriptBlock {
        param($romPath, $logPath)
        python main.py $romPath > $logPath 2>&1
    } -ArgumentList $rom.Archivo, $rom.Log
    
    # Esperar el tiempo especificado
    Write-Host "  Esperando $DuracionSegundos segundos..." -ForegroundColor Gray
    Start-Sleep -Seconds $DuracionSegundos
    
    # Detener el proceso (el job se detendrá cuando termine el proceso)
    Write-Host "  Deteniendo emulador..." -ForegroundColor Gray
    Stop-Job -Job $job -ErrorAction SilentlyContinue
    Remove-Job -Job $job -ErrorAction SilentlyContinue
    
    # Matar cualquier proceso de Python que esté ejecutando main.py
    Get-Process python -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -like "*main.py*$($rom.Archivo)*"
    } | Stop-Process -Force -ErrorAction SilentlyContinue
    
    Write-Host "  ✅ Completado: $($rom.Log)" -ForegroundColor Green
    Write-Host ""
}

Write-Host "=== Verificación completada ===" -ForegroundColor Cyan
Write-Host "Analiza los logs con: .\tools\analizar_perf_step_0308.ps1 -LogFile <archivo.log>" -ForegroundColor Yellow

