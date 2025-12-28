"""
Tests unitarios para la clase PyRegisters (wrapper Cython de CoreRegisters).

Valida el comportamiento de los registros de 8 bits, pares de 16 bits,
y el manejo de flags según las especificaciones del hardware LR35902.

Este test valida la implementación C++ a través del wrapper Cython.
"""

import pytest

# Importar desde el módulo compilado Cython
try:
    from viboy_core import PyRegisters
except ImportError:
    pytest.skip("viboy_core no disponible (requiere compilación)", allow_module_level=True)


class TestPyRegisters8Bits:
    """Tests para registros de 8 bits y wrap-around"""

    def test_registro_8_bits_wrap_around(self):
        """Test 1: Verificar que escribir en registros de 8 bits hace wrap-around"""
        reg = PyRegisters()

        # Test con valor que excede 255 (debe hacer wrap-around)
        reg.a = 256
        assert reg.a == 0, "256 debe hacer wrap-around a 0"

        reg.a = 257
        assert reg.a == 1, "257 debe hacer wrap-around a 1"

        reg.a = 0xFF
        assert reg.a == 0xFF, "0xFF debe mantenerse como 255"

        reg.a = 0x100
        assert reg.a == 0, "0x100 debe hacer wrap-around a 0"

        # Test con múltiples registros
        reg.b = 300
        reg.c = 500
        assert reg.b == 44  # 300 % 256 = 44
        assert reg.c == 244  # 500 % 256 = 244

    def test_todos_los_registros_8_bits(self):
        """Verificar que todos los registros de 8 bits funcionan correctamente"""
        reg = PyRegisters()

        # Test cada registro individualmente
        reg.a = 0xAA
        reg.b = 0xBB
        reg.c = 0xCC
        reg.d = 0xDD
        reg.e = 0xEE
        reg.h = 0x11
        reg.l = 0x22

        assert reg.a == 0xAA
        assert reg.b == 0xBB
        assert reg.c == 0xCC
        assert reg.d == 0xDD
        assert reg.e == 0xEE
        assert reg.h == 0x11
        assert reg.l == 0x22


class TestPyRegisters16Bits:
    """Tests para pares virtuales de 16 bits"""

    def test_par_bc_lectura_escritura(self):
        """Test 2: Verificar que leer/escribir BC modifica B y C correctamente"""
        reg = PyRegisters()

        # Establecer BC como par de 16 bits
        reg.bc = 0x1234

        # Verificar que B y C se establecieron correctamente
        # 0x1234 en binario es:
        # B (byte alto) = 0x12 = 18
        # C (byte bajo) = 0x34 = 52
        assert reg.b == 0x12, "B debe contener el byte alto"
        assert reg.c == 0x34, "C debe contener el byte bajo"

        # Leer el par completo
        assert reg.bc == 0x1234

        # Modificar B y C individualmente
        reg.b = 0xAB
        reg.c = 0xCD
        assert reg.bc == 0xABCD

    def test_par_de_lectura_escritura(self):
        """Verificar que leer/escribir DE modifica D y E correctamente"""
        reg = PyRegisters()

        reg.de = 0x5678
        assert reg.d == 0x56
        assert reg.e == 0x78
        assert reg.de == 0x5678

        # Modificar individualmente
        reg.d = 0xFF
        reg.e = 0x00
        assert reg.de == 0xFF00

    def test_par_hl_lectura_escritura(self):
        """Verificar que leer/escribir HL modifica H y L correctamente"""
        reg = PyRegisters()

        reg.hl = 0x9ABC
        assert reg.h == 0x9A
        assert reg.l == 0xBC
        assert reg.hl == 0x9ABC

        # Modificar individualmente
        reg.h = 0x12
        reg.l = 0x34
        assert reg.hl == 0x1234

    def test_par_af_con_mascara_flags(self):
        """Verificar que AF maneja correctamente la máscara de F"""
        reg = PyRegisters()

        # Establecer AF (F tiene máscara 0xF0)
        reg.af = 0xABCD  # F = 0xCD, pero debe quedar 0xC0 (bits bajos = 0)

        assert reg.a == 0xAB
        assert reg.f == 0xC0, "F debe tener bits bajos en 0"
        assert reg.af == 0xABC0, "AF debe reflejar F con máscara aplicada"

    def test_pares_16_bits_wrap_around(self):
        """Verificar que los pares de 16 bits hacen wrap-around"""
        reg = PyRegisters()

        # Test wrap-around en 16 bits (65536 debe volver a 0)
        reg.bc = 0xFFFF
        assert reg.bc == 0xFFFF

        reg.bc = 0x10000
        assert reg.bc == 0x0000

        reg.bc = 0x12345
        assert reg.bc == 0x2345  # Solo se mantienen los 16 bits bajos

    def test_par_af_especifico(self):
        """Test específico: Escribir A=0x12, F=0xF0, leer AF y verificar 0x12F0"""
        reg = PyRegisters()

        reg.a = 0x12
        reg.f = 0xF0
        assert reg.af == 0x12F0, "AF debe ser 0x12F0 cuando A=0x12 y F=0xF0"

    def test_par_bc_especifico(self):
        """Test específico: Escribir BC=0xABCD, verificar B=0xAB, C=0xCD"""
        reg = PyRegisters()

        reg.bc = 0xABCD
        assert reg.b == 0xAB, "B debe ser 0xAB"
        assert reg.c == 0xCD, "C debe ser 0xCD"


