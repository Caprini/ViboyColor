# Viboy Color

Un emulador de Game Boy Color escrito en Python, desarrollado desde cero con un enfoque educativo y clean-room.

## 🎯 Descripción

**Viboy Color** es un emulador del sistema Game Boy Color desarrollado completamente desde cero en Python. Este proyecto tiene como objetivo principal ser una herramienta educativa que permita comprender la arquitectura del hardware original mediante implementación clean-room (sin copiar código de otros emuladores).

### Principios del Proyecto

- ✅ **Implementación Clean-Room**: Todo el código se desarrolla únicamente desde documentación técnica oficial
- ✅ **Enfoque Educativo**: Cada componente incluye documentación detallada explicando el hardware subyacente
- ✅ **Portabilidad Total**: Compatible con Windows, Linux y macOS
- ✅ **Python Moderno**: Utiliza Python 3.10+ con tipado estricto y mejores prácticas
- ✅ **Test-Driven Development**: Suite completa de tests unitarios para validar cada componente

## ✨ Características Implementadas

### CPU (LR35902)
- ✅ **Registros completos**: Implementación de todos los registros de 8 y 16 bits (A, B, C, D, E, H, L, F, PC, SP)
- ✅ **Pares virtuales**: Soporte para pares de 16 bits (AF, BC, DE, HL)
- ✅ **Sistema de flags**: Gestión completa de flags (Z, N, H, C) con peculiaridades del hardware
- ✅ **Ciclo Fetch-Decode-Execute**: Implementación del ciclo de instrucción fundamental
- ✅ **ALU básica**: Unidad Aritmética Lógica con gestión correcta de flags, especialmente Half-Carry
- ✅ **Opcodes implementados**: NOP, LD A,d8, LD B,d8, ADD A,d8, SUB d8
- ✅ **Tabla de despacho**: Sistema escalable para manejo de opcodes

### MMU (Memory Management Unit)
- ✅ **Espacio de direcciones completo**: Gestión del espacio de 16 bits (0x0000-0xFFFF)
- ✅ **Operaciones Little-Endian**: Lectura/escritura de palabras de 16 bits con endianness correcta
- ✅ **Wrap-around**: Manejo correcto de desbordamientos de direcciones y valores
- ✅ **Enmascarado automático**: Protección contra valores fuera de rango

### Tests y Calidad
- ✅ **39 tests unitarios** pasando (registros, MMU, CPU, ALU)
- ✅ **Cobertura completa** de componentes implementados
- ✅ **Tests deterministas** sin dependencias del sistema operativo

### Documentación
- ✅ **Bitácora web estática**: Documentación educativa detallada en `docs/bitacora/`
- ✅ **Informe completo**: Bitácora técnica en `INFORME_COMPLETO.md`
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

**Estado actual**: Desarrollo activo - Fase de implementación de componentes core

### ✅ Completado
- Registros de CPU (LR35902)
- MMU básica con Little-Endian
- Ciclo de instrucción Fetch-Decode-Execute
- ALU con gestión de flags (especialmente Half-Carry)
- Sistema de tests unitarios
- Bitácora web estática

### 🚧 En Desarrollo
- Más opcodes de la CPU
- Mapeo específico de regiones de memoria
- Sistema de interrupciones
- PPU (Picture Processing Unit)
- APU (Audio Processing Unit)
- Sistema de timers
- Carga de cartuchos (MBC)

### 📅 Próximos Pasos
- Implementación de más opcodes (LD, ADD, SUB con diferentes operandos)
- Sistema de branching (JP, JR, CALL, RET)
- Interrupciones (VBlank, LCD, Timer, Serial, Joypad)
- PPU básica para renderizado de tiles
- Sistema de carga de ROMs

## 🤝 Contribuir

Este es un proyecto educativo y open source. Las contribuciones son bienvenidas, pero deben seguir los principios del proyecto:

1. **Clean-Room**: No copiar código de otros emuladores
2. **Documentación**: Incluir explicaciones educativas del hardware
3. **Tests**: Añadir tests unitarios para nuevas funcionalidades
4. **Portabilidad**: Asegurar compatibilidad Windows/Linux/macOS

## 📝 Licencia

Este proyecto es educativo y open source. Consulta el archivo LICENSE para más detalles.

## 🙏 Agradecimientos

Este proyecto se desarrolla únicamente basándose en:
- Documentación técnica oficial (Pan Docs, manuales de hardware)
- ROMs de test redistribuibles con licencia abierta
- Observación del comportamiento del hardware

**No se utiliza código de otros emuladores** (mGBA, Gambatte, SameBoy, etc.) para mantener la integridad clean-room del proyecto.

## 📧 Contacto

Para preguntas o sugerencias sobre el proyecto, abre un issue en el repositorio de GitHub.

---

**Nota**: Este proyecto está en desarrollo activo. El emulador aún no es funcional para ejecutar juegos comerciales, pero los componentes core están siendo implementados y validados con tests unitarios.

