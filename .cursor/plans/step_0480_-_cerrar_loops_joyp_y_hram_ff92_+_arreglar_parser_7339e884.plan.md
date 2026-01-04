---
name: Step 0480 - Cerrar loops JOYP y HRAM FF92 + arreglar parser
overview: "Cerrar dos loops distintos: tetris_dx.gbc desbloquea condición JOYP & 0x03 == 0x03 con semántica JOYP correcta, y mario.gbc descubre por qué HRAM[FF92] está a 0 (y si se escribe alguna vez). Arreglar el parser para evitar falsos positivos como \"FF92 = I/O\". Corregir errores de interpretación del Step 0479: 0xFF92 es HRAM (0xFF80-0xFFFE), no I/O CGB; STAT_LastRead=0x00 no demuestra bug si el juego no lee STAT."
todos:
  - id: 0480-t1-fix-parser
    content: "Arreglar parse_loop_io_pattern() en tools/rom_smoke_0442.py: solo declarar loop_waits_on si hay LDH A,(addr) con addr < 0xFF80 (I/O, no HRAM), AND mask/BIT/CP opcional, y JR/JP que vuelve al hotspot. Si solo hay LDH A,(FF92) seguido de LDH (IE),A y RET, eso no es wait loop. Criterio: mario.gbc loop_waits_on vacío, tetris_dx.gbc sigue detectando JOYP."
    status: pending
  - id: 0480-t2-instrument-hram-ff92
    content: "Añadir tracking de HRAM[FF92] en MMU.cpp (gated VIBOY_DEBUG_IO=1): hram_ff92_write_count_, last_hram_ff92_write_pc_/value_/timestamp_, hram_ff92_read_count_program_, last_hram_ff92_read_pc_/value_. Exponer getters a Python. Criterio: snapshot muestra si alguien escribe FF92 y desde qué PC."
    status: pending
  - id: 0480-t3-fix-joyp-semantics
    content: "Implementar semántica JOYP correcta en MMU.cpp y Joypad.cpp: bits 6-7 leídos como 1, writes solo afectan selección (P14/P15), lectura devuelve no presionados como 1 (inversión), con sin input & 0x03 == 0x03. Verificar implementación de Joypad::read_p1()."
    status: pending
  - id: 0480-t4-test-joyp-default
    content: "Crear tests/test_joyp_default_no_input_returns_1s_0480.py: sin input, leer JOYP, assert (joyp & 0x03) == 0x03 y (joyp & 0xC0) == 0xC0."
    status: pending
    dependencies:
      - 0480-t3-fix-joyp-semantics
  - id: 0480-t5-test-joyp-buttons
    content: "Crear tests/test_joyp_select_buttons_affects_low_nibble_0480.py: escribir JOYP=0x20 (P15=1), leer JOYP, assert bits 0-3 reflejan estado de botones."
    status: pending
    dependencies:
      - 0480-t3-fix-joyp-semantics
  - id: 0480-t6-test-joyp-dpad
    content: "Crear tests/test_joyp_select_dpad_affects_low_nibble_0480.py: escribir JOYP=0x10 (P14=1), leer JOYP, assert bits 0-3 reflejan estado de direcciones."
    status: pending
    dependencies:
      - 0480-t3-fix-joyp-semantics
  - id: 0480-t7-fix-disasm-window
    content: "Arreglar disasm_window() en tools/rom_smoke_0442.py: imprimir línea marcada >>> pc EXACTA <<< PC ACTUAL en output, leer bytes con MMU (no ROM file raw) para respetar MBC/banco. Criterio: línea del hotspot aparece y se decodifica como instrucción válida, no como DB basura."
    status: pending
  - id: 0480-t8-rom-smoke-snapshots
    content: "Modificar tools/rom_smoke_0442.py para añadir a snapshots: loop_waits_on/mask/cmp/pattern (parser corregido), JOYP metrics (last_read_value, last_write_value), HRAM FF92 metrics (reads/writes, last_write_pc/value/timestamp, last_read_pc/value), disasm_window con PC marcada."
    status: pending
    dependencies:
      - 0480-t1-fix-parser
      - 0480-t2-instrument-hram-ff92
      - 0480-t7-fix-disasm-window
  - id: 0480-t9-execute-rom-smoke
    content: "Ejecutar rom_smoke para mario.gbc, tetris_dx.gbc, tetris.gb (240 frames baseline VIBOY_SIM_BOOT_LOGO=0). Extraer snapshots y aplicar parser corregido. Criterio: tetris_dx loop JOYP se rompe o cambia, mario sabemos si FF92 se escribe."
    status: pending
    dependencies:
      - 0480-t8-rom-smoke-snapshots
      - 0480-t3-fix-joyp-semantics
  - id: 0480-t10-create-report
    content: "Crear reporte markdown /tmp/reporte_step0480.md con: para cada ROM CGB (PC_hotspot1, disasm_window con PC marcada, loop pattern parser corregido, JOYP metrics, HRAM FF92 metrics), decisión automática (¿JOYP fix desbloquea? ¿FF92 se escribe?), resultado."
    status: pending
    dependencies:
      - 0480-t9-execute-rom-smoke
  - id: 0480-t11-document
    content: "Documentar Step 0480 en bitácora HTML e informe dividido. Framing: corregir errores interpretación 0479, cerrar loops JOYP y HRAM FF92. Incluir correcciones (FF92=HRAM, STAT solo si se lee), disasm window PC marcada, loop pattern, JOYP fix, HRAM metrics, decisión automática, resultado. Update docs/bitacora/index.html y docs/informe_fase_2/."
    status: pending
    dependencies:
      - 0480-t10-create-report
