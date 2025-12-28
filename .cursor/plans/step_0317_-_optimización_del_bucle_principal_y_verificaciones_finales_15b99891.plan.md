---
name: Step 0317 - Optimización del Bucle Principal y Verificaciones Finales
overview: Investigar y optimizar el bucle principal en src/viboy.py para reducir el tiempo entre frames variable (30-150ms) identificado en Step 0316. Verificar mejoras de FPS y completar las verificaciones manuales pendientes (visual, compatibilidad GB/GBC, controles) para avanzar hacia el objetivo del plan estratégico.
todos:
  - id: investigate-main-loop
    content: "Investigar bucle principal: revisar método run() en src/viboy.py, identificar operaciones costosas (copia framebuffer, renderizado, eventos pygame, logs), documentar hallazgos en ANALISIS_BUCLE_PRINCIPAL_STEP_0317.md"
    status: pending
  - id: apply-loop-optimizations
    content: "Aplicar optimizaciones al bucle principal: según análisis, optimizar copia framebuffer, renderizado, manejo eventos, reducir logs en bucle crítico, verificar que no rompe funcionalidad"
    status: pending
    dependencies:
      - investigate-main-loop
  - id: verify-fps-improvement
    content: "Verificar mejora de FPS: recompilar si necesario, ejecutar emulador 30 segundos capturando logs, analizar muestras (FPS, errores), comparar con resultados anteriores, documentar en VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md. SIEMPRE redirigir salida, NO leer completo."
    status: pending
    dependencies:
      - apply-loop-optimizations
  - id: final-visual-verification
    content: "Verificación visual final: ejecutar emulador 1-2 minutos, observar tiles visibles, estabilidad, FPS reportado, smoothness, actualizar VERIFICACION_RENDERIZADO_STEP_0312.md con estado después de optimizaciones"
    status: pending
    dependencies:
      - verify-fps-improvement
  - id: verify-gb-gbc-compatibility-manual
    content: "Verificar compatibilidad GB/GBC manualmente: probar ROMs GB y GBC, observar carga/renderizado/errores, actualizar COMPATIBILIDAD_GB_GBC_STEP_0315.md con estado de cada ROM"
    status: pending
    dependencies:
      - final-visual-verification
  - id: verify-controls-manual
    content: "Verificar controles manualmente: ejecutar emulador, probar cada botón (D-Pad, A, B, Start, Select), observar respuesta del juego, actualizar VERIFICACION_CONTROLES_STEP_0315.md con estado de cada botón"
    status: pending
    dependencies:
      - final-visual-verification
  - id: final-strategic-plan-evaluation
    content: "Evaluación final del plan estratégico: revisar todos los documentos completados, actualizar ESTADO_PLAN_ESTRATEGICO_STEP_0315.md con estado de cada criterio, progreso de fases, logros y próximos pasos"
    status: pending
    dependencies:
      - final-visual-verification
      - verify-gb-gbc-compatibility-manual
      - verify-controls-manual
  - id: update-documentation
    content: "Actualizar documentación: crear entrada HTML bitácora Step 0317, actualizar index.html e INFORME_FASE_2.md con todos los resultados y evaluación final del plan estratégico"
    status: pending
    dependencies:
      - final-strategic-plan-evaluation
---

# Plan: Step 0317 - Optimización del Bucle Principal y Verificaciones Finales

## Objetivo

Investigar y optimizar el bucle principal en `src/viboy.py` para reducir el tiempo entre frames variable (30-150ms) identificado en Step 0316. Verificar mejoras de FPS y completar las verificaciones manuales pendientes (visual, compatibilidad GB/GBC, controles) para avanzar hacia el objetivo del plan estratégico.

## Contexto

### Estado Actual

- ✅ **Step 0316 completado**: Análisis de FPS identificó causa raíz
- **Hallazgo**: Tiempo entre frames variable (30-150ms), NO es problema de renderizado (~3.5ms)
- **FPS actual**: 6-32 FPS (variable, promedio ~25 FPS)
- **Optimización aplicada**: Monitor de rendimiento desactivado
- ⏳ **Problema pendiente**: Tiempo entre frames variable en el bucle principal
- ⏳ **Verificaciones manuales pendientes**: Visual, compatibilidad GB/GBC, controles

