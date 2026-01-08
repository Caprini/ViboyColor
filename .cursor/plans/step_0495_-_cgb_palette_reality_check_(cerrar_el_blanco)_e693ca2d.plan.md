---
name: Step 0495 - CGB Palette Reality Check (cerrar el blanco)
overview: "Step 0494 mostró: CGB (tetris_dx.gbc) - IdxNonZero=22910 (PPU genera señal), RgbNonWhite=0 (índice→RGB devuelve blanco), BGPD_Writes=0/OBPD_Writes=0 a pesar de ejecutar con VIBOY_DEBUG_CGB_PALETTE_WRITES=1. Esto solo puede ser: (1) No estás realmente en modo CGB, (2) Decode de IO para FF68–FF6B no se ejecuta/filtra, o (3) convert_framebuffer_to_rgb usa fuente equivocada. Este step: convertir el caso \"IdxNonZero>0 pero RgbNonWhite=0\" en un diagnóstico cerrable y un fix mínimo que haga RgbNonWhite>0 en tetris_dx.gbc (frame 600)."
todos:
  - id: 0495-t1-cgb-detection-snapshot
    content: "Añadir campos de CGB detection al snapshot en rom_smoke_0442.py: rom_header_cgb_flag (byte 0x0143), machine_is_cgb (flag interno real), boot_mode/dmg_compat_mode. Añadir getters en MMU.hpp/MMU.cpp para get_hardware_mode() y get_dmg_compat_mode(). Exponer vía Cython en mmu.pyx."
    status: pending
  - id: 0495-t2-io-watch-ff68-ff6b
    content: "Implementar IO Watch duro para FF68–FF6B en MMU.hpp/MMU.cpp: estructura IOWatchFF68FF6B con contadores de writes/reads y últimos PCs/valores para BGPI/BGPD/OBPI/OBPD. Actualizar en MMU::write() y MMU::read() cuando se accede a FF68–FF6B. Exponer vía Cython e integrar en snapshot."
    status: pending
  - id: 0495-t3-palette-ram-dump
    content: "Añadir dump compacto del contenido real de la RAM de paletas al snapshot: bg_palette_bytes[0:32] y obj_palette_bytes[0:32] (hex compactado), bg_palette_nonwhite_entries y obj_palette_nonwhite_entries. Añadir getter read_obj_palette_data() en MMU si no existe."
    status: pending
    dependencies:
      - 0495-t2-io-watch-ff68-ff6b
  - id: 0495-t4-pixel-proof
    content: "Añadir microdebug controlado (solo 5 píxeles) al snapshot: buscar 5 posiciones con idx!=0 dentro de FB_INDEX, para cada una mostrar (x, y, idx, palette_used, raw_15bit_color, rgb888_result). Esto demuestra qué está pasando en índice→RGB."
    status: pending
    dependencies:
      - 0495-t3-palette-ram-dump
  - id: 0495-t5-execute-cgb
    content: Ejecutar rom_smoke para tetris_dx.gbc (1200 frames) con VIBOY_DEBUG_CGB_PALETTE_WRITES=1, VIBOY_DEBUG_PRESENT_TRACE=1, VIBOY_DUMP_RGB_FRAME=600. Extraer snapshots con todas las métricas (CGBDetection, IOWatchFF68FF6B, CGBPaletteRAM, PixelProof).
    status: pending
    dependencies:
      - 0495-t1-cgb-detection-snapshot
      - 0495-t4-pixel-proof
  - id: 0495-t6-fix-case1
    content: "Si Caso 1 (machine_is_cgb==0): forzar modo CGB para ROMs con flag CGB, corregir detección/boot path en MMU::load_rom() o Viboy::load_cartridge()."
    status: pending
    dependencies:
      - 0495-t5-execute-cgb
  - id: 0495-t7-fix-case2
    content: "Si Caso 2 (machine_is_cgb==1 pero io_watch_bgpd_writes==0): arreglar el routing en MMU::write() para FF68–FF6B (no debe ignorarse ni depender de gates erróneos). Verificar que los writes se ejecutan correctamente."
    status: pending
    dependencies:
      - 0495-t5-execute-cgb
  - id: 0495-t8-fix-case3
    content: "Si Caso 3 (hay writes y paleta tiene nonwhite pero RGB sigue blanco): arreglar convert_framebuffer_to_rgb() en PPU.cpp para leer paleta correcta, aplicar selección de paleta (aunque sea palette 0 inicialmente), decode correcto de BGR555."
    status: pending
    dependencies:
      - 0495-t5-execute-cgb
  - id: 0495-t9-validate
    content: "Re-ejecutar rom_smoke tetris_dx.gbc 1200 frames con fixes aplicados. Criterio final: en frame 600, IdxNonZero>0 y RgbNonWhite>0 (y PresentNonWhite>0 si hay renderer)."
    status: pending
    dependencies:
      - 0495-t6-fix-case1
      - 0495-t7-fix-case2
      - 0495-t8-fix-case3
  - id: 0495-t10-create-report
    content: "Crear reporte markdown docs/reports/reporte_step0495.md con: CGB Detection (rom_header_cgb_flag, machine_is_cgb, diagnóstico), IO Watch FF68–FF6B (write/read counts, últimos PCs/valores, diagnóstico), CGB Palette RAM Dump (hex compactado, nonwhite_entries, diagnóstico), Pixel Proof (5 píxeles con todos los campos, diagnóstico), fix aplicado (si lo hay) y re-ejecución. NO placeholders."
    status: pending
    dependencies:
      - 0495-t9-validate
  - id: 0495-t11-document
    content: "Documentar Step 0495 en bitácora HTML e informe dividido. Framing: CGB palette reality check (cerrar el blanco). Incluir evidencia (CGB detection, IO watch, palette RAM dump, pixel proof), conclusión específica (caso identificado, fix aplicado), siguiente paso. Update docs/bitacora/index.html y docs/informe_fase_2/. Commit/push con mensaje \"feat(diag): Step 0495 - CGB palette reality check (cerrar el blanco)\"."
    status: pending
    dependencies:
      - 0495-t10-create-report
