"""
Tests unitarios para instrucciones de salto (Jumps) de la CPU.

Valida las instrucciones de control de flujo:
- JP nn (0xC3): Salto absoluto incondicional
- JR e (0x18): Salto relativo incondicional
- JR NZ, e (0x20): Salto relativo condicional (si Z flag está desactivado)

Tests críticos:
- Saltos positivos y negativos (Two's Complement)
- Timing condicional (diferentes ciclos según si se toma o no el salto)
- Comportamiento correcto de PC después del salto
"""

import pytest

from src.cpu.core import CPU
from src.cpu.registers import FLAG_Z
from src.memory.mmu import MMU


class TestJumpAbsolute:
    """Tests para JP nn (Jump Absolute)"""

    def test_jp_absolute(self):
        """
        Test 1: Verificar que JP nn salta a una dirección absoluta.
        
        - Escribe JP 0xC000 en memoria (0xC3 0x00 0xC0)
        - Ejecuta step()
        - Verifica que PC == 0xC000
        - Verifica que ciclos == 4
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir JP 0xC000 (Little-Endian: 0x00 0xC0)
        mmu.write_byte(0x0100, 0xC3)  # Opcode JP nn
        mmu.write_byte(0x0101, 0x00)  # LSB de dirección
        mmu.write_byte(0x0102, 0xC0)  # MSB de dirección
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar que PC se estableció correctamente
        assert cpu.registers.get_pc() == 0xC000, (
            f"PC debe ser 0xC000 después de JP, es 0x{cpu.registers.get_pc():04X}"
        )
        
        # Verificar que consume 4 ciclos
        assert cycles == 4, f"JP nn debe consumir 4 M-Cycles, consumió {cycles}"

    def test_jp_absolute_wraparound(self):
        """
        Test 2: Verificar que JP nn funciona correctamente con direcciones que hacen wrap.
        
        - Salta a 0xFFFF (dirección máxima)
        - Verifica que PC se establece correctamente sin overflow
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Escribir JP 0xFFFF (Little-Endian: 0xFF 0xFF)
        mmu.write_byte(0x0100, 0xC3)
        mmu.write_byte(0x0101, 0xFF)
        mmu.write_byte(0x0102, 0xFF)
        
        cycles = cpu.step()
        
        assert cpu.registers.get_pc() == 0xFFFF
        assert cycles == 4


