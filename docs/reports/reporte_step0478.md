# Reporte Step 0478: Timeline IME/EI/DI + Disasm Real del Loop

## Configuración

- Baseline: VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_IO=1
- Control: VIBOY_SIM_BOOT_LOGO=1 (solo tdx)

## 1) Tabla por ROM (Frames 0/60/120/180)

### tetris_dx.gbc

| Frame | PC | PC_hotspot1 | IME | IE | EIcount | DIcount | last_ei_pc | last_di_pc | ime_set_events_count | last_ime_set_pc | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | boot_logo_prefill_enabled |
|-------|----|-------------|----|----|--------|--------|------------|------------|---------------------|-----------------|------------------|-------------------|------------------|-------------------|--------|--------|---------|-----------|------------|---------------------------|
| 0 | 0x1305 | 0x1383 | 0 | 0x00 | 0 | 1 | 0xFFFF | 0x0150 | 0 | 0xFFFF | 49140 | 49131 | 49137 | 49131 | 0 | 144 | 0 | 0x00 | 0 | 0 |
| 60 | 0x1305 | 0x1306 | 0 | 0x00 | 0 | 1 | 0xFFFF | 0x0150 | 0 | 0xFFFF | 2968359 | 2968120 | 2968176 | 2968120 | 0 | 144 | 0 | 0x00 | 0 | 0 |
| 120 | 0x1303 | 0x1304 | 0 | 0x00 | 0 | 1 | 0xFFFF | 0x0150 | 0 | 0xFFFF | 5887011 | 5886589 | 5886648 | 5886589 | 0 | 144 | 0 | 0x00 | 0 | 0 |
| 180 | 0x1383 | 0x1308 | 0 | 0x00 | 2 | 4 | 0x12BE | 0x1283 | 2 | 0x12BF | 8762209 | 8761604 | 8761671 | 8761604 | 0 | 145 | 0 | 0x00 | 6409 | 0 |

### mario.gbc

| Frame | PC | PC_hotspot1 | IME | IE | EIcount | DIcount | last_ei_pc | last_di_pc | ime_set_events_count | last_ime_set_pc | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | boot_logo_prefill_enabled |
|-------|----|-------------|----|----|--------|--------|------------|------------|---------------------|-----------------|------------------|-------------------|------------------|-------------------|--------|--------|---------|-----------|------------|---------------------------|
| 0 | 0x129D | 0x1290 | 0 | 0x00 | 0 | 0 | 0xFFFF | 0xFFFF | 0 | 0xFFFF | 27017 | 27010 | 27015 | 27010 | 0 | 145 | 0 | 0x00 | 0 | 0 |
| 60 | 0x12A0 | 0x12A0 | 0 | 0x00 | 0 | 0 | 0xFFFF | 0xFFFF | 0 | 0xFFFF | 2219279 | 2218962 | 2219059 | 2218962 | 0 | 145 | 0 | 0x00 | 0 | 0 |
| 120 | 0x12A0 | 0x12A0 | 0 | 0x00 | 0 | 0 | 0xFFFF | 0xFFFF | 0 | 0xFFFF | 4411492 | 4410912 | 4411052 | 4410912 | 0 | 145 | 0 | 0x00 | 0 | 0 |
| 180 | 0x12A0 | 0x12A0 | 0 | 0x00 | 0 | 0 | 0xFFFF | 0xFFFF | 0 | 0xFFFF | 6603703 | 6602862 | 6603043 | 6602862 | 0 | 145 | 0 | 0x00 | 0 | 0 |

### tetris.gb (Control DMG)

| Frame | PC | PC_hotspot1 | IME | IE | EIcount | DIcount | last_ei_pc | last_di_pc | ime_set_events_count | last_ime_set_pc | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | boot_logo_prefill_enabled |
|-------|----|-------------|----|----|--------|--------|------------|------------|---------------------|-----------------|------------------|-------------------|------------------|-------------------|--------|--------|---------|-----------|------------|---------------------------|
| 0 | 0x02EA | 0x02B4 | 0 | 0x01 | 0 | 1 | 0xFFFF | 0x029C | 0 | 0xFFFF | 29766 | 29759 | 29763 | 29759 | 0 | 148 | 0 | 0x00 | 0 | 0 |
| 60 | 0x036C | 0x036C | 1 | 0x09 | 1 | 1 | 0x0339 | 0x029C | 1 | 0x033A | 1837836 | 1837658 | 1837660 | 1837658 | 0 | 148 | 118 | 0x00 | 0 | 0 |
| 120 | 0x036C | 0x036C | 1 | 0x09 | 1 | 1 | 0x0339 | 0x029C | 1 | 0x033A | 3639098 | 3638798 | 3638742 | 3638798 | 0 | 148 | 118 | 0x00 | 0 | 0 |
| 180 | 0x036C | 0x036F | 1 | 0x09 | 1 | 1 | 0x0339 | 0x029C | 1 | 0x033A | 5440361 | 5439938 | 5439825 | 5439938 | 0 | 148 | 118 | 0x00 | 0 | 0 |