---

# Step 0495: CGB Palette Reality Check (Cerrar el Blanco)

## Contexto

**Step 0494 completado**. Resultados actuales:

- **CGB (tetris_dx.gbc)**:
  - `IdxNonZero=22910` ✅ (PPU genera señal - índices 1..3)
  - `RgbNonWhite=0` ❌ (índice→RGB devuelve blanco siempre)
  - `BGPD_Writes=0/OBPD_Writes=0` ❌ (a pesar de ejecutar con `VIBOY_DEBUG_CGB_PALETTE_WRITES=1`)

**Problema**: Esto solo puede ser una de estas tres cosas (y hay que probar cuál, no adivinar):

1. **No estás realmente en modo CGB** (o tu "is_cgb"/detección está mal), por eso nunca entran los writes a FF68–FF6B.
2. Sí estás en CGB, pero tu decode de IO para FF68–FF6B no se ejecuta / se filtra, o tu contador está mal conectado.
3. Sí se escribe paleta, pero tu `convert_framebuffer_to_rgb` está usando la fuente equivocada (DMG/CGB mezclado, paleta siempre 0x7FFF, o decode BGR555 roto) y termina en blanco.

## Objetivo Step 0495

Convertir el caso "IdxNonZero>0 pero RgbNonWhite=0" en un diagnóstico cerrable y un fix mínimo que haga `RgbNonWhite>0` en tetris_dx.gbc (frame 600) y, idealmente, ya se vea algo en ventana.

## Fase A: Probar que Realmente Estás en CGB (No Suposiciones)

### A1) Añadir Campos de CGB Detection al Snapshot

**Archivo**: `tools/rom_smoke_0442.py`

