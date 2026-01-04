#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0480: Verificar que JOYP con sin input devuelve bits 0-1 en 1.

Según Pan Docs, cuando no hay botones presionados y no hay selección de fila,
los bits 0-3 deben ser 1 (todos sueltos). Con "sin input", la lectura debe
satisfacer fácilmente `& 0x03 == 0x03`.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad


def test_joyp_default_no_input_returns_1s():
    """
    Verifica que JOYP con sin input devuelve bits 0-1 en 1.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/Joypad)
    2. Sin input (estado por defecto)
    3. Leer JOYP (0xFF00)
    4. Assert: (joyp & 0x03) == 0x03 (bits 0-1 en 1 = no presionados)
    5. Assert: (joyp & 0xC0) == 0xC0 (bits 6-7 en 1)
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
    
    # Paso 1: Leer JOYP sin input (estado por defecto)
    joyp_value = mmu.read(0xFF00)
    
    # Paso 2: Verificar bits 0-1 en 1 (no presionados)
    bits_0_1 = joyp_value & 0x03
    assert bits_0_1 == 0x03, (
        f"Bits 0-1 deben ser 1 (no presionados) con sin input, "
        f"pero se leyeron como 0x{bits_0_1:02X}. Valor completo: 0x{joyp_value:02X}"
    )
    
    # Paso 3: Verificar bits 6-7 en 1 (siempre leen como 1)
    bits_6_7 = joyp_value & 0xC0
    assert bits_6_7 == 0xC0, (
        f"Bits 6-7 deben ser 1 (siempre), "
        f"pero se leyeron como 0x{bits_6_7:02X}. Valor completo: 0x{joyp_value:02X}"
    )
    
    # Verificación adicional: bits 0-3 deben ser 1 (todos sueltos por defecto)
    bits_0_3 = joyp_value & 0x0F
    assert bits_0_3 == 0x0F, (
        f"Bits 0-3 deben ser 1 (todos sueltos) con sin input, "
        f"pero se leyeron como 0x{bits_0_3:02X}. Valor completo: 0x{joyp_value:02X}"
    )

