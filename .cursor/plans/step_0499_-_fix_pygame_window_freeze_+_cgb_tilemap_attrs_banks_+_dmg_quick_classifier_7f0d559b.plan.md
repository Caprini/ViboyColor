---
name: Step 0499 - Fix pygame window freeze + CGB tilemap attrs/banks + DMG quick classifier
overview: "Steps 0495-0498 demostraron: CGB - PPU genera FB_INDEX con señal y conversión IDX→RGB funciona cuando se usa ruta correcta. Renderer/present - en rom_smoke originalmente no había renderer; se añadió renderer headless y trazas CRC/frame_id. En UI se vio que a partir de ciertos frames hay NonWhite en FB_PRESENT_SRC. Freeze \"no responde\" - existe evidencia visual de que cuando rom_smoke_0442.py crea ventana/renderer en modo windowed, la app se queda \"no responde\" por falta de event pumping/loop de eventos. Estado actual: muchos juegos siguen en blanco o negro, Tetris DX llega a mostrar \"tiles basura\" (señal parcial pero render incorrecto), rom_smoke/renderer puede provocar \"no responde\" si se abre ventana y no se bombean eventos. Este step: (A) que rom_smoke con renderer no cuelgue la ventana, (B) resolver el garbage rendering CGB (mínimo viable), (C) mejorar diagnóstico del DMG en blanco (sin asumir que es PPU)."
todos:
  - id: 0499-t1-repro-windowed
    content: "Crear modo reproducible en rom_smoke_0442.py: añadir --use-renderer-windowed que fuerza SDL_VIDEODRIVER normal (no dummy) para ver si aparece el \"no responde\". Ejecutar rom_smoke con ambos modos (headless y windowed) y generar log corto que muestre que en windowed se están procesando eventos."
    status: pending
  - id: 0499-t2-fix-event-pump
    content: "Implementar fix mínimo en renderer.py: si hay ventana (screen real) → bombear eventos cada frame (pygame.event.pump). Si headless/dummy → NO llamar a cosas que bloqueen. Modificar render_frame() para bombear eventos en modo windowed. Logging limitado (primeros 20 frames) con contador \"frames procesados\" + confirmación de event_pump activo. Criterio: en modo windowed NO debe aparecer \"no responde\", rom_smoke termina frames objetivo sin intervención manual, headless sigue estable."
    status: pending
    dependencies:
      - 0499-t1-repro-windowed
  - id: 0499-t3-audit-cgb-tilemap
    content: "Auditoría dirigida en PPU.cpp (NO código aún): localizar en ruta de background exactamente dónde se calcula tilemap_addr, de qué banco se lee tile_id (debe ser bank 0 siempre), si en CGB se lee attr (bank 1) o no, cómo se decide bank para tiledata bytes (debe ser attr bit3), si se respeta LCDC bit4 (8000 vs 8800 signed). Entrega: mini-checklist en comentario o reporte interno."
    status: pending
  - id: 0499-t4-fix-cgb-tilemap-attrs
    content: "Fix mínimo CGB tilemap/attrs en PPU.cpp: en CGB real y NO dmg_compat_mode, tile_id debe leerse de VRAM bank 0, attr debe leerse de VRAM bank 1, bank de tiledata se elige con attr bit3, (opcional) aplicar xflip/yflip y palette bits. En DMG o dmg_compat_mode seguir ruta DMG sin attrs. Verificar que se respeta LCDC bit4. Criterio: tetris_dx.gbc pasa de \"ruido caótico\" a algo estructurado, IdxNonZero>0 y RgbNonWhite>0 se mantienen, PresentNonWhite>0 en rango razonable."
    status: pending
    dependencies:
      - 0499-t3-audit-cgb-tilemap
  - id: 0499-t5-dmg-quick-classifier
    content: "Añadir DMG Quick Classifier al snapshot en rom_smoke_0442.py: reusar métricas existentes (LCDC, IdxNonZero, RgbNonWhite, VRAM tiledataNZ, PC hotspots) y clasificar automáticamente (CPU_LOOP, LCDC_OFF, VRAM_TILEDATA_ZERO, IDX_ZERO_DESPITE_TILEDATA, RGB_FAIL_DESPITE_IDX, OK_BUT_WHITE). Criterio: para tetris.gb y 1 ROM DMG extra, snapshot final da clasificación inequívoca."
    status: pending
  - id: 0499-t6-execute-cgb
    content: "Ejecutar rom_smoke para tetris_dx.gbc (1200 frames) con --use-renderer-headless, frames suficientes para pasar first signal. Guardar logs a /tmp/viboy_0499_tetris_dx.log + dumps por frame_id. Evidencia: 2-3 dumps PPM \"antes vs después\" en mismo frame_id, snapshot PixelProof/ThreeBufferStats confirmando RGB no es ruido."
    status: pending
    dependencies:
      - 0499-t4-fix-cgb-tilemap-attrs
  - id: 0499-t7-execute-dmg
    content: "Ejecutar rom_smoke para tetris.gb (3000 frames) y 1 ROM DMG adicional (p. ej. pokemon red) sin renderer. Generar snapshot con DMG Quick Classifier. Entrega: resumen de 10 líneas por ROM con clasificación final + métricas clave."
    status: pending
    dependencies:
      - 0499-t5-dmg-quick-classifier
  - id: 0499-t8-create-report
    content: "Crear reporte markdown docs/reports/reporte_step0499.md con: Fase A (log con event_pump activo, evidencia windowed no dispara \"no responde\"), Fase B (auditoría + dumps antes/después + PixelProof/ThreeBufferStats), Fase C (tabla con clasificación DMG para 2 ROMs). NO placeholders."
    status: pending
    dependencies:
      - 0499-t2-fix-event-pump
      - 0499-t6-execute-cgb
      - 0499-t7-execute-dmg
  - id: 0499-t9-document
    content: "Documentar Step 0499 en bitácora HTML (docs/bitacora/entries/YYYY-MM-DD__0499__fix-pygame-freeze-cgb-tilemap-dmg-classifier.html) e informe dividido. ⚠️ CRÍTICO: Usar fecha correcta (2026, no 2025). Actualizar docs/bitacora/index.html y docs/informe_fase_2/. Commit/push con mensaje \"feat(diag): Step 0499 - Fix pygame window freeze + CGB tilemap attrs/banks + DMG quick classifier\"."
    status: pending
    dependencies:
      - 0499-t8-create-report