**En `generate_snapshot()`, añadir campos**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
# Obtener ROM header CGB flag (byte 0x0143)
rom_header_cgb_flag = None
if hasattr(self, '_cartridge') and self._cartridge is not None:
    # Leer byte 0x0143 desde ROM
    try:
        rom_header_cgb_flag = self._cartridge.read_byte(0x0143)
    except:
        pass

# Obtener machine_is_cgb (flag interno real del emulador)
machine_is_cgb = 0
if hasattr(self, '_mmu') and self._mmu is not None:
    # Verificar hardware mode desde MMU
    hardware_mode = self._mmu.get_hardware_mode()  # Necesitar getter
    machine_is_cgb = 1 if hardware_mode == "CGB" else 0

# Obtener boot_mode / dmg_compat_mode si existe
boot_mode = None
dmg_compat_mode = None
if hasattr(self, '_mmu') and self._mmu is not None:
    # Verificar si está en modo compatibilidad DMG
    dmg_compat_mode = self._mmu.get_dmg_compat_mode()  # Necesitar getter

snapshot['CGBDetection'] = {
    'rom_header_cgb_flag': rom_header_cgb_flag,  # Byte 0x0143
    'machine_is_cgb': machine_is_cgb,  # Flag interno real
    'boot_mode': boot_mode,  # Si existe
    'dmg_compat_mode': dmg_compat_mode,  # Si existe
}
```

**Archivo**: `src/core/cpp/MMU.hpp` y `src/core/cpp/MMU.cpp`

**Añadir getters para hardware mode y dmg_compat_mode**:

```cpp
// En MMU.hpp
enum class HardwareMode {
    DMG,
    CGB,
};

HardwareMode get_hardware_mode() const;
bool get_dmg_compat_mode() const;  // Si está en modo compatibilidad DMG dentro de CGB

// En MMU.cpp
HardwareMode MMU::get_hardware_mode() const {
    return hardware_mode_;
}

bool MMU::get_dmg_compat_mode() const {
    // Verificar si está en modo compatibilidad DMG (LCDC bit 0 = 0)
    uint8_t lcdc = memory_[0xFF40];
    return (lcdc & 0x01) == 0;  // LCD OFF = modo compatibilidad DMG
}
```

**Exponer vía Cython**:

```cython
# En mmu.pyx
cdef class PyMMU:
    def get_hardware_mode(self):
        """Obtiene el modo hardware (DMG o CGB)."""
        if self._mmu == NULL:
            return None
        
        cdef HardwareMode mode = self._mmu.get_hardware_mode()
        return "CGB" if mode == HardwareMode.CGB else "DMG"
    
    def get_dmg_compat_mode(self):
        """Obtiene si está en modo compatibilidad DMG."""
        if self._mmu == NULL:
            return None
        
        return self._mmu.get_dmg_compat_mode()
```

### A2) Criterio de Aceptación A

**Para `tetris_dx.gbc`**: `machine_is_cgb==1`.

- Si sale 0, ya sabes el bug: estás corriendo el .gbc como DMG.

## Fase B: IO Watch Duro para FF68–FF6B (No Solo "Palette Writes Stats")

### B1) Implementar Contadores + Último PC para FF68–FF6B

**Archivo**: `src/core/cpp/MMU.hpp` y `src/core/cpp/MMU.cpp`

**Añadir estructura de tracking**:

```cpp
// En MMU.hpp
struct IOWatchFF68FF6B {
    // Writes
    uint32_t bgpi_writes;
    uint32_t bgpd_writes;
    uint32_t obpi_writes;
    uint32_t obpd_writes;
    
    uint16_t last_bgpi_write_pc;
    uint8_t last_bgpi_write_value;
    
    uint16_t last_bgpd_write_pc;
    uint8_t last_bgpd_write_value;
    
    uint16_t last_obpi_write_pc;
    uint8_t last_obpi_write_value;
    
    uint16_t last_obpd_write_pc;
    uint8_t last_obpd_write_value;
    
