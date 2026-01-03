#!/bin/bash
# Ejecutar headless en paralelo y capturar logs (Step 0449)

set -e

LOG_DIR="/tmp/viboy_0449/headless"
mkdir -p "$LOG_DIR"

ROMS=(
    "mario.gbc"
    "pkmn.gb"
    "tetris.gb"
    "tetris_dx.gbc"
)

echo "=========================================="
echo "Step 0449: Headless Parallel Execution"
echo "=========================================="
echo "ROMs: ${ROMS[@]}"
echo "Frames: 120 por ROM"
echo "Logs: $LOG_DIR/"
echo ""

# Función para ejecutar headless
run_headless() {
    local rom="$1"
    local out="$LOG_DIR/${rom}.txt"
    echo "[RUN-HEADLESS] $rom -> $out"
    
    python3 tools/rom_smoke_0442.py "roms/${rom}" --frames 120 > "$out" 2>&1 &
}

# Lanzar todas las ROMs en paralelo
for rom in "${ROMS[@]}"; do
    if [ -f "roms/${rom}" ]; then
        run_headless "$rom"
        sleep 0.5
    else
        echo "[SKIP] ROM no encontrada: roms/${rom}"
    fi
done

echo ""
echo "[WAIT] Esperando finalización de todas las instancias headless..."
wait

echo ""
echo "[DONE-HEADLESS] Todas las instancias headless finalizadas. Logs en $LOG_DIR/"
echo ""

