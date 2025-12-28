# Análisis del Step 0293 - Verificación de Flujo Post-Limpieza

**Fecha**: 2025-12-25  
**Step ID**: 0293  
**Objetivo**: Analizar los logs generados por los cinco monitores de rastreo para identificar el flujo de ejecución después de limpiar VRAM y determinar por qué no se cargan tiles.

---

## Resumen Ejecutivo

El análisis de los monitores implementados en el Step 0293 revela que **después de limpiar VRAM, el código nunca carga datos de tiles en VRAM**. En su lugar, el código ejecuta rutinas que copian datos a WRAM (0xC300-0xC3FF) y otras áreas, pero **nunca apunta HL a VRAM (0x8000-0x97FF)** para cargar tiles.

**Causa Raíz Identificada**: El código que debería cargar tiles en VRAM **no se ejecuta** o **no existe en el flujo post-limpieza**. El juego limpia VRAM y luego copia datos a WRAM, pero no hay código que cargue tiles gráficos en VRAM.

---

## Análisis por Monitor

### 1. [PC-TRACE] - Flujo de Ejecución

**Total de entradas**: 488

**Hallazgos Clave**:

1. **Rutina de Limpieza (0x36E0-0x36E7)**:
   - Se ejecuta 155 veces (confirmado por CLEANUP-TRACE)
   - Limpia VRAM escribiendo 0x00 desde 0x8000 usando BC como contador (2000 iteraciones = 8KB)
   - Banco ROM: 1 (correcto)

2. **Flujo Post-Limpieza**:
   - **PC:0x1F91** → `CALL 0x36E0` (llama a rutina de limpieza)
   - **PC:0x1F94** → `CALL 0x0082` (llama a rutina en HRAM)
   - **PC:0x0082-0x008A** → Bucle activo que copia datos a **WRAM (0xC300-0xC3FF)**
     - Opcodes: `LD (HL+), A | DEC BC | JR NZ`
     - HL apunta a 0xC300-0xC3FF (WRAM, NO VRAM)
     - BC se usa como contador (decrece desde 0xA000)

3. **Otras Rutinas Detectadas**:
   - **PC:0x4BF4-0x4BF5**: Copia datos (HL apunta a 0x4BFB-0x4C00, probablemente ROM)
   - **PC:0x5A8C**: Bucle de copia (HL apunta a 0xC008-0xC03A, WRAM)

4. **⚠️ CRÍTICO**: No se detectan ejecuciones de código que:
   - Apunten HL a VRAM (0x8000-0x97FF)
   - Carguen datos de tiles desde ROM a VRAM
   - Configuren el tilemap después de la limpieza

**Conclusión**: El código que debería cargar tiles en VRAM **no se ejecuta** en el flujo post-limpieza. El juego limpia VRAM y luego copia datos a WRAM, pero nunca carga tiles gráficos.

---

### 2. [REG-TRACE] - Cambios de Registros

**Total de entradas**: 100

**Hallazgos Clave**:

1. **Valores de HL después de la limpieza**:
   - **0xC300-0xC3FF** (WRAM): Múltiples trazas muestran HL apuntando a WRAM
   - **0x4BFB-0x4C00** (ROM): HL apunta a área de ROM durante copia
   - **0xA000** (Cart RAM): HL apunta a Cart RAM en algunas rutinas
   - **0xC006-0xC03A** (WRAM): HL apunta a diferentes áreas de WRAM

2. **⚠️ CRÍTICO**: **NUNCA se detecta HL apuntando a VRAM (0x8000-0x97FF)** después de la limpieza.

3. **Patrones de uso de BC/DE**:
   - BC se usa como contador en bucles de copia (decrece desde valores altos)
   - DE se mantiene en 0x00D8 o 0xA000 (no se usa como fuente de datos)

4. **Flags**:
   - Z flag cambia según resultados de comparaciones
   - N flag se establece durante operaciones de resta (DEC BC)
   - No hay flags que impidan saltos condicionales de manera anormal

