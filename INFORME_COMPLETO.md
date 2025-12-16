# Bitácora del Proyecto Viboy Color

## 2025-12-16 - Implementación del Ciclo de Instrucción de la CPU

### Conceptos Hardware Implementados

**Ciclo Fetch-Decode-Execute**: El ciclo de instrucción es el proceso fundamental que hace que una CPU funcione. Sin él, la CPU es solo una estructura de datos estática. Es el "latido" que convierte el hardware en una máquina ejecutable. El ciclo básico es: (1) Fetch: Lee el byte en la dirección apuntada por PC (opcode), (2) Increment: Avanza PC, (3) Decode: Identifica la operación, (4) Execute: Ejecuta la operación.

**M-Cycles (Ciclos de Máquina)**: Un M-Cycle corresponde a una operación de memoria. Por ahora contamos M-Cycles porque es más simple. Más adelante necesitaremos T-Cycles (ciclos de reloj) para sincronización precisa con otros componentes (PPU, APU, timers). Típicamente 1 M-Cycle = 4 T-Cycles.

**Opcodes e Instrucciones**: Un opcode es un byte (0x00 a 0xFF) que identifica una operación específica. La Game Boy tiene aproximadamente 500 opcodes diferentes. En este paso se implementaron los primeros 3: NOP (0x00), LD A,d8 (0x3E) y LD B,d8 (0x06).

#### Tareas Completadas:

1. **Clase `CPU` (`src/cpu/core.py`)**:
   - Implementación completa del ciclo Fetch-Decode-Execute
   - Método `step()` que ejecuta una sola instrucción y devuelve los ciclos consumidos
   - Método `fetch_byte()` helper para leer operandos e incrementar PC automáticamente
   - Método `_execute_opcode()` que hace dispatch de opcodes usando if/elif
   - Inyección de dependencias: CPU recibe MMU en el constructor para modularidad
   - Manejo de opcodes no implementados con `NotImplementedError` informativo
   - Logging con nivel DEBUG para trazas de depuración
   - Documentación educativa extensa explicando el ciclo de instrucción

2. **Opcodes Implementados**:
   - **0x00 - NOP (No Operation)**: No hace nada, consume 1 M-Cycle
   - **0x3E - LD A, d8**: Carga un valor inmediato de 8 bits en el registro A, consume 2 M-Cycles
   - **0x06 - LD B, d8**: Carga un valor inmediato de 8 bits en el registro B, consume 2 M-Cycles

3. **Tests Unitarios (`tests/test_cpu_core.py`)**:
   - **Test 1 (test_nop)**: Verifica que NOP avanza PC en 1 byte y consume 1 ciclo
   - **Test 2 (test_ld_a_d8)**: Verifica que LD A, d8 carga el valor correcto, avanza PC en 2 bytes y consume 2 ciclos
   - **Test 3 (test_ld_b_d8)**: Verifica que LD B, d8 funciona igual pero en el registro B
   - **Test 4 (test_unimplemented_opcode_raises)**: Verifica que opcodes no implementados lanzan NotImplementedError
   - **Test 5 (test_fetch_byte_helper)**: Verifica que fetch_byte() lee correctamente y avanza PC
   - **Test 6 (test_multiple_instructions_sequential)**: Verifica ejecución secuencial de múltiples instrucciones
   - **6 tests en total, todos pasando ✅**

4. **Actualización de Módulos**:
   - Actualizado `src/cpu/__init__.py` para exportar la clase CPU

#### Archivos Afectados:
- `src/cpu/core.py` (nuevo, 170 líneas)
- `src/cpu/__init__.py` (modificado, exporta CPU)
- `tests/test_cpu_core.py` (nuevo, 204 líneas)
- `docs/bitacora/index.html` (modificado, añadida entrada 0003)
- `docs/bitacora/entries/2025-12-16__0003__ciclo-instruccion-cpu.html` (nuevo)
- `INFORME_COMPLETO.md` (este archivo)

