"""
Tests unitarios para direccionamiento directo (LD (nn), A y LD A, (nn)).

Valida los opcodes 0xEA y 0xFA:
- LD (nn), A (0xEA): Escribe A en una dirección absoluta de 16 bits
- LD A, (nn) (0xFA): Lee de una dirección absoluta de 16 bits a A

Estas instrucciones son críticas para acceder a variables globales y registros
de hardware sin usar registros intermedios.
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU


class TestLoadDirect:
    """Tests para direccionamiento directo (LD (nn), A y LD A, (nn))"""
    
    def test_ld_direct_write(self):
        """
        Test 1: Verificar escritura directa a memoria (LD (nn), A - 0xEA).
        
        - Establece A = 0x55
        - Ejecuta LD (0xC000), A (0xEA seguido de 0x00 0xC0 en Little-Endian)
        - Verifica que memoria[0xC000] = 0x55
        - Verifica que consume 4 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A = 0x55
        cpu.registers.set_a(0x55)
        
        # Escribir opcode LD (nn), A (0xEA) seguido de dirección 0xC000 (Little-Endian: 0x00 0xC0)
        mmu.write_byte(0x0100, 0xEA)  # Opcode
        mmu.write_byte(0x0101, 0x00)  # Byte bajo de dirección
        mmu.write_byte(0x0102, 0xC0)  # Byte alto de dirección
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que memoria[0xC000] = 0x55
        assert mmu.read_byte(0xC000) == 0x55, "Memoria en 0xC000 debe contener el valor de A"
        
        # Verificar que A no cambió
        assert cpu.registers.get_a() == 0x55, "A no debe cambiar"
        
        # Verificar que PC avanzó 3 bytes (opcode + 2 bytes de dirección)
        assert cpu.registers.get_pc() == 0x0103, "PC debe avanzar 3 bytes"
        
        # Verificar que consume 4 M-Cycles (fetch opcode + fetch 2 bytes + write)
        assert cycles == 4, "LD (nn), A debe consumir 4 M-Cycles"
    
    def test_ld_direct_read(self):
        """
        Test 2: Verificar lectura directa de memoria (LD A, (nn) - 0xFA).
        
        - Escribe 0x42 en memoria[0xC000]
        - Ejecuta LD A, (0xC000) (0xFA seguido de 0x00 0xC0 en Little-Endian)
        - Verifica que A = 0x42
        - Verifica que consume 4 M-Cycles
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir valor en memoria
        mmu.write_byte(0xC000, 0x42)
        
        # Escribir opcode LD A, (nn) (0xFA) seguido de dirección 0xC000 (Little-Endian: 0x00 0xC0)
        mmu.write_byte(0x0100, 0xFA)  # Opcode
        mmu.write_byte(0x0101, 0x00)  # Byte bajo de dirección
        mmu.write_byte(0x0102, 0xC0)  # Byte alto de dirección
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que A = 0x42
        assert cpu.registers.get_a() == 0x42, "A debe contener el valor de memoria[0xC000]"
        
        # Verificar que la memoria no cambió
        assert mmu.read_byte(0xC000) == 0x42, "Memoria no debe cambiar"
        
        # Verificar que PC avanzó 3 bytes (opcode + 2 bytes de dirección)
        assert cpu.registers.get_pc() == 0x0103, "PC debe avanzar 3 bytes"
        
        # Verificar que consume 4 M-Cycles (fetch opcode + fetch 2 bytes + read)
        assert cycles == 4, "LD A, (nn) debe consumir 4 M-Cycles"
    
    def test_ld_direct_write_read_roundtrip(self):
        """
        Test 3: Verificar ida y vuelta completa (write + read).
        
        - Escribe A = 0xAA en 0xD000 usando LD (nn), A
        - Lee de 0xD000 a A usando LD A, (nn)
        - Verifica que el valor se preserva correctamente
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Establecer A = 0xAA
        cpu.registers.set_a(0xAA)
        
        # Escribir LD (0xD000), A
        mmu.write_byte(0x0100, 0xEA)  # Opcode
        mmu.write_byte(0x0101, 0x00)  # Byte bajo
        mmu.write_byte(0x0102, 0xD0)  # Byte alto
        
        cycles1 = cpu.step()
        assert mmu.read_byte(0xD000) == 0xAA, "Debe escribir correctamente"
        assert cycles1 == 4
        
        # Ahora leer de vuelta usando LD A, (0xD000)
        # Cambiar el valor de A primero para verificar que se sobrescribe
        cpu.registers.set_a(0x00)
        
        mmu.write_byte(0x0103, 0xFA)  # Opcode
        mmu.write_byte(0x0104, 0x00)  # Byte bajo
        mmu.write_byte(0x0105, 0xD0)  # Byte alto
        
        cycles2 = cpu.step()
        assert cpu.registers.get_a() == 0xAA, "Debe leer correctamente el valor escrito"
        assert cycles2 == 4
    
    def test_ld_direct_different_addresses(self):
        """
        Test 4: Verificar que funciona con diferentes direcciones.
        
        - Escribe A en múltiples direcciones usando LD (nn), A
        - Verifica que cada dirección tiene el valor correcto
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Escribir 0x11 en 0xC000
        cpu.registers.set_a(0x11)
        mmu.write_byte(0x0100, 0xEA)
        mmu.write_byte(0x0101, 0x00)
        mmu.write_byte(0x0102, 0xC0)
        cpu.step()
        assert mmu.read_byte(0xC000) == 0x11
        
        # Escribir 0x22 en 0xD000
        cpu.registers.set_a(0x22)
        mmu.write_byte(0x0103, 0xEA)
        mmu.write_byte(0x0104, 0x00)
        mmu.write_byte(0x0105, 0xD0)
        cpu.step()
        assert mmu.read_byte(0xD000) == 0x22
        
        # Escribir 0x33 en 0xE000
        cpu.registers.set_a(0x33)
        mmu.write_byte(0x0106, 0xEA)
        mmu.write_byte(0x0107, 0x00)
        mmu.write_byte(0x0108, 0xE0)
        cpu.step()
        assert mmu.read_byte(0xE000) == 0x33
        
        # Verificar que todas las direcciones tienen valores distintos
        assert mmu.read_byte(0xC000) == 0x11
        assert mmu.read_byte(0xD000) == 0x22
        assert mmu.read_byte(0xE000) == 0x33

