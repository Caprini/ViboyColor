"""
Test: Validar que write→read_raw funciona (Step 0452)

Valida que escribir a VRAM y leer con read_raw funciona correctamente.
Esto confirma que VRAM está en MMU.memory_[] y que read_raw() lee correctamente.
"""

import pytest
from viboy_core import PyMMU, PyPPU


def test_vram_write_read_raw_mmu():
    """Valida que escribir a VRAM y leer con read_raw funciona."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    
    # Escribir patrón no-cero en 0x8000-0x8010
    pattern = [0xAA, 0xBB, 0xCC, 0xDD]
    for i, byte_val in enumerate(pattern):
        mmu.write(0x8000 + i, byte_val)
    
    # Leer con read_raw (VRAM está en MMU)
    for i, expected in enumerate(pattern):
        actual = mmu.read_raw(0x8000 + i)
        assert actual == expected, (
            f"VRAM write→read_raw falló en 0x{0x8000+i:04X}: "
            f"esperado 0x{expected:02X}, obtenido 0x{actual:02X}"
        )
    
    print("✅ MMU.write→read_raw funciona correctamente")


def test_vram_write_read_raw_range():
    """Valida que dump_raw_range funciona correctamente."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    
    # Escribir patrón en 0x8000-0x8010
    pattern = [0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88]
    for i, byte_val in enumerate(pattern):
        mmu.write(0x8000 + i, byte_val)
    
    # Leer con dump_raw_range
    dumped = mmu.dump_raw_range(0x8000, len(pattern))
    
    assert len(dumped) == len(pattern), (
        f"dump_raw_range retornó tamaño incorrecto: "
        f"esperado {len(pattern)}, obtenido {len(dumped)}"
    )
    
    for i, expected in enumerate(pattern):
        actual = dumped[i]
        assert actual == expected, (
            f"dump_raw_range falló en offset {i}: "
            f"esperado 0x{expected:02X}, obtenido 0x{actual:02X}"
        )
    
    print("✅ MMU.dump_raw_range funciona correctamente")


def test_vram_nonzero_sampling():
    """Valida que podemos detectar bytes non-zero en VRAM usando read_raw."""
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    mmu.set_ppu(ppu)
    
    # Inicialmente VRAM debería estar vacía (o con valores por defecto)
    # Escribir algunos bytes non-zero
    mmu.write(0x8000, 0x01)
    mmu.write(0x8100, 0x02)
    mmu.write(0x8200, 0x03)
    
    # Muestrear VRAM cada 16 bytes (como hace headless)
    nonzero_count = 0
    for addr in range(0x8000, 0xA000, 16):
        value = mmu.read_raw(addr)
        if value != 0:
            nonzero_count += 1
    
    # Deberíamos detectar al menos 3 bytes non-zero
    assert nonzero_count >= 3, (
        f"VRAM nonzero sampling falló: esperado >= 3, obtenido {nonzero_count}"
    )
    
    print(f"✅ VRAM nonzero sampling detectó {nonzero_count} bytes non-zero")