#### Cómo se Validó:
- Ejecución de `pytest tests/test_cpu_core.py -v`: **6 tests pasando**
- Verificación de que PC avanza correctamente después de cada instrucción
- Verificación de que los registros se actualizan correctamente con valores inmediatos
- Verificación de que los ciclos se cuentan correctamente
- Verificación de ejecución secuencial de múltiples instrucciones
- Sin errores de linting (verificado con read_lints)

#### Lo que Entiendo Ahora:
- **Ciclo Fetch-Decode-Execute**: Es el bucle fundamental que hace funcionar una CPU. Sin este ciclo, los registros y la memoria son solo estructuras de datos estáticas.
- **Program Counter (PC)**: Debe avanzar automáticamente después de cada instrucción para permitir ejecución secuencial. El helper fetch_byte() facilita esto.
- **Opcodes**: Son bytes que identifican operaciones. La mayoría de opcodes tienen operandos que siguen inmediatamente después en memoria.
- **M-Cycles**: Por ahora contamos M-Cycles porque es más simple. Más adelante necesitaremos T-Cycles para sincronización precisa.
- **Modularidad**: La CPU depende de MMU pero no viceversa. Esto permite tests independientes y mejor arquitectura.

#### Lo que Falta Confirmar:
- Timing preciso: Algunas instrucciones pueden tener variaciones en timing dependiendo de condiciones. Se validará con tests ROM cuando implementemos más opcodes.
- Interrupciones: El ciclo de instrucción debe poder ser interrumpido. Esto se implementará más adelante.
- Opcodes CB (prefijo): La Game Boy tiene un prefijo especial 0xCB que cambia el significado de los siguientes 256 opcodes. Se implementará más adelante.
- Opcodes condicionales: Muchas instrucciones tienen versiones condicionales que dependen de flags. Necesitaremos lógica de branching.

---

## 2025-12-16 - Implementación de la MMU Básica

### Conceptos Hardware Implementados

**MMU (Memory Management Unit)**: La Game Boy tiene un espacio de direcciones de 16 bits (0x0000 a 0xFFFF = 65536 bytes). Este espacio está dividido en diferentes regiones que mapean a diferentes componentes del hardware: ROM del cartucho, VRAM (Video RAM), WRAM (Working RAM), OAM (Object Attribute Memory), I/O Ports, HRAM (High RAM), y el registro IE (Interrupt Enable).

**Endianness (Little-Endian)**: La Game Boy usa Little-Endian para valores de 16 bits. Esto significa que el byte menos significativo (LSB) se almacena en la dirección más baja, y el byte más significativo (MSB) se almacena en la dirección más alta (addr+1). Por ejemplo, el valor 0x1234 se almacena como 0x34 en addr y 0x12 en addr+1.

#### Tareas Completadas:

1. **Clase `MMU` (`src/memory/mmu.py`)**:
   - Implementación completa de la gestión del espacio de direcciones de 16 bits
   - Almacenamiento usando un `bytearray` de 65536 bytes (memoria lineal por ahora)
   - Métodos `read_byte(addr)` y `write_byte(addr, value)` para operaciones de 8 bits
   - Métodos `read_word(addr)` y `write_word(addr, value)` para operaciones de 16 bits con Little-Endian
   - Enmascarado automático de direcciones y valores para asegurar rangos válidos
   - Documentación educativa extensa explicando el mapa de memoria y endianness

2. **Tests Unitarios (`tests/test_mmu.py`)**:
   - **Test 1**: Lectura/escritura básica de bytes
   - **Test 2**: Wrap-around de valores > 0xFF en escritura de bytes
   - **Test 3**: Conversión de valores negativos en escritura de bytes
   - **Test 4**: Lectura de palabras en formato Little-Endian (CRÍTICO)
   - **Test 5**: Escritura de palabras en formato Little-Endian (CRÍTICO)
   - **Test 6**: Roundtrip completo (escribir y leer palabras)
   - **Test 7**: Wrap-around de valores > 0xFFFF en escritura de palabras
   - **Test 8**: Wrap-around de direcciones fuera de rango
   - **Test 9**: Lectura de palabras en el límite del espacio (0xFFFE)
   - **Test 10**: Escritura de palabras en el límite del espacio
   - **Test 11**: Verificación de inicialización a cero
   - **Test 12**: Múltiples escrituras en la misma dirección
   - **Test 13**: Ejemplo específico de Little-Endian de la documentación
   - **13 tests en total, todos pasando ✅**

