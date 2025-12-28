# Verificación de Renderizado Visual - Mario.gbc

**Fecha**: 2025-12-17  
**ROM**: mario.gbc  
**Objetivo**: Verificar que el renderizado visual funciona correctamente

---

## Qué Verificar

### 1. Estado de LCDC
- **Esperado**: `LCDC = 0x87` (bit 7=1 LCD ON, bit 0=1 BG ON)
- **Log esperado**: `Render frame: LCDC=0x87 (bit7=1, LCD ON), BGP=0xE4`
- **Si LCDC=0x00 o bit 7=0**: Pantalla blanca (LCD desactivado)

### 2. Estado de BGP (Paleta)
- **Esperado**: `BGP = 0xE4` (paleta estándar Game Boy)
- **Log esperado**: `BGP=0xE4: Paleta estándar Game Boy`
- **Si BGP=0x00**: Pantalla completamente blanca (aunque se rendericen píxeles)

### 3. Logs de Renderizado
Buscar en los logs:
```
INFO: Render frame: LCDC=0x87 (bit7=1, LCD ON), BGP=0xE4
INFO: HACK EDUCATIVO: Ignorando Bit 0 de LCDC para compatibilidad con juegos CGB (LCDC=0x80)
INFO: DIAGNÓSTICO VRAM/Tilemap: Tilemap[0:16]=['XX', 'XX', ...]... (tiles no-0: X/16), VRAM[0x8000:0x8020]=X bytes no-0, VRAM[0x9000:0x9020]=X bytes no-0
```

### 4. Diagnóstico VRAM/Tilemap
- **Tilemap no-0**: Debe haber tiles en el tilemap (no todos ceros)
- **VRAM bytes no-0**: Debe haber datos de tiles en VRAM
- **Si VRAM está vacío**: Los tiles no se han cargado aún → pantalla blanca/negro

### 5. Scroll
- **Esperado**: `SCX` y `SCY` pueden tener valores (ej: SCX=4, SCY=112)
- **Log esperado**: `Scroll: SCX=0x04 (4), SCY=0x70 (112)`

---

## Qué Deberías Ver en la Ventana

### Escenario 1: Renderizado Correcto ✅
- **Ventana**: Gráficos visibles (fondo, tiles, posiblemente sprites)
- **Colores**: Escala de grises (blanco, gris claro, gris oscuro, negro)
- **Movimiento**: Posible scroll o animación si el juego está avanzando

### Escenario 2: Pantalla Blanca ⚪
- **Causa posible 1**: LCDC bit 7=0 (LCD desactivado)
- **Causa posible 2**: BGP=0x00 (paleta completamente blanca)
- **Causa posible 3**: VRAM vacío (tiles no cargados)
- **Causa posible 4**: Tilemap vacío (no hay tiles que dibujar)

### Escenario 3: Pantalla Negra ⚫
- **Causa posible**: BGP=0xFF (paleta completamente negra) o VRAM con datos pero tilemap incorrecto

---

## Comandos para Verificar

### Opción 1: Ejecutar con script de verificación
```bash
python3 verificar_renderizado_mario.py
```

### Opción 2: Ejecutar directamente
```bash
python3 main.py mario.gbc
```

### Opción 3: Capturar solo logs de renderizado
```bash
python3 main.py mario.gbc 2>&1 | grep -E "(Render|LCDC|BGP|DIAGNÓSTICO|V-Blank|Scroll)"
```

---

## Interpretación de Logs

### Log de Renderizado Exitoso
```
INFO: V-Blank: LY=144, LCDC=0x87, BGP=0xE4, IE=0xXX, IF=0xXX - Renderizando
INFO: Render frame: LCDC=0x87 (bit7=1, LCD ON), BGP=0xE4
INFO: HACK EDUCATIVO: Ignorando Bit 0 de LCDC para compatibilidad con juegos CGB (LCDC=0x80)
INFO: Scroll: SCX=0x04 (4), SCY=0x70 (112)
INFO: DIAGNÓSTICO VRAM/Tilemap: Tilemap[0:16]=['06', '06', ...]... (tiles no-0: 16/16), VRAM[0x8000:0x8020]=X bytes no-0, VRAM[0x9000:0x9020]=X bytes no-0
```
**Interpretación**: ✅ Renderizado funcionando correctamente

### Log de LCD Desactivado
```
INFO: V-Blank: LY=144, LCDC=0x00, BGP=0xE4, IE=0xXX, IF=0xXX - Pantalla blanca
INFO: Render frame: LCDC=0x00 (bit7=0, LCD OFF), BGP=0xE4
INFO: LCDC: LCD desactivado (bit 7=0), pantalla blanca - 0 tiles dibujados
```
**Interpretación**: ⚠️ LCD desactivado, esperar a que el juego lo active

### Log de BGP Blanco
```
WARNING: BGP=0x00: Paleta completamente blanca - pantalla aparecerá toda blanca
INFO: Render frame: LCDC=0x87 (bit7=1, LCD ON), BGP=0x00
```
**Interpretación**: ⚠️ Paleta blanca, aunque se rendericen píxeles serán invisibles

### Log de VRAM Vacío
```
INFO: DIAGNÓSTICO VRAM/Tilemap: Tilemap[0:16]=['06', '06', ...]... (tiles no-0: 16/16), VRAM[0x8000:0x8020]=0 bytes no-0, VRAM[0x9000:0x9020]=0 bytes no-0
```
**Interpretación**: ⚠️ Tilemap tiene referencias pero VRAM está vacío → tiles no cargados aún

---

## Checklist de Verificación

- [ ] El emulador se ejecuta sin errores
- [ ] La ventana Pygame se abre correctamente
- [ ] LCDC se activa (bit 7=1) durante la ejecución
- [ ] BGP está en paleta normal (0xE4, no 0x00)
- [ ] Los logs muestran "Renderizando" durante V-Blank
- [ ] El diagnóstico VRAM muestra datos de tiles
- [ ] La ventana muestra gráficos (no solo blanco/negro)
- [ ] Los gráficos tienen colores correctos (escala de grises)

---

## Próximos Pasos si el Renderizado No Funciona

1. **Verificar logs de diagnóstico VRAM**: Si VRAM está vacío, el juego no ha cargado tiles aún
2. **Verificar timing**: El juego puede necesitar más ciclos para cargar gráficos
3. **Verificar inicialización**: Algunos juegos cargan gráficos después de la inicialización
4. **Comparar con Tetris DX**: Ver si el problema es específico de Mario.gbc o general

---

**Última actualización**: 2025-12-17

