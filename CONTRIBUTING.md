# Contributing to Viboy Color

**[ 🇬🇧 English ](#contributing-guide) | [ 🇪🇸 Español ](#guía-de-contribución)**

---

# Contributing Guide

Thank you for your interest in contributing to Viboy Color! This document will guide you through the project's philosophy, architecture, and development workflow.

---

## 🍷 Project Philosophy

### Clean Room Policy (CRITICAL)

**Absolute zero tolerance for piracy and code copying.**

This project follows a strict **Clean Room Implementation** approach. This means:

- ✅ **DO**: Use official technical documentation (Pan Docs, GBEDG, hardware manuals)
- ✅ **DO**: Implement features based on observed hardware behavior
- ✅ **DO**: Write code from scratch, understanding each component
- ❌ **DON'T**: Copy code from other emulators (mGBA, SameBoy, Gambatte, etc.)
- ❌ **DON'T**: Use Nintendo's leaked source code or reverse-engineered binaries
- ❌ **DON'T**: Share ROMs or BIOS files in the repository
- ❌ **DON'T**: Copy-paste implementations without understanding them

**Why?** This is an **educational project**. The goal is to learn how the Game Boy hardware works by implementing it ourselves, not by copying someone else's work. Every line of code should be the result of understanding the hardware specification.

### The "Archaeological" Approach

We implement features **only when a ROM requests them**. This is not laziness—it's precision.

**What this means:**

- We don't implement 100 opcodes at once in a "Big Bang" PR
- We implement opcodes/features when we encounter a ROM that needs them
- Each implementation is **atomic, tested, and documented**
- We value **understanding and correctness** over speed of implementation

**Why this approach?**

1. **Precision**: Each feature is implemented with full understanding of its purpose
2. **Testability**: We can test each feature against a real ROM that uses it
3. **Documentation**: Each step is documented in the development log (`docs/bitacora/`)
4. **Quality**: We avoid untested code that "might work" but breaks edge cases

**What we reject:**

- ❌ PRs that implement 50+ opcodes without individual tests
- ❌ "Completeness" PRs that add features not yet needed by any ROM
- ❌ Code that "looks right" but has no test coverage

**What we accept:**

- ✅ Atomic PRs that implement one opcode/feature with tests
- ✅ Bug fixes with reproduction steps and test cases
- ✅ Documentation improvements
- ✅ Performance optimizations with benchmarks

---

## 🏗️ Architecture Overview

Viboy Color uses a **hybrid architecture** that combines the best of both worlds:

### Python (Frontend/Orchestration)

- **Role**: User interface, game loop, input handling, audio output
- **Libraries**: Pygame-CE for rendering and input
- **Location**: `src/`, `main.py`
- **Why Python**: Easy to test, rapid development, excellent for educational documentation

### C++ (Core Emulation)

- **Role**: Cycle-accurate CPU, PPU, MMU emulation
- **Location**: `src/core/cpp/`
- **Why C++**: Performance-critical code needs compiled speed for 60 FPS emulation
- **Standard**: C++17

### Cython (The Bridge)

- **Role**: Seamless Python ↔ C++ interop
- **Location**: `src/core/cython/`
- **Files**: `.pyx` (implementation), `.pxd` (declarations)
- **Why Cython**: Zero-cost abstractions, direct memory access, GIL management

### Data Flow

```
Python (main.py)
    ↓
Cython Wrapper (native_core.pyx)
    ↓
C++ Core (CPU.cpp, PPU.cpp, MMU.cpp)
    ↓
Python (Pygame rendering)
```

---

## ⚙️ Development Setup

### Prerequisites

**Required:**

- **Python 3.11+** (required for modern features and Cython compatibility)
- **C++ Compiler**:
  - **Windows**: Visual Studio Build Tools 2019+ (or Visual Studio Community)
  - **Linux**: GCC 9+ or Clang 10+
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)
- **Git** (for version control)

**Python Packages:**

All dependencies are listed in `requirements.txt`. Install them with:

```bash
pip install -r requirements.txt
```

