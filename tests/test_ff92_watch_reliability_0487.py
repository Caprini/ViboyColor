"""
Step 0487: Test Clean-Room de Fiabilidad del Watch FF92

Verifica que el watch de FF92 cuenta correctamente writes/reads
usando el Single Source of Truth (contadores cumulativos).
"""

import os
import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


def test_ff92_watch_reliability():
    """Verifica que el watch de FF92 cuenta correctamente writes/reads"""
    # Activar debug
    os.environ["VIBOY_DEBUG_MARIO_FF92"] = "1"
    
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # Write a 0xFF92
    mmu.write(0xFF92, 0xAB)
    
    # Read de 0xFF92
    val = mmu.read(0xFF92)
    
    # Verificar contadores
    write_count = mmu.get_ff92_write_count_total()
    read_count = mmu.get_ff92_read_count_total()
    last_write_val = mmu.get_ff92_last_write_val()
    last_read_val = mmu.get_ff92_last_read_val()
    
    assert write_count == 1, f"FF92 write_count debe ser 1, pero es {write_count}"
    assert read_count == 1, f"FF92 read_count debe ser 1, pero es {read_count}"
    assert last_write_val == 0xAB, f"FF92 last_write_val debe ser 0xAB, pero es {last_write_val:02X}"
    assert last_read_val == 0xAB, f"FF92 last_read_val debe ser 0xAB, pero es {last_read_val:02X}"
    assert val == 0xAB, f"FF92 read debe devolver 0xAB, pero es {val:02X}"


def test_ff92_watch_multiple_operations():
    """Verifica que los contadores son cumulativos (no se resetean)"""
    # Activar debug
    os.environ["VIBOY_DEBUG_MARIO_FF92"] = "1"
    
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # Múltiples writes
    mmu.write(0xFF92, 0x01)
    mmu.write(0xFF92, 0x02)
    mmu.write(0xFF92, 0x03)
    
    # Múltiples reads
    mmu.read(0xFF92)
    mmu.read(0xFF92)
    
    # Verificar contadores cumulativos
    write_count = mmu.get_ff92_write_count_total()
    read_count = mmu.get_ff92_read_count_total()
    
    assert write_count == 3, f"FF92 write_count debe ser 3, pero es {write_count}"
    assert read_count == 2, f"FF92 read_count debe ser 2, pero es {read_count}"
    assert mmu.get_ff92_last_write_val() == 0x03, "Último write debe ser 0x03"
