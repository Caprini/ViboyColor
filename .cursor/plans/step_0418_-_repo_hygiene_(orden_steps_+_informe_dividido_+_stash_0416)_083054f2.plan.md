---
name: Step 0418 - Repo hygiene (orden Steps + informe dividido + stash 0416)
overview: "Restaurar coherencia del repo y documentación: Steps correlativos, bitácora index ordenada, informe dividido sin Steps fuera de rango, y resolver el stash pendiente (probablemente Step 0416 de PPU) con decisión A (cerrar) o B (descartar). Incluye verificación obligatoria build/test_build/pytest y cierre con commit+push."
todos:
  - id: 0418-t1-audit
    content: "Auditar coherencia: git status, stash list, presencia/orden 0414-0417 en bitácora index, rangos en informe dividido index."
    status: pending
  - id: 0418-t2-fix-report-split
    content: Reubicar Steps fuera de rango (ej. 0417 fuera de parte_00 0370-0412) y actualizar docs/informe_fase_2/index.md con rangos correctos.
    status: pending
    dependencies:
      - 0418-t1-audit
  - id: 0418-t3-resolve-stash-0416
    content: Inspeccionar y resolver stash (Ruta A cerrar 0416 real o Ruta B descartar) y alinear docs con la verdad (mejora parcial si aplica).
    status: pending
    dependencies:
      - 0418-t2-fix-report-split
  - id: 0418-t4-verify
    content: Ejecutar build_ext, test_build.py y pytest -q (suite completa) con logs a /tmp y reportar exit codes.
    status: pending
    dependencies:
      - 0418-t3-resolve-stash-0416
  - id: 0418-t5-docs
    content: Crear bitácora 0418 + actualizar docs/bitacora/index.html + actualizar parte correcta del informe dividido (0413+) con tabla de ubicación de steps.
    status: pending
    dependencies:
      - 0418-t4-verify
  - id: 0418-t6-git
    content: Cerrar Step 0418 con commit+push y repo limpio al final.
    status: pending
    dependencies:
      - 0418-t5-docs
---

# Plan: Step 0418 — Repo hygiene: ordenar Steps + arreglar informe dividido + resolver stash 0416

## Objetivo

Dejar el repositorio **coherente** antes de continuar con PPU/Zelda:

- Steps correlativos y reflejados correctamente en `docs/bitacora/index.html`.
- Informe dividido (`docs/informe_fase_2/`) con rangos correctos: **ninguna parte contiene Steps fuera de su [A,B]**.
- Resolver el **stash** pendiente (probable trabajo de PPU/Step 0416): **cerrarlo** correctamente o **descartarlo** y rectificar documentación.

## Reglas

- **No saturar contexto**: salidas a archivo cuando sea grande, y usar `head/tail/grep`.
- Mantener Steps correlativos: si se “recupera” 0416, debe quedar documentado como **mejora parcial** (Zelda pendiente) si aplica.

---

## [0418-T1] Auditoría rápida de coherencia (solo lectura / diagnóstico)

### 1A. Estado git + stashes

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git status -sb
git stash list | head -n 10
```



### 1B. Bitácora index (solo líneas 0414–0417)

**⚠️ NO pegar el archivo completo**

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
# Mostrar el bloque donde aparecen las entradas recientes
rg -n "Entrada 041[4-7]" docs/bitacora/index.html | head -n 50
# Si el índice no usa comentario Entrada NNNN, buscar por Step ID:
rg -n "Step ID:</strong> 041[4-7]" docs/bitacora/index.html | head -n 80
```



### 1C. Informe dividido: rangos de partes

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
sed -n '1,200p' docs/informe_fase_2/index.md
ls -1 docs/informe_fase_2 | sort
```

**Criterio de éxito T1**: identificar con certeza:

- si hay stash “0416” pendiente
- dónde están (mal) ubicados 0415/0416/0417 en informe
- si `docs/bitacora/index.html` está ordenado o necesita reorden

---

## [0418-T2] Arreglar el informe dividido (sin tocar contenido técnico)

### 2A. Detectar en qué archivo está 0417 (y 0415/0416)

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
rg -n "Step 0417" docs/informe_fase_2 | head -n 50
rg -n "Step 0416" docs/informe_fase_2 | head -n 50
rg -n "Step 0415" docs/informe_fase_2 | head -n 50
```