---

#Step 0480: Cerrar Loops JOYP y HRAM FF92 + Arreglar Parser

## Objetivo

Cerrar dos loops distintos:

1. **tetris_dx.gbc**: Desbloquear condición `JOYP & 0x03 == 0x03` con semántica JOYP correcta
2. **mario.gbc**: Descubrir por qué `HRAM[FF92]` está a 0 (y si se escribe alguna vez)

Y además: arreglar el parser para evitar falsos positivos como el de "FF92 = I/O".**Correcciones críticas del Step 0479**:

1. **0xFF92 NO es "I/O CGB no estándar"**: `LDH A,(0xFF92)` significa leer de `0xFF00 + 0x92 = 0xFF92`, y `0xFF92` está en HRAM (FF80-FFFE), no es un registro I/O "especial CGB". El código está leyendo HRAM[FF92] y copiándolo a IE. Si IE=0x00, puede ser porque HRAM[FF92] es 0 y nunca se inicializa.
2. **STAT_LastRead=0x00 NO demuestra bug**: Si el juego no lee STAT, `STAT_LastRead` se queda en el default (0). Eso no es "STAT roto", es "STAT no observado". Para afirmar "STAT roto", necesitas `stat_reads_program > 0` y valores incoherentes o invariantes cuando deberían cambiar.
3. **tetris_dx.gbc: el wait real es JOYP**: El parser detecta `waits_on = 0xFF00` (JOYP), `mask=0x03` y `cmp=0x03`. Eso suele ser "quiero ver bits0-1 en 1" (con 0 botones pulsados, etc.). Si tu JOYP está devolviendo algo incorrecto, el juego se queda en loop.

## REGLAS Anti-Falsos-Positivos (Obligatorio)

1. **FF80-FFFE = HRAM, no I/O**: Cualquier `LDH A,(0xFFxx)` con `xx ≥ 0x80` es HRAM. No lo llaméis "I/O CGB".
2. **Logo/prefill**: `VIBOY_SIM_BOOT_LOGO=0` en baseline. Si se activa, VRAMNZ/tilemapNZ pasan a ser "contaminables" y no deben usarse para inferir progreso.
3. **STAT roto solo si**: `stat_reads_program > 0` y valores incoherentes o invariantes cuando deberían cambiar.

## Fase A: Arreglar el Parser de Loop (Evitar Falsos Positivos)

### A1) Cambios en `parse_loop_io_pattern()`

**Archivo**: `tools/rom_smoke_0442.py`**Regla nueva**: Solo declarar `loop_waits_on` si hay un patrón tipo:

1. `LDH A,(addr)` o `LD A,(FF00+C)` etc (donde `addr < 0xFF80` para ser I/O, no HRAM)
2. (Opcional) `AND mask` / `BIT n` / `CP imm`
3. `JR`/`JRZ`/`JRNZ`/`JP` que vuelve al hotspot (o a un target dentro de una ventana estrecha alrededor del hotspot)

