#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0437: Pokemon Loop Evidence Capture + Diagnosis
Ejecuta Pokémon Red con instrumentación completa para capturar evidencia del loop stuck.
Incluye: HL, BC, DE, cycles, opcodes, flags.
"""

import sys
import os
import time
from collections import Counter

# Añadir directorio raíz al path para importar viboy_core
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
sys.path.insert(0, project_root)

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
    NATIVE_AVAILABLE = True
except ImportError as e:
    print(f"ERROR: viboy_core no disponible. Compilar primero con: python3 setup.py build_ext --inplace")
    print(f"ImportError: {e}")
    sys.exit(1)

# Rango del loop conocido
LOOP_PC_MIN = 0x36E2
LOOP_PC_MAX = 0x36E7

class LoopEvidence:
    """Colector de evidencia del loop"""
    def __init__(self):
        self.in_loop = False
        self.loop_entry_frame = None
        self.loop_entry_time = None
        
        # Ring buffer manual (últimas N iteraciones)
        self.ring_buffer = []
        self.ring_buffer_size = 128
        
        # Métricas
        self.unique_addrs = set()
        self.min_addr = 0xFFFF
        self.max_addr = 0x0000
        
        self.first_hl = None
        self.last_hl = None
        
        self.first_bc = None
        self.last_bc = None
        
        self.first_de = None
        self.last_de = None
        
        # Opcodes en el loop
        self.opcode_counter = Counter()
        
        # Frames y cycles
        self.total_frames = 0
        self.total_cycles = 0
        self.loop_cycles = 0
        
    def check_loop_entry(self, pc, frame):
        """Detecta entrada al loop"""
        if not self.in_loop and LOOP_PC_MIN <= pc <= LOOP_PC_MAX:
            self.in_loop = True
            self.loop_entry_frame = frame
            self.loop_entry_time = time.time()
            return True
        return False
    
    def record_iteration(self, pc, opcode, addr, val, hl, bc, de, flags, cycles):
        """Registra una iteración del loop"""
        if not self.in_loop:
            return
        
        # Ring buffer
        sample = {
            'pc': pc,
            'opcode': opcode,
            'addr': addr,
            'val': val,
            'hl': hl,
            'bc': bc,
            'de': de,
            'flags': flags,
            'cycles': cycles
        }
        
        if len(self.ring_buffer) >= self.ring_buffer_size:
            self.ring_buffer.pop(0)
        self.ring_buffer.append(sample)
        
        # Métricas de direccionamiento
        if 0x8000 <= addr <= 0x9FFF:  # VRAM write
            self.unique_addrs.add(addr)
            self.min_addr = min(self.min_addr, addr)
            self.max_addr = max(self.max_addr, addr)
        
        # Métricas de registros
        if self.first_hl is None:
            self.first_hl = hl
        self.last_hl = hl
        
        if self.first_bc is None:
            self.first_bc = bc
        self.last_bc = bc
        
        if self.first_de is None:
            self.first_de = de
        self.last_de = de
        
        # Contar opcode
        self.opcode_counter[opcode] += 1
        
        # Cycles en loop
        self.loop_cycles += cycles
    
    def should_stop(self):
        """Decide si ya tenemos suficiente evidencia"""
        # Mantener ~2 segundos dentro del loop
        if self.in_loop and self.loop_entry_time:
            elapsed = time.time() - self.loop_entry_time
            return elapsed >= 2.0
        return False
    
    def print_summary(self):
        """Imprime resumen estructurado según formato exigido"""
        print("\n" + "=" * 80)
        print("SUMMARY — POKEMON LOOP EVIDENCE (STEP 0437)")
        print("=" * 80)
        
        if not self.in_loop:
            print("ERROR: Loop nunca detectado (PC no alcanzó rango 0x36E2..0x36E7)")
            return
        
        elapsed = time.time() - self.loop_entry_time if self.loop_entry_time else 0
        
        print(f"\n[TIMING]")
        print(f"  Total frames executed: {self.total_frames}")
        print(f"  Loop entry at frame: {self.loop_entry_frame}")
        print(f"  Time inside loop: {elapsed:.2f}s")
        print(f"  Total cycles: {self.total_cycles}")
        print(f"  Loop cycles: {self.loop_cycles}")
        
        print(f"\n[ADDRESSING METRICS]")
        print(f"  unique_addr_count: {len(self.unique_addrs)}")
        print(f"  min_addr: 0x{self.min_addr:04X}")
        print(f"  max_addr: 0x{self.max_addr:04X}")
        print(f"  addr_range: {self.max_addr - self.min_addr} bytes")
        
        print(f"\n[REGISTER PROGRESSION]")
        print(f"  first_hl: 0x{self.first_hl:04X}" if self.first_hl is not None else "  first_hl: None")
        print(f"  last_hl:  0x{self.last_hl:04X}" if self.last_hl is not None else "  last_hl: None")
        hl_delta = (self.last_hl - self.first_hl) if (self.first_hl is not None and self.last_hl is not None) else 0
        print(f"  hl_delta: {hl_delta} (signed: {hl_delta if hl_delta < 32768 else hl_delta - 65536})")
        
        print(f"  first_bc: 0x{self.first_bc:04X}" if self.first_bc is not None else "  first_bc: None")
        print(f"  last_bc:  0x{self.last_bc:04X}" if self.last_bc is not None else "  last_bc: None")
        bc_delta = (self.last_bc - self.first_bc) if (self.first_bc is not None and self.last_bc is not None) else 0
        print(f"  bc_delta: {bc_delta} (signed: {bc_delta if bc_delta < 32768 else bc_delta - 65536})")
        
        print(f"  first_de: 0x{self.first_de:04X}" if self.first_de is not None else "  first_de: None")
        print(f"  last_de:  0x{self.last_de:04X}" if self.last_de is not None else "  last_de: None")
        de_delta = (self.last_de - self.first_de) if (self.first_de is not None and self.last_de is not None) else 0
        print(f"  de_delta: {de_delta} (signed: {de_delta if de_delta < 32768 else de_delta - 65536})")
        
        print(f"\n[TOP OPCODES IN LOOP]")
        top_opcodes = self.opcode_counter.most_common(10)
        for opcode, count in top_opcodes:
            pct = (count * 100.0) / sum(self.opcode_counter.values()) if self.opcode_counter else 0
            print(f"  0x{opcode:02X}: {count:6d} times ({pct:5.1f}%)")
        
        print(f"\n[RING BUFFER SAMPLES] (last {min(10, len(self.ring_buffer))} of {len(self.ring_buffer)})")
        samples_to_show = self.ring_buffer[-10:]
        for i, s in enumerate(samples_to_show, start=1):
            print(f"  SAMPLE {i:2d}: PC=0x{s['pc']:04X} OP=0x{s['opcode']:02X} addr=0x{s['addr']:04X} val=0x{s['val']:02X} "
                  f"HL=0x{s['hl']:04X} BC=0x{s['bc']:04X} DE=0x{s['de']:04X} F=0x{s['flags']:02X} cyc={s['cycles']}")
        
        print("\n" + "=" * 80)


def main():
    # Cargar ROM Pokemon Red
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[STEP-0437] Cargando ROM: {rom_path}")
    
    try:
        with open(rom_path, "rb") as f:
            rom_bytes = f.read()
    except FileNotFoundError:
        print(f"ERROR: ROM no encontrada en {rom_path}")
        sys.exit(1)
    
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
    
    print("[STEP-0437] Instrumentación: Capturando evidencia del loop...")
    print(f"[STEP-0437] Target loop range: PC=0x{LOOP_PC_MIN:04X}..0x{LOOP_PC_MAX:04X}")
    
    evidence = LoopEvidence()
    
    # Ejecutar hasta tener suficiente evidencia
    # ~70K T-cycles por frame, ~3600 frames para alcanzar el loop (paso 0436)
    max_frames = 5000  # Suficiente para entrar al loop + 2s dentro
    max_cycles_total = max_frames * 70224  # ~350M cycles
    
    frame_cycles = 0
    frame_count = 0
    
    print(f"[STEP-0437] Ejecutando hasta {max_frames} frames (o 2s dentro del loop)...")
    
    while evidence.total_cycles < max_cycles_total:
        # Guardar estado pre-step
        pc = regs.pc
        
        # Ejecutar instrucción
        cycles = cpu.step()
        evidence.total_cycles += cycles
        frame_cycles += cycles
        
        # Leer estado post-step para análisis
        opcode = mmu.read(pc)  # Opcode que se ejecutó
        hl = (regs.h << 8) | regs.l
        bc = (regs.b << 8) | regs.c
        de = (regs.d << 8) | regs.e
        flags = regs.f
        
        # Intentar inferir dirección de memoria accedida (simplificado)
        # Para este análisis, usamos HL como proxy de direccionamiento
        addr = hl
        val = mmu.read(addr) if 0x8000 <= addr <= 0x9FFF else 0
        
        # Detectar entrada al loop
        if evidence.check_loop_entry(pc, frame_count):
            print(f"\n[STEP-0437] *** LOOP DETECTED at frame {frame_count}, PC=0x{pc:04X} ***\n")
        
        # Registrar si estamos en el loop
        if evidence.in_loop and LOOP_PC_MIN <= pc <= LOOP_PC_MAX:
            evidence.record_iteration(pc, opcode, addr, val, hl, bc, de, flags, cycles)
        
        # Avanzar PPU
        ppu.step(cycles)
        frame_cycles += cycles
        
        # Contar frames (aproximado cada 70224 T-cycles)
        if frame_cycles >= 70224:
            frame_cycles = 0
            frame_count += 1
            evidence.total_frames = frame_count
            
            if frame_count % 500 == 0:
                print(f"[STEP-0437] Progress: frame {frame_count}, cycles {evidence.total_cycles // 1000}K")
        
        # Verificar si ya tenemos suficiente evidencia
        if evidence.should_stop():
            print(f"\n[STEP-0437] Evidence collection complete (2s inside loop)")
            break
    
    print(f"\n[STEP-0437] Emulation completed: {evidence.total_cycles} T-cycles, {evidence.total_frames} frames")
    
    # Imprimir resumen estructurado
    evidence.print_summary()
    
    print("\n[STEP-0437] Test completed — Evidence captured successfully")

if __name__ == "__main__":
    main()

