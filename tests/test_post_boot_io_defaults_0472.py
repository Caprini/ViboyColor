#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para Step 0472: Verificación de Power-Up Defaults cuando NO hay Boot ROM.

Este test verifica que los registros I/O están inicializados correctamente
a valores post-boot cuando se crea una MMU sin boot ROM (modo skip boot).

Fuente: Pan Docs - Power Up Sequence
https://gbdev.gg8.se/wiki/articles/Power_Up_Sequence
"""

import pytest
from viboy_core import PyMMU


def test_post_boot_io_defaults_dmg():
    """
    Verifica que los registros I/O post-boot están correctos en modo DMG.
    
    Valores esperados según Pan Docs (Power Up Sequence):
    - FF40 (LCDC): 0x91
    - FF42 (SCY): 0x00
    - FF43 (SCX): 0x00
    - FF47 (BGP): 0xFC
    - FF48 (OBP0): 0xFF
    - FF49 (OBP1): 0xFF
    - FFFF (IE): 0x00
    """
    mmu = PyMMU()
    mmu.set_hardware_mode("DMG")
    
    # Verificar registros críticos para "pantalla blanca"
    assert mmu.read(0xFF40) == 0x91, "LCDC debe ser 0x91 post-boot"
    assert mmu.read(0xFF42) == 0x00, "SCY debe ser 0x00 post-boot"
    assert mmu.read(0xFF43) == 0x00, "SCX debe ser 0x00 post-boot"
    assert mmu.read(0xFF47) == 0xFC, "BGP debe ser 0xFC post-boot"
    assert mmu.read(0xFF48) == 0xFF, "OBP0 debe ser 0xFF post-boot"
    assert mmu.read(0xFF49) == 0xFF, "OBP1 debe ser 0xFF post-boot"
    assert mmu.read(0xFFFF) == 0x00, "IE debe ser 0x00 post-boot"


def test_post_boot_io_defaults_cgb():
    """
    Verifica que los registros I/O post-boot están correctos en modo CGB.
    
    Además de los valores DMG, CGB tiene registros adicionales:
    - FF4D (KEY1): 0x00 (modo normal, no double-speed)
    - FF4F (VBK): 0x00 (banco VRAM 0)
    - FF70 (SVBK): 0x01 (banco WRAM 1)
    """
    mmu = PyMMU()
    mmu.set_hardware_mode("CGB")
    
    # Verificar registros comunes
    assert mmu.read(0xFF40) == 0x91, "LCDC debe ser 0x91 post-boot"
    assert mmu.read(0xFF47) == 0xFC, "BGP debe ser 0xFC post-boot"
    assert mmu.read(0xFF48) == 0xFF, "OBP0 debe ser 0xFF post-boot"
    assert mmu.read(0xFF49) == 0xFF, "OBP1 debe ser 0xFF post-boot"
    assert mmu.read(0xFFFF) == 0x00, "IE debe ser 0x00 post-boot"
    
    # Verificar registros CGB
    assert mmu.read(0xFF4D) == 0x00, "KEY1 debe ser 0x00 post-boot (modo normal)"
    # VBK lectura especial: devuelve 0xFE | banco_actual (según Pan Docs)
    # Con banco inicial 0: 0xFE | 0x00 = 0xFE
    assert mmu.read(0xFF4F) == 0xFE, "VBK debe ser 0xFE post-boot (0xFE | banco 0)"
    assert mmu.read(0xFF70) == 0x01, "SVBK debe ser 0x01 post-boot (banco 1)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

