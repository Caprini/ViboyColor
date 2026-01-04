---
name: Step 0481 - Cerrar Init Loops Reales (HRAM FF92 + wait-loop exacto)
overview: "Cerrar loops reales con evidencia: mario.gbc demuestra por qué FF92 nunca se escribe y qué condición bloquea la ruta que lo inicializa. tetris_dx.gbc vuelve a identificar el wait-loop real (JOYP u otro) y fija lo mínimo para romperlo. Incluye instrumentación HRAM watchlist, static scan de writers de FF92 en ROM, instrumentación JOYP completa, y re-ajuste del parser si quedó demasiado estricto."
todos:
  - id: 0481-t1-hram-watchlist
    content: "Implementar HRAM watchlist en MMU.cpp/MMU.hpp: estructura HRAMWatchEntry con write_count, read_count_program, last_write_pc/value/timestamp, first_write_pc/value/timestamp/frame, last_read_pc/value. Método add_hram_watch(addr). Gate: VIBOY_DEBUG_IO=1 o VIBOY_DEBUG_HRAM=1. Exponer getters a Python."
    status: pending
  - id: 0481-t2-static-scan
    content: "Implementar scan_rom_for_hram8_writes() en tools/rom_smoke_0442.py: buscar patrones E0 92 (LDH (0x92),A), EA 92 FF (LD (0xFF92),A), E2 con LD C,0x92 cerca (LD (FF00+C),A). Para cada match, retornar (pc, pattern_type, disasm_snippet). Ejecutar antes de correr frames y mostrar resultados."
    status: pending
  - id: 0481-t3-joyp-metrics
    content: "Añadir métricas JOYP completas en MMU.cpp/MMU.hpp: joyp_last_write_value/pc, joyp_write_count, joyp_last_read_value/pc, joyp_read_count_program. En Joypad.hpp añadir get_select_state() (bits 4-5). Exponer getters a Python."
    status: pending
  - id: 0481-t4-parser-readjust
    content: "Re-ajustar parse_loop_io_pattern() en tools/rom_smoke_0442.py: permitir salto a target dentro de ventana ±16 bytes alrededor del hotspot (configurable), detectar patrones BIT además de AND/CP. Criterio: tetris_dx vuelve a reportar loop_waits_on=0xFF00 si es JOYP, o reporta otro registro real con evidencia."
    status: pending
  - id: 0481-t5-test-hram-tracking
    content: "Crear tests/test_hram_ff92_tracking_0481.py: añadir FF92 a watchlist, escribir desde program context, verificar contadores y last_write_pc/value, leer y verificar last_read_pc/value."
    status: pending
    dependencies:
      - 0481-t1-hram-watchlist
  - id: 0481-t6-test-joyp-metrics
    content: "Crear tests/test_joyp_metrics_0481.py: escribir JOYP, verificar last_write_pc/value, leer JOYP, verificar read_count_program y last_read_pc/value, asegurar que incrementa solo desde programa."
    status: pending
    dependencies:
      - 0481-t3-joyp-metrics
  - id: 0481-t7-rom-smoke-snapshots
    content: "Modificar tools/rom_smoke_0442.py para añadir a snapshots: FF92_write_count, FF92_last_write_pc/value, FF92_first_write_frame, FF92_read_count_program (mario.gbc), JOYP_last_write_value/pc, JOYP_last_read_value/pc, JOYP_read_count_program, JOYP_select_state (tetris_dx.gbc), loop_waits_on/mask/cmp/pattern (parser re-ajustado)."
    status: pending
    dependencies:
      - 0481-t1-hram-watchlist
      - 0481-t2-static-scan
      - 0481-t3-joyp-metrics
      - 0481-t4-parser-readjust
  - id: 0481-t8-execute-rom-smoke
    content: "Ejecutar rom_smoke para mario.gbc, tetris_dx.gbc, tetris.gb (240 frames baseline VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_HRAM=1). Extraer snapshots y aplicar static scan. Criterio: mario cierra conclusión sobre FF92 writers, tetris_dx loop_waits_on identificado."
    status: pending
    dependencies:
      - 0481-t7-rom-smoke-snapshots
  - id: 0481-t9-create-report
    content: "Crear reporte markdown /tmp/reporte_step0481.md y docs/reports/reporte_step0481.md con: tabla frames 0/60/120/180 (FF92 metrics, JOYP metrics), sección Static scan FF92 writers (N writers + PCs + disasm snippets), decisión automática para mario.gbc y tetris_dx.gbc, siguiente fix mínimo propuesto (0482)."
    status: pending
    dependencies:
      - 0481-t8-execute-rom-smoke
  - id: 0481-t10-document
    content: "Documentar Step 0481 en bitácora HTML e informe dividido. Framing: cerrar loops reales con evidencia. Incluir tabla frames, static scan FF92 writers, decisión automática, siguiente fix. Update docs/bitacora/index.html y docs/informe_fase_2/."
    status: pending
    dependencies:
      - 0481-t9-create-report
