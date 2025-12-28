"""
Tests unitarios para aritmética de pila con offset (SP+r8).

Valida las siguientes instrucciones:
- ADD SP, r8 (0xE8): Suma un offset con signo de 8 bits al Stack Pointer
- LD HL, SP+r8 (0xF8): Calcula SP + offset y lo almacena en HL (SP no cambia)

Ambas instrucciones tienen flags especiales:
- Z: Siempre 0 (no se toca)
- N: Siempre 0 (es una suma)
- H: Se activa si hay carry del bit 3 al 4 (nibble bajo)
- C: Se activa si hay carry del bit 7 al 8 (byte bajo)

Fuente: Pan Docs - CPU Instruction Set (ADD SP, r8 / LD HL, SP+r8)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_Z, FLAG_N
from src.memory.mmu import MMU


class TestAddSpR8:
    """Tests para ADD SP, r8 (0xE8)"""
    
    def test_add_sp_positive(self):
        """
        Test: Verificar que ADD SP, r8 suma un offset positivo correctamente.
        
        - Establece SP = 0x1000
        - Escribe opcode 0xE8 seguido de offset 0x05 (+5)
        - Ejecuta step()
        - Verifica que SP = 0x1005
        - Verifica flags: Z=0, N=0, H y C según cálculo
        - Verifica que consume 4 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x1000)
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xE8)  # ADD SP, r8
        mmu.write_byte(0x0101, 0x05)  # +5
        
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0x1005, "SP debe ser 0x1005"
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        # H: (0x00 & 0xF) + (0x05 & 0xF) = 0 + 5 = 5, no hay carry -> H=0
        assert not cpu.registers.get_flag_h(), "H debe ser 0 (no hay half-carry)"
        # C: (0x00 + 0x05) & 0x100 = 0, no hay carry -> C=0
        assert not cpu.registers.get_flag_c(), "C debe ser 0 (no hay carry)"
        
        # Verificar ciclos
        assert cycles == 4, "ADD SP, r8 debe consumir 4 M-Cycles"
    
    def test_add_sp_negative(self):
        """
        Test: Verificar que ADD SP, r8 suma un offset negativo correctamente.
        
        - Establece SP = 0x1000
        - Escribe opcode 0xE8 seguido de offset 0xFE (-2 en signed)
        - Ejecuta step()
        - Verifica que SP = 0x0FFE
        - Verifica flags
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x1000)
        
        # Escribir opcode y offset negativo
        mmu.write_byte(0x0100, 0xE8)  # ADD SP, r8
        mmu.write_byte(0x0101, 0xFE)  # -2 (0xFE = 254 unsigned, -2 signed)
        
        cycles = cpu.step()
        
        # Verificar resultado: 0x1000 + (-2) = 0x0FFE
        assert cpu.registers.get_sp() == 0x0FFE, "SP debe ser 0x0FFE"
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        
        # Verificar ciclos
        assert cycles == 4, "ADD SP, r8 debe consumir 4 M-Cycles"
    
    def test_add_sp_with_half_carry(self):
        """
        Test: Verificar que ADD SP, r8 activa el flag H cuando hay half-carry.
        
        - Establece SP = 0x100F (byte bajo = 0x0F)
        - Escribe opcode 0xE8 seguido de offset 0x01 (+1)
        - Ejecuta step()
        - Verifica que SP = 0x1010
        - Verifica que H=1 (carry del bit 3 al 4: 0xF + 1 = 0x10)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x100F)  # Byte bajo = 0x0F
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xE8)  # ADD SP, r8
        mmu.write_byte(0x0101, 0x01)  # +1
        
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0x1010, "SP debe ser 0x1010"
        
        # Verificar H flag: (0x0F & 0xF) + (0x01 & 0xF) = 0xF + 1 = 0x10 > 0xF -> H=1
        assert cpu.registers.get_flag_h(), "H debe ser 1 (half-carry del bit 3 al 4)"
    
    def test_add_sp_with_carry(self):
        """
        Test: Verificar que ADD SP, r8 activa el flag C cuando hay carry.
        
        - Establece SP = 0x10FF (byte bajo = 0xFF)
        - Escribe opcode 0xE8 seguido de offset 0x01 (+1)
        - Ejecuta step()
        - Verifica que SP = 0x1100
        - Verifica que C=1 (carry del bit 7 al 8: 0xFF + 1 = 0x100)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x10FF)  # Byte bajo = 0xFF
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xE8)  # ADD SP, r8
        mmu.write_byte(0x0101, 0x01)  # +1
        
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_sp() == 0x1100, "SP debe ser 0x1100"
        
        # Verificar C flag: (0xFF + 0x01) & 0x100 = 0x100 != 0 -> C=1
        assert cpu.registers.get_flag_c(), "C debe ser 1 (carry del bit 7 al 8)"
    
    def test_add_sp_wraparound(self):
        """
        Test: Verificar que ADD SP, r8 maneja wrap-around correctamente.
        
        - Establece SP = 0xFFFE
        - Escribe opcode 0xE8 seguido de offset 0x03 (+3)
        - Ejecuta step()
        - Verifica que SP = 0x0001 (wrap-around: 0xFFFE + 3 = 0x10001 -> 0x0001)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xE8)  # ADD SP, r8
        mmu.write_byte(0x0101, 0x03)  # +3
        
        cpu.step()
        
        # Verificar wrap-around: 0xFFFE + 3 = 0x10001 -> 0x0001 (16 bits)
        assert cpu.registers.get_sp() == 0x0001, "SP debe hacer wrap-around a 0x0001"


