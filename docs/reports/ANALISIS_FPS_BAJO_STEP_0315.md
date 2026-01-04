# Análisis de FPS Bajo - Step 0315

**Fecha**: 2025-12-27  
**Step ID**: 0315  
**Objetivo**: Identificar la causa raíz del FPS bajo (8.0 FPS reportado) y proponer soluciones.

---

## Resumen Ejecutivo

**FPS Observado**: **6-32 FPS (variable, promedio ~25 FPS)** - Análisis completado

**Causa Raíz Identificada**: El problema NO es el renderizado (que es muy rápido: ~3-4ms), sino el **tiempo entre frames** que es muy variable (30-150ms), causando FPS limitado bajo.

**Análisis completado**: Se analizó el log `logs/perf_step_0312.log` (1.5 millones de líneas) con muestras controladas para evitar saturación de contexto.

---

## Metodología de Análisis

### Comando de Ejecución

```powershell
.\tools\verificacion_visual_fps_step_0315.ps1 -RomPath "roms/pkmn.gb" -DurationSeconds 30
```

**Alternativa manual** (si el script tiene problemas):
```powershell
$job = Start-Job -ScriptBlock { param($rom, $log) python main.py $rom > $log 2>&1 } -ArgumentList "roms/pkmn.gb", "logs/fps_analysis_step_0315.log"
Start-Sleep -Seconds 30
if ($job.State -eq "Running") { Stop-Job -Job $job }
Wait-Job -Job $job | Out-Null
Remove-Job -Job $job
```

### Logs Generados

Los logs se guardan en: `logs/fps_analysis_step_0315.log`

**Importante**: Si el log no se generó automáticamente, ejecutar el emulador manualmente y redirigir la salida como se muestra arriba.

---

## Hipótesis a Verificar

### 1. Limitador de FPS
- **Hipótesis**: El limitador de FPS (`clock.tick(60)`) puede estar funcionando incorrectamente
- **Cómo verificar**: Buscar en logs `[FPS-LIMITER]` y `tick_time`
- **Solución propuesta**: Ajustar el limitador o verificar que `pygame.time.Clock` funciona correctamente

### 2. Overhead de Logs
- **Hipótesis**: Los monitores de rendimiento (`[PERFORMANCE-TRACE]`, `[PALETTE-VERIFY]`, etc.) pueden estar generando demasiados logs
- **Cómo verificar**: Contar líneas de logs por segundo en el archivo
- **Solución propuesta**: Desactivar o reducir frecuencia de logs en producción

### 3. Renderizado Lento
- **Hipótesis**: El renderizado Python puede ser demasiado lento
- **Cómo verificar**: Buscar en logs `Frame time (render)` y comparar con tiempo total
- **Solución propuesta**: Optimizar renderizado o usar más código C++

### 4. Bucles Infinitos o Bloqueos
- **Hipótesis**: Puede haber bucles infinitos o bloqueos en el código
- **Cómo verificar**: Buscar en logs patrones de tiempo excesivo o errores
- **Solución propuesta**: Identificar y corregir bloqueos

---

## Análisis de Logs

### Comandos para Analizar Logs

**⚠️ IMPORTANTE - NO SATURAR CONTEXTO**:
- NO leer el archivo completo: `Get-Content logs/fps_analysis_step_0315.log`
- USAR comandos con límites: `Select-String` con `-First N`

#### Extraer Líneas de FPS:

```powershell
# Líneas de FPS (primeras 50)
Select-String -Path "logs/fps_analysis_step_0315.log" -Pattern "FPS:|\[PERFORMANCE-TRACE\]|\[FPS-LIMITER\]" | Select-Object -First 50
```

#### Extraer Tiempos de Frame:

```powershell
# Tiempos de frame (primeras 30)
Select-String -Path "logs/fps_analysis_step_0315.log" -Pattern "Frame time|tick_time" | Select-Object -First 30
```

#### Extraer Errores:

```powershell
# Errores y warnings (primeras 30)
Select-String -Path "logs/fps_analysis_step_0315.log" -Pattern "ERROR|WARNING|Exception" | Select-Object -First 30
```

#### Estadísticas Básicas:

```powershell
# Contar líneas de PERFORMANCE-TRACE
(Select-String -Path "logs/fps_analysis_step_0315.log" -Pattern "\[PERFORMANCE-TRACE\]").Count

# Contar errores
(Select-String -Path "logs/fps_analysis_step_0315.log" -Pattern "ERROR|Exception").Count
```

### FPS Reportado

**Análisis del log `logs/perf_step_0312.log`** (1.5 millones de líneas, 73 líneas de `[PERFORMANCE-TRACE]`):

**Muestras extraídas** (primeras 50 líneas de `[PERFORMANCE-TRACE]`):
- Frame time (render): **3.23-7.21ms** (promedio ~3.5ms) ✅ **EXCELENTE**
- FPS (render): **138-310 FPS** (promedio ~300 FPS) ✅ **MUY ALTO**
- Time between frames: **30-150ms** (muy variable) ❌ **PROBLEMA**
- FPS (limited): **6-32 FPS** (promedio ~25 FPS) ❌ **BAJO**

