#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Herramienta headless para smoke test de ROMs sin pygame.

Step 0442: Ejecutar ROM real headless y recolectar métricas para diagnosticar
si el framebuffer sigue blanco o si hay actividad VRAM/rendering.

Uso:
    python tools/rom_smoke_0442.py <ROM_PATH> [--frames N] [--dump-every N] [--dump-png]

Métricas recolectadas por frame:
    - PC (Program Counter)
    - nonwhite_pixels (muestreo de framebuffer)
    - frame_hash (hash simple del framebuffer)
    - vram_nonzero_count (muestreo de VRAM 0x8000-0x9FFF)
    - LCDC, STAT, BGP, SCY, SCX, LY (registros I/O)

Referencias:
    - Pan Docs: Memory Map, I/O Registers
    - Step 0442: Smoke real de ejecución + evidencia no-blanco
"""

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Step 0450: Preflight check - verificar que viboy_core está disponible y compilado ---
try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters, PyTimer, PyJoypad
    NATIVE_AVAILABLE = True
except ImportError as e:
    print("=" * 80, file=sys.stderr)
    print("ERROR CRÍTICO: viboy_core no está disponible", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Detalles: {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("SOLUCIÓN: Compilar el módulo C++ primero:", file=sys.stderr)
    print("", file=sys.stderr)
    print("  cd $(git rev-parse --show-toplevel)", file=sys.stderr)
    print("  python3 setup.py build_ext --inplace", file=sys.stderr)
    print("", file=sys.stderr)
    print("O usar test_build.py:", file=sys.stderr)
    print("  python3 test_build.py", file=sys.stderr)
    print("", file=sys.stderr)
    print("Si el error persiste, verificar:", file=sys.stderr)
    print("  - Cython instalado: pip install cython", file=sys.stderr)
    print("  - Compilador C++ disponible: gcc/clang", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    sys.exit(1)

# Verificación adicional: intentar crear instancia para detectar errores de linking
try:
    test_mmu = PyMMU()
    del test_mmu
except Exception as e:
    print("=" * 80, file=sys.stderr)
    print("ERROR: viboy_core importado pero falla al crear instancia", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    print(f"Detalles: {e}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Posible causa: módulo compilado pero linking fallido o incompleto", file=sys.stderr)
    print("Recompilar:", file=sys.stderr)
    print("  python3 setup.py build_ext --inplace --force", file=sys.stderr)
    print("=" * 80, file=sys.stderr)
    sys.exit(1)


# --- Step 0474: Funciones helper para disasembly ---
def _get_io_register_name(addr: int) -> str:
    """
    Devuelve el nombre de un registro I/O si es conocido.
    
    Args:
        addr: Dirección del registro I/O
    
    Returns:
        Nombre del registro o dirección hexadecimal
    """
    names = {
        0xFF00: "JOYP",
        0xFF01: "SB",
        0xFF02: "SC",
        0xFF04: "DIV",
        0xFF05: "TIMA",
        0xFF06: "TMA",
        0xFF07: "TAC",
        0xFF0F: "IF",
        0xFF40: "LCDC",
        0xFF41: "STAT",
        0xFF42: "SCY",
        0xFF43: "SCX",
        0xFF44: "LY",
        0xFF45: "LYC",
        0xFF46: "DMA",
        0xFF47: "BGP",
        0xFF48: "OBP0",
        0xFF49: "OBP1",
        0xFF4A: "WY",
        0xFF4B: "WX",
        0xFF4D: "KEY1",
        0xFFFF: "IE",
    }
    return names.get(addr, f"0x{addr:04X}")


def dump_rom_bytes(mmu: PyMMU, pc: int, count: int = 32) -> List[int]:
    """
    Dumpea bytes de ROM desde una dirección PC.
    
    Args:
        mmu: Instancia de MMU
        pc: Program Counter (dirección)
        count: Número de bytes a leer
    
    Returns:
        Lista de bytes leídos
    """
    bytes_list = []
    for i in range(count):
        addr = (pc + i) & 0xFFFF
        # Usar read_raw para evitar restricciones de modo PPU
        byte_val = mmu.read_raw(addr) if hasattr(mmu, 'read_raw') else mmu.read(addr)
        bytes_list.append(byte_val)
    return bytes_list


def disasm_lr35902(bytes_list: List[int], start_pc: int, max_instructions: int = 20) -> List[Tuple[int, str, int]]:
    """
    Desensambla instrucciones LR35902 básicas (clean-room).
    
    Solo decodifica opcodes comunes necesarios para identificar bucles de espera.
    Fuente: Pan Docs - CPU Instruction Set
    
    Args:
        bytes_list: Lista de bytes de ROM
        start_pc: PC inicial
        max_instructions: Máximo de instrucciones a decodificar
    
    Returns:
        Lista de tuplas (pc, mnemónico, bytes_leídos)
    """
    instructions = []
    pc = start_pc
    idx = 0
    
    while idx < len(bytes_list) and len(instructions) < max_instructions:
        if idx >= len(bytes_list):
            break
        
        opcode = bytes_list[idx]
        mnemonic = ""
        bytes_read = 1
        
        # Opcodes de 1 byte
        if opcode == 0x00:
            mnemonic = "NOP"
        elif opcode == 0x76:
            mnemonic = "HALT"
        elif opcode == 0xF3:
            mnemonic = "DI"
        elif opcode == 0xFB:
            mnemonic = "EI"
        elif opcode == 0xC9:
            mnemonic = "RET"
        # LD A, n (0x3E)
        elif opcode == 0x3E:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"LD A, 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "LD A, n"
        # LDH (FF00+n),A (0xE0) - Step 0477
        elif opcode == 0xE0:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                io_name = _get_io_register_name(0xFF00 + n)
                mnemonic = f"LDH ({io_name}),A"
                bytes_read = 2
            else:
                mnemonic = "LDH (FF00+n),A"
        # LD (FF00+C),A (0xE2) - Step 0477
        elif opcode == 0xE2:
            mnemonic = "LD (FF00+C),A"
        # LD A,(FF00+C) (0xF2) - Step 0477
        elif opcode == 0xF2:
            mnemonic = "LD A,(FF00+C)"
        # LD A, (n) (0xF0) - LDH A,(FF00+n)
        elif opcode == 0xF0:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                io_name = _get_io_register_name(0xFF00 + n)
                mnemonic = f"LDH A,({io_name})"
                bytes_read = 2
            else:
                mnemonic = "LDH A,(FF00+n)"
        # LD (a16),A (0xEA) - Step 0477
        elif opcode == 0xEA:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                addr = (hi << 8) | lo
                io_name = _get_io_register_name(addr)
                mnemonic = f"LD ({io_name}),A"
                bytes_read = 3
            else:
                mnemonic = "LD (a16),A"
        # LD A,(a16) (0xFA) - Step 0477
        elif opcode == 0xFA:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                addr = (hi << 8) | lo
                io_name = _get_io_register_name(addr)
                mnemonic = f"LD A,({io_name})"
                bytes_read = 3
            else:
                mnemonic = "LD A,(a16)"
        # Prefijo CB (0xCB) - Step 0477
        elif opcode == 0xCB:
            if idx + 1 < len(bytes_list):
                cb_opcode = bytes_list[idx + 1]
                mnemonic = f"CB {cb_opcode:02X}"
                bytes_read = 2  # Consumir 2 bytes para no desalinear
            else:
                mnemonic = "CB ??"
                bytes_read = 2
        # AND n (0xE6)
        elif opcode == 0xE6:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"AND 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "AND n"
        # JR Z, e (0x28)
        elif opcode == 0x28:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR Z, 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR Z, e"
        # JR NZ, e (0x20)
        elif opcode == 0x20:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR NZ, 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR NZ, e"
        # JR e (0x18)
        elif opcode == 0x18:
            if idx + 1 < len(bytes_list):
                e = bytes_list[idx + 1]
                if e & 0x80:
                    offset = -((~e + 1) & 0xFF)
                else:
                    offset = e
                target = (pc + 2 + offset) & 0xFFFF
                mnemonic = f"JR 0x{target:04X} ({offset:+d})"
                bytes_read = 2
            else:
                mnemonic = "JR e"
        # CALL nn (0xCD)
        elif opcode == 0xCD:
            if idx + 2 < len(bytes_list):
                lo = bytes_list[idx + 1]
                hi = bytes_list[idx + 2]
                nn = (hi << 8) | lo
                mnemonic = f"CALL 0x{nn:04X}"
                bytes_read = 3
            else:
                mnemonic = "CALL nn"
        # LD (HL), A (0x77)
        elif opcode == 0x77:
            mnemonic = "LD (HL), A"
        # INC HL (0x23)
        elif opcode == 0x23:
            mnemonic = "INC HL"
        # DEC HL (0x2B)
        elif opcode == 0x2B:
            mnemonic = "DEC HL"
        # LD A, (HL) (0x7E)
        elif opcode == 0x7E:
            mnemonic = "LD A, (HL)"
        # CP (HL) (0xBE)
        elif opcode == 0xBE:
            mnemonic = "CP (HL)"
        # CP n (0xFE)
        elif opcode == 0xFE:
            if idx + 1 < len(bytes_list):
                n = bytes_list[idx + 1]
                mnemonic = f"CP 0x{n:02X}"
                bytes_read = 2
            else:
                mnemonic = "CP n"
        else:
            # Opcode desconocido
            mnemonic = f"DB 0x{opcode:02X}"
        
        instructions.append((pc, mnemonic, bytes_read))
        pc = (pc + bytes_read) & 0xFFFF
        idx += bytes_read
    
    return instructions
# --- Fin Step 0474 ---


def disasm_window(mmu: PyMMU, pc: int, before: int = 16, after: int = 32) -> List[Tuple[int, str, bool]]:
    """
    Desensambla ventana alrededor de PC para evitar empezar en mitad de instrucción.
    
    Step 0480: Corregido para marcar PC actual explícitamente y leer bytes usando MMU
    (respeta banking) en lugar de raw file access.
    
    Args:
        mmu: Instancia MMU (para respetar banking)
        pc: PC actual (centro de la ventana)
        before: Bytes antes de PC a leer
        after: Bytes después de PC a leer
    
    Returns:
        Lista de (addr, instruction, is_current_pc)
    """
    start_addr = (pc - before) & 0xFFFF
    end_addr = (pc + after) & 0xFFFF
    
    # Leer bytes de ROM usando MMU (respeta banking)
    bytes_data = []
    for addr in range(start_addr, end_addr + 1):
        addr_wrapped = addr & 0xFFFF
        byte_val = mmu.read_raw(addr_wrapped) if hasattr(mmu, 'read_raw') else mmu.read(addr_wrapped)
        bytes_data.append(byte_val)
    
    # Desensamblar desde start_addr
    instructions = []
    offset = 0
    current_pc = pc
    
    while offset < len(bytes_data):
        addr = (start_addr + offset) & 0xFFFF
        is_current = (addr == current_pc)
        
        # Obtener mnemónico usando disasm_lr35902
        inst_list = disasm_lr35902(bytes_data[offset:], addr, max_instructions=1)
        if inst_list:
            _, mnemonic, bytes_read = inst_list[0]
        else:
            # Fallback: determinar bytes_read básico
            opcode = bytes_data[offset]
            if opcode == 0xCB:
                bytes_read = 2  # CB prefix consume 2 bytes
            elif opcode in [0xE0, 0xF0]:
                bytes_read = 2  # LDH consume 2 bytes
            elif opcode in [0xEA, 0xFA]:
                bytes_read = 3  # LD (a16) consume 3 bytes
            else:
                bytes_read = 1  # Default: 1 byte
            mnemonic = f"DB 0x{opcode:02X}"
        
        # Marcar PC actual explícitamente
        if is_current:
            mnemonic = f">>> {mnemonic} <<< PC ACTUAL"
        
        instructions.append((addr, mnemonic, is_current))
        offset += bytes_read
        
        if offset >= len(bytes_data):
            break
    
    return instructions
# --- Fin Step 0477 Fase A2 ---


def parse_loop_io_pattern(disasm_window: List[Tuple[int, str, bool]], jump_window: int = 16) -> Dict[str, Optional[int]]:
    """
    Parsea el disasm window y detecta automáticamente patrones de I/O.
    
    Step 0480: Reglas corregidas para evitar falsos positivos:
    - Solo declarar loop_waits_on si hay I/O read (addr < 0xFF80) Y jump de vuelta
    - FF80-FFFE = HRAM, no I/O (no marcar como wait loop)
    - Debe haber jump de vuelta al hotspot para ser considerado loop real
    
    Args:
        disasm_window: Lista de tuplas (addr, instruction, is_current_pc)
    
    Returns:
        dict con:
        - waits_on: dirección I/O esperada (0xFF44, 0xFF41, etc.) o None
        - mask: máscara AND aplicada (0x01, 0x03, etc.) o None
        - cmp: valor comparado (si hay CP) o None
        - pattern: tipo de espera (STAT_MODE, LY_GE, IF_BIT, etc.) o None
    """
    import re
    
    waits_on = None
    mask = None
    cmp_val = None
    pattern = None
    hotspot_pc = None
    
    # Encontrar PC actual (hotspot)
    for addr, instruction, is_current in disasm_window:
        if is_current:
            hotspot_pc = addr
            break
    
    if hotspot_pc is None:
        return {"waits_on": None, "mask": None, "cmp": None, "pattern": "UNKNOWN"}
    
    # Buscar I/O read y jump de vuelta
    io_read_addr = None
    jump_back_found = False
    
    for addr, instruction, is_current in disasm_window:
        # Detectar LDH A,(addr) con addr < 0xFF80 (I/O, no HRAM)
        if "LDH A,(" in instruction or "LD A,(" in instruction:
            # Extraer dirección del mnemónico
            # Formato: "LDH A,(LY)" o "LD A,(0xFF44)" o "LDH A,(FF44)" o "LDH A,(0xFF92)"
            if "0xFF" in instruction:
                matches = re.findall(r'0x([0-9A-F]{2,4})', instruction)
                if matches:
                    io_addr_hex = matches[0]
                    io_addr = int(io_addr_hex, 16)
                    # Solo considerar I/O (0xFF00-0xFF7F), no HRAM (0xFF80-0xFFFF)
                    if 0xFF00 <= io_addr < 0xFF80:
                        io_read_addr = io_addr
                        waits_on = io_addr
            elif "LY" in instruction:
                io_read_addr = 0xFF44
                waits_on = 0xFF44
            elif "STAT" in instruction:
                io_read_addr = 0xFF41
                waits_on = 0xFF41
            elif "IF" in instruction:
                io_read_addr = 0xFF0F
                waits_on = 0xFF0F
            elif "IE" in instruction:
                io_read_addr = 0xFFFF
                waits_on = 0xFFFF
            elif "JOYP" in instruction:
                io_read_addr = 0xFF00
                waits_on = 0xFF00
            elif "KEY1" in instruction:
                io_read_addr = 0xFF4D
                waits_on = 0xFF4D
            elif "VBK" in instruction:
                io_read_addr = 0xFF4F
                waits_on = 0xFF4F
            elif "SVBK" in instruction:
                io_read_addr = 0xFF70
                waits_on = 0xFF70
        
        # Detectar AND mask
        if waits_on and "AND" in instruction:
            matches = re.findall(r'AND\s+0x([0-9A-Fa-f]+)', instruction)
            if matches:
                mask = int(matches[0], 16)
        
        # Detectar CP (compare)
        if waits_on and "CP" in instruction:
            matches = re.findall(r'CP\s+0x([0-9A-Fa-f]+)', instruction)
            if matches:
                cmp_val = int(matches[0], 16)
        
        # Detectar BIT n
        if waits_on and "BIT" in instruction:
            matches = re.findall(r'BIT\s+(\d+)', instruction)
            if matches:
                bit_num = int(matches[0])
                mask = 1 << bit_num
        
        # Detectar jump de vuelta al hotspot
        if waits_on and ("JR" in instruction or "JP" in instruction):
            # Extraer target del jump
            matches = re.findall(r'(JR|JP)\s+(?:Z|NZ|C|NC)?\s*0x([0-9A-Fa-f]+)', instruction)
            if matches:
                target = int(matches[0][1], 16)
                # Verificar si el target está cerca del hotspot (ventana configurable)
                if abs(target - hotspot_pc) <= jump_window:
                    jump_back_found = True
    
    # Solo declarar loop si hay I/O read Y jump de vuelta
    if not jump_back_found:
        waits_on = None
        mask = None
        cmp_val = None
        pattern = "NO_LOOP"  # No es un wait loop, es otra cosa
    else:
        # Determinar pattern
        if waits_on == 0xFF44:  # LY
            if cmp_val is not None:
                pattern = "LY_GE"
            else:
                pattern = "LY_POLL"
        elif waits_on == 0xFF41:  # STAT
            if mask == 0x03:
                pattern = "STAT_MODE"
            else:
                pattern = "STAT_POLL"
        elif waits_on == 0xFF0F:  # IF
            if mask:
                pattern = f"IF_BIT{mask.bit_length()-1}"
            else:
                pattern = "IF_POLL"
        elif waits_on == 0xFF00:  # JOYP
            pattern = "JOYP_POLL"
        elif waits_on in [0xFF4D, 0xFF4F, 0xFF70]:  # CGB I/O
            pattern = "CGB_IO"
        elif waits_on == 0xFFFF:  # IE
            pattern = "IE_POLL"
        else:
            pattern = "UNKNOWN"
    
    return {
        "waits_on": waits_on,
        "mask": mask,
        "cmp": cmp_val,
        "pattern": pattern
    }
# --- Fin Step 0479 Fase A1 ---


# --- Step 0482: Dynamic Wait-Loop Detector ---
def detect_dynamic_wait_loop(mmu: PyMMU, cpu: PyCPU, hotspot_pc: int, window_size: int = 32, iterations: int = 100) -> Dict[str, any]:
    """
    Detecta wait-loop dinámicamente analizando I/O reads en hotspot.
    
    Step 0482: Cuando detectes un hotspot estable, analiza durante N iteraciones:
    1. Registrar I/O reads program en ese rango de PCs (ya tenéis source tagging)
    2. Sacar el "IO read dominante" y su distribución
    3. Correlaciona con last_cmp / last_bit para etiquetar waits_on_addr, mask/cmp/bit
    
    Args:
        mmu: Instancia MMU
        cpu: Instancia CPU
        hotspot_pc: PC del hotspot
        window_size: Ventana de bytes alrededor del hotspot
        iterations: Número de iteraciones a analizar
    
    Returns:
        dict con: waits_on_addr, mask, cmp, bit, io_reads_distribution
    """
    io_reads_counter = {}  # addr -> count
    
    # Calcular ventana de PCs
    start_pc = (hotspot_pc - window_size) & 0xFFFF
    end_pc = (hotspot_pc + window_size) & 0xFFFF
    
    # Guardar contadores iniciales (para calcular incrementos)
    initial_if_reads = mmu.get_if_reads_program()
    initial_ie_reads = mmu.get_ie_reads_program()
    initial_joyp_reads = mmu.get_joyp_read_count_program()
    
    # Ejecutar N iteraciones y contar I/O reads program
    # NOTA: Esto requiere que la CPU esté en el hotspot, por lo que
    # esta función debe llamarse cuando el CPU ya está en el hotspot
    # Por ahora, solo obtenemos los contadores acumulados
    # (Una implementación más completa resetearía contadores y ejecutaría pasos)
    
    # Obtener contadores actuales de I/O reads program
    current_if_reads = mmu.get_if_reads_program()
    current_ie_reads = mmu.get_ie_reads_program()
    current_joyp_reads = mmu.get_joyp_read_count_program()
    
    # Calcular incrementos (simplificado: asumimos que los contadores ya reflejan
    # la actividad del hotspot si se llama en el momento correcto)
    if_reads_increment = current_if_reads - initial_if_reads if current_if_reads >= initial_if_reads else current_if_reads
    ie_reads_increment = current_ie_reads - initial_ie_reads if current_ie_reads >= initial_ie_reads else current_ie_reads
    joyp_reads_increment = current_joyp_reads - initial_joyp_reads if current_joyp_reads >= initial_joyp_reads else current_joyp_reads
    
    io_reads_counter[0xFF0F] = if_reads_increment
    io_reads_counter[0xFFFF] = ie_reads_increment
    io_reads_counter[0xFF00] = joyp_reads_increment
    
    # Encontrar I/O read dominante
    if io_reads_counter and max(io_reads_counter.values()) > 0:
        waits_on_addr = max(io_reads_counter, key=io_reads_counter.get)
        dominant_count = io_reads_counter[waits_on_addr]
    else:
        waits_on_addr = None
        dominant_count = 0
    
    # Correlacionar con last_cmp / last_bit
    last_cmp_pc = cpu.get_last_cmp_pc()
    last_cmp_a = cpu.get_last_cmp_a()
    last_cmp_imm = cpu.get_last_cmp_imm()
    last_bit_pc = cpu.get_last_bit_pc()
    last_bit_n = cpu.get_last_bit_n()
    last_bit_value = cpu.get_last_bit_value()
    
    # Determinar mask/cmp/bit
    mask = None
    cmp_val = None
    bit_num = None
    
    if last_bit_pc != 0xFFFF and abs((last_bit_pc - hotspot_pc) & 0xFFFF) <= window_size:
        bit_num = last_bit_n
        mask = 1 << bit_num
        cmp_val = 1  # BIT espera bit = 1
    
    if last_cmp_pc != 0xFFFF and abs((last_cmp_pc - hotspot_pc) & 0xFFFF) <= window_size:
        cmp_val = last_cmp_imm
    
    return {
        "waits_on_addr": waits_on_addr,
        "mask": mask,
        "cmp": cmp_val,
        "bit": bit_num,
        "io_reads_distribution": io_reads_counter,
        "last_cmp_pc": last_cmp_pc,
        "last_cmp_imm": last_cmp_imm,
        "last_bit_pc": last_bit_pc,
        "last_bit_n": bit_num
    }
# --- Fin Step 0482 (Dynamic Wait-Loop Detector) ---


# --- Step 0482: Unknown Opcode Histogram ---
def get_unknown_opcode_histogram(disasm_window: List[Tuple[int, str, bool]]) -> List[Tuple[int, int]]:
    """
    Cuenta opcodes desconocidos (DB) en disasm window.
    
    Step 0482: Priorizar completar el disassembler por "Unknown Opcode Histogram".
    En vez de "implemento opcodes al azar", identifica los top 10 opcodes desconocidos
    en el hotspot para implementarlos primero.
    
    Args:
        disasm_window: Lista de tuplas (addr, instruction, is_current_pc)
    
    Returns:
        Lista de tuplas (opcode, count) ordenada por count descendente (top 10)
    """
    import re
    unknown_opcodes = {}  # opcode -> count
    
    for addr, instruction, is_current in disasm_window:
        if instruction.startswith("DB "):
            # Extraer byte
            match = re.search(r'DB\s+0x([0-9A-Fa-f]+)', instruction)
            if match:
                opcode = int(match.group(1), 16)
                unknown_opcodes[opcode] = unknown_opcodes.get(opcode, 0) + 1
    
    # Ordenar por count (descendente)
    sorted_opcodes = sorted(unknown_opcodes.items(), key=lambda x: x[1], reverse=True)
    
    return sorted_opcodes[:10]  # Top 10
# --- Fin Step 0482 (Unknown Opcode Histogram) ---


# --- Step 0481: Static Scan de Writers HRAM ---
def scan_rom_for_hram8_writes(rom_bytes: bytes, target_addr: int) -> List[Tuple[int, str, List[Tuple[int, str]]]]:
    """
    Escanea ROM buscando patrones típicos de escritura a HRAM.
    
    Args:
        rom_bytes: bytes del ROM (array de bytes)
        target_addr: dirección HRAM a buscar (ej: 0x92 para 0xFF92)
    
    Returns:
        Lista de (pc, pattern_type, disasm_snippet)
    """
    writers = []
    
    # Patrón 1: E0 92 → LDH (0x92),A
    pattern1 = bytes([0xE0, target_addr])
    
    # Patrón 2: EA 92 FF → LD (0xFF92),A
    pattern2 = bytes([0xEA, target_addr, 0xFF])
    
    # Buscar patrones en ROM
    for i in range(len(rom_bytes) - 2):
        # Patrón 1: LDH (0x92),A
        if rom_bytes[i:i+2] == pattern1:
            pc = i
            # Disasm window alrededor (16 bytes antes, 16 después)
            start = max(0, pc - 16)
            end = min(len(rom_bytes), pc + 16)
            snippet_bytes = rom_bytes[start:end]
            # Usar disasm_lr35902 para obtener snippet
            snippet = disasm_lr35902(list(snippet_bytes), start)
            writers.append((pc, f"LDH (0x{target_addr:02X}),A", snippet))
        
        # Patrón 2: LD (0xFF92),A
        if i < len(rom_bytes) - 3 and rom_bytes[i:i+3] == pattern2:
            pc = i
            start = max(0, pc - 16)
            end = min(len(rom_bytes), pc + 16)
            snippet_bytes = rom_bytes[start:end]
            snippet = disasm_lr35902(list(snippet_bytes), start)
            writers.append((pc, f"LD (0xFF{target_addr:02X}),A", snippet))
    
    # Patrón 3: E2 con análisis básico: LD (FF00+C),A
    # Si cerca se ve LD C,0x92
    for i in range(len(rom_bytes) - 10):
        if rom_bytes[i] == 0x0E and rom_bytes[i+1] == target_addr:  # LD C,0x92
            # Buscar E2 cerca (dentro de 20 bytes)
            for j in range(i, min(i+20, len(rom_bytes))):
                if rom_bytes[j] == 0xE2:  # LD (FF00+C),A
                    pc = j
                    start = max(0, pc - 16)
                    end = min(len(rom_bytes), pc + 16)
                    snippet_bytes = rom_bytes[start:end]
                    snippet = disasm_lr35902(list(snippet_bytes), start)
                    writers.append((pc, f"LD (FF00+C),A (C=0x{target_addr:02X})", snippet))
                    break
    
    return writers
# --- Fin Step 0481 Fase B1 ---


class ROMSmokeRunner:
    """Runner headless para smoke test de ROMs."""
    
    # Constantes del sistema
    CYCLES_PER_FRAME = 70224  # 4.194.304 MHz / 59.7 FPS
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144
    FRAMEBUFFER_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT * 3  # RGB
    
    def __init__(self, rom_path: str, max_frames: int = 300, 
                 dump_every: int = 0, dump_png: bool = False,
                 max_seconds: int = 120, stop_early_on_first_nonzero: bool = False,
                 use_renderer_headless: bool = False, use_renderer_windowed: bool = False,
                 stop_on_first_tiledata_nonzero: bool = False,
                 stop_on_first_tiledata_nonzero_write: bool = False):
        """
        Inicializa el runner.
        
        Args:
            rom_path: Ruta al archivo ROM
            max_frames: Número máximo de frames a ejecutar
            dump_every: Cada cuántos frames dumpear métricas detalladas (0 = solo final)
            dump_png: Si True, genera PNGs de framebuffers seleccionados
            max_seconds: Timeout máximo de ejecución (segundos)
            stop_early_on_first_nonzero: Si True, parar cuando tiledata_first_nonzero_frame exista
            use_renderer_headless: Si True, usar renderer headless para capturar FB_PRESENT_SRC (Step 0497)
            use_renderer_windowed: Si True, usar renderer windowed (para testing event pumping) (Step 0499)
            stop_on_first_tiledata_nonzero: Step 0502: Parar cuando se detecte primer tiledata no-cero en VRAM
            stop_on_first_tiledata_nonzero_write: Step 0502: Parar cuando se detecte primer write no-cero a tiledata
        """
        self.rom_path = Path(rom_path)
        self.max_frames = max_frames
        self.dump_every = dump_every
        self.dump_png = dump_png
        self.max_seconds = max_seconds
        self.stop_early_on_first_nonzero = stop_early_on_first_nonzero
        self.use_renderer_headless = use_renderer_headless
        self.use_renderer_windowed = use_renderer_windowed
        self.stop_on_first_tiledata_nonzero = stop_on_first_tiledata_nonzero
        self.stop_on_first_tiledata_nonzero_write = stop_on_first_tiledata_nonzero_write
        self._renderer = None
        
        # Step 0499: Si windowed, forzar SDL_VIDEODRIVER normal (no dummy)
        if self.use_renderer_windowed:
            import os
            os.environ.pop('SDL_VIDEODRIVER', None)  # Quitar dummy si existe
            os.environ.pop('VIBOY_HEADLESS', None)   # Quitar headless si existe
        
        # Validar ROM
        if not self.rom_path.exists():
            raise FileNotFoundError(f"ROM no encontrada: {self.rom_path}")
        
        # Métricas acumuladas
        self.metrics: List[Dict] = []
        self.first_nonwhite_frame: Optional[int] = None
        self.start_time: float = 0
        
        # Step 0470: Contadores para hotspots
        self.pc_samples: Dict[int, int] = {}  # Dict: PC -> count
        self.step_count = 0
        
        # --- Step 0498: First Signal Detector ---
        self._first_signal_frame_id = None
        self._first_signal_detected = False
        self._first_signal_trace_snapshot = None  # Snapshot de traces cuando se detecta first_signal
        # -----------------------------------------
        
        # Inicializar core
        self._init_core()
    
    def _init_core(self):
        """Inicializa componentes core C++ con wiring correcto."""
        # Leer ROM
        with open(self.rom_path, 'rb') as f:
            self.rom_bytes = f.read()  # Guardar para static scan
        
        # Inicializar core (mismo wiring que runtime)
        self.mmu = PyMMU()
        self.regs = PyRegisters()
        self.cpu = PyCPU(self.mmu, self.regs)
        self.ppu = PyPPU(self.mmu)
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        
        # Wiring: MMU ↔ PPU
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
        
        # Cargar ROM
        self.mmu.load_rom_py(self.rom_bytes)
        
        # --- Step 0483: Auto-press support (VIBOY_AUTOPRESS) ---
        import os
        autopress = os.getenv("VIBOY_AUTOPRESS", "")
        if autopress:
            # Mapear string a índice de botón
            button_map = {
                "START": 7, "A": 4, "B": 5, "SELECT": 6,
                "UP": 2, "DOWN": 3, "LEFT": 1, "RIGHT": 0
            }
            button_idx = button_map.get(autopress.upper(), None)
            if button_idx is not None:
                print(f"[AUTOPRESS] Configurado para presionar: {autopress.upper()} (índice {button_idx})")
                self.autopress_button = button_idx
                self.autopress_frame = 60  # Presionar después de 60 frames
            else:
                print(f"[AUTOPRESS] Botón desconocido: {autopress}, ignorando")
                self.autopress_button = None
        else:
            self.autopress_button = None
        # -----------------------------------------
        
        # --- Step 0481: Static scan FF92 writers (si VIBOY_DEBUG_HRAM=1) ---
        import os
        if os.getenv("VIBOY_DEBUG_HRAM") == "1":
            ff92_writers = scan_rom_for_hram8_writes(self.rom_bytes, 0x92)
            print(f"[ROM-SCAN] Writers de FF92 encontrados: {len(ff92_writers)}")
            for pc, pattern_type, snippet in ff92_writers:
                print(f"[ROM-SCAN] PC=0x{pc:04X} Pattern={pattern_type}")
                print(f"[ROM-SCAN] Disasm snippet:")
                for addr, inst, _ in snippet:
                    print(f"  0x{addr:04X}: {inst}")
            self.ff92_writers = ff92_writers  # Guardar para reporte
        else:
            self.ff92_writers = []
        # -----------------------------------------
        
        # Estado post-boot DMG (Step 0401)
        self.regs.a = 0x01  # DMG
        self.regs.b = 0x00
        self.regs.c = 0x13
        self.regs.d = 0x00
        self.regs.e = 0xD8
        self.regs.h = 0x01
        self.regs.l = 0x4D
        self.regs.sp = 0xFFFE
        self.regs.pc = 0x0100
        
        # Registros I/O post-boot
        io_values = [
            (0xFF05, 0x00), (0xFF06, 0x00), (0xFF07, 0x00),  # Timer
            (0xFF10, 0x80), (0xFF11, 0xBF), (0xFF12, 0xF3), (0xFF14, 0xBF),  # Audio CH1
            (0xFF16, 0x3F), (0xFF17, 0x00), (0xFF19, 0xBF),  # Audio CH2
            (0xFF1A, 0x7F), (0xFF1B, 0xFF), (0xFF1C, 0x9F), (0xFF1E, 0xBF),  # Audio CH3
            (0xFF20, 0xFF), (0xFF21, 0x00), (0xFF22, 0x00), (0xFF23, 0xBF),  # Audio CH4
            (0xFF24, 0x77), (0xFF25, 0xF3), (0xFF26, 0xF1),  # Audio control
            (0xFF40, 0x91),  # LCDC
            (0xFF42, 0x00), (0xFF43, 0x00),  # SCY, SCX
            (0xFF45, 0x00),  # LYC
            (0xFF47, 0xFC),  # BGP
            (0xFF48, 0xFF), (0xFF49, 0xFF),  # OBP0, OBP1
            (0xFF4A, 0x00), (0xFF4B, 0x00),  # WY, WX
            (0xFFFF, 0x00),  # IE
        ]
        
        for addr, value in io_values:
            self.mmu.write(addr, value)
        
        # --- Step 0497: Crear renderer headless si está activo ---
        # --- Step 0499: Añadir soporte para renderer windowed ---
        if self.use_renderer_headless:
            try:
                import os
                # Configurar variables de entorno para modo headless ANTES de importar Renderer
                os.environ['SDL_VIDEODRIVER'] = 'dummy'
                os.environ['VIBOY_HEADLESS'] = '1'
                os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
                
                from src.gpu.renderer import Renderer
                # Crear renderer en modo headless (sin ventana)
                self._renderer = Renderer(mmu=self.mmu, use_cpp_ppu=True, ppu=self.ppu, joypad=self.joypad)
                print(f"[ROM-SMOKE] Renderer headless creado para capturar FB_PRESENT_SRC")
            except Exception as e:
                print(f"[ROM-SMOKE] ⚠️ ADVERTENCIA: No se pudo crear renderer headless: {e}")
                import traceback
                traceback.print_exc()
                self._renderer = None
        elif self.use_renderer_windowed:
            try:
                import os
                # Asegurar que no hay variables de entorno que fuercen headless
                os.environ.pop('SDL_VIDEODRIVER', None)
                os.environ.pop('VIBOY_HEADLESS', None)
                
                from src.gpu.renderer import Renderer
                # Crear renderer en modo windowed (con ventana real)
                self._renderer = Renderer(mmu=self.mmu, use_cpp_ppu=True, ppu=self.ppu, joypad=self.joypad)
                print(f"[ROM-SMOKE] Renderer windowed creado para testing event pumping")
            except Exception as e:
                print(f"[ROM-SMOKE] ⚠️ ADVERTENCIA: No se pudo crear renderer windowed: {e}")
                import traceback
                traceback.print_exc()
                self._renderer = None
        # -----------------------------------------
    
    def _sample_nonwhite_pixels(self, framebuffer: List[int]) -> int:
        """
        Cuenta píxeles non-white en el framebuffer (muestreo eficiente).
        
        Args:
            framebuffer: Lista RGB [R,G,B,R,G,B,...]
        
        Returns:
            Número de píxeles non-white (muestreados)
        """
        if not framebuffer or len(framebuffer) != self.FRAMEBUFFER_SIZE:
            return 0
        
        count = 0
        # Muestrear cada 8º pixel para eficiencia
        for i in range(0, len(framebuffer), 3 * 8):
            r = framebuffer[i]
            g = framebuffer[i + 1]
            b = framebuffer[i + 2]
            
            # Non-white si cualquier canal < 200
            if r < 200 or g < 200 or b < 200:
                count += 1
        
        # Estimar total (multiplicar por 8 por el muestreo)
        return count * 8
    
    def _calculate_robust_metrics(self, framebuffer: List[int]) -> Dict[str, any]:
        """
        Calcula métricas robustas del framebuffer (Step 0454).
        
        Args:
            framebuffer: Lista RGB [R,G,B,R,G,B,...]
        
        Returns:
            Dict con unique_rgb_count, dominant_ratio, frame_hash, hash_changed
        """
        if not framebuffer or len(framebuffer) != self.FRAMEBUFFER_SIZE:
            return {
                'unique_rgb_count': 0,
                'dominant_ratio': 1.0,
                'frame_hash': 'empty',
                'hash_changed': False
            }
        
        # Muestrear grid 16x16 (256 píxeles)
        # Grid: 160/16 = 10 columnas, 144/16 = 9 filas (144/16 = 9)
        # Muestrear centro de cada celda del grid
        unique_colors = set()
        color_freq = {}
        samples = []
        
        grid_step_x = 160 // 16  # 10 píxeles
        grid_step_y = 144 // 16  # 9 píxeles (aproximado)
        
        for grid_y in range(16):
            for grid_x in range(16):
                # Calcular posición real en framebuffer
                y = (grid_y * grid_step_y) if grid_y < 16 else 143
                x = (grid_x * grid_step_x) if grid_x < 16 else 159
                
                # Asegurar dentro de límites
                y = min(y, 143)
                x = min(x, 159)
                
                # Calcular índice en framebuffer (RGB)
                idx = (y * 160 + x) * 3
                if idx + 2 < len(framebuffer):
                    r = framebuffer[idx]
                    g = framebuffer[idx + 1]
                    b = framebuffer[idx + 2]
                    rgb_tuple = (r, g, b)
                    
                    unique_colors.add(rgb_tuple)
                    color_freq[rgb_tuple] = color_freq.get(rgb_tuple, 0) + 1
                    samples.append(rgb_tuple)
        
        # Calcular dominant_ratio
        max_freq = max(color_freq.values()) if color_freq else 0
        total_samples = len(samples)
        dominant_ratio = max_freq / total_samples if total_samples > 0 else 1.0
        
        # Frame hash (MD5 de muestra)
        sample_bytes = bytes([c for rgb in samples[:100] for c in rgb])  # Primeros 100 píxeles
        frame_hash = hashlib.md5(sample_bytes).hexdigest()[:8]
        
        # Hash changed vs frame anterior
        hash_changed = False
        if hasattr(self, '_last_frame_hash'):
            hash_changed = (frame_hash != self._last_frame_hash)
        self._last_frame_hash = frame_hash
        
        return {
            'unique_rgb_count': len(unique_colors),
            'dominant_ratio': dominant_ratio,
            'frame_hash': frame_hash,
            'hash_changed': hash_changed
        }
    
    def _hash_framebuffer(self, framebuffer: List[int]) -> str:
        """Genera hash simple del framebuffer para detectar cambios."""
        if not framebuffer:
            return "empty"
        
        # Hash de muestra (primeros 1000 bytes para eficiencia)
        sample = bytes(framebuffer[:min(1000, len(framebuffer))])
        return hashlib.md5(sample).hexdigest()[:8]
    
    def _detect_first_signal(self, ppu, mmu, renderer=None):
        """
        Step 0498: Detecta primera señal real (IdxNonZero>0 o RgbNonWhite>0 o PresentNonWhite>0).
        
        Args:
            ppu: Instancia de PyPPU
            mmu: Instancia de PyMMU
            renderer: Instancia de Renderer (opcional)
        
        Returns:
            frame_id de la primera señal detectada, o None si no se ha detectado
        """
        if self._first_signal_detected:
            return self._first_signal_frame_id
        
        # Obtener métricas
        try:
            three_buf_stats = ppu.get_three_buffer_stats()
            if three_buf_stats:
                idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
                rgb_nonwhite = three_buf_stats.get('rgb_nonwhite_count', 0)
                present_nonwhite = 0
                
                # Obtener present_nonwhite del renderer si está disponible
                if renderer is not None and hasattr(renderer, 'get_renderer_trace'):
                    renderer_trace = renderer.get_renderer_trace()
                    if renderer_trace:
                        # Obtener el último evento
                        last_event = renderer_trace[-1]
                        present_nonwhite = last_event.get('present_nonwhite', 0)
                
                # Detectar primera señal
                if idx_nonzero > 0 or rgb_nonwhite > 0 or present_nonwhite > 0:
                    frame_id = ppu.get_framebuffer_frame_id()
                    self._first_signal_frame_id = frame_id
                    self._first_signal_detected = True
                    
                    # --- Step 0498: Guardar snapshot de traces para tabla FrameIdConsistency ---
                    try:
                        # Obtener traces actuales
                        ppu_trace = ppu.get_buffer_trace_ring(max_events=128)
                        renderer_trace = renderer.get_renderer_trace() if renderer is not None and hasattr(renderer, 'get_renderer_trace') else []
                        
                        self._first_signal_trace_snapshot = {
                            'ppu_trace': ppu_trace.copy() if hasattr(ppu_trace, 'copy') else list(ppu_trace),
                            'renderer_trace': renderer_trace.copy() if hasattr(renderer_trace, 'copy') else list(renderer_trace),
                            'frame_id': frame_id
                        }
                        print(f"[FirstSignal] Snapshot de traces guardado (PPU: {len(ppu_trace)} eventos, Renderer: {len(renderer_trace)} eventos)")
                    except Exception as e:
                        print(f"[FirstSignal] ⚠️ Error guardando snapshot de traces: {e}")
                    # -----------------------------------------
                    
                    print(f"[FirstSignal] Detected at frame_id={frame_id} | "
                          f"IdxNonZero={idx_nonzero} | RgbNonWhite={rgb_nonwhite} | "
                          f"PresentNonWhite={present_nonwhite}")
                    
                    return frame_id
        except Exception as e:
            # Silenciar errores en detección (puede fallar si PPU no está listo)
            pass
        
        return None
    
    def _dump_framebuffer_by_frame_id(self, buffer_type: str, frame_id: int, ppu):
        """
        Step 0498: Dump framebuffer etiquetado por frame_id.
        
        Args:
            buffer_type: Tipo de buffer ('idx' o 'rgb')
            frame_id: Frame ID del buffer a dumpear
            ppu: Instancia de PyPPU
        """
        dump_path = f'/tmp/viboy_dx_{buffer_type}_fid_{frame_id:010d}.ppm'
        
        try:
            if buffer_type == 'idx':
                # Dump FB_INDEX (índices 0-3)
                fb_indices = ppu.get_presented_framebuffer_indices()
                if fb_indices is None or len(fb_indices) != 160 * 144:
                    return
                
                # Convertir índices a RGB (usar paleta simple para visualización)
                width, height = 160, 144
                palette = [
                    (255, 255, 255),  # 0 = blanco
                    (170, 170, 170),  # 1 = gris claro
                    (85, 85, 85),     # 2 = gris oscuro
                    (0, 0, 0),        # 3 = negro
                ]
                
                with open(dump_path, 'wb') as f:
                    f.write(b"P6\n")
                    f.write(f"{width} {height}\n".encode())
                    f.write(b"255\n")
                    
                    # fb_indices es bytes, convertir a lista de enteros
                    for i in range(width * height):
                        idx = fb_indices[i] & 0x03
                        r, g, b = palette[idx]
                        f.write(bytes([r, g, b]))
                
                print(f"[FirstSignal] Dump FB_INDEX guardado: {dump_path}")
                
            elif buffer_type == 'rgb':
                # Dump FB_RGB (RGB888)
                fb_rgb = ppu.get_framebuffer_rgb()
                if fb_rgb is None:
                    return
                
                width, height = 160, 144
                with open(dump_path, 'wb') as f:
                    f.write(b"P6\n")
                    f.write(f"{width} {height}\n".encode())
                    f.write(b"255\n")
                    
                    # fb_rgb puede ser memoryview o bytes
                    if hasattr(fb_rgb, 'tobytes'):
                        f.write(fb_rgb.tobytes()[:width * height * 3])
                    else:
                        f.write(bytes(fb_rgb[:width * height * 3]))
                
                print(f"[FirstSignal] Dump FB_RGB guardado: {dump_path}")
        except Exception as e:
            print(f"[FirstSignal] ⚠️ Error dumpeando {buffer_type} para frame_id {frame_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def _dump_present_by_frame_id(self, buffer_type: str, frame_id: int, renderer):
        """
        Step 0498: Dump buffer presentado etiquetado por frame_id.
        
        Args:
            buffer_type: Tipo de buffer ('present')
            frame_id: Frame ID del buffer a dumpear
            renderer: Instancia de Renderer
        """
        dump_path = f'/tmp/viboy_dx_{buffer_type}_fid_{frame_id:010d}.ppm'
        
        try:
            # Obtener el último evento del trace del renderer
            renderer_trace = renderer.get_renderer_trace()
            if not renderer_trace:
                return
            
            # Buscar evento con el frame_id correcto
            target_event = None
            for event in reversed(renderer_trace):
                if event.get('frame_id_received') == frame_id:
                    target_event = event
                    break
            
            if target_event is None:
                print(f"[FirstSignal] ⚠️ No se encontró evento para frame_id {frame_id} en renderer trace")
                return
            
            # El buffer presentado ya fue capturado en el renderer, pero necesitamos
            # leerlo desde el Surface. Por ahora, solo loggeamos que se intentó.
            # TODO: Implementar lectura del Surface si es necesario
            print(f"[FirstSignal] Dump FB_PRESENT solicitado para frame_id {frame_id} (implementación pendiente)")
        except Exception as e:
            print(f"[FirstSignal] ⚠️ Error dumpeando {buffer_type} para frame_id {frame_id}: {e}")
    
    def _classify_frame_id_consistency(self, row: Dict) -> str:
        """
        Step 0498: Clasifica una fila de FrameIdConsistency.
        
        Args:
            row: Diccionario con datos de la fila de FrameIdConsistency
        
        Returns:
            Clasificación: OK_SAME_FRAME, OK_LAG_1, STALE_PRESENT, MISMATCH_COPY, ORDER_BUG, INCOMPLETE, UNKNOWN
        """
        ppu_front_fid = row.get('ppu_front_fid')
        ppu_back_fid = row.get('ppu_back_fid')
        ppu_front_rgb_crc = row.get('ppu_front_rgb_crc')
        renderer_received_fid = row.get('renderer_received_fid')
        renderer_src_crc = row.get('renderer_src_crc')
        renderer_present_crc = row.get('renderer_present_crc')
        
        if ppu_front_fid is None or renderer_received_fid is None:
            return "INCOMPLETE"
        
        # OK: renderer recibe el frame_id correcto y el CRC coincide
        if renderer_received_fid == ppu_front_fid and renderer_src_crc == ppu_front_rgb_crc:
            if ppu_back_fid is not None and ppu_front_fid == ppu_back_fid - 1:
                return "OK_LAG_1"  # Lag de 1 frame normal
            else:
                return "OK_SAME_FRAME"  # Mismo frame, sin lag
        
        # STALE_PRESENT: CRC present coincide con frame_id antiguo
        if renderer_present_crc == ppu_front_rgb_crc and renderer_received_fid != ppu_front_fid:
            return "STALE_PRESENT"
        
        # MISMATCH_COPY: frame_id igual pero CRC distinto (overwrite/format/copia)
        if renderer_received_fid == ppu_front_fid and renderer_src_crc != ppu_front_rgb_crc:
            return "MISMATCH_COPY"
        
        # ORDER_BUG: renderer recibe frame_id/back incorrecto (orden swap/render mal)
        if renderer_received_fid != ppu_front_fid:
            if ppu_back_fid is not None and renderer_received_fid != ppu_back_fid:
                return "ORDER_BUG"
        
        return "UNKNOWN"
    
    def _generate_frame_id_consistency_table(self) -> List[Dict]:
        """
        Step 0498: Genera tabla FrameIdConsistency con datos de PPU y Renderer.
        
        Returns:
            Lista de diccionarios, cada uno con datos de una fila de la tabla
        """
        if not self.use_renderer_headless or self._renderer is None:
            return []
        
        try:
            # --- Step 0498: Usar snapshot si está disponible, sino usar traces actuales ---
            if self._first_signal_trace_snapshot is not None:
                # Usar snapshot guardado cuando se detectó first_signal
                ppu_trace = self._first_signal_trace_snapshot['ppu_trace']
                renderer_trace = self._first_signal_trace_snapshot['renderer_trace']
                snapshot_frame_id = self._first_signal_trace_snapshot['frame_id']
                print(f"[FrameIdConsistency] Usando snapshot de traces (guardado en frame_id={snapshot_frame_id})")
            else:
                # Fallback: usar traces actuales (puede que no tengan los datos de first_signal)
                ppu_trace = self.ppu.get_buffer_trace_ring(max_events=128)
                renderer_trace = self._renderer.get_renderer_trace()
                print(f"[FrameIdConsistency] ⚠️ Usando traces actuales (snapshot no disponible)")
            # -----------------------------------------
            
            # Construir tabla FrameIdConsistency
            frame_id_consistency = []
            
            # Alrededor del first_signal (50 filas)
            if self._first_signal_frame_id is not None:
                start_fid = max(0, self._first_signal_frame_id - 25)
                end_fid = self._first_signal_frame_id + 25
                
                for fid in range(start_fid, end_fid + 1):
                    # Buscar en PPU trace
                    ppu_event = None
                    for e in ppu_trace:
                        if e.get('framebuffer_frame_id') == fid:
                            ppu_event = e
                            break
                    
                    # Buscar en renderer trace
                    renderer_event = None
                    for e in renderer_trace:
                        if e.get('frame_id_received') == fid:
                            renderer_event = e
                            break
                    
                    row = {
                        'fid': fid,
                        'ppu_front_fid': ppu_event.get('framebuffer_frame_id') if ppu_event else None,
                        'ppu_back_fid': ppu_event.get('frame_id') if ppu_event else None,
                        'ppu_front_rgb_crc': ppu_event.get('front_rgb_crc32') if ppu_event else None,
                        'renderer_received_fid': renderer_event.get('frame_id_received') if renderer_event else None,
                        'renderer_src_crc': renderer_event.get('src_crc32') if renderer_event else None,
                        'renderer_present_crc': renderer_event.get('present_crc32') if renderer_event else None,
                        'present_nonwhite': renderer_event.get('present_nonwhite') if renderer_event else None,
                    }
                    
                    # Añadir clasificación
                    row['classification'] = self._classify_frame_id_consistency(row)
                    
                    frame_id_consistency.append(row)
            
            return frame_id_consistency
        except Exception as e:
            print(f"[FrameIdConsistency] ⚠️ Error generando tabla: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _sample_vram_nonzero(self) -> int:
        """
        Cuenta bytes non-zero en VRAM 0x8000-0x9FFF (muestreo por bloques).
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 16º byte (0x2000 bytes / 16 = 512 muestras)
        for addr in range(0x8000, 0xA000, 16):
            value = self.mmu.read(addr)
            if value != 0:
                count += 1
        
        # Estimar total (multiplicar por 16)
        return count * 16
    
    def _sample_vram_nonzero_raw(self) -> int:
        """
        Cuenta bytes non-zero en VRAM usando read_raw (sin restricciones).
        
        Step 0450: Usa read_raw() para diagnóstico confiable, bypassing PPU mode restrictions.
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 16º byte (0x2000 bytes / 16 = 128 muestras)
        for addr in range(0x8000, 0xA000, 16):
            value = self.mmu.read_raw(addr)  # ← RAW, no read()
            if value != 0:
                count += 1
        
        # Estimar total (multiplicar por 16)
        return count * 16
    
    def _sample_oam_nonzero(self) -> int:
        """
        Cuenta bytes non-zero en OAM 0xFE00-0xFE9F (muestreo).
        
        Step 0444: Métricas OAM para validar DMA correctness.
        
        Returns:
            Número de bytes non-zero (estimado)
        """
        count = 0
        # Muestrear cada 4º byte (40 sprites * 4 bytes = 160 bytes, 40 muestras)
        for addr in range(0xFE00, 0xFEA0, 4):
            value = self.mmu.read(addr)
            if value != 0:
                count += 1
        # Estimar total (multiplicar por 4)
        return count * 4
    
    def _collect_metrics(self, frame_idx: int, ly_first: int, ly_mid: int, ly_last: int,
                        stat_first: int, stat_mid: int, stat_last: int) -> Dict:
        """
        Recolecta métricas del frame actual (Step 0443: incluye LY/STAT 3-points).
        
        Args:
            frame_idx: Índice del frame (0-based)
            ly_first: LY al inicio del frame
            ly_mid: LY a mitad del frame
            ly_last: LY al final del frame
            stat_first: STAT al inicio del frame
            stat_mid: STAT a mitad del frame
            stat_last: STAT al final del frame
        
        Returns:
            Diccionario con métricas
        """
        # Obtener framebuffer
        framebuffer = self.ppu.get_framebuffer_rgb()
        
        # Contar píxeles non-white
        nonwhite_pixels = self._sample_nonwhite_pixels(framebuffer)
        
        # Hash del framebuffer
        frame_hash = self._hash_framebuffer(framebuffer)
        
        # Step 0454: Calcular métricas robustas
        robust_metrics = self._calculate_robust_metrics(framebuffer)
        
        # Muestrear VRAM
        vram_nonzero = self._sample_vram_nonzero()
        
        # Step 0450: Muestrear VRAM usando read_raw (diagnóstico confiable)
        vram_nonzero_raw = self._sample_vram_nonzero_raw()
        
        # Step 0444: Muestrear OAM
        oam_nonzero = self._sample_oam_nonzero()
        
        # Leer registros I/O clave
        lcdc = self.mmu.read(0xFF40)
        stat = self.mmu.read(0xFF41)
        bgp = self.mmu.read(0xFF47)
        scy = self.mmu.read(0xFF42)
        scx = self.mmu.read(0xFF43)
        ly = self.mmu.read(0xFF44)
        pc = self.regs.pc
        
        # Step 0463: Derivar modo de tile data y tilemap base
        bg_tile_data_mode = "8000(unsigned)" if (lcdc & 0x10) else "8800(signed)"
        bg_tilemap_base = 0x9C00 if (lcdc & 0x08) else 0x9800
        win_tilemap_base = 0x9C00 if (lcdc & 0x40) else 0x9800
        
        # Step 0465: Contar nonzero bytes en ambos tilemaps usando read_raw() (RAW VRAM, sin restricciones)
        tilemap_nz_9800 = 0
        for addr in range(0x9800, 0x9C00):
            if self.mmu.read_raw(addr) != 0:  # Usar read_raw() para evitar restricciones
                tilemap_nz_9800 += 1
        
        tilemap_nz_9C00 = 0
        for addr in range(0x9C00, 0xA000):
            if self.mmu.read_raw(addr) != 0:  # Usar read_raw()
                tilemap_nz_9C00 += 1
        
        # Leer 16 tile IDs desde el base actual usando read_raw()
        tile_ids_sample = []
        for i in range(16):
            tile_ids_sample.append(self.mmu.read_raw(bg_tilemap_base + i))  # Usar read_raw()
        
        # Step 0474: Métricas IF/LY/STAT quirúrgicas
        if_read_count = self.mmu.get_if_read_count()
        if_write_count = self.mmu.get_if_write_count()
        last_if_read_val = self.mmu.get_last_if_read_val()
        last_if_write_val = self.mmu.get_last_if_write_val()
        last_if_write_pc = self.mmu.get_last_if_write_pc()
        if_writes_0 = self.mmu.get_if_writes_0()
        if_writes_nonzero = self.mmu.get_if_writes_nonzero()
        
        ly_read_min = self.mmu.get_ly_read_min()
        ly_read_max = self.mmu.get_ly_read_max()
        last_ly_read = self.mmu.get_last_ly_read()
        
        last_stat_read = self.mmu.get_last_stat_read()
        
        # Step 0475: Source tagging para IF/IE
        if_reads_program = self.mmu.get_if_reads_program() if hasattr(self.mmu, 'get_if_reads_program') else 0
        if_reads_cpu_poll = self.mmu.get_if_reads_cpu_poll() if hasattr(self.mmu, 'get_if_reads_cpu_poll') else 0
        if_writes_program = self.mmu.get_if_writes_program() if hasattr(self.mmu, 'get_if_writes_program') else 0
        ie_reads_program = self.mmu.get_ie_reads_program() if hasattr(self.mmu, 'get_ie_reads_program') else 0
        ie_reads_cpu_poll = self.mmu.get_ie_reads_cpu_poll() if hasattr(self.mmu, 'get_ie_reads_cpu_poll') else 0
        ie_writes_program = self.mmu.get_ie_writes_program() if hasattr(self.mmu, 'get_ie_writes_program') else 0
        
        # Step 0475: IF Clear on Service tracking
        last_irq_serviced_vector = self.cpu.get_last_irq_serviced_vector() if hasattr(self.cpu, 'get_last_irq_serviced_vector') else 0
        last_irq_serviced_timestamp = self.cpu.get_last_irq_serviced_timestamp() if hasattr(self.cpu, 'get_last_irq_serviced_timestamp') else 0
        last_if_before_service = self.cpu.get_last_if_before_service() if hasattr(self.cpu, 'get_last_if_before_service') else 0
        last_if_after_service = self.cpu.get_last_if_after_service() if hasattr(self.cpu, 'get_last_if_after_service') else 0
        last_if_clear_mask = self.cpu.get_last_if_clear_mask() if hasattr(self.cpu, 'get_last_if_clear_mask') else 0
        
        # Step 0475: Boot logo prefill status
        boot_logo_prefill_enabled = self.mmu.get_boot_logo_prefill_enabled() if hasattr(self.mmu, 'get_boot_logo_prefill_enabled') else 0
        
        metrics = {
            'frame': frame_idx,
            'pc': pc,
            'nonwhite_pixels': nonwhite_pixels,
            'frame_hash': frame_hash,
            'vram_nonzero': vram_nonzero,
            'vram_nonzero_raw': vram_nonzero_raw,  # Step 0450: VRAM raw (sin restricciones)
            'oam_nonzero': oam_nonzero,  # Step 0444: OAM metrics
            'lcdc': lcdc,
            'stat': stat,
            'bgp': bgp,
            'scy': scy,
            'scx': scx,
            'ly': ly,
            # Step 0443: LY/STAT 3-points sampling
            'ly_first': ly_first,
            'ly_mid': ly_mid,
            'ly_last': ly_last,
            'stat_first': stat_first,
            'stat_mid': stat_mid,
            'stat_last': stat_last,
            # Step 0454: Métricas robustas
            'unique_rgb_count': robust_metrics['unique_rgb_count'],
            'dominant_ratio': robust_metrics['dominant_ratio'],
            'frame_hash_robust': robust_metrics['frame_hash'],
            'hash_changed': robust_metrics['hash_changed'],
            # Step 0494: CGB Palette Proof
            'CGBPaletteProof': cgb_palette_proof if 'cgb_palette_proof' in locals() else {},
            # Step 0463: Modo tile data y tilemap base
            'bg_tile_data_mode': bg_tile_data_mode,
            'bg_tilemap_base': bg_tilemap_base,
            'win_tilemap_base': win_tilemap_base,
            # Step 0464: Tilemap nonzero counts y sample
            'tilemap_nz_9800': tilemap_nz_9800,
            'tilemap_nz_9C00': tilemap_nz_9C00,
            'tile_ids_sample': tile_ids_sample,
            # Step 0474: Métricas IF/LY/STAT quirúrgicas
            'if_read_count': if_read_count,
            'if_write_count': if_write_count,
            'last_if_read_val': last_if_read_val,
            'last_if_write_val': last_if_write_val,
            'last_if_write_pc': last_if_write_pc,
            'if_writes_0': if_writes_0,
            'if_writes_nonzero': if_writes_nonzero,
            'ly_read_min': ly_read_min,
            'ly_read_max': ly_read_max,
            'last_ly_read': last_ly_read,
            'last_stat_read': last_stat_read,
            # Step 0475: Source tagging para IF/IE
            'if_reads_program': if_reads_program,
            'if_reads_cpu_poll': if_reads_cpu_poll,
            'if_writes_program': if_writes_program,
            'ie_reads_program': ie_reads_program,
            'ie_reads_cpu_poll': ie_reads_cpu_poll,
            'ie_writes_program': ie_writes_program,
            # Step 0475: IF Clear on Service tracking
            'last_irq_serviced_vector': last_irq_serviced_vector,
            'last_irq_serviced_timestamp': last_irq_serviced_timestamp,
            'last_if_before_service': last_if_before_service,
            'last_if_after_service': last_if_after_service,
            'last_if_clear_mask': last_if_clear_mask,
            # Step 0475: Boot logo prefill status
            'boot_logo_prefill_enabled': boot_logo_prefill_enabled,
        }
        
        # Detectar primer frame non-white
        if self.first_nonwhite_frame is None and nonwhite_pixels > 0:
            self.first_nonwhite_frame = frame_idx
        
        return metrics
    
    def _dump_png(self, frame_idx: int, framebuffer: List[int]):
        """
        Dumped framebuffer a PNG (requiere PIL/Pillow).
        
        Args:
            frame_idx: Índice del frame
            framebuffer: Lista RGB del framebuffer
        """
        try:
            from PIL import Image
        except ImportError:
            print("WARNING: PIL/Pillow no disponible, no se puede generar PNG")
            return
        
        # Crear directorio out/
        out_dir = Path("tools/out")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Convertir lista plana a imagen
        # framebuffer = [R,G,B,R,G,B,...] (160*144*3 = 69120 valores)
        img_data = bytes(framebuffer)
        img = Image.frombytes('RGB', (self.SCREEN_WIDTH, self.SCREEN_HEIGHT), img_data)
        
        # Guardar
        out_path = out_dir / f"frame_{frame_idx:04d}.png"
        img.save(out_path)
        print(f"  [PNG] Guardado: {out_path}")
    
    def _dump_framebuffer_to_ppm(self, frame_idx: int):
        """
        Step 0488: Dump framebuffer a archivo PPM.
        
        Gateado por VIBOY_DUMP_FB_FRAME y VIBOY_DUMP_FB_PATH.
        
        Args:
            frame_idx: Índice del frame actual
        """
        import os
        
        env_frame = os.getenv("VIBOY_DUMP_FB_FRAME")
        env_path = os.getenv("VIBOY_DUMP_FB_PATH")
        
        if not env_frame or not env_path:
            return
        
        try:
            target_frame = int(env_frame)
        except ValueError:
            return
        
        if frame_idx != target_frame:
            return
        
        # Leer framebuffer de índices
        try:
            fb_indices = self.ppu.get_presented_framebuffer_indices()
            if fb_indices is None:
                return
        except (AttributeError, TypeError):
            return
        
        # Leer BGP
        bgp = self.mmu.read(0xFF47)
        
        # Paleta DMG greyscale
        shades = [
            (bgp >> 0) & 0x03,  # idx 0
            (bgp >> 2) & 0x03,  # idx 1
            (bgp >> 4) & 0x03,  # idx 2
            (bgp >> 6) & 0x03,  # idx 3
        ]
        
        # Mapeo shade → RGB
        shade_to_rgb = [
            (255, 255, 255),  # Shade 0 = blanco
            (192, 192, 192),  # Shade 1 = gris claro
            (96, 96, 96),     # Shade 2 = gris oscuro
            (0, 0, 0),        # Shade 3 = negro
        ]
        
        # Construir nombre de archivo (reemplazar #### con frame_number)
        path_template = env_path.replace("####", str(frame_idx))
        output_path = Path(path_template)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir PPM
        try:
            with open(output_path, 'wb') as f:
                # Header P6 (binary RGB)
                f.write(b"P6\n")
                f.write(f"{160} {144}\n".encode())
                f.write(b"255\n")
                
                # Píxeles
                for idx in fb_indices:
                    shade = shades[idx & 0x03]
                    r, g, b = shade_to_rgb[shade]
                    f.write(bytes([r, g, b]))
            
            print(f"[ROM-SMOKE] Framebuffer dump guardado en {output_path} (frame {frame_idx})")
        except Exception as e:
            print(f"[ROM-SMOKE] ERROR al escribir PPM: {e}")
    
    def _dump_rgb_framebuffer_to_ppm(self, frame_idx: int):
        """
        Step 0489: Dump framebuffer RGB a archivo PPM (Fase B).
        
        Gateado por VIBOY_DUMP_RGB_FRAME y VIBOY_DUMP_RGB_PATH.
        
        Args:
            frame_idx: Número de frame actual
        """
        import os
        
        env_frame = os.getenv("VIBOY_DUMP_RGB_FRAME")
        env_path = os.getenv("VIBOY_DUMP_RGB_PATH")
        
        if not env_frame or not env_path:
            return
        
        try:
            target_frame = int(env_frame)
        except ValueError:
            return
        
        if frame_idx != target_frame:
            return
        
        # Construir nombre de archivo (reemplazar #### con frame number)
        output_path = env_path.replace("####", f"{frame_idx:04d}")
        
        # Obtener framebuffer RGB desde PPU
        try:
            # Intentar obtener el buffer RGB directamente desde C++
            # Nota: Necesitamos un método en PPU para obtener el buffer RGB
            # Por ahora, convertimos desde índices usando BGP
            
            # Leer BGP para conversión DMG
            bgp = self.mmu.read(0xFF47)
            
            # Obtener framebuffer de índices
            fb_indices = self.ppu.get_framebuffer_indices()
            if not fb_indices or len(fb_indices) != 160 * 144:
                print(f"[ROM-SMOKE-RGB-DUMP] ERROR: Framebuffer inválido (len={len(fb_indices) if fb_indices else 0})")
                return
            
            # Convertir índices a RGB usando BGP
            shades = [
                (bgp >> 0) & 0x03,  # idx 0
                (bgp >> 2) & 0x03,  # idx 1
                (bgp >> 4) & 0x03,  # idx 2
                (bgp >> 6) & 0x03,  # idx 3
            ]
            
            shade_to_rgb = [
                (255, 255, 255),  # Shade 0 = blanco
                (192, 192, 192),  # Shade 1 = gris claro
                (96, 96, 96),     # Shade 2 = gris oscuro
                (0, 0, 0),        # Shade 3 = negro
            ]
            
            # Construir buffer RGB
            rgb_buffer = bytearray(160 * 144 * 3)
            for i in range(160 * 144):
                idx = fb_indices[i] & 0x03
                shade = shades[idx]
                r, g, b = shade_to_rgb[shade]
                rgb_buffer[i * 3 + 0] = r
                rgb_buffer[i * 3 + 1] = g
                rgb_buffer[i * 3 + 2] = b
            
            # Escribir PPM
            with open(output_path, 'wb') as f:
                # Header P6 (binary RGB)
                f.write(f"P6\n160 144\n255\n".encode('ascii'))
                f.write(rgb_buffer)
            
            print(f"[ROM-SMOKE-RGB-DUMP] Framebuffer RGB dump guardado en {output_path} (frame {frame_idx})")
            
        except Exception as e:
            print(f"[ROM-SMOKE-RGB-DUMP] ERROR al escribir PPM RGB: {e}")
            import traceback
            traceback.print_exc()
    
    def _dump_synchronized_buffers(self, frame_idx: int):
        """
        Step 0493: Dumps sincronizados de FB_INDEX, FB_RGB, FB_PRESENT_SRC en el mismo frame.
        
        Gateado por VIBOY_DUMP_RGB_FRAME (usa el mismo frame que RGB dump).
        Paths: VIBOY_DUMP_IDX_PATH, VIBOY_DUMP_RGB_PATH, VIBOY_DUMP_PRESENT_PATH
        
        Args:
            frame_idx: Número de frame actual
        """
        import os
        
        env_frame = os.getenv("VIBOY_DUMP_RGB_FRAME")
        if not env_frame:
            return
        
        try:
            target_frame = int(env_frame)
        except ValueError:
            return
        
        if frame_idx != target_frame:
            return
        
        # Dump FB_INDEX
        try:
            fb_indices = self.ppu.get_presented_framebuffer_indices()
            if fb_indices is not None:
                dump_path_idx = os.environ.get('VIBOY_DUMP_IDX_PATH', '/tmp/viboy_idx_f####.ppm')
                dump_path_idx = dump_path_idx.replace('####', str(frame_idx))
                
                # Leer BGP para conversión DMG
                bgp = self.mmu.read(0xFF47)
                shades = [
                    (bgp >> 0) & 0x03,
                    (bgp >> 2) & 0x03,
                    (bgp >> 4) & 0x03,
                    (bgp >> 6) & 0x03,
                ]
                shade_to_rgb = [
                    (255, 255, 255),  # Shade 0 = blanco
                    (192, 192, 192),  # Shade 1 = gris claro
                    (96, 96, 96),     # Shade 2 = gris oscuro
                    (0, 0, 0),        # Shade 3 = negro
                ]
                
                output_path_idx = Path(dump_path_idx)
                output_path_idx.parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_path_idx, 'wb') as f:
                    f.write(b"P6\n")
                    f.write(f"{160} {144}\n".encode())
                    f.write(b"255\n")
                    
                    for idx in fb_indices:
                        shade = shades[idx & 0x03]
                        r, g, b = shade_to_rgb[shade]
                        f.write(bytes([r, g, b]))
                
                print(f"[ROM-SMOKE-SYNC-DUMP] FB_INDEX dump guardado en {output_path_idx} (frame {frame_idx})")
        except Exception as e:
            print(f"[ROM-SMOKE-SYNC-DUMP] ERROR al escribir FB_INDEX PPM: {e}")
        
        # Dump FB_RGB (ya existe en _dump_rgb_framebuffer_to_ppm, pero lo hacemos aquí también para sincronización)
        try:
            # Obtener framebuffer RGB desde PPU (CGB)
            if hasattr(self.ppu, 'get_framebuffer_rgb'):
                fb_rgb = self.ppu.get_framebuffer_rgb()
                if fb_rgb is not None and len(fb_rgb) == 69120:  # 160 * 144 * 3
                    dump_path_rgb = os.environ.get('VIBOY_DUMP_RGB_PATH', '/tmp/viboy_rgb_f####.ppm')
                    dump_path_rgb = dump_path_rgb.replace('####', str(frame_idx))
                    
                    output_path_rgb = Path(dump_path_rgb)
                    output_path_rgb.parent.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path_rgb, 'wb') as f:
                        f.write(b"P6\n")
                        f.write(f"{160} {144}\n".encode())
                        f.write(b"255\n")
                        f.write(fb_rgb.tobytes() if hasattr(fb_rgb, 'tobytes') else bytes(fb_rgb))
                    
                    print(f"[ROM-SMOKE-SYNC-DUMP] FB_RGB dump guardado en {output_path_rgb} (frame {frame_idx})")
        except Exception as e:
            print(f"[ROM-SMOKE-SYNC-DUMP] ERROR al escribir FB_RGB PPM: {e}")
        
        # Dump FB_PRESENT_SRC (desde renderer si está disponible)
        # Nota: FB_PRESENT_SRC se genera en renderer.py, pero aquí podemos intentar obtenerlo
        # si el renderer está disponible. Por ahora, este dump se hace en renderer.py
        # cuando se llama render_frame() con el flag VIBOY_DUMP_RGB_FRAME.
        # No hacemos nada aquí para FB_PRESENT_SRC porque se maneja en renderer.py
    
    def run(self):
        """Ejecuta el smoke test."""
        # Step 0465: Imprimir estado de env vars para evidencia (solo en tools, no en runtime)
        import os
        env_vars = [
            'VIBOY_DEBUG_INJECTION',
            'VIBOY_FORCE_BGP',
            'VIBOY_AUTOPRESS',
            'VIBOY_FRAMEBUFFER_TRACE',
            'VIBOY_DEBUG_UI',
            'VIBOY_DEBUG_PPU',
            'VIBOY_DEBUG_IO'
        ]
        
        env_status = []
        for var in env_vars:
            value = os.environ.get(var, '0')
            env_status.append(f"{var}={value}")
        
        print(f"[ENV] {' '.join(env_status)}")
        
        print(f"=" * 80)
        print(f"ROM Smoke Test - Step 0443 (LY/STAT 3-Points Sampling)")
        print(f"=" * 80)
        print(f"ROM: {self.rom_path.name}")
        print(f"Max frames: {self.max_frames}")
        print(f"Max seconds: {self.max_seconds}")
        print(f"Dump every: {self.dump_every} frames" if self.dump_every > 0 else "Dump: final only")
        print(f"Dump PNG: {'Yes' if self.dump_png else 'No'}")
        print(f"Renderer headless: {'Yes' if self.use_renderer_headless else 'No'}")
        print(f"-" * 80)
        
        self.start_time = time.time()
        
        # Segmentos del frame para sampling 3-points (Step 0443)
        SEGMENT_1 = 0           # Inicio
        SEGMENT_2 = 35112       # Medio (~50%)
        SEGMENT_3 = 70224       # Final (CYCLES_PER_FRAME)
        
        for frame_idx in range(self.max_frames):
            # Timeout check
            elapsed = time.time() - self.start_time
            if elapsed > self.max_seconds:
                print(f"\nTIMEOUT: {self.max_seconds}s alcanzado, deteniendo en frame {frame_idx}")
                break
            
            # --- Step 0483: Auto-press support (VIBOY_AUTOPRESS) ---
            if hasattr(self, 'autopress_button') and self.autopress_button is not None:
                if frame_idx == getattr(self, 'autopress_frame', 60):
                    print(f"[AUTOPRESS] Frame {frame_idx}: Presionando botón índice {self.autopress_button}")
                    self.joypad.press_button(self.autopress_button)
                elif frame_idx == getattr(self, 'autopress_frame', 60) + 5:
                    # Soltar después de 5 frames
                    print(f"[AUTOPRESS] Frame {frame_idx}: Soltando botón índice {self.autopress_button}")
                    self.joypad.release_button(self.autopress_button)
            # -----------------------------------------
            
            # Ejecutar frame por segmentos para sampling 3-points
            frame_cycles = 0
            
            # Segmento 1: 0 → 35112 T-cycles
            while frame_cycles < SEGMENT_2:
                cycles = self.cpu.step()
                self.ppu.step(cycles)
                self.timer.step(cycles)
                frame_cycles += cycles
                
                # Step 0470: Muestrear PC cada N instrucciones
                self.step_count += 1
                if self.step_count % 50 == 0:  # Cada 50 steps
                    pc = self.regs.pc
                    self.pc_samples[pc] = self.pc_samples.get(pc, 0) + 1
            
            # Sample LY/STAT al final del segmento 1 (inicio del frame)
            ly_first = self.mmu.read(0xFF44)
            stat_first = self.mmu.read(0xFF41)
            
            # Segmento 2: 35112 → 70224 T-cycles
            while frame_cycles < SEGMENT_3:
                cycles = self.cpu.step()
                self.ppu.step(cycles)
                self.timer.step(cycles)
                frame_cycles += cycles
                
                # Step 0470: Muestrear PC cada N instrucciones
                self.step_count += 1
                if self.step_count % 50 == 0:  # Cada 50 steps
                    pc = self.regs.pc
                    self.pc_samples[pc] = self.pc_samples.get(pc, 0) + 1
            
            # Sample LY/STAT al final del segmento 2 (medio del frame)
            ly_mid = self.mmu.read(0xFF44)
            stat_mid = self.mmu.read(0xFF41)
            
            # Segmento 3: Ya completado, leer final
            ly_last = self.mmu.read(0xFF44)
            stat_last = self.mmu.read(0xFF41)
            
            # Recolectar métricas (incluye LY/STAT 3-points)
            metrics = self._collect_metrics(frame_idx, ly_first, ly_mid, ly_last, stat_first, stat_mid, stat_last)
            self.metrics.append(metrics)
            
            # --- Step 0502: Run until evidence (parada automática) ---
            # Verificar condición de parada: primer nonzero write
            if hasattr(self, 'stop_on_first_tiledata_nonzero_write') and self.stop_on_first_tiledata_nonzero_write:
                vram_stats_v2 = self.mmu.get_vram_write_stats_v2()
                if vram_stats_v2 and vram_stats_v2.get('first_nonzero_tiledata_write'):
                    first_nonzero = vram_stats_v2['first_nonzero_tiledata_write']
                    print(f"[STOP-EARLY] Primer write no-cero detectado en frame {first_nonzero['frame_id']}: PC=0x{first_nonzero['pc']:04X}, addr=0x{first_nonzero['addr']:04X}, value=0x{first_nonzero['value']:02X}")
                    break  # Parar ejecución
            
            # Verificar condición de parada: primer nonzero en VRAM (readback)
            if hasattr(self, 'stop_on_first_tiledata_nonzero') and self.stop_on_first_tiledata_nonzero:
                vram_stats_v2 = self.mmu.get_vram_write_stats_v2() if hasattr(self.mmu, 'get_vram_write_stats_v2') else None
                tiledata_nz = vram_stats_v2.get('tiledata_writes_nonzero_count', 0) if vram_stats_v2 else 0
                if tiledata_nz > 0:
                    print(f"[STOP-EARLY] Primer tiledata no-cero detectado: {tiledata_nz} writes no-cero")
                    break  # Parar ejecución
            
            # Step 0492: Stop early si tiledata_first_nonzero_frame existe (compatibilidad con código anterior)
            if hasattr(self, 'stop_early_on_first_nonzero') and self.stop_early_on_first_nonzero:
                vram_write_stats = self.mmu.get_vram_write_stats()
                if vram_write_stats and vram_write_stats.get('tiledata_first_nonzero_frame', 0) > 0:
                    print(f"[ROM-SMOKE] Stop early: tiledata_first_nonzero_frame={vram_write_stats['tiledata_first_nonzero_frame']}")
                    break
            # -----------------------------------------
            
            # Step 0488: Dump framebuffer a PPM si está activo
            self._dump_framebuffer_to_ppm(frame_idx)
            
            # Step 0489: Dump framebuffer RGB a PPM si está activo (Fase B)
            self._dump_rgb_framebuffer_to_ppm(frame_idx)
            
            # Step 0493: Dumps sincronizados para CGB (FB_INDEX, FB_RGB, FB_PRESENT_SRC en mismo frame)
            self._dump_synchronized_buffers(frame_idx)
            
            # --- Step 0498: First Signal Detector y Dumps Automáticos ---
            first_signal_id = self._detect_first_signal(self.ppu, self.mmu, self._renderer)
            
            if first_signal_id is not None:
                # Dump para first_signal_id, first_signal_id-1, first_signal_id+1
                current_frame_id = self.ppu.get_framebuffer_frame_id()
                
                for offset in [-1, 0, 1]:
                    target_frame_id = first_signal_id + offset
                    
                    # Solo dump si estamos en el frame_id correcto
                    if current_frame_id == target_frame_id:
                        # Dump FB_INDEX
                        self._dump_framebuffer_by_frame_id('idx', target_frame_id, self.ppu)
                        
                        # Dump FB_RGB
                        self._dump_framebuffer_by_frame_id('rgb', target_frame_id, self.ppu)
                        
                        # Dump FB_PRESENT_SRC (si hay renderer)
                        if self._renderer is not None:
                            self._dump_present_by_frame_id('present', target_frame_id, self._renderer)
            # -----------------------------------------
            
            # --- Step 0497: Usar renderer headless para capturar FB_PRESENT_SRC ---
            if self.use_renderer_headless and self._renderer is not None:
                try:
                    # Obtener framebuffer RGB desde PPU
                    fb_rgb = self.ppu.get_framebuffer_rgb()
                    
                    # Preparar métricas para el renderer
                    renderer_metrics = {
                        'pc': self.regs.pc,
                        'vram_nonzero': metrics.get('vram_nonzero', 0),
                        'lcdc': self.mmu.read(0xFF40),
                        'bgp': self.mmu.read(0xFF47),
                        'ly': self.mmu.read(0xFF44)
                    }
                    
                    # Renderizar frame (esto captura FB_PRESENT_SRC internamente)
                    self._renderer.render_frame(rgb_view=fb_rgb, metrics=renderer_metrics)
                except Exception as e:
                    # No fallar si el renderer tiene problemas, solo loggear
                    if frame_idx < 5:  # Solo loggear primeros 5 errores
                        print(f"[ROM-SMOKE] ⚠️ Error en renderer headless frame {frame_idx}: {e}")
            # -----------------------------------------
            
            # --- Step 0469: Snapshot cada 60 frames (o frames 0, 60, 120, 180, 240) ---
            should_snapshot = (frame_idx % 60 == 0) or frame_idx < 3
            if should_snapshot:
                # Leer registros
                pc = self.regs.pc
                ime = self.cpu.get_ime()
                halted = self.cpu.get_halted()
                
                ie = self.mmu.read(0xFFFF)
                if_reg = self.mmu.read(0xFF0F)
                
                # Contadores IRQ (si están expuestos)
                vblank_req = self.ppu.get_vblank_irq_requested_count() if hasattr(self.ppu, 'get_vblank_irq_requested_count') else 0
                vblank_serv = self.cpu.get_vblank_irq_serviced_count() if hasattr(self.cpu, 'get_vblank_irq_serviced_count') else 0
                
                # Step 0470: Contadores IE/IF writes y EI/DI
                ie_write_count = self.mmu.get_ie_write_count() if hasattr(self.mmu, 'get_ie_write_count') else 0
                if_write_count = self.mmu.get_if_write_count() if hasattr(self.mmu, 'get_if_write_count') else 0
                ei_count = self.cpu.get_ei_count() if hasattr(self.cpu, 'get_ei_count') else 0
                di_count = self.cpu.get_di_count() if hasattr(self.cpu, 'get_di_count') else 0
                
                # Step 0477: Tracking de transiciones IME + EI delayed
                ime_set_events_count = self.cpu.get_ime_set_events_count() if hasattr(self.cpu, 'get_ime_set_events_count') else 0
                last_ime_set_pc = self.cpu.get_last_ime_set_pc() if hasattr(self.cpu, 'get_last_ime_set_pc') else 0xFFFF
                last_ime_set_timestamp = self.cpu.get_last_ime_set_timestamp() if hasattr(self.cpu, 'get_last_ime_set_timestamp') else 0
                last_ei_pc = self.cpu.get_last_ei_pc() if hasattr(self.cpu, 'get_last_ei_pc') else 0xFFFF
                last_di_pc = self.cpu.get_last_di_pc() if hasattr(self.cpu, 'get_last_di_pc') else 0xFFFF
                ei_pending = self.cpu.get_ei_pending() if hasattr(self.cpu, 'get_ei_pending') else False
                
                # Step 0477: Timestamps de writes IE/IF
                last_ie_write_timestamp = self.mmu.get_last_ie_write_timestamp() if hasattr(self.mmu, 'get_last_ie_write_timestamp') else 0
                last_if_write_timestamp = self.mmu.get_last_if_write_timestamp() if hasattr(self.mmu, 'get_last_if_write_timestamp') else 0
                
                # Step 0471: Instrumentación microscópica de IE
                last_ie_write_value = self.mmu.get_last_ie_write_value() if hasattr(self.mmu, 'get_last_ie_write_value') else 0
                last_ie_read_value = self.mmu.get_last_ie_read_value() if hasattr(self.mmu, 'get_last_ie_read_value') else 0
                ie_read_count = self.mmu.get_ie_read_count() if hasattr(self.mmu, 'get_ie_read_count') else 0
                last_ie_write_pc = self.mmu.get_last_ie_write_pc() if hasattr(self.mmu, 'get_last_ie_write_pc') else 0
                
                # Step 0470: IO reads top 3
                io_reads = {}
                for io_addr in [0xFF00, 0xFF41, 0xFF44, 0xFF0F, 0xFFFF, 0xFF4D, 0xFF4F, 0xFF70]:
                    count = self.mmu.get_io_read_count(io_addr) if hasattr(self.mmu, 'get_io_read_count') else 0
                    if count > 0:
                        io_reads[io_addr] = count
                
                io_reads_top3 = sorted(io_reads.items(), key=lambda x: x[1], reverse=True)[:3]
                io_reads_str = ' '.join([f"0x{addr:04X}:{count}" for addr, count in io_reads_top3])
                
                # Step 0470: PC hotspots top 3
                pc_hotspots_top3 = sorted(self.pc_samples.items(), key=lambda x: x[1], reverse=True)[:3]
                pc_hotspots_str = ' '.join([f"0x{pc:04X}:{count}" for pc, count in pc_hotspots_top3])
                
                # Tilemap nonzero (RAW)
                tilemap_nz_9800_raw = 0
                for addr in range(0x9800, 0x9C00):
                    if self.mmu.read_raw(addr) != 0:
                        tilemap_nz_9800_raw += 1
                
                tilemap_nz_9C00_raw = 0
                for addr in range(0x9C00, 0xA000):
                    if self.mmu.read_raw(addr) != 0:
                        tilemap_nz_9C00_raw += 1
                
                # Registros PPU
                lcdc = self.mmu.read(0xFF40)
                stat = self.mmu.read(0xFF41)
                ly = self.mmu.read(0xFF44)
                
                # Step 0472: Power-up defaults (DMG)
                bgp = self.mmu.read(0xFF47)
                obp0 = self.mmu.read(0xFF48)
                obp1 = self.mmu.read(0xFF49)
                
                # Step 0472: Speed switch (CGB)
                key1 = self.mmu.read(0xFF4D)
                joyp = self.mmu.read(0xFF00)
                
                # Step 0472: STOP execution
                stop_executed_count = self.cpu.get_stop_executed_count() if hasattr(self.cpu, 'get_stop_executed_count') else 0
                last_stop_pc = self.cpu.get_last_stop_pc() if hasattr(self.cpu, 'get_last_stop_pc') else 0xFFFF
                
                # Step 0472: KEY1 writes
                key1_write_count = self.mmu.get_key1_write_count() if hasattr(self.mmu, 'get_key1_write_count') else 0
                last_key1_write_value = self.mmu.get_last_key1_write_value() if hasattr(self.mmu, 'get_last_key1_write_value') else 0
                last_key1_write_pc = self.mmu.get_last_key1_write_pc() if hasattr(self.mmu, 'get_last_key1_write_pc') else 0xFFFF
                
                # Step 0472: JOYP writes
                joyp_write_count = self.mmu.get_joyp_write_count() if hasattr(self.mmu, 'get_joyp_write_count') else 0
                last_joyp_write_value = self.mmu.get_last_joyp_write_value() if hasattr(self.mmu, 'get_last_joyp_write_value') else 0
                last_joyp_write_pc = self.mmu.get_last_joyp_write_pc() if hasattr(self.mmu, 'get_last_joyp_write_pc') else 0xFFFF
                
                # Step 0471: fb_nonzero = count de índices != 0 en framebuffer (sobre 23040 píxeles)
                fb_nonzero = 0
                try:
                    fb_indices = self.ppu.get_presented_framebuffer_indices()
                    if fb_indices is not None:
                        # fb_indices es bytes, indexable como bytes
                        for idx in range(23040):  # 160 * 144
                            if fb_indices[idx] != 0:
                                fb_nonzero += 1
                except (AttributeError, TypeError, IndexError):
                    fb_nonzero = 0  # Fallback si no está disponible
                
                # Step 0474: Métricas IF/LY/STAT quirúrgicas
                if_read_count = metrics.get('if_read_count', 0)
                if_write_count = metrics.get('if_write_count', 0)
                last_if_read_val = metrics.get('last_if_read_val', 0)
                last_if_write_val = metrics.get('last_if_write_val', 0)
                last_if_write_pc = metrics.get('last_if_write_pc', 0)
                if_writes_0 = metrics.get('if_writes_0', 0)
                if_writes_nonzero = metrics.get('if_writes_nonzero', 0)
                ly_read_min = metrics.get('ly_read_min', 0)
                ly_read_max = metrics.get('ly_read_max', 0)
                last_ly_read = metrics.get('last_ly_read', 0)
                last_stat_read = metrics.get('last_stat_read', 0)
                
                # Step 0475: Source tagging para IF/IE
                if_reads_program = metrics.get('if_reads_program', 0)
                if_reads_cpu_poll = metrics.get('if_reads_cpu_poll', 0)
                if_writes_program = metrics.get('if_writes_program', 0)
                ie_reads_program = metrics.get('ie_reads_program', 0)
                ie_reads_cpu_poll = metrics.get('ie_reads_cpu_poll', 0)
                ie_writes_program = metrics.get('ie_writes_program', 0)
                
                # Step 0475: IF Clear on Service tracking
                last_irq_serviced_vector = metrics.get('last_irq_serviced_vector', 0)
                last_irq_serviced_timestamp = metrics.get('last_irq_serviced_timestamp', 0)
                last_if_before_service = metrics.get('last_if_before_service', 0)
                last_if_after_service = metrics.get('last_if_after_service', 0)
                last_if_clear_mask = metrics.get('last_if_clear_mask', 0)
                
                # Step 0475: Boot logo prefill status
                boot_logo_prefill_enabled = metrics.get('boot_logo_prefill_enabled', 0)
                
                # Step 0480/0483: HRAM FF92 metrics (quirúrgico, gated por VIBOY_DEBUG_HRAM)
                hram_ff92_addr = 0xFF92
                hram_ff92_write_count = self.mmu.get_hram_write_count(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_write_count') else 0
                hram_ff92_read_count_program = self.mmu.get_hram_read_count_program(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_read_count_program') else 0
                last_hram_ff92_write_pc = self.mmu.get_hram_last_write_pc(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_last_write_pc') else 0xFFFF
                last_hram_ff92_write_value = self.mmu.get_hram_last_write_value(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_last_write_value') else 0
                first_hram_ff92_write_frame = self.mmu.get_hram_first_write_frame(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_first_write_frame') else 0
                last_hram_ff92_write_frame = self.mmu.get_hram_last_write_frame(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_last_write_frame') else 0
                last_hram_ff92_read_pc = self.mmu.get_hram_last_read_pc(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_last_read_pc') else 0xFFFF
                last_hram_ff92_read_value = self.mmu.get_hram_last_read_value(hram_ff92_addr) if hasattr(self.mmu, 'get_hram_last_read_value') else 0
                
                # Step 0480: JOYP read metrics (último valor leído)
                last_joyp_read_value = joyp  # Ya leído arriba
                
                # Step 0474/0479: Obtener PC hotspot #1 y disasembly
                pc_hotspot_1 = None
                disasm_snippet = ""
                io_touched = []
                
                # Step 0479: Loop I/O pattern (Fase A1)
                loop_waits_on = None
                loop_mask = None
                loop_cmp = None
                loop_pattern = None
                
                if pc_hotspots_top3:
                    pc_hotspot_1 = pc_hotspots_top3[0][0]  # PC del hotspot más frecuente
                    
                    # Step 0479: Usar disasm_window() para análisis del loop
                    try:
                        # Desensamblar ventana alrededor del hotspot
                        disasm_window_list = disasm_window(self.mmu, pc_hotspot_1, before=16, after=32)
                        
                        # Construir disasm_snippet para snapshot (más instrucciones para análisis)
                        disasm_lines = []
                        for inst_pc, mnemonic, is_current in disasm_window_list[:20]:  # Primeras 20 instrucciones
                            marker = " ←" if is_current else ""
                            disasm_lines.append(f"0x{inst_pc:04X}: {mnemonic}{marker}")
                        disasm_snippet = " | ".join(disasm_lines[:12])  # Primeras 12 instrucciones para snapshot
                        
                        # Step 0479: Parsear loop I/O pattern
                        loop_io_result = parse_loop_io_pattern(disasm_window_list)
                        loop_waits_on = loop_io_result.get("waits_on")
                        loop_mask = loop_io_result.get("mask")
                        loop_cmp = loop_io_result.get("cmp")
                        loop_pattern = loop_io_result.get("pattern")
                        
                        # Identificar IO tocado por el bucle (analizar disasm)
                        for inst_pc, mnemonic, _ in disasm_window_list:
                            if "0xFF" in mnemonic:
                                # Extraer dirección IO del mnemónico
                                import re
                                matches = re.findall(r'0x([0-9A-F]{2,4})', mnemonic)
                                for match in matches:
                                    io_addr = int(match, 16)
                                    if 0xFF00 <= io_addr <= 0xFFFF and io_addr not in io_touched:
                                        io_touched.append(io_addr)
                    except Exception as e:
                        disasm_snippet = f"ERROR: {e}"
                
                io_touched_str = ' '.join([f"0x{addr:04X}" for addr in sorted(io_touched)]) if io_touched else "None"
                
                # Step 0479: Formatear loop I/O pattern para snapshot
                loop_waits_on_str = f"0x{loop_waits_on:04X}" if loop_waits_on is not None else "None"
                loop_mask_str = f"0x{loop_mask:02X}" if loop_mask is not None else "None"
                loop_cmp_str = f"0x{loop_cmp:02X}" if loop_cmp is not None else "None"
                loop_pattern_str = loop_pattern if loop_pattern is not None else "None"
                
                # Step 0482/0483: Branch Info, Last Cmp/Bit, Dynamic Wait Loop, Unknown Opcodes
                # Obtener datos de CPU (gated por VIBOY_DEBUG_BRANCH=1)
                import os
                debug_branch = os.getenv("VIBOY_DEBUG_BRANCH") == "1"
                
                branch_info_str = "N/A"
                if debug_branch and pc_hotspot_1 is not None:
                    try:
                        # Obtener top branch blockers
                        top_blockers = self.cpu.get_top_branch_blockers(3) if hasattr(self.cpu, 'get_top_branch_blockers') else []
                        if top_blockers:
                            blocker_strs = []
                            for pc_blk, bd_dict in top_blockers[:3]:
                                taken = bd_dict.get('taken_count', 0)
                                not_taken = bd_dict.get('not_taken_count', 0)
                                blocker_strs.append(f"0x{pc_blk:04X}:{taken}/{not_taken}")
                            branch_info_str = ' '.join(blocker_strs) if blocker_strs else "N/A"
                    except Exception:
                        branch_info_str = "N/A"
                
                last_cmp_str = "N/A"
                last_bit_str = "N/A"
                if debug_branch:
                    try:
                        last_cmp_pc = self.cpu.get_last_cmp_pc() if hasattr(self.cpu, 'get_last_cmp_pc') else 0xFFFF
                        last_cmp_a = self.cpu.get_last_cmp_a() if hasattr(self.cpu, 'get_last_cmp_a') else 0
                        last_cmp_imm = self.cpu.get_last_cmp_imm() if hasattr(self.cpu, 'get_last_cmp_imm') else 0
                        if last_cmp_pc != 0xFFFF:
                            last_cmp_str = f"PC=0x{last_cmp_pc:04X} A=0x{last_cmp_a:02X} imm=0x{last_cmp_imm:02X}"
                        
                        last_bit_pc = self.cpu.get_last_bit_pc() if hasattr(self.cpu, 'get_last_bit_pc') else 0xFFFF
                        last_bit_n = self.cpu.get_last_bit_n() if hasattr(self.cpu, 'get_last_bit_n') else 0
                        last_bit_value = self.cpu.get_last_bit_value() if hasattr(self.cpu, 'get_last_bit_value') else 0
                        if last_bit_pc != 0xFFFF:
                            last_bit_str = f"PC=0x{last_bit_pc:04X} bit{last_bit_n}={last_bit_value}"
                    except Exception:
                        pass
                
                dynamic_wait_loop_str = "N/A"
                if loop_waits_on is not None:
                    dynamic_wait_loop_str = f"waits_on=0x{loop_waits_on:04X}"
                    if loop_mask is not None:
                        dynamic_wait_loop_str += f" mask=0x{loop_mask:02X}"
                    if loop_cmp is not None:
                        dynamic_wait_loop_str += f" cmp=0x{loop_cmp:02X}"
                
                unknown_opcodes_str = "N/A"
                if pc_hotspot_1 is not None:
                    try:
                        disasm_window_list = disasm_window(self.mmu, pc_hotspot_1, before=16, after=32)
                        unknown_hist = get_unknown_opcode_histogram(disasm_window_list)
                        if unknown_hist:
                            opcode_strs = [f"0x{op:02X}:{cnt}" for op, cnt in unknown_hist[:5]]
                            unknown_opcodes_str = ' '.join(opcode_strs) if opcode_strs else "N/A"
                    except Exception:
                        pass
                
                # Step 0482: LCDC Disable Events
                lcdc_disable_events = self.mmu.get_lcdc_disable_events() if hasattr(self.mmu, 'get_lcdc_disable_events') else 0
                last_lcdc_write_pc = self.mmu.get_last_lcdc_write_pc() if hasattr(self.mmu, 'get_last_lcdc_write_pc') else 0xFFFF
                last_lcdc_write_value = self.mmu.get_last_lcdc_write_value() if hasattr(self.mmu, 'get_last_lcdc_write_value') else 0
                
                # Step 0484: LCDC Current
                lcdc_current = self.mmu.get_lcdc_current() if hasattr(self.mmu, 'get_lcdc_current') else 0
                
                # Step 0484: LY Distribution Top 5
                ly_distribution_top5 = []
                if debug_branch:
                    try:
                        ly_dist = self.cpu.get_ly_distribution_top5() if hasattr(self.cpu, 'get_ly_distribution_top5') else []
                        ly_distribution_top5 = [(val, count) for val, count in ly_dist]
                    except Exception:
                        pass
                ly_dist_str = ' '.join([f"0x{val:02X}:{cnt}" for val, cnt in ly_distribution_top5]) if ly_distribution_top5 else "N/A"
                
                # Step 0484: Last Load A from LY
                last_load_a_from_ly = False
                last_load_a_ly_value = 0
                if debug_branch:
                    try:
                        last_load_a_addr = self.cpu.get_last_load_a_addr() if hasattr(self.cpu, 'get_last_load_a_addr') else 0xFFFF
                        if last_load_a_addr == 0xFF44:  # LY register
                            last_load_a_from_ly = True
                            last_load_a_ly_value = self.cpu.get_last_load_a_value() if hasattr(self.cpu, 'get_last_load_a_value') else 0
                    except Exception:
                        pass
                
                # Step 0484: Branch 0x1290 Stats
                branch_0x1290_taken_count = 0
                branch_0x1290_not_taken_count = 0
                branch_0x1290_last_flags = 0
                branch_0x1290_last_taken = False
                if debug_branch:
                    try:
                        branch_0x1290_taken_count = self.cpu.get_branch_0x1290_taken_count() if hasattr(self.cpu, 'get_branch_0x1290_taken_count') else 0
                        branch_0x1290_not_taken_count = self.cpu.get_branch_0x1290_not_taken_count() if hasattr(self.cpu, 'get_branch_0x1290_not_taken_count') else 0
                        branch_0x1290_last_flags = self.cpu.get_branch_0x1290_last_flags() if hasattr(self.cpu, 'get_branch_0x1290_last_flags') else 0
                        branch_0x1290_last_taken = self.cpu.get_branch_0x1290_last_taken() if hasattr(self.cpu, 'get_branch_0x1290_last_taken') else False
                    except Exception:
                        pass
                
                # Step 0484: JOYP Write Distribution Top 5
                joyp_write_distribution_top5 = []
                try:
                    joyp_dist = self.mmu.get_joyp_write_distribution_top5() if hasattr(self.mmu, 'get_joyp_write_distribution_top5') else []
                    joyp_write_distribution_top5 = [(val, count) for val, count in joyp_dist]
                except Exception:
                    pass
                joyp_write_dist_str = ' '.join([f"0x{val:02X}:{cnt}" for val, cnt in joyp_write_distribution_top5]) if joyp_write_distribution_top5 else "N/A"
                
                # Step 0484: JOYP Read Select Bits
                joyp_last_read_select_bits = 0
                joyp_last_read_low_nibble = 0
                try:
                    joyp_last_read_select_bits = self.mmu.get_joyp_last_read_select_bits() if hasattr(self.mmu, 'get_joyp_last_read_select_bits') else 0
                    joyp_last_read_low_nibble = self.mmu.get_joyp_last_read_low_nibble() if hasattr(self.mmu, 'get_joyp_last_read_low_nibble') else 0
                except Exception:
                    pass
                
                # Step 0485: Mario Loop LY Watch (gated por VIBOY_DEBUG_MARIO_LOOP=1)
                mario_loop_ly_reads_total = 0
                mario_loop_ly_eq_0x91_count = 0
                mario_loop_ly_last_value = 0
                mario_loop_ly_last_timestamp = 0
                mario_loop_ly_last_pc = 0xFFFF
                debug_mario_loop = os.getenv("VIBOY_DEBUG_MARIO_LOOP") == "1"
                if debug_mario_loop:
                    try:
                        mario_loop_ly_reads_total = self.cpu.get_mario_loop_ly_reads_total() if hasattr(self.cpu, 'get_mario_loop_ly_reads_total') else 0
                        mario_loop_ly_eq_0x91_count = self.cpu.get_mario_loop_ly_eq_0x91_count() if hasattr(self.cpu, 'get_mario_loop_ly_eq_0x91_count') else 0
                        mario_loop_ly_last_value = self.cpu.get_mario_loop_ly_last_value() if hasattr(self.cpu, 'get_mario_loop_ly_last_value') else 0
                        mario_loop_ly_last_timestamp = self.cpu.get_mario_loop_ly_last_timestamp() if hasattr(self.cpu, 'get_mario_loop_ly_last_timestamp') else 0
                        mario_loop_ly_last_pc = self.cpu.get_mario_loop_ly_last_pc() if hasattr(self.cpu, 'get_mario_loop_ly_last_pc') else 0xFFFF
                    except Exception:
                        pass
                
                # Step 0485: Branch 0x1290 Correlation (gated por VIBOY_DEBUG_MARIO_LOOP=1)
                branch_0x1290_eval_count = 0
                branch_0x1290_taken_count_0485 = 0
                branch_0x1290_not_taken_count_0485 = 0
                branch_0x1290_last_not_taken_ly_value = 0
                branch_0x1290_last_not_taken_flags = 0
                branch_0x1290_last_not_taken_next_pc = 0xFFFF
                if debug_mario_loop:
                    try:
                        branch_0x1290_eval_count = self.cpu.get_branch_0x1290_eval_count() if hasattr(self.cpu, 'get_branch_0x1290_eval_count') else 0
                        branch_0x1290_taken_count_0485 = self.cpu.get_branch_0x1290_taken_count_0485() if hasattr(self.cpu, 'get_branch_0x1290_taken_count_0485') else 0
                        branch_0x1290_not_taken_count_0485 = self.cpu.get_branch_0x1290_not_taken_count_0485() if hasattr(self.cpu, 'get_branch_0x1290_not_taken_count_0485') else 0
                        branch_0x1290_last_not_taken_ly_value = self.cpu.get_branch_0x1290_last_not_taken_ly_value() if hasattr(self.cpu, 'get_branch_0x1290_last_not_taken_ly_value') else 0
                        branch_0x1290_last_not_taken_flags = self.cpu.get_branch_0x1290_last_not_taken_flags() if hasattr(self.cpu, 'get_branch_0x1290_last_not_taken_flags') else 0
                        branch_0x1290_last_not_taken_next_pc = self.cpu.get_branch_0x1290_last_not_taken_next_pc() if hasattr(self.cpu, 'get_branch_0x1290_last_not_taken_next_pc') else 0xFFFF
                    except Exception:
                        pass
                
                # Step 0485: Exec Coverage para ventana Mario (0x1270..0x12B0)
                exec_count_0x1288 = 0
                exec_count_0x1298 = 0
                if debug_mario_loop:
                    try:
                        exec_count_0x1288 = self.cpu.get_exec_count(0x1288) if hasattr(self.cpu, 'get_exec_count') else 0
                        exec_count_0x1298 = self.cpu.get_exec_count(0x1298) if hasattr(self.cpu, 'get_exec_count') else 0
                    except Exception:
                        pass
                
                # Step 0485: JOYP Trace (gated por VIBOY_DEBUG_JOYP_TRACE=1)
                joyp_trace_tail = []
                joyp_reads_with_buttons_selected_count = 0
                joyp_reads_with_dpad_selected_count = 0
                joyp_reads_with_none_selected_count = 0
                debug_joyp_trace = os.getenv("VIBOY_DEBUG_JOYP_TRACE") == "1"
                if debug_joyp_trace:
                    try:
                        # Obtener últimos 16 eventos del trace
                        trace_tail = self.mmu.get_joyp_trace_tail(16) if hasattr(self.mmu, 'get_joyp_trace_tail') else []
                        joyp_trace_tail = trace_tail
                        joyp_reads_with_buttons_selected_count = self.mmu.get_joyp_reads_with_buttons_selected_count() if hasattr(self.mmu, 'get_joyp_reads_with_buttons_selected_count') else 0
                        joyp_reads_with_dpad_selected_count = self.mmu.get_joyp_reads_with_dpad_selected_count() if hasattr(self.mmu, 'get_joyp_reads_with_dpad_selected_count') else 0
                        joyp_reads_with_none_selected_count = self.mmu.get_joyp_reads_with_none_selected_count() if hasattr(self.mmu, 'get_joyp_reads_with_none_selected_count') else 0
                    except Exception:
                        pass
                
                # Step 0486: Añadir IE/IME/IF explícitos al snapshot
                irq_serviced_count = vblank_serv  # Contador de IRQs servidas (VBlank por ahora)
                
                # Step 0488: FrameBufferStats (gateado por VIBOY_DEBUG_FB_STATS=1)
                fb_stats = None
                fb_stats_str = "N/A"
                import os
                if os.getenv("VIBOY_DEBUG_FB_STATS") == "1":
                    try:
                        fb_stats = self.ppu.get_framebuffer_stats()
                        if fb_stats:
                            fb_stats_str = (f"CRC32=0x{fb_stats['fb_crc32']:08X} "
                                          f"UniqueColors={fb_stats['fb_unique_colors']} "
                                          f"NonWhite={fb_stats['fb_nonwhite_count']} "
                                          f"NonBlack={fb_stats['fb_nonblack_count']} "
                                          f"Top4={fb_stats['fb_top4_colors']} "
                                          f"Top4Count={fb_stats['fb_top4_colors_count']} "
                                          f"Changed={1 if fb_stats['fb_changed_since_last'] else 0}")
                    except (AttributeError, TypeError, KeyError) as e:
                        fb_stats_str = f"ERROR: {e}"
                
                # Step 0489: ThreeBufferStats (gateado por VIBOY_DEBUG_PRESENT_TRACE=1)
                three_buf_stats = None
                three_buf_stats_str = "N/A"
                present_details = {}  # Step 0496: PresentDetails
                if os.getenv("VIBOY_DEBUG_PRESENT_TRACE") == "1":
                    try:
                        three_buf_stats = self.ppu.get_three_buffer_stats()
                        if three_buf_stats:
                            three_buf_stats_str = (f"IdxCRC32=0x{three_buf_stats['idx_crc32']:08X} "
                                                   f"IdxUnique={three_buf_stats['idx_unique']} "
                                                   f"IdxNonZero={three_buf_stats['idx_nonzero']} | "
                                                   f"RgbCRC32=0x{three_buf_stats['rgb_crc32']:08X} "
                                                   f"RgbUnique={three_buf_stats['rgb_unique_colors_approx']} "
                                                   f"RgbNonWhite={three_buf_stats['rgb_nonwhite_count']} | "
                                                   f"PresentCRC32=0x{three_buf_stats['present_crc32']:08X} "
                                                   f"PresentNonWhite={three_buf_stats['present_nonwhite_count']}")
                            
                            # --- Step 0496: PresentDetails desde ThreeBufferStats ---
                            present_details = {
                                'present_fmt': three_buf_stats.get('present_fmt', 0),
                                'present_pitch': three_buf_stats.get('present_pitch', 0),
                                'present_w': three_buf_stats.get('present_w', 0),
                                'present_h': three_buf_stats.get('present_h', 0),
                                'present_bytes_len': three_buf_stats.get('present_w', 0) * three_buf_stats.get('present_h', 0) * 3,  # RGB888
                            }
                    except (AttributeError, TypeError, KeyError) as e:
                        three_buf_stats_str = f"ERROR: {e}"
                        present_details = {'error': str(e)}
                
                # Step 0489: CGBPaletteWriteStats (gateado por VIBOY_DEBUG_CGB_PALETTE_WRITES=1)
                # Step 0494: Reforzado con decode de palette0[0..3] y nonwhite entries
                cgb_pal_stats = None
                cgb_pal_stats_str = "N/A"
                cgb_palette_proof = {}  # Step 0494: CGB Palette Proof
                if os.getenv("VIBOY_DEBUG_CGB_PALETTE_WRITES") == "1":
                    try:
                        cgb_pal_stats = self.mmu.get_cgb_palette_write_stats()
                        if cgb_pal_stats:
                            cgb_pal_stats_str = (f"BGPD_Writes={cgb_pal_stats['bgpd_write_count']} "
                                                f"BGPD_LastPC=0x{cgb_pal_stats['last_bgpd_write_pc']:04X} "
                                                f"BGPD_LastVal=0x{cgb_pal_stats['last_bgpd_value']:02X} "
                                                f"BGPI=0x{cgb_pal_stats['last_bgpi']:02X} | "
                                                f"OBPD_Writes={cgb_pal_stats['obpd_write_count']} "
                                                f"OBPD_LastPC=0x{cgb_pal_stats['last_obpd_write_pc']:04X} "
                                                f"OBPD_LastVal=0x{cgb_pal_stats['last_obpd_value']:02X} "
                                                f"OBPI=0x{cgb_pal_stats['last_obpi']:02X}")
                            
                            # --- Step 0494: Decode de palette0[0..3] (primeras 4 entradas de BG palette 0) ---
                            palette0_decode = []
                            try:
                                for color_idx in range(4):
                                    base = 0 * 8 + color_idx * 2  # Palette 0, color color_idx
                                    lo = self.mmu.read_bg_palette_data(base)
                                    hi = self.mmu.read_bg_palette_data(base + 1)
                                    bgr555 = lo | (hi << 8)
                                    
                                    # Extraer componentes BGR555
                                    r5 = (bgr555 >> 0) & 0x1F
                                    g5 = (bgr555 >> 5) & 0x1F
                                    b5 = (bgr555 >> 10) & 0x1F
                                    
                                    # Convertir a RGB888
                                    r = int((r5 * 255) / 31)
                                    g = int((g5 * 255) / 31)
                                    b = int((b5 * 255) / 31)
                                    
                                    palette0_decode.append({
                                        'color_idx': color_idx,
                                        'bgr555': f'0x{bgr555:04X}',
                                        'rgb888': f'({r},{g},{b})',
                                    })
                            except (AttributeError, TypeError) as e:
                                palette0_decode = [{'error': str(e)}]
                            
                            # --- Step 0494: Nonwhite entries (contar paletas con al menos un color no-blanco) ---
                            bg_palette_nonwhite_entries = 0
                            try:
                                for palette_id in range(8):
                                    has_nonwhite = False
                                    for color_idx in range(4):
                                        base = palette_id * 8 + color_idx * 2
                                        lo = self.mmu.read_bg_palette_data(base)
                                        hi = self.mmu.read_bg_palette_data(base + 1)
                                        bgr555 = lo | (hi << 8)
                                        
                                        # Verificar si es blanco (0x7FFF en BGR555)
                                        if bgr555 != 0x7FFF:
                                            has_nonwhite = True
                                            break
                                    if has_nonwhite:
                                        bg_palette_nonwhite_entries += 1
                            except (AttributeError, TypeError):
                                bg_palette_nonwhite_entries = 0
                            
                            # Construir CGB Palette Proof
                            cgb_palette_proof = {
                                'bgpd_write_count': cgb_pal_stats['bgpd_write_count'],
                                'obpd_write_count': cgb_pal_stats['obpd_write_count'],
                                'last_bgpd_write_pc': cgb_pal_stats['last_bgpd_write_pc'],
                                'last_bgpd_value': cgb_pal_stats['last_bgpd_value'],
                                'last_bgpi': cgb_pal_stats['last_bgpi'],
                                'last_obpd_write_pc': cgb_pal_stats['last_obpd_write_pc'],
                                'last_obpd_value': cgb_pal_stats['last_obpd_value'],
                                'last_obpi': cgb_pal_stats['last_obpi'],
                                'palette0_decode': palette0_decode,  # Step 0494
                                'bg_palette_nonwhite_entries': bg_palette_nonwhite_entries,  # Step 0494
                            }
                    except (AttributeError, TypeError, KeyError) as e:
                        cgb_pal_stats_str = f"ERROR: {e}"
                        cgb_palette_proof = {'error': str(e)}
                
                # Step 0489: DMGTileFetchStats (gateado por VIBOY_DEBUG_DMG_TILE_FETCH=1)
                dmg_tile_stats = None
                dmg_tile_stats_str = "N/A"
                if os.getenv("VIBOY_DEBUG_DMG_TILE_FETCH") == "1":
                    try:
                        dmg_tile_stats = self.ppu.get_dmg_tile_fetch_stats()
                        if dmg_tile_stats:
                            dmg_tile_stats_str = (f"TileBytesTotal={dmg_tile_stats['tile_bytes_read_total_count']} "
                                                 f"TileBytesNonZero={dmg_tile_stats['tile_bytes_read_nonzero_count']}")
                    except (AttributeError, TypeError, KeyError) as e:
                        dmg_tile_stats_str = f"ERROR: {e}"
                
                # Step 0490: VRAM por regiones (tiledata vs tilemap)
                vram_tiledata_nonzero = 0
                vram_tilemap_nonzero = 0
                try:
                    # Contar bytes non-zero en tiledata (0x8000-0x97FF = 6144 bytes)
                    for addr in range(0x8000, 0x9800):
                        if self.mmu.read_raw(addr) != 0:
                            vram_tiledata_nonzero += 1
                    
                    # Contar bytes non-zero en tilemap (0x9800-0x9FFF = 2048 bytes)
                    for addr in range(0x9800, 0xA000):
                        if self.mmu.read_raw(addr) != 0:
                            vram_tilemap_nonzero += 1
                except Exception as e:
                    pass
                
                # Step 0490: VRAMWriteStats (gateado por VIBOY_DEBUG_VRAM_WRITES=1)
                # Step 0491: Ampliada para separar attempts vs nonzero writes + bank + VBK
                vram_write_stats = None
                vram_write_stats_str = "N/A"
                if os.getenv("VIBOY_DEBUG_VRAM_WRITES") == "1":
                    try:
                        vram_write_stats = self.mmu.get_vram_write_stats()
                        if vram_write_stats:
                            vram_write_stats_str = (
                                f"TiledataAttemptsB0={vram_write_stats.get('tiledata_attempts_bank0', 0)} "
                                f"TiledataAttemptsB1={vram_write_stats.get('tiledata_attempts_bank1', 0)} "
                                f"TiledataNonZeroB0={vram_write_stats.get('tiledata_nonzero_writes_bank0', 0)} "
                                f"TiledataNonZeroB1={vram_write_stats.get('tiledata_nonzero_writes_bank1', 0)} "
                                f"TilemapAttemptsB0={vram_write_stats.get('tilemap_attempts_bank0', 0)} "
                                f"TilemapAttemptsB1={vram_write_stats.get('tilemap_attempts_bank1', 0)} "
                                f"TilemapNonZeroB0={vram_write_stats.get('tilemap_nonzero_writes_bank0', 0)} "
                                f"TilemapNonZeroB1={vram_write_stats.get('tilemap_nonzero_writes_bank1', 0)} "
                                f"LastNonZeroTiledataPC=0x{vram_write_stats.get('last_nonzero_tiledata_write_pc', 0):04X} "
                                f"LastNonZeroTiledataAddr=0x{vram_write_stats.get('last_nonzero_tiledata_write_addr', 0):04X} "
                                f"LastNonZeroTiledataVal=0x{vram_write_stats.get('last_nonzero_tiledata_write_val', 0):02X} "
                                f"LastNonZeroTiledataBank={vram_write_stats.get('last_nonzero_tiledata_write_bank', 0)} "
                                f"VBK_Current={vram_write_stats.get('vbk_value_current', 0)} "
                                f"VBK_WriteCount={vram_write_stats.get('vbk_write_count', 0)} "
                                f"VBK_LastWritePC=0x{vram_write_stats.get('last_vbk_write_pc', 0):04X} "
                                f"VBK_LastWriteVal=0x{vram_write_stats.get('last_vbk_write_val', 0):02X} "
                                f"TiledataBlocked={vram_write_stats.get('vram_write_blocked_mode3_tiledata', 0)} "
                                f"TilemapBlocked={vram_write_stats.get('vram_write_blocked_mode3_tilemap', 0)} "
                                f"LastBlockedPC=0x{vram_write_stats.get('last_blocked_vram_write_pc', 0):04X} "
                                f"LastBlockedAddr=0x{vram_write_stats.get('last_blocked_vram_write_addr', 0):04X} | "
                                f"ClearDoneFrame={vram_write_stats.get('tiledata_clear_done_frame', 0)} "
                                f"AttemptsAfterClear={vram_write_stats.get('tiledata_attempts_after_clear', 0)} "
                                f"NonZeroAfterClear={vram_write_stats.get('tiledata_nonzero_after_clear', 0)} "
                                f"FirstNonZeroFrame={vram_write_stats.get('tiledata_first_nonzero_frame', 0)} "
                                f"FirstNonZeroPC=0x{vram_write_stats.get('tiledata_first_nonzero_pc', 0):04X} "
                                f"FirstNonZeroAddr=0x{vram_write_stats.get('tiledata_first_nonzero_addr', 0):04X} "
                                f"FirstNonZeroVal=0x{vram_write_stats.get('tiledata_first_nonzero_val', 0):02X}")
                    except (AttributeError, TypeError, KeyError) as e:
                        vram_write_stats_str = f"ERROR: {e}"
                
                # Step 0488: PaletteStats
                palette_stats = {}
                try:
                    cartridge = self.mmu.get_cartridge() if hasattr(self.mmu, 'get_cartridge') else None
                    is_cgb = cartridge.is_cgb() if cartridge and hasattr(cartridge, 'is_cgb') else False
                    
                    palette_stats = {
                        'is_cgb': is_cgb,
                        'dmg_compat_mode': False,  # TODO: detectar si CGB está en modo DMG
                        'bgp': bgp,
                        'obp0': obp0,
                        'obp1': obp1,
                        'bgp_idx_to_shade': [
                            (bgp >> 0) & 0x03,  # idx 0
                            (bgp >> 2) & 0x03,  # idx 1
                            (bgp >> 4) & 0x03,  # idx 2
                            (bgp >> 6) & 0x03,  # idx 3
                        ],
                        'bgpi': self.mmu.read(0xFF68) if is_cgb else 0,  # BG Palette Index
                        'bgpd': self.mmu.read(0xFF69) if is_cgb else 0,  # BG Palette Data
                        'obpi': self.mmu.read(0xFF6A) if is_cgb else 0,  # OB Palette Index
                        'obpd': self.mmu.read(0xFF6B) if is_cgb else 0,  # OB Palette Data
                        'cgb_bg_palette_nonwhite_entries': 0,  # Se calculará si es CGB
                        'cgb_obj_palette_nonwhite_entries': 0,  # Se calculará si es CGB
                    }
                    
                    # Calcular entradas no-blancas en paletas CGB
                    if is_cgb:
                        try:
                            bg_pal_data = self.mmu.get_cgb_bg_palette_data() if hasattr(self.mmu, 'get_cgb_bg_palette_data') else []
                            obj_pal_data = self.mmu.get_cgb_obj_palette_data() if hasattr(self.mmu, 'get_cgb_obj_palette_data') else []
                            
                            # Contar entradas no-blancas (0x7FFF = blanco en BGR555)
                            palette_stats['cgb_bg_palette_nonwhite_entries'] = sum(
                                1 for val in bg_pal_data if val != 0x7FFF
                            ) if bg_pal_data else 0
                            palette_stats['cgb_obj_palette_nonwhite_entries'] = sum(
                                1 for val in obj_pal_data if val != 0x7FFF
                            ) if obj_pal_data else 0
                        except (AttributeError, TypeError):
                            pass
                except Exception as e:
                    palette_stats = {'error': str(e)}
                
                palette_stats_str = (f"CGB={1 if palette_stats.get('is_cgb') else 0} "
                                   f"BGP=0x{palette_stats.get('bgp', 0):02X} "
                                   f"OBP0=0x{palette_stats.get('obp0', 0):02X} "
                                   f"OBP1=0x{palette_stats.get('obp1', 0):02X} "
                                   f"BGP_Shades={palette_stats.get('bgp_idx_to_shade', [0,0,0,0])} "
                                   f"CGB_BG_NonWhite={palette_stats.get('cgb_bg_palette_nonwhite_entries', 0)} "
                                   f"CGB_OB_NonWhite={palette_stats.get('cgb_obj_palette_nonwhite_entries', 0)}")
                
                # --- Step 0495: CGBDetection section (Fase A) ---
                cgb_detection = {}
                try:
                    # Obtener ROM header CGB flag (byte 0x0143)
                    rom_header_cgb_flag = self.mmu.get_rom_header_cgb_flag() if hasattr(self.mmu, 'get_rom_header_cgb_flag') else None
                    
                    # Obtener machine_is_cgb (flag interno real del emulador)
                    machine_is_cgb = 0
                    if hasattr(self.mmu, 'get_hardware_mode'):
                        hardware_mode = self.mmu.get_hardware_mode()
                        machine_is_cgb = 1 if hardware_mode == "CGB" else 0
                    
                    # Obtener dmg_compat_mode (si está en modo compatibilidad DMG dentro de CGB)
                    dmg_compat_mode = None
                    if hasattr(self.mmu, 'get_dmg_compat_mode'):
                        dmg_compat_mode = self.mmu.get_dmg_compat_mode()
                    
                    cgb_detection = {
                        'rom_header_cgb_flag': rom_header_cgb_flag,  # Byte 0x0143
                        'machine_is_cgb': machine_is_cgb,  # Flag interno real
                        'boot_mode': None,  # Si existe (por ahora None)
                        'dmg_compat_mode': dmg_compat_mode,  # Si está en modo compatibilidad DMG
                    }
                except (AttributeError, TypeError, KeyError) as e:
                    cgb_detection = {'error': str(e)}
                
                # Construir string de CGBDetection para el snapshot
                cgb_detection_str = (f"CGBDetection_ROMHeaderFlag=0x{cgb_detection.get('rom_header_cgb_flag', 0):02X} "
                                    f"CGBDetection_MachineIsCGB={cgb_detection.get('machine_is_cgb', 0)} "
                                    f"CGBDetection_DMGCompatMode={1 if cgb_detection.get('dmg_compat_mode') else 0}")
                
                # --- Step 0495: IOWatchFF68FF6B section (Fase B) ---
                io_watch_ff68_ff6b = {}
                try:
                    if hasattr(self.mmu, 'get_io_watch_ff68_ff6b'):
                        io_watch_data = self.mmu.get_io_watch_ff68_ff6b()
                        if io_watch_data:
                            io_watch_ff68_ff6b = io_watch_data
                except (AttributeError, TypeError, KeyError) as e:
                    io_watch_ff68_ff6b = {'error': str(e)}
                
                # Construir string de IOWatchFF68FF6B para el snapshot
                io_watch_str = (f"IOWatch_BGPI_WriteCount={io_watch_ff68_ff6b.get('bgpi_write_count', 0)} "
                               f"IOWatch_BGPI_LastWritePC=0x{io_watch_ff68_ff6b.get('bgpi_last_write_pc', 0xFFFF):04X} "
                               f"IOWatch_BGPD_WriteCount={io_watch_ff68_ff6b.get('bgpd_write_count', 0)} "
                               f"IOWatch_BGPD_LastWritePC=0x{io_watch_ff68_ff6b.get('bgpd_last_write_pc', 0xFFFF):04X} "
                               f"IOWatch_OBPI_WriteCount={io_watch_ff68_ff6b.get('obpi_write_count', 0)} "
                               f"IOWatch_OBPI_LastWritePC=0x{io_watch_ff68_ff6b.get('obpi_last_write_pc', 0xFFFF):04X} "
                               f"IOWatch_OBPD_WriteCount={io_watch_ff68_ff6b.get('obpd_write_count', 0)} "
                               f"IOWatch_OBPD_LastWritePC=0x{io_watch_ff68_ff6b.get('obpd_last_write_pc', 0xFFFF):04X}")
                
                # --- Step 0495: CGBPaletteRAM section (Fase C) ---
                cgb_palette_ram = {}
                try:
                    if hasattr(self.mmu, 'read_bg_palette_data') and hasattr(self.mmu, 'read_obj_palette_data'):
                        # Leer 64 bytes de paleta BG (0x00-0x3F)
                        bg_palette_bytes = []
                        for i in range(64):
                            bg_palette_bytes.append(self.mmu.read_bg_palette_data(i))
                        bg_palette_bytes_hex = ''.join(f'{b:02X}' for b in bg_palette_bytes)
                        
                        # Leer 64 bytes de paleta OBJ (0x00-0x3F)
                        obj_palette_bytes = []
                        for i in range(64):
                            obj_palette_bytes.append(self.mmu.read_obj_palette_data(i))
                        obj_palette_bytes_hex = ''.join(f'{b:02X}' for b in obj_palette_bytes)
                        
                        # Contar entradas no blancas en paleta BG
                        # Cada color es 2 bytes (low + high), hay 8 paletas de 4 colores = 64 bytes total
                        # Un color es blanco si es 0x7FFF (0xFF 0x7F en little-endian)
                        bg_palette_nonwhite_entries = 0
                        for i in range(0, 64, 2):  # Cada color son 2 bytes
                            if i + 1 < 64:
                                color_low = bg_palette_bytes[i]
                                color_high = bg_palette_bytes[i + 1]
                                color_15bit = color_low | (color_high << 8)
                                if color_15bit != 0x7FFF:  # No es blanco
                                    bg_palette_nonwhite_entries += 1
                        
                        # Contar entradas no blancas en paleta OBJ
                        obj_palette_nonwhite_entries = 0
                        for i in range(0, 64, 2):  # Cada color son 2 bytes
                            if i + 1 < 64:
                                color_low = obj_palette_bytes[i]
                                color_high = obj_palette_bytes[i + 1]
                                color_15bit = color_low | (color_high << 8)
                                if color_15bit != 0x7FFF:  # No es blanco
                                    obj_palette_nonwhite_entries += 1
                        
                        cgb_palette_ram = {
                            'bg_palette_bytes_hex': bg_palette_bytes_hex,
                            'obj_palette_bytes_hex': obj_palette_bytes_hex,
                            'bg_palette_nonwhite_entries': bg_palette_nonwhite_entries,
                            'obj_palette_nonwhite_entries': obj_palette_nonwhite_entries,
                        }
                except (AttributeError, TypeError, KeyError, IndexError) as e:
                    cgb_palette_ram = {'error': str(e)}
                
                # Construir string de CGBPaletteRAM para el snapshot (compacto)
                cgb_palette_ram_str = (f"CGBPaletteRAM_BG_NonWhite={cgb_palette_ram.get('bg_palette_nonwhite_entries', 0)} "
                                      f"CGBPaletteRAM_OBJ_NonWhite={cgb_palette_ram.get('obj_palette_nonwhite_entries', 0)} "
                                      f"CGBPaletteRAM_BG_Hex={cgb_palette_ram.get('bg_palette_bytes_hex', '')[:32]}..."  # Primeros 16 bytes
                                      f"CGBPaletteRAM_OBJ_Hex={cgb_palette_ram.get('obj_palette_bytes_hex', '')[:32]}...")  # Primeros 16 bytes
                
                # --- Step 0495: PixelProof section (Fase D) ---
                pixel_proof = []
                try:
                    if hasattr(self.ppu, 'get_framebuffer_rgb') and hasattr(self.ppu, 'get_framebuffer_indices'):
                        fb_rgb = self.ppu.get_framebuffer_rgb()
                        fb_indices = self.ppu.get_framebuffer_indices()
                        
                        if fb_rgb is not None and fb_indices is not None and len(fb_rgb) >= 69120 and len(fb_indices) >= 23040:
                            # Buscar 5 píxeles no blancos
                            nonwhite_pixels_found = 0
                            for y in range(144):
                                if nonwhite_pixels_found >= 5:
                                    break
                                for x in range(160):
                                    if nonwhite_pixels_found >= 5:
                                        break
                                    
                                    idx = y * 160 + x
                                    if idx >= len(fb_indices):
                                        continue
                                    
                                    rgb_idx = idx * 3
                                    if rgb_idx + 2 >= len(fb_rgb):
                                        continue
                                    
                                    r = fb_rgb[rgb_idx]
                                    g = fb_rgb[rgb_idx + 1]
                                    b = fb_rgb[rgb_idx + 2]
                                    
                                    # Verificar si no es blanco (255, 255, 255)
                                    if r != 255 or g != 255 or b != 255:
                                        color_idx = fb_indices[idx] & 0x03  # Índice de color (0-3)
                                        
                                        # Obtener raw_15bit_color de la paleta CGB
                                        # Asumir paleta BG por ahora (palette_used = "BG")
                                        # Cada paleta tiene 4 colores, cada color es 2 bytes
                                        # Paleta 0 = índices 0-7 (4 colores * 2 bytes)
                                        palette_idx = color_idx * 2  # Índice en la paleta (0, 2, 4, 6)
                                        raw_15bit_color = 0x7FFF  # Default: blanco
                                        
                                        try:
                                            if hasattr(self.mmu, 'read_bg_palette_data'):
                                                color_low = self.mmu.read_bg_palette_data(palette_idx)
                                                color_high = self.mmu.read_bg_palette_data(palette_idx + 1)
                                                raw_15bit_color = color_low | (color_high << 8)
                                        except:
                                            pass
                                        
                                        pixel_proof.append({
                                            'x': x,
                                            'y': y,
                                            'idx': color_idx,
                                            'palette_used': 'BG',  # Asumir BG por ahora
                                            'raw_15bit_color': raw_15bit_color,
                                            'rgb888_result': (r, g, b),
                                        })
                                        nonwhite_pixels_found += 1
                except (AttributeError, TypeError, KeyError, IndexError) as e:
                    pixel_proof = [{'error': str(e)}]
                
                # Construir string de PixelProof para el snapshot (compacto, solo primeros 2 píxeles)
                pixel_proof_str = ""
                if pixel_proof and len(pixel_proof) > 0:
                    proof_samples = pixel_proof[:2]  # Solo primeros 2 para no saturar
                    proof_parts = []
                    for i, px in enumerate(proof_samples):
                        if 'error' not in px:
                            r, g, b = px.get('rgb888_result', (255, 255, 255))
                            proof_parts.append(
                                f"P{i}_({px.get('x', 0)},{px.get('y', 0)})_idx{px.get('idx', 0)}_"
                                f"pal{px.get('palette_used', '?')}_15b0x{px.get('raw_15bit_color', 0x7FFF):04X}_"
                                f"rgb({r},{g},{b})"
                            )
                    pixel_proof_str = "PixelProof_" + "_".join(proof_parts)
                else:
                    pixel_proof_str = "PixelProof_None"
                
                # --- Step 0494: IRQReality section (siempre, no solo en AfterClear) ---
                irq_reality_snapshot = {}
                try:
                    # Obtener interrupt_taken_counts
                    interrupt_taken = self.cpu.get_interrupt_taken_counts()
                    if interrupt_taken:
                        irq_reality_snapshot['interrupt_taken_vblank'] = interrupt_taken.get('vblank', 0)
                        irq_reality_snapshot['interrupt_taken_lcd_stat'] = interrupt_taken.get('lcd_stat', 0)
                        irq_reality_snapshot['interrupt_taken_timer'] = interrupt_taken.get('timer', 0)
                        irq_reality_snapshot['interrupt_taken_serial'] = interrupt_taken.get('serial', 0)
                        irq_reality_snapshot['interrupt_taken_joypad'] = interrupt_taken.get('joypad', 0)
                    
                    # Obtener IF/IE tracking
                    if_ie_tracking = self.mmu.get_if_ie_tracking()
                    if if_ie_tracking:
                        irq_reality_snapshot['if_write_count'] = if_ie_tracking.get('if_write_count', 0)
                        irq_reality_snapshot['ie_write_count'] = if_ie_tracking.get('ie_write_count', 0)
                        irq_reality_snapshot['last_if_write_pc'] = if_ie_tracking.get('last_if_write_pc', 0)
                        irq_reality_snapshot['last_ie_write_pc'] = if_ie_tracking.get('last_ie_write_pc', 0)
                    
                    # Obtener HRAM[0xFFC5] tracking
                    hram_ffc5_tracking = self.mmu.get_hram_ffc5_tracking()
                    if hram_ffc5_tracking:
                        irq_reality_snapshot['hram_ffc5_write_count'] = hram_ffc5_tracking.get('write_count', 0)
                        irq_reality_snapshot['hram_ffc5_first_write_frame'] = hram_ffc5_tracking.get('first_write_frame', 0)
                        irq_reality_snapshot['hram_ffc5_last_write_pc'] = hram_ffc5_tracking.get('last_write_pc', 0)
                except (AttributeError, TypeError, KeyError) as e:
                    irq_reality_snapshot = {'error': str(e)}
                
                # Construir string de IRQReality para el snapshot
                irq_reality_str = (f"IRQTaken_VBlank={irq_reality_snapshot.get('interrupt_taken_vblank', 0)} "
                                 f"IRQTaken_LCD={irq_reality_snapshot.get('interrupt_taken_lcd_stat', 0)} "
                                 f"IRQTaken_Timer={irq_reality_snapshot.get('interrupt_taken_timer', 0)} "
                                 f"IF_WriteCount={irq_reality_snapshot.get('if_write_count', 0)} "
                                 f"IE_WriteCount={irq_reality_snapshot.get('ie_write_count', 0)} "
                                 f"HRAM_FFC5_WriteCount={irq_reality_snapshot.get('hram_ffc5_write_count', 0)} "
                                 f"HRAM_FFC5_FirstFrame={irq_reality_snapshot.get('hram_ffc5_first_write_frame', 0)}")
                
                print(f"[SMOKE-SNAPSHOT] Frame={frame_idx} | "
                      f"PC=0x{pc:04X} IME={ime} HALTED={halted} | "
                      f"IE=0x{ie:02X} IF=0x{if_reg:02X} | "
                      f"IE_value=0x{ie:02X} IE_last_write_pc=0x{last_ie_write_pc:04X} IE_last_write_val=0x{last_ie_write_value:02X} | "
                      f"IME_value={1 if ime else 0} IF_value=0x{if_reg:02X} irq_serviced_count={irq_serviced_count} | "
                      f"BGP=0x{bgp:02X} OBP0=0x{obp0:02X} OBP1=0x{obp1:02X} | "
                      f"KEY1=0x{key1:02X} JOYP=0x{joyp:02X} | "
                      f"STOP_count={stop_executed_count} STOP_PC=0x{last_stop_pc:04X} | "
                      f"KEY1_write_count={key1_write_count} KEY1_write_val=0x{last_key1_write_value:02X} KEY1_write_PC=0x{last_key1_write_pc:04X} | "
                      f"JOYP_write_count={joyp_write_count} JOYP_write_val=0x{last_joyp_write_value:02X} JOYP_write_PC=0x{last_joyp_write_pc:04X} | "
                      f"VBlankReq={vblank_req} VBlankServ={vblank_serv} | "
                      f"IEWrite={ie_write_count} IFWrite={if_write_count} EI={ei_count} DI={di_count} | "
                      f"IEWriteVal=0x{last_ie_write_value:02X} IEReadVal=0x{last_ie_read_value:02X} IEReadCount={ie_read_count} IEWritePC=0x{last_ie_write_pc:04X} IEWriteTS={last_ie_write_timestamp} | "
                      f"IME_SetEvents={ime_set_events_count} IME_SetPC=0x{last_ime_set_pc:04X} IME_SetTS={last_ime_set_timestamp} | "
                      f"EI_PC=0x{last_ei_pc:04X} DI_PC=0x{last_di_pc:04X} EI_Pending={1 if ei_pending else 0} | "
                      f"IF_WriteTS={last_if_write_timestamp} | "
                      f"fb_nonzero={fb_nonzero} | "
                      f"IOReadsTop3={io_reads_str} | "
                      f"PCHotspotsTop3={pc_hotspots_str} | "
                      f"PCHotspot1={'0x' + format(pc_hotspot_1, '04X') if pc_hotspot_1 is not None else 'None'} | "
                      f"Disasm={disasm_snippet[:200]} | "  # Limitar a 200 chars
                      f"IOTouched={io_touched_str} | "
                      f"LoopWaitsOn={loop_waits_on_str} LoopMask={loop_mask_str} LoopCmp={loop_cmp_str} LoopPattern={loop_pattern_str} | "
                      f"TilemapNZ_9800_RAW={tilemap_nz_9800_raw} TilemapNZ_9C00_RAW={tilemap_nz_9C00_raw} | "
                      f"LCDC=0x{lcdc:02X} STAT=0x{stat:02X} LY={ly} | "
                      f"IF_ReadCount={if_read_count} IF_WriteCount={if_write_count} IF_ReadVal=0x{last_if_read_val:02X} IF_WriteVal=0x{last_if_write_val:02X} IF_WritePC=0x{last_if_write_pc:04X} IF_Writes0={if_writes_0} IF_WritesNonZero={if_writes_nonzero} | "
                      f"LY_ReadMin={ly_read_min} LY_ReadMax={ly_read_max} LY_LastRead={last_ly_read} | "
                      f"STAT_LastRead=0x{last_stat_read:02X} | "
                      f"IF_ReadsProg={if_reads_program} IF_ReadsPoll={if_reads_cpu_poll} IF_WritesProg={if_writes_program} | "
                      f"IE_ReadsProg={ie_reads_program} IE_ReadsPoll={ie_reads_cpu_poll} IE_WritesProg={ie_writes_program} | "
                      f"LastIRQVec=0x{last_irq_serviced_vector:04X} LastIRQTS={last_irq_serviced_timestamp} | "
                      f"IF_BeforeSvc=0x{last_if_before_service:02X} IF_AfterSvc=0x{last_if_after_service:02X} IF_ClearMask=0x{last_if_clear_mask:02X} | "
                      f"BootLogoPrefill={boot_logo_prefill_enabled} | "
                      f"BranchInfo={branch_info_str} | "
                      f"LastCmp={last_cmp_str} LastBit={last_bit_str} | "
                      f"LCDC_DisableEvents={lcdc_disable_events} LCDC_WritePC=0x{last_lcdc_write_pc:04X} LCDC_WriteVal=0x{last_lcdc_write_value:02X} | "
                      f"DynamicWaitLoop={dynamic_wait_loop_str} | "
                      f"UnknownOpcodes={unknown_opcodes_str} | "
                      f"HRAM_FF92_WriteCount={hram_ff92_write_count} HRAM_FF92_ReadCountProg={hram_ff92_read_count_program} | "
                      f"HRAM_FF92_FirstWriteFrame={first_hram_ff92_write_frame} HRAM_FF92_LastWriteFrame={last_hram_ff92_write_frame} | "
                      f"HRAM_FF92_LastWritePC=0x{last_hram_ff92_write_pc:04X} HRAM_FF92_LastWriteVal=0x{last_hram_ff92_write_value:02X} | "
                      f"HRAM_FF92_LastReadPC=0x{last_hram_ff92_read_pc:04X} HRAM_FF92_LastReadVal=0x{last_hram_ff92_read_value:02X} | "
                      f"JOYP_ReadVal=0x{last_joyp_read_value:02X} | "
                      f"LCDC_Current=0x{lcdc_current:02X} | "
                      f"LY_DistributionTop5={ly_dist_str} | "
                      f"LastLoadA_FromLY={1 if last_load_a_from_ly else 0} LastLoadA_LYValue=0x{last_load_a_ly_value:02X} | "
                      f"Branch0x1290_Taken={branch_0x1290_taken_count} Branch0x1290_NotTaken={branch_0x1290_not_taken_count} | "
                      f"Branch0x1290_LastFlags=0x{branch_0x1290_last_flags:02X} Branch0x1290_LastTaken={1 if branch_0x1290_last_taken else 0} | "
                      f"JOYP_WriteDistTop5={joyp_write_dist_str} | "
                      f"JOYP_ReadSelectBits=0x{joyp_last_read_select_bits:02X} JOYP_ReadLowNibble=0x{joyp_last_read_low_nibble:02X} | "
                      f"MarioLoop_LYReadsTotal={mario_loop_ly_reads_total} MarioLoop_LYEq0x91={mario_loop_ly_eq_0x91_count} | "
                      f"MarioLoop_LYLastVal=0x{mario_loop_ly_last_value:02X} MarioLoop_LYLastPC=0x{mario_loop_ly_last_pc:04X} | "
                      f"Branch0x1290_Eval={branch_0x1290_eval_count} Branch0x1290_Taken0485={branch_0x1290_taken_count_0485} Branch0x1290_NotTaken0485={branch_0x1290_not_taken_count_0485} | "
                      f"Branch0x1290_NotTakenLY=0x{branch_0x1290_last_not_taken_ly_value:02X} Branch0x1290_NotTakenFlags=0x{branch_0x1290_last_not_taken_flags:02X} Branch0x1290_NotTakenNextPC=0x{branch_0x1290_last_not_taken_next_pc:04X} | "
                      f"ExecCount_0x1288={exec_count_0x1288} ExecCount_0x1298={exec_count_0x1298} | "
                      f"JOYPTrace_ButtonsSel={joyp_reads_with_buttons_selected_count} JOYPTrace_DpadSel={joyp_reads_with_dpad_selected_count} JOYPTrace_NoneSel={joyp_reads_with_none_selected_count} | "
                      f"FrameBufferStats={fb_stats_str} | "
                      f"PaletteStats={palette_stats_str} | "
                      f"ThreeBufferStats={three_buf_stats_str} | "
                      f"CGBPaletteWriteStats={cgb_pal_stats_str} | "
                      f"DMGTileFetchStats={dmg_tile_stats_str} | "
                      f"VRAM_Regions_TiledataNZ={vram_tiledata_nonzero} VRAM_Regions_TilemapNZ={vram_tilemap_nonzero} | "
                      f"VRAMWriteStats={vram_write_stats_str} | "
                      f"{cgb_detection_str} | "  # Step 0495: CGBDetection
                      f"{io_watch_str} | "  # Step 0495: IOWatchFF68FF6B
                      f"{cgb_palette_ram_str} | "  # Step 0495: CGBPaletteRAM
                      f"{pixel_proof_str} | "  # Step 0495: PixelProof
                      f"{irq_reality_str} | "  # Step 0494: IRQReality
                      f"PresentDetails=fmt={present_details.get('present_fmt', 0)} pitch={present_details.get('present_pitch', 0)} w={present_details.get('present_w', 0)} h={present_details.get('present_h', 0)} bytes_len={present_details.get('present_bytes_len', 0)}")  # Step 0496: PresentDetails
                
                # --- Step 0499: DMG Quick Classifier (solo para DMG) ---
                dmg_classification_str = ""
                try:
                    # Detectar si es DMG
                    is_cgb = False
                    if hasattr(self.mmu, 'get_hardware_mode'):
                        hardware_mode = self.mmu.get_hardware_mode()
                        is_cgb = (hardware_mode == "CGB")
                    
                    if not is_cgb:
                        # Solo para DMG: ejecutar clasificador rápido
                        dmg_classification, dmg_details = self._classify_dmg_quick(self.ppu, self.mmu, self._renderer)
                        dmg_classification_str = f"DMGQuickClassifier={dmg_classification} "
                        for key, value in dmg_details.items():
                            dmg_classification_str += f"DMG_{key}={value} "
                except Exception as e:
                    dmg_classification_str = f"DMGQuickClassifier=ERROR({str(e)[:50]}) "
                
                if dmg_classification_str:
                    print(f"[SMOKE-SNAPSHOT-DMG] {dmg_classification_str}")
                # -----------------------------------------
                
                # --- Step 0493: AfterClear section reforzada ---
                if vram_write_stats and vram_write_stats.get('tiledata_clear_done_frame', 0) > 0:
                    clear_frame = vram_write_stats['tiledata_clear_done_frame']
                    current_frame = frame_idx
                    
                    # Solo capturar si estamos después del clear
                    if current_frame >= clear_frame:
                        frames_since_clear = current_frame - clear_frame
                        
                        # PC hotspots top 3 (ya calculados arriba)
                        pc_hotspots_after_clear = pc_hotspots_str
                        pc_hotspots_list = pc_hotspots_top3  # Lista de tuplas (pc, count)
                        
                        # IO reads top 3 (ya calculados arriba)
                        io_reads_after_clear = io_reads_str
                        io_reads_list = io_reads_top3  # Lista de tuplas (addr, count)
                        
                        # Estado CPU/MMU
                        ime_val = 1 if ime else 0
                        halted_val = 1 if halted else 0
                        
                        # Registros I/O
                        lcdc_val = lcdc
                        stat_val = stat
                        ly_val = ly
                        
                        # VBlank stats
                        vblank_req_val = vblank_req
                        vblank_serv_val = vblank_serv
                        
                        # Disasm del hotspot top1
                        disasm_hotspot = ""
                        disasm_branch_dest = ""
                        if pc_hotspots_list:
                            pc_hotspot_1 = pc_hotspots_list[0][0]
                            try:
                                disasm_window_list = disasm_window(self.mmu, pc_hotspot_1, before=10, after=20)
                                
                                # Construir disasm snippet
                                disasm_lines = []
                                for inst_pc, mnemonic, is_current in disasm_window_list[:20]:
                                    marker = " <-- HOTSPOT" if is_current else ""
                                    disasm_lines.append(f"0x{inst_pc:04X}: {mnemonic}{marker}")
                                
                                disasm_hotspot = "\n".join(disasm_lines)
                                
                                # Detectar branch/loop y disasm del destino
                                for inst_pc, mnemonic, is_current in disasm_window_list:
                                    if 'JR' in mnemonic or 'JP' in mnemonic:
                                        # Intentar extraer dirección destino
                                        if '0x' in mnemonic:
                                            try:
                                                # Extraer dirección del mnemonic (ej: "JP 0x1234" o "JR 0x1234")
                                                parts = mnemonic.split()
                                                for part in parts:
                                                    if part.startswith('0x'):
                                                        dest_addr = int(part[2:], 16)
                                                        dest_disasm = disasm_window(self.mmu, dest_addr, before=5, after=10)
                                                        dest_lines = []
                                                        for d_pc, d_mnem, _ in dest_disasm[:10]:
                                                            dest_lines.append(f"0x{d_pc:04X}: {d_mnem}")
                                                        disasm_branch_dest = "\n".join(dest_lines)
                                                        break
                                            except:
                                                pass
                                        break
                            except Exception as e:
                                disasm_hotspot = f"ERROR: {e}"
                        
                        # --- Step 0494: IRQReality section ---
                        irq_reality = {}
                        try:
                            # Obtener interrupt_taken_counts
                            interrupt_taken = self.cpu.get_interrupt_taken_counts()
                            if interrupt_taken:
                                irq_reality['interrupt_taken_vblank'] = interrupt_taken.get('vblank', 0)
                                irq_reality['interrupt_taken_lcd_stat'] = interrupt_taken.get('lcd_stat', 0)
                                irq_reality['interrupt_taken_timer'] = interrupt_taken.get('timer', 0)
                                irq_reality['interrupt_taken_serial'] = interrupt_taken.get('serial', 0)
                                irq_reality['interrupt_taken_joypad'] = interrupt_taken.get('joypad', 0)
                            
                            # Obtener IRQ trace ring (últimos 10 eventos)
                            irq_trace = self.cpu.get_irq_trace_ring(10)
                            if irq_trace:
                                irq_reality['irq_trace_tail'] = irq_trace
                            
                            # Obtener IF/IE tracking
                            if_ie_tracking = self.mmu.get_if_ie_tracking()
                            if if_ie_tracking:
                                irq_reality['if_ie_tracking'] = if_ie_tracking
                            
                            # Obtener HRAM[0xFFC5] tracking
                            hram_ffc5_tracking = self.mmu.get_hram_ffc5_tracking()
                            if hram_ffc5_tracking:
                                irq_reality['hram_ffc5_tracking'] = hram_ffc5_tracking
                        except (AttributeError, TypeError, KeyError) as e:
                            irq_reality = {'error': str(e)}
                        # -----------------------------------------
                        
                        # Step 0501: Obtener clasificación DMG v3 (VRAM Audit + PPU Mode Stats)
                        dmg_classification_v3 = "UNKNOWN"
                        dmg_details_v3 = {}
                        try:
                            if not is_cgb:
                                dmg_classification_v3, dmg_details_v3 = self._classify_dmg_quick_v3(self.ppu, self.mmu, self._renderer)
                        except Exception as e:
                            dmg_classification_v3 = f"ERROR({str(e)[:50]})"
                        
                        # Step 0500/0501: Obtener métricas adicionales (compatibilidad con v2)
                        interrupt_taken_v2 = {}
                        reti_count_v2 = 0
                        hram_ffc5_tracking_v2 = None
                        if_ie_tracking_v2 = None
                        try:
                            if hasattr(self.cpu, 'get_interrupt_taken_counts'):
                                interrupt_taken_v2 = self.cpu.get_interrupt_taken_counts() or {}
                            if hasattr(self.cpu, 'get_reti_count'):
                                reti_count_v2 = self.cpu.get_reti_count()
                            if hasattr(self.mmu, 'get_hram_ffc5_tracking'):
                                hram_ffc5_tracking_v2 = self.mmu.get_hram_ffc5_tracking()
                            if hasattr(self.mmu, 'get_if_ie_tracking'):
                                if_ie_tracking_v2 = self.mmu.get_if_ie_tracking()
                        except:
                            pass
                        
                        # Clasificación del bloqueo
                        after_clear_snapshot = {
                            'frames_since_clear': frames_since_clear,
                            'pc_hotspots_top3': pc_hotspots_list,
                            'io_reads_top3': io_reads_list,
                            'ime': ime_val,
                            'ie': ie,
                            'if_reg': if_reg,
                            'halted': halted_val,
                            'vblank_req': vblank_req_val,
                            'vblank_serv': vblank_serv_val,
                            'lcdc': lcdc_val,
                            'stat': stat_val,
                            'ly': ly_val,
                            'disasm_hotspot_top1': disasm_hotspot,
                            'disasm_branch_dest': disasm_branch_dest,
                            'IRQReality': irq_reality,  # Step 0494
                            # Step 0501: DMGQuickClassifierV3 con VRAM Audit + PPU Mode Stats
                            'DMGQuickClassifierV3': {
                                'classification': dmg_classification_v3,
                                'details': dmg_details_v3,
                                'pc_hotspot_top1': pc_hotspots_list[0] if pc_hotspots_list else None,
                                'irq_taken_vblank': interrupt_taken_v2.get('vblank', 0),
                                'reti_count': reti_count_v2,
                                'hram_ffc5_last_value': hram_ffc5_tracking_v2.get('last_write_value') if hram_ffc5_tracking_v2 else None,
                                'hram_ffc5_write_count_total': hram_ffc5_tracking_v2.get('write_count_total', 0) if hram_ffc5_tracking_v2 else 0,
                                'hram_ffc5_write_count_in_vblank': hram_ffc5_tracking_v2.get('write_count_in_irq_vblank', 0) if hram_ffc5_tracking_v2 else 0,
                                'lcdc': lcdc_val,
                                'stat': stat_val,
                                'ly': ly_val,
                                'vram_tiledata_nz': vram_write_stats.get('tiledata_nonzero_bank0', 0) if vram_write_stats else 0,
                                'vram_tilemap_nz': vram_write_stats.get('tilemap_nonzero_bank0', 0) if vram_write_stats else 0,
                                'vram_attempts_after_clear': vram_write_stats.get('tiledata_attempts_after_clear', 0) if vram_write_stats else 0,
                                'vram_nonzero_after_clear': vram_write_stats.get('tiledata_nonzero_after_clear', 0) if vram_write_stats else 0,
                            } if not is_cgb else None,
                        }
                        
                        classification = self._classify_dmg_blockage(after_clear_snapshot)
                        
                        # Imprimir sección AfterClear reforzada
                        print(f"[SMOKE-AFTERCLEAR] Frame={frame_idx} | FramesSinceClear={frames_since_clear} | "
                              f"PCHotspotsTop3={pc_hotspots_after_clear} | "
                              f"IOReadsTop3={io_reads_after_clear} | "
                              f"IME={ime_val} IE=0x{ie:02X} IF=0x{if_reg:02X} HALTED={halted_val} | "
                              f"VBlankReq={vblank_req_val} VBlankServ={vblank_serv_val} | "
                              f"LCDC=0x{lcdc_val:02X} STAT=0x{stat_val:02X} LY=0x{ly_val:02X}")
                        
                        if disasm_hotspot:
                            print(f"[SMOKE-AFTERCLEAR-DISASM] Hotspot Top1 (0x{pc_hotspots_list[0][0]:04X}):\n{disasm_hotspot}")
                        
                        if disasm_branch_dest:
                            print(f"[SMOKE-AFTERCLEAR-DISASM] Branch Destination:\n{disasm_branch_dest}")
                        
                        if classification:
                            print(f"[SMOKE-AFTERCLEAR-CLASSIFICATION] {classification}")
                # -----------------------------------------
                
                # Step 0485: Imprimir tail de JOYP trace si está activo (últimos 16 eventos compactados)
                if debug_joyp_trace and joyp_trace_tail:
                    trace_str = " | ".join([
                        f"{evt['type']}@0x{evt['pc']:04X}:w=0x{evt['value_written']:02X},r=0x{evt['value_read']:02X},sel=0x{evt['select_bits']:02X},low=0x{evt['low_nibble_read']:02X}"
                        for evt in joyp_trace_tail[-8:]  # Últimos 8 eventos
                    ])
                    print(f"[SMOKE-JOYPTRACE] Frame={frame_idx} | Tail: {trace_str}")
                
                # Step 0477: Clasificador automático (Caso A/B/C/D)
                classification = self._classify_ime_ie_state(
                    ei_count, ime_set_events_count, ime, ie, vblank_serv
                )
                if classification:
                    print(f"[SMOKE-CLASSIFICATION] {classification}")
            
            # Dump periódico
            if self.dump_every > 0 and (frame_idx + 1) % self.dump_every == 0:
                print(f"[Frame {frame_idx:04d}] PC={metrics['pc']:04X} "
                      f"nonwhite={metrics['nonwhite_pixels']:5d} "
                      f"vram_nz={metrics['vram_nonzero']:4d} "
                      f"oam_nz={metrics['oam_nonzero']:4d} "
                      f"LCDC={metrics['lcdc']:02X} LY={metrics['ly']:02X}")
            
            # Step 0464: Imprimir diagnóstico de tilemap (primeros 5 frames + cada 120)
            should_log_tilemap_diag = (frame_idx < 5) or (frame_idx % 120 == 0)
            if should_log_tilemap_diag:
                tile_ids_str = ''.join(f'{t:02X}' for t in metrics.get('tile_ids_sample', []))
                print(f"LCDC=0x{metrics['lcdc']:02X} | BGMapBase=0x{metrics['bg_tilemap_base']:04X} | TileDataMode={metrics['bg_tile_data_mode']} | "
                      f"BG={(metrics['lcdc'] & 0x01) != 0} Win={(metrics['lcdc'] & 0x20) != 0} | "
                      f"SCX={metrics['scx']} SCY={metrics['scy']} WX={self.mmu.read(0xFF4B)} WY={self.mmu.read(0xFF4A)} LY={metrics['ly']} | "
                      f"TilemapNZ_9800={metrics.get('tilemap_nz_9800', 0)} TilemapNZ_9C00={metrics.get('tilemap_nz_9C00', 0)} | "
                      f"TileIDs[0:16]={tile_ids_str}")
            
            # Step 0463: Imprimir modo tile data en frames loggeados (mantener para compatibilidad)
            if self.dump_every > 0 and (frame_idx % self.dump_every == 0 or frame_idx <= 3 or frame_idx >= self.max_frames - 1):
                print(f"LCDC=0x{metrics['lcdc']:02X} | TileDataMode={metrics['bg_tile_data_mode']} | "
                      f"BGTilemap=0x{metrics['bg_tilemap_base']:04X} | WinTilemap=0x{metrics['win_tilemap_base']:04X} | "
                      f"SCX={metrics['scx']} SCY={metrics['scy']} LY={metrics['ly']}")
                
                # Dump PNG si está habilitado
                if self.dump_png:
                    framebuffer = self.ppu.get_framebuffer_rgb()
                    self._dump_png(frame_idx, framebuffer)
            
            # Step 0454: Imprimir métricas robustas en frames loggeados
            if self.dump_every > 0 and (frame_idx % self.dump_every == 0 or frame_idx <= 3 or frame_idx >= self.max_frames - 1):
                print(f"[ROBUST-METRICS] Frame {frame_idx} | "
                      f"unique_rgb={metrics['unique_rgb_count']} | "
                      f"dominant_ratio={metrics['dominant_ratio']:.3f} | "
                      f"hash={metrics['frame_hash_robust']} | "
                      f"hash_changed={metrics['hash_changed']}")
        
        # Resumen final
        self._print_summary()
    
    def _classify_ime_ie_state(self, ei_count: int, ime_set_events_count: int, 
                                ime: bool, ie: int, vblank_serv: int) -> Optional[str]:
        """
        Step 0477: Clasificador automático para identificar causa raíz de IME/IE en 0.
        
        Clasifica el estado en uno de los casos:
        - Caso A: EI nunca se ejecuta (el juego está atascado antes)
        - Caso B: EI ejecutado pero IME no sube (bug EI delayed enable)
        - Caso C: IME sube pero IE=0 (juego no habilita IE o no lo necesita)
        - Caso D: IME+IE OK pero no hay service (revisar generación de requests)
        
        Args:
            ei_count: Número de veces que se ejecutó EI
            ime_set_events_count: Número de veces que IME se activó
            ime: Estado actual de IME
            ie: Valor actual de IE
            vblank_serv: Número de VBlank IRQs servidos
        
        Returns:
            String con la clasificación o None si no aplica
        """
        # Caso A: EI nunca se ejecuta
        if ei_count == 0 and ime == 0:
            return "CASO_A: EI nunca ejecutado, IME=0 sostenido. El juego está atascado antes de habilitar interrupciones. Buscar condición del loop con disasm real."
        
        # Caso B: EI ejecutado pero IME no sube
        if ei_count > 0 and ime_set_events_count == 0:
            return "CASO_B: EI ejecutado pero IME no sube (ime_set_events_count=0). Bug EI delayed enable casi seguro. Revisar implementación de EI delayed enable en CPU::step()."
        
        # Caso C: IME sube pero IE=0
        if ime == 1 and ie == 0:
            return "CASO_C: IME=1 pero IE=0x00. Juego no habilita IE o no lo necesita. Mirar el loop con disasm para ver si espera otra condición (no IRQ)."
        
        # Caso D: IME+IE OK pero no hay service
        if ime == 1 and ie != 0 and vblank_serv == 0:
            return "CASO_D: IME=1 e IE!=0 pero vblank_serv=0. Revisar generación de requests (PPU/Timer) o masks. Verificar si PPU/Timer están generando IF correctamente."
        
        # Si no encaja en ningún caso, retornar None
        return None
    
    def _classify_dmg_quick(self, ppu, mmu, renderer=None):
        """
        Step 0499: Clasifica rápidamente el estado DMG para diagnóstico.
        Step 0500: Ampliado con señales de progreso (v2).
        Step 0501: Usa v3 con VRAM Write Audit y PPU Mode Stats (v3).
        Step 0502: Usa v4 con contadores cero/no-cero y source-read correlation (v4).
        
        Args:
            ppu: Instancia de PPU
            mmu: Instancia de MMU
            renderer: Instancia de Renderer (opcional)
        
        Returns:
            Tupla (classification, details) donde:
            - classification: String con la clasificación
            - details: Dict con detalles específicos
        """
        return self._classify_dmg_quick_v4(ppu, mmu, renderer)
    
    def _classify_dmg_quick_v2(self, ppu, mmu, renderer=None):
        """
        Step 0500: Clasificación DMG v2 con señales de progreso.
        
        Args:
            ppu: Instancia de PPU
            mmu: Instancia de MMU
            renderer: Instancia de Renderer (opcional)
        
        Returns:
            Tupla (classification, details) donde:
            - classification: String con la clasificación
            - details: Dict con detalles específicos
        """
        # Obtener métricas existentes
        three_buf_stats = {}
        try:
            if hasattr(ppu, 'get_three_buffer_stats'):
                three_buf_stats = ppu.get_three_buffer_stats() or {}
        except:
            pass
        
        lcdc = mmu.read(0xFF40)
        lcd_on = (lcdc & 0x80) != 0
        
        # VRAM stats
        vram_write_stats = {}
        try:
            if hasattr(mmu, 'get_vram_write_stats'):
                vram_write_stats = mmu.get_vram_write_stats() or {}
        except:
            pass
        
        # PC hotspots (del snapshot AfterClear si existe)
        pc_hotspot_1 = None
        hotspot_count = 0
        try:
            # Intentar obtener de algún snapshot o tracking
            if hasattr(mmu, 'get_pc_hotspots'):
                hotspots = mmu.get_pc_hotspots()
                if hotspots and len(hotspots) > 0:
                    pc_hotspot_1, hotspot_count = hotspots[0]
        except:
            pass
        
        # Step 0500: IRQ stats
        interrupt_taken = {}
        reti_count = 0
        try:
            if hasattr(self.cpu, 'get_interrupt_taken_counts'):
                interrupt_taken = self.cpu.get_interrupt_taken_counts() or {}
            if hasattr(self.cpu, 'get_reti_count'):
                reti_count = self.cpu.get_reti_count()
        except:
            pass
        
        # Step 0500: HRAM[0xFFC5] stats
        hram_ffc5_tracking = None
        try:
            if hasattr(mmu, 'get_hram_ffc5_tracking'):
                hram_ffc5_tracking = mmu.get_hram_ffc5_tracking()
        except:
            pass
        
        # Step 0500: IF/IE stats
        if_ie_tracking = None
        try:
            if hasattr(mmu, 'get_if_ie_tracking'):
                if_ie_tracking = mmu.get_if_ie_tracking()
        except:
            pass
        
        # Step 0500: IO reads top 3 (para detectar lecturas dominantes a FFC5)
        io_reads_top = []
        try:
            # Obtener IO reads desde snapshot AfterClear si está disponible
            # Por ahora, intentamos obtenerlo de alguna forma
            # (esto se completará cuando se añada al snapshot)
            pass
        except:
            pass
        
        # Clasificar
        classification = "UNKNOWN"
        details = {}
        
        # Step 0500: WAITING_ON_FFC5: hotspot + lecturas dominantes a FFC5 y write_count_in_vblank == 0
        if pc_hotspot_1 is not None:
            # Verificar si hay lecturas dominantes a FFC5
            ffc5_reads = 0
            # TODO: Obtener desde snapshot AfterClear cuando esté disponible
            # Por ahora, verificamos si hay tracking de FFC5
            if hram_ffc5_tracking:
                write_count_in_vblank = hram_ffc5_tracking.get('write_count_in_irq_vblank', 0)
                if write_count_in_vblank == 0:
                    # Verificar si hay muchas lecturas (esto se completará con snapshot)
                    # Por ahora, clasificamos si hay hotspot y no hay writes en VBlank
                    if hotspot_count > 1000:
                        classification = "WAITING_ON_FFC5"
                        details['hotspot_pc'] = f'0x{pc_hotspot_1:04X}'
                        details['ffc5_write_count_in_vblank'] = 0
                        return classification, details
        
        # Step 0500: IRQ_TAKEN_BUT_NO_RETI: taken aumenta y reti_count no
        if interrupt_taken:
            vblank_taken = interrupt_taken.get('vblank', 0)
            if vblank_taken > 0 and reti_count == 0:
                classification = "IRQ_TAKEN_BUT_NO_RETI"
                details['irq_taken_vblank'] = vblank_taken
                details['reti_count'] = reti_count
                return classification, details
        
        # Step 0500: IRQ_OK_BUT_FLAG_NOT_SET: taken y reti ok pero FFC5 no cambia
        if interrupt_taken and interrupt_taken.get('vblank', 0) > 0 and reti_count > 0:
            vblank_taken = interrupt_taken.get('vblank', 0)
            if hram_ffc5_tracking and hram_ffc5_tracking.get('write_count_total', 0) == 0:
                classification = "IRQ_OK_BUT_FLAG_NOT_SET"
                details['irq_taken_vblank'] = vblank_taken
                details['reti_count'] = reti_count
                details['ffc5_write_count_total'] = 0
                return classification, details
        
        # Clasificaciones básicas (de v1)
        # 1. CPU no progresa / se queda en loop duro
        if pc_hotspot_1 is not None and hotspot_count > 100000:
            classification = "CPU_LOOP"
            details['hotspot_pc'] = f'0x{pc_hotspot_1:04X}'
            details['hotspot_count'] = hotspot_count
            return classification, details
        
        # 2. Progresa pero LCDC OFF
        if not lcd_on:
            classification = "LCDC_OFF"
            details['lcdc'] = f'0x{lcdc:02X}'
            return classification, details
        
        # 3. Progresa, LCDC ON, pero VRAM tiledata se queda en cero
        if vram_write_stats:
            tiledata_nonzero = vram_write_stats.get('tiledata_nonzero_bank0', 0)
            if tiledata_nonzero == 0:
                classification = "VRAM_TILEDATA_ZERO"
                details['tiledata_nonzero'] = 0
                return classification, details
        
        # 4. Progresa, hay tiledata no-zero, pero fetch o render no lo usa
        if three_buf_stats:
            idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
            if idx_nonzero == 0:
                classification = "IDX_ZERO_DESPITE_TILEDATA"
                details['idx_nonzero'] = 0
                if vram_write_stats:
                    details['tiledata_nonzero'] = vram_write_stats.get('tiledata_nonzero_bank0', 0)
                return classification, details
        
        # 5. Progresa, produce IDX no-zero, pero RGB/present falla
        if three_buf_stats:
            idx_nonzero = three_buf_stats.get('idx_nonzero', 0)
            rgb_nonwhite = three_buf_stats.get('rgb_nonwhite_count', 0)
            if idx_nonzero > 0 and rgb_nonwhite == 0:
                classification = "RGB_FAIL_DESPITE_IDX"
                details['idx_nonzero'] = idx_nonzero
                details['rgb_nonwhite'] = rgb_nonwhite
                return classification, details
        
        # 6. Todo parece OK (pero sigue blanco - puede ser timing/init)
        classification = "OK_BUT_WHITE"
        details['lcdc'] = f'0x{lcdc:02X}'
        if three_buf_stats:
            details['idx_nonzero'] = three_buf_stats.get('idx_nonzero', 0)
            details['rgb_nonwhite'] = three_buf_stats.get('rgb_nonwhite_count', 0)
        
        return classification, details
    
    def _classify_dmg_quick_v3(self, ppu, mmu, renderer=None):
        """
        Step 0501: Clasificación DMG v3 con VRAM Write Audit y PPU Mode Stats.
        
        Este clasificador usa las nuevas métricas de:
        - VRAM Write Audit Stats: detecta si writes están siendo bloqueados, redirigidos, o mal aplicados
        - PPU Mode Stats: detecta problemas de timing del PPU (mode3 stuck, etc.)
        - VRAM Write Ring: eventos detallados de writes VRAM con estado PPU
        
        Args:
            ppu: Instancia de PPU
            mmu: Instancia de MMU
            renderer: Instancia de Renderer (opcional)
        
        Returns:
            Tupla (classification, details) donde:
            - classification: String con la clasificación
            - details: Dict con detalles específicos
        """
        # Obtener VRAM Write Audit Stats
        vram_audit_stats = {}
        try:
            if hasattr(mmu, 'get_vram_write_audit_stats'):
                vram_audit_stats = mmu.get_vram_write_audit_stats() or {}
        except:
            pass
        
        # Obtener PPU Mode Stats
        ppu_mode_stats = {}
        try:
            if hasattr(ppu, 'get_ppu_mode_stats'):
                ppu_mode_stats = ppu.get_ppu_mode_stats() or {}
        except:
            pass
        
        # Obtener VRAM Write Ring (últimos eventos)
        vram_write_ring = []
        try:
            if hasattr(mmu, 'get_vram_write_ring'):
                vram_write_ring = mmu.get_vram_write_ring(20) or []  # Últimos 20 eventos
        except:
            pass
        
        # Obtener métricas básicas
        lcdc = mmu.read(0xFF40)
        lcd_on = (lcdc & 0x80) != 0
        stat = mmu.read(0xFF41)
        ly = mmu.read(0xFF44)
        
        # Clasificar
        classification = "UNKNOWN"
        details = {}
        
        # 1. VRAM_BLOCKED_INCORRECTLY: Intentos de write pero todos bloqueados incorrectamente
        if vram_audit_stats:
            tiledata_attempts = vram_audit_stats.get('tiledata_write_attempts', 0)
            tiledata_blocked = vram_audit_stats.get('tiledata_write_blocked', 0)
            tiledata_allowed = vram_audit_stats.get('tiledata_write_allowed', 0)
            
            if tiledata_attempts > 0:
                blocked_ratio = tiledata_blocked / tiledata_attempts if tiledata_attempts > 0 else 0
                
                # Si más del 90% de los intentos están bloqueados y LCD está ON
                if blocked_ratio > 0.9 and lcd_on and tiledata_attempts > 10:
                    last_blocked_reason = vram_audit_stats.get('last_blocked_reason_str', 'UNKNOWN')
                    
                    # Verificar si el bloqueo es correcto (Mode 3) o incorrecto (otros modos)
                    if vram_write_ring:
                        # Analizar últimos eventos bloqueados
                        recent_blocked = [e for e in vram_write_ring if not e.get('allowed', False)]
                        if recent_blocked:
                            # Verificar modos STAT de eventos bloqueados
                            blocked_modes = [e.get('stat_mode', 255) for e in recent_blocked[-10:]]
                            non_mode3_blocked = [m for m in blocked_modes if m != 3]
                            
                            if non_mode3_blocked:
                                # Hay bloqueos en modos que NO deberían bloquear (según Pan Docs)
                                classification = "VRAM_BLOCKED_INCORRECTLY"
                                details['tiledata_attempts'] = tiledata_attempts
                                details['tiledata_blocked'] = tiledata_blocked
                                details['tiledata_allowed'] = tiledata_allowed
                                details['blocked_ratio'] = f"{blocked_ratio:.2%}"
                                details['last_blocked_reason'] = last_blocked_reason
                                details['blocked_in_modes'] = list(set(blocked_modes))
                                details['non_mode3_blocked_count'] = len(non_mode3_blocked)
                                return classification, details
                    
                    # Si todos los bloqueos son Mode 3 pero hay demasiados, podría ser problema de timing
                    if last_blocked_reason == "LCD_ON_MODE3_BLOCK":
                        # Verificar si Mode 3 está stuck (PPU mode stats)
                        if ppu_mode_stats:
                            frames_mode3_stuck = ppu_mode_stats.get('frames_with_mode3_stuck', 0)
                            if frames_mode3_stuck > 0:
                                classification = "VRAM_BLOCKED_MODE3_STUCK"
                                details['tiledata_attempts'] = tiledata_attempts
                                details['tiledata_blocked'] = tiledata_blocked
                                details['frames_mode3_stuck'] = frames_mode3_stuck
                                return classification, details
        
        # 2. VRAM_WRITE_READBACK_MISMATCH: Writes permitidos pero readback no coincide
        if vram_audit_stats:
            tiledata_mismatch = vram_audit_stats.get('tiledata_write_readback_mismatch', 0)
            tiledata_allowed = vram_audit_stats.get('tiledata_write_allowed', 0)
            
            if tiledata_allowed > 0:
                mismatch_ratio = tiledata_mismatch / tiledata_allowed if tiledata_allowed > 0 else 0
                
                if mismatch_ratio > 0.1 and tiledata_mismatch > 5:
                    classification = "VRAM_WRITE_READBACK_MISMATCH"
                    details['tiledata_allowed'] = tiledata_allowed
                    details['tiledata_readback_mismatch'] = tiledata_mismatch
                    details['mismatch_ratio'] = f"{mismatch_ratio:.2%}"
                    
                    # Buscar ejemplo en el ring
                    if vram_write_ring:
                        mismatched_events = [e for e in vram_write_ring if not e.get('readback_matches', True)]
                        if mismatched_events:
                            example = mismatched_events[0]
                            details['example_pc'] = f"0x{example.get('pc', 0):04X}"
                            details['example_addr'] = f"0x{example.get('addr', 0):04X}"
                            details['example_written'] = f"0x{example.get('value', 0):02X}"
                            details['example_readback'] = f"0x{example.get('readback_value', 0):02X}"
                    
                    return classification, details
        
        # 3. PPU_MODE3_STUCK: PPU está en Mode 3 demasiado tiempo
        if ppu_mode_stats:
            frames_mode3_stuck = ppu_mode_stats.get('frames_with_mode3_stuck', 0)
            mode3_cycles = ppu_mode_stats.get('mode_cycles', [0, 0, 0, 0])[3] if len(ppu_mode_stats.get('mode_cycles', [])) > 3 else 0
            
            if frames_mode3_stuck > 5:
                classification = "PPU_MODE3_STUCK"
                details['frames_mode3_stuck'] = frames_mode3_stuck
                details['mode3_cycles'] = mode3_cycles
                return classification, details
            
            # Verificar si Mode 3 está ocupando demasiado tiempo relativo
            total_mode_cycles = sum(ppu_mode_stats.get('mode_cycles', [0, 0, 0, 0]))
            if total_mode_cycles > 0:
                mode3_ratio = mode3_cycles / total_mode_cycles
                # Mode 3 normalmente ocupa ~37% del tiempo (172/456 ciclos por línea visible)
                # Si ocupa > 60%, podría haber un problema
                if mode3_ratio > 0.60 and mode3_cycles > 10000:
                    classification = "PPU_MODE3_DOMINANT"
                    details['mode3_cycles'] = mode3_cycles
                    details['total_mode_cycles'] = total_mode_cycles
                    details['mode3_ratio'] = f"{mode3_ratio:.2%}"
                    return classification, details
        
        # 4. VRAM_NO_ATTEMPTS: No hay intentos de escribir a VRAM (programa no intenta cargar tiles)
        if vram_audit_stats:
            tiledata_attempts = vram_audit_stats.get('tiledata_write_attempts', 0)
            tilemap_attempts = vram_audit_stats.get('tilemap_write_attempts', 0)
            
            if tiledata_attempts == 0 and tilemap_attempts == 0 and lcd_on:
                # Verificar si el programa está ejecutando (PC hotspots)
                pc_hotspot_1 = None
                try:
                    if hasattr(mmu, 'get_pc_hotspots'):
                        hotspots = mmu.get_pc_hotspots()
                        if hotspots and len(hotspots) > 0:
                            pc_hotspot_1, _ = hotspots[0]
                except:
                    pass
                
                if pc_hotspot_1 is not None:
                    classification = "VRAM_NO_ATTEMPTS"
                    details['tiledata_attempts'] = 0
                    details['tilemap_attempts'] = 0
                    details['lcd_on'] = lcd_on
                    details['pc_hotspot'] = f"0x{pc_hotspot_1:04X}"
                    return classification, details
        
        # 5. VRAM_ALLOWED_BUT_NOT_READABLE: Writes permitidos pero luego no se pueden leer
        # (Similar a readback mismatch pero más específico)
        if vram_audit_stats and vram_write_ring:
            allowed_events = [e for e in vram_write_ring if e.get('allowed', False)]
            if allowed_events:
                # Verificar si hay eventos donde se escribió pero luego el readback no coincide
                problematic = [e for e in allowed_events if not e.get('readback_matches', True)]
                if len(problematic) > len(allowed_events) * 0.2:  # Más del 20% tiene problemas
                    classification = "VRAM_ALLOWED_BUT_NOT_READABLE"
                    details['allowed_events'] = len(allowed_events)
                    details['readback_mismatches'] = len(problematic)
                    details['mismatch_ratio'] = f"{len(problematic) / len(allowed_events):.2%}"
                    return classification, details
        
        # 6. Si no tenemos métricas nuevas, aún intentamos usar v2 como fallback interno
        # pero siempre retornamos algo (nunca UNKNOWN si tenemos datos básicos)
        
        # 7. Si tenemos métricas pero no detectamos problemas específicos, usar v2 como base
        v2_classification, v2_details = self._classify_dmg_quick_v2(ppu, mmu, renderer)
        
        # Añadir métricas v3 a los detalles
        v2_details['v3_vram_audit_available'] = bool(vram_audit_stats)
        v2_details['v3_ppu_mode_stats_available'] = bool(ppu_mode_stats)
        if vram_audit_stats:
            v2_details['v3_tiledata_attempts'] = vram_audit_stats.get('tiledata_write_attempts', 0)
            v2_details['v3_tiledata_allowed'] = vram_audit_stats.get('tiledata_write_allowed', 0)
            v2_details['v3_tiledata_blocked'] = vram_audit_stats.get('tiledata_write_blocked', 0)
        if ppu_mode_stats:
            v2_details['v3_frames_mode3_stuck'] = ppu_mode_stats.get('frames_with_mode3_stuck', 0)
            v2_details['v3_mode_cycles'] = ppu_mode_stats.get('mode_cycles', [0, 0, 0, 0])
        
        return v2_classification, v2_details
    
    def _classify_dmg_quick_v4(self, ppu, mmu, renderer=None):
        """
        Step 0502: Clasificación DMG v4 basada en evidencia de writes cero/no-cero y source reads.
        
        Este clasificador usa las nuevas métricas de Step 0502:
        - Contadores de contenido escrito (cero vs no-cero)
        - Tracking de primer/last nonzero write
        - Correlación source-read (si el valor escrito viene de ROM/RAM que lee cero)
        
        Args:
            ppu: Instancia de PPU
            mmu: Instancia de MMU
            renderer: Instancia de Renderer (opcional)
        
        Returns:
            Tupla (classification, details) donde:
            - classification: String con la clasificación
            - details: Dict con detalles específicos
        """
        # Obtener VRAM Write Stats v2
        vram_stats_v2 = {}
        try:
            if hasattr(mmu, 'get_vram_write_stats_v2'):
                vram_stats_v2 = mmu.get_vram_write_stats_v2() or {}
        except:
            pass
        
        if not vram_stats_v2:
            # Fallback a v3 si v2 no está disponible
            return self._classify_dmg_quick_v3(ppu, mmu, renderer)
        
        tiledata_attempts = vram_stats_v2.get('tiledata_write_attempts', 0)
        tiledata_zero_count = vram_stats_v2.get('tiledata_writes_zero_count', 0)
        tiledata_nonzero_count = vram_stats_v2.get('tiledata_writes_nonzero_count', 0)
        first_nonzero = vram_stats_v2.get('first_nonzero_tiledata_write')
        nonzero_sample = vram_stats_v2.get('nonzero_unique_values_sample', [])
        
        # Clasificaciones del plan Step 0502
        
        # 1. ONLY_CLEAR_TO_ZERO (6144 writes a 0, sin nonzero jamás)
        if tiledata_attempts > 0 and tiledata_zero_count == tiledata_attempts and tiledata_nonzero_count == 0:
            classification = "ONLY_CLEAR_TO_ZERO"
            details = {
                'tiledata_attempts': tiledata_attempts,
                'tiledata_zero_count': tiledata_zero_count,
                'tiledata_nonzero_count': 0,
            }
            return classification, details
        
        # 2. NONZERO_WRITTEN_THEN_CLEARED (aparece nonzero y luego vuelve a 0)
        # Nota: Usamos tiledata_writes_nonzero_count del v2, pero no podemos verificar readback
        # directamente sin método adicional. Por ahora, si hay writes nonzero, asumimos que hay contenido.
        if first_nonzero and tiledata_nonzero_count > 0:
            # TODO: Implementar método para verificar readback de VRAM si es necesario
            # Por ahora, no podemos determinar si fue "escrito y luego borrado" sin readback
            pass
        
        # 3. NONZERO_PRESENT_OK (tiledataNZ sube)
        if first_nonzero and tiledata_nonzero_count > 0:
            # Usamos el contador de writes nonzero como indicador de que hay contenido
            tiledata_nz = tiledata_nonzero_count
            
            if tiledata_nz > 0:
                classification = "NONZERO_PRESENT_OK"
                details = {
                    'first_nonzero': first_nonzero,
                    'tiledata_nonzero_count': tiledata_nonzero_count,
                    'tiledata_nz': tiledata_nz,
                    'nonzero_sample': nonzero_sample,
                }
                return classification, details
        
        # 4. SOURCE_READS_ZERO (src_guess casi siempre 0) - requiere análisis del ring
        # Verificar correlación source-read desde el ring de writes
        vram_write_ring = []
        try:
            if hasattr(mmu, 'get_vram_write_ring'):
                vram_write_ring = mmu.get_vram_write_ring(50) or []  # Últimos 50 eventos
        except:
            pass
        
        if vram_write_ring:
            # Analizar eventos con correlación source válida
            events_with_src = [e for e in vram_write_ring if e.get('src_correlation_valid', False)]
            if events_with_src:
                src_zero_count = sum(1 for e in events_with_src if e.get('src_value_guess', 1) == 0)
                src_zero_ratio = src_zero_count / len(events_with_src) if events_with_src else 0
                
                # Si más del 80% de los source reads son cero y el write también es cero
                if src_zero_ratio > 0.8:
                    # Verificar si los writes también son cero
                    writes_zero = sum(1 for e in events_with_src if e.get('value', 1) == 0)
                    writes_zero_ratio = writes_zero / len(events_with_src) if events_with_src else 0
                    
                    if writes_zero_ratio > 0.8:
                        classification = "SOURCE_READS_ZERO"
                        details = {
                            'events_with_src': len(events_with_src),
                            'src_zero_count': src_zero_count,
                            'src_zero_ratio': f"{src_zero_ratio:.2%}",
                            'writes_zero_ratio': f"{writes_zero_ratio:.2%}",
                            # Mostrar ejemplo de source addr
                            'example_src_addr': f"0x{events_with_src[0].get('src_addr_guess', 0):04X}" if events_with_src else None,
                            'example_src_region': events_with_src[0].get('src_region_str', 'UNKNOWN') if events_with_src else None,
                        }
                        return classification, details
        
        # 5. WAIT_LOOP_ON_ADDR_X (si hotspot lee siempre la misma addr)
        # Esto requiere HotspotExplainer (se implementará en siguiente fase)
        # Por ahora, usar clasificaciones v3 como fallback
        
        # Fallback a v3
        return self._classify_dmg_quick_v3(ppu, mmu, renderer)
    
    def _classify_dmg_blockage(self, after_clear_snapshot: dict) -> str:
        """
        Step 0493: Clasifica el bloqueo DMG post-clear en una categoría.
        
        Args:
            after_clear_snapshot: Diccionario con datos del snapshot AfterClear
        
        Returns:
            Categoría del bloqueo y fix mínimo propuesto
        """
        if not after_clear_snapshot:
            return "UNKNOWN: No hay datos AfterClear"
        
        pc_hotspots_list = after_clear_snapshot.get('pc_hotspots_top3', [])
        io_reads_list = after_clear_snapshot.get('io_reads_top3', [])
        ime = after_clear_snapshot.get('ime', 0)
        ie = after_clear_snapshot.get('ie', 0)
        if_reg = after_clear_snapshot.get('if_reg', 0)
        halted = after_clear_snapshot.get('halted', 0)
        vblank_req = after_clear_snapshot.get('vblank_req', 0)
        vblank_serv = after_clear_snapshot.get('vblank_serv', 0)
        ly = after_clear_snapshot.get('ly', 0)
        stat = after_clear_snapshot.get('stat', 0)
        
        # Analizar IO reads dominantes
        io_dominant = None
        io_dominant_count = 0
        if io_reads_list:
            io_dominant_addr = io_reads_list[0][0]
            io_dominant_count = io_reads_list[0][1]
            
            if io_dominant_addr == 0xFF44:  # LY
                io_dominant = "LY"
            elif io_dominant_addr == 0xFF41:  # STAT
                io_dominant = "STAT"
            elif io_dominant_addr == 0xFF0F:  # IF
                io_dominant = "IF"
            elif io_dominant_addr == 0xFFFF:  # IE
                io_dominant = "IE"
            elif io_dominant_addr == 0xFF04:  # DIV
                io_dominant = "DIV"
            elif io_dominant_addr == 0xFF05:  # TIMA
                io_dominant = "TIMA"
            elif io_dominant_addr == 0xFF07:  # TAC
                io_dominant = "TAC"
            elif io_dominant_addr == 0xFF00:  # JOYP
                io_dominant = "JOYP"
        
        # Clasificar
        if io_dominant == "LY" or io_dominant == "STAT":
            return f"WAIT_LOOP_VBLANK_STAT: Esperando VBlank/STAT/LY. IO dominante: {io_dominant} (count={io_dominant_count}). Fix: Verificar timing PPU/interrupciones VBlank/STAT."
        elif io_dominant == "DIV" or io_dominant == "TIMA" or io_dominant == "TAC":
            return f"WAIT_LOOP_TIMER: Esperando Timer. IO dominante: {io_dominant} (count={io_dominant_count}). Fix: Verificar Timer/DIV/TIMA/TAC."
        elif io_dominant == "JOYP":
            return f"WAIT_LOOP_JOYPAD: Esperando Joypad. IO dominante: {io_dominant} (count={io_dominant_count}). Fix: Verificar Joypad/autopress."
        elif io_dominant == "IF" or io_dominant == "IE":
            if ime == 0:
                return f"WAIT_LOOP_IRQ_DISABLED: Esperando interrupción pero IME=0. IO dominante: {io_dominant} (count={io_dominant_count}). Fix: Verificar IME/IE/IF/timing interrupciones."
            else:
                return f"WAIT_LOOP_IRQ_ENABLED: Esperando interrupción con IME=1. IO dominante: {io_dominant} (count={io_dominant_count}), IE={ie:02X}, IF={if_reg:02X}. Fix: Verificar servicio de interrupciones."
        elif halted == 1:
            return f"HALTED: CPU en HALT. IME={ime}, IE={ie:02X}, IF={if_reg:02X}. Fix: Verificar que interrupciones despierten CPU de HALT."
        else:
            pc_hotspot_1 = pc_hotspots_list[0][0] if pc_hotspots_list else 0xFFFF
            return f"UNKNOWN: PC hotspot={pc_hotspot_1:04X}, IO dominante={io_dominant}, IME={ime}, IE={ie:02X}, IF={if_reg:02X}. Revisar disasm para identificar condición."
    
    def _print_summary(self):
        """Imprime resumen final de métricas."""
        elapsed = time.time() - self.start_time
        frames_executed = len(self.metrics)
        
        print(f"\n" + "=" * 80)
        print(f"RESUMEN FINAL")
        print(f"=" * 80)
        print(f"Frames ejecutados: {frames_executed}")
        print(f"Tiempo total: {elapsed:.2f}s")
        print(f"")
        
        # Baseline rendimiento (Step 0443)
        if frames_executed > 0:
            fps_approx = frames_executed / elapsed
            ms_per_frame = (elapsed / frames_executed) * 1000
            print(f"RENDIMIENTO:")
            print(f"  FPS aproximado: {fps_approx:.1f}")
            print(f"  ms/frame promedio: {ms_per_frame:.2f}")
            print(f"  Tiempo total: {elapsed:.2f}s")
            print(f"")
        
        if not self.metrics:
            print("Sin métricas recolectadas.")
            return
        
        # Estadísticas de nonwhite_pixels
        nonwhite_values = [m['nonwhite_pixels'] for m in self.metrics]
        min_nw = min(nonwhite_values)
        max_nw = max(nonwhite_values)
        avg_nw = sum(nonwhite_values) / len(nonwhite_values)
        
        print(f"NONWHITE PIXELS (estimado por muestreo):")
        print(f"  Mín: {min_nw:5d}  Máx: {max_nw:5d}  Prom: {avg_nw:5.0f}")
        print(f"  Primer frame > 0: {self.first_nonwhite_frame if self.first_nonwhite_frame is not None else 'NUNCA'}")
        print(f"")
        
        # Estadísticas de VRAM nonzero
        vram_values = [m['vram_nonzero'] for m in self.metrics]
        min_vram = min(vram_values)
        max_vram = max(vram_values)
        avg_vram = sum(vram_values) / len(vram_values)
        
        print(f"VRAM NONZERO (bytes, estimado por muestreo):")
        print(f"  Mín: {min_vram:4d}  Máx: {max_vram:4d}  Prom: {avg_vram:4.0f}")
        print(f"")
        
        # Step 0450: Estadísticas de VRAM nonzero RAW (sin restricciones)
        vram_raw_values = [m['vram_nonzero_raw'] for m in self.metrics]
        min_vram_raw = min(vram_raw_values)
        max_vram_raw = max(vram_raw_values)
        avg_vram_raw = sum(vram_raw_values) / len(vram_raw_values)
        
        print(f"VRAM NONZERO RAW (bytes, read_raw, sin restricciones) - Step 0450:")
        print(f"  Mín: {min_vram_raw:4d}  Máx: {max_vram_raw:4d}  Prom: {avg_vram_raw:4.0f}")
        print(f"")
        
        # Step 0444: Estadísticas de OAM nonzero
        oam_values = [m['oam_nonzero'] for m in self.metrics]
        min_oam = min(oam_values)
        max_oam = max(oam_values)
        avg_oam = sum(oam_values) / len(oam_values)
        
        print(f"OAM NONZERO (bytes, estimado por muestreo) - Step 0444:")
        print(f"  Mín: {min_oam:4d}  Máx: {max_oam:4d}  Prom: {avg_oam:4.0f}")
        print(f"")
        
        # Step 0454: Estadísticas de métricas robustas
        unique_rgb_values = [m['unique_rgb_count'] for m in self.metrics]
        dominant_ratio_values = [m['dominant_ratio'] for m in self.metrics]
        min_unique = min(unique_rgb_values) if unique_rgb_values else 0
        max_unique = max(unique_rgb_values) if unique_rgb_values else 0
        avg_unique = sum(unique_rgb_values) / len(unique_rgb_values) if unique_rgb_values else 0
        min_dominant = min(dominant_ratio_values) if dominant_ratio_values else 1.0
        max_dominant = max(dominant_ratio_values) if dominant_ratio_values else 1.0
        avg_dominant = sum(dominant_ratio_values) / len(dominant_ratio_values) if dominant_ratio_values else 1.0
        
        print(f"ROBUST METRICS (Step 0454):")
        print(f"  unique_rgb_count: Mín={min_unique}  Máx={max_unique}  Prom={avg_unique:.1f}")
        print(f"  dominant_ratio: Mín={min_dominant:.3f}  Máx={max_dominant:.3f}  Prom={avg_dominant:.3f}")
        print(f"")
        
        # Resumen I/O con LY/STAT 3-points (Step 0443)
        print(f"I/O RESUMEN (primeros 3 frames) - LY/STAT 3-Points:")
        for i in range(min(3, len(self.metrics))):
            m = self.metrics[i]
            print(f"  Frame {m['frame']:04d}: PC={m['pc']:04X} LCDC={m['lcdc']:02X} BGP={m['bgp']:02X}")
            print(f"    LY: first={m['ly_first']:02X} mid={m['ly_mid']:02X} last={m['ly_last']:02X}")
            print(f"    STAT: first={m['stat_first']:02X} mid={m['stat_mid']:02X} last={m['stat_last']:02X}")
        
        if len(self.metrics) > 6:
            print(f"  ... ({len(self.metrics) - 6} frames omitidos) ...")
        
        if len(self.metrics) > 3:
            print(f"I/O RESUMEN (últimos 3 frames) - LY/STAT 3-Points:")
            for i in range(max(3, len(self.metrics) - 3), len(self.metrics)):
                m = self.metrics[i]
                print(f"  Frame {m['frame']:04d}: PC={m['pc']:04X} LCDC={m['lcdc']:02X} BGP={m['bgp']:02X}")
                print(f"    LY: first={m['ly_first']:02X} mid={m['ly_mid']:02X} last={m['ly_last']:02X}")
                print(f"    STAT: first={m['stat_first']:02X} mid={m['stat_mid']:02X} last={m['stat_last']:02X}")
        
        # --- Step 0498: FrameIdConsistency Table (solo si use_renderer_headless) ---
        if self.use_renderer_headless and self._renderer is not None:
            print(f"\n" + "=" * 80)
            print(f"FRAME ID CONSISTENCY TABLE (Step 0498)")
            print(f"=" * 80)
            
            frame_id_consistency = self._generate_frame_id_consistency_table()
            
            if frame_id_consistency:
                print(f"\nFirst Signal Frame ID: {self._first_signal_frame_id}")
                print(f"\nTabla (50 filas alrededor del first signal):")
                print(f"{'fid':>10} | {'ppu_front_fid':>15} | {'ppu_back_fid':>13} | {'ppu_front_rgb_crc':>18} | "
                      f"{'renderer_received_fid':>22} | {'renderer_src_crc':>18} | {'renderer_present_crc':>22} | "
                      f"{'present_nonwhite':>17} | {'classification':>15}")
                print("-" * 160)
                
                for row in frame_id_consistency:
                    fid = row.get('fid', 0)
                    ppu_front_fid = row.get('ppu_front_fid')
                    ppu_back_fid = row.get('ppu_back_fid')
                    ppu_front_rgb_crc = row.get('ppu_front_rgb_crc')
                    renderer_received_fid = row.get('renderer_received_fid')
                    renderer_src_crc = row.get('renderer_src_crc')
                    renderer_present_crc = row.get('renderer_present_crc')
                    present_nonwhite = row.get('present_nonwhite')
                    classification = row.get('classification', 'UNKNOWN')
                    
                    # Formatear valores (convertir None a string y CRCs a hex)
                    ppu_front_fid_str = str(ppu_front_fid) if ppu_front_fid is not None else 'None'
                    ppu_back_fid_str = str(ppu_back_fid) if ppu_back_fid is not None else 'None'
                    
                    if isinstance(ppu_front_rgb_crc, int):
                        ppu_front_rgb_crc_str = f"0x{ppu_front_rgb_crc:08X}"
                    else:
                        ppu_front_rgb_crc_str = 'None'
                    
                    renderer_received_fid_str = str(renderer_received_fid) if renderer_received_fid is not None else 'None'
                    
                    if isinstance(renderer_src_crc, int):
                        renderer_src_crc_str = f"0x{renderer_src_crc:08X}"
                    else:
                        renderer_src_crc_str = 'None'
                    
                    if isinstance(renderer_present_crc, int):
                        renderer_present_crc_str = f"0x{renderer_present_crc:08X}"
                    else:
                        renderer_present_crc_str = 'None'
                    
                    present_nonwhite_str = str(present_nonwhite) if present_nonwhite is not None else 'None'
                    
                    print(f"{fid:>10} | {ppu_front_fid_str:>15} | {ppu_back_fid_str:>13} | {ppu_front_rgb_crc_str:>18} | "
                          f"{renderer_received_fid_str:>22} | {renderer_src_crc_str:>18} | {renderer_present_crc_str:>22} | "
                          f"{present_nonwhite_str:>17} | {classification:>15}")
                
                # Análisis de clasificaciones
                classifications = [row.get('classification', 'UNKNOWN') for row in frame_id_consistency]
                classification_counts = {}
                for cls in classifications:
                    classification_counts[cls] = classification_counts.get(cls, 0) + 1
                
                print(f"\nAnálisis de Clasificaciones:")
                for cls, count in sorted(classification_counts.items()):
                    print(f"  {cls}: {count} filas")
                
                # Conclusión
                ok_count = classification_counts.get('OK_SAME_FRAME', 0) + classification_counts.get('OK_LAG_1', 0)
                total_count = len(frame_id_consistency)
                
                if ok_count == total_count:
                    print(f"\n✅ CONCLUSIÓN: Present = Front (mismo frame_id y CRC) con lag de 1 frame")
                elif ok_count > total_count * 0.8:
                    print(f"\n⚠️ CONCLUSIÓN: Mayoría OK ({ok_count}/{total_count}), pero hay {total_count - ok_count} discrepancias")
                else:
                    print(f"\n❌ CONCLUSIÓN: Present no coincide (CRC/frame_id) ⇒ bug en orden/swap/copia")
            else:
                print("No se generó tabla FrameIdConsistency (first_signal no detectado o sin datos)")
            # -----------------------------------------
        
        print(f"")
        
        # Diagnóstico LY/STAT (Step 0443)
        print(f"DIAGNÓSTICO LY/STAT 3-POINTS:")
        ly_samples_all = []
        stat_samples_all = []
        for m in self.metrics[:10]:  # Primeros 10 frames
            ly_samples_all.extend([m['ly_first'], m['ly_mid'], m['ly_last']])
            stat_samples_all.extend([m['stat_first'], m['stat_mid'], m['stat_last']])
        
        unique_ly = len(set(ly_samples_all))
        unique_stat = len(set(stat_samples_all))
        max_ly = max(ly_samples_all) if ly_samples_all else 0
        min_ly = min(ly_samples_all) if ly_samples_all else 0
        
        if unique_ly == 1 and ly_samples_all[0] == 0:
            print(f"  ⚠️  LY siempre 0 en los 3 puntos → BUG REAL (LY no avanza o lectura incorrecta)")
        elif unique_ly == 1:
            print(f"  ⚠️  LY siempre {ly_samples_all[0]:02X} en los 3 puntos → posible bug (LY no avanza)")
        else:
            print(f"  ✅ LY varía correctamente (range: {min_ly:02X}..{max_ly:02X}, únicos: {unique_ly})")
            print(f"     → Sampling issue resuelto: LY avanza durante el frame")
        
        if unique_stat == 1:
            print(f"  ⚠️  STAT siempre igual ({stat_samples_all[0]:02X}) → posible bug en PPU.step() (modo no cambia)")
        else:
            stat_modes = [s & 0x03 for s in stat_samples_all]
            unique_modes = len(set(stat_modes))
            print(f"  ✅ STAT varía correctamente (modos únicos: {unique_modes}, range: {min(stat_modes)}..{max(stat_modes)})")
        
        print(f"")
        
        # Step 0450: Log MBC writes summary si está disponible
        if hasattr(self.mmu, 'log_mbc_writes_summary'):
            self.mmu.log_mbc_writes_summary()
            print(f"")
        
        # Diagnóstico preliminar
        print(f"DIAGNÓSTICO PRELIMINAR:")
        if max_nw == 0:
            print(f"  ⚠️  Framebuffer BLANCO (0 píxeles non-white)")
            
            # Step 0450: Comparar VRAM normal vs RAW
            if max_vram_raw > 0 and max_vram == 0:
                print(f"  🔍 VRAM RAW tiene datos (max={max_vram_raw}) pero read() devuelve 0")
                print(f"     → Caso: Restricciones de acceso (modo PPU/banking) bloquean lectura")
            elif max_vram_raw > 0:
                print(f"  🔍 VRAM non-zero detectado (max={max_vram_raw} raw, {max_vram} normal)")
                print(f"     → Caso 1: Probable bug en fetch BG/window/paleta")
            else:
                print(f"  🔍 VRAM completamente vacío (0 bytes non-zero)")
                print(f"     → Caso 2: CPU progresa pero writes no llegan a VRAM")
                print(f"        o juego espera condición (joypad/interrupts/DMA/MBC)")
        else:
            print(f"  ✅ Framebuffer NO BLANCO (max={max_nw} píxeles non-white)")
            print(f"     → Sistema funciona correctamente")
        
        # Step 0487: Reporte específico para Mario (FF92/IE trace)
        report_lines = []
        if 'mario' in self.rom_path.name.lower():
            report_lines.extend(self._print_mario_ff92_ie_report())
        
        # Step 0487: Reporte específico para Tetris DX (JOYP semantics)
        if 'tetris' in self.rom_path.name.lower():
            report_lines.extend(self._print_tetris_joyp_report())
        
        # Escribir reporte a /tmp/reporte_step0487.md si hay contenido
        if report_lines:
            self._write_report_to_file(report_lines)
        
        print(f"=" * 80)
    
    def _print_mario_ff92_ie_report(self):
        """
        Step 0487: Genera reporte detallado de FF92/IE trace para Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Lista de líneas del reporte (para escribir a archivo)
        """
        import os
        if not os.getenv('VIBOY_DEBUG_MARIO_FF92'):
            return []
        
        report_lines = []
        
        header = f"\n" + "=" * 80 + f"\nMARIO FF92/IE TRACE REPORT (Step 0487)\n" + "=" * 80
        print(header)
        report_lines.append(header)
        
        # FF92 Single Source of Truth
        ff92_write_count = self.mmu.get_ff92_write_count_total()
        ff92_read_count = self.mmu.get_ff92_read_count_total()
        ff92_last_write_pc = self.mmu.get_ff92_last_write_pc()
        ff92_last_write_val = self.mmu.get_ff92_last_write_val()
        ff92_last_read_pc = self.mmu.get_ff92_last_read_pc()
        ff92_last_read_val = self.mmu.get_ff92_last_read_val()
        
        section1 = f"\nFF92 Single Source of Truth:\n  Writes totales: {ff92_write_count}\n  Reads totales: {ff92_read_count}\n  Último write: PC=0x{ff92_last_write_pc:04X}, val=0x{ff92_last_write_val:02X}\n  Último read: PC=0x{ff92_last_read_pc:04X}, val=0x{ff92_last_read_val:02X}"
        print(section1)
        report_lines.append(section1)
        
        # IE Write Tracking
        ie_write_count = self.mmu.get_ie_write_count_total()
        ie_last_write_pc = self.mmu.get_ie_last_write_pc()
        ie_value_after_write = self.mmu.get_ie_value_after_write()
        
        section2 = f"\nIE Write Tracking:\n  Writes totales: {ie_write_count}\n  Último write: PC=0x{ie_last_write_pc:04X}, val=0x{ie_value_after_write:02X}"
        print(section2)
        report_lines.append(section2)
        
        # FF92/IE Trace (últimos 50 eventos)
        trace_tail = self.cpu.get_ff92_ie_trace_tail(50)
        trace_full = self.cpu.get_ff92_ie_trace()
        
        section3 = f"\nFF92/IE Trace (últimos 50 eventos):\n  Total eventos en trace: {len(trace_full)}"
        print(section3)
        report_lines.append(section3)
        
        if trace_tail:
            header_trace = f"  Formato: [Tipo] Frame | PC | a8 | effective_addr | val\n  Tipos: 0=FF92_W, 1=FF92_R, 2=IE_W\n  ---"
            print(header_trace)
            report_lines.append(header_trace)
            for event in trace_tail[-20:]:  # Mostrar últimos 20
                type_str = {0: "FF92_W", 1: "FF92_R", 2: "IE_W"}.get(event['type'], "UNK")
                line = f"  [{type_str:6s}] Frame {event['frame']:4d} | PC=0x{event['pc']:04X} | a8=0x{event['a8']:02X} | addr=0x{event['effective_addr']:04X} | val=0x{event['val']:02X}"
                print(line)
                report_lines.append(line)
            if len(trace_tail) > 20:
                omit_msg = f"  ... ({len(trace_tail) - 20} eventos anteriores omitidos)"
                print(omit_msg)
                report_lines.append(omit_msg)
        else:
            no_trace = f"  ⚠️  No hay eventos en el trace"
            print(no_trace)
            report_lines.append(no_trace)
        
        # Análisis de cadena FF92 → IE
        section4 = f"\nAnálisis de Cadena FF92 → IE:"
        print(section4)
        report_lines.append(section4)
        
        if ff92_write_count > 0 and ff92_read_count > 0 and ie_write_count > 0:
            chain_msg = f"  ✅ Evidencia de cadena: FF92_W ({ff92_write_count}) → FF92_R ({ff92_read_count}) → IE_W ({ie_write_count})"
        elif ff92_write_count > 0:
            chain_msg = f"  ⚠️  Solo FF92 writes detectados ({ff92_write_count}), no hay reads ni IE writes"
        else:
            chain_msg = f"  ⚠️  No hay actividad FF92/IE detectada"
        print(chain_msg)
        report_lines.append(chain_msg)
        
        footer = f"=" * 80
        print(footer)
        report_lines.append(footer)
        
        return report_lines
    
    def _print_tetris_joyp_report(self):
        """
        Step 0487: Genera reporte detallado de JOYP semantics para Tetris DX.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Lista de líneas del reporte (para escribir a archivo)
        """
        import os
        if not os.getenv('VIBOY_DEBUG_JOYP_TRACE'):
            return []
        
        report_lines = []
        
        header = f"\n" + "=" * 80 + f"\nTETRIS DX JOYP SEMANTICS REPORT (Step 0487)\n" + "=" * 80
        print(header)
        report_lines.append(header)
        
        # JOYP Write Counters por Selección
        joyp_write_buttons = self.mmu.get_joyp_write_buttons_selected_total()
        joyp_write_dpad = self.mmu.get_joyp_write_dpad_selected_total()
        joyp_write_none = self.mmu.get_joyp_write_none_selected_total()
        total_writes = joyp_write_buttons + joyp_write_dpad + joyp_write_none
        
        section1 = f"\nJOYP Write Counters (por tipo de selección):\n  BUTTONS_SELECTED writes: {joyp_write_buttons}\n  DPAD_SELECTED writes: {joyp_write_dpad}\n  NONE_SELECTED writes: {joyp_write_none}\n  Total writes: {total_writes}"
        print(section1)
        report_lines.append(section1)
        
        # JOYP Read Counters por Selección y Source
        joyp_read_buttons_prog = self.mmu.get_joyp_read_buttons_selected_total_prog()
        joyp_read_dpad_prog = self.mmu.get_joyp_read_dpad_selected_total_prog()
        joyp_read_none_prog = self.mmu.get_joyp_read_none_selected_total_prog()
        joyp_read_buttons_cpu_poll = self.mmu.get_joyp_read_buttons_selected_total_cpu_poll()
        joyp_read_dpad_cpu_poll = self.mmu.get_joyp_read_dpad_selected_total_cpu_poll()
        joyp_read_none_cpu_poll = self.mmu.get_joyp_read_none_selected_total_cpu_poll()
        
        total_reads = (joyp_read_buttons_prog + joyp_read_dpad_prog + joyp_read_none_prog +
                      joyp_read_buttons_cpu_poll + joyp_read_dpad_cpu_poll + joyp_read_none_cpu_poll)
        
        section2 = f"\nJOYP Read Counters (por tipo de selección y source):\n  BUTTONS_SELECTED reads:\n    Program: {joyp_read_buttons_prog}\n    CPU Poll: {joyp_read_buttons_cpu_poll}\n  DPAD_SELECTED reads:\n    Program: {joyp_read_dpad_prog}\n    CPU Poll: {joyp_read_dpad_cpu_poll}\n  NONE_SELECTED reads:\n    Program: {joyp_read_none_prog}\n    CPU Poll: {joyp_read_none_cpu_poll}\n  Total reads: {total_reads}"
        print(section2)
        report_lines.append(section2)
        
        # Análisis de patrones
        section3 = f"\nAnálisis de Patrones:"
        print(section3)
        report_lines.append(section3)
        
        if joyp_write_buttons > 0 and joyp_read_buttons_prog > 0:
            pattern1 = f"  ✅ Patrón BUTTONS detectado: {joyp_write_buttons} writes, {joyp_read_buttons_prog} reads (program)"
            print(pattern1)
            report_lines.append(pattern1)
            if joyp_read_buttons_cpu_poll > 0:
                pattern1b = f"     También {joyp_read_buttons_cpu_poll} reads desde CPU poll"
                print(pattern1b)
                report_lines.append(pattern1b)
        if joyp_write_dpad > 0 and joyp_read_dpad_prog > 0:
            pattern2 = f"  ✅ Patrón DPAD detectado: {joyp_write_dpad} writes, {joyp_read_dpad_prog} reads (program)"
            print(pattern2)
            report_lines.append(pattern2)
            if joyp_read_dpad_cpu_poll > 0:
                pattern2b = f"     También {joyp_read_dpad_cpu_poll} reads desde CPU poll"
                print(pattern2b)
                report_lines.append(pattern2b)
        if joyp_write_none > 0:
            pattern3 = f"  ⚠️  {joyp_write_none} writes con NONE_SELECTED (posible deselección)"
            print(pattern3)
            report_lines.append(pattern3)
        
        footer = f"=" * 80
        print(footer)
        report_lines.append(footer)
        
        return report_lines
    
    def _write_report_to_file(self, report_lines: List[str]):
        """
        Step 0487: Escribe el reporte a /tmp/reporte_step0487.md
        """
        report_path = Path("/tmp/reporte_step0487.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("# Reporte Step 0487 - Fiabilidad Watch/Trace + Blindar Semántica JOYP\n\n")
            f.write(f"ROM: {self.rom_path.name}\n")
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("\n".join(report_lines))
        print(f"\n✅ Reporte escrito a: {report_path}")


def main():
    """Función principal."""
    parser = argparse.ArgumentParser(
        description="ROM Smoke Test - Herramienta headless para diagnóstico (Step 0442)"
    )
    parser.add_argument("rom", type=str, help="Ruta al archivo ROM (.gb o .gbc)")
    parser.add_argument("--frames", type=int, default=300,
                        help="Número máximo de frames a ejecutar (default: 300)")
    parser.add_argument("--dump-every", type=int, default=0,
                        help="Cada cuántos frames dumpear métricas (default: 0 = solo final)")
    parser.add_argument("--dump-png", action="store_true",
                        help="Generar PNGs de framebuffers seleccionados")
    parser.add_argument("--max-seconds", type=int, default=120,
                        help="Timeout máximo de ejecución en segundos (default: 120)")
    parser.add_argument("--stop-early-on-first-nonzero", action="store_true",
                        help="Parar cuando tiledata_first_nonzero_frame exista (Step 0492)")
    parser.add_argument("--stop-on-first-tiledata-nonzero", action="store_true",
                        help="Step 0502: Parar cuando se detecte primer tiledata no-cero en VRAM (readback)")
    parser.add_argument("--stop-on-first-tiledata-nonzero-write", action="store_true",
                        help="Step 0502: Parar cuando se detecte primer write no-cero a tiledata")
    parser.add_argument("--use-renderer-headless", action="store_true",
                        help="Usar renderer headless para capturar FB_PRESENT_SRC (Step 0497)")
    parser.add_argument("--use-renderer-windowed", action="store_true",
                        help="Usar renderer windowed (para testing event pumping) (Step 0499)")
    
    args = parser.parse_args()
    
    try:
        runner = ROMSmokeRunner(
            rom_path=args.rom,
            max_frames=args.frames,
            dump_every=args.dump_every,
            dump_png=args.dump_png,
            max_seconds=args.max_seconds,
            stop_early_on_first_nonzero=args.stop_early_on_first_nonzero,
            use_renderer_headless=args.use_renderer_headless,
            use_renderer_windowed=args.use_renderer_windowed,
            stop_on_first_tiledata_nonzero=args.stop_on_first_tiledata_nonzero,
            stop_on_first_tiledata_nonzero_write=args.stop_on_first_tiledata_nonzero_write
        )
        runner.run()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

