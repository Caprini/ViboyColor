"""
Tests para MBC1 (Memory Bank Controller 1)

Valida el cambio de bancos ROM para cartuchos mayores a 32KB.
El MBC1 permite cambiar de banco ROM mediante escrituras en el rango 0x2000-0x3FFF.

Fuente: Pan Docs - MBC1 Memory Bank Controller
"""

import tempfile
from pathlib import Path

import pytest

from src.memory.cartridge import Cartridge
from src.memory.mmu import MMU


def test_mbc1_bank0_fixed() -> None:
    """
    Test: El banco 0 (0x0000-0x3FFF) siempre apunta a los primeros 16KB.
    
    Valida que el banco 0 es fijo y no cambia independientemente del banco seleccionado.
    """
    # Crear ROM dummy de 64KB (4 bancos de 16KB)
    rom_data = bytearray(64 * 1024)
    
    # Escribir "AAAA" en el banco 0 (primeros 16KB)
    for i in range(0, 0x4000):
        rom_data[i] = 0xAA
    
    # Escribir "BBBB" en el banco 1 (segundo bloque de 16KB)
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0xBB
    
    # Crear archivo temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        
        # Leer del banco 0 (debe ser 0xAA independientemente del banco seleccionado)
        assert cartridge.read_byte(0x0000) == 0xAA, "Banco 0 debe contener 0xAA"
        assert cartridge.read_byte(0x2000) == 0xAA, "Banco 0 debe contener 0xAA"
        assert cartridge.read_byte(0x3FFF) == 0xAA, "Banco 0 debe contener 0xAA"
        
        # Cambiar a banco 2 y verificar que banco 0 sigue siendo 0xAA
        cartridge.write_byte(0x2000, 2)
        assert cartridge.read_byte(0x0000) == 0xAA, "Banco 0 debe seguir siendo 0xAA"
        
    finally:
        Path(temp_path).unlink()


def test_mbc1_default_bank1() -> None:
    """
    Test: Por defecto, la zona switchable (0x4000-0x7FFF) apunta al banco 1.
    
    Valida que el banco inicial es 1 (no puede ser 0 en zona switchable).
    """
    # Crear ROM dummy de 64KB
    rom_data = bytearray(64 * 1024)
    
    # Escribir "AAAA" en banco 0
    for i in range(0, 0x4000):
        rom_data[i] = 0xAA
    
    # Escribir "BBBB" en banco 1
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0xBB
    
    # Escribir "CCCC" en banco 2
    for i in range(0x8000, 0xC000):
        rom_data[i] = 0xCC
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        
        # Leer de zona switchable (debe ser banco 1 por defecto)
        assert cartridge.read_byte(0x4000) == 0xBB, "Zona switchable debe apuntar a banco 1 por defecto"
        assert cartridge.read_byte(0x5000) == 0xBB, "Zona switchable debe apuntar a banco 1 por defecto"
        assert cartridge.read_byte(0x7FFF) == 0xBB, "Zona switchable debe apuntar a banco 1 por defecto"
        
    finally:
        Path(temp_path).unlink()


def test_mbc1_bank_switching() -> None:
    """
    Test: Cambiar de banco escribiendo en 0x2000-0x3FFF.
    
    Valida que escribir un valor N en 0x2000-0x3FFF cambia el banco a N
    (con el quirk de que 0 se convierte en 1).
    """
    # Crear ROM dummy de 64KB
    rom_data = bytearray(64 * 1024)
    
    # Escribir diferentes valores en cada banco
    for i in range(0, 0x4000):
        rom_data[i] = 0x00  # Banco 0
    
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0x11  # Banco 1
    
    for i in range(0x8000, 0xC000):
        rom_data[i] = 0x22  # Banco 2
    
    for i in range(0xC000, 0x10000):
        rom_data[i] = 0x33  # Banco 3
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        
        # Cambiar a banco 2
        cartridge.write_byte(0x2000, 2)
        assert cartridge.read_byte(0x4000) == 0x22, "Debe leer del banco 2"
        assert cartridge.read_byte(0x5000) == 0x22, "Debe leer del banco 2"
        
        # Cambiar a banco 3
        cartridge.write_byte(0x2000, 3)
        assert cartridge.read_byte(0x4000) == 0x33, "Debe leer del banco 3"
        assert cartridge.read_byte(0x5000) == 0x33, "Debe leer del banco 3"
        
        # Cambiar de vuelta a banco 1
        cartridge.write_byte(0x2000, 1)
        assert cartridge.read_byte(0x4000) == 0x11, "Debe leer del banco 1"
        
    finally:
        Path(temp_path).unlink()


