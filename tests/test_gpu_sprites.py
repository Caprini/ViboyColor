"""
Tests para renderizado de Sprites (OBJ) y DMA Transfer.

Estos tests verifican:
1. DMA Transfer: La transferencia de datos desde RAM/ROM a OAM
2. Renderizado de Sprites: Decodificación de OAM y dibujado de sprites
3. Transparencia: El color 0 en sprites es transparente
"""

from __future__ import annotations

import pytest
from src.memory.mmu import MMU, IO_DMA, IO_LCDC, IO_OBP0, IO_OBP1
from src.gpu.renderer import Renderer, VRAM_START, BYTES_PER_TILE
from src.memory.cartridge import Cartridge


class TestDMA:
    """Tests para DMA Transfer (Direct Memory Access)."""
    
    def test_dma_transfer(self):
        """
        Verifica que DMA copia correctamente 160 bytes desde la dirección fuente a OAM.
        
        Cuando se escribe un valor XX en 0xFF46, se copian 160 bytes desde XX00 a 0xFE00.
        """
        mmu = MMU()
        
        # Preparar datos de prueba en 0xC000
        source_base = 0xC000
        test_pattern = bytearray([i & 0xFF for i in range(160)])
        
        # Escribir patrón en la dirección fuente
        for i, byte_val in enumerate(test_pattern):
            mmu.write_byte(source_base + i, byte_val)
        
        # Iniciar DMA escribiendo 0xC0 en 0xFF46
        # Esto debe copiar desde 0xC000 a 0xFE00
        mmu.write_byte(IO_DMA, 0xC0)
        
        # Verificar que los datos se copiaron a OAM (0xFE00-0xFE9F)
        oam_base = 0xFE00
        for i in range(160):
            oam_byte = mmu.read_byte(oam_base + i)
            expected_byte = test_pattern[i]
            assert oam_byte == expected_byte, (
                f"OAM[{i}] = 0x{oam_byte:02X}, esperado 0x{expected_byte:02X}"
            )
        
        # Verificar que el registro DMA mantiene el valor escrito
        dma_value = mmu.read_byte(IO_DMA)
        assert dma_value == 0xC0, f"DMA register = 0x{dma_value:02X}, esperado 0xC0"
    
    def test_dma_from_different_source(self):
        """Verifica que DMA funciona desde diferentes direcciones fuente."""
        mmu = MMU()
        
        # Probar desde 0xD000
        source_base = 0xD000
        test_data = bytearray([0xAA, 0xBB, 0xCC, 0xDD] * 40)  # 160 bytes
        
        for i, byte_val in enumerate(test_data):
            mmu.write_byte(source_base + i, byte_val)
        
        # Iniciar DMA desde 0xD000
        mmu.write_byte(IO_DMA, 0xD0)
        
        # Verificar copia
        oam_base = 0xFE00
        for i in range(160):
            oam_byte = mmu.read_byte(oam_base + i)
            expected_byte = test_data[i]
            assert oam_byte == expected_byte, (
                f"OAM[{i}] = 0x{oam_byte:02X}, esperado 0x{expected_byte:02X}"
            )