3. **Estructura de Paquetes**:
   - Creado `__init__.py` en `src/memory/` para exportar la clase `MMU`

#### Archivos Afectados:
- `src/memory/__init__.py` (nuevo)
- `src/memory/mmu.py` (nuevo, 185 líneas)
- `tests/test_mmu.py` (nuevo, 195 líneas)
- `INFORME_COMPLETO.md` (este archivo)
- `docs/bitacora/index.html` (modificado)
- `docs/bitacora/entries/2025-12-16__0002__mmu-basica.html` (nuevo)

#### Cómo se Validó:
- Ejecución de `pytest tests/test_mmu.py -v`: **13 tests pasando**
- Verificación de Little-Endian con ejemplos específicos (0xCD en addr, 0xAB en addr+1 → 0xABCD)
- Verificación de wrap-around en direcciones y valores
- Verificación de comportamiento en límites del espacio de direcciones
- Sin errores de linting (verificado con read_lints)

#### Lo que Entiendo Ahora:
- **Little-Endian**: El byte menos significativo (LSB) se almacena en la dirección más baja. La implementación correcta es `(msb << 8) | lsb` al leer, y separar con `value & 0xFF` (LSB) y `(value >> 8) & 0xFF` (MSB) al escribir. Es crítico para todas las operaciones de 16 bits.
- **Mapa de memoria**: El espacio de direcciones no es solo almacenamiento, sino un mapa donde diferentes rangos activan diferentes componentes. Esto será importante cuando implementemos mapeo específico por regiones.
- **Wrap-around**: Las direcciones y valores que exceden su rango válido deben hacer wrap-around usando máscaras bitwise para simular el comportamiento del hardware real.

#### Lo que Falta Confirmar:
- Valores iniciales de regiones específicas (I/O ports pueden tener valores iniciales específicos al boot)
- Comportamiento de regiones protegidas (ROM de solo lectura, restricciones de escritura)
- Bank Switching: El mecanismo exacto de cambio de bancos de ROM/RAM del cartucho
- Echo RAM: El comportamiento exacto de la región Echo RAM (0xE000-0xFDFF) que espeja WRAM

---

## 2025-12-16 - Configuración de la Bitácora Web Estática

### Concepto de Hardware
*Este paso no implementa hardware, sino infraestructura de documentación educativa.*

La bitácora web estática permite documentar de forma estructurada y educativa cada paso del desarrollo del emulador. Al ser completamente estática y offline, garantiza portabilidad total (Windows/Linux/macOS) y no requiere servidor ni dependencias externas, cumpliendo con los principios de portabilidad y simplicidad del proyecto.

### Tareas Completadas:

1. **Estructura de Directorios Creada**:
   - `docs/bitacora/assets/style.css` - Estilos compartidos con CSS variables y soporte para modo claro/oscuro
   - `docs/bitacora/_entry_template.html` - Plantilla base canónica para nuevas entradas
   - `docs/bitacora/index.html` - Índice principal con listado de entradas
   - `docs/bitacora/entries/` - Directorio para entradas individuales
   - `docs/bitacora/entries/2025-12-16__0000__bootstrap.html` - Primera entrada bootstrap

2. **Sistema de Estilos CSS**:
   - Variables CSS para colores, espaciado y tipografía
   - Soporte automático para modo claro/oscuro mediante `prefers-color-scheme`
   - Componentes reutilizables: `.card`, `.meta`, `.tag`, `.toc`, `.kbd`, `.integridad`, `.clean-room-notice`
   - Tipografía del sistema (`system-ui`) sin dependencias externas
   - Diseño responsive con media queries

