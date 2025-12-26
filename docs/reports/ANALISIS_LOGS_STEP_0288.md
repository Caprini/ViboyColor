# Análisis Selectivo de Logs - Step 0288

**Fecha**: 2025-12-25  
**Objetivo**: Identificar patrones clave en los logs de diagnóstico para resolver el problema de pantalla verde/blanca en Pokémon Red.

---

## Resumen Ejecutivo

El análisis de los logs revela **dos problemas críticos**:

1. **VRAM está siendo escrita con ceros (0x00)**: Todas las 500 escrituras detectadas en VRAM tienen valor 0x00, lo que indica que el juego está limpiando/borrando VRAM pero **no está cargando datos de gráficos**.

2. **BGP se pone temporalmente a 0x00**: Durante la ejecución, BGP cambia a 0x00, lo que mapea todos los colores a índice 0 (blanco/verde). Aunque se restaura a 0xE4, esto podría causar problemas visuales.

**Aspectos positivos**:
- DMA funciona correctamente (49 activaciones)
- Handler de V-Blank se ejecuta correctamente (49 ejecuciones)
- LCDC está configurado correctamente (0xE3)
- V-Blank trace funciona (49 rastreos)

---

## Hallazgos Detallados por Monitor

### 1. [VRAM-VIBE] - Escrituras de Datos de Gráficos Reales

**Resultado**: ❌ **0 matches** (CRÍTICO)

**Análisis**:
- El monitor `[VRAM-VIBE]` está diseñado para detectar escrituras en VRAM con valores distintos de 0x00 y 0x7F (datos de gráficos reales).
- **No se detectó ninguna escritura de datos de gráficos**.
- Esto confirma que el juego no está cargando tiles/sprites en VRAM durante el período analizado.

**Implicación**: La VRAM está vacía o contiene solo ceros, lo que explica por qué la pantalla muestra verde/blanco.

---

### 2. [VRAM-TOTAL] - Todas las Escrituras en VRAM

**Resultado**: ✅ **500 escrituras detectadas** (límite alcanzado)

**Análisis**:
- **Todas las escrituras tienen valor 0x00**.
- Las escrituras ocurren en el rango 0x8000-0x8030 (Tile Data Area).
- Todas provienen del mismo PC: `0x36E3` (Bank:1).
- El patrón sugiere que el juego está **limpiando/borrando VRAM** en lugar de cargar gráficos.

**Ejemplos**:
```
[VRAM-TOTAL] Write 8000=00 PC:36E3 (Bank:1)
[VRAM-TOTAL] Write 8001=00 PC:36E3 (Bank:1)
[VRAM-TOTAL] Write 8002=00 PC:36E3 (Bank:1)
...
```

**Implicación**: El código en `0x36E3` está escribiendo ceros en VRAM. Esto podría ser:
- Una rutina de inicialización que limpia VRAM antes de cargar gráficos.
- Un bug en el emulador que impide que el juego cargue gráficos correctamente.
- El juego está esperando una condición que no se cumple (ej: timing, interrupciones).

---

### 3. [DMA-TRIGGER] - Activación de OAM DMA

**Resultado**: ✅ **49 activaciones detectadas**

**Análisis**:
- El DMA se activa correctamente desde `0xFF82` (HRAM).
- Copia desde `0xC300-0xC39F` a OAM `0xFE00-0xFE9F`.
- El patrón es consistente: una activación por frame (aproximadamente).

**Ejemplo**:
```
[DMA-TRIGGER] DMA activado: Source=0xC300 (0xC300-0xC39F) -> OAM (0xFE00-0xFE9F) | PC:0xFF82
```

**Implicación**: El DMA funciona correctamente. Los sprites se están cargando en OAM, pero si no hay datos en VRAM, los sprites no se renderizarán correctamente.

---

### 4. [BGP-CHANGE] - Cambios en el Registro de Paleta de Fondo

**Resultado**: ⚠️ **3 cambios detectados** (1 problemático)

**Análisis**:
1. `0xFC -> 0xE4` en PC:0x0000 (Bank:1) - Inicialización correcta
2. `0xE4 -> 0x00` en PC:0x1F6A (Bank:1) - **PROBLEMA**: BGP se pone a 0x00
3. `0x00 -> 0xE4` en PC:0x1F85 (Bank:1) - Restauración correcta

**Problema identificado**:
- BGP = 0x00 significa que todos los índices de color (0-3) se mapean a color 0 (blanco/verde).
- Aunque se restaura rápidamente, si esto ocurre durante el renderizado, causará pantalla verde/blanca.

**Implicación**: Necesitamos verificar:
- ¿Cuándo ocurre el cambio a 0x00 en relación con el renderizado?
- ¿El cambio a 0x00 es intencional (ej: fade out) o un bug?

---

### 5. [HANDLER-EXEC] - Ejecución del Handler de V-Blank

**Resultado**: ✅ **49 ejecuciones detectadas**

**Análisis**:
- El handler se ejecuta correctamente en cada V-Blank.
- Salta a `0x2024` desde el vector `0x0040`.
- El handler ejecuta múltiples instrucciones (hasta 500 capturadas).

