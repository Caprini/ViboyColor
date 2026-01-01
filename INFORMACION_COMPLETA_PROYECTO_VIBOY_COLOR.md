# **VIBOY COLOR - INFORMACIÓN COMPLETA DEL PROYECTO**

## **🎯 FINALIDAD DEL PROYECTO**

**Viboy Color** es un **emulador educativo de ciclo exacto de Game Boy Color** con triple propósito:

1. **Herramienta Educativa**: Enseñar arquitectura de computadores mediante implementación práctica
2. **Emulador Funcional**: Ejecutar ROMs comerciales de Game Boy/Game Boy Color con precisión de ciclo
3. **Demostración de "Vibe Coding"**: Mostrar cómo AI asistida (Cursor) puede construir software complejo manteniendo calidad académica

---

## **🏛️ FILOSOFÍA DEL PROYECTO**

### **1. Clean Room Policy (Política de Sala Limpia) - PRINCIPIO SUPREMO**

**Tolerancia CERO a la copia de código:**

- ✅ **PERMITIDO**: Usar documentación oficial (Pan Docs, GBEDG, manuales de hardware)
- ✅ **PERMITIDO**: Observar comportamiento del hardware real
- ✅ **PERMITIDO**: Implementar desde especificaciones técnicas
- ❌ **PROHIBIDO**: Copiar código de otros emuladores (mGBA, SameBoy, Gambatte, BGB, etc.)
- ❌ **PROHIBIDO**: Usar código fuente filtrado de Nintendo
- ❌ **PROHIBIDO**: Incluir ROMs o BIOS propietarias en el repositorio

**Razón**: Integridad legal, educativa y ética. Cada línea debe ser resultado de entender la especificación.

### **2. Archaeological Approach (Enfoque Arqueológico)**

**Implementación dirigida por necesidad:**

- Las funcionalidades se implementan **solo cuando una ROM las requiere**
- No implementar 100 opcodes "por completitud" sin probarlos
- Cada funcionalidad es **atómica, probada y documentada**
- Prioridad: **Precisión y comprensión > Velocidad de desarrollo**

**Proceso**:
1. ROM intenta ejecutar opcode/funcionalidad no implementada
2. Se documenta el concepto de hardware (Pan Docs)
3. Se implementa la funcionalidad mínima viable
4. Se crea test unitario
5. Se valida con la ROM original
6. Se documenta en la bitácora

### **3. Hybrid Architecture (Arquitectura Híbrida)**

**Python + C++ = Lo mejor de ambos mundos:**

- **Python (Frontend/Orquestación)**: UI, tests, documentación, game loop
- **C++ (Core/Performance)**: CPU, PPU, MMU con precisión de ciclo
- **Cython (Bridge)**: Interoperabilidad zero-cost entre Python y C++

**Razón**: Python es ideal para educación y tests; C++ es necesario para 60 FPS a 4.19 MHz.

---

## **📚 CONCEPTO ACADÉMICO**

### **Objetivo Educativo**

Viboy Color es un **laboratorio viviente** de arquitectura de computadores:

1. **Componentes del Sistema**:
   - CPU (LR35902 - Z80 modificado)
   - MMU (Memory Management Unit) con banking
   - PPU (Picture Processing Unit) con sprites/tiles
   - APU (Audio Processing Unit) - 4 canales
   - Timers, Interrupciones, I/O

2. **Conceptos Cubiertos**:
   - Arquitectura Von Neumann
   - Instruction Set Architecture (ISA)
   - Memory mapping y banking
   - Pipeline de renderizado
   - Sincronización hardware/software
   - DSP y síntesis de audio digital

3. **Metodología de Aprendizaje**:
   - **Bottom-Up**: Desde instrucciones básicas hasta sistema completo
   - **Test-Driven**: Cada componente tiene suite de tests
   - **Documentación Continua**: Bitácora HTML con 200+ entradas educativas

### **Documentación Técnica de Referencia**

**Fuentes primarias** (archivo `.cursor/docs.md`):
- **Pan Docs**: https://gbdev.io/pandocs/ (especificación oficial Game Boy)
- **GBEDG**: Game Boy Emulation Development Guide
- **Python 3.11+**: https://docs.python.org/3.11/
- **C++17**: https://en.cppreference.com/w/cpp/17
- **Cython**: https://cython.readthedocs.io/

