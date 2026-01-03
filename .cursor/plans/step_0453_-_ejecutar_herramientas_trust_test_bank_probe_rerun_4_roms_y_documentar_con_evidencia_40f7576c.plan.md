---
name: Step 0453 - Ejecutar herramientas trust test bank probe rerun 4 ROMs y documentar con evidencia
overview: "EJECUTAR primero (no documentar sin datos): ejecutar test_headless_trust_0452.py para validar headless, ejecutar mbc_bank_probe_0452.py sobre 3 ROMs (MBC5/MBC3/MBC1), rerun headless 4 ROMs (Mario, Pokémon, Tetris DX, Tetris) con métricas nuevas, analizar resultados y decidir causa raíz (MBC mapping vs CPU/IRQ vs PPU/paletas). SOLO DESPUÉS documentar Step 0452 y 0453 con resultados reales incrustados."
todos:
  - id: 0453-t1-execute-headless-trust
    content: Ejecutar test_headless_trust_0452.py y validar que reporta vram_raw_nz > 0 y nonwhite > 0 en ≤60 frames. Si falla, NO seguir con MBC probe (problema en lectura/runner). Guardar salida en /tmp/viboy_0453_headless_trust.txt.
    status: pending
  - id: 0453-t2-execute-mbc-bank-probe
    content: "Ejecutar mbc_bank_probe_0452.py sobre 3 ROMs (MBC5: mario.gbc, MBC3: pkmn.gb, MBC1: tetris_dx.gbc). Validar que mapping coincide con bytes del ROM (read(0x4000) == byte esperado). Si un MBC falla, identificar cuál para fix en siguiente step. Guardar salidas en /tmp/viboy_0453_probe_*.txt."
    status: pending
    dependencies:
      - 0453-t1-execute-headless-trust
  - id: 0453-t3-rerun-headless-4-roms
    content: "Rerun headless sobre 4 ROMs (mario.gbc, pkmn.gb, tetris_dx.gbc, tetris.gb) con métricas nuevas. Extraer tabla: ROM | pc_end | mbc_writes | vram_raw_nz | vram_write_nonzero | nonwhite. Generar decisión automática: mapping roto vs CPU/IRQ vs PPU/paletas. Guardar salidas en /tmp/viboy_0453/*.txt."
    status: pending
    dependencies:
      - 0453-t2-execute-mbc-bank-probe
  - id: 0453-t4-document-steps-0452-0453
    content: Documentar Steps 0452 y 0453 con resultados reales incrustados. Crear entrada HTML Step 0452 (VRAM storage + headless trust + MBC probe), entrada HTML Step 0453 (ejecución + evidencia + decisión), actualizar índice bitácora y informe dividido.
    status: pending
    dependencies:
      - 0453-t3-rerun-headless-4-roms
  - id: 0453-t5-verify-and-report
    content: Generar STEP_0453_DONE_REPORT con valores reales (headless trust PASS/FAIL, MBC probe PASS/FAIL por tipo, tabla rerun 4 ROMs, decisión automática, docs completados). Verificar que BUILD_EXIT, archivos tocados y conclusión están claros.
    status: pending
    dependencies:
      - 0453-t4-document-steps-0452-0453
  - id: 0453-t6-git-commit
    content: Commit y push con mensaje descriptivo que incluye ejecución de herramientas, decisión automática y documentación con evidencia. NO documentar sin ejecutar primero.
    status: pending
    dependencies:
      - 0453-t5-verify-and-report
---

# Pl

an: Step 0453 — Ejecutar Herramientas (Trust Test + Bank Probe + Rerun 4 ROMs) y Documentar con Evidencia

## Objetivo

**EJECUTAR PRIMERO, DOCUMENTAR DESPUÉS**. No escribir narrativa sin evidencia.Ejecutar:

1. Headless trust test (ROM clean-room conocida)
2. MBC bank probe (3 ROMs: MBC5/MBC3/MBC1)
3. Rerun headless 4 ROMs con métricas nuevas

