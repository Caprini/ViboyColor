#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0437: Diagnóstico de PPU Clock
Verifica por qué LY no avanza: analiza ciclos retornados por CPU y clock_ del PPU
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
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[DIAGNOSE-0437] Cargando ROM: {rom_path}")
    
    try:
        with open(rom_path, "rb") as f:
            rom_bytes = f.read()
    except FileNotFoundError:
        print(f"ERROR: ROM no encontrada")
        sys.exit(1)
    
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # Cargar ROM
    mmu.load_rom_py(rom_bytes)
    
    # Estado post-boot DMG
    regs.a = 0x01
    regs.b = 0x00
    regs.c = 0x13
    regs.d = 0x00
    regs.e = 0xD8
    regs.h = 0x01
    regs.l = 0x4D
    regs.sp = 0xFFFE
    regs.pc = 0x0100
    
    # I/O
    mmu.write(0xFF05, 0x00)
    mmu.write(0xFF06, 0x00)
    mmu.write(0xFF07, 0x00)
    mmu.write(0xFF10, 0x80)
    mmu.write(0xFF11, 0xBF)
    mmu.write(0xFF12, 0xF3)
    mmu.write(0xFF14, 0xBF)
    mmu.write(0xFF16, 0x3F)
    mmu.write(0xFF17, 0x00)
    mmu.write(0xFF19, 0xBF)
    mmu.write(0xFF1A, 0x7F)
    mmu.write(0xFF1B, 0xFF)
    mmu.write(0xFF1C, 0x9F)
    mmu.write(0xFF1E, 0xBF)
    mmu.write(0xFF20, 0xFF)
    mmu.write(0xFF21, 0x00)
    mmu.write(0xFF22, 0x00)
    mmu.write(0xFF23, 0xBF)
    mmu.write(0xFF24, 0x77)
    mmu.write(0xFF25, 0xF3)
    mmu.write(0xFF26, 0xF1)
    mmu.write(0xFF40, 0x91)
    mmu.write(0xFF42, 0x00)
    mmu.write(0xFF43, 0x00)
    mmu.write(0xFF45, 0x00)
    mmu.write(0xFF47, 0xFC)
    mmu.write(0xFF48, 0xFF)
    mmu.write(0xFF49, 0xFF)
    mmu.write(0xFF4A, 0x00)
    mmu.write(0xFF4B, 0x00)
    mmu.write(0xFFFF, 0x00)
    
    print("[DIAGNOSE-0437] Ejecutando hasta PC=0x006B...")
    
    # Ejecutar hasta llegar al loop
    for _ in range(100000):
        if regs.pc == 0x006B:
            break
        cpu.step()
        ppu.step(4)
    
    if regs.pc != 0x006B:
        print(f"ERROR: No se alcanzó PC=0x006B")
        sys.exit(1)
    
    print(f"[DIAGNOSE-0437] Alcanzó PC=0x006B")
    print(f"[DIAGNOSE-0437] LY inicial: {mmu.read(0xFF44)}")
    
    # Ejecutar 1000 iteraciones y monitorear ciclos
    print(f"\n[DIAGNOSE-0437] Monitoreando 1000 iteraciones:")
    print(f"ITER | PC   | CYCLES_RET | TOTAL_CYC | LY   | LCDC")
    print(f"-----+------+------------+-----------+------+-----")
    
    total_cycles = 0
    for i in range(1000):
        pc = regs.pc
        cycles_ret = cpu.step()
        total_cycles += cycles_ret
        
        # Pasar ciclos al PPU
        ppu.step(cycles_ret)
        
        ly = mmu.read(0xFF44)
        lcdc = mmu.read(0xFF40)
        
        if i < 50 or i % 100 == 0:
            print(f"{i:4d} | {pc:04X} | {cycles_ret:10d} | {total_cycles:9d} | {ly:4d} | {lcdc:02X}")
        
        # Si LY cambia, reportarlo
        if i > 0 and ly != mmu.read(0xFF44):
            print(f"\n*** LY CHANGED at iteration {i}: {ly} ***\n")
    
    print(f"\n[DIAGNOSE-0437] Resultado:")
    print(f"  Total cycles ejecutados: {total_cycles}")
    print(f"  LY final: {mmu.read(0xFF44)}")
    print(f"  Esperado: LY debería incrementar cada 456 T-cycles")
    print(f"  Incrementos de LY esperados: {total_cycles // 456}")
    
    # Verificar si el LCD está activado
    lcdc_final = mmu.read(0xFF40)
    lcd_on = (lcdc_final & 0x80) != 0
    print(f"  LCD enabled: {lcd_on}")
    
    if total_cycles > 10000 and mmu.read(0xFF44) == 0:
        print(f"\n⚠️  BUG CONFIRMADO: LY stuck en 0 después de {total_cycles} T-cycles")

if __name__ == "__main__":
    main()

