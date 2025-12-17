"""
Tests unitarios para cargas de 16 bits (BC, DE) y comparaciones (CP).

Valida las siguientes instrucciones:
- LD BC, d16 (0x01): Carga inmediata de 16 bits en BC
- LD DE, d16 (0x11): Carga inmediata de 16 bits en DE
- LD (BC), A (0x02): Escribe A en memoria apuntada por BC
- LD (DE), A (0x12): Escribe A en memoria apuntada por DE
- CP d8 (0xFE): Compara A con valor inmediato
- CP (HL) (0xBE): Compara A con valor en memoria
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z
from src.memory.mmu import MMU


class TestLoad16Bit:
    """Tests para cargas de registros de 16 bits"""

    def test_ld_bc_d16(self):
        """
        Test: Verificar que LD BC, d16 (0x01) carga un valor inmediato en BC.
        
        - Escribe 0x01 0x34 0x12 en memoria (Little-Endian: 0x1234)
        - Ejecuta step()
        - Verifica que BC = 0x1234 (B=0x12, C=0x34)
        - Verifica que PC avanzó 3 bytes
        - Verifica que consume 3 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir LD BC, d16 con valor 0x1234 (Little-Endian: 0x34 0x12)
        mmu.write_byte(0x0100, 0x01)  # Opcode
        mmu.write_byte(0x0101, 0x34)  # Low byte
        mmu.write_byte(0x0102, 0x12)  # High byte
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que BC se cargó correctamente
        assert cpu.registers.get_bc() == 0x1234, "BC debe ser 0x1234"
        assert cpu.registers.get_b() == 0x12, "B debe ser 0x12"
        assert cpu.registers.get_c() == 0x34, "C debe ser 0x34"
        
        # Verificar que PC avanzó 3 bytes
        assert cpu.registers.get_pc() == 0x0103, "PC debe avanzar 3 bytes"
        
        # Verificar que consume 3 M-Cycles
        assert cycles == 3, "LD BC, d16 debe consumir 3 M-Cycles"

    def test_ld_de_d16(self):
        """
        Test: Verificar que LD DE, d16 (0x11) carga un valor inmediato en DE.
        
        - Escribe 0x11 0x56 0x78 en memoria (Little-Endian: 0x7856)
        - Ejecuta step()
        - Verifica que DE = 0x7856 (D=0x78, E=0x56)
        - Verifica que PC avanzó 3 bytes
        - Verifica que consume 3 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir LD DE, d16 con valor 0x7856 (Little-Endian: 0x56 0x78)
        mmu.write_byte(0x0100, 0x11)  # Opcode
        mmu.write_byte(0x0101, 0x56)  # Low byte
        mmu.write_byte(0x0102, 0x78)  # High byte
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que DE se cargó correctamente
        assert cpu.registers.get_de() == 0x7856, "DE debe ser 0x7856"
        assert cpu.registers.get_d() == 0x78, "D debe ser 0x78"
        assert cpu.registers.get_e() == 0x56, "E debe ser 0x56"
        
        # Verificar que PC avanzó 3 bytes
        assert cpu.registers.get_pc() == 0x0103, "PC debe avanzar 3 bytes"
        
        # Verificar que consume 3 M-Cycles
        assert cycles == 3, "LD DE, d16 debe consumir 3 M-Cycles"

    def test_ld_bc_indirect_write(self):
        """
        Test: Verificar que LD (BC), A (0x02) escribe A en memoria apuntada por BC.
        
        - Establece BC = 0xC000
        - Establece A = 0xAA
        - Escribe opcode 0x02 en memoria
        - Ejecuta step()
        - Verifica que Memoria[0xC000] = 0xAA
        - Verifica que BC no cambió
        - Verifica que A no cambió
        - Verifica que consume 2 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer BC y A
        cpu.registers.set_bc(0xC000)
        cpu.registers.set_a(0xAA)
        
        # Escribir opcode LD (BC), A
        mmu.write_byte(0x0100, 0x02)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió en memoria
        assert mmu.read_byte(0xC000) == 0xAA, "Memoria[0xC000] debe ser 0xAA"
        
        # Verificar que BC no cambió
        assert cpu.registers.get_bc() == 0xC000, "BC no debe cambiar"
        
        # Verificar que A no cambió
        assert cpu.registers.get_a() == 0xAA, "A no debe cambiar"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "LD (BC), A debe consumir 2 M-Cycles"

    def test_ld_de_indirect_write(self):
        """
        Test: Verificar que LD (DE), A (0x12) escribe A en memoria apuntada por DE.
        
        - Establece DE = 0xD000
        - Establece A = 0x55
        - Escribe opcode 0x12 en memoria
        - Ejecuta step()
        - Verifica que Memoria[0xD000] = 0x55
        - Verifica que DE no cambió
        - Verifica que A no cambió
        - Verifica que consume 2 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer DE y A
        cpu.registers.set_de(0xD000)
        cpu.registers.set_a(0x55)
        
        # Escribir opcode LD (DE), A
        mmu.write_byte(0x0100, 0x12)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió en memoria
        assert mmu.read_byte(0xD000) == 0x55, "Memoria[0xD000] debe ser 0x55"
        
        # Verificar que DE no cambió
        assert cpu.registers.get_de() == 0xD000, "DE no debe cambiar"
        
        # Verificar que A no cambió
        assert cpu.registers.get_a() == 0x55, "A no debe cambiar"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "LD (DE), A debe consumir 2 M-Cycles"


class TestCompare:
    """Tests para instrucciones de comparación (CP)"""

    def test_cp_equality(self):
        """
        Test: Verificar que CP d8 activa Z cuando A == valor.
        
        - Establece A = 0x10
        - Escribe CP d8 con valor 0x10 en memoria
        - Ejecuta step()
        - Verifica que Z = 1 (iguales)
        - Verifica que N = 1 (siempre es resta)
        - Verifica que C = 0 (no hubo borrow, A >= valor)
        - Verifica que A NO cambió (sigue siendo 0x10)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A
        cpu.registers.set_a(0x10)
        
        # Escribir CP d8 con valor 0x10
        mmu.write_byte(0x0100, 0xFE)  # Opcode CP d8
        mmu.write_byte(0x0101, 0x10)  # Operando
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert cpu.registers.get_flag_z(), "Z debe estar activo (A == valor)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        assert not cpu.registers.get_flag_c(), "C debe estar inactivo (no hubo borrow)"
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x10, "A no debe cambiar en CP"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "CP d8 debe consumir 2 M-Cycles"

    def test_cp_less(self):
        """
        Test: Verificar que CP d8 activa C cuando A < valor.
        
        - Establece A = 0x01
        - Escribe CP d8 con valor 0x02 en memoria
        - Ejecuta step()
        - Verifica que Z = 0 (no iguales)
        - Verifica que N = 1 (siempre es resta)
        - Verifica que C = 1 (hubo borrow, A < valor)
        - Verifica que A NO cambió (sigue siendo 0x01)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A
        cpu.registers.set_a(0x01)
        
        # Escribir CP d8 con valor 0x02
        mmu.write_byte(0x0100, 0xFE)  # Opcode CP d8
        mmu.write_byte(0x0101, 0x02)  # Operando
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe estar inactivo (A != valor)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        assert cpu.registers.get_flag_c(), "C debe estar activo (hubo borrow, A < valor)"
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x01, "A no debe cambiar en CP"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "CP d8 debe consumir 2 M-Cycles"

    def test_cp_greater(self):
        """
        Test: Verificar que CP d8 no activa C cuando A > valor.
        
        - Establece A = 0x05
        - Escribe CP d8 con valor 0x03 en memoria
        - Ejecuta step()
        - Verifica que Z = 0 (no iguales)
        - Verifica que N = 1 (siempre es resta)
        - Verifica que C = 0 (no hubo borrow, A > valor)
        - Verifica que A NO cambió (sigue siendo 0x05)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A
        cpu.registers.set_a(0x05)
        
        # Escribir CP d8 con valor 0x03
        mmu.write_byte(0x0100, 0xFE)  # Opcode CP d8
        mmu.write_byte(0x0101, 0x03)  # Operando
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert not cpu.registers.get_flag_z(), "Z debe estar inactivo (A != valor)"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        assert not cpu.registers.get_flag_c(), "C debe estar inactivo (no hubo borrow, A > valor)"
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x05, "A no debe cambiar en CP"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "CP d8 debe consumir 2 M-Cycles"

    def test_cp_hl_ptr(self):
        """
        Test: Verificar que CP (HL) compara A con valor en memoria apuntada por HL.
        
        - Establece A = 0x42
        - Establece HL = 0xC000
        - Escribe 0x42 en Memoria[0xC000]
        - Escribe opcode 0xBE en memoria
        - Ejecuta step()
        - Verifica que Z = 1 (iguales)
        - Verifica que A NO cambió
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A y HL
        cpu.registers.set_a(0x42)
        cpu.registers.set_hl(0xC000)
        
        # Escribir valor en memoria
        mmu.write_byte(0xC000, 0x42)
        
        # Escribir opcode CP (HL)
        mmu.write_byte(0x0100, 0xBE)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert cpu.registers.get_flag_z(), "Z debe estar activo (A == (HL))"
        assert cpu.registers.get_flag_n(), "N debe estar activo (es resta)"
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x42, "A no debe cambiar en CP"
        
        # Verificar que consume 2 M-Cycles
        assert cycles == 2, "CP (HL) debe consumir 2 M-Cycles"

    def test_cp_half_carry(self):
        """
        Test: Verificar que CP d8 actualiza H correctamente cuando hay half-borrow.
        
        - Establece A = 0x10 (nibble bajo = 0x0)
        - Escribe CP d8 con valor 0x05 (nibble bajo = 0x5) en memoria
        - Ejecuta step()
        - Verifica que H = 1 (hubo borrow del nibble bajo: 0x0 < 0x5)
        - Verifica que A NO cambió
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A = 0x10 (nibble bajo = 0x0)
        cpu.registers.set_a(0x10)
        
        # Escribir CP d8 con valor 0x05 (nibble bajo = 0x5)
        mmu.write_byte(0x0100, 0xFE)  # Opcode CP d8
        mmu.write_byte(0x0101, 0x05)  # Operando
        
        # Ejecutar instrucción
        cpu.step()
        
        # Verificar que H está activo (hubo borrow del nibble bajo)
        assert cpu.registers.get_flag_h(), "H debe estar activo (hubo half-borrow)"
        
        # Verificar que A NO cambió
        assert cpu.registers.get_a() == 0x10, "A no debe cambiar en CP"