Con esos 3 outputs, decidir si el siguiente fix es:

- **MBC mapping roto** (probe falla)
- **CPU/IRQ/boot** (VRAM writes nonzero = 0)
- **PPU/paletas** (VRAM nonzero > 0 y nonwhite = 0)

**SOLO DESPUÉS**: Documentar Step 0452 y 0453 con resultados reales incrustados.---

## Guardrails

- **NO documentar sin ejecutar primero**.
- **NO asumir resultados**: medir y reportar evidencia.
- **Si headless trust falla → NO seguir con MBC probe** (problema en lectura/runner).
- **Documentación al final** con valores reales de ejecución.

---

## Fase A — [0453-T1] Ejecutar Headless Trust Test (OBLIGATORIO)

### Objetivo

Demostrar que headless ve `nonwhite > 0` y `vram_raw_nz > 0` en ROM clean-room conocida.

### Implementación

**Verificar que la herramienta existe**:

```bash
cd "$(git rev-parse --show-toplevel)"
ls -la tools/test_headless_trust_0452.py
```

**Ejecutar headless trust test**:

```bash
cd "$(git rev-parse --show-toplevel)"
mkdir -p /tmp/viboy_0453

python3 tools/test_headless_trust_0452.py 2>&1 | tee /tmp/viboy_0453_headless_trust.txt
```

**Criterio PASS**:

- Reporta `vram_raw_nz > 0` en ≤60 frames
- Reporta `nonwhite > 0` en ≤60 frames
- No hay errores de importación ni crashes

**Si FALLA**:

- Problema en lectura/runner headless
- NO seguir con MBC probe (diagnóstico está contaminado)
- Reportar error y corregir en siguiente step

**Análisis de salida**:

```bash
# Extraer métricas clave
grep -E "vram_raw_nz|nonwhite|max_nonwhite|max_vram" /tmp/viboy_0453_headless_trust.txt

# Verificar si PASS o FAIL
grep -i "pass\|fail\|error\|assertion" /tmp/viboy_0453_headless_trust.txt | tail -n 10
```



### Criterios de Éxito

- Headless trust test ejecuta sin crashes
- Reporta `vram_raw_nz > 0` y `nonwhite > 0`
- Salida guardada en `/tmp/viboy_0453_headless_trust.txt`

---

## Fase B — [0453-T2] Ejecutar MBC Bank Probe (OBLIGATORIO)

### Objetivo

Comprobar que el mapping de bancos coincide con los bytes del ROM en disco.

### Implementación

**Verificar que la herramienta existe**:

```bash
cd "$(git rev-parse --show-toplevel)"
ls -la tools/mbc_bank_probe_0452.py
```

**Ejecutar sobre 3 ROMs representativas**:

```bash
cd "$(git rev-parse --show-toplevel)"

# MBC5 (mario.gbc o zelda-dx.gbc)
python3 tools/mbc_bank_probe_0452.py roms/mario.gbc 2>&1 | tee /tmp/viboy_0453_probe_mbc5.txt

# MBC3 (pkmn.gb o Oro.gbc)
python3 tools/mbc_bank_probe_0452.py roms/pkmn.gb 2>&1 | tee /tmp/viboy_0453_probe_mbc3.txt

# MBC1 (tetris_dx.gbc)
python3 tools/mbc_bank_probe_0452.py roms/tetris_dx.gbc 2>&1 | tee /tmp/viboy_0453_probe_mbc1.txt
```

**Criterio PASS**:

- Para N banks muestreados: `read(0x4000+off) == byte esperado del archivo ROM`
- Todos los banks coinciden (o >90% coinciden si hay edge cases)

**Si un MBC FALLA**:

- Mapping roto en ese MBC específico
- Step siguiente = fix mapping en ese MBC (uno por step)

**Análisis de salida**:

