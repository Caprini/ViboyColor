# Análisis del Bucle Principal - Step 0317

## Objetivo
Identificar operaciones costosas en el método `run()` de `src/viboy.py` que causan tiempo entre frames variable (30-150ms).

## Estructura del Bucle Principal

El bucle principal en `src/viboy.py` (método `run()`, líneas 694-1334) tiene la siguiente estructura:

### Arquitectura del Bucle

```
1. Bucle Externo (por Frame): `while self.running:` (línea 780)
   ↓
2. Bucle Medio (por Scanline): `for line in range(SCANLINES_PER_FRAME):` (línea 796)
   - 154 iteraciones (144 visibles + 10 V-Blank)
   - Llamada C++: `self._cpu.run_scanline()` (línea 805)
   - Verificación frame listo: `self._ppu.get_frame_ready_and_reset()` (línea 810)
   - Snapshot: `bytearray(raw_view)` (línea 817) ⚠️ COSTOSO
   ↓
3. Renderizado (solo si hay frame listo):
   - Manejo eventos: `self._handle_pygame_events()` (línea 849)
   - Renderizado: `self._renderer.render_frame()` (línea 858)
   - Limitador FPS: `self._clock.tick(TARGET_FPS)` (línea 867)
   - Logs cada 60 frames (líneas 870, 910, 1061) ⚠️ COSTOSO
   ↓
4. Incremento contador: `self.frame_count += 1` (línea 1033)
```

## Operaciones Costosas Identificadas

### 1. ⚠️ CRÍTICO: Copia del Framebuffer (Línea 817)
**Operación**: `fb_data = bytearray(raw_view)`
- **Tamaño**: 160 × 144 × 3 = 69,120 bytes por frame
- **Frecuencia**: Una vez por frame (60 veces por segundo)
- **Costo estimado**: ~1-3ms por copia
- **Impacto**: ALTO - Se ejecuta en cada frame

**Análisis**: Esta copia es necesaria para crear un snapshot inmutable del framebuffer, pero puede optimizarse usando memoryview o reduciendo la frecuencia de copia.

### 2. ⚠️ ALTO: Logs Frecuentes (Líneas 870, 910, 1061)
**Operaciones**:
- Línea 870: `print(f"[FPS-LIMITER]...")` cada 60 frames
- Línea 910: `print(f"[FPS-DIAG]...")` cada 60 frames
- Línea 1061: Monitor GPS cada 60 frames (lee muchos registros)

**Frecuencia**: Cada 60 frames (1 vez por segundo)
- **Costo estimado**: ~0.5-2ms por log
- **Impacto**: MEDIO-ALTO - I/O es costoso, especialmente con múltiples logs

**Análisis**: Los logs son útiles para debugging pero pueden reducirse o desactivarse en modo producción.

### 3. ⚠️ MEDIO: Verificación de Paleta en Cada Frame (Líneas 784-786)
**Operación**:
```python
if self._mmu.read(0xFF47) == 0:
    self._mmu.write(0xFF47, 0xE4)
```
- **Frecuencia**: Una vez por frame (60 veces por segundo)
- **Costo estimado**: ~0.1-0.5ms por verificación
- **Impacto**: MEDIO - Acceso a memoria en cada frame

**Análisis**: Esta verificación solo es necesaria al inicio. Una vez que la paleta está configurada, no necesita verificarse cada frame.

### 4. ⚠️ MEDIO: Imports Dentro del Bucle (Líneas 877, 911)
**Operaciones**:
- Línea 877: `import pygame` dentro del bucle
- Línea 911: `import time` dentro del bucle

**Frecuencia**: Cada 60 frames
- **Costo estimado**: ~0.1-0.3ms por import (solo primera vez, luego cache)
- **Impacto**: BAJO-MEDIO - Los imports se cachean, pero es mala práctica

**Análisis**: Los imports deberían estar al inicio del archivo, no dentro del bucle.

### 5. ⚠️ BAJO: Monitor GPS Completo (Líneas 1061-1174)
**Operación**: Lee múltiples registros y calcula checksums de VRAM
- **Frecuencia**: Cada 60 frames (1 vez por segundo)
- **Costo estimado**: ~1-3ms por ejecución
- **Impacto**: MEDIO - Solo ocurre una vez por segundo, pero lee mucha memoria

**Análisis**: Útil para debugging pero puede desactivarse o reducirse en modo producción.

## Operaciones NO Problemáticas

### ✅ Renderizado (Línea 858)
- **Costo**: ~3.5ms (según Step 0316)
- **Análisis**: El renderizado es rápido y no es el cuello de botella.

### ✅ Limitador FPS (Línea 867)
- **Costo**: <0.1ms
- **Análisis**: `pygame.time.Clock.tick()` es muy eficiente.

### ✅ Manejo de Eventos (Línea 849)
- **Costo**: <0.5ms (depende del número de eventos)
- **Análisis**: Necesario y eficiente.

## Recomendaciones de Optimización

### Prioridad ALTA (Aplicar Inmediatamente)

1. **Reducir/Desactivar Logs en Bucle Crítico**
   - Desactivar logs de FPS-DIAG y FPS-LIMITER en modo producción
   - Reducir frecuencia del monitor GPS o desactivarlo completamente
   - Usar flags de debug para controlar logs

2. **Optimizar Verificación de Paleta**
   - Verificar solo una vez al inicio o cuando cambia el registro
   - No verificar en cada frame si ya está configurada

3. **Mover Imports al Inicio**
   - Mover `import pygame` y `import time` al inicio del archivo
   - Evitar imports dentro del bucle

### Prioridad MEDIA (Aplicar si es Necesario)

4. **Optimizar Copia del Framebuffer**
   - Considerar usar memoryview si es seguro
   - Reducir frecuencia de copia si es posible
   - **NOTA**: La copia es necesaria para snapshot inmutable, pero puede optimizarse

5. **Reducir Monitor GPS**
   - Desactivar completamente en modo producción
   - Reducir frecuencia (cada 300 frames en lugar de 60)
   - Simplificar cálculos (menos lecturas de memoria)

## Conclusión

El problema principal del tiempo entre frames variable (30-150ms) NO es el renderizado (~3.5ms), sino:

1. **Logs frecuentes** que causan I/O costoso
2. **Verificaciones innecesarias** en cada frame (paleta)
3. **Imports dentro del bucle** (mala práctica)
4. **Monitor GPS completo** que lee mucha memoria

Las optimizaciones propuestas deberían reducir significativamente el tiempo entre frames y mejorar el FPS de 6-32 FPS variable a un FPS más estable cercano a 60 FPS.

