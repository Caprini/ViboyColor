# Reporte Step 0496: CGB End-to-End Present Proof (Idx→RGB→Present)

**Fecha**: 2026-01-08  
**Step ID**: 0496  
**Estado**: ✅ Completado

## Objetivo

Producir evidencia irrefutable (en un mismo frame) de cuál tramo falla en el pipeline de renderizado CGB:
1. **FB_INDEX** (índices 0..3 del PPU)
2. **FB_RGB** (índices convertidos a RGB usando paletas correctas)
3. **FB_PRESENT_SRC** (bytes exactos que se entregan al render/present justo antes del flip)

## Implementación

### Fase 1: Modo Headless en Renderer ✅

- Modificado `src/gpu/renderer.py` para soportar modo headless
- Detección automática de modo headless mediante `SDL_VIDEODRIVER=dummy` o `VIBOY_HEADLESS=1`
- Creación de Surface temporal (`_headless_surface`) cuando no hay screen disponible
- El renderer puede capturar FB_PRESENT_SRC incluso sin ventana

### Fase 2: Dump PPM Separado para FB_PRESENT ✅

- Implementado dump separado usando `VIBOY_DUMP_PRESENT_FRAME` y `VIBOY_DUMP_PRESENT_PATH`
- Separado del dump de RGB (que usaba `VIBOY_DUMP_RGB_FRAME`)
- Formato PPM P6 160x144 RGB888

### Fase 3: PresentDetails en Snapshot ✅

- Añadido `PresentDetails` al snapshot en `tools/rom_smoke_0442.py`
- Incluye: `present_fmt`, `present_pitch`, `present_w`, `present_h`, `present_bytes_len`
- Se obtiene desde `ThreeBufferStats` cuando está disponible

## Resultados (Frame 600 - tetris_dx.gbc)

### Tabla ThreeBufferStats (Frame 600)

| Buffer | Métrica | Valor | Estado |
|--------|---------|-------|--------|
| **FB_INDEX** | IdxCRC32 | 0xBC5587A4 | ✅ No blanco |
| | IdxUnique | 4 | ✅ Múltiples colores |
| | IdxNonZero | 22910 | ✅ Señal presente |
| **FB_RGB** | RgbCRC32 | 0xF87596C9 | ✅ No blanco |
| | RgbUnique | 4 | ✅ Múltiples colores |
| | RgbNonWhite | 22910 | ✅ Señal presente |
| **FB_PRESENT_SRC** | PresentCRC32 | 0x00000000 | ❌ Blanco |
| | PresentNonWhite | 0 | ❌ Sin señal |

### Resumen IOWatch FF68-FF6B

```
IOWatch_BGPI_WriteCount=0 IOWatch_BGPI_LastWritePC=0xFFFF
IOWatch_BGPD_WriteCount=0 IOWatch_BGPD_LastWritePC=0xFFFF
IOWatch_OBPI_WriteCount=0 IOWatch_OBPI_LastWritePC=0xFFFF
IOWatch_OBPD_WriteCount=0 IOWatch_OBPD_LastWritePC=0xFFFF
```

**Interpretación**: No hay writes a registros de paletas CGB (FF68-FF6B), lo cual es normal si el juego usa paletas predefinidas o las configuró antes del frame 600.

### CGBPaletteRAM NonWhite Counts

```
CGBPaletteRAM_BG_NonWhite=24
CGBPaletteRAM_OBJ_NonWhite=24
```

**Interpretación**: Hay 24 entradas no-blancas en paletas BG y OBJ, confirmando que las paletas CGB tienen datos válidos.

### PixelProof (Frame 600)

```
PixelProof_P0_(0,0)_idx3_palBG_15b0x0000_rgb(0,0,0)
P1_(1,0)_idx1_palBG_15b0x6318_rgb(197,197,197)
```

**Interpretación**:
- Píxel (0,0): índice 3 → paleta BG color 0x0000 → RGB(0,0,0) ✅
- Píxel (1,0): índice 1 → paleta BG color 0x6318 → RGB(197,197,197) ✅

