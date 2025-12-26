# Análisis Step 0306 - Rendimiento y Corrupción Gráfica

**Fecha**: 2025-12-25  
**Step ID**: 0306  
**Estado**: En Progreso

## Resumen Ejecutivo

Este documento analiza dos problemas críticos identificados en Step 0305:
1. **Rendimiento bajo**: FPS 21.8 (debería ser ~60 FPS)
2. **Corrupción gráfica**: Patrón de tablero de ajedrez y sprites fragmentados

---

## 1. Análisis de Corrupción Gráfica

### 1.1 Patrón de Tablero de Ajedrez (Checkerboard Pattern)

**Hipótesis Investigadas**:

1. **Problema con cálculo de direcciones de tiles**
   - **Análisis**: El código en `PPU.cpp` (líneas 452-456) calcula correctamente:
     ```cpp
     uint8_t map_x = (x + scx) & 0xFF;
     uint8_t map_y = (ly_ + scy) & 0xFF;
     uint16_t tile_map_addr = tile_map_base + (map_y / 8) * 32 + (map_x / 8);
     ```
   - **Conclusión**: ✅ El cálculo es correcto según Pan Docs. El `& 0xFF` asegura wrap-around de 256 píxeles.

2. **Problema con scroll (SCX/SCY)**
   - **Análisis**: Los registros SCX/SCY se leen correctamente (líneas 384-385) y se aplican correctamente en el cálculo de `map_x` y `map_y`.
   - **Conclusión**: ✅ El scroll se aplica correctamente.

3. **Problema con mapeo del tilemap**
   - **Análisis**: El tilemap se mapea correctamente usando `(map_y / 8) * 32 + (map_x / 8)` que convierte coordenadas de píxel a coordenadas de tile (32x32 tiles).
   - **Conclusión**: ✅ El mapeo es correcto.

4. **Problema con sincronización entre frames**
   - **Análisis**: El framebuffer se limpia al inicio de cada frame (línea 195 en `PPU.cpp`), pero el renderizado ocurre línea por línea durante el frame. Si hay desincronización, podría causar artefactos.
   - **Conclusión**: ⚠️ **POSIBLE CAUSA**: Si el renderizado Python lee el framebuffer mientras C++ aún está escribiendo, podría causar patrones de tablero de ajedrez.

**Causa Más Probable**:
- **Desincronización entre C++ y Python**: El framebuffer se lee desde Python mientras C++ aún está renderizando, causando que algunos píxeles muestren valores de frames anteriores o parciales.

### 1.2 Sprites Fragmentados

**Hipótesis Investigadas**:

1. **Problema con renderizado de sprites en `render_sprites()`**
   - **Análisis**: El código en `renderer.py` (líneas 1011-1167) renderiza sprites correctamente:
     - Lee OAM correctamente (líneas 1075-1078)
     - Calcula posiciones correctamente (líneas 1092-1093)
     - Aplica flip correctamente (líneas 1120-1128)
     - Verifica transparencia correctamente (líneas 1151-1152)
   - **Conclusión**: ✅ La lógica de renderizado es correcta.

2. **Problema con orden de renderizado (sprites vs fondo)**
   - **Análisis**: Los sprites se renderizan DESPUÉS del fondo (línea 961 en `renderer.py`), lo cual es correcto según Pan Docs.
   - **Conclusión**: ✅ El orden es correcto.

3. **Problema con prioridad de sprites**
   - **Análisis**: El código lee el bit de prioridad (línea 1081) pero actualmente lo ignora (comentario línea 1154-1157). Esto podría causar que sprites se dibujen detrás del fondo cuando no deberían.
   - **Conclusión**: ⚠️ **POSIBLE CAUSA**: La prioridad de sprites no se implementa completamente, pero esto no explicaría fragmentación.

4. **Problema con OAM (Object Attribute Memory)**
   - **Análisis**: El OAM se lee correctamente desde 0xFE00-0xFE9F. No hay evidencia de corrupción en la lectura.
   - **Conclusión**: ✅ OAM se lee correctamente.

**Causa Más Probable**:
- **Renderizado de sprites sobre framebuffer parcial**: Si los sprites se renderizan sobre un framebuffer que aún no está completo (por desincronización), podrían aparecer fragmentados.

---

## 2. Análisis de Rendimiento

### 2.1 FPS Observado vs Esperado

- **FPS Observado**: 21.8
- **FPS Esperado**: ~60
- **Diferencia**: ~2.75x más lento de lo esperado

### 2.2 Operaciones Lentas Identificadas

**Operaciones Investigadas**:

1. **PixelArray**: ¿Es lento crear/modificar PixelArray en cada frame?
   - **Análisis**: En `renderer.py` línea 609, se crea un `PixelArray` en cada frame para el método C++ PPU. Esto es necesario para escribir píxel a píxel.
   - **Conclusión**: ⚠️ **POSIBLE CAUSA**: Crear `PixelArray` en cada frame puede ser costoso, pero es necesario para el renderizado.

2. **Scaling**: ¿Es lento hacer `pygame.transform.scale()` en cada frame?
   - **Análisis**: En `renderer.py` línea 637, se hace `pygame.transform.scale()` en cada frame para escalar de 160x144 a 480x432 (scale=3).
   - **Conclusión**: ⚠️ **POSIBLE CAUSA**: `pygame.transform.scale()` puede ser costoso, especialmente si se hace en cada frame sin cachear.

