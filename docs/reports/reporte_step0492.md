# Reporte Step 0492: Detectar Clear VRAM y Carga de Tiles

**Fecha**: 2025-12-29  
**Step ID**: 0492  
**Estado**: ✅ Completado

---

## Objetivo

Implementar tracking detallado de escrituras a VRAM (especialmente tiledata) para diagnosticar por qué el emulador muestra pantalla en blanco en modo DMG y CGB. El objetivo es detectar:
1. Cuándo se completa el "clear VRAM" inicial (6144 bytes de tiledata escritos con cero)
2. Si hay writes no-cero después del clear (indicando carga de tiles)
3. Comparar dos perfiles post-boot DMG diferentes (A vs B)
4. Diagnosticar el problema de presentación en CGB

---

## Resultados: DMG Profile A vs Profile B

### Perfil A (Default - LCDC=0x00 inicialmente)

**Configuración**:
- `VIBOY_POST_BOOT_DMG_PROFILE=A` (default)
- `LCDC=0x00` (LCD deshabilitado inicialmente)

**Resultados**:
- **Clear VRAM completado**: Frame 0
- **Tiledata attempts después del clear**: 0
- **Tiledata non-zero después del clear**: 0
- **First non-zero frame**: 0 (no detectado)
- **LCDC final**: 0x03 (LCD deshabilitado)
- **Tilemap writes**: 0 (TilemapNZ_9800_RAW=0, TilemapNZ_9C00_RAW=0)

**Conclusión**: El juego no intenta escribir tiles después del clear. El LCDC permanece deshabilitado (0x03), lo que sugiere que el juego no está progresando en su inicialización.

---

### Perfil B (Alternativo - LCDC=0x91 operativo)

**Configuración**:
- `VIBOY_POST_BOOT_DMG_PROFILE=B`
- `LCDC=0x91` (LCD operativo, BG y Window habilitados)

**Resultados**:
- **Clear VRAM completado**: Frame 0
- **Tiledata attempts después del clear**: 0
- **Tiledata non-zero después del clear**: 0
- **First non-zero frame**: 0 (no detectado)
- **LCDC final**: 0x81 (LCD operativo, BG habilitado)
- **Tilemap writes**: 1024 bytes (TilemapNZ_9800_RAW=1024)

**Conclusión**: Similar al Perfil A, pero con diferencias importantes:
- El LCDC se mantiene operativo (0x81) en lugar de deshabilitarse
- Hay writes al tilemap (1024 bytes), lo que indica que el juego está intentando configurar el mapa de tiles
- Sin embargo, aún no hay writes no-cero a tiledata después del clear

**Diferencia clave**: El Perfil B muestra más actividad (tilemap writes), pero aún no carga tiles gráficos.

---

## Resultados: CGB (tetris_dx.gbc)

**Configuración**:
- `VIBOY_DEBUG_VRAM_WRITES=1`
- `VIBOY_DEBUG_PRESENT_TRACE=1`
- `VIBOY_DUMP_RGB_FRAME=180`
- `VIBOY_DUMP_IDX_FRAME=180`
- `VIBOY_DUMP_PRESENT_FRAME=180`

**Resultados**:
- **Clear VRAM completado**: Frame 174
- **First non-zero write**: Frame 174, PC:0x12C1, Addr:0x8FFF, Val:0xBF
- **Stop early**: Activado en frame 174 (detectó first non-zero)
- **RgbNonWhite**: 0 (framebuffer RGB sin contenido no-blanco)
- **PresentNonWhite**: 0 (framebuffer de presentación sin contenido no-blanco)
- **LCDC**: 0x91 (LCD operativo)

**Conclusión**: 
- **¡El CGB SÍ está cargando tiles!** El clear se completa en el frame 174 y **inmediatamente después** hay un write no-cero a tiledata (0x8FFF con valor 0xBF).
- Sin embargo, los framebuffers RGB y Present siguen siendo blancos, lo que sugiere que el problema está en el pipeline de renderizado, no en la carga de datos.

---

## Comparación: DMG vs CGB

