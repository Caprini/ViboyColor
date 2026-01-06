# Reporte Step 0491: DMG Tiledata Cero + CGB Present Blanco

**Fecha**: 2025-12-29  
**Step ID**: 0491  
**Estado**: ✅ Completado (Parcial - Fix aplicado, problema persistente)

---

## Resumen Ejecutivo

Este reporte documenta el diagnóstico y fix aplicado para dos problemas críticos:
1. **DMG Mode (tetris.gb)**: Pantalla en blanco - tiledata completamente vacío
2. **CGB Mode (tetris_dx.gbc)**: Ventana blanca - FB_RGB tiene señal pero FB_PRESENT está blanco

### Hallazgos Clave

- ✅ **Fix de Estado Post-Boot DMG**: Implementado `init_post_boot_dmg_state()` que establece el estado correcto según Pan Docs
- ✅ **Progreso**: El juego ahora intenta escribir a tiledata (6144 intentos en frame 180)
- ⚠️ **Problema Persistente**: Todos los writes a tiledata son cero (`TiledataNonZeroB0=0`)

---

## Métricas Comparativas

### tetris.gb (DMG Mode) - Frame 180

| Métrica | Antes del Fix | Después del Fix | Cambio |
|---------|---------------|-----------------|--------|
| **TiledataAttemptsB0** | 0 | 6144 | ✅ +6144 |
| **TiledataNonZeroB0** | 0 | 0 | ⚠️ Sin cambio |
| **TilemapAttemptsB0** | 0 | 3072 | ✅ +3072 |
| **TilemapNonZeroB0** | 0 | 1024 | ✅ +1024 |
| **DMGTileFetchStats.TileBytesTotal** | 517880 | 517880 | Sin cambio |
| **DMGTileFetchStats.TileBytesNonZero** | 0 | 0 | ⚠️ Sin cambio |
| **PresentCRC32** | 0x00000000 | 0x00000000 | ⚠️ Sin cambio |
| **PresentNonWhite** | 0 | 0 | ⚠️ Sin cambio |
| **RgbCRC32** | 0x70866000 | 0x70866000 | Sin cambio |
| **RgbNonWhite** | 0 | 0 | ⚠️ Sin cambio |
| **VRAM_Regions_TiledataNZ** | 0 | 0 | ⚠️ Sin cambio |
| **VRAM_Regions_TilemapNZ** | 1024 | 1024 | Sin cambio |

### Análisis de Resultados

1. **Progreso Significativo**: El fix de estado post-boot permitió que el juego intente escribir a tiledata y tilemap
2. **Problema Raíz Identificado**: Todos los writes a tiledata son cero, lo que sugiere que el juego está en un estado de inicialización donde aún no ha descomprimido los datos gráficos
3. **Tilemap Funciona**: El tilemap tiene datos (1024 bytes non-zero), pero tiledata está completamente vacío

---

## Implementación del Fix

### Fase C: Fix Mínimo DMG - Caso 2

**Problema**: Writes a tiledata son todos cero  
**Causa Raíz**: Estado post-boot incorrecto cuando `VIBOY_SIM_BOOT_LOGO=0`  
**Solución**: Implementar `init_post_boot_dmg_state()` que establece el estado correcto según Pan Docs

#### Archivos Modificados

1. **`src/core/cpp/MMU.hpp`**:
   - Añadido método `init_post_boot_dmg_state()`
   - Marcado `vram_write_stats_` como `mutable` para permitir actualización desde métodos const

2. **`src/core/cpp/MMU.cpp`**:
   - Implementado `init_post_boot_dmg_state()` con valores según Pan Docs:
     - LCDC: 0x00 (LCD OFF)
     - STAT: 0x00
     - SCY, SCX: 0x00
     - BGP: 0xFC
     - OBP0, OBP1: 0x00
     - IF: 0xE1
     - IE: 0x00
   - Modificado `initialize_io_registers()` para llamar a `init_post_boot_dmg_state()` cuando es DMG y `VIBOY_SIM_BOOT_LOGO=0`

