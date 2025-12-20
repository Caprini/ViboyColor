"""
Test de Integración: HALT y Despertar por Interrupciones (Step 0173)

Este test verifica el ciclo completo de HALT:
1. CPU ejecuta HALT
2. PPU genera una interrupción V-Blank
3. La CPU se despierta del estado HALT

Este test es crítico para validar que el bucle principal de viboy.py
maneja correctamente el estado HALT, permitiendo que la CPU se despierte
cuando ocurren interrupciones.
"""

import pytest
import sys
from pathlib import Path

# Añadir raíz del proyecto al path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Importar componentes
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU, PyPPU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False

from src.viboy import Viboy

# Constantes de timing para el test
CYCLES_PER_SCANLINE = 456
SCANLINES_PER_FRAME = 154
CYCLES_PER_FRAME = CYCLES_PER_SCANLINE * SCANLINES_PER_FRAME

# Direcciones de registros de interrupciones
IO_IF = 0xFF0F  # Interrupt Flag
IO_IE = 0xFFFF  # Interrupt Enable


@pytest.mark.skipif(not CPP_CORE_AVAILABLE, reason="Módulo viboy_core no compilado")
def test_halt_wakeup_integration():
    """
    Step 0173: Test de integración que verifica el ciclo completo:
    1. CPU ejecuta HALT.
    2. PPU genera una interrupción V-Blank.
    3. La CPU se despierta del estado HALT.
    
    Este test valida que el bucle principal de viboy.py siempre llama
    a cpu.step() incluso cuando la CPU está en HALT, permitiendo que
    handle_interrupts() pueda despertar la CPU.
    """
    # 1. Inicializar el emulador sin ROM (modo de prueba)
    viboy = Viboy(rom_path=None, use_cpp_core=True)
    cpu = viboy.get_cpu()
    mmu = viboy.get_mmu()
    ppu = viboy.get_ppu()
    
    assert cpu is not None, "CPU debe estar inicializada"
    assert mmu is not None, "MMU debe estar inicializada"
    assert ppu is not None, "PPU debe estar inicializada"
    
    # 2. Configurar el escenario
    # Habilitar la interrupción V-Blank en el registro IE
    mmu.write(IO_IE, 0x01)  # Bit 0 = V-Blank
    # Activar el interruptor maestro de interrupciones
    cpu.ime = True
    
    # Escribir un programa simple: HALT seguido de NOPs
    mmu.write(0x0100, 0x76)  # HALT
    mmu.write(0x0101, 0x00)  # NOP
    mmu.write(0x0102, 0x00)  # NOP
    
    # Establecer PC al inicio del programa
    if hasattr(cpu, 'registers'):
        cpu.registers.pc = 0x0100
    else:
        # Si es PyCPU, necesitamos acceso a los registros a través de Viboy
        regs = viboy.registers
        if regs is not None:
            regs.pc = 0x0100
    
    # 3. Ejecutar la primera instrucción para entrar en HALT
    initial_pc = 0x0100
    cycles = viboy.tick()
    
    # Verificar que la CPU entró en HALT
    assert cpu.get_halted() == 1, "CPU debe estar en estado HALT después de ejecutar HALT"
    
    # Verificar que PC avanzó (HALT consume 1 M-Cycle y avanza PC)
    if hasattr(cpu, 'registers'):
        assert cpu.registers.pc == 0x0101, "PC debe avanzar después de HALT"
    else:
        regs = viboy.registers
        if regs is not None:
            assert regs.pc == 0x0101, "PC debe avanzar después de HALT"
    
    # 4. Simular la ejecución hasta que ocurra V-Blank y la CPU despierte
    # Corremos casi un frame completo. La PPU debería generar un V-Blank
    # y la CPU debería despertarse.
    max_iterations = CYCLES_PER_FRAME * 2  # Límite de seguridad
    iteration = 0
    cpu_woke_up = False
    
    while iteration < max_iterations:
        # Ejecutar un tick del emulador
        viboy.tick()
        
        # Verificar si la CPU se despertó
        if cpu.get_halted() == 0:
            cpu_woke_up = True
            break
        
        iteration += 1
    
    # 5. Verificar
    assert cpu_woke_up, (
        f"La CPU debería haberse despertado por la interrupción V-Blank "
        f"después de {iteration} iteraciones (máximo: {max_iterations})"
    )
    assert cpu.get_halted() == 0, "La CPU debe estar despierta (halted=0)"


@pytest.mark.skipif(not CPP_CORE_AVAILABLE, reason="Módulo viboy_core no compilado")
def test_halt_continues_calling_step():
    """
    Test auxiliar: Verificar que el bucle principal sigue llamando a cpu.step()
    incluso cuando la CPU está en HALT.
    
    Este test valida que la corrección del Step 0173 funciona correctamente:
    el bucle principal debe siempre llamar a cpu.step() para permitir que
    handle_interrupts() pueda despertar la CPU.
    """
    # Inicializar componentes directamente
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    
    # Configurar interrupciones
    mmu.write(IO_IE, 0x01)  # Habilitar V-Blank
    cpu.ime = True
    
    # Escribir HALT
    mmu.write(0x0100, 0x76)  # HALT
    regs.pc = 0x0100
    
    # Ejecutar HALT
    cycles = cpu.step()
    assert cycles == 1, "HALT debe consumir 1 M-Cycle"
    assert cpu.get_halted() == 1, "CPU debe estar en HALT"
    
    # Simular múltiples llamadas a step() mientras está en HALT
    # Cada llamada debe consumir 1 M-Cycle y permitir que handle_interrupts()
    # compruebe si hay interrupciones pendientes
    for i in range(10):
        cycles = cpu.step()
        assert cycles == 1, f"En HALT, cada step() debe consumir 1 M-Cycle (iteración {i})"
        assert cpu.get_halted() == 1, f"CPU debe seguir en HALT hasta que haya interrupción (iteración {i})"
    
    # Simular V-Blank: establecer bit 0 en IF
    mmu.write(IO_IF, 0x01)
    
    # La siguiente llamada a step() debe despertar la CPU
    cycles = cpu.step()
    assert cpu.get_halted() == 0, "CPU debe despertarse cuando hay interrupción pendiente"

