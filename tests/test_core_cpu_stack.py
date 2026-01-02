"""
Tests de integración para operaciones de Stack (Pila) en CPU nativa (C++).

Este módulo prueba las operaciones de pila implementadas en C++:
- PUSH BC (0xC5): Empuja BC en la pila
- POP BC (0xC1): Saca valor de la pila a BC
- CALL nn (0xCD): Llama a subrutina guardando dirección de retorno
- RET (0xC9): Retorna de subrutina recuperando dirección de retorno

Tests críticos:
- Verificar que la pila crece hacia abajo (SP decrece en PUSH)
- Verificar orden correcto de bytes (Little-Endian) en PUSH/POP
- Verificar que CALL guarda la dirección correcta de retorno
- Verificar que RET restaura el PC correctamente
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestPushPop:
    """Tests para PUSH BC y POP BC"""

    def test_push_pop_bc(self):
        """
        Test 1: Verificar PUSH BC y POP BC básico.
        
        - Establecer SP en 0xFFFE (típico valor inicial en Game Boy)
        - Establecer BC en 0x1234
        - Ejecutar PUSH BC
        - Verificar que memoria en 0xFFFD y 0xFFFC tiene los datos correctos
        - Verificar que SP decrementó a 0xFFFC
        - Ejecutar POP BC
        - Verificar que BC es 0x1234
        - Verificar que SP volvió a 0xFFFE
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP (típico valor inicial en Game Boy)
        regs.sp = 0xFFFE
        
        # Establecer BC
        regs.b = 0x12
        regs.c = 0x34
        
        # Ejecutar PUSH BC
        regs.pc = 0x0100
        mmu.write(0x0100, 0xC5)  # Opcode PUSH BC
        cycles = cpu.step()
        
        # Verificar que SP decrementó (pila crece hacia abajo)
        assert regs.sp == 0xFFFC, (
            f"SP debe ser 0xFFFC después de PUSH, es 0x{regs.sp:04X}"
        )
        
        # Verificar que los datos están en memoria en orden Little-Endian
        # PUSH escribe primero high byte, luego low byte
        # Así que en memoria: [0xFFFD] = 0x12 (high), [0xFFFC] = 0x34 (low)
        assert mmu.read(0xFFFD) == 0x12, "Byte alto debe estar en 0xFFFD"
        assert mmu.read(0xFFFC) == 0x34, "Byte bajo debe estar en 0xFFFC"
        
        assert cycles == 4, f"PUSH BC debe consumir 4 M-Cycles, consumió {cycles}"
        
        # Ahora ejecutar POP BC
        regs.pc = 0x0101
        mmu.write(0x0101, 0xC1)  # Opcode POP BC
        # Limpiar BC para verificar que POP lo restaura
        regs.b = 0x00
        regs.c = 0x00
        cycles = cpu.step()
        
        # Verificar que BC se restauró correctamente
        assert regs.b == 0x12, "B debe ser 0x12 después de POP"
        assert regs.c == 0x34, "C debe ser 0x34 después de POP"
        
        # Verificar que SP volvió a su valor original
        assert regs.sp == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de POP, es 0x{regs.sp:04X}"
        )
        
        assert cycles == 3, f"POP BC debe consumir 3 M-Cycles, consumió {cycles}"

    def test_stack_grows_downwards(self):
        """
        Test 2: Verificar que la pila crece hacia abajo (SP decrece en PUSH).
        
        Este es el test CRÍTICO: verifica que la pila funciona correctamente.
        Si la pila creciera hacia arriba, los juegos se corromperían.
        
        - SP inicial en 0xFFFE
        - PUSH BC
        - Verificar que SP < valor inicial
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        initial_sp = 0xFFFE
        regs.sp = initial_sp
        regs.b = 0xAA
        regs.c = 0xBB
        
        regs.pc = 0x0100
        mmu.write(0x0100, 0xC5)  # PUSH BC
        cpu.step()
        
        # Verificar que SP decrementó
        assert regs.sp < initial_sp, (
            f"SP debe decrementar en PUSH. Inicial: 0x{initial_sp:04X}, "
            f"Después: 0x{regs.sp:04X}"
        )
        assert regs.sp == 0xFFFC, "SP debe ser 0xFFFC después de PUSH"


class TestCallRet:
    """Tests para CALL nn y RET"""

    def test_call_ret_basic(self):
        """
        Test 3: Verificar CALL nn y RET básico.
        
        - Establecer SP en 0xFFFE
        - Establecer PC en 0x0100
        - Ejecutar CALL 0x2000
        - Verificar que PC = 0x2000
        - Verificar que SP = 0xFFFC (decrementó 2 bytes)
        - Verificar que la dirección de retorno (0x0103) está en la pila
        - Ejecutar RET
        - Verificar que PC vuelve a 0x0103
        - Verificar que SP vuelve a 0xFFFE
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP y PC
        regs.sp = 0xFFFE
        regs.pc = 0x0100
        
        # Escribir CALL 0x2000 (0xCD 0x00 0x20)
        mmu.write(0x0100, 0xCD)  # Opcode CALL nn
        mmu.write(0x0101, 0x00)  # LSB de dirección (Little-Endian)
        mmu.write(0x0102, 0x20)  # MSB de dirección
        
        # Ejecutar CALL
        cycles = cpu.step()
        
        # Verificar que PC saltó a la dirección destino
        assert regs.pc == 0x2000, (
            f"PC debe ser 0x2000 después de CALL, es 0x{regs.pc:04X}"
        )
        
        # Verificar que SP decrementó (pila crece hacia abajo)
        assert regs.sp == 0xFFFC, (
            f"SP debe ser 0xFFFC después de CALL (decrementó 2 bytes), "
            f"es 0x{regs.sp:04X}"
        )
        
        # Verificar que la dirección de retorno está en la pila
        # La dirección de retorno es 0x0103 (PC después de leer toda la instrucción)
        # PUSH escribe high byte en SP+1, low byte en SP
        # POP lee low byte de SP, high byte de SP+1
        low_byte = mmu.read(0xFFFC)
        high_byte = mmu.read(0xFFFD)
        return_addr = (high_byte << 8) | low_byte
        assert return_addr == 0x0103, (
            f"Dirección de retorno debe ser 0x0103, es 0x{return_addr:04X}. "
            "Esta es la dirección de la siguiente instrucción tras el CALL."
        )
        
        assert cycles == 6, f"CALL nn debe consumir 6 M-Cycles, consumió {cycles}"
        
        # Ahora ejecutar RET
        regs.pc = 0x2000
        mmu.write(0x2000, 0xC9)  # Opcode RET
        cycles = cpu.step()
        
        # Verificar que PC volvió a la dirección de retorno
        assert regs.pc == 0x0103, (
            f"PC debe ser 0x0103 después de RET, es 0x{regs.pc:04X}"
        )
        
        # Verificar que SP volvió a su valor original
        assert regs.sp == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de RET, es 0x{regs.sp:04X}"
        )
        
        assert cycles == 4, f"RET debe consumir 4 M-Cycles, consumió {cycles}"

    def test_call_nested(self):
        """
        Test 4: Verificar CALL anidado (subrutina que llama a otra subrutina).
        
        - CALL 0x2000 desde 0x0100
        - CALL 0x3000 desde 0x2000
        - RET (debe volver a 0x2003)
        - RET (debe volver a 0x0103)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.sp = 0xFFFE
        regs.pc = 0x0100
        
        # Primer CALL: 0x0100 -> 0x2000
        mmu.write(0x0100, 0xCD)  # CALL nn
        mmu.write(0x0101, 0x00)
        mmu.write(0x0102, 0x20)
        cpu.step()
        assert regs.pc == 0x2000
        assert regs.sp == 0xFFFC
        
        # Segundo CALL: 0x2000 -> 0x3000
        regs.pc = 0x2000
        mmu.write(0x2000, 0xCD)  # CALL nn
        mmu.write(0x2001, 0x00)
        mmu.write(0x2002, 0x30)
        cpu.step()
        assert regs.pc == 0x3000
        assert regs.sp == 0xFFFA  # Decrementó 2 bytes más
        
        # Primer RET: 0x3000 -> 0x2003
        regs.pc = 0x3000
        mmu.write(0x3000, 0xC9)  # RET
        cpu.step()
        assert regs.pc == 0x2003
        assert regs.sp == 0xFFFC
        
        # Segundo RET: 0x2003 -> 0x0103
        regs.pc = 0x2003
        mmu.write(0x2003, 0xC9)  # RET
        cpu.step()
        assert regs.pc == 0x0103
        assert regs.sp == 0xFFFE

