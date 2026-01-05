"""
Test Step 0485: Consistencia de Select Bits

Verifica que cuando se escribe 0x30 (ningún grupo seleccionado),
el low nibble lee 0xF (todos los bits en 1, todos sueltos).

Fuente: Pan Docs - Joypad Input
- 0x30 = 0011 0000 -> P14=1, P15=1 (ninguno seleccionado)
- Cuando ningún grupo está seleccionado, el low nibble lee 0xF
"""

import os
import pytest

try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


def test_joyp_0x30_reads_0xF():
    """Test: Si se escribe 0x30, el low nibble debe leer 0xF"""
    os.environ["VIBOY_DEBUG_JOYP_TRACE"] = "1"
    
    mmu = PyMMU()
    joypad = PyJoypad()
    mmu.set_joypad(joypad)
    
    # Escribir 0x30 (ningún grupo seleccionado)
    mmu.write(0xFF00, 0x30)
    
    # Leer JOYP
    value = mmu.read(0xFF00)
    
    # Verificar: low nibble (bits 0-3) debe ser 0xF
    low_nibble = value & 0x0F
    assert low_nibble == 0x0F, f"Low nibble debería ser 0xF cuando se escribe 0x30, pero se leyó 0x{low_nibble:X}"
    
    # Verificar que el trace capturó el evento
    trace = mmu.get_joyp_trace()
    assert len(trace) > 0, "El trace debería tener al menos un evento"
    
    # El último evento debería ser un READ con select_bits = 0x03 (ninguno seleccionado)
    last_event = trace[-1]
    assert last_event['type'] == 'READ', "El último evento debería ser un READ"
    assert last_event['select_bits'] == 0x03, f"Select bits debería ser 0x03 (ninguno seleccionado), pero es 0x{last_event['select_bits']:02X}"
    assert last_event['low_nibble_read'] == 0x0F, f"Low nibble debería ser 0xF, pero es 0x{last_event['low_nibble_read']:02X}"


def test_joyp_0x30_multiple_reads_consistency():
    """Test: Múltiples lecturas con 0x30 deben leer consistentemente 0xF"""
    os.environ["VIBOY_DEBUG_JOYP_TRACE"] = "1"
    
    mmu = PyMMU()
    joypad = PyJoypad()
    mmu.set_joypad(joypad)
    
    # Escribir 0x30 una vez
    mmu.write(0xFF00, 0x30)
    
    # Leer múltiples veces
    for i in range(10):
        value = mmu.read(0xFF00)
        low_nibble = value & 0x0F
        assert low_nibble == 0x0F, f"Lectura #{i+1}: Low nibble debería ser 0xF, pero se leyó 0x{low_nibble:X}"
    
    # Verificar contador de reads sin selección
    count_none = mmu.get_joyp_reads_with_none_selected_count()
    assert count_none >= 10, f"Debería haber al menos 10 reads sin selección, pero hay {count_none}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

