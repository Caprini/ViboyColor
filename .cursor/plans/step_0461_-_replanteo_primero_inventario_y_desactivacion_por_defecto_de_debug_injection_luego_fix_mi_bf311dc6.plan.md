---
name: Step 0461 - REPLANTEO primero inventario y desactivacion por defecto de debug injection luego fix minimo OBJ palette
overview: "Inventariar todos los mecanismos de prueba/diagnóstico que puedan interferir (checkerboard/patrones, autopress/scripted input, fallbacks, test modes). Garantizar que por defecto no interfieren (gated con flags/env vars, kill-switch global). Solo si tras esto el test OBJ sigue fallando: fix mínimo OBJ palette en core (attr-buffer para diferenciar BG vs OBJ). No fixes por intuición, clean-room, no tocar timing."
todos:
  - id: 0461-t1-inventory
    content: "Ejecutar inventario exhaustivo con rg: A1) patrones/overlays (checkerboard, stripes, pygame.draw), A2) fallbacks (legacy presenter, surface.fill), A3) autopress/scripted input, A4) modos especiales (test_mode, VIBOY_DEBUG), A5) escrituras forzadas a registros. Crear docs/diag/inventory_debug_injections_0461.md con tabla completa (Feature, Archivo:línea, Condición de Activación, Impacto, Acción)."
    status: pending
  - id: 0461-t2-killswitch-gating
    content: "Si el inventario detecta interferencias: introducir kill-switch global (VIBOY_DEBUG_INJECTION env var, default OFF). Gatear patrones (checkerboard OFF por defecto), autopress (VIBOY_AUTOPRESS=1 explícito), y otros mecanismos. Añadir logging claro cuando se activa (1 línea cada 120 frames). Solo aplicar si hay riesgo real de interferencia en runtime normal."
    status: pending
    dependencies:
      - 0461-t1-inventory
  - id: 0461-t3-validate-ui
    content: "Ejecutar UI controlada (VIBOY_DEBUG_INJECTION=0, VIBOY_AUTOPRESS=0) y capturar logs mínimos por ROM (primeros 5 frames): path real (cpp_rgb_view), PC, LCDC, BGP, SCX, SCY, LY, indicador boolean de debug pattern activo. Analizar: si SCY está estable → posible interferencia; si SCY cambia → scroll normal."
    status: pending
    dependencies:
      - 0461-t2-killswitch-gating
  - id: 0461-t4-fix-obj-palette-if-needed
    content: "SOLO si tras inventario y kill-switch el test test_palette_dmg_obj_0454.py sigue fallando: implementar fix mínimo OBJ palette. Añadir buffer paralelo de atributos por pixel (framebuffer_attr_front_/back_) con bits is_obj y obj_pal. En render_bg() escribir attr=0, en render_sprites() escribir attr con is_obj=1. En swap también swap attr buffers. En convert_framebuffer_to_rgb() usar BGP u OBP según atributo."
    status: pending
    dependencies:
      - 0461-t3-validate-ui
  - id: 0461-t5-execute-tests
    content: Ejecutar tests objetivo (test_palette_dmg_bgp_0454.py, test_palette_dmg_obj_0454.py, test_framebuffer_not_flat_0456.py) y suite completa. Validar que tests pasan o bug identificado con evidencia si persiste.
    status: pending
    dependencies:
      - 0461-t4-fix-obj-palette-if-needed
  - id: 0461-t6-document
    content: Documentar Step 0461 (inventario completo, kill-switch/gating aplicado, validación UI, fix OBJ palette si aplica) en bitácora HTML e informe dividido. Incluir resumen del inventario y snippet clave del fix OBJ palette si se aplicó.
    status: pending
    dependencies:
      - 0461-t5-execute-tests
---

# Plan: Step 0461 — REPLANTEO: Primero Inventario y "Desactivación por Defecto" de TODO lo que Pueda Inyectar Patrones/Inputs/Debug en Runtime

## Objetivo

