"""
Test Step 0483: JOYP sin selección lee todos los bits en 1.

Verifica que cuando bits 4-5 = 11 (ningún grupo seleccionado),
el low nibble debe ser 0x0F (todos los bits en 1 = no pulsados).
Con bits 6-7 en 1, debe ser 0xFF si preservas 4-5.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest

try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


class TestJoypNoSelectReadsOnes:
    """Tests para verificar que JOYP sin selección lee todos los bits en 1."""
    
    def test_no_select_reads_ones(self):
        """
        Verifica que sin seleccionar ningún grupo (bits 4-5 = 11),
        el low nibble debe ser 0x0F (todos los bits en 1 = no pulsados).
        """
        joypad = PyJoypad()
        mmu = PyMMU()
        mmu.set_joypad(joypad)
        
        # Escribir JOYP con bits4=1 y bits5=1 (sin seleccionar ningún grupo)
        # 0x30 = 0b00110000 (bits 4-5 = 11, bits 6-7 = 00, pero MMU los pondrá a 1)
        mmu.write(0xFF00, 0x30)
        
        # Leer JOYP
        result = mmu.read(0xFF00)
        
        # Assert: Low nibble debe ser 0x0F (todos los bits en 1 = no pulsados)
        low_nibble = result & 0x0F
        assert low_nibble == 0x0F, f"Low nibble debe ser 0x0F, pero es 0x{low_nibble:02X}. Result completo: 0x{result:02X}"
        
        # Assert: Con bits 6-7 en 1, debe ser 0xFF si preservas 4-5
        # O al menos bits 6-7 deben ser 1
        bits_67 = (result >> 6) & 0x03
        assert bits_67 == 0x03, f"Bits 6-7 deben ser 1, pero son 0b{bits_67:02b}. Result completo: 0x{result:02X}"
        
        # Verificar que bits 4-5 se preservan (deben ser 11 = 0x30)
        bits_45 = (result >> 4) & 0x03
        assert bits_45 == 0x03, f"Bits 4-5 deben preservarse como 11, pero son 0b{bits_45:02b}. Result completo: 0x{result:02X}"

