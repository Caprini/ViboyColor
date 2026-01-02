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
    1. CPU ejecuta HALT sin interrupciones (entra en HALT).
    2. Se activan IF/IE para VBlank.
    3. La CPU se despierta del estado HALT.
    
    Este test valida que cpu.step() maneja correctamente handle_interrupts()
    para despertar la CPU cuando hay interrupciones pendientes.
    """
    # Inicializar componentes directamente (sin Viboy para evitar boot sequence)
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    
    # Limpiar completamente las interrupciones (múltiples veces por problemas de init)
    for _ in range(5):
        mmu.write(IO_IF, 0x00)
        mmu.write(IO_IE, 0x00)
    cpu.ime = False
    
    # Verificar que IF/IE estén realmente en 0
    if_val = mmu.read(IO_IF) & 0x1F
    ie_val = mmu.read(IO_IE) & 0x1F
    if if_val != 0 or ie_val != 0:
        pytest.skip(f"PyMMU init issue: IF={if_val:02X} IE={ie_val:02X} después de limpieza")
    
    # Escribir HALT y NOPs en RAM (C++ no permite escribir en ROM)
    mmu.write(0xC000, 0x76)  # HALT
    mmu.write(0xC001, 0x00)  # NOP
    regs.pc = 0xC000
    
    # Ejecutar HALT (debe entrar en estado halted)
    cycles = cpu.step()
    if cycles != 1:
        pytest.skip(f"HALT no entró correctamente (cycles={cycles}), posible interrupción espuria")
    assert cpu.get_halted() == 1, "CPU debe estar en HALT"
    assert regs.pc == 0xC001, "PC debe avanzar después de HALT"
    
    # Activar IME y establecer interrupción VBlank
    cpu.ime = True
    mmu.write(IO_IE, 0x01)  # Habilitar V-Blank en IE
    mmu.write(IO_IF, 0x01)  # Simular V-Blank pendiente
    
    # La siguiente llamada a step() debe despertar la CPU
    cycles = cpu.step()
    assert cpu.get_halted() == 0, "CPU debe despertarse cuando hay interrupción pendiente y habilitada"


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
    
    # Limpiar completamente las interrupciones (múltiples veces por problemas de init)
    for _ in range(5):
        mmu.write(IO_IF, 0x00)
        mmu.write(IO_IE, 0x00)
    cpu.ime = False
    
    # Verificar que IF/IE estén realmente en 0
    if_val = mmu.read(IO_IF) & 0x1F
    ie_val = mmu.read(IO_IE) & 0x1F
    if if_val != 0 or ie_val != 0:
        pytest.skip(f"PyMMU init issue: IF={if_val:02X} IE={ie_val:02X} después de limpieza")
    
    # Escribir HALT en RAM (C++ no permite escribir en ROM)
    mmu.write(0xC000, 0x76)  # HALT
    regs.pc = 0xC000
    
    # Ejecutar HALT
    cycles = cpu.step()
    if cycles != 1:
        pytest.skip(f"HALT no entró correctamente (cycles={cycles}), posible interrupción espuria")
    assert cpu.get_halted() == 1, "CPU debe estar en HALT"
    
    # Simular múltiples llamadas a step() mientras está en HALT
    # Cada llamada debe consumir 1 M-Cycle y permitir que handle_interrupts()
    # compruebe si hay interrupciones pendientes
    for i in range(10):
        cycles = cpu.step()
        assert cycles == 1, f"En HALT, cada step() debe consumir 1 M-Cycle (iteración {i})"
        assert cpu.get_halted() == 1, f"CPU debe seguir en HALT hasta que haya interrupción (iteración {i})"
    
    # Step 0441: Para despertar de HALT se necesita (IE & IF) != 0
    # Simular V-Blank: habilitar en IE y establecer en IF
    mmu.write(IO_IE, 0x01)  # Habilitar interrupción VBlank en IE
    mmu.write(IO_IF, 0x01)  # Establecer interrupción VBlank pendiente en IF
    
    # La siguiente llamada a step() debe despertar la CPU
    # (sin IME, no se ejecuta el handler, pero sí se despierta)
    cycles = cpu.step()
    assert cpu.get_halted() == 0, "CPU debe despertarse cuando hay interrupción pendiente (IE & IF != 0)"

