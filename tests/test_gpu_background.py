"""
Tests unitarios para el renderizado del Background (fondo)

Verifica:
- Control del registro LCDC (selección de direcciones base)
- Modo signed/unsigned de direccionamiento de tiles
- Renderizado básico del tilemap
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
from src.memory.mmu import MMU, IO_LCDC, IO_BGP


@pytest.mark.skipif(not PYGAME_AVAILABLE, reason="Pygame no está instalado")
class TestBackgroundRendering:
    """Suite de tests para el renderizado del Background"""

    def test_lcdc_control_tile_map_area(self) -> None:
        """
        Test: Verificar que el bit 3 de LCDC selecciona correctamente el área del tilemap.
        
        Bit 3 de LCDC:
        - 0 = Tile Map en 0x9800
        - 1 = Tile Map en 0x9C00
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        
        # Mockear pygame para evitar inicialización de ventana
        renderer.screen = MagicMock()
        # Mockear _draw_tile_with_palette para evitar pygame.draw.rect
        renderer._draw_tile_with_palette = MagicMock()
        
        # Test 1: Bit 3 = 0 -> map_base = 0x9800
        mmu.write_byte(IO_LCDC, 0x91)  # 0x91 = 10010001 (bit 7=1, bit 4=1, bit 3=0, bit 0=1)
        mmu.write_byte(IO_BGP, 0xE4)  # Paleta básica
        
        # Inicializar tilemap en 0x9800 con tile ID 0
        mmu.write_byte(0x9800, 0x00)
        
        # Mockear read_byte para verificar que se lee de 0x9800
        read_calls = []
        original_read = mmu.read_byte
        
        def tracked_read(addr: int) -> int:
            if 0x9800 <= addr < 0x9C00:  # Rango del tilemap
                read_calls.append(addr)
            return original_read(addr)
        
        mmu.read_byte = tracked_read
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se leyó del tilemap correcto (0x9800)
        assert any(0x9800 <= addr < 0x9C00 for addr in read_calls), \
            "Debe leer del tilemap en 0x9800 cuando bit 3 = 0"
        
        # Test 2: Bit 3 = 1 -> map_base = 0x9C00
        read_calls.clear()
        mmu.write_byte(IO_LCDC, 0x99)  # 0x99 = 10011001 (bit 7=1, bit 4=1, bit 3=1, bit 0=1)
        
        # Inicializar tilemap en 0x9C00 con tile ID 0
        mmu.write_byte(0x9C00, 0x00)
        
        # Actualizar tracked_read para capturar también 0x9C00-0xA000
        def tracked_read2(addr: int) -> int:
            if 0x9C00 <= addr < 0xA000:  # Rango del tilemap 2
                read_calls.append(addr)
            return original_read(addr)
        
        mmu.read_byte = tracked_read2
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se leyó del tilemap correcto (0x9C00)
        assert any(0x9C00 <= addr < 0xA000 for addr in read_calls), \
            f"Debe leer del tilemap en 0x9C00 cuando bit 3 = 1, pero se leyó: {read_calls}"
        
        renderer.quit()

    def test_lcdc_control_tile_data_area_unsigned(self) -> None:
        """
        Test: Verificar modo unsigned de direccionamiento de tiles (bit 4 = 1).
        
        Bit 4 de LCDC:
        - 1 = Tile Data en 0x8000 (unsigned: tile IDs 0-255)
        - Tile ID 0 está en 0x8000
        - Tile ID 1 está en 0x8010
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        renderer._draw_tile_with_palette = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 4=1 (unsigned), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x91)  # 10010001
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar tilemap: tile ID 1 en posición (0,0)
        mmu.write_byte(0x9800, 0x01)
        
        # Configurar tile en 0x8010 (tile ID 1 en modo unsigned)
        # Escribir un tile simple (todo color 3 = negro)
        for line in range(8):
            mmu.write_byte(0x8010 + (line * 2), 0xFF)  # Byte 1 (LSB)
            mmu.write_byte(0x8010 + (line * 2) + 1, 0xFF)  # Byte 2 (MSB)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que _draw_tile_with_palette fue llamado con tile_addr = 0x8010
        # (Tile ID 1 en modo unsigned: 0x8000 + (1 * 16) = 0x8010)
        calls = renderer._draw_tile_with_palette.call_args_list
        assert len(calls) > 0, "Debe llamar a _draw_tile_with_palette"
        # Verificar que al menos una llamada tiene tile_addr = 0x8010
        tile_addrs = [call[0][2] for call in calls]  # call[0] son los args posicionales, [2] es tile_addr
        assert 0x8010 in tile_addrs, f"Debe renderizar tile en 0x8010 (tile ID 1 en modo unsigned), pero se llamó con: {tile_addrs}"
        
        renderer.quit()

    def test_lcdc_control_tile_data_area_signed(self) -> None:
        """
        Test: Verificar modo signed de direccionamiento de tiles (bit 4 = 0).
        
        Bit 4 de LCDC = 0:
        - Tile Data en modo signed (0x8800-0x97FF, pero tile ID 0 está en 0x9000)
        - Tile ID 0 está en 0x9000
        - Tile ID 1 está en 0x9010
        - Tile ID 127 está en 0x8FF0
        - Tile ID 128 (signed: -128) está en 0x8800
        - Tile ID 255 (signed: -1) está en 0x8FF0
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        renderer._draw_tile_with_palette = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 4=0 (signed), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x81)  # 10000001
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Test 1: Tile ID 0 -> debe apuntar a 0x9000
        mmu.write_byte(0x9800, 0x00)  # Tile ID 0 en tilemap
        # Configurar tile en 0x9000
        for line in range(8):
            mmu.write_byte(0x9000 + (line * 2), 0xFF)
            mmu.write_byte(0x9000 + (line * 2) + 1, 0xFF)
        
        renderer.render_frame()
        # Verificar que se llamó con tile_addr = 0x9000
        calls = renderer._draw_tile_with_palette.call_args_list
        tile_addrs = [call[0][2] for call in calls]
        assert 0x9000 in tile_addrs, f"Tile ID 0 debe apuntar a 0x9000 en modo signed, pero se llamó con: {tile_addrs}"
        
        # Test 2: Tile ID 128 (signed: -128) -> debe apuntar a 0x8800
        renderer._draw_tile_with_palette.reset_mock()
        mmu.write_byte(0x9800, 0x80)  # Tile ID 128 (signed: -128)
        # Configurar tile en 0x8800
        for line in range(8):
            mmu.write_byte(0x8800 + (line * 2), 0xFF)
            mmu.write_byte(0x8800 + (line * 2) + 1, 0xFF)
        
        renderer.render_frame()
        # Verificar que se llamó con tile_addr = 0x8800
        calls = renderer._draw_tile_with_palette.call_args_list
        tile_addrs = [call[0][2] for call in calls]
        assert 0x8800 in tile_addrs, f"Tile ID 0x80 (signed: -128) debe apuntar a 0x8800, pero se llamó con: {tile_addrs}"
        
        renderer.quit()

    def test_lcdc_lcd_disable(self) -> None:
        """
        Test: Verificar que si LCD está desactivado (bit 7 = 0), se pinta pantalla blanca.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7 = 0 (LCD desactivado)
        mmu.write_byte(IO_LCDC, 0x00)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se llamó fill con color blanco
        renderer.screen.fill.assert_called_with((255, 255, 255))
        
        renderer.quit()

    def test_lcdc_bg_disable(self) -> None:
        """
        Test: Verificar que si Background está desactivado (bit 0 = 0), se pinta pantalla blanca.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7 = 1 (LCD activado), bit 0 = 0 (BG desactivado)
        mmu.write_byte(IO_LCDC, 0x80)  # 10000000
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se llamó fill con color blanco
        renderer.screen.fill.assert_called_with((255, 255, 255))
        
        renderer.quit()

    def test_signed_addressing_tile_id_128(self) -> None:
        """
        Test: Verificar que Tile ID 0x80 con bit 4=0 (signed) apunta a 0x8800.
        
        En modo signed:
        - Tile ID 0x80 (128 en unsigned) = -128 en signed
        - Dirección = 0x9000 + (-128 * 16) = 0x9000 - 0x800 = 0x8800
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        renderer._draw_tile_with_palette = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 4=0 (signed), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x81)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar tilemap: tile ID 0x80 en posición (0,0)
        mmu.write_byte(0x9800, 0x80)
        
        # Configurar tile en 0x8800 (donde debe estar tile ID 0x80 en modo signed)
        for line in range(8):
            mmu.write_byte(0x8800 + (line * 2), 0xAA)  # Patrón de prueba
            mmu.write_byte(0x8800 + (line * 2) + 1, 0x55)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que _draw_tile_with_palette fue llamado con tile_addr = 0x8800
        calls = renderer._draw_tile_with_palette.call_args_list
        assert len(calls) > 0, "Debe llamar a _draw_tile_with_palette"
        tile_addrs = [call[0][2] for call in calls]
        assert 0x8800 in tile_addrs, \
            f"Tile ID 0x80 (signed: -128) debe apuntar a 0x8800, pero se llamó con: {tile_addrs}"
        
        renderer.quit()

