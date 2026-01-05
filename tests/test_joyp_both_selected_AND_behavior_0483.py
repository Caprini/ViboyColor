"""
Test Step 0483: JOYP con ambos grupos seleccionados (AND behavior).

Verifica que cuando ambos grupos están seleccionados (P15=0, P14=0),
bits 0-3 deben ser 1111 (0x0F) si nada está pulsado (AND de ambos grupos).
El resultado debe combinar de forma consistente.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest

try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


class TestJoypBothSelectedANDBehavior:
    """Tests para verificar que JOYP con ambos grupos seleccionados usa AND."""
    
    def test_both_selected_all_released(self):
        """
        Verifica que con ambos grupos seleccionados (P15=0, P14=0) y todos sueltos,
        bits 0-3 deben ser 1111 (0x0F) (AND de ambos grupos).
        """
        joypad = PyJoypad()
        mmu = PyMMU()
        mmu.set_joypad(joypad)
        
        # Escribir JOYP = 0x00 (P15=0, P14=0, ambos grupos seleccionados)
        # 0x00 = 0b00000000 (bit 5=0, bit 4=0)
        mmu.write(0xFF00, 0x00)
        
        # Leer JOYP
        result = mmu.read(0xFF00)
        
        # Assert: Bits 0-3 deben ser 1111 (0x0F) si nada está pulsado (AND de ambos grupos)
        low_nibble = result & 0x0F
        assert low_nibble == 0x0F, f"Bits 0-3 deben ser 0x0F (AND de ambos grupos, todos sueltos), pero son 0x{low_nibble:02X}. Result completo: 0x{result:02X}"
        
        # Verificar que el resultado combina de forma consistente
        # Bits 4-5 deben preservar la selección (deben ser 00 = ambos seleccionados)
        bits_45 = (result >> 4) & 0x03
        assert bits_45 == 0x00, f"Bits 4-5 deben preservar selección (00), pero son 0b{bits_45:02b}. Result completo: 0x{result:02X}"
    
    def test_both_selected_with_pressed_buttons(self):
        """
        Verifica que con ambos grupos seleccionados, si un botón está pulsado,
        el AND debe reflejarlo correctamente.
        """
        joypad = PyJoypad()
        mmu = PyMMU()
        mmu.set_joypad(joypad)
        
        # Presionar Right (dirección, bit 0)
        joypad.press_button(0)
        
        # Escribir JOYP = 0x00 (ambos grupos seleccionados)
        mmu.write(0xFF00, 0x00)
        
        # Leer JOYP
        result = mmu.read(0xFF00)
        
        # Assert: Bit 0 debe ser 0 (Right pulsado) porque está en ambos grupos
        bit_0 = result & 0x01
        assert bit_0 == 0x00, f"Bit 0 debe ser 0 (Right pulsado), pero es {bit_0}. Result completo: 0x{result:02X}"
        
        # Presionar A (acción, bit 0 también)
        joypad.press_button(4)  # A es índice 4
        
        # Leer JOYP de nuevo
        result2 = mmu.read(0xFF00)
        
        # Assert: Bit 0 sigue siendo 0 (ambos pulsados, AND = 0)
        bit_0_2 = result2 & 0x01
        assert bit_0_2 == 0x00, f"Bit 0 debe seguir siendo 0 (ambos pulsados), pero es {bit_0_2}. Result completo: 0x{result2:02X}"