### 2B. Corregir rangos

Acción requerida:

- Quitar/mover la entrada de **0417** fuera de `parte_00_steps_0370_0412.md` (si está ahí).
- Crear (o usar si ya existe) una parte que cubra **0413–0418** (o 0413–XXXX) y colocar ahí **0415–0417** (y 0416 si corresponde).
- Actualizar `docs/informe_fase_2/index.md` con el nuevo archivo/rango.

**Criterio de éxito T2**:

- Ningún archivo `parte_XX_steps_A_B.md` contiene Steps fuera de `[A,B]`.

Comando de verificación rápida (post-fix):

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
# Ejemplo: comprobar que parte_00 no contiene 0413+
rg -n "Step 041[3-9]" docs/informe_fase_2/parte_00_steps_0370_0412.md || true
```

---

## [0418-T3] Resolver el stash PPU (probable 0416)

### 3A. Inspeccionar el stash sin mezclar

1) Identificar el stash candidato (por mensaje):

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git stash list | head -n 10
```

2) Ver el diff del stash (sin aplicarlo aún):

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
# Sustituye stash@{N} por el que corresponda

git stash show -p stash@{0} --stat
# Si hace falta más detalle (ojo, puede ser largo):
# git stash show -p stash@{0} | head -n 200
```



### 3B. Decisión (UNA ruta)

**Ruta A (recomendada si el cambio es válido)**:

- Aplicar stash en una rama de trabajo limpia:
```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git stash apply stash@{0}
```




- Verificar que lo que afirma la doc de 0416 está respaldado por código real.
- Ejecutar una verificación mínima de suite (con VBC_SUITE=1) para confirmar “mejora parcial” (si aplica) sin reventar logs.
- Ajustar la documentación de 0416 si el texto es demasiado optimista (debe decir explícitamente: **mejora parcial; Zelda pendiente**).
- Cerrar coherentemente 0416 si aún no está cerrado (si ya está en `main`/`develop` por commit, entonces este stash es basura → Ruta B).

**Ruta B (si era experimentación / duplicado / ya está en main)**:

- Descartar stash (drop) y eliminar/rectificar cualquier documentación de 0416 que no esté respaldada por código.
```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git stash drop stash@{0}
```


**Criterio de éxito T3**:

- Confirmación explícita: **0416 queda cerrado** (con evidencia en repo) o **0416 queda descartado** (y docs coherentes).

---

## [0418-T4] Verificación obligatoria del Step

**⚠️ IMPORTANTE - NO SATURAR CONTEXTO**: redirigir a `/tmp`.

```bash
cd /media/fabini/8CD1-4C30/ViboyColor

python3 setup.py build_ext --inplace > /tmp/viboy_step0418_build.log 2>&1
echo "BUILD_EXIT=$?"

python3 test_build.py > /tmp/viboy_step0418_test_build.log 2>&1
echo "TEST_BUILD_EXIT=$?"

pytest -q > /tmp/viboy_step0418_pytest.log 2>&1
echo "PYTEST_EXIT=$?"

tail -n 60 /tmp/viboy_step0418_pytest.log
```

---

## [0418-T5] Documentación

Crear bitácora:

- `docs/bitacora/entries/2026-01-02__0418__repo-hygiene-step-order-informe-dividido.html`

Debe incluir:

- Qué se arregló (índice de bitácora, informe dividido, stash 0416).
- Tabla corta: dónde quedan 0415/0416/0417 (archivo de informe)
- Evidencia de verificación: comandos + resultados (exit codes y resumen pytest).

Actualizar:

- `docs/bitacora/index.html` (insertar 0418 arriba, mantener formato antiguo obligatorio)
- Parte correcta del informe dividido (la de 0413+), y `docs/informe_fase_2/index.md`.

---

## [0418-T6] Git

Commit sugerido:

- `chore(docs): fix step order + report split (Step 0418)`
```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git add .
git commit -m "chore(docs): fix step order + report split (Step 0418)"
git push
```


---

## Output obligatorio del Ejecutor (para validación)

- Listado: “qué parte(s) del informe contienen 0415/0416/0417” tras el arreglo
- Confirmación: 0416 **cerrado** o **descartado**