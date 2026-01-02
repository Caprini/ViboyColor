"""
Tests de integración para instrucciones de salto (Jumps) en CPU nativa (C++).

Este módulo prueba el control de flujo implementado en C++:
- JP nn (0xC3): Salto absoluto incondicional
- JR e (0x18): Salto relativo incondicional
- JR NZ, e (0x20): Salto relativo condicional

Tests críticos:
- Saltos positivos y negativos (Two's Complement nativo en C++)
- Timing condicional (diferentes ciclos según si se toma o no el salto)
- Comportamiento correcto de PC después del salto

Nota Step 0423: TODOS los tests migrados a WRAM usando load_program() y fixture mmu estándar.
"""

import pytest
from tests.helpers_cpu import load_program, TEST_EXEC_BASE

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestJumpAbsolute:
    """Tests para JP nn (Jump Absolute) - 0xC3 - Step 0423: ejecuta desde WRAM"""

    def test_jp_absolute(self, mmu):
        """
        Test: Verificar que JP nn salta a una dirección absoluta.
        
        - Escribe JP 0xC000 en memoria (0xC3 0x00 0xC0)
        - Ejecuta step()
        - Verifica que PC == 0xC000
        - Verifica que ciclos == 4
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar JP 0xC000 (Little-Endian: 0x00 0xC0)
        load_program(mmu, regs, [0xC3, 0x00, 0xC0])  # JP nn
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC se estableció correctamente
        assert regs.pc == 0xC000, (
            f"PC debe ser 0xC000 después de JP, es 0x{regs.pc:04X}"
        )
        
        # Verificar que consume 4 ciclos
        assert cycles == 4, f"JP nn debe consumir 4 M-Cycles, consumió {cycles}"
        assert cpu.get_cycles() == 4, "Contador acumulado debe ser 4"

    def test_jp_absolute_wraparound(self, mmu):
        """
        Test: Verificar que JP nn funciona correctamente con direcciones que hacen wrap.
        
        - Salta a 0xFFFF (dirección máxima)
        - Verifica que PC se establece correctamente sin overflow
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar JP 0xFFFF (Little-Endian: 0xFF 0xFF)
        load_program(mmu, regs, [0xC3, 0xFF, 0xFF])
        
        cycles = cpu.step()
        
        assert regs.pc == 0xFFFF
        assert cycles == 4