Ahora que sabemos que en algún punto del proyecto se añadió un patrón como prueba de render, es irresponsable seguir interpretando "lo que veo en pantalla" como output del emulador sin antes descartar interferencias (overlays, fill patterns, autopress, modo demo, fallbacks, etc.). Esto puede estar contaminando tanto el análisis visual como los tests.La idea es simple: inventario → evidencia de si está activo → kill-switch por defecto. Y después atacamos el único rojo real (OBJ palette) con un fix limpio.---

## Guardrails

- **No "fixes por intuición"**: solo cambios basados en evidencia del inventario.
- **Clean-room**: basado en documentación técnica.
- **No tocar timing**: no modificar ciclos ni sincronización.
- **No tocar PPU core** salvo que sea estrictamente necesario para OBJ palette (y con evidencia).

---

## Fase A — [0461-T1] Inventario de "Interferencias" (OBLIGATORIA, Antes de Tocar Core)

### Objetivo

Generar lista exhaustiva de todos los mecanismos que puedan interferir con el output del emulador.

### Implementación

**A1) Buscar patrones/overlays/test-render**:

```bash
cd "$(git rev-parse --show-toplevel)"

# Patrones visuales
rg -n --hidden --glob '!**/.git/**' \
   "(checker|chequer|stripe|pattern|test[_-]?pattern|draw[_-]?pattern|fill[_-]?pattern|debug[_-]?pattern|render[_-]?test|grid|barras|rayas|ajedrez)" \
   src tools tests > /tmp/viboy_0461_inventory_patterns.txt

# Operaciones de dibujo Pygame
rg -n --hidden --glob '!**/.git/**' \
   "(pygame\.draw|surfarray\.blit_array|blit_array|make_surface|transform\.scale|SCALED)" \
   src > /tmp/viboy_0461_inventory_pygame.txt
```

**A2) Buscar fallbacks que "dibujan algo" cuando no hay frame válido**:

```bash
rg -n --hidden \
   "(fallback|legacy|presenter|if .*rgb_view is None|if .*framebuffer.*None|clear\(|fill\(|surface\.fill)" \
   src/gpu src > /tmp/viboy_0461_inventory_fallbacks.txt
```

**A3) Buscar inyección de input (autopress / scripted joypad)**:

```bash
rg -n --hidden \
   "(autopress|auto[_-]?press|scripted|demo[_-]?mode|inject[_-]?input|joypad.*press|press_start|turbo|macro)" \
   src tools tests > /tmp/viboy_0461_inventory_autopress.txt
```

**A4) Buscar "modos especiales" que puedan alterar estado**:

```bash
rg -n --hidden \
   "(test[_-]?mode|triage|diagnostic|VIBOY_DEBUG|VIBOY_TEST|FORCE_|STUB_|FAKE_|OVERRIDE_)" \
   src tools tests > /tmp/viboy_0461_inventory_modes.txt
```

**A5) Buscar escrituras forzadas a registros (LCDC/BGP/SCX/SCY)**:

```bash
rg -n --hidden \
   "(write.*0xFF40|write.*0xFF47|write.*0xFF48|write.*0xFF49|write.*0xFF42|write.*0xFF43|LCDC.*=|BGP.*=|SCX.*=|SCY.*=)" \
   src tools tests > /tmp/viboy_0461_inventory_regwrites.txt
```

**Generar documento de inventario**:Crear `docs/diag/inventory_debug_injections_0461.md` con tabla:

```markdown
# Inventario de Debug/Test Injections (Step 0461)

Fecha: 2026-01-02

## Objetivo
Identificar todos los mecanismos que puedan interferir con el output del emulador (patrones, autopress, fallbacks, modos especiales).

## Tabla de Hallazgos

| Feature | Archivo:línea | Condición de Activación | Impacto | Acción |
|---------|---------------|------------------------|---------|--------|
| checkerboard pattern | src/core/cpp/PPU.cpp:XXXX | `vram_is_empty_ && enable_checkerboard_temporal` | Visual (patrón ajedrez) | Gatear / Documentar |
| auto-press joypad | src/viboy.py:XXXX | `simulate_input` flag | Input (presiona botones) | Gatear |
| ... | ... | ... | ... | ... |

## Resumen por Categoría

### Patrones Visuales
- [Lista de hallazgos]

### Input Injection
- [Lista de hallazgos]

### Fallbacks/Legacy
- [Lista de hallazgos]

### Modos Especiales
- [Lista de hallazgos]

### Registros Forzados
- [Lista de hallazgos]

## Recomendaciones

### Alto Riesgo (interfieren siempre o con flag débil)
- [Lista]

### Medio Riesgo (solo en tests/tools, pero sin guardrails claros)
- [Lista]

### Bajo Riesgo (ya gated correctamente)
- [Lista]
```



