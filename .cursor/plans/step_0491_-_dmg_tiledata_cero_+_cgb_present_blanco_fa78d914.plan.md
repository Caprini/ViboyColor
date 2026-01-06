---
name: Step 0491 - DMG tiledata cero + CGB present blanco
overview: "Hay DOS bugs distintos: (1) DMG (tetris.gb): tilemap no-cero pero tiledata en 0 → PPU lee pero dibuja todo índice 0 (blanco); (2) CGB (tetris_dx.gbc): framebuffer con diversidad pero ventana blanca → problema de presentación/blit. Este step: re-ejecuta con fix de medición aplicado, amplía VRAMWriteStats para separar attempts vs nonzero writes + bank + VBK, aplica fix mínimo DMG según resultado (3 casos), y diagnostica CGB (FB_RGB tiene señal pero FB_PRESENT está blanco)."
todos:
  - id: 0491-t1-re-execute-tetris
    content: "Re-ejecutar rom_smoke para tetris.gb (240 frames) con VIBOY_DEBUG_DMG_TILE_FETCH=1, VIBOY_DEBUG_VRAM_WRITES=1, VIBOY_DEBUG_PRESENT_TRACE=1, VIBOY_DUMP_RGB_FRAME=180, snapshots 0/60/120/180. Criterio: confirmar que DMGTileFetchStats > 0 (si sigue 0, el render_scanline no entra en el bloque o el gate/condición está mal)."
    status: pending
  - id: 0491-t2-amplify-vram-write-stats
    content: "Ampliar VRAMWriteStats en MMU.hpp: añadir tiledata_attempts_bank0/bank1, tiledata_nonzero_writes_bank0/bank1, tilemap_attempts_bank0/bank1, tilemap_nonzero_writes_bank0/bank1, last_nonzero_tiledata_write_{pc,addr,val,bank}, vbk_value_current, vbk_write_count, last_vbk_write_{pc,val}. Inicializar en constructor MMU."
    status: pending
  - id: 0491-t3-vram-write-stats-tracking
    content: "Implementar tracking en MMU::write() para VRAM: contar attempts y nonzero writes por bank (0/1) para tiledata y tilemap, guardar last_nonzero_tiledata_write, tracking de VBK writes/reads. Gate: VIBOY_DEBUG_VRAM_WRITES=1. Exponer getters a Python."
    status: pending
    dependencies:
      - 0491-t2-amplify-vram-write-stats
  - id: 0491-t4-vram-write-stats-snapshot
    content: Integrar VRAMWriteStats ampliado en snapshots en rom_smoke_0442.py (bloque VRAMWriteStats con todos los campos nuevos).
    status: pending
    dependencies:
      - 0491-t3-vram-write-stats-tracking
  - id: 0491-t5-fix-case1-dmg-bank
    content: "Implementar fix Caso 1 (writes no-cero van a bank1 en DMG): en modo DMG, ignorar VBK para VRAM CPU writes y/o para PPU reads. En MMU::write() usar effective_bank=0 si DMG. En PPU::render_bg() usar effective_bank=0 si DMG. Gate: solo aplicar si evidencia lo justifica."
    status: pending
    dependencies:
      - 0491-t4-vram-write-stats-snapshot
  - id: 0491-t6-fix-case2-dmg-boot-state
    content: "Implementar fix Caso 2 (writes a tiledata son todos cero): revisar estado post-boot (registros/LCDC/SCY/SCX/BGP/IF/IE/STAT) o mecanismo VIBOY_SIM_BOOT_LOGO=0. Implementar init_post_boot_dmg_state() con valores conocidos post-boot DMG. Gate: solo aplicar si evidencia lo justifica."
    status: pending
    dependencies:
      - 0491-t4-vram-write-stats-snapshot
  - id: 0491-t7-fix-case3-dmg-vram-storage
    content: "Implementar fix Caso 3 (writes no-cero existen pero VRAM sigue 0): revisar lógica de escritura a VRAM (punteros/bancos/máscaras), corregir dónde se escribe realmente. Gate: solo aplicar si evidencia lo justifica."
    status: pending
    dependencies:
      - 0491-t4-vram-write-stats-snapshot
  - id: 0491-t8-cgb-present-src-dump
    content: "Modificar renderer.py render_frame() para capturar y dump FB_PRESENT_SRC: en el mismo frame N, dump a PPM del buffer exacto que se manda a flip, log present_w/h/pitch/format y CRC32 del buffer fuente usado para blit. Gate: VIBOY_DEBUG_PRESENT_TRACE=1 y VIBOY_DUMP_RGB_FRAME."
    status: pending
  - id: 0491-t9-execute-both-roms
    content: Ejecutar rom_smoke para tetris.gb y tetris_dx.gbc (240 frames) con todos los flags activos. Extraer snapshots frames 0/60/120/180. Generar dumps RGB y FB_PRESENT_SRC en frame 180.
    status: pending
    dependencies:
      - 0491-t1-re-execute-tetris
      - 0491-t4-vram-write-stats-snapshot
      - 0491-t8-cgb-present-src-dump
  - id: 0491-t10-create-report
    content: "Crear reporte markdown docs/reports/reporte_step0491.md con: tabla comparativa frame 180 (VRAM tiledata/tilemap nonzero, nonzero writes por bank, VBK stats, DMGTileFetchStats, ThreeBufferStats), enlaces/rutas a dumps RGB y FB_PRESENT_SRC, una de las 3 conclusiones del fix mínimo DMG demostrada con números. NO placeholders."
    status: pending
    dependencies:
      - 0491-t9-execute-both-roms
  - id: 0491-t11-document
    content: "Documentar Step 0491 en bitácora HTML e informe dividido. Framing: DMG tiledata cero + CGB present blanco. Incluir evidencia (VRAM writes por bank, VBK, tile fetch, present src), conclusión específica (Caso 1/2/3), siguiente fix. Update docs/bitacora/index.html y docs/informe_fase_2/."
    status: pending
    dependencies:
      - 0491-t10-create-report