---

## **🗺️ ROADMAP DEL PROYECTO**

### **Fase 1 (v0.0.1) - ✅ COMPLETADA (2025-12-18)**

**Estado**: Proof of Concept Académica

**Logros**:
- ✅ CPU LR35902 completo (100% opcodes implementados)
- ✅ PPU básico (Background, Window, Sprites)
- ✅ MMU con MBC1
- ✅ Timer (DIV) funcional
- ✅ Joypad completo
- ✅ Suite de tests completa
- ✅ Bitácora web con 160+ entradas

**Limitaciones identificadas**:
- ❌ Audio APU no implementado
- ❌ Timing en Python puro causa inestabilidad en juegos sensibles
- ❌ Rendimiento insuficiente para 60 FPS estables

### **Fase 2 (v0.0.2) - 🚧 EN DESARROLLO (Actual)**

**Objetivo**: **Migración del Núcleo a C++/Cython + Audio (APU)**

**Progreso**:
- ✅ CPU (LR35902) migrado a C++17
- ✅ MMU migrado a C++ con banking
- ✅ PPU migrado a C++ (timing y renderizado)
- ✅ Puente Cython funcional (Python ↔ C++)
- ✅ Sistema de compilación (`setup.py`) robusto
- ✅ Tests híbridos (Python → Cython → C++)
- 🔄 **APU (Audio) en progreso** (Canal 1-4 pendientes)
- 🔄 **Compatibilidad CGB mejorada** (en progreso)

**Estado actual (Step 0404)**:
- Tetris DX funciona perfectamente
- Zelda DX/Pokémon Red tienen problemas de inicialización (registros CGB)
- Implementando separación DMG/CGB clean-room

**Steps completados**: 0001-0404 (404 pasos documentados)

### **Fase 3 (v0.0.3) - 📅 PLANIFICADA**

**Objetivos**:
- 🎵 APU completo (4 canales + mezcla)
- 🎨 Soporte CGB completo (paletas, VRAM banking, HDMA)
- 🖼️ Menú principal con tkinter
- 🎮 Save states y controles configurables
- 🔊 Ring buffer para audio sin cortes

### **Fase 4 (v1.0.0) - 🔮 FUTURA**

**Objetivos**:
- 🐛 Debugger visual (Dear ImGui)
- 📜 API de scripting (Lua)
- 🔧 GDB stub para debugging externo
- 🎨 Shaders y filtros visuales
- 🌐 Modo networked multiplayer (Link Cable)

---

## **🔗 ENLACES OFICIALES**

- **Web Oficial**: https://viboycolor.fabini.one
- **GitHub**: https://github.com/Caprini/ViboyColor
- **Documentación Local**: `docs/bitacora/index.html` (bitácora web completa)
- **Informe Técnico**: `docs/informe_fase_2/` (dividido en partes)

---

## **⚙️ METODOLOGÍA UTILIZADA**

### **1. Vibe Coding con Cursor**

**Definición**: Desarrollo asistido por IA (Cursor IDE + Claude Sonnet) con metodología académica estricta.

**Características**:
- **AI como Ingeniero Senior**: El agente actúa como Principal Systems Engineer
- **Documentación Continua**: Cada cambio genera entrada en bitácora HTML
- **Iteración Incremental**: Steps pequeños y atómicos (1 funcionalidad = 1 step)
- **Control de Calidad**: Tests obligatorios antes de avanzar

**Flujo de Trabajo (Definido en `.cursorrules`)**:

```
1. Usuario solicita funcionalidad
   ↓
2. AI explica concepto de hardware (Pan Docs)
   ↓
3. AI implementa código (C++/Cython/Python)
   ↓
4. AI crea/actualiza tests
   ↓
5. AI compila módulo C++ (python setup.py build_ext --inplace)
   ↓
6. AI ejecuta tests (pytest)
   ↓
7. AI genera entrada HTML para bitácora
   ↓
8. AI actualiza informe dividido (docs/informe_fase_2/)
   ↓
9. AI proporciona comandos git (add, commit, push)
```

### **2. Test-Driven Development (TDD) Híbrido**

**Estructura**:
- Tests en Python (`pytest`)
- Tests instancian módulos Cython
- Módulos Cython invocan código C++
- Validación con ROMs reales

