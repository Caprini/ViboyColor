#!/bin/bash
# Extraer líneas relevantes de logs UI y headless (Step 0449)

LOG_DIR="/tmp/viboy_0449"
SUMMARY_FILE="$LOG_DIR/comparison_summary.txt"

echo "=========================================="
echo "Step 0449: Logs Summary"
echo "=========================================="
echo ""

> "$SUMMARY_FILE"

# Extraer logs UI
echo "==================== UI LOGS ====================" | tee -a "$SUMMARY_FILE"
for f in "$LOG_DIR/ui"/*.log; do
    if [ ! -f "$f" ]; then
        continue
    fi
    rom_name=$(basename "$f" .log)
    echo "" | tee -a "$SUMMARY_FILE"
    echo "--- $rom_name (UI) ---" | tee -a "$SUMMARY_FILE"
    
    # UI-PATH: primeros 10 líneas
    echo "[UI-PATH]:" | tee -a "$SUMMARY_FILE"
    grep "\[UI-PATH\]" "$f" | head -n 10 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    
    # UI-PROFILING: primeros 10 líneas
    echo "[UI-PROFILING]:" | tee -a "$SUMMARY_FILE"
    grep "\[UI-PROFILING\]" "$f" | head -n 10 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    
    # UI-DEBUG: primeros 10 líneas
    echo "[UI-DEBUG]:" | tee -a "$SUMMARY_FILE"
    grep "\[UI-DEBUG\]" "$f" | head -n 10 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
done

# Extraer logs headless
echo "" | tee -a "$SUMMARY_FILE"
echo "==================== HEADLESS LOGS ====================" | tee -a "$SUMMARY_FILE"
for f in "$LOG_DIR/headless"/*.txt; do
    if [ ! -f "$f" ]; then
        continue
    fi
    rom_name=$(basename "$f" .txt)
    echo "" | tee -a "$SUMMARY_FILE"
    echo "--- $rom_name (Headless) ---" | tee -a "$SUMMARY_FILE"
    
    # Buscar resumen final (nonwhite, VRAM nonzero, PC, LCDC)
    echo "Resumen final:" | tee -a "$SUMMARY_FILE"
    grep -A 20 "RESUMEN FINAL" "$f" | head -n 25 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    
    # Buscar últimos frames (PC, LCDC, etc.)
    echo "Últimos frames:" | tee -a "$SUMMARY_FILE"
    grep "I/O RESUMEN (últimos" -A 10 "$f" | head -n 12 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
done

echo ""
echo "[DONE] Resumen guardado en $SUMMARY_FILE"

