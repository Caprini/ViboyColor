"""
Tests unitarios para el renderizado de la Window (Ventana)

NOTA STEP 0433: Estos tests legacy están deprecados porque:
1. Mockean implementación Python legacy (no el core C++ que es la verdad)
2. No validan el framebuffer real generado por el core C++
3. Esperan comportamiento del renderer Python legacy

Los tests equivalentes de Window están en:
- tests/test_core_ppu_rendering.py (incluye window rendering con core C++)

Estos tests se mantienen marcados como skip para referencia histórica.
"""

import pytest
from unittest.mock import Mock, MagicMock

# Importar condicionalmente pygame para tests
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from src.gpu.renderer import Renderer
from src.memory.mmu import MMU, IO_LCDC, IO_BGP, IO_WX, IO_WY


@pytest.mark.skip(reason="Legacy GPU tests - replaced by core PPU tests (Step 0433)")
@pytest.mark.skipif(not PYGAME_AVAILABLE, reason="Pygame no está instalado")
class TestWindowRendering:
    """Suite de tests para el renderizado de la Window"""

    def test_window_positioning(self) -> None:
        """
        Test: Verificar que con WX=7 (x=0) y WY=0, la ventana cubre toda la pantalla.
        
        WX tiene un offset histórico de 7 píxeles, así que WX=7 significa que la ventana
        comienza en x=0 de la pantalla. Con WY=0, la ventana comienza en y=0.
        Por lo tanto, la ventana debe cubrir toda la pantalla (160x144 píxeles).
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1 (LCD ON), bit 5=1 (Window Enable), bit 4=1 (unsigned), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0xB1)  # 10110001
        mmu.write_byte(IO_BGP, 0xE4)  # Paleta básica
        
        # Configurar Window: WX=7 (x=0), WY=0
        mmu.write_byte(IO_WX, 7)
        mmu.write_byte(IO_WY, 0)
        
        # Configurar tilemap de Window (0x9800 por defecto, bit 6=0)
        # Poner tile ID 1 en posición (0,0) del tilemap de Window
        mmu.write_byte(0x9800, 0x01)
        
        # Configurar tile en 0x8010 (tile ID 1 en modo unsigned)
        # Escribir un tile simple (todo color 3 = negro) para distinguirlo del fondo
        for line in range(8):
            mmu.write_byte(0x8010 + (line * 2), 0xFF)  # Byte 1 (LSB)
            mmu.write_byte(0x8010 + (line * 2) + 1, 0xFF)  # Byte 2 (MSB)
        
        # Configurar tilemap de Background (0x9800 también, pero usaremos otro tile)
        # Poner tile ID 0 (blanco) en el fondo para que se vea la diferencia
        # (El tilemap de Window y Background pueden compartir la misma área, pero
        #  en este test usamos posiciones diferentes para distinguirlos)
        # Como Window está habilitada y cubre toda la pantalla, no deberíamos ver el fondo
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se leyó del tilemap de Window (0x9800)
        # Para esto, necesitamos verificar que el píxel (0,0) tiene el color del tile de Window
        # Leer el píxel del buffer
        pixel_color = renderer.buffer.get_at((0, 0))
        
        # El tile de Window es todo color 3 (negro), que en la paleta 0xE4 es (0, 0, 0)
        # Verificar que el píxel es negro (color del tile de Window)
        assert pixel_color == (0, 0, 0, 255), \
            f"El píxel (0,0) debe ser negro (color del tile de Window), pero es {pixel_color}"
        
        renderer.quit()

    def test_window_offset(self) -> None:
        """
        Test: Verificar que con WX=87 (mitad de pantalla), los píxeles a la izquierda
        son del fondo y los de la derecha son de la ventana.
        
        WX=87 significa que la ventana comienza en x=80 (87-7=80).
        Los píxeles con x < 80 deben ser del fondo, los píxeles con x >= 80 deben ser de la ventana.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 6=1 (Window Map en 0x9C00), bit 5=1 (Window Enable), 
        # bit 4=1 (unsigned), bit 3=0 (Background Map en 0x9800), bit 0=1
        # Usamos tilemaps diferentes para Window y Background
        mmu.write_byte(IO_LCDC, 0xF1)  # 11110001
        mmu.write_byte(IO_BGP, 0xE4)  # Paleta básica
        
        # Configurar Window: WX=87 (x=80), WY=0
        mmu.write_byte(IO_WX, 87)
        mmu.write_byte(IO_WY, 0)
        
        # Configurar tilemap de Window en 0x9C00: tile ID 1 (negro) en posición (0,0)
        # La ventana comienza en x=80 de la pantalla, pero dentro de la ventana
        # el píxel (80,0) corresponde a win_x=0, win_y=0, que es el tile (0,0) del tilemap
        mmu.write_byte(0x9C00 + (0 * 32) + 0, 0x01)  # Tile ID 1 en (0,0)
        
        # Configurar tile en 0x8010 (tile ID 1 = negro)
        for line in range(8):
            mmu.write_byte(0x8010 + (line * 2), 0xFF)
            mmu.write_byte(0x8010 + (line * 2) + 1, 0xFF)
        
        # Configurar tilemap de Background en 0x9800: tile ID 0 (blanco) en todas las posiciones
        # Tile ID 0 está en 0x8000 y por defecto es blanco (color 0)
        for y in range(18):  # 18 tiles de alto (144/8)
            for x in range(20):  # 20 tiles de ancho (160/8)
                mmu.write_byte(0x9800 + (y * 32) + x, 0x00)  # Tile ID 0 (blanco)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar píxel a la izquierda de la ventana (x=79, y=0) debe ser blanco (fondo)
        pixel_left = renderer.buffer.get_at((79, 0))
        # Color 0 de paleta 0xE4 es blanco (255, 255, 255)
        assert pixel_left == (255, 255, 255, 255), \
            f"El píxel (79,0) debe ser blanco (fondo), pero es {pixel_left}"
        
        # Verificar píxel dentro de la ventana (x=80, y=0) debe ser negro (ventana)
        pixel_right = renderer.buffer.get_at((80, 0))
        # Color 3 de paleta 0xE4 es negro (0, 0, 0)
        assert pixel_right == (0, 0, 0, 255), \
            f"El píxel (80,0) debe ser negro (ventana), pero es {pixel_right}"
        
        renderer.quit()

    def test_window_enable_bit(self) -> None:
        """
        Test: Verificar que si LCDC Bit 5 (Window Enable) es 0, no se dibuja la ventana
        aunque WX/WY estén en rango.
        
        Esto es importante porque el juego puede configurar WX/WY pero deshabilitar la ventana
        con el bit 5 de LCDC.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1 (LCD ON), bit 5=0 (Window DISABLED), bit 4=1 (unsigned), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x91)  # 10010001 (bit 5=0)
        mmu.write_byte(IO_BGP, 0xE4)  # Paleta básica
        
        # Configurar Window: WX=7 (x=0), WY=0 (pero está deshabilitada)
        mmu.write_byte(IO_WX, 7)
        mmu.write_byte(IO_WY, 0)
        
        # Configurar tilemap de Window: tile ID 1 (negro) en posición (0,0)
        mmu.write_byte(0x9800, 0x01)
        
        # Configurar tile en 0x8010 (tile ID 1 = negro)
        for line in range(8):
            mmu.write_byte(0x8010 + (line * 2), 0xFF)
            mmu.write_byte(0x8010 + (line * 2) + 1, 0xFF)
        
        # Configurar tilemap de Background: tile ID 0 (blanco) en todas las posiciones
        for y in range(18):
            for x in range(20):
                mmu.write_byte(0x9800 + (y * 32) + x, 0x00)  # Tile ID 0 (blanco)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que el píxel (0,0) es blanco (fondo), no negro (ventana)
        # Esto demuestra que la ventana NO se dibujó aunque WX/WY estén en rango
        pixel_color = renderer.buffer.get_at((0, 0))
        assert pixel_color == (255, 255, 255, 255), \
            f"El píxel (0,0) debe ser blanco (fondo, ventana deshabilitada), pero es {pixel_color}"
        
        renderer.quit()

    def test_window_tile_map_area(self) -> None:
        """
        Test: Verificar que el bit 6 de LCDC selecciona correctamente el área del tilemap de Window.
        
        Bit 6 de LCDC:
        - 0 = Window Tile Map en 0x9800
        - 1 = Window Tile Map en 0x9C00
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 6=0 (Window Map en 0x9800), bit 5=1 (Window Enable), bit 4=1, bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0xB1)  # 10110001 (bit 6=0)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar Window: WX=7, WY=0
        mmu.write_byte(IO_WX, 7)
        mmu.write_byte(IO_WY, 0)
        
        # Configurar tilemap de Background en 0x9800: tile ID 0 (blanco) en todas las posiciones
        # (para que no interfiera con la Window)
        for y in range(18):
            for x in range(20):
                mmu.write_byte(0x9800 + (y * 32) + x, 0x00)  # Tile ID 0 (blanco)
        
        # Configurar tilemap de Window en 0x9800: tile ID 1 (negro) en posición (0,0)
        # NOTA: Window y Background comparten el mismo tilemap cuando bit 6=0 y bit 3=0
        # Para distinguirlos, usaremos un tile diferente
        mmu.write_byte(0x9800, 0x01)  # Tile ID 1 en (0,0) del tilemap
        
        # Configurar tile en 0x8010 (tile ID 1 = negro)
        for line in range(8):
            mmu.write_byte(0x8010 + (line * 2), 0xFF)
            mmu.write_byte(0x8010 + (line * 2) + 1, 0xFF)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se leyó del tilemap de Window en 0x9800
        pixel_color = renderer.buffer.get_at((0, 0))
        assert pixel_color == (0, 0, 0, 255), \
            f"El píxel (0,0) debe ser negro (tile de Window en 0x9800), pero es {pixel_color}"
        
        # Ahora cambiar bit 6 a 1 (Window Map en 0x9C00) y bit 3 a 0 (Background Map en 0x9800)
        # para que Window y Background usen tilemaps diferentes
        mmu.write_byte(IO_LCDC, 0xF1)  # 11110001 (bit 6=1, bit 3=0)
        
        # Limpiar tilemap de Background en 0x9800 (poner todo en tile ID 0, blanco)
        # para asegurar que no interfiera con la Window
        for y in range(18):
            for x in range(20):
                mmu.write_byte(0x9800 + (y * 32) + x, 0x00)  # Tile ID 0 (blanco)
        
        # Limpiar tilemap de Window en 0x9C00 (poner todo en tile ID 0)
        for y in range(18):
            for x in range(20):
                mmu.write_byte(0x9C00 + (y * 32) + x, 0x00)  # Tile ID 0 (blanco)
        
        # Configurar tilemap de Window en 0x9C00: tile ID 3 (negro, pero diferente al tile ID 1)
        # Usaremos tile ID 3 para verificar que se lee de 0x9C00
        mmu.write_byte(0x9C00, 0x03)  # Tile ID 3 en (0,0)
        
        # Configurar tile en 0x8030 (tile ID 3 = negro, color 3 de paleta)
        for line in range(8):
            mmu.write_byte(0x8030 + (line * 2), 0xFF)
            mmu.write_byte(0x8030 + (line * 2) + 1, 0xFF)
        
        # Asegurar que el tilemap de Background en 0x9800 tiene tile ID 0 (blanco) en (0,0)
        # para que si se lee del fondo, sea blanco, no negro
        mmu.write_byte(0x9800, 0x00)  # Tile ID 0 (blanco) en (0,0)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que ahora se leyó del tilemap de Window en 0x9C00
        # Si se lee de 0x9C00, el píxel debe ser negro (tile ID 3)
        # Si se lee de 0x9800 (fondo), el píxel debe ser blanco (tile ID 0)
        pixel_color = renderer.buffer.get_at((0, 0))
        # El píxel debe ser negro (tile ID 3 de Window en 0x9C00), no blanco (tile ID 0 de fondo)
        assert pixel_color == (0, 0, 0, 255), \
            f"El píxel (0,0) debe ser negro (tile de Window en 0x9C00), pero es {pixel_color}. " \
            f"Si es blanco, significa que se está leyendo del fondo en lugar de la Window."
        
        renderer.quit()

