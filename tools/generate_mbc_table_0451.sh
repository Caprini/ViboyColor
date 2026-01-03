#!/bin/bash
# Generar tabla final MBC + decisión automática (Step 0451)

LOG_DIR="/tmp/viboy_0451"
TABLE_FILE="$LOG_DIR/mbc_table_final.txt"

echo "=========================================="
echo "Step 0451: MBC Table + Decision"
echo "=========================================="
echo ""

> "$TABLE_FILE"

echo "ROM | cart_type | MBC | supported | mbc_writes | pc_end | vram_raw_nz | nonwhite | conclusión" | tee "$TABLE_FILE"
echo "----|-----------|-----|-----------|------------|--------|-------------|----------|-----------" | tee -a "$TABLE_FILE"

for rom in "mario.gbc" "pkmn.gb" "tetris.gb" "tetris_dx.gbc"; do
    # Obtener ROM info
    rom_info=$(python3 tools/rom_info_0450.py "roms/${rom}" 2>/dev/null | tail -n 1)
    if [ -z "$rom_info" ]; then
        echo "$rom | ERROR | - | - | - | - | - | - | Error leyendo header" | tee -a "$TABLE_FILE"
        continue
    fi
    
    cart_type=$(echo "$rom_info" | awk -F'|' '{print $2}' | xargs)
    mbc_name=$(echo "$rom_info" | awk -F'|' '{print $3}' | xargs)
    supported=$(echo "$rom_info" | awk -F'|' '{print $5}' | xargs)
    
    # Extraer métricas de headless
    headless_file="$LOG_DIR/headless/${rom}.txt"
    if [ ! -f "$headless_file" ]; then
        echo "$rom | $cart_type | $mbc_name | $supported | ERROR | - | - | - | Log no encontrado" | tee -a "$TABLE_FILE"
        continue
    fi
    
    # Extraer PC final (último PC del resumen final)
    pc_end=$(grep "I/O RESUMEN (últimos" -A 10 "$headless_file" | grep "PC=" | tail -n 1 | grep -oP "PC=\K[0-9A-Fa-f]+" || echo "0000")
    
    # Extraer VRAM RAW nonzero (máximo)
    vram_raw=$(grep "VRAM NONZERO RAW" -A 5 "$headless_file" | grep "Máx:" | grep -oP "Máx:\s*\K[0-9]+" | head -1 | tr -d '\n' || echo "0")
    if [ -z "$vram_raw" ]; then
        vram_raw="0"
    fi
    
    # Extraer nonwhite (primer frame > 0)
    nonwhite=$(grep "Primer frame > 0:" "$headless_file" | grep -oP ":\s*\K[0-9]+" | head -1 | tr -d '\n' || echo "0")
    if [ -z "$nonwhite" ]; then
        nonwhite="0"
    fi
    
    # Extraer MBC writes count
    mbc_count=$(grep "MBC-SUMMARY.*Total writes:" "$headless_file" | grep -oP ":\s*\K[0-9]+" || echo "0")
    
    # Conclusión automática
    conclusion=""
    if [ "$supported" != "sí" ] && [ "$mbc_count" -gt 0 ]; then
        conclusion="Causa raíz: MBC no soportado (writes detectados)"
    elif [ "$supported" == "sí" ] && [ "$mbc_count" -gt 0 ] && [ "$vram_raw" -eq 0 ] && [ "$pc_end" != "0000" ]; then
        conclusion="MBC soportado pero mapping incorrecto (writes existen, VRAM vacío)"
    elif [ "$vram_raw" -gt 0 ] && [ "$nonwhite" -eq 0 ]; then
        conclusion="VRAM tiene datos pero framebuffer blanco (bug PPU/paleta)"
    elif [ "$mbc_count" -eq 0 ] && [ "$mbc_name" == "None" ] || [ "$cart_type" == "0x00" ]; then
        conclusion="ROM_ONLY: no es MBC, mirar PPU/IRQ"
    elif [ "$pc_end" == "0000" ] || [ -z "$pc_end" ]; then
        conclusion="PC estancado (bug CPU/IRQ)"
    else
        conclusion="OK o requiere análisis manual"
    fi
    
    echo "$rom | $cart_type | $mbc_name | $supported | $mbc_count | 0x$pc_end | $vram_raw | $nonwhite | $conclusion" | tee -a "$TABLE_FILE"
done

echo ""
echo "[DONE] Tabla guardada en $TABLE_FILE"
cat "$TABLE_FILE"

