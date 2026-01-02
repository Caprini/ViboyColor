"""
Tests de integración para CPU nativa (C++).

Este módulo prueba el esqueleto básico de la CPU migrada a C++,
verificando que el ciclo Fetch-Decode-Execute funciona correctamente
con inyección de dependencias (MMU y Registros).
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)

# Importar helpers para tests de CPU
from .helpers_cpu import load_program, TEST_EXEC_BASE


class TestCoreCPU:
    """Tests para el esqueleto básico de CPU nativa."""
    
    def test_cpu_initialization(self):
        """Test: La CPU se inicializa correctamente con MMU y Registros."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Verificar que se creó correctamente
        assert cpu is not None
        assert cpu.get_cycles() == 0
    
    def test_nop_instruction(self):
        """Test: La instrucción NOP (0x00) funciona correctamente."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar programa de test en WRAM
        load_program(mmu, regs, [0x00])  # NOP
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar resultados
        assert cycles == 1, "NOP debe consumir 1 M-Cycle"
        assert regs.pc == TEST_EXEC_BASE + 1, "PC debe incrementarse después de fetch"
        assert cpu.get_cycles() == 1, "Contador de ciclos debe ser 1"
    
    def test_ld_a_d8_instruction(self):
        """Test: La instrucción LD A, d8 (0x3E) funciona correctamente."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar programa de test en WRAM
        # 0x3E = LD A, d8
        # 0x42 = valor inmediato (d8)
        load_program(mmu, regs, [0x3E, 0x42])
        regs.a = 0x00  # Inicializar A a 0
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar resultados
        assert cycles == 2, "LD A, d8 debe consumir 2 M-Cycles"
        assert regs.a == 0x42, "Registro A debe contener 0x42"
        assert regs.pc == TEST_EXEC_BASE + 2, "PC debe incrementarse 2 bytes"
        assert cpu.get_cycles() == 2, "Contador de ciclos debe ser 2"
    
    def test_ld_a_d8_multiple_executions(self):
        """Test: Múltiples ejecuciones de LD A, d8 funcionan correctamente."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar múltiples instrucciones LD A, d8 en WRAM
        load_program(mmu, regs, [
            0x3E, 0x10,  # LD A, 0x10
            0x3E, 0x20,  # LD A, 0x20
            0x3E, 0x30,  # LD A, 0x30
        ])
        
        # Ejecutar primera instrucción
        cycles1 = cpu.step()
        assert cycles1 == 2
        assert regs.a == 0x10
        assert regs.pc == TEST_EXEC_BASE + 2
        
        # Ejecutar segunda instrucción
        cycles2 = cpu.step()
        assert cycles2 == 2
        assert regs.a == 0x20
        assert regs.pc == TEST_EXEC_BASE + 4
        
        # Ejecutar tercera instrucción
        cycles3 = cpu.step()
        assert cycles3 == 2
        assert regs.a == 0x30
        assert regs.pc == TEST_EXEC_BASE + 6
        
        # Verificar contador total de ciclos
        assert cpu.get_cycles() == 6
    
    def test_unknown_opcode_returns_zero(self):
        """Test: Un opcode desconocido retorna 0 (error)."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar opcode no implementado en WRAM (0xD3 es un opcode ilegal en Game Boy)
        load_program(mmu, regs, [0xD3])
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar que retorna 0 (error)
        assert cycles == 0, "Opcode desconocido debe retornar 0"
        # PC debe haberse incrementado al menos una vez (fetch)
        assert regs.pc == TEST_EXEC_BASE + 1, "PC debe incrementarse después de fetch"
    
    def test_cpu_with_shared_mmu_and_registers(self):
        """Test: Múltiples CPUs pueden compartir MMU y Registros (inyección de dependencias)."""
        mmu = PyMMU()
        regs = PyRegisters()
        
        # Crear dos CPUs que comparten la misma MMU y Registros
        cpu1 = PyCPU(mmu, regs)
        cpu2 = PyCPU(mmu, regs)
        
        # Cargar instrucciones en WRAM
        load_program(mmu, regs, [
            0x3E, 0xAA,  # LD A, 0xAA
            0x3E, 0xBB,  # LD A, 0xBB
        ])
        
        # CPU1 ejecuta primera instrucción
        cpu1.step()
        assert regs.a == 0xAA
        assert regs.pc == TEST_EXEC_BASE + 2
        
        # CPU2 ejecuta segunda instrucción (mismo estado compartido)
        cpu2.step()
        assert regs.a == 0xBB
        assert regs.pc == TEST_EXEC_BASE + 4
        
        # Verificar que cada CPU mantiene su propio contador de ciclos
        assert cpu1.get_cycles() == 2
        assert cpu2.get_cycles() == 2