3. **Estructura Semántica de Entradas**:
   - Cada entrada sigue una estructura estricta con 8 secciones obligatorias:
     1. Resumen (2-4 líneas)
     2. Concepto de Hardware (explicación educativa)
     3. Implementación (qué se hizo y por qué)
     4. Archivos Afectados (lista con rutas)
     5. Tests y Verificación (pytest/logs/ROMs de test)
     6. Fuentes Consultadas (referencias técnicas)
     7. Integridad Educativa (qué entiendo / qué falta / hipótesis)
     8. Próximos Pasos (checklist)

4. **Características Implementadas**:
   - Sin dependencias externas: funciona completamente offline
   - Links relativos correctos para navegación sin servidor
   - Aviso clean-room visible en todas las páginas
   - HTML5 semántico (header, nav, main, section, footer)
   - Navegación entre entradas (Anterior/Siguiente)

### Archivos Afectados:
- `docs/bitacora/assets/style.css` (nuevo, 512 líneas)
- `docs/bitacora/_entry_template.html` (nuevo, 168 líneas)
- `docs/bitacora/index.html` (nuevo, 116 líneas)
- `docs/bitacora/entries/2025-12-16__0000__bootstrap.html` (nuevo, 243 líneas)
- `INFORME_COMPLETO.md` (este archivo)

### Cómo se Validó:
- Verificación HTML: Estructura HTML5 válida y semántica
- Links relativos: Todos los enlaces funcionan correctamente desde cualquier ubicación
- CSS: Estilos aplicados correctamente, variables CSS funcionando
- Modo oscuro: Soporte automático verificado mediante `prefers-color-scheme: dark`
- Portabilidad: Archivos abren correctamente offline en navegadores modernos (Chrome, Firefox, Safari)
- Responsive: Diseño adaptativo verificado con diferentes anchos de pantalla
- Aviso clean-room: Visible en todas las páginas creadas

### Fuentes Consultadas:
- MDN Web Docs - CSS Variables: https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties
- MDN Web Docs - prefers-color-scheme: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme
- HTML5 Semántico: Conocimiento general de estándares web

### Lo que Entiendo Ahora:
- **CSS Variables**: Permiten crear temas fácilmente cambiando valores en `:root` y usando media queries para modo oscuro
- **HTML Semántico**: La estructura semántica mejora la accesibilidad y mantenibilidad del código
- **Links Relativos**: Permiten que la bitácora funcione completamente offline sin necesidad de servidor
- **System Fonts**: Usar `system-ui` garantiza buen rendimiento y apariencia nativa sin cargar fuentes externas
- **Documentación Educativa**: La estructura estricta de entradas fuerza a documentar aspectos clave (integridad educativa, fuentes, tests)

### Lo que Falta Confirmar:
- La estructura de secciones será validada con uso real en próximas entradas de implementación de hardware
- Si es necesario, se pueden añadir más componentes CSS según necesidades futuras
- La plantilla puede necesitar ajustes una vez se documenten implementaciones de hardware reales

---

## 2024-12-19 - Inicio del Proyecto

### Configuración Inicial

Se ha configurado la estructura inicial del proyecto "Viboy Color", un emulador de Game Boy Color escrito en Python.

#### Tareas Completadas:

1. **Inicialización de Git**: Se ha inicializado un repositorio Git en la carpeta del proyecto para control de versiones.

2. **Archivo .gitignore**: Se ha creado un archivo `.gitignore` robusto que incluye:
   - Exclusiones estándar de Python (__pycache__, *.pyc, etc.)
   - Entornos virtuales (.venv, venv/, etc.)
   - Archivos del sistema operativo (.DS_Store para macOS, Thumbs.db para Windows)
   - Archivos de IDEs (.idea/, .vscode/)
   - Archivos temporales y logs
   - ROMs de Game Boy (*.gb, *.gbc) para evitar incluir contenido con derechos de autor

