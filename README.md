# Viboy Color - Python Game Boy Emulator (Academic PoC)

[![Status: Proof of Concept](https://img.shields.io/badge/Status-Proof%20of%20Concept-orange.svg)](https://github.com/Caprini/ViboyColor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

## 🌐 Official Website / Web Oficial

**[viboycolor.fabini.one](https://viboycolor.fabini.one)**

---

## Language / Idioma

**[ 🇬🇧 English ](#viboy-color---english) | [ 🇪🇸 Español ](#viboy-color---español)**

---

# Viboy Color - English

A Game Boy Color emulator written in Python, developed from scratch through **"Vibe Coding"** (AI-assisted programming without deep prior knowledge of GB architecture) with an educational and clean-room approach.

## 🎯 Description

**Viboy Color** is a Game Boy Color system emulator developed completely from scratch in Python through **"Vibe Coding"** (AI-assisted programming without deep prior knowledge of the Game Boy architecture). This project's main goal is to be an educational tool that allows understanding the original hardware architecture through clean-room implementation (without copying code from other emulators).

### ⚠️ Current Status: v0.0.2-dev (Work in Progress)

**Phase 1 (v0.0.1) - CLOSED**: The project reached a successful **Academic Proof of Concept (PoC)** status. The emulator works at a technical level: loads ROMs, executes CPU instructions, manages memory, renders graphics and displays games on screen. However, gameplay is not viable due to fine synchronization issues and latency inherent to pure Python implementation.

**Phase 2 (v0.0.2) - IN DEVELOPMENT**: Core migration to C++/Cython and Audio (APU) implementation. The goal is to achieve the timing precision necessary for complete gameplay through compiled code, maintaining the Python interface for frontend and tests.

### Project Principles

- ✅ **Clean-Room Implementation**: All code is developed exclusively from official technical documentation
- ✅ **Educational Approach**: Each component includes detailed documentation explaining the underlying hardware
- ✅ **Total Portability**: Compatible with Windows, Linux and macOS
- ✅ **Modern Python**: Uses Python 3.10+ with strict typing and best practices
- ✅ **Test-Driven Development**: Complete suite of unit tests to validate each component

## ✨ Implemented Features (v0.0.1)

### CPU (LR35902) - ✅ Complete
- ✅ **Complete registers**: Implementation of all 8 and 16-bit registers (A, B, C, D, E, H, L, F, PC, SP)
- ✅ **Virtual pairs**: Support for 16-bit pairs (AF, BC, DE, HL)
- ✅ **Flag system**: Complete flag management (Z, N, H, C) with hardware peculiarities
- ✅ **Fetch-Decode-Execute cycle**: Implementation of the fundamental instruction cycle
- ✅ **Complete ALU**: Arithmetic Logic Unit with correct flag handling, especially Half-Carry
- ✅ **Complete opcodes**: Implementation of all opcodes in the LR35902 instruction set (including CB prefix)
- ✅ **Dispatch table**: Scalable system for opcode handling with match/case

### MMU (Memory Management Unit) - ✅ Functional
- ✅ **Complete address space**: Management of 16-bit space (0x0000-0xFFFF)
- ✅ **Little-Endian operations**: Read/write of 16-bit words with correct endianness
- ✅ **Wrap-around**: Correct handling of address and value overflows
- ✅ **Automatic masking**: Protection against out-of-range values
- ✅ **Region mapping**: ROM, VRAM, OAM, I/O, HRAM, Cartridges (MBC1)

### PPU (Picture Processing Unit) - ✅ Functional
- ✅ **Background rendering**: Complete tilemap with scroll (SCX/SCY)
- ✅ **Window rendering**: Independent window layer
- ✅ **Sprite rendering**: Up to 40 sprites with priority and attributes
- ✅ **PPU modes**: Implementation of modes 0-3 (H-Blank, V-Blank, OAM Search, Pixel Transfer)
- ✅ **STAT register**: Management of PPU mode-based interrupts
- ✅ **Optimizations**: Tile cache, scanline-based rendering

### Timer - ✅ Complete
- ✅ **DIV, TIMA, TMA, TAC registers**: Complete Timer subsystem implementation
- ✅ **Configurable frequencies**: 4096 Hz, 262144 Hz, 65536 Hz, 16384 Hz
- ✅ **Timer interrupts**: Correct interrupt generation on overflow

### Interrupts - ✅ Functional
- ✅ **Interrupt system**: VBlank, LCD STAT, Timer, Serial, Joypad
- ✅ **IF/IE registers**: Management of interrupt flags and masks
- ✅ **Correct timing**: 1 instruction delay for EI (Enable Interrupts)

### Cartridges - ✅ MBC1 Implemented
- ✅ **ROM loading**: Support for ROMs up to 2MB
- ✅ **MBC1**: Complete implementation of Memory Bank Controller type 1
- ✅ **Bank Switching**: Dynamic ROM/RAM bank switching

### Tests and Quality
- ✅ **Complete test suite**: Hundreds of passing unit tests
- ✅ **Complete coverage** of implemented components
- ✅ **Deterministic tests** without OS dependencies

### Documentation
- ✅ **Static web log**: 90+ detailed educational entries in `docs/bitacora/`
- ✅ **Complete report**: Complete technical log in `INFORME_COMPLETO.md`
- ✅ **Educational docstrings**: Each component includes hardware explanations

## 📋 Requirements

- **Python 3.10 or higher** (required for match/case and other modern features)
- **pip** (Python package manager)

## 🚀 Installation

1. **Clone the repository**:
```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run tests** to verify installation:
```bash
pytest tests/ -v
```

5. **Run the emulator** (currently in development):
```bash
python main.py
```

## 📁 Project Structure

```
ViboyColor/
├── src/
│   ├── cpu/              # LR35902 processor logic
│   │   ├── core.py       # Instruction cycle and opcodes
│   │   └── registers.py  # Registers and flags
│   ├── memory/           # Memory management
│   │   └── mmu.py        # Memory Management Unit
│   └── gpu/              # Graphics rendering (pending)
├── tests/                # Unit tests
│   ├── test_registers.py # Register tests
│   ├── test_mmu.py       # MMU tests
│   ├── test_cpu_core.py  # Instruction cycle tests
│   └── test_alu.py       # ALU and flag tests
├── docs/
│   └── bitacora/         # Static web log
│       ├── index.html    # Entry index
│       ├── entries/      # Individual entries
│       └── assets/       # CSS styles
├── main.py               # Main entry point
├── requirements.txt      # Project dependencies
├── INFORME_COMPLETO.md   # Complete technical log
└── README.md             # This file
```

## 🧪 Running Tests

To run all tests:
```bash
pytest tests/ -v
```

To run tests with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

## 📚 Documentation

### Web Log
The static web log contains detailed educational documentation of each development step:
- Open `docs/bitacora/index.html` in your browser
- Works completely offline (no external dependencies)
- Includes hardware explanations, implementation and validation

### Technical Report
See `INFORME_COMPLETO.md` for the complete technical log with all implementation details.

## 🔄 Project Status

**Current version**: v0.0.2-dev (Work in Progress)

### ✅ Phase 1 (v0.0.1) - Completed and Closed

**Technical Achievements:**
- ✅ Complete LR35902 CPU with all opcodes
- ✅ Functional MMU with complete memory mapping
- ✅ Functional PPU with Background, Window and Sprite rendering
- ✅ Complete Timer with all frequencies
- ✅ Functional interrupt system
- ✅ Cartridge loading (MBC1)
- ✅ Complete suite of unit tests
- ✅ Web log with 90+ educational entries

**Functional Status:**
- ✅ The emulator boots and loads ROMs
- ✅ Executes CPU instructions correctly
- ✅ Displays graphics on screen
- ⚠️ **Known limitation**: Cycle-by-cycle synchronization in pure Python prevents smooth gameplay

**Academic Conclusion:**
This project has been a success as a computer architecture learning tool. The goal of "learning how the machine works" has been achieved through practical implementation from scratch. The "scanline loop" architecture in an interpreted language introduces input latency and timer desynchronization that breaks the logic of timing-sensitive games.

**Archived documentation**: `docs/archive/INFORME_v0.0.1_FINAL.md`

### 🚀 Phase 2 (v0.0.2) - In Progress

**Goal**: Core migration to C++/Cython and Audio (APU).

**Main Tasks:**
- [ ] Core rewrite in C++/Cython
  - [ ] CPU (LR35902) in C++ with Cython wrapper
  - [ ] MMU in compiled code
  - [ ] PPU in compiled code
- [ ] Audio (APU) implementation
  - [ ] Channel 1 & 2: Square wave with Sweep and Envelope
  - [ ] Channel 3: Arbitrary wave (Wave RAM)
  - [ ] Channel 4: White noise (LFSR)
  - [ ] Mixing and output at 44100Hz/48000Hz
- [ ] Maintain Python interface for frontend and tests
- [ ] Cycle-by-cycle synchronization optimization
- [ ] Validation with timing-sensitive games (Tetris, Pokémon)

**Development log**: `INFORME_FASE_2.md`

## 🤝 Contributing

This is an educational and open source project. Contributions are welcome, but must follow the project principles:

1. **Clean-Room**: Do not copy code from other emulators
2. **Documentation**: Include educational hardware explanations
3. **Tests**: Add unit tests for new features
4. **Portability**: Ensure Windows/Linux/macOS compatibility

## 📝 License

This project is educational and open source, distributed under the **MIT** license.

See the [LICENSE](LICENSE) file for details about terms of use, distribution and code modification.

**MIT License Summary:**
- ✅ Allows commercial and private use
- ✅ Allows modification and distribution
- ✅ Requires maintaining copyright notice
- ✅ No warranties (software "as is")

## 🙏 Acknowledgments

This project is developed exclusively based on:
- Official technical documentation (Pan Docs, hardware manuals)
- Redistributable test ROMs with open license
- Observation of hardware behavior

**No code from other emulators is used** (mGBA, Gambatte, SameBoy, etc.) to maintain the project's clean-room integrity.

## 📧 Contact

For questions or suggestions about the project, open an issue in the GitHub repository.

---

## 📖 Methodology: Vibe Coding

This project was developed through **"Vibe Coding"** (AI-assisted programming without deep prior knowledge of the Game Boy architecture). Each development step was documented in the web log (`docs/bitacora/`), reflecting the learning process and technical decisions made.

**Applied principles:**
- Clean-room implementation based solely on technical documentation
- Educational documentation of each component
- Unit tests to validate implementations
- Transparency about limitations and design decisions

**Note**: This project is an Academic Proof of Concept (PoC). The emulator works technically but gameplay is not viable due to synchronization limitations in pure Python. Version v0.0.2 will migrate the core to a compiled language to achieve the necessary timing precision.

---

# Viboy Color - Español

Un emulador de Game Boy Color escrito en Python, desarrollado desde cero mediante **"Vibe Coding"** (Programación asistida por IA sin conocimientos previos profundos de la arquitectura GB) con un enfoque educativo y clean-room.

## 🎯 Descripción

**Viboy Color** es un emulador del sistema Game Boy Color desarrollado completamente desde cero en Python mediante **"Vibe Coding"** (Programación asistida por IA sin conocimientos previos profundos de la arquitectura Game Boy). Este proyecto tiene como objetivo principal ser una herramienta educativa que permita comprender la arquitectura del hardware original mediante implementación clean-room (sin copiar código de otros emuladores).

### ⚠️ Estado Actual: v0.0.2-dev (Work in Progress)

**Fase 1 (v0.0.1) - CERRADA**: El proyecto alcanzó el estado de **Prueba de Concepto (PoC) Académica** exitosa. El emulador funciona a nivel técnico: carga ROMs, ejecuta instrucciones de CPU, gestiona memoria, dibuja gráficos y muestra juegos en pantalla. Sin embargo, la jugabilidad no es viable debido a problemas de sincronización fina y latencia inherentes a la implementación en Python puro.

**Fase 2 (v0.0.2) - EN DESARROLLO**: Migración del núcleo a C++/Cython y implementación de Audio (APU). El objetivo es alcanzar precisión de timing necesaria para jugabilidad completa mediante código compilado, manteniendo la interfaz Python para frontend y tests.

### Principios del Proyecto

- ✅ **Implementación Clean-Room**: Todo el código se desarrolla únicamente desde documentación técnica oficial
- ✅ **Enfoque Educativo**: Cada componente incluye documentación detallada explicando el hardware subyacente
- ✅ **Portabilidad Total**: Compatible con Windows, Linux y macOS
- ✅ **Python Moderno**: Utiliza Python 3.10+ con tipado estricto y mejores prácticas
- ✅ **Test-Driven Development**: Suite completa de tests unitarios para validar cada componente

## ✨ Características Implementadas (v0.0.1)

### CPU (LR35902) - ✅ Completa
- ✅ **Registros completos**: Implementación de todos los registros de 8 y 16 bits (A, B, C, D, E, H, L, F, PC, SP)
- ✅ **Pares virtuales**: Soporte para pares de 16 bits (AF, BC, DE, HL)
- ✅ **Sistema de flags**: Gestión completa de flags (Z, N, H, C) con peculiaridades del hardware
- ✅ **Ciclo Fetch-Decode-Execute**: Implementación del ciclo de instrucción fundamental
- ✅ **ALU completa**: Unidad Aritmética Lógica con gestión correcta de flags, especialmente Half-Carry
- ✅ **Opcodes completos**: Implementación de todos los opcodes del set de instrucciones LR35902 (incluyendo prefijo CB)
- ✅ **Tabla de despacho**: Sistema escalable para manejo de opcodes con match/case

### MMU (Memory Management Unit) - ✅ Funcional
- ✅ **Espacio de direcciones completo**: Gestión del espacio de 16 bits (0x0000-0xFFFF)
- ✅ **Operaciones Little-Endian**: Lectura/escritura de palabras de 16 bits con endianness correcta
- ✅ **Wrap-around**: Manejo correcto de desbordamientos de direcciones y valores
- ✅ **Enmascarado automático**: Protección contra valores fuera de rango
- ✅ **Mapeo de regiones**: ROM, VRAM, OAM, I/O, HRAM, Cartuchos (MBC1)

### PPU (Picture Processing Unit) - ✅ Funcional
- ✅ **Renderizado de Background**: Tilemap completo con scroll (SCX/SCY)
- ✅ **Renderizado de Window**: Capa de ventana independiente
- ✅ **Renderizado de Sprites**: Hasta 40 sprites con prioridad y atributos
- ✅ **Modos PPU**: Implementación de modos 0-3 (H-Blank, V-Blank, OAM Search, Pixel Transfer)
- ✅ **Registro STAT**: Gestión de interrupciones basadas en modos PPU
- ✅ **Optimizaciones**: Caché de tiles, renderizado por scanlines

### Timer - ✅ Completo
- ✅ **Registros DIV, TIMA, TMA, TAC**: Implementación completa del subsistema Timer
- ✅ **Frecuencias configurables**: 4096 Hz, 262144 Hz, 65536 Hz, 16384 Hz
- ✅ **Interrupciones de Timer**: Generación correcta de interrupciones en overflow

### Interrupciones - ✅ Funcional
- ✅ **Sistema de interrupciones**: VBlank, LCD STAT, Timer, Serial, Joypad
- ✅ **Registros IF/IE**: Gestión de flags y máscaras de interrupciones
- ✅ **Timing correcto**: Retraso de 1 instrucción para EI (Enable Interrupts)

### Cartuchos - ✅ MBC1 Implementado
- ✅ **Carga de ROMs**: Soporte para ROMs de hasta 2MB
- ✅ **MBC1**: Implementación completa del Memory Bank Controller tipo 1
- ✅ **Bank Switching**: Cambio dinámico de bancos ROM/RAM

### Tests y Calidad
- ✅ **Suite completa de tests**: Cientos de tests unitarios pasando
- ✅ **Cobertura completa** de componentes implementados
- ✅ **Tests deterministas** sin dependencias del sistema operativo

### Documentación
- ✅ **Bitácora web estática**: 90+ entradas educativas detalladas en `docs/bitacora/`
- ✅ **Informe completo**: Bitácora técnica completa en `INFORME_COMPLETO.md`
- ✅ **Docstrings educativos**: Cada componente incluye explicaciones del hardware

## 📋 Requisitos

- **Python 3.10 o superior** (requerido para match/case y otras características modernas)
- **pip** (gestor de paquetes de Python)

## 🚀 Instalación

1. **Clona el repositorio**:
```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Crea un entorno virtual** (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. **Instala las dependencias**:
```bash
pip install -r requirements.txt
```

4. **Ejecuta los tests** para verificar la instalación:
```bash
pytest tests/ -v
```

5. **Ejecuta el emulador** (actualmente en desarrollo):
```bash
python main.py
```

## 📁 Estructura del Proyecto

```
ViboyColor/
├── src/
│   ├── cpu/              # Lógica del procesador LR35902
│   │   ├── core.py       # Ciclo de instrucción y opcodes
│   │   └── registers.py  # Registros y flags
│   ├── memory/           # Gestión de memoria
│   │   └── mmu.py        # Memory Management Unit
│   └── gpu/              # Renderizado gráfico (pendiente)
├── tests/                # Tests unitarios
│   ├── test_registers.py # Tests de registros
│   ├── test_mmu.py       # Tests de MMU
│   ├── test_cpu_core.py  # Tests del ciclo de instrucción
│   └── test_alu.py       # Tests de ALU y flags
├── docs/
│   └── bitacora/         # Bitácora web estática
│       ├── index.html    # Índice de entradas
│       ├── entries/      # Entradas individuales
│       └── assets/       # Estilos CSS
├── main.py               # Punto de entrada principal
├── requirements.txt      # Dependencias del proyecto
├── INFORME_COMPLETO.md   # Bitácora técnica completa
└── README.md             # Este archivo
```

## 🧪 Ejecutar Tests

Para ejecutar todos los tests:
```bash
pytest tests/ -v
```

Para ejecutar tests con cobertura:
```bash
pytest tests/ --cov=src --cov-report=html
```

## 📚 Documentación

### Bitácora Web
La bitácora web estática contiene documentación educativa detallada de cada paso del desarrollo:
- Abre `docs/bitacora/index.html` en tu navegador
- Funciona completamente offline (sin dependencias externas)
- Incluye explicaciones del hardware, implementación y validación

### Informe Técnico
Consulta `INFORME_COMPLETO.md` para la bitácora técnica completa con todos los detalles de implementación.

## 🔄 Estado del Proyecto

**Versión actual**: v0.0.2-dev (Work in Progress)

### ✅ Fase 1 (v0.0.1) - Completada y Cerrada

**Logros Técnicos:**
- ✅ CPU LR35902 completa con todos los opcodes
- ✅ MMU funcional con mapeo completo de memoria
- ✅ PPU funcional con renderizado de Background, Window y Sprites
- ✅ Timer completo con todas las frecuencias
- ✅ Sistema de interrupciones funcional
- ✅ Carga de cartuchos (MBC1)
- ✅ Suite completa de tests unitarios
- ✅ Bitácora web con 90+ entradas educativas

**Estado Funcional:**
- ✅ El emulador arranca y carga ROMs
- ✅ Ejecuta instrucciones de CPU correctamente
- ✅ Muestra gráficos en pantalla
- ⚠️ **Limitación conocida**: La sincronización ciclo a ciclo en Python puro impide jugabilidad fluida

**Conclusión Académica:**
Este proyecto ha sido un éxito como herramienta de aprendizaje de arquitectura de computadores. El objetivo de "aprender cómo funciona la máquina" se ha cumplido mediante implementación práctica desde cero. La arquitectura de "bucle por scanline" en un lenguaje interpretado introduce latencia de input y desincronización de timer que rompe la lógica de juegos sensibles al timing.

**Documentación archivada**: `docs/archive/INFORME_v0.0.1_FINAL.md`

### 🚀 Fase 2 (v0.0.2) - En Progreso

**Objetivo**: Migración del núcleo a C++/Cython y Audio (APU).

**Tareas Principales:**
- [ ] Reescritura del núcleo en C++/Cython
  - [ ] CPU (LR35902) en C++ con wrapper Cython
  - [ ] MMU en código compilado
  - [ ] PPU en código compilado
- [ ] Implementación de Audio (APU)
  - [ ] Canal 1 & 2: Onda cuadrada con Sweep y Envelope
  - [ ] Canal 3: Onda arbitraria (Wave RAM)
  - [ ] Canal 4: Ruido blanco (LFSR)
  - [ ] Mezcla y salida a 44100Hz/48000Hz
- [ ] Mantener interfaz Python para frontend y tests
- [ ] Optimización de sincronización ciclo a ciclo
- [ ] Validación con juegos sensibles al timing (Tetris, Pokémon)

**Bitácora de desarrollo**: `INFORME_FASE_2.md`

## 🤝 Contribuir

Este es un proyecto educativo y open source. Las contribuciones son bienvenidas, pero deben seguir los principios del proyecto:

1. **Clean-Room**: No copiar código de otros emuladores
2. **Documentación**: Incluir explicaciones educativas del hardware
3. **Tests**: Añadir tests unitarios para nuevas funcionalidades
4. **Portabilidad**: Asegurar compatibilidad Windows/Linux/macOS

## 📝 Licencia

Este proyecto es educativo y open source, distribuido bajo la licencia **MIT**.

Consulta el archivo [LICENSE](LICENSE) para más detalles sobre los términos de uso, distribución y modificación del código.

**Resumen de la licencia MIT:**
- ✅ Permite uso comercial y privado
- ✅ Permite modificación y distribución
- ✅ Requiere mantener el aviso de copyright
- ✅ No ofrece garantías (software "as is")

## 🙏 Agradecimientos

Este proyecto se desarrolla únicamente basándose en:
- Documentación técnica oficial (Pan Docs, manuales de hardware)
- ROMs de test redistribuibles con licencia abierta
- Observación del comportamiento del hardware

**No se utiliza código de otros emuladores** (mGBA, Gambatte, SameBoy, etc.) para mantener la integridad clean-room del proyecto.

## 📧 Contacto

Para preguntas o sugerencias sobre el proyecto, abre un issue en el repositorio de GitHub.

---

## 📖 Metodología: Vibe Coding

Este proyecto fue desarrollado mediante **"Vibe Coding"** (Programación asistida por IA sin conocimientos previos profundos de la arquitectura Game Boy). Cada paso del desarrollo fue documentado en la bitácora web (`docs/bitacora/`), reflejando el proceso de aprendizaje y las decisiones técnicas tomadas.

**Principios aplicados:**
- Implementación clean-room basada únicamente en documentación técnica
- Documentación educativa de cada componente
- Tests unitarios para validar implementaciones
- Transparencia sobre limitaciones y decisiones de diseño

**Nota**: Este proyecto es una Prueba de Concepto (PoC) Académica. El emulador funciona técnicamente pero la jugabilidad no es viable debido a limitaciones de sincronización en Python puro. La versión v0.0.2 migrará el núcleo a un lenguaje compilado para alcanzar precisión de timing necesaria.
