# Inventario de Debug/Test Injections (Step 0461)

Fecha: 2026-01-03

## Objetivo
Identificar todos los mecanismos que puedan interferir con el output del emulador (patrones, autopress, fallbacks, modos especiales).

## Tabla de Hallazgos

| Feature | Archivo:línea | Condición de Activación | Impacto | Acción |
|---------|---------------|------------------------|---------|--------|
| checkerboard pattern | `src/core/cpp/PPU.cpp:1961` | `enable_checkerboard_temporal = true` (hardcoded) + `vram_is_empty_` | Visual (patrón ajedrez cuando VRAM vacía) | **Gatear con kill-switch** |
| checkerboard (tile vacío) | `src/core/cpp/PPU.cpp:3187` | `tile_is_empty && enable_checkerboard_temporal && vram_is_empty_` | Visual (patrón ajedrez en tiles vacíos) | **Gatear con kill-switch** |
| checkerboard (dirección inválida) | `src/core/cpp/PPU.cpp:3069` | `!tile_addr_valid \|\| !tile_line_addr_valid` | Visual (patrón ajedrez cuando dirección inválida) | **Gatear con kill-switch** |
| auto-press joypad | `src/viboy.py:1446` | `simulate_input=True` (parámetro de `run()`) | Input (presiona botones automáticamente) | **Gatear con env var** |
| framebuffer trace (rayas verdes) | `src/gpu/renderer.py:256` | `_framebuffer_trace_enabled = True` (hardcoded) | Visual (logging puede interferir) | **Gatear con env var** |
| BGP forzado | `src/viboy.py:765` | `self._mmu.read(0xFF47) == 0` (siempre activo) | Estado (fuerza BGP=0xE4 si es 0) | **Gatear con env var** |
| triage mode | `src/core/cpp/MMU.cpp:3742` | `set_triage_mode(true)` (llamado desde tools) | Estado (instrumentación de escrituras) | Ya gated (solo en tools) |
| VIBOY_DEBUG_PPU | `src/core/cpp/PPU.cpp:31` | `#ifdef VIBOY_DEBUG_PPU` (compile-time) | Logging (solo en builds debug) | Ya gated (compile-time) |
| VIBOY_DEBUG_UI | `src/gpu/renderer.py:699` | `VIBOY_DEBUG_UI = os.environ.get('VIBOY_DEBUG_UI', '0') == '1'` | Logging (solo si env var activa) | Ya gated correctamente |

## Resumen por Categoría

### Patrones Visuales
- **checkerboard pattern** (3 instancias):
  - Línea 1961: Flag `enable_checkerboard_temporal = true` (hardcoded)
  - Línea 3187: Activación cuando tile vacío + VRAM vacía
  - Línea 3069: Activación cuando dirección de tile inválida
  - **Riesgo**: ALTO - Se activa automáticamente cuando VRAM está vacía o hay tiles vacíos
  - **Acción**: Gatear con kill-switch `VIBOY_DEBUG_INJECTION`

### Input Injection
- **auto-press joypad**:
  - Línea 1446: `simulate_input` parámetro de `run()`
  - **Riesgo**: MEDIO - Solo se activa si se pasa explícitamente `simulate_input=True`
  - **Acción**: Gatear con env var `VIBOY_AUTOPRESS`

### Fallbacks/Legacy
- **BGP forzado**:
  - Línea 765: Fuerza BGP=0xE4 si BGP==0
  - **Riesgo**: MEDIO - Puede interferir con tests que esperan BGP=0x00
  - **Acción**: Gatear con env var `VIBOY_FORCE_BGP`

### Modos Especiales
- **framebuffer trace**:
  - Línea 256: `_framebuffer_trace_enabled = True` (hardcoded)
  - **Riesgo**: BAJO - Solo logging, no modifica output visual
  - **Acción**: Gatear con env var `VIBOY_FRAMEBUFFER_TRACE` (opcional)

### Registros Forzados
- **BGP forzado** (ya listado en Fallbacks)
- No se encontraron otras escrituras forzadas a registros críticos (LCDC, SCX, SCY)

## Recomendaciones

### Alto Riesgo (interfieren siempre o con flag débil)
1. **checkerboard pattern** (3 instancias) - **PRIORIDAD 1**
   - Se activa automáticamente cuando VRAM está vacía
   - Puede interferir con análisis visual de pantallas en blanco
   - **Acción**: Gatear con `VIBOY_DEBUG_INJECTION=1` (OFF por defecto)

### Medio Riesgo (solo en tests/tools, pero sin guardrails claros)
1. **auto-press joypad** - **PRIORIDAD 2**
   - Solo se activa si se pasa `simulate_input=True`
   - Pero no hay guardrail claro en el código principal
   - **Acción**: Gatear con `VIBOY_AUTOPRESS=1` (OFF por defecto)

2. **BGP forzado** - **PRIORIDAD 3**
   - Fuerza BGP=0xE4 si BGP==0
   - Puede interferir con tests que esperan BGP=0x00
   - **Acción**: Gatear con `VIBOY_FORCE_BGP=1` (OFF por defecto)

### Bajo Riesgo (ya gated correctamente)
1. **triage mode** - Ya gated (solo se activa desde tools)
2. **VIBOY_DEBUG_PPU** - Ya gated (compile-time)
3. **VIBOY_DEBUG_UI** - Ya gated correctamente (env var)

## Conclusión

**Hallazgos críticos**:
- 3 instancias de checkerboard pattern que se activan automáticamente
- 1 instancia de BGP forzado que puede interferir con tests
- 1 instancia de auto-press que necesita guardrail más claro

**Acciones requeridas**:
1. Implementar kill-switch global `VIBOY_DEBUG_INJECTION` para checkerboard
2. Gatear auto-press con `VIBOY_AUTOPRESS`
3. Gatear BGP forzado con `VIBOY_FORCE_BGP`
4. Opcional: Gatear framebuffer trace con `VIBOY_FRAMEBUFFER_TRACE`

