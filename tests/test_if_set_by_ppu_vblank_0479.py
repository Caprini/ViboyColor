#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0479: Verificar que IF bit0 se pone a 1 cuando PPU entra en VBlank.

Este test valida que PPU requestea VBlank correctamente, lo cual es crítico
para identificar si el loop espera IF bit0 pero este nunca llega (Caso 2 del plan).

Fuente: Pan Docs - Interrupts, V-Blank Interrupt
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad, PyCPU, PyRegisters


def test_if_set_by_ppu_vblank():
    """
    Verifica que IF bit0 se pone a 1 cuando PPU entra en VBlank.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/CPU/PPU/Timer)
    2. Encender LCD (LCDC bit 7 = 1)
    3. IE = 0x01 (VBlank habilitado)
    4. Step suficiente para que PPU entre en VBlank (LY=144)
    5. Assert:
       - IF bit0 == 1 (IF bit0 debe ponerse 1 al entrar en VBlank)
       - if_bit0_set_count_this_frame > 0
    
    Criterio de éxito: Test pasa. Si falla, PPU no está requesteando VBlank correctamente.
    """
    # Inicializar componentes
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
    cpu.set_ppu(ppu)
    cpu.set_timer(timer)
    
    # Paso 1: Encender LCD (LCDC bit 7 = 1)
    lcdc = mmu.read(0xFF40)
    lcdc |= 0x80  # Bit 7 = 1 (LCD Enable)
    mmu.write(0xFF40, lcdc)
    
    # Paso 2: IE = 0x01 (VBlank habilitado)
    mmu.write(0xFFFF, 0x01)  # IE bit 0 = 1 (VBlank interrupt enabled)
    
    # Paso 3: Limpiar IF (empezar con IF = 0x00)
    mmu.write(0xFF0F, 0x00)
    
    # Paso 4: Step suficiente para que PPU entre en VBlank (LY=144)
    # Necesitamos llegar a LY=144, que son 144 scanlines × 456 ciclos = 65,664 ciclos
    # Para ser seguro, ejecutamos 66,000 ciclos
    cycles_target = 144 * 456 + 1000  # 144 scanlines + margen
    cycles_accumulated = 0
    
    while cycles_accumulated < cycles_target:
        cycles = cpu.step()
        ppu.step(cycles)
        timer.step(cycles)
        cycles_accumulated += cycles
        
        # Verificar si ya llegamos a VBlank (LY >= 144)
        ly = mmu.read(0xFF44)
        if ly >= 144:
            break  # Ya llegamos a VBlank
    
    # Paso 5: Verificar que IF bit0 == 1
    if_reg = mmu.read(0xFF0F)
    if_bit0 = if_reg & 0x01
    
    assert if_bit0 == 1, f"IF bit0 debe ser 1 al entrar en VBlank, pero IF=0x{if_reg:02X} (bit0={if_bit0})."
    
    # Paso 6: Verificar contador de veces que IF bit0 se pone a 1 por frame
    if_bit0_set_count = mmu.get_if_bit0_set_count_this_frame()
    
    assert if_bit0_set_count > 0, f"if_bit0_set_count_this_frame debe ser > 0, pero es {if_bit0_set_count}. PPU no está requesteando VBlank."
    
    # Verificar que LY >= 144 (confirmamos que llegamos a VBlank)
    ly = mmu.read(0xFF44)
    assert ly >= 144, f"LY debe ser >= 144 (VBlank), pero es {ly}. No llegamos a VBlank."
    
    # Verificar que IE sigue siendo 0x01
    ie = mmu.read(0xFFFF)
    assert (ie & 0x01) == 0x01, f"IE bit0 debe seguir siendo 1, pero IE=0x{ie:02X}."


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

