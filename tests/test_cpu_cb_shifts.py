"""
Tests unitarios para operaciones CB de rotaciones, shifts y SWAP (rango 0x00-0x3F).

Valida:
- SWAP: Intercambio de nibbles con flags correctos
- SRA: Shift right arithmetic (preserva signo)
- SRL: Shift right logical (sin signo)
- Diferencia crítica de flags Z entre rotaciones rápidas (RLCA) y CB (RLC)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestSWAP:
    """Tests para la instrucción SWAP (intercambio de nibbles)"""

    def test_swap_basic(self):
        """
        Test: SWAP intercambia correctamente los nibbles.
        
        - B = 0xF0 (11110000)
        - Ejecuta CB 0x30 (SWAP B)
        - Verifica que B = 0x0F (00001111)
        - Verifica Z=0 (resultado no es cero)
        - Verifica N=0, H=0, C=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_b(0xF0)
        cpu.registers.set_pc(0x8000)
        
        # Escribir prefijo CB y opcode en memoria
        mmu.write_byte(0x8000, 0xCB)  # Prefijo CB
        mmu.write_byte(0x8001, 0x38)  # SWAP B
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_b() == 0x0F, "B debe ser 0x0F después de SWAP"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (resultado no es cero)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        assert not cpu.registers.get_flag_h(), "H debe ser 0"
        assert not cpu.registers.get_flag_c(), "C debe ser 0"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_swap_zero_result(self):
        """
        Test: SWAP con resultado cero activa flag Z.
        
        - B = 0x00 (00000000)
        - Ejecuta CB 0x30 (SWAP B)
        - Verifica que B = 0x00
        - Verifica Z=1 (resultado es cero)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x00)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x30)  # SWAP B
        
        cpu.step()
        
        assert cpu.registers.get_b() == 0x00
        assert cpu.registers.get_flag_z(), "Z debe ser 1 (resultado es cero)"
    
    def test_swap_a5(self):
        """
        Test: SWAP con valor 0xA5 produce 0x5A.
        
        - A = 0xA5 (10100101)
        - Ejecuta CB 0x37 (SWAP A)
        - Verifica que A = 0x5A (01011010)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0xA5)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x3F)  # SWAP A
        
        cpu.step()
        
        assert cpu.registers.get_a() == 0x5A, "A debe ser 0x5A después de SWAP"


