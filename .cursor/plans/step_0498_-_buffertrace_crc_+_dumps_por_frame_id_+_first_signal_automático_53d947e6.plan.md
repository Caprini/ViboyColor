---
name: Step 0498 - BufferTrace CRC + Dumps por frame_id + First Signal automático
overview: "Step 0497 implementó frame_id end-to-end, logs FRONT/BACK, y rom_smoke con --use-renderer-headless. Falta Fase B (CRC trace). Sin CRC, el frame_id solo prueba \"quién dice que es qué\", pero no prueba integridad del contenido. Este step: probar con evidencia si el renderer presenta frame_id = X o X-1 (lag normal), y si los bytes coinciden (CRC). Si hay discrepancia, aislar dónde se corrompe o se desincroniza: ¿PPU front cambia después del swap? ¿convert RGB lee back? ¿renderer blitea otro buffer? ¿present usa surface stale?"
todos:
  - id: 0498-t1-buffertrace-struct
    content: "Implementar estructura BufferTraceEvent en PPU.hpp/PPU.cpp: frame_id, framebuffer_frame_id, front_idx_crc32, front_rgb_crc32, back_idx_crc32, back_rgb_crc32, buffer_uid. Ring buffer de 128 eventos. Implementar compute_crc32_full() y compute_buffer_uid() para calcular CRC32 sobre todo el buffer (no muestreo)."
    status: pending
  - id: 0498-t2-buffertrace-ppu
    content: "Capturar BufferTrace en PPU.cpp: en swap_framebuffers() registrar CRC32 justo tras llenar FB_INDEX (después del swap), CRC32 justo tras convertir a FB_RGB, CRC32 del buffer back (antes del swap). Logging limitado (primeros 50 eventos). Exponer get_buffer_trace_ring() vía Cython."
    status: pending
    dependencies:
      - 0498-t1-buffertrace-struct
  - id: 0498-t3-buffertrace-renderer
    content: "Capturar BufferTrace en renderer.py: estructura _renderer_trace (máximo 128 eventos). En render_frame() capturar frame_id_received, CRC32 del buffer que entra al blit (RGB bytes origen), CRC32 del Surface/buffer inmediatamente antes del flip, present_pitch, present_format, bytes_len, present_nonwhite. Logging limitado (primeros 50 eventos)."
    status: pending
  - id: 0498-t4-first-signal-detector
    content: "Implementar detector First Signal en rom_smoke_0442.py: detectar cuando IdxNonZero>0 o RgbNonWhite>0 o PresentNonWhite>0, guardar first_signal_frame_id. Cuando detecte first signal, dumpear automáticamente FB_INDEX, FB_RGB, FB_PRESENT_SRC para frame_id = first_signal_id, first_signal_id-1, first_signal_id+1. Dumps etiquetados por frame_id (ej: /tmp/viboy_dx_idx_fid_0000001234.ppm)."
    status: pending
    dependencies:
      - 0498-t2-buffertrace-ppu
      - 0498-t3-buffertrace-renderer
  - id: 0498-t5-frameid-consistency-table
    content: "Implementar tabla FrameIdConsistency en rom_smoke_0442.py: con --use-renderer-headless, incluir tabla por frame_id (50 filas alrededor del first signal) con columnas fid, ppu_front_fid, ppu_back_fid, ppu_front_rgb_crc, renderer_received_fid, renderer_src_crc, renderer_present_crc, present_nonwhite. Implementar clasificador automático (OK_SAME_FRAME, OK_LAG_1, STALE_PRESENT, MISMATCH_COPY, ORDER_BUG)."
    status: pending
    dependencies:
      - 0498-t4-first-signal-detector
  - id: 0498-t6-execute-rom-smoke
    content: "Ejecutar rom_smoke para tetris_dx.gbc (1200 frames) con --use-renderer-headless, suficiente para pasar first signal. Log a /tmp/viboy_0498_tetris_dx.log. Criterio: reporte señala explícitamente first_signal_frame_id=N, si hay lag (0 o 1), si CRC coincide end-to-end."
    status: pending
    dependencies:
      - 0498-t5-frameid-consistency-table
  - id: 0498-t7-create-report
    content: "Crear reporte markdown docs/reports/reporte_step0498.md con: BufferTrace CRC (tabla con CRCs en puntos clave), First Signal (frame_id y dumps generados), FrameIdConsistency (tabla con 50 filas y clasificación), conclusión (una frase con datos: lag o bug). NO placeholders."
    status: pending
    dependencies:
      - 0498-t6-execute-rom-smoke
  - id: 0498-t8-document
    content: "Documentar Step 0498 en bitácora HTML (docs/bitacora/entries/YYYY-MM-DD__0498__buffertrace-crc-dumps-frameid.html) e informe dividido. ⚠️ CRÍTICO: Usar fecha correcta (2026, no 2025). Actualizar docs/bitacora/index.html y docs/informe_fase_2/. Commit/push con mensaje \"feat(diag): Step 0498 - BufferTrace CRC + dumps por frame_id + First Signal automático\"."
    status: pending
    dependencies:
      - 0498-t7-create-report