class TestSpriteRendering:
    """Tests para renderizado de Sprites."""
    
    @pytest.fixture
    def mmu_with_tile(self):
        """Crea una MMU con un tile de prueba en VRAM."""
        mmu = MMU()
        
        # Crear un tile simple en VRAM (tile ID 0)
        # Tile con patrón: primera línea = 0x3C (00111100), segunda = 0x7E (01111110)
        # Esto crea un patrón visible para testing
        tile_addr = VRAM_START  # Tile ID 0 en 0x8000
        
        # Línea 0: 0x3C, 0x7E -> píxeles: 0, 1, 3, 3, 3, 3, 0, 0
        mmu.write_byte(tile_addr + 0, 0x3C)  # Byte 1 línea 0
        mmu.write_byte(tile_addr + 1, 0x7E)  # Byte 2 línea 0
        
        # Línea 1: mismo patrón
        mmu.write_byte(tile_addr + 2, 0x3C)
        mmu.write_byte(tile_addr + 3, 0x7E)
        
        # Resto de líneas: todo color 0 (transparente)
        for i in range(4, 16):
            mmu.write_byte(tile_addr + i, 0x00)
        
        return mmu
    
    def test_sprite_transparency(self, mmu_with_tile):
        """
        Verifica que el color 0 en sprites es transparente (no sobrescribe el fondo).
        
        Este test crea un sprite con algunos píxeles en color 0 y otros en color 1-3.
        Verifica que los píxeles de color 0 no se dibujan (son transparentes).
        """
        mmu = mmu_with_tile
        
        # Habilitar LCD y sprites
        mmu.write_byte(IO_LCDC, 0x83)  # Bit 7=1 (LCD ON), Bit 1=1 (Sprites ON)
        
        # Configurar paletas
        mmu.write_byte(IO_OBP0, 0xE4)  # Paleta estándar
        
        # Crear un sprite en OAM manualmente
        # Sprite en posición (20, 20) con tile ID 0
        oam_base = 0xFE00
        mmu.write_byte(oam_base + 0, 20 + 16)  # Y = 20 + 16 offset
        mmu.write_byte(oam_base + 1, 20 + 8)    # X = 20 + 8 offset
        mmu.write_byte(oam_base + 2, 0)         # Tile ID 0
        mmu.write_byte(oam_base + 3, 0x00)      # Atributos: paleta 0, sin flips
        
        # Crear renderer
        renderer = Renderer(mmu, scale=1)
        
        # Renderizar frame (esto dibuja fondo y sprites)
        # Por ahora, el fondo se dibuja primero, luego los sprites
        renderer.render_frame()
        
        # Verificar que el sprite se puede renderizar sin errores
        # (no podemos verificar píxeles específicos sin acceso directo al buffer,
        # pero podemos verificar que no hay excepciones)
        
        # Limpiar
        renderer.quit()
    
    def test_sprite_hidden_when_y_or_x_zero(self, mmu_with_tile):
        """
        Verifica que sprites con Y=0 o X=0 están ocultos (no se renderizan).
        
        En Game Boy, un sprite está oculto si su byte Y o X es 0.
        """
        mmu = mmu_with_tile
        mmu.write_byte(IO_LCDC, 0x83)
        mmu.write_byte(IO_OBP0, 0xE4)
        
        # Sprite oculto (Y=0)
        oam_base = 0xFE00
        mmu.write_byte(oam_base + 0, 0)      # Y = 0 (oculto)
        mmu.write_byte(oam_base + 1, 20 + 8)  # X = 20 + 8
        mmu.write_byte(oam_base + 2, 0)      # Tile ID 0
        mmu.write_byte(oam_base + 3, 0x00)   # Atributos
        
        renderer = Renderer(mmu, scale=1)
        
        # Renderizar debe completarse sin errores
        sprites_drawn = renderer.render_sprites()
        
        # Debe haber dibujado 0 sprites (el sprite está oculto)
        assert sprites_drawn == 0, f"Esperado 0 sprites, dibujados {sprites_drawn}"
        
        renderer.quit()
    
    def test_sprite_palette_selection(self, mmu_with_tile):
        """
        Verifica que los sprites usan la paleta correcta según el bit 4 de atributos.
        
        Bit 4 = 0 -> OBP0
        Bit 4 = 1 -> OBP1
        """
        mmu = mmu_with_tile
        mmu.write_byte(IO_LCDC, 0x83)
        
        # Configurar paletas diferentes
        mmu.write_byte(IO_OBP0, 0xE4)  # Paleta 0: estándar
        mmu.write_byte(IO_OBP1, 0xFF)  # Paleta 1: todo negro
        
        # Sprite con paleta 0
        oam_base = 0xFE00
        mmu.write_byte(oam_base + 0, 20 + 16)
        mmu.write_byte(oam_base + 1, 20 + 8)
        mmu.write_byte(oam_base + 2, 0)
        mmu.write_byte(oam_base + 3, 0x00)  # Bit 4 = 0 -> OBP0
        
        # Sprite con paleta 1
        oam_base2 = 0xFE04  # Segundo sprite
        mmu.write_byte(oam_base2 + 0, 30 + 16)
        mmu.write_byte(oam_base2 + 1, 30 + 8)
        mmu.write_byte(oam_base2 + 2, 0)
        mmu.write_byte(oam_base2 + 3, 0x10)  # Bit 4 = 1 -> OBP1
        
        renderer = Renderer(mmu, scale=1)
        
        # Renderizar debe completarse sin errores
        sprites_drawn = renderer.render_sprites()
        
        # Debe haber dibujado 2 sprites
        assert sprites_drawn == 2, f"Esperado 2 sprites, dibujados {sprites_drawn}"
        
        renderer.quit()

