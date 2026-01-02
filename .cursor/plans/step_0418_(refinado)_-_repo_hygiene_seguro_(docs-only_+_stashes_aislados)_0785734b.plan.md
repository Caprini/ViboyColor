---
name: Step 0418 (refinado) - Repo hygiene seguro (docs-only + stashes aislados)
overview: "Refinar el plan 0418 con proceso seguro: usar siempre la raíz git, identificar el stash correcto sin asumir stash@{0}, no mezclar código (PPU/MMU/renderer) en el commit de hygiene, y corregir informe dividido para que ningún archivo parte_XX_steps_A_B.md contenga steps fuera de rango. Incluye gates y outputs obligatorios por tarea."
todos:
  - id: 0418-t1-audit-readonly
    content: "Auditar coherencia (git/stash/bitácora/informe) y producir outputs obligatorios. Gate: stash si dirty."
    status: pending
  - id: 0418-t2-fix-report-split-docs-only
    content: Arreglar informe dividido creando parte 0413-0450 y moviendo 0413+; actualizar index.md; verificar con rg que parte_00 no contiene 0413+.
    status: pending
    dependencies:
      - 0418-t1-audit-readonly
  - id: 0418-t3-resolve-stashes-safely
    content: Clasificar stashes (A docs-only / B código) sin asumir stash@{0}; aplicar solo docs; aparcar código en rama WIP o descartar duplicados; outputs obligatorios.
    status: pending
    dependencies:
      - 0418-t2-fix-report-split-docs-only
  - id: 0418-t4-verify
    content: Ejecutar build_ext, test_build.py, pytest -q y pytest -q tests/test_core_cpu.py con logs a /tmp; reportar exit codes + tails.
    status: pending
    dependencies:
      - 0418-t3-resolve-stashes-safely
  - id: 0418-t5-docs-step
    content: Crear bitácora 0418 + actualizar docs/bitacora/index.html + actualizar docs/informe_fase_2/index.md (si aplica) con tabla de ubicación de steps y resolución de stashes.
    status: pending
    dependencies:
      - 0418-t4-verify
  - id: 0418-t6-git-docs-only
    content: Commit+push en develop con docs-only (verificar git diff --stat antes), y status final limpio.
    status: pending
    dependencies:
      - 0418-t5-docs-step
---

# Plan: Step 0418 (refinado) — Repo hygiene (orden Steps + informe dividido + stashes aislados)

## Objetivo

Restaurar coherencia del repo **antes** de continuar con PPU/Zelda:

- `docs/informe_fase_2/` cumple rangos: **ningún** `parte_XX_steps_A_B.md` contiene Steps fuera de `[A,B]`.
- `docs/bitacora/index.html` tiene Steps recientes en orden y con entries existentes.
- No queda un stash “misterioso” bloqueando el flujo.

## Reglas de proceso (críticas)

- No usar rutas absolutas: siempre `cd "$(git rev-parse --show-toplevel)"`.
- No asumir `stash@{0}`: **identificar** stash por mensaje/contenido.
- Step 0418 es **hygiene**: el commit en `develop` debe ser **docs-only**.
- Si un stash contiene **código** (PPU/MMU/renderer/etc): **NO** se mezcla en 0418. Se **aparca** en rama WIP (`git stash branch ...`) o se descarta si es duplicado.
- Evitar saturación: redirigir logs grandes a `/tmp`.

---

## [0418-T1] Auditoría (solo lectura, sin cambios)

### Comandos obligatorios

```bash
cd "$(git rev-parse --show-toplevel)"

git status -sb
git rev-parse --short HEAD

git stash list | head -n 20

rg -n "041[4-8]" docs/bitacora/index.html | head -n 120
ls -1 docs/bitacora/entries | rg "041[4-8]" || true

rg -n "Step 041[4-8]" docs/informe_fase_2 | head -n 80
sed -n '1,220p' docs/informe_fase_2/index.md
ls -1 docs/informe_fase_2 | sort
```



### OUTPUT obligatorio del Ejecutor (al final de T1)

- HEAD
- lista de stashes (top 5)
- tabla “Step -> archivo(s) donde aparece en informe” (0414–0418)
- confirmación: ¿existe entry HTML de 0416? ¿está linkeada en index?

### GATE T1

Si el working tree está **dirty**, el Ejecutor debe hacer stash antes de continuar:

```bash
cd "$(git rev-parse --show-toplevel)"
git stash push -u -m "WIP before Step0418 hygiene (keep develop clean)"
git status -sb
git stash list | head -n 5
```

---

## [0418-T2] Arreglo del informe dividido (docs only)

### Regla

- Si solo existe `parte_00_steps_0370_0412.md`, crear una parte nueva:
- `docs/informe_fase_2/parte_01_steps_0413_0450.md`
- Rango amplio para no crear partes cada 2 Steps.

### Acciones

- Mover (no duplicar) **todas** las entradas `Step 0413+` (incluyendo 0415/0416/0417/0418) a `parte_01_steps_0413_0450.md`.
- Actualizar `docs/informe_fase_2/index.md` para enlazar la nueva parte y su rango.

### Verificación obligatoria post-fix

