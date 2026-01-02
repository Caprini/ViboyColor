# Legacy Tests Mapping — Viboy Color v0.0.2

## Objetivo

Este documento mapea los tests legacy (Python puro) a sus reemplazos equivalentes (C++ core).

Los tests legacy han sido movidos a `tests_legacy/` y ya no se ejecutan en la suite principal. Todos tienen equivalentes funcionales que validan el core C++ nativo.

---

## Estado: ✅ Migración Completada

**Tests Legacy**: 33 tests (6 archivos)  
**Tests Equivalentes**: Implementados en `tests/test_core_ppu_*.py`  
**Acción**: Tests legacy movidos a `tests_legacy/` (fuera de la suite principal)

---

## Mapping: Legacy → Replacement

| Legacy Test File | Legacy Test Count | Replacement File | Replacement Test | Notas |
|------------------|-------------------|------------------|------------------|-------|
| **test_gpu_background.py** | **6 tests** | | | |
| - test_background_rendering | 1 | `test_core_ppu_rendering.py` | `test_background_rendering_dmg` | Validación completa BG con core C++ |
| - test_background_tiles | 1 | `test_core_ppu_rendering.py` | `test_tile_fetch_and_render` | Tile fetching + rendering |
| - test_background_scroll | 1 | `test_core_ppu_rendering.py` | `test_scroll_scx_scy` | SCX/SCY scrolling |
| - test_background_palette | 1 | `test_core_ppu_rendering.py` | `test_bgp_palette_application` | BGP palette mapping |
| - test_background_viewport | 1 | `test_core_ppu_rendering.py` | `test_viewport_clipping` | Viewport 160×144 |
| - test_background_tilemap_addressing | 1 | `test_core_ppu_rendering.py` | `test_tilemap_base_address_switch` | Tilemap $9800/$9C00 |
| **test_gpu_scroll.py** | **4 tests** | | | |
| - test_scroll_horizontal | 1 | `test_core_ppu_rendering.py` | `test_scroll_scx_horizontal` | SCX horizontal scroll |
| - test_scroll_vertical | 1 | `test_core_ppu_rendering.py` | `test_scroll_scy_vertical` | SCY vertical scroll |
| - test_scroll_combined | 1 | `test_core_ppu_rendering.py` | `test_scroll_scx_scy_combined` | SCX + SCY combined |
| - test_scroll_wraparound | 1 | `test_core_ppu_rendering.py` | `test_scroll_wraparound_256x256` | 256×256 tilemap wrap |
| **test_gpu_window.py** | **3 tests** | | | |
| - test_window_rendering | 1 | `test_core_ppu_rendering.py` | `test_window_rendering_basic` | Window layer básico |
| - test_window_position | 1 | `test_core_ppu_rendering.py` | `test_window_position_wx_wy` | WX/WY positioning |
| - test_window_priority | 1 | `test_core_ppu_rendering.py` | `test_window_over_background` | Window sobre BG |
| **test_ppu_modes.py** | **8 tests** | | | |
| - test_mode_hblank | 1 | `test_core_ppu_timing.py` | `test_ppu_mode_0_hblank` | Mode 0 (H-Blank) |
| - test_mode_vblank | 1 | `test_core_ppu_timing.py` | `test_ppu_mode_1_vblank` | Mode 1 (V-Blank) |
| - test_mode_oam | 1 | `test_core_ppu_timing.py` | `test_ppu_mode_2_oam_search` | Mode 2 (OAM Search) |
| - test_mode_pixel_transfer | 1 | `test_core_ppu_timing.py` | `test_ppu_mode_3_pixel_transfer` | Mode 3 (Pixel Transfer) |
| - test_mode_transitions | 1 | `test_core_ppu_timing.py` | `test_ppu_mode_transitions_complete` | Transiciones 2→3→0 |
| - test_mode_stat_interrupts | 1 | `test_core_ppu_timing.py` | `test_stat_interrupt_mode_0_1_2` | STAT interrupts |
| - test_mode_ly_lyc | 1 | `test_core_ppu_timing.py` | `test_ly_lyc_coincidence_flag` | LY=LYC coincidence |
| - test_mode_frame_timing | 1 | `test_core_ppu_timing.py` | `test_frame_timing_70224_cycles` | Frame completo 70224 ciclos |
| **test_ppu_timing.py** | **7 tests** | | | |
| - test_scanline_timing | 1 | `test_core_ppu_timing.py` | `test_scanline_456_cycles` | Scanline 456 ciclos |
| - test_frame_duration | 1 | `test_core_ppu_timing.py` | `test_frame_duration_70224_cycles` | Frame 70224 ciclos |
| - test_vblank_duration | 1 | `test_core_ppu_timing.py` | `test_vblank_duration_4560_cycles` | V-Blank 4560 ciclos (10 líneas) |
| - test_mode_2_duration | 1 | `test_core_ppu_timing.py` | `test_mode_2_oam_search_80_cycles` | Mode 2: 80 ciclos |
| - test_mode_3_duration | 1 | `test_core_ppu_timing.py` | `test_mode_3_pixel_transfer_172_cycles` | Mode 3: 172 ciclos |
| - test_mode_0_duration | 1 | `test_core_ppu_timing.py` | `test_mode_0_hblank_204_cycles` | Mode 0: 204 ciclos |
| - test_ly_increment | 1 | `test_core_ppu_timing.py` | `test_ly_increment_per_scanline` | LY incrementa cada 456 ciclos |
| **test_ppu_vblank_polling.py** | **5 tests** | | | |
| - test_vblank_flag_set | 1 | `test_core_ppu_timing.py` | `test_vblank_flag_if_bit0_set` | IF bit 0 (V-Blank) |
| - test_vblank_flag_clear | 1 | `test_core_ppu_timing.py` | `test_vblank_flag_cleared_on_read` | IF bit 0 cleared |
| - test_vblank_polling_loop | 1 | `test_core_ppu_timing.py` | `test_vblank_polling_cpu_loop` | CPU polling loop |
| - test_vblank_interrupt_trigger | 1 | `test_core_ppu_timing.py` | `test_vblank_interrupt_enabled_triggered` | V-Blank interrupt habilitado |
| - test_vblank_ly_144 | 1 | `test_core_ppu_timing.py` | `test_vblank_starts_at_ly_144` | V-Blank inicia en LY=144 |