```bash
# Extraer resultados por MBC
echo "=== MBC5 (Mario) ==="
grep -E "Bank|esperado|obtenido|✅|❌|Resultados:" /tmp/viboy_0453_probe_mbc5.txt | tail -n 20

echo "=== MBC3 (Pokémon) ==="
grep -E "Bank|esperado|obtenido|✅|❌|Resultados:" /tmp/viboy_0453_probe_mbc3.txt | tail -n 20

echo "=== MBC1 (Tetris DX) ==="
grep -E "Bank|esperado|obtenido|✅|❌|Resultados:" /tmp/viboy_0453_probe_mbc1.txt | tail -n 20

# Resumen de PASS/FAIL
for probe in mbc5 mbc3 mbc1; do
    echo "--- $probe ---"
    grep "Resultados:" /tmp/viboy_0453_probe_${probe}.txt || echo "No se encontraron resultados"
done
```



### Criterios de Éxito

- MBC bank probe ejecuta sobre 3 ROMs (MBC5/MBC3/MBC1)
- Reporta PASS/FAIL por tipo MBC
- Incluye ejemplo concreto: bank X esperado vs leído
- Salidas guardadas en `/tmp/viboy_0453_probe_*.txt`

---

## Fase C — [0453-T3] Rerun Headless 4 ROMs con Métricas Nuevas

### Objetivo

Capturar métricas confiables de 4 ROMs clave para diagnóstico.

### Implementación

**Verificar que `rom_smoke_0442.py` imprime métricas necesarias**:Revisar que `rom_smoke_0442.py` reporta:

- `pc_end`
- `vram_raw_nz`
- `vram_write_nonzero_count` (añadir si no existe aún)
- `nonwhite_pixels`
- `mbc_write_count`

**Si `vram_write_nonzero_count` no existe**:Añadir contador rápido en `tools/rom_smoke_0442.py`:

```python
# En ROMSmokeRunner.__init__():
self.vram_write_nonzero_count = 0

# En _step_frame() o similar, interceptar writes a VRAM:
# (Nota: Esto requiere exponer contador desde MMU o interceptar en Python)
# Por ahora, usar estimación basada en muestreo si no está expuesto
```

**Ejecutar rerun**:

```bash
cd "$(git rev-parse --show-toplevel)"
mkdir -p /tmp/viboy_0453

run_one() {
    local rom="$1"
    echo "=== Ejecutando headless para $rom ==="
    python3 tools/rom_smoke_0442.py "roms/${rom}" --frames 240 2>&1 | tee "/tmp/viboy_0453/${rom}.txt"
    echo ""
}

run_one mario.gbc
run_one pkmn.gb
run_one tetris_dx.gbc
run_one tetris.gb
```

**Extraer tabla de resultados**:

```bash
cd /tmp/viboy_0453

echo "ROM | pc_end | mbc_writes | vram_raw_nz | vram_write_nonzero | nonwhite"
echo "----|--------|------------|-------------|---------------------|----------"

for rom in mario.gbc pkmn.gb tetris_dx.gbc tetris.gb; do
    # Extraer métricas del log
    pc_end=$(grep -i "pc.*end\|final.*pc\|I/O RESUMEN" "${rom}.txt" | grep -oE "0x[0-9A-Fa-f]+|[0-9A-Fa-f]{4}" | tail -n 1 || echo "0000")
    mbc_count=$(grep -i "mbc.*write\|MBC-SUMMARY" "${rom}.txt" | grep -oE "[0-9]+" | head -n 1 || echo "0")
    vram_raw=$(grep -i "vram.*nonzero\|VRAM NONZERO" "${rom}.txt" | grep -oE "[0-9]+" | head -n 1 || echo "0")
    vram_write_nz=$(grep -i "vram.*write.*nonzero\|VRAM.*write.*non.*zero" "${rom}.txt" | grep -oE "[0-9]+" | head -n 1 || echo "0")
    nonwhite=$(grep -i "nonwhite\|non.*white" "${rom}.txt" | grep -oE "[0-9]+" | tail -n 1 || echo "0")
    
    echo "${rom} | 0x${pc_end} | ${mbc_count} | ${vram_raw} | ${vram_write_nz} | ${nonwhite}"
done
```

**Decisión automática**:

```bash
# Generar decisión basada en tabla
cd /tmp/viboy_0453

# Si MBC probe falló → mapping roto
if grep -q "❌.*Mapping.*roto\|FAIL.*mapping" probe_*.txt; then
    echo "Decisión: fix MBC mapping (probe falló)"
elif [ "$vram_write_nonzero" = "0" ] && [ "$mbc_count" -gt 0 ] && [ "$pc_end" != "0000" ]; then
    echo "Decisión: CPU/IRQ/boot/joypad gating (PC progresa, MBC writes existen, pero no hay writes a VRAM)"
elif [ "$vram_raw" -gt 0 ] && [ "$nonwhite" = "0" ]; then
    echo "Decisión: PPU/paletas/render path (VRAM tiene datos pero framebuffer blanco)"
else
    echo "Decisión: Requiere análisis manual (métricas mixtas)"
fi
```



### Criterios de Éxito

- Headless ejecuta sobre 4 ROMs (Mario, Pokémon, Tetris DX, Tetris)
- Tabla muestra: ROM | pc_end | mbc_writes | vram_raw_nz | vram_write_nonzero | nonwhite
- Decisión automática identifica causa raíz (mapping vs CPU/IRQ vs PPU)

---

## Fase D — [0453-T4] Documentar Steps 0452 y 0453 con Resultados Reales

### Objetivo

Completar documentación de Steps 0452 y 0453 incrustando resultados reales de ejecución.

### Implementación

**Completar entrada HTML de Step 0452**:Crear `docs/bitacora/entries/2026-01-02__0452__validar-diagnostico-vram-raw-headless-mapping-bancos.html`:Incluir:

- Confirmación VRAM storage (MMU vs PPU) + evidencia write→read_raw
- Test write→read_raw (resultado de test mínimo)
- **INCORPORAR**: Resultados de headless trust test (Fase A)
- **INCORPORAR**: Resultados de MBC bank probe (Fase B)

**Crear entrada HTML de Step 0453**:Crear `docs/bitacora/entries/2026-01-02__0453__ejecutar-herramientas-trust-probe-rerun-documentar-evidencia.html`:Incluir:

- Ejecución de headless trust test (valores reales: vram_raw_nz, nonwhite, frames)
- Ejecución de MBC bank probe (PASS/FAIL por MBC1/MBC3/MBC5 + ejemplo)
- Rerun 4 ROMs (tabla completa con valores reales)
- Decisión automática (causa raíz identificada)

**Actualizar índice de bitácora**:Actualizar `docs/bitacora/index.html`:

- Añadir entrada 0452 (al principio de la lista)
- Añadir entrada 0453 (después de 0452)

**Actualizar informe dividido**:Actualizar `docs/informe_fase_2/parte_01_steps_0412_0450.md` (o parte correspondiente):

- Añadir Step 0452 (validación VRAM storage, headless trust, MBC bank probe)
- Añadir Step 0453 (ejecución + evidencia + decisión)

### Criterios de Éxito

- Entrada HTML Step 0452 incluye resultados reales (headless trust + MBC probe)
- Entrada HTML Step 0453 incluye tabla completa de rerun y decisión
- Índice y informe actualizados

---

## [0453-T5] Verificación Obligatoria

**Extraer resumen ejecutivo**:

