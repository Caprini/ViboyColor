"""
Tests unitarios para ALU (Arithmetic Logic Unit) nativa en C++.

Este módulo prueba las operaciones aritméticas y lógicas implementadas
en la CPU nativa (C++), verificando:
- Operaciones básicas: ADD, SUB
- Gestión de flags: Z, N, H, C
- Half-Carry: Detección correcta de desbordamiento de nibble bajo
- Optimizaciones: XOR A (para limpiar registro A)

Tests críticos:
- Math: ADD A, d8 (10 + 2 = 12)
- Flags: SUB d8 (10 - 10 = 0) -> Debe encender Flag Z
- Half-Carry: ADD que cause desbordamiento de nibble bajo
- Optimization: XOR A debe dejar A en 0 y Z en 1

Nota (Step 0422): Tests migrados a WRAM usando load_program() y fixtures.
"""

import pytest
from tests.helpers_cpu import load_program

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestCoreCPUALU:
    """Tests para ALU nativa (C++)"""

    def test_add_immediate_basic(self, mmu):
        """
        Test 1: Verificar suma básica sin carry.
        
        Suma: 10 + 2 = 12
        - Resultado: A = 12 (0x0C)
        - Z: 0 (no es cero)
        - N: 0 (es suma)
        - H: 0 (no hay half-carry)
        - C: 0 (no hay carry)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar programa en WRAM (Step 0422: sin ROM-writes)
        program = [
            0x3E, 0x0A,  # LD A, 10
            0xC6, 0x02,  # ADD A, 2
        ]
        load_program(mmu, regs, program)
        
        # Ejecutar LD A
        cpu.step()
        
        # Ejecutar ADD A
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 12, f"A debe ser 12, es {regs.a}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert not regs.flag_n, "N debe estar apagado (es suma)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-carry)"
        assert not regs.flag_c, "C debe estar apagado (no hay carry)"

    def test_sub_immediate_zero_flag(self, mmu):
        """
        Test 2: Verificar que SUB activa Flag Z cuando resultado es 0.
        
        Resta: 10 - 10 = 0
        - Resultado: A = 0
        - Z: 1 (resultado == 0) <- CRÍTICO
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow)
        - C: 0 (no hay borrow)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x0A,  # LD A, 10
            0xD6, 0x0A,  # SUB 10
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # SUB
        
        # Verificar resultado
        assert regs.a == 0, f"A debe ser 0, es {regs.a}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-borrow)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow)"

    def test_add_half_carry(self, mmu):
        """
        Test 3: Verificar detección de Half-Carry.
        
        Suma: 0x0F + 0x01 = 0x10
        - Resultado: A = 0x10 (16)
        - Z: 0
        - N: 0
        - H: 1 (half-carry: bit 3 -> 4) <- CRÍTICO
        - C: 0
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x0F,  # LD A, 0x0F
            0xC6, 0x01,  # ADD A, 0x01
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # ADD A
        
        # Verificar resultado
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar ACTIVO (half-carry detectado)"
        assert not regs.flag_c, "C debe estar apagado"

    def test_xor_a_optimization(self, mmu):
        """
        Test 4: Verificar optimización XOR A (limpia A a 0).
        
        XOR A con A mismo siempre da 0 (optimización común en código Game Boy).
        - Resultado: A = 0
        - Z: 1 (resultado == 0)
        - N: 0
        - H: 0
        - C: 0
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x42,  # LD A, 0x42
            0xAF,        # XOR A
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # XOR A
        
        # Verificar resultado
        assert regs.a == 0, f"A debe ser 0, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert not regs.flag_n, "N debe estar apagado"
        assert not regs.flag_h, "H debe estar apagado"
        assert not regs.flag_c, "C debe estar apagado"

    def test_inc_a(self, mmu):
        """
        Test 5: Verificar incremento de A (INC A).
        
        Incrementa A en 1.
        - Flags: Z, N, H se actualizan; C no se afecta
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x0F,  # LD A, 0x0F
            0x3C,        # INC A
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # INC A
        
        # Verificar resultado
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar activo (half-carry)"

    def test_dec_a(self, mmu):
        """
        Test 6: Verificar decremento de A (DEC A).
        
        Decrementa A en 1.
        - Flags: Z, N, H se actualizan; C no se afecta
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x10,  # LD A, 0x10
            0x3D,        # DEC A
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # DEC A
        
        # Verificar resultado: 0x10 - 1 = 0x0F
        assert regs.a == 0x0F, f"A debe ser 0x0F, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert regs.flag_h, "H debe estar activo (half-borrow: nibble bajo 0x0 -> 0xF)"

    def test_add_full_carry(self, mmu):
        """
        Test 7: Verificar detección de Carry completo (overflow 8 bits).
        
        Suma: 0xFF + 0x01 = 0x00 (con carry)
        - Resultado: A = 0x00
        - Z: 1 (resultado == 0)
        - N: 0
        - H: 1 (half-carry también)
        - C: 1 (carry completo) <- CRÍTICO
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0xFF,  # LD A, 0xFF
            0xC6, 0x01,  # ADD A, 0x01
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # ADD A
        
        # Verificar resultado
        assert regs.a == 0x00, f"A debe ser 0x00, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar activo (half-carry)"
        assert regs.flag_c, "C debe estar ACTIVO (carry completo)"

    def test_sub_a_b(self, mmu):
        """
        Test 8: Verificar SUB B (resta con registro).
        
        Resta: A = 0x3E - B = 0x3E = 0x00
        - Resultado: A = 0x00
        - Z: 1 (resultado == 0) <- CRÍTICO para checksum
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow)
        - C: 0 (no hay borrow)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x3E,  # LD A, 0x3E
            0x06, 0x3E,  # LD B, 0x3E
            0x90,        # SUB B
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # LD B
        cpu.step()  # SUB B
        
        # Verificar resultado
        assert regs.a == 0x00, f"A debe ser 0x00, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-borrow)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow)"

    def test_sbc_a_b_with_borrow(self, mmu):
        """
        Test 9: Verificar SBC A, B con el flag de carry (borrow) activado.
        
        Resta con carry: A = 0x3B - B = 0x2A - C = 1 = 0x10
        - Resultado: A = 0x10
        - Z: 0 (resultado != 0)
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow en este caso)
        - C: 0 (no hay borrow completo)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x3B,  # LD A, 0x3B
            0x06, 0x2A,  # LD B, 0x2A
            0x98,        # SBC A, B
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # LD B
        
        # Activar flag C (borrow previo)
        regs.flag_c = True
        
        cpu.step()  # SBC A, B
        
        # Verificar resultado: 0x3B - 0x2A - 1 = 0x10
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow completo)"

    def test_sbc_a_b_with_full_borrow(self, mmu):
        """
        Test 10: Verificar SBC A, B con borrow completo (underflow).
        
        Resta con carry: A = 0x10 - B = 0x20 - C = 0 = 0xF0 (con borrow)
        - Resultado: A = 0xF0 (underflow)
        - Z: 0
        - N: 1
        - H: 1 (half-borrow: nibble bajo 0x0 < 0x0)
        - C: 1 (borrow completo) <- CRÍTICO
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        program = [
            0x3E, 0x10,  # LD A, 0x10
            0x06, 0x20,  # LD B, 0x20
            0x98,        # SBC A, B
        ]
        load_program(mmu, regs, program)
        
        cpu.step()  # LD A
        cpu.step()  # LD B
        
        # Desactivar flag C (sin borrow previo)
        regs.flag_c = False
        
        cpu.step()  # SBC A, B
        
        # Verificar resultado: 0x10 - 0x20 = 0xF0 (underflow)
        assert regs.a == 0xF0, f"A debe ser 0xF0, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert regs.flag_n, "N debe estar activo"
        assert regs.flag_c, "C debe estar ACTIVO (borrow completo detectado)"

