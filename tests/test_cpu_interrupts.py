"""
Tests para el manejo de interrupciones de la CPU

Estos tests validan:
- Procesamiento de interrupciones (V-Blank, Timer, etc.)
- Prioridad de interrupciones
- Despertar de HALT por interrupciones
- Limpieza de flags y desactivación de IME
- Guardado correcto de PC en la pila
- Vectores de interrupción correctos
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU, IO_IF, IO_IE


class TestCPUInterrupts:
    """Tests para el manejo de interrupciones"""

    def test_vblank_interrupt(self) -> None:
        """
        Test: Interrupción V-Blank se procesa correctamente.
        
        Verifica que cuando IME está activo, IE tiene el bit 0 activo,
        y IF tiene el bit 0 activo, la CPU:
        - Salta a 0x0040 (vector V-Blank)
        - Desactiva IME
        - Limpia el bit 0 de IF
        - Guarda PC en la pila
        - Consume 5 M-Cycles
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x1234)  # PC inicial
        cpu.registers.set_sp(0xFFFE)  # Stack Pointer inicial
        cpu.ime = True  # IME activado
        
        # Habilitar interrupción V-Blank en IE (bit 0)
        mmu.write_byte(IO_IE, 0x01)
        
        # Activar flag V-Blank en IF (bit 0)
        mmu.write_byte(IO_IF, 0x01)
        
        # Ejecutar step (debe procesar la interrupción)
        cycles = cpu.step()
        
        # Verificaciones
        assert cycles == 5, "La interrupción debe consumir 5 M-Cycles"
        assert cpu.registers.get_pc() == 0x0040, "PC debe saltar al vector V-Blank"
        assert cpu.ime is False, "IME debe desactivarse automáticamente"
        
        # Verificar que el bit 0 de IF se limpió
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) == 0, "El bit 0 de IF debe estar limpio"
        
        # Verificar que PC se guardó en la pila (Little-Endian)
        # La pila se decrementa antes de escribir, así que:
        # SP inicial: 0xFFFE
        # Después de PUSH: SP = 0xFFFC
        # Memoria[0xFFFC] = 0x34 (LSB de 0x1234)
        # Memoria[0xFFFD] = 0x12 (MSB de 0x1234)
        assert cpu.registers.get_sp() == 0xFFFC, "SP debe decrementarse en 2"
        saved_pc_low = mmu.read_byte(0xFFFC)
        saved_pc_high = mmu.read_byte(0xFFFD)
        saved_pc = (saved_pc_high << 8) | saved_pc_low
        assert saved_pc == 0x1234, "PC debe guardarse correctamente en la pila"

    def test_interrupt_priority(self) -> None:
        """
        Test: Las interrupciones se procesan según prioridad.
        
        Si múltiples interrupciones están pendientes simultáneamente,
        se procesa primero la de mayor prioridad (menor número de bit).
        V-Blank (bit 0) tiene mayor prioridad que Timer (bit 2).
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x2000)
        cpu.registers.set_sp(0xFFFE)
        cpu.ime = True
        
        # Habilitar V-Blank (bit 0) y Timer (bit 2) en IE
        mmu.write_byte(IO_IE, 0x05)  # Bits 0 y 2 activos
        
        # Activar flags de V-Blank y Timer en IF
        mmu.write_byte(IO_IF, 0x05)  # Bits 0 y 2 activos
        
        # Ejecutar step
        cycles = cpu.step()
        
        # Debe procesar V-Blank (prioridad más alta), no Timer
        assert cycles == 5
        assert cpu.registers.get_pc() == 0x0040, "Debe saltar a V-Blank (mayor prioridad)"
        assert cpu.ime is False
        
        # Verificar que solo el bit 0 de IF se limpió (bit 2 sigue activo)
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) == 0, "Bit 0 (V-Blank) debe estar limpio"
        assert (if_val & 0x04) != 0, "Bit 2 (Timer) debe seguir activo"

    def test_halt_wakeup(self) -> None:
        """
        Test: HALT se despierta con interrupciones pendientes, incluso si IME es False.
        
        Si la CPU está en HALT y hay interrupciones pendientes (en IE y IF),
        la CPU debe despertar (halted = False), pero NO saltar al vector
        si IME está desactivado. Después de despertar, la CPU continúa ejecutando
        normalmente (avanza PC con la siguiente instrucción).
        Esto permite polling manual de IF después de HALT.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x3000)
        cpu.halted = True  # CPU en HALT
        cpu.ime = False  # IME desactivado
        
        # Habilitar V-Blank en IE y activar flag en IF
        mmu.write_byte(IO_IE, 0x01)
        mmu.write_byte(IO_IF, 0x01)
        
        # Poner un NOP en 0x3000 para que la CPU pueda ejecutar algo después de despertar
        mmu.write_byte(0x3000, 0x00)  # NOP
        
        # Ejecutar step
        cycles = cpu.step()
        
        # Debe despertar (halted = False) pero NO saltar a interrupción (IME está desactivado)
        assert cpu.halted is False, "CPU debe despertar de HALT"
        # Después de despertar, ejecuta la instrucción normal (NOP), así que PC avanza
        assert cpu.registers.get_pc() == 0x3001, "PC debe avanzar (ejecutó NOP después de despertar)"
        assert cycles == 1, "Debe consumir 1 ciclo (NOP), no ciclos de interrupción"
        
        # El bit de IF debe seguir activo (no se procesó la interrupción porque IME está desactivado)
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) != 0, "Bit de IF debe seguir activo (no se procesó)"

    def test_no_interrupt_if_ime_disabled(self) -> None:
        """
        Test: Las interrupciones no se procesan si IME está desactivado.
        
        Aunque IE e IF tengan bits activos, si IME es False,
        no se procesa ninguna interrupción.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x4000)
        cpu.registers.set_sp(0xFFFE)
        cpu.ime = False  # IME desactivado
        
        # Habilitar V-Blank en IE y activar flag en IF
        mmu.write_byte(IO_IE, 0x01)
        mmu.write_byte(IO_IF, 0x01)
        
        # Ejecutar step (debe ejecutar instrucción normal, no interrupción)
        # Pero primero necesitamos inicializar memoria con un opcode válido
        mmu.write_byte(0x4000, 0x00)  # NOP
        
        cycles = cpu.step()
        
        # No debe saltar a interrupción
        assert cpu.registers.get_pc() == 0x4001, "PC debe avanzar normalmente (ejecutó NOP)"
        assert cycles == 1, "Debe consumir 1 ciclo (NOP)"
        
        # IF debe seguir activo
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) != 0, "Bit de IF debe seguir activo"

    def test_timer_interrupt_vector(self) -> None:
        """
        Test: Interrupción Timer salta al vector correcto (0x0050).
        
        Verifica que la interrupción Timer (bit 2) salta al vector 0x0050.
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x5000)
        cpu.registers.set_sp(0xFFFE)
        cpu.ime = True
        
        # Habilitar Timer en IE (bit 2)
        mmu.write_byte(IO_IE, 0x04)
        
        # Activar flag Timer en IF (bit 2)
        mmu.write_byte(IO_IF, 0x04)
        
        # Ejecutar step
        cycles = cpu.step()
        
        # Debe saltar al vector Timer
        assert cycles == 5
        assert cpu.registers.get_pc() == 0x0050, "Debe saltar al vector Timer (0x0050)"
        
        # Verificar que el bit 2 de IF se limpió
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) == 0, "El bit 2 de IF debe estar limpio"

    def test_all_interrupt_vectors(self) -> None:
        """
        Test: Todos los vectores de interrupción son correctos.
        
        Verifica que cada tipo de interrupción salta al vector correcto:
        - V-Blank (bit 0) -> 0x0040
        - LCD STAT (bit 1) -> 0x0048
        - Timer (bit 2) -> 0x0050
        - Serial (bit 3) -> 0x0058
        - Joypad (bit 4) -> 0x0060
        """
        interrupt_configs = [
            (0, 0x01, 0x0040, "V-Blank"),
            (1, 0x02, 0x0048, "LCD STAT"),
            (2, 0x04, 0x0050, "Timer"),
            (3, 0x08, 0x0058, "Serial"),
            (4, 0x10, 0x0060, "Joypad"),
        ]
        
        for bit_num, bit_mask, expected_vector, name in interrupt_configs:
            mmu = MMU(None)
            cpu = CPU(mmu)
            
            cpu.registers.set_pc(0x6000)
            cpu.registers.set_sp(0xFFFE)
            cpu.ime = True
            
            # Habilitar interrupción en IE
            mmu.write_byte(IO_IE, bit_mask)
            
            # Activar flag en IF
            mmu.write_byte(IO_IF, bit_mask)
            
            # Ejecutar step
            cpu.step()
            
            # Verificar vector
            assert cpu.registers.get_pc() == expected_vector, \
                f"{name} debe saltar a 0x{expected_vector:04X}, pero saltó a 0x{cpu.registers.get_pc():04X}"

    def test_reti_reactivates_ime(self) -> None:
        """
        Test: RETI reactiva IME después de retornar de una interrupción.
        
        Verifica que RETI:
        - Hace POP de la dirección de retorno de la pila
        - Salta a esa dirección (igual que RET)
        - Reactiva IME (esto es lo que lo diferencia de RET)
        - Consume 4 M-Cycles
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        
        # Configurar estado inicial
        cpu.registers.set_pc(0x0040)  # Estamos en la rutina de interrupción V-Blank
        cpu.registers.set_sp(0xFFFC)  # Stack Pointer (ya se hizo PUSH PC antes)
        cpu.ime = False  # IME desactivado (se desactiva automáticamente al procesar interrupción)
        
        # Simular que hay una dirección de retorno en la pila (0x1234)
        # La pila crece hacia abajo, así que 0xFFFC contiene el LSB y 0xFFFD contiene el MSB
        mmu.write_byte(0xFFFC, 0x34)  # LSB de 0x1234
        mmu.write_byte(0xFFFD, 0x12)  # MSB de 0x1234
        
        # Escribir RETI en la posición actual
        mmu.write_byte(0x0040, 0xD9)  # Opcode RETI
        
        # Ejecutar RETI
        cycles = cpu.step()
        
        # Verificaciones
        assert cycles == 4, f"RETI debe consumir 4 M-Cycles, consumió {cycles}"
        assert cpu.registers.get_pc() == 0x1234, \
            f"PC debe ser 0x1234 (dirección de retorno), es 0x{cpu.registers.get_pc():04X}"
        assert cpu.registers.get_sp() == 0xFFFE, \
            f"SP debe ser 0xFFFE (incrementó 2 bytes), es 0x{cpu.registers.get_sp():04X}"
        assert cpu.ime is True, \
            "IME debe estar activado después de RETI (esto es lo que diferencia RETI de RET)"

