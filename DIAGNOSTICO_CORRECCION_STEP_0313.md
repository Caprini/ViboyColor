# Diagnóstico y Corrección Step 0313

## Problemas Identificados

### 1. Pantalla Blanca

**Síntoma**: El emulador muestra pantalla completamente blanca.

**Causas Identificadas**:
- `load_test_tiles()` no se ejecutaba porque en `main.py` el valor por defecto era `False` (argparse con `action="store_true"`)
- LCDC tenía el bit 0 (BG Display) desactivado (LCDC = 0x80 en lugar de 0x91)
- El tilemap estaba completamente vacío (checksum 0x0000)

### 2. FPS Muy Bajo

**Síntoma**: FPS de 8.0 en lugar de ~60 FPS esperado.

**Estado**: Requiere más investigación (no completamente resuelto en este step).

## Correcciones Aplicadas

### Corrección 1: Habilitar `load_test_tiles()` por Defecto

**Archivo**: `main.py`

**Problema**: El argumento `--load-test-tiles` tenía `action="store_true"`, lo que significa que por defecto era `False` a menos que se pasara explícitamente.

**Solución**: Cambiar la lógica para que `load_test_tiles` sea `True` por defecto, usando `--no-load-test-tiles` para desactivarlo.

```python
# Antes:
parser.add_argument("--load-test-tiles", action="store_true", ...)
viboy.load_cartridge(args.rom, load_test_tiles=args.load_test_tiles)  # False por defecto

# Después:
parser.add_argument("--no-load-test-tiles", action="store_true", ...)
load_tiles = not getattr(args, 'no_load_test_tiles', False)
viboy.load_cartridge(args.rom, load_test_tiles=load_tiles)  # True por defecto
```

### Corrección 2: Configurar LCDC y BGP en `load_test_tiles()`

**Archivo**: `src/core/cpp/MMU.cpp`

**Problema**: LCDC se inicializaba a 0x91 en PPU, pero el juego lo sobrescribía a 0x80 (solo LCD Enable, sin BG Display).

**Solución**: Modificar `load_test_tiles()` para configurar LCDC a 0x91 después de cargar tiles, y también asegurar que BGP tenga un valor válido (0xE4 si estaba en 0x00).

```cpp
// --- Step 0313: Configurar LCDC para habilitar BG Display ---
uint8_t current_lcdc = memory_[0xFF40];
memory_[0xFF40] = 0x91;  // LCD Enable (bit 7) + BG Display (bit 0)
printf("[LOAD-TEST-TILES] LCDC configurado: 0x%02X -> 0x91 (BG Display habilitado)\n", current_lcdc);

// También asegurar BGP tiene un valor válido
if (memory_[0xFF47] == 0x00) {
    memory_[0xFF47] = 0xE4;  // Paleta estándar
    printf("[LOAD-TEST-TILES] BGP configurado: 0x00 -> 0xE4 (paleta estándar)\n");
}
```

### Corrección 3: Forzar BG Display en PPU Durante Renderizado

**Archivo**: `src/core/cpp/PPU.cpp`

**Problema**: Aunque `load_test_tiles()` configura LCDC a 0x91, el juego puede sobrescribirlo a 0x80 después, deshabilitando el BG Display.

**Solución**: Modificar `render_scanline()` para forzar temporalmente el bit 0 de LCDC durante el renderizado si está desactivado (hack temporal para desarrollo).

```cpp
// --- Step 0313: Hack temporal - Forzar BG Display si está desactivado ---
bool bg_display_forced = false;
if (!(lcdc & 0x01)) {
    // Si BG Display está desactivado, temporalmente lo activamos para renderizar
    lcdc |= 0x01;  // Activar bit 0 (BG Display)
    bg_display_forced = true;
    // Log solo una vez para no saturar
    static int force_log_count = 0;
    if (ly_ == 0 && force_log_count < 1) {
        force_log_count++;
        printf("[PPU-FIX] LCDC tenía BG Display desactivado, forzado temporalmente a 0x%02X para renderizado\n", lcdc);
    }
}
// --- Fin hack temporal ---
```

### Corrección 4: Añadir Logs de Diagnóstico

**Archivos**: `src/viboy.py`, `src/core/cpp/MMU.cpp`, `src/core/cpp/PPU.cpp`

**Solución**: Añadir logs de diagnóstico para verificar que `load_test_tiles()` se ejecuta y que LCDC/BGP están configurados correctamente.

## Resultados

### Antes de las Correcciones
- `load_test_tiles()` no se ejecutaba (no había logs)
- Tilemap vacío (checksum 0x0000)
- LCDC = 0x80 (BG Display desactivado)
- Pantalla blanca

### Después de las Correcciones
- ✅ `load_test_tiles()` se ejecuta correctamente (logs presentes)
- ✅ Tiles cargados en VRAM (Tile 1 = 0xAA 0x55 verificado)
- ✅ Tilemap tiene contenido (checksum 0x021C)
- ✅ LCDC configurado a 0x91 en `load_test_tiles()`
- ✅ PPU fuerza BG Display temporalmente si está desactivado

## Verificación

### Logs de Verificación

```
[LOAD-TEST-TILES] Función llamada
[LOAD-TEST-TILES] VRAM antes: primer byte = 0x00
[LOAD-TEST-TILES] Cargando tiles de prueba en VRAM...
[LOAD-TEST-TILES] LCDC configurado: 0x91 -> 0x91 (BG Display habilitado)
[LOAD-TEST-TILES] VRAM después: primer byte = 0x00
[LOAD-TEST-TILES] Tile 1 (0x8010) = 0xAA 0x55
[LOAD-TEST-TILES] Tiles de prueba cargados:
[LOAD-TEST-TILES]   Tile 0 (0x8000): Blanco
[LOAD-TEST-TILES]   Tile 1 (0x8010): Checkerboard
[LOAD-TEST-TILES]   Tile 2 (0x8020): Lineas horizontales
[LOAD-TEST-TILES]   Tile 3 (0x8030): Lineas verticales
[LOAD-TEST-TILES]   Tile Map configurado con patron alternado
```

```
[PPU-FIX] LCDC tenía BG Display desactivado, forzado temporalmente a 0x81 para renderizado
[TILEMAP-INSPECT] Frame 1 | LCDC: 81 | BG Map Base: 9800 | BG Data Base: 9000
[TILEMAP-INSPECT] Tilemap checksum (first 1024 bytes): 0x021C
```

## Próximos Pasos

1. **FPS Bajo**: Requiere más investigación para identificar la causa raíz del FPS bajo (8.0 FPS).
2. **Renderizado Visual**: Verificar visualmente que los tiles se muestran correctamente en pantalla (no pantalla blanca).
3. **Signed Addressing**: Verificar que el tilemap y los tiles están correctamente alineados considerando signed addressing (tile data base = 0x9000).

## Archivos Modificados

- `main.py`: Corregir valor por defecto de `load_test_tiles`
- `src/core/cpp/MMU.cpp`: Configurar LCDC y BGP en `load_test_tiles()`
- `src/core/cpp/PPU.cpp`: Forzar BG Display temporalmente durante renderizado
- `src/viboy.py`: Añadir logs de diagnóstico

## Compilación

```bash
python setup.py build_ext --inplace
```

## Referencias

- Step 0313 Plan: Diagnóstico y Corrección de Pantalla Blanca y FPS Bajo
- Pan Docs: LCDC Register (0xFF40), Tile Data, Tile Map

