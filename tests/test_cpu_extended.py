"""
Tests unitarios para instrucciones extendidas: LDH (I/O Access) y Prefijo CB (Bit Operations).

Valida:
- LDH (n), A (0xE0): Escribe A en dirección 0xFF00 + n
- LDH A, (n) (0xF0): Lee de dirección 0xFF00 + n y carga en A
- Prefijo CB: Manejo correcto del prefijo 0xCB
- BIT 7, H (CB 0x7C): Test de bit con flags correctos
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestLDH:
    """Tests para instrucciones LDH (Load High - acceso a I/O)"""

    def test_ldh_write_read(self):
        """
        Test: LDH (n), A escribe correctamente en el área I/O (0xFF00-0xFFFF).
        
        - A = 0xAA
        - Ejecuta 0xE0 0x80 (LDH (0x80), A)
        - Verifica que Memoria[0xFF80] == 0xAA
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_a(0xAA)
        cpu.registers.set_pc(0x8000)  # Usar área fuera de ROM
        
        # Escribir opcode y operando en memoria
        mmu.write_byte(0x8000, 0xE0)  # LDH (n), A
        mmu.write_byte(0x8001, 0x80)  # n = 0x80
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió correctamente en 0xFF00 + 0x80 = 0xFF80
        assert mmu.read_byte(0xFF80) == 0xAA, "Memoria[0xFF80] debe ser 0xAA"
        assert cycles == 3, "Debe consumir 3 M-Cycles"
    
    def test_ldh_read(self):
        """
        Test: LDH A, (n) lee correctamente del área I/O.
        
        - Memoria[0xFF90] = 0x42
        - Ejecuta 0xF0 0x90 (LDH A, (0x90))
        - Verifica que A == 0x42
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        mmu.write_byte(0xFF90, 0x42)  # Escribir valor en área I/O
        cpu.registers.set_a(0x00)  # A inicialmente en 0
        cpu.registers.set_pc(0x8000)  # Usar área fuera de ROM
        
        # Escribir opcode y operando en memoria
        mmu.write_byte(0x8000, 0xF0)  # LDH A, (n)
        mmu.write_byte(0x8001, 0x90)  # n = 0x90
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se leyó correctamente
        assert cpu.registers.get_a() == 0x42, "A debe ser 0x42"
        assert cycles == 3, "Debe consumir 3 M-Cycles"
    
    def test_ldh_write_boundary(self):
        """
        Test: LDH (n), A funciona en el límite del área I/O (0xFF00).
        
        - A = 0x55
        - Ejecuta 0xE0 0x00 (LDH (0x00), A)
        - Verifica que Memoria[0xFF00] == 0x55
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_a(0x55)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xE0)  # LDH (n), A
        mmu.write_byte(0x8001, 0x00)  # n = 0x00
        
        cycles = cpu.step()
        
        assert mmu.read_byte(0xFF00) == 0x55, "Memoria[0xFF00] debe ser 0x55"
        assert cycles == 3


class TestCBPrefix:
    """Tests para el prefijo CB (instrucciones extendidas)"""

    def test_cb_bit_7_h_set(self):
        """
        Test: BIT 7, H cuando el bit 7 de H está encendido (H = 0x80).
        
        - H = 0x80 (bit 7 = 1)
        - Ejecuta 0xCB 0x7C (BIT 7, H)
        - Verifica Z=0 (bit está encendido, Z=0 significa "no es cero")
        - Verifica H=1 (siempre se activa en BIT)
        - Verifica N=0 (siempre se desactiva en BIT)
        - Verifica que C no cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_h(0x80)  # Bit 7 encendido
        cpu.registers.set_flag(FLAG_C)  # C inicialmente activado
        cpu.registers.set_pc(0x8000)
        
        # Escribir prefijo CB y opcode en memoria
        mmu.write_byte(0x8000, 0xCB)  # Prefijo CB
        mmu.write_byte(0x8001, 0x7C)  # BIT 7, H
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe ser 0 (bit está encendido)"
        assert cpu.registers.get_flag_h(), "H debe ser 1 (siempre activado en BIT)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0 (siempre desactivado en BIT)"
        assert cpu.registers.get_flag_c(), "C no debe cambiar (debe seguir activado)"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_cb_bit_7_h_clear(self):
        """
        Test: BIT 7, H cuando el bit 7 de H está apagado (H = 0x00).
        
        - H = 0x00 (bit 7 = 0)
        - Ejecuta 0xCB 0x7C (BIT 7, H)
        - Verifica Z=1 (bit está apagado, Z=1 significa "es cero")
        - Verifica H=1 (siempre se activa en BIT)
        - Verifica N=0 (siempre se desactiva en BIT)
        - Verifica que C no cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_h(0x00)  # Bit 7 apagado
        cpu.registers.clear_flag(FLAG_C)  # C inicialmente desactivado
        cpu.registers.set_pc(0x8000)
        
        # Escribir prefijo CB y opcode en memoria
        mmu.write_byte(0x8000, 0xCB)  # Prefijo CB
        mmu.write_byte(0x8001, 0x7C)  # BIT 7, H
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert cpu.registers.get_flag_z(), "Z debe ser 1 (bit está apagado)"
        assert cpu.registers.get_flag_h(), "H debe ser 1 (siempre activado en BIT)"
        assert not cpu.registers.get_flag_n(), "N debe ser 0 (siempre desactivado en BIT)"
        assert not cpu.registers.get_flag_c(), "C no debe cambiar (debe seguir desactivado)"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_cb_bit_7_h_preserves_c(self):
        """
        Test: BIT 7, H preserva el flag C independientemente del resultado.
        
        - H = 0x80 (bit 7 = 1)
        - C inicialmente activado
        - Ejecuta BIT 7, H
        - Verifica que C sigue activado
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_h(0x80)
        cpu.registers.set_flag(FLAG_C)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x7C)
        
        cpu.step()
        
        assert cpu.registers.get_flag_c(), "C debe preservarse (seguir activado)"
    
    def test_cb_bit_7_h_preserves_c_clear(self):
        """
        Test: BIT 7, H preserva el flag C cuando está desactivado.
        
        - H = 0x00 (bit 7 = 0)
        - C inicialmente desactivado
        - Ejecuta BIT 7, H
        - Verifica que C sigue desactivado
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_h(0x00)
        cpu.registers.clear_flag(FLAG_C)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xCB)
        mmu.write_byte(0x8001, 0x7C)
        
        cpu.step()
        
        assert not cpu.registers.get_flag_c(), "C debe preservarse (seguir desactivado)"