    // Reads (por si hay lectura/auto-inc)
    uint32_t bgpi_reads;
    uint32_t bgpd_reads;
    uint32_t obpi_reads;
    uint32_t obpd_reads;
    
    uint16_t last_bgpi_read_pc;
    uint8_t last_bgpi_read_value;
    
    uint16_t last_bgpd_read_pc;
    uint8_t last_bgpd_read_value;
    
    uint16_t last_obpi_read_pc;
    uint8_t last_obpi_read_value;
    
    uint16_t last_obpd_read_pc;
    uint8_t last_obpd_read_value;
};

IOWatchFF68FF6B io_watch_ff68_ff6b_;
```

**En `MMU::write()`, cuando se escribe a FF68–FF6B**:

```cpp
// En MMU.cpp, método write()
if (addr == 0xFF68) {  // BGPI
    io_watch_ff68_ff6b_.bgpi_writes++;
    io_watch_ff68_ff6b_.last_bgpi_write_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_bgpi_write_value = value;
    // ... código existente de escritura ...
}

if (addr == 0xFF69) {  // BGPD
    io_watch_ff68_ff6b_.bgpd_writes++;
    io_watch_ff68_ff6b_.last_bgpd_write_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_bgpd_write_value = value;
    // ... código existente de escritura ...
}

if (addr == 0xFF6A) {  // OBPI
    io_watch_ff68_ff6b_.obpi_writes++;
    io_watch_ff68_ff6b_.last_obpi_write_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_obpi_write_value = value;
    // ... código existente de escritura ...
}

if (addr == 0xFF6B) {  // OBPD
    io_watch_ff68_ff6b_.obpd_writes++;
    io_watch_ff68_ff6b_.last_obpd_write_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_obpd_write_value = value;
    // ... código existente de escritura ...
}
```

**En `MMU::read()`, cuando se lee de FF68–FF6B**:

```cpp
// En MMU.cpp, método read()
if (addr == 0xFF68) {  // BGPI
    io_watch_ff68_ff6b_.bgpi_reads++;
    io_watch_ff68_ff6b_.last_bgpi_read_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_bgpi_read_value = memory_[addr];
}

if (addr == 0xFF69) {  // BGPD
    io_watch_ff68_ff6b_.bgpd_reads++;
    io_watch_ff68_ff6b_.last_bgpd_read_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_bgpd_read_value = memory_[addr];
}

if (addr == 0xFF6A) {  // OBPI
    io_watch_ff68_ff6b_.obpi_reads++;
    io_watch_ff68_ff6b_.last_obpi_read_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_obpi_read_value = memory_[addr];
}

if (addr == 0xFF6B) {  // OBPD
    io_watch_ff68_ff6b_.obpd_reads++;
    io_watch_ff68_ff6b_.last_obpd_read_pc = debug_current_pc;
    io_watch_ff68_ff6b_.last_obpd_read_value = memory_[addr];
}
```

**Exponer vía Cython**:

```cython
# En mmu.pyx
cdef class PyMMU:
    def get_io_watch_ff68_ff6b(self):
        """Obtiene tracking de IO para FF68–FF6B."""
        if self._mmu == NULL:
            return None
        
        cdef IOWatchFF68FF6B watch = self._mmu.get_io_watch_ff68_ff6b()
        return {
            'bgpi_writes': watch.bgpi_writes,
            'bgpd_writes': watch.bgpd_writes,
            'obpi_writes': watch.obpi_writes,
            'obpd_writes': watch.obpd_writes,
            'last_bgpi_write_pc': watch.last_bgpi_write_pc,
            'last_bgpi_write_value': watch.last_bgpi_write_value,
            'last_bgpd_write_pc': watch.last_bgpd_write_pc,
            'last_bgpd_write_value': watch.last_bgpd_write_value,
            'last_obpi_write_pc': watch.last_obpi_write_pc,
            'last_obpi_write_value': watch.last_obpi_write_value,
            'last_obpd_write_pc': watch.last_obpd_write_pc,
            'last_obpd_write_value': watch.last_obpd_write_value,
            'bgpi_reads': watch.bgpi_reads,
            'bgpd_reads': watch.bgpd_reads,
            'obpi_reads': watch.obpi_reads,
            'obpd_reads': watch.obpd_reads,
            'last_bgpi_read_pc': watch.last_bgpi_read_pc,
            'last_bgpi_read_value': watch.last_bgpi_read_value,
            'last_bgpd_read_pc': watch.last_bgpd_read_pc,
            'last_bgpd_read_value': watch.last_bgpd_read_value,
            'last_obpi_read_pc': watch.last_obpi_read_pc,
            'last_obpi_read_value': watch.last_obpi_read_value,
            'last_obpd_read_pc': watch.last_obpd_read_pc,
            'last_obpd_read_value': watch.last_obpd_read_value,
        }
