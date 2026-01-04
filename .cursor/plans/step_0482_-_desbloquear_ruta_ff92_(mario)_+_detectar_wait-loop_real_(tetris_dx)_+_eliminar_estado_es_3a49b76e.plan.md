---
name: Step 0482 - Desbloquear ruta FF92 (Mario) + detectar wait-loop real (Tetris DX) + eliminar estado estático
overview: Desbloquear la ruta hacia FF92 (Mario) identificando EXACTAMENTE qué condición bloquea llegar a PC=0x1288 (donde está el writer). Detectar wait-loop real en Tetris DX aunque el parser no lo vea (dynamic detector + completar disassembler). Eliminar estado estático compartido entre tests que causa falsos negativos. El próximo avance no sale de "más contadores"; sale de ver qué branch se repite y qué condición no cambia.
todos:
  - id: 0482-t0-eliminate-static
    content: "Eliminar estado estático compartido entre tests: Opción A (convertir contadores/telemetría de static a miembros de instancia en MMU/CPU) o Opción B (añadir reset_debug_counters_for_tests() en MMU/CPU, llamado en setup_method de tests). Criterio: suite limpia, 0 flakes, 7/7."
    status: pending
  - id: 0482-t1-branch-counters
    content: "Implementar Branch Decision Counters en CPU.cpp/CPU.hpp: contadores por PC para saltos condicionales (taken_count, not_taken_count), last_cond_jump_pc/target/taken/flags. Gate: VIBOY_DEBUG_BRANCH=1. Exponer getters a Python."
    status: pending
    dependencies:
      - 0482-t0-eliminate-static
  - id: 0482-t2-last-compare-tracking
    content: "Implementar Last Compare Tracking en CPU.cpp/CPU.hpp: last_cmp_pc/a/imm/result_flags, last_bit_pc/n/value. En opcodes CP y BIT, guardar tracking. Gate: VIBOY_DEBUG_BRANCH=1. Exponer getters a Python."
    status: pending
    dependencies:
      - 0482-t0-eliminate-static
  - id: 0482-t3-lcdc-disable-tracking
    content: "Implementar LCDC Disable Tracking en MMU.cpp/MMU.hpp: lcdc_disable_events_, last_lcdc_write_pc/value. Detectar cuando LCDC bit7 pasa de 1→0. Implementar handle_lcd_disable() en PPU.cpp/PPU.hpp: reset LY→0, STAT mode→HBlank, limpiar frame_ready. Exponer getters a Python."
    status: pending
  - id: 0482-t4-test-lcdc-disable
    content: "Crear tests/test_lcdc_disable_resets_ly_0482.py: escribir LCDC bit7=1, step ciclos, confirmar LY progresa, escribir LCDC bit7=0, step ciclos, assert LY→0, STAT mode estable, lcdc_disable_events==1. Criterio: test pasa. Si falla, candidato fuerte para bloqueo de Mario."
    status: pending
    dependencies:
      - 0482-t3-lcdc-disable-tracking
  - id: 0482-t5-dynamic-wait-loop-detector
    content: "Implementar detect_dynamic_wait_loop() en tools/rom_smoke_0442.py: durante N iteraciones en hotspot, registrar I/O reads program, sacar I/O dominante y distribución, correlacionar con last_cmp/bit para etiquetar waits_on_addr, mask/cmp/bit. Esto funciona aunque disasm esté incompleto."
    status: pending
    dependencies:
      - 0482-t1-branch-counters
      - 0482-t2-last-compare-tracking
  - id: 0482-t6-unknown-opcode-histogram
    content: "Implementar get_unknown_opcode_histogram() en tools/rom_smoke_0442.py: contar opcodes desconocidos (DB) en disasm window, retornar top 10. En snapshot del hotspot, mostrar top 10 unknown opcodes. Objetivo: priorizar completar disassembler por frecuencia real."
    status: pending
  - id: 0482-t7-rom-smoke-snapshots
    content: "Modificar tools/rom_smoke_0442.py para añadir a snapshots: branch counters top 5 (taken/not_taken), last_cmp/bit (pc/a/imm/flags, pc/n/value), LCDC disable events + last_lcdc_write_pc/value, dynamic wait-loop detection (I/O dominante, distribución), unknown opcode histogram (top 10)."
    status: pending
    dependencies:
      - 0482-t1-branch-counters
      - 0482-t2-last-compare-tracking
      - 0482-t3-lcdc-disable-tracking
      - 0482-t5-dynamic-wait-loop-detector
      - 0482-t6-unknown-opcode-histogram
  - id: 0482-t8-execute-rom-smoke
    content: "Ejecutar rom_smoke para mario.gbc, tetris_dx.gbc, tetris.gb (240 frames baseline VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_BRANCH=1, VIBOY_DEBUG_HRAM=1). Extraer snapshots y aplicar análisis. Criterio: Mario identifica por qué NO llega a 0x1288, Tetris DX I/O dominante identificado."
    status: pending
    dependencies:
      - 0482-t7-rom-smoke-snapshots
  - id: 0482-t9-create-report
    content: "Crear reporte markdown /tmp/reporte_step0482.md con: higiene (fix aplicado, resultado), Mario (branch counters top 5, last_cmp/bit, LCDC disable events, por qué NO llega a 0x1288), Tetris DX (I/O dominante dynamic, last_cmp/bit, unknown opcode histogram, conclusión), siguiente fix mínimo propuesto (0483)."
    status: pending
    dependencies:
      - 0482-t8-execute-rom-smoke
  - id: 0482-t10-document
    content: "Documentar Step 0482 en bitácora HTML e informe dividido. Framing: desbloquear ruta FF92 + detectar wait-loop real. Incluir higiene, branch counters, LCDC disable, dynamic detector, conclusión, siguiente fix. Update docs/bitacora/index.html y docs/informe_fase_2/."
    status: pending
    dependencies:
      - 0482-t9-create-report