---

# Step 0491: "DMG Tiledata Cero + CGB Present Blanco"

## Contexto

**DMG**: `tetris.gb` muestra pantalla blanca. Evidencia: `vram_tilemap_nonzero_9800_9FFF=1024`, pero `vram_tiledata_nonzero_8000_97FF=0`. `VRAMWriteStats` muestra attempts altos pero no sabemos si escriben valores no-cero ni a qué bank.**CGB**: En pasos previos hubo PPM con diversidad pero ventana blanca ⇒ problema de renderer/present.

## Correcciones de Interpretación (Del Reporte 0490)

1. **LY "fuera de rango"**: No. LY en hardware va 0..153 (0..143 visibles + 144..153 VBlank). Ver 148 es normal.
2. **BGP=0xE4**: Es el mapeo "identity" (0→0, 1→1, 2→2, 3→3), no "[3,2,1,0]".

## Fase A: Re-Ejecutar con el "Fix de Medición" Ya Aplicado (Bloqueante)

### A1) Acción

**Ejecutar `rom_smoke_0442.py` para `tetris.gb` 240 frames con**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=180
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_tetris_gb_rgb_f####.ppm
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 240 | tee /tmp/viboy_0491_tetris.log
```

**Snapshots a 0/60/120/180**.

### A2) Criterio

**Confirmar que `DMGTileFetchStats > 0`** (si sigue 0, el `render_scanline` no entra en el bloque o el gate/condición está mal).

## Fase B: VRAMWriteStats - Separar "Attempts" vs "Nonzero Writes" + Bank + VBK

### B1) Ampliar VRAMWriteStats

**Archivo**: `src/core/cpp/MMU.hpp` y `src/core/cpp/MMU.cpp`**Ampliar `VRAMWriteStats` para registrar, por separado**:

```cpp
// En MMU.hpp
struct VRAMWriteStats {
    // Tiledata (0x8000-0x97FF)
    uint32_t tiledata_attempts_bank0;      // Intentos de write a tiledata bank 0
    uint32_t tiledata_attempts_bank1;      // Intentos de write a tiledata bank 1
    uint32_t tiledata_nonzero_writes_bank0;  // Writes no-cero a tiledata bank 0
    uint32_t tiledata_nonzero_writes_bank1;  // Writes no-cero a tiledata bank 1
    
