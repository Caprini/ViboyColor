# 📊 REPORTE: Análisis del Script test_emulator_timeout.py

**Fecha**: 2025-01-20  
**Archivo analizado**: `tools/test_emulator_timeout.py`  
**Problema reportado**: El script pasa un minuto y no se acaba.

---

## 🔍 PROBLEMAS IDENTIFICADOS

### 1. **PROBLEMA CRÍTICO: El timeout no detiene el emulador correctamente**

**Ubicación**: Líneas 54-61, 153-160

**Descripción**:
- El `timeout_handler()` solo cambia el flag global `running`, pero **NO cambia `viboy.running`**.
- El emulador (`Viboy.run()`) verifica `self.running` (instancia), no el flag global del script.
- El código intenta cambiar `viboy.running` después de que el bucle principal detecta que `running` (global) es False, pero:
  - El emulador está en un thread separado (`emulator_thread`)
  - Puede estar bloqueado en un bucle que no verifica el flag con suficiente frecuencia
  - El cambio del flag puede no ser visible inmediatamente

**Código problemático**:
```python
def timeout_handler():
    global running, timeout_reached
    time.sleep(60)  # Esperar 60 segundos
    if running:
        timeout_reached = True
        running = False  # ❌ Solo cambia el flag global, no viboy.running
        print("\n⏰ TIMEOUT: Se alcanzó el límite de 1 minuto. Cerrando emulador...")

# Más adelante...
while running:
    time.sleep(0.1)

# Detener el emulador
if hasattr(viboy, 'stop'):
    viboy.stop()  # ❌ Viboy no tiene método stop()
elif hasattr(viboy, 'running'):
    viboy.running = False  # ⚠️ Puede no funcionar si el emulador está bloqueado
```

---

### 2. **PROBLEMA: El monitor no retorna estadísticas correctamente**

**Ubicación**: Líneas 64-98, 168-173

**Descripción**:
- La función `monitor_emulator()` retorna un diccionario con estadísticas, pero:
  - El código que obtiene las estadísticas está **fuera del try-except** donde se ejecuta el monitor
  - Las estadísticas se inicializan con valores por defecto en lugar de obtenerlas del monitor
  - El thread del monitor es `daemon=True`, por lo que puede terminar abruptamente

**Código problemático**:
```python
monitor_thread = threading.Thread(target=monitor_emulator, args=(viboy,), daemon=True)
monitor_thread.start()

# ... código del emulador ...

# Esperar a que termine el thread de monitoreo
monitor_thread.join(timeout=1.0)  # ⚠️ Solo espera 1 segundo

# Obtener estadísticas del monitor
stats = {
    'duration': 60.0 if timeout_reached else 0.0,  # ❌ Valores hardcodeados
    'ly_changes': [],  # ❌ Siempre vacío
    'heartbeat_count': 0  # ❌ Siempre 0
}
```

---

### 3. **PROBLEMA: El emulador puede estar bloqueado**

**Ubicación**: Línea 145

**Descripción**:
- El emulador se ejecuta en un thread daemon con `viboy.run(debug=False)`
- Si el emulador entra en un bucle infinito o se bloquea, cambiar `viboy.running = False` puede no detenerlo
- No hay mecanismo de fuerza bruta para terminar el thread si no responde

**Código problemático**:
```python
def run_emulator():
    try:
        viboy.run(debug=False)  # ⚠️ Puede bloquearse indefinidamente
    except Exception as e:
        logging.error(f"Error en run(): {e}", exc_info=True)

emulator_thread = threading.Thread(target=run_emulator, daemon=True)
emulator_thread.start()
```

---

### 4. **PROBLEMA: Falta de sincronización entre threads**

**Descripción**:
- El script usa múltiples threads sin sincronización adecuada:
  - `timeout_thread`: Cambia el flag global `running`
  - `monitor_thread`: Monitorea el emulador
  - `emulator_thread`: Ejecuta el emulador
  - Thread principal: Espera y procesa resultados
- No hay locks o mecanismos de sincronización para evitar condiciones de carrera

---

## ✅ SOLUCIONES PROPUESTAS

### Solución 1: Cambiar `viboy.running` directamente en el timeout

