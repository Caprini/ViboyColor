---
name: "Step 0394 - Fix checkerboard: activación/desactivación determinista + métricas VRAM correctas"
overview: "Corregir la lógica y telemetría del checkerboard: (1) asegurar que vram_is_empty_ se calcula sobre la VRAM real dual-bank y cambia de estado cuando se cargan tiles/tilemap, (2) asegurar que render_scanline() deja de entrar al camino checkerboard cuando vram_is_empty_ es false, (3) emitir logs inequívocos de ON/OFF y métricas VRAM por región que el script de suite pueda usar sin falsos 'TileData=0%'."
todos:
  - id: step0394-vram-helper
    content: Unificar conteo VRAM non-zero (tiledata/tilemap) usando read_vram_bank para VRAM dual-bank en un helper estable.
    status: pending
  - id: step0394-checkerboard-state
    content: Añadir flag checkerboard_active_ y logs explícitos ON/OFF; asegurar apagado cuando vram_is_empty_ pasa a false.
    status: pending
    dependencies:
      - step0394-vram-helper
  - id: step0394-vram-regions-log
    content: Emitir log periódico [VRAM-REGIONS] y ajustar el analizador de suite para usarlo, evitando falsos TileData=0%.
    status: pending
    dependencies:
      - step0394-vram-helper
  - id: step0394-suite-verify
    content: Re-ejecutar suite de 6 ROMs y validar OFF del checkerboard y métricas coherentes (greps limitados).
    status: pending
    dependencies:
      - step0394-checkerboard-state
      - step0394-vram-regions-log
  - id: step0394-docs
    content: Crear bitácora HTML Step 0394 + actualizar docs/bitacora/index.html + actualizar informe dividido con resultados de suite y conclusiones.
    status: pending
    dependencies:
      - step0394-suite-verify
---

# Plan: Step 0394 - Fix checkerboard: activación/desactivación determinista + métricas VRAM correctas

## Objetivo

Tras Step 0393, hay dos problemas:1) **Checkerboard “persistente”**: las ROMs reportan 100 activaciones y nunca se ve una señal clara de desactivación.2) **Métricas VRAM inconsistentes**: el analizador reporta `TileData=0%` incluso cuando visualmente hay texto (p.ej. Tetris DX), lo cual apunta a que la medición está leyendo el buffer equivocado tras el VRAM dual‑bank.Este step debe:

- Hacer el checkerboard **determinista y autocontenible**: ON solo con VRAM realmente vacía y tile vacío; OFF al detectar VRAM con datos/tiles no vacíos.
- Hacer las métricas **correctas** para VRAM dual‑bank (sin leer `memory_` antiguo).

## Contexto

- Step 0389 separó VRAM en bancos y VBK.
- Step 0392 ya corrigió algunos chequeos de VRAM en PPU para usar `read_vram_bank`.
- Step 0393 ejecutó suite 6 ROMs, pero el resumen es contradictorio con observación visual.

## Hipótesis

- **H1 (métrica)**: el cálculo de “TileData %” está leyendo `memory_` antiguo o un rango incorrecto, y por eso da 0%.
- **H2 (lógica)**: el checkerboard se activa por un estado stale:
- `vram_is_empty_` se recalcula mal o tarde,
- se sobrescribe en otro punto,
- o se usa una condición que no refleja tiledata/tilemap.
- **H3 (observabilidad)**: el contador/print de activación está limitado a 100 y el analizador interpreta “100” como “siempre”, aunque pudiera apagarse después; falta un log explícito de OFF.

---

## Tareas

### Tarea 1: Unificar el cálculo de VRAM non-zero (dual-bank) en un solo helper

**Objetivo**: evitar lecturas mezcladas (`mmu_->read` vs `read_vram_bank`) y asegurar coherencia.**Archivos**:

- `src/core/cpp/PPU.cpp`
- (opcional) `src/core/cpp/MMU.hpp/.cpp`

**Implementación**:

- Crear un helper en PPU o MMU:
- `count_vram_nonzero_bank0_tiledata()` sobre `0x8000–0x97FF`.
- `count_vram_nonzero_bank0_tilemap()` sobre `0x9800–0x9FFF`.
- (opcional) conteo bank1 attrs para CGB.
- Debe usar **solo** `mmu_->read_vram_bank(bank, offset_or_addr)`.

