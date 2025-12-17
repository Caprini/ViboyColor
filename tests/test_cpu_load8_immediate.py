"""
Tests unitarios para cargas inmediatas de 8 bits:
- LD r, d8   (cargas en registros)
- LD (HL), d8 (carga inmediata en memoria indirecta)

Estas instrucciones son fundamentales para inicializar contadores,
constantes y buffers de memoria en juegos como Tetris DX.
"""

import pytest

from src.cpu.core import CPU
from src.memory.mmu import MMU


@pytest.mark.parametrize(
    "opcode, setter_name, getter_name, value",
    [
        (0x0E, "set_c", "get_c", 0x12),  # LD C, d8
        (0x16, "set_d", "get_d", 0x34),  # LD D, d8
        (0x1E, "set_e", "get_e", 0x56),  # LD E, d8
        (0x26, "set_h", "get_h", 0x78),  # LD H, d8
        (0x2E, "set_l", "get_l", 0x9A),  # LD L, d8
    ],
)
def test_ld_registers_immediate(opcode: int, setter_name: str, getter_name: str, value: int) -> None:
    """
    Verifica que las instrucciones LD r, d8 cargan correctamente un valor inmediato
    en los registros C, D, E, H y L.

    Patrón de prueba:
    - Colocar PC en 0x0100
    - Escribir opcode seguido del operando inmediato en memoria
    - Ejecutar cpu.step()
    - Verificar que el registro de destino contiene el valor inmediato
    - Verificar que PC avanza 2 bytes (opcode + operando)
    - Verificar que consume 2 M-Cycles (fetch opcode + fetch operando)
    """
    mmu = MMU()
    cpu = CPU(mmu)

    # Establecer PC inicial
    cpu.registers.set_pc(0x0100)

    # Por claridad, inicializamos el registro destino a 0x00
    setter = getattr(cpu.registers, setter_name)
    getter = getattr(cpu.registers, getter_name)
    setter(0x00)

    # Escribir opcode y operando inmediato en memoria
    mmu.write_byte(0x0100, opcode)
    mmu.write_byte(0x0101, value)

    # Ejecutar instrucción
    cycles = cpu.step()

    # Verificar que el registro contiene el valor inmediato
    assert getter() == value & 0xFF, f"Registro destino debe contener 0x{value:02X}"

    # Verificar que PC avanzó 2 bytes
    assert cpu.registers.get_pc() == 0x0102, "PC debe avanzar 2 bytes (opcode + inmediato)"

    # Verificar que consume 2 M-Cycles
    assert cycles == 2, "LD r, d8 debe consumir 2 M-Cycles"


def test_ld_hl_ptr_immediate() -> None:
    """
    Verifica la instrucción LD (HL), d8 (0x36).

    Patrón de prueba:
    - Colocar PC en 0x0100
    - Establecer HL = 0xC000
    - Escribir opcode 0x36 seguido del operando inmediato 0x99 en memoria
    - Ejecutar cpu.step()
    - Verificar que MMU[0xC000] == 0x99
    - Verificar que HL no cambia
    - Verificar que PC avanza 2 bytes
    - Verificar que consume 3 M-Cycles (fetch opcode + fetch operando + write memoria)
    """
    mmu = MMU()
    cpu = CPU(mmu)

    # Establecer PC inicial
    cpu.registers.set_pc(0x0100)

    # Establecer HL = 0xC000
    cpu.registers.set_hl(0xC000)

    # Escribir opcode y operando inmediato en memoria
    mmu.write_byte(0x0100, 0x36)  # LD (HL), d8
    mmu.write_byte(0x0101, 0x99)  # Operando inmediato

    # Ejecutar instrucción
    cycles = cpu.step()

    # Verificar que se escribió el valor en memoria
    assert mmu.read_byte(0xC000) == 0x99, "Memoria en (HL) debe contener el valor inmediato 0x99"

    # Verificar que HL no cambió
    assert cpu.registers.get_hl() == 0xC000, "HL no debe cambiar en LD (HL), d8"

    # Verificar que PC avanzó 2 bytes
    assert cpu.registers.get_pc() == 0x0102, "PC debe avanzar 2 bytes (opcode + inmediato)"

    # Verificar que consume 3 M-Cycles
    assert cycles == 3, "LD (HL), d8 debe consumir 3 M-Cycles"