---

# Step 0482: Desb

loquear Ruta FF92 (Mario) + Detectar Wait-Loop Real (Tetris DX) + Eliminar Estado Estático

## Objetivo

1. **mario.gbc**: Identificar EXACTAMENTE qué condición bloquea llegar a PC=0x1288 (donde está el writer de FF92)
2. **tetris_dx.gbc**: Detectar wait-loop real aunque el parser no lo vea (dynamic detector + completar disassembler)
3. **Higiene**: Eliminar estado estático compartido entre tests que causa falsos negativos

**Contexto crítico**: Step 0481 os dio la prueba que necesitabais: no es FF92, es control flow bloqueado. Ya no es "falta implementar FF92": el writer existe (PC=0x1288) y no se alcanza. Eso significa bloqueo de control flow (condición de espera que nunca cambia), no "registro desconocido".**Conclusión crítica**: El próximo avance no sale de "más contadores"; sale de ver qué branch se repite y qué condición no cambia.**Problema adicional**: Test fallando por estáticos compartidos es deuda técnica que os va a envenenar cada paso: hay que matar el estado global o resetearlo bien.

## Fase 0: Higiene - Eliminar Falsos Negativos por Estado Global

### 0.1) Problema Identificado

El test relacionado con `irq_poll` falla por variables estáticas compartidas entre tests.

### 0.2) Fix Mínimo (Elegir Uno, pero Hacerlo de Verdad, No Parche)

#### Opción A (Mejor): Convertir Contadores/Telemetría en Miembros de Instancia

**Archivo**: `src/core/cpp/MMU.cpp` y `src/core/cpp/MMU.hpp`**Convertir contadores/watch entries/telemetría de `static` a miembros de instancia** (MMU/CPU), no static.**Ejemplo**:**Antes** (static):

```cpp
static uint32_t ie_write_count = 0;
```

**Después** (miembro de instancia):

```cpp
// En MMU.hpp
uint32_t ie_write_count_;

// En MMU.cpp constructor
ie_write_count_(0)

// En MMU.cpp write
ie_write_count_++;
```

**Aplicar a todos los contadores/telemetría**:

- `ie_write_count`, `if_write_count`
- `ie_reads_program_`, `ie_reads_cpu_poll_`, etc.
- `hram_watchlist_`
- Cualquier otra variable `static` relacionada con telemetría

**Archivo**: `src/core/cpp/CPU.cpp` y `src/core/cpp/CPU.hpp`**Similar para CPU**:

- `ei_count_global`, `di_count_global`
- `ime_set_events_count_`, etc.

#### Opción B (Rápida y Aceptable): Reset en setup_method

**Archivo**: Tests (pytest fixtures o setup_method)**Añadir `reset_debug_counters_for_tests()` en MMU y CPU, llamado en `setup_method()` de tests**.**Implementar**:

```cpp
// En MMU.hpp
void reset_debug_counters_for_tests();

// En MMU.cpp
void MMU::reset_debug_counters_for_tests() {
    ie_write_count_ = 0;
    if_write_count_ = 0;
    // ... reset todos los contadores
}

// En CPU.hpp
void reset_debug_counters_for_tests();

// En CPU.cpp
void CPU::reset_debug_counters_for_tests() {
    ei_count_global_ = 0;
    di_count_global_ = 0;
    ime_set_events_count_ = 0;
    // ... reset todos los contadores
}
```

**En tests**:

```python
def setup_method(self):
    # ...
    self.mmu.reset_debug_counters_for_tests()
    self.cpu.reset_debug_counters_for_tests()
```

**Criterio de éxito 0**: Suite limpia, 0 flakes, 7/7.

## Fase A: Mario - Identificar EXACTAMENTE Qué Condición Bloquea Llegar a PC=0x1288

### A1) "Branch Decision Counters" (En CPU, Gated)

**Archivo**: `src/core/cpp/CPU.cpp` y `src/core/cpp/CPU.hpp`**Instrumentar contadores por PC para**:**Implementar**:

```cpp
// En CPU.hpp
struct BranchDecision {
    uint16_t pc;
    uint32_t taken_count;
    uint32_t not_taken_count;
    uint16_t last_target;
    bool last_taken;
    uint8_t last_flags;  // Flags al momento del salto
};

std::map<uint16_t, BranchDecision> branch_decisions_;
uint16_t last_cond_jump_pc_;
uint16_t last_target_;
bool last_taken_;
uint8_t last_flags_;
```

**En `CPU::step()` cuando se ejecuta salto condicional** (JR Z/NZ/C/NC, JP Z/NZ/C/NC, RET Z/NZ/C/NC, etc.):

```cpp
// Ejemplo para JR Z
case 0x28:  // JR Z, e
    {
        int8_t offset = static_cast<int8_t>(read_byte(regs_->pc++));
        uint16_t target = regs_->pc + offset;
        bool taken = regs_->get_flag_z();
        
        // Actualizar branch decision
        if (branch_decisions_.find(regs_->pc - 2) == branch_decisions_.end()) {
            branch_decisions_[regs_->pc - 2] = {regs_->pc - 2, 0, 0, target, false, 0};
        }
        auto& bd = branch_decisions_[regs_->pc - 2];
        if (taken) {
            bd.taken_count++;
        } else {
            bd.not_taken_count++;
        }
        bd.last_target = target;
        bd.last_taken = taken;
        bd.last_flags = regs_->get_flags();
        
        last_cond_jump_pc_ = regs_->pc - 2;
        last_target_ = target;
        last_taken_ = taken;
        last_flags_ = regs_->get_flags();
        
        if (taken) {
            regs_->pc = target;
            cycles_ += 3;
            return 3;
        } else {
            cycles_ += 2;
            return 2;
        }
    }
```

**Gate**: `VIBOY_DEBUG_BRANCH=1`**Exponer getters a Python**:

```cpp
uint32_t get_branch_taken_count(uint16_t pc) const;
uint32_t get_branch_not_taken_count(uint16_t pc) const;
uint16_t get_last_cond_jump_pc() const;
uint16_t get_last_target() const;
bool get_last_taken() const;
uint8_t get_last_flags() const;
```

