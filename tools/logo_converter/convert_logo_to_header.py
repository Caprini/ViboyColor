#!/usr/bin/env python3
"""
Script para convertir una imagen PNG a formato de header de cartucho de Game Boy
y a formato de Tile (2bpp) para VRAM.

El logo de Nintendo en el header del cartucho (0x0104-0x0133) son 48 bytes
que representan 48x8 píxeles en formato 1-bit (1 bit por píxel).

Formato Header:
- 48 bytes = 48 columnas x 8 filas
- Cada byte representa 8 píxeles verticales (1 bit por píxel)
- Bit 7 = píxel superior, Bit 0 = píxel inferior
- 0 = blanco/transparente, 1 = negro/visible

Formato Tile (2bpp) para VRAM:
- 48x8 píxeles = 6 tiles de 8x8
- Cada tile ocupa 16 bytes (2 bytes por fila, 8 filas)
- Total: 96 bytes para los 6 tiles
- Cada píxel usa 2 bits (4 colores posibles)

Fuente: Pan Docs - "Nintendo Logo", Cart Header (0x0104-0x0133)
Fuente: Pan Docs - "Tile Data", "Tile Map"
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


def image_to_gb_tiles(image_path: str) -> tuple[str, str]:
    """
    Convierte una imagen PNG a formato de Tile (2bpp) y Tilemap para VRAM.
    
    Args:
        image_path: Ruta a la imagen PNG (debe ser 48x8 píxeles)
    
    Returns:
        Tupla (tile_data_cpp, tile_map_cpp) con los arrays C++ generados
    """
    try:
        img = Image.open(image_path).convert('1')  # B/N
    except Exception as e:
        print(f"Error abriendo imagen: {e}")
        return "", ""

    width, height = img.size
    if width != 48 or height != 8:
        print(f"Error: La imagen debe ser 48x8. Actual: {width}x{height}")
        return "", ""

    pixels = list(img.getdata())
    
    # 1. Generar Tile Data (2bpp)
    # El logo son 6 tiles de 8x8.
    tile_data_cpp = "// --- Logo Personalizado 'Viboy Color' (48x8 píxeles, formato 2bpp) ---\n"
    tile_data_cpp += "// Convertido desde: " + str(Path(image_path).name) + "\n"
    tile_data_cpp += "// Formato: 6 tiles de 8x8 = 96 bytes (16 bytes por tile)\n"
    tile_data_cpp += "// Cada tile: 2 bytes por fila (LSB y MSB), 8 filas\n"
    tile_data_cpp += "// Color 0 (00) = Blanco, Color 3 (11) = Negro\n"
    tile_data_cpp += "static const uint8_t VIBOY_LOGO_TILES[96] = {\n    "
    byte_count = 0
    
    for tile_idx in range(6):  # 6 tiles
        for row in range(8):  # 8 filas por tile
            byte1 = 0  # LSB
            byte2 = 0  # MSB
            for col in range(8):  # 8 pixels por fila
                x = tile_idx * 8 + col
                y = row
                pixel = pixels[y * 48 + x]
                
                # Pixel 0 (Negro) -> Color 3 (11 binary) en GB
                # Pixel 255 (Blanco) -> Color 0 (00 binary) en GB
                if pixel == 0:  # Negro
                    mask = 1 << (7 - col)
                    byte1 |= mask  # Bit LSB
                    byte2 |= mask  # Bit MSB
            
            tile_data_cpp += f"0x{byte1:02X}, 0x{byte2:02X}, "
            byte_count += 2
            if byte_count % 16 == 0:
                tile_data_cpp += "\n    "
    
    tile_data_cpp = tile_data_cpp.rstrip(", \n    ") + "\n};\n"

    # 2. Generar Tilemap (Fila única)
    # Mapea los tiles 0x01 a 0x06 en secuencia
    tile_map_cpp = "// --- Tilemap del Logo (32 bytes = 1 fila del mapa de tiles) ---\n"
    tile_map_cpp += "// Centrado horizontalmente: 7 tiles de padding, 6 tiles del logo, resto padding\n"
    tile_map_cpp += "static const uint8_t VIBOY_LOGO_MAP[32] = {\n    "
    
    # Rellenar con 0 (blanco) hasta la posición, luego los tiles 1-6, luego 0.
    map_bytes = [0] * 32
    start_pos = 7  # Posición horizontal para centrar
    for i in range(6):
        map_bytes[start_pos + i] = i + 1  # Tiles empiezan en ID 1 (el 0 suele ser blanco)
        
    for i, val in enumerate(map_bytes):
        tile_map_cpp += f"0x{val:02X}, "
        if (i + 1) % 16 == 0:
            tile_map_cpp += "\n    "
            
    tile_map_cpp = tile_map_cpp.rstrip(", \n    ") + "\n};"

    return tile_data_cpp, tile_map_cpp


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
    
    # Convertir a formato Header (1bpp)
    print(f"Convirtiendo a formato Header (1bpp): {image_path}")
    print("-" * 60)
    
    result_header = image_to_gb_logo_header(image_path, output_cpp=True)
    
    print("\n" + "=" * 60)
    print("ARRAY C++ HEADER (1bpp) GENERADO:")
    print("=" * 60)
    print(result_header)
    print("=" * 60)
    
    # Convertir a formato Tile (2bpp) y Tilemap
    print("\n" + "=" * 60)
    print("Convirtiendo a formato Tile (2bpp) y Tilemap:")
    print("=" * 60)
    
    # Usar la imagen debug si existe, sino la original
    debug_path = Path(image_path).parent / "viboy_logo_48x8_debug.png"
    if debug_path.exists():
        tile_image_path = str(debug_path)
    else:
        tile_image_path = image_path
    
    tile_data, tile_map = image_to_gb_tiles(tile_image_path)
    
    print("\n" + "=" * 60)
    print("ARRAYS C++ TILE DATA Y TILEMAP GENERADOS:")
    print("=" * 60)
    print(tile_data)
    print(tile_map)
    print("=" * 60)
    
    # Guardar también en archivos
    output_file_header = Path("tools") / "viboy_logo_header.txt"
    with open(output_file_header, "w", encoding="utf-8") as f:
        f.write(result_header)
    
    output_file_tiles = Path("tools") / "viboy_logo_tiles.txt"
    with open(output_file_tiles, "w", encoding="utf-8") as f:
        f.write(tile_data)
        f.write("\n")
        f.write(tile_map)
    
    print(f"\nArray Header guardado en: {output_file_header}")
    print(f"Arrays Tile y Tilemap guardados en: {output_file_tiles}")

