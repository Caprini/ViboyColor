#!/usr/bin/env python3
"""
Script para convertir una imagen PNG a formato de header de cartucho de Game Boy.

El logo de Nintendo en el header del cartucho (0x0104-0x0133) son 48 bytes
que representan 48x8 píxeles en formato 1-bit (1 bit por píxel).

Formato:
- 48 bytes = 48 columnas x 8 filas
- Cada byte representa 8 píxeles verticales (1 bit por píxel)
- Bit 7 = píxel superior, Bit 0 = píxel inferior
- 0 = blanco/transparente, 1 = negro/visible

Fuente: Pan Docs - "Nintendo Logo", Cart Header (0x0104-0x0133)
"""

from PIL import Image
import sys
from pathlib import Path

def image_to_gb_logo_header(image_path: str, output_cpp: bool = True) -> str:
    """
    Convierte una imagen PNG a un array de 48 bytes para el header del cartucho.
    
    Args:
        image_path: Ruta a la imagen PNG
        output_cpp: Si es True, genera código C++. Si False, solo muestra los bytes.
    
    Returns:
        String con el código C++ o los bytes en formato hexadecimal
    """
    try:
        # Abrir la imagen
        img = Image.open(image_path)
        print(f"Imagen original cargada: {img.size} píxeles, modo: {img.mode}")
        
        # Redimensionar a 48x8 (ancho x alto)
        # Usamos LANCZOS para mejor calidad en el downscale
        img_resized = img.resize((48, 8), Image.Resampling.LANCZOS)
        print(f"Imagen redimensionada: {img_resized.size} píxeles")
        
        # Convertir a escala de grises si no lo está
        if img_resized.mode != 'L':
            img_gray = img_resized.convert('L')
        else:
            img_gray = img_resized
        
        # Convertir a 1-bit (blanco y negro) usando umbral
        # Umbral: píxeles más oscuros que 128 se convierten a negro (1), 
        # píxeles más claros a blanco (0)
        img_1bit = img_gray.point(lambda x: 0 if x > 128 else 255, mode='1')
        
        # Guardar versión de referencia (opcional, para debugging)
        debug_path = Path(image_path).parent / "viboy_logo_48x8_debug.png"
        img_1bit.save(debug_path)
        print(f"Versión 48x8 guardada en: {debug_path}")
        
        # Obtener los píxeles como lista
        pixels = list(img_1bit.getdata())
        
        # El formato del header es:
        # - 48 bytes = 48 columnas
        # - Cada byte representa 8 píxeles verticales (1 bit por píxel)
        # - Bit 7 = píxel superior (fila 0), Bit 0 = píxel inferior (fila 7)
        # - 0 en PIL '1' mode = negro (255), 1 = blanco (0)
        # - En Game Boy: 1 = visible/negro, 0 = transparente/blanco
        
        header_data = bytearray(48)
        
        # Para cada columna (0-47)
        for col in range(48):
            byte_value = 0
            # Para cada fila (0-7), desde arriba hacia abajo
            for row in range(8):
                # Calcular índice del píxel en la lista plana
                pixel_index = row * 48 + col
                if pixel_index < len(pixels):
                    # En modo '1' de PIL: 0 = negro, 255 = blanco
                    # Pero en realidad, getdata() devuelve 0 para negro y 255 para blanco
                    # Necesitamos invertir: si el píxel es negro (0), poner el bit a 1
                    pixel_value = pixels[pixel_index]
                    if pixel_value == 0:  # Negro en PIL
                        # Bit 7-row: bit más significativo para la fila superior
                        byte_value |= (1 << (7 - row))
            
            header_data[col] = byte_value
        
        # Formatear para C++
        if output_cpp:
            cpp_array = "// --- Logo Personalizado 'Viboy Color' (48x8 píxeles, formato 1bpp) ---\n"
            cpp_array += "// Convertido desde: " + str(Path(image_path).name) + "\n"
            cpp_array += "// Formato: 48 bytes = 48 columnas x 8 filas (1 bit por píxel)\n"
            cpp_array += "// Bit 7 = píxel superior, Bit 0 = píxel inferior\n"
            cpp_array += "// 1 = visible/negro, 0 = transparente/blanco\n"
            cpp_array += "static const uint8_t VIBOY_LOGO_HEADER_DATA[48] = {\n    "
            
            for i, byte in enumerate(header_data):
                cpp_array += f"0x{byte:02X}, "
                if (i + 1) % 12 == 0:
                    cpp_array += "\n    "
            
            cpp_array = cpp_array.rstrip(", \n    ") + "\n};"
            return cpp_array
        else:
            # Solo mostrar los bytes en formato hexadecimal
            hex_string = " ".join(f"{b:02X}" for b in header_data)
            return hex_string
            
    except FileNotFoundError:
        return f"Error: No se encontró el archivo en la ruta: {image_path}"
    except Exception as e:
        return f"Error al procesar la imagen: {e}"


if __name__ == "__main__":
    # Ruta por defecto
    default_path = "assets/svg viboycolor logo.png"
    
    # Permitir pasar la ruta como argumento
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        image_path = default_path
    
    # Verificar que el archivo existe
    if not Path(image_path).exists():
        print(f"Error: No se encontró el archivo: {image_path}")
        print(f"Buscando en: {Path(image_path).absolute()}")
        sys.exit(1)
    
    # Convertir
    print(f"Convirtiendo: {image_path}")
    print("-" * 60)
    
    result = image_to_gb_logo_header(image_path, output_cpp=True)
    
    print("\n" + "=" * 60)
    print("ARRAY C++ GENERADO:")
    print("=" * 60)
    print(result)
    print("=" * 60)
    
    # Guardar también en un archivo
    output_file = Path("tools") / "viboy_logo_header.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(result)
    
    print(f"\nArray guardado también en: {output_file}")