**Ejemplo**:
```python
# tests/test_core_cpu.py
from viboy_core import NativeCore  # Módulo compilado C++

def test_opcode_ld_b_d():
    core = NativeCore()
    core.cpu_set_register_B(0x42)
    # ... ejecutar opcode ...
    assert core.cpu_get_register_D() == 0x42
```

### **3. Sistema de Bitácora (Documentación Continua)**

**Ubicación**: `docs/bitacora/`

**Estructura**:
```
docs/bitacora/
├── index.html (índice principal con lista de todas las entradas)
├── entries/
│   ├── 2026-01-01__0404__separacion-cgb-dmg.html
│   ├── 2026-01-01__0403__analisis-tetris-zelda.html
│   └── ... (200+ entradas)
└── assets/ (CSS, imágenes)
```

**Contenido de cada entrada**:
- Fecha y Step ID correlativo
- Concepto de hardware (explicación académica)
- Implementación (código con explicación)
- Tests y verificación (resultados de pytest)
- Archivos modificados
- Comandos git ejecutados

**Regla crítica**: Cada Step incrementa el Step ID secuencialmente (nunca duplicados).

### **4. Informe Dividido (para Agentes AI)**

**Ubicación**: `docs/informe_fase_2/`

**Razón**: Archivos grandes (>10K líneas) saturan contexto de IA. Se divide en partes de ~2000 líneas.

**Estructura**:
```
docs/informe_fase_2/
├── index.md (índice con rangos de Steps)
├── parte_00_steps_0370_0402.md
├── parte_01_steps_0308_0369.md
├── parte_02_steps_0267_0307.md
└── ... (6 partes actualmente)
```

**Regla**: Al documentar un Step, se actualiza SOLO la parte correspondiente (no todas).

### **5. Prevención de Saturación de Contexto**

**Problema**: Logs gigantes rompen la conexión con el servidor de IA.

**Soluciones implementadas**:
- ✅ Redirigir salida de comandos largos: `comando > log.txt 2>&1`
- ✅ Usar `head -n 50` o `tail -n 50` para análisis limitado
- ✅ NO usar `cat` en logs completos
- ✅ Generar resúmenes en lugar de volcar logs enteros
- ✅ Logs de build van a archivos (`build_log_step0XXX.txt`)

---

## **✅ LO QUE TENEMOS IMPLEMENTADO**

### **Core C++ (Compilado con Cython)**

#### **CPU (LR35902)**
- ✅ 100% de opcodes (0x00-0xFF, 0xCB00-0xCBFF)
- ✅ Timing de ciclo exacto por opcode
- ✅ Registros de 8 bits: A, B, C, D, E, H, L, F (flags)
- ✅ Registros de 16 bits: AF, BC, DE, HL, SP, PC
- ✅ Flags: Z (Zero), N (Subtract), H (Half-Carry), C (Carry)
- ✅ Instrucciones aritméticas, lógicas, saltos, llamadas

#### **MMU (Memory Management Unit)**
- ✅ Espacio de direcciones de 16 bits (0x0000-0xFFFF)
- ✅ Memory banking (MBC1 completo)
- ✅ ROM banking (hasta 128 bancos)
- ✅ RAM externa (hasta 4 bancos)
- ✅ VRAM (0x8000-0x9FFF)
- ✅ WRAM (0xC000-0xDFFF)
- ✅ OAM (0xFE00-0xFE9F)
- ✅ I/O Registers (0xFF00-0xFF7F)
- ✅ HRAM (0xFF80-0xFFFE)
- 🔄 **Separación DMG/CGB en progreso** (Step 0404)

#### **PPU (Picture Processing Unit)**
- ✅ Resolución: 160×144 píxeles
- ✅ Background (fondo con tiles de 8×8)
- ✅ Window (ventana superpuesta)
- ✅ Sprites (OBJ, hasta 40 objetos, 10 por línea)
- ✅ Timing de línea de escaneo (456 ciclos)
- ✅ Modos PPU: OAM Search, Pixel Transfer, HBlank, VBlank
- ✅ Registros: LCDC, STAT, SCY, SCX, LY, LYC, BGP, OBP0, OBP1
- ✅ Interrupción VBlank y LCD STAT

