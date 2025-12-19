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
        
        # Escribir NOP en la dirección 0
        mmu.write(0x0000, 0x00)
        regs.pc = 0x0000
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar resultados
        assert cycles == 1, "NOP debe consumir 1 M-Cycle"
        assert regs.pc == 0x0001, "PC debe incrementarse después de fetch"
        assert cpu.get_cycles() == 1, "Contador de ciclos debe ser 1"
    
    def test_ld_a_d8_instruction(self):
        """Test: La instrucción LD A, d8 (0x3E) funciona correctamente."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir LD A, 0x42 en la dirección 0
        # 0x3E = LD A, d8
        # 0x42 = valor inmediato (d8)
        mmu.write(0x0000, 0x3E)  # Opcode
        mmu.write(0x0001, 0x42)   # Valor inmediato
        regs.pc = 0x0000
        regs.a = 0x00  # Inicializar A a 0
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar resultados
        assert cycles == 2, "LD A, d8 debe consumir 2 M-Cycles"
        assert regs.a == 0x42, "Registro A debe contener 0x42"
        assert regs.pc == 0x0002, "PC debe ser 0x0002 (incrementado 2 veces)"
        assert cpu.get_cycles() == 2, "Contador de ciclos debe ser 2"
    
    def test_ld_a_d8_multiple_executions(self):
        """Test: Múltiples ejecuciones de LD A, d8 funcionan correctamente."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir múltiples instrucciones LD A, d8
        mmu.write(0x0000, 0x3E)  # LD A, 0x10
        mmu.write(0x0001, 0x10)
        mmu.write(0x0002, 0x3E)  # LD A, 0x20
        mmu.write(0x0003, 0x20)
        mmu.write(0x0004, 0x3E)  # LD A, 0x30
        mmu.write(0x0005, 0x30)
        
        regs.pc = 0x0000
        
        # Ejecutar primera instrucción
        cycles1 = cpu.step()
        assert cycles1 == 2
        assert regs.a == 0x10
        assert regs.pc == 0x0002
        
        # Ejecutar segunda instrucción
        cycles2 = cpu.step()
        assert cycles2 == 2
        assert regs.a == 0x20
        assert regs.pc == 0x0004
        
        # Ejecutar tercera instrucción
        cycles3 = cpu.step()
        assert cycles3 == 2
        assert regs.a == 0x30
        assert regs.pc == 0x0006
        
        # Verificar contador total de ciclos
        assert cpu.get_cycles() == 6
    
    def test_unknown_opcode_returns_zero(self):
        """Test: Un opcode desconocido retorna 0 (error)."""
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Escribir un opcode no implementado (por ejemplo, 0xFF)
        mmu.write(0x0000, 0xFF)
        regs.pc = 0x0000
        
        # Ejecutar un ciclo
        cycles = cpu.step()
        
        # Verificar que retorna 0 (error)
        assert cycles == 0, "Opcode desconocido debe retornar 0"
        # PC debe haberse incrementado al menos una vez (fetch)
        assert regs.pc == 0x0001, "PC debe incrementarse después de fetch"
    
    def test_cpu_with_shared_mmu_and_registers(self):
        """Test: Múltiples CPUs pueden compartir MMU y Registros (inyección de dependencias)."""
        mmu = PyMMU()
        regs = PyRegisters()
        
        # Crear dos CPUs que comparten la misma MMU y Registros
        cpu1 = PyCPU(mmu, regs)
        cpu2 = PyCPU(mmu, regs)
        
        # Escribir instrucciones en memoria
        mmu.write(0x0000, 0x3E)  # LD A, 0xAA
        mmu.write(0x0001, 0xAA)
        mmu.write(0x0002, 0x3E)  # LD A, 0xBB
        mmu.write(0x0003, 0xBB)
        
        # CPU1 ejecuta primera instrucción
        regs.pc = 0x0000
        cpu1.step()
        assert regs.a == 0xAA
        assert regs.pc == 0x0002
        
        # CPU2 ejecuta segunda instrucción (mismo estado compartido)
        cpu2.step()
        assert regs.a == 0xBB
        assert regs.pc == 0x0004
        
        # Verificar que cada CPU mantiene su propio contador de ciclos
        assert cpu1.get_cycles() == 2
        assert cpu2.get_cycles() == 2