```bash
cd /tmp/viboy_0453

cat > STEP_0453_DONE_REPORT.txt << 'EOF'
STEP_0453_DONE_REPORT

HEAD:

Headless trust test: [PASS/FAIL] + valores (vram_raw_nz=[X], nonwhite=[Y], frames=[Z])

MBC bank probe:
- MBC5 (mario.gbc): [PASS/FAIL] + ejemplo (bank [X] esperado 0x[AA], leído 0x[BB])
- MBC3 (pkmn.gb): [PASS/FAIL] + ejemplo (bank [X] esperado 0x[AA], leído 0x[BB])
- MBC1 (tetris_dx.gbc): [PASS/FAIL] + ejemplo (bank [X] esperado 0x[AA], leído 0x[BB])

Rerun 4 ROMs (tabla):
ROM | pc_end | mbc_writes | vram_raw_nz | vram_write_nonzero | nonwhite
----|--------|------------|-------------|---------------------|----------
mario.gbc | 0x[XXXX] | [N] | [M] | [P] | [Q]
pkmn.gb | 0x[XXXX] | [N] | [M] | [P] | [Q]
tetris_dx.gbc | 0x[XXXX] | [N] | [M] | [P] | [Q]
tetris.gb | 0x[XXXX] | [N] | [M] | [P] | [Q]

Decisión automática (1 línea): "[fix MBCX mapping]" o "[CPU/IRQ]" o "[PPU/paleta]"

Docs: 0452/0453 bitácora + índice + informe (sí/no)

BUILD_EXIT: [0/1]
TEST_BUILD_EXIT: [N/A si no hay tests]
PYTEST_EXIT: [N/A si no hay tests]

Archivos tocados:
- tools/test_headless_trust_0452.py (ejecutado, no modificado)
- tools/mbc_bank_probe_0452.py (ejecutado, no modificado)
- tools/rom_smoke_0442.py (posible modificación para vram_write_nonzero_count)
- docs/bitacora/entries/2026-01-02__0452__*.html (nuevo)
- docs/bitacora/entries/2026-01-02__0453__*.html (nuevo)
- docs/bitacora/index.html (actualizado)
- docs/informe_fase_2/parte_01_steps_0412_0450.md (actualizado)

Snippet clave (10-25 líneas):
[Incluir snippet de decisión automática o ejemplo de tabla]

Conclusión (1 frase):
[Una frase que resume la causa raíz identificada y el siguiente step]
EOF

# Rellenar valores reales
# (Se completará manualmente con resultados de ejecución)
```

---

## [0453-T6] Git Commit

**Commit sugerido**:

```javascript
feat(diag): ejecutar herramientas trust/probe/rerun y documentar con evidencia (Step 0453)

- Ejecutar test_headless_trust_0452.py (validar headless confiable)
- Ejecutar mbc_bank_probe_0452.py sobre 3 ROMs (MBC5/MBC3/MBC1)
- Rerun headless 4 ROMs con métricas nuevas (pc_end, vram_raw_nz, vram_write_nonzero, nonwhite, mbc_writes)
- Decisión automática: causa raíz identificada (MBC mapping vs CPU/IRQ vs PPU/paletas)
- Documentar Steps 0452 y 0453 con resultados reales incrustados
- NO documentar sin ejecutar primero (evitar narrativa sin evidencia)
```

---

## Formato Exigido al Ejecutor (exacto)

```text
STEP_0453_DONE_REPORT

HEAD:

Headless trust test: PASS/FAIL + valores (vram_raw_nz, nonwhite, frames)

MBC bank probe: PASS/FAIL por MBC1/MBC3/MBC5 + 1 ejemplo (bank/off esperado vs leído)

Rerun 4 ROMs (tabla):
ROM | pc_end | mbc_writes | vram_raw_nz | vram_write_nonzero | nonwhite

Decisión automática (1 línea): "fix MBCX mapping" o "CPU/IRQ" o "PPU/paleta"

Docs: 0452/0453 bitácora + índice + informe (sí/no)

BUILD_EXIT / TEST_BUILD_EXIT / PYTEST_EXIT:

Archivos tocados:

Snippet clave (10-25 líneas):

Conclusión (1 frase)

Respuesta a tu pregunta ("¿documentar ahora o ejecutar?")

Ejecutar primero. Documentar ahora es escribir ficción.
```

---