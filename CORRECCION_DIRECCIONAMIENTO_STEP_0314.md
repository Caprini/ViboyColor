# Corrección de Direccionamiento de Tiles - Step 0314

## Problema Identificado

En Step 0313 se identificó que `load_test_tiles()` configuraba LCDC a 0x91, que corresponde a:
- Bit 7 = 1 (LCD Enable ✅)
- Bit 4 = 0 (Signed addressing → tile data base = 0x9000 ❌)
- Bit 0 = 1 (BG Display ✅)

Sin embargo, los tiles se cargaban en 0x8000-0x803F (tiles 0-3 en unsigned addressing). Esto causaba que la PPU buscara tiles en 0x9000+ pero los tiles estaban en 0x8000+, resultando en pantalla blanca.

## Solución Aplicada

Se corrigió LCDC a 0x99 = `10011001` en binario:
- Bit 7 = 1 (LCD Enable ✅)
- Bit 4 = 1 (Unsigned addressing → tile data base = 0x8000 ✅)
- Bit 0 = 1 (BG Display ✅)

**Cambio en código**: `src/core/cpp/MMU.cpp` línea ~1208
```cpp
memory_[0xFF40] = 0x99;  // LCD Enable (bit 7) + Unsigned addressing (bit 4) + BG Display (bit 0)
```

## Resultados Esperados

- Tiles visibles en pantalla (no pantalla blanca)
- Patrones reconocibles: checkerboard (Tile 1), líneas horizontales (Tile 2), líneas verticales (Tile 3)
- Log `[LOAD-TEST-TILES] LCDC configurado: ... -> 0x99` visible
- Log `[TILEMAP-INSPECT] BG Data Base: 8000` (no 9000)

## Estado Actual

- ✅ Corrección aplicada en código
- ✅ Módulo C++ recompilado
- ⏳ Verificación visual pendiente
- ⏳ Documentación pendiente de completar

## Notas Técnicas

### Direccionamiento de Tiles en Game Boy

- **Unsigned (bit 4 = 1)**: Tile data base = 0x8000, tile IDs 0-255
- **Signed (bit 4 = 0)**: Tile data base = 0x9000, tile IDs -128 a 127

Los tiles deben cargarse donde la PPU los busca según el modo de direccionamiento configurado en LCDC bit 4.

### LCDC 0x99

```
Bit 7 = 1  → LCD Enable
Bit 4 = 1  → Unsigned addressing (tile data base = 0x8000)
Bit 0 = 1  → BG Display
Otros bits: Tile Map 0x9800, Window Tile Map 0x9800
```

