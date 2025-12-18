# Hallazgos - Mario Deluxe (mario.gbc)

**Fecha**: 2025-12-17  
**ROM**: mario.gbc (1.0 MB, tipo 0x1B)  
**Título**: MARIO DELUXAHYE

---

## Resumen Ejecutivo

Mario.gbc ejecuta **sin errores de opcodes no implementados**, a diferencia de Tetris DX. El juego activa correctamente el LCD y configura los registros de scroll, lo que sugiere que el emulador está funcionando correctamente para este juego.

---

## Comparación con Tetris DX

| Aspecto | Tetris DX | Mario.gbc |
|---------|-----------|-----------|
| **Opcodes faltantes** | ❌ 0xD9 (RETI), 0x1A (LD A, (DE)), 0x3A (LD A, (HL-)) | ✅ Ninguno |
| **LCDC inicial** | 0x80 (bit 7=1, bit 0=0) | 0x00 → 0x87 (bit 7=1, bit 0=1) |
| **BGP inicial** | 0x00 (todo blanco) | 0xE4 (paleta normal) |
| **Scroll** | SCX=0, SCY=0 | SCX=4, SCY=112 |
| **Estado final PC** | Atascado en inicialización | Avanza correctamente (0xFF87) |

---

## Análisis Detallado

### 1. Ejecución sin Errores

**Prueba realizada**: 1,000,000 ciclos ejecutados  
**Resultado**: ✅ **0 errores de opcodes no implementados**

Esto indica que Mario.gbc utiliza un conjunto de opcodes más básico o que ya están todos implementados en el emulador.

### 2. Activación del LCD

**Cambios detectados en LCDC**:

1. **Ciclo 279,000**: `0x00 → 0x87`
   - Bit 7 (LCD): 0 → 1 ✅ (LCD activado)
   - Bit 0 (BG): 0 → 1 ✅ (Background activado)

2. **Ciclo 298,000**: `0x87 → 0x07`
   - Bit 7 (LCD): 1 → 0 (LCD desactivado temporalmente)
   - Bit 0 (BG): 1 → 1 (Background sigue activo)

3. **Ciclo 521,000**: `0x07 → 0x87`
   - Bit 7 (LCD): 0 → 1 ✅ (LCD reactivado)
   - Bit 0 (BG): 1 → 1 ✅ (Background sigue activo)

**Estado final**: `LCDC = 0x87` (bit 7=1, bit 0=1)
- ✅ LCD activado
- ✅ Background activado
- ✅ Debería renderizar correctamente

### 3. Paleta (BGP)

**Estado**: `BGP = 0xE4` (paleta estándar Game Boy)
- Índice 0: Blanco (0x00)
- Índice 1: Gris claro (0x01)
- Índice 2: Gris oscuro (0x02)
- Índice 3: Negro (0x03)

**Comparación con Tetris DX**: Tetris DX usa `BGP=0x00` (todo blanco), lo que hace que los gráficos sean invisibles aunque se rendericen correctamente.

### 4. Scroll

**Estado final**:
- `SCX = 0x04` (4 píxeles de scroll horizontal)
- `SCY = 0x70` (112 píxeles de scroll vertical)

Esto indica que el juego está usando scroll, lo cual es normal para un juego de plataformas como Mario.

### 5. Progreso de Ejecución

**PC inicial**: `0x0100` (punto de entrada estándar)  
**PC final**: `0xFF87` (después de 1,000,000 ciclos)

El juego avanza correctamente, a diferencia de Tetris DX que se quedaba atascado en la inicialización.

---

## Conclusión

Mario.gbc es un **mejor caso de prueba** que Tetris DX porque:

1. ✅ **No requiere opcodes adicionales** - Todos los opcodes necesarios ya están implementados
2. ✅ **Activa el LCD correctamente** - Escribe `LCDC=0x87` (ambos bits activos)
3. ✅ **Usa paleta normal** - `BGP=0xE4` permite ver los gráficos
4. ✅ **Avanza en ejecución** - No se queda atascado en bucles infinitos

**Recomendación**: Usar Mario.gbc como ROM de referencia para validar el renderizado y el comportamiento general del emulador, mientras que Tetris DX puede usarse para identificar opcodes faltantes.

---

## Próximos Pasos

1. ✅ **Ejecutar con UI** - Verificar que los gráficos se renderizan correctamente
2. ⏳ **Verificar renderizado** - Confirmar que el fondo y los tiles se dibujan correctamente
3. ⏳ **Probar interacciones** - Verificar que el joypad responde correctamente
4. ⏳ **Comparar con Tetris DX** - Entender por qué Tetris DX tiene problemas diferentes

---

## Notas Técnicas

- **Tipo de cartucho**: 0x1B (MBC5 con RAM y batería)
- **Tamaño ROM**: 1024 KB (8 MBits)
- **Tamaño RAM**: Variable (según header)

---

## Comandos de Prueba

```bash
# Ejecutar con monitoreo de registros
python3 test_mario_monitor.py

# Ejecutar con UI
python3 test_mario_ui.py

# Ejecutar con emulador normal
python3 main.py mario.gbc
```

---

**Última actualización**: 2025-12-17