```

**Integrar en snapshot**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
io_watch = self.mmu.get_io_watch_ff68_ff6b()
if io_watch:
    snapshot['IOWatchFF68FF6B'] = io_watch
```

### B2) Criterio de Aceptación B

**En tetris_dx.gbc, en 1200 frames**: **BGPD u OBPD writes > 0**.

- Si sigue 0, el problema está en el decode del MMU o en "no CGB".

## Fase C: Dump Compacto del Contenido Real de la RAM de Paletas

### C1) Añadir Dump de Paletas al Snapshot

**Archivo**: `tools/rom_smoke_0442.py`

**En `generate_snapshot()`, añadir dump compacto**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
# Dump compacto del contenido real de la RAM de paletas
bg_palette_bytes = []
obj_palette_bytes = []

if hasattr(self, '_mmu') and self._mmu is not None:
    # Leer primeros 32 bytes de BG palette RAM (0x40 bytes total, pero dump 32)
    for i in range(32):
        bg_palette_bytes.append(self._mmu.read_bg_palette_data(i))
    
    # Leer primeros 32 bytes de OBJ palette RAM
    for i in range(32):
        obj_palette_bytes.append(self._mmu.read_obj_palette_data(i))  # Necesitar getter
    
    # Contar nonwhite entries (entries != 0x7FFF)
    bg_palette_nonwhite_entries = 0
    for palette_id in range(8):
        for color_idx in range(4):
            base = palette_id * 8 + color_idx * 2
            lo = self._mmu.read_bg_palette_data(base)
            hi = self._mmu.read_bg_palette_data(base + 1)
            bgr555 = lo | (hi << 8)
            
            if bgr555 != 0x7FFF:  # No es blanco
                bg_palette_nonwhite_entries += 1
                break  # Solo contar una vez por paleta
    
    obj_palette_nonwhite_entries = 0
    for palette_id in range(8):
        for color_idx in range(4):
            base = palette_id * 8 + color_idx * 2
            lo = self._mmu.read_obj_palette_data(base)
            hi = self._mmu.read_obj_palette_data(base + 1)
            bgr555 = lo | (hi << 8)
            
            if bgr555 != 0x7FFF:  # No es blanco
                obj_palette_nonwhite_entries += 1
                break  # Solo contar una vez por paleta
    
    # Convertir a hex compactado
    bg_palette_hex = ''.join(f'{b:02X}' for b in bg_palette_bytes)
    obj_palette_hex = ''.join(f'{b:02X}' for b in obj_palette_bytes)
    
    snapshot['CGBPaletteRAM'] = {
        'bg_palette_bytes_hex': bg_palette_hex,  # Hex compactado
        'obj_palette_bytes_hex': obj_palette_hex,  # Hex compactado
        'bg_palette_nonwhite_entries': bg_palette_nonwhite_entries,
        'obj_palette_nonwhite_entries': obj_palette_nonwhite_entries,
    }
```

**Añadir getter para OBJ palette data**:

```cpp
// En MMU.hpp
uint8_t read_obj_palette_data(uint8_t index) const;