This will install:
- `cython>=3.0.0` (for compiling C++ extensions)
- `pytest>=7.4.0` (for running tests)
- `pygame-ce>=2.3.0` (for rendering)
- `numpy>=1.24.0` (for efficient array operations)
- `setuptools>=68.0.0` (for building extensions)

### Installation Steps

1. **Clone the repository:**

```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Create a virtual environment (recommended):**

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

4. **Compile the C++ core (MANDATORY):**

The emulator **will not run** without compiling the C++ module. This is the most critical step.

**Standard method:**

```bash
python setup.py build_ext --inplace
```

This will:
- Compile all `.cpp` files in `src/core/cpp/`
- Generate Cython bindings from `.pyx` files
- Create a `.pyd` file (Windows) or `.so` file (Linux/macOS) named `viboy_core.*.pyd`

**Windows helper script:**

If you're on Windows, you can use the helper script for easier recompilation:

```powershell
.\rebuild_cpp.ps1
```

This script:
- Renames old `.pyd` files to avoid conflicts
- Cleans previous build artifacts
- Recompiles the module
- Provides helpful status messages

**Troubleshooting compilation:**

- **Error: "Microsoft Visual C++ 14.0 or greater is required"** (Windows):
  - Install Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
  - Select "Desktop development with C++" workload

- **Error: "Cython not found"**:
  - Run: `pip install cython`

- **Error: "Cannot find C++ compiler"** (Linux/macOS):
  - Linux: `sudo apt-get install build-essential` (Debian/Ubuntu)
  - macOS: `xcode-select --install`

5. **Verify the build:**

Run the build test script:

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

If you see errors, check the troubleshooting section above.

---

## 🧪 Running Tests

The project uses **pytest** for testing. Tests cover both Python logic and compiled C++ modules.

### Run all tests:

```bash
pytest
```

### Run with verbose output:

```bash
pytest -v
```

### Run specific test file:

```bash
pytest tests/test_core_cpu.py
```

### Run with coverage report:

```bash
pytest --cov=src --cov-report=html
```

This generates an HTML coverage report in `htmlcov/index.html`.

### Test Structure

- **Python tests**: `tests/test_*.py` (test Python components)
- **C++ integration tests**: `tests/test_integration_cpp.py` (test compiled modules)
- **Core tests**: `tests/test_core_*.py` (test C++ core functionality via Cython)

**Important**: Tests that import `viboy_core` require the module to be compiled first. If you see `ImportError: No module named 'viboy_core'`, run `python setup.py build_ext --inplace`.

---

## 🚀 Pull Request Process

### Before You Start

1. **Check existing issues**: Someone might already be working on the feature
2. **Read the philosophy**: Make sure your contribution aligns with the "Archaeological" approach
3. **Compile the core**: Ensure `python test_build.py` passes on your machine

### Creating a Pull Request

1. **Fork the repository** (if you don't have write access)

2. **Create a feature branch:**

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

**Branch naming convention:**
- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation
- `refactor/` for code refactoring

3. **Make your changes:**

   - Follow the **Clean Room Policy**: Don't copy code from other emulators
   - Follow the **Archaeological Approach**: Implement one feature at a time
   - Add **unit tests** for any new opcode or hardware feature
   - Update **documentation** if you add new components

4. **Ensure tests pass:**

```bash
# Run all tests
pytest

