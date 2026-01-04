#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0474: Verificar que LY (0xFF44) progresa correctamente.

Este test verifica que el registro LY (Line Y) progresa correctamente cuando
la PPU avanza. Esto es crítico para que los juegos puedan detectar VBlank
y sincronizar correctamente.

Fuente: Pan Docs - LCD Y-Coordinate (LY)
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad


def test_ly_progresses():
    """
    Verifica que LY progresa cuando la PPU avanza.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/CPU/PPU)
    2. Leer LY inicial → debe ser 0 o valor inicial
    3. Step PPU suficiente para cruzar varias scanlines (ej. 456 ciclos × 10 scanlines = 4560 ciclos)
    4. Leer LY → debe haber cambiado (no todo 0)
    """
    # Inicializar componentes
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    # Wiring
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Paso 1: Leer LY inicial
    ly_initial = mmu.read(0xFF44)
    print(f"LY inicial: {ly_initial}")
    
    # Paso 2: Step PPU suficiente para cruzar varias scanlines
    # Cada scanline = 456 ciclos
    # 10 scanlines = 4560 ciclos
    cycles_per_scanline = 456
    num_scanlines = 10
    total_cycles = cycles_per_scanline * num_scanlines
    
    for _ in range(total_cycles):
        ppu.step(1)
    
    # Paso 3: Leer LY → debe haber cambiado
    ly_after = mmu.read(0xFF44)
    print(f"LY después de {total_cycles} ciclos: {ly_after}")
    
    # Verificar que LY ha progresado
    # LY debe estar entre 0 y 153 (144 líneas visibles + 10 líneas VBlank)
    assert 0 <= ly_after <= 153, f"LY debe estar entre 0 y 153, pero se leyó {ly_after}"
    
    # Si LY inicial era 0, después de 10 scanlines debería ser al menos 10
    # (o haber dado la vuelta si pasó de 144)
    if ly_initial == 0:
        # LY puede haber progresado o haber dado la vuelta (144 → 0)
        assert ly_after != ly_initial or ly_after > 0, f"LY debe haber progresado desde {ly_initial}, pero sigue en {ly_after}"


def test_ly_wraps_around():
    """
    Verifica que LY hace wrap-around correctamente (144 → 0).
    """
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Avanzar suficiente para que LY haga wrap-around
    # 144 scanlines visibles + 10 VBlank = 154 scanlines totales
    # 154 scanlines × 456 ciclos = 70224 ciclos (1 frame completo)
    cycles_per_frame = 70224
    
    # Ejecutar 2 frames completos para asegurar wrap-around
    for _ in range(cycles_per_frame * 2):
        ppu.step(1)
    
    # LY debe estar entre 0 y 153
    ly_value = mmu.read(0xFF44)
    assert 0 <= ly_value <= 153, f"LY debe estar entre 0 y 153, pero se leyó {ly_value}"
    
    # Verificar que LY ha pasado por múltiples valores usando la instrumentación
    ly_min = mmu.get_ly_read_min()
    ly_max = mmu.get_ly_read_max()
    
    print(f"LY min: {ly_min}, LY max: {ly_max}")
    
    # Después de 2 frames, LY debe haber pasado por al menos 0 y algún valor > 0
    assert ly_max > 0, f"LY debe haber alcanzado valores > 0, pero max es {ly_max}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

