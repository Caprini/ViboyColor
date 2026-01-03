#!/bin/bash
# Ejecutar headless RAW + MBC writes para 4 ROMs clave (Step 0451)

set -e

LOG_DIR="/tmp/viboy_0451/headless"
mkdir -p "$LOG_DIR"

ROMS=(
    "mario.gbc"
    "pkmn.gb"
    "tetris.gb"
    "tetris_dx.gbc"
)

echo "=========================================="
echo "Step 0451: Headless RAW + MBC Writes"
echo "=========================================="
echo "ROMs: ${ROMS[@]}"
echo "Frames: 240 por ROM"
echo "Logs: $LOG_DIR/"
echo ""

# Función para ejecutar headless
run_one() {
    local rom="$1"
    local out="$LOG_DIR/${rom}.txt"
    echo "[RUN] $rom -> $out"
    
    # Asegurar PYTHONPATH incluye el directorio raíz
    export PYTHONPATH="$(cd "$(dirname "$0")/.." && pwd):$PYTHONPATH"
    
    timeout 60 python3 tools/rom_smoke_0442.py "roms/${rom}" --frames 240 > "$out" 2>&1
    local exit_code=$?
    
    if [ $exit_code -ne 0 ]; then
        echo "[ERROR] Headless falló para $rom (exit code: $exit_code)" | tee -a "$out"
        return $exit_code
    fi
    
    echo "[OK] $rom completado"
}

# Ejecutar secuencialmente (no paralelo para evitar confusión)
for rom in "${ROMS[@]}"; do
    if [ -f "roms/${rom}" ]; then
        run_one "$rom"
    else
        echo "[SKIP] ROM no encontrada: roms/${rom}"
    fi
done

echo ""
echo "[DONE] Headless ejecutado. Logs en $LOG_DIR/"

