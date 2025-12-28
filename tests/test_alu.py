"""
Tests unitarios para la ALU (Unidad Aritmética Lógica) de la CPU.

Valida las operaciones aritméticas básicas (suma y resta) y la gestión
correcta de flags, especialmente el Half-Carry (H) que es crítico para
la instrucción DAA y el manejo de números decimales en juegos.

Tests implementados:
- test_add_basic: Suma básica sin carry
- test_add_half_carry: Suma que activa Half-Carry (bit 3 a 4)
- test_add_full_carry: Suma que activa Carry completo (overflow 8 bits)
- test_sub_basic: Resta básica sin borrow
- test_sub_half_carry: Resta que activa Half-Borrow (bit 4 a 3)
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestALU:
    """Tests para la Unidad Aritmética Lógica (ALU)"""

    def test_add_basic(self):
        """
        Test 1: Verificar suma básica sin carry.
        
        Suma: 10 + 5 = 15
        - Resultado: A = 15 (0x0F)
        - Z: 0 (no es cero)
        - N: 0 (es suma)
        - H: 0 (no hay half-carry)
        - C: 0 (no hay carry)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 10 (0x0A)
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x0A)  # Operando: 10
        cpu.step()
        
        # Sumar 5 (0x05) a A
        mmu.write_byte(0x0102, 0xC6)  # ADD A, d8
        mmu.write_byte(0x0103, 0x05)  # Operando: 5
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 15, f"A debe ser 15, es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado (es suma)"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (no hay half-carry)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (no hay carry)"

    def test_add_half_carry(self):
        """
        Test 2: Verificar que Half-Carry se activa correctamente.
        
        Suma: 15 (0x0F) + 1 (0x01) = 16 (0x10)
        - Resultado: A = 16 (0x10)
        - Z: 0 (no es cero)
        - N: 0 (es suma)
        - H: 1 (HAY half-carry: 0xF + 0x1 = 0x10, carry del bit 3 al 4)
        - C: 0 (no hay carry completo)
        
        Este test es CRÍTICO porque el Half-Carry es necesario para DAA.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 15 (0x0F)
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x0F)  # Operando: 15
        cpu.step()
        
        # Sumar 1 (0x01) a A
        mmu.write_byte(0x0102, 0xC6)  # ADD A, d8
        mmu.write_byte(0x0103, 0x01)  # Operando: 1
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 16, f"A debe ser 16 (0x10), es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado (es suma)"
        assert cpu.registers.get_flag_h(), "H debe estar ENCENDIDO (half-carry del bit 3 al 4)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (no hay carry completo)"

    def test_add_full_carry(self):
        """
        Test 3: Verificar que Carry completo se activa en overflow.
        
        Suma: 255 (0xFF) + 1 (0x01) = 0 (0x00) con wrap-around
        - Resultado: A = 0 (wrap-around de 8 bits)
        - Z: 1 (resultado es cero)
        - N: 0 (es suma)
        - H: 1 (hay half-carry: 0xF + 0x1 = 0x10)
        - C: 1 (HAY carry completo: overflow de 8 bits)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 255 (0xFF)
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0xFF)  # Operando: 255
        cpu.step()
        
        # Sumar 1 (0x01) a A
        mmu.write_byte(0x0102, 0xC6)  # ADD A, d8
        mmu.write_byte(0x0103, 0x01)  # Operando: 1
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 0, f"A debe ser 0 (wrap-around), es {cpu.registers.get_a()}"
        assert cpu.registers.get_flag_z(), "Z debe estar ENCENDIDO (resultado == 0)"
        assert not cpu.registers.get_flag_n(), "N debe estar apagado (es suma)"
        assert cpu.registers.get_flag_h(), "H debe estar ENCENDIDO (half-carry)"
        assert cpu.registers.get_flag_c(), "C debe estar ENCENDIDO (carry completo)"

    def test_sub_basic(self):
        """
        Test 4: Verificar resta básica sin borrow.
        
        Resta: 10 - 5 = 5
        - Resultado: A = 5 (0x05)
        - Z: 0 (no es cero)
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow)
        - C: 0 (no hay borrow)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 10 (0x0A)
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x0A)  # Operando: 10
        cpu.step()
        
        # Restar 5 (0x05) de A
        mmu.write_byte(0x0102, 0xD6)  # SUB d8
        mmu.write_byte(0x0103, 0x05)  # Operando: 5
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 5, f"A debe ser 5, es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert cpu.registers.get_flag_n(), "N debe estar ENCENDIDO (es resta)"
        assert not cpu.registers.get_flag_h(), "H debe estar apagado (no hay half-borrow)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (no hay borrow)"

    def test_sub_half_carry(self):
        """
        Test 5: Verificar que Half-Borrow se activa correctamente.
        
        Resta: 16 (0x10) - 1 (0x01) = 15 (0x0F)
        - Resultado: A = 15 (0x0F)
        - Z: 0 (no es cero)
        - N: 1 (es resta)
        - H: 1 (HAY half-borrow: nibble bajo 0x0 < 0x1, necesita borrow del nibble alto)
        - C: 0 (no hay borrow completo)
        
        Half-borrow ocurre cuando el nibble bajo del minuendo es menor
        que el nibble bajo del sustraendo. En este caso:
        - 16 (0x10) tiene nibble bajo 0x0
        - 1 (0x01) tiene nibble bajo 0x1
        - Como 0x0 < 0x1, necesitamos pedir prestado del nibble alto, activando H.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Cargar A = 16 (0x10)
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x10)  # Operando: 16
        cpu.step()
        
        # Restar 1 (0x01) de A
        mmu.write_byte(0x0102, 0xD6)  # SUB d8
        mmu.write_byte(0x0103, 0x01)  # Operando: 1
        cpu.step()
        
        # Verificar resultado
        assert cpu.registers.get_a() == 15, f"A debe ser 15 (0x0F), es {cpu.registers.get_a()}"
        assert not cpu.registers.get_flag_z(), "Z debe estar apagado (resultado != 0)"
        assert cpu.registers.get_flag_n(), "N debe estar ENCENDIDO (es resta)"
        assert cpu.registers.get_flag_h(), "H debe estar ENCENDIDO (half-borrow: 0x0 < 0x1)"
        assert not cpu.registers.get_flag_c(), "C debe estar apagado (no hay borrow completo)"