---

# Step 0498: BufferTrace CRC + Dumps por frame_id + First Signal automático

## Contexto

**Step 0497**: frame_id en PPU, logs FRONT/BACK, rom_smoke con `--use-renderer-headless`.

**Falta**: Fase B (CRC trace). Sin CRC, el frame_id solo prueba "quién dice que es qué", pero no prueba integridad del contenido.

## Objetivo (Sin Bullshit)

Probar con evidencia si el renderer presenta `frame_id = X` o `X-1` (lag normal), y si los bytes coinciden (CRC).

Si hay discrepancia, aislar dónde se corrompe o se desincroniza:

- ¿PPU front cambia después del swap?
- ¿convert RGB lee back?
- ¿renderer blitea otro buffer?
- ¿present usa surface stale?

## Resultado Esperado

Un reporte que pueda decir una sola frase con datos:

- "Present = Front (mismo frame_id y CRC) con lag de 1 frame" o
- "Present no coincide (CRC/frame_id) ⇒ bug en orden/swap/copia".

## Fase A: BufferTrace CRC (PPU + Renderer) [Bloqueante]

### A1) Implementar Traza Compacta (Ring Buffer) con CRC32 + Metadatos

**Archivo**: `src/core/cpp/PPU.hpp` y `src/core/cpp/PPU.cpp`

**Estructura BufferTrace**:

```cpp
// En PPU.hpp
struct BufferTraceEvent {
    uint64_t frame_id;
    uint64_t framebuffer_frame_id;  // Frame_id del buffer front
    uint32_t front_idx_crc32;       // CRC32 del framebuffer_front_ (índices)
    uint32_t front_rgb_crc32;       // CRC32 del framebuffer_rgb_front_
    uint32_t back_idx_crc32;        // CRC32 del framebuffer_back_ (índices)
    uint32_t back_rgb_crc32;        // CRC32 del framebuffer_rgb_back_ (si existe)
    uint32_t buffer_uid;            // ID único del buffer (hash del puntero o contenido)
};

static constexpr size_t BUFFER_TRACE_RING_SIZE = 128;
BufferTraceEvent buffer_trace_ring_[BUFFER_TRACE_RING_SIZE];
size_t buffer_trace_ring_head_;
```

**Capturar por frame_id en PPU (C++)**:

```cpp
// En PPU.cpp, método swap_framebuffers()
void PPU::swap_framebuffers() {
    // ... código existente de swap ...
    
    // CRC32 justo tras llenar FB_INDEX (después del swap)
    uint32_t front_idx_crc32 = compute_crc32_full(framebuffer_front_, FRAMEBUFFER_SIZE);
    
    // Convertir a RGB
    convert_framebuffer_to_rgb();
    
    // CRC32 justo tras convertir a FB_RGB
    uint32_t front_rgb_crc32 = compute_crc32_full(framebuffer_rgb_front_, FRAMEBUFFER_SIZE * 3);
    
    // CRC32 del buffer back (antes del swap, para comparación)
    uint32_t back_idx_crc32 = compute_crc32_full(framebuffer_back_, FRAMEBUFFER_SIZE);
    uint32_t back_rgb_crc32 = 0;  // Si existe framebuffer_rgb_back_
    
    // Buffer UID (hash del puntero o contenido)
    uint32_t buffer_uid = compute_buffer_uid(framebuffer_front_);
    
    // Registrar en trace
    size_t idx = buffer_trace_ring_head_ % BUFFER_TRACE_RING_SIZE;
    buffer_trace_ring_[idx].frame_id = frame_id_;
    buffer_trace_ring_[idx].framebuffer_frame_id = framebuffer_frame_id_;
    buffer_trace_ring_[idx].front_idx_crc32 = front_idx_crc32;
    buffer_trace_ring_[idx].front_rgb_crc32 = front_rgb_crc32;
    buffer_trace_ring_[idx].back_idx_crc32 = back_idx_crc32;
    buffer_trace_ring_[idx].back_rgb_crc32 = back_rgb_crc32;
    buffer_trace_ring_[idx].buffer_uid = buffer_uid;
    buffer_trace_ring_head_++;
    
    // Logging limitado (primeros 50 eventos o cuando cambie algo)
    static int trace_log_count = 0;
    if (trace_log_count < 50) {
        trace_log_count++;
        printf("[PPU-BufferTrace] frame_id=%llu | framebuffer_frame_id=%llu | "
               "front_idx_crc32=0x%08X | front_rgb_crc32=0x%08X | "
               "back_idx_crc32=0x%08X | buffer_uid=0x%08X\n",
               static_cast<unsigned long long>(frame_id_),
               static_cast<unsigned long long>(framebuffer_frame_id_),
               front_idx_crc32, front_rgb_crc32, back_idx_crc32, buffer_uid);
    }
}
```

