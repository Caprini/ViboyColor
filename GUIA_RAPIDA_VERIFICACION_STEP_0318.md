# Guía Rápida de Verificación - Step 0318

## ⚠️ Requisito Previo: Pygame Instalado

Antes de ejecutar las verificaciones, asegúrate de que pygame está instalado:

```bash
# Opción 1: Instalar desde apt (requiere sudo)
sudo apt install python3-pygame

# Opción 2: Instalar en entorno virtual
python3 -m venv ~/venv_viboy
source ~/venv_viboy/bin/activate
pip install pygame-ce
```

---

## 🚀 Ejecutar Verificaciones

### Método 1: Usar el Script Automático

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
./tools/ejecutar_verificaciones_manuales_step_0318.sh
```

### Método 2: Ejecutar Manualmente

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
python3 main.py roms/pkmn.gb
```

---

## 📋 Checklist de Verificación

### 1. Verificación de FPS (2 minutos)

- [ ] ¿Se abrió la ventana del emulador?
- [ ] ¿Qué FPS muestra la barra de título? (ej: "FPS: 45.2")
- [ ] **FPS promedio**: Valor más frecuente observado
- [ ] **FPS mínimo**: Valor más bajo observado
- [ ] **FPS máximo**: Valor más alto observado
- [ ] **Estabilidad**: ¿Estable (variación < 5 FPS) o Variable?
- [ ] **Smoothness**: ¿Fluido o Entrecortado?

### 2. Verificación Visual

- [ ] ¿Se muestran gráficos/tiles? (Sí/No - describe qué ves)
- [ ] ¿La pantalla está completamente blanca? (Sí/No)
- [ ] ¿Qué patrones ves? (checkerboard, líneas horizontales/verticales, sprites)
- [ ] ¿El renderizado es estable? (sin parpadeos excesivos)
- [ ] ¿Hay artefactos visuales? (rayas, corrupción, etc.)

### 3. Verificación de Controles (opcional ahora)

- [ ] **D-Pad →**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **D-Pad ←**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **D-Pad ↑**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **D-Pad ↓**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **Z (A)**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **X (B)**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **RETURN (Start)**: ¿Funciona? ¿Qué hace en el juego?
- [ ] **RSHIFT (Select)**: ¿Funciona? ¿Qué hace en el juego?

---

## 📝 Reportar Resultados

Una vez que completes las verificaciones, comparte los resultados y los documentaré en:

- `VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md`
- `VERIFICACION_RENDERIZADO_STEP_0312.md`
- `VERIFICACION_CONTROLES_STEP_0315.md`
- `COMPATIBILIDAD_GB_GBC_STEP_0315.md`
- `ESTADO_PLAN_ESTRATEGICO_STEP_0315.md`

---

## 🆘 Solución de Problemas

### Error: "Pygame no está instalado"
- Instala pygame usando uno de los métodos del inicio de esta guía

### Error: "viboy_core no disponible"
- Esto es normal si el módulo C++ no está compilado
- El emulador funcionará pero será más lento (usando componentes Python)

### Pantalla blanca
- Esto puede ser normal si el juego no ha inicializado completamente
- Observa si aparecen gráficos después de unos segundos

### FPS muy bajo
- Si el módulo C++ no está compilado, el FPS será bajo
- Las optimizaciones del Step 0317 deberían mejorar el FPS incluso sin C++

