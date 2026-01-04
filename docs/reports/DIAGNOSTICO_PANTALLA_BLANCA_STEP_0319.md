# Diagnóstico de Pantalla Blanca - Step 0319

**Fecha**: 2025-12-27  
**Step ID**: 0319  
**Problema**: Pantalla completamente blanca con todas las ROMs (pkmn.gb, tetris.gb, mario.gbc)

---

## Resumen del Problema

Aunque el módulo C++ está compilado y `load_test_tiles()` se ejecuta correctamente, el emulador muestra pantalla completamente blanca con todas las ROMs probadas.

---

## Verificaciones Realizadas

### 1. Módulo C++ Compilado ✅
- ✅ Módulo `viboy_core.cpython-312-x86_64-linux-gnu.so` generado correctamente
- ✅ Módulo se importa sin errores
- ✅ Todos los componentes C++ (PyMMU, PyPPU, etc.) están disponibles

### 2. `load_test_tiles()` Funciona ✅
- ✅ Se ejecuta correctamente cuando se carga la ROM
- ✅ Carga tiles de prueba en VRAM (0x8000-0x803F)
- ✅ Configura LCDC a 0x99 (LCD Enable + BG Display + Unsigned addressing)
- ✅ Configura Tile Map básico en 0x9800-0x9BFF

### 3. Framebuffer Disponible ✅
- ✅ Framebuffer tiene 23040 bytes (160x144 píxeles)
- ⚠️ **PROBLEMA**: Framebuffer está completamente vacío (todos los píxeles son 0 = blanco)

---

## Análisis del Problema

### Causa Raíz Identificada

El framebuffer está vacío porque la PPU no está renderizando. Posibles causas:

1. **LCDC Sobrescrito por el Juego**: Aunque `load_test_tiles()` configura LCDC a 0x99, el juego puede estar ejecutando código que:
   - Desactiva el LCD (LCDC bit 7 = 0)
   - Desactiva el BG Display (LCDC bit 0 = 0)
   - Cambia el modo de direccionamiento de tiles

2. **PPU No Renderiza**: La PPU verifica si el LCD está encendido antes de renderizar:
   ```cpp
   uint8_t lcdc = mmu_->read(IO_LCDC);
   bool lcd_enabled = (lcdc & 0x80) != 0;
   if (!lcd_enabled) {
       return;  // No renderiza si LCD está apagado
   }
   ```

3. **Timing del Renderizado**: `load_test_tiles()` se ejecuta ANTES de que el juego comience a ejecutarse. El juego puede estar:
   - Desactivando el LCD durante la inicialización
   - Cambiando LCDC después de que se cargan los tiles
   - Ejecutando código que limpia VRAM

---

## Logs Distintos Entre Juegos

El usuario reporta que los logs son distintos entre Pokémon y Tetris. Esto sugiere que:
- Cada juego ejecuta código de inicialización diferente
- Cada juego puede estar configurando LCDC de manera diferente
- Cada juego puede estar accediendo a VRAM de manera diferente

---

## Próximos Pasos de Diagnóstico

### 1. Verificar LCDC Durante la Ejecución
Agregar logs para verificar el valor de LCDC durante la ejecución:
- Al inicio de cada frame
- Cuando se escribe en LCDC (0xFF40)
- Cuando la PPU intenta renderizar

### 2. Verificar Estado de VRAM
Agregar logs para verificar que los tiles siguen en VRAM después de que el juego comienza:
- Verificar que los tiles de prueba no fueron sobrescritos
- Verificar que el Tile Map sigue configurado correctamente

### 3. Verificar Renderizado de PPU
Agregar logs en `render_scanline()` para verificar:
- Si se está llamando `render_scanline()`
- Si el LCD está encendido cuando se intenta renderizar
- Si el BG Display está activado cuando se intenta renderizar
- Qué valores tiene LCDC cuando se intenta renderizar

### 4. Verificar Timing
Verificar que:
- La PPU está avanzando correctamente (LY incrementa)
- Los frames se están completando (154 scanlines)
- El framebuffer se está actualizando

---

## Soluciones Propuestas

### Solución 1: Forzar LCDC en Cada Frame (Temporal)
Modificar `render_scanline()` para forzar LCDC a 0x99 temporalmente durante el renderizado:
```cpp
// Forzar LCDC temporalmente solo para renderizado
uint8_t original_lcdc = mmu_->read(IO_LCDC);
uint8_t forced_lcdc = original_lcdc | 0x99;  // Forzar bits 7, 4, 3, 0
// Usar forced_lcdc para el renderizado
```

**Ventajas**: Permite ver los tiles de prueba inmediatamente  
**Desventajas**: No es emulación precisa, puede causar problemas con juegos reales

### Solución 2: Esperar a que el Juego Active el LCD
Modificar el bucle principal para esperar a que el juego active el LCD antes de renderizar:
- No renderizar hasta que LCDC bit 7 = 1
- Esperar a que el juego configure LCDC correctamente

**Ventajas**: Emulación más precisa  
**Desventajas**: Puede requerir esperar varios frames

### Solución 3: Investigar Inicialización del Juego
Investigar por qué los juegos no están activando el LCD:
- Verificar si falta implementar alguna instrucción de CPU
- Verificar si falta implementar alguna interrupción
- Verificar si el juego está esperando algún estado específico

**Ventajas**: Solución correcta a largo plazo  
**Desventajas**: Requiere más investigación

---

## Archivos a Modificar

1. `src/core/cpp/PPU.cpp`: Agregar logs de diagnóstico en `render_scanline()`
2. `src/core/cpp/MMU.cpp`: Agregar logs cuando se escribe en LCDC (0xFF40)
3. `src/viboy.py`: Agregar logs para verificar estado de LCDC durante la ejecución

---

## Referencias

- Pan Docs - LCD Control Register (LCDC)
- Pan Docs - LCD Timing
- Step 0313: Corrección de LCDC en `load_test_tiles()`
- Step 0318: Identificación del problema de pantalla blanca