---

# Step 0481: Cerrar Init Loops Reales (mario: HRAM FF92 / tetris_dx: Wait-Loop Exacto)

## Objetivo del Step

1. **mario.gbc**: Demostrar por qué FF92 nunca se escribe y qué condición está bloqueando la ruta que lo inicializa
2. **tetris_dx.gbc**: Volver a identificar el wait-loop real (JOYP u otro), y fijar lo mínimo para romperlo sin inventar hardware

**Contexto crítico**: Step 0480 ha hecho dos cosas bien (cerrar el falso positivo FF92 y añadir evidencia real), y ha dejado dos frentes claros:

- **mario.gbc**: HRAM[FF92] nunca se escribe ⇒ el `LDH (IE),A` siempre mete 0 en IE porque A viene de 0 (variable HRAM no inicializada)
- **tetris_dx.gbc**: Antes parecía un wait-loop de JOYP; ahora "no se detecta" ⇒ o el parser quedó demasiado estricto o el loop real no es JOYP (o no tiene el patrón AND/CP/JR clásico)

## Evitar Falsos Positivos

1. **FF80-FFFE = HRAM (no I/O)**: Jamás clasificarlo como "wait-loop IO"
2. **Logo Viboy**: Baseline siempre con `VIBOY_SIM_BOOT_LOGO=0` para no contaminar VRAM/tiles/stats

**Nota explícita**:

- **HRAM**: `0xFF80-0xFFFE` no es I/O. Solo `0xFF00-0xFF7F` se trata como I/O en el parser de loops
- **Logo Viboy**: El proyecto usa logo propio (no Nintendo) y el prefill VRAM del logo es opcional y debe estar OFF para análisis de VRAM/tilemaps (baseline)

## Fase A: Instrumentación - "Watchlist" HRAM y "Primera Escritura"

### A1) HRAM Watchlist (Quirúrgico, No General)

**Archivo**: `src/core/cpp/MMU.cpp` y `src/core/cpp/MMU.hpp`**Implementar watchlist de HRAM addresses** (por ahora solo `0xFF92`, y opcional `0xFF90..0xFF9F` si hace falta):**Archivo**: `src/core/cpp/MMU.hpp`Añadir estructura para tracking:

```cpp
struct HRAMWatchEntry {
    uint16_t addr;
    uint32_t write_count;
    uint32_t read_count_program;
    uint16_t last_write_pc;
    uint8_t last_write_value;
    uint32_t last_write_timestamp;
    uint16_t first_write_pc;
    uint8_t first_write_value;
    uint32_t first_write_timestamp;
    uint32_t first_write_frame;
    uint16_t last_read_pc;
    uint8_t last_read_value;
    bool first_write_recorded;
};

std::vector<HRAMWatchEntry> hram_watchlist_;
```

**Método para añadir a watchlist**:

```cpp
void add_hram_watch(uint16_t addr) {
    HRAMWatchEntry entry;
    entry.addr = addr;
    entry.write_count = 0;
    entry.read_count_program = 0;
    entry.first_write_recorded = false;
    hram_watchlist_.push_back(entry);
}
```

**En `MMU::write(addr, value)`**:

```cpp
// Verificar si addr está en watchlist
for (auto& entry : hram_watchlist_) {
    if (entry.addr == addr) {
        entry.write_count++;
        entry.last_write_pc = debug_current_pc;
        entry.last_write_value = value;
        entry.last_write_timestamp++;
        
        // Registrar primera escritura
        if (!entry.first_write_recorded) {
            entry.first_write_pc = debug_current_pc;
            entry.first_write_value = value;
            entry.first_write_timestamp = entry.last_write_timestamp;
            if (ppu_ != nullptr) {
                entry.first_write_frame = ppu_->get_frame_counter();
            }
            entry.first_write_recorded = true;
        }
        break;
    }
}
```