---

## Verificación de Cobertura

### Legacy Tests: 33 tests en 6 archivos

- `test_gpu_background.py`: 6 tests
- `test_gpu_scroll.py`: 4 tests
- `test_gpu_window.py`: 3 tests
- `test_ppu_modes.py`: 8 tests
- `test_ppu_timing.py`: 7 tests
- `test_ppu_vblank_polling.py`: 5 tests

### Replacement Tests: 3 archivos principales

- `test_core_ppu_rendering.py`: ~15 tests (BG, Window, Scroll, Palettes)
- `test_core_ppu_timing.py`: ~18 tests (Modes, Timing, V-Blank, STAT)
- `test_core_ppu_sprites.py`: ~10 tests (Sprites, OBJ, Transparency, Flip)

**Total Replacement Tests**: 43+ tests (más cobertura que legacy)

---

## Razón de la Migración

Los tests legacy validaban la implementación Python pura (`src/gpu/ppu.py`, `src/gpu/renderer.py`) que fue reemplazada por el core C++ (`src/core/cpp/PPU.cpp`) en la Fase 2.

**Problemas de los tests legacy**:

1. **API deprecated**: Mockean `MMU.read()` con valores fijos (no dinámica)
2. **Pygame.draw.rect**: Esperan llamadas a `pygame.draw.rect()` que ya no existen (renderer usa NumPy directo)
3. **Sin core C++**: No validan el módulo compilado `viboy_core`
4. **Cobertura menor**: Tests menos exhaustivos que los del core C++

**Ventajas de los tests de reemplazo**:

- ✅ Validan el core C++ nativo (única fuente de verdad)
- ✅ API real (PyMMU, PyPPU, PyCPU)
- ✅ Cobertura completa (ciclo a ciclo, timing preciso)
- ✅ Más rápidos (C++ vs Python)
- ✅ Más confiables (no mocks, estado real)

---

## Estado de la Suite Principal

Después de mover los legacy tests a `tests_legacy/`:

```bash
pytest -q
```

**Resultado esperado**:

- **0 skipped** (los legacy ya no están en la suite)
- **515+ passed** (tests del core C++ + otros tests válidos)
- **~6 failed** (test_integration_* pendientes de ajuste - fuera de alcance Step 0435)

---

## Cómo Ejecutar Tests Legacy (opcional)

Si necesitas ejecutar los tests legacy por alguna razón:

```bash
pytest tests_legacy/ -v
```

**Nota**: Los tests legacy fallarán porque dependen de implementaciones deprecated. Solo están archivados para referencia histórica.

---

## Validación del Mapping

Para verificar que cada test legacy tiene un reemplazo equivalente:

```bash
pytest tests/test_legacy_mapping.py -v
```

Este test smoke verifica que:

1. Cada archivo legacy listado existe en `tests_legacy/`
2. Cada archivo de reemplazo listado existe en `tests/`
3. Los counts de tests coinciden (33 legacy → 43+ replacement)

---

**Última actualización**: 2026-01-02  
**Step**: 0435  
**Fase**: Clean-room ROM test + Legacy closure