    // Tilemap (0x9800-0x9FFF)
    uint32_t tilemap_attempts_bank0;      // Intentos de write a tilemap bank 0
    uint32_t tilemap_attempts_bank1;      // Intentos de write a tilemap bank 1
    uint32_t tilemap_nonzero_writes_bank0;  // Writes no-cero a tilemap bank 0
    uint32_t tilemap_nonzero_writes_bank1;  // Writes no-cero a tilemap bank 1
    
    // Last nonzero tiledata write
    uint16_t last_nonzero_tiledata_write_pc;
    uint16_t last_nonzero_tiledata_write_addr;
    uint8_t last_nonzero_tiledata_write_val;
    uint8_t last_nonzero_tiledata_write_bank;
    
    // Tracking de VBK
    uint8_t vbk_value_current;              // Valor actual de VBK (0xFF4F)
    uint32_t vbk_write_count;               // Número de writes a VBK
    uint16_t last_vbk_write_pc;             // PC del último write a VBK
    uint8_t last_vbk_write_val;              // Valor escrito a VBK
    
    // Legacy (mantener por compatibilidad)
    uint32_t vram_write_attempts_tiledata;  // Total attempts (bank0 + bank1)
    uint32_t vram_write_attempts_tilemap;   // Total attempts (bank0 + bank1)
    uint32_t vram_write_blocked_mode3_tiledata;
    uint32_t vram_write_blocked_mode3_tilemap;
    uint16_t last_blocked_vram_write_pc;
    uint16_t last_blocked_vram_write_addr;
};

VRAMWriteStats vram_write_stats_;
```



### B2) Implementar Tracking en MMU::write()

**Archivo**: `src/core/cpp/MMU.cpp`**En `MMU::write()`, cuando se escribe a VRAM**:

```cpp
// En MMU.cpp, método write()
if (addr >= 0x8000 && addr <= 0x9FFF) {
    // Gate: solo si VIBOY_DEBUG_VRAM_WRITES está activo
    const char* env_debug = std::getenv("VIBOY_DEBUG_VRAM_WRITES");
    if (env_debug && std::string(env_debug) == "1") {
        // Obtener banco actual (VBK)
        uint8_t vbk = vram_bank_;  // O leer de memory_[0xFF4F] & 0x01
        
        // Determinar región
        bool is_tiledata = (addr >= 0x8000 && addr <= 0x97FF);
        bool is_tilemap = (addr >= 0x9800 && addr <= 0x9FFF);
        
        // Contar attempts
        if (is_tiledata) {
            if (vbk == 0) {
                vram_write_stats_.tiledata_attempts_bank0++;
            } else {
                vram_write_stats_.tiledata_attempts_bank1++;
            }
            vram_write_stats_.vram_write_attempts_tiledata++;
        } else if (is_tilemap) {
            if (vbk == 0) {
                vram_write_stats_.tilemap_attempts_bank0++;
            } else {
                vram_write_stats_.tilemap_attempts_bank1++;
            }
            vram_write_stats_.vram_write_attempts_tilemap++;
        }
        
        // Contar nonzero writes
        if (value != 0x00) {
            if (is_tiledata) {
                if (vbk == 0) {
                    vram_write_stats_.tiledata_nonzero_writes_bank0++;
                } else {
                    vram_write_stats_.tiledata_nonzero_writes_bank1++;
                }
                
                // Guardar último nonzero write
                vram_write_stats_.last_nonzero_tiledata_write_pc = debug_current_pc;
                vram_write_stats_.last_nonzero_tiledata_write_addr = addr;
                vram_write_stats_.last_nonzero_tiledata_write_val = value;
                vram_write_stats_.last_nonzero_tiledata_write_bank = vbk;
            } else if (is_tilemap) {
                if (vbk == 0) {
                    vram_write_stats_.tilemap_nonzero_writes_bank0++;
                } else {
                    vram_write_stats_.tilemap_nonzero_writes_bank1++;
                }
            }
        }
        
        // Verificar si está bloqueado por Mode 3
        // (código existente de bloqueo)
        if (is_blocked_by_mode3) {
            if (is_tiledata) {
                vram_write_stats_.vram_write_blocked_mode3_tiledata++;
            } else if (is_tilemap) {
                vram_write_stats_.vram_write_blocked_mode3_tilemap++;
            }
            vram_write_stats_.last_blocked_vram_write_pc = debug_current_pc;
            vram_write_stats_.last_blocked_vram_write_addr = addr;
        }
    }
    
    // ... resto del código de write ...
}