# Verify the build still works
python test_build.py
```

5. **Commit your changes:**

```bash
git add .
git commit -m "feat(core): implement opcode 0x42 (LD B, D)"
```

**Commit message format:**

- `feat(component): description` - New feature
- `fix(component): description` - Bug fix
- `docs(component): description` - Documentation
- `test(component): description` - Tests
- `refactor(component): description` - Code refactoring

6. **Push to your fork:**

```bash
git push origin feature/your-feature-name
```

7. **Create a Pull Request on GitHub:**

   - **Title**: Clear, descriptive (e.g., "feat(core): implement opcode 0x42")
   - **Description**: Explain what you implemented and why
   - **Link to documentation**: If you referenced Pan Docs or GBEDG, include the link
   - **Test results**: Include output from `pytest` showing your tests pass

### PR Review Criteria

Your PR will be reviewed for:

- ✅ **Clean Room compliance**: No copied code from other emulators
- ✅ **Test coverage**: New features have unit tests
- ✅ **Documentation**: Code includes docstrings explaining hardware behavior
- ✅ **Build verification**: `python test_build.py` passes
- ✅ **Atomic changes**: One feature/opcode per PR (unless logically grouped)
- ✅ **Code quality**: Follows project style (PEP 8 for Python, Google C++ Style Guide for C++)

### Common PR Rejection Reasons

- ❌ **"Big Bang" PRs**: Implementing 50+ opcodes without individual tests
- ❌ **Copied code**: Code that matches other emulators line-by-line
- ❌ **Untested features**: New opcodes without unit tests
- ❌ **Build failures**: `python test_build.py` fails
- ❌ **Missing documentation**: No docstrings explaining hardware behavior

---

## 📝 Code Style Guidelines

### Python

- Follow **PEP 8** strictly
- Use type hints: `from __future__ import annotations`
- Maximum line length: 100 characters
- Use `match/case` for opcode dispatch (Python 3.10+)

### C++

- Follow **Google C++ Style Guide** or similar consistent style
- Use **C++17** features (smart pointers, `auto`, etc.)
- Avoid `new/delete`; use `std::unique_ptr` or `std::vector`
- Use `inline` for small functions in hot paths
- **NO logging in the emulation loop** (use debug builds only)

### Cython

- Use static types: `cdef int`, `cdef unsigned char`
- Free C++ resources in `__dealloc__`
- Use MemoryViews for efficient array passing: `unsigned char[:]`

---

## 🐛 Reporting Bugs

Before reporting a bug, please:

1. **Verify the build**: Run `python test_build.py` to ensure the C++ module is compiled
2. **Check existing issues**: Search for similar bugs
3. **Provide reproduction steps**: Include ROM name, exact steps to reproduce
4. **Include logs**: If applicable, include error messages or console output

**Bug report template:**

```markdown
**ROM**: [ROM name]
**Steps to reproduce**:
1. ...
2. ...

**Expected behavior**: ...

**Actual behavior**: ...

