#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Volcado de Zona de ROM (Step 0249)
Volca una zona específica de la ROM en formato hexadecimal y desensamblado básico.

Uso:
    python tools/dump_rom_zone.py [rom_path] [start_addr] [end_addr]
    
Ejemplo:
    python tools/dump_rom_zone.py roms/tetris.gb 0x2B20 0x2BC0
"""

import sys
import os
from pathlib import Path

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    import io
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Diccionario básico de opcodes Game Boy (solo los más comunes para referencia)
GB_OPCODES = {
    0x00: "NOP",
    0x01: "LD BC,d16",
    0x02: "LD (BC),A",
    0x03: "INC BC",
    0x04: "INC B",
    0x05: "DEC B",
    0x06: "LD B,d8",
    0x07: "RLCA",
    0x08: "LD (a16),SP",
    0x09: "ADD HL,BC",
    0x0A: "LD A,(BC)",
    0x0B: "DEC BC",
    0x0C: "INC C",
    0x0D: "DEC C",
    0x0E: "LD C,d8",
    0x0F: "RRCA",
    0x10: "STOP",
    0x11: "LD DE,d16",
    0x12: "LD (DE),A",
    0x13: "INC DE",
    0x14: "INC D",
    0x15: "DEC D",
    0x16: "LD D,d8",
    0x17: "RLA",
    0x18: "JR r8",
    0x19: "ADD HL,DE",
    0x1A: "LD A,(DE)",
    0x1B: "DEC DE",
    0x1C: "INC E",
    0x1D: "DEC E",
    0x1E: "LD E,d8",
    0x1F: "RRA",
    0x20: "JR NZ,r8",
    0x21: "LD HL,d16",
    0x22: "LD (HL+),A",
    0x23: "INC HL",
    0x24: "INC H",
    0x25: "DEC H",
    0x26: "LD H,d8",
    0x27: "DAA",
    0x28: "JR Z,r8",
    0x29: "ADD HL,HL",
    0x2A: "LD A,(HL+)",
    0x2B: "DEC HL",
    0x2C: "INC L",
    0x2D: "DEC L",
    0x2E: "LD L,d8",
    0x2F: "CPL",
    0x30: "JR NC,r8",
    0x31: "LD SP,d16",
    0x32: "LD (HL-),A",
    0x33: "INC SP",
    0x34: "INC (HL)",
    0x35: "DEC (HL)",
    0x36: "LD (HL),d8",
    0x37: "SCF",
    0x38: "JR C,r8",
    0x39: "ADD HL,SP",
    0x3A: "LD A,(HL-)",
    0x3B: "DEC SP",
    0x3C: "INC A",
    0x3D: "DEC A",
    0x3E: "LD A,d8",
    0x3F: "CCF",
    0x40: "LD B,B",
    0x41: "LD B,C",
    0x42: "LD B,D",
    0x43: "LD B,E",
    0x44: "LD B,H",
    0x45: "LD B,L",
    0x46: "LD B,(HL)",
    0x47: "LD B,A",
    0x48: "LD C,B",
    0x49: "LD C,C",
    0x4A: "LD C,D",
    0x4B: "LD C,E",
    0x4C: "LD C,H",
    0x4D: "LD C,L",
    0x4E: "LD C,(HL)",
    0x4F: "LD C,A",
    0x50: "LD D,B",
    0x51: "LD D,C",
    0x52: "LD D,D",
    0x53: "LD D,E",
    0x54: "LD D,H",
    0x55: "LD D,L",
    0x56: "LD D,(HL)",
    0x57: "LD D,A",
    0x58: "LD E,B",
    0x59: "LD E,C",
    0x5A: "LD E,D",
    0x5B: "LD E,E",
    0x5C: "LD E,H",
    0x5D: "LD E,L",
    0x5E: "LD E,(HL)",
    0x5F: "LD E,A",
    0x60: "LD H,B",
    0x61: "LD H,C",
    0x62: "LD H,D",
    0x63: "LD H,E",
    0x64: "LD H,H",
    0x65: "LD H,L",
    0x66: "LD H,(HL)",
    0x67: "LD H,A",
    0x68: "LD L,B",
    0x69: "LD L,C",
    0x6A: "LD L,D",
    0x6B: "LD L,E",
    0x6C: "LD L,H",
    0x6D: "LD L,L",
    0x6E: "LD L,(HL)",
    0x6F: "LD L,A",
    0x70: "LD (HL),B",
    0x71: "LD (HL),C",
    0x72: "LD (HL),D",
    0x73: "LD (HL),E",
    0x74: "LD (HL),H",
    0x75: "LD (HL),L",
    0x76: "HALT",
    0x77: "LD (HL),A",
    0x78: "LD A,B",
    0x79: "LD A,C",
    0x7A: "LD A,D",
    0x7B: "LD A,E",
    0x7C: "LD A,H",
    0x7D: "LD A,L",
    0x7E: "LD A,(HL)",
    0x7F: "LD A,A",
    0x80: "ADD A,B",
    0x81: "ADD A,C",
    0x82: "ADD A,D",
    0x83: "ADD A,E",
    0x84: "ADD A,H",
    0x85: "ADD A,L",
    0x86: "ADD A,(HL)",
    0x87: "ADD A,A",
    0x88: "ADC A,B",
    0x89: "ADC A,C",
    0x8A: "ADC A,D",
    0x8B: "ADC A,E",
    0x8C: "ADC A,H",
    0x8D: "ADC A,L",
    0x8E: "ADC A,(HL)",
    0x8F: "ADC A,A",
    0x90: "SUB B",
    0x91: "SUB C",
    0x92: "SUB D",
    0x93: "SUB E",
    0x94: "SUB H",
    0x95: "SUB L",
    0x96: "SUB (HL)",
    0x97: "SUB A",
    0x98: "SBC A,B",
    0x99: "SBC A,C",
    0x9A: "SBC A,D",
    0x9B: "SBC A,E",
    0x9C: "SBC A,H",
    0x9D: "SBC A,L",
    0x9E: "SBC A,(HL)",
    0x9F: "SBC A,A",
    0xA0: "AND B",
    0xA1: "AND C",
    0xA2: "AND D",
    0xA3: "AND E",
    0xA4: "AND H",
    0xA5: "AND L",
    0xA6: "AND (HL)",
    0xA7: "AND A",
    0xA8: "XOR B",
    0xA9: "XOR C",
    0xAA: "XOR D",
    0xAB: "XOR E",
    0xAC: "XOR H",
    0xAD: "XOR L",
    0xAE: "XOR (HL)",
    0xAF: "XOR A",
    0xB0: "OR B",
    0xB1: "OR C",
    0xB2: "OR D",
    0xB3: "OR E",
    0xB4: "OR H",
    0xB5: "OR L",
    0xB6: "OR (HL)",
    0xB7: "OR A",
    0xB8: "CP B",
    0xB9: "CP C",
    0xBA: "CP D",
    0xBB: "CP E",
    0xBC: "CP H",
    0xBD: "CP L",
    0xBE: "CP (HL)",
    0xBF: "CP A",
    0xC0: "RET NZ",
    0xC1: "POP BC",
    0xC2: "JP NZ,a16",
    0xC3: "JP a16",
    0xC4: "CALL NZ,a16",
    0xC5: "PUSH BC",
    0xC6: "ADD A,d8",
    0xC7: "RST 00H",
    0xC8: "RET Z",
    0xC9: "RET",
    0xCA: "JP Z,a16",
    0xCB: "PREFIX CB",  # Instrucciones CB
    0xCC: "CALL Z,a16",
    0xCD: "CALL a16",
    0xCE: "ADC A,d8",
    0xCF: "RST 08H",
    0xD0: "RET NC",
    0xD1: "POP DE",
    0xD2: "JP NC,a16",
    0xD3: None,  # No existe
    0xD4: "CALL NC,a16",
    0xD5: "PUSH DE",
    0xD6: "SUB d8",
    0xD7: "RST 10H",
    0xD8: "RET C",
    0xD9: "RETI",
    0xDA: "JP C,a16",
    0xDB: None,  # No existe
    0xDC: "CALL C,a16",
    0xDD: None,  # No existe
    0xDE: "SBC A,d8",
    0xDF: "RST 18H",
    0xE0: "LDH (a8),A",
    0xE1: "POP HL",
    0xE2: "LD (C),A",
    0xE3: None,  # No existe
    0xE4: None,  # No existe
    0xE5: "PUSH HL",
    0xE6: "AND d8",
    0xE7: "RST 20H",
    0xE8: "ADD SP,r8",
    0xE9: "JP (HL)",
    0xEA: "LD (a16),A",
    0xEB: None,  # No existe
    0xEC: None,  # No existe
    0xED: None,  # No existe
    0xEE: "XOR d8",
    0xEF: "RST 28H",
    0xF0: "LDH A,(a8)",
    0xF1: "POP AF",
    0xF2: "LD A,(C)",
    0xF3: "DI",
    0xF4: None,  # No existe
    0xF5: "PUSH AF",
    0xF6: "OR d8",
    0xF7: "RST 30H",
    0xF8: "LD HL,SP+r8",
    0xF9: "LD SP,HL",
    0xFA: "LD A,(a16)",
    0xFB: "EI",
    0xFC: None,  # No existe
    0xFD: None,  # No existe
    0xFE: "CP d8",
    0xFF: "RST 38H",
}

def parse_address(addr_str):
    """Convierte una dirección hexadecimal a entero."""
    if addr_str.startswith('0x') or addr_str.startswith('0X'):
        return int(addr_str, 16)
    return int(addr_str, 16)

def dump_rom_zone(rom_path, start_addr, end_addr):
    """Volca una zona de la ROM en formato hexadecimal."""
    rom_file = Path(rom_path)
    
    if not rom_file.exists():
        print(f"❌ Error: No se encuentra el archivo ROM: {rom_path}")
        return False
    
    try:
        with open(rom_file, 'rb') as f:
            # Leer toda la ROM
            rom_data = f.read()
            
            if start_addr >= len(rom_data):
                print(f"❌ Error: Dirección de inicio ({hex(start_addr)}) está fuera del rango de la ROM")
                return False
            
            if end_addr > len(rom_data):
                print(f"⚠️  Advertencia: Dirección de fin ({hex(end_addr)}) está fuera del rango de la ROM. Ajustando a {hex(len(rom_data))}")
                end_addr = len(rom_data)
            
            zone_data = rom_data[start_addr:end_addr]
            
            print(f"\n{'='*80}")
            print(f"📦 VOLCADO DE ROM: {rom_file.name}")
            print(f"📍 Zona: {hex(start_addr)} - {hex(end_addr)} ({len(zone_data)} bytes)")
            print(f"{'='*80}\n")
            
            # Volcado hexadecimal con desensamblado básico
            bytes_per_line = 16
            current_addr = start_addr
            i = 0
            
            while i < len(zone_data):
                # Dirección actual
                addr_str = f"{current_addr:04X}"
                
                # Bytes en hexadecimal
                hex_bytes = []
                ascii_repr = []
                
                for j in range(bytes_per_line):
                    if i + j < len(zone_data):
                        byte_val = zone_data[i + j]
                        hex_bytes.append(f"{byte_val:02X}")
                        # ASCII (solo caracteres imprimibles)
                        if 32 <= byte_val <= 126:
                            ascii_repr.append(chr(byte_val))
                        else:
                            ascii_repr.append('.')
                    else:
                        hex_bytes.append("  ")
                        ascii_repr.append(" ")
                
                # Formato: ADDR  | BYTES... | ASCII | DESENSAMBLADO
                hex_str = " ".join(hex_bytes)
                ascii_str = "".join(ascii_repr)
                
                # Intentar desensamblado básico (solo el primer byte de la línea)
                if i < len(zone_data):
                    opcode = zone_data[i]
                    mnemonic = GB_OPCODES.get(opcode, "???")
                    
                    # Determinar longitud de la instrucción
                    inst_len = 1
                    if mnemonic and mnemonic != "???":
                        if "d16" in mnemonic or "a16" in mnemonic:
                            inst_len = 3
                        elif "d8" in mnemonic or "r8" in mnemonic or "a8" in mnemonic:
                            inst_len = 2
                        elif mnemonic == "PREFIX CB":
                            inst_len = 2  # CB + 1 byte más
                    
                    # Mostrar la línea
                    print(f"{addr_str} | {hex_str} | {ascii_str} | {mnemonic or '???'}")
                    
                    # Si la instrucción tiene operandos, mostrar información adicional
                    if inst_len > 1 and i + inst_len <= len(zone_data):
                        if inst_len == 2:
                            operand = zone_data[i + 1]
                            if "r8" in mnemonic:
                                # r8 es signed
                                signed_val = operand if operand < 128 else operand - 256
                                target = current_addr + 2 + signed_val
                                print(f"      └─ Operando: {operand:02X} (r8 = {signed_val:+d}, target = {target:04X})")
                            elif "a8" in mnemonic:
                                print(f"      └─ Operando: {operand:02X} (a8 = {operand:02X})")
                            else:
                                print(f"      └─ Operando: {operand:02X}")
                        elif inst_len == 3:
                            low = zone_data[i + 1]
                            high = zone_data[i + 2]
                            addr = (high << 8) | low
                            print(f"      └─ Operando: {low:02X} {high:02X} (a16/d16 = {addr:04X})")
                else:
                    print(f"{addr_str} | {hex_str} | {ascii_str} |")
                
                i += bytes_per_line
                current_addr += bytes_per_line
            
            print(f"\n{'='*80}")
            print(f"✅ Volcado completado: {len(zone_data)} bytes")
            print(f"{'='*80}\n")
            
            return True
            
    except Exception as e:
        print(f"❌ Error al leer la ROM: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal."""
    # Argumentos por defecto
    default_rom = "roms/tetris.gb"
    default_start = 0x2AE0
    default_end = 0x2B20
    
    if len(sys.argv) >= 2:
        rom_path = sys.argv[1]
    else:
        rom_path = default_rom
    
    if len(sys.argv) >= 3:
        start_addr = parse_address(sys.argv[2])
    else:
        start_addr = default_start
    
    if len(sys.argv) >= 4:
        end_addr = parse_address(sys.argv[3])
    else:
        end_addr = default_end
    
    if start_addr >= end_addr:
        print("❌ Error: La dirección de inicio debe ser menor que la de fin")
        return 1
    
    success = dump_rom_zone(rom_path, start_addr, end_addr)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