**Modificación necesaria**:
```python
def timeout_handler(viboy: Viboy):
    """Función que se ejecuta después de 60 segundos"""
    global running, timeout_reached
    time.sleep(60)  # Esperar 60 segundos
    if running:
        timeout_reached = True
        running = False
        # ✅ Cambiar directamente viboy.running
        if hasattr(viboy, 'running'):
            viboy.running = False
        print("\n⏰ TIMEOUT: Se alcanzó el límite de 1 minuto. Cerrando emulador...")
```

### Solución 2: Usar un mecanismo de timeout más robusto

**Modificación necesaria**:
- Usar `threading.Timer` en lugar de un thread con `time.sleep()`
- Verificar periódicamente el tiempo transcurrido en lugar de esperar 60 segundos completos
- Usar un lock para sincronizar el acceso a `viboy.running`

### Solución 3: Obtener estadísticas del monitor correctamente

**Modificación necesaria**:
```python
# Usar una variable compartida para las estadísticas
monitor_stats = {'duration': 0.0, 'ly_changes': [], 'heartbeat_count': 0}

def monitor_emulator(viboy: Viboy, stats_dict: dict):
    """Monitorea el estado del emulador mientras corre"""
    # ... código del monitor ...
    stats_dict.update({
        'duration': time.time() - start_time,
        'ly_changes': ly_changes,
        'heartbeat_count': heartbeat_count
    })

# En main():
monitor_thread = threading.Thread(
    target=monitor_emulator, 
    args=(viboy, monitor_stats), 
    daemon=True
)
monitor_thread.start()

# ... después del timeout ...
monitor_thread.join(timeout=2.0)  # Esperar más tiempo
stats = monitor_stats  # ✅ Usar las estadísticas reales
```

### Solución 4: Agregar un timeout de fuerza bruta

**Modificación necesaria**:
- Si después de cambiar `viboy.running = False` el emulador no se detiene en X segundos, forzar la terminación
- Usar `threading.Event` para señalizar el timeout de manera más robusta

---

## 🎯 RECOMENDACIÓN PRINCIPAL

**Implementar una solución híbrida**:
1. Pasar `viboy` al `timeout_handler()` para cambiar `viboy.running` directamente
2. Usar `threading.Event` para sincronización entre threads
3. Agregar un timeout de fuerza bruta si el emulador no responde
4. Corregir la obtención de estadísticas del monitor

---

## ✅ SOLUCIONES IMPLEMENTADAS

### 1. **Protecciones en el bucle de scanline (`src/viboy.py`)**

**Cambios realizados**:
- ✅ Verificación de `self.running` antes de cada scanline
- ✅ Verificación de `self.running` dentro del bucle interno de CPU
- ✅ Contador de seguridad (`safety_counter`) con límite de 1000 iteraciones
- ✅ Detección y logging de bucles infinitos
- ✅ Protección contra `m_cycles == 0` (forzar avance mínimo)
- ✅ Protección contra `t_cycles <= 0` (forzar avance mínimo)

**Ubicación**: Líneas 710-780 en `src/viboy.py`

### 2. **Modo headless en el script de test (`tools/test_emulator_timeout.py`)**

**Cambios realizados**:
- ✅ Configuración de variables de entorno para modo headless (`SDL_VIDEODRIVER=dummy`)
- ✅ Desactivación del renderer para evitar bloqueos de ventana
- ✅ Corrección del timeout handler para cambiar `viboy.running` directamente
- ✅ Uso de diccionario compartido para estadísticas del monitor
- ✅ Agregado de lock de sincronización (`running_lock`)

**Ubicación**: Líneas 54-61, 130-160 en `tools/test_emulator_timeout.py`

---

## 📝 PRÓXIMOS PASOS

1. ✅ Revisar el código del script (COMPLETADO)
2. ✅ Implementar las correcciones propuestas (COMPLETADO)
3. ⏳ Ejecutar el script corregido y analizar logs
4. ⏳ Verificar que el timeout funciona correctamente
5. ⏳ Generar reporte final de pruebas

---

## 🔗 REFERENCIAS

- `src/viboy.py`: Líneas 655-800 (método `run()`)
- `tools/test_emulator_timeout.py`: Líneas 54-173 (lógica de timeout y monitoreo)

