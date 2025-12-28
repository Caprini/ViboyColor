"""
Tests para el subsistema del Joypad (C++).

Este módulo valida la implementación del registro P1 (0xFF00) y el mapeo
de botones del Joypad de la Game Boy.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest

# Intentar importar componentes C++
try:
    from viboy_core import PyJoypad, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Los tests requieren el módulo C++ compilado.", allow_module_level=True)


class TestJoypad:
    """Tests para el subsistema del Joypad C++."""
    
    def test_joypad_initial_state(self):
        """Verifica que el Joypad inicia con todos los botones sueltos."""
        joypad = PyJoypad()
        
        # El registro P1 debe leer 0xCF cuando ninguna fila está seleccionada
        # (bits 6-7 siempre a 1, bits 4-5 a 1 = ninguna fila, bits 0-3 a 1 = todos sueltos)
        assert joypad.read_p1() == 0xCF
    
    def test_joypad_selection_direction(self):
        """Verifica que escribir en P1 selecciona la fila de dirección correctamente."""
        joypad = PyJoypad()
        
        # Presionar Derecha (dirección, índice 0)
        joypad.press_button(0)
        
        # Seleccionar fila de dirección (bit 4 = 0)
        # Escribir 0x20 = 0b00100000 (bit 5=1, bit 4=0)
        joypad.write_p1(0x20)
        
        # Leer P1. Debería mostrar Derecha presionada (bit 0 = 0)
        # Resultado esperado: 0xDE = 1101 1110
        # (bits 6-7=1, bit 5=1, bit 4=0 seleccionado, bit 0=0 presionado, bits 1-3=1 sueltos)
        result = joypad.read_p1()
        assert result == 0xDE, f"Esperado 0xDE, obtenido 0x{result:02X}"
    
    def test_joypad_selection_action(self):
        """Verifica que escribir en P1 selecciona la fila de acción correctamente."""
        joypad = PyJoypad()
        
        # Presionar A (acción, índice 4)
        joypad.press_button(4)
        
        # Seleccionar fila de acción (bit 5 = 0)
        # Escribir 0x10 = 0b00010000 (bit 5=0, bit 4=1)
        joypad.write_p1(0x10)
        
        # Leer P1. Debería mostrar A presionado (bit 0 = 0)
        # Resultado esperado: 0xEE = 1110 1110
        # (bits 6-7=1, bit 5=0 seleccionado, bit 4=1, bit 0=0 presionado, bits 1-3=1 sueltos)
        result = joypad.read_p1()
        assert result == 0xEE, f"Esperado 0xEE, obtenido 0x{result:02X}"
    
    def test_joypad_multiple_buttons(self):
        """Verifica que múltiples botones se pueden presionar simultáneamente."""
        joypad = PyJoypad()
        
        # Presionar Derecha (dirección) y A (acción)
        joypad.press_button(0)  # Derecha
        joypad.press_button(4)  # A
        
        # Seleccionar fila de dirección (bit 4 = 0)
        joypad.write_p1(0x20)
        result_dir = joypad.read_p1()
        # Debería mostrar Derecha presionada
        assert result_dir == 0xDE, f"Esperado 0xDE, obtenido 0x{result_dir:02X}"
        
        # Seleccionar fila de acción (bit 5 = 0)
        joypad.write_p1(0x10)
        result_action = joypad.read_p1()
        # Debería mostrar A presionado
        assert result_action == 0xEE, f"Esperado 0xEE, obtenido 0x{result_action:02X}"
    
    def test_joypad_release_button(self):
        """Verifica que los botones se pueden soltar correctamente."""
        joypad = PyJoypad()
        
        # Presionar y luego soltar Derecha
        joypad.press_button(0)
        joypad.write_p1(0x20)  # Seleccionar dirección
        assert joypad.read_p1() == 0xDE  # Derecha presionada
        
        joypad.release_button(0)
        assert joypad.read_p1() == 0xDF  # Todos sueltos (0xDF = 1101 1111)
    
    def test_joypad_mmu_integration(self):
        """Verifica la integración del Joypad con la MMU."""
        joypad = PyJoypad()
        mmu = PyMMU()
        
        # Conectar Joypad a MMU
        mmu.set_joypad(joypad)
        
        # Presionar Derecha
        joypad.press_button(0)
        
        # Seleccionar fila de dirección en P1 (0xFF00)
        mmu.write(0xFF00, 0x20)
        
        # Leer P1 desde MMU
        result = mmu.read(0xFF00)
        assert result == 0xDE, f"Esperado 0xDE, obtenido 0x{result:02X}"
    
    def test_joypad_all_direction_buttons(self):
        """Verifica todos los botones de dirección."""
        joypad = PyJoypad()
        
        # Mapeo: 0=Derecha, 1=Izquierda, 2=Arriba, 3=Abajo
        test_cases = [
            (0, 0xDE),  # Derecha: bit 0 = 0
            (1, 0xDD),  # Izquierda: bit 1 = 0
            (2, 0xDB),  # Arriba: bit 2 = 0
            (3, 0xD7),  # Abajo: bit 3 = 0
        ]
        
        for button_index, expected_value in test_cases:
            joypad = PyJoypad()  # Resetear para cada test
            joypad.press_button(button_index)
            joypad.write_p1(0x20)  # Seleccionar dirección
            result = joypad.read_p1()
            assert result == expected_value, (
                f"Botón {button_index}: Esperado 0x{expected_value:02X}, "
                f"obtenido 0x{result:02X}"
            )
    
    def test_joypad_all_action_buttons(self):
        """Verifica todos los botones de acción."""
        joypad = PyJoypad()
        
        # Mapeo: 4=A, 5=B, 6=Select, 7=Start
        test_cases = [
            (4, 0xEE),  # A: bit 0 = 0
            (5, 0xED),  # B: bit 1 = 0
            (6, 0xEB),  # Select: bit 2 = 0
            (7, 0xE7),  # Start: bit 3 = 0
        ]
        
        for button_index, expected_value in test_cases:
            joypad = PyJoypad()  # Resetear para cada test
            joypad.press_button(button_index)
            joypad.write_p1(0x10)  # Seleccionar acción
            result = joypad.read_p1()
            assert result == expected_value, (
                f"Botón {button_index}: Esperado 0x{expected_value:02X}, "
                f"obtenido 0x{result:02X}"
            )

