#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0438 T4: Test directo del clock de PPU
Verifica si la PPU está recibiendo y procesando ciclos correctamente
"""

import sys
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
except ImportError as e:
    print(f"ERROR: viboy_core no disponible: {e}")
    sys.exit(1)

def main():
    print("[TEST-PPU-CLOCK-0438] Test directo del clock de PPU")
    
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # CRÍTICO: Conectar PPU a MMU para que MMU pueda leer LY desde la PPU
    mmu.set_ppu(ppu)
    
    # Configurar LCDC para encender el LCD
    mmu.write(0xFF40, 0x91)  # LCDC: LCD ON, BG ON
    
    print(f"[TEST-PPU-CLOCK-0438] LCDC inicial: 0x{mmu.read(0xFF40):02X}")
    print(f"[TEST-PPU-CLOCK-0438] LY inicial: {mmu.read(0xFF44)}")
    
    # Test 1: Pasar ciclos directamente a la PPU
    print("\n[TEST-PPU-CLOCK-0438] Test 1: Pasar 1000 T-cycles a la PPU")
    for i in range(10):
        ppu.step(100)  # 100 T-cycles
        ly = mmu.read(0xFF44)
        print(f"  Iteración {i+1}: ppu.step(100 T-cycles) -> LY = {ly}")
    
    # Test 2: Verificar si LY avanza después de 456 T-cycles (1 scanline)
    print("\n[TEST-PPU-CLOCK-0438] Test 2: Pasar exactamente 456 T-cycles (1 scanline)")
    ly_before = mmu.read(0xFF44)
    ppu.step(456)  # 456 T-cycles = 1 scanline
    ly_after = mmu.read(0xFF44)
    print(f"  LY antes: {ly_before}, LY después: {ly_after}")
    print(f"  ¿LY incrementó? {ly_after > ly_before}")
    
    # Test 3: Verificar LCDC durante step
    print("\n[TEST-PPU-CLOCK-0438] Test 3: Verificar LCDC durante step")
    lcdc_before = mmu.read(0xFF40)
    ppu.step(100)  # 100 T-cycles
    lcdc_after = mmu.read(0xFF40)
    print(f"  LCDC antes: 0x{lcdc_before:02X}, LCDC después: 0x{lcdc_after:02X}")
    print(f"  LCD enabled (bit 7): {(lcdc_after & 0x80) != 0}")
    
    # Test 4: Ejecutar un frame completo (70224 T-cycles)
    print("\n[TEST-PPU-CLOCK-0438] Test 4: Ejecutar 1 frame completo (70224 T-cycles)")
    ly_start = mmu.read(0xFF44)
    total_cycles = 0
    while total_cycles < 70224:
        ppu.step(456)  # 456 T-cycles por scanline
        total_cycles += 456
    ly_end = mmu.read(0xFF44)
    print(f"  LY inicio: {ly_start}, LY fin: {ly_end}")
    print(f"  ¿LY completó un ciclo? {ly_end == 0 or ly_end == 153}")
    
    print("\n[TEST-PPU-CLOCK-0438] NOTA: Este test pasa T-cycles directamente.")
    print("[TEST-PPU-CLOCK-0438] En el emulador real, CPU.step() retorna M-Cycles que deben multiplicarse x4.")
    
    print("\n[TEST-PPU-CLOCK-0438] Test completado")

if __name__ == "__main__":
    main()

