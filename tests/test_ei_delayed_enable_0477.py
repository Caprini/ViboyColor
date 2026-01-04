"""
Step 0477: Test para verificar que EI habilita IME con retraso de 1 instrucción.

Este test valida la implementación de EI delayed enable según Pan Docs:
"The interrupt master enable flag is set one instruction after EI is executed."

Verifica:
- IME no se activa inmediatamente después de ejecutar EI
- IME se activa después de ejecutar la siguiente instrucción
- ei_pending es True inmediatamente después de EI
- ei_pending es False después de la siguiente instrucción
- ime_set_events_count se incrementa cuando IME se activa
"""

import pytest

try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)

from tests.helpers_cpu import load_program, TEST_EXEC_BASE


class TestEIDelayedEnable:
    """Tests para verificar que EI habilita IME con retraso de 1 instrucción"""
    
    def test_ei_delayed_enable_basic(self):
        """
        Test: Verificar que IME se activa después de la siguiente instrucción.
        
        - Estado inicial: IME=0
        - Ejecutar EI
        - Verificar: IME=0, ei_pending=True
        - Ejecutar NOP (siguiente instrucción)
        - Verificar: IME=1, ei_pending=False, ime_set_events_count=1
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Estado inicial: IME debe estar en 0
        assert cpu.get_ime() == 0, "IME debe iniciar en 0"
        assert cpu.get_ei_pending() == False, "ei_pending debe iniciar en False"
        assert cpu.get_ime_set_events_count() == 0, "ime_set_events_count debe iniciar en 0"
        
        # Cargar programa: EI, NOP
        load_program(mmu, regs, [0xFB, 0x00])  # EI, NOP
        
        # Ejecutar EI
        cpu.step()  # EI
        
        # Verificar que IME NO se activó inmediatamente
        assert cpu.get_ime() == 0, "IME NO debe activarse inmediatamente después de EI"
        assert cpu.get_ei_pending() == True, "ei_pending debe ser True después de EI"
        assert cpu.get_ime_set_events_count() == 0, "ime_set_events_count no debe incrementarse hasta la siguiente instrucción"
        assert cpu.get_last_ei_pc() == TEST_EXEC_BASE, f"last_ei_pc debe ser {TEST_EXEC_BASE:04X}"
        
        # Ejecutar NOP (siguiente instrucción)
        cpu.step()  # NOP
        
        # Verificar que IME se activó después de la siguiente instrucción
        assert cpu.get_ime() == 1, "IME debe activarse después de la siguiente instrucción"
        assert cpu.get_ei_pending() == False, "ei_pending debe ser False después de la siguiente instrucción"
        assert cpu.get_ime_set_events_count() == 1, "ime_set_events_count debe ser 1 después de activar IME"
        # El PC se incrementa durante la ejecución de NOP, así que last_ime_set_pc es TEST_EXEC_BASE + 1
        assert cpu.get_last_ime_set_pc() == TEST_EXEC_BASE + 1, f"last_ime_set_pc debe ser {TEST_EXEC_BASE + 1:04X} (PC después de NOP)"
        assert cpu.get_last_ime_set_timestamp() == 1, "last_ime_set_timestamp debe ser 1"
    
    def test_ei_delayed_enable_with_inc(self):
        """
        Test: Verificar que funciona con cualquier instrucción siguiente (no solo NOP).
        
        - Estado inicial: IME=0
        - Ejecutar EI
        - Ejecutar INC A (siguiente instrucción)
        - Verificar: IME=1 después de INC A
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Cargar programa: EI, INC A
        load_program(mmu, regs, [0xFB, 0x3C])  # EI, INC A
        
        # Ejecutar EI
        cpu.step()  # EI
        assert cpu.get_ime() == 0, "IME NO debe activarse inmediatamente"
        assert cpu.get_ei_pending() == True, "ei_pending debe ser True"
        
        # Ejecutar INC A
        cpu.step()  # INC A
        
        # Verificar que IME se activó después de INC A
        assert cpu.get_ime() == 1, "IME debe activarse después de INC A"
        assert cpu.get_ei_pending() == False, "ei_pending debe ser False"
        assert cpu.get_ime_set_events_count() == 1, "ime_set_events_count debe ser 1"
    
    def test_multiple_ei_delayed_enable(self):
        """
        Test: Verificar que múltiples EI funcionan correctamente.
        
        - Ejecutar EI, NOP (IME se activa)
        - Ejecutar DI (IME se desactiva)
        - Ejecutar EI, NOP (IME se activa de nuevo)
        - Verificar: ime_set_events_count=2
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Cargar programa: EI, NOP, DI, EI, NOP
        load_program(mmu, regs, [0xFB, 0x00, 0xF3, 0xFB, 0x00])  # EI, NOP, DI, EI, NOP
        
        # Primer EI
        cpu.step()  # EI
        cpu.step()  # NOP
        assert cpu.get_ime() == 1, "IME debe estar activo después del primer EI+NOP"
        assert cpu.get_ime_set_events_count() == 1, "ime_set_events_count debe ser 1"
        
        # DI
        cpu.step()  # DI
        assert cpu.get_ime() == 0, "IME debe estar inactivo después de DI"
        assert cpu.get_last_di_pc() == TEST_EXEC_BASE + 2, f"last_di_pc debe ser {TEST_EXEC_BASE + 2:04X}"
        
        # Segundo EI
        cpu.step()  # EI
        cpu.step()  # NOP
        assert cpu.get_ime() == 1, "IME debe estar activo después del segundo EI+NOP"
        assert cpu.get_ime_set_events_count() == 2, "ime_set_events_count debe ser 2"
        assert cpu.get_last_ime_set_timestamp() == 2, "last_ime_set_timestamp debe ser 2"

