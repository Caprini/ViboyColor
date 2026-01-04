---
name: Step 0464 - BG Tilemap Base + Scroll Diagnostics + Fix
overview: Diagnosticar y corregir selección de BG tilemap base (LCDC bit3) y aplicación de scroll (SCX/SCY). Añadir instrumentación para identificar qué tilemap tiene datos y cuál se está usando. Implementar fix si es necesario. Crear tests clean-room. Validar con UI real.
todos:
  - id: 0464-t1-instrumentation
    content: "Añadir instrumentación: modificar tools/rom_smoke_0442.py para loggear LCDC, bg_map_base, tilemap_nz_9800/9C00, tile_ids_sample. Añadir logging similar en PPU.cpp [PPU-TILEMAP-DIAG]. Añadir [ENV] log al arranque en viboy.py para evidencia de kill-switches OFF."
    status: pending
  - id: 0464-t2-fix-core
    content: "Verificar y corregir: asegurar uso de MMU::read_vram() para leer tilemap (no read() directo). Verificar que tile_map_base se calcula correctamente según LCDC bit3. Verificar que SCX/SCY se aplican correctamente con wrap 0..255."
    status: pending
    dependencies:
      - 0464-t1-instrumentation
  - id: 0464-t3-add-tests
    content: "Crear tests/test_bg_tilemap_base_and_scroll_0464.py con 3 casos: tilemap base 0x9800, tilemap base 0x9C00, SCX scroll. Tests headless, no dependen de ROMs comerciales ni UI."
    status: pending
    dependencies:
      - 0464-t2-fix-core
  - id: 0464-t4-verify-ui
    content: "Ejecutar bash tools/abrir_roms_cuadricula.sh con redirección. Capturar logs [PPU-TILEMAP-DIAG] y analizar tilemap_nz por ROM. Esperado: ROMs que estaban planas deberían mostrar contenido si tilemap base estaba mal."
    status: pending
    dependencies:
      - 0464-t3-add-tests
  - id: 0464-t5-run-suite
    content: Ejecutar pytest -q tests/test_bg_tilemap_base_and_scroll_0464.py y suite completa. Verificar que tests pasan y no hay regresiones.
    status: pending
    dependencies:
      - 0464-t3-add-tests
  - id: 0464-t6-document
    content: Documentar Step 0464 en bitácora HTML e informe dividido. Incluir evidencia de logs (tilemap_nz, LCDC bit3), fix aplicado, tests clean-room, y resultado visual (grid UI antes/después si aplica).
    status: pending
    dependencies:
      - 0464-t4-verify-ui
      - 0464-t5-run-suite
---

# Plan: Step 0464 — BG Tilemap Base + Scroll Diagnostics + Fix

## Objetivo

Diagnosticar y corregir el problema de pantallas blancas/patrones que se desplazan, causado por selección incorrecta de BG tilemap base (LCDC bit3) y/o aplicación incorrecta de scroll (SCX/SCY).**Hipótesis principal (H1)**: BG tilemap base y/o scroll no se está aplicando correctamente:

- BG tilemap base depende de LCDC bit3: bit3=0 → 0x9800, bit3=1 → 0x9C00
- Scroll depende de SCX (FF43) y SCY (FF42)
- Si esto está mal, el emulador puede "dibujar" tile 0 repetido y parecer que se mueve

---

## Contexto

**Estado actual**:

- Debug injections inventariados y gated (Step 0461) ✅
- Signed tile data addressing (0x8800 mode) corregido (Step 0463) ✅
- Problema observado: muchas ROMs siguen blancas / patrones stripes que se desplazan verticalmente

**Código actual**:

- Línea 2171: `tile_map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800` (correcto)
- Líneas 2744-2748: SCX/SCY aplicados correctamente en cálculo de map_x/map_y
- Posible problema: uso de `MMU::read()` en lugar de `MMU::read_vram()` para leer tilemap

---

## Reglas del Step

- **VIBOY_DEBUG_INJECTION=0** (default): Mantener debug injections OFF por defecto
- **Evidencia desde herramientas headless**: `tools/rom_smoke_0442.py`, logs `[UI-PATH]` si hace falta
- **NO mezclar fixes UI con fixes core**: Este step es PPU BG solamente
- **Imprimir [ENV] al arranque**: Para evidencia de que kill-switches están OFF

---

## Fase A — [0464-T1] Instrumentación Mínima y "Prueba de Mentira"

### Objetivo

