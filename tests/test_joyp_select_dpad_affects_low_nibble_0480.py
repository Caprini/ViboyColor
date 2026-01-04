#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0480: Verificar que seleccionar fila de direcciones afecta el nibble bajo.

Según Pan Docs, escribir JOYP = 0x10 (P14=1, seleccionar fila de direcciones) debe
hacer que los bits 0-3 reflejen el estado de los botones de dirección.

Fuente: Pan Docs - Joypad Input, P1 Register
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad


def test_joyp_select_dpad_affects_low_nibble():
    """
    Verifica que seleccionar fila de direcciones afecta el nibble bajo.
    
    Pasos:
    1. Inicializar sistema mínimo
    2. Escribir JOYP = 0x10 (seleccionar fila de direcciones, P14=1)
    3. Leer JOYP
    4. Assert: bits 0-3 reflejan estado de direcciones (1 = no presionado, 0 = presionado)
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
    
    # Paso 1: Escribir JOYP = 0x20 (seleccionar fila de direcciones, P14=0, P15=1)
    # 0x20 = 0b00100000 (bit 4=0, bit 5=1, bits 6-7=0 pero se ponen a 1 en read)
    # bit 4=0 selecciona fila de dirección
    mmu.write(0xFF00, 0x20)
    
    # Paso 2: Leer JOYP
    joyp_value = mmu.read(0xFF00)
    
    # Paso 3: Verificar que bits 0-3 reflejan estado de direcciones
    # Con sin input, todos deben ser 1 (no presionados)
    bits_0_3 = joyp_value & 0x0F
    assert bits_0_3 == 0x0F, (
        f"Bits 0-3 deben ser 1 (todos sueltos) con sin input, "
        f"pero se leyeron como 0x{bits_0_3:02X}. Valor completo: 0x{joyp_value:02X}"
    )
    
    # Paso 4: Verificar que bits 6-7 son 1 (siempre)
    bits_6_7 = joyp_value & 0xC0
    assert bits_6_7 == 0xC0, (
        f"Bits 6-7 deben ser 1 (siempre), "
        f"pero se leyeron como 0x{bits_6_7:02X}. Valor completo: 0x{joyp_value:02X}"
    )
    
    # Paso 5: Presionar Right (índice 0) y verificar que bit 0 cambia a 0
    joypad.press_button(0)  # Right
    joyp_value_pressed = mmu.read(0xFF00)
    bit_0 = joyp_value_pressed & 0x01
    assert bit_0 == 0x00, (
        f"Bit 0 debe ser 0 (presionado) cuando se presiona Right, "
        f"pero se leyó como {bit_0}. Valor completo: 0x{joyp_value_pressed:02X}"
    )
    
    # Paso 6: Soltar Right y verificar que bit 0 vuelve a 1
    joypad.release_button(0)
    joyp_value_released = mmu.read(0xFF00)
    bit_0 = joyp_value_released & 0x01
    assert bit_0 == 0x01, (
        f"Bit 0 debe ser 1 (suelto) cuando se suelta Right, "
        f"pero se leyó como {bit_0}. Valor completo: 0x{joyp_value_released:02X}"
    )