**En `MMU::read(addr)`**:

```cpp
// Verificar si addr está en watchlist
for (auto& entry : hram_watchlist_) {
    if (entry.addr == addr) {
        if (!cpu_->is_in_irq_poll()) {  // Solo reads desde programa
            entry.read_count_program++;
            entry.last_read_pc = debug_current_pc;
            entry.last_read_value = memory_[addr];
        }
        break;
    }
}
```

**Gate**: Solo activo si `VIBOY_DEBUG_IO=1` o un flag nuevo `VIBOY_DEBUG_HRAM=1`**Exponer getters a Python**:

```cpp
uint32_t get_hram_write_count(uint16_t addr) const;
uint16_t get_hram_last_write_pc(uint16_t addr) const;
uint8_t get_hram_last_write_value(uint16_t addr) const;
uint32_t get_hram_first_write_frame(uint16_t addr) const;
uint32_t get_hram_read_count_program(uint16_t addr) const;
```

**Criterio de éxito A**: En el snapshot de `rom_smoke` aparece claramente: "FF92 jamás escrito" (mario), o si se escribe, desde qué PC/cuándo.

## Fase B: "Static Scan" Dentro de rom_smoke - ¿Existe un Writer de FF92 en ROM?

### B1) Implementar `scan_rom_for_hram8_writes(0x92)`

**Archivo**: `tools/rom_smoke_0442.py`**Función**:

```python
def scan_rom_for_hram8_writes(rom_bytes, target_addr):
    """
    Escanea ROM buscando patrones típicos de escritura a HRAM.
    
    Args:
        rom_bytes: bytes del ROM (array de bytes)
        target_addr: dirección HRAM a buscar (ej: 0x92)
    
    Returns:
        Lista de (pc, pattern_type, disasm_snippet)
    """
    writers = []
    
    # Patrón 1: E0 92 → LDH (0x92),A
    pattern1 = bytes([0xE0, target_addr])
    
    # Patrón 2: EA 92 FF → LD (0xFF92),A
    pattern2 = bytes([0xEA, target_addr, 0xFF])
    
    # Buscar patrones en ROM
    for i in range(len(rom_bytes) - 2):
        # Patrón 1: LDH (0x92),A
        if rom_bytes[i:i+2] == pattern1:
            pc = i
            # Disasm window alrededor (16 bytes antes, 16 después)
            start = max(0, pc - 16)
            end = min(len(rom_bytes), pc + 16)
            snippet = disasm_bytes(rom_bytes[start:end], start)
            writers.append((pc, "LDH (0x92),A", snippet))
        
        # Patrón 2: LD (0xFF92),A
        if i < len(rom_bytes) - 3 and rom_bytes[i:i+3] == pattern2:
            pc = i
            start = max(0, pc - 16)
            end = min(len(rom_bytes), pc + 16)
            snippet = disasm_bytes(rom_bytes[start:end], start)
            writers.append((pc, "LD (0xFF92),A", snippet))
    
    # Patrón 3: E2 con análisis básico: LD (FF00+C),A
    # Si cerca se ve LD C,0x92
    for i in range(len(rom_bytes) - 10):
        if rom_bytes[i] == 0x0E and rom_bytes[i+1] == target_addr:  # LD C,0x92
            # Buscar E2 cerca (dentro de 20 bytes)
            for j in range(i, min(i+20, len(rom_bytes))):
                if rom_bytes[j] == 0xE2:  # LD (FF00+C),A
                    pc = j
                    start = max(0, pc - 16)
                    end = min(len(rom_bytes), pc + 16)
                    snippet = disasm_bytes(rom_bytes[start:end], start)
                    writers.append((pc, "LD (FF00+C),A (C=0x92)", snippet))
                    break
    
    return writers
```

**En `rom_smoke_0442.py`, antes de correr frames**:

```python
# Escanear ROM para writers de FF92
rom_bytes = mmu.get_rom_bytes()  # O método equivalente para obtener bytes del ROM
ff92_writers = scan_rom_for_hram8_writes(rom_bytes, 0x92)

print(f"[ROM-SCAN] Writers de FF92 encontrados: {len(ff92_writers)}")
for pc, pattern_type, snippet in ff92_writers:
    print(f"[ROM-SCAN] PC=0x{pc:04X} Pattern={pattern_type}")
    print(f"[ROM-SCAN] Disasm snippet:")
    for addr, inst in snippet:
        print(f"  0x{addr:04X}: {inst}")
```

