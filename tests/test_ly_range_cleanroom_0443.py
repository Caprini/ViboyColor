"""
Test Clean-Room: LY Range Validation (Step 0443)

Valida que LY avanza correctamente durante frames con LCD on.
No requiere ROM comercial, solo inicializa sistema y ejecuta frames.

Referencias:
    - Pan Docs: LCD Status Register (0xFF44 = LY)
    - Step 0443: Resolver ambigüedad LY sampling vs bug real
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


def test_ly_range_with_lcd_on():
    """Valida que LY cubre rango >= 10 y varía durante frames."""
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    # Wiring
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Activar LCD (LCDC bit 7 = 1)
    mmu.write(0xFF40, 0x80)
    
    # Ejecutar 2 frames completos (70224 T-cycles cada uno)
    CYCLES_PER_FRAME = 70224
    ly_samples = []
    
    for frame in range(2):
        frame_cycles = 0
        while frame_cycles < CYCLES_PER_FRAME:
            cycles = cpu.step()
            ppu.step(cycles)
            timer.step(cycles)
            frame_cycles += cycles
            
            # Samplear LY cada ~1000 T-cycles (aprox 70 muestras por frame)
            if frame_cycles % 1000 == 0:
                ly = mmu.read(0xFF44)
                ly_samples.append(ly)
    
    # Validaciones
    assert len(ly_samples) > 0, "No se recolectaron muestras de LY"
    max_ly = max(ly_samples)
    min_ly = min(ly_samples)
    unique_ly = len(set(ly_samples))
    
    assert max_ly >= 10, f"LY máximo ({max_ly}) debe ser >= 10 con LCD on"
    assert unique_ly > 1, f"LY debe variar (únicos: {unique_ly}), pero todos son {ly_samples[0]}"
    
    # Diagnóstico adicional
    print(f"LY range: {min_ly}..{max_ly}, únicos: {unique_ly}")

