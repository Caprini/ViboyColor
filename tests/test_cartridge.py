"""
Tests para la clase Cartridge

Valida la carga de ROMs y el parsing del Header.
"""

import tempfile
from pathlib import Path

import pytest

from src.memory.cartridge import Cartridge


def test_cartridge_loads_rom() -> None:
    """Test básico: carga una ROM dummy y verifica que se lee correctamente."""
    # Crear un archivo ROM dummy de 32KB
    rom_data = bytearray(32 * 1024)
    
    # Escribir algunos bytes conocidos
    rom_data[0x0100] = 0xC3  # JP nn (opcode)
    rom_data[0x0101] = 0x00
    rom_data[0x0102] = 0xC0
    
    # Escribir título en el header (0x0134 - 0x0143)
    title = b"TEST ROM"
    for i, byte in enumerate(title):
        rom_data[0x0134 + i] = byte
    
    # Escribir tipo de cartucho (0x0147): 0x00 = ROM ONLY
    rom_data[0x0147] = 0x00
    
    # Escribir tamaño de ROM (0x0148): 0x00 = 32KB
    rom_data[0x0148] = 0x00
    
    # Escribir tamaño de RAM (0x0149): 0x00 = No RAM
    rom_data[0x0149] = 0x00
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        # Cargar cartucho
        cartridge = Cartridge(temp_path)
        
        # Verificar que se puede leer
        assert cartridge.read_byte(0x0100) == 0xC3
        assert cartridge.read_byte(0x0101) == 0x00
        assert cartridge.read_byte(0x0102) == 0xC0
        
        # Verificar tamaño
        assert cartridge.get_rom_size() == 32 * 1024
        
    finally:
        # Limpiar archivo temporal
        Path(temp_path).unlink()


def test_cartridge_parses_header() -> None:
    """Test: verifica que el Header se parsea correctamente."""
    # Crear un archivo ROM dummy con header válido
    rom_data = bytearray(32 * 1024)
    
    # Escribir título: "TETRIS"
    title = b"TETRIS"
    for i, byte in enumerate(title):
        rom_data[0x0134 + i] = byte
    rom_data[0x0134 + len(title)] = 0x00  # Terminador
    
    # Tipo de cartucho: 0x00 = ROM ONLY
    rom_data[0x0147] = 0x00
    
    # Tamaño de ROM: 0x00 = 32KB
    rom_data[0x0148] = 0x00
    
    # Tamaño de RAM: 0x00 = No RAM
    rom_data[0x0149] = 0x00
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        # Cargar cartucho
        cartridge = Cartridge(temp_path)
        
        # Obtener información del header
        header_info = cartridge.get_header_info()
        
        # Verificar que el título se parseó correctamente
        assert header_info["title"] == "TETRIS"
        assert header_info["cartridge_type"] == "0x00"
        assert header_info["rom_size"] == 32
        assert header_info["ram_size"] == 0
        
    finally:
        # Limpiar archivo temporal
        Path(temp_path).unlink()


def test_cartridge_reads_out_of_bounds() -> None:
    """Test: verifica que leer fuera de rango devuelve 0xFF."""
    # Crear un archivo ROM pequeño (solo 16KB)
    rom_data = bytearray(16 * 1024)
    
    # Escribir header mínimo
    rom_data[0x0134] = ord("T")
    rom_data[0x0135] = 0x00
    rom_data[0x0147] = 0x00
    rom_data[0x0148] = 0x00
    rom_data[0x0149] = 0x00
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        # Cargar cartucho
        cartridge = Cartridge(temp_path)
        
        # Leer dentro del rango: debe funcionar
        assert cartridge.read_byte(0x0100) == rom_data[0x0100]
        
        # Leer fuera del rango: debe devolver 0xFF
        assert cartridge.read_byte(0x8000) == 0xFF
        assert cartridge.read_byte(0xFFFF) == 0xFF
        
    finally:
        # Limpiar archivo temporal
        Path(temp_path).unlink()


def test_cartridge_handles_missing_file() -> None:
    """Test: verifica que lanza FileNotFoundError si el archivo no existe."""
    with pytest.raises(FileNotFoundError):
        Cartridge("/ruta/inexistente/rom.gb")


def test_cartridge_handles_too_small_rom() -> None:
    """Test: verifica que lanza ValueError si la ROM es demasiado pequeña."""
    # Crear un archivo muy pequeño (menos de 0x014F bytes)
    rom_data = bytearray(100)  # Solo 100 bytes
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        # Intentar cargar cartucho: debe lanzar ValueError
        with pytest.raises(ValueError, match="demasiado pequeña"):
            Cartridge(temp_path)
    finally:
        # Limpiar archivo temporal
        Path(temp_path).unlink()


def test_cartridge_parses_rom_size_codes() -> None:
    """Test: verifica que se parsean correctamente diferentes códigos de tamaño de ROM."""
    # Probar diferentes códigos de tamaño según Pan Docs
    size_codes = {
        0x00: 32,   # 32KB
        0x01: 64,   # 64KB
        0x02: 128,  # 128KB
        0x03: 256,  # 256KB
    }
    
    for code, expected_kb in size_codes.items():
        # Crear ROM con el código de tamaño
        rom_data = bytearray(32 * 1024)  # Mínimo para el header
        
        # Header básico
        rom_data[0x0134] = ord("T")
        rom_data[0x0135] = 0x00
        rom_data[0x0147] = 0x00
        rom_data[0x0148] = code
        rom_data[0x0149] = 0x00
        
        # Crear archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
            f.write(rom_data)
            temp_path = f.name
        
        try:
            cartridge = Cartridge(temp_path)
            header_info = cartridge.get_header_info()
            
            # Verificar que el tamaño se parseó correctamente
            assert header_info["rom_size"] == expected_kb, (
                f"Código 0x{code:02X} debería ser {expected_kb}KB, "
                f"pero se obtuvo {header_info['rom_size']}KB"
            )
        finally:
            Path(temp_path).unlink()

