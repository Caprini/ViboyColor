"""
Tests para validar la generación de interrupciones STAT en la PPU.

Estos tests verifican que la PPU solicita correctamente interrupciones STAT
cuando se cumplen las condiciones configuradas en el registro STAT.
"""

import pytest
from viboy_core import PyPPU, PyMMU


def test_stat_hblank_interrupt():
    """Verifica que se solicita una interrupción STAT al entrar en Modo 0 (H-Blank)."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    mmu.write(0xFF40, 0x80)  # LCD ON

    # Habilitar interrupción de H-Blank en STAT (bit 3)
    mmu.write(0xFF41, 0x08)
    
    # Limpiar el registro IF
    mmu.write(0xFF0F, 0x00)

    # Avanzar PPU hasta justo antes de H-Blank (Modo 3)
    # Mode 2: 80 ciclos, Mode 3: 172 ciclos, total: 252 ciclos
    ppu.step(80 + 171)  # 251 ciclos (justo antes de H-Blank)
    assert ppu.mode == 3, f"Esperado modo 3, obtenido {ppu.mode}"
    assert mmu.read(0xFF0F) == 0x00, "IF no debería tener interrupciones antes de H-Blank"

    # Dar el último paso para entrar en H-Blank
    ppu.step(1)  # 1 ciclo más = 252 ciclos (entra en H-Blank)
    assert ppu.mode == 0, f"Esperado modo 0 (H-Blank), obtenido {ppu.mode}"
    
    # Verificar que la interrupción fue solicitada
    if_val = mmu.read(0xFF0F)
    assert (if_val & 0x02) != 0, f"El bit 1 (STAT) de IF debería estar activado. IF={if_val:02X}"


def test_stat_vblank_interrupt():
    """Verifica que se solicita una interrupción STAT al entrar en Modo 1 (V-Blank)."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    mmu.write(0xFF40, 0x80)  # LCD ON

    # Habilitar interrupción de V-Blank en STAT (bit 4)
    mmu.write(0xFF41, 0x10)
    
    # Limpiar el registro IF
    mmu.write(0xFF0F, 0x00)

    # Avanzar PPU hasta la línea 144 (inicio de V-Blank)
    # Cada línea tiene 456 ciclos, necesitamos 144 líneas
    for _ in range(144):
        ppu.step(456)
    
    assert ppu.ly == 144, f"Esperado LY=144, obtenido {ppu.ly}"
    assert ppu.mode == 1, f"Esperado modo 1 (V-Blank), obtenido {ppu.mode}"
    
    # Verificar que la interrupción STAT fue solicitada
    if_val = mmu.read(0xFF0F)
    assert (if_val & 0x02) != 0, f"El bit 1 (STAT) de IF debería estar activado. IF={if_val:02X}"
    
    # También debería estar activa la interrupción V-Blank (bit 0)
    assert (if_val & 0x01) != 0, f"El bit 0 (V-Blank) de IF debería estar activado. IF={if_val:02X}"


def test_stat_oam_search_interrupt():
    """Verifica que se solicita una interrupción STAT al entrar en Modo 2 (OAM Search)."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    mmu.write(0xFF40, 0x80)  # LCD ON

    # Habilitar interrupción de OAM Search en STAT (bit 5)
    mmu.write(0xFF41, 0x20)
    
    # Limpiar el registro IF
    mmu.write(0xFF0F, 0x00)

    # Avanzar PPU hasta el inicio de una nueva línea (Modo 2)
    # Completar una línea completa (456 ciclos) para llegar al inicio de la siguiente
    ppu.step(456)
    
    # Al inicio de la línea, deberíamos estar en Modo 2
    assert ppu.mode == 2, f"Esperado modo 2 (OAM Search), obtenido {ppu.mode}"
    
    # Verificar que la interrupción fue solicitada
    if_val = mmu.read(0xFF0F)
    assert (if_val & 0x02) != 0, f"El bit 1 (STAT) de IF debería estar activado. IF={if_val:02X}"


def test_stat_lyc_coincidence_interrupt():
    """Verifica que se solicita una interrupción STAT cuando LY == LYC."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    mmu.write(0xFF40, 0x80)  # LCD ON

    # Configurar LYC a 10
    ppu.set_lyc(10)
    
    # Habilitar interrupción de LYC=LY en STAT (bit 6)
    mmu.write(0xFF41, 0x40)
    
    # Limpiar el registro IF
    mmu.write(0xFF0F, 0x00)

    # Avanzar PPU hasta la línea 9 (justo antes de LYC)
    for _ in range(9):
        ppu.step(456)
    
    assert ppu.ly == 9, f"Esperado LY=9, obtenido {ppu.ly}"
    assert mmu.read(0xFF0F) == 0x00, "IF no debería tener interrupciones antes de LYC"

    # Avanzar una línea más para llegar a LY=10 (coincidencia con LYC)
    ppu.step(456)
    
    assert ppu.ly == 10, f"Esperado LY=10, obtenido {ppu.ly}"
    
    # Verificar que la interrupción fue solicitada
    if_val = mmu.read(0xFF0F)
    assert (if_val & 0x02) != 0, f"El bit 1 (STAT) de IF debería estar activado. IF={if_val:02X}"


def test_stat_interrupt_rising_edge():
    """Verifica que las interrupciones STAT solo se solicitan en rising edge (no continuamente)."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    mmu.write(0xFF40, 0x80)  # LCD ON

    # Habilitar interrupción de H-Blank en STAT (bit 3)
    mmu.write(0xFF41, 0x08)
    
    # Limpiar el registro IF
    mmu.write(0xFF0F, 0x00)

    # Avanzar hasta H-Blank (primera vez)
    ppu.step(252)  # Entrar en H-Blank
    assert ppu.mode == 0
    
    # Verificar que la interrupción fue solicitada
    if_val_1 = mmu.read(0xFF0F)
    assert (if_val_1 & 0x02) != 0, "Primera interrupción debería estar activa"
    
    # Limpiar IF manualmente (simulando que la CPU procesó la interrupción)
    mmu.write(0xFF0F, 0x00)
    
    # Avanzar más ciclos dentro del mismo H-Blank (sin cambiar de modo)
    ppu.step(100)  # Seguimos en H-Blank
    assert ppu.mode == 0
    
    # Verificar que NO se solicitó otra interrupción (no hay rising edge)
    if_val_2 = mmu.read(0xFF0F)
    assert (if_val_2 & 0x02) == 0, f"NO debería haber nueva interrupción en el mismo H-Blank. IF={if_val_2:02X}"


def test_cpu_ime_setter():
    """Verifica que el setter de IME funciona correctamente para los tests."""
    from viboy_core import PyCPU, PyRegisters
    
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # IME debería iniciar en False
    assert cpu.ime == False, "IME debería iniciar en False"
    
    # Establecer IME a True
    cpu.ime = True
    assert cpu.ime == True, "IME debería ser True después de setter"
    
    # Establecer IME a False
    cpu.ime = False
    assert cpu.ime == False, "IME debería ser False después de setter"

