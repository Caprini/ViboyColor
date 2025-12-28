"""
Tests unitarios para la clase Registers.

Valida el comportamiento de los registros de 8 bits, pares de 16 bits,
y el manejo de flags según las especificaciones del hardware LR35902.
"""

import pytest

from src.cpu.registers import (
    Registers,
    FLAG_Z,
    FLAG_N,
    FLAG_H,
    FLAG_C,
    REGISTER_F_MASK,
)


class TestRegisters8Bits:
    """Tests para registros de 8 bits y wrap-around"""

    def test_registro_8_bits_wrap_around(self):
        """Test 1: Verificar que escribir en registros de 8 bits hace wrap-around"""
        reg = Registers()

        # Test con valor que excede 255 (debe hacer wrap-around)
        reg.set_a(256)
        assert reg.get_a() == 0, "256 debe hacer wrap-around a 0"

        reg.set_a(257)
        assert reg.get_a() == 1, "257 debe hacer wrap-around a 1"

        reg.set_a(0xFF)
        assert reg.get_a() == 0xFF, "0xFF debe mantenerse como 255"

        reg.set_a(0x100)
        assert reg.get_a() == 0, "0x100 debe hacer wrap-around a 0"

        # Test con valores negativos (tratados como unsigned)
        # En Python, valores negativos con & 0xFF se convierten correctamente
        reg.set_a(-1)
        assert reg.get_a() == 0xFF, "-1 debe convertirse a 0xFF"

        # Test con múltiples registros
        reg.set_b(300)
        reg.set_c(500)
        assert reg.get_b() == 44  # 300 % 256 = 44
        assert reg.get_c() == 244  # 500 % 256 = 244

    def test_todos_los_registros_8_bits(self):
        """Verificar que todos los registros de 8 bits funcionan correctamente"""
        reg = Registers()

        # Test cada registro individualmente
        reg.set_a(0xAA)
        reg.set_b(0xBB)
        reg.set_c(0xCC)
        reg.set_d(0xDD)
        reg.set_e(0xEE)
        reg.set_h(0x11)
        reg.set_l(0x22)

        assert reg.get_a() == 0xAA
        assert reg.get_b() == 0xBB
        assert reg.get_c() == 0xCC
        assert reg.get_d() == 0xDD
        assert reg.get_e() == 0xEE
        assert reg.get_h() == 0x11
        assert reg.get_l() == 0x22


class TestRegisters16Bits:
    """Tests para pares virtuales de 16 bits"""

    def test_par_bc_lectura_escritura(self):
        """Test 2: Verificar que leer/escribir BC modifica B y C correctamente"""
        reg = Registers()

        # Establecer BC como par de 16 bits
        reg.set_bc(0x1234)

        # Verificar que B y C se establecieron correctamente
        # 0x1234 en binario es:
        # B (byte alto) = 0x12 = 18
        # C (byte bajo) = 0x34 = 52
        assert reg.get_b() == 0x12, "B debe contener el byte alto"
        assert reg.get_c() == 0x34, "C debe contener el byte bajo"

        # Leer el par completo
        assert reg.get_bc() == 0x1234

        # Modificar B y C individualmente
        reg.set_b(0xAB)
        reg.set_c(0xCD)
        assert reg.get_bc() == 0xABCD

    def test_par_de_lectura_escritura(self):
        """Verificar que leer/escribir DE modifica D y E correctamente"""
        reg = Registers()

        reg.set_de(0x5678)
        assert reg.get_d() == 0x56
        assert reg.get_e() == 0x78
        assert reg.get_de() == 0x5678

        # Modificar individualmente
        reg.set_d(0xFF)
        reg.set_e(0x00)
        assert reg.get_de() == 0xFF00

    def test_par_hl_lectura_escritura(self):
        """Verificar que leer/escribir HL modifica H y L correctamente"""
        reg = Registers()

        reg.set_hl(0x9ABC)
        assert reg.get_h() == 0x9A
        assert reg.get_l() == 0xBC
        assert reg.get_hl() == 0x9ABC

        # Modificar individualmente
        reg.set_h(0x12)
        reg.set_l(0x34)
        assert reg.get_hl() == 0x1234

    def test_par_af_con_mascara_flags(self):
        """Verificar que AF maneja correctamente la máscara de F"""
        reg = Registers()

        # Establecer AF (F tiene máscara 0xF0)
        reg.set_af(0xABCD)  # F = 0xCD, pero debe quedar 0xC0 (bits bajos = 0)

        assert reg.get_a() == 0xAB
        assert reg.get_f() == 0xC0, "F debe tener bits bajos en 0"
        assert reg.get_af() == 0xABC0, "AF debe reflejar F con máscara aplicada"

    def test_pares_16_bits_wrap_around(self):
        """Verificar que los pares de 16 bits hacen wrap-around"""
        reg = Registers()

        # Test wrap-around en 16 bits (65536 debe volver a 0)
        reg.set_bc(0xFFFF)
        assert reg.get_bc() == 0xFFFF

        reg.set_bc(0x10000)
        assert reg.get_bc() == 0x0000

        reg.set_bc(0x12345)
        assert reg.get_bc() == 0x2345  # Solo se mantienen los 16 bits bajos


