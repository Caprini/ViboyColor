#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0436: Test de Pokemon Loop Trace
Ejecuta Pokémon Red con instrumentación para capturar evidencia del loop stuck.
"""

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
    NATIVE_AVAILABLE = True
except ImportError:
    print("ERROR: viboy_core no disponible. Compilar primero con: python3 setup.py build_ext --inplace")
    exit(1)

def main():
    # Cargar ROM Pokemon Red
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[TEST-0436] Cargando ROM: {rom_path}")
    
    with open(rom_path, "rb") as f:
        rom_bytes = f.read()
    
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # Cargar ROM
    mmu.load_rom_py(rom_bytes)
    
    # Configurar estado post-boot DMG
    regs.a = 0x01
    regs.b = 0x00
    regs.c = 0x13
    regs.d = 0x00
    regs.e = 0xD8
    regs.h = 0x01
    regs.l = 0x4D
    regs.sp = 0xFFFE
    regs.pc = 0x0100
    
    # Registros I/O post-boot
    mmu.write(0xFF05, 0x00)  # TIMA
    mmu.write(0xFF06, 0x00)  # TMA
    mmu.write(0xFF07, 0x00)  # TAC
    mmu.write(0xFF10, 0x80)  # NR10
    mmu.write(0xFF11, 0xBF)  # NR11
    mmu.write(0xFF12, 0xF3)  # NR12
    mmu.write(0xFF14, 0xBF)  # NR14
    mmu.write(0xFF16, 0x3F)  # NR21
    mmu.write(0xFF17, 0x00)  # NR22
    mmu.write(0xFF19, 0xBF)  # NR24
    mmu.write(0xFF1A, 0x7F)  # NR30
    mmu.write(0xFF1B, 0xFF)  # NR31
    mmu.write(0xFF1C, 0x9F)  # NR32
    mmu.write(0xFF1E, 0xBF)  # NR34
    mmu.write(0xFF20, 0xFF)  # NR41
    mmu.write(0xFF21, 0x00)  # NR42
    mmu.write(0xFF22, 0x00)  # NR43
    mmu.write(0xFF23, 0xBF)  # NR44
    mmu.write(0xFF24, 0x77)  # NR50
    mmu.write(0xFF25, 0xF3)  # NR51
    mmu.write(0xFF26, 0xF1)  # NR52
    mmu.write(0xFF40, 0x91)  # LCDC
    mmu.write(0xFF42, 0x00)  # SCY
    mmu.write(0xFF43, 0x00)  # SCX
    mmu.write(0xFF45, 0x00)  # LYC
    mmu.write(0xFF47, 0xFC)  # BGP
    mmu.write(0xFF48, 0xFF)  # OBP0
    mmu.write(0xFF49, 0xFF)  # OBP1
    mmu.write(0xFF4A, 0x00)  # WY
    mmu.write(0xFF4B, 0x00)  # WX
    mmu.write(0xFFFF, 0x00)  # IE
    
    print("[TEST-0436] Activando Pokemon Loop Trace (Fase A: VRAM writes)")
    mmu.set_pokemon_loop_trace(True)
    
    print("[TEST-0436] Activando Pokemon Micro Trace (Fase B: CPU trace)")
    cpu.set_pokemon_micro_trace(True)
    
    print("[TEST-0436] Ejecutando emulación por 60 segundos (timeout)...")
    
    # Ejecutar ~3M T-cycles (~42 frames) para alcanzar el loop stuck
    max_cycles = 3000000
    total_cycles = 0
    
    while total_cycles < max_cycles:
        cycles = cpu.step()
        ppu.step(cycles)
        total_cycles += cycles
    
    print(f"\n[TEST-0436] Emulación completada: {total_cycles} T-cycles ejecutados")
    
    # Desactivar traces
    mmu.set_pokemon_loop_trace(False)
    cpu.set_pokemon_micro_trace(False)
    
    # Generar resúmenes
    print("\n" + "=" * 80)
    print("RESUMEN DE EVIDENCIA - STEP 0436")
    print("=" * 80)
    
    cpu.log_pokemon_micro_trace_summary()
    
    print("\n[TEST-0436] Test completado")

if __name__ == "__main__":
    main()

