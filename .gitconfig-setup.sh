#!/bin/bash
# Script de configuración de Git para ViboyColor
# Ejecutar: bash .gitconfig-setup.sh

echo "=== Configuración de Git para ViboyColor ==="
echo ""

# Verificar configuración actual
echo "📋 Configuración actual:"
echo "  User name: $(git config user.name 2>/dev/null || echo 'No configurado')"
echo "  User email: $(git config user.email 2>/dev/null || echo 'No configurado')"
echo "  Remote origin: $(git config --get remote.origin.url 2>/dev/null || echo 'No configurado')"
echo ""

# Configurar usuario (usar valores del repositorio si están disponibles)
GIT_USER="${GIT_USER:-Caprini}"
GIT_EMAIL="${GIT_EMAIL:-}"

# Solicitar email si no está configurado
if [ -z "$GIT_EMAIL" ]; then
    read -p "📧 Ingresa tu email de GitHub (o presiona Enter para usar el valor por defecto): " input_email
    if [ -n "$input_email" ]; then
        GIT_EMAIL="$input_email"
    else
        # Intentar obtener email de GitHub si es posible
        GIT_EMAIL="${GIT_USER}@users.noreply.github.com"
        echo "   Usando email por defecto: $GIT_EMAIL"
    fi
fi

# Configurar git localmente (solo para este repositorio)
echo ""
echo "🔧 Configurando Git para este repositorio..."
git config user.name "$GIT_USER"
git config user.email "$GIT_EMAIL"

# Verificar remoto
REMOTE_URL=$(git config --get remote.origin.url)
if [ -z "$REMOTE_URL" ]; then
    echo "⚠️  No hay remoto configurado. Configurando..."
    git remote add origin https://github.com/Caprini/ViboyColor.git
else
    echo "✅ Remoto ya configurado: $REMOTE_URL"
fi

# Configurar rama por defecto
echo ""
echo "🔧 Configurando rama por defecto..."
git config branch.develop-v0.0.2.remote origin
git config branch.develop-v0.0.2.merge refs/heads/develop-v0.0.2

# Verificar configuración final
echo ""
echo "✅ Configuración completada:"
echo "  User name: $(git config user.name)"
echo "  User email: $(git config user.email)"
echo "  Remote origin: $(git config --get remote.origin.url)"
echo ""
echo "📊 Estado del repositorio:"
git status --short | head -20
echo ""
echo "💡 Para hacer push de tus commits:"
echo "   git push origin develop-v0.0.2"
echo ""