```bash
cd "$(git rev-parse --show-toplevel)"

# parte_00 no debe contener steps 0413+
rg -n "Step 041[3-9]" docs/informe_fase_2/parte_00_steps_0370_0412.md || true

# parte_01 debe contener 0415-0418 (y 0416 si existe)
rg -n "Step 041[5-8]" docs/informe_fase_2/parte_01_steps_0413_0450.md
```



### OUTPUT obligatorio T2

- “parte_00 contiene: … / parte_01 contiene: …” (resumen por grep)

---

## [0418-T3] Resolver stashes (sin contaminar 0418)

### Objetivo

Que en `develop` no quede stash sin clasificar.

### PASO 1: Clasificar stashes (sin aplicar)

Para cada stash candidato (máx 3, escogidos por mensaje/fecha):

```bash
cd "$(git rev-parse --show-toplevel)"

git stash show -p stash@{N} --stat
```

Clasificar como:

- **Tipo A (docs-only)**: solo `docs/` (aplicable dentro de 0418 si hace falta)
- **Tipo B (código)**: toca `src/`, `tests/`, `setup.py`, etc. (NO mezclar en 0418)

### PASO 2: Resolver según tipo

#### Si es Tipo A (docs-only)

- Puede aplicarse en 0418:
```bash
cd "$(git rev-parse --show-toplevel)"
git stash apply stash@{N}
```




#### Si es Tipo B (código)

Opción recomendada: **aparcar en rama WIP sin mergear en este Step**:

```bash
cd "$(git rev-parse --show-toplevel)"

git stash branch wip/stash-step0416 stash@{N}

git status -sb

# (opcional) sanity, sin logs enormes
python3 setup.py build_ext --inplace > /tmp/viboy_step0418_wip_build.log 2>&1 || true

git add -A
git commit -m "wip: park stash from develop (not merged)"
git push -u origin wip/stash-step0416

# volver a develop

git checkout develop-v0.0.2
```

Si el stash es duplicado de algo ya presente en `develop`:

- documentar por qué (diffstat coincide) y hacer:
```bash
cd "$(git rev-parse --show-toplevel)"
git stash drop stash@{N}
```




### OUTPUT obligatorio T3

- Decisión por stash candidato: “aplicado (docs) / aparcado en rama WIP / descartado”
- `git stash list | head -n 5` final
- Confirmación: no quedan stashes sin clasificar.

### GATE T3

Si se crea rama WIP, el Ejecutor debe dejar explícito en el reporte que:

- la rama **NO se mergea** en Step 0418.

---

## [0418-T4] Verificación obligatoria (después de docs + stash resolution)

**⚠️ NO SATURAR CONTEXTO**: logs a `/tmp`, mostrar solo exit codes + tail.

```bash
cd "$(git rev-parse --show-toplevel)"

python3 setup.py build_ext --inplace > /tmp/viboy_step0418_build.log 2>&1
echo "BUILD_EXIT=$?"

python3 test_build.py > /tmp/viboy_step0418_test_build.log 2>&1
echo "TEST_BUILD_EXIT=$?"

pytest -q > /tmp/viboy_step0418_pytest.log 2>&1
echo "PYTEST_EXIT=$?"

tail -n 40 /tmp/viboy_step0418_pytest.log

pytest -q tests/test_core_cpu.py > /tmp/viboy_step0418_pytest_cpu.log 2>&1
echo "PYTEST_CPU_EXIT=$?"

tail -n 40 /tmp/viboy_step0418_pytest_cpu.log
```



### OUTPUT obligatorio T4

- exit codes: build / test_build / pytest / pytest_cpu
- tail relevante (máx 40 líneas)

---

## [0418-T5] Documentación Step 0418

Crear:

- `docs/bitacora/entries/2026-01-02__0418__repo-hygiene-step-order-informe-dividido.html`

Debe incluir:

- qué se arregló del informe dividido (antes/después)
- tabla: `Step 0415/0416/0417/0418 -> archivo correcto del informe`
- qué se hizo con stashes (aparcado/descartado/aplicado)
- verificación: comandos + exit codes + resumen pytest

Actualizar:

- `docs/bitacora/index.html` (0418 arriba, formato antiguo obligatorio)
- `docs/informe_fase_2/index.md` (si cambió)

---

## [0418-T6] Git (solo develop, commit docs-only)

### Pre-check: confirmar que el diff es docs-only

```bash
cd "$(git rev-parse --show-toplevel)"

git diff --stat
```

Si aparece cualquier `src/` / `tests/` / código:

- parar y aislar (stash o rama) antes de commitear.

### Commit sugerido

```bash
cd "$(git rev-parse --show-toplevel)"

git add docs/ 
# si hubo cambios fuera de docs por accidente, NO agregarlos

git commit -m "chore(docs): fix report split + resolve stashes safely (Step 0418)"
git push

git status -sb
```



### OUTPUT final obligatorio del Ejecutor

- `git status -sb` limpio
- diffstat del commit (resumen)
- confirmación: bitácora index ok + informe dividido ok + stash resuelto/aislado

---

## Entregable

Cerrar Step 0418 limpio. **No avanzar a Step 0419** hasta que:

- informe dividido esté correcto,