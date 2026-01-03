#!/bin/bash
# Extraer muestras de logs UI por ROM (Step 0447)

LOG_DIR="/tmp/viboy_0447"
SUMMARY_FILE="$LOG_DIR/summary.txt"

echo "=========================================="
echo "Step 0447: UI Logs Summary"
echo "=========================================="
echo ""

> "$SUMMARY_FILE"

for f in "$LOG_DIR"/*.log; do
    if [ ! -f "$f" ]; then
        continue
    fi
    
    rom_name=$(basename "$f" .log)
    echo "==================== $rom_name ====================" | tee -a "$SUMMARY_FILE"
    
    # UI-PATH: primeros 8 líneas
    echo "--- UI-PATH ---" | tee -a "$SUMMARY_FILE"
    grep "\[UI-PATH\]" "$f" | head -n 8 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    echo "" | tee -a "$SUMMARY_FILE"
    
    # UI-PROFILING: primeros 8 líneas
    echo "--- UI-PROFILING ---" | tee -a "$SUMMARY_FILE"
    grep "\[UI-PROFILING\]" "$f" | head -n 8 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    echo "" | tee -a "$SUMMARY_FILE"
    
    # UI-DEBUG: primeros 8 líneas
    echo "--- UI-DEBUG ---" | tee -a "$SUMMARY_FILE"
    grep "\[UI-DEBUG\]" "$f" | head -n 8 | tee -a "$SUMMARY_FILE" || echo "(no encontrado)" | tee -a "$SUMMARY_FILE"
    echo "" | tee -a "$SUMMARY_FILE"
    
    # Conteo de líneas (para detectar freezes)
    line_count=$(wc -l < "$f")
    echo "Total lines: $line_count" | tee -a "$SUMMARY_FILE"
    echo "" | tee -a "$SUMMARY_FILE"
done

echo ""
echo "[DONE] Resumen guardado en $SUMMARY_FILE"