**Build verification**: `python test_build.py` output
```

---

## 📚 Additional Resources

- **Pan Docs**: https://gbdev.io/pandocs/
- **GBEDG**: https://gbdev.io/gb-opcodes/
- **Project Web Log**: `docs/bitacora/index.html` (open in browser)
- **Development Log**: `INFORME_FASE_2.md`

---

## 🙏 Thank You!

Thank you for contributing to Viboy Color! Every contribution, no matter how small, helps make this educational project better. Remember: we value **precision and understanding** over speed. Take your time, understand the hardware, and write clean, tested code.

Happy coding! 🎮

---

# Guía de Contribución

¡Gracias por tu interés en contribuir a Viboy Color! Este documento te guiará a través de la filosofía del proyecto, la arquitectura y el flujo de trabajo de desarrollo.

---

## 🍷 Filosofía del Proyecto

### Política Clean Room (CRÍTICA)

**Tolerancia cero absoluta a la piratería y la copia de código.**

Este proyecto sigue un enfoque estricto de **Implementación Clean Room**. Esto significa:

- ✅ **SÍ**: Usar documentación técnica oficial (Pan Docs, GBEDG, manuales de hardware)
- ✅ **SÍ**: Implementar funcionalidades basándose en el comportamiento observado del hardware
- ✅ **SÍ**: Escribir código desde cero, entendiendo cada componente
- ❌ **NO**: Copiar código de otros emuladores (mGBA, SameBoy, Gambatte, etc.)
- ❌ **NO**: Usar código fuente filtrado de Nintendo o binarios desensamblados
- ❌ **NO**: Compartir ROMs o archivos BIOS en el repositorio
- ❌ **NO**: Copiar y pegar implementaciones sin entenderlas

**¿Por qué?** Este es un **proyecto educativo**. El objetivo es aprender cómo funciona el hardware del Game Boy implementándolo nosotros mismos, no copiando el trabajo de otros. Cada línea de código debe ser el resultado de entender la especificación del hardware.

### El Enfoque "Arqueológico"

Implementamos funcionalidades **solo cuando una ROM las solicita**. Esto no es pereza, es precisión.

**Qué significa esto:**

- No implementamos 100 opcodes a la vez en un PR "Big Bang"
- Implementamos opcodes/funcionalidades cuando encontramos una ROM que los necesita
- Cada implementación es **atómica, probada y documentada**
- Valoramos la **comprensión y la corrección** sobre la velocidad de implementación

**¿Por qué este enfoque?**

1. **Precisión**: Cada funcionalidad se implementa con plena comprensión de su propósito
2. **Testabilidad**: Podemos probar cada funcionalidad contra una ROM real que la usa
3. **Documentación**: Cada paso se documenta en el log de desarrollo (`docs/bitacora/`)
4. **Calidad**: Evitamos código no probado que "podría funcionar" pero rompe casos límite

**Qué rechazamos:**

- ❌ PRs que implementan 50+ opcodes sin tests individuales
- ❌ PRs de "Completitud" que añaden funcionalidades que ninguna ROM necesita aún
- ❌ Código que "se ve bien" pero no tiene cobertura de tests

**Qué aceptamos:**

- ✅ PRs atómicos que implementan un opcode/funcionalidad con tests
- ✅ Correcciones de bugs con pasos de reproducción y casos de prueba
- ✅ Mejoras de documentación
- ✅ Optimizaciones de rendimiento con benchmarks

---

## 🏗️ Resumen de Arquitectura

Viboy Color usa una **arquitectura híbrida** que combina lo mejor de ambos mundos:

### Python (Frontend/Orquestación)

- **Rol**: Interfaz de usuario, bucle de juego, manejo de input, salida de audio
- **Bibliotecas**: Pygame-CE para renderizado e input
- **Ubicación**: `src/`, `main.py`
- **Por qué Python**: Fácil de probar, desarrollo rápido, excelente para documentación educativa

### C++ (Núcleo de Emulación)

- **Rol**: Emulación de ciclo exacto de CPU, PPU, MMU
- **Ubicación**: `src/core/cpp/`
- **Por qué C++**: El código crítico de rendimiento necesita velocidad compilada para emulación a 60 FPS
- **Estándar**: C++17

### Cython (El Puente)

- **Rol**: Interoperabilidad fluida Python ↔ C++
- **Ubicación**: `src/core/cython/`
- **Archivos**: `.pyx` (implementación), `.pxd` (declaraciones)
- **Por qué Cython**: Abstracciones sin costo, acceso directo a memoria, gestión de GIL

### Flujo de Datos

```
Python (main.py)
    ↓
Wrapper Cython (native_core.pyx)
    ↓
Núcleo C++ (CPU.cpp, PPU.cpp, MMU.cpp)
    ↓
