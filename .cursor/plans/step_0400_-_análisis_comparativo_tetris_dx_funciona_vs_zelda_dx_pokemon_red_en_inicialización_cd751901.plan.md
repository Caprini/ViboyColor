---
name: "Step 0400 - Análisis comparativo: Tetris DX funciona vs Zelda DX/Pokemon Red en inicialización"
overview: Realizar análisis comparativo entre Tetris DX (funciona correctamente, gameplay_state=YES) y Zelda DX/Pokemon Red (estado de inicialización, no cargan tiles). Investigar diferencias en ejecución CPU, interrupciones, timing, registros críticos (LCDC, BGP, IE/IME) y secuencia de inicialización para identificar por qué algunos juegos progresan y otros no.
todos:
  - id: step0400-capture-snapshots
    content: Crear función capture_execution_snapshot() que registra estado completo (PC, opcode, LCDC, BGP, IE/IME/IF, VRAM, componentes) en frames clave (1, 60, 120, 240, 480, 720) con tag [EXEC-SNAPSHOT].
    status: pending
  - id: step0400-init-sequence
    content: Agregar tracking histórico de cambios de registros críticos (LCDC, BGP, IE, IME) en MMU.cpp y generar resumen de primeros 720 frames con tag [INIT-SEQUENCE] mostrando secuencia de inicialización.
    status: pending
  - id: step0400-irq-analysis
    content: Agregar contadores de interrupciones por tipo en CPU.cpp (VBlank, STAT, Timer, Serial, Joypad) y generar resumen cada 720 frames con tag [IRQ-SUMMARY] mostrando requests/services por tipo.
    status: pending
  - id: step0400-vram-progression
    content: Extender tracking histórico de VRAM en PPU.cpp para registrar frames de cambios (TileData >5%, TileMap >5%, unique_tile_ids >10, gameplay_state=YES) y generar log comparativo [VRAM-PROGRESSION] cada 120 frames.
    status: pending
  - id: step0400-opcode-distribution
    content: Agregar contador de opcodes por tipo (ALU, Load/Store, Control Flow, CB) en CPU.cpp y registrar distribución cada 1000 instrucciones (máx 10 logs) con tag [OPCODE-DIST].
    status: pending
  - id: step0400-comparative-tests
    content: Ejecutar tests comparativos con Tetris DX, Zelda DX y Pokemon Red (30s cada uno) y analizar logs para identificar diferencias clave en ejecución, inicialización, interrupciones y progresión VRAM.
    status: pending
    dependencies:
      - step0400-capture-snapshots
      - step0400-init-sequence
      - step0400-irq-analysis
      - step0400-vram-progression
      - step0400-opcode-distribution
  - id: step0400-docs
    content: Crear bitácora HTML Step 0400 + actualizar docs/bitacora/index.html + actualizar informe dividido con análisis comparativo completo, tabla comparativa y conclusiones con hipótesis para siguiente step.
    status: pending
    dependencies:
      - step0400-comparative-tests
---

# Plan: Step 0400 - Análisis Comparativo: Tetris DX Funciona vs Zelda DX/Pokemon Red en Inicialización

## Objetivo

El Step 0399 confirmó que:

- **Tetris DX**: Funciona correctamente, alcanza `gameplay_state=YES` desde Frame 720 con 256 tile IDs únicos
- **Zelda DX**: Permanece en estado de inicialización (1 tile ID único, todos 0x00) durante 60+ segundos
- **Pokemon Red**: Similar a Zelda DX, no progresa

Este step realiza un **análisis comparativo** para identificar qué diferencias en la ejecución causan que Tetris DX progrese mientras otros juegos se quedan en inicialización.

## Hipótesis

- **H1**: Diferencias en secuencia de inicialización (LCDC, BGP, IE/IME).
- **H2**: Tetris DX usa interrupciones/sincronización que funcionan, Zelda DX/Pokemon Red esperan condiciones diferentes.
- **H3**: Diferencias en timing de carga de VRAM (Tetris DX carga rápido, otros esperan eventos específicos).
- **H4**: Problemas de emulación de CPU que afectan a juegos más complejos (Zelda DX, Pokemon Red).

---

## Tareas

### Tarea 1: Capturar snapshots comparativos de ejecución (primeros 1000 frames)

**Objetivo**: Capturar estado de registros críticos en frames clave para comparar Tetris DX vs Zelda DX/Pokemon Red.**Archivo**: `src/core/cpp/PPU.cpp` o `src/core/cpp/CPU.cpp`**Implementación**:

- Crear función `capture_execution_snapshot()` que registra:
- Frame, PC, opcode actual
- LCDC, BGP, SCX, SCY
- IE, IME, IF
- VRAM estado: tiledata_nonzero, tilemap_nonzero, unique_tile_ids
- Estado de componentes: Timer activo, Joypad estado
- Ejecutar en frames: 1, 60, 120, 240, 480, 720 (comparar dónde Tetris DX alcanza gameplay_state)
- Generar logs con tag `[EXEC-SNAPSHOT]` limitados a estos frames específicos

**Criterio de éxito**: Se capturan snapshots comparables de Tetris DX vs Zelda DX/Pokemon Red en frames clave.---

### Tarea 2: Análisis de secuencia de inicialización (LCDC, BGP, IE/IME)

**Objetivo**: Comparar cuándo y cómo cada juego configura registros críticos.**Archivo**: `src/core/cpp/MMU.cpp`**Implementación**:

- Agregar tracking histórico de cambios de registros:
- LCDC (0xFF40): Registrar cada cambio con frame y valor
- BGP (0xFF47): Registrar cada cambio con frame y valor
- IE (0xFFFF): Registrar cada cambio con frame y valor
- IME: Registrar cambios con frame
- Generar resumen de primeros 720 frames con tag `[INIT-SEQUENCE]`:
- Frame en que LCDC se configura a valor final
- Frame en que BGP se configura a valor final (no 0x00)
- Frame en que IE se configura
- Frame en que IME se activa (si se activa)

