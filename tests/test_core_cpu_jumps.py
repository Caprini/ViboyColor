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
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestJumpAbsolute:
    """Tests para JP nn (Jump Absolute) - 0xC3"""

    def test_jp_absolute(self):
        """
        Test: Verificar que JP nn salta a una dirección absoluta.
        
        - Escribe JP 0xC000 en memoria (0xC3 0x00 0xC0)
        - Ejecuta step()
        - Verifica que PC == 0xC000
        - Verifica que ciclos == 4
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Establecer PC inicial
        regs.pc = 0x0100
        
        # Escribir JP 0xC000 (Little-Endian: 0x00 0xC0)
        mmu.write(0x0100, 0xC3)  # Opcode JP nn
        mmu.write(0x0101, 0x00)  # LSB de dirección
        mmu.write(0x0102, 0xC0)  # MSB de dirección
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC se estableció correctamente
        assert regs.pc == 0xC000, (
            f"PC debe ser 0xC000 después de JP, es 0x{regs.pc:04X}"
        )
        
        # Verificar que consume 4 ciclos
        assert cycles == 4, f"JP nn debe consumir 4 M-Cycles, consumió {cycles}"
        assert cpu.get_cycles() == 4, "Contador acumulado debe ser 4"

    def test_jp_absolute_wraparound(self):
        """
        Test: Verificar que JP nn funciona correctamente con direcciones que hacen wrap.
        
        - Salta a 0xFFFF (dirección máxima)
        - Verifica que PC se establece correctamente sin overflow
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Escribir JP 0xFFFF (Little-Endian: 0xFF 0xFF)
        mmu.write(0x0100, 0xC3)
        mmu.write(0x0101, 0xFF)
        mmu.write(0x0102, 0xFF)
        
        cycles = cpu.step()
        
        assert regs.pc == 0xFFFF
        assert cycles == 4