Python (Renderizado Pygame)
```

---

## ⚙️ Configuración de Desarrollo

### Prerrequisitos

**Requerido:**

- **Python 3.11+** (requerido para características modernas y compatibilidad con Cython)
- **Compilador C++**:
  - **Windows**: Visual Studio Build Tools 2019+ (o Visual Studio Community)
  - **Linux**: GCC 9+ o Clang 10+
  - **macOS**: Xcode Command Line Tools (`xcode-select --install`)
- **Git** (para control de versiones)

**Paquetes de Python:**

Todas las dependencias están listadas en `requirements.txt`. Instálalas con:

```bash
pip install -r requirements.txt
```

Esto instalará:
- `cython>=3.0.0` (para compilar extensiones C++)
- `pytest>=7.4.0` (para ejecutar tests)
- `pygame-ce>=2.3.0` (para renderizado)
- `numpy>=1.24.0` (para operaciones eficientes con arrays)
- `setuptools>=68.0.0` (para construir extensiones)

### Pasos de Instalación

1. **Clona el repositorio:**

```bash
git clone https://github.com/Caprini/ViboyColor.git
cd ViboyColor
```

2. **Crea un entorno virtual (recomendado):**

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

4. **Compila el núcleo C++ (OBLIGATORIO):**

El emulador **NO funcionará** sin compilar el módulo C++. Este es el paso más crítico.

**Método estándar:**

```bash
python setup.py build_ext --inplace
```

Esto:
- Compilará todos los archivos `.cpp` en `src/core/cpp/`
- Generará bindings de Cython desde archivos `.pyx`
- Creará un archivo `.pyd` (Windows) o `.so` (Linux/macOS) llamado `viboy_core.*.pyd`

**Script auxiliar para Windows:**

Si estás en Windows, puedes usar el script auxiliar para recompilar más fácilmente:

```powershell
.\rebuild_cpp.ps1
```

Este script:
- Renombra archivos `.pyd` antiguos para evitar conflictos
- Limpia artefactos de compilación previos
- Recompila el módulo
- Proporciona mensajes de estado útiles

**Solución de problemas de compilación:**

- **Error: "Se requiere Microsoft Visual C++ 14.0 o superior"** (Windows):
  - Instala Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/
  - Selecciona la carga de trabajo "Desktop development with C++"

- **Error: "Cython no encontrado"**:
  - Ejecuta: `pip install cython`

- **Error: "No se puede encontrar compilador C++"** (Linux/macOS):
  - Linux: `sudo apt-get install build-essential` (Debian/Ubuntu)
  - macOS: `xcode-select --install`

5. **Verifica la compilación:**

Ejecuta el script de prueba de compilación:

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

Si ves errores, revisa la sección de solución de problemas arriba.

---

## 🧪 Ejecutar Tests

El proyecto usa **pytest** para testing. Los tests cubren tanto la lógica de Python como los módulos C++ compilados.

### Ejecutar todos los tests:

```bash
pytest
```

### Ejecutar con salida verbose:

```bash
pytest -v
```

### Ejecutar archivo de test específico:

```bash
pytest tests/test_core_cpu.py
```

### Ejecutar con reporte de cobertura:

```bash
pytest --cov=src --cov-report=html
```

Esto genera un reporte de cobertura HTML en `htmlcov/index.html`.

### Estructura de Tests

- **Tests de Python**: `tests/test_*.py` (prueban componentes de Python)
- **Tests de integración C++**: `tests/test_integration_cpp.py` (prueban módulos compilados)
- **Tests del núcleo**: `tests/test_core_*.py` (prueban funcionalidad del núcleo C++ vía Cython)

**Importante**: Los tests que importan `viboy_core` requieren que el módulo esté compilado primero. Si ves `ImportError: No module named 'viboy_core'`, ejecuta `python setup.py build_ext --inplace`.

---

## 🚀 Proceso de Pull Request

### Antes de Empezar

1. **Revisa issues existentes**: Alguien podría estar trabajando ya en la funcionalidad
2. **Lee la filosofía**: Asegúrate de que tu contribución se alinee con el enfoque "Arqueológico"
3. **Compila el núcleo**: Asegúrate de que `python test_build.py` pase en tu máquina

### Crear un Pull Request

1. **Haz fork del repositorio** (si no tienes acceso de escritura)

2. **Crea una rama de funcionalidad:**

```bash
git checkout -b feature/tu-nombre-de-funcionalidad
# o
git checkout -b fix/tu-correccion-de-bug
```

**Convención de nombres de rama:**
- `feature/` para nuevas funcionalidades
- `fix/` para correcciones de bugs
- `docs/` para documentación
- `refactor/` para refactorización de código

3. **Haz tus cambios:**

   - Sigue la **Política Clean Room**: No copies código de otros emuladores
   - Sigue el **Enfoque Arqueológico**: Implementa una funcionalidad a la vez
   - Añade **tests unitarios** para cualquier nuevo opcode o funcionalidad de hardware
   - Actualiza la **documentación** si añades nuevos componentes

4. **Asegúrate de que los tests pasen:**

```bash
# Ejecutar todos los tests
pytest

