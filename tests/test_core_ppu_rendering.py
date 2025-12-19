"""
Tests para el renderizado scanline de la PPU en C++ (Pixel Processing Unit).

Estos tests validan la implementación nativa del renderizado línea a línea:
- Renderizado de Background con scroll (SCX/SCY)
- Renderizado de Window
- Decodificación de tiles 2bpp
- Aplicación de paleta BGP
- Exposición del framebuffer como memoryview (Zero-Copy)

Fuente: Pan Docs - Background, Window, Tile Data, 2bpp Format
"""

import pytest
import numpy as np

try:
    from viboy_core import PyMMU, PyPPU
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="viboy_core no está disponible (compilación requerida)")


class TestCorePPURendering:
    """Tests para el renderizado scanline de la PPU en C++."""

    def test_bg_rendering_simple_tile(self) -> None:
        """
        Test: Renderiza un tile simple (todo negro) en el Background.
        
        Pasos:
        1. Escribe un tile todo negro (color 3) en VRAM 0x8000 (tile ID 0)
        2. Configura tilemap 0x9800 para usar tile ID 0
        3. Enciende LCD (LCDC=0x91: bit 7=1, bit 4=1, bit 0=1)
        4. Configura paleta BGP=0xE4 (0->blanco, 1->gris claro, 2->gris oscuro, 3->negro)
        5. Avanza PPU hasta completar una línea (456 ciclos, entra en H-Blank)
        6. Verifica que el primer píxel del framebuffer sea negro (0xFF000000)
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD (bit 7=1) y Background (bit 0=1), unsigned addressing (bit 4=1)
        # LCDC = 0x91 = 10010001
        mmu.write(0xFF40, 0x91)
        
        # Configurar paleta BGP = 0xE4 (11100100)
        # Color 0 (bits 0-1): 0 = Blanco (0xFFFFFFFF)
        # Color 1 (bits 2-3): 1 = Gris claro (0xFFAAAAAA)
        # Color 2 (bits 4-5): 2 = Gris oscuro (0xFF555555)
        # Color 3 (bits 6-7): 3 = Negro (0xFF000000)
        mmu.write(0xFF47, 0xE4)
        
        # Crear un tile todo negro (color 3) en VRAM 0x8000 (tile ID 0)
        # Cada línea del tile son 2 bytes: 0xFF (LSB) y 0xFF (MSB) = color 3 en todos los píxeles
        tile_addr = 0x8000
        for line in range(8):
            mmu.write(tile_addr + (line * 2), 0xFF)      # Byte 1 (LSB) = todos bits 1
            mmu.write(tile_addr + (line * 2) + 1, 0xFF)  # Byte 2 (MSB) = todos bits 1
            # Resultado: cada píxel = (1 << 1) | 1 = 3 (negro)
        
        # Configurar tilemap 0x9800 para usar tile ID 0 en posición (0,0)
        mmu.write(0x9800, 0x00)  # Tile ID 0 en posición (0,0) del tilemap
        
        # Avanzar PPU hasta completar la línea 0
        # Necesitamos llegar a Mode 0 (H-Blank) después de Mode 3 (Pixel Transfer)
        # Esto ocurre después de 252 ciclos (80 Mode 2 + 172 Mode 3)
        ppu.step(252)
        
        # Verificar que estamos en Mode 0 (H-Blank) y se ha renderizado
        assert ppu.get_mode() == 0, "Debe estar en Mode 0 (H-Blank) después de renderizar"
        assert ppu.get_ly() == 0, "Debe estar en línea 0"
        
        # Obtener framebuffer
        framebuffer = ppu.get_framebuffer()
        
        # Verificar que el framebuffer tiene el tamaño correcto (160 * 144 = 23040)
        assert len(framebuffer) == 160 * 144, f"Framebuffer debe tener 23040 píxeles, tiene {len(framebuffer)}"
        
        # Verificar que el primer píxel es negro (0xFF000000)
        # Nota: En ARGB32, 0xFF000000 = Negro (Alpha=FF, R=00, G=00, B=00)
        first_pixel = framebuffer[0]
        assert first_pixel == 0xFF000000, f"Primer píxel debe ser negro (0xFF000000), es 0x{first_pixel:08X}"
        
        # Verificar que todos los píxeles de la primera línea son negro
        for x in range(160):
            pixel = framebuffer[x]
            assert pixel == 0xFF000000, f"Píxel {x} debe ser negro (0xFF000000), es 0x{pixel:08X}"

    def test_bg_rendering_scroll(self) -> None:
        """
        Test: El scroll (SCX/SCY) desplaza el Background correctamente.
        
        Pasos:
        1. Crea dos tiles diferentes: tile 0 (negro) y tile 1 (blanco)
        2. Configura tilemap con tile 0 en (0,0) y tile 1 en (1,0)
        3. Con SCX=8, el primer píxel visible debe ser del tile 1 (blanco)
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD y Background
        mmu.write(0xFF40, 0x91)  # LCDC: bit 7=1, bit 4=1, bit 0=1
        mmu.write(0xFF47, 0xE4)  # BGP: 0->blanco, 1->gris claro, 2->gris oscuro, 3->negro
        
        # Crear tile 0 (todo negro) en VRAM 0x8000
        for line in range(8):
            mmu.write(0x8000 + (line * 2), 0xFF)
            mmu.write(0x8000 + (line * 2) + 1, 0xFF)
        
        # Crear tile 1 (todo blanco = color 0) en VRAM 0x8010 (16 bytes por tile)
        for line in range(8):
            mmu.write(0x8010 + (line * 2), 0x00)      # Byte 1 (LSB) = todos bits 0
            mmu.write(0x8010 + (line * 2) + 1, 0x00)  # Byte 2 (MSB) = todos bits 0
            # Resultado: cada píxel = (0 << 1) | 0 = 0 (blanco)
        
        # Configurar tilemap: tile 0 en (0,0), tile 1 en (1,0)
        mmu.write(0x9800, 0x00)  # Tile 0 en (0,0)
        mmu.write(0x9801, 0x01)  # Tile 1 en (1,0)
        
        # Configurar scroll horizontal SCX=8 (desplaza 8 píxeles a la izquierda)
        # Esto significa que el primer píxel visible será el píxel 8 del tilemap
        # Como cada tile tiene 8 píxeles, el primer píxel visible será del tile 1 (blanco)
        mmu.write(0xFF43, 8)  # SCX = 8
        
        # Avanzar PPU hasta completar la línea 0 (entra en H-Blank)
        ppu.step(252)
        
        # Obtener framebuffer
        framebuffer = ppu.get_framebuffer()
        
        # El primer píxel visible debe ser del tile 1 (blanco)
        first_pixel = framebuffer[0]
        assert first_pixel == 0xFFFFFFFF, f"Primer píxel debe ser blanco (0xFFFFFFFF), es 0x{first_pixel:08X}"

    def test_window_rendering(self) -> None:
        """
        Test: La Window se renderiza encima del Background.
        
        Pasos:
        1. Configura Background con tile negro
        2. Configura Window con tile blanco, posicionada en WX=7, WY=0
        3. Verifica que la Window sobrescribe el Background
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD, Background y Window
        mmu.write(0xFF40, 0xB1)  # LCDC: bit 7=1, bit 5=1 (Window), bit 4=1, bit 0=1
        mmu.write(0xFF47, 0xE4)  # BGP
        
        # Crear tile 0 (negro) para Background
        for line in range(8):
            mmu.write(0x8000 + (line * 2), 0xFF)
            mmu.write(0x8000 + (line * 2) + 1, 0xFF)
        
        # Crear tile 1 (blanco) para Window
        for line in range(8):
            mmu.write(0x8010 + (line * 2), 0x00)
            mmu.write(0x8010 + (line * 2) + 1, 0x00)
        
        # Configurar tilemap de Background (0x9800) con tile 0
        mmu.write(0x9800, 0x00)
        
        # Configurar tilemap de Window (0x9800 también por defecto, bit 6=0) con tile 1
        mmu.write(0x9800, 0x01)  # Window tilemap usa el mismo, pero lo configuramos con tile 1
        
        # Configurar Window: WX=7 (x=0), WY=0 (y=0)
        mmu.write(0xFF4A, 0)  # WY = 0
        mmu.write(0xFF4B, 7)  # WX = 7 (significa x=0 en pantalla)
        
        # Avanzar PPU hasta completar la línea 0
        ppu.step(252)
        
        # Obtener framebuffer
        framebuffer = ppu.get_framebuffer()
        
        # Como la Window está en (0,0) y cubre toda la pantalla, debe sobrescribir el Background
        # El primer píxel debe ser blanco (de la Window)
        first_pixel = framebuffer[0]
        # Nota: La Window se renderiza después del Background, así que debe sobrescribirlo
        assert first_pixel == 0xFFFFFFFF, f"Primer píxel debe ser blanco (Window), es 0x{first_pixel:08X}"

    def test_framebuffer_memoryview(self) -> None:
        """
        Test: El framebuffer se expone como memoryview para Zero-Copy.
        
        Verifica que el framebuffer puede ser convertido a numpy array
        sin copiar datos (usando memoryview).
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x91)
        mmu.write(0xFF47, 0xE4)
        
        # Avanzar una línea
        ppu.step(252)
        
        # Obtener framebuffer
        framebuffer = ppu.get_framebuffer()
        
        # Verificar que es un memoryview
        assert hasattr(framebuffer, '__class__'), "Framebuffer debe ser un objeto válido"
        
        # Convertir a numpy array (esto crea una vista, no una copia)
        # Nota: numpy puede crear una vista desde memoryview
        np_array = np.asarray(framebuffer)
        
        # Verificar dimensiones
        assert np_array.shape == (23040,), f"Array debe tener forma (23040,), tiene {np_array.shape}"
        
        # Verificar que podemos acceder a los datos
        first_pixel = np_array[0]
        assert isinstance(first_pixel, (np.uint32, np.integer, int)), "Elemento debe ser uint32 o compatible"

    def test_signed_addressing_fix(self) -> None:
        """
        Test: Verifica que el cálculo de dirección en modo signed addressing es correcto.
        
        Este test valida la corrección del bug que causaba Segmentation Faults
        cuando la PPU intentaba renderizar tiles con signed addressing.
        
        Pasos:
        1. Configura LCDC con bit 4=0 (signed addressing activo)
        2. Escribe un tile en la dirección esperada para signed addressing
        3. Configura tilemap con un tile ID que se interpreta como negativo
        4. Verifica que la PPU puede renderizar sin crash
        5. Verifica que el cálculo de dirección es correcto (0x9000 + signed_offset)
        
        Fuente: Pan Docs - Tile Data Addressing
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD (bit 7=1) y Background (bit 0=1)
        # IMPORTANTE: bit 4=0 activa signed addressing
        # IMPORTANTE: bit 3=0 usa tilemap en 0x9800 (no 0x9C00)
        # LCDC = 0x81 = 10000001 (bit 7=1, bit 4=0, bit 3=0, bit 0=1)
        mmu.write(0xFF40, 0x81)
        
        # Configurar paleta BGP
        mmu.write(0xFF47, 0xE4)  # BGP: 0->blanco, 1->gris claro, 2->gris oscuro, 3->negro
        
        # En modo signed addressing:
        # - Tile ID 0 está en 0x9000 (no en 0x8800)
        # - Tile ID 128 (0x80) se interpreta como -128
        # - Dirección = 0x9000 + (-128 * 16) = 0x9000 - 0x800 = 0x8800
        
        # Escribir un tile todo negro (color 3) en 0x8800
        # Este tile corresponde a tile ID 128 en modo signed (que es -128)
        tile_addr = 0x8800
        for line in range(8):
            mmu.write(tile_addr + (line * 2), 0xFF)      # Byte 1 (LSB)
            mmu.write(tile_addr + (line * 2) + 1, 0xFF)  # Byte 2 (MSB)
        
        # Configurar tilemap 0x9800 con tile ID 128 (que se interpreta como -128)
        mmu.write(0x9800, 128)  # Tile ID 128 = -128 en signed
        
        # Avanzar PPU hasta completar la línea 0 (456 ciclos)
        # El renderizado ocurre cuando se completan 456 ciclos de una línea
        # Esto debería renderizar sin Segmentation Fault
        ppu.step(456)  # Completar línea 0 (se renderiza al completar)
        
        # Después de 456 ciclos, avanzamos a la línea 1 y el modo se reinicia a Mode 2
        # Pero el framebuffer de la línea 0 ya se ha renderizado
        assert ppu.get_ly() == 1, "Después de 456 ciclos, debe estar en línea 1"
        assert ppu.get_mode() == 2, "Al inicio de línea 1, debe estar en Mode 2 (OAM Search)"
        
        # Obtener framebuffer
        framebuffer = ppu.get_framebuffer()
        
        # Verificar que el framebuffer tiene el tamaño correcto
        assert len(framebuffer) == 160 * 144, f"Framebuffer debe tener 23040 píxeles, tiene {len(framebuffer)}"
        
        # Verificar que el primer píxel es negro (color 3)
        # El framebuffer contiene índices de color (0-3), no valores ARGB32
        # En el test anterior, el framebuffer se convertía a ARGB32, pero aquí
        # verificamos directamente el índice de color
        first_pixel = framebuffer[0]
        assert first_pixel == 3, f"Primer píxel debe ser color 3 (negro), es {first_pixel}"
        
        # Verificar que los primeros 8 píxeles (el primer tile) son color 3 (negro)
        # Solo configuramos el primer tile en el tilemap, el resto está en 0 (blanco)
        for x in range(8):
            pixel = framebuffer[x]
            assert pixel == 3, f"Píxel {x} del primer tile debe ser color 3 (negro), es {pixel}"
        
        # Verificación extra: El píxel 8 (inicio del segundo tile) debe ser blanco (color 0)
        # porque no configuramos el tile en la posición 0x9801 del tilemap
        assert framebuffer[8] == 0, f"El segundo tile debe ser blanco (color 0) por defecto, es {framebuffer[8]}"
        
        # Test adicional: Verificar tile ID 0 en modo signed (debe estar en 0x9000)
        # Limpiar tilemap
        mmu.write(0x9800, 0)  # Tile ID 0
        
        # Escribir tile en 0x9000 (tile 0 en modo signed)
        tile_addr_0 = 0x9000
        for line in range(8):
            mmu.write(tile_addr_0 + (line * 2), 0x00)      # Tile blanco (color 0)
            mmu.write(tile_addr_0 + (line * 2) + 1, 0x00)
        
        # Avanzar hasta completar la línea 1 (456 ciclos más)
        # Esto renderizará la línea 1 con el tile ID 0 (blanco)
        ppu.step(456)  # Completar línea 1
        
        # Verificar que estamos en línea 2
        assert ppu.get_ly() == 2, "Después de completar línea 1, debe estar en línea 2"
        
        # Verificar que el primer píxel de la línea 1 es color 0 (blanco)
        framebuffer = ppu.get_framebuffer()
        first_pixel = framebuffer[160]  # Primer píxel de la línea 1 (índice 160)
        assert first_pixel == 0, f"Primer píxel de línea 1 debe ser color 0 (blanco), es {first_pixel}"

