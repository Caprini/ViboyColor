"""
Tests unitarios para el decodificador de tiles 2bpp

Verifica:
- Decodificación correcta de líneas de tiles en formato 2bpp
- Combinación correcta de bits bajos y altos
- Valores de color resultantes (0-3)
"""

import pytest
from src.gpu.renderer import decode_tile_line


class TestTileDecoder:
    """Suite de tests para el decodificador de tiles 2bpp"""

    def test_decode_2bpp_line_basic(self) -> None:
        """
        Test básico: decodificar una línea de tile 2bpp
        
        Byte1 (LSB): 0x3C = 00111100
        Byte2 (MSB): 0x7E = 01111110
        
        Formato: color = (MSB << 1) | LSB
        
        Píxel 0: Bit 7 -> LSB=0, MSB=0 -> Color 0 (0b00)
        Píxel 1: Bit 6 -> LSB=0, MSB=1 -> Color 2 (0b10)
        Píxel 2: Bit 5 -> LSB=1, MSB=1 -> Color 3 (0b11)
        Píxel 3: Bit 4 -> LSB=1, MSB=1 -> Color 3 (0b11)
        Píxel 4: Bit 3 -> LSB=1, MSB=1 -> Color 3 (0b11)
        Píxel 5: Bit 2 -> LSB=1, MSB=1 -> Color 3 (0b11)
        Píxel 6: Bit 1 -> LSB=0, MSB=1 -> Color 2 (0b10)
        Píxel 7: Bit 0 -> LSB=0, MSB=0 -> Color 0 (0b00)
        """
        byte1 = 0x3C  # 00111100 (LSB)
        byte2 = 0x7E  # 01111110 (MSB)
        
        result = decode_tile_line(byte1, byte2)
        
        # Verificar longitud (8 píxeles)
        assert len(result) == 8
        
        # Verificar valores esperados
        # Bit 7: LSB=0, MSB=0 -> 0
        assert result[0] == 0
        # Bit 6: LSB=0, MSB=1 -> (1<<1)|0 = 2
        assert result[1] == 2
        # Bits 5-2: LSB=1, MSB=1 -> (1<<1)|1 = 3
        assert result[2] == 3
        assert result[3] == 3
        assert result[4] == 3
        assert result[5] == 3
        # Bit 1: LSB=0, MSB=1 -> (1<<1)|0 = 2
        assert result[6] == 2
        # Bit 0: LSB=0, MSB=0 -> 0
        assert result[7] == 0

    def test_decode_2bpp_line_all_colors(self) -> None:
        """
        Test: verificar que podemos obtener todos los valores de color (0-3)
        
        Byte1 (LSB): 0x00 = 00000000 (todos los bits bajos a 0)
        Byte2 (MSB): 0xFF = 11111111 (todos los bits altos a 1)
        
        Resultado esperado: todos los píxeles serán Color 2 (0b10)
        porque: color = (MSB << 1) | LSB = (1 << 1) | 0 = 2
        """
        byte1 = 0x00  # 00000000 (LSB)
        byte2 = 0xFF  # 11111111 (MSB)
        
        result = decode_tile_line(byte1, byte2)
        
        # Todos los píxeles deben ser Color 2 (LSB=0, MSB=1 -> (1<<1)|0 = 2)
        assert all(pixel == 2 for pixel in result)

    def test_decode_2bpp_line_color_1(self) -> None:
        """
        Test: verificar Color 1 (LSB=1, MSB=0)
        
        Byte1 (LSB): 0xFF = 11111111 (todos los bits bajos a 1)
        Byte2 (MSB): 0x00 = 00000000 (todos los bits altos a 0)
        
        Resultado esperado: todos los píxeles serán Color 1 (0b01)
        porque: color = (MSB << 1) | LSB = (0 << 1) | 1 = 1
        """
        byte1 = 0xFF  # 11111111 (LSB)
        byte2 = 0x00  # 00000000 (MSB)
        
        result = decode_tile_line(byte1, byte2)
        
        # Todos los píxeles deben ser Color 1 (LSB=1, MSB=0 -> (0<<1)|1 = 1)
        assert all(pixel == 1 for pixel in result)

    def test_decode_2bpp_line_color_3(self) -> None:
        """
        Test: verificar Color 3 (bit bajo=1, bit alto=1)
        
        Byte1: 0xFF = 11111111 (todos los bits bajos a 1)
        Byte2: 0xFF = 11111111 (todos los bits altos a 1)
        
        Resultado esperado: todos los píxeles serán Color 3 (0b11)
        """
        byte1 = 0xFF  # 11111111
        byte2 = 0xFF  # 11111111
        
        result = decode_tile_line(byte1, byte2)
        
        # Todos los píxeles deben ser Color 3 (bit bajo=1, bit alto=1)
        assert all(pixel == 3 for pixel in result)

    def test_decode_2bpp_line_color_0(self) -> None:
        """
        Test: verificar Color 0 (bit bajo=0, bit alto=0)
        
        Byte1: 0x00 = 00000000 (todos los bits bajos a 0)
        Byte2: 0x00 = 00000000 (todos los bits altos a 0)
        
        Resultado esperado: todos los píxeles serán Color 0 (0b00)
        """
        byte1 = 0x00  # 00000000
        byte2 = 0x00  # 00000000
        
        result = decode_tile_line(byte1, byte2)
        
        # Todos los píxeles deben ser Color 0 (bit bajo=0, bit alto=0)
        assert all(pixel == 0 for pixel in result)

    def test_decode_2bpp_line_pattern(self) -> None:
        """
        Test: verificar un patrón más complejo
        
        Byte1 (LSB): 0xAA = 10101010
        Byte2 (MSB): 0x55 = 01010101
        
        Resultado esperado: 
        - Píxeles pares (0,2,4,6): LSB=1, MSB=0 -> Color 1 (0b01)
        - Píxeles impares (1,3,5,7): LSB=0, MSB=1 -> Color 2 (0b10)
        """
        byte1 = 0xAA  # 10101010 (LSB)
        byte2 = 0x55  # 01010101 (MSB)
        
        result = decode_tile_line(byte1, byte2)
        
        # Píxeles pares: LSB=1, MSB=0 -> (0<<1)|1 = 1
        assert result[0] == 1
        assert result[2] == 1
        assert result[4] == 1
        assert result[6] == 1
        
        # Píxeles impares: LSB=0, MSB=1 -> (1<<1)|0 = 2
        assert result[1] == 2
        assert result[3] == 2
        assert result[5] == 2
        assert result[7] == 2

