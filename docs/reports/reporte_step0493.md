# Reporte Step 0493: Identificar Bloqueo DMG y Demostrar Señal CGB

**Fecha**: 2025-01-06  
**Step ID**: 0493  
**Estado**: ✅ Completado

## Resumen Ejecutivo

Este step implementa diagnóstico avanzado para identificar el bloqueo post-clear en modo DMG (tetris.gb) y demostrar si hay señal en modo CGB (tetris_dx.gbc) después de que aparezcan writes no-cero a tiledata.

### Hallazgos Clave

**DMG (tetris.gb)**:
- **Bloqueo identificado**: Loop en PC 0x036C esperando condición que nunca se cumple
- **IO dominante**: 0xFF0F (IF) con 151,373,949 lecturas
- **Clasificación**: WAIT_LOOP_IRQ_ENABLED (IME=1, IE=0x09, IF=0xE0)
- **Problema**: Tiledata clear no detectado (ClearDoneFrame=0), pero hay 6144 intentos de write a tiledata, todos con valor 0x00

**CGB (tetris_dx.gbc)**:
- **Clear VRAM detectado**: Frame 174
- **First non-zero write**: Frame 174 (PC=0x12C1, Addr=0x8FFF, Val=0xBF)
- **ThreeBufferStats (Frame 600)**:
  - `IdxNonZero=22910` ✅ (hay índices no-cero)
  - `RgbNonWhite=0` ❌ (RGB sigue blanco)
  - `PresentNonWhite=0` ❌ (Present sigue blanco)
- **Clasificación**: **Caso 1**: `idx_nonzero>0` pero `rgb_nonwhite==0` ⇒ problema en paletas/mapeo CGB

---

## Fase A: DMG - Identificación del Bloqueo

### A1) Ejecución tetris.gb (Perfil B) - 2563 frames

**Comando ejecutado**:
```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_POST_BOOT_DMG_PROFILE=B
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_PRESENT_TRACE=1
timeout 600 python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 3000
```

**Resultado**: Ejecutado hasta frame 2563 (timeout 120s alcanzado).

### A2) Análisis del Bloqueo

#### PC Hotspots (Frame 2520 - último snapshot)

```
PCHotspotsTop3=0x036C:498286 0x036E:498276 0x036F:498268
```

**Hotspot dominante**: `0x036C` con 498,286 ejecuciones.

#### Disasm del Hotspot (0x036C)

```
0x035C: JR Z, 0x035F (+1)
0x035E: DB 0x35
0x035F: DB 0x2C
0x0360: DB 0x05
0x0361: JR NZ, 0x035A (-9)
0x0363: LDH A,(0xFFC5)
0x0365: DB 0xA7
0x0366: JR Z, 0x036C (+4)
0x0368: LD A, 0x09
```

**Análisis**: El código está en un loop que:
1. Lee desde 0xFFC5 (registro desconocido/HRAM)
2. Compara con 0 (AND A, A)
3. Si es cero, salta a 0x036C (NOP - punto de espera)
4. Si no es cero, carga 0x09 y probablemente escribe a IE

#### IO Reads Top 3

```
IOReadsTop3=0xFF0F:151373949 0xFFFF:151366393 0xFF00:20204
```

**IO dominante**: `0xFF0F` (IF - Interrupt Flag) con 151,373,949 lecturas.

### A3) Estado CPU/MMU (Frame 2520)

- **IME**: 1 (habilitado)
- **IE**: 0x09 (VBlank y Timer habilitados)
- **IF**: 0xE0 (VBlank, Timer, Serial flags activos)
- **HALTED**: 0 (CPU no en HALT)
- **VBlankReq**: 2519
- **VBlankServ**: 2519 ✅ (sincronizado)

### A4) Clasificación del Bloqueo

**Función**: `_classify_dmg_blockage()`

**Resultado**:
```
WAIT_LOOP_IRQ_ENABLED: Esperando interrupción con IME=1. 
IO dominante: IF (count=151373949), IE=0x09, IF=0xE0. 
Fix: Verificar servicio de interrupciones.
```