**Esto te dice**: Qué salto condicional está siempre tomado, o siempre no tomado, bloqueando el progreso.

### A2) "Last Compare" Tracking (En CPU)

**Archivo**: `src/core/cpp/CPU.cpp` y `src/core/cpp/CPU.hpp`**Guardar el último CP/AND/BIT relevante**:**Implementar**:

```cpp
// En CPU.hpp
uint16_t last_cmp_pc_;
uint8_t last_cmp_a_;
uint8_t last_cmp_imm_;
uint8_t last_cmp_result_flags_;
uint16_t last_bit_pc_;
uint8_t last_bit_n_;
uint8_t last_bit_value_;
```

**En `CPU::step()` cuando se ejecuta CP**:

```cpp
case 0xFE:  // CP n
    {
        uint8_t imm = read_byte(regs_->pc++);
        uint8_t a = regs_->get_a();
        
        // Tracking
        last_cmp_pc_ = regs_->pc - 2;
        last_cmp_a_ = a;
        last_cmp_imm_ = imm;
        last_cmp_result_flags_ = regs_->get_flags();  // Después de la comparación
        
        // ... resto de la lógica CP
    }
```

**En `CPU::step()` cuando se ejecuta BIT**:

```cpp
case 0xCB:  // Prefijo CB
    {
        uint8_t cb_opcode = read_byte(regs_->pc++);
        if ((cb_opcode & 0xF8) == 0x40) {  // BIT n, r
            uint8_t bit_num = (cb_opcode >> 3) & 0x07;
            uint8_t reg = cb_opcode & 0x07;
            uint8_t value = get_register_8(reg);
            uint8_t bit_value = (value >> bit_num) & 0x01;
            
            // Tracking
            last_bit_pc_ = regs_->pc - 2;
            last_bit_n_ = bit_num;
            last_bit_value_ = bit_value;
            
            // ... resto de la lógica BIT
        }
    }
```

**Gate**: `VIBOY_DEBUG_BRANCH=1`**Exponer getters a Python**:

```cpp
uint16_t get_last_cmp_pc() const;
uint8_t get_last_cmp_a() const;
uint8_t get_last_cmp_imm() const;
uint8_t get_last_cmp_result_flags() const;
uint16_t get_last_bit_pc() const;
uint8_t get_last_bit_n() const;
uint8_t get_last_bit_value() const;
```

**Resultado esperado**: En el hotspot (0x12A0 / zona 0x128C..0x1292) podrás decir:

- "está esperando que BIT n de X sea 1" o
- "está esperando que (A & mask) == cmp"

y qué valor está viendo realmente.

### A3) LCDC-Off / LY Reset Sanity (Muy Probable)

**Archivo**: `src/core/cpp/MMU.cpp` y `src/core/cpp/MMU.hpp`**En tus disasm anteriores de Mario aparece**:

```javascript
LDH A,(LCDC)
AND 0x7F
LDH (LCDC),A  (apagar LCD)
```

Muchísimos juegos hacen: "apago LCD y espero a que LY se resetee / PPU se pare".**Instrumentación**:**En `MMU::write(0xFF40, value)`**:

```cpp
if (addr == 0xFF40) {  // LCDC
    uint8_t old_lcdc = memory_[addr];
    uint8_t new_lcdc = value;
    bool lcd_on_old = (old_lcdc & 0x80) != 0;
    bool lcd_on_new = (new_lcdc & 0x80) != 0;
    
    // Tracking
    last_lcdc_write_pc_ = debug_current_pc;
    last_lcdc_write_value_ = value;
    
    // Detectar disable (1→0)
    if (lcd_on_old && !lcd_on_new) {
        lcdc_disable_events_++;
    }
    
    // ... resto de la lógica
}
```

**Archivo**: `src/core/cpp/MMU.hpp`Añadir miembros privados:

```cpp
uint32_t lcdc_disable_events_;
uint16_t last_lcdc_write_pc_;
uint8_t last_lcdc_write_value_;
```

**Archivo**: `src/core/cpp/PPU.cpp` y `src/core/cpp/PPU.hpp`**En PPU, cuando LCDC bit7 pasa de 1→0, asegurar comportamiento consistente (mínimo)**:

- LY acaba en 0 (o se fuerza a 0 tras el apagado)
- STAT mode en estado estable (no 3 eterno)
- No queda "frame pending" infinito

**Implementar**:

```cpp
// En PPU.hpp
void handle_lcd_disable();

// En PPU.cpp
void PPU::handle_lcd_disable() {
    // Cuando LCD se apaga (LCDC bit7 = 0):
    // - LY se resetea a 0
    ly_ = 0;
    ly_internal_ = 0;
    
    // - STAT mode en estado estable (Mode 0 = HBlank)
    mode_ = PPUMode::HBLANK;
    
    // - No queda frame pending infinito
    frame_ready_ = false;
    framebuffer_swap_pending_ = false;
}
```

**En `MMU::write(0xFF40, value)`**:

```cpp
if (lcd_on_old && !lcd_on_new) {
    lcdc_disable_events_++;
    if (ppu_ != nullptr) {
        ppu_->handle_lcd_disable();
    }
}
```

**Exponer getters a Python**:

```cpp
uint32_t get_lcdc_disable_events() const;
uint16_t get_last_lcdc_write_pc() const;
uint8_t get_last_lcdc_write_value() const;
```

**Criterio de éxito A3**: Si este test falla hoy, es un candidato fuerte para el bloqueo de Mario.

### A4) Test Clean-Room LCDC Disable Resets LY

**Archivo**: `tests/test_lcdc_disable_resets_ly_0482.py`**Diseño**:

1. Inicializar sistema mínimo (MMU/CPU/PPU)
2. Escribir `LCDC` con `bit7=1` (encender LCD)
3. Dejar correr ciclos suficientes (ej. 456 ciclos × 10 scanlines = 4560 ciclos)
4. Confirmar `LY` progresa (debe ser > 0)
5. Escribir `LCDC` con `bit7=0` (apagar LCD)
6. Dejar correr ciclos suficientes
7. Verificar:

- `LY → 0` y se estabiliza
- `STAT mode` en estado estable (Mode 0 = HBlank)
- `lcdc_disable_events == 1`

**Criterio de éxito A4**: Test pasa. Si falla, es un candidato fuerte para el bloqueo de Mario.

## Fase B: Tetris DX - Detectar Wait-Loop Real Aunque el Parser No lo Vea

### B1) Dynamic Wait-Loop Detector (En rom_smoke)

**Archivo**: `tools/rom_smoke_0442.py`**Cuando detectes un hotspot estable, haz durante N iteraciones**:

1. Registrar I/O reads program en ese rango de PCs (ya tenéis source tagging)
2. Sacar el "IO read dominante" y su distribución
3. Eso te da: "en el loop, el juego lee sobre todo: JOYP / IF / STAT / LY / algo"
4. Luego correlaciona con `last_cmp` / `last_bit` para etiquetar:

- `waits_on_addr`
- `mask`/`cmp` o `bit`

**Implementar**:

```python
def detect_dynamic_wait_loop(mmu, cpu, hotspot_pc, window_size=32, iterations=100):
    """
    Detecta wait-loop dinámicamente analizando I/O reads en hotspot.
    
    Args:
        mmu: Instancia MMU
        cpu: Instancia CPU
        hotspot_pc: PC del hotspot
        window_size: Ventana de bytes alrededor del hotspot
        iterations: Número de iteraciones a analizar
    
    Returns:
        dict con: waits_on_addr, mask, cmp, bit, io_reads_distribution
    """
    io_reads_counter = {}  # addr -> count
    
    # Reset contadores antes de empezar
    # (asumir que MMU tiene método para resetear contadores de I/O reads program)
    
    start_pc = (hotspot_pc - window_size) & 0xFFFF
    end_pc = (hotspot_pc + window_size) & 0xFFFF
    
    # Ejecutar N iteraciones y contar I/O reads program
    for i in range(iterations):
        # Step CPU hasta que PC esté en la ventana del hotspot
        while True:
            cpu.step()
            current_pc = cpu.get_pc()
            if start_pc <= current_pc <= end_pc or current_pc == hotspot_pc:
                break
    
    # Obtener contadores de I/O reads program
    # (asumir que MMU expone getters para if_reads_program, ie_reads_program, etc.)
    io_reads_counter[0xFF0F] = mmu.get_if_reads_program()
    io_reads_counter[0xFFFF] = mmu.get_ie_reads_program()
    io_reads_counter[0xFF44] = mmu.get_ly_read_count_program()  # Si existe
    io_reads_counter[0xFF41] = mmu.get_stat_read_count_program()  # Si existe
    io_reads_counter[0xFF00] = mmu.get_joyp_read_count_program()
    
    # Encontrar I/O read dominante
    if io_reads_counter:
        waits_on_addr = max(io_reads_counter, key=io_reads_counter.get)
        dominant_count = io_reads_counter[waits_on_addr]
    else:
        waits_on_addr = None
        dominant_count = 0
    
    # Correlacionar con last_cmp / last_bit
    last_cmp_pc = cpu.get_last_cmp_pc()
    last_cmp_a = cpu.get_last_cmp_a()
    last_cmp_imm = cpu.get_last_cmp_imm()
    last_bit_pc = cpu.get_last_bit_pc()
    last_bit_n = cpu.get_last_bit_n()
    last_bit_value = cpu.get_last_bit_value()
    
    # Determinar mask/cmp/bit
    mask = None
    cmp_val = None
    bit_num = None
    
    if last_bit_pc != 0 and abs(last_bit_pc - hotspot_pc) <= window_size:
        bit_num = last_bit_n
        mask = 1 << bit_num
        cmp_val = 1  # BIT espera bit = 1
    
    if last_cmp_pc != 0 and abs(last_cmp_pc - hotspot_pc) <= window_size:
        cmp_val = last_cmp_imm
    
    return {
        "waits_on_addr": waits_on_addr,
        "mask": mask,
        "cmp": cmp_val,
        "bit": bit_num,
        "io_reads_distribution": io_reads_counter
    }
```

**Esto funciona aunque el disasm esté incompleto**.**Criterio de éxito B1**: tetris_dx reporta I/O dominante con valores concretos.

### B2) Priorizar Completar el Disassembler por "Unknown Opcode Histogram"

**Archivo**: `tools/rom_smoke_0442.py`**En vez de "implemento opcodes al azar"**:

1. Loggear top 10 bytes "unknown opcode" en el hotspot
2. Implementar esos opcodes primero

**Implementar**:

```python
def get_unknown_opcode_histogram(disasm_window):
    """
    Cuenta opcodes desconocidos (DB) en disasm window.
    
    Returns:
        dict: opcode -> count
    """
    unknown_opcodes = {}
    
    for addr, instruction, is_current in disasm_window:
        if instruction.startswith("DB "):
            # Extraer byte
            import re
            match = re.search(r'DB\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                opcode = int(match.group(1), 16)
                unknown_opcodes[opcode] = unknown_opcodes.get(opcode, 0) + 1
    
    # Ordenar por count (descendente)
    sorted_opcodes = sorted(unknown_opcodes.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_opcodes[:10]  # Top 10
```

**En `rom_smoke_0442.py`, en el snapshot del hotspot**:

```python
# Obtener histograma de opcodes desconocidos
unknown_opcodes = get_unknown_opcode_histogram(disasm_window)
if unknown_opcodes:
    print(f"[DISASM-UNKNOWN] Top 10 unknown opcodes en hotspot:")
    for opcode, count in unknown_opcodes:
        print(f"  0x{opcode:02X}: {count} veces")
```

**Objetivo**: Que el disasm en hotspot deje de ser "DB" basura.**Criterio de éxito B2**: Top 10 opcodes desconocidos identificados y priorizados para implementar.

## Fase C: Ejecutar rom_smoke y Decidir Fixes Mínimos

### C1) Baseline Obligatorio

**Flags**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_HRAM=1
export VIBOY_DEBUG_BRANCH=1
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0
```



### C2) Comandos Exactos

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_HRAM=1
export VIBOY_DEBUG_BRANCH=1
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0482_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0482_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0482_tetris.log
```



### C3) Reporte `/tmp/reporte_step0482.md`

**Estructura**:

```markdown
# Reporte Step 0482: Desbloquear Ruta FF92 + Detectar Wait-Loop Real

## Configuración

- Baseline: VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_HRAM=1, VIBOY_DEBUG_BRANCH=1, VIBOY_DEBUG_IO=1

## Higiene (Fase 0)

**Fix aplicado**: Opción A/B

**Resultado**: Suite limpia, 0 flakes, 7/7

## mario.gbc (Fase A)

### Branch Counters Top 5

| PC | Taken | Not Taken | Ratio | Last Target | Last Taken | Last Flags |
|----|-------|-----------|-------|-------------|------------|------------|
| ...| ...   | ...       | ...   | ...         | ...        | ...        |

### Last Compare/BIT en Hotspot

- `last_cmp_pc`: `0x????`
- `last_cmp_a`: `0x??`
- `last_cmp_imm`: `0x??`
- `last_cmp_result_flags`: `0x??`
- `last_bit_pc`: `0x????`
- `last_bit_n`: `?`
- `last_bit_value`: `?`

### LCDC Disable Events

- `lcdc_disable_events`: `?`
- `last_lcdc_write_pc`: `0x????`
- `last_lcdc_write_value`: `0x??`
- `LY` después de disable: `?`
- `STAT mode` después de disable: `?`

### Por Qué NO Llega a 0x1288

**Conclusión**: [Descripción basada en branch counters + last_cmp/bit + LCDC disable]

**Siguiente fix mínimo (0483)**: [Propuesta basada en evidencia]

## tetris_dx.gbc (Fase B)

### Dynamic Wait-Loop Detection

- **I/O dominante**: `0xFF??` (JOYP/IF/STAT/LY/otro)
- **I/O reads distribution**:
    - `0xFF00` (JOYP): `??? reads`
    - `0xFF0F` (IF): `??? reads`
    - `0xFF41` (STAT): `??? reads`
    - `0xFF44` (LY): `??? reads`
    - ...

### Last Compare/BIT Asociado

- `last_cmp_pc`: `0x????`
- `last_cmp_imm`: `0x??`
- `last_bit_pc`: `0x????`
- `last_bit_n`: `?`

### Unknown Opcode Histogram (Top 10)

| Opcode | Count |
|--------|-------|
| 0x??   | ???   |
| ...    | ...   |

### Conclusión

**Loop espera**: JOYP / IF / STAT / LY / otro

**Siguiente fix mínimo (0483)**: [Propuesta basada en evidencia]
```

**Criterio de éxito C**:

- **Mario**: Branch counters top 5, last_cmp/bit en hotspot, LCDC disable events + LY/STAT alrededor, "por qué NO llega a 0x1288"
- **Tetris DX**: I/O dominante en hotspot (dynamic), last_cmp/bit asociado, conclusión "espera JOYP" o "espera X"

## Entregables Obligatorios

1. **Diff del fix en `MMU.cpp/MMU.hpp` y `CPU.cpp/CPU.hpp`** (estado estático eliminado - Opción A o B)
2. **Diff del fix en `CPU.cpp/CPU.hpp`** (branch decision counters + last compare/bit tracking)
3. **Diff del fix en `MMU.cpp/MMU.hpp` y `PPU.cpp/PPU.hpp`** (LCDC disable tracking + handle_lcd_disable)
4. **Diff del fix en `tools/rom_smoke_0442.py`** (dynamic wait-loop detector + unknown opcode histogram)
5. **Tests `test_lcdc_disable_resets_ly_0482.py` pasando** (y otros tests anti-regresión)
6. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0482.md`** con:

- Higiene: Fix aplicado (Opción A/B) y resultado
- Mario: Branch counters top 5, last_cmp/bit, LCDC disable events, "por qué NO llega a 0x1288"
- Tetris DX: I/O dominante (dynamic), last_cmp/bit, unknown opcode histogram, conclusión
- Siguiente fix mínimo propuesto (0483) basado en evidencia

## Comandos Exactos

### Build

```bash
python3 setup.py build_ext --inplace
```



### Tests

```bash
pytest -q tests/test_lcdc_disable_resets_ly_0482.py
pytest -q tests/test_hram_ff92_tracking_0481.py tests/test_joyp_metrics_0481.py  # Anti-regresión
# Verificar que suite completa pasa (0 flakes, 7/7)
```



### rom_smoke (Baseline Obligatorio)

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_HRAM=1
export VIBOY_DEBUG_BRANCH=1
export VIBOY_DEBUG_IO=1
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0
export VIBOY_FRAMEBUFFER_TRACE=0

python3 tools/rom_smoke_0442.py /ruta/mario.gbc     --frames 240 | tee /tmp/viboy_0482_mario.log
python3 tools/rom_smoke_0442.py /ruta/tetris_dx.gbc --frames 240 | tee /tmp/viboy_0482_tdx.log
python3 tools/rom_smoke_0442.py /ruta/tetris.gb     --frames 240 | tee /tmp/viboy_0482_tetris.log
```



### Análisis (Sin Saturar Contexto)

```bash
# Solo snapshots
grep -E "\[SMOKE-SNAPSHOT\]" /tmp/viboy_0482_*.log | head -n 260

# Branch counters (si están gated)
grep -E "\[BRANCH-DECISION\]" /tmp/viboy_0482_*.log | head -n 100

# Unknown opcodes
grep -E "\[DISASM-UNKNOWN\]" /tmp/viboy_0482_*.log | head -n 50
```



## Documentación

**⚠️ IMPORTANTE**: NO documentar hasta tener el reporte `/tmp/reporte_step0482.md` completo. Documentar antes es el patrón que genera "steps completados" que luego no sostienen la realidad.

### Bitácora HTML

**Archivo**: `docs/bitacora/entries/2026-01-04__0482__desbloquear-ruta-ff92-detectar-wait-loop-real.html`**Framing correcto**:

- "Step 0481 demostró que FF92 writer existe pero no se alcanza (control flow bloqueado). Step 0482 identifica qué condición bloquea llegar a PC=0x1288 (Mario), detecta wait-loop real en Tetris DX (dynamic detector), y elimina estado estático compartido entre tests."

**Incluir en HTML**:

- Higiene: Fix aplicado (Opción A/B) y resultado
- Mario: Branch counters top 5, last_cmp/bit, LCDC disable events, conclusión
- Tetris DX: I/O dominante (dynamic), last_cmp/bit, unknown opcode histogram, conclusión
- Siguiente fix mínimo propuesto (0483)

### Informe Dividido

**Archivo**: `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o la parte que contenga Step 0482)Añadir entrada al principio de "## Entradas de Desarrollo".

### Update `docs/bitacora/index.html`

Añadir entrada 0482 al principio de `<ul class="entry-list">` (formato antiguo, homogéneo con entradas anteriores).

## Git

```bash
git add .
git commit -m "feat(cpu/mmu/tools): branch tracking + LCDC disable + dynamic wait-loop detector (step 0482)"
git push
```



## Criterios de Éxito

1. **⚠️ CRÍTICO: Estado estático eliminado** (Opción A o B) - Suite limpia, 0 flakes, 7/7
2. Test `test_lcdc_disable_resets_ly_0482.py` pasa
3. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0482.md` completo** con:

- Higiene: Fix aplicado y resultado
- Mario: Branch counters top 5, last_cmp/bit, LCDC disable events, "por qué NO llega a 0x1288"
- Tetris DX: I/O dominante (dynamic), last_cmp/bit, unknown opcode histogram, conclusión
- Siguiente fix mínimo propuesto (0483)

4. Bitácora/informe actualizados con reporte y decisión automática

## Conclusión Crítica (Sin Azúcar)

**Step 0481 os dio la prueba que necesitabais: no es FF92, es control flow bloqueado.**