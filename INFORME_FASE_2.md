# Bitácora de Desarrollo - Fase 2 (v0.0.2)

**Objetivo**: Migración del Núcleo a C++/Cython y Audio (APU).

**Estado**: En desarrollo.

---

## Objetivos Principales de la Fase 2

### 1. Migración del Núcleo a C++/Cython
- [ ] Reescritura de CPU (LR35902) en C++ con wrapper Cython
- [x] Migración de MMU a código compilado
- [ ] Migración de PPU a código compilado
- [ ] Optimización de sincronización ciclo a ciclo
- [ ] Mantener interfaz Python para frontend y tests

### 2. Implementación de Audio (APU)
- [ ] Canal 1: Onda cuadrada con Sweep y Envelope
- [ ] Canal 2: Onda cuadrada con Envelope
- [ ] Canal 3: Onda arbitraria (Wave RAM)
- [ ] Canal 4: Ruido blanco (LFSR)
- [ ] Mezcla de canales y salida a 44100Hz/48000Hz
- [ ] Sincronización de audio con emulación (Dynamic Rate Control o Ring Buffer)

### 3. Mejoras de Arquitectura
- [x] Arquitectura híbrida Python/C++ establecida
- [ ] Gestión de memoria optimizada
- [ ] Tests híbridos (Python instancia Cython -> Cython llama C++)

---

## Entradas de Desarrollo

### 2025-12-19 - Step 0101: Configuración del Pipeline de Compilación Híbrido
**Estado**: ✅ Completado

Se configuró la infraestructura completa de compilación híbrida (Python + C++/Cython):
- ✅ Estructura de directorios creada (`src/core/cpp/`, `src/core/cython/`)
- ✅ Dependencias añadidas (Cython, setuptools, numpy)
- ✅ Prueba de concepto implementada (NativeCore con método `add()`)
- ✅ Sistema de build configurado (`setup.py`)
- ✅ Script de verificación creado (`test_build.py`)

**Archivos creados**:
- `src/core/cpp/NativeCore.hpp` / `.cpp` - Clase C++ de prueba
- `src/core/cython/native_core.pyx` - Wrapper Cython
- `setup.py` - Sistema de compilación
- `test_build.py` - Script de verificación

**Bitácora**: `docs/bitacora/entries/2025-12-19__0101__configuracion-pipeline-compilacion-hibrido.html`

**Comando de compilación**: `python setup.py build_ext --inplace`
**Comando de verificación**: `python test_build.py`

**Resultados de verificación**:
- ✅ Compilación exitosa con Visual Studio 2022 (MSVC 14.44.35207)
- ✅ Archivo generado: `viboy_core.cp313-win_amd64.pyd` (44 KB)
- ✅ Módulo importado correctamente desde Python
- ✅ Instancia `PyNativeCore()` creada sin errores
- ✅ Método `add(2, 2)` retorna `4` correctamente
- ✅ Pipeline completamente funcional y verificado

---

### 2025-12-19 - Step 0102: Migración de MMU a C++ (CoreMMU)
**Estado**: ✅ Completado

Se ha completado la primera migración real de un componente crítico: la MMU (Memory Management Unit).
Esta migración establece el patrón para futuras migraciones (CPU, PPU, APU) y proporciona acceso
de alta velocidad a la memoria del Game Boy.

**Implementación**:
- ✅ Clase C++ `MMU` creada (`MMU.hpp` / `MMU.cpp`)
  - Memoria plana de 64KB usando `std::vector<uint8_t>`
  - Métodos `read()`, `write()`, `load_rom()` con acceso O(1)
- ✅ Wrapper Cython `PyMMU` creado (`mmu.pxd` / `mmu.pyx`)
  - Gestión automática de memoria (RAII)
  - Método `load_rom_py(bytes)` para cargar ROMs desde Python
- ✅ Integración en sistema de compilación
  - `MMU.cpp` añadido a `setup.py`
  - `mmu.pyx` incluido en `native_core.pyx`
