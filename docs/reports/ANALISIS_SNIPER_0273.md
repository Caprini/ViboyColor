# Análisis de Sniper Traces - Step 0273

## Resumen de Resultados

### Trazas Capturadas

1. **TRIGGER-D732**: 
   - **Escritura detectada**: `[TRIGGER-D732] Write 00 from PC:1F80 (Bank:1)`
   - **Análisis**: El juego SÍ intenta escribir en `0xD732` desde PC `0x1F80` (banco ROM 1), pero siempre escribe `0x00`.
   - **Conclusión**: El flag `0xD732` se inicializa a `0x00` pero nunca se modifica a un valor distinto, lo que sugiere que la ISR que debería modificarlo no se está ejecutando o no está escribiendo el valor correcto.

2. **SNIPER Traces**: 
   - **Resultado**: NO se capturaron trazas `[SNIPER]` para las direcciones críticas `0x36E3`, `0x6150`, `0x6152`.
   - **Observación**: Sin embargo, en el log completo se observan múltiples escrituras de VRAM desde `PC:36E3`:
     ```
     [VRAM] Write 8000=00 PC:36E3
     [VRAM] Write 8001=00 PC:36E3
     [VRAM] Write 8002=00 PC:36E3
     ...
     ```
   - **Problema identificado**: El código de verificación estaba usando `regs_->pc` después de que el PC avanzara durante `fetch_byte()`, por lo que nunca coincidía con las direcciones críticas.
   - **Corrección aplicada**: Se modificó el código para capturar `original_pc` antes del fetch y usar ese valor en la verificación.

### Análisis de Opcodes

**PC:1F80 (Banco 1) - Escritura a 0xD732**:
- El código en `0x1F80` está escribiendo `0x00` en `0xD732`.
- Esto sugiere que es código de inicialización que establece el flag a `0x00`.
- El problema es que ninguna otra parte del código modifica este flag después.

### Hallazgos Clave

1. **El juego SÍ llega a PC:36E3**: Las escrituras de VRAM confirman que el código en `0x36E3` se está ejecutando.
2. **El flag 0xD732 solo se escribe una vez**: Solo hay un intento de escritura, siempre con valor `0x00`.
3. **Las trazas SNIPER no aparecen**: Aunque el código corregido debería capturarlas, necesitamos ejecutar de nuevo con el código corregido.

### Próximos Pasos

1. **Re-ejecutar con código corregido**: El código ahora captura `original_pc` antes del fetch, por lo que debería detectar las direcciones críticas correctamente.
2. **Analizar opcodes en PC:36E3**: Una vez capturadas las trazas, desensamblar los opcodes para entender qué está haciendo el código.
3. **Investigar por qué 0xD732 no cambia**: Si el flag solo se escribe una vez con `0x00`, necesitamos encontrar qué código debería modificarlo y por qué no lo hace.

### Hipótesis

**Hipótesis Principal**: El juego espera que una ISR (Interrupt Service Routine) modifique `0xD732` después de completar una tarea (probablemente durante V-Blank), pero esta ISR:
- No se está ejecutando (IME=0 o interrupción no habilitada)
- Se ejecuta pero no modifica el flag
- Se ejecuta pero el flag se lee antes de que se modifique (race condition)

**Verificación necesaria**: 
- Verificar si hay interrupciones habilitadas en IE
- Verificar si IME está activo cuando debería ejecutarse la ISR
- Buscar en el código del juego qué ISR debería modificar `0xD732`