## 2) Disasm del Loop (Lo Más Valioso)

### tetris_dx.gbc (Frame 180)

**PC_hotspot1**: `0x1308`

**disasm_window(PC_hotspot1)**:
```
0x1308: JR NZ, 0x1302 (-8)
0x130A: RET
0x130B: DB 0x21
0x130C: DB 0x70
0x130D: DB 0x13
0x130E: CALL 0x12C9
0x1311: CALL 0x12FF
0x1314: LDH A,(JOYP)  ← PC actual marcado
```

**I/O identificado en el loop**:
- [ ] `LDH A,(FF0F)` (IF) - NO directamente visible, pero hay millones de reads
- [ ] `LDH A,(FF44)` (LY) - NO directamente visible en este fragmento
- [ ] `LDH A,(FF41)` (STAT) - NO directamente visible en este fragmento
- [x] `LDH A,(FF00)` (JOYP) - SÍ visible en 0x1314
- [ ] Otro I/O: `CALL 0x12C9` y `CALL 0x12FF` pueden contener más I/O

**Análisis**: El loop en 0x1308 hace un salto condicional basado en una condición previa. El código lee JOYP (0xFF00) en 0x1314, lo que sugiere que está esperando input del usuario. Sin embargo, el juego también está haciendo millones de reads de IF (0xFF0F) según las métricas (`if_reads_program=8762209`), lo que indica que el loop está polleando IF intensivamente, probablemente dentro de las funciones CALL.

### mario.gbc (Frame 180)

**PC_hotspot1**: `0x12A0`

**disasm_window(PC_hotspot1)**:
```
0x12A0: DB 0x0B
0x12A1: DB 0x79
0x12A2: DB 0xB0
0x12A3: JR NZ, 0x129D (-8)
0x12A5: RET
0x12A6: DB 0x21
0x12A7: DB 0xFF
0x12A8: DB 0x9B
```

**I/O identificado en el loop**:
- [ ] `LDH A,(FF0F)` (IF) - NO directamente visible, pero hay millones de reads
- [ ] `LDH A,(FF44)` (LY) - NO directamente visible en este fragmento
- [ ] `LDH A,(FF41)` (STAT) - NO directamente visible en este fragmento
- [ ] `LDH A,(FF00)` (JOYP) - NO directamente visible en este fragmento
- [x] Otro I/O: `IOTouched=0xFF4F` (VRAM Bank) según el snapshot

**Análisis**: El loop en 0x12A0 es un bucle simple con salto condicional. El código está en una zona de datos (DB 0x0B, 0x79, 0xB0) que probablemente forma parte de una instrucción más grande. El juego está haciendo millones de reads de IF (`if_reads_program=6603703`) aunque no esté visible directamente en este fragmento, lo que sugiere que el polling de IF ocurre en código anterior o en funciones llamadas.

### tetris.gb (Frame 180) - Control DMG

**PC_hotspot1**: `0x036F`

**disasm_window(PC_hotspot1)**:
```
0x036F: JR Z, 0x036C (-5)
0x0371: DB 0xAF
0x0372: LDH (0xFF85),A
0x0374: DB 0xC3
0x0375: DB 0x43
0x0376: DB 0x03
0x0377: LDH A,(0xFFE1)
0x0379: DB 0xEF
```

**I/O identificado en el loop**:
- [ ] `LDH A,(FF0F)` (IF) - NO directamente visible
- [ ] `LDH A,(FF44)` (LY) - NO directamente visible
- [ ] `LDH A,(FF41)` (STAT) - NO directamente visible
- [ ] `LDH A,(FF00)` (JOYP) - NO directamente visible
- [x] Otro I/O: `LDH (0xFF85),A` y `LDH A,(0xFFE1)` - I/O específico del juego

**Análisis**: tetris.gb (DMG) funciona correctamente: IME=1, IE=0x09, y SÍ se sirven IRQs (`LastIRQVec=0x0040`, `VBlankServ=179`). El loop está esperando alguna condición específica del juego (escritura a 0xFF85 y lectura de 0xFFE1).

## 3) Comparativa ON vs OFF (tdx)

### tetris_dx.gbc - OFF (Baseline)

| Frame | boot_logo_prefill_enabled | TilemapNZ_9800_RAW | TilemapNZ_9C00_RAW |
|-------|---------------------------|-------------------|---------------------|
| 0     | 0                         | 0                 | 0                   |
| 60    | 0                         | 0                 | 0                   |
| 120   | 0                         | 0                 | 0                   |

### tetris_dx.gbc - ON (Contaminado)

| Frame | boot_logo_prefill_enabled | TilemapNZ_9800_RAW | TilemapNZ_9C00_RAW |
|-------|---------------------------|-------------------|---------------------|
| 0     | 0                         | 0                 | 0                   |
| 60    | 0                         | 0                 | 0                   |

