# STEP 0431 - TRIAGE REPORT
## PPU/GPU 10 Fails → 2 Clusters Aislados

---

## HEAD (Estado actual)
```
Commit: 7ad3821f3442cac742a92a68935567d744159206
Fecha: 2026-01-02
Branch: develop-v0.0.2
```

---

## RESUMEN EJECUTIVO

**Total de fallos**: 10 tests
- **Cluster A (C++ PPU Sprites)**: 3 tests
- **Cluster B (GPU Python Background/Scroll)**: 7 tests

**Naturaleza de los fallos**:
- Cluster A: Sprites **NO se renderizan** en el framebuffer del core C++
- Cluster B: Tests están **mal diseñados** (intentan mockear atributos read-only de MMU C++)

---

## CLUSTER A: C++ PPU SPRITES (3 TESTS)

### A1: `test_sprite_rendering_simple` ❌
**Exit code**: 1

**Assertion**:
```python
assert sprite_found, "El sprite debe estar renderizado en la línea 4"
```

**Evidencia del log**:
- PPU escribe a framebuffer: `[PPU-FRAMEBUFFER-WRITE] Frame 1 | LY: 0 | Non-zero pixels written: 80/160`
- Framebuffer después del swap: `[PPU-FRAMEBUFFER-AFTER-SWAP] Frame 1 | Total non-zero pixels in front: 320/23040`
- **PERO**: El test espera encontrar sprites en LY=4, y el log muestra que solo se renderizan 4 líneas (LY 0-3)
- **SOSPECHA**: El test avanza hasta LY=4 pero **no completa el frame**, así que `swap_buffers()` no se ejecuta y el framebuffer front sigue vacío o sin sprites.

**Causa probable**: El sprite SÍ se renderiza en el back buffer, pero el test **no llama a `swap_buffers()`** antes de leer el framebuffer.

---

### A2: `test_sprite_x_flip` ❌
**Exit code**: 1

**Assertion**:
```python
assert 4294967295 == 4278190080
# 0xFFFFFFFF (blanco) == 0xFF000000 (negro) → FAIL
```

**Evidencia del log**:
- Similar al A1: framebuffer tiene datos (`320 non-zero pixels`)
- Test espera píxel negro con flip, pero obtiene blanco (0xFFFFFFFF)

**Causa probable**: El X-Flip **no está implementado** en `render_sprites()` de `PPU.cpp`, o la lógica de flip está invertida.

---

### A3: `test_sprite_palette_selection` ❌
**Exit code**: 1

**Assertion**:
```python
assert 4294967295 == 4289374890
# 0xFFFFFFFF (blanco) == 0xFFAAAAAAA (gris claro) → FAIL
```

**Evidencia del log**:
- VRAM tiene 1 tile completo: `Complete tiles: 1/384 (0.26%)`
- Test espera color 3 mapeado a gris claro según OBP1, pero obtiene blanco

**Causa probable**: La **paleta OBP1 no se aplica correctamente** en `render_sprites()`, o el sprite siempre usa OBP0.

---

## CLUSTER B: GPU PYTHON BACKGROUND/SCROLL (7 TESTS)

### B1: `test_lcdc_control_tile_map_area` ❌
**Exit code**: 1

**Error**:
```python
AttributeError: 'MMU' object attribute 'read_byte' is read-only
```

**Línea del fallo**:
```python
mmu.read_byte = tracked_read  # ❌ MMU en C++ tiene métodos read-only
```

**Causa**: El test intenta **mockear `mmu.read_byte`** (método Cython), pero los métodos de extensiones C++ **no son modificables** en runtime.

**Archivos afectados**: `tests/test_gpu_background.py` (línea 60), `tests/test_gpu_scroll.py`

---

### B2: `test_scroll_x` ❌
**Exit code**: 1

**Assertion**:
```python
assert mock_draw_rect.called, "Debe llamar a pygame.draw.rect para dibujar píxeles"
```

**Evidencia del log**:
- Renderer ejecuta `render_frame()` correctamente
- Buffer tiene píxeles: `[(8, 24, 32), ..., (255, 255, 255), ...]`
- **PERO**: `pygame.draw.rect` NO se llama porque el test mockea el método pero el renderer usa **renderizado vectorizado con NumPy** cuando está disponible.

**Causa**: El test asume que renderer usa `pygame.draw.rect`, pero el código real usa **blit de surface preallocada** (optimización NumPy).

---

### Resto de tests del Cluster B (5 más)
Todos tienen el mismo patrón:
- Intentan mockear `mmu.read_byte` (read-only)
- O esperan llamadas a `pygame.draw.rect` que no ocurren por optimizaciones

---

## TABLA: TESTS → MÓDULO REAL

| Test | Módulo que debería renderizar | Módulo actual | Comentario |
|------|-------------------------------|---------------|------------|
| `test_sprite_rendering_simple` | `PPU.cpp::render_sprites()` | `PPU.cpp` | ✅ Correcto, pero sin swap |
| `test_sprite_x_flip` | `PPU.cpp::render_sprites()` | `PPU.cpp` | ✅ Correcto, flip no implementado |
| `test_sprite_palette_selection` | `PPU.cpp::render_sprites()` | `PPU.cpp` | ✅ Correcto, OBP1 no aplicado |
| `test_lcdc_control_tile_map_area` | `renderer.py::render_frame()` | `renderer.py` (Python GPU) | ❌ Test mal diseñado (mock read-only) |
| `test_scroll_x` | `renderer.py::render_frame()` | `renderer.py` (Python GPU) | ❌ Test mal diseñado (mock pygame) |
| Resto `test_gpu_*` | `renderer.py` | `renderer.py` | ❌ Mismo problema |

---

## DECISIÓN PROPUESTA

**ELEGIR OPCIÓN 1**: Priorizar **C++ PPU como "verdad" futura**

### Justificación:
1. El core C++ (`PPU.cpp`) ya renderiza background, window y sprites al framebuffer.
2. `renderer.py` (GPU Python) es legacy/adaptador para Pygame y tests antiguos.
3. Mantener 2 motores de renderizado (C++ y Python) duplica reglas LCDC/scroll/paletas.
4. Los tests `test_gpu_*` están **desactualizados** (intentan mockear MMU C++ que es read-only).

### Consecuencias:
- **Cluster A**: Fix en `PPU.cpp` (sprites, flip, paletas) → 3 tests pasan.
- **Cluster B**: Reescribir tests `test_gpu_*` para consumir framebuffer del core C++ (o marcar como legacy/skip).

---

## PLAN RESULTANTE

### Step 0432: Fix C++ PPU Sprites (Cluster A)
**Archivos**:
- `src/core/cpp/PPU.cpp::render_sprites()`
- `src/core/wrappers/ppu_wrapper.pyx` (si hace falta exponer `swap_buffers()`)
- `tests/test_core_ppu_sprites.py` (añadir llamada a swap antes de leer framebuffer)

**Tareas**:
1. Verificar que `render_sprites()` se ejecuta correctamente en `render_scanline()`
2. Implementar X-Flip/Y-Flip en el bucle de píxeles del sprite
3. Aplicar paleta OBP0/OBP1 según atributo del sprite (bit 4)
4. Asegurar que tests llaman `ppu.swap_buffers()` antes de leer framebuffer

**Entregable**: 3/3 tests de sprites pasan.

---

### Step 0433: Migrar tests GPU Python → Framebuffer C++ (Cluster B)
**Archivos**:
- `tests/test_gpu_background.py`
- `tests/test_gpu_scroll.py`
- `src/gpu/renderer.py` (marcar como legacy si no se usa más)

**Opción A (Reescribir tests)**:
- Cambiar tests para usar `PyMMU + PyPPU` (core C++)
- Leer framebuffer del core directamente (sin mockear `read_byte`)
- Verificar píxeles esperados según LCDC/SCX/SCY

**Opción B (Marcar legacy/skip)**:
- Documentar que `test_gpu_*` son legacy de v0.0.1 (Python puro)
- Skip con mensaje: "Tests legacy - usar test_core_ppu_* para validar C++"
- Mantener `renderer.py` solo para Pygame UI, NO para lógica de renderizado

**Recomendación**: **Opción B** (marcar legacy), para no duplicar cobertura.

**Entregable**: 7 tests marcados como legacy con justificación documentada, o reescritos para consumir core C++.

---

## EVIDENCIA TÉCNICA (FRAGMENTOS CLAVE)

### Fragmento 1: `PPU.cpp::render_sprites()` (línea 4165)
```cpp
void PPU::render_sprites() {
    // ...
    uint8_t sprite_height = ((lcdc & 0x04) != 0) ? 16 : 8;
    
    for (uint8_t sprite_index = 0; sprite_index < MAX_SPRITES; sprite_index++) {
        // Leer atributos del sprite
        uint8_t sprite_y = mmu_->read(sprite_addr + 0);
        uint8_t sprite_x = mmu_->read(sprite_addr + 1);
        uint8_t tile_id = mmu_->read(sprite_addr + 2);
        uint8_t attributes = mmu_->read(sprite_addr + 3);
        
        // ⚠️ FALTA: Extraer X-Flip (bit 5), Y-Flip (bit 6), Paleta (bit 4)
        // ⚠️ FALTA: Aplicar flip en el bucle de píxeles
        // ⚠️ FALTA: Usar OBP0 o OBP1 según (attributes & 0x10)
    }
}
```

### Fragmento 2: `test_gpu_background.py` (línea 60)
```python
mmu.read_byte = tracked_read  # ❌ MMU C++ no permite reasignar métodos
```

**Solución**: Usar `unittest.mock.patch.object(mmu, 'read_byte', side_effect=tracked_read)` o reescribir sin mocks.

---

## CONCLUSIÓN

**10 tests divididos en 2 problemas distintos**:
1. **Cluster A (3 tests)**: Funcionalidad sprite incompleta en C++ → Fix técnico en `PPU.cpp`.
2. **Cluster B (7 tests)**: Tests legacy de Python GPU incompatibles con core C++ → Reescribir o deprecar.

**Decisión final**: Priorizar C++ PPU como verdad (Opción 1).

**Próximos Steps**: 0432 (fix sprites C++) → 0433 (migrar/deprecar tests GPU Python).

---

**Fecha del reporte**: 2026-01-02  
**Ejecutor**: Cursor Agent  
**Plan ID**: step_0431_-_triage_ppu_vs_gpu_(10_fails)_+_split_0082c421.plan.md

