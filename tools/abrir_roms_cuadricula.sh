#!/bin/bash
# Script para abrir múltiples ROMs en ventanas organizadas en cuadrícula de 2 filas
# Para captura de pantalla - sin timing automático

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ROMS_DIR="$PROJECT_DIR/roms"

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🎮 Abriendo ROMs en cuadrícula de 2 filas...${NC}"

# Buscar todas las ROMs
ROMS=($(find "$ROMS_DIR" -type f \( -name "*.gb" -o -name "*.gbc" \) | sort))

if [ ${#ROMS[@]} -eq 0 ]; then
    echo "❌ No se encontraron ROMs en $ROMS_DIR"
    exit 1
fi

echo -e "${YELLOW}Encontradas ${#ROMS[@]} ROMs${NC}"

# Verificar si wmctrl está instalado
HAS_WMCTRL=false
if command -v wmctrl &> /dev/null; then
    HAS_WMCTRL=true
else
    echo "⚠️  wmctrl no está instalado."
    echo "   Para posicionar ventanas automáticamente, instala wmctrl:"
    echo "   sudo apt-get install wmctrl"
    echo "   Las ventanas se abrirán pero no se posicionarán automáticamente."
    echo ""
fi

# NO redimensionar ventanas, solo moverlas
# Obtener dimensiones reales de la primera ventana encontrada
# Espaciado entre ventanas (más compacto como en la captura)
SPACING=10

# Calcular posiciones para cuadrícula de 2 filas
# 4 columnas por fila (o distribuir según número de ROMs)
COLS_PER_ROW=4
ROWS=2

# Obtener resolución de pantalla
SCREEN_WIDTH=$(xrandr | grep '*' | head -n1 | awk '{print $1}' | cut -d'x' -f1)
SCREEN_HEIGHT=$(xrandr | grep '*' | head -n1 | awk '{print $1}' | cut -d'x' -f2)

# Calcular offset inicial (se ajustará después de obtener dimensiones reales)
START_Y=30  # Margen superior (más compacto como en la captura)

echo -e "${GREEN}Abriendo ${#ROMS[@]} ventanas...${NC}"

# Array para almacenar PIDs
declare -a PIDS=()

# Abrir cada ROM en background
for i in "${!ROMS[@]}"; do
    ROM="${ROMS[$i]}"
    ROM_NAME=$(basename "$ROM")
    
    echo "  → Abriendo: $ROM_NAME"
    
    # Cambiar al directorio del proyecto y ejecutar en background
    (cd "$PROJECT_DIR" && python3 main.py "$ROM" > /dev/null 2>&1) &
    PID=$!
    PIDS+=($PID)
    
    # Pequeña pausa entre aperturas para que el sistema pueda manejar las ventanas
    sleep 0.5
done

echo -e "${YELLOW}Esperando a que las ventanas se abran...${NC}"
sleep 5  # Esperar más tiempo para que todas las ventanas se inicialicen completamente

# Posicionar ventanas (solo si wmctrl está disponible)
if [ "$HAS_WMCTRL" = true ]; then
    echo -e "${GREEN}Posicionando ventanas en cuadrícula...${NC}"
    
    # Esperar un poco más y luego obtener ventanas recientes
    sleep 3
    
    # Obtener SOLO ventanas que contengan "ViboyColor" en el título (muy específico)
    # Usar formato completo de wmctrl -l para obtener título también
    WINDOW_LIST=$(wmctrl -l | grep -i "ViboyColor")
    
    if [ -z "$WINDOW_LIST" ]; then
        echo "  ❌ No se encontraron ventanas con 'ViboyColor' en el título"
        echo "     Las ventanas pueden no haberse inicializado completamente."
        echo "     Espera unos segundos más y ejecuta el script de nuevo."
        exit 1
    fi
    
    # Filtrar ventanas por tamaño razonable (entre 300-800 píxeles de ancho)
    # Esto excluye ventanas grandes como Cursor u otros editores
    FILTERED_WINDOWS=""
    while IFS= read -r line; do
        WINDOW_ID=$(echo "$line" | awk '{print $1}')
        # Obtener geometría de esta ventana
        GEOM=$(wmctrl -lG | grep "^$WINDOW_ID" | awk '{print $5, $6}')
        if [ -n "$GEOM" ]; then
            WIDTH=$(echo $GEOM | awk '{print $1}')
            HEIGHT=$(echo $GEOM | awk '{print $2}')
            # Solo incluir si el ancho está en rango razonable (300-2000 píxeles)
            # Las ventanas pueden ser más grandes si están maximizadas o escaladas
            if [ $WIDTH -ge 300 ] && [ $WIDTH -le 2000 ]; then
                FILTERED_WINDOWS="$FILTERED_WINDOWS$WINDOW_ID\n"
            else
                echo "  ⚠️  Excluyendo ventana $WINDOW_ID (tamaño fuera de rango: ${WIDTH}x${HEIGHT})"
            fi
        fi
    done <<< "$WINDOW_LIST"
    
    WINDOWS=$(echo -e "$FILTERED_WINDOWS" | grep -v '^$')
    WINDOW_COUNT_FOUND=$(echo "$WINDOWS" | wc -l)
    
    if [ $WINDOW_COUNT_FOUND -lt ${#ROMS[@]} ]; then
        echo "  ⚠️  Se encontraron $WINDOW_COUNT_FOUND ventanas válidas, se esperaban ${#ROMS[@]}"
        echo "     Esperando un poco más..."
        sleep 2
        WINDOW_LIST=$(wmctrl -l | grep -i "ViboyColor")
        FILTERED_WINDOWS=""
        while IFS= read -r line; do
            WINDOW_ID=$(echo "$line" | awk '{print $1}')
            GEOM=$(wmctrl -lG | grep "^$WINDOW_ID" | awk '{print $5, $6}')
            if [ -n "$GEOM" ]; then
                WIDTH=$(echo $GEOM | awk '{print $1}')
                if [ $WIDTH -ge 300 ] && [ $WIDTH -le 2000 ]; then
                    FILTERED_WINDOWS="$FILTERED_WINDOWS$WINDOW_ID\n"
                fi
            fi
        done <<< "$WINDOW_LIST"
        WINDOWS=$(echo -e "$FILTERED_WINDOWS" | grep -v '^$')
        WINDOW_COUNT_FOUND=$(echo "$WINDOWS" | wc -l)
    fi
    
    if [ $WINDOW_COUNT_FOUND -eq 0 ]; then
        echo "  ❌ No se encontraron ventanas válidas del emulador"
        exit 1
    fi
    
    # Usar dimensiones estándar del emulador (no calcular promedio)
    # Tamaño estándar: escala 3x = 480x432 + barra de título ≈ 480x480
    WINDOW_WIDTH=480
    WINDOW_HEIGHT=480
    echo "  📐 Usando dimensiones estándar: ${WINDOW_WIDTH}x${WINDOW_HEIGHT}"
    
    # Calcular offset inicial para centrar (asegurar que no sea negativo)
    TOTAL_GRID_WIDTH=$((COLS_PER_ROW * WINDOW_WIDTH + (COLS_PER_ROW - 1) * SPACING))
    START_X=$(( (SCREEN_WIDTH - TOTAL_GRID_WIDTH) / 2 ))
    # Asegurar que START_X no sea negativo
    if [ $START_X -lt 0 ]; then
        START_X=10  # Margen mínimo
        echo "  ⚠️  Ajustando START_X a $START_X (pantalla muy pequeña)"
    fi
    
    # Contador para ventanas encontradas
    WINDOW_COUNT=0
    
    for WINDOW_ID in $WINDOWS; do
        if [ $WINDOW_COUNT -ge ${#ROMS[@]} ]; then
            break
        fi
        
        # Verificar que la ventana realmente contiene "ViboyColor" en el título
        WINDOW_TITLE=$(wmctrl -l | grep "^$WINDOW_ID" | cut -d' ' -f5-)
        if [[ ! "$WINDOW_TITLE" =~ [Vv]iboy[Cc]olor ]]; then
            echo "  ⚠️  Saltando ventana $WINDOW_ID (no contiene 'ViboyColor'): $WINDOW_TITLE"
            continue
        fi
        
        # Calcular posición en la cuadrícula
        ROW=$((WINDOW_COUNT / COLS_PER_ROW))
        COL=$((WINDOW_COUNT % COLS_PER_ROW))
        
        X=$((START_X + COL * (WINDOW_WIDTH + SPACING)))
        Y=$((START_Y + ROW * (WINDOW_HEIGHT + SPACING)))
        
        # Mover y redimensionar la ventana a un tamaño estándar para la cuadrícula
        # Tamaño estándar del emulador (escala 3x: 480x432 + barra de título)
        TARGET_WIDTH=480
        TARGET_HEIGHT=480
        
        # Redimensionar y mover la ventana
        if wmctrl -i -r "$WINDOW_ID" -e 0,$X,$Y,$TARGET_WIDTH,$TARGET_HEIGHT 2>/dev/null; then
            ROM_NAME=$(basename "${ROMS[$WINDOW_COUNT]}")
            echo "  → [$((WINDOW_COUNT + 1))/${#ROMS[@]}] $ROM_NAME → ($X, $Y) [${TARGET_WIDTH}x${TARGET_HEIGHT}]"
        else
            echo "  ⚠️  Error moviendo/redimensionando ventana $WINDOW_ID"
        fi
        
        WINDOW_COUNT=$((WINDOW_COUNT + 1))
        
        # Pequeña pausa entre posicionamientos
        sleep 0.2
    done
else
    echo -e "${YELLOW}⚠️  Saltando posicionamiento automático (wmctrl no disponible)${NC}"
    echo "   Puedes posicionar las ventanas manualmente o instalar wmctrl:"
    echo "   sudo apt-get install wmctrl"
fi

echo ""
echo -e "${GREEN}✅ Todas las ventanas abiertas y posicionadas${NC}"
echo -e "${YELLOW}💡 Cierra las ventanas manualmente cuando termines${NC}"
echo ""
echo "PIDs de procesos: ${PIDS[@]}"
echo "Para cerrar todas las ventanas: kill ${PIDS[@]}"

