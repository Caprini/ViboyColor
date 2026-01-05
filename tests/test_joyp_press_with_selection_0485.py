"""
Test Step 0485: JOYP Press con Selección

Verifica que cuando se selecciona un grupo (botones o dpad) y se presiona
un botón, el bit correspondiente se lee como 0 (pulsado).

Fuente: Pan Docs - Joypad Input
- Selección activa: bit a 0 (P14=0 para botones, P15=0 para dpad)
- Botón pulsado: bit a 0
- Botón suelto: bit a 1
"""

import os
import pytest

try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


def test_joyp_press_start_with_buttons_selected():
    """Test: Seleccionar botones (P14=0), presionar START (bit 3), leer y verificar bit 3 = 0"""
    os.environ["VIBOY_DEBUG_JOYP_TRACE"] = "1"
    
    mmu = PyMMU()
    joypad = PyJoypad()
    mmu.set_joypad(joypad)
    
    # Seleccionar botones (P14=0, P15=1) -> escribir 0x20
    mmu.write(0xFF00, 0x20)
    
    # Presionar START (bit 3 del grupo de botones)
    # START es índice 7 en press_button (4-7: A, B, Select, Start)
    joypad.press_button(7)  # START = índice 7
    
    # Leer JOYP
    value = mmu.read(0xFF00)
    
    # Verificar: bit 3 debe ser 0 (pulsado)
    assert (value & 0x08) == 0, f"START debería estar pulsado (bit 3=0), pero se leyó 0x{value:02X}"
    
    # Verificar que el trace capturó el evento
    trace = mmu.get_joyp_trace()
    assert len(trace) > 0, "El trace debería tener al menos un evento"
    
    # El último evento debería ser un READ con select_bits indicando botones seleccionados
    last_event = trace[-1]
    assert last_event['type'] == 'READ', "El último evento debería ser un READ"
    assert (last_event['select_bits'] & 0x01) == 0, "P14 debería estar en 0 (botones seleccionados)"
    assert (last_event['value_read'] & 0x08) == 0, "Bit 3 (START) debería ser 0 (pulsado)"


def test_joyp_press_down_with_dpad_selected():
    """Test: Seleccionar dpad (P15=0), presionar DOWN (bit 3), leer y verificar bit 3 = 0"""
    os.environ["VIBOY_DEBUG_JOYP_TRACE"] = "1"
    
    mmu = PyMMU()
    joypad = PyJoypad()
    mmu.set_joypad(joypad)
    
    # Seleccionar dpad (P14=1, P15=0) -> escribir 0x10
    mmu.write(0xFF00, 0x10)
    
    # Presionar DOWN (bit 3 del grupo dpad)
    # DOWN es índice 3 en press_button (0-3: Derecha, Izquierda, Arriba, Abajo)
    joypad.press_button(3)  # DOWN = índice 3
    
    # Leer JOYP
    value = mmu.read(0xFF00)
    
    # Verificar: bit 3 debe ser 0 (pulsado)
    assert (value & 0x08) == 0, f"DOWN debería estar pulsado (bit 3=0), pero se leyó 0x{value:02X}"
    
    # Verificar que el trace capturó el evento
    trace = mmu.get_joyp_trace()
    assert len(trace) > 0, "El trace debería tener al menos un evento"
    
    # El último evento debería ser un READ con select_bits indicando dpad seleccionado
    last_event = trace[-1]
    assert last_event['type'] == 'READ', "El último evento debería ser un READ"
    assert (last_event['select_bits'] & 0x02) == 0, "P15 debería estar en 0 (dpad seleccionado)"
    assert (last_event['value_read'] & 0x08) == 0, "Bit 3 (DOWN) debería ser 0 (pulsado)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