// En MMU::write(), cuando se escribe a VBK (0xFF4F)
if (addr == 0xFF4F) {
    // Gate: solo si VIBOY_DEBUG_VRAM_WRITES está activo
    const char* env_debug = std::getenv("VIBOY_DEBUG_VRAM_WRITES");
    if (env_debug && std::string(env_debug) == "1") {
        vram_write_stats_.vbk_write_count++;
        vram_write_stats_.last_vbk_write_pc = debug_current_pc;
        vram_write_stats_.last_vbk_write_val = value;
        vram_write_stats_.vbk_value_current = value & 0x01;  // Solo bit 0
    }
    
    // ... resto del código de write a VBK ...
}
```

**En `MMU::read()`, cuando se lee VBK (0xFF4F)**:

```cpp
// En MMU.cpp, método read()
if (addr == 0xFF4F) {
    // Gate: solo si VIBOY_DEBUG_VRAM_WRITES está activo
    const char* env_debug = std::getenv("VIBOY_DEBUG_VRAM_WRITES");
    if (env_debug && std::string(env_debug) == "1") {
        // Actualizar valor actual de VBK
        vram_write_stats_.vbk_value_current = vram_bank_;
    }
    
    // ... resto del código de read de VBK ...
}
```



### B3) Exponer Getters a Python

**Archivo**: `src/core/cython/mmu.pyx`

```cython
# En mmu.pyx
cdef class PyMMU:
    def get_vram_write_stats(self):
        """Obtiene estadísticas de writes a VRAM."""
        if self._mmu == NULL:
            return None
        
        cdef VRAMWriteStats stats = self._mmu.get_vram_write_stats()
        return {
            'tiledata_attempts_bank0': stats.tiledata_attempts_bank0,
            'tiledata_attempts_bank1': stats.tiledata_attempts_bank1,
            'tiledata_nonzero_writes_bank0': stats.tiledata_nonzero_writes_bank0,
            'tiledata_nonzero_writes_bank1': stats.tiledata_nonzero_writes_bank1,
            'tilemap_attempts_bank0': stats.tilemap_attempts_bank0,
            'tilemap_attempts_bank1': stats.tilemap_attempts_bank1,
            'tilemap_nonzero_writes_bank0': stats.tilemap_nonzero_writes_bank0,
            'tilemap_nonzero_writes_bank1': stats.tilemap_nonzero_writes_bank1,
            'last_nonzero_tiledata_write_pc': stats.last_nonzero_tiledata_write_pc,
            'last_nonzero_tiledata_write_addr': stats.last_nonzero_tiledata_write_addr,
            'last_nonzero_tiledata_write_val': stats.last_nonzero_tiledata_write_val,
            'last_nonzero_tiledata_write_bank': stats.last_nonzero_tiledata_write_bank,
            'vbk_value_current': stats.vbk_value_current,
            'vbk_write_count': stats.vbk_write_count,
            'last_vbk_write_pc': stats.last_vbk_write_pc,
            'last_vbk_write_val': stats.last_vbk_write_val,
            # Legacy
            'vram_write_attempts_tiledata': stats.vram_write_attempts_tiledata,
            'vram_write_attempts_tilemap': stats.vram_write_attempts_tilemap,
            'vram_write_blocked_mode3_tiledata': stats.vram_write_blocked_mode3_tiledata,
            'vram_write_blocked_mode3_tilemap': stats.vram_write_blocked_mode3_tilemap,
            'last_blocked_vram_write_pc': stats.last_blocked_vram_write_pc,
            'last_blocked_vram_write_addr': stats.last_blocked_vram_write_addr,
        }