- ✅ Suite completa de tests (`test_core_mmu.py`)
  - 7 tests que validan funcionalidad básica
  - Todos los tests pasan (7/7 ✅)

**Archivos creados/modificados**:
- `src/core/cpp/MMU.hpp` / `MMU.cpp` - Clase C++ de MMU
- `src/core/cython/mmu.pxd` / `mmu.pyx` - Wrapper Cython
- `src/core/cython/native_core.pyx` - Actualizado para incluir mmu.pyx
- `setup.py` - Añadido MMU.cpp a fuentes
- `tests/test_core_mmu.py` - Suite de tests (7 tests)

**Bitácora**: `docs/bitacora/entries/2025-12-19__0102__migracion-mmu-cpp.html`

**Resultados de verificación**:
- ✅ Compilación exitosa (sin errores, warnings menores de C++)
- ✅ Módulo `viboy_core` actualizado con `PyMMU`
- ✅ Todos los tests pasan: `7/7 passed in 0.05s`
- ✅ Acceso a memoria ahora es O(1) directo (nanosegundos vs microsegundos)

**Próximos pasos**:
- Migrar CPU a C++ (siguiente componente crítico)
- Implementar mapeo de regiones de memoria (ROM, VRAM, etc.)
- Añadir métodos `read_word()` / `write_word()` (16 bits, Little-Endian)

---

### 2025-12-19 - Step 0103: Migración de Registros a C++ (CoreRegisters)
**Estado**: ✅ Completado

Se ha completado la migración de los registros de la CPU de Python a C++, creando la clase
<code>CoreRegisters</code> que proporciona acceso ultrarrápido a los registros de 8 y 16 bits.
Esta implementación es crítica para el rendimiento, ya que los registros se acceden miles de
veces por segundo durante la emulación.

**Implementación**:
- ✅ Clase C++ `CoreRegisters` creada (`Registers.hpp` / `Registers.cpp`)
  - Registros de 8 bits: a, b, c, d, e, h, l, f (miembros públicos para acceso directo)
  - Registros de 16 bits: pc, sp
  - Métodos inline para pares virtuales (get_af, set_af, get_bc, set_bc, etc.)
  - Helpers inline para flags (get_flag_z, set_flag_z, etc.)
  - Máscara automática para registro F (bits bajos siempre 0)
- ✅ Wrapper Cython `PyRegisters` creado (`registers.pxd` / `registers.pyx`)
  - Propiedades Python para acceso intuitivo (reg.a = 0x12 en lugar de reg.set_a(0x12))
  - Wrap-around automático en setters (acepta valores int de Python, aplica máscara)
  - Gestión automática de memoria (RAII)
- ✅ Integración en sistema de compilación
  - `Registers.cpp` añadido a `setup.py`
  - `registers.pyx` incluido en `native_core.pyx`
- ✅ Suite completa de tests (`test_core_registers.py`)
  - 14 tests que validan todos los aspectos de los registros
  - Todos los tests pasan (14/14 ✅)

**Archivos creados/modificados**:
- `src/core/cpp/Registers.hpp` / `Registers.cpp` - Clase C++ de registros
- `src/core/cython/registers.pxd` / `registers.pyx` - Wrapper Cython
- `src/core/cython/native_core.pyx` - Actualizado para incluir registers.pyx
- `setup.py` - Añadido Registers.cpp a fuentes
- `tests/test_core_registers.py` - Suite de tests (14 tests)

**Bitácora**: `docs/bitacora/entries/2025-12-19__0103__migracion-registros-cpp.html`

**Resultados de verificación**:
- ✅ Compilación exitosa (sin errores, warnings menores de Cython esperados)
- ✅ Módulo `viboy_core` actualizado con `PyRegisters`
- ✅ Todos los tests pasan: `14/14 passed in 0.05s`
- ✅ Acceso directo a memoria (cache-friendly, sin overhead de Python)

**Próximos pasos**:
- Migrar CPU a C++ usando CoreRegisters y CoreMMU
- Implementar ciclo de instrucción (Fetch-Decode-Execute) en C++
- Integrar CoreRegisters con el bucle principal de emulación

