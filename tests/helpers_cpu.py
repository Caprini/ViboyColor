"""
Helpers para tests de CPU.

Este módulo proporciona utilidades para configurar y ejecutar tests
de CPU de forma más realista, ejecutando código desde WRAM en lugar
de intentar escribir en ROM.
"""

from typing import List

# Constante: dirección base para ejecutar programas de test
# Usamos WRAM (0xC000-0xDFFF) porque ROM (0x0000-0x7FFF) no es escribible
TEST_EXEC_BASE = 0xC000


def load_program(mmu, regs, program_bytes: List[int], start_addr: int = TEST_EXEC_BASE) -> None:
    """
    Carga un programa de test en memoria y configura el PC.
    
    Args:
        mmu: Instancia de PyMMU donde escribir el programa
        regs: Instancia de PyRegisters donde configurar el PC
        program_bytes: Lista de bytes (opcodes e inmediatos) del programa
        start_addr: Dirección de inicio (por defecto TEST_EXEC_BASE = 0xC000)
    
    Concepto Hardware:
    -------------------
    En Game Boy, el mapa de memoria es:
    - 0x0000-0x7FFF: ROM (Read Only Memory) - No se puede escribir
    - 0x8000-0x9FFF: VRAM
    - 0xA000-0xBFFF: External RAM (Cartridge)
    - 0xC000-0xDFFF: WRAM (Work RAM) - RAM escribible interna
    - 0xE000-0xFDFF: Echo RAM (espejo de WRAM)
    - 0xFE00-0xFE9F: OAM (Sprite Attribute Table)
    - 0xFF00-0xFF7F: I/O Registers
    - 0xFF80-0xFFFE: HRAM (High RAM)
    - 0xFFFF: IE Register
    
    Para tests unitarios, necesitamos escribir opcodes de prueba en memoria.
    Como ROM no es escribible, ejecutamos desde WRAM (0xC000+).
    """
    # Escribir cada byte del programa
    for i, byte_val in enumerate(program_bytes):
        addr = start_addr + i
        mmu.write(addr, byte_val)
    
    # Configurar PC al inicio del programa
    regs.pc = start_addr
    
    # Verificación: leer de vuelta para confirmar escritura
    for i, byte_val in enumerate(program_bytes):
        addr = start_addr + i
        read_back = mmu.read(addr)
        if read_back != byte_val:
            raise AssertionError(
                f"load_program: Verificación falló en 0x{addr:04X}: "
                f"esperado 0x{byte_val:02X}, leído 0x{read_back:02X}"
            )

