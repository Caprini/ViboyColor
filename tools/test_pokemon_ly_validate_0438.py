#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0438: Pokemon LY Validation - Tarea T1
Ejecuta Pokémon Red hasta el loop de espera VBlank y captura métricas:
- count_A_eq_0x91 (A==0x91 justo tras LDH A,(FF44))
- count_Z_after_CP (Z==1 justo tras CP $91)
- Histograma top-10 de valores de A

Salida: Las métricas se imprimen desde el núcleo C++ automáticamente
        Este script solo ejecuta y muestra el resumen final.
"""

import sys
import os
import time

# Añadir directorio raíz al path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
except ImportError as e:
    print(f"ERROR: viboy_core no disponible: {e}")
    print("Ejecuta: python setup.py build_ext --inplace")
    sys.exit(1)

def main():
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[STEP0438-T1] Cargando ROM: {rom_path}")
    
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
    
    # CRÍTICO Step 0438: Conectar PPU a MMU para que MMU pueda leer LY desde la PPU
    mmu.set_ppu(ppu)
    
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
    
    # Registros I/O (estado post-boot DMG)
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
    
    print("[STEP0438-T1] Ejecutando hasta alcanzar el loop VBlank (PC=0x006B...0x006F)")
    print("[STEP0438-T1] La instrumentación C++ imprimirá métricas automáticamente cada 10K iteraciones")
    print("[STEP0438-T1] Se ejecutarán aproximadamente 100 frames (~1.7 segundos)")
    
    max_frames = 100
    frame_cycles = 0
    frame_count = 0
    total_cycles = 0
    loop_reached = False
    start_time = time.time()
    
    # Ejecutar hasta llegar al loop
    for _ in range(500000):  # Suficiente para llegar al loop
        pc = regs.pc
        
        if pc in [0x006B, 0x006D, 0x006F] and not loop_reached:
            loop_reached = True
            print(f"\n[STEP0438-T1] *** Loop alcanzado en PC=0x{pc:04X} después de {frame_count} frames ***\n")
            break
        
        m_cycles = cpu.step()  # CPU retorna M-Cycles
        t_cycles = m_cycles * 4  # Convertir a T-Cycles
        total_cycles += t_cycles
        frame_cycles += t_cycles
        
        ppu.step(t_cycles)  # PPU espera T-Cycles
        
        # Contar frames
        if frame_cycles >= 70224:
            frame_cycles = 0
            frame_count += 1
    
    if not loop_reached:
        print(f"[STEP0438-T1] ERROR: No se alcanzó el loop después de {frame_count} frames")
        sys.exit(1)
    
    # Ejecutar 100 frames dentro del loop para capturar métricas
    print(f"[STEP0438-T1] Ejecutando {max_frames} frames dentro del loop para capturar métricas...")
    
    frame_cycles = 0
    frames_in_loop = 0
    instructions_in_loop = 0
    
    while frames_in_loop < max_frames:
        pc = regs.pc
        m_cycles = cpu.step()  # CPU retorna M-Cycles
        t_cycles = m_cycles * 4  # Convertir a T-Cycles para PPU
        total_cycles += t_cycles
        frame_cycles += t_cycles
        instructions_in_loop += 1
        
        ppu.step(t_cycles)  # PPU espera T-Cycles
        
        # Contar frames
        if frame_cycles >= 70224:
            frame_cycles = 0
            frames_in_loop += 1
            
            if frames_in_loop % 10 == 0:
                elapsed = time.time() - start_time
                print(f"[STEP0438-T1] Frame {frames_in_loop}/{max_frames} | Tiempo: {elapsed:.1f}s")
    
    elapsed = time.time() - start_time
    print(f"\n[STEP0438-T1] ==================== EJECUCIÓN COMPLETADA ====================")
    print(f"[STEP0438-T1] Total frames: {frame_count + frames_in_loop}")
    print(f"[STEP0438-T1] Frames en loop: {frames_in_loop}")
    print(f"[STEP0438-T1] Instrucciones en loop: {instructions_in_loop}")
    print(f"[STEP0438-T1] Tiempo total: {elapsed:.2f}s")
    print(f"[STEP0438-T1] PC final: 0x{regs.pc:04X}")
    print(f"[STEP0438-T1] LY final: {mmu.read(0xFF44)}")
    print(f"[STEP0438-T1] =============================================================\n")
    
    print("[STEP0438-T1] Las métricas detalladas fueron impresas por el núcleo C++ durante la ejecución.")
    print("[STEP0438-T1] Busca en la salida:")
    print("  - [STEP0438-SUMMARY] para resúmenes cada 10K iteraciones")
    print("  - [STEP0438-HISTOGRAM] para el histograma de valores de A")

if __name__ == "__main__":
    main()

