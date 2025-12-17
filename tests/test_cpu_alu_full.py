"""
Tests unitarios para el bloque ALU completo (0x80-0xBF).

Valida todas las operaciones aritméticas y lógicas del bloque principal de la ALU:
- ADD A, r (0x80-0x87)
- ADC A, r (0x88-0x8F) - Add with Carry
- SUB A, r (0x90-0x97)
- SBC A, r (0x98-0x9F) - Subtract with Carry
- AND A, r (0xA0-0xA7)
- XOR A, r (0xA8-0xAF)
- OR A, r (0xB0-0xB7)
- CP A, r (0xB8-0xBF)

Tests críticos:
- Flags lógicos: AND pone H=1 (quirk del hardware)
- ADC/SBC: Deben usar el flag Carry actual
- OR/XOR: H=0, C=0
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestALUFull:
    """Tests para el bloque ALU completo"""

    def test_and_h_flag(self):
        """
        Test 1: Verificar que AND siempre pone H=1 (quirk del hardware).
        
        Este es un comportamiento especial del hardware Game Boy que muchos
        emuladores fallan en implementar correctamente.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x55
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x55)  # Operando: 0x55
        cpu.step()
        
        # Cargar B = 0xAA
        mmu.write_byte(0x0102, 0x06)  # LD B, d8
        mmu.write_byte(0x0103, 0xAA)  # Operando: 0xAA
        cpu.step()
        
        # AND A, B (0xA0)
        mmu.write_byte(0x0104, 0xA0)  # AND A, B
        cpu.step()
        
        # Verificar resultado: 0x55 AND 0xAA = 0x00
        assert cpu.registers.get_a() == 0x00, "A debe ser 0x00"
        assert cpu.registers.get_flag_z(), "Z debe estar activo (resultado == 0)"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado"
        assert cpu.registers.get_flag_h(), "H debe estar ACTIVO (quirk: AND siempre pone H=1)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_or_logic(self):
        """
        Test 2: Verificar operación OR básica.
        
        OR: 0x00 OR 0x55 = 0x55
        Flags: Z=0, N=0, H=0, C=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x00
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0x00
        cpu.step()
        
        # Cargar E = 0x55 directamente (usando setter)
        cpu.registers.set_e(0x55)
        
        # OR A, E (0xB3) - Este es el opcode que Tetris pide
        mmu.write_byte(0x0102, 0xB3)  # OR A, E
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 0x55, f"A debe ser 0x55, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (OR pone H=0)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_adc_carry(self):
        """
        Test 3: Verificar ADC con carry activo.
        
        ADC debe sumar: A + value + Carry
        Si A=0, value=0, Carry=1 -> resultado debe ser 1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Activar Carry directamente usando el registro de flags
        cpu.registers.set_flag(FLAG_C)
        assert cpu.registers.get_flag_c(), "Carry debe estar activo"
        
        # Cargar A = 0
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0
        cpu.step()
        
        # Cargar B = 0
        mmu.write_byte(0x0102, 0x06)  # LD B, d8
        mmu.write_byte(0x0103, 0x00)  # Operando: 0
        cpu.step()
        
        # ADC A, B (0x88)
        mmu.write_byte(0x0104, 0x88)  # ADC A, B
        cpu.step()
        
        # Verificar resultado: 0 + 0 + 1 = 1
        assert cpu.registers.get_a() == 1, f"A debe ser 1, es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (0+0+1 no causa carry)"
    
    def test_sbc_borrow(self):
        """
        Test 4: Verificar SBC con borrow activo.
        
        SBC debe restar: A - value - Carry
        Si A=0, value=0, Carry=1 -> resultado debe ser 0xFF (-1)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Activar Carry directamente usando el registro de flags
        cpu.registers.set_flag(FLAG_C)
        assert cpu.registers.get_flag_c(), "Carry debe estar activo"
        
        # Cargar A = 0
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x00)  # Operando: 0
        cpu.step()
        
        # Cargar B = 0
        mmu.write_byte(0x0102, 0x06)  # LD B, d8
        mmu.write_byte(0x0103, 0x00)  # Operando: 0
        cpu.step()
        
        # SBC A, B (0x98)
        mmu.write_byte(0x0104, 0x98)  # SBC A, B
        cpu.step()
        
        # Verificar resultado: 0 - 0 - 1 = 0xFF (-1)
        assert cpu.registers.get_a() == 0xFF, f"A debe ser 0xFF, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        assert cpu.registers.get_flag_h(), "H debe estar activo (half-borrow)"
        assert cpu.registers.get_flag_c(), "C debe estar activo (borrow completo)"
    
    def test_alu_register_mapping(self):
        """
        Test 5: Verificar que el mapeo de registros es correcto.
        
        Verifica que 0xB3 (OR A, E) realmente llama a OR con el registro E.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x11
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x11)  # Operando: 0x11
        cpu.step()
        
        # Cargar E = 0x22
        # Necesitamos usar LD E, d8 - pero primero verificamos si existe
        # Si no existe, usamos transferencia LD E, A y luego modificamos
        # Por ahora, asumimos que podemos cargar E directamente
        # Alternativa: usar LD E, A y luego modificar A
        cpu.registers.set_e(0x22)
        
        # OR A, E (0xB3) - Este es el opcode que Tetris pide
        mmu.write_byte(0x0102, 0xB3)  # OR A, E
        cpu.step()
        
        # Verificar resultado: 0x11 OR 0x22 = 0x33
        assert cpu.registers.get_a() == 0x33, f"A debe ser 0x33, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado"
    
    def test_xor_logic(self):
        """
        Test 6: Verificar operación XOR básica.
        
        XOR: 0x55 XOR 0xAA = 0xFF
        Flags: Z=0, N=0, H=0, C=0
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x55
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x55)  # Operando: 0x55
        cpu.step()
        
        # Cargar C = 0xAA
        cpu.registers.set_c(0xAA)
        
        # XOR A, C (0xA9)
        mmu.write_byte(0x0102, 0xA9)  # XOR A, C
        cpu.step()
        
        # Verificar resultado: 0x55 XOR 0xAA = 0xFF
        assert cpu.registers.get_a() == 0xFF, f"A debe ser 0xFF, es 0x{cpu.registers.get_a():02X}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (XOR pone H=0)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado"
    
    def test_and_memory_indirect(self):
        """
        Test 7: Verificar AND con memoria indirecta (HL).
        
        AND A, (HL) debe leer de memoria y hacer AND.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0xF0
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0xF0)  # Operando: 0xF0
        cpu.step()
        
        # Configurar HL = 0xC000
        mmu.write_byte(0x0102, 0x21)  # LD HL, d16
        mmu.write_byte(0x0103, 0x00)  # Low byte
        mmu.write_byte(0x0104, 0xC0)  # High byte
        cpu.step()
        
        # Escribir 0x0F en memoria[0xC000]
        mmu.write_byte(0xC000, 0x0F)
        
        # AND A, (HL) (0xA6)
        mmu.write_byte(0x0105, 0xA6)  # AND A, (HL)
        cpu.step()
        
        # Verificar resultado: 0xF0 AND 0x0F = 0x00
        assert cpu.registers.get_a() == 0x00, f"A debe ser 0x00, es 0x{cpu.registers.get_a():02X}"
        assert cpu.registers.get_flag_z(), "Z debe estar activo (resultado == 0)"
        assert cpu.registers.get_flag_h(), "H debe estar ACTIVO (quirk: AND siempre pone H=1)"
    
    def test_cp_register(self):
        """
        Test 8: Verificar CP (Compare) con registro.
        
        CP A, B debe comparar A con B sin modificar A.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 0x10
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x10)  # Operando: 0x10
        cpu.step()
        
        # Cargar B = 0x10
        cpu.registers.set_b(0x10)
        
        # CP A, B (0xB8)
        mmu.write_byte(0x0102, 0xB8)  # CP A, B
        cpu.step()
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x10, "A no debe cambiar en CP"
        # Verificar flags: A == B, entonces Z=1, C=0
        assert cpu.registers.get_flag_z(), "Z debe estar activo (A == B)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es comparación/resta)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (A >= B)"

