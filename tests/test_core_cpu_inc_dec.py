"""
Tests unitarios para instrucciones INC/DEC de 8 bits en CPU nativa (C++).

Este módulo prueba las operaciones de incremento y decremento implementadas
en la CPU nativa (C++), verificando:
- Operaciones básicas: INC r, DEC r
- Gestión de flags: Z, N, H
- Preservación del flag C (QUIRK crítico del hardware)
- Half-Carry/Half-Borrow: Detección correcta de desbordamiento de nibble bajo

Tests críticos:
- DEC B (0x05): El opcode que causaba el crash en bucles de inicialización
- Preservación de C: INC/DEC NO deben modificar el flag Carry
- Half-Carry: INC que cause desbordamiento de nibble bajo (0x0F -> 0x10)
- Half-Borrow: DEC que cause underflow de nibble bajo (0x10 -> 0x0F)
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestCoreCPUIncDec:
    """Tests para INC/DEC nativo (C++)"""

    def test_dec_b_preserves_carry(self):
        """
        Test 1: Verificar que DEC B (0x05) preserva el flag Carry.
        
        Este es el opcode que causaba el crash en los bucles de inicialización.
        El juego ejecutaba DEC B y esperaba que el flag Z se actualizara, pero
        el flag C debía preservarse.
        
        Escenario:
        - B = 0x01, C = 1 (flag Carry activo)
        - Ejecutar DEC B
        - Resultado: B = 0x00, Z = 1, C = 1 (preservado)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Establecer PC inicial
        regs.pc = 0x8000
        
        # Cargar B = 0x01
        mmu.write(0x8000, 0x06)  # LD B, d8
        mmu.write(0x8001, 0x01)  # Operando: 0x01
        cpu.step()
        
        # Activar flag Carry
        regs.flag_c = True
        assert regs.flag_c == True, "Flag C debe estar activo"
        
        # Ejecutar DEC B (0x05)
        mmu.write(0x8002, 0x05)  # DEC B
        cpu.step()
        
        # Verificar resultado
        assert regs.b == 0x00, f"B debe ser 0x00, es 0x{regs.b:02X}"
        assert regs.flag_z == True, "Z debe estar activo (resultado == 0)"
        assert regs.flag_n == True, "N debe estar activo (es decremento)"
        assert regs.flag_c == True, "C debe haberse preservado como True (QUIRK del hardware)"
        
        # Segundo test: DEC B con Carry=0
        regs.pc = 0x8000
        mmu.write(0x8000, 0x06)  # LD B, d8
        mmu.write(0x8001, 0x10)  # Operando: 0x10
        cpu.step()
        
        # Desactivar flag Carry
        regs.flag_c = False
        assert regs.flag_c == False, "Flag C debe estar desactivado"
        
        # Ejecutar DEC B (0x05)
        mmu.write(0x8002, 0x05)  # DEC B
        cpu.step()
        
        # Verificar resultado
        assert regs.b == 0x0F, f"B debe ser 0x0F, es 0x{regs.b:02X}"
        assert regs.flag_z == False, "Z debe estar desactivado (resultado != 0)"
        assert regs.flag_n == True, "N debe estar activo (es decremento)"
        assert regs.flag_h == True, "H debe estar activo (half-borrow: 0x10 -> 0x0F)"
        assert regs.flag_c == False, "C debe haberse preservado como False (QUIRK del hardware)"

    def test_inc_a_preserves_carry(self):
        """
        Test 2: Verificar que INC A preserva el flag Carry.
        
        Escenario:
        - A = 0xFF, C = 1 (flag Carry activo)
        - Ejecutar INC A
        - Resultado: A = 0x00, Z = 1, C = 1 (preservado)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        
        # Cargar A = 0xFF
        mmu.write(0x8000, 0x3E)  # LD A, d8
        mmu.write(0x8001, 0xFF)  # Operando: 0xFF
        cpu.step()
        
        # Activar flag Carry
        regs.flag_c = True
        
        # Ejecutar INC A (0x3C)
        mmu.write(0x8002, 0x3C)  # INC A
        cpu.step()
        
        # Verificar resultado
        assert regs.a == 0x00, f"A debe ser 0x00, es 0x{regs.a:02X}"
        assert regs.flag_z == True, "Z debe estar activo (resultado == 0)"
        assert regs.flag_n == False, "N debe estar desactivado (es incremento)"
        assert regs.flag_h == True, "H debe estar activo (half-carry: 0x0F -> 0x10 en nibble bajo)"
        assert regs.flag_c == True, "C debe haberse preservado como True (QUIRK del hardware)"

    def test_inc_half_carry(self):
        """
        Test 3: Verificar detección de half-carry en INC.
        
        Escenario:
        - B = 0x0F (nibble bajo al máximo)
        - Ejecutar INC B
        - Resultado: B = 0x10, H = 1 (half-carry detectado)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        
        # Cargar B = 0x0F
        mmu.write(0x8000, 0x06)  # LD B, d8
        mmu.write(0x8001, 0x0F)  # Operando: 0x0F
        cpu.step()
        
        # Ejecutar INC B (0x04)
        mmu.write(0x8002, 0x04)  # INC B
        cpu.step()
        
        # Verificar resultado
        assert regs.b == 0x10, f"B debe ser 0x10, es 0x{regs.b:02X}"
        assert regs.flag_z == False, "Z debe estar desactivado (resultado != 0)"
        assert regs.flag_n == False, "N debe estar desactivado (es incremento)"
        assert regs.flag_h == True, "H debe estar activo (half-carry: 0x0F -> 0x10)"

    def test_dec_half_borrow(self):
        """
        Test 4: Verificar detección de half-borrow en DEC.
        
        Escenario:
        - C = 0x10 (nibble bajo en 0x00)
        - Ejecutar DEC C
        - Resultado: C = 0x0F, H = 1 (half-borrow detectado)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        
        # Cargar C = 0x10
        mmu.write(0x8000, 0x0E)  # LD C, d8
        mmu.write(0x8001, 0x10)  # Operando: 0x10
        cpu.step()
        
        # Ejecutar DEC C (0x0D)
        mmu.write(0x8002, 0x0D)  # DEC C
        cpu.step()
        
        # Verificar resultado
        assert regs.c == 0x0F, f"C debe ser 0x0F, es 0x{regs.c:02X}"
        assert regs.flag_z == False, "Z debe estar desactivado (resultado != 0)"
        assert regs.flag_n == True, "N debe estar activo (es decremento)"
        assert regs.flag_h == True, "H debe estar activo (half-borrow: 0x10 -> 0x0F)"

    def test_inc_all_registers(self):
        """
        Test 5: Verificar que todos los opcodes INC funcionan correctamente.
        
        Opcodes:
        - 0x04: INC B
        - 0x0C: INC C
        - 0x14: INC D
        - 0x1C: INC E
        - 0x24: INC H
        - 0x2C: INC L
        - 0x3C: INC A
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Test INC B (0x04)
        regs.pc = 0x8000
        regs.b = 0x05
        mmu.write(0x8000, 0x04)  # INC B
        cpu.step()
        assert regs.b == 0x06, "INC B debe incrementar B"
        
        # Test INC C (0x0C)
        regs.pc = 0x8000
        regs.c = 0x0A
        mmu.write(0x8000, 0x0C)  # INC C
        cpu.step()
        assert regs.c == 0x0B, "INC C debe incrementar C"
        
        # Test INC D (0x14)
        regs.pc = 0x8000
        regs.d = 0xFF
        mmu.write(0x8000, 0x14)  # INC D
        cpu.step()
        assert regs.d == 0x00, "INC D debe hacer wrap-around (0xFF -> 0x00)"
        assert regs.flag_z == True, "Z debe estar activo después de wrap-around"
        
        # Test INC E (0x1C)
        regs.pc = 0x8000
        regs.e = 0x42
        mmu.write(0x8000, 0x1C)  # INC E
        cpu.step()
        assert regs.e == 0x43, "INC E debe incrementar E"
        
        # Test INC H (0x24)
        regs.pc = 0x8000
        regs.h = 0x7F
        mmu.write(0x8000, 0x24)  # INC H
        cpu.step()
        assert regs.h == 0x80, "INC H debe incrementar H"
        
        # Test INC L (0x2C)
        regs.pc = 0x8000
        regs.l = 0x99
        mmu.write(0x8000, 0x2C)  # INC L
        cpu.step()
        assert regs.l == 0x9A, "INC L debe incrementar L"
        
        # Test INC A (0x3C)
        regs.pc = 0x8000
        regs.a = 0x01
        mmu.write(0x8000, 0x3C)  # INC A
        cpu.step()
        assert regs.a == 0x02, "INC A debe incrementar A"

    def test_dec_all_registers(self):
        """
        Test 6: Verificar que todos los opcodes DEC funcionan correctamente.
        
        Opcodes:
        - 0x05: DEC B
        - 0x0D: DEC C
        - 0x15: DEC D
        - 0x1D: DEC E
        - 0x25: DEC H
        - 0x2D: DEC L
        - 0x3D: DEC A
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Test DEC B (0x05) - El opcode crítico
        regs.pc = 0x8000
        regs.b = 0x05
        mmu.write(0x8000, 0x05)  # DEC B
        cpu.step()
        assert regs.b == 0x04, "DEC B debe decrementar B"
        
        # Test DEC C (0x0D)
        regs.pc = 0x8000
        regs.c = 0x01
        mmu.write(0x8000, 0x0D)  # DEC C
        cpu.step()
        assert regs.c == 0x00, "DEC C debe hacer wrap-around (0x01 -> 0x00)"
        assert regs.flag_z == True, "Z debe estar activo después de llegar a 0"
        
        # Test DEC D (0x15)
        regs.pc = 0x8000
        regs.d = 0x00
        mmu.write(0x8000, 0x15)  # DEC D
        cpu.step()
        assert regs.d == 0xFF, "DEC D debe hacer wrap-around (0x00 -> 0xFF)"
        
        # Test DEC E (0x1D)
        regs.pc = 0x8000
        regs.e = 0x42
        mmu.write(0x8000, 0x1D)  # DEC E
        cpu.step()
        assert regs.e == 0x41, "DEC E debe decrementar E"
        
        # Test DEC H (0x25)
        regs.pc = 0x8000
        regs.h = 0x80
        mmu.write(0x8000, 0x25)  # DEC H
        cpu.step()
        assert regs.h == 0x7F, "DEC H debe decrementar H"
        
        # Test DEC L (0x2D)
        regs.pc = 0x8000
        regs.l = 0x01
        mmu.write(0x8000, 0x2D)  # DEC L
        cpu.step()
        assert regs.l == 0x00, "DEC L debe hacer wrap-around (0x01 -> 0x00)"
        
        # Test DEC A (0x3D)
        regs.pc = 0x8000
        regs.a = 0x01
        mmu.write(0x8000, 0x3D)  # DEC A
        cpu.step()
        assert regs.a == 0x00, "DEC A debe hacer wrap-around (0x01 -> 0x00)"
        assert regs.flag_z == True, "Z debe estar activo después de llegar a 0"

    def test_dec_b_sets_zero_flag(self):
        """
        Test 7: Verificar que DEC B activa el flag Z cuando el resultado es 0.
        
        Este es el test crítico que valida el fix del Step 0152.
        El bucle infinito en las ROMs se debía a que DEC B no activaba el flag Z
        cuando B pasaba de 1 a 0, causando que JR NZ siempre saltara.
        
        Escenario:
        - B = 1, flag Z = 0 (desactivado)
        - Ejecutar DEC B (0x05)
        - Resultado esperado: B = 0, flag Z = 1 (activado)
        - Esto permite que JR NZ no salte y el bucle termine
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar B=1 y el flag Z=0
        regs.pc = 0x0100
        regs.b = 1
        regs.set_flag_z(False)  # Asegurar que Z está desactivado
        
        # Verificar estado inicial
        assert regs.b == 1, "B debe ser 1 inicialmente"
        assert regs.get_flag_z() == False, "Flag Z debe estar desactivado inicialmente"
        
        # Ejecutar DEC B (opcode 0x05)
        mmu.write(0x0100, 0x05)  # Opcode DEC B
        cpu.step()
        
        # Verificar resultado: B debe ser 0 y Z debe estar activo
        assert regs.b == 0, f"B debe ser 0 después de DEC, es {regs.b}"
        assert regs.get_flag_z() == True, "Flag Z debe estar activo cuando resultado es 0 (¡COMPROBACIÓN CLAVE!)"
        assert regs.flag_n == True, "Flag N debe estar activo (es decremento)"
        assert regs.pc == 0x0101, "PC debe avanzar 1 byte después de DEC B"

