"""
Tests unitarios para acceso a I/O usando el registro C como offset.

Valida:
- LD (C), A (0xE2): Escribe A en 0xFF00 + C
- LD A, (C) (0xF2): Lee de 0xFF00 + C a A

Estas instrucciones son variantes optimizadas de LDH que usan el registro C
en lugar de un byte inmediato, útiles para bucles de inicialización de hardware.
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU, IO_LCDC, IO_STAT, IO_BGP


class TestIOAccessViaC:
    """Tests para acceso a I/O usando registro C como offset"""

    def test_ld_c_a_write(self):
        """
        Test: LD (C), A escribe correctamente en 0xFF00 + C.
        
        - C = 0x40 (LCDC)
        - A = 0x91
        - Ejecuta 0xE2 (LD (C), A)
        - Verifica que Memoria[0xFF40] == 0x91
        - Verifica que C y A no cambian
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_c(0x40)  # LCDC
        cpu.registers.set_a(0x91)
        cpu.registers.set_pc(0x8000)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x8000, 0xE2)  # LD (C), A
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió correctamente en 0xFF40 (LCDC)
        assert mmu.read_byte(IO_LCDC) == 0x91, "LCDC debe ser 0x91"
        assert cpu.registers.get_c() == 0x40, "C no debe cambiar"
        assert cpu.registers.get_a() == 0x91, "A no debe cambiar"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_ld_c_a_write_stat(self):
        """
        Test: LD (C), A con C apuntando a HRAM (0xFF80).
        
        - C = 0x80 (HRAM)
        - A = 0x85
        - Ejecuta 0xE2
        - Verifica escritura en HRAM
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_c(0x80)  # HRAM
        cpu.registers.set_a(0x85)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xE2)  # LD (C), A
        
        cycles = cpu.step()
        
        assert mmu.read_byte(0xFF80) == 0x85, "HRAM[0xFF80] debe ser 0x85"
        assert cycles == 2
    
    def test_ld_c_a_write_bgp(self):
        """
        Test: LD (C), A con C apuntando a BGP (0xFF47).
        
        - C = 0x47 (BGP)
        - A = 0xE4
        - Ejecuta 0xE2
        - Verifica escritura en BGP
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_c(0x47)  # BGP
        cpu.registers.set_a(0xE4)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xE2)  # LD (C), A
        
        cycles = cpu.step()
        
        assert mmu.read_byte(IO_BGP) == 0xE4, "BGP debe ser 0xE4"
        assert cycles == 2
    
    def test_ld_a_c_read(self):
        """
        Test: LD A, (C) lee correctamente de 0xFF00 + C (HRAM).
        
        - Escribir 0x55 en 0xFF80 (HRAM)
        - C = 0x80
        - Ejecuta 0xF2 (LD A, (C))
        - Verifica que A == 0x55
        - Verifica que C no cambia
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Pre-escribir valor en HRAM
        mmu.write_byte(0xFF80, 0x55)
        
        # Configurar estado inicial
        cpu.registers.set_c(0x80)  # HRAM
        cpu.registers.set_a(0x00)  # A inicialmente en 0
        cpu.registers.set_pc(0x8000)
        
        # Escribir opcode en memoria
        mmu.write_byte(0x8000, 0xF2)  # LD A, (C)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se leyó correctamente
        assert cpu.registers.get_a() == 0x55, "A debe ser 0x55"
        assert cpu.registers.get_c() == 0x80, "C no debe cambiar"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_ld_a_c_read_lcdc(self):
        """
        Test: LD A, (C) leyendo de LCDC (0xFF40).
        
        - Escribir 0x80 en LCDC
        - C = 0x40
        - Ejecuta 0xF2
        - Verifica lectura correcta
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        mmu.write_byte(IO_LCDC, 0x80)
        
        cpu.registers.set_c(0x40)  # LCDC
        cpu.registers.set_a(0x00)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xF2)  # LD A, (C)
        
        cycles = cpu.step()
        
        assert cpu.registers.get_a() == 0x80, "A debe ser 0x80"
        assert cycles == 2
    
    def test_ld_c_a_wrap_around(self):
        """
        Test: LD (C), A con wrap-around de dirección I/O.
        
        - C = 0xFF (máximo valor)
        - A = 0x42
        - Ejecuta 0xE2
        - Verifica que escribe en 0xFFFF (IE, aunque técnicamente fuera del rango I/O)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_c(0xFF)
        cpu.registers.set_a(0x42)
        cpu.registers.set_pc(0x8000)
        
        mmu.write_byte(0x8000, 0xE2)  # LD (C), A
        
        cycles = cpu.step()
        
        # 0xFF00 + 0xFF = 0xFFFF (IE)
        assert mmu.read_byte(0xFFFF) == 0x42, "Debe escribir en 0xFFFF"
        assert cycles == 2