#### **Timer**
- ✅ DIV (Divider Register, 0xFF04)
- ✅ TIMA (Timer Counter, 0xFF05)
- ✅ TMA (Timer Modulo, 0xFF06)
- ✅ TAC (Timer Control, 0xFF07)
- ✅ Frecuencias: 4096 Hz, 262144 Hz, 65536 Hz, 16384 Hz

#### **Joypad**
- ✅ Registro JOYP (0xFF00)
- ✅ Botones: A, B, Start, Select
- ✅ Direccionales: Up, Down, Left, Right
- ✅ Interrupción de Joypad

### **Frontend Python**

#### **Renderizado (Pygame-CE)**
- ✅ Ventana de 160×144 escalada a 640×576 (4x)
- ✅ Renderizado de framebuffer desde C++
- ✅ Sincronización a 60 FPS

#### **Input**
- ✅ Mapeo de teclado: Flechas (D-Pad), Z (A), X (B), Enter (Start), Shift (Select)

#### **Cartridge Loader**
- ✅ Parsing de header de ROM
- ✅ Detección de MBC (Memory Bank Controller)
- ✅ Carga de ROM en memoria

### **Testing**

#### **Suite de Tests (pytest)**
- ✅ `tests/test_core_cpu.py`: Tests de CPU (opcodes, flags, timing)
- ✅ `tests/test_core_ppu.py`: Tests de PPU (timing, modos, registros)
- ✅ `tests/test_core_mmu.py`: Tests de MMU (banking, escritura/lectura)
- ✅ `tests/test_integration_cpp.py`: Tests de integración Python-C++
- ✅ `test_build.py`: Verificación de pipeline de compilación

**Comando**: `pytest -v`

### **Build System**

#### **Compilación (setup.py + Cython)**
- ✅ Archivo `setup.py` con configuración de extensiones
- ✅ Wrappers Cython (`.pyx`, `.pxd`) para todos los componentes
- ✅ Script `rebuild_cpp.sh` (Linux)
- ✅ Script `rebuild_cpp.ps1` (Windows)

**Comando principal**: `python setup.py build_ext --inplace`

### **Documentación**

- ✅ `README.md` bilingüe (Inglés/Español)
- ✅ `CONTRIBUTING.md` (guía de contribución completa)
- ✅ `CODE_OF_CONDUCT.md`
- ✅ `SECURITY.md`
- ✅ Bitácora web (`docs/bitacora/index.html`) con 200+ entradas
- ✅ Informe técnico dividido (`docs/informe_fase_2/`)

---

## **❌ LO QUE FALTA POR IMPLEMENTAR**

### **Fase 2 Actual (v0.0.2)**

#### **APU (Audio Processing Unit) - PRIORIDAD ALTA**
- ❌ Canal 1: Onda cuadrada con Sweep y Envelope
- ❌ Canal 2: Onda cuadrada con Envelope
- ❌ Canal 3: Wave RAM (onda arbitraria)
- ❌ Canal 4: Ruido (LFSR - Linear Feedback Shift Register)
- ❌ Mixer (mezcla de 4 canales a stereo)
- ❌ Salida a 44100 Hz o 48000 Hz
- ❌ Ring buffer para sincronización audio-video
- ❌ Registros APU (0xFF10-0xFF26)

#### **Compatibilidad CGB (Game Boy Color) - EN PROGRESO**
- 🔄 Separación clean-room DMG/CGB (Step 0404 en progreso)
- ❌ VRAM Banking (VBK, 0xFF4F) - 2 bancos de 8KB
- ❌ WRAM Banking (SVBK, 0xFF70) - 8 bancos de 4KB
- ❌ Paletas CGB (BCPS/BCPD, OCPS/OCPD)
- ❌ HDMA (Horizontal DMA, 0xFF51-0xFF55)
- ❌ Double-speed mode (KEY1, 0xFF4D)

#### **MBC Adicionales**
- ❌ MBC2 (ROM/RAM con funcionalidades específicas)
- ❌ MBC3 (con RTC - Real Time Clock)
- ❌ MBC5 (ROMs grandes, usado en juegos CGB)

### **Fase 3 Planificada (v0.0.3)**

