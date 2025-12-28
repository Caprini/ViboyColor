"""
Tests unitarios para operaciones de pila (Stack) de la CPU.

Valida las instrucciones de pila y subrutinas:
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

from src.cpu.core import CPU
from src.memory.mmu import MMU


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
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Inicializar SP (típico valor inicial en Game Boy)
        cpu.registers.set_sp(0xFFFE)
        
        # Establecer BC
        cpu.registers.set_bc(0x1234)
        
        # Ejecutar PUSH BC
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xC5)  # Opcode PUSH BC
        cycles = cpu.step()
        
        # Verificar que SP decrementó (pila crece hacia abajo)
        assert cpu.registers.get_sp() == 0xFFFC, (
            f"SP debe ser 0xFFFC después de PUSH, es 0x{cpu.registers.get_sp():04X}"
        )
        
        # Verificar que los datos están en memoria en orden Little-Endian
        # PUSH escribe primero high byte, luego low byte
        # Así que en memoria: [0xFFFD] = 0x12 (high), [0xFFFC] = 0x34 (low)
        assert mmu.read_byte(0xFFFD) == 0x12, "Byte alto debe estar en 0xFFFD"
        assert mmu.read_byte(0xFFFC) == 0x34, "Byte bajo debe estar en 0xFFFC"
        
        # Verificar que read_word lee correctamente (Little-Endian)
        assert mmu.read_word(0xFFFC) == 0x1234, "read_word debe leer 0x1234 correctamente"
        
        assert cycles == 4, f"PUSH BC debe consumir 4 M-Cycles, consumió {cycles}"
        
        # Ahora ejecutar POP BC
        cpu.registers.set_pc(0x0101)
        mmu.write_byte(0x0101, 0xC1)  # Opcode POP BC
        cycles = cpu.step()
        
        # Verificar que BC se restauró correctamente
        assert cpu.registers.get_bc() == 0x1234, (
            f"BC debe ser 0x1234 después de POP, es 0x{cpu.registers.get_bc():04X}"
        )
        
        # Verificar que SP volvió a su valor original
        assert cpu.registers.get_sp() == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de POP, es 0x{cpu.registers.get_sp():04X}"
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
        mmu = MMU()
        cpu = CPU(mmu)
        
        initial_sp = 0xFFFE
        cpu.registers.set_sp(initial_sp)
        cpu.registers.set_bc(0x5678)
        
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xC5)  # PUSH BC
        cpu.step()
        
        # Verificar que SP decrementó
        assert cpu.registers.get_sp() < initial_sp, (
            f"SP debe decrementar en PUSH. Inicial: 0x{initial_sp:04X}, "
            f"Actual: 0x{cpu.registers.get_sp():04X}"
        )
        
        # Verificar que decrementó exactamente 2 (una palabra = 2 bytes)
        assert cpu.registers.get_sp() == (initial_sp - 2) & 0xFFFF, (
            f"SP debe decrementar en 2 bytes. Esperado: 0x{(initial_sp - 2) & 0xFFFF:04X}, "
            f"Actual: 0x{cpu.registers.get_sp():04X}"
        )

    def test_push_pop_multiple(self):
        """
        Test 3: Verificar múltiples PUSH/POP consecutivos.
        
        - PUSH BC con valor 0x1111
        - PUSH BC con valor 0x2222 (nuevo valor)
        - POP BC (debe obtener 0x2222)
        - POP BC (debe obtener 0x1111)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_sp(0xFFFE)
        
        # Primer PUSH
        cpu.registers.set_bc(0x1111)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xC5)  # PUSH BC
        cpu.step()
        
        # Segundo PUSH
        cpu.registers.set_bc(0x2222)
        cpu.registers.set_pc(0x0101)
        mmu.write_byte(0x0101, 0xC5)  # PUSH BC
        cpu.step()
        
        # Verificar que SP decrementó 4 bytes en total
        assert cpu.registers.get_sp() == 0xFFFA
        
        # Primer POP (debe obtener el último valor pusheado)
        cpu.registers.set_pc(0x0102)
        mmu.write_byte(0x0102, 0xC1)  # POP BC
        cpu.step()
        assert cpu.registers.get_bc() == 0x2222, "Primer POP debe obtener 0x2222"
        
        # Segundo POP (debe obtener el primer valor pusheado)
        cpu.registers.set_pc(0x0103)
        mmu.write_byte(0x0103, 0xC1)  # POP BC
        cpu.step()
        assert cpu.registers.get_bc() == 0x1111, "Segundo POP debe obtener 0x1111"
        
        # Verificar que SP volvió al valor original
        assert cpu.registers.get_sp() == 0xFFFE


