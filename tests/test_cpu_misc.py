"""
Tests unitarios para instrucciones misceláneas de la CPU.

Valida las últimas instrucciones del set de la CPU:
- DAA (0x27): Decimal Adjust Accumulator - Ajuste decimal para BCD
- CPL (0x2F): Complement Accumulator - Inversión de bits
- SCF (0x37): Set Carry Flag - Activar flag Carry
- CCF (0x3F): Complement Carry Flag - Invertir flag Carry
- RST n (0xC7-0xFF): Restart - Saltos a vectores de interrupción

Tests críticos:
- DAA: Verificar conversión binario -> BCD en sumas y restas
- CPL: Verificar inversión de bits y flags N/H
- SCF/CCF: Verificar manipulación del flag Carry
- RST: Verificar que guarda PC en pila y salta al vector correcto
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestDAA:
    """Tests para DAA (Decimal Adjust Accumulator)"""

    def test_daa_addition_simple(self):
        """
        Test 1: DAA después de suma simple (9 + 1 = 10 en BCD).
        
        - Establecer A = 0x09
        - Ejecutar ADD A, 0x01 (resultado: 0x0A)
        - Ejecutar DAA
        - Verificar que A = 0x10 (BCD correcto)
        - Verificar flags: Z=0, N=0, H=0, C=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar: A = 0x09
        cpu.registers.set_a(0x09)
        cpu.registers.clear_flag(FLAG_N)  # Última operación fue suma
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.clear_flag(FLAG_H)
        
        # Simular ADD A, 0x01 (resultado: 0x0A)
        # En una suma real, H se activaría porque 9 + 1 = 10 (0x0A > 9)
        cpu.registers.set_a(0x0A)
        cpu.registers.set_flag(FLAG_H)  # Half-carry activado
        
        # Ejecutar DAA
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x27)  # Opcode DAA
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.get_a() == 0x10  # BCD: 10 decimal
        assert not cpu.registers.check_flag(FLAG_Z)  # No es cero
        assert not cpu.registers.check_flag(FLAG_N)  # No es resta
        assert not cpu.registers.check_flag(FLAG_H)  # H se limpia
        assert not cpu.registers.check_flag(FLAG_C)  # No hay carry
    
    def test_daa_addition_with_carry(self):
        """
        Test 2: DAA después de suma con carry (99 + 1 = 100 en BCD).
        
        - Establecer A = 0x99
        - Simular ADD A, 0x01 (resultado: 0x9A, pero con carry)
        - Ejecutar DAA
        - Verificar que A = 0x00 y C = 1 (overflow a 100, pero solo 8 bits)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar: A = 0x99
        cpu.registers.set_a(0x99)
        cpu.registers.clear_flag(FLAG_N)
        cpu.registers.set_flag(FLAG_C)  # Carry activado (99 + 1 > 255)
        cpu.registers.set_flag(FLAG_H)  # Half-carry también
        
        # Simular resultado: 0x9A (pero con carry)
        cpu.registers.set_a(0x9A)
        
        # Ejecutar DAA
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x27)  # Opcode DAA
        cycles = cpu.step()
        
        assert cycles == 1
        # DAA ajusta: 0x9A + 0x66 = 0x00 (con carry)
        assert cpu.registers.get_a() == 0x00
        assert cpu.registers.check_flag(FLAG_C)  # Carry activado
        assert cpu.registers.check_flag(FLAG_Z)  # Resultado es cero
    
    def test_daa_subtraction(self):
        """
        Test 3: DAA después de resta (10 - 1 = 9 en BCD).
        
        - Establecer A = 0x10
        - Simular SUB A, 0x01 (resultado: 0x0F)
        - Ejecutar DAA
        - Verificar que A = 0x09 (BCD correcto)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar: A = 0x10
        cpu.registers.set_a(0x10)
        cpu.registers.set_flag(FLAG_N)  # Última operación fue resta
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_flag(FLAG_H)  # Half-carry en resta
        
        # Simular SUB A, 0x01 (resultado: 0x0F)
        cpu.registers.set_a(0x0F)
        
        # Ejecutar DAA
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x27)  # Opcode DAA
        cycles = cpu.step()
        
        assert cycles == 1
        # DAA ajusta: 0x0F - 0x06 = 0x09
        assert cpu.registers.get_a() == 0x09
        assert not cpu.registers.check_flag(FLAG_Z)
        assert cpu.registers.check_flag(FLAG_N)  # N se mantiene
        assert not cpu.registers.check_flag(FLAG_H)  # H se limpia


class TestCPL:
    """Tests para CPL (Complement Accumulator)"""

    def test_cpl_basic(self):
        """
        Test 1: CPL básico - Inversión de bits.
        
        - Establecer A = 0x55 (01010101)
        - Ejecutar CPL
        - Verificar que A = 0xAA (10101010)
        - Verificar flags: N=1, H=1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar: A = 0x55
        cpu.registers.set_a(0x55)
        cpu.registers.clear_flag(FLAG_N)
        cpu.registers.clear_flag(FLAG_H)
        
        # Ejecutar CPL
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x2F)  # Opcode CPL
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.get_a() == 0xAA  # ~0x55 = 0xAA
        assert cpu.registers.check_flag(FLAG_N)  # N se activa
        assert cpu.registers.check_flag(FLAG_H)  # H se activa
    
    def test_cpl_all_ones(self):
        """
        Test 2: CPL de 0xFF -> 0x00.
        
        - Establecer A = 0xFF
        - Ejecutar CPL
        - Verificar que A = 0x00
        - Verificar que Z no se modifica (CPL no afecta Z)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0xFF)
        cpu.registers.clear_flag(FLAG_Z)  # Z inicialmente desactivado
        
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x2F)  # Opcode CPL
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.get_a() == 0x00  # ~0xFF = 0x00
        # CPL no modifica Z, solo N y H
        assert not cpu.registers.check_flag(FLAG_Z)  # Z no se modifica
        assert cpu.registers.check_flag(FLAG_N)  # N se activa
        assert cpu.registers.check_flag(FLAG_H)  # H se activa


