# Logo Converter para Game Boy Header

Este directorio contiene herramientas para convertir imágenes PNG a formato de header de cartucho de Game Boy.

## Descripción

El script `convert_logo_to_header.py` convierte una imagen PNG a un array de 48 bytes compatible con el formato del logo de Nintendo en el header del cartucho de Game Boy (direcciones 0x0104-0x0133).

## Formato del Logo

El logo de Nintendo en el header del cartucho son **48 bytes** que representan **48x8 píxeles** en formato **1-bit** (1 bit por píxel):

- **48 bytes** = 48 columnas × 8 filas
- Cada byte representa 8 píxeles verticales (1 bit por píxel)
- **Bit 7** = píxel superior, **Bit 0** = píxel inferior
- **0** = blanco/transparente, **1** = negro/visible

## Uso

### Requisitos

- Python 3.10+
- Pillow (PIL): `pip install Pillow`

### Ejecución

```bash
# Usar la ruta por defecto (assets/svg viboycolor logo.png)
python tools/logo_converter/convert_logo_to_header.py

# O especificar una imagen personalizada
python tools/logo_converter/convert_logo_to_header.py ruta/a/tu/imagen.png
```

### Salida

El script genera:

1. **Array C++** en la consola con el formato correcto para usar en `MMU.cpp`
2. **Archivo de texto** en `tools/viboy_logo_header.txt` con el array
3. **Imagen de debug** en `assets/viboy_logo_48x8_debug.png` para verificar el resultado visual

## Ejemplo de Salida

```cpp
// --- Logo Personalizado 'Viboy Color' (48x8 píxeles, formato 1bpp) ---
// Convertido desde: svg viboycolor logo.png
// Formato: 48 bytes = 48 columnas x 8 filas (1 bit por píxel)
// Bit 7 = píxel superior, Bit 0 = píxel inferior
// 1 = visible/negro, 0 = transparente/blanco
static const uint8_t VIBOY_LOGO_HEADER_DATA[48] = {
    0xF7, 0xC3, 0x9D, 0xBD, 0xBE, 0x7E, 0x6E, 0x76, 0x66, 0x7E, 0x66, 0x7E, 
    0x66, 0x66, 0x7E, 0x66, 0x7E, 0x6E, 0x66, 0x6E, 0x66, 0x6E, 0x7E, 0x7E, 
    0x66, 0x6E, 0x7E, 0x7E, 0x66, 0x7E, 0x66, 0x7E, 0x66, 0x7E, 0x7E, 0x66, 
    0x7E, 0x6E, 0x76, 0x66, 0x66, 0x66, 0x7E, 0xBE, 0xBD, 0x9D, 0xC3, 0xE7
};
```

## Integración en el Código

Una vez generado el array, cópialo y reemplázalo en `src/core/cpp/MMU.cpp`:

```cpp
static const uint8_t VIBOY_LOGO_HEADER_DATA[48] = {
    // ... tu array aquí ...
};
```

Luego recompila el módulo C++:

```bash
python setup.py build_ext --inplace
# O usando el script de PowerShell:
.\rebuild_cpp.ps1
```

## Notas Técnicas

### Mecanismo Antipiratería de Nintendo

El logo de Nintendo en el encabezado del cartucho (0x0104-0x0133) no es solo decorativo. La Boot ROM oficial compara estos 48 bytes con los datos que copia a la VRAM. Si no coinciden, el sistema se congela, impidiendo que juegos no autorizados se ejecuten. Este es uno de los primeros mecanismos antipiratería de la industria de los videojuegos.

### Proceso de Conversión

1. **Redimensionamiento**: La imagen se redimensiona a 48×8 píxeles usando el algoritmo LANCZOS para mejor calidad.
2. **Escala de Grises**: Se convierte a escala de grises si no lo está.
3. **Binarización**: Se convierte a 1-bit usando un umbral de 128 (píxeles más oscuros = negro, más claros = blanco).
4. **Codificación**: Cada columna de 8 píxeles se codifica en un byte, donde el bit 7 representa el píxel superior y el bit 0 el inferior.

### Recomendaciones

- Para mejores resultados, diseña el logo directamente en una cuadrícula de 48×8 píxeles
- Usa alto contraste (blanco y negro puro) para evitar artefactos en la conversión
- Verifica el resultado visual usando la imagen de debug generada

## Fuentes

- **Pan Docs**: ["Nintendo Logo", Cart Header (0x0104-0x0133)](https://gbdev.io/pandocs/#the-cartridge-header)
- **Pan Docs**: ["Boot ROM Behavior"](https://gbdev.io/pandocs/#boot-rom)

## Licencia

Este script es parte del proyecto Viboy Color y está bajo la misma licencia del proyecto.