### Plan Estratégico (Step 0311)

- ✅ **Fase 1**: Diagnóstico y Activación de Gráficos - COMPLETADA
- ⏳ **Fase 2**: Optimización y Estabilidad (Steps 0315-0317) - EN PROGRESO (~50% completado)
- ⏳ **Fase 3**: Controles y Jugabilidad (Steps 0318+) - PENDIENTE

## Tareas de Implementación

### Tarea 1: Investigar el Bucle Principal en `src/viboy.py`

**Objetivo**: Identificar operaciones costosas en el método `run()` que causan tiempo entre frames variable.**Archivos**: `src/viboy.py` (método `run()`, líneas 694-920 aproximadamente)**Acciones**:

1. Revisar el bucle principal (`run()`):

- Bucle externo: `while self.running:` (por frame)
- Bucle medio: `for line in range(SCANLINES_PER_FRAME):` (154 scanlines)
- Llamada C++: `self._cpu.run_scanline()` por cada scanline
- Obtención framebuffer: `self._ppu.get_frame_ready_and_reset()`
- Snapshot: `bytearray(raw_view)` (línea 817)
- Renderizado: `self._renderer.render_frame()`
- Manejo eventos: `self._handle_pygame_events()`
- Limitador FPS: `self._clock.tick(TARGET_FPS)`

2. Identificar posibles operaciones costosas:

- ¿El bucle de 154 scanlines tiene overhead?
- ¿La copia `bytearray(raw_view)` es costosa?
- ¿El renderizado tiene operaciones costosas?
- ¿El manejo de eventos pygame tiene overhead?
- ¿Hay logs o prints que se ejecutan frecuentemente?

3. Agregar monitoreo temporal (si es necesario):

- Medir tiempo de cada componente del bucle
- Identificar cuál componente es el cuello de botella

4. Documentar hallazgos en `ANALISIS_BUCLE_PRINCIPAL_STEP_0317.md`:

- Estructura del bucle identificada
- Operaciones costosas encontradas
- Recomendaciones de optimización

**Entregable**: `ANALISIS_BUCLE_PRINCIPAL_STEP_0317.md` con hallazgos---

### Tarea 2: Aplicar Optimizaciones al Bucle Principal

**Objetivo**: Aplicar optimizaciones basadas en el análisis de la Tarea 1.**Archivos**: `src/viboy.py`, `src/gpu/renderer.py` (si es necesario)**Acciones** (según hallazgos del análisis):

1. **Si el problema es la copia del framebuffer (`bytearray(raw_view)`)**:

- Verificar si se puede optimizar la copia
- Considerar usar memoryview directamente si es seguro
- Documentar la optimización

2. **Si el problema es el renderizado**:

- Verificar que no hay operaciones costosas en `render_frame()`
- Optimizar operaciones de pygame si es necesario

3. **Si el problema es el manejo de eventos**:

- Optimizar `_handle_pygame_events()` para procesar eventos más rápido
- Considerar procesar eventos menos frecuentemente

4. **Si hay logs o prints frecuentes**:

- Reducir o eliminar logs en el bucle crítico
- Usar logs solo cada N frames

5. **Si el problema es el bucle de scanlines**:

- Verificar que no hay overhead en la iteración
- Optimizar la lógica del bucle si es necesario

6. Verificar que las optimizaciones no rompen funcionalidad:

- Los tiles deben seguir mostrándose
- El emulador no debe crashear
- El FPS debe mejorar

**Entregable**: Código optimizado---

### Tarea 3: Verificar Mejora de FPS Después de Optimizaciones

**Objetivo**: Verificar que las optimizaciones mejoran el FPS.**⚠️ IMPORTANTE - CONTROL DE CONTEXTO**:

- Ejecutar durante 30 segundos
- Redirigir salida a archivo
- NO leer archivo completo
- Usar solo muestras para análisis

**Acciones**:

1. Recompilar módulos C++ si es necesario:
   ```powershell
            python setup.py build_ext --inplace
   ```




2. Ejecutar emulador capturando logs:
   ```powershell
            python main.py roms/pkmn.gb > logs/fps_after_optimization_step_0317.log 2>&1
   ```