**Conclusión**: Los registros muestran que el código copia datos a WRAM, pero **nunca apunta HL a VRAM** para cargar tiles. Esto confirma que el código de carga de tiles no se ejecuta.

---

### 3. [JUMP-TRACE] - Rutas de Ejecución

**Total de entradas**: 8,521

**Destinos más frecuentes**:

| Destino | Frecuencia | Descripción |
|---------|------------|-------------|
| **0x36E2** | 8,319 | Bucle de limpieza de VRAM (JR NZ loop) |
| **0x0088** | 160 | Bucle de copia a WRAM (JR NZ loop) |
| **0x1CF9** | 23 | Rutina desconocida |
| **0x4BF4** | 10 | Rutina de copia |
| **0x0000** | 4 | Reset (probablemente error) |
| **0x36E0** | 1 | Inicio de rutina de limpieza |
| **0x1CF5** | 1 | Rutina desconocida |
| **0x1CF0** | 1 | Rutina desconocida |
| **0x0082** | 1 | Inicio de rutina en HRAM |
| **0x4BED** | 1 | Rutina desconocida |

**Hallazgos Clave**:

1. **Bucle de Limpieza (0x36E2)**: 8,319 saltos
   - Confirma que la rutina de limpieza se ejecuta muchas veces
   - El bucle salta de 0x36E7 a 0x36E2 mientras BC != 0

2. **Bucle de Copia a WRAM (0x0088)**: 160 saltos
   - Confirma que el código copia datos a WRAM después de la limpieza
   - El bucle salta de 0x008A a 0x0088 mientras BC != 0

3. **⚠️ CRÍTICO**: **No hay saltos a rutinas que carguen tiles en VRAM**.
   - No se detectan saltos a direcciones que podrían ser rutinas de carga de tiles
   - No se detectan CALLs a rutinas de inicialización gráfica

4. **Rutinas Desconocidas**:
   - 0x1CF9, 0x1CF5, 0x1CF0: Rutinas que se ejecutan pero no están relacionadas con carga de tiles
   - 0x4BF4, 0x4BED: Rutinas de copia que no apuntan a VRAM

**Conclusión**: Los saltos confirman que el código ejecuta bucles de limpieza y copia a WRAM, pero **nunca salta a rutinas que carguen tiles en VRAM**.

---

### 4. [BANK-CHANGE] - Cambios de Banco ROM

**Total de entradas**: 2

**Hallazgos**:

1. **Cambios detectados**:
   - Banco 1 → Banco 19 (en PC:0x3E7A)
   - Banco 19 → Banco 28 (en PC:0x3E85)

2. **Timing**: Estos cambios ocurren **mucho después** de la limpieza de VRAM (líneas 11342 y 11346 del log, mientras que la limpieza ocurre en las primeras líneas).

3. **⚠️ CRÍTICO**: El banco ROM correcto (Banco 1) está activo durante la limpieza y el flujo post-limpieza. Los cambios de banco ocurren después, cuando el código ya debería haber cargado tiles.

**Conclusión**: El banco ROM no es el problema. El banco correcto está activo durante la limpieza y el flujo post-limpieza.

---

### 5. [HARDWARE-STATE] - Estado de Hardware

**Total de entradas**: 100

**Hallazgos Clave**:

1. **LCDC (0xFF40)**: `0x80`
   - Bit 7 (LCD Enable): **1** (LCD ON) ✅
   - Bit 0 (BG Display): **0** (BG Display OFF) ⚠️
   - **CRÍTICO**: El Background Display está **DESHABILITADO**

2. **BGP (0xFF47)**: `0xE4`
   - Valor válido (no 0x00) ✅
   - Paleta de colores configurada correctamente

3. **IE (0xFFFF)**: `0x00`
   - **TODAS las interrupciones están DESHABILITADAS** ⚠️
   - Esto significa que las ISR (Interrupt Service Routines) no se ejecutan

4. **IME (Interrupt Master Enable)**: `0`
   - Interrupciones deshabilitadas a nivel de CPU ⚠️

5. **IF (0xFF0F)**: `0x01`
   - V-Blank pendiente (bit 0 = 1)
   - Pero no se procesa porque IE=0 e IME=0