3. **Estructura de Directorios**: Se ha creado la siguiente estructura:
   - `src/`: Carpeta principal del código fuente
   - `src/cpu/`: Para la lógica del procesador (CPU Z80 modificado)
   - `src/memory/`: Para la gestión de memoria (MMU - Memory Management Unit)
   - `src/gpu/`: Para el renderizado gráfico (GPU)
   - `tests/`: Para los tests unitarios
   - `docs/`: Para documentación adicional

4. **Gestión de Dependencias**: Se ha creado el archivo `requirements.txt` con las siguientes dependencias:
   - `pygame-ce>=2.3.0`: Biblioteca para el renderizado gráfico y manejo de entrada
   - `pytest>=7.4.0`: Framework para tests unitarios
   - `pytest-cov>=4.1.0`: Plugin para cobertura de código en tests

5. **Documentación**:
   - `README.md`: Contiene título del proyecto, descripción, instrucciones de instalación y estructura del proyecto
   - `INFORME_COMPLETO.md`: Este archivo, que servirá como bitácora del proyecto

6. **Script de Entrada**: Se ha creado `main.py` en la raíz del proyecto con un mensaje de inicio básico para verificación.

### Próximos Pasos

- Implementación de la CPU (procesador Z80 modificado)
- Desarrollo del sistema de memoria (MMU)
- Implementación de la GPU para renderizado
- Sistema de carga de ROMs
- Tests unitarios básicos

---

## 2025-12-16 - Configuración del Entorno de Desarrollo y Repositorio Remoto

### Configuración del Entorno Virtual y Dependencias

Se ha configurado el entorno de desarrollo profesional del proyecto ViboyColor.

#### Tareas Completadas:

1. **Entorno Virtual Python**:
   - Creado entorno virtual en `.venv/` usando `python3 -m venv .venv`
   - Comando de activación para macOS/Linux: `source .venv/bin/activate`
   - Actualizado `pip` a la versión más reciente (25.3)

2. **Instalación de Dependencias**:
   - Instaladas todas las dependencias de `requirements.txt`:
     - `pygame-ce 2.5.6` (SDL 2.32.10) - Verificado importación correcta
     - `pytest 8.4.2` - Framework de testing funcional
     - `pytest-cov 7.0.0` - Plugin para cobertura de código
   - Todas las dependencias instaladas sin errores

3. **Verificación del Entorno**:
   - ✅ `pygame-ce` se importa correctamente (versión 2.5.6)
   - ✅ `main.py` ejecuta sin errores
   - ✅ `pytest` funciona correctamente (recolector de tests operativo, 0 tests encontrados como esperado)

4. **Control de Versiones**:
   - Commit inicial realizado: `chore: configuración inicial del proyecto ViboyColor`
   - Archivos incluidos: `.gitignore`, `README.md`, `requirements.txt`, `main.py`, `INFORME_COMPLETO.md`

#### Configuración de GitHub

5. **Repositorio Remoto Configurado**:
   - Repositorio creado en GitHub: `https://github.com/Caprini/ViboyColor`
   - Remoto `origin` configurado y vinculado correctamente
   - Push inicial completado exitosamente
   - Rama `main` configurada como rama de seguimiento
   - Commit inicial (`2506a18`) subido al repositorio remoto

**Nota de Seguridad**: El token de acceso personal (PAT) está actualmente en la configuración del remoto. Se recomienda configurar autenticación SSH o usar Git Credential Helper para mayor seguridad en futuras operaciones.

#### Archivos Afectados:
- `.venv/` (nuevo, excluido de Git por .gitignore)
- `requirements.txt` (verificado)
- `main.py` (verificado)
- `INFORME_COMPLETO.md` (este archivo)

#### Cómo se Validó:
- Ejecución exitosa de `python -c "import pygame"` sin errores
- Ejecución de `main.py` sin errores
- Ejecución de `pytest --version` y `pytest` (recolector funcional)
- Verificación de instalación de dependencias con `pip list`

---

## 2025-12-16 - Implementación de los Registros de la CPU (LR35902)

### Conceptos Hardware Implementados