---

# Step 0499: Fix pygame window freeze + CGB tilemap attrs/banks + DMG quick classifier

## Contexto

**Steps 0495–0498** con estos hechos ya demostrados:

- **CGB**: el PPU genera FB_INDEX con señal y (tras Step 0495/0496) la conversión IDX→RGB funciona cuando se usa la ruta correcta (paletas CGB, BGR555→RGB888 ok).

- **Renderer/present**: en rom_smoke originalmente no había renderer; se añadió renderer headless y trazas CRC/frame_id. En UI se vio que a partir de ciertos frames hay NonWhite en FB_PRESENT_SRC.

- **Freeze "no responde"**: existe evidencia visual (captura) de que cuando `rom_smoke_0442.py` crea ventana/renderer en modo windowed, la app se queda "no responde" por falta de event pumping/loop de eventos (pygame/SDL).

**Estado actual (problema real)**:

- Muchos juegos (Mario, Pokémon, Zelda…) siguen en blanco o negro.
- Tetris DX llega a mostrar "tiles basura" (señal parcial pero render incorrecto).
- rom_smoke/renderer puede provocar "no responde" si se abre ventana y no se bombean eventos.

## Objetivo del Step 0499 (Prioridad en Orden)

**Objetivo A (bloqueante)**: que rom_smoke con renderer (windowed o headless) no cuelgue la ventana ni dispare "no responde".