**Criterio**:

- Las métricas reflejan lo mismo que el render real.

---

### Tarea 2: Estado de checkerboard con transición explícita ON→OFF

**Objetivo**: que el sistema tenga un “estado” claro y observable.**Archivo**: `src/core/cpp/PPU.cpp`**Implementación**:1) Definir claramente:

- `vram_is_empty_` derivado de conteo de VRAM (umbral consistente; p.ej. `tiledata_nonzero < 200`).
- `checkerboard_active_` (nuevo flag de PPU, si no existe):
- Se activa cuando `vram_is_empty_ == true` **y** el tile es vacío.
- Se desactiva cuando `vram_is_empty_ == false`.

2) Logs inequívocos (limitados):

- `[CHECKERBOARD-STATE] ON` cuando pasa OFF→ON
- `[CHECKERBOARD-STATE] OFF` cuando pasa ON→OFF
- Incluir: frame, LY, conteos tiledata/tilemap.

3) Reducir el ruido:

- El log pixel-a-pixel `[PPU-CHECKERBOARD-ACTIVATE]` solo como debug opcional (o mantener pero con límite muy bajo).

**Criterio**:

- En logs de suite se puede ver claramente si se apagó o no.

---

### Tarea 3: Métricas VRAM por región para la suite (sin falsos 0%)

**Objetivo**: que el analizador de Step 0393 use señales correctas.**Archivos**:

- `src/core/cpp/PPU.cpp` (o `MMU.cpp`)
- `tools/analyze_suite_step_0393.py` (o script equivalente)

**Implementación**:

- Emitir cada 120 frames (máx 10 líneas) un log estable:
- `[VRAM-REGIONS] tiledata_nonzero=.../6144 tilemap_nonzero=.../2048 vbk=...`
- Actualizar el analizador para:
- leer `[VRAM-REGIONS]` en vez de inferir por otras trazas.
- reportar “tiledata%” con esos conteos.

**Criterio**:

- Tetris DX debe mostrar tiledata% > 0 coherente con el texto visible.

---

### Tarea 4: Verificación con suite (mismo set de 6 ROMs)

**Comandos**:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
python3 setup.py build_ext --inplace

./tools/run_rom_suite_step_0393.sh
```

**Análisis seguro**:

```bash
# Ver transiciones ON/OFF
for f in logs/suite_0393/*.log; do echo "=== $f ==="; grep -E "\[CHECKERBOARD-STATE\]" "$f" | head -n 20; done

# Ver VRAM regions
for f in logs/suite_0393/*.log; do echo "=== $f ==="; grep -E "\[VRAM-REGIONS\]" "$f" | head -n 5; done

# Errores
for f in logs/suite_0393/*.log; do echo "=== $f ==="; grep -i "error|exception|traceback" "$f" | head -n 5; done
```

**Criterio**:

- En al menos Tetris DX y Pokémon Yellow/Red, ver `CHECKERBOARD-STATE OFF` si llegan a cargar.
- Las métricas VRAM por región no deben ser 0% si hay texto/tiledata.

---

### Tarea 5: Documentación (bitácora + informe)

**Archivos**:

- `docs/bitacora/entries/2025-12-30__0394__fix-checkerboard-metricas-vram.html`
- `docs/bitacora/index.html`
- `docs/informe_fase_2/index.md`
- Parte correspondiente en `docs/informe_fase_2/`.

**Obligatorio**:

- Concepto hardware: VRAM tiledata/tilemap y por qué un patrón diagnóstico debe apagarse.
- Tabla resumen de suite (6 ROMs) basada en `[VRAM-REGIONS]` y `[CHECKERBOARD-STATE]`.

---

## Criterios de éxito

- ✅ Logs muestran transiciones ON/OFF del checkerboard.
- ✅ Métricas de tiledata/tilemap son correctas bajo VRAM dual-bank.
- ✅ La suite deja de reportar falsos “TileData=0%” cuando visualmente hay tiles.

---

## Comandos Git

```bash
git add .
git commit -m "fix(ppu): checkerboard determinista y métricas VRAM dual-bank (Step 0394)"
git push



```