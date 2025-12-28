"""
Tests para LD A, (BC) y LD A, (DE)

Verifica:
- LD A, (BC) - opcode 0x0A
- LD A, (DE) - opcode 0x1A
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU


class TestLDIndirect:
    """Tests para LD A, (BC) y LD A, (DE)"""

    def test_ld_a_bc_ptr(self) -> None:
        """
        Test: Verificar LD A, (BC) - opcode 0x0A
        
        Lee un byte de la dirección apuntada por BC y lo carga en A.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_bc(0xC000)
        cpu.registers.set_a(0x00)  # A inicialmente en 0
        
        # Escribir valor en memoria
        mmu.write_byte(0xC000, 0x42)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x0100, 0x0A)  # LD A, (BC)
        
        # Ejecutar opcode
        cycles = cpu.step()
        
        # Verificaciones
        assert cycles == 2, f"LD A, (BC) debe consumir 2 M-Cycles, consumió {cycles}"
        assert cpu.registers.get_a() == 0x42, \
            f"A debe ser 0x42, es 0x{cpu.registers.get_a():02X}"
        assert cpu.registers.get_pc() == 0x0101, \
            f"PC debe avanzar a 0x0101, es 0x{cpu.registers.get_pc():04X}"
        assert cpu.registers.get_bc() == 0xC000, \
            f"BC no debe cambiar, es 0x{cpu.registers.get_bc():04X}"

    def test_ld_a_de_ptr(self) -> None:
        """
        Test: Verificar LD A, (DE) - opcode 0x1A
        
        Lee un byte de la dirección apuntada por DE y lo carga en A.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_de(0xD000)
        cpu.registers.set_a(0x00)  # A inicialmente en 0
        
        # Escribir valor en memoria
        mmu.write_byte(0xD000, 0x55)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x0100, 0x1A)  # LD A, (DE)
        
        # Ejecutar opcode
        cycles = cpu.step()
        
        # Verificaciones
        assert cycles == 2, f"LD A, (DE) debe consumir 2 M-Cycles, consumió {cycles}"
        assert cpu.registers.get_a() == 0x55, \
            f"A debe ser 0x55, es 0x{cpu.registers.get_a():02X}"
        assert cpu.registers.get_pc() == 0x0101, \
            f"PC debe avanzar a 0x0101, es 0x{cpu.registers.get_pc():04X}"
        assert cpu.registers.get_de() == 0xD000, \
            f"DE no debe cambiar, es 0x{cpu.registers.get_de():04X}"

    def test_ld_a_bc_ptr_wrap_around(self) -> None:
        """
        Test: Verificar que LD A, (BC) funciona con wrap-around de direcciones.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar BC en 0xFFFF (límite de 16 bits)
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_bc(0xFFFF)
        cpu.registers.set_a(0x00)
        
        # Escribir valor en 0xFFFF
        mmu.write_byte(0xFFFF, 0xAA)
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0x0A)
        
        # Ejecutar
        cycles = cpu.step()
        
        # Verificar
        assert cycles == 2
        assert cpu.registers.get_a() == 0xAA

    def test_ld_a_de_ptr_zero(self) -> None:
        """
        Test: Verificar que LD A, (DE) funciona con dirección 0x0000.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar DE en 0x0000
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_de(0x0000)
        cpu.registers.set_a(0x00)
        
        # Escribir valor en 0x0000
        mmu.write_byte(0x0000, 0x33)
        
        # Escribir opcode
        mmu.write_byte(0x0100, 0x1A)
        
        # Ejecutar
        cycles = cpu.step()
        
        # Verificar
        assert cycles == 2
        assert cpu.registers.get_a() == 0x33

    def test_ld_a_hl_ptr_decrement(self) -> None:
        """
        Test: Verificar LD A, (HL-) - opcode 0x3A
        
        Lee un byte de la dirección apuntada por HL y lo carga en A, luego decrementa HL.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x0100)
        cpu.registers.set_hl(0xC000)
        cpu.registers.set_a(0x00)
        
        # Escribir valor en memoria
        mmu.write_byte(0xC000, 0x77)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x0100, 0x3A)  # LD A, (HL-)
        
        # Ejecutar opcode
        cycles = cpu.step()
        
        # Verificaciones
        assert cycles == 2, f"LD A, (HL-) debe consumir 2 M-Cycles, consumió {cycles}"
        assert cpu.registers.get_a() == 0x77, \
            f"A debe ser 0x77, es 0x{cpu.registers.get_a():02X}"
        assert cpu.registers.get_hl() == 0xBFFF, \
            f"HL debe decrementar a 0xBFFF, es 0x{cpu.registers.get_hl():04X}"
        assert cpu.registers.get_pc() == 0x0101, \
            f"PC debe avanzar a 0x0101, es 0x{cpu.registers.get_pc():04X}"