**Objetivo B**: resolver el garbage rendering CGB (mínimo viable: leer tilemap/attrs/bank correctamente) usando tetris_dx.gbc como ROM de validación.

**Objetivo C**: mejorar diagnóstico del DMG en blanco (sin asumir que es PPU). Necesitamos una prueba rápida para saber si el juego:

- no progresa (CPU/IRQ/ROM mapping/MBC), o
- progresa pero dibuja blanco (BGP/tiles/VRAM), o
- progresa pero el render no llega a pantalla.

## Alcance Estricto (Evitar Dispersión)

**Este step NO debe meterse a arreglar "todo Pokémon" completo** si implica MBC/RTC/sonido/etc.

**Se busca una causa raíz demostrable + fix mínimo para**:

- freeze (A)
- CGB garbage (B)
- y para DMG (C) solo dejar instrumentación que diga "qué falla", no arreglar todo DMG salvo que sea obvio y pequeño.

## Fase A: "rom_smoke/pygame no responde" (Windowed Safety)

### A1) Repro Controlada

**Crear un modo reproducible**:

- Ejecutar `rom_smoke_0442.py` con `--use-renderer-headless` (debe ir bien)
- Ejecutar otro modo que cree ventana real (si existe) o forzar `SDL_VIDEODRIVER` normal para ver si aparece el "no responde".

**Archivo**: `tools/rom_smoke_0442.py`

**Añadir modo windowed opcional**:

```python
# En rom_smoke_0442.py, clase ROMSmokeRunner
def __init__(self, use_renderer_headless: bool = False, use_renderer_windowed: bool = False):
    self.use_renderer_headless = use_renderer_headless
    self.use_renderer_windowed = use_renderer_windowed
    
    # Si windowed, forzar SDL_VIDEODRIVER normal (no dummy)
    if self.use_renderer_windowed:
        os.environ.pop('SDL_VIDEODRIVER', None)  # Quitar dummy si existe
        os.environ.pop('VIBOY_HEADLESS', None)   # Quitar headless si existe
```

**Añadir argumento CLI**:

```python
# En rom_smoke_0442.py, función main()
parser.add_argument('--use-renderer-windowed', action='store_true',
                    help='Use windowed renderer (for testing event pumping)')
```

**Entrega**: un log corto que muestre que en windowed se están procesando eventos (aunque no haya interacción).

### A2) Fix Mínimo

**Implementar un contrato claro**:

**Si hay ventana (screen real) → hay que bombear eventos cada frame** (`pygame.event.pump` o loop QUIT).

**Si headless/dummy → NO llamar a cosas que bloqueen** (ya hubo fixes parciales), pero asegurar que la lógica no deja recursos a medias.

**Archivo**: `src/gpu/renderer.py`

**Modificar `render_frame()` para bombear eventos en modo windowed**:

```python
# En renderer.py, método render_frame()
# Detectar si hay ventana real
has_window = hasattr(self, 'screen') and self.screen is not None

if has_window:
    # Modo windowed: bombear eventos cada frame para evitar "no responde"
    pygame.event.pump()  # Procesar eventos del sistema (no bloquea)
    
    # Verificar eventos QUIT (opcional, pero útil para debugging)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            print("[Renderer] QUIT event recibido")
            # No hacer nada, solo loggear (rom_smoke controla el loop)
    
    # Logging limitado
    if not hasattr(self, '_event_pump_log_count'):
        self._event_pump_log_count = 0
    
    if self._event_pump_log_count < 20:
        self._event_pump_log_count += 1
        print(f"[Renderer-EventPump] Frame {frame_number} | Event pump activo (windowed mode)")
```

**Asegurar que headless no llama a funciones que bloqueen**:

```python
# En renderer.py, método render_frame()
is_headless = not hasattr(self, 'screen') or self.screen is None

if is_headless:
    # Modo headless: NO llamar a pygame.event (ya protegido en código existente)
    # ... código existente ...
else:
    # Modo windowed: bombear eventos
    pygame.event.pump()
```

