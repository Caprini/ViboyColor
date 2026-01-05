# Reporte Step 0488: Blank Screen Triage - Framebuffer vs Paletas vs Blit

**Fecha**: 2026-01-05  
**Step ID**: 0488  
**Objetivo**: Responder con evidencia a 2 preguntas:
1. ¿El PPU está generando un framebuffer con más de 1 color/patrón?
2. Si sí, ¿dónde se destruye la señal: mapeo de paleta/colores o blit/presentación?

---

## Configuración de Ejecución

**Flags utilizados**:
- `VIBOY_SIM_BOOT_LOGO=0` (evitar contaminación)
- `VIBOY_DEBUG_FB_STATS=1` (activar estadísticas de framebuffer)
- `VIBOY_DUMP_FB_FRAME=180` (dump PPM en frame 180)
- `VIBOY_DUMP_FB_PATH=/tmp/viboy_<rom>_f180.ppm`

**ROMs ejecutadas**:
- `tetris.gb` (control DMG) - 240 frames
- `tetris_dx.gbc` (CGB) - 240 frames

---

## Tabla de Snapshots: tetris.gb

### Frame 0
- **FrameBufferStats**:
  - `fb_crc32`: 0x00000000
  - `fb_unique_colors`: 1
  - `fb_nonwhite_count`: 0
  - `fb_nonblack_count`: 23040
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [23040, 0, 0, 0]
  - `fb_changed_since_last`: 0
- **PaletteStats**:
  - `is_cgb`: 0 (DMG)
  - `bgp`: 0xE4
  - `obp0`: 0xE4
  - `obp1`: 0xC4
  - `bgp_idx_to_shade`: [0, 1, 2, 3] (todos distintos)
  - `cgb_bg_palette_nonwhite_entries`: 0
  - `cgb_obj_palette_nonwhite_entries`: 0
- **boot_logo_prefill_enabled**: 0
- **TilemapNZ_9800_RAW**: 0
- **TilemapNZ_9C00_RAW**: 0

### Frame 60
- **FrameBufferStats**:
  - `fb_crc32`: 0x00000000
  - `fb_unique_colors`: 1
  - `fb_nonwhite_count`: 0
  - `fb_nonblack_count`: 23040
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [23040, 0, 0, 0]
  - `fb_changed_since_last`: 0
- **PaletteStats**:
  - `is_cgb`: 0 (DMG)
  - `bgp`: 0xE4
  - `obp0`: 0xE4
  - `obp1`: 0xC4
  - `bgp_idx_to_shade`: [0, 1, 2, 3]
  - `cgb_bg_palette_nonwhite_entries`: 0
  - `cgb_obj_palette_nonwhite_entries`: 0
- **boot_logo_prefill_enabled**: 0
- **TilemapNZ_9800_RAW**: 1024
- **TilemapNZ_9C00_RAW**: 0

### Frame 120
- **FrameBufferStats**:
  - `fb_crc32`: 0x00000000
  - `fb_unique_colors`: 1
  - `fb_nonwhite_count`: 0
  - `fb_nonblack_count`: 23040
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [23040, 0, 0, 0]
  - `fb_changed_since_last`: 0
- **PaletteStats**: (mismo que frame 60)
- **boot_logo_prefill_enabled**: 0
- **TilemapNZ_9800_RAW**: 1024
- **TilemapNZ_9C00_RAW**: 0

### Frame 180
- **FrameBufferStats**:
  - `fb_crc32`: 0x00000000
  - `fb_unique_colors`: 1
  - `fb_nonwhite_count`: 0
  - `fb_nonblack_count`: 23040
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [23040, 0, 0, 0]
  - `fb_changed_since_last`: 0
- **PaletteStats**: (mismo que frame 60)
- **boot_logo_prefill_enabled**: 0
- **TilemapNZ_9800_RAW**: 1024
- **TilemapNZ_9C00_RAW**: 0
- **PPM generado**: `/tmp/viboy_tetris_gb_f180.ppm` (68KB, 160x144)
  - **Análisis PPM**: **Uniforme (blanco completo)**
  - **Colores únicos**: 1 (solo RGB 255,255,255)
  - **Conclusión**: Framebuffer completamente blanco

---

## Tabla de Snapshots: tetris_dx.gbc