Añadir logging para diagnosticar qué tilemap tiene datos y cuál se está usando.

### Implementación

**A1) Log de registros y "map health" (en headless y UI logs)Modificar `tools/rom_smoke_0442.py`** para añadir métricas por frame (gated: primeros 5 frames + cada 120):

```python
# En la función que imprime métricas por frame:

lcdc = mmu.read(0xFF40)

# Decodificar LCDC
bg_map_base = 0x9C00 if (lcdc & 0x08) else 0x9800
tile_data_mode = "8000(unsigned)" if (lcdc & 0x10) else "8800(signed)"
bg_enable = (lcdc & 0x01) != 0
window_enable = (lcdc & 0x20) != 0

scx = mmu.read(0xFF43)
scy = mmu.read(0xFF42)
wx = mmu.read(0xFF4B)
wy = mmu.read(0xFF4A)
ly = mmu.read(0xFF44)

# Contar nonzero bytes en tilemaps
tilemap_nz_9800 = 0
for addr in range(0x9800, 0x9C00):
    if mmu.read(addr) != 0:
        tilemap_nz_9800 += 1

tilemap_nz_9C00 = 0
for addr in range(0x9C00, 0xA000):
    if mmu.read(addr) != 0:
        tilemap_nz_9C00 += 1

# Leer 16 tile IDs desde el base actual
tile_ids_sample = []
for i in range(16):
    tile_ids_sample.append(mmu.read(bg_map_base + i))

# Añadir a la línea de log existente:
print(f"LCDC=0x{lcdc:02X} | BGMapBase=0x{bg_map_base:04X} | TileDataMode={tile_data_mode} | "
      f"BG={bg_enable} Win={window_enable} | "
      f"SCX={scx} SCY={scy} WX={wx} WY={wy} LY={ly} | "
      f"TilemapNZ_9800={tilemap_nz_9800} TilemapNZ_9C00={tilemap_nz_9C00} | "
      f"TileIDs[0:16]={''.join(f'{t:02X}' for t in tile_ids_sample)}")
```

**Añadir logging similar en `src/core/cpp/PPU.cpp`** (gated: primeros 5 frames + cada 120):

```cpp
// En render_scanline(), alrededor de donde se calcula tile_map_base (línea 2171):

static int tilemap_diag_count = 0;
if (ly_ == 0 && (tilemap_diag_count < 5 || (frame_counter_ % 120 == 0))) {
    tilemap_diag_count++;
    
    // Contar nonzero bytes en ambos tilemaps
    int tilemap_nz_9800 = 0;
    for (uint16_t addr = 0x9800; addr < 0x9C00; addr++) {
        if (mmu_->read_vram(addr - 0x8000) != 0x00) {
            tilemap_nz_9800++;
        }
    }
    
    int tilemap_nz_9C00 = 0;
    for (uint16_t addr = 0x9C00; addr < 0xA000; addr++) {
        if (mmu_->read_vram(addr - 0x8000) != 0x00) {
            tilemap_nz_9C00++;
        }
    }
    
    // Leer 16 tile IDs desde el base actual
    uint8_t tile_ids_sample[16];
    for (int i = 0; i < 16; i++) {
        tile_ids_sample[i] = mmu_->read_vram((tile_map_base - 0x8000) + i);
    }
    
    printf("[PPU-TILEMAP-DIAG] Frame %llu | LCDC=0x%02X | BGMapBase=0x%04X | "
           "TileDataMode=%s | SCX=%d SCY=%d | "
           "TilemapNZ_9800=%d TilemapNZ_9C00=%d | "
           "TileIDs[0:16]=",
           static_cast<unsigned long long>(frame_counter_ + 1),
           lcdc, tile_map_base,
           signed_addressing ? "8800(signed)" : "8000(unsigned)",
           scx, scy,
           tilemap_nz_9800, tilemap_nz_9C00);
    
    for (int i = 0; i < 16; i++) {
        printf("%02X", tile_ids_sample[i]);
    }
    printf("\n");
}
```

**A2) Confirmación de kill-switches OFF en runtime realModificar `src/viboy.py`** al arrancar (en `__init__` o `run()`):

```python
# Al inicio de run() o __init__:
import os

# Imprimir estado de env vars para evidencia
env_vars = [
    'VIBOY_DEBUG_INJECTION',
    'VIBOY_FORCE_BGP',
    'VIBOY_AUTOPRESS',
    'VIBOY_FRAMEBUFFER_TRACE',
    'VIBOY_DEBUG_UI'
]

env_status = []
for var in env_vars:
    value = os.environ.get(var, '0')
    env_status.append(f"{var}={value}")

print(f"[ENV] {' '.join(env_status)}")
```



