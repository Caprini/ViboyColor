# Reporte Step 0320: Pruebas con ROMs Reales

**Fecha**: 2025-12-27  
**Step ID**: 0320  
**Duración de cada prueba**: 2.5 minutos (150 segundos)

## Resumen Ejecutivo

Se ejecutaron pruebas con 3 ROMs diferentes para verificar el sistema de diagnóstico implementado en el Step 0320. Los resultados muestran que:

1. ✅ **Los logs de diagnóstico funcionan correctamente** - Se detectan cambios en LCDC, activación del LCD, y estado de VRAM
2. ❌ **El problema de pantalla blanca persiste** - Todas las ROMs muestran framebuffer completamente blanco
3. ⚠️ **Causa raíz identificada**: Los tiles de prueba fueron sobrescritos por el juego, y aunque el tilemap apunta a ellos, los tiles están vacíos (todos ceros)

## Resultados por ROM

### 1. Pokémon Red (pkmn.gb) - ROM GB

**Logs generados**: 58,825,120 líneas

**Cambios de LCDC detectados**: 5 cambios
- Frame 1: LCDC cambió de 0xFF → 0x99 (LCD ON, BG ON)
- Frame 1: LCDC cambió de 0x99 → 0x80 (LCD ON, BG OFF)
- Frame 1: LCDC cambió de 0x80 → 0x81 (LCD ON, BG ON - forzado por el sistema)

**Activaciones de LCD detectadas**: 389,932 (⚠️ **PROBLEMA**: Se dispara demasiadas veces, necesita corrección)

**Verificación de VRAM**:
- Frame 4920: Tiles de prueba fueron sobrescritos con ceros (Checksum: 0x0000)
- Los tiles de prueba fueron completamente borrados por el juego

**Renderizado**:
- Píxeles no-blancos: 0/160 (100% blanco)
- Distribución: 0=160, 1=0, 2=0, 3=0
- **WARNING**: Toda la línea es blanca (todos los píxeles son 0)

**Tilemap**:
- Tilemap Base: 0x9800
- Tile Data Base: 0x9000 (signed addressing)
- Primera fila del tilemap: `00 01 02 03 00 01 02 03 00 01 02 03 00 01 02 03`
- El tilemap apunta a tiles 0, 1, 2, 3 (los tiles de prueba)

**Datos de Tiles**:
- Tile ID 03 en dirección 0x9030: Byte1=0x00, Byte2=0x00
- **WARNING**: Tile 03 contiene solo ceros (tile vacío)
- Los tiles apuntados por el tilemap están vacíos

**Conclusión**: El tilemap apunta a los tiles de prueba (0, 1, 2, 3), pero estos tiles fueron sobrescritos con ceros por el juego. Por eso se renderiza todo blanco.

---

### 2. Tetris (tetris.gb) - ROM GB

**Cambios de LCDC detectados**: 3 cambios
- Frame 1: LCDC cambió de 0xFF → 0x99 (LCD ON, BG ON)
- Frame 2: LCDC cambió de 0x99 → 0x03 (LCD OFF, BG ON)
- Frame 2: LCDC cambió de 0x03 → 0x80 (LCD ON, BG OFF)

**Activaciones de LCD detectadas**: 113

**Verificación de VRAM**:
- Frame 8880: Tiles de prueba fueron sobrescritos con ceros (Checksum: 0x0000)
- Los tiles de prueba fueron completamente borrados por el juego

**Renderizado**:
- Píxeles no-blancos: 0/160 (100% blanco)
- Distribución: 0=160, 1=0, 2=0, 3=0
- **WARNING**: Toda la línea es blanca (todos los píxeles son 0)

**Conclusión**: Similar a Pokémon Red. Los tiles de prueba fueron sobrescritos y el tilemap apunta a tiles vacíos.

---

### 3. Super Mario Deluxe (mario.gbc) - ROM GBC

**Cambios de LCDC detectados**: 1 cambio
- Frame 1: LCDC cambió de 0xFF → 0x99 (LCD ON, BG ON)

**Activaciones de LCD detectadas**: 542,984 (⚠️ **PROBLEMA**: Se dispara demasiadas veces, necesita corrección)