**Registros de la CPU LR35902**: La Game Boy utiliza una CPU híbrida basada en arquitectura Z80/8080. La peculiaridad principal es que tiene registros de 8 bits que pueden combinarse en pares virtuales de 16 bits para direccionamiento y operaciones aritméticas.

**Registros de 8 bits**:
- **A** (Acumulador): Registro principal para operaciones aritméticas y lógicas
- **B, C, D, E, H, L**: Registros de propósito general
- **F** (Flags): Registro de estado con peculiaridad hardware: los 4 bits bajos siempre son 0

**Pares virtuales de 16 bits**:
- **AF**: A (byte alto) + F (byte bajo, pero solo bits 4-7 válidos)
- **BC**: B (byte alto) + C (byte bajo)
- **DE**: D (byte alto) + E (byte bajo)
- **HL**: H (byte alto) + L (byte bajo) - usado frecuentemente para direccionamiento indirecto

**Registros de 16 bits**:
- **PC** (Program Counter): Contador de programa, apunta a la siguiente instrucción
- **SP** (Stack Pointer): Puntero de pila para llamadas a subrutinas y manejo de interrupciones

**Flags del registro F**:
- **Bit 7 (Z - Zero)**: Se activa cuando el resultado de una operación es cero
- **Bit 6 (N - Subtract)**: Indica si la última operación fue una resta
- **Bit 5 (H - Half Carry)**: Indica carry del bit 3 al 4 (nibble bajo)
- **Bit 4 (C - Carry)**: Indica carry del bit 7 (overflow en suma o borrow en resta)

#### Tareas Completadas:

1. **Clase `Registers` (`src/cpu/registers.py`)**:
   - Implementación completa de todos los registros de 8 bits (A, B, C, D, E, H, L, F)
   - Implementación de registros de 16 bits (PC, SP)
   - Métodos getters/setters para todos los registros individuales
   - Métodos para pares virtuales de 16 bits (get_af, set_af, get_bc, set_bc, etc.)
   - Wrap-around automático usando máscaras bitwise (`& 0xFF` para 8 bits, `& 0xFFFF` para 16 bits)
   - **Peculiaridad hardware implementada**: Registro F con máscara `0xF0` (bits bajos siempre 0)
   - Helpers para flags: `set_flag()`, `clear_flag()`, `check_flag()`, y métodos individuales (`get_flag_z()`, etc.)
   - Documentación educativa extensa en docstrings explicando cada componente

2. **Tests Unitarios (`tests/test_registers.py`)**:
   - **Test 1**: Verificación de wrap-around en registros de 8 bits (256 → 0, valores negativos)
   - **Test 2**: Verificación de lectura/escritura de pares de 16 bits (BC, DE, HL, AF)
   - **Test 3**: Verificación de que el registro F ignora los 4 bits bajos
   - **Test 4**: Verificación completa de helpers de flags (set, clear, check)
   - Tests adicionales para PC, SP, e inicialización
   - **15 tests en total, todos pasando ✅**

3. **Estructura de Paquetes**:
   - Creados `__init__.py` en `src/cpu/` y `tests/` para paquetes Python válidos

#### Archivos Afectados:
- `src/cpu/__init__.py` (nuevo)
- `src/cpu/registers.py` (nuevo, 361 líneas)
- `tests/__init__.py` (nuevo)
- `tests/test_registers.py` (nuevo, 321 líneas)
- `INFORME_COMPLETO.md` (este archivo)

#### Cómo se Validó:
- Ejecución de `pytest tests/test_registers.py -v`: **15 tests pasando**
- Verificación de wrap-around en registros de 8 y 16 bits
- Verificación de máscara de flags (F solo bits altos válidos)
- Verificación de operaciones bitwise en pares de 16 bits
- Sin errores de linting (verificado con read_lints)

#### Lo que Entiendo Ahora:
- Los registros de 8 bits se combinan usando operaciones bitwise: `(byte_alto << 8) | byte_bajo`
- La separación se hace con `(valor >> 8) & 0xFF` (byte alto) y `valor & 0xFF` (byte bajo)
- El hardware real de la Game Boy fuerza los bits bajos de F a 0, no es una convención de software
- El wrap-around es crítico para simular el comportamiento del hardware correctamente