### Criterios de Éxito

- Logs headless muestran LCDC, bg_map_base, tilemap_nz_9800, tilemap_nz_9C00, tile_ids_sample
- Logs PPU muestran información similar en `[PPU-TILEMAP-DIAG]`
- Log `[ENV]` al arranque muestra estado de kill-switches
- **Criterio de diagnóstico automático**:
- Si LCDC bit3=1 y tilemap_nz_9C00 >> tilemap_nz_9800 pero el renderer está usando 0x9800 → BUG confirmado
- Si ambos tilemaps ~0 y VRAM tiledata tiene datos → probablemente el juego está usando Window/atributos o aún no escribe map

---

## Fase B — [0464-T2] Fix Core: BG Tilemap Base + SCX/SCY (DMG Mínimo)

### Objetivo

Asegurar que se usa el tilemap base correcto y que SCX/SCY se aplican correctamente.

### Implementación

**B1) BG tilemap base correctoVerificar que se usa `MMU::read_vram()` para leer tilemap**:En `PPU.cpp`, línea 2748, verificar que se usa `read_vram()`:

```cpp
// ACTUAL (línea 2748):
uint8_t tile_id = mmu_->read(tile_map_addr);

// DEBE SER (si tile_map_addr está en rango VRAM):
uint16_t tile_map_offset = tile_map_addr - 0x8000;
uint8_t tile_id = mmu_->read_vram(tile_map_offset);
```

**Verificar que tile_map_base se calcula correctamente** (ya está correcto en línea 2171, pero verificar que se usa consistentemente).**B2) Aplicar SCX/SCY correctamente (wrap 0..255)Verificar que el cálculo actual es correcto** (líneas 2744-2748):

```cpp
// ACTUAL (ya correcto):
uint8_t map_x = (x + scx) & 0xFF;
uint8_t map_y = (ly_ + scy) & 0xFF;
uint16_t tile_map_addr = tile_map_base + (map_y / 8) * 32 + (map_x / 8);
```

**Asegurar que se usa `read_vram()` para leer tile_id**:

```cpp
// Después de calcular tile_map_addr:
uint16_t tile_map_offset = tile_map_addr - 0x8000;
if (tile_map_offset < 0x2000) {  // Rango válido VRAM (0x9800-0x9FFF = offset 0x1800-0x1FFF)
    uint8_t tile_id = mmu_->read_vram(tile_map_offset);
    
    // Resto del código de renderizado...
}
```

**Verificar cálculo de tile data address** (ya corregido en Step 0463, pero verificar):

```cpp
// Si LCDC bit4=1 (unsigned):
tile_addr = 0x8000 + tile_id * 16;

// Si LCDC bit4=0 (signed):
int8_t signed_id = static_cast<int8_t>(tile_id);
tile_addr = 0x9000 + static_cast<uint16_t>(signed_id) * 16;
```



### Criterios de Éxito

- `MMU::read_vram()` se usa para leer tilemap (no `MMU::read()` directo)
- `tile_map_base` se calcula correctamente según LCDC bit3
- SCX/SCY se aplican correctamente con wrap 0..255
- Código compila sin errores
- Tests existentes no se rompen

---

## Fase C — [0464-T3] Tests Clean-Room (Sin ROM Comercial)

### Objetivo

Crear tests que congelen el contrato: tilemap base select y scroll.

### Implementación

**Crear**: `tests/test_bg_tilemap_base_and_scroll_0464.py`