def test_mbc1_bank0_quirk() -> None:
    """
    Test: Quirk de MBC1 - escribir 0 en 0x2000 selecciona banco 1.
    
    Valida el comportamiento especial: si el juego intenta seleccionar banco 0,
    el MBC1 le da banco 1 (no se puede poner banco 0 en zona switchable).
    
    Fuente: Pan Docs - MBC1: "Writing 0x00 to 0x2000-0x3FFF selects ROM bank 1"
    """
    # Crear ROM dummy de 64KB
    rom_data = bytearray(64 * 1024)
    
    # Escribir "AAAA" en banco 0
    for i in range(0, 0x4000):
        rom_data[i] = 0xAA
    
    # Escribir "BBBB" en banco 1
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0xBB
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        
        # Intentar seleccionar banco 0 (debe convertirse en banco 1)
        cartridge.write_byte(0x2000, 0)
        
        # Verificar que lee del banco 1 (no del banco 0)
        assert cartridge.read_byte(0x4000) == 0xBB, "Escribir 0 debe seleccionar banco 1"
        assert cartridge.read_byte(0x5000) == 0xBB, "Escribir 0 debe seleccionar banco 1"
        
        # Verificar que el banco 0 sigue siendo accesible en su zona fija
        assert cartridge.read_byte(0x0000) == 0xAA, "Banco 0 debe seguir siendo accesible en 0x0000-0x3FFF"
        assert cartridge.read_byte(0x2000) == 0xAA, "Banco 0 debe seguir siendo accesible en 0x0000-0x3FFF"
        
    finally:
        Path(temp_path).unlink()


def test_mbc1_bank_bits_masking() -> None:
    """
    Test: Solo los 5 bits bajos (0x1F) se usan para seleccionar banco.
    
    Valida que escribir valores mayores a 0x1F se enmascaran correctamente.
    """
    # Crear ROM dummy de 64KB
    rom_data = bytearray(64 * 1024)
    
    # Escribir diferentes valores en cada banco
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0x11  # Banco 1
    
    for i in range(0x8000, 0xC000):
        rom_data[i] = 0x22  # Banco 2
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        
        # Escribir 0x22 (banco 2) con bits extra
        cartridge.write_byte(0x2000, 0x22)  # 0x22 & 0x1F = 0x02 (banco 2)
        assert cartridge.read_byte(0x4000) == 0x22, "Debe seleccionar banco 2"
        
        # Escribir 0x3F (todos los bits bajos, pero bits altos también)
        # 0x3F & 0x1F = 0x1F (banco 31, pero solo tenemos hasta banco 3)
        # En este caso, intentará leer fuera de rango y devolverá 0xFF
        cartridge.write_byte(0x2000, 0x3F)
        # Como solo tenemos 64KB (4 bancos), leerá 0xFF
        assert cartridge.read_byte(0x4000) == 0xFF, "Debe devolver 0xFF si está fuera de rango"
        
    finally:
        Path(temp_path).unlink()


def test_mbc1_via_mmu() -> None:
    """
    Test: Cambio de banco a través de MMU (integración completa).
    
    Valida que la MMU permite escrituras en zona ROM que se envían al cartucho.
    """
    # Crear ROM dummy de 64KB
    rom_data = bytearray(64 * 1024)
    
    # Escribir diferentes valores en cada banco
    for i in range(0x4000, 0x8000):
        rom_data[i] = 0x11  # Banco 1
    
    for i in range(0x8000, 0xC000):
        rom_data[i] = 0x22  # Banco 2
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gb") as f:
        f.write(rom_data)
        temp_path = f.name
    
    try:
        cartridge = Cartridge(temp_path)
        mmu = MMU(cartridge)
        
        # Leer banco por defecto (debe ser banco 1)
        assert mmu.read_byte(0x4000) == 0x11, "Debe leer banco 1 por defecto"
        
        # Cambiar banco escribiendo a través de MMU
        mmu.write_byte(0x2000, 2)
        
        # Verificar que cambió de banco
        assert mmu.read_byte(0x4000) == 0x22, "Debe leer banco 2 después del cambio"
        
    finally:
        Path(temp_path).unlink()