### Criterios de Éxito

- Inventario completo generado con todos los hallazgos.
- Documento `docs/diag/inventory_debug_injections_0461.md` creado con tabla y resumen.
- Cada hallazgo incluye: archivo:línea, condición de activación, impacto, acción recomendada.

---

## Fase B — [0461-T2] Kill-Switch y Gating por Defecto (Solo Si Hay Riesgo Real)

### Objetivo

Si el inventario detecta algo que pueda activarse en ejecución normal, aplicar kill-switch y gating.

### Implementación

**Introducir kill-switch global**:

```cpp
// En src/core/cpp/common.hpp o similar:
inline bool is_debug_injection_enabled() {
    // Por defecto: OFF en runtime normal
    // Solo activar si VIBOY_DEBUG_INJECTION=1 explícitamente
    const char* env = std::getenv("VIBOY_DEBUG_INJECTION");
    return (env != nullptr && std::string(env) == "1");
}
```

**Gating de patrones**:

```cpp
// En PPU.cpp, donde se activa checkerboard:
if (vram_is_empty_ && enable_checkerboard_temporal) {
    // --- Step 0461: Gate checkerboard con kill-switch ---
    if (!is_debug_injection_enabled()) {
        // Checkerboard OFF por defecto en runtime normal
        // Solo activar si VIBOY_DEBUG_INJECTION=1
        return;  // O usar framebuffer blanco/negro simple
    }
    
    // ... (código checkerboard) ...
}
```

**Gating de autopress**:

```python
# En src/viboy.py, donde se simula input:
# --- Step 0461: Gate autopress con kill-switch ---
VIBOY_AUTOPRESS = os.environ.get('VIBOY_AUTOPRESS', '0') == '1'
if VIBOY_AUTOPRESS:
    # Solo activar si VIBOY_AUTOPRESS=1 explícitamente
    simulate_input(...)
```

**Logging cuando se activa**:

```cpp
// En cualquier punto donde se active un patrón/input:
if (is_debug_injection_enabled()) {
    static int log_count = 0;
    if (log_count < 5) {
        log_count++;
        printf("[DEBUG-INJECTION] Checkerboard activo (VIBOY_DEBUG_INJECTION=1)\n");
    }
}
```



### Criterios de Éxito

- Kill-switch global implementado (env var `VIBOY_DEBUG_INJECTION`).
- Patrones/autopress gated: OFF por defecto, solo activan con flag explícito.
- Logging claro cuando se activa (1 línea cada 120 frames o similar).

---

## Fase C — [0461-T3] Validación Visual Controlada (Sin Interpretar Aún)

### Objetivo

Ejecutar UI y capturar logs mínimos para verificar que no hay interferencias activas.

### Implementación

**Modificar `tools/abrir_roms_cuadricula.sh`** (o crear versión diagnóstica):

```bash
#!/bin/bash
# Versión diagnóstica: captura logs sin silenciar stdout/stderr

# Asegurar que kill-switch está OFF
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0

# Ejecutar UI con logs
timeout 5s python3 src/viboy.py "roms/mario.gbc" 2>&1 | \
    grep -E "\[UI-PATH\]|\[DEBUG-INJECTION\]|\[PPU-.*\]" | \
    head -n 50 > /tmp/viboy_0461_ui_mario.log

# Extraer métricas clave:
# - Path real (cpp_rgb_view)
# - PC, LCDC, BGP, SCX, SCY, LY
# - Indicador boolean de "debug pattern activo"
```

**Script de análisis**:

```bash
#!/bin/bash
# Analizar logs de UI para detectar interferencias

ROM=$1
LOG_FILE="/tmp/viboy_0461_ui_${ROM}.log"

echo "=== Análisis UI para ${ROM} ==="

# Path real
echo "Path:"
grep "\[UI-PATH\]" "$LOG_FILE" | head -n 1

# Registros I/O (primeros 5 frames)
echo ""
echo "Registros I/O (primeros 5 frames):"
grep "\[UI-PATH\]" "$LOG_FILE" | head -n 5 | \
    grep -oE "PC=[0-9A-Fa-f]+|LCDC=[0-9A-Fa-f]+|BGP=[0-9A-Fa-f]+|SCX=[0-9]+|SCY=[0-9]+|LY=[0-9]+"

# Debug pattern activo?
echo ""
echo "Debug pattern activo?:"
if grep -q "\[DEBUG-INJECTION\]" "$LOG_FILE"; then
    echo "SÍ (interferencia detectada)"
    grep "\[DEBUG-INJECTION\]" "$LOG_FILE" | head -n 3
else
    echo "NO (ninguna interferencia detectada)"
fi

# SCY cambiando (scroll normal vs interferencia)
echo ""
echo "SCY values (primeros 5 frames):"
grep "\[UI-PATH\]" "$LOG_FILE" | head -n 5 | grep -oE "SCY=[0-9]+" | cut -d= -f2
```



### Criterios de Éxito

- Logs capturados para 1-2 ROMs (Mario, Pokémon) con primeros 5 frames.
- Métricas extraídas: PC, LCDC, BGP, SCX, SCY, LY.
- Indicador boolean de "debug pattern activo".
- Si SCY está estable → posible interferencia. Si SCY cambia → scroll normal del juego.

---

## Fase D — [0461-T4] SOLO Si Persiste el Rojo: Fix Mínimo OBJ Palette (Core)

### Objetivo

Si tras A-C el test `test_palette_dmg_obj_0454.py` sigue fallando, implementar fix mínimo para diferenciar BG vs OBJ en la conversión DMG.

### Implementación

**Implementación recomendada (mínimo riesgo, sin romper tests de índices)**:**Añadir buffer paralelo de atributos por pixel (front/back)**:

```cpp
// En PPU.hpp:
// --- Step 0461: Buffer de atributos por pixel (BG vs OBJ, paleta) ---
std::vector<uint8_t> framebuffer_attr_front_;  // Atributos front (23040 bytes)
std::vector<uint8_t> framebuffer_attr_back_;   // Atributos back (23040 bytes)

// Bits del atributo:
// bit 0: is_obj (0=BG, 1=OBJ)
// bit 1: obj_pal (0=OBP0, 1=OBP1)
// bits 2-7: reservados (futuro: prioridad, etc.)
```

**Render: BG escribe attr=0, Sprite escribe attr con is_obj=1**:

```cpp
// En render_bg(), al escribir pixel:
framebuffer_back_[idx] = final_color;
framebuffer_attr_back_[idx] = 0x00;  // BG: is_obj=0

// En render_sprites(), al escribir pixel:
framebuffer_back_[idx] = sprite_color_idx;
framebuffer_attr_back_[idx] = 0x01 | (use_obp1 ? 0x02 : 0x00);  // OBJ: is_obj=1, pal=OBP0/OBP1
```

**Swap: también swap attr buffers**:

```cpp
// En swap_framebuffers():
std::swap(framebuffer_front_, framebuffer_back_);
std::swap(framebuffer_attr_front_, framebuffer_attr_back_);  // ← Añadir
```

**Convert DMG: usar BGP u OBP según atributo**:

```cpp
// En convert_framebuffer_to_rgb():
for (uint16_t y = 0; y < SCREEN_HEIGHT; y++) {
    for (uint16_t x = 0; x < SCREEN_WIDTH; x++) {
        size_t fb_index = y * SCREEN_WIDTH + x;
        uint8_t color_idx = framebuffer_front_[fb_index] & 0x03;
        uint8_t attr = framebuffer_attr_front_[fb_index];
        
        // Determinar paleta según atributo
        uint8_t pal_reg;
        bool is_obj = (attr & 0x01) != 0;
        
        if (is_obj) {
            // OBJ: usar OBP0 u OBP1 según bit 1
            bool use_obp1 = (attr & 0x02) != 0;
            pal_reg = use_obp1 ? obp1 : obp0;
        } else {
            // BG: usar BGP
            pal_reg = bgp;
        }
        
        // Aplicar paleta
        uint8_t shade = dmg_apply_palette(color_idx, pal_reg);
        
        // Convertir shade a RGB
        uint8_t r, g, b;
        dmg_shade_to_rgb(shade, r, g, b);
        
        // Escribir RGB
        size_t rgb_idx = fb_index * 3;
        framebuffer_rgb_front_[rgb_idx + 0] = r;
        framebuffer_rgb_front_[rgb_idx + 1] = g;
        framebuffer_rgb_front_[rgb_idx + 2] = b;
    }
}
```



### Criterios de Éxito

- Fix mínimo aplicado solo si test OBJ sigue fallando tras inventario y kill-switch.
- Atributo buffer implementado (is_obj, obj_pal).
- Convert DMG usa BGP u OBP según atributo.
- Tests objetivo pasan: `test_palette_dmg_obj_0454.py` pasa.
- No rompe tests de índices ni CGB path.

---

## [0461-T5] Ejecución Obligatoria

### Implementación

```bash
cd "$(git rev-parse --show-toplevel)"

# Ejecutar inventario
bash tools/abrir_roms_cuadricula.sh  # Con logs capturados

# Ejecutar tests objetivo
pytest -v tests/test_palette_dmg_bgp_0454.py tests/test_palette_dmg_obj_0454.py tests/test_framebuffer_not_flat_0456.py

# Suite completa
pytest -q
```



### Criterios de Éxito

- Inventario completo generado.
- Kill-switch/gating aplicado si hay riesgo.
- Tests objetivo pasan (o bug identificado con evidencia si persiste).

---

## [0461-T6] Documentación

### Implementación

**Crear entrada HTML Step 0461**:`docs/bitacora/entries/2026-01-02__0461__inventario-debug-injection-killswitch-fix-obj-palette.html`Incluir:

- Inventario (resumen): nº hallazgos + 3 ejemplos con archivo:línea + "siempre on / gated".
- ¿Se encontró interferencia activa?: sí/no + evidencia (condición real).
- Cambios de gating/kill-switch: sí/no + detalle.
- Validación UI: 1-2 ROMs con logs de SCY/SCX/LCDC (5 líneas) + "pattern debug activo?: sí/no".
- OBJ palette: ¿se tocó core?: sí/no. Si sí: resumen del attr-buffer + por qué era necesario.

**Actualizar**:

- `docs/bitacora/index.html`
- `docs/informe_fase_2/parte_01_steps_0412_0450.md`

---

## Formato Exigido al Ejecutor

```text
STEP_0461_DONE_REPORT

HEAD:

Inventario (resumen): nº hallazgos + 3 ejemplos con archivo:línea + "siempre on / gated"

¿Se encontró interferencia activa?: sí/no + evidencia (condición real)

Cambios de gating/kill-switch: sí/no + detalle

Validación UI: 1–2 ROMs con logs de SCY/SCX/LCDC (5 líneas) + "pattern debug activo?: sí/no"

OBJ palette: ¿se tocó core?: sí/no. Si sí: resumen del attr-buffer + por qué era necesario

Tests objetivo (3) + pytest -q global

BUILD_EXIT / TEST_BUILD_EXIT / PYTEST_EXIT:

Archivos tocados:

Snippet clave (10-25 líneas)

Conclusión (1 frase)

Nota crítica (para evitar autoengaño)

Vuestro síntoma "patrones blancos y negros bajando" puede ser literalmente SCY. Sin logs de SCY/SCX + confirmación de que ningún "pattern mode" está activo, ese síntoma no vale como evidencia de bug.

Este STEP 0461 es para limpiar el terreno y volver a confiar en lo que vemos y medimos. Después, si queda el rojo OBJ, se arregla con el attr-buffer (que es el fix correcto).

```