6. **LY (0xFF44)**: Avanza correctamente (43, 44, 45, 46, 47, 48, 49, 50, 51, 52...)
   - El contador de líneas funciona correctamente ✅

**Conclusión**: El estado de hardware muestra que:
- ✅ LCD está habilitado
- ✅ BGP está configurado
- ✅ LY avanza correctamente
- ⚠️ **BG Display está DESHABILITADO** (LCDC bit 0 = 0)
- ⚠️ **TODAS las interrupciones están DESHABILITADAS** (IE=0, IME=0)

**Implicación**: Si el BG Display está deshabilitado, el juego podría no cargar tiles porque no los necesita todavía. Sin embargo, esto no explica por qué no se cargan tiles cuando se debería.

---

## Síntesis y Evaluación de Hipótesis

### Hipótesis A: Código existe pero no se ejecuta por condiciones no cumplidas
**Estado**: ✅ **CONFIRMADA PARCIALMENTE**

**Evidencia**:
- El código de carga de tiles podría existir pero no ejecutarse porque:
  - BG Display está deshabilitado (LCDC bit 0 = 0)
  - Las interrupciones están deshabilitadas (IE=0, IME=0)
  - El juego podría esperar un estado específico antes de cargar tiles

**Conclusión**: Es posible que el código de carga de tiles exista pero no se ejecute porque las condiciones no se cumplen (BG Display OFF, interrupciones deshabilitadas).

---

### Hipótesis B: Código está en otro banco ROM
**Estado**: ❌ **RECHAZADA**

**Evidencia**:
- El banco ROM correcto (Banco 1) está activo durante la limpieza y el flujo post-limpieza
- Los cambios de banco ocurren mucho después de la limpieza
- No hay evidencia de que el código de carga de tiles esté en otro banco

**Conclusión**: El banco ROM no es el problema.

---

### Hipótesis C: Juego espera estado específico
**Estado**: ✅ **CONFIRMADA**

**Evidencia**:
- BG Display está deshabilitado (LCDC bit 0 = 0)
- Todas las interrupciones están deshabilitadas (IE=0, IME=0)
- El juego podría esperar que se habilite BG Display o que se procesen interrupciones antes de cargar tiles

**Conclusión**: El juego probablemente espera un estado específico (BG Display habilitado, interrupciones habilitadas) antes de cargar tiles.

---

### Hipótesis D: Bug en emulación
**Estado**: ❓ **INCONCLUSA**

**Evidencia**:
- El código ejecuta correctamente (bucles, saltos, copias a WRAM)
- Los registros se actualizan correctamente
- El hardware funciona (LY avanza, LCDC se lee correctamente)
- No hay evidencia de bugs obvios en la emulación

**Conclusión**: No hay evidencia clara de bugs en la emulación, pero no se puede descartar completamente.

---

## Causa Raíz Identificada

**Causa Raíz Más Probable**: **El código de carga de tiles no se ejecuta porque el juego espera condiciones específicas que no se cumplen**:

1. **BG Display está deshabilitado** (LCDC bit 0 = 0)
   - El juego podría no cargar tiles hasta que se habilite BG Display
   - La carga de tiles podría ocurrir en una ISR de V-Blank que no se ejecuta porque IE=0 e IME=0

2. **Interrupciones deshabilitadas** (IE=0, IME=0)
   - Muchos juegos cargan tiles durante V-Blank usando ISRs
   - Si las interrupciones están deshabilitadas, las ISRs no se ejecutan
   - El código de carga de tiles podría estar en una ISR que nunca se ejecuta

3. **Flujo de ejecución post-limpieza**
   - Después de limpiar VRAM, el código copia datos a WRAM (0xC300-0xC3FF)
   - No hay código que cargue tiles en VRAM en el flujo inmediato post-limpieza
   - El código de carga de tiles podría ejecutarse más tarde, cuando se cumplan las condiciones

---

## Recomendaciones de Correcciones

### Corrección 1: Habilitar BG Display
**Acción**: Verificar si el juego habilita BG Display después de la limpieza y asegurar que se habilite correctamente.