**Criterio de éxito B**: El reporte Step 0481 incluye una sección: "Writers de FF92 encontrados: N" + lista de PCs + disasm_window.

## Fase C: tetris_dx - Instrumentar JOYP "de Verdad" para Decidir si Sigue Siendo el Wait-Loop

### C1) Añadir Métricas de JOYP a Snapshot

**Archivo**: `src/core/cpp/MMU.cpp` y `src/core/cpp/MMU.hpp`**En `MMU::write(0xFF00, value)`**:

```cpp
if (addr == 0xFF00) {
    joyp_last_write_value_ = value;
    joyp_last_write_pc_ = debug_current_pc;
    joyp_write_count_++;
    
    if (joypad_ != nullptr) {
        joypad_->write_p1(value);
    }
    memory_[addr] = (memory_[addr] & 0x0F) | (value & 0xF0);
    return;
}
```

**En `MMU::read(0xFF00)`**:

```cpp
if (addr == 0xFF00) {
    uint8_t value;
    if (joypad_ != nullptr) {
        value = joypad_->read_p1();
        // Bits 6-7 siempre leen como 1
        value |= 0xC0;
    } else {
        value = 0xFF;  // Default: todos los bits en 1
    }
    
    if (!cpu_->is_in_irq_poll()) {  // Solo reads desde programa
        joyp_read_count_program_++;
        joyp_last_read_pc_ = debug_current_pc;
        joyp_last_read_value_ = value;
    }
    
    return value;
}
```

**Archivo**: `src/core/cpp/MMU.hpp`Añadir miembros privados:

```cpp
uint8_t joyp_last_write_value_;
uint16_t joyp_last_write_pc_;
uint32_t joyp_write_count_;
uint8_t joyp_last_read_value_;
uint16_t joyp_last_read_pc_;
uint32_t joyp_read_count_program_;
```

**Archivo**: `src/core/cpp/Joypad.hpp` (si existe)Añadir getter para select state:

```cpp
uint8_t get_select_state() const;  // Bits 4-5 (P14/P15)
```

**Exponer getters a Python**:

```cpp
uint8_t get_joyp_last_write_value() const;
uint16_t get_joyp_last_write_pc() const;
uint8_t get_joyp_last_read_value() const;
uint16_t get_joyp_last_read_pc() const;
uint32_t get_joyp_read_count_program() const;
uint8_t get_joyp_select_state() const;  // Del Joypad
```

**Criterio de éxito C1**: En tetris_dx frame 180 puedes decir: "está leyendo JOYP con select X y recibe value Y" y compararlo con el mask/cmp del loop.

### C2) Re-Ajuste del Parser si Quedó Demasiado Estricto

**Archivo**: `tools/rom_smoke_0442.py` (función `parse_loop_io_pattern()`)**El parser nuevo exige "I/O read + jump back", bien. Pero hay wait-loops que usan**:

- `BIT n,A` + `JR Z/NZ`
- `CP` con salto a otra instrucción que retorna al hotspot
- `JR` corto a un punto cercano, no exactamente al hotspot

**Modificar `parse_loop_io_pattern()` para permitir**:

- Salto a un target dentro de una ventana ±16 bytes alrededor del hotspot (configurable)
- Patrones `BIT` además de `AND`/`CP`

**Implementar**:

```python
def parse_loop_io_pattern(disasm_window, hotspot_pc, jump_window=16):
    """
    Parsea el disasm window y detecta automáticamente patrones de I/O.
    
    Args:
        disasm_window: Lista de (addr, instruction, is_current)
        hotspot_pc: PC del hotspot
        jump_window: Ventana de bytes alrededor del hotspot para considerar "jump back"
    
    Returns:
        dict con waits_on, mask, cmp, pattern
    """
    waits_on = None
    mask = None
    cmp_val = None
    pattern = None
    
    # Buscar I/O read y jump de vuelta
    io_read_addr = None
    jump_back_found = False
    
    for addr, instruction, is_current in disasm_window:
        # Detectar LDH A,(addr) con addr < 0xFF80 (I/O, no HRAM)
        if "LDH A,(" in instruction:
            import re
            match = re.search(r'LDH A,\(0x([0-9A-Fa-f]+)\)', instruction)
            if match:
                io_addr = int(match.group(1), 16)
                if 0xFF00 <= io_addr < 0xFF80:
                    io_read_addr = io_addr
                    waits_on = io_addr
        
        # Detectar AND mask
        if "AND" in instruction and waits_on:
            match = re.search(r'AND\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                mask = int(match.group(1), 16)
        
        # Detectar BIT n (nuevo)
        if "BIT" in instruction and waits_on:
            match = re.search(r'BIT\s+(\d+)', instruction)
            if match:
                bit_num = int(match.group(1))
                mask = 1 << bit_num
        
        # Detectar CP (compare)
        if "CP" in instruction and waits_on:
            match = re.search(r'CP\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                cmp_val = int(match.group(1), 16)
        
        # Detectar jump de vuelta al hotspot (ventana ±jump_window bytes)
        if waits_on and ("JR" in instruction or "JP" in instruction):
            match = re.search(r'(JR|JP)\s+(?:Z|NZ|C|NC)?\s*0x([0-9A-Fa-f]+)', instruction)
            if match:
                target = int(match.group(2), 16)
                # Verificar si el target está cerca del hotspot (ventana configurable)
                if abs(target - hotspot_pc) <= jump_window:
                    jump_back_found = True
    
    # Solo declarar loop si hay I/O read Y jump de vuelta
    if not jump_back_found:
        waits_on = None
        mask = None
        cmp_val = None
        pattern = "NO_LOOP"
    
    # Determinar pattern
    if waits_on == 0xFF44:  # LY
        if cmp_val is not None:
            pattern = "LY_GE"
        else:
            pattern = "LY_POLL"
    elif waits_on == 0xFF41:  # STAT
        if mask == 0x03:
            pattern = "STAT_MODE"
        else:
            pattern = "STAT_POLL"
    elif waits_on == 0xFF0F:  # IF
        if mask:
            pattern = f"IF_BIT{mask.bit_length()-1}"
        else:
            pattern = "IF_POLL"
    elif waits_on == 0xFF00:  # JOYP
        pattern = "JOYP_POLL"
    elif waits_on in [0xFF4D, 0xFF4F, 0xFF70]:  # CGB I/O
        pattern = "CGB_IO"
    else:
        pattern = "UNKNOWN"
    
    return {
        "waits_on": waits_on,
        "mask": mask,
        "cmp": cmp_val,
        "pattern": pattern
    }
```

**Criterio de éxito C2**: tetris_dx vuelve a reportar `loop_waits_on=0xFF00` si de verdad sigue siendo JOYP, o reporta otro registro real (IF/LY/etc) con evidencia.

## Fase D: Tests Clean-Room (Mínimos pero Útiles)

### D1) Tests de HRAM FF92 Tracking

**Archivo**: `tests/test_hram_ff92_tracking_0481.py`**Diseño**:

1. Inicializar sistema mínimo (MMU/CPU)
2. Añadir `0xFF92` a watchlist: `mmu.add_hram_watch(0xFF92)`
3. Escribir a `0xFF92` desde "program context" (MMU.write): `mmu.write(0xFF92, 0x1F)`
4. Verificar contadores:

- `mmu.get_hram_write_count(0xFF92) == 1`
- `mmu.get_hram_last_write_pc() != 0`
- `mmu.get_hram_last_write_value() == 0x1F`

5. Leer `0xFF92`: `value = mmu.read(0xFF92)`
6. Verificar:

- `mmu.get_hram_read_count_program(0xFF92) == 1`
- `mmu.get_hram_last_read_pc() != 0`
- `mmu.get_hram_last_read_value() == 0x1F`

**Criterio de éxito**: Test pasa.

### D2) Tests de JOYP Métricas + Semántica

**Archivo**: `tests/test_joyp_metrics_0481.py`**Diseño**:

1. Inicializar sistema mínimo (MMU/Joypad)
2. Escribir `JOYP = 0x20` (P15=1, seleccionar botones)
3. Verificar:

- `mmu.get_joyp_last_write_pc() != 0`
- `mmu.get_joyp_last_write_value() == 0x20`

4. Leer `JOYP`: `value = mmu.read(0xFF00)`
5. Verificar:

- `mmu.get_joyp_read_count_program() > 0`
- `mmu.get_joyp_last_read_pc() != 0`
- `mmu.get_joyp_last_read_value() == value`

6. Asegurar que `read_count_program` incrementa solo desde programa (si tenéis source-tagging aplicable)

**Criterio de éxito**: Tests pasan y no dependen de ROMs externas.

## Fase E: Ejecutar rom_smoke y Generar Reporte Step 0481

### E1) Baseline Obligatorio

**Flags**:

```bash
export VIBOY_SIM_BOOT_LOGO=0  # Para no contaminar VRAM stats por el prefill del logo Viboy
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_HRAM=1  # Nuevo flag para HRAM watchlist
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0
```



### E2) Comandos Exactos

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_HRAM=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0481_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0481_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0481_tetris.log
```



### E3) Reporte (`/tmp/reporte_step0481.md` + `docs/reports/reporte_step0481.md`)

**Estructura**:

```markdown
# Reporte Step 0481: Cerrar Init Loops Reales

## Configuración

- Baseline: VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_IO=1, VIBOY_DEBUG_HRAM=1

## Tabla Frames 0/60/120/180

### mario.gbc

| Frame | PC | PC_hotspot1 | FF92_write_count | FF92_last_write_pc | FF92_last_write_value | FF92_first_write_frame | FF92_read_count_program | IME | IE | IF | loop_waits_on | loop_mask | loop_cmp | loop_pattern | fb_nonzero |
|-------|----|-------------|------------------|--------------------|----------------------|------------------------|-------------------------|-----|----|----|---------------|-----------|----------|--------------|------------|
| 0     | ...| ...         | ...              | ...                | ...                  | ...                    | ...                     | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 60    | ...| ...         | ...              | ...                | ...                  | ...                    | ...                     | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 120   | ...| ...         | ...              | ...                | ...                  | ...                    | ...                     | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 180   | ...| ...         | ...              | ...                | ...                  | ...                    | ...                     | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |

### tetris_dx.gbc

| Frame | PC | PC_hotspot1 | JOYP_last_write_value | JOYP_last_write_pc | JOYP_last_read_value | JOYP_last_read_pc | JOYP_read_count_program | JOYP_select_state | IME | IE | IF | loop_waits_on | loop_mask | loop_cmp | loop_pattern | fb_nonzero |
|-------|----|-------------|----------------------|--------------------|---------------------|-------------------|-------------------------|-------------------|-----|----|----|---------------|-----------|----------|--------------|------------|
| 0     | ...| ...         | ...                  | ...                | ...                 | ...               | ...                     | ...               | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 60    | ...| ...         | ...                  | ...                | ...                 | ...               | ...                     | ...               | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 120   | ...| ...         | ...                  | ...                | ...                 | ...               | ...                     | ...               | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |
| 180   | ...| ...         | ...                  | ...                | ...                 | ...               | ...                     | ...               | ... | ...| ...| ...            | ...       | ...      | ...          | ...        |

## Static Scan FF92 Writers (mario.gbc)

**Writers de FF92 encontrados**: N

### Writer 1

**PC**: `0x????`

**Pattern**: `LDH (0x92),A` / `LD (0xFF92),A` / `LD (FF00+C),A (C=0x92)`

**Disasm snippet**:
```

0x????: [instrucción]0x????: LDH (0x92),A0x????: [instrucción]...

```javascript

### Writer 2

[Similar]

## Decisión Automática

### mario.gbc

**Condición observada**: [FF92_write_count, FF92_first_write_frame, etc.]

**Static scan**: [N writers encontrados en ROM]

**Conclusión**:
- ✅ "Sí existen writers de FF92 pero no se alcanzan" + cuál es el loop que lo impide
- ✅ "No existen writers de FF92" → entonces ese `LDH A,(FF92)` pertenece a una ruta que no es la que creíamos, y el loop real está en otro lado

**Siguiente fix mínimo (0482)**: [Propuesta basada en evidencia]

### tetris_dx.gbc

**Condición observada**: [JOYP metrics, loop_waits_on, etc.]

**Conclusión**: `loop_waits_on` vuelve a quedar identificado (JOYP u otro) con valores concretos