- ❌ Menú principal (tkinter)
- ❌ Save states (guardar/cargar estado)
- ❌ Configuración de controles
- ❌ Filtros visuales (scanlines, shaders básicos)
- ❌ Fast-forward (turbo)

### **Fase 4 Futura (v1.0.0)**

- ❌ Debugger visual (Dear ImGui)
- ❌ API de scripting (Lua)
- ❌ GDB stub
- ❌ Link Cable (multiplayer networked)
- ❌ Rewinding (retroceso en el tiempo)

---

## **🔧 STACK TECNOLÓGICO**

### **Lenguajes**

- **Python 3.11+** (Frontend, tests, orquestación)
- **C++17** (Core: CPU, PPU, MMU, APU)
- **Cython 3.0+** (Bridge Python ↔ C++)

### **Bibliotecas Python**

- `pygame-ce>=2.3.0` (Renderizado y input)
- `pytest>=7.4.0` (Testing)
- `numpy>=1.24.0` (Arrays eficientes)
- `setuptools>=68.0.0` (Build system)

### **Herramientas de Build**

- **Compiladores**:
  - Windows: Visual Studio Build Tools 2019+
  - Linux: GCC 9+ o Clang 10+
  - macOS: Xcode Command Line Tools

### **Control de Versiones**

- **Git** + **GitHub** (https://github.com/Caprini/ViboyColor)
- **Rama actual**: `develop-v0.0.2`
- **Formato de commits**: `feat(core): descripción` / `fix(ppu): descripción`

### **Sistema Operativo Principal**

- Ubuntu Linux 6.14.0-37-generic
- Compatible con Windows 10/11 y macOS

---

## **📊 ESTADO ACTUAL DEL PROYECTO (2026-01-01)**

### **Últimos Steps Completados**

- **Step 0403**: Análisis comparativo Tetris DX (funciona) vs Zelda DX/Pokémon Red (no funcionan)
- **Step 0404 (Tarea 1/5)**: Implementación de separación DMG/CGB clean-room (enum `HardwareMode`, métodos de gestión)

### **Problema Actual (Step 0404)**

**Síntoma**: Zelda DX y Pokémon Red (juegos CGB) no inicializan correctamente, pantalla blanca.

**Causa identificada**: Falta separación clean-room entre modo DMG (Game Boy clásico) y CGB (Game Boy Color) en inicialización de registros I/O.

**Solución en progreso** (Plan Step 0404 - 5 tareas):
1. ✅ Implementar enum `HardwareMode` y métodos de gestión
2. ⏳ Detectar modo desde ROM header (byte 0x0143)
3. ⏳ Inicializar registros I/O según modo DMG/CGB
4. ⏳ Añadir logging de diagnóstico
5. ⏳ Validar con Zelda DX y Pokémon Red

### **ROMs de Prueba Funcionales**

- ✅ **Tetris (DMG)**: Funciona perfectamente
- ✅ **Tetris DX (CGB)**: Funciona perfectamente
- ❌ **Zelda DX (CGB)**: Pantalla blanca (en diagnóstico)
- ❌ **Pokémon Red (DMG/CGB)**: Pantalla blanca (en diagnóstico)

### **Métricas del Proyecto**

- **Steps documentados**: 404
- **Entradas de bitácora**: 200+
- **Líneas de código C++**: ~3000 (src/core/cpp/)
- **Líneas de código Python**: ~2000 (src/, main.py, tests/)
- **Tests unitarios**: 50+ (pytest)
- **Cobertura de código**: ~70% (estimado)

---

## **🎯 PRÓXIMOS PASOS (Roadmap Inmediato)**

### **Corto Plazo (Steps 0404-0420)**

1. ✅ **Step 0404**: Completar separación DMG/CGB clean-room (5 tareas)
2. **Step 0405**: Validar Zelda DX y Pokémon Red con nueva inicialización
3. **Step 0406**: Implementar VRAM banking (VBK, 0xFF4F)
4. **Step 0407**: Implementar WRAM banking (SVBK, 0xFF70)
5. **Step 0408**: Implementar paletas CGB (BCPS/BCPD, OCPS/OCPD)
6. **Step 0410**: Iniciar APU - Canal 1 (onda cuadrada con Sweep)

### **Medio Plazo (Steps 0420-0450)**

- Completar APU (4 canales + mixer)
- Ring buffer para audio
- Sincronización audio-video robusta
- HDMA (Horizontal DMA)
- Double-speed mode (KEY1)

### **Largo Plazo (Fase 3)**

- Menú principal con tkinter
- Save states
- Configuración de controles
- Filtros visuales

---

## **⚠️ CONSIDERACIONES CRÍTICAS PARA EL AGENTE PLANIFICADOR**

### **1. NUNCA Romper Clean Room Policy**

El agente planificador debe asegurar que **ningún plan** sugiera:
- Copiar código de otros emuladores
- Usar implementaciones de referencia sin entenderlas
- "Inspirarse" en código existente

Siempre partir de **Pan Docs** o **GBEDG**.

### **2. Respetar el Archaeological Approach**

Los planes deben:
- Implementar funcionalidades **cuando ROMs las requieran**
- NO implementar "por completitud"
- Cada funcionalidad debe tener **test asociado**

### **3. Mantener Documentación Continua**

Cada plan debe incluir:
- Generación de entrada HTML para bitácora
- Actualización del informe dividido
- Comandos git (add, commit, push)

### **4. Prevenir Saturación de Contexto**

Los planes deben:
- Redirigir logs largos a archivos
- Usar `head`/`tail` para análisis limitado
- NO volcar logs completos en respuestas

### **5. Compilación Obligatoria**

Cada plan que toque código C++ debe incluir:
- Comando de compilación: `python setup.py build_ext --inplace`
- Verificación: `python test_build.py`
- Tests: `pytest -v`

### **6. Steps Atómicos**

Los planes deben:
- Dividir tareas grandes en steps pequeños (1 funcionalidad = 1 step)
- Cada step debe ser completable en una sesión
- Step IDs **correlativos** (nunca duplicados ni saltos)

### **7. Sincronización con GitHub**

Cada paso debe terminar con:
```bash
git add .
git commit -m "tipo(componente): descripción"
git push
```

---

## **📝 FORMATO DE PLANES (para el Agente Planificador)**

**Estructura obligatoria de un plan:**

```markdown
## Plan Step XXXX: Título del Step

### Objetivo
[Qué se busca lograr con este plan]

### Contexto
[Estado actual del código/proyecto]
[Hallazgos previos relevantes]

### Tareas
1. **[ID]** - [Descripción clara]
   - **Archivos afectados**: `ruta/archivo.cpp`, `ruta/archivo.pyx`
   - **Acciones concretas**:
     ```bash
     # Comandos exactos
     ```
   - **Criterios de éxito**: [Condiciones medibles]
   - **Dependencias**: [ID de tareas previas]

### Concepto de Hardware
[Explicación técnica desde Pan Docs con sección específica]
[Por qué se hace de esta manera]

### Comandos de Compilación
python setup.py build_ext --inplace
python test_build.py
pytest -v

### Tests
[Qué tests ejecutar]
[Qué resultados esperar]

### Documentación
- Generar entrada HTML: `docs/bitacora/entries/YYYY-MM-DD__XXXX__slug.html`
- Actualizar índice: `docs/bitacora/index.html`
- Actualizar informe dividido: `docs/informe_fase_2/parte_XX_steps_YYYY_ZZZZ.md`

### Comandos Git
git add .
git commit -m "tipo(componente): descripción"
git push
```

---

## **✨ RESUMEN EJECUTIVO**

**Viboy Color** es un proyecto educativo único que combina:

1. **Rigor Académico**: Clean Room Implementation + Archaeological Approach
2. **Tecnología Híbrida**: Python (educación) + C++ (performance) + Cython (bridge)
3. **AI-Assisted Development**: Vibe Coding con Cursor (Claude Sonnet)
4. **Documentación Exhaustiva**: 200+ entradas de bitácora explicando hardware
5. **Open Source**: MIT License, código público en GitHub

**Estado actual**: Fase 2 (v0.0.2) con CPU/PPU/MMU completamente migrados a C++. APU pendiente. Trabajando en compatibilidad CGB (Step 0404).

**Objetivo inmediato**: Completar separación DMG/CGB para que Zelda DX y Pokémon Red funcionen correctamente.

---

**Este documento es la fuente de verdad para el agente planificador. Cualquier plan debe alinearse con la filosofía, metodología y estado actual aquí descritos.**

