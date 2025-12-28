#!/bin/bash
# Script de Bash para forzar la recompilación del módulo C++ en Linux
# Uso: ./rebuild_cpp.sh

echo -e "\033[0;36mHard Rebuild del módulo C++ de Viboy Color\033[0m"
echo ""

# 1. Cerrar procesos de Python (opcional, comentado por seguridad)
# echo -e "\033[0;33mCERRANDO PROCESOS DE PYTHON...\033[0m"
# pkill -9 python
# sleep 2

# 2. Buscar y renombrar archivos .so antiguos
echo -e "\033[0;33mBuscando archivos .so antiguos...\033[0m"
SO_FILES=$(find . -name "*.so" -type f 2>/dev/null)

if [ -n "$SO_FILES" ]; then
    while IFS= read -r file; do
        if [ -f "$file" ]; then
            timestamp=$(date +"%Y%m%d_%H%M%S")
            old_name="$file"
            new_name="${file}_OLD_${timestamp}"
            echo -e "  \033[0;37mRenombrando: $(basename "$file") -> $(basename "$file")_OLD\033[0m"
            if mv "$old_name" "$new_name" 2>/dev/null; then
                echo -e "  \033[0;32m[OK] Renombrado exitosamente\033[0m"
            else
                echo -e "  \033[0;33m[WARN] No se pudo renombrar (puede estar en uso)\033[0m"
            fi
        fi
    done <<< "$SO_FILES"
else
    echo -e "  \033[0;37m[INFO] No se encontraron archivos .so\033[0m"
fi

# 3. Limpiar archivos compilados
echo ""
echo -e "\033[0;33mLimpiando archivos compilados...\033[0m"
if python setup.py clean --all >/dev/null 2>&1; then
    echo -e "  \033[0;32m[OK] Limpieza completada\033[0m"
else
    echo -e "  \033[0;33m[WARN] Error en limpieza\033[0m"
fi

# 4. Recompilar
echo ""
echo -e "\033[0;33mRecompilando módulo C++...\033[0m"
if python setup.py build_ext --inplace; then
    echo ""
    echo -e "\033[0;32m[OK] Recompilación exitosa!\033[0m"
    echo ""
    echo -e "\033[0;36mPróximos pasos:\033[0m"
    echo -e "  1. Ejecuta el emulador: python main.py roms/tetris.gb"
    echo -e "  2. Busca el log '[PPU C++] STEP LIVE' en la consola"
    echo -e "  3. Verifica que la pantalla es blanca (sin punto rojo)"
else
    echo ""
    echo -e "\033[0;31m[ERROR] Error en la recompilación. Revisa los mensajes anteriores.\033[0m"
    exit 1
fi

