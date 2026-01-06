# Reporte Step 0489: Cerrar Ambigüedad PPU vs Paletas vs Presentación

**Fecha**: 2025-01-06  
**Step ID**: 0489  
**Objetivo**: Proporcionar evidencia irrefutable para determinar si una pantalla en blanco se debe a problemas de paletas, presentación/blit, o el PPU no genera datos útiles.

---

## Resumen Ejecutivo

Se implementaron instrumentaciones en tres puntos críticos del pipeline de renderizado:
1. **FB_INDEX**: Buffer de índices (0..3) generado por el PPU
2. **FB_RGB**: Buffer RGB después de mapear paletas
3. **FB_PRESENT_SRC**: Buffer exacto pasado a SDL/ventana

Adicionalmente, se añadieron instrumentaciones para:
- **CGB Palette Writes**: Tracking de escrituras a paletas CGB (BGPI/BGPD, OBPI/OBPD)
- **DMG Tile Fetch**: Contadores de lecturas de tile data por scanline

---

## Implementación

### Fase A: ThreeBufferStats ✅

**Archivos modificados**:
- `src/core/cpp/PPU.hpp`: Estructura `ThreeBufferStats`
- `src/core/cpp/PPU.cpp`: Método `compute_three_buffer_stats()`
- `src/core/cython/ppu.pxd` y `ppu.pyx`: Exposición a Python
- `src/gpu/renderer.py`: Captura de `FB_PRESENT_SRC` desde Pygame Surface

**Gate**: `VIBOY_DEBUG_PRESENT_TRACE=1`

**Métricas capturadas**:
- `idx_crc32`, `idx_unique`, `idx_nonzero`: Estadísticas del buffer de índices
- `rgb_crc32`, `rgb_unique_colors_approx`, `rgb_nonwhite_count`: Estadísticas del buffer RGB
- `present_crc32`, `present_nonwhite_count`, `present_fmt`, `present_pitch`, `present_w`, `present_h`: Estadísticas del buffer presentado

### Fase B: Dump PPM RGB ✅

**Archivos modificados**:
- `tools/rom_smoke_0442.py`: Función `_dump_rgb_framebuffer_to_ppm()`

**Gate**: `VIBOY_DUMP_RGB_FRAME` y `VIBOY_DUMP_RGB_PATH`

**Funcionalidad**: Dump obligatorio del framebuffer RGB (convertido desde índices usando BGP para DMG) en formato PPM.

### Fase C: CGB Palette Write Stats ✅

**Archivos modificados**:
- `src/core/cpp/MMU.hpp`: Estructura `CGBPaletteWriteStats`
- `src/core/cpp/MMU.cpp`: Tracking en writes a 0xFF68-0xFF6B
- `src/core/cython/mmu.pxd` y `mmu.pyx`: Exposición a Python

**Gate**: `VIBOY_DEBUG_CGB_PALETTE_WRITES=1`

**Métricas capturadas**:
- `bgpd_write_count`, `last_bgpd_write_pc`, `last_bgpd_value`, `last_bgpi`
- `obpd_write_count`, `last_obpd_write_pc`, `last_obpd_value`, `last_obpi`

### Fase D: DMG Tile Fetch Stats ✅

**Archivos modificados**:
- `src/core/cpp/PPU.hpp`: Estructura `DMGTileFetchStats`
- `src/core/cpp/PPU.cpp`: Tracking en `decode_tile_line()`
- `src/core/cython/ppu.pxd` y `ppu.pyx`: Exposición a Python

**Gate**: `VIBOY_DEBUG_DMG_TILE_FETCH=1`

**Métricas capturadas**:
- `tile_bytes_read_total_count`: Total de bytes de tile data leídos
- `tile_bytes_read_nonzero_count`: Bytes no-cero leídos

---

## Resultados de Ejecución

### ROM: `tetris.gb` (DMG)

**Comando ejecutado**:
```bash
VIBOY_DEBUG_PRESENT_TRACE=1 \
VIBOY_DEBUG_CGB_PALETTE_WRITES=1 \
VIBOY_DEBUG_DMG_TILE_FETCH=1 \
VIBOY_DUMP_RGB_FRAME=5 \
VIBOY_DUMP_RGB_PATH=docs/reports/dumps/tetris_frame_####.ppm \
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 60 --max-seconds 10
```

### Snapshot Frame 0

```
ThreeBufferStats=IdxCRC32=0x00000000 IdxUnique=1 IdxNonZero=0 | 
RgbCRC32=0x00000000 RgbUnique=1 RgbNonWhite=2304 | 
PresentCRC32=0x00000000 PresentNonWhite=0
```

**Análisis**:
- **FB_INDEX**: CRC32=0, Unique=1, NonZero=0 → **Buffer completamente en 0 (blanco)**
- **FB_RGB**: CRC32=0, Unique=1, NonWhite=2304 → **Conversión detecta 2304 píxeles no-blancos** (posible bug en conversión o BGP)
- **FB_PRESENT**: CRC32=0, NonWhite=0 → **Buffer presentado está en blanco**

