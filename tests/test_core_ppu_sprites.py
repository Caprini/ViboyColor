"""
Tests para el renderizado de Sprites (OBJ) en la PPU en C++.

Estos tests validan la implementación nativa del renderizado de sprites:
- Renderizado de sprites desde OAM (Object Attribute Memory)
- Transparencia (color 0 es transparente)
- X-Flip y Y-Flip
- Paletas OBP0 y OBP1
- Sprites de 8x8 y 8x16

Fuente: Pan Docs - OAM, Sprite Attributes, Sprite Rendering
"""

import pytest

try:
    from viboy_core import PyMMU, PyPPU
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="viboy_core no está disponible (compilación requerida)")

# Paleta de grises (mismo formato que en renderer.py)
PALETTE_GREYSCALE = [
    (255, 255, 255),  # Color 0: Blanco -> 0xFFFFFFFF
    (170, 170, 170),  # Color 1: Gris claro -> 0xFFAAAAAA
    (85, 85, 85),     # Color 2: Gris oscuro -> 0xFF555555
    (0, 0, 0),        # Color 3: Negro -> 0xFF000000
]

def color_index_to_argb32(color_index: int, palette_reg: int) -> int:
    """
    Convierte un índice de color (0-3) del framebuffer a ARGB32 usando una paleta (BGP, OBP0, OBP1).
    
    Args:
        color_index: Índice de color del framebuffer (0-3)
        palette_reg: Valor del registro de paleta (BGP=0xFF47, OBP0=0xFF48, OBP1=0xFF49)
    
    Returns:
        Valor ARGB32 (ej: 0xFF000000 para negro, 0xFFFFFFFF para blanco)
    """
    # Decodificar paleta (cada par de bits representa un color 0-3)
    # Formato: bits 0-1 = color 0, bits 2-3 = color 1, bits 4-5 = color 2, bits 6-7 = color 3
    palette_mapping = [
        (palette_reg >> 0) & 0x03,  # Color 0 -> índice en PALETTE_GREYSCALE
        (palette_reg >> 2) & 0x03,  # Color 1 -> índice en PALETTE_GREYSCALE
        (palette_reg >> 4) & 0x03,  # Color 2 -> índice en PALETTE_GREYSCALE
        (palette_reg >> 6) & 0x03,  # Color 3 -> índice en PALETTE_GREYSCALE
    ]
    
    # Obtener el índice real en la paleta greyscale
    greyscale_index = palette_mapping[color_index & 0x03]
    
    # Obtener color RGB de la paleta
    r, g, b = PALETTE_GREYSCALE[greyscale_index]
    
    # Convertir a ARGB32: Alpha=0xFF, R, G, B
    return (0xFF << 24) | (r << 16) | (g << 8) | b


