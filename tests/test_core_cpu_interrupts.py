"""
Tests de integración para Sistema de Interrupciones en CPU nativa (C++).

Este módulo prueba el sistema de interrupciones implementado en C++:
- DI (0xF3): Desactiva IME inmediatamente
- EI (0xFB): Habilita IME con retraso de 1 instrucción
- HALT (0x76): Pone la CPU en estado de bajo consumo
- handle_interrupts(): Procesa interrupciones pendientes según prioridad

Tests críticos:
- Verificar que DI desactiva IME inmediatamente
- Verificar que EI activa IME después de la siguiente instrucción
- Verificar que HALT detiene la ejecución hasta interrupción
- Verificar que las interrupciones se procesan con prioridad correcta
- Verificar que los vectores de interrupción son correctos
"""

import pytest
from tests.helpers_cpu import load_program, TEST_EXEC_BASE

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)

# Direcciones de registros de interrupciones
IO_IF = 0xFF0F  # Interrupt Flag
IO_IE = 0xFFFF  # Interrupt Enable


class TestDI_EI:
    """Tests para DI (Disable Interrupts) y EI (Enable Interrupts)"""

    def test_di_disables_ime(self):
        """
        Test 1: Verificar que DI (0xF3) desactiva IME inmediatamente.
        
        - IME inicia en False por defecto
        - Activar IME manualmente (simulando estado previo)
        - Ejecutar DI
        - Verificar que IME es False
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # IME inicia en False por defecto (retorna 0)
        assert cpu.get_ime() == 0, "IME debe iniciar en False (0)"
        
        # Nota: No podemos activar IME directamente desde Python,
        # pero podemos usar EI para activarlo y luego DI para desactivarlo
        
        # Cargar programa en WRAM
        program = [
            0xFB,  # EI
            0x00,  # NOP (para que EI tome efecto)
            0xF3,  # DI
        ]
        load_program(mmu, regs, program)
        
        # Ejecutar EI
        cpu.step()
        
        # Ejecutar NOP para que EI tome efecto
        cpu.step()
        
        # Verificar que IME está activo
        assert cpu.get_ime() == 1, "IME debe estar activo después de EI + NOP"
        
        # Ejecutar DI
        cycles = cpu.step()
        
        # Verificar que IME está desactivado
        assert cpu.get_ime() == 0, "IME debe estar desactivado después de DI"
        assert cycles == 1, "DI debe consumir 1 M-Cycle"
    
    def test_ei_delayed_activation(self):
        """
        Test 2: Verificar que EI (0xFB) activa IME después de la siguiente instrucción.
        
        - IME inicia en False
        - Ejecutar EI
        - Verificar que IME sigue siendo False (retraso)
        - Ejecutar NOP
        - Verificar que IME ahora es True
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # IME inicia en False
        assert cpu.ime == False
        
        # Cargar programa en WRAM
        program = [
            0xFB,  # EI
            0x00,  # NOP
        ]
        load_program(mmu, regs, program)
        
        # Ejecutar EI
        cycles = cpu.step()
        
        # Verificar que IME sigue siendo False (retraso de 1 instrucción)
        assert cpu.get_ime() == 0, "IME debe seguir siendo False (0) inmediatamente después de EI"
        assert cycles == 1, "EI debe consumir 1 M-Cycle"
        
        # Ejecutar siguiente instrucción (NOP)
        cpu.step()
        
        # Verificar que IME ahora está activo
        assert cpu.get_ime() == 1, "IME debe estar activo después de la siguiente instrucción"


