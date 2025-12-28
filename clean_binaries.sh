#!/bin/bash
# Script de limpieza agresiva de binarios compilados
# Step 0242: Hard Reset del Binario y Marcador Radiactivo

echo -e "\033[0;33m=== Limpieza Agresiva de Binarios ===\033[0m"
echo ""

# 1. Cerrar procesos Python
echo -e "\033[0;36m1. Cerrando procesos Python...\033[0m"
PYTHON_PROCESSES=$(pgrep -x python 2>/dev/null)
if [ -n "$PYTHON_PROCESSES" ]; then
    COUNT=$(echo "$PYTHON_PROCESSES" | wc -l)
    echo -e "   Encontrados $COUNT proceso(s) Python"
    pkill -9 python
    echo -e "   \033[0;32mProcesos Python cerrados\033[0m"
else
    echo -e "   \033[0;32mNo hay procesos Python activos\033[0m"
fi

sleep 1

# 2. Eliminar carpeta build
echo ""
echo -e "\033[0;36m2. Eliminando carpeta build/...\033[0m"
if [ -d "build" ]; then
    rm -rf build
    echo -e "   \033[0;32mCarpeta build/ eliminada\033[0m"
else
    echo -e "   \033[0;32mCarpeta build/ no existe\033[0m"
fi

# 3. Eliminar archivos .so
echo ""
echo -e "\033[0;36m3. Eliminando archivos .so...\033[0m"
SO_FILES=$(find . -name "*.so" -type f 2>/dev/null)
if [ -n "$SO_FILES" ]; then
    COUNT=$(echo "$SO_FILES" | wc -l)
    echo -e "   Encontrados $COUNT archivo(s) .so"
    echo "$SO_FILES" | xargs rm -f
    echo -e "   \033[0;32mArchivos .so eliminados\033[0m"
else
    echo -e "   \033[0;32mNo se encontraron archivos .so\033[0m"
fi

# 4. Eliminar archivos .pyd (por si acaso, para compatibilidad con otros sistemas)
echo ""
echo -e "\033[0;36m4. Eliminando archivos .pyd...\033[0m"
PYD_FILES=$(find . -name "*.pyd" -type f 2>/dev/null)
if [ -n "$PYD_FILES" ]; then
    COUNT=$(echo "$PYD_FILES" | wc -l)
    echo -e "   Encontrados $COUNT archivo(s) .pyd"
    echo "$PYD_FILES" | xargs rm -f
    echo -e "   \033[0;32mArchivos .pyd eliminados\033[0m"
else
    echo -e "   \033[0;32mNo se encontraron archivos .pyd\033[0m"
fi

echo ""
echo -e "\033[0;32m=== Limpieza Completada ===\033[0m"
echo ""
echo -e "\033[0;33mAhora puedes ejecutar: ./rebuild_cpp.sh\033[0m"