3. Esperar **30 segundos** y detener (Ctrl+C)
4. Analizar logs (solo muestras):
   ```powershell
            # Verificar FPS reportado en barra de título (si hay logs)
            Select-String -Path "logs/fps_after_optimization_step_0317.log" -Pattern "FPS:" | Select-Object -First 20 -Last 10
            
            # Verificar si hay errores
            Select-String -Path "logs/fps_after_optimization_step_0317.log" -Pattern "ERROR|Exception" | Select-Object -First 20
   ```




5. Comparar con resultados anteriores:

- FPS antes: 6-32 FPS (variable, promedio ~25 FPS)
- FPS después: [completar con resultados]
- Tiempo entre frames antes: 30-150ms
- Tiempo entre frames después: [completar con resultados]

6. Documentar resultados en `VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md`:

- FPS observado después de optimizaciones
- Comparación con resultados anteriores
- Conclusión sobre efectividad de optimizaciones

**Entregable**: `VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md` con resultados---

### Tarea 4: Verificación Visual Final

**Objetivo**: Ejecutar verificación visual final después de optimizaciones.**Archivos**: Emulador ejecutándose, `VERIFICACION_RENDERIZADO_STEP_0312.md`**Acciones**:

1. Ejecutar emulador:
   ```powershell
            python main.py roms/pkmn.gb
   ```




2. Observar durante **1-2 minutos**:

- ¿Pantalla blanca? (debe ser NO)
- ¿Tiles visibles? (checkerboard, líneas horizontales/verticales)
- ¿Estabilidad? (sin parpadeos excesivos)
- ¿FPS reportado? (verificar en barra de título, debe ser ~60 FPS o mejor)
- ¿Smoothness? (movimiento fluido si hay animación)

3. Actualizar `VERIFICACION_RENDERIZADO_STEP_0312.md`:

- Estado del renderizado (funciona/parcial/no funciona)
- Descripción visual de lo observado
- FPS observado
- Problemas visuales (si los hay)
- Estado después de optimizaciones

**Entregable**: `VERIFICACION_RENDERIZADO_STEP_0312.md` actualizado---

### Tarea 5: Verificación de Compatibilidad GB/GBC (Manual)

**Objetivo**: Verificar compatibilidad con ROMs de GB y GBC manualmente.**Archivos**: Múltiples ROMs, `COMPATIBILIDAD_GB_GBC_STEP_0315.md`**Acciones**:

1. **Probar ROM GB (DMG)**:
   ```powershell
            python main.py roms/pkmn.gb
   ```




- ¿Carga correctamente?
- ¿Renderiza gráficos?
- ¿Se ejecuta sin errores?
- Observar durante 30 segundos

2. **Probar ROM GBC** (si está disponible):
   ```powershell
            python main.py roms/mario.gbc
   ```




- ¿Carga correctamente?
- ¿Se detecta como GBC?
- ¿Renderiza gráficos (puede ser en escala de grises)?
- Observar durante 30 segundos

3. Actualizar `COMPATIBILIDAD_GB_GBC_STEP_0315.md`:

- Estado de cada ROM probada (funciona/parcial/no funciona)
- Descripción de lo observado
- Problemas específicos encontrados

**Entregable**: `COMPATIBILIDAD_GB_GBC_STEP_0315.md` actualizado---

### Tarea 6: Verificación de Controles (Manual)

**Objetivo**: Verificar que los controles funcionan correctamente.**Archivos**: Emulador ejecutándose, `VERIFICACION_CONTROLES_STEP_0315.md`**Acciones**:

1. Ejecutar emulador:
   ```powershell
            python main.py roms/pkmn.gb
   ```




2. Probar cada botón:

- **D-Pad**: → ← ↑ ↓
- **Botones**: Z (A), X (B)
- **Menú**: RETURN (Start), RSHIFT (Select)

3. Observar si hay respuesta:

- ¿El juego reacciona a los botones?
- ¿Hay navegación en menú?
- ¿Hay movimiento de personaje?
- ¿Los controles se sienten responsivos?

4. Actualizar `VERIFICACION_CONTROLES_STEP_0315.md`:

- Estado de cada botón (funciona/no funciona)
- Observaciones sobre respuesta del juego
- Problemas identificados

**Entregable**: `VERIFICACION_CONTROLES_STEP_0315.md` actualizado---

### Tarea 7: Evaluación Final del Plan Estratégico

**Objetivo**: Evaluar el progreso completo del plan estratégico después de todas las optimizaciones y verificaciones.**Archivos**: Todos los documentos completados, `ESTADO_PLAN_ESTRATEGICO_STEP_0315.md`**Acciones**:

1. Revisar todos los documentos completados:

- `VERIFICACION_RENDERIZADO_STEP_0312.md`
- `ANALISIS_FPS_BAJO_STEP_0315.md`
- `ANALISIS_BUCLE_PRINCIPAL_STEP_0317.md`
- `VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md`
- `COMPATIBILIDAD_GB_GBC_STEP_0315.md`
- `VERIFICACION_CONTROLES_STEP_0315.md`

2. Actualizar `ESTADO_PLAN_ESTRATEGICO_STEP_0315.md`:

- Estado de cada criterio de éxito:
    - ✅ Gráficos: ¿Funcionan? [completar]
    - ⏳ Rendimiento: ¿FPS estable ~60? [completar]
    - ⏳ Controles: ¿Funcionan? [completar]
    - ⏳ Compatibilidad: ¿GB y GBC? [completar]
    - ⏳ Jugabilidad: ¿ROMs funcionan? [completar]
- Progreso de cada fase (% completado)
- Logros alcanzados
- Problemas pendientes
- Próximos pasos recomendados

**Entregable**: `ESTADO_PLAN_ESTRATEGICO_STEP_0315.md` actualizado completamente---

### Tarea 8: Actualización de Documentación

**Archivos**:

- `docs/bitacora/entries/2025-12-27__0317__optimizacion-bucle-principal-verificaciones-finales.html`
- `docs/bitacora/index.html`
- `INFORME_FASE_2.md`

**Objetivo**: Documentar todo el trabajo realizado en Step 0317.**Acciones**:

1. Crear entrada HTML de bitácora con:

- Resumen del step
- Análisis del bucle principal
- Optimizaciones aplicadas
- Verificación de mejoras de FPS
- Resultados de verificaciones manuales (visual, compatibilidad, controles)
- Evaluación actualizada del plan estratégico

2. Actualizar `docs/bitacora/index.html` (insertar al inicio de la lista)
3. Actualizar `INFORME_FASE_2.md` con el Step 0317

**Entregable**: Documentación completa actualizada---

## Criterios de Éxito

- ✅ Bucle principal analizado (operaciones costosas identificadas)
- ✅ Optimizaciones aplicadas (código mejorado)
- ✅ FPS mejorado después de optimizaciones (verificado)
- ✅ Verificación visual final completada y documentada
- ✅ Compatibilidad GB/GBC verificada y documentada
- ✅ Controles verificados y documentados
- ✅ Plan estratégico evaluado completamente
- ✅ Documentación completa actualizada

---

## Notas Importantes

1. **Prioridad de Tareas**:

- Primero: Investigar bucle principal (Tarea 1) - crítico para rendimiento
- Segundo: Aplicar optimizaciones (Tarea 2) - mejora inmediata
- Tercero: Verificar mejoras (Tarea 3) - confirmar efectividad
- Cuarto: Verificaciones manuales (Tareas 4-6) - completar validación
- Final: Evaluación y documentación (Tareas 7-8)

2. **Control de Contexto**:

- **SIEMPRE** usar límites en comandos (`Select-Object -First N`)
- **NO** leer archivos completos de logs
- Redirigir salidas grandes a archivos temporales
- Analizar muestras, no datos completos

3. **Optimizaciones del Bucle Principal**:

- Enfocarse en operaciones dentro del bucle crítico
- Evitar operaciones costosas por frame
- Optimizar copia del framebuffer si es necesario
- Reducir overhead de eventos pygame

4. **Plan Estratégico**:

- Este step debe completar la Fase 2 (~80-90% del plan)
- Si se completan todas las verificaciones, el plan estará ~80% completo
- Documentar claramente qué queda pendiente

5. **Siguiente Step**: