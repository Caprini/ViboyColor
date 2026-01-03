#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROM Info Tool (Step 0450)

Lee header ROM y detecta tipo MBC, CGB flag, ROM/RAM size, y soporte por el emulador.

Uso:
    python3 tools/rom_info_0450.py <ROM_PATH> [ROM_PATH...]

Referencias:
    - Pan Docs: Cartridge Header (0x0100-0x014F)
    - Step 0450: Triage Real "No Veo Gráficos" - MBC Requerido + VRAM Raw
"""

import sys
from pathlib import Path

# Tabla de tipos de cartucho (0x0147)
CARTRIDGE_TYPES = {
    0x00: ("ROM ONLY", "None", True),
    0x01: ("MBC1", "MBC1", True),
    0x02: ("MBC1+RAM", "MBC1", True),
    0x03: ("MBC1+RAM+BATTERY", "MBC1", True),
    0x05: ("MBC2", "MBC2", False),  # No implementado
    0x06: ("MBC2+BATTERY", "MBC2", False),
    0x08: ("ROM+RAM", "None", False),
    0x09: ("ROM+RAM+BATTERY", "None", False),
    0x0B: ("MMM01", "MMM01", False),
    0x0C: ("MMM01+RAM", "MMM01", False),
    0x0D: ("MMM01+RAM+BATTERY", "MMM01", False),
    0x0F: ("MBC3+TIMER+BATTERY", "MBC3", True),  # RTC
    0x10: ("MBC3+TIMER+RAM+BATTERY", "MBC3", True),
    0x11: ("MBC3", "MBC3", True),
    0x12: ("MBC3+RAM", "MBC3", True),
    0x13: ("MBC3+RAM+BATTERY", "MBC3", True),
    0x19: ("MBC5", "MBC5", True),
    0x1A: ("MBC5+RAM", "MBC5", True),
    0x1B: ("MBC5+RAM+BATTERY", "MBC5", True),
    0x1C: ("MBC5+RUMBLE", "MBC5", True),
    0x1D: ("MBC5+RUMBLE+RAM", "MBC5", True),
    0x1E: ("MBC5+RUMBLE+RAM+BATTERY", "MBC5", True),
    0x20: ("MBC6", "MBC6", False),
    0x22: ("MBC7+SENSOR+RUMBLE+RAM+BATTERY", "MBC7", False),
    0xFC: ("POCKET CAMERA", "CAMERA", False),
    0xFD: ("BANDAI TAMA5", "TAMA5", False),
    0xFE: ("HuC3", "HuC3", False),
    0xFF: ("HuC1+RAM+BATTERY", "HuC1", False),
}

# Tamaños ROM (0x0148)
ROM_SIZES = {
    0x00: ("32KB", 2),
    0x01: ("64KB", 4),
    0x02: ("128KB", 8),
    0x03: ("256KB", 16),
    0x04: ("512KB", 32),
    0x05: ("1MB", 64),
    0x06: ("2MB", 128),
    0x07: ("4MB", 256),
    0x08: ("8MB", 512),
}

# Tamaños RAM (0x0149)
RAM_SIZES = {
    0x00: ("None", 0),
    0x01: ("2KB", 1),
    0x02: ("8KB", 1),
    0x03: ("32KB", 4),
    0x04: ("128KB", 16),
    0x05: ("64KB", 8),
}

# MBCs soportados por el emulador (actualizar según implementación)
SUPPORTED_MBCS = {"None", "MBC1", "MBC3", "MBC5"}


def read_rom_header(rom_path: Path) -> dict:
    """Lee header ROM y extrae información."""
    with open(rom_path, 'rb') as f:
        rom_data = f.read(0x150)  # Leer hasta end of header
    
    if len(rom_data) < 0x150:
        raise ValueError(f"ROM demasiado pequeña: {len(rom_data)} bytes")
    
    # Title (0x0134-0x0143)
    title_bytes = rom_data[0x0134:0x0143]
    title = title_bytes.split(b'\x00')[0].decode('ascii', errors='replace').strip()
    
    # CGB Flag (0x0143)
    cgb_flag = rom_data[0x0143]
    cgb_mode = "CGB" if cgb_flag == 0x80 or cgb_flag == 0xC0 else "DMG"
    
    # Cartridge Type (0x0147)
    cart_type = rom_data[0x0147]
    cart_info = CARTRIDGE_TYPES.get(cart_type, (f"UNKNOWN(0x{cart_type:02X})", "Unknown", False))
    cart_name = cart_info[0]
    mbc_name = cart_info[1]
    is_common = cart_info[2]
    
    # ROM Size (0x0148)
    rom_size_code = rom_data[0x0148]
    rom_size_info = ROM_SIZES.get(rom_size_code, (f"UNKNOWN(0x{rom_size_code:02X})", 0))
    
    # RAM Size (0x0149)
    ram_size_code = rom_data[0x0149]
    ram_size_info = RAM_SIZES.get(ram_size_code, (f"UNKNOWN(0x{ram_size_code:02X})", 0))
    
    # Soporte
    supported = mbc_name in SUPPORTED_MBCS or (mbc_name == "None" and cart_type == 0x00)
    
    return {
        'title': title,
        'cart_type': cart_type,
        'cart_name': cart_name,
        'mbc_name': mbc_name,
        'cgb_flag': cgb_flag,
        'cgb_mode': cgb_mode,
        'rom_size': rom_size_info[0],
        'ram_size': ram_size_info[0],
        'supported': supported,
        'is_common': is_common,
    }


def main():
    """Función principal."""
    if len(sys.argv) < 2:
        print("Uso: python3 tools/rom_info_0450.py <ROM_PATH> [ROM_PATH...]")
        sys.exit(1)
    
    print("ROM | cart_type(hex) | MBC name | CGB flag | soportado")
    print("----|----------------|----------|----------|----------")
    
    for rom_path_str in sys.argv[1:]:
        rom_path = Path(rom_path_str)
        if not rom_path.exists():
            print(f"{rom_path.name} | ERROR: No encontrada")
            continue
        
        try:
            info = read_rom_header(rom_path)
            supported_str = "sí" if info['supported'] else "no"
            print(f"{rom_path.name} | 0x{info['cart_type']:02X} | {info['mbc_name']} | 0x{info['cgb_flag']:02X}({info['cgb_mode']}) | {supported_str}")
        except Exception as e:
            print(f"{rom_path.name} | ERROR: {e}")


if __name__ == "__main__":
    main()

