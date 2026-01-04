"""
Step 0475: Test para verificar que el bit IF se limpia al servir una IRQ.

Este test valida la instrumentación añadida en Step 0475 para rastrear
el estado de IF antes y después de servir una interrupción.

Verifica:
- Cuando la CPU sirve una IRQ, el bit correspondiente en IF se limpia
- Los valores de IF antes/después se capturan correctamente
- La máscara del bit limpiado es correcta
- El vector de interrupción servida es correcto
"""

import pytest

try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)

from tests.helpers_cpu import load_program, TEST_EXEC_BASE

# Direcciones de registros de interrupciones
IO_IF = 0xFF0F  # Interrupt Flag
IO_IE = 0xFFFF  # Interrupt Enable


class TestIFClearedOnIRQService:
    """Tests para verificar que IF se limpia al servir una IRQ"""
    
    def test_vblank_irq_clears_if_bit(self):
        """
        Test: Verificar que al servir VBlank IRQ, el bit 0 de IF se limpia.
        
        - Configurar IME activo
        - Habilitar VBlank en IE (bit 0)
        - Activar VBlank en IF (bit 0)
        - Ejecutar step() para servir la interrupción
        - Verificar que get_last_if_before_service() muestra el bit 0 activo
        - Verificar que get_last_if_after_service() muestra el bit 0 limpio
        - Verificar que get_last_if_clear_mask() es 0x01 (bit 0)
        - Verificar que get_last_irq_serviced_vector() es 0x0040
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Cargar programa: EI, NOP (para activar IME)
        load_program(mmu, regs, [0xFB, 0x00])  # EI, NOP
        
        # Activar IME usando EI
        cpu.step()  # EI
        cpu.step()  # NOP (para que EI tome efecto)
        assert cpu.get_ime() == 1, "IME debe estar activo"
        
        # Limpiar contadores previos
        # (Los getters retornan 0 si no se ha servido ninguna IRQ)
        
        # Habilitar VBlank en IE y activar flag en IF
        mmu.write(IO_IE, 0x01)  # Habilitar V-Blank (bit 0)
        mmu.write(IO_IF, 0x01)  # Activar flag V-Blank (bit 0)
        
        # Verificar estado inicial de IF
        if_before = mmu.read(IO_IF)
        assert (if_before & 0x01) != 0, "IF bit 0 debe estar activo antes de servir IRQ"
        
        # Ejecutar step() (debe procesar la interrupción)
        initial_pc = regs.pc
        cycles = cpu.step()
        
        # Verificar que PC saltó al vector V-Blank
        assert regs.pc == 0x0040, f"PC debe saltar a 0x0040 (vector V-Blank), es 0x{regs.pc:04X}"
        assert cycles == 5, "La interrupción debe consumir 5 M-Cycles"
        
        # Verificar que IF se limpió
        if_after = mmu.read(IO_IF)
        assert (if_after & 0x01) == 0, "IF bit 0 debe estar limpio después de servir IRQ"
        
        # Verificar la instrumentación de Step 0475
        if_before_service = cpu.get_last_if_before_service()
        if_after_service = cpu.get_last_if_after_service()
        if_clear_mask = cpu.get_last_if_clear_mask()
        irq_vector = cpu.get_last_irq_serviced_vector()
        irq_timestamp = cpu.get_last_irq_serviced_timestamp()
        
        assert if_before_service == 0x01, \
            f"IF antes de servir debe ser 0x01 (bit 0 activo), es 0x{if_before_service:02X}"
        assert if_after_service == 0x00, \
            f"IF después de servir debe ser 0x00 (bit 0 limpio), es 0x{if_after_service:02X}"
        assert if_clear_mask == 0x01, \
            f"Máscara de bit limpiado debe ser 0x01 (bit 0), es 0x{if_clear_mask:02X}"
        assert irq_vector == 0x0040, \
            f"Vector de IRQ servida debe ser 0x0040 (V-Blank), es 0x{irq_vector:04X}"
        assert irq_timestamp > 0, \
            f"Timestamp de IRQ servida debe ser > 0, es {irq_timestamp}"
    
    def test_timer_irq_clears_if_bit(self):
        """
        Test: Verificar que al servir Timer IRQ, el bit 2 de IF se limpia.
        
        Similar al test anterior, pero para Timer (bit 2, vector 0x0050).
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Cargar programa: EI, NOP
        load_program(mmu, regs, [0xFB, 0x00])  # EI, NOP
        
        # Activar IME
        cpu.step()  # EI
        cpu.step()  # NOP
        assert cpu.get_ime() == 1
        
        # Habilitar Timer en IE y activar flag en IF
        mmu.write(IO_IE, 0x04)  # Habilitar Timer (bit 2)
        mmu.write(IO_IF, 0x04)  # Activar flag Timer (bit 2)
        
        # Ejecutar step() para servir la interrupción
        cpu.step()
        
        # Verificar vector
        assert regs.pc == 0x0050, f"PC debe saltar a 0x0050 (vector Timer), es 0x{regs.pc:04X}"
        
        # Verificar instrumentación
        if_before_service = cpu.get_last_if_before_service()
        if_after_service = cpu.get_last_if_after_service()
        if_clear_mask = cpu.get_last_if_clear_mask()
        irq_vector = cpu.get_last_irq_serviced_vector()
        
        assert if_before_service == 0x04, \
            f"IF antes de servir debe ser 0x04 (bit 2 activo), es 0x{if_before_service:02X}"
        assert if_after_service == 0x00, \
            f"IF después de servir debe ser 0x00 (bit 2 limpio), es 0x{if_after_service:02X}"
        assert if_clear_mask == 0x04, \
            f"Máscara de bit limpiado debe ser 0x04 (bit 2), es 0x{if_clear_mask:02X}"
        assert irq_vector == 0x0050, \
            f"Vector de IRQ servida debe ser 0x0050 (Timer), es 0x{irq_vector:04X}"
    
    def test_multiple_irqs_update_tracking(self):
        """
        Test: Verificar que el tracking se actualiza para cada IRQ servida.
        
        Sirve múltiples IRQs y verifica que los valores de tracking se actualizan
        correctamente para cada una.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Primera IRQ: VBlank
        load_program(mmu, regs, [0xFB, 0x00, 0x00])  # EI, NOP, NOP
        cpu.step()  # EI
        cpu.step()  # NOP
        assert cpu.get_ime() == 1
        
        mmu.write(IO_IE, 0x01)
        mmu.write(IO_IF, 0x01)
        cpu.step()  # Servir VBlank
        
        assert cpu.get_last_irq_serviced_vector() == 0x0040
        assert cpu.get_last_if_clear_mask() == 0x01
        timestamp1 = cpu.get_last_irq_serviced_timestamp()
        
        # Segunda IRQ: Timer (necesitamos reactivar IME y configurar Timer)
        # Como la IRQ desactiva IME, necesitamos reactivarlo
        regs.pc = TEST_EXEC_BASE
        load_program(mmu, regs, [0xFB, 0x00, 0x00])  # EI, NOP, NOP
        cpu.step()  # EI
        cpu.step()  # NOP
        assert cpu.get_ime() == 1
        
        mmu.write(IO_IE, 0x04)
        mmu.write(IO_IF, 0x04)
        cpu.step()  # Servir Timer
        
        assert cpu.get_last_irq_serviced_vector() == 0x0050
        assert cpu.get_last_if_clear_mask() == 0x04
        timestamp2 = cpu.get_last_irq_serviced_timestamp()
        
        # Verificar que el timestamp aumentó
        assert timestamp2 > timestamp1, \
            f"Timestamp debe aumentar: timestamp1={timestamp1}, timestamp2={timestamp2}"

