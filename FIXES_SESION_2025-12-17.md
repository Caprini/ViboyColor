# Fixes y Mejoras - Sesión 2025-12-17

Este documento registra todos los fixes, mejoras y cambios realizados durante esta sesión de desarrollo.
Posteriormente, estos cambios se documentarán correctamente en las bitácoras correspondientes.

---

## Fix 001: Forzar Renderizado con LCDC=0x80 e Implementar Scroll (SCX/SCY)

**Fecha**: 2025-12-17  
**Step ID**: 0033  
**Estado**: ✅ Implementado y Testeado

### Problema Identificado
- Tetris DX escribe `LCDC=0x80` (Bit 7=1 LCD ON, Bit 0=0 BG OFF)
- En Game Boy Clásica (DMG), Bit 0=0 apaga el fondo → pantalla blanca
- En Game Boy Color (CGB), Bit 0 no apaga el fondo, sino que cambia prioridad de sprites
- Tetris DX es un juego CGB/dual que espera comportamiento CGB
- Nuestro emulador actúa como DMG estricta → pantalla blanca

### Solución Implementada

#### 1. Hack Educativo: Ignorar Bit 0 de LCDC
- **Archivo**: `src/gpu/renderer.py`
- **Cambio**: Comentada la verificación del Bit 0 de LCDC en `render_frame()`
- **Comportamiento**: Si Bit 7 (LCD Enable) está activo, el fondo se dibuja siempre, independientemente del Bit 0
- **Documentación**: Añadido comentario extenso explicando que es un hack temporal y educativo
- **Nota**: El código original queda comentado para referencia futura

#### 2. Implementación de Scroll (SCX/SCY)
- **Archivo**: `src/gpu/renderer.py`
- **Cambio**: Renderizado cambiado de tile a tile a píxel a píxel
- **Funcionalidad**:
  - Lectura de SCX (0xFF43) y SCY (0xFF42) desde la MMU
  - Cálculo de posición en tilemap: `map_pixel = (screen_pixel + scroll) % 256`
  - Wrap-around correcto (módulo 256)
  - Decodificación píxel a píxel de los tiles
- **Razón del cambio**: El renderizado píxel a píxel permite implementar scroll correctamente cuando el desplazamiento no es múltiplo de 8

### Tests Implementados
- **Archivo**: `tests/test_gpu_scroll.py` (nuevo)
- **Tests creados** (5 tests, todos pasando):
  1. `test_scroll_x`: Scroll horizontal (SCX)
  2. `test_scroll_y`: Scroll vertical (SCY)
  3. `test_scroll_wrap_around`: Wrap-around del scroll (módulo 256)
  4. `test_force_bg_render_lcdc_0x80`: Renderizado forzado con LCDC=0x80 (hack educativo)
  5. `test_scroll_zero`: Renderizado sin scroll (SCX=0, SCY=0)

**Resultado de tests**: ✅ 5 passed in 11.81s

### Archivos Modificados
- `src/gpu/renderer.py` - Modificado `render_frame()`
- `tests/test_gpu_scroll.py` - Nuevo archivo con tests
- `docs/bitacora/entries/2025-12-17__0033__forzar-renderizado-scroll.html` - Nueva entrada de bitácora
- `docs/bitacora/index.html` - Actualizado con nueva entrada
- `docs/bitacora/entries/2025-12-17__0032__diagnostico-opcodes-condicionales-lcdc.html` - Actualizado link "Siguiente"
- `INFORME_COMPLETO.md` - Añadida nueva entrada

### Validación Pendiente
- [ ] Probar Tetris DX con el hack del Bit 0 y verificar que se muestran gráficos
- [ ] Verificar que el scroll funciona correctamente en el juego (animaciones, desplazamiento de fondo)

### Notas Técnicas
- El hack del Bit 0 es temporal y educativo. En el futuro, cuando se implemente modo CGB completo, el Bit 0 deberá funcionar correctamente según la especificación CGB.
- El renderizado píxel a píxel es más lento pero más correcto y flexible. Se podría optimizar renderizando por tiles cuando el scroll es múltiplo de 8, pero por ahora la implementación píxel a píxel es más clara.

### Fuentes Consultadas
- Pan Docs: LCD Control Register (LCDC) - https://gbdev.io/pandocs/LCDC.html
- Pan Docs: Scrolling - https://gbdev.io/pandocs/Scrolling.html
- Pan Docs: Game Boy Color Registers - https://gbdev.io/pandocs/CGB_Registers.html

---

## Próximos Fixes (Pendientes)

### Fix 002: [Título del próximo fix]
**Estado**: ⏳ Pendiente

[Descripción del problema y solución cuando se implemente]

---

## Notas Generales

- Todos los fixes deben seguir el principio clean-room (sin copiar código de otros emuladores)
- Cada fix debe incluir tests que validen el comportamiento
- Los fixes deben documentarse en este documento antes de añadirse a las bitácoras
- Mantener este documento actualizado durante la sesión

