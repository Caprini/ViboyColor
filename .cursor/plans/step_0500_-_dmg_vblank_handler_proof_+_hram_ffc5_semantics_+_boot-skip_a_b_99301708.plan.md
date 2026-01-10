# Step 0500: DMG VBlank Handler Proof + HRAM FFC5 Semantics + Boot-Skip A/B

## Contexto

**Hechos ya establecidos (no re-debatir)**:

- En CGB ya hay **pipeline completo** (IDX→RGB→PRESENT) y el "garbage" se corrigió con lectura correcta de tilemap (ID bank0, ATTR bank1, tile_bank por attr bit3).
- En DMG, `tetris.gb` queda clasificado como **VRAM_TILEDATA_ZERO**: tilemap con datos, tiledata vacío.
- IRQ VBlank **parece** tomarse (IRQTaken_VBlank > 0), pero eso **no prueba** que el handler real del juego esté ejecutándose correctamente y progresando.

## Objetivo Step 0500

**Objetivo A (bloqueante)**: Demostrar con evidencia si el juego DMG **ejecuta realmente** su rutina de VBlank/handler y si está escribiendo flags esperadas (p.ej. HRAM[0xFFC5]) **en cada frame**, no "una vez".

**Objetivo B**: Localizar por qué el juego no llega a escribir tiledata no-cero:

- **B1**: está en loop de espera legítimo pero la condición nunca se cumple (IO/HRAM/IRQ)
- **B2**: el handler corre pero escribe mal (RETI/IME/IF/IE)
- **B3**: el handler corre y la condición se cumple, pero la rutina de carga de tiles nunca se ejecuta (PC hotspots / flujo)

**Objetivo C**: Si el fallo es "boot-skip state", demostrarlo con un A/B (SIM_BOOT_LOGO 0 vs 1) con métricas.

## Alcance (Estricto)

- No arreglar "todo DMG" ni meterse con timing fino del PPU aún.
- No cambiar 20 cosas: **instrumentar mínimo**, aislar causa, aplicar **un fix mínimo** si hay evidencia clara.

## Fase A: "VBlank Handler Proof" (Evidencia Dura)

### A1) IRQTrace Real: Vector + Retorno + Contexto

**Archivo**: `src/core/cpp/CPU.hpp` y `src/core/cpp/CPU.cpp`

**Ampliar/confirmar el tracking de IRQ para que cada evento tenga**:

```cpp
// En CPU.hpp, ampliar IRQTraceEvent
struct IRQTraceEvent {
    uint32_t frame;
    uint16_t pc_before;        // Donde estaba antes del take
    uint16_t vector_addr;      // 0x0040, 0x0048, etc.
    uint16_t pc_after;         // PC justo tras saltar a vector (debe ser vector)
    uint16_t sp_before;
    uint16_t sp_after;
    uint8_t ime_before;
    uint8_t ime_after;
    uint8_t ie;                // IE en el instante del take
    uint8_t if_before;         // IF antes del take
    uint8_t if_after;          // IF después del take (con bit limpiado)
    uint8_t irq_type;          // VBlank/STAT/Timer/Serial/Joypad
    uint8_t opcode_at_vector;  // Opcional: opcode byte en vector_addr (detecta ROM mapping correcto)
};

// Ring buffer existente (ya implementado en Step 0497)
```

**Además, tracking de RETI ejecutados**:

```cpp
// En CPU.hpp
struct RETITraceEvent {
    uint32_t frame;
    uint16_t pc;               // PC donde ocurrió RETI
    uint16_t return_addr;      // Dirección de retorno (pop de la pila)
    uint8_t ime_after;         // IME después de RETI (debe ser 1)
    uint16_t sp_before;
    uint16_t sp_after;
};

static constexpr size_t RETI_TRACE_RING_SIZE = 64;
RETITraceEvent reti_trace_ring_[RETI_TRACE_RING_SIZE];
size_t reti_trace_ring_head_;

uint32_t reti_count_;  // Contador total de RETI ejecutados
```

**En `CPU::handle_interrupts()`, ampliar captura**:

