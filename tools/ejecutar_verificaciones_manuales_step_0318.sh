#!/bin/bash
# Script de Verificación Manual - Step 0318
# Ejecuta el emulador y guía al usuario en las verificaciones

set -e

echo "============================================================"
echo "Verificación Manual - Step 0318"
echo "============================================================"
echo ""

# Verificar que pygame está instalado
echo "🔍 Verificando pygame..."
if ! python3 -c "import pygame" 2>/dev/null; then
    echo "❌ ERROR: pygame no está instalado"
    echo ""
    echo "Por favor, instala pygame con uno de estos métodos:"
    echo "  1. sudo apt install python3-pygame"
    echo "  2. pip install pygame-ce (en un entorno virtual)"
    echo ""
    exit 1
fi

echo "✅ pygame está instalado"
echo ""

# Verificar que la ROM existe
ROM_PATH="roms/pkmn.gb"
if [ ! -f "$ROM_PATH" ]; then
    echo "❌ ERROR: No se encuentra la ROM: $ROM_PATH"
    exit 1
fi

echo "✅ ROM encontrada: $ROM_PATH"
echo ""

echo "============================================================"
echo "INSTRUCCIONES DE VERIFICACIÓN"
echo "============================================================"
echo ""
echo "El emulador se ejecutará ahora. Por favor:"
echo ""
echo "1. 📊 VERIFICACIÓN DE FPS:"
echo "   - Observa la barra de título (muestra 'FPS: XX.X')"
echo "   - Observa durante 2 minutos"
echo "   - Anota: FPS promedio, mínimo, máximo, estabilidad"
echo ""
echo "2. 👁️  VERIFICACIÓN VISUAL:"
echo "   - ¿Se muestran gráficos/tiles? (NO debe ser pantalla blanca)"
echo "   - ¿Qué patrones ves? (checkerboard, líneas, etc.)"
echo "   - ¿El renderizado es estable? (sin parpadeos excesivos)"
echo ""
echo "3. 🎮 VERIFICACIÓN DE CONTROLES (opcional ahora):"
echo "   - Prueba: D-Pad (→←↑↓), Z (A), X (B), RETURN (Start), RSHIFT (Select)"
echo "   - Observa si el juego reacciona"
echo ""
echo "Presiona Ctrl+C para detener el emulador cuando termines."
echo ""
echo "============================================================"
echo "EJECUTANDO EMULADOR..."
echo "============================================================"
echo ""

# Ejecutar emulador
cd "$(dirname "$0")/.."
python3 main.py "$ROM_PATH"