**Si solo hay `LDH A,(FF92)` seguido de `LDH (IE),A` y `RET`, eso no es "wait loop"**.**Implementar**:

```python
def parse_loop_io_pattern(disasm_window):
    """
    Parsea el disasm window y detecta automáticamente patrones de I/O.
    
    Regla: solo declarar loop_waits_on si hay:
    1. LDH A,(addr) con addr < 0xFF80 (I/O, no HRAM)
    2. AND mask / BIT n / CP imm (opcional)
    3. JR/JRZ/JRNZ/JP que vuelve al hotspot
    
    Returns:
        dict con:
        - waits_on: dirección I/O esperada (0xFF44, 0xFF41, etc.) o None
        - mask: máscara AND aplicada (0x01, 0x03, etc.)
        - cmp: valor comparado (si hay CP)
        - pattern: tipo de espera (STAT_MODE, LY_GE, IF_BIT, etc.)
    """
    waits_on = None
    mask = None
    cmp_val = None
    pattern = None
    hotspot_pc = None
    
    # Encontrar PC actual (hotspot)
    for addr, instruction, is_current in disasm_window:
        if is_current:
            hotspot_pc = addr
            break
    
    if hotspot_pc is None:
        return {"waits_on": None, "mask": None, "cmp": None, "pattern": "UNKNOWN"}
    
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
                # Solo considerar I/O (0xFF00-0xFF7F), no HRAM (0xFF80-0xFFFF)
                if 0xFF00 <= io_addr < 0xFF80:
                    io_read_addr = io_addr
                    waits_on = io_addr
        
        # Detectar AND mask
        if "AND" in instruction and waits_on:
            match = re.search(r'AND\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                mask = int(match.group(1), 16)
        
        # Detectar CP (compare)
        if "CP" in instruction and waits_on:
            match = re.search(r'CP\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                cmp_val = int(match.group(1), 16)
        
        # Detectar BIT n
        if "BIT" in instruction and waits_on:
            match = re.search(r'BIT\s+(\d+)', instruction)
            if match:
                bit_num = int(match.group(1))
                mask = 1 << bit_num
        
        # Detectar jump de vuelta al hotspot
        if waits_on and ("JR" in instruction or "JP" in instruction):
            match = re.search(r'(JR|JP)\s+(?:Z|NZ|C|NC)?\s*0x([0-9A-Fa-f]+)', instruction)
            if match:
                target = int(match.group(2), 16)
                # Verificar si el target está cerca del hotspot (ventana de ±32 bytes)
                if abs(target - hotspot_pc) <= 32:
                    jump_back_found = True
    
    # Solo declarar loop si hay I/O read Y jump de vuelta
    if not jump_back_found:
        waits_on = None
        mask = None
        cmp_val = None
        pattern = "NO_LOOP"  # No es un wait loop, es otra cosa
    
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

**Criterio de éxito A**: En mario.gbc, `loop_waits_on` debe quedar vacío o apuntar a un I/O real con compare+jump. En tetris_dx.gbc, debe seguir detectando JOYP con máscara/compare.

## Fase B: Instrumentación HRAM Quirúrgica (mario.gbc)

### B1) Tracking de HRAM[FF92]

**Archivo**: `src/core/cpp/MMU.cpp` (gated por `VIBOY_DEBUG_IO=1`)**En `MMU::write(0xFF92, value)`**:

```cpp
if (addr == 0xFF92) {
    hram_ff92_write_count_++;
    last_hram_ff92_write_pc_ = debug_current_pc;
    last_hram_ff92_write_value_ = value;
    last_hram_ff92_write_timestamp_++;
}
```

**En `MMU::read(0xFF92)`**:

```cpp
if (addr == 0xFF92) {
    if (!cpu_->is_in_irq_poll()) {  // Solo reads desde programa
        hram_ff92_read_count_program_++;
        last_hram_ff92_read_pc_ = debug_current_pc;
        last_hram_ff92_read_value_ = memory_[addr];
    }
}
```

**Archivo**: `src/core/cpp/MMU.hpp`Añadir miembros privados:

```cpp
uint32_t hram_ff92_write_count_;
uint16_t last_hram_ff92_write_pc_;
uint8_t last_hram_ff92_write_value_;
uint32_t last_hram_ff92_write_timestamp_;
uint32_t hram_ff92_read_count_program_;
uint16_t last_hram_ff92_read_pc_;
uint8_t last_hram_ff92_read_value_;
```

**Exponer getters a Python**:

```cpp
uint32_t get_hram_ff92_write_count() const;
uint16_t get_last_hram_ff92_write_pc() const;
uint8_t get_last_hram_ff92_write_value() const;
uint32_t get_last_hram_ff92_write_timestamp() const;
uint32_t get_hram_ff92_read_count_program() const;
uint16_t get_last_hram_ff92_read_pc() const;
uint8_t get_last_hram_ff92_read_value() const;
```

**Criterio de éxito B**: El snapshot por frame muestra si alguien escribe FF92 y desde qué PC. Si no hay writes, ya sabes que el juego nunca inicializa esa variable (porque no llega o porque otra condición falla antes).

## Fase C: Fix Mínimo JOYP (tetris_dx.gbc)

### C1) Semántica Mínima Correcta de JOYP

**Archivo**: `src/core/cpp/MMU.cpp` (en `MMU::read(0xFF00)` y `MMU::write(0xFF00)`)**Reglas según Pan Docs**:

1. **Bits 6-7 leídos como 1** (siempre)
2. **Writes solo afectan selección** (P14/P15 típicamente bits 4 y 5; el resto se conserva según implementación del proyecto)
3. **Lectura devuelve líneas "no presionadas" como 1** (inversión clásica), y "presionadas" como 0
4. **Con "sin input", la lectura debe satisfacer fácilmente `& 0x03 == 0x03`** en el caso que detectaste

**Implementar**:

```cpp
// En MMU::read(0xFF00)
if (addr == 0xFF00) {
    if (joypad_ != nullptr) {
        uint8_t joyp = joypad_->read_p1();
        // Bits 6-7 siempre leen como 1
        return joyp | 0xC0;
    }
    // Default: todos los bits en 1 (no presionados)
    return 0xFF;
}