### Frame 0
- **FrameBufferStats**:
  - `fb_crc32`: 0x00000000
  - `fb_unique_colors`: 1
  - `fb_nonwhite_count`: 0
  - `fb_nonblack_count`: 23040
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [23040, 0, 0, 0]
  - `fb_changed_since_last`: 0
- **PaletteStats**:
  - `is_cgb`: 1 (CGB)
  - `bgp`: 0xE4
  - `obp0`: 0xE4
  - `obp1`: 0xC4
  - `bgp_idx_to_shade`: [0, 1, 2, 3]
  - `cgb_bg_palette_nonwhite_entries`: 0
  - `cgb_obj_palette_nonwhite_entries`: 0
- **boot_logo_prefill_enabled**: 0

### Frame 60
- **FrameBufferStats**: (mismo que frame 0)
- **PaletteStats**: (mismo que frame 0)

### Frame 120
- **FrameBufferStats**: (mismo que frame 0)
- **PaletteStats**: (mismo que frame 0)

### Frame 180
- **FrameBufferStats**:
  - `fb_crc32`: 0x75957663
  - `fb_unique_colors`: **4** ⚠️
  - `fb_nonwhite_count`: **6409**
  - `fb_nonblack_count`: 21968
  - `fb_top4_colors`: [0, 1, 2, 3]
  - `fb_top4_colors_count`: [16631, 3189, 2148, 1072]
  - `fb_changed_since_last`: 1
- **PaletteStats**: (mismo que frame 0)
- **PPM generado**: `/tmp/viboy_tetris_dx_f180.ppm` (68KB, 160x144)
  - **Análisis PPM**: **NO uniforme** (4 colores únicos detectados)
  - **Colores únicos**: 4 (RGB: 255,255,255; 255,255,192; 192,192,192; 255,96,96)
  - **Conclusión**: Framebuffer tiene diversidad de colores

---

## Análisis y Árbol de Decisión

### Evidencia Recolectada

#### tetris.gb (DMG)
1. **Framebuffer Stats**:
   - `fb_unique_colors = 1` en todos los frames (0, 60, 120, 180)
   - `fb_nonwhite_count = 0` (todos los píxeles son índice 0 = blanco)
   - `fb_nonblack_count = 23040` (todos los píxeles son distintos de índice 3)
   - `fb_top4_colors_count = [23040, 0, 0, 0]` (solo índice 0 presente)
   - `fb_crc32 = 0x00000000` (hash de framebuffer completamente blanco)
   - `fb_changed_since_last = 0` (framebuffer no cambia entre frames)

#### tetris_dx.gbc (CGB)
1. **Framebuffer Stats** (Frame 180):
   - `fb_unique_colors = 4` ⚠️ **DIVERSIDAD DETECTADA**
   - `fb_nonwhite_count = 6409` (píxeles no-blancos presentes)
   - `fb_nonblack_count = 21968`
   - `fb_top4_colors_count = [16631, 3189, 2148, 1072]` (4 índices presentes)
   - `fb_crc32 = 0x75957663` (hash no-cero, framebuffer tiene datos)
   - `fb_changed_since_last = 1` (framebuffer cambia entre frames)

2. **Palette Stats**:
   - **DMG (tetris.gb)**: BGP=0xE4 (mapea índices 0→0, 1→1, 2→2, 3→3 - todos distintos)
   - **CGB (tetris_dx.gbc)**: BGP=0xE4, paletas CGB vacías (todas 0x7FFF = blanco)
   - `cgb_bg_palette_nonwhite_entries = 0` (paletas CGB no inicializadas)
   - `cgb_obj_palette_nonwhite_entries = 0`

3. **VRAM/Tilemap**:
   - **Frame 0**: TilemapNZ_9800_RAW = 0 (tilemap vacío)
   - **Frame 60+**: TilemapNZ_9800_RAW = 1024 (tilemap tiene datos)
   - El tilemap se llena, pero el framebuffer sigue blanco

4. **PPM Dumps**:
   - **tetris.gb**: PPM **uniforme** (blanco completo, 1 color único)
   - **tetris_dx.gbc**: PPM **NO uniforme** (4 colores únicos detectados)
   - Tamaño correcto: 160x144, 68KB ambos
   - Formato correcto: Netpbm P6 (binary RGB)

### Conclusión del Árbol de Decisión

**Resultados por ROM**:

#### tetris.gb (DMG) - Caso 3: PPM uniforme + paletas correctas → Bug en fetch/decode/VRAM write lock

**Evidencia**:
- ✅ PPM uniforme (blanco completo) - confirmado por análisis de archivo
- ✅ Paletas correctas (BGP=0xE4 mapea índices a shades distintos)
- ✅ Tilemap tiene datos (1024 bytes no-cero desde frame 60)
- ❌ Framebuffer completamente blanco (índice 0 en todos los píxeles)
- ❌ FrameBufferStats: `fb_unique_colors=1`, `fb_nonwhite_count=0`

**Diagnóstico**: El problema está en el **pipeline de renderizado del PPU en modo DMG**:
- VRAM tiene datos (tilemap se llena)
- Paletas están correctas
- Framebuffer está vacío (solo índice 0 = blanco)

**Posibles causas**:
- Bug en fetch de tiles (DMG)
- Bug en decode 2bpp (DMG)
- Bug en aplicación de paleta BGP (DMG)
- Bug en write al framebuffer (DMG)
- VRAM write lock durante modos incorrectos

#### tetris_dx.gbc (CGB) - Caso 1: PPM NO uniforme + ventana uniforme → Bug blit/SDL/format/pitch

**Evidencia**:
- ✅ PPM **NO uniforme** (4 colores únicos detectados)
- ✅ FrameBufferStats: `fb_unique_colors=4`, `fb_nonwhite_count=6409`
- ✅ Framebuffer tiene diversidad: Top4Count=[16631, 3189, 2148, 1072]
- ✅ Paletas correctas (BGP=0xE4)
- ❌ **Ventana sigue blanca** (a pesar de que el framebuffer tiene datos)

**Diagnóstico**: El problema está en la **presentación/blit**:
- El PPU **SÍ está generando** un framebuffer con diversidad (4 colores)
- El PPM muestra la diversidad correctamente
- La ventana SDL/pygame muestra pantalla blanca
- **Conclusión**: Bug en blit/presentación (SDL texture update, pitch/stride, formato RGBA/BGRA, o se está blanqueando después del render)

**Próximos pasos sugeridos (Step 0489)**:

**Para tetris.gb (DMG)**:
1. Instrumentar `render_scanline()` para verificar fetch/decode en modo DMG
2. Comparar con tetris_dx.gbc que SÍ funciona (modo CGB)
3. Verificar restricciones de acceso a VRAM durante modos PPU en DMG

**Para tetris_dx.gbc (CGB)**:
1. Instrumentar antes y después del blit (hash del buffer fuente vs hash del buffer subido a textura)
2. Verificar formato de textura SDL (RGBA vs BGRA)
3. Verificar pitch/stride del framebuffer
4. Verificar que no se esté blanqueando el framebuffer después del render

---

## Archivos Generados

- `/tmp/viboy_tetris_gb_f180.ppm` - Dump PPM de tetris.gb (frame 180)
- `/tmp/viboy_tetris_dx_f180.ppm` - Dump PPM de tetris_dx.gbc (frame 180)
- `/tmp/viboy_0488_tetris_gb.log` - Log completo de tetris.gb
- `/tmp/viboy_0488_tetris_dx.log` - Log completo de tetris_dx.gbc

---

## Validación del Test Unitario

**Test**: `test_ppu_framebuffer_diversity_0488.py::test_ppu_produces_multiple_colors_when_vram_has_pattern`

**Resultado**: ✅ **PASA**

**Evidencia**:
- El test crea un tile checkerboard en VRAM
- Configura tilemap y activa LCD/BG
- Ejecuta frames completos y verifica `fb_unique_colors >= 2`
- **El test pasa**, lo que confirma que el PPU **puede** producir diversidad cuando VRAM tiene datos

**Implicación**:
- El problema NO es un bug fundamental en el pipeline de renderizado
- El problema es específico a cómo se cargan/usan los tiles en ROMs reales
- Posible causa: timing de carga de tiles, restricciones de acceso VRAM, o inicialización incorrecta

---

## Notas Técnicas

- `VIBOY_SIM_BOOT_LOGO=0` reportado en todos los snapshots (baseline limpio)
- `boot_logo_prefill_enabled=0` confirmado
- FrameBufferStats se calcula correctamente (gate funciona)
- PaletteStats se integra correctamente en snapshots
- Dump PPM funciona correctamente (archivos generados, formato válido)