class TestCallRet:
    """Tests para CALL nn y RET"""

    def test_call_ret(self):
        """
        Test 4: Verificar CALL nn y RET básico.
        
        Este es el test CRÍTICO para subrutinas.
        
        - PC en 0x0100
        - Ejecutar CALL 0x2000
        - Verificar PC == 0x2000
        - Verificar que en la pila está 0x0103 (siguiente instrucción tras el call)
        - Ejecutar RET
        - Verificar PC == 0x0103
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        # Inicializar SP
        cpu.registers.set_sp(0xFFFE)
        
        # Establecer PC inicial
        cpu.registers.set_pc(0x0100)
        
        # Escribir CALL 0x2000 (0xCD 0x00 0x20)
        mmu.write_byte(0x0100, 0xCD)  # Opcode CALL nn
        mmu.write_byte(0x0101, 0x00)   # LSB de dirección
        mmu.write_byte(0x0102, 0x20)   # MSB de dirección
        
        # Ejecutar CALL
        cycles = cpu.step()
        
        # Verificar que PC saltó a la dirección objetivo
        assert cpu.registers.get_pc() == 0x2000, (
            f"PC debe ser 0x2000 después de CALL, es 0x{cpu.registers.get_pc():04X}"
        )
        
        # Verificar que SP decrementó (se guardó dirección de retorno)
        assert cpu.registers.get_sp() == 0xFFFC, (
            f"SP debe ser 0xFFFC después de CALL (decrementó 2 bytes), "
            f"es 0x{cpu.registers.get_sp():04X}"
        )
        
        # Verificar que la dirección de retorno está en la pila
        # Dirección de retorno = PC después de leer toda la instrucción = 0x0103
        return_addr = mmu.read_word(0xFFFC)
        assert return_addr == 0x0103, (
            f"Dirección de retorno debe ser 0x0103, es 0x{return_addr:04X}. "
            "Esta es la dirección de la siguiente instrucción tras el CALL."
        )
        
        assert cycles == 6, f"CALL nn debe consumir 6 M-Cycles, consumió {cycles}"
        
        # Ahora ejecutar RET
        cpu.registers.set_pc(0x2000)  # Estamos en la subrutina
        mmu.write_byte(0x2000, 0xC9)  # Opcode RET
        cycles = cpu.step()
        
        # Verificar que PC se restauró a la dirección de retorno
        assert cpu.registers.get_pc() == 0x0103, (
            f"PC debe ser 0x0103 después de RET, es 0x{cpu.registers.get_pc():04X}"
        )
        
        # Verificar que SP volvió a su valor original
        assert cpu.registers.get_sp() == 0xFFFE, (
            f"SP debe volver a 0xFFFE después de RET, es 0x{cpu.registers.get_sp():04X}"
        )
        
        assert cycles == 4, f"RET debe consumir 4 M-Cycles, consumió {cycles}"

    def test_call_nested(self):
        """
        Test 5: Verificar CALL anidado (subrutina que llama a otra subrutina).
        
        - CALL 0x2000 desde 0x0100
        - CALL 0x3000 desde 0x2000
        - RET (debe volver a 0x2003)
        - RET (debe volver a 0x0103)
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_sp(0xFFFE)
        
        # Primer CALL: 0x0100 -> 0x2000
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xCD)  # CALL nn
        mmu.write_byte(0x0101, 0x00)
        mmu.write_byte(0x0102, 0x20)
        cpu.step()
        
        assert cpu.registers.get_pc() == 0x2000
        assert cpu.registers.get_sp() == 0xFFFC
        
        # Segundo CALL: 0x2000 -> 0x3000
        cpu.registers.set_pc(0x2000)
        mmu.write_byte(0x2000, 0xCD)  # CALL nn
        mmu.write_byte(0x2001, 0x00)
        mmu.write_byte(0x2002, 0x30)
        cpu.step()
        
        assert cpu.registers.get_pc() == 0x3000
        assert cpu.registers.get_sp() == 0xFFFA
        
        # Verificar que la segunda dirección de retorno está en la pila
        second_return = mmu.read_word(0xFFFA)
        assert second_return == 0x2003, "Segunda dirección de retorno debe ser 0x2003"
        
        # Primer RET: 0x3000 -> 0x2003
        cpu.registers.set_pc(0x3000)
        mmu.write_byte(0x3000, 0xC9)  # RET
        cpu.step()
        
        assert cpu.registers.get_pc() == 0x2003
        assert cpu.registers.get_sp() == 0xFFFC
        
        # Segundo RET: 0x2003 -> 0x0103
        cpu.registers.set_pc(0x2003)
        mmu.write_byte(0x2003, 0xC9)  # RET
        cpu.step()
        
        assert cpu.registers.get_pc() == 0x0103
        assert cpu.registers.get_sp() == 0xFFFE

    def test_push_pop_de_hl(self):
        """
        Test 6: Verificar PUSH/POP DE y HL.
        
        - PUSH DE con valor 0x5678
        - POP DE debe restaurar 0x5678
        - PUSH HL con valor 0x9ABC
        - POP HL debe restaurar 0x9ABC
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_sp(0xFFFE)
        
        # Test DE
        cpu.registers.set_de(0x5678)
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xD5)  # PUSH DE
        cpu.step()
        
        assert cpu.registers.get_sp() == 0xFFFC
        assert mmu.read_word(0xFFFC) == 0x5678
        
        cpu.registers.set_de(0x0000)  # Limpiar para verificar POP
        cpu.registers.set_pc(0x0101)
        mmu.write_byte(0x0101, 0xD1)  # POP DE
        cpu.step()
        
        assert cpu.registers.get_de() == 0x5678
        assert cpu.registers.get_sp() == 0xFFFE
        
        # Test HL
        cpu.registers.set_hl(0x9ABC)
        cpu.registers.set_pc(0x0102)
        mmu.write_byte(0x0102, 0xE5)  # PUSH HL
        cpu.step()
        
        assert cpu.registers.get_sp() == 0xFFFC
        assert mmu.read_word(0xFFFC) == 0x9ABC
        
        cpu.registers.set_hl(0x0000)  # Limpiar para verificar POP
        cpu.registers.set_pc(0x0103)
        mmu.write_byte(0x0103, 0xE1)  # POP HL
        cpu.step()
        
        assert cpu.registers.get_hl() == 0x9ABC
        assert cpu.registers.get_sp() == 0xFFFE

    def test_pop_af_mask(self):
        """
        Test 7: Verificar que POP AF aplica máscara 0xF0 a F.
        
        CRÍTICO: Los 4 bits bajos de F siempre deben ser cero.
        Si recuperamos 0xFFFF de la pila, F debe ser 0xF0 (no 0xFF).
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_sp(0xFFFE)
        
        # Escribir manualmente 0xFFFF en la pila (simulando un PUSH previo)
        # PUSH escribe primero high byte, luego low byte
        mmu.write_byte(0xFFFD, 0xFF)  # High byte (A)
        mmu.write_byte(0xFFFC, 0xFF)  # Low byte (F)
        cpu.registers.set_sp(0xFFFC)  # SP apunta al inicio del valor
        
        # Ejecutar POP AF
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xF1)  # POP AF
        cpu.step()
        
        # Verificar que A es 0xFF
        assert cpu.registers.get_a() == 0xFF, (
            f"A debe ser 0xFF, es 0x{cpu.registers.get_a():02X}"
        )
        
        # Verificar que F es 0xF0 (bits bajos limpiados)
        assert cpu.registers.get_f() == 0xF0, (
            f"F debe ser 0xF0 (bits bajos limpiados), es 0x{cpu.registers.get_f():02X}. "
            "Los 4 bits bajos de F siempre deben ser cero en hardware real."
        )
        
        # Verificar que SP incrementó
        assert cpu.registers.get_sp() == 0xFFFE

    def test_push_pop_af(self):
        """
        Test 8: Verificar PUSH/POP AF completo.
        
        - Establecer A=0xAA, F=0xF0 (flags activos)
        - PUSH AF
        - Limpiar AF
        - POP AF
        - Verificar que A y F se restauraron correctamente
        """
        mmu = MMU()
        cpu = CPU(mmu)
        
        cpu.registers.set_sp(0xFFFE)
        
        # Establecer AF
        cpu.registers.set_a(0xAA)
        cpu.registers.set_f(0xF0)  # Todos los flags activos
        
        # PUSH AF
        cpu.registers.set_pc(0x0100)
        mmu.write_byte(0x0100, 0xF5)  # PUSH AF
        cpu.step()
        
        assert cpu.registers.get_sp() == 0xFFFC
        # Verificar que AF está en memoria (A=0xAA, F=0xF0)
        assert mmu.read_byte(0xFFFD) == 0xAA  # High byte (A)
        assert mmu.read_byte(0xFFFC) == 0xF0   # Low byte (F)
        
        # Limpiar AF
        cpu.registers.set_a(0x00)
        cpu.registers.set_f(0x00)
        
        # POP AF
        cpu.registers.set_pc(0x0101)
        mmu.write_byte(0x0101, 0xF1)  # POP AF
        cpu.step()
        
        # Verificar que se restauraron
        assert cpu.registers.get_a() == 0xAA
        assert cpu.registers.get_f() == 0xF0
        assert cpu.registers.get_sp() == 0xFFFE