// En MMU::write(0xFF00)
if (addr == 0xFF00) {
    if (joypad_ != nullptr) {
        joypad_->write_p1(value);
    }
    // Conservar bits 0-3 en memoria (según implementación)
    memory_[addr] = (memory_[addr] & 0x0F) | (value & 0xF0);
    return;
}
```

**Verificar implementación de `Joypad::read_p1()`**:**Archivo**: `src/core/cpp/Joypad.cpp` (o equivalente)**Debe devolver**:

- Bits 0-3: líneas de botones (1 = no presionado, 0 = presionado)
- Bits 4-5: selección (P14/P15)
- Bits 6-7: siempre 0 (se ponen a 1 en MMU::read)

**Con "sin input"**, todos los bits 0-3 deben ser 1 (no presionados), así que `& 0x03 == 0x03` se satisface.

### C2) Tests Clean-Room Nuevos

**Archivo**: `tests/test_joyp_default_no_input_returns_1s_0480.py`**Diseño**:

1. Inicializar sistema mínimo (MMU/Joypad)
2. Sin input (estado por defecto)
3. Leer `JOYP` (0xFF00)
4. Assert: `(joyp & 0x03) == 0x03` (bits 0-1 en 1 = no presionados)
5. Assert: `(joyp & 0xC0) == 0xC0` (bits 6-7 en 1)

**Archivo**: `tests/test_joyp_select_buttons_affects_low_nibble_0480.py`**Diseño**:

1. Inicializar sistema mínimo
2. Escribir `JOYP = 0x20` (seleccionar fila de botones, P15=1)
3. Leer `JOYP`
4. Assert: bits 0-3 reflejan estado de botones (1 = no presionado, 0 = presionado)

**Archivo**: `tests/test_joyp_select_dpad_affects_low_nibble_0480.py`**Diseño**:

1. Inicializar sistema mínimo
2. Escribir `JOYP = 0x10` (seleccionar fila de direcciones, P14=1)
3. Leer `JOYP`
4. Assert: bits 0-3 reflejan estado de direcciones (1 = no presionado, 0 = presionado)

**Criterio de éxito C**: `rom_smoke` en tetris_dx deja de estar clavado en el hotspot y cambia PC hotspots o aumenta progreso (`fb_nonzero` y/o cambia el patrón de polling).

## Fase D: Disasm_Window Sanity (tetris_dx está Sospechoso)

### D1) Fix Disasm Window

**Archivo**: `tools/rom_smoke_0442.py` (función `disasm_window()`)**Problema**: Tu disasm_window para tetris_dx muestra direcciones raras y "DB". Eso puede ser:

- Bug de ventana (no está centrando en PC_hotspot)
- Lectura de bytes sin respetar banking

**Fix**:

1. **`disasm_window(pc)` debe imprimir una línea marcada `>>> pc EXACTA` en el output**
2. **Preferible: leer bytes con MMU (no con ROM file raw), para respetar MBC/banco**

**Implementar**:

```python
def disasm_window(mmu, pc, before=16, after=32):
    """
    Disasmar ventana alrededor de PC para evitar empezar en mitad de instrucción.
    
    Args:
        mmu: Instancia MMU (para respetar banking)
        pc: PC actual (centro de la ventana)
        before: Bytes antes de PC a leer
        after: Bytes después de PC a leer
    
    Returns:
        Lista de (addr, instruction, is_current_pc)
    """
    start_addr = (pc - before) & 0xFFFF
    end_addr = (pc + after) & 0xFFFF
    
    # Leer bytes de ROM usando MMU (respeta banking)
    bytes_data = []
    for addr in range(start_addr, end_addr + 1):
        bytes_data.append(mmu.read(addr))
    
    # Disasmar desde start_addr
    instructions = []
    offset = 0
    current_pc = pc
    
    while offset < len(bytes_data):
        addr = (start_addr + offset) & 0xFFFF
        is_current = (addr == current_pc)
        
        # Disasmar instrucción
        instruction = disasm_lr35902(bytes_data, offset, start_addr + offset)
        
        # Marcar PC actual explícitamente
        if is_current:
            instruction = f">>> {instruction} <<< PC ACTUAL"
        
        instructions.append((addr, instruction, is_current))
        
        # Avanzar según longitud de instrucción
        opcode = bytes_data[offset]
        if opcode == 0xCB:
            offset += 2  # CB prefix consume 2 bytes
        elif opcode in [0xE0, 0xF0, 0xEA, 0xFA]:
            offset += 3  # LDH/LD (a16) consumen 3 bytes
        else:
            offset += 1  # Default: 1 byte
        
        if offset >= len(bytes_data):
            break
    
    return instructions
