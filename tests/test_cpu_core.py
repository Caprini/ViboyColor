"""
Tests unitarios para la clase CPU.

Valida el ciclo Fetch-Decode-Execute y los primeros opcodes implementados:
- NOP (0x00): No operation
- LD A, d8 (0x3E): Load immediate into A
- LD B, d8 (0x06): Load immediate into B
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import Registers
from src.memory.mmu import MMU


class TestCPUCycle:
    """Tests para el ciclo Fetch-Decode-Execute básico"""

    def test_nop(self):
        """
        Test 1: Verificar que NOP (0x00) se ejecuta correctamente.
        
        - Escribe 0x00 en memoria en dirección 0x0100
        - Ejecuta step()
        - Verifica que PC aumentó en 1 (de 0x0100 a 0x0101)
        - Verifica que ciclos = 1
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir opcode NOP en memoria
        mmu.write_byte(0x0100, 0x00)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC avanzó 1 byte
        assert cpu.registers.get_pc() == 0x0101, "PC debe avanzar 1 byte después de NOP"
        
        # Verificar que consume 1 ciclo
        assert cycles == 1, "NOP debe consumir 1 M-Cycle"

    def test_ld_a_d8(self):
        """
        Test 2: Verificar que LD A, d8 (0x3E) carga un valor inmediato en A.
        
        - Escribe 0x3E y luego 0x42 en memoria
        - Ejecuta step()
        - Verifica que Registro A == 0x42
        - Verifica que PC aumentó en 2 (opcode + operand)
        - Verifica que ciclos = 2
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir instrucción LD A, 0x42
        mmu.write_byte(0x0100, 0x3E)  # Opcode LD A, d8
        mmu.write_byte(0x0101, 0x42)  # Operando inmediato
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que A contiene el valor correcto
        assert cpu.registers.get_a() == 0x42, f"Registro A debe ser 0x42, es 0x{cpu.registers.get_a():02X}"
        
        # Verificar que PC avanzó 2 bytes (opcode + operand)
        assert cpu.registers.get_pc() == 0x0102, "PC debe avanzar 2 bytes después de LD A, d8"
        
        # Verificar que consume 2 ciclos
        assert cycles == 2, "LD A, d8 debe consumir 2 M-Cycles"

    def test_ld_b_d8(self):
        """
        Test 3: Verificar que LD B, d8 (0x06) carga un valor inmediato en B.
        
        - Escribe 0x06 y luego 0xAB en memoria
        - Ejecuta step()
        - Verifica que Registro B == 0xAB
        - Verifica que PC aumentó en 2
        - Verifica que ciclos = 2
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir instrucción LD B, 0xAB
        mmu.write_byte(0x0100, 0x06)  # Opcode LD B, d8
        mmu.write_byte(0x0101, 0xAB)  # Operando inmediato
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que B contiene el valor correcto
        assert cpu.registers.get_b() == 0xAB, f"Registro B debe ser 0xAB, es 0x{cpu.registers.get_b():02X}"
        
        # Verificar que PC avanzó 2 bytes
        assert cpu.registers.get_pc() == 0x0102, "PC debe avanzar 2 bytes después de LD B, d8"
        
        # Verificar que consume 2 ciclos
        assert cycles == 2, "LD B, d8 debe consumir 2 M-Cycles"

    def test_unimplemented_opcode_raises(self):
        """
        Test 4: Verificar que un opcode no implementado lanza NotImplementedError.
        
        - Escribe un opcode no implementado (0xFF) en memoria
        - Verifica que step() lanza NotImplementedError
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir opcode no implementado
        mmu.write_byte(0x0100, 0xFF)
        
        # Verificar que lanza excepción
        with pytest.raises(NotImplementedError) as exc_info:
            cpu.step()
        
        # Verificar que el mensaje incluye el opcode
        assert "0xFF" in str(exc_info.value), "Mensaje de error debe incluir el opcode no implementado"

    def test_fetch_byte_helper(self):
        """
        Test 5: Verificar que fetch_byte() lee y avanza PC correctamente.
        
        - Escribe valores en memoria
        - Verifica que fetch_byte() lee correctamente y avanza PC
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0200)
        
        # Escribir valores en memoria
        mmu.write_byte(0x0200, 0xAA)
        mmu.write_byte(0x0201, 0xBB)
        
        # Leer primer byte
        value1 = cpu.fetch_byte()
        assert value1 == 0xAA, "fetch_byte debe leer 0xAA"
        assert cpu.registers.get_pc() == 0x0201, "PC debe avanzar a 0x0201"
        
        # Leer segundo byte
        value2 = cpu.fetch_byte()
        assert value2 == 0xBB, "fetch_byte debe leer 0xBB"
        assert cpu.registers.get_pc() == 0x0202, "PC debe avanzar a 0x0202"

    def test_multiple_instructions_sequential(self):
        """
        Test 6: Verificar que múltiples instrucciones se ejecutan secuencialmente.
        
        - Programa: LD A, 0x11; LD B, 0x22; NOP
        - Ejecuta cada instrucción
        - Verifica que los valores se cargan correctamente y PC avanza
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir programa en memoria
        mmu.write_byte(0x0100, 0x3E)  # LD A, d8
        mmu.write_byte(0x0101, 0x11)  # Operando
        mmu.write_byte(0x0102, 0x06)  # LD B, d8
        mmu.write_byte(0x0103, 0x22)  # Operando
        mmu.write_byte(0x0104, 0x00)  # NOP
        
        # Ejecutar primera instrucción (LD A, 0x11)
        cycles1 = cpu.step()
        assert cpu.registers.get_a() == 0x11, "A debe ser 0x11"
        assert cpu.registers.get_pc() == 0x0102, "PC debe ser 0x0102"
        assert cycles1 == 2, "Debe consumir 2 ciclos"
        
        # Ejecutar segunda instrucción (LD B, 0x22)
        cycles2 = cpu.step()
        assert cpu.registers.get_b() == 0x22, "B debe ser 0x22"
        assert cpu.registers.get_pc() == 0x0104, "PC debe ser 0x0104"
        assert cycles2 == 2, "Debe consumir 2 ciclos"
        
        # Ejecutar tercera instrucción (NOP)
        cycles3 = cpu.step()
        assert cpu.registers.get_pc() == 0x0105, "PC debe ser 0x0105"
        assert cycles3 == 1, "Debe consumir 1 ciclo"

