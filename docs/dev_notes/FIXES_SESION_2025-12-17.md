# Fixes y Mejoras - Sesión 2025-12-17

Este documento registra todos los fixes, mejoras y cambios realizados durante esta sesión de desarrollo.
Posteriormente, estos cambios se documentarán correctamente en las bitácoras correspondientes.

---

## Fix 001: Forzar Renderizado con LCDC=0x80 e Implementar Scroll (SCX/SCY)

**Fecha**: 2025-12-17  
**Step ID**: 0033  
**Estado**: ✅ Implementado y Testeado

### Problema Identificado
- Tetris DX escribe `LCDC=0x80` (Bit 7=1 LCD ON, Bit 0=0 BG OFF)
- En Game Boy Clásica (DMG), Bit 0=0 apaga el fondo → pantalla blanca
- En Game Boy Color (CGB), Bit 0 no apaga el fondo, sino que cambia prioridad de sprites
- Tetris DX es un juego CGB/dual que espera comportamiento CGB
- Nuestro emulador actúa como DMG estricta → pantalla blanca

### Solución Implementada

#### 1. Hack Educativo: Ignorar Bit 0 de LCDC
- **Archivo**: `src/gpu/renderer.py`
- **Cambio**: Comentada la verificación del Bit 0 de LCDC en `render_frame()`
- **Comportamiento**: Si Bit 7 (LCD Enable) está activo, el fondo se dibuja siempre, independientemente del Bit 0
- **Documentación**: Añadido comentario extenso explicando que es un hack temporal y educativo
- **Nota**: El código original queda comentado para referencia futura

#### 2. Implementación de Scroll (SCX/SCY)
- **Archivo**: `src/gpu/renderer.py`
- **Cambio**: Renderizado cambiado de tile a tile a píxel a píxel
- **Funcionalidad**:
  - Lectura de SCX (0xFF43) y SCY (0xFF42) desde la MMU
  - Cálculo de posición en tilemap: `map_pixel = (screen_pixel + scroll) % 256`
  - Wrap-around correcto (módulo 256)
  - Decodificación píxel a píxel de los tiles
- **Razón del cambio**: El renderizado píxel a píxel permite implementar scroll correctamente cuando el desplazamiento no es múltiplo de 8

### Tests Implementados
- **Archivo**: `tests/test_gpu_scroll.py` (nuevo)
- **Tests creados** (5 tests, todos pasando):
  1. `test_scroll_x`: Scroll horizontal (SCX)
  2. `test_scroll_y`: Scroll vertical (SCY)
  3. `test_scroll_wrap_around`: Wrap-around del scroll (módulo 256)
  4. `test_force_bg_render_lcdc_0x80`: Renderizado forzado con LCDC=0x80 (hack educativo)
  5. `test_scroll_zero`: Renderizado sin scroll (SCX=0, SCY=0)

**Resultado de tests**: ✅ 5 passed in 11.81s

### Archivos Modificados
- `src/gpu/renderer.py` - Modificado `render_frame()`
- `tests/test_gpu_scroll.py` - Nuevo archivo con tests
- `docs/bitacora/entries/2025-12-17__0033__forzar-renderizado-scroll.html` - Nueva entrada de bitácora
- `docs/bitacora/index.html` - Actualizado con nueva entrada
- `docs/bitacora/entries/2025-12-17__0032__diagnostico-opcodes-condicionales-lcdc.html` - Actualizado link "Siguiente"
- `INFORME_COMPLETO.md` - Añadida nueva entrada

### Validación Realizada
- [x] Probar Tetris DX con el hack del Bit 0
  - **Resultado**: El hack funciona correctamente - se dibujan 23040 píxeles cuando LCDC=0x80
  - **Problema encontrado**: BGP=0x00 hace que todos los píxeles sean blancos (paleta completamente blanca)
  - **Observación**: El juego escribe `BGP=0x00` intencionalmente, lo cual es válido pero hace que no se vean gráficos
  - **Log relevante**: `WARNING: BGP=0x00: Paleta completamente blanca - pantalla aparecerá toda blanca`
- [ ] Verificar que el scroll funciona correctamente en el juego (animaciones, desplazamiento de fondo)

### Notas Técnicas
- El hack del Bit 0 es temporal y educativo. En el futuro, cuando se implemente modo CGB completo, el Bit 0 deberá funcionar correctamente según la especificación CGB.
- El renderizado píxel a píxel es más lento pero más correcto y flexible. Se podría optimizar renderizando por tiles cuando el scroll es múltiplo de 8, pero por ahora la implementación píxel a píxel es más clara.

### Fuentes Consultadas
- Pan Docs: LCD Control Register (LCDC) - https://gbdev.io/pandocs/LCDC.html
- Pan Docs: Scrolling - https://gbdev.io/pandocs/Scrolling.html
- Pan Docs: Game Boy Color Registers - https://gbdev.io/pandocs/CGB_Registers.html