```

**Criterio de éxito D**: En el reporte, la línea del hotspot aparece y se decodifica como instrucción válida, no como "DB" basura.

## Fase E: Ejecutar rom_smoke y Emitir Reporte 0480

### E1) Baseline Limpio

**Flags obligatorios**:

```bash
export VIBOY_SIM_BOOT_LOGO=0  # Obligatorio para no contaminar VRAM/tilemap stats
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0
```



### E2) Comandos Exactos

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0480_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0480_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0480_tetris.log
```



### E3) Snapshots (Frames 0/60/120/180) Deben Incluir

**Loop pattern** (ya):

- `loop_waits_on`/`mask`/`cmp`/`pattern`

**JOYP** (si aplica):

- `last_joyp_read_value`, `last_joyp_write_value`
- `joyp_select_bits` (P14/P15, si está instrumentado)

**HRAM FF92** (mario.gbc):

- `hram_ff92_read_count_program`
- `hram_ff92_write_count`
- `last_hram_ff92_write_pc`/`value`/`timestamp`
- `last_hram_ff92_read_pc`/`value`

**Mantener source tagging**:

- `if_reads_program` vs `if_reads_cpu_poll`
- `ie_reads_program` vs `ie_reads_cpu_poll`

**Mantener**:

- `PC`, `PC_hotspot1`, `disasm_window` (con PC marcada)
- `IME`, `IE`, `EIcount`, `ime_set_events_count`
- `fb_nonzero`
- `boot_logo_prefill_enabled` (debe ser 0 en baseline)

### E4) Criterio de Éxito E