// En MMU.cpp
uint8_t MMU::read_obj_palette_data(uint8_t index) const {
    if (index >= 0x40) return 0xFF;
    return obj_palette_data_[index];
}
```

### C2) Criterio de Aceptación C

**Si hubo BGPD writes, el dump debe reflejar cambios** (`nonwhite_entries > 0` normalmente).

## Fase D: "Pixel Proof" - Demostrar Qué Está Pasando en Índice→RGB

### D1) Añadir Microdebug Controlado (Solo 5 Píxeles) al Snapshot

**Archivo**: `tools/rom_smoke_0442.py`

**En `generate_smoke()`, añadir pixel proof**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
# Pixel proof: demostrar qué está pasando en índice→RGB
pixel_proof = []

if hasattr(self, '_ppu') and self._ppu is not None:
    # Obtener framebuffer de índices
    fb_indices = self._ppu.get_presented_framebuffer_indices()
    
    if fb_indices is not None:
        # Buscar 5 posiciones con idx!=0 dentro de FB_INDEX
        found = 0
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                idx = fb_indices[y * SCREEN_WIDTH + x]
                if idx != 0 and found < 5:
                    # Para cada píxel: (x, y, idx, palette_used, raw_15bit_color, rgb888_result)
                    
                    # Leer índice de color
                    color_index = idx & 0x03
                    
                    # Calcular posición del tile en el tilemap (considerando scroll)
                    lcdc = self._mmu.read(0xFF40)
                    scx = self._mmu.read(0xFF43)
                    scy = self._mmu.read(0xFF42)
                    
                    tilemap_base = 0x9800 if (lcdc & 0x08) == 0 else 0x9C00
                    world_x = (x + scx) & 0xFF
                    world_y = (y + scy) & 0xFF
                    tile_x = world_x // 8
                    tile_y = world_y // 8
                    tilemap_offset = tile_y * 32 + tile_x
                    tilemap_addr = tilemap_base + tilemap_offset
                    
                    # Leer tile attributes de VRAM bank 1 (CGB)
                    attributes = self._mmu.read_vram_bank(1, tilemap_addr)
                    palette_id = attributes & 0x07
                    
                    # Leer color CGB (BGR555) de la paleta correcta
                    base = palette_id * 8 + color_index * 2
                    lo = self._mmu.read_bg_palette_data(base)
                    hi = self._mmu.read_bg_palette_data(base + 1)
                    raw_15bit_color = lo | (hi << 8)
                    
                    # Obtener RGB888 result (desde framebuffer RGB)
                    fb_rgb = self._ppu.get_framebuffer_rgb()
                    if fb_rgb is not None:
                        rgb_idx = (y * SCREEN_WIDTH + x) * 3
                        r = fb_rgb[rgb_idx]
                        g = fb_rgb[rgb_idx + 1]
                        b = fb_rgb[rgb_idx + 2]
                        rgb888_result = (r << 16) | (g << 8) | b
                    else:
                        rgb888_result = 0xFFFFFF  # Blanco por defecto
                    
                    pixel_proof.append({
                        'x': x,
                        'y': y,
                        'idx': idx,
                        'palette_used': palette_id,
                        'raw_15bit_color': f'0x{raw_15bit_color:04X}',
                        'rgb888_result': f'0x{rgb888_result:06X}',
                    })
                    
                    found += 1
                    if found >= 5:
                        break
            if found >= 5:
                break
        
        snapshot['PixelProof'] = pixel_proof
```

### D2) Criterio de Aceptación D

**Si `idx!=0` y `raw_15bit != 0x7FFF`, entonces `rgb888_result` NO puede ser blanco**.

## Fase E: Fix Mínimo (Solo Después de A–D)

### E1) Aplicar Fix Según el Caso que Salga

**Caso 1**: `machine_is_cgb==0` ⇒ forzar modo CGB para ROMs con flag CGB, corregir detección/boot path.