class TestJumpRelative:
    """Tests para JR e (Jump Relative)"""

    def test_jr_relative_positive(self):
        """
        Test 3: Verificar salto relativo positivo.
        
        - PC en 0x0100
        - JR +5 (offset positivo)
        - PC debe ser 0x0100 + 1 (opcode) + 1 (offset) + 5 = 0x0107
        
        Nota: El offset se suma al PC DESPUÉS de leer toda la instrucción.
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Escribir JR +5 (0x18 0x05)
        mmu.write_byte(0x0100, 0x18)  # Opcode JR e
        mmu.write_byte(0x0101, 0x05)  # Offset +5
        
        cycles = cpu.step()
        
        # PC inicial: 0x0100
        # Después de leer opcode: 0x0101
        # Después de leer offset: 0x0102
        # Después de sumar offset: 0x0102 + 5 = 0x0107
        assert cpu.registers.get_pc() == 0x0107, (
            f"PC debe ser 0x0107 después de JR +5, es 0x{cpu.registers.get_pc():04X}"
        )
        
        assert cycles == 3, f"JR e debe consumir 3 M-Cycles, consumió {cycles}"

    def test_jr_relative_negative(self):
        """
        Test 4: Verificar salto relativo negativo (Two's Complement).
        
        Este es el test CRÍTICO: verifica que 0xFF se interpreta como -1,
        no como 255. Si falla, los bucles infinitos saltarán hacia adelante.
        
        - PC en 0x0100
        - JR -2 (0x18 0xFE, donde 0xFE = 254 unsigned = -2 signed)
        - PC debe ser 0x0100 + 1 + 1 - 2 = 0x0100
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        # Escribir JR -2 (0x18 0xFE)
        # 0xFE = 254 en unsigned, pero -2 en signed (Two's Complement)
        mmu.write_byte(0x0100, 0x18)  # Opcode JR e
        mmu.write_byte(0x0101, 0xFE)  # Offset 0xFE = -2 signed
        
        cycles = cpu.step()
        
        # PC inicial: 0x0100
        # Después de leer opcode: 0x0101
        # Después de leer offset: 0x0102
        # Después de sumar offset: 0x0102 + (-2) = 0x0100
        assert cpu.registers.get_pc() == 0x0100, (
            f"PC debe ser 0x0100 después de JR -2, es 0x{cpu.registers.get_pc():04X}. "
            "Si es 0x0200, el byte no se está interpretando como signed."
        )
        
        assert cycles == 3

    def test_jr_relative_max_negative(self):
        """
        Test 5: Verificar salto relativo máximo negativo (-128).
        
        - JR -128 (0x18 0x80, donde 0x80 = 128 unsigned = -128 signed)
        - Verifica que retrocede correctamente
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0200)
        
        mmu.write_byte(0x0200, 0x18)  # Opcode JR e
        mmu.write_byte(0x0201, 0x80)  # Offset 0x80 = -128 signed
        
        cycles = cpu.step()
        
        # PC después de leer instrucción: 0x0202
        # Después de sumar -128: 0x0202 - 128 = 0x0182
        assert cpu.registers.get_pc() == 0x0182
        assert cycles == 3

    def test_jr_relative_max_positive(self):
        """
        Test 6: Verificar salto relativo máximo positivo (+127).
        
        - JR +127 (0x18 0x7F)
        - Verifica que avanza correctamente
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        mmu.write_byte(0x0100, 0x18)  # Opcode JR e
        mmu.write_byte(0x0101, 0x7F)  # Offset +127
        
        cycles = cpu.step()
        
        # PC después de leer instrucción: 0x0102
        # Después de sumar +127: 0x0102 + 127 = 0x0181
        assert cpu.registers.get_pc() == 0x0181
        assert cycles == 3

    def test_jr_relative_zero(self):
        """
        Test 7: Verificar salto relativo con offset 0 (no hace nada efectivo).
        
        - JR +0 (0x18 0x00)
        - PC debe avanzar normalmente (solo incrementar por la instrucción)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        
        mmu.write_byte(0x0100, 0x18)  # Opcode JR e
        mmu.write_byte(0x0101, 0x00)  # Offset 0
        
        cycles = cpu.step()
        
        # PC después de leer instrucción: 0x0102
        # Después de sumar 0: 0x0102
        assert cpu.registers.get_pc() == 0x0102
        assert cycles == 3


class TestJumpRelativeConditional:
    """Tests para JR NZ, e (Jump Relative if Not Zero)"""

    def test_jr_nz_taken(self):
        """
        Test 8: Verificar JR NZ cuando la condición se cumple (Z flag = 0, salta).
        
        - Establecer Z flag a 0 (desactivado)
        - Ejecutar JR NZ, +10
        - Verificar que salta
        - Verificar que ciclos == 3
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        # Asegurar que Z flag está desactivado
        cpu.registers.clear_flag(FLAG_Z)
        
        # Escribir JR NZ, +10 (0x20 0x0A)
        mmu.write_byte(0x0100, 0x20)  # Opcode JR NZ, e
        mmu.write_byte(0x0101, 0x0A)  # Offset +10
        
        cycles = cpu.step()
        
        # Verificar que saltó
        # PC después de leer instrucción: 0x0102
        # Después de sumar +10: 0x010C
        assert cpu.registers.get_pc() == 0x010C, (
            f"PC debe ser 0x010C después de JR NZ (taken), es 0x{cpu.registers.get_pc():04X}"
        )
        
        # Verificar timing: 3 M-Cycles cuando salta
        assert cycles == 3, (
            f"JR NZ debe consumir 3 M-Cycles cuando salta, consumió {cycles}"
        )

    def test_jr_nz_not_taken(self):
        """
        Test 9: Verificar JR NZ cuando la condición NO se cumple (Z flag = 1, no salta).
        
        Este test es CRÍTICO: verifica el timing condicional.
        
        - Establecer Z flag a 1 (activado)
        - Ejecutar JR NZ, +10
        - Verificar que NO salta (PC solo avanza normalmente)
        - Verificar que ciclos == 2 (diferente del caso anterior)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0100)
        # Activar Z flag
        cpu.registers.set_flag(FLAG_Z)
        
        # Escribir JR NZ, +10 (0x20 0x0A)
        mmu.write_byte(0x0100, 0x20)  # Opcode JR NZ, e
        mmu.write_byte(0x0101, 0x0A)  # Offset +10
        
        cycles = cpu.step()
        
        # Verificar que NO saltó
        # PC solo avanza por la instrucción: 0x0100 -> 0x0102
        assert cpu.registers.get_pc() == 0x0102, (
            f"PC debe ser 0x0102 después de JR NZ (not taken), es 0x{cpu.registers.get_pc():04X}"
        )
        
        # Verificar timing: 2 M-Cycles cuando NO salta
        assert cycles == 2, (
            f"JR NZ debe consumir 2 M-Cycles cuando NO salta, consumió {cycles}. "
            "Este es el test crítico de timing condicional."
        )

    def test_jr_nz_negative_taken(self):
        """
        Test 10: Verificar JR NZ con offset negativo cuando se toma el salto.
        
        - Z flag = 0
        - JR NZ, -5
        - Verifica que retrocede correctamente
        - Verifica ciclos = 3
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0200)
        cpu.registers.clear_flag(FLAG_Z)
        
        mmu.write_byte(0x0200, 0x20)  # Opcode JR NZ, e
        mmu.write_byte(0x0201, 0xFB)  # Offset 0xFB = -5 signed
        
        cycles = cpu.step()
        
        # PC después de leer instrucción: 0x0202
        # Después de sumar -5: 0x0202 - 5 = 0x01FD
        assert cpu.registers.get_pc() == 0x01FD
        assert cycles == 3

    def test_jr_nz_negative_not_taken(self):
        """
        Test 11: Verificar JR NZ con offset negativo cuando NO se toma el salto.
        
        - Z flag = 1
        - JR NZ, -5
        - Verifica que NO salta
        - Verifica ciclos = 2
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_pc(0x0200)
        cpu.registers.set_flag(FLAG_Z)
        
        mmu.write_byte(0x0200, 0x20)  # Opcode JR NZ, e
        mmu.write_byte(0x0201, 0xFB)  # Offset 0xFB = -5 signed
        
        cycles = cpu.step()
        
        # PC solo avanza normalmente: 0x0202
        assert cpu.registers.get_pc() == 0x0202
        assert cycles == 2

