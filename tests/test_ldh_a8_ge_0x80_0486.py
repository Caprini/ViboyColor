"""
Test Step 0486: LDH con a8 >= 0x80

Verifica que las instrucciones LDH (n),A y LDH A,(n) calculan correctamente
la dirección efectiva cuando el operando a8 es >= 0x80 (sin sign-extension).

Fuente: Pan Docs - LDH (n), A y LDH A, (n)
"""

import os
import pytest

try:
    from viboy_core import PyCPU, PyMMU, PyRegisters
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no está compilado", allow_module_level=True)


class TestLDHA8Ge0x80:
    """Tests para verificar LDH con a8 >= 0x80"""
    
    def test_ldh_write_0x92_writes_to_ff92(self):
        """Verifica que LDH (0x92),A escribe en 0xFF92, no en 0x0092 ni 0xFE92"""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir valor conocido en A
        regs.a = 0xAB
        
        # Ejecutar LDH (0x92),A (opcode 0xE0)
        # Usar WRAM (0xC000-0xDFFF) en lugar de ROM para poder escribir
        mmu.write(0xC000, 0xE0)  # LDH (a8),A
        mmu.write(0xC001, 0x92)  # a8 = 0x92
        
        regs.pc = 0xC000
        cycles = cpu.step()
        
        # Verificar que se escribió en 0xFF92, no en 0x0092 ni 0xFE92
        val_ff92 = mmu.read(0xFF92)
        val_0092 = mmu.read(0x0092)
        val_fe92 = mmu.read(0xFE92)
        
        assert val_ff92 == 0xAB, f"LDH (0x92),A debe escribir en 0xFF92, pero 0xFF92={val_ff92:02X}"
        assert val_0092 == 0x00, f"LDH (0x92),A NO debe escribir en 0x0092, pero 0x0092={val_0092:02X}"
        assert val_fe92 == 0x00, f"LDH (0x92),A NO debe escribir en 0xFE92, pero 0xFE92={val_fe92:02X}"
    
    def test_ldh_read_0x92_reads_from_ff92(self):
        """Verifica que LDH A,(0x92) lee de 0xFF92 y lee lo mismo que se escribió"""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir valor conocido en 0xFF92 directamente
        mmu.write(0xFF92, 0xCD)
        
        # Ejecutar LDH A,(0x92) (opcode 0xF0)
        # Usar WRAM (0xC000-0xDFFF) en lugar de ROM para poder escribir
        mmu.write(0xC000, 0xF0)  # LDH A,(a8)
        mmu.write(0xC001, 0x92)  # a8 = 0x92
        
        regs.pc = 0xC000
        cycles = cpu.step()
        
        # Verificar que A contiene el valor escrito
        a_value = regs.a
        assert a_value == 0xCD, f"LDH A,(0x92) debe leer 0xCD de 0xFF92, pero A={a_value:02X}"
    
    def test_ldh_write_0xFF_writes_to_ffff(self):
        """Verifica que LDH (0xFF),A escribe en 0xFFFF (IE register)"""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir valor conocido en A
        regs.a = 0x1F
        
        # Ejecutar LDH (0xFF),A (opcode 0xE0)
        # Usar WRAM (0xC000-0xDFFF) en lugar de ROM para poder escribir
        mmu.write(0xC000, 0xE0)  # LDH (a8),A
        mmu.write(0xC001, 0xFF)  # a8 = 0xFF
        
        regs.pc = 0xC000
        cycles = cpu.step()
        
        # Verificar que se escribió en 0xFFFF
        val_ffff = mmu.read(0xFFFF)
        assert val_ffff == 0x1F, f"LDH (0xFF),A debe escribir en 0xFFFF, pero 0xFFFF={val_ffff:02X}"
    
    def test_ldh_read_0xFF_reads_from_ffff(self):
        """Verifica que LDH A,(0xFF) lee de 0xFFFF (IE register)"""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir valor conocido en 0xFFFF directamente
        mmu.write(0xFFFF, 0x0F)
        
        # Ejecutar LDH A,(0xFF) (opcode 0xF0)
        # Usar WRAM (0xC000-0xDFFF) en lugar de ROM para poder escribir
        mmu.write(0xC000, 0xF0)  # LDH A,(a8)
        mmu.write(0xC001, 0xFF)  # a8 = 0xFF
        
        regs.pc = 0xC000
        cycles = cpu.step()
        
        # Verificar que A contiene el valor escrito
        a_value = regs.a
        assert a_value == 0x0F, f"LDH A,(0xFF) debe leer 0x0F de 0xFFFF, pero A={a_value:02X}"