# Verificar que la compilación aún funciona
python test_build.py
```

5. **Haz commit de tus cambios:**

```bash
git add .
git commit -m "feat(core): implement opcode 0x42 (LD B, D)"
```

**Formato de mensaje de commit:**

- `feat(componente): descripción` - Nueva funcionalidad
- `fix(componente): descripción` - Corrección de bug
- `docs(componente): descripción` - Documentación
- `test(componente): descripción` - Tests
- `refactor(componente): descripción` - Refactorización de código

6. **Haz push a tu fork:**

```bash
git push origin feature/tu-nombre-de-funcionalidad
```

7. **Crea un Pull Request en GitHub:**

   - **Título**: Claro, descriptivo (ej: "feat(core): implement opcode 0x42")
   - **Descripción**: Explica qué implementaste y por qué
   - **Enlace a documentación**: Si referenciaste Pan Docs o GBEDG, incluye el enlace
   - **Resultados de tests**: Incluye la salida de `pytest` mostrando que tus tests pasan

### Criterios de Revisión de PR

Tu PR será revisado por:

- ✅ **Cumplimiento Clean Room**: Sin código copiado de otros emuladores
- ✅ **Cobertura de tests**: Las nuevas funcionalidades tienen tests unitarios
- ✅ **Documentación**: El código incluye docstrings explicando el comportamiento del hardware
- ✅ **Verificación de compilación**: `python test_build.py` pasa
- ✅ **Cambios atómicos**: Una funcionalidad/opcode por PR (a menos que estén agrupados lógicamente)
- ✅ **Calidad de código**: Sigue el estilo del proyecto (PEP 8 para Python, Google C++ Style Guide para C++)

### Razones Comunes de Rechazo de PR

- ❌ **PRs "Big Bang"**: Implementar 50+ opcodes sin tests individuales
- ❌ **Código copiado**: Código que coincide línea por línea con otros emuladores
- ❌ **Funcionalidades no probadas**: Nuevos opcodes sin tests unitarios
- ❌ **Fallos de compilación**: `python test_build.py` falla
- ❌ **Documentación faltante**: Sin docstrings explicando el comportamiento del hardware

---

## 📝 Guías de Estilo de Código

### Python

- Sigue **PEP 8** estrictamente
- Usa type hints: `from __future__ import annotations`
- Longitud máxima de línea: 100 caracteres
- Usa `match/case` para despacho de opcodes (Python 3.10+)

### C++

- Sigue **Google C++ Style Guide** o estilo consistente similar
- Usa características de **C++17** (smart pointers, `auto`, etc.)
- Evita `new/delete`; usa `std::unique_ptr` o `std::vector`
- Usa `inline` para funciones pequeñas en rutas críticas
- **NO logging en el bucle de emulación** (usa solo builds de debug)

### Cython

- Usa tipos estáticos: `cdef int`, `cdef unsigned char`
- Libera recursos C++ en `__dealloc__`
- Usa MemoryViews para pasar arrays eficientemente: `unsigned char[:]`

---

## 🐛 Reportar Bugs

Antes de reportar un bug, por favor:

1. **Verifica la compilación**: Ejecuta `python test_build.py` para asegurar que el módulo C++ está compilado
2. **Revisa issues existentes**: Busca bugs similares
3. **Proporciona pasos de reproducción**: Incluye nombre de ROM, pasos exactos para reproducir
4. **Incluye logs**: Si aplica, incluye mensajes de error o salida de consola

**Plantilla de reporte de bug:**

```markdown
**ROM**: [nombre de ROM]
**Pasos para reproducir**:
1. ...
2. ...

**Comportamiento esperado**: ...

**Comportamiento actual**: ...

**Verificación de compilación**: Salida de `python test_build.py`
```

---

## 📚 Recursos Adicionales

- **Pan Docs**: https://gbdev.io/pandocs/
- **GBEDG**: https://gbdev.io/gb-opcodes/
- **Bitácora Web del Proyecto**: `docs/bitacora/index.html` (abre en navegador)
- **Log de Desarrollo**: `INFORME_FASE_2.md`

---

## 🙏 ¡Gracias!

¡Gracias por contribuir a Viboy Color! Cada contribución, sin importar cuán pequeña, ayuda a hacer este proyecto educativo mejor. Recuerda: valoramos la **precisión y la comprensión** sobre la velocidad. Tómate tu tiempo, entiende el hardware y escribe código limpio y probado.

¡Feliz codificación! 🎮
