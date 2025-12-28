# Instrucciones para Compilar Módulo C++ - Step 0318

## Objetivo
Compilar el módulo C++ (`viboy_core`) para habilitar el renderizado completo y mejorar el rendimiento.

## Requisitos Previos

### Dependencias del Sistema

Instalar las siguientes dependencias (requiere sudo):

```bash
sudo apt install -y python3-cython python3-setuptools python3-numpy python3-dev build-essential
```

O si prefieres usar pip en un entorno virtual:

```bash
python3 -m venv ~/venv_viboy
source ~/venv_viboy/bin/activate
pip install Cython setuptools numpy
```

### Compilador C++

Verificar que tienes un compilador C++ instalado:

```bash
g++ --version  # Debe mostrar versión 9+ o Clang 10+
```

Si no está instalado:

```bash
sudo apt install -y build-essential
```

## Compilación

Una vez que las dependencias estén instaladas:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
python3 setup.py build_ext --inplace
```

Este comando:
1. Compila los archivos `.pyx` (Cython) a código C++
2. Compila el código C++ a módulos Python (`.so` en Linux)
3. Coloca los módulos compilados en el directorio del proyecto

## Verificación

Después de compilar, verificar que el módulo está disponible:

```bash
python3 -c "from src.core.cython import viboy_core; print('✅ Módulo C++ disponible')"
```

Si funciona, deberías ver: `✅ Módulo C++ disponible`

Si falla, verificar errores de compilación en la salida de `setup.py`.

## Re-ejecutar Emulador

Después de compilar exitosamente:

```bash
python3 main.py roms/pkmn.gb
```

Deberías ver:
- ✅ "Core: C++" en lugar de "Core: Python"
- ✅ "[VIBOY] Ejecutando load_test_tiles()..." en lugar de "NO ejecutado"
- ✅ Gráficos renderizados en lugar de pantalla blanca

## Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'Cython'"
- Instalar Cython: `sudo apt install python3-cython` o `pip install Cython`

### Error: "g++: command not found"
- Instalar build-essential: `sudo apt install build-essential`

### Error: "numpy not found"
- Instalar numpy: `sudo apt install python3-numpy` o `pip install numpy`

### Error de compilación C++
- Verificar que todos los archivos `.cpp` y `.hpp` están presentes en `src/core/cpp/`
- Verificar que los archivos `.pyx` y `.pxd` están presentes en `src/core/cython/`
- Revisar errores específicos en la salida de compilación

## Notas

- La compilación puede tardar varios minutos la primera vez
- Los archivos compilados (`.so`) se generan en el directorio del proyecto
- No es necesario recompilar a menos que cambies código C++ o Cython
- Si cambias código Python puro, no necesitas recompilar

