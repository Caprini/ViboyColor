# Script de verificación visual para Step 0312
# Ejecuta el emulador durante 15 segundos para verificación visual

Write-Host "Step 0312: Verificación Visual del Renderizado con Tiles Cargados" -ForegroundColor Cyan
Write-Host "=" * 70

# Verificar que existe la ROM
$romPath = "roms/pkmn.gb"
if (-not (Test-Path $romPath)) {
    Write-Host "ERROR: No se encuentra la ROM en $romPath" -ForegroundColor Red
    exit 1
}

Write-Host "ROM encontrada: $romPath" -ForegroundColor Green
Write-Host ""
Write-Host "Ejecutando emulador durante 15 segundos..." -ForegroundColor Yellow
Write-Host "Observa la ventana del emulador para verificar el renderizado." -ForegroundColor Yellow
Write-Host ""

# Ejecutar emulador con timeout de 15 segundos
# Redirigir salida a archivo temporal para no saturar contexto
$logFile = "logs/verificacion_step_0312.log"
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# Ejecutar con timeout (PowerShell 5.1+)
$job = Start-Job -ScriptBlock {
    param($rom)
    Set-Location $using:PWD
    python main.py $rom 2>&1
} -ArgumentList $romPath

# Esperar 15 segundos
Start-Sleep -Seconds 15

# Detener el job
Stop-Job -Job $job
Remove-Job -Job $job -Force

Write-Host ""
Write-Host "Ejecución completada (15 segundos)" -ForegroundColor Green
Write-Host ""
Write-Host "RESULTADOS DE VERIFICACIÓN VISUAL:" -ForegroundColor Cyan
Write-Host "Por favor, responde las siguientes preguntas:" -ForegroundColor Yellow
Write-Host "1. El emulador inicio correctamente? (Si/No)"
Write-Host "2. Aparecio la ventana? (Si/No)"
Write-Host "3. Se muestran graficos en la pantalla? (Si/No/Parcial)"
Write-Host "4. Que se ve en la pantalla? (Descripcion breve)"
Write-Host "5. Hay errores en la consola? (Si/No - Si si, describe)"
Write-Host "6. FPS reportado en la barra de titulo? (Si/No - Si si, que valor?)"
Write-Host ""