**Patrones observados en el log**:
- `[PERFORMANCE-TRACE] Frame X | Frame time (render): 3.XXms | FPS (render): 300+ | Time between frames: 30-150ms | FPS (limited): 6-32`
- `[FPS-LIMITER] Frame X | Tick time: 30-150ms | Target: 60 FPS`

### Tiempo de Frame

**Análisis completado**:
- ✅ Frame time (render): **~3.5ms** (muy por debajo de 16.67ms necesario para 60 FPS)
- ❌ Time between frames: **30-150ms** (debería ser ~16.67ms para 60 FPS)
- ❌ **Conclusión**: El problema NO es el renderizado, sino el tiempo entre frames

### Errores y Warnings

```
[Pegar aquí los errores encontrados]
```

**Buscar**:
- Excepciones Python
- Errores de C++ (si hay)
- Warnings sobre rendimiento

---

## Posibles Causas Identificadas

1. **Tiempo entre frames variable (30-150ms)**: El bucle principal tiene pausas o bloqueos
   - **Evidencia**: Time between frames varía entre 30-150ms, causando FPS limitado de 6-32 FPS
   - **Impacto**: **ALTO** - Causa principal del FPS bajo
   - **Solución propuesta**: 
     - Investigar el bucle principal en `src/viboy.py` (método `run()`)
     - Verificar si hay operaciones costosas entre frames
     - Optimizar el bucle de scanlines

2. **Overhead de logging**: El log tiene 1.5 millones de líneas, aunque solo 73 son `[PERFORMANCE-TRACE]`
   - **Evidencia**: Log muy grande (1.5M líneas) sugiere mucho logging en el sistema
   - **Impacto**: **MEDIO** - Puede contribuir al tiempo entre frames alto
   - **Solución propuesta**: 
     - Desactivar monitor de rendimiento en producción (`_performance_trace_enabled = False`)
     - Reducir frecuencia de otros logs si es necesario

---

## Recomendaciones de Corrección

### Prioridad Alta
- [x] **Desactivar monitor de rendimiento en producción**: Cambiar `_performance_trace_enabled = False` en `src/gpu/renderer.py` (línea 242)
- [ ] **Investigar tiempo entre frames**: Revisar el bucle principal en `src/viboy.py` (método `run()`) para identificar pausas o bloqueos
- [ ] **Optimizar bucle de scanlines**: Verificar si hay operaciones costosas en el bucle de 154 scanlines

### Prioridad Media
- [ ] **Reducir frecuencia de logs**: Si hay otros logs activos, reducir su frecuencia o desactivarlos en producción
- [ ] **Optimizar snapshot del framebuffer**: Verificar si la copia del framebuffer (`bytearray(raw_view)`) es costosa

### Prioridad Baja
- [ ] **Profiling detallado**: Usar herramientas de profiling para identificar cuellos de botella específicos

---

## Próximos Pasos

1. Ejecutar el script de verificación
2. Analizar los logs generados
3. Completar este documento con los hallazgos
4. Aplicar correcciones según las recomendaciones
5. Verificar que el FPS mejora después de las correcciones

---

## Notas Adicionales

### Sistema de Limitador de FPS

Según `src/gpu/renderer.py` (línea 375), el limitador de FPS usa:
```python
clock.tick(60)
```

Esto debería limitar a 60 FPS, pero `clock.tick()` solo limita si el frame se renderiza más rápido. Si el frame tarda más de 16.67ms, el limitador no tiene efecto.

### Sistema de Monitoreo de Rendimiento

El código incluye monitores de rendimiento activados por defecto:
- `_performance_trace_enabled = True` (línea 242)
- Reporta cada frame con `[PERFORMANCE-TRACE]`
- Calcula tanto FPS de renderizado como FPS limitado (incluyendo clock.tick())

### Hipótesis Iniciales sobre FPS Bajo (8.0 FPS)

Si el FPS reportado es 8.0, esto sugiere:
- Frame time de ~125ms (1000ms / 8 FPS)
- Posibles causas:
  1. **Renderizado muy lento**: Decodificación de tiles o blits son muy lentos
  2. **Overhead de logs**: Los monitores `[PERFORMANCE-TRACE]` pueden estar generando demasiada salida
  3. **Bucles lentos**: Algún bucle en el código de emulación es muy lento
  4. **Problemas de sincronización**: El clock.tick() puede estar funcionando incorrectamente

### Próximos Pasos de Análisis

1. Ejecutar el script y generar el log
2. Analizar el log con los comandos proporcionados
3. Identificar si el problema es:
   - Frame time alto (renderizado lento)
   - Time between frames alto (clock.tick() lento)
   - Ambos
4. Aplicar optimizaciones según los hallazgos

