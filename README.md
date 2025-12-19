# Viboy Color - Python Game Boy Emulator (Academic PoC)

[![Status: Proof of Concept](https://img.shields.io/badge/Status-Proof%20of%20Concept-orange.svg)](https://github.com/Caprini/ViboyColor)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)

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

