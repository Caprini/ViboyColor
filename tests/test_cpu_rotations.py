"""
Tests unitarios para rotaciones rápidas del acumulador.

Valida las instrucciones de rotación del acumulador:
- RLCA (0x07): Rotate Left Circular Accumulator
- RRCA (0x0F): Rotate Right Circular Accumulator
- RLA (0x17): Rotate Left Accumulator through Carry
- RRA (0x1F): Rotate Right Accumulator through Carry

Tests críticos:
- Verificar que Z siempre es 0 (quirk del hardware)
- Verificar que las rotaciones circulares funcionan correctamente
- Verificar que las rotaciones a través de carry incluyen el carry anterior
- Verificar que el flag C se actualiza correctamente
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_Z, FLAG_N, FLAG_H
from src.memory.mmu import MMU


class TestRLCA:
    """Tests para RLCA (Rotate Left Circular Accumulator)"""

    def test_rlca_basic(self):
        """
        Test 1: RLCA básico - rotar 0x80 a la izquierda.
        
        - A = 0x80 (10000000)
        - RLCA
        - A debe ser 0x01 (00000001)
        - C debe ser 1 (bit 7 original)
        - Z, N, H deben ser 0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x80)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x07)  # RLCA
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x01, (
            f"A debe ser 0x01 después de RLCA, es 0x{cpu.registers.get_a():02X}"
        )
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 7 original era 1)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (quirk: siempre 0 en rotaciones rápidas)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        assert not cpu.registers.get_flag_h(), "H debe ser 0"
        assert cycles == 1, f"RLCA debe consumir 1 M-Cycle, consumió {cycles}"

    def test_rlca_zero_result(self):
        """
        Test 2: RLCA con resultado cero - verificar que Z sigue siendo 0.
        
        CRÍTICO: Aunque el resultado sea 0, Z debe ser 0.
        Esta es una diferencia clave con las rotaciones CB.
        
        - A = 0x00
        - RLCA
        - A debe ser 0x00
        - Z debe ser 0 (quirk del hardware)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x00)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x07)  # RLCA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x00
        assert not cpu.registers.get_flag_z(), (
            "Z debe ser 0 incluso si el resultado es 0 (quirk del hardware)"
        )

    def test_rlca_carry(self):
        """
        Test 3: RLCA verifica que C se actualiza correctamente.
        
        - A = 0x40 (01000000), bit 7 = 0
        - RLCA
        - C debe ser 0
        - A debe ser 0x80
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x40)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x07)  # RLCA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x80
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 7 original era 0)"


class TestRRCA:
    """Tests para RRCA (Rotate Right Circular Accumulator)"""

    def test_rrca_basic(self):
        """
        Test 4: RRCA básico - rotar 0x01 a la derecha.
        
        - A = 0x01 (00000001)
        - RRCA
        - A debe ser 0x80 (10000000)
        - C debe ser 1 (bit 0 original)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x01)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x0F)  # RRCA
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x80, (
            f"A debe ser 0x80 después de RRCA, es 0x{cpu.registers.get_a():02X}"
        )
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 0 original era 1)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert cycles == 1


class TestRLA:
    """Tests para RLA (Rotate Left Accumulator through Carry)"""

    def test_rla_with_carry(self):
        """
        Test 5: RLA con carry activo.
        
        - A = 0x00, C = 1
        - RLA
        - A debe ser 0x01 (el carry entra por el bit 0)
        - C debe ser 0 (bit 7 original era 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x00)
        cpu.registers.set_flag(FLAG_C)  # Activar carry
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x17)  # RLA
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x01, (
            f"A debe ser 0x01 (carry entró por bit 0), es 0x{cpu.registers.get_a():02X}"
        )
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 7 original era 0)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert cycles == 1

    def test_rla_without_carry(self):
        """
        Test 6: RLA sin carry activo.
        
        - A = 0x80, C = 0
        - RLA
        - A debe ser 0x00 (bit 7 sale, nada entra)
        - C debe ser 1 (bit 7 original era 1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x80)
        cpu.registers.clear_flag(FLAG_C)  # Desactivar carry
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x17)  # RLA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x00
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 7 original era 1)"

    def test_rla_chain(self):
        """
        Test 7: Cadena de RLA para simular generador aleatorio.
        
        Este test simula cómo Tetris usa RLA para generar números aleatorios.
        - A = 0x01, C = 0
        - RLA múltiples veces
        - Verificar que la secuencia es correcta
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x01)
        cpu.registers.clear_flag(FLAG_C)
        
        # Primera RLA
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x17)  # RLA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x02, "Primera RLA: A debe ser 0x02"
        assert not cpu.registers.get_flag_c(), "C debe ser 0"
        
        # Segunda RLA
        cpu.registers.set_pc(0x0101)
        mmu.write_byte(0x0101, 0x17)  # RLA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x04, "Segunda RLA: A debe ser 0x04"


class TestRRA:
    """Tests para RRA (Rotate Right Accumulator through Carry)"""

    def test_rra_with_carry(self):
        """
        Test 8: RRA con carry activo.
        
        - A = 0x00, C = 1
        - RRA
        - A debe ser 0x80 (el carry entra por el bit 7)
        - C debe ser 0 (bit 0 original era 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x00)
        cpu.registers.set_flag(FLAG_C)  # Activar carry
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x1F)  # RRA
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x80, (
            f"A debe ser 0x80 (carry entró por bit 7), es 0x{cpu.registers.get_a():02X}"
        )
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 0 original era 0)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert cycles == 1

    def test_rra_without_carry(self):
        """
        Test 9: RRA sin carry activo.
        
        - A = 0x01, C = 0
        - RRA
        - A debe ser 0x00 (bit 0 sale, nada entra)
        - C debe ser 1 (bit 0 original era 1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x01)
        cpu.registers.clear_flag(FLAG_C)  # Desactivar carry
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x1F)  # RRA
        cpu.step()
        
        assert cpu.registers.get_a() == 0x00
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 0 original era 1)"

