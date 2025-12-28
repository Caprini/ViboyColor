# Script de Verificación Manual Step 0318
# Ejecuta verificaciones y documenta resultados

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación Step 0318 - Verificaciones Manuales Finales" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Verificar que existe la ROM
$romPath = "roms/pkmn.gb"
if (-not (Test-Path $romPath)) {
    Write-Host "ERROR: No se encuentra la ROM: $romPath" -ForegroundColor Red
    exit 1
}

Write-Host "ROM encontrada: $romPath" -ForegroundColor Green
Write-Host ""

# Instrucciones para el usuario
Write-Host "INSTRUCCIONES DE VERIFICACIÓN:" -ForegroundColor Yellow
Write-Host "1. El emulador se ejecutará en una ventana" -ForegroundColor White
Write-Host "2. Observa el FPS en la barra de título de la ventana" -ForegroundColor White
Write-Host "3. Observa durante 2 minutos y anota:" -ForegroundColor White
Write-Host "   - FPS promedio observado" -ForegroundColor White
Write-Host "   - FPS mínimo y máximo" -ForegroundColor White
Write-Host "   - Estabilidad (estable/variable)" -ForegroundColor White
Write-Host "   - Smoothness del movimiento" -ForegroundColor White
Write-Host "4. Verifica visualmente:" -ForegroundColor White
Write-Host "   - ¿Se muestran tiles/gráficos?" -ForegroundColor White
Write-Host "   - ¿Hay pantalla blanca?" -ForegroundColor White
Write-Host "   - ¿El renderizado es estable?" -ForegroundColor White
Write-Host "5. Prueba los controles:" -ForegroundColor White
Write-Host "   - D-Pad (→ ← ↑ ↓)" -ForegroundColor White
Write-Host "   - Botones A (Z) y B (X)" -ForegroundColor White
Write-Host "   - Start (RETURN) y Select (RSHIFT)" -ForegroundColor White
Write-Host ""
Write-Host "Presiona ENTER para iniciar el emulador..." -ForegroundColor Yellow
Read-Host

# Ejecutar emulador
Write-Host "Ejecutando emulador..." -ForegroundColor Green
Write-Host "Observa la ventana y anota los resultados." -ForegroundColor Yellow
Write-Host "Presiona Ctrl+C en esta ventana cuando termines de observar." -ForegroundColor Yellow
Write-Host ""

python main.py $romPath

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación completada" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ahora completa los documentos de verificación con tus observaciones:" -ForegroundColor Yellow
Write-Host "1. VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md" -ForegroundColor White
Write-Host "2. VERIFICACION_RENDERIZADO_STEP_0312.md" -ForegroundColor White
Write-Host "3. COMPATIBILIDAD_GB_GBC_STEP_0315.md" -ForegroundColor White
Write-Host "4. VERIFICACION_CONTROLES_STEP_0315.md" -ForegroundColor White
Write-Host ""