#### Lo que Falta Confirmar:
- Valores iniciales exactos de los registros al inicio del boot (pendiente de verificar con documentación)
- Comportamiento específico de flags en operaciones aritméticas complejas (se implementará con la ALU)

---

### 2025-12-16 — Implementación de la ALU y Gestión de Flags (Step 0004)

#### Resumen:
Implementación de la ALU (Unidad Aritmética Lógica) de la CPU con gestión correcta de flags, especialmente el Half-Carry (H) que es crítico para la instrucción DAA y el manejo de números decimales en juegos. Refactorización de la CPU para usar una tabla de despacho (dispatch table) en lugar de if/elif, mejorando la escalabilidad. Implementación de los opcodes ADD A, d8 (0xC6) y SUB d8 (0xD6). Suite completa de tests TDD (5 tests) validando operaciones aritméticas y flags.

#### Concepto de Hardware:
La **ALU (Unidad Aritmética Lógica)** es el componente de la CPU responsable de realizar operaciones aritméticas (suma, resta) y lógicas. En la Game Boy, la ALU opera sobre valores de 8 bits y actualiza un conjunto de **flags** que indican el estado del resultado.

**Los Flags de la CPU LR35902:**
- **Z (Zero, bit 7):** Se activa cuando el resultado es cero
- **N (Subtract, bit 6):** Indica si la última operación fue una resta (1) o suma (0)
- **H (Half-Carry, bit 5):** Indica si hubo carry/borrow del bit 3 al 4 (nibble bajo)
- **C (Carry, bit 4):** Indica si hubo carry/borrow del bit 7 (overflow/underflow de 8 bits)

**El Half-Carry: La "Bestia Negra" de los Emuladores**

El flag **Half-Carry (H)** es especialmente crítico. Indica si hubo un "carry" (en suma) o "borrow" (en resta) entre el nibble bajo (bits 0-3) y el nibble alto (bits 4-7).

**¿Por qué es importante?** La instrucción `DAA (Decimal Adjust Accumulator)` utiliza el flag H para convertir números binarios a BCD (Binary Coded Decimal). Sin H correcto, los números decimales en juegos (puntuaciones, vidas, contadores) se mostrarán corruptos.

**Fórmulas:**
- **Suma:** H = 1 si `(A & 0xF) + (value & 0xF) > 0xF`
- **Resta:** H = 1 si `(A & 0xF) < (value & 0xF)`

**Ejemplo:** Sumar 15 (0x0F) + 1 (0x01) = 16 (0x10). El nibble bajo pasa de 0xF a 0x0 con carry al nibble alto. H se activa porque `0xF + 0x1 = 0x10` (excede 0xF).

#### Implementación:

1. **Refactorización a Tabla de Despacho (`src/cpu/core.py`)**:
   - Reemplazado el sistema if/elif por un diccionario `_opcode_table` que mapea opcodes a funciones manejadoras
   - Compatible con Python 3.9+ (no requiere match/case de Python 3.10+)
   - Cada opcode tiene su propia función handler (ej: `_op_nop()`, `_op_add_a_d8()`, `_op_sub_d8()`)
   - Mejora la escalabilidad: añadir nuevos opcodes es tan simple como añadir una entrada al diccionario

2. **Helpers ALU (`_add()` y `_sub()`)**:
   - **`_add(value)`**: Suma un valor al registro A y actualiza flags Z, N, H, C
     - Fórmula H: `(A & 0xF) + (value & 0xF) > 0xF`
     - Fórmula C: `(A + value) > 0xFF`
   - **`_sub(value)`**: Resta un valor del registro A y actualiza flags Z, N, H, C
     - Fórmula H: `(A & 0xF) < (value & 0xF)`
     - Fórmula C: `A < value`
   - Helpers privados y reutilizables: futuros opcodes (ADD A, B; SUB A, C; etc.) pueden reutilizarlos