**Implementar `compute_crc32_full()`**:

```cpp
// En PPU.cpp
uint32_t PPU::compute_crc32_full(const std::vector<uint8_t>& data, size_t size) const {
    // CRC32 simple (polinomio 0xEDB88320, tabla lookup)
    // O usar implementación estándar si está disponible
    uint32_t crc = 0xFFFFFFFF;
    static const uint32_t crc_table[256] = {
        // ... tabla CRC32 estándar ...
    };
    
    for (size_t i = 0; i < size && i < data.size(); i++) {
        uint8_t byte = data[i];
        crc = (crc >> 8) ^ crc_table[(crc ^ byte) & 0xFF];
    }
    
    return crc ^ 0xFFFFFFFF;
}

uint32_t PPU::compute_buffer_uid(const std::vector<uint8_t>& data) const {
    // Hash simple del puntero o contenido (para identidad de buffer)
    uint32_t hash = 0;
    for (size_t i = 0; i < data.size() && i < 100; i++) {  // Primeros 100 bytes
        hash = (hash * 31) + data[i];
    }
    return hash;
}
```

**Exponer vía Cython**:

```cython
# En ppu.pyx
cdef class PyPPU:
    def get_buffer_trace_ring(self, max_events: int = 128):
        """Obtiene ring buffer de eventos BufferTrace (últimos N eventos)."""
        if self._ppu == NULL:
            return []
        
        # Obtener ring buffer desde PPU
        # ... implementar ...
        
        events = []
        # ... extraer eventos del ring ...
        return events
```

### A2) Capturar por frame_id en Renderer (Python)

**Archivo**: `src/gpu/renderer.py`

**Estructura para tracking**:

```python
# En renderer.py, clase Renderer
class Renderer:
    def __init__(self, ...):
        # ... código existente ...
        self._renderer_trace = []  # Lista de eventos (máximo 128)
    
    def _add_renderer_trace_event(self, frame_id_received, src_crc32, present_crc32, 
                                   present_pitch, present_format, bytes_len, present_nonwhite):
        """Añade evento al trace del renderer."""
        event = {
            'frame_id_received': frame_id_received,
            'src_crc32': src_crc32,  # CRC32 del buffer que entra al blit (RGB bytes origen)
            'present_crc32': present_crc32,  # CRC32 del Surface/buffer inmediatamente antes del flip
            'present_pitch': present_pitch,
            'present_format': present_format,
            'bytes_len': bytes_len,
            'present_nonwhite': present_nonwhite,
        }
        
        self._renderer_trace.append(event)
        if len(self._renderer_trace) > 128:
            self._renderer_trace.pop(0)  # Mantener solo últimos 128
```

**En `render_frame()`, capturar CRC en puntos clave**:

```python
# En renderer.py, método render_frame()
if hasattr(self, '_ppu') and self._ppu is not None:
    frame_id_received = self._ppu.get_framebuffer_frame_id()
    
    # CRC32 del buffer que entra al blit (RGB bytes origen)
    if rgb_view is not None:
        import zlib
        src_crc32 = zlib.crc32(rgb_view) & 0xFFFFFFFF
    else:
        src_crc32 = 0
    
    # ... código de blit ...
    
    # CRC32 del Surface/buffer inmediatamente antes del flip
    present_buffer = pygame.surfarray.array3d(self.surface)
    present_buffer_flat = present_buffer.flatten()
    present_buffer_bytes = present_buffer_flat.tobytes()
    present_crc32 = zlib.crc32(present_buffer_bytes) & 0xFFFFFFFF
    
    # Obtener metadatos del Surface
    present_pitch = self.surface.get_pitch() if hasattr(self.surface, 'get_pitch') else self.surface.get_width() * 3
    present_format = self.surface.get_flags()
    bytes_len = len(present_buffer_bytes)
    present_nonwhite = sum(1 for i in range(0, len(present_buffer_bytes), 3) 
                           if present_buffer_bytes[i] < 240 or 
                              present_buffer_bytes[i+1] < 240 or 
                              present_buffer_bytes[i+2] < 240)
    
    # Añadir al trace
    self._add_renderer_trace_event(frame_id_received, src_crc32, present_crc32,
                                   present_pitch, present_format, bytes_len, present_nonwhite)
    
    # Logging limitado
    if not hasattr(self, '_trace_log_count'):
        self._trace_log_count = 0
    
    if self._trace_log_count < 50:
        self._trace_log_count += 1
        print(f"[Renderer-BufferTrace] frame_id_received={frame_id_received} | "
              f"src_crc32=0x{src_crc32:08X} | present_crc32=0x{present_crc32:08X} | "
              f"present_nonwhite={present_nonwhite}")
```

### A3) Regla de Oro

**CRC debe calcularse sobre todo el buffer, no muestreo**.

**Ring buffer de 128 eventos máximo**.

**Logging limitado** (p. ej., primeros 50 eventos o cuando cambie algo) para no inundar.

### A4) Criterios de Aceptación Fase A

**En un mismo frame_id, se puede comparar**:

- `PPU.front_rgb_crc32` vs `Renderer.pre_flip_surface_crc32`
- Y saber si son iguales (o por qué no).

## Fase B: "First Signal" Detector y Dumps Automáticos (por frame_id)

### B1) Añadir Detector "Primera Señal Real"

**Archivo**: `tools/rom_smoke_0442.py`

**Basado en**:

- `IdxNonZero>0` y/o
- `RgbNonWhite>0` y/o
- `PresentNonWhite>0`

**Implementar detector**:

```python
# En rom_smoke_0442.py, clase ROMSmokeRunner
class ROMSmokeRunner:
    def __init__(self, ...):
        # ... código existente ...
        self._first_signal_frame_id = None
        self._first_signal_detected = False
    
    def _detect_first_signal(self, ppu, mmu, renderer=None):
        """Detecta primera señal real (IdxNonZero>0 o RgbNonWhite>0 o PresentNonWhite>0)."""
        if self._first_signal_detected:
            return self._first_signal_frame_id
        
        # Obtener métricas
        three_buf_stats = ppu.get_three_buffer_stats()
        if three_buf_stats:
            idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
            rgb_nonwhite = three_buf_stats.get('rgb_nonwhite_count', 0)
            present_nonwhite = three_buf_stats.get('present_nonwhite_count', 0)
            
            # Detectar primera señal
            if idx_nonzero > 0 or rgb_nonwhite > 0 or present_nonwhite > 0:
                frame_id = ppu.get_framebuffer_frame_id()
                self._first_signal_frame_id = frame_id
                self._first_signal_detected = True
                
                print(f"[FirstSignal] Detected at frame_id={frame_id} | "
                      f"IdxNonZero={idx_nonzero} | RgbNonWhite={rgb_nonwhite} | "
                      f"PresentNonWhite={present_nonwhite}")
                
                return frame_id
        
        return None
```

### B2) Dumps Automáticos por frame_id

**Cuando detecte "first signal", dumpear automáticamente**:

- FB_INDEX
- FB_RGB
- FB_PRESENT_SRC

**Para frame_id = first_signal_id y también first_signal_id-1 y +1**.

**Importante**: Dumps deben etiquetarse por frame_id, no por número de iteración, para que el análisis sea estable.

**Ejemplo de naming**:

- `/tmp/viboy_dx_idx_fid_0000001234.ppm`
- `/tmp/viboy_dx_rgb_fid_0000001234.ppm`
- `/tmp/viboy_dx_present_fid_0000001234.ppm`

**Implementar**:

```python
# En rom_smoke_0442.py, método run()
first_signal_id = self._detect_first_signal(self._ppu, self._mmu, self._renderer)

if first_signal_id is not None:
    # Dump para first_signal_id, first_signal_id-1, first_signal_id+1
    for offset in [-1, 0, 1]:
        target_frame_id = first_signal_id + offset
        
        # Solo dump si estamos en el frame_id correcto
        current_frame_id = self._ppu.get_framebuffer_frame_id()
        if current_frame_id == target_frame_id:
            # Dump FB_INDEX
            self._dump_framebuffer_by_frame_id('idx', target_frame_id, self._ppu)
            
            # Dump FB_RGB
            self._dump_framebuffer_by_frame_id('rgb', target_frame_id, self._ppu)
            
            # Dump FB_PRESENT_SRC (si hay renderer)
            if self._renderer is not None:
                self._dump_present_by_frame_id('present', target_frame_id, self._renderer)

def _dump_framebuffer_by_frame_id(self, buffer_type, frame_id, ppu):
    """Dump framebuffer etiquetado por frame_id."""
    dump_path = f'/tmp/viboy_dx_{buffer_type}_fid_{frame_id:010d}.ppm'
    
    if buffer_type == 'idx':
        fb_indices = ppu.get_presented_framebuffer_indices()
        # ... generar PPM ...
    elif buffer_type == 'rgb':
        fb_rgb = ppu.get_framebuffer_rgb()
        # ... generar PPM ...
```

## Fase C: rom_smoke: Tabla "FrameIdConsistency"

### C1) Con --use-renderer-headless, Incluir Tabla por frame_id

**Archivo**: `tools/rom_smoke_0442.py`

**El reporte debe incluir una tabla por frame_id** (p. ej. 50 filas alrededor del first signal):

| fid | ppu_front_fid | ppu_back_fid | ppu_front_rgb_crc | renderer_received_fid | renderer_src_crc | renderer_present_crc | present_nonwhite |

|-----|---------------|--------------|-------------------|----------------------|------------------|---------------------|------------------|

| ... | ... | ... | ... | ... | ... | ... | ... |

**Implementar**:

```python
# En rom_smoke_0442.py, método generate_snapshot()
if self.use_renderer_headless and self._renderer is not None:
    # Obtener buffer trace del PPU
    ppu_trace = self._ppu.get_buffer_trace_ring(max_events=128)
    
    # Obtener renderer trace
    renderer_trace = self._renderer.get_renderer_trace()  # Necesitar getter
    
    # Construir tabla FrameIdConsistency
    frame_id_consistency = []
    
    # Alrededor del first_signal (50 filas)
    if self._first_signal_frame_id is not None:
        start_fid = max(0, self._first_signal_frame_id - 25)
        end_fid = self._first_signal_frame_id + 25
        
        for fid in range(start_fid, end_fid + 1):
            # Buscar en PPU trace
            ppu_event = next((e for e in ppu_trace if e['framebuffer_frame_id'] == fid), None)
            
            # Buscar en renderer trace
            renderer_event = next((e for e in renderer_trace if e['frame_id_received'] == fid), None)
            
            frame_id_consistency.append({
                'fid': fid,
                'ppu_front_fid': ppu_event['framebuffer_frame_id'] if ppu_event else None,
                'ppu_back_fid': ppu_event['frame_id'] if ppu_event else None,
                'ppu_front_rgb_crc': ppu_event['front_rgb_crc32'] if ppu_event else None,
                'renderer_received_fid': renderer_event['frame_id_received'] if renderer_event else None,
                'renderer_src_crc': renderer_event['src_crc32'] if renderer_event else None,
                'renderer_present_crc': renderer_event['present_crc32'] if renderer_event else None,
                'present_nonwhite': renderer_event['present_nonwhite'] if renderer_event else None,
            })
    
    snapshot['FrameIdConsistency'] = frame_id_consistency
```

### C2) Clasificador Automático

**Implementar clasificador**:

```python
# En rom_smoke_0442.py
def _classify_frame_id_consistency(self, row):
    """Clasifica una fila de FrameIdConsistency."""
    ppu_front_fid = row.get('ppu_front_fid')
    ppu_back_fid = row.get('ppu_back_fid')
    ppu_front_rgb_crc = row.get('ppu_front_rgb_crc')
    renderer_received_fid = row.get('renderer_received_fid')
    renderer_src_crc = row.get('renderer_src_crc')
    renderer_present_crc = row.get('renderer_present_crc')
    
    if ppu_front_fid is None or renderer_received_fid is None:
        return "INCOMPLETE"
    
    if renderer_received_fid == ppu_front_fid and renderer_src_crc == ppu_front_rgb_crc:
        if ppu_front_fid == ppu_back_fid - 1:
            return "OK_LAG_1"  # Lag de 1 frame normal
        else:
            return "OK_SAME_FRAME"  # Mismo frame, sin lag
    
    if renderer_present_crc == ppu_front_rgb_crc:
        # CRC present coincide con fid antiguo
        return "STALE_PRESENT"
    
    if renderer_received_fid == ppu_front_fid but renderer_src_crc != ppu_front_rgb_crc:
        # fid igual pero CRC distinto (overwrite/format/copia)
        return "MISMATCH_COPY"
    
    if renderer_received_fid != ppu_front_fid and renderer_received_fid != ppu_back_fid:
        # renderer recibe fid/back incorrecto (orden swap/render mal)
        return "ORDER_BUG"
    
    return "UNKNOWN"
```