**Ejemplo**:
```
[HANDLER-EXEC] PC:0x0040 OP:0xC3 | A:0x40 HL:0xA000 | IME:0
[HANDLER-EXEC] PC:0x2024 OP:0xF5 | A:0x40 HL:0xA000 | IME:0
[HANDLER-EXEC] PC:0x2025 OP:0xC5 | A:0x40 HL:0xA000 | IME:0
...
```

**Implicación**: El handler de V-Blank funciona correctamente. El problema no está en la sincronización de interrupciones.

---

### 6. [VBLANK-TRACE] - Rastreo del Vector de V-Blank

**Resultado**: ✅ **49 rastreos detectados**

**Análisis**:
- El vector `0x0040` siempre salta a `0x2024`.
- El rastreo funciona correctamente.

**Ejemplo**:
```
[VBLANK-TRACE] Vector 0x0040: JP 0x2024 detectado. Iniciando rastreo del handler...
```

**Implicación**: El sistema de interrupciones funciona correctamente.

---

### 7. LCDC (LCD Control Register)

**Resultado**: ✅ **Configuración correcta (0xE3)**

**Análisis**:
- LCDC = 0xE3 = `11100011` (binario)
- Bit 7 (LCD Enable): 1 ✅
- Bit 6 (Window Tile Map): 1 (0x9C00)
- Bit 5 (Window Display): 1 ✅
- Bit 4 (Tile Data Base): 0 (0x8800 signed)
- Bit 3 (BG Tile Map): 0 (0x9800)
- Bit 2 (Sprite Size): 0 (8x8)
- Bit 1 (Sprite Display): 1 ✅
- Bit 0 (BG Display): 1 ✅

**Implicación**: LCDC está configurado correctamente. El problema no está en la configuración del LCD.

---

## Patrones Sospechosos

### Patrón 1: VRAM Solo Recibe Ceros

**Observación**: Todas las escrituras en VRAM son 0x00, todas desde PC:0x36E3.

**Hipótesis**:
1. El juego está en una fase de inicialización que limpia VRAM antes de cargar gráficos.
2. El juego está esperando una condición que no se cumple (ej: timing, interrupciones, estado de hardware).
3. Hay un bug en el emulador que impide que el juego cargue gráficos (ej: acceso a VRAM bloqueado durante cierto período).

**Acción requerida**: Investigar el código en `0x36E3` y verificar si hay condiciones que impidan la carga de gráficos.

---

### Patrón 2: BGP Temporalmente a 0x00

**Observación**: BGP cambia a 0x00 en PC:0x1F6A y se restaura en PC:0x1F85.

**Hipótesis**:
1. El juego está haciendo un fade out/fade in (transición de pantalla).
2. El juego está limpiando la pantalla antes de mostrar nuevos gráficos.
3. Hay un bug en el emulador que causa que BGP se ponga a 0x00 incorrectamente.

**Acción requerida**: Verificar el timing del cambio de BGP en relación con el renderizado. Si el cambio ocurre durante el renderizado, causará pantalla verde/blanca.

---

## Problema Raíz Identificado

**Problema Principal**: **VRAM está vacía (solo ceros)**

La pantalla verde/blanca se debe a que:
1. VRAM no contiene datos de gráficos (solo ceros).
2. El tilemap probablemente apunta a tiles vacíos (todos con valor 0x00).
3. Cuando el PPU renderiza, lee tiles vacíos y aplica la paleta, resultando en pantalla verde/blanca.

**Problema Secundario**: BGP se pone temporalmente a 0x00, lo que agrava el problema.

---

## Próximos Pasos (Step 0289)

1. **Implementar monitor de lectura de VRAM** (`[VRAM-READ]`):
   - Capturar qué direcciones lee la PPU.
   - Verificar qué valores obtiene la PPU.

2. **Implementar inspector de Tilemap** (`[TILEMAP-INSPECT]`):
   - Al inicio de cada frame (LY=0), imprimir los primeros 32 bytes del tilemap.
   - Identificar qué tile IDs se están usando.

3. **Implementar inspector de Tile Data** (`[TILEDATA-INSPECT]`):
   - Cuando se lee un tile, verificar si contiene datos != 0x00.

4. **Investigar el código en PC:0x36E3**:
   - ¿Por qué está escribiendo ceros en VRAM?
   - ¿Hay condiciones que impidan la carga de gráficos?

---

## Conclusión

El análisis confirma que el problema principal es que **VRAM está vacía**. El juego está escribiendo ceros en VRAM pero no está cargando datos de gráficos. Esto explica por qué la pantalla muestra verde/blanco.

El siguiente paso (Step 0289) debe implementar monitores adicionales para verificar:
- Qué lee la PPU de VRAM.
- Qué contiene el tilemap.
- Qué datos tienen los tiles.

Esto nos permitirá confirmar el problema y determinar si es un bug del emulador o un comportamiento esperado del juego que requiere condiciones adicionales.