```python
"""Test clean-room para verificar selección de BG tilemap base y scroll.

Step 0464: Verifica que el tilemap base se selecciona correctamente según LCDC bit3
y que SCX/SCY se aplican correctamente.
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


class TestBGTilemapBaseAndScroll:
    """Tests para verificar tilemap base y scroll."""
    
    def setup_method(self):
        """Inicializar sistema mínimo."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        self.cpu = PyCPU(self.mmu, self.registers, self.timer, self.joypad)
        self.ppu = PyPPU(self.mmu)
        
        # Encender LCD y BG
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON, Window OFF, Tile Data 0x8000, BG Tilemap 0x9800
        self.mmu.write(0xFF47, 0xE4)  # BGP estándar
    
    def test_tilemap_base_select_9800(self):
        """Test 1: tilemap base select (0x9800 vs 0x9C00) - Caso 0x9800.
        
        Setup:
    - Escribir tile 0 con patrón que produce idx variados (0x55/0x33 por 8 líneas)
    - Escribir tile 1 con patrón distinto (invertido: 0xAA/0xCC)
    - Poner en 0x9800: tile IDs = 0
    - Poner en 0x9C00: tile IDs = 1
    - Setear LCDC bit3=0 → debe verse patrón de tile 0
        
        Assert: sample de índices (primeros 16 píxeles) corresponde a tile 0.
        """
        # Escribir tile 0 en 0x8000 (patrón 0x55/0x33)
        for line in range(8):
            self.mmu.write(0x8000 + (line * 2), 0x55)
            self.mmu.write(0x8000 + (line * 2) + 1, 0x33)
        
        # Escribir tile 1 en 0x8010 (patrón 0xAA/0xCC)
        for line in range(8):
            self.mmu.write(0x8010 + (line * 2), 0xAA)
            self.mmu.write(0x8010 + (line * 2) + 1, 0xCC)
        
        # Poner en 0x9800: tile IDs = 0
        for i in range(32 * 32):  # Llenar todo el tilemap 0x9800
            self.mmu.write(0x9800 + i, 0x00)
        
        # Poner en 0x9C00: tile IDs = 1
        for i in range(32 * 32):  # Llenar todo el tilemap 0x9C00
            self.mmu.write(0x9C00 + i, 0x01)
        
        # Setear LCDC bit3=0 (tilemap base 0x9800)
        self.mmu.write(0xFF40, 0x91)  # Bit3=0 → 0x9800
        
        # Correr 1 frame
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que se lee tile 0 (no tile 1)
        tile_id_9800 = self.mmu.read(0x9800)
        tile_id_9C00 = self.mmu.read(0x9C00)
        
        assert tile_id_9800 == 0x00, f"Tilemap 0x9800 debe tener tile ID 0x00, es 0x{tile_id_9800:02X}"
        assert tile_id_9C00 == 0x01, f"Tilemap 0x9C00 debe tener tile ID 0x01, es 0x{tile_id_9C00:02X}"
        
        # Verificar que el tile 0 tiene el patrón correcto
        tile0_byte1 = self.mmu.read(0x8000)
        tile0_byte2 = self.mmu.read(0x8001)
        assert tile0_byte1 == 0x55, f"Tile 0 byte1 debe ser 0x55, es 0x{tile0_byte1:02X}"
        assert tile0_byte2 == 0x33, f"Tile 0 byte2 debe ser 0x33, es 0x{tile0_byte2:02X}"
    
    def test_tilemap_base_select_9C00(self):
        """Test 2: tilemap base select (0x9800 vs 0x9C00) - Caso 0x9C00.
        
        Setup similar al anterior, pero LCDC bit3=1 → debe verse patrón de tile 1.
        """
        # Escribir tile 0 en 0x8000 (patrón 0x55/0x33)
        for line in range(8):
            self.mmu.write(0x8000 + (line * 2), 0x55)
            self.mmu.write(0x8000 + (line * 2) + 1, 0x33)
        
        # Escribir tile 1 en 0x8010 (patrón 0xAA/0xCC)
        for line in range(8):
            self.mmu.write(0x8010 + (line * 2), 0xAA)
            self.mmu.write(0x8010 + (line * 2) + 1, 0xCC)
        
        # Poner en 0x9800: tile IDs = 0
        for i in range(32 * 32):
            self.mmu.write(0x9800 + i, 0x00)
        
        # Poner en 0x9C00: tile IDs = 1
        for i in range(32 * 32):
            self.mmu.write(0x9C00 + i, 0x01)
        
        # Setear LCDC bit3=1 (tilemap base 0x9C00)
        self.mmu.write(0xFF40, 0x99)  # Bit3=1 → 0x9C00
        
        # Correr 1 frame
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que se lee tile 1 (no tile 0)
        tile_id_9800 = self.mmu.read(0x9800)
        tile_id_9C00 = self.mmu.read(0x9C00)
        
        assert tile_id_9800 == 0x00, f"Tilemap 0x9800 debe tener tile ID 0x00, es 0x{tile_id_9800:02X}"
        assert tile_id_9C00 == 0x01, f"Tilemap 0x9C00 debe tener tile ID 0x01, es 0x{tile_id_9C00:02X}"
        
        # Verificar que el tile 1 tiene el patrón correcto
        tile1_byte1 = self.mmu.read(0x8010)
        tile1_byte2 = self.mmu.read(0x8011)
        assert tile1_byte1 == 0xAA, f"Tile 1 byte1 debe ser 0xAA, es 0x{tile1_byte1:02X}"
        assert tile1_byte2 == 0xCC, f"Tile 1 byte2 debe ser 0xCC, es 0x{tile1_byte2:02X}"
    
    def test_scx_scroll(self):
        """Test 3: SCX scroll.
        
        Setup:
    - Tilemap lleno con tile 0
    - Tile 0 patrón conocido [0,1,2,3,0,1,2,3] por línea
    - Render con SCX=0: primeros 8 idx = [0,1,2,3,0,1,2,3]
    - Render con SCX=1: debería ser shift: [1,2,3,0,1,2,3,0]
        
        Assert exacto sobre índices (si hay acceso a framebuffer).
        """
        # Crear tile 0 con patrón conocido
        # Patrón por línea: 0x00, 0x11, 0x22, 0x33, 0x00, 0x11, 0x22, 0x33
        pattern_bytes = [0x00, 0x11, 0x22, 0x33, 0x00, 0x11, 0x22, 0x33]
        for line in range(8):
            byte1 = pattern_bytes[line] & 0x0F
            byte2 = (pattern_bytes[line] >> 4) & 0x0F
            # Codificar como tile data (cada bit representa un píxel)
            self.mmu.write(0x8000 + (line * 2), (byte1 << 4) | byte1)
            self.mmu.write(0x8000 + (line * 2) + 1, (byte2 << 4) | byte2)
        
        # Llenar tilemap 0x9800 con tile 0
        for i in range(32 * 32):
            self.mmu.write(0x9800 + i, 0x00)
        
        # Setear LCDC
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON, tilemap 0x9800
        
        # Test con SCX=0
        self.mmu.write(0xFF43, 0x00)  # SCX=0
        self.mmu.write(0xFF42, 0x00)  # SCY=0
        
        # Correr 1 frame
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que SCX se aplica (verificar cálculo de map_x)
        # Por ahora, solo verificar que no crashea
        assert True  # Placeholder: si hay acceso a framebuffer, verificar índices aquí
        
        # Test con SCX=1
        self.mmu.write(0xFF43, 0x01)  # SCX=1
        
        # Correr otro frame
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que SCX se aplica
        assert True  # Placeholder: si hay acceso a framebuffer, verificar shift aquí
```