**Añadir clasificación a cada fila**:

```python
# En frame_id_consistency
for row in frame_id_consistency:
    row['classification'] = self._classify_frame_id_consistency(row)
```

## Fase D: Ejecución Obligatoria (Evidencia)

### D1) Ejecutar tetris_dx.gbc con --use-renderer-headless

**Comando de ejecución**:

```bash
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DEBUG_CGB_PALETTE_WRITES=1
python3 tools/rom_smoke_0442.py roms/tetris_dx.gbc --frames 1200 --use-renderer-headless | tee /tmp/viboy_0498_tetris_dx.log
```

**Suficiente para pasar "first signal"**.

### D2) Criterio

**Reporte Step 0498 debe señalar explícitamente**:

- `first_signal_frame_id = N`
- Si hay lag (0 o 1)
- Si CRC coincide end-to-end

## Fase E: Docs + Git

### E1) Generar Reporte

**Archivo**: `docs/reports/reporte_step0498.md`

**Debe incluir**:

1. **BufferTrace CRC**:

   - Tabla: Frame ID | PPU front_rgb_crc32 | Renderer src_crc32 | Renderer present_crc32 | Match
   - Análisis: ¿CRC coincide end-to-end?

2. **First Signal**:

   - `first_signal_frame_id = N`
   - Dumps generados (paths)

3. **FrameIdConsistency**:

   - Tabla con 50 filas alrededor del first signal
   - Clasificación automática (OK_SAME_FRAME, OK_LAG_1, STALE_PRESENT, MISMATCH_COPY, ORDER_BUG)
   - Análisis: ¿hay lag? ¿CRC coincide?

4. **Conclusión**:

   - "Present = Front (mismo frame_id y CRC) con lag de 1 frame" o
   - "Present no coincide (CRC/frame_id) ⇒ bug en orden/swap/copia"

### E2) Bitácora HTML

**Archivo**: `docs/bitacora/entries/YYYY-MM-DD__0498__buffertrace-crc-dumps-frameid.html`

**⚠️ CRÍTICO: Usar fecha correcta (2026, no 2025)**.

### E3) Actualizar

- `docs/bitacora/index.html`
- `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o donde corresponda)
- `docs/informe_fase_2/index.md` si aplica

### E4) Commit + Push

**Mensaje claro**:

```
feat(diag): Step 0498 - BufferTrace CRC + dumps por frame_id + First Signal automático
```

## Criterios de Éxito

1. **⚠️ CRÍTICO: Reporte `/tmp/reporte_step0498.md` completo SIN placeholders**:

   - BufferTrace CRC (tabla con CRCs en puntos clave)
   - First Signal (frame_id y dumps generados)
   - FrameIdConsistency (tabla con 50 filas y clasificación)
   - Conclusión (una frase con datos: lag o bug)

2. **⚠️ CRÍTICO: BufferTrace CRC implementado** en PPU y Renderer

3. **⚠️ CRÍTICO: First Signal detector** funcionando y dumps automáticos por frame_id

4. **FrameIdConsistency tabla** con clasificador automático

5. **Ejecución con --use-renderer-headless** completada

6. **Bitácora/informe actualizados** con evidencia y conclusión específica, **fechas correctas (2026)**

7. **Commit/push** con mensaje claro

## Nota Directa

**En vuestro propio Step 0496 UI: la señal empezó sobre frame 672–680. A 60 FPS eso son ~11–11,3 segundos. Si estabas mirando 2–5s y cerrando: es normal ver blanco**.

**Si me pegas el extract de logs de Step 0497 (unas 30–50 líneas alrededor de cuando empieza la señal, con Renderer received/presented + PPU FRONT/BACK), te digo ya si huele a lag normal o a bug de orden. Pero Step 0498 lo deja cerrado sin interpretación humana**.