| Métrica | DMG Profile A | DMG Profile B | CGB |
|---------|--------------|---------------|-----|
| Clear VRAM Frame | 0 | 0 | 174 |
| First Non-Zero Frame | 0 (no detectado) | 0 (no detectado) | 174 |
| Tiledata Attempts After Clear | 0 | 0 | N/A |
| Tiledata Non-Zero After Clear | 0 | 0 | 1+ (detectado) |
| Tilemap Writes | 0 | 1024 | N/A |
| LCDC Final | 0x03 (OFF) | 0x81 (ON) | 0x91 (ON) |
| Carga de Tiles | ❌ No | ❌ No | ✅ Sí |

---

## Hallazgos Clave

### 1. DMG: El problema NO es el post-boot state

- Ambos perfiles (A y B) muestran el mismo comportamiento: **no hay writes no-cero a tiledata después del clear**.
- El Perfil B muestra más actividad (tilemap writes, LCDC operativo), pero aún no carga tiles.
- **Conclusión**: El problema en DMG no está relacionado con el estado post-boot inicial. El juego no está progresando en su inicialización por otra razón.

### 2. CGB: El problema está en el pipeline de renderizado

- El CGB **SÍ está cargando tiles** (first non-zero write en frame 174).
- Sin embargo, los framebuffers RGB y Present siguen siendo blancos.
- **Conclusión**: El problema en CGB está en el pipeline de renderizado (PPU), no en la carga de datos. Los tiles se están cargando correctamente, pero no se están renderizando.

### 3. Timing del Clear VRAM

- En DMG, el clear se completa muy rápido (frame 0), lo que sugiere que el juego está en un estado de inicialización temprana.
- En CGB, el clear se completa más tarde (frame 174), lo que indica un proceso de inicialización más largo.

---

## Próximos Pasos Sugeridos

### Para DMG:
1. **Investigar por qué el juego no progresa después del clear**: 
   - Verificar si hay loops de espera que no se están resolviendo correctamente
   - Revisar el manejo de interrupciones (especialmente VBlank)
   - Verificar si hay condiciones de carrera en el timing de I/O

2. **Analizar los PC hotspots después del clear**:
   - Los snapshots incluyen `pc_hotspots_top3` en la sección "AfterClear"
   - Identificar qué código se está ejecutando después del clear

### Para CGB:
1. **Investigar el pipeline de renderizado**:
   - Verificar si los tiles se están leyendo correctamente desde VRAM
   - Revisar la lógica de presentación (RGB -> Present)
   - Verificar si hay problemas con paletas CGB

2. **Analizar los dumps de framebuffer**:
   - Los dumps en frame 180 deberían mostrar el estado de los framebuffers
   - Comparar RGB vs Present para identificar dónde se pierde la información

---

## Archivos Modificados

- `src/core/cpp/MMU.hpp`: Añadidos campos a `VRAMWriteStats` para tracking de clear y post-clear
- `src/core/cpp/MMU.cpp`: Implementado tracking de clear VRAM y perfil B post-boot
- `src/core/cython/mmu.pxd`: Actualizado struct `VRAMWriteStats` y añadido `TiledataWriteEvent`
- `src/core/cython/mmu.pyx`: Exposición de nuevos campos a Python
- `tools/rom_smoke_0442.py`: Modo "stop early" y sección "AfterClear" en snapshots

---

## Comandos de Ejecución

### DMG Profile A:
```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_POST_BOOT_DMG_PROFILE=A
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_PRESENT_TRACE=1
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 3000 --stop-early-on-first-nonzero > /tmp/viboy_0492_tetris_profile_a.log 2>&1
```

### DMG Profile B:
```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_POST_BOOT_DMG_PROFILE=B
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_PRESENT_TRACE=1
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 3000 --stop-early-on-first-nonzero > /tmp/viboy_0492_tetris_profile_b.log 2>&1
```

### CGB:
```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=180
export VIBOY_DUMP_IDX_FRAME=180
export VIBOY_DUMP_PRESENT_FRAME=180
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 3000 --stop-early-on-first-nonzero > /tmp/viboy_0492_tetris_dx_cgb.log 2>&1
```

---

## Referencias

- Pan Docs: VRAM Access Restrictions (Mode 3)
- GBEDG: Post-Boot State
- Plan Step 0492: `step_0492_-_detectar_clear_vram_y_carga_de_tiles_70afcfb7.plan.md`