class TestJumpRelative:
    """Tests para JR e (Jump Relative) - 0x18 - Step 0423: ejecuta desde WRAM"""

    def test_jr_relative_positive(self, mmu):
        """
        Test: Verificar salto relativo positivo.
        
        - PC en TEST_EXEC_BASE
        - JR +5 (offset positivo)
        - PC debe ser TEST_EXEC_BASE + 2 (instrucción) + 5 (offset) = TEST_EXEC_BASE + 7
        
        Nota: El offset se suma al PC DESPUÉS de leer toda la instrucción.
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar JR +5 (0x18 0x05)
        load_program(mmu, regs, [0x18, 0x05])
        
        cycles = cpu.step()
        
        # PC debe ser: TEST_EXEC_BASE + 2 (instrucción) + 5 (offset)
        expected_pc = TEST_EXEC_BASE + 7
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR +5, es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR e debe consumir 3 M-Cycles, consumió {cycles}"

    def test_jr_relative_negative(self, mmu):
        """
        Test: Verificar salto relativo negativo (CRÍTICO para C++).
        
        - PC en TEST_EXEC_BASE
        - JR -2 (offset negativo: 0xFE en complemento a dos)
        - PC debe ser TEST_EXEC_BASE + 2 - 2 = TEST_EXEC_BASE (loop infinito)
        
        Este test verifica que C++ maneja correctamente el cast de uint8_t a int8_t
        para obtener el valor negativo.
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar JR -2 (0x18 0xFE)
        # 0xFE en complemento a dos es -2
        load_program(mmu, regs, [0x18, 0xFE])
        
        cycles = cpu.step()
        
        # PC debe ser: TEST_EXEC_BASE + 2 (instrucción) - 2 (offset) = TEST_EXEC_BASE
        expected_pc = TEST_EXEC_BASE
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR -2, es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR e debe consumir 3 M-Cycles, consumió {cycles}"

    def test_jr_relative_loop(self, mmu):
        """
        Test: Simular un bucle con salto relativo negativo.
        
        - PC en TEST_EXEC_BASE
        - JR -3 (offset negativo: 0xFD)
        - PC debe retroceder 3 posiciones desde después del offset
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar JR -3 (0x18 0xFD)
        load_program(mmu, regs, [0x18, 0xFD])
        
        cycles = cpu.step()
        
        # PC debe ser: TEST_EXEC_BASE + 2 - 3 = TEST_EXEC_BASE - 1
        expected_pc = TEST_EXEC_BASE - 1
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR -3, es 0x{regs.pc:04X}"
        )
        assert cycles == 3


class TestJumpRelativeConditional:
    """Tests para JR NZ, e (Jump Relative if Not Zero) - 0x20 - Step 0423: ejecuta desde WRAM"""

    def test_jr_nz_condition_true(self, mmu):
        """
        Test: Verificar que JR NZ salta cuando Z=0 (condición verdadera).
        
        - Flag Z desactivado (Z=0)
        - JR NZ +5
        - Debe saltar (igual que JR normal)
        - Debe consumir 3 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Desactivar flag Z (asegurar que el bit 7 de F es 0)
        regs.f = regs.f & 0x7F  # Limpiar bit 7 (FLAG_Z)
        
        # Cargar JR NZ +5 (0x20 0x05)
        load_program(mmu, regs, [0x20, 0x05])
        
        cycles = cpu.step()
        
        # Debe saltar (Z=0, condición verdadera)
        expected_pc = TEST_EXEC_BASE + 7
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR NZ +5 (Z=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR NZ debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_nz_condition_false(self, mmu):
        """
        Test: Verificar que JR NZ NO salta cuando Z=1 (condición falsa).
        
        - Flag Z activado (Z=1)
        - JR NZ +5
        - NO debe saltar (continúa ejecución normal)
        - Debe consumir 2 M-Cycles (menos ciclos porque no hay salto)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Activar flag Z (bit 7 de F = 1)
        regs.f = regs.f | 0x80  # Establecer bit 7 (FLAG_Z)
        
        # Cargar JR NZ +5 (0x20 0x05)
        load_program(mmu, regs, [0x20, 0x05])
        
        cycles = cpu.step()
        
        # NO debe saltar (Z=1, condición falsa)
        # PC debe estar después de leer el offset: TEST_EXEC_BASE + 2
        expected_pc = TEST_EXEC_BASE + 2
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR NZ +5 (Z=1, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR NZ debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"

    def test_jr_nz_negative_when_condition_true(self, mmu):
        """
        Test: Verificar que JR NZ maneja correctamente offsets negativos cuando salta.
        
        - Flag Z desactivado
        - JR NZ -2
        - Debe saltar hacia atrás
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Desactivar flag Z
        regs.f = regs.f & 0x7F
        
        # Cargar JR NZ -2 (0x20 0xFE)
        load_program(mmu, regs, [0x20, 0xFE])
        
        cycles = cpu.step()
        
        # Debe saltar hacia atrás: TEST_EXEC_BASE + 2 - 2 = TEST_EXEC_BASE
        expected_pc = TEST_EXEC_BASE
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR NZ -2 (Z=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, "JR NZ debe consumir 3 M-Cycles cuando salta (incluso hacia atrás)"


class TestJumpRelativeConditionalZ:
    """Tests para JR Z, e (Jump Relative if Zero) - 0x28 - Step 0423: ejecuta desde WRAM"""

    def test_jr_z_taken(self, mmu):
        """
        Test: Verificar JR Z, e cuando el salto se toma (Z=1).
        
        - Flag Z activado (Z=1)
        - JR Z +10
        - Debe saltar (igual que JR normal)
        - Debe consumir 3 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Activar flag Z (bit 7 de F = 1)
        regs.f = regs.f | 0x80
        
        # Cargar JR Z +10 (0x28 0x0A)
        load_program(mmu, regs, [0x28, 0x0A])
        
        cycles = cpu.step()
        
        # Debe saltar (Z=1, condición verdadera)
        expected_pc = TEST_EXEC_BASE + 12
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR Z +10 (Z=1), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR Z debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_z_not_taken(self, mmu):
        """
        Test: Verificar JR Z, e cuando el salto NO se toma (Z=0).
        
        - Flag Z desactivado (Z=0)
        - JR Z +10
        - NO debe saltar (continúa ejecución normal)
        - Debe consumir 2 M-Cycles (menos ciclos porque no hay salto)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Desactivar flag Z
        regs.f = regs.f & 0x7F
        
        # Cargar JR Z +10 (0x28 0x0A)
        load_program(mmu, regs, [0x28, 0x0A])
        
        cycles = cpu.step()
        
        # NO debe saltar (Z=0, condición falsa)
        # PC debe estar después de leer el offset: TEST_EXEC_BASE + 2
        expected_pc = TEST_EXEC_BASE + 2
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR Z +10 (Z=0, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR Z debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"


class TestJumpRelativeConditionalC:
    """Tests para JR C, e (Jump Relative if Carry) - 0x38 y JR NC, e (Jump Relative if No Carry) - 0x30 - Step 0423: ejecuta desde WRAM"""

    def test_jr_c_taken(self, mmu):
        """
        Test: Verificar JR C, e cuando el salto se toma (C=1).
        
        - Flag C activado (C=1)
        - JR C +5
        - Debe saltar
        - Debe consumir 3 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Activar flag C (bit 4 de F = 1)
        regs.f = regs.f | 0x10
        
        # Cargar JR C +5 (0x38 0x05)
        load_program(mmu, regs, [0x38, 0x05])
        
        cycles = cpu.step()
        
        # Debe saltar (C=1, condición verdadera)
        expected_pc = TEST_EXEC_BASE + 7
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR C +5 (C=1), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR C debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_c_not_taken(self, mmu):
        """
        Test: Verificar JR C, e cuando el salto NO se toma (C=0).
        
        - Flag C desactivado (C=0)
        - JR C +5
        - NO debe saltar
        - Debe consumir 2 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Desactivar flag C (limpiar bit 4)
        regs.f = regs.f & 0xEF
        
        # Cargar JR C +5 (0x38 0x05)
        load_program(mmu, regs, [0x38, 0x05])
        
        cycles = cpu.step()
        
        # NO debe saltar (C=0, condición falsa)
        expected_pc = TEST_EXEC_BASE + 2
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR C +5 (C=0, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR C debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"

    def test_jr_nc_taken(self, mmu):
        """
        Test: Verificar JR NC, e cuando el salto se toma (C=0).
        
        - Flag C desactivado (C=0)
        - JR NC +8
        - Debe saltar
        - Debe consumir 3 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Desactivar flag C
        regs.f = regs.f & 0xEF
        
        # Cargar JR NC +8 (0x30 0x08)
        load_program(mmu, regs, [0x30, 0x08])
        
        cycles = cpu.step()
        
        # Debe saltar (C=0, condición verdadera)
        expected_pc = TEST_EXEC_BASE + 10
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR NC +8 (C=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR NC debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_nc_not_taken(self, mmu):
        """
        Test: Verificar JR NC, e cuando el salto NO se toma (C=1).
        
        - Flag C activado (C=1)
        - JR NC +8
        - NO debe saltar
        - Debe consumir 2 M-Cycles
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Activar flag C
        regs.f = regs.f | 0x10
        
        # Cargar JR NC +8 (0x30 0x08)
        load_program(mmu, regs, [0x30, 0x08])
        
        cycles = cpu.step()
        
        # NO debe saltar (C=1, condición falsa)
        expected_pc = TEST_EXEC_BASE + 2
        assert regs.pc == expected_pc, (
            f"PC debe ser 0x{expected_pc:04X} después de JR NC +8 (C=1, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR NC debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"