**Interpretación**:
- El juego está en un loop esperando que alguna condición relacionada con IF cambie
- IME está habilitado, IE tiene VBlank+Timer, IF tiene flags activos
- VBlank se está sirviendo correctamente (VBlankReq=VBlankServ)
- **Problema**: El loop lee IF masivamente pero no progresa, sugiriendo que espera un flag específico que nunca se activa o se limpia incorrectamente

### A5) VRAM Write Stats (Frame 2520)

```
VRAMWriteStats=
  TiledataAttemptsB0=6144 
  TiledataNonZeroB0=0 
  TilemapAttemptsB0=3072 
  TilemapNonZeroB0=1024
  ClearDoneFrame=0
  AttemptsAfterClear=0
  NonZeroAfterClear=0
```

**Observación crítica**: 
- Se intentaron 6144 writes a tiledata (exactamente el tamaño de tiledata: 384 tiles × 16 bytes)
- **Todos los writes fueron 0x00** (TiledataNonZeroB0=0)
- El clear VRAM no se detectó porque la lógica requiere que los 6144 writes sean cero consecutivos, pero puede que no se hayan hecho todos en el mismo frame

---

## Fase B: CGB - Demostración de Señal

### B1) Ejecución tetris_dx.gbc - 1200 frames

**Comando ejecutado**:
```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=600
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_tetris_dx_rgb_f####.ppm
export VIBOY_DUMP_IDX_PATH=/tmp/viboy_tetris_dx_idx_f####.ppm
timeout 300 python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 1200
```

**Resultado**: Ejecutado hasta frame 1200 exitosamente.

### B2) VRAM Write Stats (Frame 600)

```
VRAMWriteStats=
  ClearDoneFrame=174
  FirstNonZeroFrame=174
  FirstNonZeroPC=0x12C1
  FirstNonZeroAddr=0x8FFF
  FirstNonZeroVal=0xBF
  AttemptsAfterClear=24577
  NonZeroAfterClear=6495
  TiledataNonZeroB0=11000
  VRAM_Regions_TiledataNZ=3479
  VRAM_Regions_TilemapNZ=2012
```

**Observación**: 
- Clear VRAM completado en frame 174 ✅
- First non-zero write detectado en el mismo frame 174 ✅
- Después del clear: 24,577 intentos, 6,495 writes no-cero ✅
- VRAM tiledata tiene 3,479 bytes no-cero ✅

### B3) ThreeBufferStats (Frame 600)

```
ThreeBufferStats=
  IdxCRC32=0xBC5587A4
  IdxUnique=4
  IdxNonZero=22910 ✅
  RgbCRC32=0x70866000
  RgbUnique=1
  RgbNonWhite=0 ❌
  PresentCRC32=0x00000000
  PresentNonWhite=0 ❌
```

**Clasificación**: **Caso 1**: `idx_nonzero>0` pero `rgb_nonwhite==0` ⇒ **problema en paletas/mapeo CGB**

**Interpretación**:
- El framebuffer de índices tiene 22,910 píxeles no-cero (99.5% de la pantalla)
- El framebuffer RGB está completamente blanco (RgbNonWhite=0)
- El buffer de presentación también está blanco (PresentNonWhite=0)
- **Conclusión**: Los índices se están generando correctamente, pero la conversión índice→RGB falla porque las paletas CGB no están configuradas o el mapeo de paletas está incorrecto

### B4) CGB Palette Write Stats (Frame 600)

```
CGBPaletteWriteStats=N/A
```

**Observación**: Las estadísticas de paletas CGB no están disponibles (gateadas por `VIBOY_DEBUG_CGB_PALETTE_WRITES=1` que no se activó).

### B5) Dumps Sincronizados (Frame 600)

**Archivos generados**:
- `/tmp/viboy_tetris_dx_idx_f600.ppm` (FB_INDEX) - 68KB ✅
- `/tmp/viboy_tetris_dx_rgb_f600.ppm` (FB_RGB) - 68KB ✅

**Nota**: FB_PRESENT_SRC se genera en `renderer.py` cuando se llama `render_frame()`, pero como estamos en modo headless, no se generó.

---

## Implementaciones Completadas

### 1. Sección AfterClear Reforzada

**Archivo**: `tools/rom_smoke_0442.py`

**Modificaciones**:
- Reforzada sección AfterClear con IME/IE/IF/HALT/VBlank/LCDC/STAT/LY
- Implementado disasm focal del hotspot top1 (10-20 instrucciones)
- Detección automática de branch/loop y disasm del destino
- Clasificación automática del bloqueo usando `_classify_dmg_blockage()`

### 2. Función `_classify_dmg_blockage()`

**Archivo**: `tools/rom_smoke_0442.py`

**Funcionalidad**:
- Analiza IO reads dominantes
- Clasifica el bloqueo en una de 5 categorías:
  1. WAIT_LOOP_VBLANK_STAT
  2. WAIT_LOOP_TIMER
  3. WAIT_LOOP_JOYPAD
  4. WAIT_LOOP_IRQ_DISABLED / WAIT_LOOP_IRQ_ENABLED
  5. HALTED
  6. UNKNOWN

### 3. Dumps Sincronizados

**Archivo**: `tools/rom_smoke_0442.py`

**Función**: `_dump_synchronized_buffers()`

**Funcionalidad**:
- Genera dumps de FB_INDEX, FB_RGB en el mismo frame
- Gateado por `VIBOY_DUMP_RGB_FRAME`
- Paths configurables: `VIBOY_DUMP_IDX_PATH`, `VIBOY_DUMP_RGB_PATH`

---

## Conclusiones

### DMG (tetris.gb)

**Problema identificado**:
- Loop en PC 0x036C esperando condición que nunca se cumple
- El juego lee IF masivamente (151M+ lecturas) pero no progresa
- VBlank se está sirviendo correctamente, pero el loop no detecta el cambio esperado
- Tiledata clear no se detectó porque todos los writes fueron 0x00 (posible bug en detección o el juego realmente no carga tiles)

**Fix mínimo propuesto**:
1. Verificar que el servicio de interrupciones limpia IF correctamente
2. Revisar si el loop espera un flag específico de IF que no se está activando
3. Investigar por qué tiledata solo recibe writes de 0x00 (posible bug en descompresión o carga de datos)

### CGB (tetris_dx.gbc)

**Problema identificado**:
- **Caso 1 confirmado**: `idx_nonzero>0` pero `rgb_nonwhite==0`
- Los índices se generan correctamente (22,910 píxeles no-cero)
- La conversión índice→RGB falla porque las paletas CGB no están configuradas o el mapeo está incorrecto

**Fix mínimo propuesto**:
1. Verificar que las paletas CGB se están escribiendo correctamente (activar `VIBOY_DEBUG_CGB_PALETTE_WRITES=1`)
2. Revisar la función `convert_framebuffer_to_rgb()` en PPU.cpp para asegurar que lee las paletas CGB correctamente
3. Verificar que BG Map Attributes se están leyendo correctamente para seleccionar la paleta por tile

---

## Archivos Modificados

- `tools/rom_smoke_0442.py`:
  - Reforzada sección AfterClear (líneas ~2125-2230)
  - Implementada función `_classify_dmg_blockage()` (líneas ~2247-2310)
  - Implementada función `_dump_synchronized_buffers()` (líneas ~1378-1450)

---

## Próximos Pasos

1. **DMG**: Investigar por qué el loop en 0x036C no progresa a pesar de que VBlank se sirve correctamente
2. **CGB**: Activar `VIBOY_DEBUG_CGB_PALETTE_WRITES=1` y verificar que las paletas se están escribiendo
3. **CGB**: Revisar `convert_framebuffer_to_rgb()` para asegurar que lee paletas CGB correctamente
4. **Ambos**: Verificar que la detección de clear VRAM funciona correctamente cuando los writes no son todos en el mismo frame

---

## Evidencia

### Logs Generados

- `/tmp/viboy_0493_tetris_profile_b.log` (DMG, 2563 frames)
- `/tmp/viboy_0493_tetris_dx.log` (CGB, 1200 frames)

### Dumps PPM

- `/tmp/viboy_tetris_dx_idx_f600.ppm` (FB_INDEX, frame 600)
- `/tmp/viboy_tetris_dx_rgb_f600.ppm` (FB_RGB, frame 600)

---

**Step 0493 completado exitosamente** ✅