**Caso 2**: `machine_is_cgb==1` pero `io_watch_bgpd_writes==0` ⇒ arreglar el routing en `MMU::write()` para FF68–FF6B (no debe ignorarse ni depender de gates erróneos).

**Caso 3**: hay writes y paleta tiene nonwhite pero RGB sigue blanco ⇒ arreglar `convert_framebuffer_to_rgb()` para:

- leer paleta correcta,
- aplicar selección de paleta (aunque sea palette 0 inicialmente),
- decode correcto de BGR555.

## Fase F: Validación

### F1) Re-ejecutar rom_smoke tetris_dx.gbc 1200 frames

**Comando de ejecución**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_CGB_PALETTE_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=600
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_tetris_dx_rgb_f####.ppm
export VIBOY_DUMP_IDX_PATH=/tmp/viboy_tetris_dx_idx_f####.ppm
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 1200 | tee /tmp/viboy_0495_tetris_dx.log
```

### F2) Criterio Final

**En frame 600**:

- `IdxNonZero>0` ✅
- `RgbNonWhite>0` ✅
- Y si hay renderer activo, que `PresentNonWhite>0` ✅

## Fase G: Docs + Git

### G1) Generar Reporte

**Archivo**: `docs/reports/reporte_step0495.md`

**Debe incluir**:

1. **CGB Detection**:

   - `rom_header_cgb_flag` (byte 0x0143)
   - `machine_is_cgb` (flag interno real)
   - `boot_mode` / `dmg_compat_mode`
   - Diagnóstico: ¿estás en CGB de verdad?

2. **IO Watch FF68–FF6B**:

   - Write/read counts para BGPI/BGPD/OBPI/OBPD
   - Últimos PCs y valores
   - Diagnóstico: ¿se están viendo los writes de paletas?

3. **CGB Palette RAM Dump**:

   - `bg_palette_bytes_hex[0:32]` y `obj_palette_bytes_hex[0:32]`
   - `bg_palette_nonwhite_entries` y `obj_palette_nonwhite_entries`
   - Diagnóstico: ¿la paleta RAM tiene color?

4. **Pixel Proof**:

   - 5 píxeles con `idx!=0`: `(x, y, idx, palette_used, raw_15bit_color, rgb888_result)`
   - Diagnóstico: ¿qué color exacto sale de un pixel con idx!=0?

5. **Fix Aplicado** (si lo hay):

   - Descripción del fix según el caso identificado
   - Re-ejecución: resultados después del fix

### G2) Documentar

**Bitácora HTML nueva** (Step 0495), **index bitácora**, **informe dividido**, **commit/push**.

**Mensaje de commit**: `feat(diag): Step 0495 - CGB palette reality check (cerrar el blanco)`

## Criterios de Éxito

1. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0495.md` completo SIN placeholders**:

   - CGB Detection (rom_header_cgb_flag, machine_is_cgb, diagnóstico)
   - IO Watch FF68–FF6B (write/read counts, últimos PCs/valores, diagnóstico)
   - CGB Palette RAM Dump (hex compactado, nonwhite_entries, diagnóstico)
   - Pixel Proof (5 píxeles con todos los campos, diagnóstico)
   - Fix aplicado (si lo hay) y re-ejecución

2. **⚠️ CRÍTICO: CGB ejecutado** (1200 frames) con todas las métricas

3. **Criterio final**: En frame 600, `IdxNonZero>0` y `RgbNonWhite>0` (y `PresentNonWhite>0` si hay renderer)

4. Bitácora/informe actualizados con evidencia y conclusión específica

## Nota Final

**Si me pegas aquí el trozo del snapshot de tetris_dx.gbc frame 600 con**:

- `machine_is_cgb`
- `io_watch_*` FF68–FF6B
- y el dump de `bg_palette_bytes[0:32]`

**Te digo en una línea cuál de los 3 casos es y qué fix mínimo toca**.