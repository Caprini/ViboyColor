#!/bin/bash
# Detectar posibles freezes y generar tabla resumen (Step 0447)

LOG_DIR="/tmp/viboy_0447"
TABLE_FILE="$LOG_DIR/table_summary.txt"

echo "=========================================="
echo "Step 0447: Freeze Detection + Table Summary"
echo "=========================================="
echo ""

> "$TABLE_FILE"

echo "ROM | Lines | Path | FPS | NonWhite (before/after) | Etapa más cara" | tee "$TABLE_FILE"
echo "----|-------|------|-----|------------------------|-----------------" | tee -a "$TABLE_FILE"

for f in "$LOG_DIR"/*.log; do
    if [ ! -f "$f" ]; then
        continue
    fi
    
    rom_name=$(basename "$f" .log)
    line_count=$(wc -l < "$f")
    
    # Extraer path (última línea [UI-PATH])
    path=$(grep "\[UI-PATH\]" "$f" | tail -n 1 | grep -oP "Path=\K[^|]+" || echo "unknown")
    
    # Extraer FPS (última línea [UI-PATH])
    fps=$(grep "\[UI-PATH\]" "$f" | tail -n 1 | grep -oP "FPS=\K[0-9.]+" || echo "N/A")
    
    # Extraer nonwhite (última línea [UI-DEBUG])
    nonwhite_before=$(grep "\[UI-DEBUG\]" "$f" | grep "antes del blit" | tail -n 1 | grep -oP ":\s*\K[0-9]+" || echo "N/A")
    nonwhite_after=$(grep "\[UI-DEBUG\]" "$f" | grep "después del blit" | tail -n 1 | grep -oP ":\s*\K[0-9]+" || echo "N/A")
    
    # Extraer etapa más cara (última línea [UI-PROFILING])
    etapa_cara=$(grep "\[UI-PROFILING\]" "$f" | tail -n 1 | awk -F'|' '{for(i=2;i<=NF;i++){split($i,a,":");if(a[2]+0>max){max=a[2];name=a[1]}}} END{print name}')
    etapa_cara=${etapa_cara:-"N/A"}
    
    # Detectar posible freeze (muy pocas líneas)
    freeze_indicator=""
    if [ "$line_count" -lt 50 ]; then
        freeze_indicator=" ⚠️ FREEZE?"
    fi
    
    echo "$rom_name | $line_count$freeze_indicator | $path | $fps | $nonwhite_before/$nonwhite_after | $etapa_cara" | tee -a "$TABLE_FILE"
done

echo ""
echo "[DONE] Tabla guardada en $TABLE_FILE"