**Siguiente fix mínimo (0482)**: [Propuesta basada en evidencia]
```

**Criterio de éxito E**:

- **mario**: El reporte cierra una de estas dos conclusiones con evidencia:
- "Sí existen writers de FF92 pero no se alcanzan" + cuál es el loop que lo impide
- "No existen writers de FF92" → entonces ese `LDH A,(FF92)` pertenece a una ruta que no es la que creíamos, y el loop real está en otro lado
- **tetris_dx**: `loop_waits_on` vuelve a quedar identificado (JOYP u otro) con valores concretos

## Entregables Obligatorios

1. **Diff del fix en `MMU.cpp/MMU.hpp`** (HRAM watchlist + JOYP metrics)
2. **Diff del fix en `tools/rom_smoke_0442.py`** (static scan + parser re-ajustado)
3. **Tests `test_hram_ff92_tracking_0481.py` y `test_joyp_metrics_0481.py` pasando**
4. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0481.md` y `docs/reports/reporte_step0481.md`** con:

- Tabla frames 0/60/120/180 incluyendo FF92 metrics y JOYP metrics
- Sección "Static scan FF92 writers" (de la Fase B)
- Decisión automática para mario.gbc y tetris_dx.gbc
- Siguiente fix mínimo propuesto (0482) basado en evidencia

## Comandos Exactos

### Build

```bash
python3 setup.py build_ext --inplace
```



### Tests

```bash
pytest -q tests/test_hram_ff92_tracking_0481.py tests/test_joyp_metrics_0481.py
pytest -q tests/test_joyp_*_0480.py  # Anti-regresión
```



### rom_smoke (Baseline Obligatorio)

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_HRAM=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0481_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0481_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0481_tetris.log
```



### Análisis (Sin Saturar Contexto)

```bash
# Solo snapshots
grep -E "\[SMOKE-SNAPSHOT\]" /tmp/viboy_0481_*.log | head -n 260

# Static scan results
grep -E "\[ROM-SCAN\]" /tmp/viboy_0481_*.log | head -n 100
```



## Documentación

**⚠️ IMPORTANTE**: NO documentar hasta tener el reporte `/tmp/reporte_step0481.md` completo. Documentar antes es el patrón que genera "steps completados" que luego no sostienen la realidad.

### Bitácora HTML

**Archivo**: `docs/bitacora/entries/2026-01-04__0481__cerrar-init-loops-reales.html`**Framing correcto**:

- "Step 0480 cerró falso positivo FF92 y añadió evidencia real. Step 0481 cierra loops reales: mario.gbc demuestra por qué FF92 nunca se escribe, tetris_dx.gbc vuelve a identificar wait-loop real (JOYP u otro)."

**Incluir en HTML**:

- Tabla frames 0/60/120/180 con FF92 metrics (mario.gbc) y JOYP metrics (tetris_dx.gbc)
- Sección "Static scan FF92 writers" con lista de PCs + disasm snippets
- Decisión automática para cada ROM
- Siguiente fix mínimo propuesto (0482)

### Informe Dividido

**Archivo**: `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o la parte que contenga Step 0481)Añadir entrada al principio de "## Entradas de Desarrollo".

### Update `docs/bitacora/index.html`

Añadir entrada 0481 al principio de `<ul class="entry-list">` (formato antiguo, homogéneo con entradas anteriores).

## Git

```bash
git add .
git commit -m "feat(tools/core): step 0481 - HRAM FF92 writer scan + JOYP telemetry + robust wait-loop detection"
git push
```



## Criterios de Éxito

1. Tests `test_hram_ff92_tracking_0481.py` y `test_joyp_metrics_0481.py` pasan
2. **⚠️ CRÍTICO: Static scan implementado** (busca writers de FF92 en ROM)
3. **⚠️ CRÍTICO: Parser re-ajustado** (permite BIT, ventana configurable para jump back)
4. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0481.md` completo** con:

- Tabla frames 0/60/120/180 con FF92 metrics y JOYP metrics
- Sección "Static scan FF92 writers" con N writers + PCs + disasm snippets
- Decisión automática para mario.gbc (writers encontrados o no, loop que impide)
- Decisión automática para tetris_dx.gbc (loop_waits_on identificado con valores)
- Siguiente fix mínimo propuesto (0482)

5. **NO se repite**:

- "FF92 = I/O CGB" (es HRAM)
- "STAT roto" sin `stat_reads_program > 0`
- Usar VRAMNZ/tilemapNZ como señal del juego con prefill ON

6. Bitácora/informe actualizados con reporte y decisión automática