### A3) Criterio de Aceptación A

**En modo windowed (si se usa) NO debe aparecer el diálogo de "no responde"**.

**rom_smoke debe terminar los frames objetivo sin intervención manual**.

**En headless/dummy sigue estable**.

**Evidencia requerida**:

- Log con contador "frames procesados" + confirmación de `event_pump` activo SOLO cuando corresponde.
- Si existe un flag nuevo, documentarlo.

## Fase B: CGB Garbage (tetris_dx.gbc)

**La captura muestra señal "tipo mosaico basura"**: esto huele a tilemap/attr/bank incorrecto, típico error en CGB:

- leer tile_id desde el banco equivocado,
- ignorar atributos de tilemap (bank 1),
- usar mal el bit de VRAM bank (attr bit3),
- o mezclar 8800 signed/8000 unsigned.

### B1) Auditoría Dirigida (NO Código Aún)

**Localizar en PPU (ruta de background) exactamente**:

**Archivo**: `src/core/cpp/PPU.cpp`

**Revisar `render_bg()` o `render_scanline()` donde se lee el tilemap**:

1. **Dónde se calcula tilemap_addr**
2. **De qué banco se lee tile_id** (debe ser bank 0 siempre)
3. **Si en CGB se lee attr (bank 1) o no**
4. **Cómo se decide bank para tiledata bytes** (debe ser attr bit3)
5. **Si se respeta LCDC bit4 (8000 vs 8800 signed)**

**Código actual** (líneas 3056-3073):

```cpp
// --- Step 0389: CGB BG Map Attributes ---
uint16_t tile_map_offset = tile_map_addr - 0x8000;
uint8_t tile_attr = mmu_->read_vram_bank(1, tile_map_offset);  // Leer atributo desde bank 1
uint8_t tile_bank = (tile_attr >> 3) & 0x01;  // Bit 3: banco del tile pattern
```

**Verificar que tile_id se lee de bank 0**:

```cpp
// Debe ser:
uint8_t tile_id = mmu_->read_vram_bank(0, tile_map_offset);  // Bank 0 para tile_id
```

**Entrega**: mini-checklist en comentario del PR o reporte interno ("antes: tile_id se leía con bank=X, debería ser bank0 siempre").

### B2) Fix Mínimo CGB Tilemap/Attrs (Lo Mínimo para que Deje de Ser Basura)

**Implementar comportamiento correcto (mínimo viable)**:

**En CGB real y NO dmg_compat_mode**:

- tile_id debe leerse de VRAM bank 0 en tilemap.
- attr debe leerse de VRAM bank 1 en la misma dirección.
- bank de tiledata se elige con attr bit3.
- (ideal pero opcional si no rompe) aplicar xflip/yflip y palette bits.

**En DMG o dmg_compat_mode**: seguir ruta DMG sin attrs.

**Archivo**: `src/core/cpp/PPU.cpp`

**Modificar `render_bg()` o donde se lee tilemap**:

```cpp
// En PPU.cpp, método render_bg() o render_scanline()
// Detectar modo CGB
bool is_cgb = (hardware_mode_ == HardwareMode::CGB);
bool dmg_compat_mode = false;
if (is_cgb) {
    uint8_t lcdc = mmu_->read(IO_LCDC);
    dmg_compat_mode = (lcdc & 0x01) == 0;  // LCD OFF = modo compatibilidad DMG
}

// Calcular tilemap_addr (ya existe)
uint16_t tile_map_addr = tile_map_base + tile_map_offset;

// Leer tile_id y attr
uint16_t tile_map_offset_vram = tile_map_addr - 0x8000;  // Offset desde 0x8000

if (is_cgb && !dmg_compat_mode) {
    // CGB real: leer tile_id de bank 0, attr de bank 1
    uint8_t tile_id = mmu_->read_vram_bank(0, tile_map_offset_vram);  // Bank 0 para tile_id
    uint8_t tile_attr = mmu_->read_vram_bank(1, tile_map_offset_vram);  // Bank 1 para attr
    
    // Extraer bits del attr
    uint8_t tile_bank = (tile_attr >> 3) & 0x01;  // Bit 3: banco del tile pattern
    uint8_t palette_id = tile_attr & 0x07;        // Bits 0-2: paleta CGB
    bool xflip = (tile_attr & 0x20) != 0;          // Bit 5: flip horizontal
    bool yflip = (tile_attr & 0x40) != 0;          // Bit 6: flip vertical
    bool priority = (tile_attr & 0x80) != 0;       // Bit 7: prioridad BG
    
    // Leer tiledata desde el banco correcto
    uint16_t tile_data_addr = tile_data_base + (tile_id * 16);
    uint8_t byte1 = mmu_->read_vram_bank(tile_bank, tile_data_addr - 0x8000 + line_in_tile * 2);
    uint8_t byte2 = mmu_->read_vram_bank(tile_bank, tile_data_addr - 0x8000 + line_in_tile * 2 + 1);
    
    // Aplicar flips si es necesario
    if (xflip) {
        // Invertir bits horizontalmente
        // ... implementar flip horizontal ...
    }
    if (yflip) {
        // Invertir línea verticalmente
        line_in_tile = 7 - line_in_tile;
    }
} else {
    // DMG o dmg_compat_mode: ruta DMG sin attrs
    uint8_t tile_id = mmu_->read_vram_bank(0, tile_map_offset_vram);  // Bank 0 siempre en DMG
    // ... resto del código DMG ...
}
```

**Verificar que se respeta LCDC bit4 (8000 vs 8800 signed)**:

```cpp
// En PPU.cpp, donde se calcula tile_data_base
uint8_t lcdc = mmu_->read(IO_LCDC);
bool unsigned_addressing = (lcdc & 0x10) != 0;  // Bit 4: 0=signed (8800), 1=unsigned (8000)
uint16_t tile_data_base = unsigned_addressing ? 0x8000 : 0x9000;
```

### B3) Criterio de Aceptación B (Medible)

**En tetris_dx.gbc, los dumps o la ventana deben pasar de "ruido caótico" a algo estructurado** (logo/pantalla reconocible o al menos coherente).

**IdxNonZero > 0 y RgbNonWhite > 0 se mantienen**.

**Si se usa renderer, PresentNonWhite debe volverse >0 en un rango razonable de frames** (no necesariamente en 600).

**Evidencia requerida**:

- 2–3 dumps PPM "antes vs después" en el mismo frame_id (usa el sistema de dumps por frame_id ya existente).
- Un snapshot PixelProof y/o ThreeBufferStats confirmando que RGB no es blanco y no es puro ruido (CRC cambia, Unique>1).

## Fase C: DMG Blanco - Diagnóstico Rápido Sin Suposiciones

**Tetris.gb en DMG llevaba a loop/espera en steps previos, pero ahora ya se probó que VBlank IRQ se toma. Aun así, muchos DMG siguen blancos**.

**Aquí NO quiero un "arreglo grande". Quiero una clasificación automática en runtime para DMG**, tipo:

- CPU no progresa / se queda en loop duro
- progresa pero LCDC OFF
- progresa, LCDC ON, pero VRAM tiledata se queda en cero
- progresa, hay tiledata no-zero, pero fetch o render no lo usa
- progresa, produce IDX no-zero, pero RGB/present falla

### C1) Añadir "DMG Quick Classifier" al Snapshot (Ligero)

**Archivo**: `tools/rom_smoke_0442.py`