class TestLdHlSpR8:
    """Tests para LD HL, SP+r8 (0xF8)"""
    
    def test_ld_hl_sp_r8_positive(self):
        """
        Test: Verificar que LD HL, SP+r8 calcula SP + offset y lo guarda en HL.
        
        - Establece SP = 0x2000
        - Escribe opcode 0xF8 seguido de offset 0x10 (+16)
        - Ejecuta step()
        - Verifica que HL = 0x2010
        - Verifica que SP NO cambia (sigue siendo 0x2000)
        - Verifica flags: Z=0, N=0, H y C según cálculo
        - Verifica que consume 3 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x2000)
        original_sp = cpu.registers.get_sp()
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xF8)  # LD HL, SP+r8
        mmu.write_byte(0x0101, 0x10)  # +16
        
        cycles = cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_hl() == 0x2010, "HL debe ser 0x2010"
        
        # Verificar que SP NO cambió (CRÍTICO)
        assert cpu.registers.get_sp() == original_sp, "SP no debe cambiar"
        assert cpu.registers.get_sp() == 0x2000, "SP debe seguir siendo 0x2000"
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe ser 0"
        assert not cpu.registers.get_flag_n(), "N debe ser 0"
        
        # Verificar ciclos
        assert cycles == 3, "LD HL, SP+r8 debe consumir 3 M-Cycles"
    
    def test_ld_hl_sp_r8_negative(self):
        """
        Test: Verificar que LD HL, SP+r8 funciona con offset negativo.
        
        - Establece SP = 0x2000
        - Escribe opcode 0xF8 seguido de offset 0xFC (-4 en signed)
        - Ejecuta step()
        - Verifica que HL = 0x1FFC
        - Verifica que SP NO cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x2000)
        original_sp = cpu.registers.get_sp()
        
        # Escribir opcode y offset negativo
        mmu.write_byte(0x0100, 0xF8)  # LD HL, SP+r8
        mmu.write_byte(0x0101, 0xFC)  # -4 (0xFC = 252 unsigned, -4 signed)
        
        cpu.step()
        
        # Verificar resultado: 0x2000 + (-4) = 0x1FFC
        assert cpu.registers.get_hl() == 0x1FFC, "HL debe ser 0x1FFC"
        
        # Verificar que SP NO cambió
        assert cpu.registers.get_sp() == original_sp, "SP no debe cambiar"
    
    def test_ld_hl_sp_r8_with_flags(self):
        """
        Test: Verificar que LD HL, SP+r8 calcula flags H y C correctamente.
        
        - Establece SP = 0x10FF (byte bajo = 0xFF)
        - Escribe opcode 0xF8 seguido de offset 0x01 (+1)
        - Ejecuta step()
        - Verifica que HL = 0x1100
        - Verifica que H=1 y C=1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0x10FF)  # Byte bajo = 0xFF
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xF8)  # LD HL, SP+r8
        mmu.write_byte(0x0101, 0x01)  # +1
        
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_hl() == 0x1100, "HL debe ser 0x1100"
        
        # Verificar flags
        # H: (0xFF & 0xF) + (0x01 & 0xF) = 0xF + 1 = 0x10 > 0xF -> H=1
        assert cpu.registers.get_flag_h(), "H debe ser 1 (half-carry)"
        # C: (0xFF + 0x01) & 0x100 = 0x100 != 0 -> C=1
        assert cpu.registers.get_flag_c(), "C debe ser 1 (carry)"
    
    def test_ld_hl_sp_r8_sp_unchanged(self):
        """
        Test: Verificar que LD HL, SP+r8 NO modifica SP incluso con wrap-around.
        
        - Establece SP = 0xFFFE
        - Escribe opcode 0xF8 seguido de offset 0x05 (+5)
        - Ejecuta step()
        - Verifica que HL = 0x0003 (wrap-around)
        - Verifica que SP sigue siendo 0xFFFE
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_sp(0xFFFE)
        original_sp = cpu.registers.get_sp()
        
        # Escribir opcode y offset
        mmu.write_byte(0x0100, 0xF8)  # LD HL, SP+r8
        mmu.write_byte(0x0101, 0x05)  # +5
        
        cpu.step()
        
        # Verificar HL con wrap-around: 0xFFFE + 5 = 0x10003 -> 0x0003
        assert cpu.registers.get_hl() == 0x0003, "HL debe hacer wrap-around a 0x0003"
        
        # Verificar que SP NO cambió
        assert cpu.registers.get_sp() == original_sp, "SP no debe cambiar"
        assert cpu.registers.get_sp() == 0xFFFE, "SP debe seguir siendo 0xFFFE"

