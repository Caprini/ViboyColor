"""
Test Step 0483: JOYP seleccionando direcciones con todos sueltos.

Verifica que cuando se selecciona direcciones (P15=0, bit 5=0),
bits 0-3 deben ser 1111 (0x0F) si nada está pulsado.
Bits 4-5 deben preservar la selección.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest

try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


class TestJoypSelectDpadDefaultAllReleased:
    """Tests para verificar que JOYP seleccionando direcciones con todos sueltos."""
    
    def test_select_dpad_default_all_released(self):
        """
        Verifica que seleccionando direcciones (P15=0, bit 5=0) con todos sueltos,
        bits 0-3 deben ser 1111 (0x0F).
        """
        joypad = PyJoypad()
        mmu = PyMMU()
        mmu.set_joypad(joypad)
        
        # Escribir JOYP = 0x10 (P15=0, P14=1, seleccionar direcciones)
        # 0x10 = 0b00010000 (bit 5=0, bit 4=1)
        mmu.write(0xFF00, 0x10)
        
        # Leer JOYP
        result = mmu.read(0xFF00)
        
        # Assert: Bits 0-3 deben ser 1111 (0x0F) si nada está pulsado
        low_nibble = result & 0x0F
        assert low_nibble == 0x0F, f"Bits 0-3 deben ser 0x0F (todos sueltos), pero son 0x{low_nibble:02X}. Result completo: 0x{result:02X}"
        
        # Assert: Bits 4-5 preservan la selección (deben ser 01 = bit 5=0, bit 4=1)
        bits_45 = (result >> 4) & 0x03
        assert bits_45 == 0x01, f"Bits 4-5 deben preservar selección (01), pero son 0b{bits_45:02b}. Result completo: 0x{result:02X}"