class TestPyRegistersFlags:
    """Tests para el registro F (Flags)"""

    def test_registro_f_ignora_bits_bajos(self):
        """Test 3: Verificar que el registro F ignora los 4 bits bajos"""
        reg = PyRegisters()

        # Intentar establecer F con bits bajos
        reg.f = 0xFF  # Todos los bits activos
        assert reg.f == 0xF0, "F debe ignorar los bits bajos (0-3)"

        reg.f = 0xAB  # 1010 1011
        assert reg.f == 0xA0, "Solo bits 4-7 deben permanecer"

        reg.f = 0x0F  # Solo bits bajos
        assert reg.f == 0x00, "Bits bajos deben ser siempre 0"

        reg.f = 0x80  # Solo bit 7 (FLAG_Z)
        assert reg.f == 0x80

        reg.f = 0x10  # Solo bit 4 (FLAG_C)
        assert reg.f == 0x10

    def test_helpers_flags_individuales(self):
        """Test 4: Verificar los helpers get/set_flag_*"""
        reg = PyRegisters()

        # Test FLAG_Z
        reg.flag_z = True
        assert reg.flag_z is True
        assert reg.flag_n is False
        reg.flag_z = False
        assert reg.flag_z is False

        # Test FLAG_N
        reg.flag_n = True
        assert reg.flag_n is True
        assert reg.flag_z is False

        # Test FLAG_H
        reg.flag_h = True
        assert reg.flag_h is True

        # Test FLAG_C
        reg.flag_c = True
        assert reg.flag_c is True

        # Verificar que todos los flags pueden estar activos simultáneamente
        reg.flag_z = True
        reg.flag_n = True
        reg.flag_h = True
        reg.flag_c = True
        assert reg.flag_z is True
        assert reg.flag_n is True
        assert reg.flag_h is True
        assert reg.flag_c is True
        assert reg.f == 0xF0, "Todos los flags activos = 0xF0"

        # Desactivar todos
        reg.flag_z = False
        reg.flag_n = False
        reg.flag_h = False
        reg.flag_c = False
        assert reg.flag_z is False
        assert reg.flag_n is False
        assert reg.flag_h is False
        assert reg.flag_c is False
        assert reg.f == 0x00


class TestPyRegistersPCSP:
    """Tests para Program Counter y Stack Pointer"""

    def test_program_counter(self):
        """Verificar Program Counter (16 bits)"""
        reg = PyRegisters()

        assert reg.pc == 0

        reg.pc = 0x1234
        assert reg.pc == 0x1234

        # Wrap-around
        reg.pc = 0x10000
        assert reg.pc == 0x0000

        reg.pc = 0xFFFF
        assert reg.pc == 0xFFFF

    def test_stack_pointer(self):
        """Verificar Stack Pointer (16 bits)"""
        reg = PyRegisters()

        assert reg.sp == 0

        reg.sp = 0xABCD
        assert reg.sp == 0xABCD

        # Wrap-around
        reg.sp = 0x10000
        assert reg.sp == 0x0000


class TestPyRegistersInicializacion:
    """Tests para verificar inicialización correcta"""

    def test_inicializacion_por_defecto(self):
        """Verificar que todos los registros se inicializan a 0"""
        reg = PyRegisters()

        assert reg.a == 0
        assert reg.b == 0
        assert reg.c == 0
        assert reg.d == 0
        assert reg.e == 0
        assert reg.h == 0
        assert reg.l == 0
        assert reg.f == 0
        assert reg.pc == 0
        assert reg.sp == 0

        assert reg.af == 0
        assert reg.bc == 0
        assert reg.de == 0
        assert reg.hl == 0

        assert reg.flag_z is False
        assert reg.flag_n is False
        assert reg.flag_h is False
        assert reg.flag_c is False