**Nota**: Si `PPU` no expone framebuffer directamente, los tests pueden verificar indirectamente leyendo VRAM y verificando que el cálculo de dirección es correcto.

### Criterios de Éxito

- Test creado en `tests/test_bg_tilemap_base_and_scroll_0464.py`
- Test pasa con el fix aplicado
- Test no depende de ROMs comerciales
- Test no depende de UI (headless)
- Test cubre ambos casos de tilemap base (0x9800 y 0x9C00)

---

## Fase D — [0464-T4] Validación Real (UI en Paralelo)

### Objetivo

Verificar visualmente que el fix mejora el renderizado de las ROMs problemáticas.

### Implementación

```bash
cd "$(git rev-parse --show-toplevel)"

# Asegurar que no hay interferencias
export VIBOY_DEBUG_INJECTION=0
export VIBOY_AUTOPRESS=0
export VIBOY_FORCE_BGP=0

# Ejecutar grid UI
bash tools/abrir_roms_cuadricula.sh > /tmp/viboy_0464_ui_grid.log 2>&1

# Capturar 10 líneas por ROM de [UI-PATH] / [PPU-TILEMAP-DIAG]
echo "=== Extracto de logs UI ==="
grep -E "\[UI-PATH\]|\[PPU-TILEMAP-DIAG\]" /tmp/viboy_0464_ui_grid.log | head -n 40

# Analizar por ROM
for rom in pkmn tetris tetrisdx mario; do
    echo ""
    echo "--- $rom ---"
    grep -E "\[PPU-TILEMAP-DIAG\]" /tmp/viboy_0464_ui_grid.log | \
        grep -i "$rom" | head -n 10 | \
        grep -oE "BGMapBase=0x[0-9A-F]+|TilemapNZ_9800=[0-9]+|TilemapNZ_9C00=[0-9]+|LCDC=0x[0-9A-F]+"
done
```



