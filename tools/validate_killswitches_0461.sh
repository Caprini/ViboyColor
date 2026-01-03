#!/bin/bash
# Step 0461: Validación Visual Controlada - Verificar que kill-switches funcionan
# Ejecuta UI y captura logs mínimos para verificar que no hay interferencias activas

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROMS_DIR="$PROJECT_DIR/roms"

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}🔍 Step 0461: Validación de Kill-Switches${NC}"
echo ""

# Asegurar que kill-switches están OFF por defecto
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

echo -e "${YELLOW}Kill-switches configurados (OFF por defecto):${NC}"
echo "  VIBOY_DEBUG_INJECTION=0"
echo "  VIBOY_AUTOPRESS=0"
echo "  VIBOY_FORCE_BGP=0"
echo "  VIBOY_FRAMEBUFFER_TRACE=0"
echo ""

# Buscar ROMs disponibles
ROMS=($(find "$ROMS_DIR" -type f \( -name "*.gb" -o -name "*.gbc" \) | head -n 2))

if [ ${#ROMS[@]} -eq 0 ]; then
    echo -e "${RED}❌ No se encontraron ROMs en $ROMS_DIR${NC}"
    exit 1
fi

echo -e "${YELLOW}Ejecutando validación con ${#ROMS[@]} ROM(s)...${NC}"
echo ""

# Función para analizar logs
analyze_logs() {
    local ROM_NAME=$1
    local LOG_FILE=$2
    
    echo -e "${GREEN}=== Análisis para ${ROM_NAME} ===${NC}"
    
    # Verificar path real
    if grep -q "\[UI-PATH\]" "$LOG_FILE" 2>/dev/null; then
        echo "✅ Path detectado:"
        grep "\[UI-PATH\]" "$LOG_FILE" | head -n 1 | sed 's/^/  /'
    else
        echo -e "${YELLOW}⚠️  No se detectó [UI-PATH] en logs${NC}"
    fi
    
    # Verificar registros I/O (primeros 5 frames)
    echo ""
    echo "Registros I/O (primeros 5 frames):"
    if grep -q "\[UI-PATH\]" "$LOG_FILE" 2>/dev/null; then
        grep "\[UI-PATH\]" "$LOG_FILE" | head -n 5 | \
            grep -oE "PC=[0-9A-Fa-f]+|LCDC=[0-9A-Fa-f]+|BGP=[0-9A-Fa-f]+|SCX=[0-9]+|SCY=[0-9]+|LY=[0-9]+" | \
            head -n 10 | sed 's/^/  /'
    else
        echo "  (No disponible)"
    fi
    
    # Verificar si hay debug pattern activo
    echo ""
    echo "Debug pattern activo?:"
    if grep -q "\[DEBUG-INJECTION\]" "$LOG_FILE" 2>/dev/null; then
        echo -e "${RED}❌ SÍ (interferencia detectada)${NC}"
        grep "\[DEBUG-INJECTION\]" "$LOG_FILE" | head -n 3 | sed 's/^/  /'
    else
        echo -e "${GREEN}✅ NO (ninguna interferencia detectada)${NC}"
    fi
    
    # Verificar SCY (scroll normal vs interferencia)
    echo ""
    echo "SCY values (primeros 5 frames):"
    if grep -q "\[UI-PATH\]" "$LOG_FILE" 2>/dev/null; then
        SCY_VALUES=$(grep "\[UI-PATH\]" "$LOG_FILE" | head -n 5 | grep -oE "SCY=[0-9]+" | cut -d= -f2)
        if [ -n "$SCY_VALUES" ]; then
            echo "$SCY_VALUES" | sed 's/^/  /'
            # Verificar si SCY está cambiando (scroll normal) o estable (posible interferencia)
            UNIQUE_SCY=$(echo "$SCY_VALUES" | sort -u | wc -l)
            if [ "$UNIQUE_SCY" -gt 1 ]; then
                echo -e "  ${GREEN}✅ SCY cambiando (scroll normal)${NC}"
            else
                echo -e "  ${YELLOW}⚠️  SCY estable (posible interferencia o pantalla estática)${NC}"
            fi
        else
            echo "  (No disponible)"
        fi
    else
        echo "  (No disponible)"
    fi
    
    echo ""
}

# Ejecutar validación para cada ROM
for ROM in "${ROMS[@]}"; do
    ROM_NAME=$(basename "$ROM")
    LOG_FILE="/tmp/viboy_0461_validate_${ROM_NAME}.log"
    
    echo -e "${YELLOW}Ejecutando ${ROM_NAME} (5 segundos)...${NC}"
    
    # Ejecutar UI con logs (timeout 5 segundos)
    timeout 5s python3 "$PROJECT_DIR/src/viboy.py" "$ROM" 2>&1 | \
        grep -E "\[UI-PATH\]|\[DEBUG-INJECTION\]|\[PPU-.*\]|\[CHECKERBOARD-STATE\]" | \
        head -n 50 > "$LOG_FILE" || true
    
    # Analizar logs
    analyze_logs "$ROM_NAME" "$LOG_FILE"
    
    echo "---"
    echo ""
done

echo -e "${GREEN}✅ Validación completada${NC}"
echo ""
echo "Resumen:"
echo "  - Kill-switches verificados (OFF por defecto)"
echo "  - Logs capturados para análisis"
echo "  - Interferencias detectadas: $(grep -l "\[DEBUG-INJECTION\]" /tmp/viboy_0461_validate_*.log 2>/dev/null | wc -l) archivo(s)"
echo ""