3. **Opcodes Implementados**:
   - **0xC6 (ADD A, d8)**: Suma el siguiente byte de memoria al registro A. 2 M-Cycles.
   - **0xD6 (SUB d8)**: Resta el siguiente byte de memoria del registro A. 2 M-Cycles.

4. **Tests TDD (`tests/test_alu.py`)**:
   - **test_add_basic**: Suma 10 + 5 = 15, verifica flags Z=0, N=0, H=0, C=0
   - **test_add_half_carry**: Suma 15 + 1 = 16, verifica que H se activa (CRÍTICO para DAA)
   - **test_add_full_carry**: Suma 255 + 1 = 0 (wrap-around), verifica Z=1, H=1, C=1
   - **test_sub_basic**: Resta 10 - 5 = 5, verifica flags Z=0, N=1, H=0, C=0
   - **test_sub_half_carry**: Resta 16 - 1 = 15, verifica que H se activa (half-borrow)

#### Archivos Afectados:
- `src/cpu/core.py` - Refactorizado para usar tabla de despacho, implementados helpers ALU y opcodes 0xC6/0xD6
- `tests/test_alu.py` - Nuevo archivo con 5 tests TDD para validar ALU y flags
- `INFORME_COMPLETO.md` - Este archivo (entrada de bitácora)
- `docs/bitacora/entries/2025-12-16__0004__alu-flags.html` - Nueva entrada de bitácora web
- `docs/bitacora/index.html` - Actualizado con nueva entrada

#### Cómo se Validó:
- Ejecución de tests: **5 tests pasando** en `tests/test_alu.py`
- Verificación de sintaxis con `py_compile`: sin errores
- Validación de flags especialmente Half-Carry en casos críticos (15+1, 16-1)
- Tests ejecutan el ciclo completo de la CPU (fetch-decode-execute), no solo helpers ALU

#### Lo que Entiendo Ahora:
- **Half-Carry:** Es un flag que detecta overflow/underflow del nibble bajo (bits 0-3). Es crítico para DAA y el manejo de números decimales. Sin H correcto, las puntuaciones y contadores se mostrarán corruptos.
- **Tabla de despacho:** Un diccionario que mapea opcodes a funciones es más escalable que if/elif, especialmente cuando hay 256 opcodes posibles. Compatible con Python 3.9+.
- **Helpers reutilizables:** Los métodos `_add()` y `_sub()` pueden ser reutilizados por múltiples opcodes (ADD A, B; ADD A, C; SUB A, B; etc.), asegurando consistencia en la gestión de flags.
- **Fórmulas de flags:** H en suma: `(A & 0xF) + (value & 0xF) > 0xF`. H en resta: `(A & 0xF) < (value & 0xF)`. C en suma: `(A + value) > 0xFF`. C en resta: `A < value`.

#### Lo que Falta Confirmar:
- **Comportamiento de flags en operaciones con carry previo:** Cuando se implementen instrucciones ADC (Add with Carry) y SBC (Subtract with Carry), habrá que verificar cómo se combinan los flags con el carry previo.
- **Validación con ROMs de test:** Aunque los tests unitarios pasan, sería ideal validar con ROMs de test redistribuibles que prueben operaciones aritméticas y DAA.
- **Timing exacto de flags:** Los flags se actualizan inmediatamente después de la operación, pero falta verificar si hay casos edge donde el timing sea crítico.

#### Hipótesis y Suposiciones:
Las fórmulas de Half-Carry implementadas son correctas según la documentación técnica consultada (Pan Docs, manuales Z80/8080). Sin embargo, no he podido verificar directamente con hardware real o ROMs de test comerciales. La implementación se basa en documentación técnica estándar, tests unitarios que validan casos conocidos, y lógica matemática del comportamiento esperado.

**Plan de validación futura:** Cuando se implemente DAA, si los números decimales se muestran correctamente en juegos, confirmará que H está bien implementado. Si hay corrupción, habrá que revisar las fórmulas.

---