```cpp
// En CPU.cpp, método handle_interrupts()
if (ime_ && pending != 0) {
    // ... código existente ...
    
    // Ampliar IRQTraceEvent
    size_t idx = irq_trace_ring_head_ % IRQ_TRACE_RING_SIZE;
    irq_trace_ring_[idx].frame = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
    irq_trace_ring_[idx].pc_before = prev_pc;
    irq_trace_ring_[idx].vector_addr = vector;
    irq_trace_ring_[idx].pc_after = vector;  // PC justo tras saltar (debe ser vector)
    irq_trace_ring_[idx].sp_before = sp_before_push;
    irq_trace_ring_[idx].sp_after = regs_->sp;
    irq_trace_ring_[idx].ime_before = 1;  // IME estaba activo
    irq_trace_ring_[idx].ime_after = 0;   // IME desactivado tras take
    irq_trace_ring_[idx].ie = ie_reg;
    irq_trace_ring_[idx].if_before = if_before_clear;
    irq_trace_ring_[idx].if_after = new_if;
    irq_trace_ring_[idx].irq_type = interrupt_bit;  // 0x01=VBlank, 0x02=STAT, etc.
    
    // Opcional: leer opcode en vector_addr para detectar ROM mapping correcto
    irq_trace_ring_[idx].opcode_at_vector = mmu_->read(vector);
    
    irq_trace_ring_head_++;
}
```

**En `CPU::execute_opcode()`, cuando se ejecuta RETI (0xD9)**:

```cpp
// En CPU.cpp, case 0xD9 (RETI)
case 0xD9:  // RETI (Return and Enable Interrupts)
{
    // ... código existente de RETI ...
    
    // Tracking de RETI
    reti_count_++;
    
    size_t idx = reti_trace_ring_head_ % RETI_TRACE_RING_SIZE;
    reti_trace_ring_[idx].frame = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
    reti_trace_ring_[idx].pc = original_pc;
    reti_trace_ring_[idx].return_addr = return_addr;
    reti_trace_ring_[idx].ime_after = ime_ ? 1 : 0;  // Debe ser 1
    reti_trace_ring_[idx].sp_before = sp_before_pop;
    reti_trace_ring_[idx].sp_after = regs_->sp;
    
    reti_trace_ring_head_++;
    
    // ... resto del código ...
}
```

**Exponer vía Cython**:

```cython
# En cpu.pyx
cdef class PyCPU:
    def get_irq_trace_ring(self, max_events: int = 128):
        """Obtiene ring buffer de eventos IRQ (últimos N eventos)."""
        # ... implementar ...
    
    def get_reti_trace_ring(self, max_events: int = 64):
        """Obtiene ring buffer de eventos RETI (últimos N eventos)."""
        # ... implementar ...
    
    def get_reti_count(self):
        """Obtiene contador total de RETI ejecutados."""
        if self._cpu == NULL:
            return 0
        return self._cpu.get_reti_count()
```

### A2) Criterio de Aceptación A1

**En `tetris.gb`, ver secuencia repetida**:

- "IRQ taken VBlank" → PC salta a 0x0040 → más tarde "RETI" → vuelve a ejecución.

### A3) HRAM[0xFFC5] "Flag Semantics"

**El loop histórico lee FFC5. No basta con "WriteCount=1"**.

**Archivo**: `src/core/cpp/MMU.hpp` y `src/core/cpp/MMU.cpp`

**Implementar tracking completo**:

```cpp
// En MMU.hpp, ampliar HRAMFFC5Tracking
struct HRAMFFC5Tracking {
    uint16_t last_write_pc;
    uint8_t last_write_value;
    uint32_t write_count_total;
    uint32_t write_count_in_irq_vblank;  // Crítico: cuántas escrituras ocurren mientras se sirve VBlank
    uint32_t first_write_frame;
    
    // Mini tabla de últimos 8 writes
    struct FFC5WriteEvent {
        uint16_t pc;
        uint8_t value;
        uint64_t frame_id;  // Si existe
        bool in_vblank_irq;  // Si ocurrió durante VBlank IRQ
    };
    static constexpr size_t FFC5_WRITE_RING_SIZE = 8;
    FFC5WriteEvent write_ring_[FFC5_WRITE_RING_SIZE];
    size_t write_ring_head_;
};

HRAMFFC5Tracking hram_ffc5_tracking_;
```

**En `MMU::write()`, cuando se escribe a HRAM[0xFFC5]**:

```cpp
// En MMU.cpp, método write()
if (addr == 0xFFC5 && addr >= 0xFF80 && addr <= 0xFFFE) {  // HRAM[0xFFC5]
    hram_ffc5_tracking_.last_write_pc = debug_current_pc;
    hram_ffc5_tracking_.last_write_value = value;
    hram_ffc5_tracking_.write_count_total++;
    
    // Verificar si estamos en VBlank IRQ (necesitar acceso a CPU o flag)
    bool in_vblank_irq = false;
    if (cpu_ != nullptr) {
        // Verificar si CPU está en handler de VBlank (necesitar getter)
        // ... implementar verificación ...
    }
    
    if (in_vblank_irq) {
        hram_ffc5_tracking_.write_count_in_irq_vblank++;
    }
    
    if (hram_ffc5_tracking_.first_write_frame == 0 && ppu_ != nullptr) {
        hram_ffc5_tracking_.first_write_frame = ppu_->get_frame_counter();
    }
    
    // Añadir al ring
    size_t idx = hram_ffc5_tracking_.write_ring_head_ % FFC5_WRITE_RING_SIZE;
    hram_ffc5_tracking_.write_ring_[idx].pc = debug_current_pc;
    hram_ffc5_tracking_.write_ring_[idx].value = value;
    hram_ffc5_tracking_.write_ring_[idx].frame_id = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
    hram_ffc5_tracking_.write_ring_[idx].in_vblank_irq = in_vblank_irq;
    hram_ffc5_tracking_.write_ring_head_++;
}
```

**Exponer vía Cython**:

```cython
# En mmu.pyx
cdef class PyMMU:
    def get_hram_ffc5_tracking(self):
        """Obtiene tracking completo de HRAM[0xFFC5]."""
        if self._mmu == NULL:
            return None
        
        cdef HRAMFFC5Tracking tracking = self._mmu.get_hram_ffc5_tracking()
        # Extraer ring de últimos 8 writes
        write_ring = []
        for i in range(min(FFC5_WRITE_RING_SIZE, tracking.write_ring_head_)):
            idx = (tracking.write_ring_head_ - i - 1) % FFC5_WRITE_RING_SIZE
            write_ring.append({
                'pc': tracking.write_ring_[idx].pc,
                'value': tracking.write_ring_[idx].value,
                'frame_id': tracking.write_ring_[idx].frame_id,
                'in_vblank_irq': tracking.write_ring_[idx].in_vblank_irq,
            })
        
        return {
            'last_write_pc': tracking.last_write_pc,
            'last_write_value': tracking.last_write_value,
            'write_count_total': tracking.write_count_total,
            'write_count_in_irq_vblank': tracking.write_count_in_irq_vblank,
            'first_write_frame': tracking.first_write_frame,
            'write_ring': write_ring,  # Últimos 8 writes
        }
```

### A4) Criterio de Aceptación A2

**Si el juego usa FFC5 como handshake, debería cambiar (0→1 o incrementar) muchas veces, no una sola**.

### A5) IF/IE Correctness Proof (No Solo Counters)

**Ya hay tracking de writes a IF/IE. Necesito evidencia de**:

- El valor real aplicado a IF cuando se "ackea" la IRQ.
- Si se está limpiando el bit correcto.
- Si hay writes que pisan bits erróneos.

**Archivo**: `src/core/cpp/MMU.hpp` y `src/core/cpp/MMU.cpp`

**Añadir snapshot compacto**:

```cpp
// En MMU.hpp, ampliar IFIETracking
struct IFIETracking {
    // ... campos existentes ...
    
    // Últimos 5 writes a IF
    struct IFWriteEvent {
        uint16_t pc;
        uint8_t written;
        uint8_t applied;
    };
    static constexpr size_t IF_WRITE_HISTORY_SIZE = 5;
    IFWriteEvent if_write_history_[IF_WRITE_HISTORY_SIZE];
    size_t if_write_history_head_;
    
    // Últimos 5 writes a IE
    struct IEWriteEvent {
        uint16_t pc;
        uint8_t written;
    };
    static constexpr size_t IE_WRITE_HISTORY_SIZE = 5;
    IEWriteEvent ie_write_history_[IE_WRITE_HISTORY_SIZE];
    size_t ie_write_history_head_;
    
    uint8_t if_current;  // Valor actual de IF
    uint8_t ie_current;  // Valor actual de IE
};
```

**En `MMU::write()`, cuando se escribe a IF/IE**:

```cpp
// En MMU.cpp, método write()
if (addr == 0xFF0F) {  // IF
    // ... código existente ...
    
    // Añadir al historial
    size_t idx = if_ie_tracking_.if_write_history_head_ % IF_WRITE_HISTORY_SIZE;
    if_ie_tracking_.if_write_history_[idx].pc = debug_current_pc;
    if_ie_tracking_.if_write_history_[idx].written = value;
    if_ie_tracking_.if_write_history_[idx].applied = value & 0x1F;  // Máscara aplicada
    if_ie_tracking_.if_write_history_head_++;
    
    if_ie_tracking_.if_current = value & 0x1F;
}

if (addr == 0xFFFF) {  // IE
    // ... código existente ...
    
    // Añadir al historial
    size_t idx = if_ie_tracking_.ie_write_history_head_ % IE_WRITE_HISTORY_SIZE;
    if_ie_tracking_.ie_write_history_[idx].pc = debug_current_pc;
    if_ie_tracking_.ie_write_history_[idx].written = value;
    if_ie_tracking_.ie_write_history_head_++;
    
    if_ie_tracking_.ie_current = value & 0x1F;
}
```

### A6) Criterio de Aceptación A3

**IF VBlank bit debe bajar tras servicio; IME debe comportarse como DMG real** (DI/EI/RETI).

## Fase B: "DMG Progress Proof" (Por Qué No Hay Tiledata)

### B1) "AfterClear+Progress" Snapshot en rom_smoke (DMG)

**Archivo**: `tools/rom_smoke_0442.py`

**Ampliar `DMGQuickClassifier` con señales de progreso**:

```python
# En rom_smoke_0442.py, función _classify_dmg_quick()
def _classify_dmg_quick_v2(self, ppu, mmu, renderer=None):
    """Clasificación DMG v2 con señales de progreso."""
    
    # Obtener métricas existentes
    three_buf_stats = ppu.get_three_buffer_stats()
    lcdc = mmu.read(0xFF40)
    lcd_on = (lcdc & 0x80) != 0
    
    # VRAM stats
    vram_write_stats = mmu.get_vram_write_stats()
    
    # PC hotspots
    after_clear = snapshot.get('AfterClear', {})
    pc_hotspot_1 = after_clear.get('pc_hotspots_top3', [])
    
    # IRQ stats
    interrupt_taken = self.cpu.get_interrupt_taken_counts()
    reti_count = self.cpu.get_reti_count()
    
    # HRAM[0xFFC5] stats
    hram_ffc5_tracking = mmu.get_hram_ffc5_tracking()
    
    # IF/IE stats
    if_ie_tracking = mmu.get_if_ie_tracking()
    
    # Clasificación DMG v2
    classification = "UNKNOWN"
    details = {}
    
    # WAITING_ON_FFC5: hotspot + lecturas dominantes a FFC5 y write_count_in_vblank == 0
    if pc_hotspot_1 and len(pc_hotspot_1) > 0:
        hotspot_pc, hotspot_count = pc_hotspot_1[0]
        io_reads_top = after_clear.get('io_reads_top3', [])
        
        # Verificar si hay lecturas dominantes a FFC5
        ffc5_reads = 0
        for addr, count in io_reads_top:
            if addr == 0xFFC5:
                ffc5_reads = count
                break
        
        if ffc5_reads > 1000 and hram_ffc5_tracking and hram_ffc5_tracking.get('write_count_in_irq_vblank', 0) == 0:
            classification = "WAITING_ON_FFC5"
            details['hotspot_pc'] = f'0x{hotspot_pc:04X}'
            details['ffc5_reads'] = ffc5_reads
            details['ffc5_write_count_in_vblank'] = 0
            return classification, details
    
    # IRQ_TAKEN_BUT_NO_RETI: taken aumenta y reti_count no
    if interrupt_taken and interrupt_taken.get('vblank', 0) > 0:
        vblank_taken = interrupt_taken['vblank']
        if vblank_taken > 0 and reti_count == 0:
            classification = "IRQ_TAKEN_BUT_NO_RETI"
            details['irq_taken_vblank'] = vblank_taken
            details['reti_count'] = reti_count
            return classification, details
    
    # IRQ_OK_BUT_FLAG_NOT_SET: taken y reti ok pero FFC5 no cambia
    if interrupt_taken and interrupt_taken.get('vblank', 0) > 0 and reti_count > 0:
        vblank_taken = interrupt_taken['vblank']
        if hram_ffc5_tracking and hram_ffc5_tracking.get('write_count_total', 0) == 0:
            classification = "IRQ_OK_BUT_FLAG_NOT_SET"
            details['irq_taken_vblank'] = vblank_taken
            details['reti_count'] = reti_count
            details['ffc5_write_count_total'] = 0
            return classification, details
    
    # BOOT_SKIP_SUSPECT: se detectará en A/B test
    # ... (se añade después del A/B test)
    
    # Clasificaciones básicas (de v1)
    # ... código existente de CPU_LOOP, LCDC_OFF, etc. ...
    
    return classification, details
```

**Añadir al snapshot**:

```python
# En rom_smoke_0442.py, función generate_snapshot()
if not is_cgb:
    dmg_classification, dmg_details = self._classify_dmg_quick_v2(self._ppu, self._mmu, self._renderer)
    
    # Ampliar con señales de progreso
    snapshot['DMGQuickClassifierV2'] = {
        'classification': dmg_classification,
        'details': dmg_details,
        'pc_hotspot_top1': after_clear.get('pc_hotspots_top3', [])[0] if after_clear.get('pc_hotspots_top3') else None,
        'irq_taken_vblank': interrupt_taken.get('vblank', 0) if interrupt_taken else 0,
        'reti_count': self.cpu.get_reti_count(),
        'hram_ffc5_last_value': hram_ffc5_tracking.get('last_write_value') if hram_ffc5_tracking else None,
        'hram_ffc5_write_count_total': hram_ffc5_tracking.get('write_count_total', 0) if hram_ffc5_tracking else 0,
        'hram_ffc5_write_count_in_vblank': hram_ffc5_tracking.get('write_count_in_irq_vblank', 0) if hram_ffc5_tracking else 0,
        'lcdc': lcdc,
        'stat': mmu.read(0xFF41),
        'ly': ppu.get_ly(),
        'vram_tiledata_nz': vram_write_stats.get('tiledata_nonzero_bank0', 0) if vram_write_stats else 0,
        'vram_tilemap_nz': vram_write_stats.get('tilemap_nonzero_bank0', 0) if vram_write_stats else 0,
        'vram_attempts_after_clear': vram_write_stats.get('tiledata_attempts_after_clear', 0) if vram_write_stats else 0,
        'vram_nonzero_after_clear': vram_write_stats.get('tiledata_nonzero_after_clear', 0) if vram_write_stats else 0,
    }
```

### B2) A/B Test "SIM_BOOT_LOGO=0 vs 1"

**Ejecutar `tetris.gb` dos veces** (misma cantidad de frames, p. ej. 1200):

**Run A**: `VIBOY_SIM_BOOT_LOGO=0`

**Run B**: `VIBOY_SIM_BOOT_LOGO=1` (o el modo que "simule" boot logo si existe)

**Comandos**:

```bash
# Run A
export VIBOY_SIM_BOOT_LOGO=0
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 1200 | tee /tmp/viboy_0500_tetris_boot0.log

# Run B
export VIBOY_SIM_BOOT_LOGO=1
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 1200 | tee /tmp/viboy_0500_tetris_boot1.log
```

**Comparar al final**:

- `VRAM_TiledataNZ`
- `ffC5_write_count_in_vblank`
- `irq_taken_vblank` y `reti_count`
- PC hotspot top1

### B3) Criterio de Aceptación B2

**Si B progresa y A no → post-boot state sigue incompleto** (y ya sabes dónde atacar).

**Si ambos fallan igual → no es boot-skip, es core/handler/HRAM/flow**.

## Fase C: Fix Mínimo (Solo si la Evidencia lo Permite)

### C1) Regla: SOLO Tocar Código si el Diagnóstico es Concluyente

**Ejemplos de fixes "permitidos"**:

1. **Si se ve que IRQ "taken" pero PC_after no es 0x0040** → bug de vectoring.
2. **Si se ve que no hay RETI** → bug en opcode RETI o stack.
3. **Si FFC5 writes ocurren pero leer FFC5 devuelve distinto** → bug HRAM mapping.
4. **Si A/B indica boot-skip state** → completar init post-boot DMG con los registros faltantes (no inventar: basarse en Pan Docs/GBEDG y documentar exactamente qué se añade).

**No permitido en este step**: "tocar timings del PPU" a ciegas.

## Fase D: Ejecución / Validación

### D1) tetris.gb (DMG)

**Ejecutar 1200–3000 frames** según lo que tarde.

**Guardar logs a `/tmp`**.

**Confirmar clasificación DMG v2**.

### D2) 1 ROM DMG Extra (Pokemon Red o Zelda DMG)

**Repetir para ver si patrón es general**.

**Comando**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
python3 tools/rom_smoke_0442.py roms/pokemon_red.gb --frames 1200 | tee /tmp/viboy_0500_pokemon_red.log
```

**Entrega**:

- Un resumen de 10 líneas por ROM con la clasificación final + métricas clave.

## Fase E: Documentación + Git

### E1) Generar Reporte

**Archivo**: `docs/reports/reporte_step0500.md`

**Debe incluir**:

1. **Fase A (VBlank Handler Proof)**:

   - IRQTrace: secuencia repetida (IRQ taken → PC salta a 0x0040 → RETI → vuelve)
   - HRAM[0xFFC5]: write_count_total, write_count_in_irq_vblank, últimos 8 writes
   - IF/IE: últimos 5 writes, valores aplicados, comportamiento tras servicio

2. **Fase B (DMG Progress Proof)**:

   - Clasificación DMG v2 (WAITING_ON_FFC5, IRQ_TAKEN_BUT_NO_RETI, IRQ_OK_BUT_FLAG_NOT_SET, BOOT_SKIP_SUSPECT)
   - A/B test: comparación Run A vs Run B (VRAM_TiledataNZ, ffC5 stats, IRQ stats, PC hotspot)

3. **Fase C (Fix Mínimo)**:

   - Si se aplicó fix, descripción del fix y evidencia que lo justifica

### E2) Bitácora HTML

**Archivo**: `docs/bitacora/entries/YYYY-MM-DD__0500__dmg-vblank-handler-proof-hram-ffc5-boot-skip.html`

**⚠️ CRÍTICO: Usar fecha correcta (2026, no 2025)**.

### E3) Actualizar

- `docs/bitacora/index.html`
- `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o donde corresponda)
- `docs/informe_fase_2/index.md` si aplica

### E4) Commit + Push

**Mensaje claro**:

```
feat(diag): Step 0500 - DMG VBlank handler proof + HRAM FFC5 semantics + boot-skip A/B
```

## Criterios de Éxito

1. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0500.md` completo SIN placeholders**:

   - Fase A: IRQTrace secuencia repetida, HRAM[0xFFC5] stats completos, IF/IE correctness proof
   - Fase B: Clasificación DMG v2, A/B test comparación
   - Fase C: Fix aplicado (si lo hay) con evidencia

2. **⚠️ CRÍTICO: IRQTrace ampliado** con vector, retorno, contexto completo

3. **⚠️ CRÍTICO: HRAM[0xFFC5] tracking completo** con write_count_in_irq_vblank y ring de últimos 8 writes

4. **IF/IE correctness proof** con historial de últimos 5 writes

5. **DMG Quick Classifier v2** con clasificaciones nuevas (WAITING_ON_FFC5, IRQ_TAKEN_BUT_NO_RETI, etc.)

6. **A/B test ejecutado** (SIM_BOOT_LOGO=0 vs 1) con comparación

7. **Ejecución con 2 ROMs DMG** (tetris.gb + 1 extra)

8. **Bitácora/informe actualizados** con evidencia y conclusión específica, **fechas correctas (2026)**

9. **Commit/push** con mensaje claro

## Resultado Esperado (Lo que Debe Salir de 0500 Sí o Sí)

**Aunque no arregle DMG aún, 0500 debe darte una respuesta binaria**:

- **"El handler no ejecuta / no retorna / no setea flag"** (y por qué exacto), o
- **"El boot-skip state es el culpable"** (demostrado por A/B), o
- **"El juego progresa pero nunca entra en carga de tiles"** (PC flow) → siguiente step se centra en eso.

## Nota Crítica (Para el Ejecutor)

**El dato "IRQTaken_VBlank=2579" por sí solo no vale** si el take está mal instrumentado o si el vector/RETI están rotos.

**La prueba de fuego es**: **PC salta a 0x0040, ejecuta rutina, y vuelve con RETI** + side effects (FFC5 o lo que toque).

**Si el ejecutor te devuelve la salida de Step 0500 (aunque sea un resumen), yo te preparo el Step 0501 ya con el fix mínimo exacto (core/boot/HRAM/vector/RETI), sin dispersión**.