---
name: "Step 0416 - Fix PPU: framebuffer blanco con TileData alta (render_bg/render_window/swap)"
overview: "Diagnosticar y corregir por qué ROMs con TileData cargada (tetris_dx.gbc, zelda-dx.gbc) terminan con framebuffer todo blanco. Enfocar en: (1) gating LCDC/BG/Window y vram_has_tiles_, (2) lógica de swap/clear del doble buffering, (3) render_bg/render_window (tile addressing/attrs) y conversión CGB. Validación obligatoria: suite ROMs 2min paralela con VBC_SUITE=1 y logs mínimos."
todos:
  - id: step0416-log-analysis
    content: Extraer de logs Step 0415 las líneas clave (VIDEO-SUMMARY/VRAM-REGIONS/CGB-RGB-CHECK/TRANSITION) para aislar patrón blanco sin saturar.
    status: pending
  - id: step0416-pputarget-instrument
    content: Añadir instrumentación ultra-acotada en PPU (modo suite) para localizar si el blanco viene de gating, swap/clear, o render_bg/window.
    status: pending
    dependencies:
      - step0416-log-analysis
  - id: step0416-fix-swap-clear
    content: Auditar y corregir swap_framebuffers()/clear para asegurar que no se borra el front antes de que Python lo lea.
    status: pending
    dependencies:
      - step0416-pputarget-instrument
  - id: step0416-fix-render-gating
    content: Revisar/ajustar vram_has_tiles_ y condiciones LCDC/BG/Window para evitar falsos negativos cuando tiledata_effective es alta.
    status: pending
    dependencies:
      - step0416-fix-swap-clear
  - id: step0416-fix-render-bg-window
    content: Si evidencia lo indica, corregir addressing/tilemap base/attrs en render_bg() y/o render_window() (muestreo en modo suite).
    status: pending
    dependencies:
      - step0416-fix-render-gating
  - id: step0416-tests-suite
    content: Ejecutar suite ROMs 2 min simultánea con VBC_SUITE=1, logs por ROM y análisis acotado.
    status: pending
    dependencies:
      - step0416-fix-render-bg-window
  - id: step0416-docs
    content: Crear bitácora HTML Step 0416 + actualizar índice + actualizar informe con evidencia antes/después.
    status: pending
    dependencies:
      - step0416-tests-suite
---

# Plan: Step 0416 - Fix PPU: framebuffer blanco con TileData alta (render_bg/render_window/swap)

## Objetivo

Corregir el fallo observado en Step 0415:

- `tetris_dx.gbc` y `zelda-dx.gbc` reportan **TileData alta** pero el **framebuffer queda completamente blanco**.

Meta del Step:

- Que `tetris_dx.gbc` vuelva a mostrar imagen estable (no solo checkerboard/white).
- Que el “TRANSITION_TO_WHITE” (ej. `mario.gbc` frame 480) se reduzca/eliminee o quede explicado.

**Requisito de tests** (nuevo estándar): suite con **todas** las ROMs de `/media/fabini/8CD1-4C30/ViboyColor/roms`, **2 minutos**, **simultánea**, con `VBC_SUITE=1`, logs por ROM y análisis acotado.---

## Hipótesis (ordenadas)

1) **Gating/estado LCDC**: `LCDC bit7` (LCD off) o `bit0` (BG off) o `bit5` (Window) cambia y el renderer deja de dibujar → framebuffer queda en índice 0.2) **`vram_has_tiles_` demasiado estricto**: TileData puede estar cargada pero tilemap/diversidad baja → `vram_has_tiles_` se vuelve false y se omite render_bg/window.3) **Bug de doble buffering**: `swap_framebuffers()` o `clear_framebuffer` limpia el buffer equivocado (front en vez de back) o limpia justo antes de que Python lo lea.4) **Bug en render_bg/render_window**: tile addressing (signed/unsigned), tilemap base (LCDC bit3/bit6), o lectura de atributos CGB causa que `color_index` sea siempre 0.---

## Tarea 1: Extraer evidencia mínima de logs (sin saturar)

Antes de tocar lógica, usar los logs de la suite (Step 0415) para identificar el patrón exacto.**Comandos seguros**:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor

# Ver la telemetría resumida de las ROMs problemáticas (últimos ~80 eventos)
for rom in tetris_dx zelda mario Oro pkmn; do
  f=$(ls logs/step0415_suite/*${rom}*.log 2>/dev/null | head -n 1)
  [ -n "$f" ] || continue
  echo "=== $(basename "$f") ==="
  grep -E "\[VIDEO-SUMMARY\]|\[VRAM-REGIONS\]|\[CGB-RGB-CHECK\]|TRANSITION_TO_WHITE" "$f" | tail -n 80
  echo
Done
```

**Qué decidir con esto**:

- Si `LCDC BG off` o `LCD off` coincide con el blanco.
- Si `tilemap_nonzero` / `unique_tile_ids` se desploma antes del blanco.
- Si `fb_nonzero_indices` cae a 0 aunque tiledata siga alta.

---

## Tarea 2: Instrumentación C++ ultra-acotada para aislar el punto exacto

**Archivo**: [`src/core/cpp/PPU.cpp`](src/core/cpp/PPU.cpp)En modo suite (`VBC_SUITE=1`):

- Añadir un contador por frame (LY=144 o fin de frame) que capture:
- `nonzero_indices_front` (cuántos píxeles en `framebuffer_front_` son !=0)
- `nonzero_indices_back` (en `framebuffer_back_`)
- `did_render_bg`, `did_render_window`
- `LCDC`, `STAT`, `SCX/SCY`, `WX/WY`
- `vram_has_tiles_`, `tiledata_effective`, `unique_tile_ids`
- Log cada 120 frames (como `[VIDEO-SUMMARY]`) y log único en transición a blanco.

**Criterio de éxito**: localizar si el “blanco” se origina porque no se dibuja (gating) o porque el buffer se borra (swap/clear).---

## Tarea 3: Auditar y corregir `swap_framebuffers()` y limpieza

**Archivo**: [`src/core/cpp/PPU.cpp`](src/core/cpp/PPU.cpp)Verificar:

- Que el render escribe al **back buffer de índices**.
- Que `swap_framebuffers()` intercambia correctamente front/back.
- Que la limpieza ocurre en el **back** al empezar frame, no en el front ya listo para Python.
- Que `confirm_framebuffer_read()` no limpia indebidamente.

**Fix esperado si aplica**:

- Mover/asegurar `clear_framebuffer(back)` solo cuando `LY` se reinicia a 0 y/o después del swap.

---

## Tarea 4: Revisar gating `vram_has_tiles_` para evitar falsos negativos

**Archivo**: [`src/core/cpp/PPU.cpp`](src/core/cpp/PPU.cpp)

- Verificar el criterio actual (TileData + complete_tiles + diversidad) contra los valores reportados en `[VRAM-REGIONS]`.
- Si tetris_dx/zelda tienen tiledata alta pero `unique_tile_ids` baja momentáneamente, relajar el gating:
- CGB: permitir render si `tiledata_effective >= 200` aunque diversidad sea baja durante transición.
- Mantener checkerboard solo si tiledata_effective == 0.

**Criterio de éxito**: no “apagamos” el render por heurística cuando hay tiles reales.---

## Tarea 5: Revisar `render_bg()` y `render_window()` (tile addressing + tilemap base)

**Archivo**: [`src/core/cpp/PPU.cpp`](src/core/cpp/PPU.cpp)En modo suite, agregar un muestreo muy acotado (1 vez por 120 frames) de:

- tile_id, byte1/byte2 para un píxel fijo (x=80,y=72)
- `LCDC bit4` (signed/unsigned)
- tilemap base (LCDC bit3 / bit6)
- para CGB: attributes y palette_id

Si el muestreo muestra `byte1=byte2=0` siempre, el problema es de direccionamiento/base.---

## Tarea 6: Tests oficiales (suite ROMs 2 min, simultánea)

**⚠️ IMPORTANTE - NO SATURAR CONTEXTO**

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
python3 setup.py build_ext --inplace > build_log_step0416.txt 2>&1

mkdir -p logs/step0416_suite
export VBC_SUITE=1

pids=()
while IFS= read -r rom; do
  base=$(basename "$rom")
  safe=${base//[^A-Za-z0-9._-]/_}
  out="logs/step0416_suite/${safe}.log"
  timeout 120s python3 main.py "$rom" > "$out" 2>&1 &
  pids+=("$!")
done < <(find /media/fabini/8CD1-4C30/ViboyColor/roms -maxdepth 1 -type f \( -iname '*.gb' -o -iname '*.gbc' \) | sort)

for pid in "${pids[@]}"; do
  wait "$pid" || true
done
```

Análisis seguro:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
for f in logs/step0416_suite/*.log; do
  echo "=== $(basename "$f") ==="
  grep -E "\[VIDEO-SUMMARY\]|\[VRAM-REGIONS\]|\[CGB-RGB-CHECK\]|TRANSITION_TO_WHITE" "$f" | tail -n 60
  echo
done
```

**Criterios de éxito**:

- `tetris_dx.gbc`: `fb_nonzero_indices` estable y `CGB-RGB-CHECK` no-blanco sostenido.
- `zelda-dx.gbc`: si sigue blanco, que el log indique exactamente si es `LCDC off/BG off`, `tilemap=0`, o “render no escribe”.

---

## Documentación Step 0416

- `docs/bitacora/entries/2026-01-02__0416__fix-framebuffer-blanco-render-bg-window-swap.html`
- `docs/bitacora/index.html`
- Actualizar parte del informe `docs/informe_fase_2/`.

Incluir:

- Evidencia (extractos mínimos) antes/después.
- Conclusión: cuál de las hipótesis era correcta y qué fix se aplicó.

---

## Git

```bash
git add .
git commit -m "fix(ppu): corregir framebuffer blanco (render_bg/window/swap) (Step 0416)"
git push



```