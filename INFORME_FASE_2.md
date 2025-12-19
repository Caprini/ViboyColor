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

---

### 2025-12-19 - Step 0104: Migración del Esqueleto de CPU a C++ (CoreCPU)
**Estado**: ✅ Completado

Se ha completado la migración del esqueleto básico de la CPU a C++, estableciendo el patrón
de **inyección de dependencias** en código nativo. La CPU ahora ejecuta el ciclo Fetch-Decode-Execute
en C++ puro, accediendo a MMU y Registros mediante punteros directos.

**Implementación**:
- ✅ Clase C++ `CPU` creada (`CPU.hpp` / `CPU.cpp`)
  - Punteros a MMU y CoreRegisters (inyección de dependencias)
  - Método `step()` que ejecuta un ciclo Fetch-Decode-Execute
  - Helper `fetch_byte()` para leer opcodes de memoria
  - Switch optimizado por compilador para decodificación
  - Implementados 2 opcodes de prueba: NOP (0x00) y LD A, d8 (0x3E)
- ✅ Wrapper Cython `PyCPU` creado (`cpu.pxd` / `cpu.pyx`)
  - Constructor recibe `PyMMU` y `PyRegisters`
  - Extrae punteros C++ subyacentes para inyección
  - Expone `step()` y `get_cycles()` a Python
- ✅ Integración en sistema de compilación
  - `CPU.cpp` añadido a `setup.py`
  - `cpu.pyx` incluido en `native_core.pyx`
- ✅ Suite completa de tests (`test_core_cpu.py`)
  - 6 tests que validan funcionalidad básica e inyección de dependencias
  - Todos los tests pasan (6/6 ✅)

**Archivos creados/modificados**:
- `src/core/cpp/CPU.hpp` / `CPU.cpp` - Clase C++ de CPU
- `src/core/cython/cpu.pxd` / `cpu.pyx` - Wrapper Cython
- `src/core/cython/native_core.pyx` - Incluido cpu.pyx
- `src/core/cython/mmu.pyx` - Comentario sobre acceso a miembros privados
- `src/core/cython/registers.pyx` - Comentario sobre acceso a miembros privados
- `setup.py` - Añadido CPU.cpp a fuentes
- `tests/test_core_cpu.py` - Suite de tests (6 tests)

**Bitácora**: `docs/bitacora/entries/2025-12-19__0104__migracion-cpu-esqueleto-cpp.html`

**Resultados de verificación**:
- ✅ Compilación exitosa (warnings menores de Cython esperados)
- ✅ Módulo `viboy_core` actualizado con `PyCPU`
- ✅ Todos los tests pasan: `6/6 passed in 0.06s`
- ✅ Patrón de inyección de dependencias validado
- ✅ Ciclo Fetch-Decode-Execute funcionando en código nativo

**Próximos pasos**:
- Migrar más opcodes básicos (LD, ADD, SUB, etc.)
- Implementar manejo de interrupciones (IME, HALT)
- Añadir profiling para medir rendimiento real vs Python
- Migrar opcodes CB (prefijo 0xCB)
- Integrar CPU nativa con el bucle principal de emulación

---

### 2025-12-19 - Step 0105: Implementación de ALU y Flags en C++
**Estado**: ✅ Completado

Se implementó la ALU (Arithmetic Logic Unit) y la gestión de Flags en C++, añadiendo operaciones
aritméticas básicas (ADD, SUB) y lógicas (AND, XOR) al núcleo nativo. Se implementaron 5 nuevos
opcodes: INC A, DEC A, ADD A d8, SUB d8 y XOR A.

**Implementación**:
- ✅ Métodos ALU inline añadidos a `CPU.hpp` / `CPU.cpp`:
  - `alu_add()`: Suma con cálculo de flags Z, N, H, C
  - `alu_sub()`: Resta con cálculo de flags Z, N, H, C
  - `alu_and()`: AND lógico (quirk: siempre pone H=1)
  - `alu_xor()`: XOR lógico (limpia flags H y C)
- ✅ 5 nuevos opcodes implementados:
  - `0x3C`: INC A (Increment A) - 1 M-Cycle
  - `0x3D`: DEC A (Decrement A) - 1 M-Cycle
  - `0xC6`: ADD A, d8 (Add immediate) - 2 M-Cycles
  - `0xD6`: SUB d8 (Subtract immediate) - 2 M-Cycles
  - `0xAF`: XOR A (XOR A with A, optimización para A=0) - 1 M-Cycle
- ✅ Suite completa de tests (`test_core_cpu_alu.py`):
  - 7 tests que validan operaciones aritméticas, flags y half-carry
  - Todos los tests pasan (7/7 ✅)

**Archivos creados/modificados**:
- `src/core/cpp/CPU.hpp` - Añadidas declaraciones de métodos ALU inline
- `src/core/cpp/CPU.cpp` - Implementación de ALU y 5 nuevos opcodes
- `tests/test_core_cpu_alu.py` - Suite de 7 tests para validar ALU nativa

**Bitácora**: `docs/bitacora/entries/2025-12-19__0105__implementacion-alu-flags-cpp.html`

**Resultados de verificación**:
- ✅ Compilación exitosa (sin errores)
- ✅ Todos los tests pasan: `7/7 passed in 0.04s`
- ✅ Gestión precisa de flags (Z, N, H, C) validada
- ✅ Cálculo eficiente de half-carry en C++ (compila a pocas instrucciones de máquina)
- ✅ Optimización XOR A validada (limpia A a 0 en un ciclo)

**Conceptos clave**:
- **Half-Carry en C++**: La fórmula `((a & 0xF) + (b & 0xF)) > 0xF` se compila a muy pocas
  instrucciones de máquina (AND, ADD, CMP), ofreciendo rendimiento máximo comparado con Python.
- **Flags y DAA**: El flag H (Half-Carry) es crítico para DAA, que ajusta resultados binarios
  a BCD. Sin H correcto, DAA falla y los juegos que usan BCD crashean.
- **Optimización XOR A**: `XOR A` (0xAF) es una optimización común en código Game Boy para
  limpiar A a 0 en un solo ciclo, más eficiente que `LD A, 0`.

**Próximos pasos**:
- Implementar ADC A, d8 (0xCE) y SBC A, d8 (0xDE) - operaciones con carry/borrow
- Implementar operaciones ALU con registros (ADD A, r donde r = B, C, D, E, H, L)
- Implementar operaciones lógicas restantes (OR, CP)
- Implementar operaciones de 16 bits (ADD HL, rr, INC rr, DEC rr)

