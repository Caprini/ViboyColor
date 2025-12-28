<div align="center">

<img src="assets/viboycolor-logo.png" width="400" alt="Viboy Color Logo">

# Viboy Color

**Educational, cycle-accurate Game Boy Color emulator**  
*Built with Python & C++ through "Vibe Coding" and the "Archaeological Approach"*

[![Status: Phase 2 Development](https://img.shields.io/badge/Status-Phase%202%20Development-blue.svg)](https://github.com/Caprini/ViboyColor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![C++17](https://img.shields.io/badge/C%2B%2B-17-blue.svg)](https://en.cppreference.com/w/cpp/17)
[![Clean Room](https://img.shields.io/badge/Clean%20Room-✓-green.svg)](https://github.com/Caprini/ViboyColor)
[![Hybrid Architecture](https://img.shields.io/badge/Architecture-Hybrid-orange.svg)](https://github.com/Caprini/ViboyColor)

## 🌐 Official Website / Web Oficial

**[viboycolor.fabini.one](https://viboycolor.fabini.one)**

---

## Language / Idioma

**[ 🇬🇧 English ](#viboy-color---english) | [ 🇪🇸 Español ](#viboy-color---español)**

---

</div>

# Viboy Color - English

An **educational, cycle-accurate Game Boy Color emulator** written in **Python 3.11** and **C++17**, developed from scratch through **"Vibe Coding"** (AI-assisted programming) with a strict **Clean Room** approach and an **"Archaeological"** development methodology.

## 🎯 What is Viboy Color?

**Viboy Color** is a Game Boy Color system emulator that serves as both a **functional emulator** and an **educational tool** for understanding computer architecture. Unlike other emulators, this project is built entirely from scratch using only official hardware documentation (Pan Docs, GBEDG), following a **Clean Room Implementation** policy that prohibits copying code from existing emulators.

### Key Principles

- ✅ **Clean Room Policy**: Zero tolerance for code copying. All implementations are based on official documentation.
- ✅ **Archaeological Approach**: Features are implemented only when a ROM requests them, ensuring precision and understanding.
- ✅ **Educational Focus**: Every component includes detailed documentation explaining the underlying hardware.
- ✅ **Hybrid Architecture**: Python handles frontend/orchestration; C++ handles cycle-accurate emulation for performance.

## ⚠️ Current Status: v0.0.2-dev (Phase 2)

**Phase 1 (v0.0.1) - ✅ COMPLETED**: Successfully achieved **Academic Proof of Concept** status. The emulator loads ROMs, executes CPU instructions, manages memory, and renders graphics. However, pure Python implementation introduced timing limitations that prevented smooth gameplay.

**Phase 2 (v0.0.2) - 🚀 IN DEVELOPMENT**: **Hybrid Core Migration**

- ✅ **CPU (LR35902)**: Migrated to C++17 for cycle-accurate performance
- ✅ **MMU (Memory Management Unit)**: Compiled C++ implementation
- ✅ **PPU (Picture Processing Unit)**: Compiled C++ implementation
- 🔄 **Audio (APU)**: In progress
- ✅ **Cython Bridge**: Seamless Python ↔ C++ interop
- ✅ **Python Frontend**: Pygame-based UI and orchestration

**The emulator now uses a hybrid architecture where the performance-critical core (CPU/PPU/MMU) runs in compiled C++, while Python handles the user interface and testing infrastructure.**

## ⚡ Quick Start

### Prerequisites

- **Python 3.11+** (required for Cython compatibility)
- **C++ Compiler**:
  - **Windows**: Visual Studio Build Tools 2019+ (or Visual Studio Community)
  - **Linux**: GCC 9+ or Clang 10+
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **⚠️ Compile the C++ Core (MANDATORY):**

**The emulator will NOT run without compiling the C++ module.**

```bash
python setup.py build_ext --inplace
```

**Windows users can use the helper script:**
```powershell
.\rebuild_cpp.ps1
```

5. **Verify the build:**
```bash
python test_build.py
```

You should see:
```
[OK] Módulo importado correctamente
[OK] Instancia creada correctamente
[OK] Resultado: 4
[EXITO] El pipeline de compilación funciona correctamente
```

6. **Run the emulator:**
```bash
python main.py <path_to_rom>
```

## 🏗️ Architecture

Viboy Color uses a **hybrid architecture** that combines the best of both worlds:

```
┌─────────────────────────────────────────┐
│  Python (Frontend/Orchestration)       │
│  - Pygame UI & Rendering                │
│  - Input Handling                       │
│  - Game Loop                            │
│  - Test Infrastructure                  │
└──────────────┬──────────────────────────┘
               │
               │ Cython Bridge
               │ (Zero-cost abstractions)
               │
┌──────────────▼──────────────────────────┐
│  C++17 (Core Emulation)                 │
│  - CPU (LR35902) - Cycle-accurate       │
│  - PPU (Picture Processing Unit)        │
│  - MMU (Memory Management Unit)         │
│  - Registers & Flags                    │
└─────────────────────────────────────────┘
```

### Why Hybrid?

- **Python**: Excellent for rapid development, testing, and educational documentation
- **C++**: Required for cycle-accurate emulation at 60 FPS (4.19 MHz Game Boy clock)
- **Cython**: Seamless interop with zero overhead, direct memory access, GIL management

## ✨ Implemented Features

### Core Components (C++)

- ✅ **CPU (LR35902)**: Complete instruction set, cycle-accurate timing
- ✅ **MMU**: Full 16-bit address space, memory banking (MBC1)
- ✅ **PPU**: Background, Window, and Sprite rendering
- ✅ **Registers**: All 8-bit and 16-bit registers with correct flag handling

### Python Components

- ✅ **Frontend**: Pygame-based rendering and input
- ✅ **Cartridge Loading**: ROM parsing and MBC1 support
- ✅ **Timer**: Configurable frequencies (4096 Hz, 262144 Hz, etc.)
- ✅ **Interrupts**: VBlank, LCD STAT, Timer, Serial, Joypad

### Testing & Quality

- ✅ **Complete test suite**: Hundreds of unit tests (Python + C++ integration)
- ✅ **Test-Driven Development**: Every feature is validated with tests
- ✅ **Build verification**: `test_build.py` ensures compilation pipeline works

## 📚 Documentation

### Web Log (Bitácora)

The project maintains a detailed **static web log** documenting every development step:

- **Location**: `docs/bitacora/index.html`
- **Format**: Self-contained HTML (works offline)
- **Content**: Hardware explanations, implementation details, test results
- **Entries**: 160+ educational entries

**Open in your browser**: `docs/bitacora/index.html`

### Technical Reports

- **Phase 2 Development Log**: `INFORME_FASE_2.md`
- **Phase 1 Archive**: `docs/archive/INFORME_v0.0.1_FINAL.md`

### Contributing

- **Contributing Guide**: [`CONTRIBUTING.md`](CONTRIBUTING.md) - Complete setup and development workflow
- **Code of Conduct**: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **Security Policy**: [`SECURITY.md`](SECURITY.md)

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=src --cov-report=html
```

**Note**: Tests that import `viboy_core` require the C++ module to be compiled first.

## 🤝 Contributing

Contributions are welcome! However, please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.

**Key Requirements:**
- ✅ Follow the **Clean Room Policy** (no copied code from other emulators)
- ✅ Use the **Archaeological Approach** (implement features when ROMs need them)
- ✅ Add unit tests for new features
- ✅ Ensure `python test_build.py` passes
- ✅ Document hardware behavior in code comments

## 📝 License

This project is distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

## 🙏 Acknowledgments

This project is developed exclusively based on:
- **Official technical documentation**: Pan Docs, GBEDG, hardware manuals
- **Redistributable test ROMs**: With open licenses
- **Hardware observation**: Behavioral analysis of real Game Boy hardware

**No code from other emulators is used** (mGBA, SameBoy, Gambatte, etc.) to maintain Clean Room integrity.

## 📧 Contact

For questions, suggestions, or bug reports, please open an issue in the [GitHub repository](https://github.com/Caprini/ViboyColor).

---

# Viboy Color - Español

Un **emulador educativo de ciclo exacto de Game Boy Color** escrito en **Python 3.11** y **C++17**, desarrollado desde cero mediante **"Vibe Coding"** (Programación asistida por IA) con un enfoque estricto **Clean Room** y una metodología de desarrollo **"Arqueológica"**.

## 🎯 ¿Qué es Viboy Color?

**Viboy Color** es un emulador del sistema Game Boy Color que sirve tanto como **emulador funcional** como **herramienta educativa** para comprender la arquitectura de computadores. A diferencia de otros emuladores, este proyecto se construye completamente desde cero usando únicamente documentación oficial del hardware (Pan Docs, GBEDG), siguiendo una política de **Implementación Clean Room** que prohíbe copiar código de emuladores existentes.

### Principios Clave

- ✅ **Política Clean Room**: Tolerancia cero a la copia de código. Todas las implementaciones se basan en documentación oficial.
- ✅ **Enfoque Arqueológico**: Las funcionalidades se implementan solo cuando una ROM las requiere, asegurando precisión y comprensión.
- ✅ **Enfoque Educativo**: Cada componente incluye documentación detallada explicando el hardware subyacente.
- ✅ **Arquitectura Híbrida**: Python maneja el frontend/orquestación; C++ maneja la emulación de ciclo exacto para rendimiento.

## ⚠️ Estado Actual: v0.0.2-dev (Fase 2)

**Fase 1 (v0.0.1) - ✅ COMPLETADA**: Se alcanzó exitosamente el estado de **Prueba de Concepto Académica**. El emulador carga ROMs, ejecuta instrucciones de CPU, gestiona memoria y renderiza gráficos. Sin embargo, la implementación en Python puro introdujo limitaciones de timing que impidieron jugabilidad fluida.

**Fase 2 (v0.0.2) - 🚀 EN DESARROLLO**: **Migración del Núcleo Híbrido**

- ✅ **CPU (LR35902)**: Migrada a C++17 para rendimiento de ciclo exacto
- ✅ **MMU (Memory Management Unit)**: Implementación compilada en C++
- ✅ **PPU (Picture Processing Unit)**: Implementación compilada en C++
- 🔄 **Audio (APU)**: En progreso
- ✅ **Puente Cython**: Interoperabilidad fluida Python ↔ C++
- ✅ **Frontend Python**: UI basada en Pygame y orquestación

**El emulador ahora usa una arquitectura híbrida donde el núcleo crítico de rendimiento (CPU/PPU/MMU) corre en C++ compilado, mientras Python maneja la interfaz de usuario y la infraestructura de tests.**

## ⚡ Inicio Rápido

### Prerrequisitos

- **Python 3.11+** (requerido para compatibilidad con Cython)
- **Compilador C++**:
  - **Windows**: Visual Studio Build Tools 2019+ (o Visual Studio Community)
  - **Linux**: GCC 9+ o Clang 10+
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)

### Instalación

1. **Clona el repositorio:**
```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Crea un entorno virtual** (recomendado):
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

3. **Instala las dependencias:**
```bash
pip install -r requirements.txt
```

4. **⚠️ Compila el Núcleo C++ (OBLIGATORIO):**

**El emulador NO funcionará sin compilar el módulo C++.**

```bash
python setup.py build_ext --inplace
```

**Usuarios de Windows pueden usar el script auxiliar:**
```powershell
.\rebuild_cpp.ps1
```

5. **Verifica la compilación:**
```bash
python test_build.py
```

Deberías ver:
```
[OK] Módulo importado correctamente
[OK] Instancia creada correctamente
[OK] Resultado: 4
[EXITO] El pipeline de compilación funciona correctamente
```

6. **Ejecuta el emulador:**
```bash
python main.py <ruta_a_rom>
```

## 🏗️ Arquitectura

Viboy Color usa una **arquitectura híbrida** que combina lo mejor de ambos mundos:

```
┌─────────────────────────────────────────┐
│  Python (Frontend/Orquestación)         │
│  - UI y Renderizado con Pygame          │
│  - Manejo de Input                       │
│  - Bucle de Juego                        │
│  - Infraestructura de Tests              │
└──────────────┬──────────────────────────┘
               │
               │ Puente Cython
               │ (Abstracciones sin costo)
               │
┌──────────────▼──────────────────────────┐
│  C++17 (Núcleo de Emulación)            │
│  - CPU (LR35902) - Ciclo exacto         │
│  - PPU (Picture Processing Unit)        │
│  - MMU (Memory Management Unit)         │
│  - Registros y Flags                     │
└─────────────────────────────────────────┘
```

### ¿Por qué Híbrida?

- **Python**: Excelente para desarrollo rápido, testing y documentación educativa
- **C++**: Necesario para emulación de ciclo exacto a 60 FPS (reloj de Game Boy a 4.19 MHz)
- **Cython**: Interoperabilidad fluida sin overhead, acceso directo a memoria, gestión de GIL

## ✨ Características Implementadas

### Componentes del Núcleo (C++)

- ✅ **CPU (LR35902)**: Set de instrucciones completo, timing de ciclo exacto
- ✅ **MMU**: Espacio de direcciones de 16 bits completo, memory banking (MBC1)
- ✅ **PPU**: Renderizado de Background, Window y Sprites
- ✅ **Registros**: Todos los registros de 8 y 16 bits con manejo correcto de flags

### Componentes Python

- ✅ **Frontend**: Renderizado y input basados en Pygame
- ✅ **Carga de Cartuchos**: Parsing de ROMs y soporte MBC1
- ✅ **Timer**: Frecuencias configurables (4096 Hz, 262144 Hz, etc.)
- ✅ **Interrupciones**: VBlank, LCD STAT, Timer, Serial, Joypad

### Testing y Calidad

- ✅ **Suite completa de tests**: Cientos de tests unitarios (Python + integración C++)
- ✅ **Test-Driven Development**: Cada funcionalidad se valida con tests
- ✅ **Verificación de compilación**: `test_build.py` asegura que el pipeline de compilación funciona

## 📚 Documentación

### Bitácora Web

El proyecto mantiene una **bitácora web estática** detallada documentando cada paso del desarrollo:

- **Ubicación**: `docs/bitacora/index.html`
- **Formato**: HTML autocontenido (funciona offline)
- **Contenido**: Explicaciones del hardware, detalles de implementación, resultados de tests
- **Entradas**: 160+ entradas educativas

**Abre en tu navegador**: `docs/bitacora/index.html`

### Informes Técnicos

- **Bitácora de Desarrollo Fase 2**: `INFORME_FASE_2.md`
- **Archivo Fase 1**: `docs/archive/INFORME_v0.0.1_FINAL.md`

### Herramientas y Utilidades

El proyecto incluye herramientas auxiliares para desarrollo y personalización:

#### 🎨 Logo Converter

**Ubicación**: [`tools/logo_converter/`](tools/logo_converter/)

Script para convertir imágenes PNG a formato de header de cartucho de Game Boy (48 bytes, formato 1bpp). Útil para personalizar el logo de arranque del emulador.

**Uso:**
```bash
python tools/logo_converter/convert_logo_to_header.py ruta/a/tu/imagen.png
```

**Documentación completa**: Ver [`tools/logo_converter/README.md`](tools/logo_converter/README.md)

### Contribuir

- **Guía de Contribución**: [`CONTRIBUTING.md`](CONTRIBUTING.md) - Workflow completo de setup y desarrollo
- **Código de Conducta**: [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md)
- **Política de Seguridad**: [`SECURITY.md`](SECURITY.md)

## 🧪 Ejecutar Tests

```bash
# Ejecutar todos los tests
pytest

# Ejecutar con salida verbose
pytest -v

# Ejecutar con reporte de cobertura
pytest --cov=src --cov-report=html
```

**Nota**: Los tests que importan `viboy_core` requieren que el módulo C++ esté compilado primero.

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Sin embargo, por favor lee [`CONTRIBUTING.md`](CONTRIBUTING.md) primero.

**Requisitos Clave:**
- ✅ Seguir la **Política Clean Room** (no copiar código de otros emuladores)
- ✅ Usar el **Enfoque Arqueológico** (implementar funcionalidades cuando las ROMs las necesiten)
- ✅ Añadir tests unitarios para nuevas funcionalidades
- ✅ Asegurar que `python test_build.py` pase
- ✅ Documentar el comportamiento del hardware en comentarios de código

## 📝 Licencia

Este proyecto está distribuido bajo la **Licencia MIT**. Consulta [`LICENSE`](LICENSE) para más detalles.

## 🙏 Agradecimientos

Este proyecto se desarrolla exclusivamente basándose en:
- **Documentación técnica oficial**: Pan Docs, GBEDG, manuales de hardware
- **ROMs de test redistribuibles**: Con licencias abiertas
- **Observación del hardware**: Análisis del comportamiento del hardware real de Game Boy

**No se utiliza código de otros emuladores** (mGBA, SameBoy, Gambatte, etc.) para mantener la integridad Clean Room.

## 📧 Contacto

Para preguntas, sugerencias o reportes de bugs, por favor abre un issue en el [repositorio de GitHub](https://github.com/Caprini/ViboyColor).

---

<div align="center">

**Built with ❤️ for education and understanding computer architecture**

[Website](https://viboycolor.fabini.one) • [GitHub](https://github.com/Caprini/ViboyColor) • [Contributing](CONTRIBUTING.md)

</div>
