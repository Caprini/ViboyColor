#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Step 0437: Desensamblar el loop detectado y capturar estado de registros
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

# Tabla simplificada de opcodes
OPCODES = {
    0x00: ("NOP", 0),
    0x01: ("LD BC,d16", 2),
    0x02: ("LD (BC),A", 0),
    0x03: ("INC BC", 0),
    0x04: ("INC B", 0),
    0x05: ("DEC B", 0),
    0x06: ("LD B,d8", 1),
    0x0E: ("LD C,d8", 1),
    0x11: ("LD DE,d16", 2),
    0x20: ("JR NZ,r8", 1),
    0x21: ("LD HL,d16", 2),
    0x22: ("LD (HL+),A", 0),
    0x28: ("JR Z,r8", 1),
    0x2A: ("LD A,(HL+)", 0),
    0x31: ("LD SP,d16", 2),
    0x32: ("LD (HL-),A", 0),
    0x3E: ("LD A,d8", 1),
    0xAF: ("XOR A", 0),
    0xC3: ("JP a16", 2),
    0xC9: ("RET", 0),
    0xCD: ("CALL a16", 2),
    0xFE: ("CP d8", 1),
}

def disassemble_at(mmu, addr, count=10):
    """Desensambla 'count' instrucciones desde 'addr'"""
    result = []
    current = addr
    
    for i in range(count):
        opcode = mmu.read(current)
        
        if opcode in OPCODES:
            mnemonic, operand_len = OPCODES[opcode]
            operands = []
            for j in range(1, operand_len + 1):
                operands.append(mmu.read(current + j))
            
            if operand_len == 0:
                instruction = f"{mnemonic}"
            elif operand_len == 1:
                instruction = f"{mnemonic.replace('d8', f'${operands[0]:02X}').replace('r8', f'${operands[0]:02X}')}"
            else:  # operand_len == 2
                val = operands[0] | (operands[1] << 8)
                instruction = f"{mnemonic.replace('d16', f'${val:04X}').replace('a16', f'${val:04X}')}"
            
            result.append(f"  0x{current:04X}: {opcode:02X} | {instruction}")
            current += 1 + operand_len
        else:
            result.append(f"  0x{current:04X}: {opcode:02X} | UNKNOWN")
            current += 1
    
    return result

def main():
    rom_path = "/media/fabini/8CD1-4C30/ViboyColor/roms/pkmn.gb"
    print(f"[DISASM-0437] Cargando ROM: {rom_path}")
    
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
    
    print("[DISASM-0437] Desensamblando zona del loop (0x0060-0x0080):")
    print()
    disasm = disassemble_at(mmu, 0x0060, 20)
    for line in disasm:
        print(line)
    
    print("\n[DISASM-0437] Ejecutando hasta alcanzar el loop...")
    
    # Ejecutar hasta alcanzar 0x006B
    max_steps = 100000
    for step in range(max_steps):
        pc = regs.pc
        if pc == 0x006B:
            print(f"\n[DISASM-0437] *** Alcanzó PC=0x006B en step {step} ***")
            break
        cpu.step()
        ppu.step(4)  # Dummy
    else:
        print(f"\n[DISASM-0437] No alcanzó 0x006B en {max_steps} steps")
        print(f"  PC final: 0x{regs.pc:04X}")
        return
    
    # Ahora capturar 20 iteraciones del loop con estado completo
    print("\n[DISASM-0437] Capturando 20 iteraciones del loop con estado completo:")
    print()
    print("ITER | PC   | OPCODE | A    | F    | B    | C    | D    | E    | H    | L    | SP   | Instrucción")
    print("-----+------+--------+------+------+------+------+------+------+------+------+------+------------------------")
    
    for iteration in range(20):
        pc = regs.pc
        opcode = mmu.read(pc)
        a = regs.a
        f = regs.f
        b = regs.b
        c = regs.c
        d = regs.d
        e = regs.e
        h = regs.h
        l = regs.l
        sp = regs.sp
        
        # Desensamblar instrucción actual
        if opcode in OPCODES:
            mnemonic, operand_len = OPCODES[opcode]
            operands = []
            for j in range(1, operand_len + 1):
                operands.append(mmu.read(pc + j))
            
            if operand_len == 0:
                instruction = f"{mnemonic}"
            elif operand_len == 1:
                instruction = f"{mnemonic} ${operands[0]:02X}"
            else:
                val = operands[0] | (operands[1] << 8)
                instruction = f"{mnemonic} ${val:04X}"
        else:
            instruction = f"UNKNOWN (0x{opcode:02X})"
        
        print(f"{iteration:4d} | {pc:04X} | {opcode:02X}     | {a:02X}   | {f:02X}   | {b:02X}   | {c:02X}   | {d:02X}   | {e:02X}   | {h:02X}   | {l:02X}   | {sp:04X} | {instruction}")
        
        cpu.step()
        ppu.step(4)  # Dummy
    
    print("\n[DISASM-0437] Análisis completado")
    
    # Analizar flags
    print(f"\n[DISASM-0437] Análisis de flags F=0x{regs.f:02X}:")
    print(f"  Z (Zero):      {(regs.f >> 7) & 1}")
    print(f"  N (Subtract):  {(regs.f >> 6) & 1}")
    print(f"  H (Half-carry):{(regs.f >> 5) & 1}")
    print(f"  C (Carry):     {(regs.f >> 4) & 1}")
    
    # Leer memoria en HL
    hl = (regs.h << 8) | regs.l
    val_at_hl = mmu.read(hl)
    print(f"\n[DISASM-0437] Memoria en HL=0x{hl:04X}: 0x{val_at_hl:02X}")

if __name__ == "__main__":
    main()