---

## Próximos Fixes (Pendientes)

### Fix 002: Implementar RETI (Return from Interrupt) - Opcode 0xD9
**Estado**: ✅ Implementado y Testeado

### Problema Identificado
- Tetris DX se crasheaba con: `ERROR: Opcode no implementado: Opcode 0xD9 no implementado en PC=0x02A9`
- Opcode 0xD9 es **RETI** (Return from Interrupt)
- RETI es esencial para que las rutinas de interrupción puedan retornar correctamente
- Sin RETI, el juego no puede salir de las rutinas de interrupción y se queda atascado

### Solución Implementada
- **Archivo**: `src/cpu/core.py`
- **Cambio**: Añadido opcode 0xD9 al dispatch table e implementado `_op_reti()`
- **Comportamiento**: RETI es igual que RET pero además reactiva IME (Interrupt Master Enable)
- **Timing**: 4 M-Cycles (igual que RET)
- **Implementación**:
  - POP dirección de retorno de la pila
  - Saltar a esa dirección (PC = dirección de retorno)
  - Reactivar IME (IME = True)

### Tests Implementados
- **Archivo**: `tests/test_cpu_interrupts.py`
- **Test creado**: `test_reti_reactivates_ime`
  - Verifica que RETI hace POP correctamente
  - Verifica que RETI salta a la dirección de retorno
  - Verifica que RETI reactiva IME (diferencia clave con RET)
  - Verifica que consume 4 M-Cycles

**Resultado de test**: ✅ 1 passed in 0.24s

### Archivos Modificados
- `src/cpu/core.py` - Añadido `_op_reti()` y registrado 0xD9 en dispatch table
- `tests/test_cpu_interrupts.py` - Añadido test `test_reti_reactivates_ime`

---

### Fix 004: Implementar LD A, (DE) - Opcode 0x1A
**Estado**: ✅ Implementado y Testeado

### Problema Identificado
- Tetris DX se crasheaba con: `ERROR: Opcode no implementado: Opcode 0x1A no implementado en PC=0x4380`
- Opcode 0x1A es **LD A, (DE)** (Load from memory address pointed by DE into A)
- Es el gemelo de LD (DE), A (0x12): mientras que 0x12 escribe A en memoria, 0x1A lee de memoria y lo guarda en A

### Solución Implementada
- **Archivo**: `src/cpu/core.py`
- **Cambio**: Añadido opcode 0x1A al dispatch table e implementado `_op_ld_a_de_ptr()`
- **Comportamiento**: Lee un byte de la dirección apuntada por DE y lo carga en A
- **Timing**: 2 M-Cycles (fetch opcode + read from memory)
- **Implementación**:
  - Obtener dirección de DE
  - Leer byte de memoria en esa dirección
  - Cargar valor en A
  - DE no se modifica

### Tests Implementados
- **Archivo**: `tests/test_cpu_ld_indirect.py`
- **Test creado**: `test_ld_a_de_ptr`
  - Verifica que LD A, (DE) lee correctamente de memoria
  - Verifica que A se actualiza con el valor leído
  - Verifica que DE no se modifica
  - Verifica que consume 2 M-Cycles
- **Test adicional**: `test_ld_a_de_ptr_zero` (verifica funcionamiento con dirección 0x0000)

**Resultado de tests**: ✅ 2 passed (parte de 5 tests en total en el archivo)

### Archivos Modificados
- `src/cpu/core.py` - Añadido `_op_ld_a_de_ptr()` y registrado 0x1A en dispatch table
- `tests/test_cpu_ld_indirect.py` - Añadido test `test_ld_a_de_ptr` y `test_ld_a_de_ptr_zero`

---

### Fix 005: Implementar LD A, (HL-) - Opcode 0x3A
**Estado**: ✅ Implementado y Testeado

### Problema Identificado
- Tetris DX se crasheaba con: `ERROR: Opcode no implementado: Opcode 0x3A no implementado en PC=0x4380`
- Opcode 0x3A es **LD A, (HL-)** / **LDD A, (HL)** (Load from (HL) into A and decrement HL)
- Es el complemento de LD (HL-), A. Útil para bucles de lectura rápida hacia atrás

### Solución Implementada
- **Archivo**: `src/cpu/core.py`
- **Cambio**: Añadido opcode 0x3A al dispatch table e implementado `_op_ldd_a_hl_ptr()`
- **Comportamiento**: Lee un byte de la dirección apuntada por HL y lo carga en A, luego decrementa HL
- **Timing**: 2 M-Cycles (fetch opcode + read from memory)
- **Implementación**:
  - Obtener dirección de HL
  - Leer byte de memoria en esa dirección
  - Cargar valor en A
  - Decrementar HL (con wrap-around de 16 bits)