**Reusar métricas ya existentes y agregar solo lo imprescindible**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
def _classify_dmg_quick(self, ppu, mmu, renderer=None):
    """Clasifica rápidamente el estado DMG para diagnóstico."""
    
    # Obtener métricas existentes
    three_buf_stats = ppu.get_three_buffer_stats()
    lcdc = mmu.read(0xFF40)
    lcd_on = (lcdc & 0x80) != 0
    
    # VRAM stats (ya existe)
    vram_write_stats = mmu.get_vram_write_stats()
    
    # PC hotspots (ya existe)
    after_clear = snapshot.get('AfterClear', {})
    pc_hotspot_1 = after_clear.get('pc_hotspots_top3', [])
    
    # Contadores de writes a registros críticos (añadir si no existen)
    # ... obtener de MMU si existe tracking ...
    
    # Clasificar
    classification = "UNKNOWN"
    details = {}
    
    # 1. CPU no progresa / se queda en loop duro
    if pc_hotspot_1 and len(pc_hotspot_1) > 0:
        hotspot_pc, hotspot_count = pc_hotspot_1[0]
        if hotspot_count > 100000:  # Loop duro
            classification = "CPU_LOOP"
            details['hotspot_pc'] = f'0x{hotspot_pc:04X}'
            details['hotspot_count'] = hotspot_count
            return classification, details
    
    # 2. Progresa pero LCDC OFF
    if not lcd_on:
        classification = "LCDC_OFF"
        details['lcdc'] = f'0x{lcdc:02X}'
        return classification, details
    
    # 3. Progresa, LCDC ON, pero VRAM tiledata se queda en cero
    if vram_write_stats:
        tiledata_nonzero = vram_write_stats.get('tiledata_nonzero_bank0', 0)
        if tiledata_nonzero == 0:
            classification = "VRAM_TILEDATA_ZERO"
            details['tiledata_nonzero'] = 0
            return classification, details
    
    # 4. Progresa, hay tiledata no-zero, pero fetch o render no lo usa
    if three_buf_stats:
        idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
        if idx_nonzero == 0:
            classification = "IDX_ZERO_DESPITE_TILEDATA"
            details['idx_nonzero'] = 0
            if vram_write_stats:
                details['tiledata_nonzero'] = vram_write_stats.get('tiledata_nonzero_bank0', 0)
            return classification, details
    
    # 5. Progresa, produce IDX no-zero, pero RGB/present falla
    if three_buf_stats:
        idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
        rgb_nonwhite = three_buf_stats.get('rgb_nonwhite_count', 0)
        if idx_nonzero > 0 and rgb_nonwhite == 0:
            classification = "RGB_FAIL_DESPITE_IDX"
            details['idx_nonzero'] = idx_nonzero
            details['rgb_nonwhite'] = rgb_nonwhite
            return classification, details
    
    # 6. Todo parece OK (pero sigue blanco - puede ser timing/init)
    classification = "OK_BUT_WHITE"
    details['lcdc'] = f'0x{lcdc:02X}'
    if three_buf_stats:
        details['idx_nonzero'] = three_buf_stats.get('idx_nonzero', 0)
        details['rgb_nonwhite'] = three_buf_stats.get('rgb_nonwhite_count', 0)
    
    return classification, details
```

**Añadir al snapshot**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
# Solo para DMG (no CGB)
if not is_cgb:
    dmg_classification, dmg_details = self._classify_dmg_quick(self._ppu, self._mmu, self._renderer)
    snapshot['DMGQuickClassifier'] = {
        'classification': dmg_classification,
        'details': dmg_details,
    }
```

### C2) Criterio de Aceptación C

**Para tetris.gb y 1 ROM DMG extra** (p. ej. pokemon red), el snapshot final debe dar una clasificación inequívoca (aunque sea "CPU_LOOP" o "LCDC_OFF").

## Fase D: Ejecución / Validación

### D1) CGB: tetris_dx.gbc

