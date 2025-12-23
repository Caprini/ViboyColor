#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis detallado del flujo de código (Step 0250)
"""

import sys
import io

# Configurar encoding UTF-8 para Windows
if sys.platform == "win32":
    if sys.stdout is not None and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Bytes del rango 0x2B05 - 0x2B25
code = bytes([
    0x21, 0xAC, 0x2B,  # 2B05: LD HL, 0x2BAC
    0x07,               # 2B08: RLCA
    0x5F,               # 2B09: LD E,A
    0x16, 0x00,         # 2B0A: LD D, 0x00
    0x19,               # 2B0C: ADD HL,DE
    0x5E,               # 2B0D: LD E,(HL)
    0x23,               # 2B0E: INC HL
    0x56,               # 2B0F: LD D,(HL)
    0x1A,               # 2B10: LD A,(DE)
    0x6F,               # 2B11: LD L,A
    0x13,               # 2B12: INC DE
    0x1A,               # 2B13: LD A,(DE)
    0x67,               # 2B14: LD H,A
    0x13,               # 2B15: INC DE
    0x1A,               # 2B16: LD A,(DE)
    0xE0, 0x90,         # 2B17: LDH (0x90),A
    0x13,               # 2B19: INC DE
    0x1A,               # 2B1A: LD A,(DE)
    0xE0, 0x91,         # 2B1B: LDH (0x91),A
    0x5E,               # 2B1D: LD E,(HL)
    0x23,               # 2B1E: INC HL
    0x56,               # 2B1F: LD D,(HL)
    0x23,               # 2B20: INC HL  <-- INICIO DEL BUCLE
])

print("="*80)
print("🔍 ANÁLISIS DEL FLUJO DE CÓDIGO (0x2B05 - 0x2B20)")
print("="*80)
print()

addr = 0x2B05
i = 0

while i < len(code):
    opcode = code[i]
    addr_str = f"{addr:04X}"
    
    if opcode == 0x21:  # LD HL,d16
        low = code[i+1]
        high = code[i+2]
        val = (high << 8) | low
        print(f"{addr_str}: LD HL, 0x{val:04X}  ; HL = 0x{val:04X}")
        i += 3
        addr += 3
    elif opcode == 0x07:  # RLCA
        print(f"{addr_str}: RLCA  ; A = (A << 1) | (A >> 7)")
        i += 1
        addr += 1
    elif opcode == 0x5F:  # LD E,A
        print(f"{addr_str}: LD E,A  ; E = A")
        i += 1
        addr += 1
    elif opcode == 0x16:  # LD D,d8
        val = code[i+1]
        print(f"{addr_str}: LD D, 0x{val:02X}  ; D = 0x{val:02X}")
        i += 2
        addr += 2
    elif opcode == 0x19:  # ADD HL,DE
        print(f"{addr_str}: ADD HL,DE  ; HL = HL + DE")
        i += 1
        addr += 1
    elif opcode == 0x5E:  # LD E,(HL)
        print(f"{addr_str}: LD E,(HL)  ; E = [HL]")
        i += 1
        addr += 1
    elif opcode == 0x23:  # INC HL
        print(f"{addr_str}: INC HL  ; HL++")
        i += 1
        addr += 1
    elif opcode == 0x56:  # LD D,(HL)
        print(f"{addr_str}: LD D,(HL)  ; D = [HL]")
        i += 1
        addr += 1
    elif opcode == 0x1A:  # LD A,(DE)
        print(f"{addr_str}: LD A,(DE)  ; A = [DE]")
        i += 1
        addr += 1
    elif opcode == 0x6F:  # LD L,A
        print(f"{addr_str}: LD L,A  ; L = A")
        i += 1
        addr += 1
    elif opcode == 0x13:  # INC DE
        print(f"{addr_str}: INC DE  ; DE++")
        i += 1
        addr += 1
    elif opcode == 0x67:  # LD H,A
        print(f"{addr_str}: LD H,A  ; H = A")
        i += 1
        addr += 1
    elif opcode == 0xE0:  # LDH (a8),A
        val = code[i+1]
        print(f"{addr_str}: LDH (0x{val:02X}),A  ; [0xFF{val:02X}] = A")
        i += 2
        addr += 2
    else:
        print(f"{addr_str}: ??? (0x{opcode:02X})")
        i += 1
        addr += 1

print()
print("="*80)
print("📊 RESUMEN DEL FLUJO:")
print("="*80)
print()
print("1. 2B05: LD HL, 0x2BAC  → HL apunta a tabla de punteros en ROM")
print("2. 2B08: RLCA           → Rota A (índice?)")
print("3. 2B09: LD E,A / 2B0A: LD D,0x00  → DE = A (como offset)")
print("4. 2B0C: ADD HL,DE      → HL = 0x2BAC + A (apunta a entrada de tabla)")
print("5. 2B0D-2B0F: Lee puntero desde [HL] → DE = [HL] (dirección en memoria)")
print("6. 2B10-2B14: Lee datos desde [DE] → HL = [DE] (nueva dirección)")
print("7. 2B16-2B1B: Escribe datos a registros de hardware (0xFF90, 0xFF91)")
print("8. 2B1D-2B1F: Lee OTRO puntero desde [HL] → DE = [HL+1]")
print("9. 2B20: INC HL  → ¡AQUÍ EMPIEZA EL BUCLE!")
print()
print("🔑 CONCLUSIÓN:")
print("   El bucle en 0x2B20 busca 0xFD en la memoria apuntada por HL.")
print("   HL se inicializa desde una tabla de punteros en 0x2BAC.")
print("   El valor final de HL depende de:")
print("   - El valor de A (índice en la tabla)")
print("   - Los datos leídos desde la dirección apuntada por la tabla")
print("   - Si esos datos no están inicializados (son 0x00), HL será incorrecto")
print()

