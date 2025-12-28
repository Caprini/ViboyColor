"""
Tests de integración para instrucciones CB (Prefijo Extendido) en CPU nativa (C++).

Este módulo prueba las instrucciones extendidas del prefijo CB:
- Rotaciones y Shifts (RLC, RRC, RL, RR, SLA, SRA, SWAP, SRL)
- BIT (Test bit)
- RES (Reset bit)
- SET (Set bit)

Valida:
- Decodificación correcta del opcode CB
- Operaciones bitwise nativas en C++
- Timing correcto (2 M-Cycles para registros, 4 para (HL))
- Flags correctos según Pan Docs
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestCBBit:
    """Tests para la instrucción BIT (Test bit)"""
    
    def test_cb_bit_7_h_set(self):
        """
        Test: BIT 7, H cuando el bit 7 de H está encendido (H = 0x80).
        
        - H = 0x80 (bit 7 = 1)
        - Ejecuta 0xCB 0x7C (BIT 7, H)
        - Verifica Z=0 (bit está encendido, Z=0 significa "no es cero")
        - Verifica H=1 (siempre se activa en BIT)
        - Verifica N=0 (siempre se desactiva en BIT)
        - Verifica que C no cambia
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.h = 0x80  # Bit 7 encendido
        regs.f = 0x10  # C inicialmente activado (FLAG_C = 0x10)
        regs.pc = 0x8000
        
        # Escribir prefijo CB y opcode en memoria
        mmu.write(0x8000, 0xCB)  # Prefijo CB
        mmu.write(0x8001, 0x7C)  # BIT 7, H
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar flags
        assert not regs.flag_z, "Z debe ser 0 (bit está encendido)"
        assert regs.flag_h, "H debe ser 1 (siempre activado en BIT)"
        assert not regs.flag_n, "N debe ser 0 (siempre desactivado en BIT)"
        assert regs.flag_c, "C no debe cambiar (debe seguir activado)"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_cb_bit_7_h_clear(self):
        """
        Test: BIT 7, H cuando el bit 7 de H está apagado (H = 0x00).
        
        - H = 0x00 (bit 7 = 0)
        - Ejecuta 0xCB 0x7C (BIT 7, H)
        - Verifica Z=1 (bit está apagado)
        - Verifica H=1 (siempre se activa en BIT)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.h = 0x00  # Bit 7 apagado
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x7C)  # BIT 7, H
        
        cpu.step()
        
        assert regs.flag_z, "Z debe ser 1 (bit está apagado)"
        assert regs.flag_h, "H debe ser 1 (siempre en BIT)"
    
    def test_cb_bit_preserves_carry(self):
        """
        Test: BIT preserva el flag C (no lo modifica).
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        
        # Probar con C activado
        regs.b = 0x01
        regs.f = 0x10  # C activado
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x40)  # BIT 0, B
        
        cpu.step()
        
        assert regs.flag_c, "C debe preservarse (seguir activado)"
        
        # Probar con C desactivado
        regs.b = 0x00
        regs.f = 0x00  # C desactivado
        regs.pc = 0x8000
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x40)  # BIT 0, B
        
        cpu.step()
        
        assert not regs.flag_c, "C debe preservarse (seguir desactivado)"


class TestCBRot:
    """Tests para rotaciones CB (RL, RR, RLC, RRC)"""
    
    def test_cb_rl_c(self):
        """
        Test: RL C (Rotate Left through Carry).
        
        - C = 0x80, C flag = 0
        - Ejecuta 0xCB 0x11 (RL C)
        - Verifica que C = 0x00 (bit 7 va a C, bit 0 entra 0)
        - Verifica C flag = 1 (bit 7 original era 1)
        - Verifica Z=1 (resultado es cero)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.c = 0x80
        regs.f = 0x00  # C flag = 0
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x11)  # RL C
        
        cycles = cpu.step()
        
        assert regs.c == 0x00, "C debe ser 0x00 después de RL"
        assert regs.flag_c, "C flag debe ser 1 (bit 7 original era 1)"
        assert regs.flag_z, "Z debe ser 1 (resultado es cero)"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_cb_rl_with_carry(self):
        """
        Test: RL C con carry previo.
        
        - C = 0x80, C flag = 1
        - Ejecuta 0xCB 0x11 (RL C)
        - Verifica que C = 0x01 (bit 7 va a C, antiguo C entra en bit 0)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.c = 0x80
        regs.f = 0x10  # C flag = 1
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x11)  # RL C
        
        cpu.step()
        
        assert regs.c == 0x01, "C debe ser 0x01 (antiguo C entra en bit 0)"
        assert regs.flag_c, "C flag debe ser 1 (bit 7 original era 1)"


class TestCBHL:
    """Tests para operaciones CB con direccionamiento indirecto (HL)"""
    
    def test_cb_set_3_hl(self):
        """
        Test: SET 3, (HL) - Escribe en memoria, modifica, verifica el cambio.
        
        - HL = 0xC000
        - Memoria[0xC000] = 0x00
        - Ejecuta 0xCB 0xDE (SET 3, (HL))
        - Verifica que Memoria[0xC000] = 0x08 (bit 3 encendido)
        - Verifica que consume 4 M-Cycles (acceso a memoria)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Configurar estado inicial
        regs.hl = 0xC000
        mmu.write(0xC000, 0x00)  # Todos los bits apagados
        regs.pc = 0x8000
        
        # Escribir prefijo CB y opcode
        mmu.write(0x8000, 0xCB)  # Prefijo CB
        mmu.write(0x8001, 0xDE)  # SET 3, (HL)
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificar resultado
        assert mmu.read(0xC000) == 0x08, "(HL) debe ser 0x08 (bit 3 encendido)"
        assert cycles == 4, "Debe consumir 4 M-Cycles (acceso a memoria)"
    
    def test_cb_res_0_hl(self):
        """
        Test: RES 0, (HL) - Apaga bit 0 en memoria.
        
        - HL = 0xC000
        - Memoria[0xC000] = 0xFF (todos los bits encendidos)
        - Ejecuta 0xCB 0x86 (RES 0, (HL))
        - Verifica que Memoria[0xC000] = 0xFE (bit 0 apagado)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.hl = 0xC000
        mmu.write(0xC000, 0xFF)  # Todos los bits encendidos
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x86)  # RES 0, (HL)
        
        cycles = cpu.step()
        
        assert mmu.read(0xC000) == 0xFE, "(HL) debe ser 0xFE (bit 0 apagado)"
        assert cycles == 4, "Debe consumir 4 M-Cycles"


class TestCBSwap:
    """Tests para la instrucción SWAP"""
    
    def test_cb_swap_a(self):
        """
        Test: SWAP A (0xF0 -> 0x0F).
        
        - A = 0xF0 (11110000)
        - Ejecuta 0xCB 0x37 (SWAP A)
        - Verifica que A = 0x0F (00001111)
        - Verifica Z=0 (resultado no es cero)
        - Verifica N=0, H=0, C=0
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.a = 0xF0
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x37)  # SWAP A
        
        cycles = cpu.step()
        
        assert regs.a == 0x0F, "A debe ser 0x0F después de SWAP"
        assert not regs.flag_z, "Z debe ser 0 (resultado no es cero)"
        assert not regs.flag_n, "N debe ser 0"
        assert not regs.flag_h, "H debe ser 0"
        assert not regs.flag_c, "C debe ser 0"
        assert cycles == 2, "Debe consumir 2 M-Cycles"
    
    def test_cb_swap_zero_result(self):
        """
        Test: SWAP con resultado cero activa flag Z.
        
        - A = 0x00
        - Ejecuta 0xCB 0x37 (SWAP A)
        - Verifica que A = 0x00
        - Verifica Z=1 (resultado es cero)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.a = 0x00
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x37)  # SWAP A
        
        cpu.step()
        
        assert regs.a == 0x00
        assert regs.flag_z, "Z debe ser 1 (resultado es cero)"


class TestCBRLC:
    """Tests para verificar la diferencia crítica de flags Z entre rotaciones rápidas y CB"""
    
    def test_cb_rlc_z_flag(self):
        """
        Test: CB RLC calcula Z según el resultado (DIFERENCIA con RLCA).
        
        - B = 0x00
        - Ejecuta 0xCB 0x00 (RLC B)
        - Verifica que B = 0x00 (rotar 0 sigue siendo 0)
        - Verifica Z=1 (resultado es cero) <- DIFERENCIA: RLCA siempre pone Z=0
        - Verifica C=0 (bit 7 original era 0)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.b = 0x00
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x00)  # RLC B
        
        cycles = cpu.step()
        
        assert regs.b == 0x00, "B debe seguir siendo 0x00"
        assert regs.flag_z, "Z debe ser 1 (resultado es cero) - DIFERENCIA con RLCA"
        assert not regs.flag_c, "C debe ser 0 (bit 7 original era 0)"
        assert cycles == 2
    
    def test_cb_rlc_nonzero_result(self):
        """
        Test: CB RLC con resultado no cero pone Z=0.
        
        - B = 0x80
        - Ejecuta 0xCB 0x00 (RLC B)
        - Verifica que B = 0x01
        - Verifica Z=0 (resultado no es cero)
        - Verifica C=1 (bit 7 original era 1)
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.b = 0x80
        regs.pc = 0x8000
        
        mmu.write(0x8000, 0xCB)
        mmu.write(0x8001, 0x00)  # RLC B
        
        cpu.step()
        
        assert regs.b == 0x01, "B debe ser 0x01 después de RLC"
        assert not regs.flag_z, "Z debe ser 0 (resultado no es cero)"
        assert regs.flag_c, "C debe ser 1 (bit 7 original era 1)"

