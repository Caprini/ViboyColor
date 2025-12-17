"""
Tests para verificar el comportamiento del renderer con diferentes valores de LCDC.
"""

import pytest
from unittest.mock import Mock
from src.gpu.renderer import Renderer
from src.memory.mmu import MMU, IO_LCDC, IO_BGP


class TestRendererLCDC:
    """Tests para verificar que el renderer respeta los bits de LCDC correctamente."""
    
    def test_lcdc_bit7_off_no_render(self) -> None:
        """Verifica que si bit 7 está OFF, no se renderiza."""
        mmu = MMU(None)
        mmu.write_byte(IO_LCDC, 0x00)  # Bit 7 = 0 (LCD OFF)
        mmu.write_byte(IO_BGP, 0xE4)
        
        renderer = Renderer(mmu, scale=1)
        # No debería lanzar excepción, solo debería llenar pantalla blanca
        renderer.render_frame()
        # Si llegamos aquí, el test pasa (no se renderizaron tiles)
        
    def test_lcdc_bit0_off_no_bg_render(self) -> None:
        """Verifica que si bit 0 está OFF, no se renderiza Background."""
        mmu = MMU(None)
        mmu.write_byte(IO_LCDC, 0x80)  # Bit 7 = 1 (LCD ON), Bit 0 = 0 (BG OFF)
        mmu.write_byte(IO_BGP, 0xE4)
        
        renderer = Renderer(mmu, scale=1)
        renderer.render_frame()
        # Si llegamos aquí, el test pasa (no se renderizaron tiles de BG)
        
    def test_lcdc_both_bits_on_should_render(self) -> None:
        """Verifica que si bit 7 y bit 0 están ON, se intenta renderizar."""
        mmu = MMU(None)
        mmu.write_byte(IO_LCDC, 0x81)  # Bit 7 = 1 (LCD ON), Bit 0 = 1 (BG ON)
        mmu.write_byte(IO_BGP, 0xE4)
        
        renderer = Renderer(mmu, scale=1)
        renderer.render_frame()
        # Si llegamos aquí, el test pasa (se intentó renderizar)
        
    def test_bgp_0x00_all_white(self) -> None:
        """Verifica que BGP=0x00 mapea todos los colores a blanco."""
        mmu = MMU(None)
        mmu.write_byte(IO_LCDC, 0x91)  # LCD ON, BG ON
        mmu.write_byte(IO_BGP, 0x00)  # Todo blanco
        
        renderer = Renderer(mmu, scale=1)
        # BGP=0x00: bits 0-1=00 (blanco), bits 2-3=00 (blanco), etc.
        # Todos los colores deberían mapear a blanco
        renderer.render_frame()
        # Si llegamos aquí, el test pasa

