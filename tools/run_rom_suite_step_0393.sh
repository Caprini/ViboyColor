#!/bin/bash
# Script de ejecución de suite - Step 0393
# Ejecuta 6 ROMs con timeout para verificar salud de render/VRAM/FPS

set -e  # Salir en error

echo "=== Suite Multi-ROM Step 0393 - Inicio ==="
echo "Directorio: $(pwd)"
echo "Fecha: $(date)"
echo ""

# Crear directorio de logs si no existe
mkdir -p logs/suite_0393

# Recompilar extensión (por si acaso)
echo "Recompilando extensión Cython..."
python3 setup.py build_ext --inplace
echo "Compilación completada."
echo ""

# Función para ejecutar ROM con timeout
run_rom() {
    local rom_path="$1"
    local log_file="$2"
    local rom_name=$(basename "$rom_path")

    echo "Ejecutando: $rom_name"
    echo "Log: $log_file"
    echo "Timeout: 30 segundos"

    # Ejecutar con timeout y redirigir salida
    (timeout 30 python3 main.py "$rom_path" > "$log_file" 2>&1) || true

    echo "Completado: $rom_name"
    echo "Tamaño del log: $(wc -c < "$log_file") bytes"
    echo ""
}

echo "=== Ejecutando Suite de 6 ROMs ==="

# Ejecutar cada ROM
run_rom "roms/pkmn.gb" "logs/suite_0393/pkmn_gb_30s.log"
run_rom "roms/pkmn-amarillo.gb" "logs/suite_0393/pkmn_amarillo_gb_30s.log"
run_rom "roms/Oro.gbc" "logs/suite_0393/oro_gbc_30s.log"
run_rom "roms/tetris_dx.gbc" "logs/suite_0393/tetris_dx_gbc_30s.log"
run_rom "roms/tetris.gb" "logs/suite_0393/tetris_gb_30s.log"
run_rom "roms/mario.gbc" "logs/suite_0393/mario_gbc_30s.log"

echo "=== Suite Completada ==="
echo "Logs generados en: logs/suite_0393/"
echo "Total de logs: $(ls logs/suite_0393/*.log | wc -l)"
echo ""
echo "Para analizar los resultados, ejecutar:"
echo "python3 tools/analyze_suite_step_0393.py"
echo "o usar los comandos manuales del plan."
