#!/bin/bash
# Comparación Headless vs UI (Step 0448)

set -e

LOG_DIR="/tmp/viboy_0448"
mkdir -p "$LOG_DIR"

ROMS=(
    "mario.gbc"
    "pkmn.gb"
    "tetris.gb"
    "zelda-dx.gbc"
)

echo "=========================================="
echo "Step 0448: Headless vs UI Comparison"
echo "=========================================="
echo ""

> "$LOG_DIR/comparison_table.txt"

echo "ROM | headless NonWhite | UI NonWhite_before | UI NonWhite_after | VRAMnz | PC_end" | tee "$LOG_DIR/comparison_table.txt"
echo "----|-------------------|-------------------|-------------------|--------|-------" | tee -a "$LOG_DIR/comparison_table.txt"

for rom in "${ROMS[@]}"; do
    if [ ! -f "roms/${rom}" ]; then
        echo "[SKIP] ROM no encontrada: roms/${rom}"
        continue
    fi
    
    echo "[HEADLESS] $rom..."
    # Ejecutar headless
    python3 tools/rom_smoke_0442.py "roms/${rom}" --frames 120 --dump-every 0 > "$LOG_DIR/${rom}.headless.log" 2>&1 || true
    
    # Extraer métricas del headless
    headless_nonwhite=$(grep "Primer frame > 0:" "$LOG_DIR/${rom}.headless.log" | tail -n 1 | grep -oP ":\s*\K[0-9]+" || echo "0")
    headless_vram=$(grep "VRAM NONZERO" "$LOG_DIR/${rom}.headless.log" | tail -n 1 | grep -oP "Máx:\s*\K[0-9]+" || echo "0")
    
    echo "[UI] $rom (15s timeout)..."
    # Ejecutar UI con timeout
    timeout 15s python3 main.py "roms/${rom}" > "$LOG_DIR/${rom}.ui.log" 2>&1 || true
    
    # Extraer métricas de UI
    ui_nonwhite_before=$(grep "\[UI-PATH\]" "$LOG_DIR/${rom}.ui.log" | tail -n 1 | grep -oP "NonWhite=\K[0-9]+" || echo "0")
    ui_nonwhite_after=$(grep "\[UI-DEBUG\]" "$LOG_DIR/${rom}.ui.log" | grep "después del blit" | tail -n 1 | grep -oP "después del blit:\s*\K[0-9]+" || echo "0")
    ui_vram=$(grep "\[UI-PATH\]" "$LOG_DIR/${rom}.ui.log" | tail -n 1 | grep -oP "VRAMnz=\K[0-9]+" || echo "0")
    ui_pc=$(grep "\[UI-PATH\]" "$LOG_DIR/${rom}.ui.log" | tail -n 1 | grep -oP "PC=\K[0-9A-Fa-f]+" || echo "0000")
    
    echo "$rom | $headless_nonwhite | $ui_nonwhite_before | $ui_nonwhite_after | $ui_vram | 0x$ui_pc" | tee -a "$LOG_DIR/comparison_table.txt"
done

echo ""
echo "[DONE] Tabla guardada en $LOG_DIR/comparison_table.txt"
cat "$LOG_DIR/comparison_table.txt"

