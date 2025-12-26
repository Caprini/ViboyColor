# Ejecutar Verificación Step 0304 - Guía Rápida

## ✅ Paso 1: Compilación Completada
La extensión C++ ya está compilada y lista.

## 📋 Paso 2: Ejecutar Verificación Visual

### Comando para ejecutar el emulador:
```powershell
python main.py roms/pkmn.gb
```

### Instrucciones:
1. **Ejecuta el comando anterior**
2. **Observa la pantalla durante 10-15 minutos**
3. **Busca rayas verdes** que aparezcan en la pantalla
4. **Registra tus observaciones** (ver sección siguiente)

## 📝 Paso 3: Registrar Observaciones

### ¿Aparecen rayas verdes?
- [ ] **Sí** → Continuar con Paso 4 (Activar Monitores)
- [ ] **No** → ✅ Problema resuelto. Ir a Paso 5 (Documentar Éxito)

### Si aparecen rayas verdes, registra:
- **¿Cuándo aparecen?** (minutos): ___________
- **¿Cómo se ven?**
  - [ ] Verticales
  - [ ] Horizontales
  - [ ] Ambos
- **¿Desaparecen y vuelven o persisten?**
  - [ ] Desaparecen y vuelven
  - [ ] Persisten

## 🔧 Paso 4: Activar Monitores (Solo si aparecen rayas)

### 4.1 Activar Monitor Python
Edita `src/gpu/renderer.py` línea ~211:
```python
self._framebuffer_trace_enabled = True  # Cambiar de False a True
```

### 4.2 Activar Monitor C++
Edita `src/core/cpp/PPU.cpp` línea ~625:
```cpp
static constexpr bool ENABLE_FRAMEBUFFER_DETAILED_TRACE = true;  // Cambiar de false a true
```

### 4.3 Recompilar
```powershell
python setup.py build_ext --inplace
```

### 4.4 Ejecutar con Logs
```powershell
python main.py roms/pkmn.gb > debug_step_0304_framebuffer.log 2>&1
```

Espera 5-10 minutos o hasta que aparezcan las rayas, luego presiona **Ctrl+C** para detener.

### 4.5 Analizar Logs
```powershell
# Contar entradas
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-INDEX-TRACE\]" | Measure-Object

# Ver entradas con valores no-cero (primeras 20)
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-INDEX-TRACE\].*Has non-zero: True" | Select-Object -First 20

# Ver entradas detalladas (primeras 20)
Select-String -Path debug_step_0304_framebuffer.log -Pattern "\[FRAMEBUFFER-DETAILED\]" | Select-Object -First 20
```

## ✅ Paso 5: Documentar Resultado

### Si NO aparecieron rayas:
1. Actualizar `RESUMEN_STEP_0304.md` con el resultado
2. Actualizar estado de entrada HTML a VERIFIED
3. Continuar con otras funcionalidades

### Si SÍ aparecieron rayas:
1. Actualizar `RESUMEN_STEP_0304.md` con:
   - Observaciones registradas
   - Resultados de análisis de logs
   - Próximos pasos (Step 0305)
2. Preparar Step 0305 para investigar código de PPU C++

---

## 🚀 Comando Rápido para Empezar

```powershell
# Ejecutar verificación visual (10-15 minutos)
python main.py roms/pkmn.gb
```

**Nota**: Mantén esta ventana abierta y observa la pantalla del emulador durante 10-15 minutos.

