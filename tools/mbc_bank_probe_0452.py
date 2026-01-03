#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MBC Bank Probe (Step 0452)

Prueba determinista de mapping MBC: carga ROM real,
cambia bank y verifica que el byte leído en 0x4000
coincide con el ROM real.

Uso:
    python3 tools/mbc_bank_probe_0452.py <ROM_PATH>
"""

import sys
import random
from pathlib import Path

# Añadir directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad
    NATIVE_AVAILABLE = True
except ImportError:
    print("ERROR: viboy_core no disponible. Compilar primero.")
    print("  python3 setup.py build_ext --inplace")
    sys.exit(1)


def probe_mbc_banking(rom_path: Path, mbc_type: str) -> dict:
    """
    Prueba mapping MBC para un tipo específico.
    
    Args:
        rom_path: Ruta a ROM real
        mbc_type: "MBC1", "MBC3", "MBC5"
    
    Returns:
        dict con resultados: {bank: (expected, actual, match)}
    """
    # Leer ROM
    with open(rom_path, 'rb') as f:
        rom_data = f.read()
    
    # Obtener tamaño ROM del header (0x0148)
    rom_size_code = rom_data[0x0148]
    rom_size_map = {
        0x00: 2, 0x01: 4, 0x02: 8, 0x03: 16, 0x04: 32,
        0x05: 64, 0x06: 128, 0x07: 256, 0x08: 512
    }
    rom_banks = rom_size_map.get(rom_size_code, 2)
    
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Cargar ROM
    mmu.load_rom_py(rom_data)
    
    results = {}
    
    # Probar 5-10 banks aleatorios (dentro del tamaño)
    test_banks = sorted(random.sample(range(min(rom_banks, 128)), min(10, rom_banks)))
    
    for bank in test_banks:
        # Calcular byte esperado del ROM real
        # Bank N en 0x4000 corresponde a offset N*0x4000 + 0x0000 en ROM
        rom_offset = bank * 0x4000 + 0x0000
        if rom_offset < len(rom_data):
            expected = rom_data[rom_offset]
        else:
            expected = 0xFF  # Fuera de ROM
        
        # Cambiar bank según tipo MBC
        if mbc_type == "MBC1":
            # MBC1: 0x2000-0x3FFF selecciona bank (low 5 bits)
            bank_low5 = bank & 0x1F
            if bank_low5 == 0:
                bank_low5 = 1  # Bank 0 → Bank 1
            mmu.write(0x2000, bank_low5)
            
            # MBC1: 0x4000-0x5FFF selecciona high bits (si modo RAM banking)
            bank_high2 = (bank >> 5) & 0x03
            mmu.write(0x4000, bank_high2)
            
        elif mbc_type == "MBC3":
            # MBC3: similar a MBC1 pero sin modo RAM banking
            bank_low7 = bank & 0x7F
            if bank_low7 == 0:
                bank_low7 = 1
            mmu.write(0x2000, bank_low7)
            
        elif mbc_type == "MBC5":
            # MBC5: 0x2000-0x2FFF = low 8 bits, 0x3000-0x3FFF = high 1 bit
            bank_low8 = bank & 0xFF
            bank_high1 = (bank >> 8) & 0x01
            mmu.write(0x2000, bank_low8)
            mmu.write(0x3000, bank_high1)
        
        # Leer 0x4000 usando read() (el mapping ROM se hace dinámicamente en read())
        # read_raw() lee de memory_[] que no tiene el ROM mapeado
        actual = mmu.read(0x4000)
        
        match = (actual == expected)
        results[bank] = {
            'expected': expected,
            'actual': actual,
            'match': match
        }
        
        if not match:
            print(f"❌ Bank {bank}: esperado 0x{expected:02X}, obtenido 0x{actual:02X}")
        else:
            print(f"✅ Bank {bank}: 0x{expected:02X} (match)")
    
    return results


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 tools/mbc_bank_probe_0452.py <ROM_PATH>")
        sys.exit(1)
    
    rom_path = Path(sys.argv[1])
    if not rom_path.exists():
        print(f"ERROR: ROM no encontrada: {rom_path}")
        sys.exit(1)
    
    # Detectar tipo MBC del header (0x0147)
    with open(rom_path, 'rb') as f:
        rom_data = f.read(0x150)
    
    cart_type = rom_data[0x0147]
    
    # Mapear a tipo MBC
    mbc_type_map = {
        0x01: "MBC1", 0x02: "MBC1", 0x03: "MBC1",
        0x11: "MBC3", 0x12: "MBC3", 0x13: "MBC3",
        0x19: "MBC5", 0x1A: "MBC5", 0x1B: "MBC5",
    }
    mbc_type = mbc_type_map.get(cart_type, "UNKNOWN")
    
    if mbc_type == "UNKNOWN":
        print(f"⚠️ Tipo de cartucho 0x{cart_type:02X} no soportado en probe")
        sys.exit(1)
    
    print(f"Probing MBC banking: {rom_path.name} (type 0x{cart_type:02X}, MBC={mbc_type})")
    print("")
    
    results = probe_mbc_banking(rom_path, mbc_type)
    
    # Resumen
    matches = sum(1 for r in results.values() if r['match'])
    total = len(results)
    
    print("")
    print(f"Resultados: {matches}/{total} banks coinciden")
    
    if matches == total:
        print("✅ Mapping MBC funciona correctamente")
        sys.exit(0)
    else:
        print(f"❌ Mapping MBC roto: {total - matches} banks no coinciden")
        sys.exit(1)


if __name__ == "__main__":
    main()

