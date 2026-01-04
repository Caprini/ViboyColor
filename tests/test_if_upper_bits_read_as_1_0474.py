#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0474: Verificar que los bits superiores (5-7) de IF (0xFF0F) leen como 1.

Según Pan Docs, los bits 5-7 del registro IF siempre leen como 1, independientemente
de su valor escrito. Esto es crítico para la semántica correcta de IF.

Fuente: Pan Docs - Interrupt Flag Register (IF)
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad


def test_if_upper_bits_read_as_1():
    """
    Verifica que los bits 5-7 de IF siempre leen como 1.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/CPU/PPU)
    2. Escribir IF = 0x00 (limpiar)
    3. Leer IF y assert: bits 5-7 = 1 (debe ser 0xE0 | lowbits)
    4. Escribir IF = 0x1F (todos los bits bajos)
    5. Leer IF y assert: debe ser 0xFF (0xE0 | 0x1F)
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
    
    # Paso 1: Escribir IF = 0x00 (limpiar)
    mmu.write(0xFF0F, 0x00)
    
    # Paso 2: Leer IF y verificar bits 5-7 = 1
    if_value = mmu.read(0xFF0F)
    upper_bits = if_value & 0xE0  # Bits 5-7
    assert upper_bits == 0xE0, f"Bits 5-7 deben ser 1, pero se leyeron como 0x{upper_bits:02X}. Valor completo: 0x{if_value:02X}"
    
    # El valor completo debe ser 0xE0 (bits 5-7 = 1, bits 0-4 = 0)
    assert if_value == 0xE0, f"IF debe ser 0xE0 cuando se escribe 0x00, pero se leyó 0x{if_value:02X}"
    
    # Paso 3: Escribir IF = 0x1F (todos los bits bajos activos)
    mmu.write(0xFF0F, 0x1F)
    
    # Paso 4: Leer IF y verificar que es 0xFF (0xE0 | 0x1F)
    if_value = mmu.read(0xFF0F)
    assert if_value == 0xFF, f"IF debe ser 0xFF cuando se escribe 0x1F, pero se leyó 0x{if_value:02X}"
    
    # Verificar que bits 5-7 siguen siendo 1
    upper_bits = if_value & 0xE0
    assert upper_bits == 0xE0, f"Bits 5-7 deben seguir siendo 1, pero se leyeron como 0x{upper_bits:02X}"


def test_if_upper_bits_persist_after_write():
    """
    Verifica que los bits 5-7 persisten como 1 incluso después de escribir valores que no los incluyen.
    """
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Escribir varios valores y verificar que bits 5-7 siempre son 1
    test_values = [0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F]
    
    for write_val in test_values:
        mmu.write(0xFF0F, write_val)
        read_val = mmu.read(0xFF0F)
        
        # Bits 5-7 deben ser siempre 1
        upper_bits = read_val & 0xE0
        assert upper_bits == 0xE0, f"Al escribir 0x{write_val:02X}, bits 5-7 deben ser 1, pero se leyeron 0x{upper_bits:02X}. Valor completo: 0x{read_val:02X}"
        
        # El valor leído debe ser (0xE0 | write_val)
        expected = 0xE0 | write_val
        assert read_val == expected, f"Al escribir 0x{write_val:02X}, se esperaba 0x{expected:02X} pero se leyó 0x{read_val:02X}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

