"""
Tests unitarios para operaciones ALU inmediatas (d8).

Valida las operaciones aritméticas y lógicas con operandos inmediatos:
- ADC A, d8 (0xCE) - Add with Carry immediate
- SBC A, d8 (0xDE) - Subtract with Carry immediate
- AND d8 (0xE6) - Logical AND immediate
- XOR d8 (0xEE) - Logical XOR immediate
- OR d8 (0xF6) - Logical OR immediate

Tests críticos:
- Flags lógicos: AND pone H=1 (quirk del hardware)
- ADC/SBC: Deben usar el flag Carry actual
- OR/XOR: H=0, C=0
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_Z
from src.memory.mmu import MMU


class TestALUImmediate:
    """Tests para operaciones ALU inmediatas"""

    def test_and_immediate(self):
        """
        Test 1: Verificar AND d8 con máscara de bits.
        
        A = 0xFF, AND 0x0F -> A = 0x0F
        Flag H debe estar activo (quirk del hardware).
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0xFF
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0xFF)  # Operando: 0xFF
        cpu.step()
        
        # AND d8 (0xE6) seguido de 0x0F
        mmu.write_byte(0x0102, 0xE6)  # AND d8
        mmu.write_byte(0x0103, 0x0F)  # Operando: 0x0F
        cpu.step()
        
        # Verificar resultado: 0xFF AND 0x0F = 0x0F
        assert cpu.registers.get_a() == 0x0F, f"A debe ser 0x0F, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert cpu.registers.get_flag_h(), "H debe estar ACTIVO (quirk: AND siempre pone H=1)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_xor_immediate(self):
        """
        Test 2: Verificar XOR d8 que resulta en cero.
        
        A = 0xFF, XOR 0xFF -> A = 0x00, Z=1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0xFF
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0xFF)  # Operando: 0xFF
        cpu.step()
        
        # XOR d8 (0xEE) seguido de 0xFF
        mmu.write_byte(0x0102, 0xEE)  # XOR d8
        mmu.write_byte(0x0103, 0xFF)  # Operando: 0xFF
        cpu.step()
        
        # Verificar resultado: 0xFF XOR 0xFF = 0x00
        assert cpu.registers.get_a() == 0x00, f"A debe ser 0x00, es 0x{cpu.registers.get_a():02X}"
        assert cpu.registers.get_flag_z(), "Z debe estar activo (resultado == 0)"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (XOR pone H=0)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_adc_immediate(self):
        """
        Test 3: Verificar ADC A, d8 con carry activo.
        
        A = 0x00, Carry = 1, ADC 0x00 -> A = 0x01
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Activar Carry directamente
        cpu.registers.set_flag(FLAG_C)
        assert cpu.registers.get_flag_c(), "Carry debe estar activo"
        
        # Cargar A = 0x00
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0x00
        cpu.step()
        
        # ADC A, d8 (0xCE) seguido de 0x00
        mmu.write_byte(0x0102, 0xCE)  # ADC A, d8
        mmu.write_byte(0x0103, 0x00)  # Operando: 0x00
        cpu.step()
        
        # Verificar resultado: 0x00 + 0x00 + 1 = 0x01
        assert cpu.registers.get_a() == 1, f"A debe ser 1, es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (0+0+1 no causa carry)"
    
    def test_or_immediate(self):
        """
        Test 4: Verificar OR d8 básico.
        
        A = 0x00, OR 0x55 -> A = 0x55
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x00
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0x00
        cpu.step()
        
        # OR d8 (0xF6) seguido de 0x55
        mmu.write_byte(0x0102, 0xF6)  # OR d8
        mmu.write_byte(0x0103, 0x55)  # Operando: 0x55
        cpu.step()
        
        # Verificar resultado: 0x00 OR 0x55 = 0x55
        assert cpu.registers.get_a() == 0x55, f"A debe ser 0x55, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (OR pone H=0)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_sbc_immediate(self):
        """
        Test 5: Verificar SBC A, d8 con borrow activo.
        
        A = 0x00, Carry = 1, SBC 0x00 -> A = 0xFF (-1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Activar Carry directamente
        cpu.registers.set_flag(FLAG_C)
        assert cpu.registers.get_flag_c(), "Carry debe estar activo"
        
        # Cargar A = 0x00
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0x00
        cpu.step()
        
        # SBC A, d8 (0xDE) seguido de 0x00
        mmu.write_byte(0x0102, 0xDE)  # SBC A, d8
        mmu.write_byte(0x0103, 0x00)  # Operando: 0x00
        cpu.step()
        
        # Verificar resultado: 0x00 - 0x00 - 1 = 0xFF (-1)
        assert cpu.registers.get_a() == 0xFF, f"A debe ser 0xFF, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        assert cpu.registers.get_flag_h(), "H debe estar activo (half-borrow)"
        assert cpu.registers.get_flag_c(), "C debe estar activo (borrow completo)"