```



### B4) Integración en Snapshots

**Archivo**: `tools/rom_smoke_0442.py`**En snapshots, añadir bloque `VRAMWriteStats` ampliado**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
vram_write_stats = mmu.get_vram_write_stats()
if vram_write_stats:
    snapshot['VRAMWriteStats'] = {
        'tiledata_attempts_bank0': vram_write_stats['tiledata_attempts_bank0'],
        'tiledata_attempts_bank1': vram_write_stats['tiledata_attempts_bank1'],
        'tiledata_nonzero_writes_bank0': vram_write_stats['tiledata_nonzero_writes_bank0'],
        'tiledata_nonzero_writes_bank1': vram_write_stats['tiledata_nonzero_writes_bank1'],
        'tilemap_attempts_bank0': vram_write_stats['tilemap_attempts_bank0'],
        'tilemap_attempts_bank1': vram_write_stats['tilemap_attempts_bank1'],
        'tilemap_nonzero_writes_bank0': vram_write_stats['tilemap_nonzero_writes_bank0'],
        'tilemap_nonzero_writes_bank1': vram_write_stats['tilemap_nonzero_writes_bank1'],
        'last_nonzero_tiledata_write_pc': vram_write_stats['last_nonzero_tiledata_write_pc'],
        'last_nonzero_tiledata_write_addr': vram_write_stats['last_nonzero_tiledata_write_addr'],
        'last_nonzero_tiledata_write_val': vram_write_stats['last_nonzero_tiledata_write_val'],
        'last_nonzero_tiledata_write_bank': vram_write_stats['last_nonzero_tiledata_write_bank'],
        'vbk_value_current': vram_write_stats['vbk_value_current'],
        'vbk_write_count': vram_write_stats['vbk_write_count'],
        'last_vbk_write_pc': vram_write_stats['last_vbk_write_pc'],
        'last_vbk_write_val': vram_write_stats['last_vbk_write_val'],
    }
```



### B5) Criterio

**En `tetris.gb`**:

- **Si `tiledata_nonzero_writes_* == 0`**: El juego está escribiendo solo ceros (probable stuck-before-decompress / init state / boot).
- **Si hay `tiledata_nonzero_writes_bank1 > 0` pero bank0 sigue vacío**: Bug claro de bank selection en DMG (VBK afectando cuando no debería o PPU leyendo bank distinto).

## Fase C: Fix Mínimo DMG Según Resultado (Uno de Estos, No Todos)

### C1) Caso 1: Writes No-Cero Van a Bank1 en DMG

**Fix**: En modo DMG, ignorar VBK para VRAM CPU writes y/o para PPU reads (según dónde esté el desvío).**Archivo**: `src/core/cpp/MMU.cpp`**En `MMU::write()`, cuando se escribe a VRAM en modo DMG**:

```cpp
// En MMU.cpp, método write()
if (addr >= 0x8000 && addr <= 0x9FFF) {
    // En modo DMG, ignorar VBK (siempre escribir a bank 0)
    bool is_dmg = !is_cgb_mode();  // O detectar de otra manera
    uint8_t effective_bank = is_dmg ? 0 : vram_bank_;
    
    // ... resto del código de write usando effective_bank ...
}
```

**En `PPU::render_bg()`, cuando se lee VRAM en modo DMG**:

```cpp
// En PPU.cpp, método render_bg()
// En modo DMG, siempre leer de bank 0
bool is_dmg = !is_cgb_mode();  // O detectar de otra manera
uint8_t effective_bank = is_dmg ? 0 : tile_bank;

uint8_t byte1 = mmu_->read_vram_bank(effective_bank, tile_line_offset);
uint8_t byte2 = mmu_->read_vram_bank(effective_bank, tile_line_offset + 1);
```



### C2) Caso 2: Writes a Tiledata Son Todos Cero