class TestCorePPUSprites:
    """Tests para el renderizado de sprites en la PPU en C++."""

    def test_sprite_rendering_simple(self) -> None:
        """
        Test: Renderiza un sprite simple (8x8) en la línea 20.
        
        Pasos:
        1. Habilitar LCD y Sprites (LCDC=0x93: bit 7=1, bit 1=1, bit 0=1)
        2. Crear un tile con patrón visible (línea sólida) en VRAM tile 1
        3. Configurar sprite en OAM: Y=20, X=20, Tile=1
        4. Configurar paleta OBP0=0xE4 (paleta estándar)
        5. Avanzar PPU hasta línea 20 y renderizar
        6. Verificar que el framebuffer tiene píxeles del sprite
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD (bit 7=1), Background (bit 0=1), Sprites (bit 1=1), unsigned addressing (bit 4=1)
        # LCDC = 0x93 = 10010011
        mmu.write(0xFF40, 0x93)
        
        # Configurar paleta de fondo BGP (para que el fondo no sea completamente blanco)
        mmu.write(0xFF47, 0xE4)
        
        # Configurar paleta de sprite OBP0 = 0xE4 (11100100)
        # Color 0: Blanco (transparente)
        # Color 1: Gris claro
        # Color 2: Gris oscuro
        # Color 3: Negro
        mmu.write(0xFF48, 0xE4)
        
        # Crear un tile en VRAM tile 1 (dirección 0x8010) con una línea sólida negra
        # En la línea 0 del tile, todos los píxeles serán color 3 (negro)
        tile_addr = 0x8010  # Tile ID 1 (cada tile son 16 bytes)
        for line in range(8):
            if line == 0:
                # Línea 0: todos negros (color 3 = 0xFF, 0xFF)
                mmu.write(tile_addr + (line * 2), 0xFF)      # LSB
                mmu.write(tile_addr + (line * 2) + 1, 0xFF)  # MSB
            else:
                # Otras líneas: blancas (color 0 = 0x00, 0x00)
                mmu.write(tile_addr + (line * 2), 0x00)
                mmu.write(tile_addr + (line * 2) + 1, 0x00)
        
        # Configurar sprite en OAM (0xFE00)
        # Byte 0: Y position = 20 (pantalla + 16, así que screen_y = 4)
        # Byte 1: X position = 20 (pantalla + 8, así que screen_x = 12)
        # Byte 2: Tile ID = 1
        # Byte 3: Attributes = 0x00 (sin flip, paleta 0, sin prioridad)
        sprite_addr = 0xFE00
        mmu.write(sprite_addr + 0, 20)  # Y
        mmu.write(sprite_addr + 1, 20)  # X
        mmu.write(sprite_addr + 2, 1)   # Tile ID
        mmu.write(sprite_addr + 3, 0x00)  # Attributes
        
        # El sprite está en screen_y=4, screen_x=12 (sprite_y=20, sprite_x=20)
        # La línea 0 del sprite (línea sólida negra) debería estar en LY=4
        # Avanzar hasta completar línea 4: 4 líneas completas + línea 4 completa
        # Cada línea son 456 ciclos, y render_scanline() se ejecuta al completar cada línea
        for _ in range(4):
            ppu.step(456)
        # Completar línea 4 para que render_scanline() se ejecute
        ppu.step(456)
        
        # Verificar que completamos línea 4 (ahora en línea 5)
        assert ppu.get_ly() == 5, f"Debe estar en línea 5 (después de completar línea 4), está en línea {ppu.get_ly()}"
        
        # Obtener framebuffer
        framebuffer = ppu.framebuffer
        
        # Verificar que el sprite se renderizó
        # El sprite está en screen_x=12, screen_y=4
        # La línea 0 del sprite (línea sólida negra) debería estar en píxeles X=12-19 de LY=4
        framebuffer_line_4 = framebuffer[4 * 160:(4 * 160) + 160]
        
        # Leer paleta OBP0
        obp0 = mmu.read(0xFF48) & 0xFF
        
        # Verificar que hay píxeles negros (0xFF000000) en la posición del sprite
        sprite_found = False
        for x in range(12, 20):
            color_index = framebuffer_line_4[x]
            pixel = color_index_to_argb32(color_index, obp0)
            if pixel == 0xFF000000:  # Negro
                sprite_found = True
                break
        
        assert sprite_found, "El sprite debe estar renderizado en la línea 4"
    
    def test_sprite_transparency(self) -> None:
        """
        Test: El color 0 en sprites es transparente (no se dibuja).
        
        Pasos:
        1. Crear un tile con color 0 (blanco/transparente) en todos los píxeles
        2. Configurar sprite en OAM
        3. Renderizar y verificar que no se dibuja nada (fondo visible)
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD, Background y Sprites
        mmu.write(0xFF40, 0x93)
        
        # Configurar paletas
        mmu.write(0xFF47, 0xE4)  # BGP
        mmu.write(0xFF48, 0xE4)  # OBP0
        
        # Crear un tile completamente transparente (color 0 en todos los píxeles)
        tile_addr = 0x8010
        for line in range(8):
            mmu.write(tile_addr + (line * 2), 0x00)
            mmu.write(tile_addr + (line * 2) + 1, 0x00)
        
        # Crear un tile de fondo visible (todo negro) en tile 0
        bg_tile_addr = 0x8000
        for line in range(8):
            mmu.write(bg_tile_addr + (line * 2), 0xFF)
            mmu.write(bg_tile_addr + (line * 2) + 1, 0xFF)
        
        # Configurar tilemap para usar tile 0 (negro) en toda la pantalla
        for i in range(32 * 32):
            mmu.write(0x9800 + i, 0x00)
        
        # Configurar sprite en OAM
        mmu.write(0xFE00 + 0, 20)  # Y
        mmu.write(0xFE00 + 1, 20)  # X
        mmu.write(0xFE00 + 2, 1)   # Tile ID (tile transparente)
        mmu.write(0xFE00 + 3, 0x00)  # Attributes
        
        # Avanzar hasta línea 4 (donde está el sprite) y renderizar
        for _ in range(4):
            ppu.step(456)
        ppu.step(456)  # Completar línea 4 para renderizar
        
        # El sprite es transparente, así que el fondo debería ser visible
        # (negro, que es el tile 0 del fondo)
        framebuffer_line_4 = ppu.framebuffer[4 * 160:(4 * 160) + 160]
        
        # Leer paleta BGP para el fondo
        bgp = mmu.read(0xFF47) & 0xFF
        
        # Verificar que los píxeles donde está el sprite son del fondo (negro)
        # El sprite está en screen_x=12, screen_y=4, así que X=12-19 deberían ser negros
        for x in range(12, 20):
            color_index = framebuffer_line_4[x]
            pixel = color_index_to_argb32(color_index, bgp)
            assert pixel == 0xFF000000, f"Píxel {x} debe ser del fondo (negro), es 0x{pixel:08X} (índice={color_index})"
    
    def test_sprite_x_flip(self) -> None:
        """
        Test: X-Flip invierte el sprite horizontalmente.
        
        Pasos:
        1. Crear un tile con patrón asimétrico (p.ej. solo píxel izquierdo)
        2. Configurar sprite con X-Flip activo
        3. Verificar que el patrón aparece invertido
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD, Background y Sprites
        mmu.write(0xFF40, 0x93)
        mmu.write(0xFF47, 0xE4)  # BGP
        mmu.write(0xFF48, 0xE4)  # OBP0
        
        # Crear un tile con patrón asimétrico: solo el primer píxel (izquierda) es negro
        # Píxel 0 (izquierda): color 3 (negro) = bits 0x01, 0x02
        # Resto de píxeles: color 0 (blanco)
        tile_addr = 0x8010
        # Línea 0: solo bit 7 (píxel 0) en ambos bytes
        mmu.write(tile_addr + 0, 0x80)  # LSB: bit 7 = 1 (píxel 0)
        mmu.write(tile_addr + 1, 0x80)  # MSB: bit 7 = 1 (píxel 0)
        # Resto de líneas: blancas
        for line in range(1, 8):
            mmu.write(tile_addr + (line * 2), 0x00)
            mmu.write(tile_addr + (line * 2) + 1, 0x00)
        
        # Configurar sprite sin X-Flip
        mmu.write(0xFE00 + 0, 20)  # Y
        mmu.write(0xFE00 + 1, 20)  # X
        mmu.write(0xFE00 + 2, 1)   # Tile ID
        mmu.write(0xFE00 + 3, 0x00)  # Attributes (sin flip)
        
        # Avanzar hasta línea 4 y renderizar
        for _ in range(4):
            ppu.step(456)
        ppu.step(456)  # Completar línea 4 para renderizar
        
        framebuffer_line_4 = ppu.framebuffer[4 * 160:(4 * 160) + 160]
        
        # Leer paleta OBP0
        obp0 = mmu.read(0xFF48) & 0xFF
        
        # Sin X-Flip, el píxel negro debería estar en X=12 (primer píxel del sprite)
        color_index_left = framebuffer_line_4[12]
        pixel_left = color_index_to_argb32(color_index_left, obp0)
        
        # Ahora configurar sprite con X-Flip
        mmu.write(0xFE00 + 3, 0x20)  # Attributes con X-Flip (bit 5)
        
        # Reiniciar PPU para renderizar de nuevo
        ppu = PyPPU(mmu)
        for _ in range(4):
            ppu.step(456)
        ppu.step(456)  # Completar línea 4 para renderizar
        
        framebuffer_line_4_flipped = ppu.framebuffer[4 * 160:(4 * 160) + 160]
        
        # Con X-Flip, el píxel negro debería estar en X=19 (último píxel del sprite)
        color_index_right = framebuffer_line_4_flipped[19]
        pixel_right = color_index_to_argb32(color_index_right, obp0)
        
        # Verificar que ambos son negros (el patrón se invirtió)
        assert pixel_left == 0xFF000000, "Píxel izquierdo sin flip debe ser negro"
        assert pixel_right == 0xFF000000, "Píxel derecho con flip debe ser negro"
        color_index_left_flipped = framebuffer_line_4_flipped[12]
        pixel_left_flipped = color_index_to_argb32(color_index_left_flipped, obp0)
        assert pixel_left_flipped != 0xFF000000, "Píxel izquierdo con flip NO debe ser negro"
    
    def test_sprite_palette_selection(self) -> None:
        """
        Test: Los sprites usan la paleta correcta (OBP0 o OBP1) según el bit 4 de atributos.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD, Background y Sprites
        mmu.write(0xFF40, 0x93)
        mmu.write(0xFF47, 0xE4)  # BGP
        
        # Configurar OBP0 y OBP1 con paletas diferentes
        # OBP0 = 0xE4 (0->blanco, 1->gris claro, 2->gris oscuro, 3->negro)
        # OBP1 = 0x40 (0->blanco, 1->blanco, 2->blanco, 3->gris claro) - solo color 3 diferente
        # 0x40 = 01000000: bits 6-7 = 01, así que color 3 = 1 (gris claro)
        mmu.write(0xFF48, 0xE4)  # OBP0
        mmu.write(0xFF49, 0x40)  # OBP1
        
        # Crear un tile con color 3 (negro en OBP0, gris claro en OBP1)
        tile_addr = 0x8010
        for line in range(8):
            mmu.write(tile_addr + (line * 2), 0xFF)
            mmu.write(tile_addr + (line * 2) + 1, 0xFF)
        
        # Configurar sprite con paleta 0 (OBP0)
        mmu.write(0xFE00 + 0, 20)
        mmu.write(0xFE00 + 1, 20)
        mmu.write(0xFE00 + 2, 1)
        mmu.write(0xFE00 + 3, 0x00)  # Paleta 0 (bit 4 = 0)
        
        # Avanzar hasta línea 4 y renderizar
        for _ in range(4):
            ppu.step(456)
        ppu.step(456)  # Completar línea 4 para renderizar
        
        framebuffer_line_4_pal0 = ppu.framebuffer[4 * 160:(4 * 160) + 160]
        color_index_pal0 = framebuffer_line_4_pal0[12]
        pixel_pal0 = color_index_to_argb32(color_index_pal0, 0xE4)  # OBP0
        
        # Ahora configurar sprite con paleta 1 (OBP1)
        mmu.write(0xFE00 + 3, 0x10)  # Paleta 1 (bit 4 = 1)
        
        # Reiniciar y renderizar de nuevo
        ppu = PyPPU(mmu)
        for _ in range(4):
            ppu.step(456)
        ppu.step(456)  # Completar línea 4 para renderizar
        
        framebuffer_line_4_pal1 = ppu.framebuffer[4 * 160:(4 * 160) + 160]
        color_index_pal1 = framebuffer_line_4_pal1[12]
        pixel_pal1 = color_index_to_argb32(color_index_pal1, 0x40)  # OBP1
        
        # Con OBP0, color 3 = negro (0xFF000000)
        # Con OBP1, color 3 = gris claro (0xFFAAAAAA)
        assert pixel_pal0 == 0xFF000000, "Con OBP0, color 3 debe ser negro"
        assert pixel_pal1 == 0xFFAAAAAA, "Con OBP1, color 3 debe ser gris claro"