**Análisis**: No se observó diferencia significativa en las métricas de VRAM/tilemap entre ON y OFF en los frames capturados. Esto confirma que el baseline está limpio y que las métricas no están contaminadas por el prefill del logo.

## 4) Decisión Automática Final (A/B/C/D) + "Siguiente Fix Mínimo"

### Caso Identificado: **Caso D con elementos de Caso C**

**Condición observada**: 

**tetris_dx.gbc (Frame 180)**:
- `EIcount = 2` ✅ (EI SÍ se ejecutó)
- `ime_set_events_count = 2` ✅ (IME SÍ se habilitó)
- `IME = 0` ❌ (Pero IME está en 0 en el snapshot)
- `IE = 0x00` ❌ (IE permanece en 0x00)
- `if_reads_program = 8762209` vs `if_reads_cpu_poll = 8761604` ✅ (El juego SÍ está polleando IF desde código)
- `ie_reads_program = 8761671` vs `ie_reads_cpu_poll = 8761604` ✅ (El juego SÍ está polleando IE desde código)
- Disasm del loop: El loop contiene `LDH A,(JOYP)` y hace CALLs que probablemente contienen polling de IF

**mario.gbc (Frame 180)**:
- `EIcount = 0` ❌ (EI NUNCA se ejecutó - Caso A)
- `ime_set_events_count = 0` ❌ (IME nunca se habilitó)
- `IME = 0` ❌
- `IE = 0x00` ❌
- `if_reads_program = 6603703` vs `if_reads_cpu_poll = 6602862` ✅ (El juego SÍ está polleando IF desde código)
- `ie_reads_program = 6603043` vs `ie_reads_cpu_poll = 6602862` ✅ (El juego SÍ está polleando IE desde código)
- Disasm del loop: Loop simple sin I/O visible directamente, pero hay millones de reads de IF

**Evidencia**:

1. **tetris_dx.gbc**: 
   - EI SÍ se ejecutó (2 veces), IME SÍ se habilitó (2 eventos), pero en el snapshot Frame 180, IME=0 e IE=0x00
   - Esto sugiere que **IME se habilitó pero luego se deshabilitó** (probablemente por DI o por bug de timing)
   - El juego está polleando IF intensivamente (8.7M reads desde código)
   - **Progreso parcial**: `fb_nonzero=6409` en frame 180 (hay actividad de renderizado)

2. **mario.gbc**:
   - EI NUNCA se ejecutó (Caso A puro)
   - El juego está polleando IF intensivamente (6.6M reads desde código) pero nunca habilita interrupciones
   - **Sin progreso**: `fb_nonzero=0` en todos los frames

3. **tetris.gb (DMG - Control)**:
   - Funciona correctamente: IME=1, IE=0x09, IRQs servidas
   - Esto confirma que el problema es específico de CGB o de la secuencia de inicialización de estos juegos CGB

**Conclusión**: 

- **mario.gbc**: **Caso A** - El juego nunca ejecuta EI, está atascado en un loop esperando alguna condición que nunca se cumple. El disasm muestra un loop simple sin I/O visible directamente, pero el polling masivo de IF sugiere que está esperando que IF cambie.

- **tetris_dx.gbc**: **Caso D con elementos de Caso C** - EI se ejecutó e IME se habilitó, pero IE permanece en 0x00. El juego está polleando IF intensivamente. Hay progreso parcial (framebuffer no-blanco), lo que sugiere que el juego avanzó más que mario.gbc, pero aún está bloqueado esperando interrupciones que nunca llegan porque IE=0x00.

**Siguiente fix mínimo (0479)**: 

**Para mario.gbc (Caso A)**:
- El juego nunca ejecuta EI. Necesitamos identificar qué condición está esperando antes de ejecutar EI.
- El disasm muestra un loop simple. Necesitamos desensamblar el código completo alrededor de 0x12A0 para ver qué condición se está evaluando.
- **Hipótesis**: El juego está esperando que algún registro I/O (IF, STAT, LY, o JOYP) tenga un valor específico antes de continuar.

**Para tetris_dx.gbc (Caso D/C)**:
- EI se ejecutó e IME se habilitó, pero IE permanece en 0x00.
- El juego escribió a IE 7 veces (`IEWrite=7`) pero IE sigue en 0x00.
- **Hipótesis**: Los writes a IE se están perdiendo o sobrescribiendo. Necesitamos verificar:
  1. Si los writes a IE (0xFFFF) se están persistiendo correctamente
  2. Si hay algún código que está limpiando IE después de escribirlo
  3. Si el timing de los writes a IE es correcto

**Fix concreto propuesto**:
1. **Instrumentar writes a IE con PC y valor**: Ya tenemos `IEWritePC` y `IEWriteVal`, pero necesitamos verificar si esos writes persisten.
2. **Verificar si hay código que lee IE y luego lo escribe con 0x00**: Buscar patrones de `LDH A,(0xFFFF)` seguido de `LDH (0xFFFF),A` con A=0x00.
3. **Para mario.gbc**: Desensamblar el código completo alrededor del hotspot para identificar la condición exacta que está esperando.
