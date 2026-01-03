#!/bin/bash
# Ejecutar UI en paralelo con varias ROMs para capturar logs (Step 0447)

set -e

# Directorio de logs
LOG_DIR="/tmp/viboy_0447"
mkdir -p "$LOG_DIR"

# ROMs a probar
ROMS=(
    "mario.gbc"      # Crítico: antes freeze + 0.1 FPS
    "pkmn.gb"        # Crítico: blanco previo
    "tetris.gb"      # Baseline DMG
    "tetris_dx.gbc"  # Baseline GBC
    "zelda-dx.gbc"   # Baseline GBC
)

echo "=========================================="
echo "Step 0447: UI Parallel Execution"
echo "=========================================="
echo "ROMs: ${ROMS[@]}"
echo "Timeout: 15s por ROM"
echo "Logs: $LOG_DIR/"
echo ""

# Función para ejecutar UI con timeout
run_ui() {
    local rom="$1"
    local out="$LOG_DIR/${rom}.log"
    echo "[RUN] $rom -> $out"
    
    # Timeout 15s, line-buffering para captura en tiempo real
    timeout 15s stdbuf -oL -eL python3 main.py "roms/${rom}" 2>&1 | tee "$out" &
    
    # Guardar PID para wait
    echo $! >> "$LOG_DIR/pids.txt"
}

# Limpiar archivo de PIDs
> "$LOG_DIR/pids.txt"

# Lanzar todas las ROMs en paralelo
for rom in "${ROMS[@]}"; do
    if [ -f "roms/${rom}" ]; then
        run_ui "$rom"
        sleep 0.5  # Pequeño delay para evitar race conditions
    else
        echo "[SKIP] ROM no encontrada: roms/${rom}"
    fi
done

echo ""
echo "[WAIT] Esperando finalización de todas las instancias..."
wait

echo ""
echo "[DONE] Todas las instancias finalizadas. Logs en $LOG_DIR/"
echo ""

