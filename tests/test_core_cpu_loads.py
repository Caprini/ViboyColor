"""
Tests de integración para Operaciones de Carga (Load) y Aritmética 16-bit en CPU nativa (C++).

Este módulo prueba las operaciones de transferencia de datos y aritmética de 16 bits:
- LD r, r' (bloque 0x40-0x7F): Carga entre registros
- LD r, n (inmediatas): Carga valor inmediato en registro
- LD (HL), r y LD r, (HL): Carga desde/hacia memoria
- LD rr, nn: Carga valor inmediato de 16 bits en par de registros
- INC/DEC rr: Incremento/decremento de pares de 16 bits (NO afecta flags)
- ADD HL, rr: Suma de 16 bits a HL (afecta flags H y C, NO Z)

Tests críticos:
- Verificar que LD r, r' copia valores correctamente
- Verificar que LD (HL), r escribe en memoria
- Verificar que LD r, (HL) lee de memoria
- Verificar que INC/DEC rr NO afecta flags
- Verificar que ADD HL, rr calcula Half-Carry y Carry correctamente
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestLD_8bit_Register:
    """Tests para LD r, r' (carga entre registros de 8 bits)"""

    def test_ld_b_a(self):
        """
        Test 1: Verificar LD B, A (0x47).
        
        - Establecer A = 0x10
        - Ejecutar LD B, A
        - Verificar que B = 0x10
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC
        regs.pc = 0x0100
        
        # Establecer A = 0x10
        regs.a = 0x10
        
        # Ejecutar LD B, A (0x47)
        mmu.write(0x0100, 0x47)
        cycles = cpu.step()
        
        # Verificar que B = 0x10
        assert regs.b == 0x10, f"B debe ser 0x10, es 0x{regs.b:02X}"
        assert cycles == 1, "LD B, A debe consumir 1 M-Cycle"
    
    def test_ld_c_d(self):
        """
        Test 2: Verificar LD C, D (0x4A).
        
        - Establecer D = 0x42
        - Ejecutar LD C, D
        - Verificar que C = 0x42
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.d = 0x42
        
        mmu.write(0x0100, 0x4A)  # LD C, D
        cycles = cpu.step()
        
        assert regs.c == 0x42, f"C debe ser 0x42, es 0x{regs.c:02X}"
        assert cycles == 1
    
    def test_ld_hl_mem_write(self):
        """
        Test 3: Verificar LD (HL), A (0x77) - escribir en memoria.
        
        - Establecer HL = 0xC000, A = 0x55
        - Ejecutar LD (HL), A
        - Verificar que memoria[0xC000] = 0x55
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0xC000
        regs.a = 0x55
        
        mmu.write(0x0100, 0x77)  # LD (HL), A
        cycles = cpu.step()
        
        # Verificar que se escribió en memoria
        assert mmu.read(0xC000) == 0x55, f"Memoria[0xC000] debe ser 0x55, es 0x{mmu.read(0xC000):02X}"
        assert cycles == 2, "LD (HL), A debe consumir 2 M-Cycles"
    
    def test_ld_hl_mem_read(self):
        """
        Test 4: Verificar LD A, (HL) (0x7E) - leer de memoria.
        
        - Establecer HL = 0xC000
        - Escribir 0xAA en memoria[0xC000]
        - Ejecutar LD A, (HL)
        - Verificar que A = 0xAA
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0xC000
        mmu.write(0xC000, 0xAA)
        
        mmu.write(0x0100, 0x7E)  # LD A, (HL)
        cycles = cpu.step()
        
        assert regs.a == 0xAA, f"A debe ser 0xAA, es 0x{regs.a:02X}"
        assert cycles == 2, "LD A, (HL) debe consumir 2 M-Cycles"
    
    def test_ld_block_matrix(self):
        """
        Test 5: Verificar múltiples combinaciones del bloque LD r, r' (0x40-0x7F).
        
        Prueba una muestra representativa del bloque completo.
        """
        test_cases = [
            (0x40, 'b', 'b'),  # LD B, B (no-op efectivo)
            (0x41, 'b', 'c'),  # LD B, C
            (0x50, 'd', 'b'),  # LD D, B
            (0x5F, 'e', 'a'),  # LD E, A
            (0x68, 'l', 'b'),  # LD L, B
            (0x7C, 'a', 'h'),  # LD A, H
        ]
        
        for opcode, dest_reg, src_reg in test_cases:
            mmu = PyMMU()
            mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
            regs = PyRegisters()
            cpu = PyCPU(mmu, regs)
            
            regs.pc = 0x0100
            
            # Establecer valor en registro origen
            src_value = 0x42
            setattr(regs, src_reg, src_value)
            
            # Ejecutar instrucción
            mmu.write(0x0100, opcode)
            cpu.step()
            
            # Verificar que destino tiene el valor correcto
            dest_value = getattr(regs, dest_reg)
            assert dest_value == src_value, (
                f"LD {dest_reg.upper()}, {src_reg.upper()} (0x{opcode:02X}): "
                f"destino debe ser 0x{src_value:02X}, es 0x{dest_value:02X}"
            )