**Verificación de VRAM**:
- Frame 60: Tiles de prueba intactos (Checksum: 0x17E8)
- **IMPORTANTE**: Los tiles de prueba NO fueron sobrescritos en esta ROM

**Renderizado**:
- Píxeles no-blancos: 0/160 (100% blanco)
- Distribución: 0=160, 1=0, 2=0, 3=0
- **WARNING**: Toda la línea es blanca (todos los píxeles son 0)

**Conclusión**: Aunque los tiles de prueba siguen intactos en VRAM, el renderizado sigue siendo blanco. Esto sugiere que el tilemap no apunta a los tiles de prueba, o hay otro problema en el pipeline de renderizado.

---

## Análisis de Problemas Identificados

### Problema 1: Tiles de Prueba Sobrescritos

**Síntoma**: En pkmn.gb y tetris.gb, los tiles de prueba fueron sobrescritos con ceros por el juego.

**Causa**: Los juegos cargan sus propios tiles en VRAM durante la inicialización, sobrescribiendo los tiles de prueba.

**Impacto**: Aunque el tilemap apunta a los tiles de prueba (0, 1, 2, 3), estos tiles están vacíos, resultando en renderizado blanco.

**Solución propuesta**: 
- No depender de tiles de prueba permanentes
- Esperar a que el juego cargue sus propios tiles
- Verificar que el tilemap apunte a tiles válidos con datos

### Problema 2: Log [PPU-LCD-ON] Se Dispara Demasiadas Veces

**Síntoma**: El log `[PPU-LCD-ON]` se dispara cientos de miles de veces (389,932 en pkmn, 542,984 en mario).

**Causa**: La lógica de detección tiene un bug. El flag `lcd_was_off` no se está manejando correctamente, causando que se dispare en cada frame cuando el LCD está encendido.

**Impacto**: Satura los logs y hace difícil analizar el comportamiento real.

**Solución propuesta**: 
- Corregir la lógica de detección para que solo se dispare cuando el LCD cambia de apagado a encendido (rising edge)
- Agregar un contador para limitar los logs a los primeros N frames

### Problema 3: Renderizado Blanco Aunque Tiles Existen (mario.gbc)

**Síntoma**: En mario.gbc, los tiles de prueba siguen intactos, pero el renderizado sigue siendo blanco.

**Causa posible**: 
- El tilemap no apunta a los tiles de prueba
- El tilemap está vacío (todo ceros)
- Hay un problema en el pipeline de renderizado (direccionamiento de tiles, paleta, etc.)

**Solución propuesta**: 
- Verificar el contenido del tilemap en mario.gbc
- Verificar que el direccionamiento de tiles (signed vs unsigned) sea correcto
- Verificar que la paleta BGP esté configurada correctamente

---

## Conclusiones

1. ✅ **Sistema de diagnóstico funciona**: Los logs capturan correctamente los cambios de LCDC, estado de VRAM, y renderizado.

2. ❌ **Problema de pantalla blanca persiste**: Todas las ROMs muestran framebuffer completamente blanco.

3. 🔍 **Causa raíz identificada**: 
   - En pkmn.gb y tetris.gb: Tiles de prueba sobrescritos por el juego
   - En mario.gbc: Tiles intactos pero tilemap posiblemente no apunta a ellos o hay otro problema

4. ⚠️ **Bugs identificados**:
   - Log [PPU-LCD-ON] se dispara demasiadas veces (necesita corrección)
   - La lógica de detección de activación del LCD tiene un bug

5. 📋 **Próximos pasos**:
   - Corregir el bug del log [PPU-LCD-ON]
   - Investigar por qué el tilemap no funciona correctamente
   - Verificar el direccionamiento de tiles (signed vs unsigned)
   - Verificar que el juego esté cargando sus propios tiles y tilemap correctamente

---

## Archivos de Log Generados

- `logs/test_pkmn_step0320.log` - 58,825,120 líneas
- `logs/test_tetris_step0320.log` - (tamaño no verificado)
- `logs/test_mario_step0320.log` - (tamaño no verificado)

**Nota**: Los archivos de log son muy grandes debido a la cantidad de logs generados. Se recomienda usar comandos como `grep`, `head`, `tail` para analizar sin saturar el contexto.