class TestSRA:
    """Tests para la instrucción SRA (Shift Right Arithmetic - preserva signo)"""

    def test_sra_negative(self):
        """
        Test: SRA preserva el signo en valores negativos.
        
        - B = 0x80 (-128 en complemento a 2)
        - Ejecuta CB 0x28 (SRA B)
        - Verifica que B = 0xC0 (-64, bit 7 se mantiene)
        - Verifica C=0 (bit 0 original era 0)
        - Verifica Z=0 (resultado no es cero)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x80)  # -128
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x28)  # SRA B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0xC0, "B debe ser 0xC0 (-64) después de SRA"
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 0 original era 0)"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (resultado no es cero)"
        assert cycles == 2
    
    def test_sra_positive(self):
        """
        Test: SRA con valor positivo.
        
        - B = 0x40 (64)
        - Ejecuta CB 0x28 (SRA B)
        - Verifica que B = 0x20 (32)
        - Verifica C=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x40)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x28)  # SRA B
        
        cpu.step()
        
        assert cpu.registers.get_b() == 0x20, "B debe ser 0x20 después de SRA"
        assert not cpu.registers.get_flag_c()
    
    def test_sra_with_carry(self):
        """
        Test: SRA activa C cuando bit 0 es 1.
        
        - B = 0x81 (bit 0 = 1)
        - Ejecuta CB 0x28 (SRA B)
        - Verifica que C=1 (bit 0 original era 1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x81)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x28)  # SRA B
        
        cpu.step()
        
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 0 original era 1)"


class TestSRL:
    """Tests para la instrucción SRL (Shift Right Logical - sin signo)"""

    def test_srl_basic(self):
        """
        Test: SRL desplaza sin signo (bit 7 entra 0).
        
        - B = 0x01 (1)
        - Ejecuta CB 0x38 (SRL B)
        - Verifica que B = 0x00 (0)
        - Verifica C=1 (bit 0 original era 1)
        - Verifica Z=1 (resultado es cero)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x01)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x30)  # SRL B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x00, "B debe ser 0x00 después de SRL"
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 0 original era 1)"
        assert cpu.registers.get_flag_z(), "Z debe ser 1 (resultado es cero)"
        assert cycles == 2
    
    def test_srl_negative_treated_as_positive(self):
        """
        Test: SRL trata valores negativos como positivos (bit 7 entra 0).
        
        - B = 0x80 (128, no -128)
        - Ejecuta CB 0x38 (SRL B)
        - Verifica que B = 0x40 (64, bit 7 entró como 0)
        - Verifica C=0 (bit 0 original era 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x80)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x30)  # SRL B
        
        cpu.step()
        
        assert cpu.registers.get_b() == 0x40, "B debe ser 0x40 (bit 7 entró como 0)"
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 0 original era 0)"


class TestRLCZFlag:
    """Tests para verificar la diferencia crítica de flags Z entre rotaciones rápidas y CB"""

    def test_rlc_z_flag(self):
        """
        Test: CB RLC calcula Z según el resultado (DIFERENCIA con RLCA).
        
        - B = 0x00
        - Ejecuta CB 0x00 (RLC B)
        - Verifica que B = 0x00 (rotar 0 sigue siendo 0)
        - Verifica Z=1 (resultado es cero) <- DIFERENCIA: RLCA siempre pone Z=0
        - Verifica C=0 (bit 7 original era 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x00)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x00)  # RLC B
        
        cycles = cpu.step()
        
        assert cpu.registers.get_b() == 0x00, "B debe seguir siendo 0x00"
        assert cpu.registers.get_flag_z(), "Z debe ser 1 (resultado es cero) - DIFERENCIA con RLCA"
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 7 original era 0)"
        assert cycles == 2
    
    def test_rlc_nonzero_result(self):
        """
        Test: CB RLC con resultado no cero pone Z=0.
        
        - B = 0x80
        - Ejecuta CB 0x00 (RLC B)
        - Verifica que B = 0x01
        - Verifica Z=0 (resultado no es cero)
        - Verifica C=1 (bit 7 original era 1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_b(0x80)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x00)  # RLC B
        
        cpu.step()
        
        assert cpu.registers.get_b() == 0x01, "B debe ser 0x01 después de RLC"
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (resultado no es cero)"
        assert cpu.registers.get_flag_c(), "C debe ser 1 (bit 7 original era 1)"


class TestCBMemoryIndirect:
    """Tests para operaciones CB con direccionamiento indirecto (HL)"""

    def test_swap_hl_indirect(self):
        """
        Test: SWAP (HL) funciona con direccionamiento indirecto.
        
        - HL = 0xC000
        - Memoria[0xC000] = 0xF0
        - Ejecuta CB 0x36 (SWAP (HL))
        - Verifica que Memoria[0xC000] = 0x0F
        - Verifica que consume 4 M-Cycles (acceso a memoria)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_hl(0xC000)
        mmu.write_byte(0xC000, 0xF0)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x3E)  # SWAP (HL)
        
        cycles = cpu.step()
        
        assert mmu.read_byte(0xC000) == 0x0F, "Memoria[0xC000] debe ser 0x0F"
        assert cycles == 4, "Debe consumir 4 M-Cycles (acceso a memoria)"
    
    def test_srl_hl_indirect(self):
        """
        Test: SRL (HL) funciona con direccionamiento indirecto.
        
        - HL = 0xC000
        - Memoria[0xC000] = 0x02
        - Ejecuta CB 0x3E (SRL (HL))
        - Verifica que Memoria[0xC000] = 0x01
        - Verifica C=0 (bit 0 original era 0)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_hl(0xC000)
        mmu.write_byte(0xC000, 0x02)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x36)  # SRL (HL)
        
        cpu.step()
        
        assert mmu.read_byte(0xC000) == 0x01, "Memoria[0xC000] debe ser 0x01"
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (bit 0 original era 0)"

