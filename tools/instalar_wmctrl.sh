#!/bin/bash
# Script auxiliar para instalar wmctrl

echo "🔧 Verificando wmctrl..."

if command -v wmctrl &> /dev/null; then
    echo "✅ wmctrl ya está instalado"
    wmctrl --version
else
    echo "📦 Instalando wmctrl..."
    echo "   (Se requiere contraseña de sudo)"
    sudo apt-get update && sudo apt-get install -y wmctrl
    
    if command -v wmctrl &> /dev/null; then
        echo "✅ wmctrl instalado correctamente"
        wmctrl --version
    else
        echo "❌ Error instalando wmctrl"
        exit 1
    fi
fi