3. **Blit**: ¿Es lento hacer `screen.blit()` en cada frame?
   - **Análisis**: En `renderer.py` línea 639, se hace `screen.blit()` en cada frame. Esto es necesario para actualizar la pantalla.
   - **Conclusión**: ✅ `blit()` es necesario y generalmente rápido.

4. **Lectura de framebuffer**: ¿Es lenta la lectura desde C++?
   - **Análisis**: El framebuffer se lee usando memoryview de Cython (línea 502), que es Zero-Copy y debería ser rápido.
   - **Conclusión**: ✅ La lectura es eficiente (Zero-Copy).

**Operaciones Más Probables como Causa**:
1. **`pygame.transform.scale()`**: Escalar 160x144 a 480x432 en cada frame puede ser costoso.
2. **Creación de `PixelArray`**: Crear un nuevo `PixelArray` en cada frame puede tener overhead.
3. **Bucle de renderizado píxel a píxel**: El bucle en líneas 626-631 itera sobre 23,040 píxeles en cada frame.

### 2.3 Cuellos de Botella Encontrados

1. **Bucle de renderizado píxel a píxel** (líneas 626-631):
   - Itera sobre 23,040 píxeles (160x144)
   - Para cada píxel: lee índice, mapea a RGB, escribe en PixelArray
   - **Impacto**: Alto - se ejecuta en cada frame

2. **`pygame.transform.scale()`** (línea 637):
   - Escala una superficie de 160x144 a 480x432
   - **Impacto**: Medio-Alto - operación de transformación de imagen

3. **Creación de `PixelArray`** (línea 609):
   - Crea un nuevo objeto PixelArray en cada frame
   - **Impacto**: Medio - overhead de creación de objeto

---

## 3. Correlaciones

### 3.1 ¿Están relacionados los problemas?

**Hipótesis**: Sí, los problemas pueden estar relacionados.

**Razonamiento**:
1. Si el renderizado es lento (21.8 FPS), el framebuffer puede leerse mientras C++ aún está escribiendo, causando corrupción gráfica.
2. Si hay desincronización entre C++ y Python, los sprites pueden renderizarse sobre un framebuffer parcial, causando fragmentación.

### 3.2 ¿Uno causa el otro?

**Hipótesis**: El rendimiento bajo puede causar corrupción gráfica.

**Razonamiento**:
- Si el renderizado Python es lento, puede leer el framebuffer mientras C++ está escribiendo.
- Esto causaría que algunos píxeles muestren valores de frames anteriores o parciales.
- El patrón de tablero de ajedrez podría ser el resultado de leer píxeles de diferentes frames mezclados.

---

## 4. Conclusiones

### 4.1 Causas Raíz Identificadas

1. **Rendimiento bajo**:
   - **Causa principal**: Bucle de renderizado píxel a píxel (23,040 iteraciones por frame)
   - **Causa secundaria**: `pygame.transform.scale()` sin cachear
   - **Causa terciaria**: Creación de `PixelArray` en cada frame

2. **Corrupción gráfica**:
   - **Causa principal**: Desincronización entre C++ (escritura) y Python (lectura) del framebuffer
   - **Causa secundaria**: Renderizado lento que permite leer framebuffer parcial

### 4.2 Correcciones Necesarias

1. **Optimizar renderizado**:
   - Cachear la superficie escalada si el tamaño no cambia
   - Optimizar el bucle de renderizado píxel a píxel (usar NumPy si es posible)
   - Reutilizar `PixelArray` si es posible

2. **Sincronización framebuffer**:
   - Asegurar que el framebuffer se lea solo cuando esté completo (usar snapshot inmutable como en Step 0219)
   - Verificar que el snapshot se tome en el momento correcto (después de V-Blank)

3. **Monitor de rendimiento**:
   - Implementado en Step 0306 para medir tiempo de frame y FPS
   - Permitirá identificar qué operaciones son más costosas

### 4.3 Próximos Pasos

1. **Optimizar renderizado** (Step 0307):
   - Cachear superficie escalada
   - Optimizar bucle de renderizado
   - Medir impacto con monitor de rendimiento

2. **Verificar sincronización** (Step 0308):
   - Confirmar que el snapshot se toma en el momento correcto
   - Verificar que no hay condiciones de carrera

3. **Probar correcciones**:
   - Ejecutar emulador y verificar FPS mejora
   - Verificar que corrupción gráfica desaparece

---

## 5. Evidencia de Tests

### 5.1 Monitor de Rendimiento Implementado

**Comando**: El monitor se activa automáticamente en `renderer.py`

**Resultado Esperado**: 
```
[PERFORMANCE-TRACE] Frame 0 | Frame time: XX.XXms | FPS: XX.X
```

**Validación**: El monitor reportará el tiempo de frame y FPS cada 60 frames (1 segundo).

---

## Referencias

- Pan Docs - "Background Tile Map"
- Pan Docs - "Sprites"
- Pan Docs - "LCD Timing"
- Step 0219 - Snapshot Inmutable del Framebuffer
- Step 0305 - Investigación de Renderizado Python