class TestHALT:
    """Tests para HALT (0x76)"""

    def test_halt_stops_execution(self):
        """
        Test 3: Verificar que HALT detiene la ejecución de instrucciones.
        
        - Ejecutar HALT
        - Verificar que halted es True
        - Verificar que step() devuelve -1 (código especial para avance rápido)
        - Ejecutar step() múltiples veces
        - Verificar que PC no cambia (CPU dormida)
        - Verificar que step() sigue devolviendo -1
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar programa en WRAM
        program = [
            0x76,  # HALT
        ]
        load_program(mmu, regs, program)
        
        # Ejecutar HALT
        cycles = cpu.step()
        
        # Verificar que halted es True
        assert cpu.get_halted() == 1, "CPU debe estar en estado HALT (1)"
        assert cycles == -1, "HALT debe devolver -1 para señalar avance rápido"
        
        # Ejecutar step() múltiples veces
        # La CPU debe seguir dormida (PC no cambia)
        initial_pc = regs.pc
        for _ in range(5):
            cycles = cpu.step()
            assert cycles == -1, "HALT debe devolver -1 por ciclo (señal de avance rápido)"
            assert regs.pc == initial_pc, "PC no debe cambiar cuando CPU está en HALT"
            assert cpu.get_halted() == 1, "CPU debe seguir en HALT"
    
    def test_halt_instruction_signals_correctly(self):
        """
        Step 0172: Verifica que HALT (0x76) activa el flag 'halted' y
        que step() devuelve -1 para señalarlo.
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Cargar programa en WRAM
        program = [
            0x76,  # HALT
        ]
        load_program(mmu, regs, program)
        
        assert cpu.get_halted() == 0, "CPU no debe estar en HALT inicialmente"
        
        # Ejecutar
        cycles = cpu.step()
        
        # Verificar
        assert cycles == -1, "step() debe devolver -1 para señalar HALT"
        assert cpu.get_halted() == 1, "El flag 'halted' debe activarse"
        # El PC avanza porque fetch_byte() se ejecuta antes del switch
        expected_pc = TEST_EXEC_BASE + 1
        assert regs.pc == expected_pc, f"PC debe haber avanzado 1 byte a 0x{expected_pc:04X}"
    
    def test_halt_wakeup_on_interrupt(self):
        """
        Test 4: Verificar que HALT se despierta cuando hay interrupción pendiente.
        
        - Poner CPU en HALT
        - Activar interrupción en IF (sin IME)
        - Ejecutar step()
        - Verificar que halted es False (CPU despierta)
        - Verificar que la interrupción NO se procesa (IME está desactivado)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC y SP
        regs.pc = 0x0100
        regs.sp = 0xFFFE
        
        # Ejecutar HALT
        mmu.write(0x0100, 0x76)  # HALT
        cpu.step()
        assert cpu.halted == True
        
        # Activar interrupción V-Blank en IF (bit 0)
        mmu.write(IO_IF, 0x01)  # V-Blank flag
        mmu.write(IO_IE, 0x01)  # Habilitar V-Blank en IE
        
        # Poner un NOP en la dirección actual (después de HALT, PC está en 0x0101)
        # Cuando la CPU despierta, ejecutará esta instrucción
        mmu.write(regs.pc, 0x00)  # NOP
        
        # Ejecutar step() (debe despertar la CPU)
        initial_pc = regs.pc
        cycles = cpu.step()
        
        # Verificar que CPU despertó
        assert cpu.get_halted() == 0, "CPU debe despertar cuando hay interrupción pendiente"
        
        # Verificar que la interrupción NO se procesó (IME está desactivado)
        # Cuando la CPU despierta del HALT sin procesar la interrupción, ejecuta la siguiente instrucción
        # Por lo tanto, el PC debe avanzar (no saltó al vector, pero ejecutó la siguiente instrucción)
        assert regs.pc == initial_pc + 1, "PC debe avanzar (ejecutó la siguiente instrucción después de despertar)"
        assert cycles == 1, "Debe consumir 1 M-Cycle (NOP), no ciclos de interrupción"
        
        # Verificar que IF sigue activo (no se limpió)
        assert (mmu.read(IO_IF) & 0x01) == 0x01, "IF debe seguir activo si IME está desactivado"


class TestInterruptDispatch:
    """Tests para el dispatcher de interrupciones"""

    def test_interrupt_dispatch_vblank(self):
        """
        Test 5: Verificar que una interrupción V-Blank se procesa correctamente.
        
        - Activar IME
        - Habilitar V-Blank en IE
        - Activar flag V-Blank en IF
        - Ejecutar step()
        - Verificar que PC saltó a 0x0040 (vector V-Blank)
        - Verificar que PC anterior está en la pila
        - Verificar que IF se limpió
        - Verificar que IME se desactivó
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC y SP
        regs.pc = 0x1234
        regs.sp = 0xFFFE
        
        # Activar IME usando EI
        mmu.write(0x1234, 0xFB)  # EI
        cpu.step()
        mmu.write(0x1235, 0x00)  # NOP (para que EI tome efecto)
        cpu.step()
        assert cpu.get_ime() == 1
        
        # Habilitar V-Blank en IE y activar flag en IF
        mmu.write(IO_IE, 0x01)  # Habilitar V-Blank (bit 0)
        mmu.write(IO_IF, 0x01)  # Activar flag V-Blank (bit 0)
        
        # Ejecutar step() (debe procesar la interrupción)
        initial_pc = regs.pc
        cycles = cpu.step()
        
        # Verificar que PC saltó al vector V-Blank
        assert regs.pc == 0x0040, f"PC debe saltar a 0x0040 (vector V-Blank), es 0x{regs.pc:04X}"
        
        # Verificar que PC anterior está en la pila
        low_byte = mmu.read(0xFFFC)
        high_byte = mmu.read(0xFFFD)
        saved_pc = (high_byte << 8) | low_byte
        assert saved_pc == initial_pc, (
            f"PC anterior (0x{initial_pc:04X}) debe estar en la pila, "
            f"pero se encontró 0x{saved_pc:04X}"
        )
        
        # Verificar que SP decrementó
        assert regs.sp == 0xFFFC, "SP debe decrementar 2 bytes (PUSH PC)"
        
        # Verificar que IF se limpió
        if_reg = mmu.read(IO_IF)
        assert (if_reg & 0x01) == 0, "Bit 0 de IF debe estar limpio después de procesar interrupción"
        
        # Verificar que IME se desactivó
        assert cpu.get_ime() == 0, "IME debe desactivarse automáticamente al procesar interrupción"
        
        # Verificar ciclos consumidos
        assert cycles == 5, f"Procesar interrupción debe consumir 5 M-Cycles, consumió {cycles}"
    
    def test_interrupt_priority(self):
        """
        Test 6: Verificar que las interrupciones se procesan según prioridad.
        
        Prioridad (de mayor a menor):
        - Bit 0: V-Blank -> 0x0040
        - Bit 1: LCD STAT -> 0x0048
        - Bit 2: Timer -> 0x0050
        - Bit 3: Serial -> 0x0058
        - Bit 4: Joypad -> 0x0060
        
        - Activar múltiples interrupciones simultáneamente
        - Verificar que se procesa la de mayor prioridad (V-Blank)
        """
        mmu = PyMMU()
        mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC y SP
        regs.pc = 0x0100
        regs.sp = 0xFFFE
        
        # Activar IME
        mmu.write(0x0100, 0xFB)  # EI
        cpu.step()
        mmu.write(0x0101, 0x00)  # NOP
        cpu.step()
        
        # Activar múltiples interrupciones: Timer (bit 2) y V-Blank (bit 0)
        # V-Blank tiene mayor prioridad
        mmu.write(IO_IE, 0x05)  # Habilitar V-Blank (bit 0) y Timer (bit 2)
        mmu.write(IO_IF, 0x05)  # Activar flags V-Blank y Timer
        
        # Ejecutar step()
        cpu.step()
        
        # Verificar que se procesó V-Blank (mayor prioridad)
        assert regs.pc == 0x0040, "Debe procesarse V-Blank (mayor prioridad), no Timer"
        
        # Verificar que solo el bit 0 de IF se limpió
        if_reg = mmu.read(IO_IF)
        assert (if_reg & 0x01) == 0, "Bit 0 (V-Blank) debe estar limpio"
        assert (if_reg & 0x04) == 0x04, "Bit 2 (Timer) debe seguir activo (no se procesó)"
    
    def test_all_interrupt_vectors(self):
        """
        Test 7: Verificar que todos los vectores de interrupción son correctos.
        
        - Para cada tipo de interrupción:
          - Activar IME
          - Habilitar interrupción en IE
          - Activar flag en IF
          - Ejecutar step()
          - Verificar que PC saltó al vector correcto
        """
        interrupt_configs = [
            (0x01, 0x0040, "V-Blank"),      # Bit 0
            (0x02, 0x0048, "LCD STAT"),     # Bit 1
            (0x04, 0x0050, "Timer"),         # Bit 2
            (0x08, 0x0058, "Serial"),       # Bit 3
            (0x10, 0x0060, "Joypad"),        # Bit 4
        ]
        
        for bit_mask, expected_vector, name in interrupt_configs:
            mmu = PyMMU()
            mmu.set_test_mode_allow_rom_writes(True)  # Step 0421: Permitir escrituras en ROM para testing
            regs = PyRegisters()
            cpu = PyCPU(mmu, regs)
            
            # Inicializar PC y SP
            regs.pc = 0x0100
            regs.sp = 0xFFFE
            
            # Activar IME
            mmu.write(0x0100, 0xFB)  # EI
            cpu.step()
            mmu.write(0x0101, 0x00)  # NOP
            cpu.step()
            assert cpu.get_ime() == 1
            
            # Habilitar interrupción en IE y activar flag en IF
            mmu.write(IO_IE, bit_mask)
            mmu.write(IO_IF, bit_mask)
            
            # Ejecutar step()
            cpu.step()
            
            # Verificar vector
            assert regs.pc == expected_vector, (
                f"{name} debe saltar a 0x{expected_vector:04X}, "
                f"pero saltó a 0x{regs.pc:04X}"
            )