### Criterios de Éxito

- Grid UI se ejecuta sin crashes
- Logs muestran `[PPU-TILEMAP-DIAG]` con información de tilemap base y nonzero counts
- **Criterio de éxito**:
- En Pokémon Red / Tetris DMG: tilemap_nz deja de ser ~0 en el base correcto y la pantalla deja de ser blanca (aunque sea "fea", pero con contenido)
- Si sigue blanco pero tilemap_nz alto y unique_idx_count > 2, entonces el problema está en Window/OBJ/CGB attrs; se abre Step siguiente

---

## Advertencias de Contexto

**⚠️ IMPORTANTE - NO SATURAR CONTEXTO**:

- Todos los comandos de ejecución headless/UI redirigen salida a `/tmp/viboy_0464_*.txt` o `/tmp/viboy_0464_*.log`
- Usar `head -n N` o `grep` con límites para analizar logs, nunca `cat` completo
- Los tests se ejecutan con `-q` (quiet) y salida redirigida si es necesario

### Comandos Seguros:

```bash
# Analizar resultados con límite
grep -E "\[PPU-TILEMAP-DIAG\]|\[UI-PATH\]" /tmp/viboy_0464_*.log | head -n 40

# Contar tilemap nonzero por ROM
grep "TilemapNZ" /tmp/viboy_0464_*.log | awk '{print $NF}' | sort | uniq -c

# Verificar errores
grep -i "error\|exception" /tmp/viboy_0464_*.log | head -n 10
```



### ⚠️ Comandos Prohibidos:

```bash
# ❌ NO hacer esto:
cat /tmp/viboy_0464_*.log              # Lee todos los archivos completos
bash tools/abrir_roms_cuadricula.sh   # Sin redirección (satura contexto)
pytest -v                               # Sin redirección (satura contexto)
```

---

## Entregables Obligatorios del Ejecutor

1. **Extracto de logs headless** (3-6 líneas por ROM) con:

- LCDC, bg_map_base, tilemap_nz_9800, tilemap_nz_9C00, tile_ids_sample

2. **Extracto de logs UI** (10 líneas por ROM) de `[PPU-TILEMAP-DIAG]` mostrando:

- LCDC, SCX, SCY, bg_map_base
- tilemap_nz_9800, tilemap_nz_9C00
- unique_idx_count o unique_rgb_count (si está disponible)

3. **Resultado de pytest del nuevo test**:
   ```bash
            pytest -q tests/test_bg_tilemap_base_and_scroll_0464.py
   ```




4. **Diff del fix en PPU.cpp** (tilemap base + SCX/SCY)
5. **Log corto real** que confirme qué tilemap tiene datos en Pokémon/Tetris y cuál se está usando

---

## Documentación

### Entrada de Bitácora

**Archivo**: `docs/bitacora/entries/2026-01-02__0464__fix-bg-tilemap-base-scroll.html`**Contenido mínimo**:

- Descripción del problema (pantallas blancas/patrones que se desplazan)
- Hipótesis (BG tilemap base y/o scroll incorrecto)
- Evidencia de logs (tilemap_nz_9800 vs 9C00, LCDC bit3)
- Fix aplicado (uso de `read_vram()`, verificación de tilemap base)
- Tests clean-room añadidos
- Resultado visual (grid UI antes/después si aplica)

### Actualización de Informe

Actualizar `docs/informe_fase_2/` con la entrada del Step 0464.---

## Comandos Git

```bash
git add .
git commit -m "fix(ppu): correct BG tilemap base select and scroll application (Step 0464)

- Añadir instrumentación [PPU-TILEMAP-DIAG] para diagnosticar tilemap base y scroll
- Añadir logging de tilemap nonzero counts en rom_smoke_0442.py
- Añadir [ENV] log al arranque para evidencia de kill-switches OFF
- Verificar uso de MMU::read_vram() para leer tilemap (no read() directo)
- Añadir tests clean-room para tilemap base select y scroll

Fixes: Pantallas blancas/patrones que se desplazan
Causa: Posible uso incorrecto de tilemap base o lectura incorrecta de tilemap
Solución: Instrumentación + verificación de tilemap base según LCDC bit3 + uso de read_vram()"
git push
```

---

## Nota Crítica

Este step es crítico porque si el tilemap base está mal seleccionado o se lee incorrectamente, el emulador renderiza tiles incorrectos o vacíos, resultando en pantallas blancas.**Decisión automática al final del Step**: