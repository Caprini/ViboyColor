"""
Tests de I/O básico (LDH) para CPU nativa (C++).

Este módulo prueba las instrucciones de I/O de memoria alta (LDH),
que son críticas para la comunicación entre la CPU y los registros
de hardware (PPU, Timer, etc.).

Fuente: Pan Docs - LDH (n), A y LDH A, (n)
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestCoreCPUIO:
    """Tests para instrucciones de I/O básico (LDH)."""
    
    def test_ldh_write(self):
        """Test: LDH (n), A (0xE0) escribe A en 0xFF00 + n."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.pc = 0x8000
        regs.a = 0xAB
        
        # Escribir instrucción LDH (n), A
        mmu.write(0x8000, 0xE0)  # Opcode LDH (n), A
        mmu.write(0x8001, 0x40)  # offset 'n' (para la dirección 0xFF40 - LCDC)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultados
        assert mmu.read(0xFF40) == 0xAB, "El valor de A debería estar en 0xFF40"
        assert regs.pc == 0x8002, "PC debe avanzar 2 bytes (opcode + offset)"
        assert cycles == 3, "LDH (n), A debe consumir 3 M-Cycles"
    
    def test_ldh_read(self):
        """Test: LDH A, (n) (0xF0) lee de 0xFF00 + n y lo carga en A."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.pc = 0x8000
        regs.a = 0x00  # A inicia en 0
        
        # Escribir un valor en HRAM (0xFF80) - no tiene lógica especial en MMU
        mmu.write(0xFF80, 0xCD)
        
        # Escribir instrucción LDH A, (n)
        mmu.write(0x8000, 0xF0)  # Opcode LDH A, (n)
        mmu.write(0x8001, 0x80)  # offset 'n' (para la dirección 0xFF80 - HRAM)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultados
        assert regs.a == 0xCD, "El registro A debería tener el valor de 0xFF80"
        assert regs.pc == 0x8002, "PC debe avanzar 2 bytes (opcode + offset)"
        assert cycles == 3, "LDH A, (n) debe consumir 3 M-Cycles"
    
    def test_ldh_write_lcdc(self):
        """Test: LDH (n), A puede escribir en LCDC (0xFF40)."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.pc = 0x0100
        regs.a = 0x91  # Valor típico de LCDC (LCD habilitado, BG habilitado, etc.)
        
        # Escribir instrucción LDH (n), A
        mmu.write(0x0100, 0xE0)  # Opcode LDH (n), A
        mmu.write(0x0101, 0x40)  # offset para 0xFF40 (LCDC)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que LCDC tiene el valor correcto
        assert mmu.read(0xFF40) == 0x91, "LCDC debe tener el valor escrito"
        assert cycles == 3
    
    def test_ldh_read_hram(self):
        """Test: LDH A, (n) puede leer de HRAM (0xFF80)."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.pc = 0x0200
        regs.a = 0x00
        
        # Escribir un valor en HRAM (0xFF80) - no tiene lógica especial
        mmu.write(0xFF80, 0x85)
        
        # Escribir instrucción LDH A, (n)
        mmu.write(0x0200, 0xF0)  # Opcode LDH A, (n)
        mmu.write(0x0201, 0x80)  # offset para 0xFF80 (HRAM)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que A tiene el valor de HRAM
        assert regs.a == 0x85, "A debe tener el valor leído de HRAM"
        assert cycles == 3
    
    def test_ldh_offset_wraparound(self):
        """Test: LDH maneja correctamente offsets que causan wraparound."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.pc = 0x0300
        regs.a = 0x42
        
        # Escribir instrucción LDH (n), A con offset 0xFF
        # 0xFF00 + 0xFF = 0xFFFF (IE - Interrupt Enable)
        mmu.write(0x0300, 0xE0)  # Opcode LDH (n), A
        mmu.write(0x0301, 0xFF)  # offset 0xFF
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que se escribió en 0xFFFF
        assert mmu.read(0xFFFF) == 0x42, "Debe escribir en 0xFFFF (IE)"
        assert cycles == 3

