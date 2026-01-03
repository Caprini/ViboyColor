"""
Test Clean-Room: OAM DMA Copy Correctness (Step 0444)

Valida que escribir a 0xFF46 copia correctamente 160 bytes
desde la dirección source (value << 8) a OAM (0xFE00-0xFE9F).
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


def test_dma_oam_copies_160_bytes():
    """Valida que DMA copia 160 bytes correctamente desde WRAM a OAM."""
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
    
    # Preparar patrón en WRAM (0xC000-0xC09F)
    # Patrón incremental: 0x00, 0x01, 0x02, ..., 0x9F
    source_base = 0xC000
    pattern = [i & 0xFF for i in range(160)]
    
    for i, byte_value in enumerate(pattern):
        mmu.write(source_base + i, byte_value)
    
    # Verificar que OAM está limpio (0xFE00-0xFE9F)
    for i in range(160):
        assert mmu.read(0xFE00 + i) == 0, f"OAM debe estar limpio, pero 0xFE00+{i} = {mmu.read(0xFE00 + i):02X}"
    
    # Activar DMA: escribir source page (0xC0) a 0xFF46
    dma_source_page = 0xC0  # Página alta de source_base (0xC000 >> 8)
    mmu.write(0xFF46, dma_source_page)
    
    # Verificar que DMA copió correctamente
    for i in range(160):
        expected = pattern[i]
        actual = mmu.read(0xFE00 + i)
        assert actual == expected, f"DMA copy falló en byte {i}: esperado 0x{expected:02X}, obtenido 0x{actual:02X}"
    
    # Verificar que source no cambió (DMA no modifica source)
    for i in range(160):
        assert mmu.read(source_base + i) == pattern[i], f"Source fue modificado en {i}: esperado 0x{pattern[i]:02X}"
    
    print(f"✅ DMA copió correctamente 160 bytes desde 0x{source_base:04X} a OAM (0xFE00-0xFE9F)")


def test_dma_oam_from_different_source():
    """Valida que DMA funciona desde diferentes sources (VRAM, ROM, etc.)."""
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Test desde WRAM alternativo (0xD000)
    source_base = 0xD000
    pattern = [0xAA + (i & 0x0F) for i in range(160)]
    
    for i, byte_value in enumerate(pattern):
        mmu.write(source_base + i, byte_value)
    
    dma_source_page = 0xD0
    mmu.write(0xFF46, dma_source_page)
    
    # Verificar copia
    for i in range(160):
        expected = pattern[i]
        actual = mmu.read(0xFE00 + i)
        assert actual == expected, f"DMA desde 0x{source_base:04X} falló en byte {i}"

