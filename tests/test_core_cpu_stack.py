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

Nota Step 0423: TODOS los tests migrados a WRAM usando load_program() y fixture mmu estándar.
"""

import pytest
from tests.helpers_cpu import load_program, TEST_EXEC_BASE

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestPushPop:
    """Tests para PUSH BC y POP BC - Step 0423: ejecuta desde WRAM"""

    def test_push_pop_bc(self, mmu):
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
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP (típico valor inicial en Game Boy)
        regs.sp = 0xFFFE
        
        # Establecer BC
        regs.b = 0x12
        regs.c = 0x34
        
        # Cargar programa con PUSH y POP consecutivos
        load_program(mmu, regs, [0xC5, 0xC1])  # PUSH BC, POP BC
        
        # Ejecutar PUSH BC
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
        
        # Limpiar BC para verificar que POP lo restaura
        regs.b = 0x00
        regs.c = 0x00
        
        # Ejecutar POP BC (ya está en memoria después de PUSH)
        cycles = cpu.step()
        
        # Verificar que BC se restauró correctamente
        assert regs.b == 0x12, "B debe ser 0x12 después de POP"
        assert regs.c == 0x34, "C debe ser 0x34 después de POP"
        
        # Verificar que SP volvió a su valor original
        assert regs.sp == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de POP, es 0x{regs.sp:04X}"
        )
        
        assert cycles == 3, f"POP BC debe consumir 3 M-Cycles, consumió {cycles}"

    def test_stack_grows_downwards(self, mmu):
        """
        Test 2: Verificar que la pila crece hacia abajo (SP decrece en PUSH).
        
        Este es el test CRÍTICO: verifica que la pila funciona correctamente.
        Si la pila creciera hacia arriba, los juegos se corromperían.
        
        - SP inicial en 0xFFFE
        - PUSH BC
        - Verificar que SP < valor inicial
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        initial_sp = 0xFFFE
        regs.sp = initial_sp
        regs.b = 0xAA
        regs.c = 0xBB
        
        load_program(mmu, regs, [0xC5])  # PUSH BC
        cpu.step()
        
        # Verificar que SP decrementó
        assert regs.sp < initial_sp, (
            f"SP debe decrementar en PUSH. Inicial: 0x{initial_sp:04X}, "
            f"Después: 0x{regs.sp:04X}"
        )
        assert regs.sp == 0xFFFC, "SP debe ser 0xFFFC después de PUSH"


class TestCallRet:
    """Tests para CALL nn y RET - Step 0423: ejecuta desde WRAM"""

    def test_call_ret_basic(self, mmu):
        """
        Test 3: Verificar CALL nn y RET básico.
        
        - Establecer SP en 0xFFFE
        - Ejecutar CALL (a dirección WRAM)
        - Verificar que PC salta correctamente
        - Verificar que SP decrementó 2 bytes
        - Verificar que la dirección de retorno está en la pila
        - Ejecutar RET
        - Verificar que PC vuelve correctamente
        - Verificar que SP se restaura
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar SP
        regs.sp = 0xFFFE
        
        # Dirección destino para el CALL (en WRAM alta para no pisar el programa)
        call_target = 0xC100
        
        # Escribir RET en la dirección destino (antes de ejecutar CALL)
        mmu.write(call_target, 0xC9)  # RET
        
        # Cargar CALL call_target (0xCD LSB MSB)
        lsb = call_target & 0xFF
        msb = (call_target >> 8) & 0xFF
        load_program(mmu, regs, [0xCD, lsb, msb])  # CALL nn
        
        # Ejecutar CALL
        cycles = cpu.step()
        
        # Verificar que PC saltó a la dirección destino
        assert regs.pc == call_target, (
            f"PC debe ser 0x{call_target:04X} después de CALL, es 0x{regs.pc:04X}"
        )
        
        # Verificar que SP decrementó (pila crece hacia abajo)
        assert regs.sp == 0xFFFC, (
            f"SP debe ser 0xFFFC después de CALL (decrementó 2 bytes), "
            f"es 0x{regs.sp:04X}"
        )
        
        # Verificar que la dirección de retorno está en la pila
        # La dirección de retorno es TEST_EXEC_BASE + 3 (después de CALL nn)
        low_byte = mmu.read(0xFFFC)
        high_byte = mmu.read(0xFFFD)
        return_addr = (high_byte << 8) | low_byte
        expected_return = TEST_EXEC_BASE + 3
        assert return_addr == expected_return, (
            f"Dirección de retorno debe ser 0x{expected_return:04X}, es 0x{return_addr:04X}. "
            "Esta es la dirección de la siguiente instrucción tras el CALL."
        )
        
        assert cycles == 6, f"CALL nn debe consumir 6 M-Cycles, consumió {cycles}"
        
        # Ahora ejecutar RET (ya está en call_target)
        cycles = cpu.step()
        
        # Verificar que PC volvió a la dirección de retorno
        assert regs.pc == expected_return, (
            f"PC debe ser 0x{expected_return:04X} después de RET, es 0x{regs.pc:04X}"
        )
        
        # Verificar que SP volvió a su valor original
        assert regs.sp == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de RET, es 0x{regs.sp:04X}"
        )
        
        assert cycles == 4, f"RET debe consumir 4 M-Cycles, consumió {cycles}"

    def test_call_nested(self, mmu):
        """
        Test 4: Verificar CALL anidado (subrutina que llama a otra subrutina).
        
        - CALL target1 desde base
        - CALL target2 desde target1
        - RET (debe volver a target1 + 3)
        - RET (debe volver a base + 3)
        """
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.sp = 0xFFFE
        
        # Direcciones para los CALLs (en WRAM, separadas)
        target1 = 0xC100
        target2 = 0xC200
        
        # Preparar target2: solo RET
        mmu.write(target2, 0xC9)  # RET
        
        # Preparar target1: CALL target2 seguido de RET
        lsb2 = target2 & 0xFF
        msb2 = (target2 >> 8) & 0xFF
        mmu.write(target1 + 0, 0xCD)  # CALL nn
        mmu.write(target1 + 1, lsb2)
        mmu.write(target1 + 2, msb2)
        mmu.write(target1 + 3, 0xC9)  # RET
        
        # Cargar primer CALL en base
        lsb1 = target1 & 0xFF
        msb1 = (target1 >> 8) & 0xFF
        load_program(mmu, regs, [0xCD, lsb1, msb1])  # CALL target1
        
        # Primer CALL: base -> target1
        cpu.step()
        assert regs.pc == target1, f"PC debe ser 0x{target1:04X}"
        assert regs.sp == 0xFFFC
        
        # Segundo CALL: target1 -> target2
        cpu.step()
        assert regs.pc == target2, f"PC debe ser 0x{target2:04X}"
        assert regs.sp == 0xFFFA  # Decrementó 2 bytes más
        
        # Primer RET: target2 -> target1 + 3
        cpu.step()
        assert regs.pc == target1 + 3, f"PC debe ser 0x{target1 + 3:04X}"
        assert regs.sp == 0xFFFC
        
        # Segundo RET: target1 + 3 -> base + 3
        cpu.step()
        assert regs.pc == TEST_EXEC_BASE + 3, f"PC debe ser 0x{TEST_EXEC_BASE + 3:04X}"
        assert regs.sp == 0xFFFE