**Fix**: Revisar estado post-boot (registros/LCDC/SCY/SCX/BGP/IF/IE/STAT) o el mecanismo `VIBOY_SIM_BOOT_LOGO=0` (puede estar dejando el hw en un estado que hace que el juego nunca cargue gráficos).**Acción mínima**: Comparar init con "post-boot DMG known state" y alinear.**Archivo**: `src/core/cpp/MMU.cpp` y `src/core/cpp/MMU.hpp`**Implementar inicialización de estado post-boot DMG**:

```cpp
// En MMU.cpp, método init_post_boot_dmg_state()
void MMU::init_post_boot_dmg_state() {
    // Estado conocido después del boot ROM DMG
    // Fuente: Pan Docs - Power Up Sequence
    
    // LCDC: LCD OFF por defecto
    memory_[0xFF40] = 0x00;
    
    // STAT: 0x00 por defecto
    memory_[0xFF41] = 0x00;
    
    // SCY, SCX: 0x00 por defecto
    memory_[0xFF42] = 0x00;
    memory_[0xFF43] = 0x00;
    
    // LY: 0x00 por defecto
    memory_[0xFF44] = 0x00;
    
    // BGP: 0xFC por defecto (shades 3,2,1,0)
    memory_[0xFF47] = 0xFC;
    
    // OBP0, OBP1: 0x00 por defecto
    memory_[0xFF48] = 0x00;
    memory_[0xFF49] = 0x00;
    
    // IF: 0xE1 por defecto (VBlank, Timer, Serial flags set)
    memory_[0xFF0F] = 0xE1;
    
    // IE: 0x00 por defecto
    memory_[0xFFFF] = 0x00;
    
    // ... otros registros ...
}
```



### C3) Caso 3: Writes No-Cero Existen Pero VRAM Sigue 0

**Fix**: Bug de almacenamiento VRAM (punteros/bancos/máscaras) ⇒ corregir dónde se escribe realmente.**Archivo**: `src/core/cpp/MMU.cpp`**Revisar lógica de escritura a VRAM**:

```cpp
// En MMU.cpp, método write()
if (addr >= 0x8000 && addr <= 0x9FFF) {
    uint16_t vram_offset = addr - 0x8000;
    
    // Verificar que se escribe en el banco correcto
    if (vram_bank_ == 0) {
        memory_[addr] = value;  // Bank 0
    } else {
        // Bank 1 (CGB only)
        if (vram_banks_[1].size() > vram_offset) {
            vram_banks_[1][vram_offset] = value;
        }
    }
    
    // ... resto del código ...
}
```



## Fase D: CGB - Por Qué "FB_RGB Tiene Señal" Pero "FB_PRESENT" Está Blanco

### D1) Acción (renderer.py)

**En el mismo frame N**:

1. **Dump a PPM del `FB_PRESENT_SRC`** (lo que realmente se manda a flip)
2. **Log**: `present_w`, `present_h`, `present_pitch`, `present_format`, y CRC32 del buffer fuente usado para blit.

**Archivo**: `src/gpu/renderer.py`**Modificar `render_frame()` para capturar y dump `FB_PRESENT_SRC`**:

```python
# En renderer.py, método render_frame()
def render_frame(self, framebuffer_data: bytearray | None = None, rgb_view = None, metrics: dict | None = None) -> None:
    # ... código existente ...
    
    # Si VIBOY_DEBUG_PRESENT_TRACE está activo, capturar y dump FB_PRESENT_SRC
    import os
    if os.environ.get('VIBOY_DEBUG_PRESENT_TRACE') == '1':
        # Obtener el buffer exacto que se pasa a SDL (justo antes del blit final)
        if rgb_view is not None:
            # Modo CGB: usar RGB
            present_buffer = np.frombuffer(rgb_view, dtype=np.uint8)
        else:
            # Modo DMG: convertir índices a RGB
            # ... código de conversión ...
            present_buffer = converted_rgb_buffer
        
        if present_buffer is not None:
            # Calcular CRC32 y stats
            import zlib
            present_crc32 = zlib.crc32(present_buffer) & 0xFFFFFFFF
            present_nonwhite = sum(1 for i in range(0, len(present_buffer), 3) 
                                  if present_buffer[i] < 240 or present_buffer[i+1] < 240 or present_buffer[i+2] < 240)
            
            # Obtener formato/pitch de la textura SDL
            present_fmt = 0  # Placeholder
            present_pitch = 160 * 3  # RGB888
            present_w = 160
            present_h = 144
            
            # Log
            print(f"[FB_PRESENT_SRC] Frame {frame_number} | "
                  f"CRC32=0x{present_crc32:08X} | NonWhite={present_nonwhite} | "
                  f"W={present_w} H={present_h} Pitch={present_pitch} Format={present_fmt}")
            
            # Dump a PPM si está activo
            dump_frame = int(os.environ.get('VIBOY_DUMP_RGB_FRAME', '0'))
            if dump_frame > 0 and frame_number == dump_frame:
                dump_path = os.environ.get('VIBOY_DUMP_RGB_PATH', '/tmp/viboy_present_f####.ppm')
                dump_path = dump_path.replace('####', str(frame_number))
                
                with open(dump_path, 'wb') as f:
                    f.write(b"P6\n")
                    f.write(f"{present_w} {present_h}\n".encode())
                    f.write(b"255\n")
                    f.write(present_buffer.tobytes())
                
                print(f"[FB_PRESENT_SRC] Dump guardado en {dump_path}")
            
            # Guardar en métricas
            if metrics is None:
                metrics = {}
            metrics['present_crc32'] = present_crc32
            metrics['present_nonwhite'] = present_nonwhite
            metrics['present_fmt'] = present_fmt
            metrics['present_pitch'] = present_pitch
            metrics['present_w'] = present_w
            metrics['present_h'] = present_h
```



### D2) Criterio

**Si `FB_RGB nonwhite > 0` y `FB_PRESENT nonwhite == 0`**: El bug está en la conversión/copia al surface (stride/pitch/orden canales/transposición w/h o overwrite por clear posterior).

## Fase E: Ejecución y Reporte

### E1) Ejecutar rom_smoke

**ROMs**:

- `tetris.gb` (DMG) - 240 frames
- `tetris_dx.gbc` (CGB) - 240 frames (solo si CGB necesita diagnóstico)

**Flags**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=180
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_<rom>_rgb_f####.ppm
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0
```

**Ejecutar**:

```bash
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 240 | tee /tmp/viboy_0491_tetris.log
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0491_tetris_dx.log
```



### E2) Generar Reporte

**Archivo**: `docs/reports/reporte_step0491.md`**Debe incluir tabla comparativa (frame 180)**:| Métrica | tetris.gb | tetris_dx.gbc ||---------|-----------|---------------|| `VRAM_tiledata_nonzero` (0x8000-0x97FF) | ... | ... || `VRAM_tilemap_nonzero` (0x9800-0x9FFF) | ... | ... || `tiledata_nonzero_writes_bank0` | ... | ... || `tiledata_nonzero_writes_bank1` | ... | ... || `vbk_value_current` | ... | ... || `vbk_write_count` | ... | ... || `DMGTileFetchStats_total` | ... | ... || `DMGTileFetchStats_nonzero` | ... | ... || `ThreeBufferStats_idx_nonzero` | ... | ... || `ThreeBufferStats_rgb_nonwhite` | ... | ... || `ThreeBufferStats_present_nonwhite` | ... | ... |

### E3) Documentar

**Bitácora HTML nueva** (Step 0491), **index bitácora**, **informe dividido**, **commit/push**.

## Criterios de Éxito

1. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0491.md` completo SIN placeholders**:

- Tabla comparativa frame 180 con todas las métricas reales
- Enlaces/rutas a dumps RGB y FB_PRESENT_SRC generados
- **Una de las 3 conclusiones del fix mínimo DMG demostrada con números**

2. **⚠️ CRÍTICO: `DMGTileFetchStats > 0`** (confirmar que el fix de medición funciona)
3. **VIBOY_SIM_BOOT_LOGO=0** reportado en todos los snapshots
4. **Dumps RGB y FB_PRESENT_SRC en frame 180** generados
5. Bitácora/informe actualizados con evidencia y conclusión específica