class TestRegistersFlags:
    """Tests para el registro F (Flags)"""

    def test_registro_f_ignora_bits_bajos(self):
        """Test 3: Verificar que el registro F ignora los 4 bits bajos"""
        reg = Registers()

        # Intentar establecer F con bits bajos
        reg.set_f(0xFF)  # Todos los bits activos
        assert reg.get_f() == 0xF0, "F debe ignorar los bits bajos (0-3)"

        reg.set_f(0xAB)  # 1010 1011
        assert reg.get_f() == 0xA0, "Solo bits 4-7 deben permanecer"

        reg.set_f(0x0F)  # Solo bits bajos
        assert reg.get_f() == 0x00, "Bits bajos deben ser siempre 0"

        reg.set_f(0x80)  # Solo bit 7 (FLAG_Z)
        assert reg.get_f() == 0x80

        reg.set_f(0x10)  # Solo bit 4 (FLAG_C)
        assert reg.get_f() == 0x10

    def test_set_flag(self):
        """Test 4: Verificar set_flag activa flags correctamente"""
        reg = Registers()
        reg.set_f(0x00)

        # Activar FLAG_Z
        reg.set_flag(FLAG_Z)
        assert reg.get_f() == FLAG_Z
        assert reg.check_flag(FLAG_Z) is True

        # Activar FLAG_C sin perder FLAG_Z
        reg.set_flag(FLAG_C)
        assert reg.get_f() == (FLAG_Z | FLAG_C)
        assert reg.check_flag(FLAG_Z) is True
        assert reg.check_flag(FLAG_C) is True

        # Activar todos los flags
        reg.set_flag(FLAG_N)
        reg.set_flag(FLAG_H)
        assert reg.get_f() == REGISTER_F_MASK  # Todos los bits válidos activos

    def test_clear_flag(self):
        """Verificar clear_flag desactiva flags correctamente"""
        reg = Registers()

        # Activar todos los flags
        reg.set_f(REGISTER_F_MASK)

        # Desactivar FLAG_Z
        reg.clear_flag(FLAG_Z)
        assert reg.check_flag(FLAG_Z) is False
        assert reg.check_flag(FLAG_C) is True  # Los demás deben seguir activos
        assert reg.check_flag(FLAG_N) is True
        assert reg.check_flag(FLAG_H) is True

        # Desactivar FLAG_C
        reg.clear_flag(FLAG_C)
        assert reg.check_flag(FLAG_C) is False
        assert reg.check_flag(FLAG_N) is True
        assert reg.check_flag(FLAG_H) is True

    def test_check_flag(self):
        """Verificar check_flag retorna correctamente el estado"""
        reg = Registers()
        reg.set_f(0x00)

        # Verificar que todos los flags están desactivados
        assert reg.check_flag(FLAG_Z) is False
        assert reg.check_flag(FLAG_N) is False
        assert reg.check_flag(FLAG_H) is False
        assert reg.check_flag(FLAG_C) is False

        # Activar FLAG_Z
        reg.set_flag(FLAG_Z)
        assert reg.check_flag(FLAG_Z) is True
        assert reg.check_flag(FLAG_N) is False

    def test_helpers_flags_individuales(self):
        """Verificar los helpers get_flag_*"""
        reg = Registers()

        # Test FLAG_Z
        reg.set_flag(FLAG_Z)
        assert reg.get_flag_z() is True
        assert reg.get_flag_n() is False
        reg.clear_flag(FLAG_Z)
        assert reg.get_flag_z() is False

        # Test FLAG_N
        reg.set_flag(FLAG_N)
        assert reg.get_flag_n() is True
        assert reg.get_flag_z() is False

        # Test FLAG_H
        reg.set_flag(FLAG_H)
        assert reg.get_flag_h() is True

        # Test FLAG_C
        reg.set_flag(FLAG_C)
        assert reg.get_flag_c() is True


class TestRegistersPCSP:
    """Tests para Program Counter y Stack Pointer"""

    def test_program_counter(self):
        """Verificar Program Counter (16 bits)"""
        reg = Registers()

        assert reg.get_pc() == 0

        reg.set_pc(0x1234)
        assert reg.get_pc() == 0x1234

        # Wrap-around
        reg.set_pc(0x10000)
        assert reg.get_pc() == 0x0000

        reg.set_pc(0xFFFF)
        assert reg.get_pc() == 0xFFFF

    def test_stack_pointer(self):
        """Verificar Stack Pointer (16 bits)"""
        reg = Registers()

        assert reg.get_sp() == 0

        reg.set_sp(0xABCD)
        assert reg.get_sp() == 0xABCD

        # Wrap-around
        reg.set_sp(0x10000)
        assert reg.get_sp() == 0x0000


class TestRegistersInicializacion:
    """Tests para verificar inicialización correcta"""

    def test_inicializacion_por_defecto(self):
        """Verificar que todos los registros se inicializan a 0"""
        reg = Registers()

        assert reg.get_a() == 0
        assert reg.get_b() == 0
        assert reg.get_c() == 0
        assert reg.get_d() == 0
        assert reg.get_e() == 0
        assert reg.get_h() == 0
        assert reg.get_l() == 0
        assert reg.get_f() == 0
        assert reg.get_pc() == 0
        assert reg.get_sp() == 0

        assert reg.get_af() == 0
        assert reg.get_bc() == 0
        assert reg.get_de() == 0
        assert reg.get_hl() == 0

        assert reg.check_flag(FLAG_Z) is False
        assert reg.check_flag(FLAG_N) is False
        assert reg.check_flag(FLAG_H) is False
        assert reg.check_flag(FLAG_C) is False