**Implementación**:
- Buscar escrituras a LCDC (0xFF40) que habiliten BG Display (bit 0 = 1)
- Verificar que el juego escriba 0x91 o similar a LCDC después de la limpieza
- Si el juego no habilita BG Display, investigar por qué

### Corrección 2: Habilitar Interrupciones
**Acción**: Verificar si el juego habilita interrupciones después de la limpieza y asegurar que se habiliten correctamente.

**Implementación**:
- Buscar escrituras a IE (0xFFFF) que habiliten interrupciones
- Buscar instrucciones EI que habiliten IME
- Verificar que el juego habilite interrupciones después de la limpieza
- Si el juego no habilita interrupciones, investigar por qué

### Corrección 3: Investigar Rutinas de Carga de Tiles
**Acción**: Buscar en el código del juego rutinas que carguen tiles en VRAM.

**Implementación**:
- Desensamblar el código en bancos ROM relevantes
- Buscar rutinas que:
  - Apunten HL a VRAM (0x8000-0x97FF)
  - Copien datos desde ROM a VRAM
  - Se ejecuten durante V-Blank o después de habilitar BG Display
- Verificar si estas rutinas se llaman desde ISRs o desde el flujo principal

### Corrección 4: Rastrear Escrituras a LCDC
**Acción**: Implementar un monitor que rastree todas las escrituras a LCDC para ver cuándo se habilita BG Display.

**Implementación**:
- Agregar monitor `[LCDC-WRITE]` que detecte escrituras a 0xFF40
- Rastrear el valor escrito y el PC desde donde se escribe
- Verificar si el juego escribe 0x91 o similar después de la limpieza

### Corrección 5: Rastrear Habilitación de Interrupciones
**Acción**: Implementar un monitor que rastree habilitación de interrupciones (IE y IME).

**Implementación**:
- Agregar monitor `[IE-WRITE]` que detecte escrituras a 0xFFFF (ya existe, verificar que funcione)
- Agregar monitor `[EI-TRACE]` que detecte instrucciones EI
- Verificar si el juego habilita interrupciones después de la limpieza

---

## Próximos Pasos

1. **Implementar monitores adicionales**:
   - `[LCDC-WRITE]`: Rastrear escrituras a LCDC
   - `[EI-TRACE]`: Rastrear instrucciones EI
   - Verificar que `[IE-WRITE]` funcione correctamente

2. **Ejecutar el emulador con los nuevos monitores**:
   - Generar nuevo log con monitores adicionales
   - Analizar cuándo se habilita BG Display
   - Analizar cuándo se habilitan interrupciones

3. **Desensamblar código relevante**:
   - Buscar rutinas de carga de tiles en bancos ROM
   - Verificar si estas rutinas se llaman desde ISRs
   - Verificar si estas rutinas se ejecutan después de habilitar BG Display

4. **Verificar flujo completo**:
   - Confirmar que el juego habilita BG Display
   - Confirmar que el juego habilita interrupciones
   - Confirmar que el código de carga de tiles se ejecuta después de habilitar BG Display

---

## Archivos Generados

- `ANALISIS_STEP_0293_VERIFICACION.md` (este documento)
- `analisis_pc_trace.txt` (muestra de 200 líneas de PC-TRACE)
- `analisis_reg_trace.txt` (muestra de 100 líneas de REG-TRACE)
- `analisis_jump_trace.txt` (muestra de 100 líneas de JUMP-TRACE)
- `analisis_hardware_state.txt` (muestra de 100 líneas de HARDWARE-STATE)

---

## Referencias

- **Pan Docs**: "Video RAM (VRAM)", "LCD Control Register (LCDC)", "CPU Registers", "Interrupts"
- **Step 0291**: Análisis previo que confirmó que solo se detectan escrituras de limpieza (0x00) desde PC:0x36E3
- **Step 0293**: Implementación de los cinco monitores de diagnóstico

---

**Análisis completado**: 2025-12-25  
**Próximo Step**: 0294 - Implementar monitores adicionales y verificar habilitación de BG Display e interrupciones