class TestJumpRelative:
    """Tests para JR e (Jump Relative) - 0x18"""

    def test_jr_relative_positive(self):
        """
        Test: Verificar salto relativo positivo.
        
        - PC en 0x0100
        - JR +5 (offset positivo)
        - PC debe ser 0x0100 + 1 (opcode) + 1 (offset) + 5 = 0x0107
        
        Nota: El offset se suma al PC DESPUÉS de leer toda la instrucción.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Escribir JR +5 (0x18 0x05)
        mmu.write(0x0100, 0x18)  # Opcode JR e
        mmu.write(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # PC debe ser: 0x0100 (inicial) + 1 (opcode) + 1 (offset) + 5 (salto) = 0x0107
        assert regs.pc == 0x0107, (
            f"PC debe ser 0x0107 después de JR +5, es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR e debe consumir 3 M-Cycles, consumió {cycles}"

    def test_jr_relative_negative(self):
        """
        Test: Verificar salto relativo negativo (CRÍTICO para C++).
        
        - PC en 0x0105
        - JR -2 (offset negativo: 0xFE en complemento a dos)
        - PC debe retroceder
        
        Este test verifica que C++ maneja correctamente el cast de uint8_t a int8_t
        para obtener el valor negativo.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0105
        
        # Escribir JR -2 (0x18 0xFE)
        # 0xFE en complemento a dos es -2
        mmu.write(0x0105, 0x18)  # Opcode JR e
        mmu.write(0x0106, 0xFE)  # Offset -2 (0xFE = 254 unsigned, -2 signed)
        
        cycles = cpu.step()
        
        # PC debe ser: 0x0105 (inicial) + 1 (opcode) + 1 (offset) - 2 (salto) = 0x0105
        assert regs.pc == 0x0105, (
            f"PC debe ser 0x0105 después de JR -2, es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR e debe consumir 3 M-Cycles, consumió {cycles}"

    def test_jr_relative_loop(self):
        """
        Test: Simular un bucle con salto relativo negativo.
        
        - PC en 0x0200
        - JR -3 (offset negativo: 0xFD)
        - PC debe retroceder 3 posiciones desde después del offset
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0200
        
        # Escribir JR -3 (0x18 0xFD)
        mmu.write(0x0200, 0x18)  # Opcode JR e
        mmu.write(0x0201, 0xFD)  # Offset -3 (0xFD = 253 unsigned, -3 signed)
        
        cycles = cpu.step()
        
        # PC debe ser: 0x0200 + 1 + 1 - 3 = 0x01FF
        assert regs.pc == 0x01FF, (
            f"PC debe ser 0x01FF después de JR -3, es 0x{regs.pc:04X}"
        )
        assert cycles == 3


class TestJumpRelativeConditional:
    """Tests para JR NZ, e (Jump Relative if Not Zero) - 0x20"""

    def test_jr_nz_condition_true(self):
        """
        Test: Verificar que JR NZ salta cuando Z=0 (condición verdadera).
        
        - Flag Z desactivado (Z=0)
        - JR NZ +5
        - Debe saltar (igual que JR normal)
        - Debe consumir 3 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Desactivar flag Z (asegurar que el bit 7 de F es 0)
        regs.f = regs.f & 0x7F  # Limpiar bit 7 (FLAG_Z)
        
        # Escribir JR NZ +5 (0x20 0x05)
        mmu.write(0x0100, 0x20)  # Opcode JR NZ, e
        mmu.write(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # Debe saltar (Z=0, condición verdadera)
        assert regs.pc == 0x0107, (
            f"PC debe ser 0x0107 después de JR NZ +5 (Z=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR NZ debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_nz_condition_false(self):
        """
        Test: Verificar que JR NZ NO salta cuando Z=1 (condición falsa).
        
        - Flag Z activado (Z=1)
        - JR NZ +5
        - NO debe saltar (continúa ejecución normal)
        - Debe consumir 2 M-Cycles (menos ciclos porque no hay salto)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Activar flag Z (bit 7 de F = 1)
        regs.f = regs.f | 0x80  # Establecer bit 7 (FLAG_Z)
        
        # Escribir JR NZ +5 (0x20 0x05)
        mmu.write(0x0100, 0x20)  # Opcode JR NZ, e
        mmu.write(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # NO debe saltar (Z=1, condición falsa)
        # PC debe estar después de leer el offset: 0x0100 + 1 + 1 = 0x0102
        assert regs.pc == 0x0102, (
            f"PC debe ser 0x0102 después de JR NZ +5 (Z=1, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR NZ debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"

    def test_jr_nz_negative_when_condition_true(self):
        """
        Test: Verificar que JR NZ maneja correctamente offsets negativos cuando salta.
        
        - Flag Z desactivado
        - JR NZ -2
        - Debe saltar hacia atrás
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0200
        # Desactivar flag Z
        regs.f = regs.f & 0x7F
        
        # Escribir JR NZ -2 (0x20 0xFE)
        mmu.write(0x0200, 0x20)  # Opcode JR NZ, e
        mmu.write(0x0201, 0xFE)  # Offset -2
        
        cycles = cpu.step()
        
        # Debe saltar hacia atrás: 0x0200 + 1 + 1 - 2 = 0x0200
        assert regs.pc == 0x0200, (
            f"PC debe ser 0x0200 después de JR NZ -2 (Z=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, "JR NZ debe consumir 3 M-Cycles cuando salta (incluso hacia atrás)"


class TestJumpRelativeConditionalZ:
    """Tests para JR Z, e (Jump Relative if Zero) - 0x28"""

    def test_jr_z_taken(self):
        """
        Test: Verificar JR Z, e cuando el salto se toma (Z=1).
        
        - Flag Z activado (Z=1)
        - JR Z +10
        - Debe saltar (igual que JR normal)
        - Debe consumir 3 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Activar flag Z (bit 7 de F = 1)
        regs.f = regs.f | 0x80
        
        # Escribir JR Z +10 (0x28 0x0A)
        mmu.write(0x0100, 0x28)  # Opcode JR Z, e
        mmu.write(0x0101, 0x0A)  # Offset +10
        
        cycles = cpu.step()
        
        # Debe saltar (Z=1, condición verdadera)
        assert regs.pc == 0x010C, (
            f"PC debe ser 0x010C después de JR Z +10 (Z=1), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR Z debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_z_not_taken(self):
        """
        Test: Verificar JR Z, e cuando el salto NO se toma (Z=0).
        
        - Flag Z desactivado (Z=0)
        - JR Z +10
        - NO debe saltar (continúa ejecución normal)
        - Debe consumir 2 M-Cycles (menos ciclos porque no hay salto)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Desactivar flag Z
        regs.f = regs.f & 0x7F
        
        # Escribir JR Z +10 (0x28 0x0A)
        mmu.write(0x0100, 0x28)  # Opcode JR Z, e
        mmu.write(0x0101, 0x0A)  # Offset +10
        
        cycles = cpu.step()
        
        # NO debe saltar (Z=0, condición falsa)
        # PC debe estar después de leer el offset: 0x0100 + 1 + 1 = 0x0102
        assert regs.pc == 0x0102, (
            f"PC debe ser 0x0102 después de JR Z +10 (Z=0, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR Z debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"


class TestJumpRelativeConditionalC:
    """Tests para JR C, e (Jump Relative if Carry) - 0x38 y JR NC, e (Jump Relative if No Carry) - 0x30"""

    def test_jr_c_taken(self):
        """
        Test: Verificar JR C, e cuando el salto se toma (C=1).
        
        - Flag C activado (C=1)
        - JR C +5
        - Debe saltar
        - Debe consumir 3 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Activar flag C (bit 4 de F = 1)
        regs.f = regs.f | 0x10
        
        # Escribir JR C +5 (0x38 0x05)
        mmu.write(0x0100, 0x38)  # Opcode JR C, e
        mmu.write(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # Debe saltar (C=1, condición verdadera)
        assert regs.pc == 0x0107, (
            f"PC debe ser 0x0107 después de JR C +5 (C=1), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR C debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_c_not_taken(self):
        """
        Test: Verificar JR C, e cuando el salto NO se toma (C=0).
        
        - Flag C desactivado (C=0)
        - JR C +5
        - NO debe saltar
        - Debe consumir 2 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Desactivar flag C (limpiar bit 4)
        regs.f = regs.f & 0xEF
        
        # Escribir JR C +5 (0x38 0x05)
        mmu.write(0x0100, 0x38)  # Opcode JR C, e
        mmu.write(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # NO debe saltar (C=0, condición falsa)
        assert regs.pc == 0x0102, (
            f"PC debe ser 0x0102 después de JR C +5 (C=0, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR C debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"

    def test_jr_nc_taken(self):
        """
        Test: Verificar JR NC, e cuando el salto se toma (C=0).
        
        - Flag C desactivado (C=0)
        - JR NC +8
        - Debe saltar
        - Debe consumir 3 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Desactivar flag C
        regs.f = regs.f & 0xEF
        
        # Escribir JR NC +8 (0x30 0x08)
        mmu.write(0x0100, 0x30)  # Opcode JR NC, e
        mmu.write(0x0101, 0x08)  # Offset +8
        
        cycles = cpu.step()
        
        # Debe saltar (C=0, condición verdadera)
        assert regs.pc == 0x010A, (
            f"PC debe ser 0x010A después de JR NC +8 (C=0), es 0x{regs.pc:04X}"
        )
        assert cycles == 3, f"JR NC debe consumir 3 M-Cycles cuando salta, consumió {cycles}"

    def test_jr_nc_not_taken(self):
        """
        Test: Verificar JR NC, e cuando el salto NO se toma (C=1).
        
        - Flag C activado (C=1)
        - JR NC +8
        - NO debe saltar
        - Debe consumir 2 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        # Activar flag C
        regs.f = regs.f | 0x10
        
        # Escribir JR NC +8 (0x30 0x08)
        mmu.write(0x0100, 0x30)  # Opcode JR NC, e
        mmu.write(0x0101, 0x08)  # Offset +8
        
        cycles = cpu.step()
        
        # NO debe saltar (C=1, condición falsa)
        assert regs.pc == 0x0102, (
            f"PC debe ser 0x0102 después de JR NC +8 (C=1, no salta), es 0x{regs.pc:04X}"
        )
        assert cycles == 2, f"JR NC debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}"