**Criterio de éxito**: Se identifica la secuencia de inicialización de cada juego y se comparan diferencias.---

### Tarea 3: Análisis de interrupciones (qué interrupciones usa cada juego)

**Objetivo**: Comparar qué interrupciones activa y usa cada juego.**Archivo**: `src/core/cpp/CPU.cpp`**Implementación**:

- Agregar contadores de interrupciones por tipo (VBlank, STAT, Timer, Serial, Joypad).
- Registrar para cada interrupción:
- Número de solicitudes (IRQ requests)
- Número de servicios (IRQ services ejecutados)
- Frame de primera solicitud y servicio
- Generar resumen cada 720 frames con tag `[IRQ-SUMMARY]` mostrando:
- VBlank: requests/services
- STAT: requests/services
- Timer: requests/services
- Joypad: requests/services

**Criterio de éxito**: Se identifica qué interrupciones usa cada juego y si hay diferencias significativas.---

### Tarea 4: Análisis de progresión de VRAM (cuándo cargan tiles)

**Objetivo**: Comparar timing de carga de VRAM entre juegos.**Archivo**: `src/core/cpp/PPU.cpp`**Implementación**:

- Extender tracking histórico existente para registrar:
- Frame en que TileData cambia de 0% a >5%
- Frame en que TileMap cambia de 0% a >5%
- Frame en que unique_tile_ids cambia de 1 a >10
- Frame en que se alcanza gameplay_state=YES (si se alcanza)
- Generar log comparativo con tag `[VRAM-PROGRESSION]` cada 120 frames mostrando:
- Evolución de tiledata_nonzero, tilemap_nonzero, unique_tile_ids
- Comparación frame por frame entre juegos

**Criterio de éxito**: Se identifica el timing exacto de carga de VRAM y se comparan diferencias.---

### Tarea 5: Análisis de opcodes ejecutados (distribución)

**Objetivo**: Comparar si hay diferencias en qué opcodes usa cada juego.**Archivo**: `src/core/cpp/CPU.cpp`**Implementación**:

- Agregar contador de opcodes por tipo (ALU, Load/Store, Control Flow, CB prefix).
- Registrar distribución cada 1000 instrucciones (máx 10 logs):
- Conteo de opcodes por categoría
- Opcodes más comunes (top 10)
- Opcodes CB usados (si hay)
- Generar log con tag `[OPCODE-DIST]` para comparación

**Criterio de éxito**: Se identifica si hay diferencias significativas en qué opcodes usa cada juego.---

### Tarea 6: Tests comparativos y análisis

**Comandos**:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
python3 setup.py build_ext --inplace

# Test Tetris DX (30 segundos) - juego que funciona
timeout 30s python3 main.py roms/tetris_dx.gbc > logs/step0400_tetris_dx_comparative.log 2>&1

# Test Zelda DX (30 segundos) - juego en inicialización
timeout 30s python3 main.py roms/Oro.gbc > logs/step0400_zelda_dx_comparative.log 2>&1

# Test Pokemon Red (30 segundos) - juego en inicialización
timeout 30s python3 main.py roms/pkmn.gb > logs/step0400_pokemon_red_comparative.log 2>&1
```

**Análisis seguro**:

```bash
# Snapshots comparativos
for f in logs/step0400_*.log; do echo "=== $f ==="; grep -E "\[EXEC-SNAPSHOT\]" "$f" | head -n 15; done

# Secuencias de inicialización
for f in logs/step0400_*.log; do echo "=== $f ==="; grep -E "\[INIT-SEQUENCE\]" "$f" | head -n 10; done

# Interrupciones
for f in logs/step0400_*.log; do echo "=== $f ==="; grep -E "\[IRQ-SUMMARY\]" "$f" | head -n 5; done

# Progresión VRAM
for f in logs/step0400_*.log; do echo "=== $f ==="; grep -E "\[VRAM-PROGRESSION\]" "$f" | head -n 10; done
```

**Criterio de éxito**: Los logs revelan diferencias clave entre juegos que funcionan y juegos que no progresan.---

### Tarea 7: Documentación (bitácora + informe)

**Archivos**:

- `docs/bitacora/entries/2025-12-31__0400__analisis-comparativo-tetris-vs-zelda-pokemon.html`
- `docs/bitacora/index.html`
- `docs/informe_fase_2/index.md`
- Parte correspondiente en `docs/informe_fase_2/`

**Contenido obligatorio**:

- Concepto de hardware: Por qué diferentes juegos tienen diferentes secuencias de inicialización.
- Tabla comparativa: Tetris DX vs Zelda DX vs Pokemon Red (snapshots, secuencias, interrupciones, VRAM).
- Conclusiones: Diferencias identificadas y qué podría estar bloqueando a Zelda DX/Pokemon Red.
- Hipótesis para siguiente step: Qué debería investigarse o corregirse.

---

## Criterios de Éxito del Step

- ✅ Snapshots comparativos capturados en frames clave.
- ✅ Secuencias de inicialización comparadas y diferencias identificadas.
- ✅ Análisis de interrupciones revela diferencias entre juegos.
- ✅ Progresión de VRAM comparada frame por frame.
- ✅ Distribución de opcodes comparada (si es relevante).
- ✅ Conclusiones documentadas con hipótesis para siguiente step.

---

## Comandos Git

```bash
git add .
git commit -m "feat(debug): análisis comparativo Tetris DX vs Zelda DX/Pokemon Red (Step 0400)"
git push



```