class TestLD_8bit_Immediate:
    """Tests para LD r, n (carga inmediata de 8 bits)"""

    @pytest.mark.parametrize("opcode,register_name,test_value", [
        (0x06, 'b', 0x33),  # LD B, d8
        (0x0E, 'c', 0x42),  # LD C, d8
        (0x16, 'd', 0x55),  # LD D, d8
        (0x1E, 'e', 0x78),  # LD E, d8
        (0x26, 'h', 0x9A),  # LD H, d8
        (0x2E, 'l', 0xBC),  # LD L, d8
        (0x3E, 'a', 0xDE),  # LD A, d8
    ])
    def test_ld_register_immediate(self, opcode, register_name, test_value):
        """
        Test parametrizado: Verificar todas las instrucciones LD r, d8.
        
        Valida que cada instrucción:
        - Carga correctamente el valor inmediato en el registro
        - Consume 2 M-Cycles
        - Avanza PC en 2 bytes
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        mmu.write(0x0100, opcode)
        mmu.write(0x0101, test_value)
        
        cycles = cpu.step()
        
        # Verificar que el registro tiene el valor correcto
        register_value = getattr(regs, register_name)
        assert register_value == test_value, (
            f"LD {register_name.upper()}, d8 (0x{opcode:02X}): "
            f"registro debe ser 0x{test_value:02X}, es 0x{register_value:02X}"
        )
        assert cycles == 2, f"LD {register_name.upper()}, d8 debe consumir 2 M-Cycles"
        assert regs.pc == 0x0102, "PC debe avanzar 2 bytes después de LD r, d8"
    
    def test_ld_b_immediate(self):
        """
        Test 6: Verificar LD B, d8 (0x06) - Test legacy para compatibilidad.
        
        - Ejecutar LD B, 0x33
        - Verificar que B = 0x33
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        mmu.write(0x0100, 0x06)  # LD B, d8
        mmu.write(0x0101, 0x33)  # d8 = 0x33
        
        cycles = cpu.step()
        
        assert regs.b == 0x33, f"B debe ser 0x33, es 0x{regs.b:02X}"
        assert cycles == 2, "LD B, d8 debe consumir 2 M-Cycles"
        assert regs.pc == 0x0102, "PC debe avanzar 2 bytes"
    
    def test_ld_hl_immediate(self):
        """
        Test 7: Verificar LD (HL), d8 (0x36).
        
        - Establecer HL = 0xC000
        - Ejecutar LD (HL), 0xAA
        - Verificar que memoria[0xC000] = 0xAA
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0xC000
        
        mmu.write(0x0100, 0x36)  # LD (HL), d8
        mmu.write(0x0101, 0xAA)  # d8 = 0xAA
        
        cycles = cpu.step()
        
        assert mmu.read(0xC000) == 0xAA, f"Memoria[0xC000] debe ser 0xAA, es 0x{mmu.read(0xC000):02X}"
        assert cycles == 3, "LD (HL), d8 debe consumir 3 M-Cycles"


class TestLD_16bit:
    """Tests para LD rr, nn (carga inmediata de 16 bits)"""

    def test_ld_bc_immediate(self):
        """
        Test 8: Verificar LD BC, d16 (0x01).
        
        - Ejecutar LD BC, 0x1234
        - Verificar que BC = 0x1234 (B=0x12, C=0x34)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        mmu.write(0x0100, 0x01)  # LD BC, d16
        mmu.write(0x0101, 0x34)  # Low byte (Little-Endian)
        mmu.write(0x0102, 0x12)  # High byte
        
        cycles = cpu.step()
        
        assert regs.bc == 0x1234, f"BC debe ser 0x1234, es 0x{regs.bc:04X}"
        assert regs.b == 0x12, f"B debe ser 0x12, es 0x{regs.b:02X}"
        assert regs.c == 0x34, f"C debe ser 0x34, es 0x{regs.c:02X}"
        assert cycles == 3, "LD BC, d16 debe consumir 3 M-Cycles"
        assert regs.pc == 0x0103, "PC debe avanzar 3 bytes"
    
    def test_ld_hl_immediate(self):
        """
        Test 9: Verificar LD HL, d16 (0x21).
        
        - Ejecutar LD HL, 0xABCD
        - Verificar que HL = 0xABCD
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        mmu.write(0x0100, 0x21)  # LD HL, d16
        mmu.write(0x0101, 0xCD)  # Low byte
        mmu.write(0x0102, 0xAB)  # High byte
        
        cycles = cpu.step()
        
        assert regs.hl == 0xABCD, f"HL debe ser 0xABCD, es 0x{regs.hl:04X}"
        assert cycles == 3


class TestINC_DEC_16bit:
    """Tests para INC/DEC rr (incremento/decremento de 16 bits)"""

    def test_inc_bc(self):
        """
        Test 10: Verificar INC BC (0x03) - NO afecta flags.
        
        - Establecer BC = 0x0001, flags Z=1, H=1, C=1
        - Ejecutar INC BC
        - Verificar que BC = 0x0002
        - Verificar que flags NO cambiaron
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.bc = 0x0001
        regs.flag_z = True
        regs.flag_h = True
        regs.flag_c = True
        
        mmu.write(0x0100, 0x03)  # INC BC
        cycles = cpu.step()
        
        assert regs.bc == 0x0002, f"BC debe ser 0x0002, es 0x{regs.bc:04X}"
        assert regs.flag_z == True, "Flag Z NO debe cambiar (INC rr no afecta flags)"
        assert regs.flag_h == True, "Flag H NO debe cambiar"
        assert regs.flag_c == True, "Flag C NO debe cambiar"
        assert cycles == 2, "INC BC debe consumir 2 M-Cycles"
    
    def test_dec_hl(self):
        """
        Test 11: Verificar DEC HL (0x2B) - NO afecta flags.
        
        - Establecer HL = 0x0001
        - Ejecutar DEC HL
        - Verificar que HL = 0x0000
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0x0001
        
        mmu.write(0x0100, 0x2B)  # DEC HL
        cycles = cpu.step()
        
        assert regs.hl == 0x0000, f"HL debe ser 0x0000, es 0x{regs.hl:04X}"
        assert cycles == 2
    
    def test_inc_sp_wraparound(self):
        """
        Test 12: Verificar que INC SP (0x33) hace wrap-around en 16 bits.
        
        - Establecer SP = 0xFFFF
        - Ejecutar INC SP
        - Verificar que SP = 0x0000
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.sp = 0xFFFF
        
        mmu.write(0x0100, 0x33)  # INC SP
        cpu.step()
        
        assert regs.sp == 0x0000, f"SP debe hacer wrap-around a 0x0000, es 0x{regs.sp:04X}"


class TestADD_HL:
    """Tests para ADD HL, rr (suma de 16 bits a HL)"""

    def test_add_hl_bc_no_carry(self):
        """
        Test 13: Verificar ADD HL, BC (0x09) sin carry.
        
        - Establecer HL = 0x0001, BC = 0x0002
        - Ejecutar ADD HL, BC
        - Verificar que HL = 0x0003
        - Verificar flags: N=0, H=0, C=0 (Z no afectado)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0x0001
        regs.bc = 0x0002
        regs.flag_z = True  # Z debe mantenerse
        
        mmu.write(0x0100, 0x09)  # ADD HL, BC
        cycles = cpu.step()
        
        assert regs.hl == 0x0003, f"HL debe ser 0x0003, es 0x{regs.hl:04X}"
        assert regs.flag_n == False, "Flag N debe ser 0 (es suma)"
        assert regs.flag_h == False, "Flag H debe ser 0 (no hay half-carry)"
        assert regs.flag_c == False, "Flag C debe ser 0 (no hay carry)"
        assert regs.flag_z == True, "Flag Z NO debe cambiar (mantiene valor anterior)"
        assert cycles == 2, "ADD HL, BC debe consumir 2 M-Cycles"
    
    def test_add_hl_de_half_carry(self):
        """
        Test 14: Verificar ADD HL, DE (0x19) con half-carry.
        
        Half-carry ocurre cuando hay carry en el bit 11 (bit 3 del byte alto).
        
        - Establecer HL = 0x0FFF, DE = 0x0001
        - Ejecutar ADD HL, DE
        - Verificar que HL = 0x1000
        - Verificar flags: H=1 (half-carry en bit 11), C=0
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0x0FFF
        regs.de = 0x0001
        
        mmu.write(0x0100, 0x19)  # ADD HL, DE
        cpu.step()
        
        assert regs.hl == 0x1000, f"HL debe ser 0x1000, es 0x{regs.hl:04X}"
        assert regs.flag_h == True, "Flag H debe ser 1 (half-carry en bit 11)"
        assert regs.flag_c == False, "Flag C debe ser 0 (no hay carry completo)"
    
    def test_add_hl_hl_full_carry(self):
        """
        Test 15: Verificar ADD HL, HL (0x29) con carry completo.
        
        - Establecer HL = 0x8000
        - Ejecutar ADD HL, HL (equivale a HL * 2)
        - Verificar que HL = 0x0000 (wrap-around)
        - Verificar flags: H=0, C=1 (carry completo)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0x8000
        
        mmu.write(0x0100, 0x29)  # ADD HL, HL
        cpu.step()
        
        assert regs.hl == 0x0000, f"HL debe ser 0x0000 (wrap-around), es 0x{regs.hl:04X}"
        assert regs.flag_c == True, "Flag C debe ser 1 (carry completo en 16 bits)"
    
    def test_add_hl_sp_both_carries(self):
        """
        Test 16: Verificar ADD HL, SP (0x39) con half-carry y carry completo.
        
        - Establecer HL = 0xFFF0, SP = 0x0010
        - Ejecutar ADD HL, SP
        - Verificar que HL = 0x0000 (wrap-around)
        - Verificar flags: H=1, C=1
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x0100
        regs.hl = 0xFFF0
        regs.sp = 0x0010
        
        mmu.write(0x0100, 0x39)  # ADD HL, SP
        cpu.step()
        
        assert regs.hl == 0x0000, f"HL debe ser 0x0000, es 0x{regs.hl:04X}"
        assert regs.flag_h == True, "Flag H debe ser 1 (half-carry)"
        assert regs.flag_c == True, "Flag C debe ser 1 (carry completo)"


class TestMemoryClearLoop:
    """Tests para validar el escenario de bucle de limpieza de memoria que requiere cargas inmediatas"""
    
    def test_memory_clear_loop_scenario(self):
        """
        Test: Simula el escenario de bucle de limpieza de memoria que se ejecuta al arrancar ROMs.
        
        Este test valida que las instrucciones de carga inmediata (LD B, d8, LD C, d8, LD HL, d16)
        funcionan correctamente para inicializar los registros necesarios para bucles de limpieza.
        
        Secuencia simulada:
        1. XOR A (poner A=0)
        2. LD HL, d16 (inicializar puntero de memoria)
        3. LD C, d8 (inicializar contador bajo)
        4. LD B, d8 (inicializar contador alto)
        5. LDD (HL), A (escribir cero y decrementar HL)
        6. DEC B (decrementar contador)
        7. JR NZ (saltar si B != 0)
        
        Este es el patrón que usa Tetris al arrancar para limpiar memoria.
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC
        regs.pc = 0x0100
        
        # Paso 1: XOR A (poner A=0)
        mmu.write(0x0100, 0xAF)  # XOR A
        cycles = cpu.step()
        assert regs.a == 0, "A debe ser 0 después de XOR A"
        assert regs.pc == 0x0101
        
        # Paso 2: LD HL, 0xC000 (inicializar puntero de memoria)
        mmu.write(0x0101, 0x21)  # LD HL, d16
        mmu.write(0x0102, 0x00)  # LSB
        mmu.write(0x0103, 0xC0)  # MSB
        cycles = cpu.step()
        assert regs.hl == 0xC000, f"HL debe ser 0xC000, es 0x{regs.hl:04X}"
        assert regs.pc == 0x0104
        
        # Paso 3: LD C, 0x10 (contador bajo)
        mmu.write(0x0104, 0x0E)  # LD C, d8
        mmu.write(0x0105, 0x10)  # d8 = 0x10
        cycles = cpu.step()
        assert regs.c == 0x10, f"C debe ser 0x10, es 0x{regs.c:02X}"
        assert regs.pc == 0x0106
        
        # Paso 4: LD B, 0x02 (contador alto - bucle se ejecutará 0x02 veces)
        mmu.write(0x0106, 0x06)  # LD B, d8
        mmu.write(0x0107, 0x02)  # d8 = 0x02
        cycles = cpu.step()
        assert regs.b == 0x02, f"B debe ser 0x02, es 0x{regs.b:02X}"
        assert regs.pc == 0x0108
        assert regs.bc == 0x0210, f"BC debe ser 0x0210, es 0x{regs.bc:04X}"
        
        # Paso 5-7: Ejecutar una iteración del bucle de limpieza
        # LDD (HL), A - escribir cero en memoria y decrementar HL
        mmu.write(0x0108, 0x32)  # LDD (HL), A
        cycles = cpu.step()
        assert mmu.read(0xC000) == 0, "Memoria[0xC000] debe ser 0"
        assert regs.hl == 0xBFFF, f"HL debe decrementarse a 0xBFFF, es 0x{regs.hl:04X}"
        assert regs.pc == 0x0109
        
        # DEC B - decrementar contador
        mmu.write(0x0109, 0x05)  # DEC B
        cycles = cpu.step()
        assert regs.b == 0x01, f"B debe ser 0x01 después de DEC B, es 0x{regs.b:02X}"
        assert regs.pc == 0x010A
        
        # Verificar que las instrucciones de carga inmediata inicializaron correctamente
        # los registros para el bucle
        assert regs.bc == 0x0110, f"BC debe ser 0x0110 después de una iteración, es 0x{regs.bc:04X}"
        assert regs.hl == 0xBFFF, f"HL debe apuntar a la siguiente dirección (0xBFFF), es 0x{regs.hl:04X}"