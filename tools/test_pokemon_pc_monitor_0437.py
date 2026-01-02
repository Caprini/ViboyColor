#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0437: Pokemon PC Monitor
Monitorea dónde está ejecutándose el PC y detecta loops automáticamente.
"""

import sys
import os
import time
from collections import Counter, deque

# Añadir directorio raíz al path
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
except ImportError as e:
    print(f"ERROR: viboy_core no disponible: {e}")
    sys.exit(1)

class PCLoopDetector:
    """Detector genérico de loops basado en frecuencia de PC"""
    def __init__(self, window_size=10000):
        self.window_size = window_size
        self.pc_history = deque(maxlen=window_size)
        self.pc_counter = Counter()
        self.frame_count = 0
        
    def record(self, pc):
        """Registra un PC"""
        # Guardar en historial
        if len(self.pc_history) == self.window_size:
            old_pc = self.pc_history[0]
            self.pc_counter[old_pc] -= 1
            if self.pc_counter[old_pc] == 0:
                del self.pc_counter[old_pc]
        
        self.pc_history.append(pc)
        self.pc_counter[pc] += 1
    
    def detect_loops(self, threshold=0.5):
        """
        Detecta loops: si un pequeño rango de PC representa >threshold del total
        Retorna: (is_loop, loop_pcs, percentage)
        """
        if len(self.pc_history) < 1000:
            return False, [], 0.0
        
        # Buscar los top 10 PC más frecuentes
        top_pcs = self.pc_counter.most_common(10)
        top_count = sum(count for pc, count in top_pcs)
        percentage = top_count / len(self.pc_history)
        
        if percentage > threshold:
            loop_pcs = [pc for pc, count in top_pcs]
            return True, loop_pcs, percentage
        
        return False, [], percentage
    
    def print_summary(self):
        """Imprime resumen de ejecución"""
        print(f"\n[PC-MONITOR] Total instructions recorded: {len(self.pc_history)}")
        print(f"[PC-MONITOR] Unique PC values: {len(self.pc_counter)}")
        print(f"\n[PC-MONITOR] Top 20 most frequent PC values:")
        for i, (pc, count) in enumerate(self.pc_counter.most_common(20), start=1):
            pct = (count * 100.0) / len(self.pc_history)
            print(f"  {i:2d}. PC=0x{pc:04X}: {count:7d} times ({pct:6.2f}%)")


def main():
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[PC-MONITOR-0437] Cargando ROM: {rom_path}")
    
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
    
    # Registros I/O
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
    
    print("[PC-MONITOR-0437] Monitoreando ejecución...")
    print("[PC-MONITOR-0437] Se ejecutarán 2000 frames (~28 segundos)")
    print("[PC-MONITOR-0437] Buscando loops automáticamente...")
    
    detector = PCLoopDetector(window_size=10000)
    
    max_frames = 2000
    frame_cycles = 0
    frame_count = 0
    total_cycles = 0
    
    last_report_time = time.time()
    loop_detected = False
    loop_start_frame = None
    
    while frame_count < max_frames:
        pc = regs.pc
        detector.record(pc)
        
        cycles = cpu.step()
        total_cycles += cycles
        frame_cycles += cycles
        
        ppu.step(cycles)
        
        # Contar frames
        if frame_cycles >= 70224:
            frame_cycles = 0
            frame_count += 1
            detector.frame_count = frame_count
            
            # Detectar loops cada 100 frames
            if frame_count % 100 == 0:
                is_loop, loop_pcs, pct = detector.detect_loops(threshold=0.3)
                
                now = time.time()
                elapsed = now - last_report_time
                last_report_time = now
                
                print(f"\n[PC-MONITOR-0437] Frame {frame_count} | {elapsed:.1f}s")
                print(f"  Unique PCs (last 10K instr): {len(detector.pc_counter)}")
                print(f"  Top 3 PCs: ", end="")
                for pc_val, count in detector.pc_counter.most_common(3):
                    pct_val = (count * 100.0) / len(detector.pc_history)
                    print(f"0x{pc_val:04X}({pct_val:.1f}%) ", end="")
                print()
                
                if is_loop and not loop_detected:
                    loop_detected = True
                    loop_start_frame = frame_count
                    print(f"\n*** LOOP DETECTED at frame {frame_count} ***")
                    print(f"  Loop PCs (top 10): {[f'0x{pc:04X}' for pc in loop_pcs]}")
                    print(f"  Coverage: {pct*100:.1f}% of recent instructions")
                
                # Si detectamos loop, ejecutar 200 frames más y parar
                if loop_detected and (frame_count - loop_start_frame) >= 200:
                    print(f"\n[PC-MONITOR-0437] Loop confirmed for 200 frames, stopping")
                    break
    
    print(f"\n[PC-MONITOR-0437] Emulation completed")
    print(f"  Total frames: {frame_count}")
    print(f"  Total cycles: {total_cycles}")
    print(f"  Loop detected: {loop_detected}")
    
    detector.print_summary()
    
    # Verificar rango específico de Pokémon loop
    print(f"\n[PC-MONITOR-0437] Checking specific range 0x36E2..0x36E7:")
    target_range_count = sum(count for pc, count in detector.pc_counter.items() if 0x36E2 <= pc <= 0x36E7)
    if target_range_count > 0:
        pct = (target_range_count * 100.0) / len(detector.pc_history)
        print(f"  Found {target_range_count} instructions in this range ({pct:.2f}%)")
    else:
        print(f"  ZERO instructions in this range")

if __name__ == "__main__":
    main()