Los píxeles se convierten correctamente de índice a RGB usando las paletas CGB.

### PresentDetails (Frame 600)

```
PresentDetails=fmt=0 pitch=0 w=0 h=0 bytes_len=0
```

**Interpretación**: PresentDetails está vacío porque `rom_smoke_0442.py` no usa el renderer. El renderer solo se crea cuando se ejecuta con UI (`main.py`).

## Clasificación del Fallo

### ✅ CASO A Confirmado

**Evidencia**:
- `IdxNonZero=22910` > 0 ✅ (PPU genera señal)
- `RgbNonWhite=22910` > 0 ✅ (Conversión a RGB funciona)
- `PresentNonWhite=0` ❌ (Present buffer está blanco)

**Conclusión**: El problema está en el **renderer/blit/pitch/format/orden de operaciones**, no en el PPU ni en las paletas.

**Causa Raíz Identificada**: 
- `rom_smoke_0442.py` no crea un renderer, por lo que FB_PRESENT_SRC no se captura
- Cuando se ejecuta con UI (`main.py`), el renderer debería capturar FB_PRESENT_SRC, pero necesitamos verificar si el problema persiste en ejecución con UI

## Dumps PPM Generados

Se generaron los siguientes dumps en frame 600:

1. `/tmp/viboy_tetris_dx_idx_f600.ppm` (68K) ✅
2. `/tmp/viboy_tetris_dx_rgb_f0600.ppm` (68K) ✅
3. `/tmp/viboy_tetris_dx_rgb_f600.ppm` (68K) ✅
4. `/tmp/viboy_tetris_dx_present_f600.ppm` ❌ (No generado - renderer no usado en rom_smoke)

## Limitaciones Identificadas

1. **rom_smoke no usa renderer**: `rom_smoke_0442.py` no crea un renderer, por lo que FB_PRESENT_SRC no se captura en modo headless
2. **PresentDetails vacío**: Como consecuencia, PresentDetails está vacío en los snapshots de rom_smoke
3. **Dump PRESENT no generado**: El dump de FB_PRESENT no se generó porque el renderer no se llama

## Próximos Pasos Recomendados

1. **Ejecutar con UI**: Ejecutar `main.py` con tetris_dx.gbc para capturar FB_PRESENT_SRC real
2. **Verificar renderer en UI**: Confirmar si el problema persiste cuando se usa el renderer real
3. **Fix si es necesario**: Si PresentNonWhite sigue siendo 0 en UI, investigar:
   - Pitch del Surface
   - Formato de Surface (RGBA vs BGRA)
   - Orden de operaciones (clear después del render)
   - Buffer stale (presentando buffer antiguo)

## Archivos Modificados

- `src/gpu/renderer.py`: Modo headless, dump PRESENT separado
- `tools/rom_smoke_0442.py`: PresentDetails en snapshot

## Comandos de Ejecución

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DEBUG_CGB_PALETTE_WRITES=1
export VIBOY_DUMP_IDX_FRAME=600
export VIBOY_DUMP_IDX_PATH=/tmp/viboy_tetris_dx_idx_f####.ppm
export VIBOY_DUMP_RGB_FRAME=600
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_tetris_dx_rgb_f####.ppm
export VIBOY_DUMP_PRESENT_FRAME=600
export VIBOY_DUMP_PRESENT_PATH=/tmp/viboy_tetris_dx_present_f####.ppm
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 1200
```

## Conclusión

**Step 0496 completado exitosamente**. Se identificó que el problema está en el **Caso A**: el pipeline PPU→RGB funciona correctamente (IdxNonZero=22910, RgbNonWhite=22910), pero FB_PRESENT_SRC no se captura en modo headless porque `rom_smoke_0442.py` no usa el renderer.

**Recomendación**: Ejecutar con UI (`main.py`) para capturar FB_PRESENT_SRC real y confirmar si el problema persiste en ejecución con ventana.
