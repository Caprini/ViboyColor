# Análisis de Monitores del Step 0290

## Objetivo

Analizar los logs generados por los nuevos monitores implementados en el Step 0290 para verificar:
1. **LCDC**: Si el LCD está configurado correctamente
2. **Paleta**: Si la paleta BGP se aplica correctamente durante el renderizado
3. **Carga de Tiles**: **CRÍTICO** - Si el juego está cargando tiles en VRAM y cuándo lo hace

## Pasos para Ejecutar el Análisis

### 1. Compilar el Módulo C++

```bash
python setup.py build_ext --inplace
```

### 2. Ejecutar el Emulador con una ROM

```bash
python main.py roms/pkmn.gb > debug_step_0290.log 2>&1
```

**Nota**: Ejecutar durante unos segundos (10-15 segundos) y luego detener con Ctrl+C para tener suficientes datos pero no saturar el log.

### 3. Analizar los Logs

```bash
python tools/analizar_monitores_step_0290.py debug_step_0290.log
```

## Qué Buscar en los Logs

### Monitor [LCDC-CHANGE]

**Formato del log:**
```
[LCDC-CHANGE] 0xXX -> 0xYY en PC:0xZZZZ (Bank:N) | LCD:ON/OFF BG:ON/OFF Window:ON/OFF
```

**Qué verificar:**
- ✅ LCD debe estar ON (bit 7 = 1)
- ✅ BG Display debe estar ON (bit 0 = 1)
- ⚠️ Si LCD está OFF, no se renderizará nada
- ⚠️ Si BG Display está OFF, no se renderizará el fondo

**Análisis esperado:**
- Debe haber cambios iniciales cuando el juego configura el LCD
- El valor final debe tener LCD:ON y BG:ON

### Monitor [PALETTE-APPLY]

**Formato del log:**
```
[PALETTE-APPLY] LY:72 X:80 | ColorIndex:N -> FinalColor:M | BGP:0xXX
```

**Qué verificar:**
- ✅ BGP debe ser 0xE4 (mapeo identidad estándar) o un valor válido
- ⚠️ Si BGP es 0x00, todos los colores se mapean a índice 0 (blanco/verde)
- ✅ ColorIndex debe mapear correctamente a FinalColor según BGP

**Análisis esperado:**
- Máximo 3 líneas (una por cada uno de los primeros 3 frames)
- Debe mostrar la aplicación correcta de la paleta

### Monitor [TILE-LOAD] (CRÍTICO)

**Formato del log:**
```
[TILE-LOAD] Write 8XXX=YY (TileID~N, Byte:M) PC:XXXX (Bank:B)
```

**Qué verificar:**
- ✅ **DEBE haber escrituras de tiles** - Si no hay ninguna, el juego NO está cargando tiles
- ✅ Tile IDs cargados - ¿Qué tiles se están cargando?
- ✅ PCs que cargan tiles - ¿Dónde en el código se cargan los tiles?
- ✅ Timing - ¿Cuándo se cargan los tiles? ¿Al inicio? ¿Durante el juego?

**Análisis esperado:**
- **Si NO hay escrituras**: El problema está confirmado - el juego no está cargando tiles en VRAM
- **Si HAY escrituras**: Necesitamos verificar:
  - ¿Se cargan tiles pero se borran después?
  - ¿Los tiles cargados coinciden con los referenciados por el tilemap?
  - ¿Hay alguna condición que impide la carga?

## Interpretación de Resultados

### Escenario 1: No se detectan escrituras de tiles ([TILE-LOAD] = 0)

**Diagnóstico**: El juego NO está cargando tiles en VRAM.

**Posibles causas:**
1. El juego espera que los tiles ya estén cargados desde la Boot ROM (no implementada)
2. Hay una condición que impide la carga de tiles (ej: LCD apagado, modo incorrecto)
3. Los tiles se cargan en un momento diferente al esperado (después de los primeros frames)
4. El juego usa un método de carga diferente (DMA, compresión, etc.)

**Próximos pasos:**
- Verificar si LCDC está configurado correctamente
- Verificar si hay alguna condición que impida la escritura en VRAM
- Implementar monitores adicionales para detectar otros métodos de carga

### Escenario 2: Se detectan escrituras de tiles ([TILE-LOAD] > 0)

**Diagnóstico**: El juego SÍ está cargando tiles, pero algo más está mal.

**Análisis necesario:**
1. **Timing**: ¿Cuándo se cargan los tiles?
   - Si se cargan después del frame 0, puede que el tilemap ya haya sido leído
2. **Tile IDs**: ¿Los tiles cargados coinciden con los referenciados por el tilemap?
   - Comparar Tile IDs cargados con Tile IDs del tilemap (del Step 0289)
3. **Borrado**: ¿Se borran los tiles después de cargarlos?
   - Buscar escrituras de 0x00 en las mismas direcciones después de cargar tiles

**Próximos pasos:**
- Analizar el timing de carga vs. renderizado
- Verificar si los tiles se borran después de cargarse
- Comparar Tile IDs cargados con Tile IDs del tilemap

### Escenario 3: LCDC está mal configurado

**Diagnóstico**: El LCD está apagado o el BG Display está deshabilitado.

**Solución:**
- Verificar por qué LCDC está mal configurado
- Puede ser que el juego espere un estado inicial diferente

### Escenario 4: BGP está mal configurado

**Diagnóstico**: La paleta está mapeando todos los colores a índice 0.

**Solución:**
- Verificar por qué BGP se pone a 0x00 (ya detectado en Step 0288)
- Implementar corrección para evitar que BGP se ponga a 0x00

## Comandos Rápidos

```bash
# Compilar
python setup.py build_ext --inplace

# Ejecutar (10-15 segundos, luego Ctrl+C)
python main.py roms/pkmn.gb > debug_step_0290.log 2>&1

# Analizar
python tools/analizar_monitores_step_0290.py debug_step_0290.log

# Buscar patrones específicos en el log
grep "[TILE-LOAD]" debug_step_0290.log | head -20
grep "[LCDC-CHANGE]" debug_step_0290.log
grep "[PALETTE-APPLY]" debug_step_0290.log
```

## Próximo Step (0291)

Basado en los resultados del análisis:
- Si NO hay carga de tiles: Investigar por qué no se cargan
- Si HAY carga de tiles: Investigar timing, borrado, o coincidencia con tilemap
- Aplicar correcciones necesarias

