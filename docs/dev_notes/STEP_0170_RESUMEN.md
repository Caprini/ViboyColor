# Step 0170: PPU Fase D - Implementación de Modos PPU y Registro STAT

**Fecha:** 2025-12-20  
**Step ID:** 0170  
**Estado:** ✅ Implementado (Tests pasan, pero bucle de polling persiste)

## Resumen

El análisis de la traza del Step 0169 reveló un bucle de "polling" infinito. La CPU está esperando un cambio en el registro STAT (0xFF41) que nunca ocurre, porque nuestra PPU en C++ aún no implementaba correctamente la máquina de estados de renderizado. Este Step documenta la corrección del registro STAT dinámico y la verificación de que los modos PPU funcionan correctamente.

## Cambios Implementados

### 1. Corrección del Registro STAT en `MMU.cpp`

**Problema:** El registro STAT estaba forzando el bit 7 a 1, lo cual no es correcto según Pan Docs.

**Solución:** Se eliminó el forzado del bit 7. El registro STAT ahora preserva correctamente los bits escribibles (3-7) desde la memoria y actualiza dinámicamente los bits de solo lectura (0-2) desde la PPU.

```cpp
// Antes (incorrecto):
uint8_t result = (stat_base & 0xF8) | mode | lyc_match | 0x80;  // Forzaba bit 7

// Después (correcto):
uint8_t result = (stat_base & 0xF8) | mode | lyc_match;  // Preserva bit 7 de memoria
```

### 2. Actualización del Test

Se eliminó la verificación del bit 7 en `test_core_ppu_modes.py`, ya que no debe forzarse.

### 3. Verificación de Implementación

Todos los tests pasan correctamente:
- ✅ `test_ppu_mode_transitions` - Verifica transiciones de modo durante una scanline
- ✅ `test_ppu_vblank_mode` - Verifica que la PPU entra en Modo 1 durante V-Blank
- ✅ `test_ppu_stat_register` - Verifica que el registro STAT se lee correctamente
- ✅ `test_ppu_stat_lyc_coincidence` - Verifica que el bit 2 de STAT se actualiza correctamente

## Estado Actual

### ✅ Lo que Funciona

1. **Máquina de Estados PPU:** Los 4 modos (0-3) se calculan correctamente según los ciclos dentro de la línea
2. **Registro STAT Dinámico:** Se construye correctamente combinando bits escribibles y de solo lectura
3. **Conexión PPU-MMU:** Establecida correctamente en `viboy.py`
4. **Tests:** Todos pasan, validando que la implementación funciona

### ⚠️ Problema Identificado

**Bucle de Polling Infinito Persiste:**

Aunque los tests pasan, el bucle de polling identificado en el Step 0169 aún persiste. El heartbeat muestra `LY=0 | Mode=2` constantemente, lo que sugiere que:

1. La PPU no está avanzando durante el bucle de polling, O
2. El modo no cambia lo suficiente durante el bucle de polling para que el juego lo detecte

**Análisis:**

- El bucle de polling está en `PC: 0x02B2-0x02B6`:
  - `0x02B2 | Opcode: 0xF0` -> `LDH A, (n)` - Lee un registro de hardware (probablemente STAT en 0xFF41)
  - `0x02B4 | Opcode: 0xFE` -> `CP d8` - Compara A con un valor constante
  - `0x02B6 | Opcode: 0x20` -> `JR NZ, e` - Si no son iguales, salta de vuelta

- El juego está esperando que el valor de STAT cambie, pero el heartbeat muestra que siempre es `Mode=2`

**Posibles Causas:**

1. El modo se actualiza al inicio y al final de `step()`, pero si el bucle de polling ejecuta muchas instrucciones pequeñas, el modo podría no cambiar lo suficiente
2. La PPU podría no estar recibiendo los ciclos correctamente durante el bucle de polling
3. El LCD podría estar apagado en algún momento durante el bucle

## Archivos Modificados

- `src/core/cpp/MMU.cpp` - Corrección del registro STAT (eliminado forzado del bit 7)
- `tests/test_core_ppu_modes.py` - Actualización del test (quitada verificación del bit 7)
- `docs/bitacora/entries/2025-12-20__0170__ppu-fase-d-implementacion-modos-ppu-registro-stat.html` - Documentación actualizada

## Próximos Pasos

1. [ ] Investigar por qué la PPU no avanza durante el bucle de polling
2. [ ] Agregar logs temporales para ver qué valor está leyendo el juego del STAT y qué está comparando
3. [ ] Verificar si el modo se actualiza con suficiente frecuencia durante el bucle de polling
4. [ ] Si el deadlock persiste, analizar la traza para identificar qué valor específico del STAT está esperando el juego

## Fuentes Consultadas

- Pan Docs: [LCD Status Register (STAT)](https://gbdev.io/pandocs/LCDC.html#lcd-status-register-stat-ff41)
- Pan Docs: [LCD Timing](https://gbdev.io/pandocs/LCDC.html#lcd-timing)
- Pan Docs: [PPU Modes](https://gbdev.io/pandocs/LCDC.html#ppu-modes)

