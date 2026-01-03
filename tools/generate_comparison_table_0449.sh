#!/bin/bash
# Generar tabla comparativa Headless vs UI (Step 0449)

LOG_DIR="/tmp/viboy_0449"
TABLE_FILE="$LOG_DIR/comparison_table_final.txt"

echo "=========================================="
echo "Step 0449: Comparison Table"
echo "=========================================="
echo ""

> "$TABLE_FILE"

echo "ROM | Headless NonWhite | UI NonWhite_before | UI NonWhite_after | VRAMnz | PC_end | wall_ms/pacing_ms" | tee "$TABLE_FILE"
echo "----|-------------------|-------------------|-------------------|--------|--------|-------------------" | tee -a "$TABLE_FILE"

for rom in "mario.gbc" "pkmn.gb" "tetris.gb" "tetris_dx.gbc"; do
    # Extraer métricas de headless
    headless_file="$LOG_DIR/headless/${rom}.txt"
    if [ -f "$headless_file" ]; then
        headless_nonwhite=$(grep "Primer frame > 0:" "$headless_file" | tail -n 1 | grep -oP ":\s*\K[0-9]+" || echo "0")
        headless_vram=$(grep "VRAM NONZERO" "$headless_file" | tail -n 1 | grep -oP "Máx:\s*\K[0-9]+" || echo "0")
        headless_pc=$(grep "I/O RESUMEN (últimos" -A 10 "$headless_file" | grep "PC=" | tail -n 1 | grep -oP "PC=\K[0-9A-Fa-f]+" || echo "0000")
        headless_lcdc=$(grep "I/O RESUMEN (últimos" -A 10 "$headless_file" | grep "LCDC=" | tail -n 1 | grep -oP "LCDC=\K[0-9A-Fa-f]+" || echo "00")
    else
        headless_nonwhite="N/A"
        headless_vram="N/A"
        headless_pc="N/A"
        headless_lcdc="N/A"
    fi
    
    # Extraer métricas de UI
    ui_file="$LOG_DIR/ui/${rom}.log"
    if [ -f "$ui_file" ]; then
        ui_nonwhite_before=$(grep "\[UI-PATH\]" "$ui_file" | tail -n 1 | grep -oP "NonWhite=\K[0-9]+" || echo "0")
        ui_nonwhite_after=$(grep "\[UI-DEBUG\]" "$ui_file" | grep "después del blit" | tail -n 1 | grep -oP "después del blit:\s*\K[0-9]+" || echo "0")
        ui_vram=$(grep "\[UI-PATH\]" "$ui_file" | tail -n 1 | grep -oP "VRAMnz=\K[0-9]+" || echo "0")
        ui_pc=$(grep "\[UI-PATH\]" "$ui_file" | tail -n 1 | grep -oP "PC=\K[0-9A-Fa-f]+" || echo "0000")
        ui_wall=$(grep "\[UI-PROFILING\]" "$ui_file" | tail -n 1 | grep -oP "wall=\K[0-9.]+" || echo "0")
        ui_pacing=$(grep "\[UI-PROFILING\]" "$ui_file" | tail -n 1 | grep -oP "pacing=\K[0-9.]+" || echo "0")
        wall_pacing_str="${ui_wall}ms/${ui_pacing}ms"
    else
        ui_nonwhite_before="N/A"
        ui_nonwhite_after="N/A"
        ui_vram="N/A"
        ui_pc="N/A"
        wall_pacing_str="N/A"
    fi
    
    # Usar VRAM de headless como referencia (o UI si headless no disponible)
    vram_ref="${headless_vram:-$ui_vram}"
    
    echo "$rom | $headless_nonwhite | $ui_nonwhite_before | $ui_nonwhite_after | $vram_ref | 0x$ui_pc | $wall_pacing_str" | tee -a "$TABLE_FILE"
done

echo ""
echo "[DONE] Tabla guardada en $TABLE_FILE"
cat "$TABLE_FILE"

