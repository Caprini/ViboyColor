"""
Tests unitarios para el scroll (SCX/SCY) del Background

NOTA STEP 0433: Estos tests legacy están deprecados porque:
1. Esperan pygame.draw.rect (pero core C++ usa NumPy vectorizado)
2. Mockean implementación Python legacy (no el core C++ que es la verdad)
3. No validan el framebuffer real generado por el core C++

Los tests equivalentes están en:
- tests/test_core_ppu_rendering.py (incluye scroll tests con SCX/SCY)

Estos tests se mantienen marcados como skip para referencia histórica.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

# Importar condicionalmente pygame para tests
try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False

from src.gpu.renderer import Renderer
from src.memory.mmu import MMU, IO_LCDC, IO_BGP, IO_SCX, IO_SCY


@pytest.mark.skip(reason="Legacy GPU tests - replaced by core PPU tests (Step 0433)")
@pytest.mark.skipif(not PYGAME_AVAILABLE, reason="Pygame no está instalado")
class TestScroll:
    """Suite de tests para el scroll (SCX/SCY)"""

    @patch('src.gpu.renderer.pygame.draw.rect')
    def test_scroll_x(self, mock_draw_rect: MagicMock) -> None:
        """
        Test: Verificar que SCX desplaza correctamente el fondo horizontalmente.
        
        Si SCX=4, el píxel 0 de pantalla debe mostrar el píxel 4 del tilemap.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 4=1 (unsigned), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x91)  # 10010001
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar SCX = 4
        mmu.write_byte(IO_SCX, 4)
        mmu.write_byte(IO_SCY, 0)
        
        # Configurar tilemap: tile ID 0 en posición (0,0)
        mmu.write_byte(0x9800, 0x00)
        
        # Configurar tile en 0x8000 (tile ID 0) con un patrón visible
        # Línea 0: píxel 0-3 = color 0 (blanco), píxel 4-7 = color 3 (negro)
        # Byte 1 (LSB): 0b00001111 = 0x0F (píxeles 4-7 tienen bit bajo)
        # Byte 2 (MSB): 0b00001111 = 0x0F (píxeles 4-7 tienen bit alto)
        # Resultado: píxeles 0-3 = 00 (color 0), píxeles 4-7 = 11 (color 3)
        mmu.write_byte(0x8000, 0x0F)  # Línea 0, byte 1
        mmu.write_byte(0x8001, 0x0F)  # Línea 0, byte 2
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se llamó a pygame.draw.rect (debe haber 160*144 = 23040 llamadas)
        assert mock_draw_rect.called, "Debe llamar a pygame.draw.rect para dibujar píxeles"
        assert mock_draw_rect.call_count == 160 * 144, \
            f"Debe dibujar 160*144 píxeles, pero se llamó {mock_draw_rect.call_count} veces"
        
        # Verificar que se renderizó (screen.fill fue llamado)
        renderer.screen.fill.assert_called()
        
        renderer.quit()

    @patch('src.gpu.renderer.pygame.draw.rect')
    def test_scroll_y(self, mock_draw_rect: MagicMock) -> None:
        """
        Test: Verificar que SCY desplaza correctamente el fondo verticalmente.
        
        Si SCY=8, la línea 0 de pantalla debe mostrar la línea 8 del tilemap.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC: bit 7=1, bit 4=1 (unsigned), bit 3=0, bit 0=1
        mmu.write_byte(IO_LCDC, 0x91)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar SCY = 8
        mmu.write_byte(IO_SCX, 0)
        mmu.write_byte(IO_SCY, 8)
        
        # Configurar tilemap: tile ID 0 en posición (0,0)
        mmu.write_byte(0x9800, 0x00)
        
        # Configurar tile en 0x8000: línea 0 = color 0, línea 1 = color 3
        # Línea 0: todo color 0 (blanco)
        mmu.write_byte(0x8000, 0x00)
        mmu.write_byte(0x8001, 0x00)
        # Línea 1: todo color 3 (negro)
        mmu.write_byte(0x8002, 0xFF)
        mmu.write_byte(0x8003, 0xFF)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se renderizó
        renderer.screen.fill.assert_called()
        assert mock_draw_rect.called, "Debe llamar a pygame.draw.rect"
        
        renderer.quit()

    @patch('src.gpu.renderer.pygame.draw.rect')
    def test_scroll_wrap_around(self, mock_draw_rect: MagicMock) -> None:
        """
        Test: Verificar que el scroll hace wrap-around correctamente (módulo 256).
        
        Si SCX=200 y screen_x=100, map_x = (100 + 200) % 256 = 44
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC
        mmu.write_byte(IO_LCDC, 0x91)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar SCX = 200 (cerca del límite de 256)
        mmu.write_byte(IO_SCX, 200)
        mmu.write_byte(IO_SCY, 0)
        
        # Configurar tilemap básico
        mmu.write_byte(0x9800, 0x00)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se renderizó sin errores
        renderer.screen.fill.assert_called()
        assert mock_draw_rect.called, "Debe llamar a pygame.draw.rect"
        
        renderer.quit()

    @patch('src.gpu.renderer.pygame.draw.rect')
    def test_force_bg_render_lcdc_0x80(self, mock_draw_rect: MagicMock) -> None:
        """
        Test: Verificar que con LCDC=0x80 (bit 7=1, bit 0=0) se dibuja el fondo.
        
        Este test valida el "hack educativo" que ignora el Bit 0 de LCDC para
        permitir que juegos CGB (como Tetris DX) que escriben LCDC=0x80 puedan
        mostrar gráficos.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC = 0x80 (bit 7=1 LCD ON, bit 0=0 BG OFF en DMG)
        # Con el hack, debería dibujar el fondo de todas formas
        mmu.write_byte(IO_LCDC, 0x80)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar tilemap básico
        mmu.write_byte(0x9800, 0x00)
        
        # Configurar tile en 0x8000 (tile ID 0)
        for line in range(8):
            mmu.write_byte(0x8000 + (line * 2), 0x00)
            mmu.write_byte(0x8000 + (line * 2) + 1, 0x00)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que NO se llamó fill con blanco (que sería el comportamiento
        # sin el hack cuando bit 0=0)
        # En su lugar, debería haber dibujado píxeles
        fill_calls = renderer.screen.fill.call_args_list
        
        # Debe haber llamado a fill al menos una vez (para limpiar pantalla con paleta[0])
        assert len(fill_calls) > 0, "Debe llamar a fill para limpiar pantalla"
        
        # El primer fill debe ser con el color de la paleta (no blanco por bit 0=0)
        # Paleta[0] con BGP=0xE4 es blanco, pero el punto es que NO retornó temprano
        # Verificar que se llamó a draw_rect (indicando que se dibujaron píxeles)
        assert mock_draw_rect.called, \
            "Con LCDC=0x80 (hack educativo), debe dibujar píxeles en lugar de retornar temprano"
        assert mock_draw_rect.call_count == 160 * 144, \
            f"Debe dibujar 160*144 píxeles, pero se llamó {mock_draw_rect.call_count} veces"
        
        renderer.quit()

    @patch('src.gpu.renderer.pygame.draw.rect')
    def test_scroll_zero(self, mock_draw_rect: MagicMock) -> None:
        """
        Test: Verificar que con SCX=0 y SCY=0, el renderizado funciona normalmente.
        
        Sin scroll, el píxel (0,0) de pantalla debe mostrar el píxel (0,0) del tilemap.
        """
        mmu = MMU(None)
        renderer = Renderer(mmu, scale=1)
        renderer.screen = MagicMock()
        
        # Configurar LCDC
        mmu.write_byte(IO_LCDC, 0x91)
        mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar scroll a cero
        mmu.write_byte(IO_SCX, 0)
        mmu.write_byte(IO_SCY, 0)
        
        # Configurar tilemap básico
        mmu.write_byte(0x9800, 0x00)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que se renderizó
        renderer.screen.fill.assert_called()
        assert mock_draw_rect.called, "Debe llamar a pygame.draw.rect"
        
        renderer.quit()