**Correr**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DEBUG_CGB_PALETTE_WRITES=1
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 1200 --use-renderer-headless | tee /tmp/viboy_0499_tetris_dx.log
```

**Frames suficientes para pasar el "first signal" y ver estabilidad**.

**Guardar logs a archivo** (regla del proyecto) + dumps por frame_id en /tmp.

### D2) DMG: tetris.gb + 1 ROM DMG Adicional

**Correr con rom_smoke** (sin renderer si no hace falta) y generar el snapshot con el clasificador.

**Comando**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 3000 | tee /tmp/viboy_0499_tetris_dmg.log
```

**Entrega**:

- Un resumen de 10 líneas por ROM con la clasificación final + métricas clave.

## Fase E: Documentación + Git

### E1) Generar Reporte

**Archivo**: `docs/reports/reporte_step0499.md`

**Debe incluir**:

1. **Fase A (Freeze Fix)**:

   - Log con contador "frames procesados" + confirmación de event_pump activo
   - Evidencia de que windowed no dispara "no responde"

2. **Fase B (CGB Garbage Fix)**:

   - Auditoría: checklist de qué se corrigió (tile_id bank, attr bank, tile_bank selection)
   - Dumps "antes vs después" (2-3 PPM en mismo frame_id)
   - PixelProof y/o ThreeBufferStats confirmando RGB no es ruido

3. **Fase C (DMG Quick Classifier)**:

   - Tabla: ROM | Clasificación | Detalles
   - Resumen de 10 líneas por ROM

### E2) Bitácora HTML

**Archivo**: `docs/bitacora/entries/YYYY-MM-DD__0499__fix-pygame-freeze-cgb-tilemap-dmg-classifier.html`

**⚠️ CRÍTICO: Usar fecha correcta (2026, no 2025)**.

### E3) Actualizar

- `docs/bitacora/index.html`
- `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o donde corresponda)
- `docs/informe_fase_2/index.md` si aplica

### E4) Commit + Push

**Mensaje claro**:

```
feat(diag): Step 0499 - Fix pygame window freeze + CGB tilemap attrs/banks + DMG quick classifier
```

## Criterios de Éxito

1. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0499.md` completo SIN placeholders**:

   - Fase A: Log con event_pump activo, evidencia de que windowed no dispara "no responde"
   - Fase B: Auditoría + dumps antes/después + PixelProof/ThreeBufferStats
   - Fase C: Tabla con clasificación DMG para 2 ROMs

2. **⚠️ CRÍTICO: Fase A ejecutada** - windowed no dispara "no responde"

3. **⚠️ CRÍTICO: Fase B ejecutada** - tetris_dx.gbc deja de verse como "basura"

4. **Fase C ejecutada** - DMG quick classifier funcionando con 2 ROMs

5. **Bitácora/informe actualizados** con evidencia y conclusión específica, **fechas correctas (2026)**

6. **Commit/push** con mensaje claro

## Notas Técnicas (Para Guiar al Ejecutor Sin "Adivinar")

- **El "no responde" casi siempre es event loop**: si hay ventana y no llamas a pump/get, el WM marca la app como colgada.

- **El "garbage CGB" suele ser tile_id leído del banco equivocado o attrs ignoradas**: en CGB tilemap bank0=tile#, bank1=attrs.

- **No mezclar responsabilidades**: PPU produce buffers; renderer presenta. Si rom_smoke crea renderer, debe mantenerlo vivo sin bloquear.

## Entregables Mínimos al Final del Step

1. **Confirmación de que rom_smoke con renderer NO dispara "no responde" en windowed** (o alternativa: forzar dummy y no crear ventana nunca, pero entonces documentarlo).

2. **tetris_dx.gbc deja de verse como "basura"** (evidencia con dumps antes/después).

3. **DMG quick classifier funcionando con 2 ROMs**, con resultado claro.

**Si me pegas la respuesta del agente ejecutor (lo que cambió, resultados y métricas), te doy el siguiente prompt para el planificador (Step 0500) ya enfocado a lo que quede vivo (probablemente MBC/boot/IRQ vectors o STAT/timing)**.