#### Código Clave

```cpp
void MMU::init_post_boot_dmg_state() {
    // Estado conocido después del boot ROM DMG
    // Fuente: Pan Docs - Power Up Sequence
    
    memory_[0xFF40] = 0x00;  // LCDC: LCD OFF
    memory_[0xFF41] = 0x00;  // STAT
    memory_[0xFF42] = 0x00;  // SCY
    memory_[0xFF43] = 0x00;  // SCX
    memory_[0xFF47] = 0xFC;  // BGP
    memory_[0xFF48] = 0x00;  // OBP0
    memory_[0xFF49] = 0x00;  // OBP1
    memory_[0xFF0F] = 0xE1;  // IF
    memory_[0xFFFF] = 0x00;  // IE
    // ... otros registros ...
}
```

---

## Conceptos de Hardware

### Estado Post-Boot DMG

Según Pan Docs - Power Up Sequence, después de que la Boot ROM termina, el hardware queda en un estado conocido:

- **LCDC (0xFF40)**: LCD OFF (0x00) inicialmente. El juego debe activarlo manualmente.
- **STAT (0xFF41)**: 0x00 por defecto
- **BGP (0xFF47)**: 0xFC (shades 3,2,1,0) - paleta estándar DMG
- **IF (0xFF0F)**: 0xE1 (VBlank, Timer, Serial flags set)
- **IE (0xFFFF)**: 0x00 (sin interrupciones habilitadas inicialmente)

**Problema Identificado**: Nuestro emulador estaba inicializando LCDC=0x91 (LCD ON) cuando `VIBOY_SIM_BOOT_LOGO=0`, lo que puede haber causado que el juego no ejecutara correctamente su rutina de inicialización.

---

## Próximos Pasos

1. **Investigar Descompresión**: El problema de writes cero sugiere que el juego está en un estado de inicialización donde aún no ha descomprimido los datos gráficos. Investigar:
   - ¿El juego está esperando alguna condición antes de descomprimir?
   - ¿Hay algún problema con el estado de los registros que impide la descompresión?
   - ¿El juego está en un bucle de espera?

2. **CGB Mode (tetris_dx.gbc)**: Ejecutar `rom_smoke` para CGB y analizar `FB_PRESENT_SRC` para entender por qué está blanco a pesar de que `FB_RGB` tiene señal.

3. **Análisis de VRAM**: Verificar el contenido real de VRAM después de los writes para confirmar si los datos están siendo escritos pero no se están leyendo correctamente.

---

## Archivos Generados/Modificados

- `src/core/cpp/MMU.hpp` - Añadido método `init_post_boot_dmg_state()`
- `src/core/cpp/MMU.cpp` - Implementado `init_post_boot_dmg_state()` y modificado `initialize_io_registers()`
- `docs/reports/reporte_step0491.md` - Este reporte

---

## Comandos de Ejecución

```bash
# Compilación
python3 setup.py build_ext --inplace

# Ejecución con fix
export PYTHONPATH=/media/fabini/8CD1-4C30/ViboyColor:$PYTHONPATH
export VIBOY_SIM_BOOT_LOGO=0
export VIBOY_DEBUG_DMG_TILE_FETCH=1
export VIBOY_DEBUG_VRAM_WRITES=1
export VIBOY_DEBUG_PRESENT_TRACE=1
export VIBOY_DUMP_RGB_FRAME=180
export VIBOY_DUMP_RGB_PATH=/tmp/viboy_tetris_gb_rgb_f####.ppm
python3 tools/rom_smoke_0442.py roms/tetris.gb --frames 240 > /tmp/viboy_0491_tetris_fix.log 2>&1
```

---

## Referencias

- Pan Docs - Power Up Sequence
- Pan Docs - LCDC Register (0xFF40)
- Pan Docs - VRAM Banking (CGB)
- Step 0490: VRAMWriteStats Expansion
- Step 0489: FB_PRESENT_SRC Capture

---

**Fin del Reporte**

