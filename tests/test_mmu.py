"""
Tests unitarios para la MMU (Memory Management Unit)

Verifica:
- Lectura/escritura de bytes (8 bits)
- Lectura/escritura de palabras (16 bits) con Little-Endian
- Comportamiento en límites del espacio de direcciones
"""

import pytest
from src.memory.mmu import MMU


class TestMMU:
    """Suite de tests para la clase MMU"""

    def test_read_write_byte(self) -> None:
        """Test básico: escribir y leer un byte"""
        mmu = MMU()
        
        # Escribimos 0xAB en la dirección 0x1000
        mmu.write_byte(0x1000, 0xAB)
        
        # Leemos y verificamos que obtenemos 0xAB
        assert mmu.read_byte(0x1000) == 0xAB

    def test_write_byte_wraps_value(self) -> None:
        """Test: escribir un valor > 0xFF hace wrap-around"""
        mmu = MMU()
        
        # Escribimos 0x1AB (valor > 0xFF)
        mmu.write_byte(0x2000, 0x1AB)
        
        # Debe hacer wrap-around: 0x1AB & 0xFF = 0xAB
        assert mmu.read_byte(0x2000) == 0xAB

    def test_write_byte_negative_value(self) -> None:
        """Test: escribir un valor negativo se convierte correctamente"""
        mmu = MMU()
        
        # Escribimos -1 (que en complemento a 2 es 0xFF)
        mmu.write_byte(0x3000, -1)
        
        # Debe convertirse a 0xFF
        assert mmu.read_byte(0x3000) == 0xFF

    def test_read_word_little_endian(self) -> None:
        """
        Test CRÍTICO: leer palabra de 16 bits en formato Little-Endian.
        
        En Little-Endian:
        - Byte en addr es LSB (menos significativo)
        - Byte en addr+1 es MSB (más significativo)
        - Resultado: (MSB << 8) | LSB
        """
        mmu = MMU()
        
        # Escribimos 0xCD en 0x1000 (LSB)
        mmu.write_byte(0x1000, 0xCD)
        # Escribimos 0xAB en 0x1001 (MSB)
        mmu.write_byte(0x1001, 0xAB)
        
        # read_word(0x1000) debe devolver 0xABCD
        # (0xAB << 8) | 0xCD = 0xAB00 | 0xCD = 0xABCD
        result = mmu.read_word(0x1000)
        assert result == 0xABCD, f"Esperado 0xABCD, obtenido 0x{result:04X}"

    def test_write_word_little_endian(self) -> None:
        """
        Test CRÍTICO: escribir palabra de 16 bits en formato Little-Endian.
        
        Al escribir 0x1234:
        - LSB (0x34) debe ir a addr
        - MSB (0x12) debe ir a addr+1
        """
        mmu = MMU()
        
        # Escribimos 0x1234 usando write_word
        mmu.write_word(0x2000, 0x1234)
        
        # Verificamos que los bytes individuales están en el orden correcto
        lsb = mmu.read_byte(0x2000)
        msb = mmu.read_byte(0x2001)
        
        assert lsb == 0x34, f"LSB esperado 0x34, obtenido 0x{lsb:02X}"
        assert msb == 0x12, f"MSB esperado 0x12, obtenido 0x{msb:02X}"
        
        # Verificamos que read_word devuelve el valor original
        assert mmu.read_word(0x2000) == 0x1234

    def test_read_write_word_roundtrip(self) -> None:
        """Test: escribir y leer una palabra completa (roundtrip)"""
        mmu = MMU()
        
        # Escribimos varios valores y verificamos que se leen correctamente
        test_values = [0x0000, 0x0001, 0x00FF, 0x0100, 0x1234, 0xABCD, 0xFFFF]
        
        for value in test_values:
            mmu.write_word(0x3000, value)
            read_value = mmu.read_word(0x3000)
            assert read_value == value, f"Roundtrip falló: escrito 0x{value:04X}, leído 0x{read_value:04X}"

    def test_write_word_wraps_value(self) -> None:
        """Test: escribir un valor > 0xFFFF hace wrap-around"""
        mmu = MMU()
        
        # Escribimos 0x1ABCD (valor > 0xFFFF)
        mmu.write_word(0x4000, 0x1ABCD)
        
        # Debe hacer wrap-around: 0x1ABCD & 0xFFFF = 0xABCD
        assert mmu.read_word(0x4000) == 0xABCD

    def test_address_wrap_around(self) -> None:
        """Test: direcciones fuera de rango hacen wrap-around"""
        mmu = MMU()
        
        # Escribimos en dirección que excede 0xFFFF
        mmu.write_byte(0x1FFFF, 0x42)
        
        # Debe hacer wrap-around: 0x1FFFF & 0xFFFF = 0xFFFF
        assert mmu.read_byte(0xFFFF) == 0x42

    def test_read_word_at_boundary(self) -> None:
        """Test: leer palabra en el límite del espacio de direcciones"""
        mmu = MMU()
        
        # Escribimos bytes en 0xFFFE y 0xFFFF
        mmu.write_byte(0xFFFE, 0x34)
        mmu.write_byte(0xFFFF, 0x12)
        
        # Leemos palabra en 0xFFFE
        result = mmu.read_word(0xFFFE)
        assert result == 0x1234

    def test_write_word_at_boundary(self) -> None:
        """Test: escribir palabra en el límite del espacio de direcciones"""
        mmu = MMU()
        
        # Escribimos palabra en 0xFFFE (última posición válida para write_word)
        mmu.write_word(0xFFFE, 0x5678)
        
        # Verificamos que se escribió correctamente
        assert mmu.read_byte(0xFFFE) == 0x78
        assert mmu.read_byte(0xFFFF) == 0x56
        
        # Verificamos que read_word devuelve el valor correcto
        assert mmu.read_word(0xFFFE) == 0x5678

    def test_memory_initialized_to_zero(self) -> None:
        """Test: la memoria se inicializa a cero"""
        mmu = MMU()
        
        # Verificamos que todas las direcciones están en 0
        assert mmu.read_byte(0x0000) == 0x00
        assert mmu.read_byte(0x7FFF) == 0x00
        assert mmu.read_byte(0xFFFF) == 0x00
        assert mmu.read_word(0x1000) == 0x0000

    def test_multiple_writes_same_address(self) -> None:
        """Test: múltiples escrituras en la misma dirección sobrescriben"""
        mmu = MMU()
        
        # Escribimos varios valores en la misma dirección
        mmu.write_byte(0x5000, 0x11)
        assert mmu.read_byte(0x5000) == 0x11
        
        mmu.write_byte(0x5000, 0x22)
        assert mmu.read_byte(0x5000) == 0x22
        
        mmu.write_byte(0x5000, 0x33)
        assert mmu.read_byte(0x5000) == 0x33

    def test_little_endian_example_from_docs(self) -> None:
        """
        Test: ejemplo específico mencionado en la documentación.
        
        Si en 0x1000 hay 0xCD y en 0x1001 hay 0xAB,
        read_word(0x1000) debe devolver 0xABCD.
        """
        mmu = MMU()
        
        mmu.write_byte(0x1000, 0xCD)
        mmu.write_byte(0x1001, 0xAB)
        
        result = mmu.read_word(0x1000)
        assert result == 0xABCD, f"Ejemplo de docs falló: esperado 0xABCD, obtenido 0x{result:04X}"