**Interpretación**: El PPU genera un buffer de índices completamente en 0, pero la conversión RGB detecta píxeles no-blancos. Esto sugiere un problema en la conversión DMG o en el mapeo de BGP.

### Snapshot Frame 1

```
ThreeBufferStats=IdxCRC32=0x00000000 IdxUnique=1 IdxNonZero=0 | 
RgbCRC32=0x00000000 RgbUnique=1 RgbNonWhite=2304 | 
PresentCRC32=0x00000000 PresentNonWhite=0
```

**Análisis**: Similar al Frame 0.

### Snapshot Frame 2

```
ThreeBufferStats=IdxCRC32=0x00000000 IdxUnique=1 IdxNonZero=0 | 
RgbCRC32=0x4F0D7000 RgbUnique=1 RgbNonWhite=0 | 
PresentCRC32=0x00000000 PresentNonWhite=0
```

**Análisis**:
- **FB_INDEX**: Sigue en 0
- **FB_RGB**: CRC32 cambió a `0x4F0D7000`, pero NonWhite=0 → **Inconsistencia**
- **FB_PRESENT**: Sigue en blanco

### CGB Palette Write Stats

```
CGBPaletteWriteStats=BGPD_Writes=0 BGPD_LastPC=0x0000 BGPD_LastVal=0x00 BGPI=0x00 | 
OBPD_Writes=0 OBPD_LastPC=0x0000 OBPD_LastVal=0x00 OBPI=0x00
```

**Análisis**: No hay writes a paletas CGB (esperado para ROM DMG).

### DMG Tile Fetch Stats

```
DMGTileFetchStats=TileBytesTotal=0 TileBytesNonZero=0
```

**Análisis**: **CRÍTICO** - El PPU no está leyendo tile data. Esto explica por qué el buffer de índices está en 0.

---

## Hallazgos Clave

### 1. PPU no lee Tile Data

**Evidencia**: `DMGTileFetchStats=TileBytesTotal=0 TileBytesNonZero=0`

**Implicación**: El PPU no está ejecutando `decode_tile_line()` o las lecturas de VRAM están bloqueadas/retornando 0.

**Posibles causas**:
- VRAM está vacía (confirmado: `VRAM non-zero: 0/6144`)
- El PPU no está en modo de renderizado activo
- Las lecturas de VRAM están bloqueadas por locks en `MMU.cpp`

### 2. Buffer de Índices en Blanco

**Evidencia**: `IdxCRC32=0x00000000 IdxUnique=1 IdxNonZero=0`

**Implicación**: El framebuffer de índices está completamente en 0 (blanco).

**Causa raíz**: Relacionado con el hallazgo #1 - si no se lee tile data, no se puede generar píxeles.

### 3. Inconsistencia en Conversión RGB

**Evidencia**: `RgbCRC32=0x00000000 RgbUnique=1 RgbNonWhite=2304` (Frame 0-1) vs `RgbCRC32=0x4F0D7000 RgbNonWhite=0` (Frame 2)

**Implicación**: Hay un bug en la conversión de índices a RGB o en el muestreo.

**Recomendación**: Revisar `compute_three_buffer_stats()` en `PPU.cpp`, específicamente la conversión DMG.

### 4. Buffer Presentado en Blanco

**Evidencia**: `PresentCRC32=0x00000000 PresentNonWhite=0`

**Implicación**: El buffer que se pasa a SDL está en blanco, consistente con el buffer de índices.

---

## Dump PPM Generado

**Archivo**: `docs/reports/dumps/tetris_frame_0005.ppm`

**Estado**: ✅ Generado exitosamente

**Contenido esperado**: Framebuffer RGB convertido desde índices usando BGP.

---

## Recomendaciones

### Prioridad Alta

1. **Investigar por qué `decode_tile_line()` no se ejecuta**:
   - Verificar que el PPU esté en modo de renderizado activo
   - Revisar locks de VRAM en `MMU.cpp` durante modo 3 (Pixel Transfer)
   - Verificar que `render_scanline()` esté llamando a `decode_tile_line()`

2. **Corregir inconsistencia en conversión RGB**:
   - Revisar muestreo en `compute_three_buffer_stats()` (cada 10 píxeles puede estar causando el problema)
   - Verificar que BGP se lea correctamente

### Prioridad Media

3. **Verificar que VRAM se llene con datos**:
   - El juego debería escribir tiles a VRAM antes de renderizar
   - Revisar si hay un problema de timing (el PPU intenta renderizar antes de que VRAM esté lista)

---

## Próximos Pasos

1. Ejecutar con ROM CGB (`tetris_dx.gbc`) para comparar comportamiento
2. Añadir más instrumentación en `decode_tile_line()` para ver por qué no se ejecuta
3. Revisar logs de VRAM writes para verificar si el juego está escribiendo tiles

---

## Archivos Generados

- `docs/reports/logs/tetris_step0489.log`: Log completo de ejecución
- `docs/reports/dumps/tetris_frame_0005.ppm`: Dump PPM del framebuffer RGB (frame 5)

---

**Estado**: ✅ Fase E completada - Evidencia recopilada

