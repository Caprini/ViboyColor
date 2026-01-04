# Guía Rápida de Verificación - Step 0318

## Instrucciones para Ejecutar las Verificaciones

### Paso 1: Verificación de FPS

1. **Ejecutar el emulador**:
   ```bash
   python3 main.py roms/pkmn.gb
   ```

2. **Observar durante 2 minutos**:
   - Mira la barra de título de la ventana (muestra "FPS: XX.X")
   - Anota:
     - **FPS promedio**: Valor que ves más frecuentemente
     - **FPS mínimo**: Valor más bajo observado
     - **FPS máximo**: Valor más alto observado
     - **Estabilidad**: ¿Es estable (variación < 5 FPS) o variable?
     - **Smoothness**: ¿El movimiento es fluido o entrecortado?

3. **Reportar resultados**: Completa la sección "Resultados Observados" en `VERIFICACION_FPS_OPTIMIZACIONES_STEP_0317.md`

---

### Paso 2: Verificación Visual

1. **Mientras el emulador está ejecutándose** (del Paso 1):
   - Observa la pantalla del emulador
   - Verifica:
     - ✅ ¿Se muestran tiles/gráficos? (NO debe ser pantalla blanca)
     - ✅ ¿Hay patrones visibles? (checkerboard, líneas, etc.)
     - ✅ ¿El renderizado es estable? (sin parpadeos excesivos)
     - ✅ ¿El FPS reportado en la barra de título?

2. **Tomar captura de pantalla**:
   - Presiona Print Screen o usa tu herramienta de captura
   - Guarda como `docs/screenshots/step_0318_renderizado.png` (opcional)

3. **Reportar resultados**: Actualiza `VERIFICACION_RENDERIZADO_STEP_0312.md` con:
   - Estado del renderizado (Funciona / Parcial / No funciona)
   - Descripción visual de lo observado
   - FPS observado
   - Confirmación de captura de pantalla

---

### Paso 3: Verificación de Compatibilidad GB/GBC

1. **Probar ROM GB (DMG)**:
   ```bash
   python3 main.py roms/pkmn.gb
   ```
   - Observar 30 segundos
   - Verificar: ¿Carga? ¿Renderiza? ¿FPS estable?

2. **Probar ROM GBC** (si está disponible):
   ```bash
   python3 main.py roms/[nombre_rom].gbc
   ```
   - Observar 30 segundos
   - Verificar: ¿Carga? ¿Se detecta como GBC? ¿Renderiza?

3. **Reportar resultados**: Actualiza `COMPATIBILIDAD_GB_GBC_STEP_0315.md` con:
   - Estado de cada ROM probada
   - Descripción de lo observado
   - Problemas encontrados (si los hay)

---

### Paso 4: Verificación de Controles

1. **Ejecutar el emulador**:
   ```bash
   python3 main.py roms/pkmn.gb
   ```

2. **Probar cada botón durante 2-3 minutos**:
   - **D-Pad**: → ← ↑ ↓
   - **Botones**: Z (A), X (B)
   - **Menú**: RETURN (Start), RSHIFT (Select)

3. **Observar respuesta del juego**:
   - ¿El juego reacciona a los botones?
   - ¿Hay navegación en menú?
   - ¿Hay movimiento de personaje?
   - ¿Los controles se sienten responsivos?

4. **Reportar resultados**: Actualiza `VERIFICACION_CONTROLES_STEP_0315.md` con:
   - Estado de cada botón (Funciona / No funciona / Parcial)
   - Descripción de respuesta
   - Observaciones sobre responsividad

---

## Formato de Reporte

Después de completar las verificaciones, reporta los resultados en este formato:

```markdown
## Resumen de Verificación [Nombre]
- Estado: [Éxito/Parcial/Fallo]
- Detalles: [Descripción breve]
- Problemas encontrados: [Lista o "Ninguno"]
- Próximos pasos: [Si aplica]
```

---

## Siguiente Paso

Una vez que completes las verificaciones y actualices los documentos, el Planificador actualizará:
- `ESTADO_PLAN_ESTRATEGICO_STEP_0315.md` (evaluación final)
- Entrada HTML de bitácora (Step 0318)
- `docs/bitacora/index.html`
- `INFORME_FASE_2.md`