class TestSCF:
    """Tests para SCF (Set Carry Flag)"""

    def test_scf_basic(self):
        """
        Test 1: SCF activa Carry y limpia N/H.
        
        - Ejecutar SCF
        - Verificar que C=1, N=0, H=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Limpiar todos los flags
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.clear_flag(FLAG_N)
        cpu.registers.clear_flag(FLAG_H)
        
        # Ejecutar SCF
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x37)  # Opcode SCF
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.check_flag(FLAG_C)  # C activado
        assert not cpu.registers.check_flag(FLAG_N)  # N limpio
        assert not cpu.registers.check_flag(FLAG_H)  # H limpio
    
    def test_scf_with_carry_already_set(self):
        """
        Test 2: SCF mantiene C=1 si ya estaba activo.
        
        - Activar C
        - Ejecutar SCF
        - Verificar que C sigue activo
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_flag(FLAG_C)
        
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x37)  # Opcode SCF
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.check_flag(FLAG_C)  # C sigue activo


class TestCCF:
    """Tests para CCF (Complement Carry Flag)"""

    def test_ccf_clear_to_set(self):
        """
        Test 1: CCF invierte C de 0 a 1.
        
        - Limpiar C
        - Ejecutar CCF
        - Verificar que C=1, N=0, H=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.clear_flag(FLAG_C)
        
        # Ejecutar CCF
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x3F)  # Opcode CCF
        cycles = cpu.step()
        
        assert cycles == 1
        assert cpu.registers.check_flag(FLAG_C)  # C invertido a 1
        assert not cpu.registers.check_flag(FLAG_N)  # N limpio
        assert not cpu.registers.check_flag(FLAG_H)  # H limpio
    
    def test_ccf_set_to_clear(self):
        """
        Test 2: CCF invierte C de 1 a 0.
        
        - Activar C
        - Ejecutar CCF
        - Verificar que C=0, N=0, H=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_flag(FLAG_C)
        
        # Ejecutar CCF
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0x3F)  # Opcode CCF
        cycles = cpu.step()
        
        assert cycles == 1
        assert not cpu.registers.check_flag(FLAG_C)  # C invertido a 0
        assert not cpu.registers.check_flag(FLAG_N)  # N limpio
        assert not cpu.registers.check_flag(FLAG_H)  # H limpio


class TestRST:
    """Tests para RST (Restart)"""

    def test_rst_38(self):
        """
        Test 1: RST 0x38 guarda PC en pila y salta al vector.
        
        - Establecer PC = 0x1234
        - Establecer SP = 0xFFFE
        - Ejecutar RST 0x38 (opcode 0xFF)
        - Verificar que PC = 0x0038
        - Verificar que memoria en 0xFFFD y 0xFFFC contiene 0x1235 (PC+1)
        - Verificar que SP = 0xFFFC
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar PC y SP
        cpu.registers.set_pc(0x1234)
        cpu.registers.set_sp(0xFFFE)
        
        # Ejecutar RST 0x38
        mmu.write_byte(0x1234, 0xFF)  # Opcode RST 38h
        cycles = cpu.step()
        
        assert cycles == 4  # RST consume 4 M-Cycles
        assert cpu.registers.get_pc() == 0x0038  # Saltó al vector
        
        # Verificar que PC anterior está en la pila
        # PC que se guarda es 0x1235 (PC+1 después de leer opcode)
        high_byte = mmu.read_byte(0xFFFD)
        low_byte = mmu.read_byte(0xFFFC)
        saved_pc = (high_byte << 8) | low_byte
        assert saved_pc == 0x1235
        
        # Verificar que SP decrementó
        assert cpu.registers.get_sp() == 0xFFFC
    
    def test_rst_00(self):
        """
        Test 2: RST 0x00 salta a 0x0000.
        
        - Ejecutar RST 0x00 (opcode 0xC7)
        - Verificar que PC = 0x0000
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        mmu.write_byte(0x0100, 0xC7)  # Opcode RST 00h
        cycles = cpu.step()
        
        assert cycles == 4
        assert cpu.registers.get_pc() == 0x0000
    
    def test_rst_all_vectors(self):
        """
        Test 3: Verificar todos los vectores RST.
        
        Vectores: 0x00, 0x08, 0x10, 0x18, 0x20, 0x28, 0x30, 0x38
        Opcodes: 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        vectors = [
            (0xC7, 0x0000),  # RST 00h
            (0xCF, 0x0008),  # RST 08h
            (0xD7, 0x0010),  # RST 10h
            (0xDF, 0x0018),  # RST 18h
            (0xE7, 0x0020),  # RST 20h
            (0xEF, 0x0028),  # RST 28h
            (0xF7, 0x0030),  # RST 30h
            (0xFF, 0x0038),  # RST 38h
        ]
        
        for opcode, expected_vector in vectors:
            cpu.registers.set_pc(0x0100)
            cpu.registers.set_sp(0xFFFE)
            
            mmu.write_byte(0x0100, opcode)
            cycles = cpu.step()
            
            assert cycles == 4
            assert cpu.registers.get_pc() == expected_vector, (
                f"RST 0x{opcode:02X} debería saltar a 0x{expected_vector:04X}, "
                f"pero saltó a 0x{cpu.registers.get_pc():04X}"
            )

