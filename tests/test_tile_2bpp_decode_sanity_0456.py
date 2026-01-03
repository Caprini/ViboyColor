"""
Test sanity: Decodificación 2bpp (Step 0456)

Verifica que el decode 2bpp funciona correctamente y qué patrones
generan índices de color constantes vs variados.
"""

import pytest


def decode_2bpp_line(byte_low: int, byte_high: int) -> list[int]:
    """
    Decodifica una línea de tile 2bpp a índices de color (0..3).
    
    Args:
        byte_low: Byte bajo (bit plano 0)
        byte_high: Byte alto (bit plano 1)
    
    Returns:
        Lista de 8 índices de color (0..3)
    """
    color_indices = []
    for i in range(8):
        bit_pos = 7 - i  # Bit position (MSB first)
        bit_low = (byte_low >> bit_pos) & 0x01
        bit_high = (byte_high >> bit_pos) & 0x01
        color_idx = bit_low | (bit_high << 1)
        color_indices.append(color_idx)
    return color_indices


def test_2bpp_decode_00_ff():
    """Verifica qué índices genera el patrón 0x00/0xFF."""
    # Patrón usado en test original
    byte_low = 0x00
    byte_high = 0xFF
    
    indices = decode_2bpp_line(byte_low, byte_high)
    
    print(f"Patrón 0x00/0xFF genera índices: {indices}")
    
    # Verificar si es constante o variado
    unique_indices = set(indices)
    print(f"Índices únicos: {unique_indices}")
    
    if len(unique_indices) == 1:
        print(f"⚠️ ADVERTENCIA: Patrón 0x00/0xFF genera índice constante = {unique_indices.pop()}")
        print("   Este patrón NO es adecuado para tests de paleta que requieren 0/1/2/3")
    else:
        print(f"✅ Patrón 0x00/0xFF genera {len(unique_indices)} índices únicos")
    
    # Assert: permitir constante (no es un error del decode, es el patrón)
    assert len(indices) == 8, "Debe generar 8 índices"


def test_2bpp_decode_55_33():
    """Verifica qué índices genera el patrón 0x55/0x33."""
    # Patrón que según el debug genera 0/1/2/3
    byte_low = 0x55  # 0b01010101
    byte_high = 0x33  # 0b00110011
    
    indices = decode_2bpp_line(byte_low, byte_high)
    
    print(f"Patrón 0x55/0x33 genera índices: {indices}")
    
    # Verificar que contiene 0/1/2/3
    unique_indices = set(indices)
    print(f"Índices únicos: {unique_indices}")
    
    # Assert: debe contener {0, 1, 2, 3}
    assert unique_indices == {0, 1, 2, 3}, \
        f"Patrón 0x55/0x33 debe generar índices {{0,1,2,3}}, obtuvo {unique_indices}"
    
    print("✅ Patrón 0x55/0x33 genera los 4 índices (adecuado para tests de paleta)")


def test_2bpp_decode_distribution():
    """Verifica distribución de índices para varios patrones comunes."""
    test_cases = [
        (0x00, 0x00, "todo 0"),
        (0xFF, 0xFF, "todo 3"),
        (0x00, 0xFF, "constante (probablemente 2)"),
        (0x55, 0x33, "variado 0/1/2/3"),
        (0xAA, 0xCC, "otro patrón variado"),
    ]
    
    for byte_low, byte_high, desc in test_cases:
        indices = decode_2bpp_line(byte_low, byte_high)
        unique_indices = set(indices)
        print(f"Patrón 0x{byte_low:02X}/0x{byte_high:02X} ({desc}): "
              f"índices={indices}, únicos={unique_indices}")


if __name__ == "__main__":
    test_2bpp_decode_00_ff()
    test_2bpp_decode_55_33()
    test_2bpp_decode_distribution()
    print("✅ Todos los tests de decode 2bpp pasaron")