- **tetris_dx**: El loop JOYP se rompe o al menos cambia de condición / hotspot
- **mario**: Sabemos si FF92 se escribe o no, y desde qué PC

## Entregables Obligatorios

1. **Diff del fix en `tools/rom_smoke_0442.py`** (parser corregido + disasm_window con PC marcada)
2. **Diff del fix en `MMU.cpp/MMU.hpp`** (instrumentación HRAM[FF92] gated)
3. **Diff del fix en `MMU.cpp` y `Joypad.cpp`** (semántica JOYP correcta)
4. **Tests `test_joyp_*_0480.py` pasando**
5. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0480.md`** con:

- Para cada ROM CGB:
    - `PC_hotspot1`
    - `disasm_window(PC_hotspot1)` con PC marcada (10-20 instrucciones)
    - `loop_waits_on`/`mask`/`cmp`/`pattern` (parser corregido)
    - JOYP metrics (si aplica)
    - HRAM FF92 metrics (mario.gbc)
- Decisión automática: ¿JOYP fix desbloquea tetris_dx? ¿HRAM[FF92] se escribe en mario?
- Resultado: ¿Los loops se desbloquean?

## Comandos Exactos

### Build

```bash
python3 setup.py build_ext --inplace
```



### Tests

```bash
pytest -q tests/test_joyp_*_0480.py
pytest -q tests/test_if_upper_bits_read_as_1_0474.py tests/test_if_clear_0474.py  # Anti-regresión
```



### rom_smoke (Baseline Limpio)

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0480_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0480_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0480_tetris.log
```



### Análisis (Sin Saturar Contexto)

```bash
# Solo snapshots
grep -E "\[SMOKE-SNAPSHOT\]" /tmp/viboy_0480_*.log | head -n 260
```



## Documentación

**⚠️ IMPORTANTE**: NO documentar hasta tener el reporte `/tmp/reporte_step0480.md` completo. Documentar antes es el patrón que genera "steps completados" que luego no sostienen la realidad.

### Bitácora HTML

**Archivo**: `docs/bitacora/entries/2026-01-04__0480__cerrar-loops-joyp-hram-ff92.html`**Framing correcto**:

- "Step 0479 identificó loops pero con errores de interpretación: 0xFF92 es HRAM no I/O, STAT_LastRead=0x00 no demuestra bug si no se lee. Step 0480 corrige el parser, instrumenta HRAM[FF92], y aplica fix mínimo JOYP para desbloquear tetris_dx."

**Incluir en HTML**:

- Correcciones de interpretación (FF92=HRAM, STAT solo si se lee)
- Disasm window con PC marcada (10-20 instrucciones) para cada ROM CGB
- Loop pattern (parser corregido)
- JOYP metrics y fix aplicado
- HRAM FF92 metrics (mario.gbc)
- Decisión automática y resultado

### Informe Dividido

**Archivo**: `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o la parte que contenga Step 0480)Añadir entrada al principio de "## Entradas de Desarrollo".

### Update `docs/bitacora/index.html`

Añadir entrada 0480 al principio de `<ul class="entry-list">` (formato antiguo, homogéneo con entradas anteriores).

## Git

```bash
git add .
git commit -m "fix(joyp/mmu): semántica JOYP correcta + instrumentación HRAM FF92 + parser corregido (step 0480)"
git push
```



## Criterios de Éxito

1. Tests `test_joyp_*_0480.py` pasan
2. **⚠️ CRÍTICO: Parser corregido** (FF92 no se marca como I/O, solo loops reales con jump de vuelta)
3. **⚠️ CRÍTICO: Disasm window con PC marcada** (no más "DB" basura)
4. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0480.md` completo** con:

- Disasm window con PC marcada para cada ROM CGB
- Loop pattern (parser corregido)
- JOYP metrics y fix aplicado
- HRAM FF92 metrics (mario.gbc)
- Decisión automática: ¿JOYP fix desbloquea tetris_dx? ¿HRAM[FF92] se escribe en mario?
- Resultado: ¿Los loops se desbloquean?

5. **NO se repite**:

- "FF92 = I/O CGB" (es HRAM)
- "STAT roto" sin `stat_reads_program > 0`
- Usar VRAMNZ/tilemapNZ como señal del juego con prefill ON