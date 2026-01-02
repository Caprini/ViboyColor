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
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestCoreCPUALU:
    """Tests para ALU nativa (C++)"""

    def test_add_immediate_basic(self):
        """
        Test 1: Verificar suma básica sin carry.
        
        Suma: 10 + 2 = 12
        - Resultado: A = 12 (0x0C)
        - Z: 0 (no es cero)
        - N: 0 (es suma)
        - H: 0 (no hay half-carry)
        - C: 0 (no hay carry)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Establecer PC inicial
        regs.pc = 0x0100
        
        # Cargar A = 10 (0x0A)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x0A)  # Operando: 10
        cpu.step()
        
        # Sumar 2 (0x02) a A
        mmu.write(0x0102, 0xC6)  # ADD A, d8
        mmu.write(0x0103, 0x02)  # Operando: 2
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 12, f"A debe ser 12, es {regs.a}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert not regs.flag_n, "N debe estar apagado (es suma)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-carry)"
        assert not regs.flag_c, "C debe estar apagado (no hay carry)"

    def test_sub_immediate_zero_flag(self):
        """
        Test 2: Verificar que SUB activa Flag Z cuando resultado es 0.
        
        Resta: 10 - 10 = 0
        - Resultado: A = 0
        - Z: 1 (resultado == 0) <- CRÍTICO
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow)
        - C: 0 (no hay borrow)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 10 (0x0A)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x0A)  # Operando: 10
        cpu.step()
        
        # Restar 10 (0x0A) de A
        mmu.write(0x0102, 0xD6)  # SUB d8
        mmu.write(0x0103, 0x0A)  # Operando: 10
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0, f"A debe ser 0, es {regs.a}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-borrow)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow)"

    def test_add_half_carry(self):
        """
        Test 3: Verificar detección de Half-Carry.
        
        Suma: 0x0F + 0x01 = 0x10
        - Resultado: A = 0x10 (16)
        - Z: 0
        - N: 0
        - H: 1 (half-carry: bit 3 -> 4) <- CRÍTICO
        - C: 0
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x0F (15)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x0F)  # Operando: 0x0F
        cpu.step()
        
        # Sumar 0x01 a A
        mmu.write(0x0102, 0xC6)  # ADD A, d8
        mmu.write(0x0103, 0x01)  # Operando: 0x01
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar ACTIVO (half-carry detectado)"
        assert not regs.flag_c, "C debe estar apagado"

    def test_xor_a_optimization(self):
        """
        Test 4: Verificar optimización XOR A (limpia A a 0).
        
        XOR A con A mismo siempre da 0 (optimización común en código Game Boy).
        - Resultado: A = 0
        - Z: 1 (resultado == 0)
        - N: 0
        - H: 0
        - C: 0
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x42 (valor arbitrario)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x42)  # Operando: 0x42
        cpu.step()
        
        # XOR A (0xAF) - debe limpiar A a 0
        mmu.write(0x0102, 0xAF)  # XOR A
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0, f"A debe ser 0, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert not regs.flag_n, "N debe estar apagado"
        assert not regs.flag_h, "H debe estar apagado"
        assert not regs.flag_c, "C debe estar apagado"

    def test_inc_a(self):
        """
        Test 5: Verificar incremento de A (INC A).
        
        Incrementa A en 1.
        - Flags: Z, N, H se actualizan; C no se afecta
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x0F
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x0F)  # Operando: 0x0F
        cpu.step()
        
        # INC A (0x3C)
        mmu.write(0x0102, 0x3C)  # INC A
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar activo (half-carry)"

    def test_dec_a(self):
        """
        Test 6: Verificar decremento de A (DEC A).
        
        Decrementa A en 1.
        - Flags: Z, N, H se actualizan; C no se afecta
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x10 (para probar half-borrow: nibble bajo = 0x0)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x10)  # Operando: 0x10
        cpu.step()
        
        # DEC A (0x3D)
        mmu.write(0x0102, 0x3D)  # DEC A
        cpu.step()
        
        # Verificar resultado: 0x10 - 1 = 0x0F
        assert regs.a == 0x0F, f"A debe ser 0x0F, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert regs.flag_h, "H debe estar activo (half-borrow: nibble bajo 0x0 -> 0xF)"

    def test_add_full_carry(self):
        """
        Test 7: Verificar detección de Carry completo (overflow 8 bits).
        
        Suma: 0xFF + 0x01 = 0x00 (con carry)
        - Resultado: A = 0x00
        - Z: 1 (resultado == 0)
        - N: 0
        - H: 1 (half-carry también)
        - C: 1 (carry completo) <- CRÍTICO
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0xFF (255)
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0xFF)  # Operando: 0xFF
        cpu.step()
        
        # Sumar 0x01 a A
        mmu.write(0x0102, 0xC6)  # ADD A, d8
        mmu.write(0x0103, 0x01)  # Operando: 0x01
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0x00, f"A debe ser 0x00, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert not regs.flag_n, "N debe estar apagado"
        assert regs.flag_h, "H debe estar activo (half-carry)"
        assert regs.flag_c, "C debe estar ACTIVO (carry completo)"

    def test_sub_a_b(self):
        """
        Test 8: Verificar SUB B (resta con registro).
        
        Resta: A = 0x3E - B = 0x3E = 0x00
        - Resultado: A = 0x00
        - Z: 1 (resultado == 0) <- CRÍTICO para checksum
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow)
        - C: 0 (no hay borrow)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x3E
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x3E)  # Operando: 0x3E
        cpu.step()
        
        # Cargar B = 0x3E
        mmu.write(0x0102, 0x06)  # LD B, d8
        mmu.write(0x0103, 0x3E)  # Operando: 0x3E
        cpu.step()
        
        # SUB B (0x90)
        mmu.write(0x0104, 0x90)  # SUB B
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0x00, f"A debe ser 0x00, es 0x{regs.a:02X}"
        assert regs.flag_z, "Z debe estar ACTIVO (resultado == 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_h, "H debe estar apagado (no hay half-borrow)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow)"

    def test_sbc_a_b_with_borrow(self):
        """
        Test 9: Verificar SBC A, B con el flag de carry (borrow) activado.
        
        Resta con carry: A = 0x3B - B = 0x2A - C = 1 = 0x10
        - Resultado: A = 0x10
        - Z: 0 (resultado != 0)
        - N: 1 (es resta)
        - H: 0 (no hay half-borrow en este caso)
        - C: 0 (no hay borrow completo)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x3B
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x3B)  # Operando: 0x3B
        cpu.step()
        
        # Cargar B = 0x2A
        mmu.write(0x0102, 0x06)  # LD B, d8
        mmu.write(0x0103, 0x2A)  # Operando: 0x2A
        cpu.step()
        
        # Activar flag C (borrow previo)
        regs.flag_c = True
        
        # SBC A, B (0x98)
        mmu.write(0x0104, 0x98)  # SBC A, B
        cpu.step()
        
        # Verificar resultado: 0x3B - 0x2A - 1 = 0x10
        assert regs.a == 0x10, f"A debe ser 0x10, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado (resultado != 0)"
        assert regs.flag_n, "N debe estar activo (es resta)"
        assert not regs.flag_c, "C debe estar apagado (no hay borrow completo)"

    def test_sbc_a_b_with_full_borrow(self):
        """
        Test 10: Verificar SBC A, B con borrow completo (underflow).
        
        Resta con carry: A = 0x10 - B = 0x20 - C = 0 = 0xF0 (con borrow)
        - Resultado: A = 0xF0 (underflow)
        - Z: 0
        - N: 1
        - H: 1 (half-borrow: nibble bajo 0x0 < 0x0)
        - C: 1 (borrow completo) <- CRÍTICO
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0419: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        
        # Cargar A = 0x10
        mmu.write(0x0100, 0x3E)  # LD A, d8
        mmu.write(0x0101, 0x10)  # Operando: 0x10
        cpu.step()
        
        # Cargar B = 0x20
        mmu.write(0x0102, 0x06)  # LD B, d8
        mmu.write(0x0103, 0x20)  # Operando: 0x20
        cpu.step()
        
        # Desactivar flag C (sin borrow previo)
        regs.flag_c = False
        
        # SBC A, B (0x98)
        mmu.write(0x0104, 0x98)  # SBC A, B
        cpu.step()
        
        # Verificar resultado: 0x10 - 0x20 = 0xF0 (underflow)
        assert regs.a == 0xF0, f"A debe ser 0xF0, es 0x{regs.a:02X}"
        assert not regs.flag_z, "Z debe estar apagado"
        assert regs.flag_n, "N debe estar activo"
        assert regs.flag_c, "C debe estar ACTIVO (borrow completo detectado)"

