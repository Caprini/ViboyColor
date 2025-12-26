# Instrucciones de Verificación Visual - Step 0304

## Objetivo
Verificar que las correcciones de paleta del Step 0303 eliminaron las rayas verdes durante una sesión extendida (10-15 minutos).

## Pasos de Verificación

### 1. Preparación
Asegúrate de que el código esté compilado:
```powershell
python setup.py build_ext --inplace
```

### 2. Ejecución del Emulador
Ejecuta el emulador con Pokémon Red:
```powershell
python main.py roms/pkmn.gb
```

### 3. Observación Visual
- **Duración**: Ejecutar durante **10-15 minutos** mientras observas la pantalla
- **Qué buscar**: Rayas verdes que aparecen en la pantalla
- **Cuándo aparecen**: Generalmente después de unos minutos de ejecución

### 4. Registro de Observaciones
Registra las siguientes observaciones:

#### ¿Aparecen rayas verdes?
- [ ] Sí
- [ ] No

#### Si aparecen rayas verdes:
- **¿Cuándo aparecen aproximadamente?** (minutos): ___________
- **¿Cómo se ven las rayas?**
  - [ ] Verticales
  - [ ] Horizontales
  - [ ] Ambos
- **¿Desaparecen y vuelven a aparecer o persisten?**
  - [ ] Desaparecen y vuelven
  - [ ] Persisten una vez que aparecen
- **¿Colores específicos?** (describe): ___________

### 5. Resultado
- **Si NO aparecen rayas verdes**: ✅ Problema resuelto. Continuar con documentación del éxito.
- **Si SÍ aparecen rayas verdes**: ⚠️ Continuar con implementación de monitores (Tareas 2-5 del plan).

## Activación de Monitores (Solo si las rayas aparecen)

Si las rayas verdes aparecen, activa los monitores:

### Monitor en Python (renderer.py)
Edita `src/gpu/renderer.py` y cambia:
```python
self._framebuffer_trace_enabled = False
```
a:
```python
self._framebuffer_trace_enabled = True
```

### Monitor en C++ (PPU.cpp)
Edita `src/core/cpp/PPU.cpp` y cambia:
```cpp
static constexpr bool ENABLE_FRAMEBUFFER_DETAILED_TRACE = false;
```
a:
```cpp
static constexpr bool ENABLE_FRAMEBUFFER_DETAILED_TRACE = true;
```

Luego recompila:
```powershell
python setup.py build_ext --inplace
```

### Ejecución con Monitores
Ejecuta capturando logs:
```powershell
python main.py roms/pkmn.gb > debug_step_0304_framebuffer.log 2>&1
```

Espera 5-10 minutos o hasta que aparezcan las rayas verdes, luego detén el emulador (Ctrl+C).

## Análisis de Logs (Solo si se capturaron)

Usa estos comandos para analizar los logs sin saturar el contexto:

```powershell
# Contar entradas de [FRAMEBUFFER-INDEX-TRACE]
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-INDEX-TRACE\]" | Measure-Object

# Ver entradas con valores no-cero
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-INDEX-TRACE\].*Has non-zero: True" | Select-Object -First 20

# Ver entradas de [FRAMEBUFFER-DETAILED]
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-DETAILED\]" | Select-Object -First 20
```

## Notas Importantes

1. **NO saturar contexto**: Si se capturan logs, usar solo muestras y estadísticas para análisis.
2. **Tiempo de ejecución**: 10-15 minutos es suficiente para detectar problemas que aparecen "después de unos minutos".
3. **Flexibilidad**: El plan debe adaptarse según los resultados de la verificación visual.