### Tests Implementados
- **Archivo**: `tests/test_cpu_ld_indirect.py`
- **Test creado**: `test_ld_a_hl_ptr_decrement`
  - Verifica que LD A, (HL-) lee correctamente de memoria
  - Verifica que A se actualiza con el valor leído
  - Verifica que HL se decrementa correctamente
  - Verifica que consume 2 M-Cycles

**Resultado de test**: ✅ 1 passed (parte de 5 tests en total en el archivo)

### Archivos Modificados
- `src/cpu/core.py` - Añadido `_op_ldd_a_hl_ptr()` y registrado 0x3A en dispatch table
- `tests/test_cpu_ld_indirect.py` - Añadido test `test_ld_a_hl_ptr_decrement`

---

### Fix 003: Investigar por qué BGP=0x00 (Pantalla Blanca)
**Estado**: ⏳ Pendiente de investigación

### Problema Identificado
- El juego escribe `BGP=0x00` (paleta completamente blanca)
- Aunque se dibujan 23040 píxeles correctamente, todos son blancos
- Posibles causas:
  1. El juego inicializa BGP=0x00 intencionalmente (comportamiento válido)
  2. Los tiles en VRAM están vacíos o no se han cargado aún
  3. El tilemap está vacío o apunta a tiles vacíos
  4. Falta algún paso de inicialización que carga los gráficos

### Investigación Necesaria
- Verificar qué hay en VRAM cuando se renderiza
- Verificar qué hay en el tilemap (0x9800-0x9BFF)
- Verificar si el juego carga tiles después de escribir BGP=0x00
- Comparar con comportamiento de otros emuladores (sin copiar código, solo observar comportamiento)

---

### Fix 006: Análisis Comparativo - Mario.gbc vs Tetris DX
**Estado**: ✅ Análisis completado

### Objetivo
Probar el emulador con una ROM diferente (mario.gbc) para comparar el comportamiento y validar que los fixes implementados funcionan correctamente.

### Hallazgos Principales

#### Mario.gbc - Ejecución Exitosa
- ✅ **0 errores de opcodes no implementados** (1,000,000 ciclos ejecutados)
- ✅ **LCDC se activa correctamente**: Cambia de `0x00 → 0x87` (bit 7=1, bit 0=1)
- ✅ **BGP en paleta normal**: `0xE4` (permite ver gráficos)
- ✅ **Scroll activo**: SCX=4, SCY=112
- ✅ **Juego avanza**: PC final = 0xFF87 (no se queda atascado)

#### Comparación con Tetris DX

| Aspecto | Tetris DX | Mario.gbc |
|---------|-----------|-----------|
| **Opcodes faltantes** | ❌ 0xD9, 0x1A, 0x3A | ✅ Ninguno |
| **LCDC inicial** | 0x80 (bit 7=1, bit 0=0) | 0x00 → 0x87 (bit 7=1, bit 0=1) |
| **BGP inicial** | 0x00 (todo blanco) | 0xE4 (paleta normal) |
| **Scroll** | SCX=0, SCY=0 | SCX=4, SCY=112 |
| **Estado final** | Atascado | Avanza correctamente |

### Conclusión
Mario.gbc es un **mejor caso de prueba** que Tetris DX porque:
1. No requiere opcodes adicionales (todos ya implementados)
2. Activa el LCD correctamente (ambos bits de LCDC activos)
3. Usa paleta normal (permite ver gráficos)
4. Avanza en ejecución (no se queda atascado)

**Recomendación**: Usar Mario.gbc como ROM de referencia para validar renderizado y comportamiento general, mientras que Tetris DX puede usarse para identificar opcodes faltantes.

### Archivos Creados
- `HALLAZGOS_MARIO_GBC.md` - Documento detallado con análisis completo
- `test_mario.py` - Script de prueba básico
- `test_mario_monitor.py` - Script de monitoreo de registros I/O
- `test_mario_ui.py` - Script para ejecutar con UI

### Validación Realizada
- **Comando ejecutado**: `python3 test_mario_monitor.py`
- **Entorno**: macOS (darwin 21.6.0), Python 3.9.6
- **Resultado**: ✅ 1,000,000 ciclos ejecutados sin errores
- **Cambios detectados en LCDC**: 3 cambios (0x00 → 0x87 → 0x07 → 0x87)
- **Estado final**: LCDC=0x87 (LCD y Background activos), BGP=0xE4, Scroll activo

---

## Notas Generales

- Todos los fixes deben seguir el principio clean-room (sin copiar código de otros emuladores)
- Cada fix debe incluir tests que validen el comportamiento
- Los fixes deben documentarse en este documento antes de añadirse a las bitácoras
- Mantener este documento actualizado durante la sesión

