#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0474: Verificar que IF puede limpiarse manualmente.

Este test verifica que cuando se escribe un valor a IF, ese valor se refleja
correctamente en la lectura (con bits 5-7 forzados a 1). Esto es crítico
para que los juegos puedan limpiar bits de interrupción manualmente.

Fuente: Pan Docs - Interrupt Flag Register (IF)
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad


def test_if_clear_manual():
    """
    Verifica que IF puede limpiarse manualmente escribiendo 0x00.
    
    Pasos:
    1. Inicializar sistema mínimo
    2. Forzar IF con bits (ej. IF = 0x1F en lowbits)
    3. Leer IF → debe ser 0xFF (0xE0 | 0x1F)
    4. Escribir IF = 0x00 (limpiar manualmente)
    5. Leer IF → debe ser 0xE0 (upper bits = 1, lowbits = 0)
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
    
    # Paso 1: Forzar IF con todos los bits bajos activos
    mmu.write(0xFF0F, 0x1F)
    
    # Paso 2: Leer IF → debe ser 0xFF (0xE0 | 0x1F)
    if_value = mmu.read(0xFF0F)
    assert if_value == 0xFF, f"IF debe ser 0xFF después de escribir 0x1F, pero se leyó 0x{if_value:02X}"
    
    # Paso 3: Escribir IF = 0x00 (limpiar manualmente)
    mmu.write(0xFF0F, 0x00)
    
    # Paso 4: Leer IF → debe ser 0xE0 (upper bits = 1, lowbits = 0)
    if_value = mmu.read(0xFF0F)
    assert if_value == 0xE0, f"IF debe ser 0xE0 después de escribir 0x00, pero se leyó 0x{if_value:02X}"
    
    # Verificar que bits bajos (0-4) están en 0
    low_bits = if_value & 0x1F
    assert low_bits == 0x00, f"Bits 0-4 deben ser 0 después de clear, pero se leyeron 0x{low_bits:02X}"


def test_if_clear_specific_bits():
    """
    Verifica que se pueden limpiar bits específicos de IF.
    """
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Activar todos los bits bajos
    mmu.write(0xFF0F, 0x1F)
    if_value = mmu.read(0xFF0F)
    assert if_value == 0xFF, "IF debe tener todos los bits bajos activos"
    
    # Limpiar solo el bit 0 (VBlank)
    mmu.write(0xFF0F, 0x1E)  # 0x1E = bits 1-4 activos, bit 0 = 0
    if_value = mmu.read(0xFF0F)
    expected = 0xE0 | 0x1E  # 0xFE
    assert if_value == expected, f"IF debe ser 0x{expected:02X} después de limpiar bit 0, pero se leyó 0x{if_value:02X}"
    
    # Verificar que bit 0 está en 0
    assert (if_value & 0x01) == 0, "Bit 0 (VBlank) debe estar en 0"
    
    # Verificar que bits 1-4 siguen activos
    assert (if_value & 0x1E) == 0x1E, "Bits 1-4 deben seguir activos"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

