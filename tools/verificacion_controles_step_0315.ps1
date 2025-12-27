# Script de Verificación de Controles - Step 0315
# Este script documenta el mapeo de teclas y verifica controles

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación de Controles" -ForegroundColor Cyan
Write-Host "Step 0315" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Mapeo de teclas según renderer.py
Write-Host "📋 Mapeo de Teclas (según src/gpu/renderer.py):" -ForegroundColor Green
Write-Host ""

Write-Host "Direcciones:" -ForegroundColor Yellow
Write-Host "  → (RIGHT)     → Botón Right" -ForegroundColor White
Write-Host "  ← (LEFT)      → Botón Left" -ForegroundColor White
Write-Host "  ↑ (UP)        → Botón Up" -ForegroundColor White
Write-Host "  ↓ (DOWN)      → Botón Down" -ForegroundColor White
Write-Host ""

Write-Host "Botones de Acción:" -ForegroundColor Yellow
Write-Host "  Z o A         → Botón A" -ForegroundColor White
Write-Host "  X o S         → Botón B" -ForegroundColor White
Write-Host ""

Write-Host "Botones del Menú:" -ForegroundColor Yellow
Write-Host "  RETURN        → Start" -ForegroundColor White
Write-Host "  RSHIFT        → Select" -ForegroundColor White
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Instrucciones para Verificación Manual" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Ejecuta el emulador:" -ForegroundColor Yellow
Write-Host "   python main.py roms/pkmn.gb" -ForegroundColor White
Write-Host ""
Write-Host "2. Prueba cada botón manualmente:" -ForegroundColor Yellow
Write-Host "   - Presiona cada tecla y observa si responde" -ForegroundColor White
Write-Host "   - Si el juego muestra menú o personaje, prueba navegación" -ForegroundColor White
Write-Host "   - Verifica que la entrada se registra correctamente" -ForegroundColor White
Write-Host ""
Write-Host "3. Documenta los resultados:" -ForegroundColor Yellow
Write-Host "   - Completa VERIFICACION_CONTROLES_STEP_0315.md" -ForegroundColor White
Write-Host "   - Indica qué botones funcionan y cuáles no" -ForegroundColor White
Write-Host "   - Describe cualquier problema encontrado" -ForegroundColor White
Write-Host ""

# Verificar que el código de mapeo existe
$rendererPath = "src/gpu/renderer.py"
if (Test-Path $rendererPath) {
    Write-Host "✅ Código de mapeo encontrado en: $rendererPath" -ForegroundColor Green
    Write-Host ""
    
    # Buscar el mapeo de teclas
    $keyMapLines = Select-String -Path $rendererPath -Pattern "KEY_MAP|pygame\.K_" | Select-Object -First 15
    if ($keyMapLines) {
        Write-Host "📝 Mapeo encontrado en el código:" -ForegroundColor Green
        $keyMapLines | ForEach-Object { Write-Host "   $($_.Line)" -ForegroundColor Gray }
    }
} else {
    Write-Host "⚠️  ADVERTENCIA: No se encontró $rendererPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Verificación de Joypad (src/io/joypad.py)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$joypadPath = "src/io/joypad.py"
if (Test-Path $joypadPath) {
    Write-Host "✅ Módulo Joypad encontrado" -ForegroundColor Green
    
    # Verificar métodos disponibles
    $methods = Select-String -Path $joypadPath -Pattern "def (press|release|get_state)" | Select-Object -First 5
    if ($methods) {
        Write-Host "📝 Métodos disponibles:" -ForegroundColor Green
        $methods | ForEach-Object { Write-Host "   $($_.Line)" -ForegroundColor Gray }
    }
} else {
    Write-Host "⚠️  ADVERTENCIA: No se encontró $joypadPath" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "✅ Verificación de código completada" -ForegroundColor Green
Write-Host "   Ahora ejecuta el emulador manualmente y prueba los controles" -ForegroundColor Yellow
Write-Host ""

