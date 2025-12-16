"""
CPU (Central Processing Unit) - Procesador LR35902

La CPU de la Game Boy ejecuta instrucciones en un ciclo continuo:
1. Fetch: Lee el byte apuntado por PC (Program Counter)
2. Increment: Avanza PC al siguiente byte
3. Decode/Execute: Identifica el opcode y ejecuta la operación

El ciclo de instrucción es el "latido" del sistema. Sin él, la CPU no hace nada.

Ciclos de Máquina (M-Cycles) vs Ciclos de Reloj (T-Cycles):
- M-Cycle: Un ciclo de máquina corresponde a una operación de memoria
- T-Cycle: Un ciclo de reloj es la unidad básica de tiempo del hardware
- En la Game Boy, un M-Cycle = 4 T-Cycles típicamente
- Por ahora, contaremos M-Cycles (más simple para empezar)

Fuente: Pan Docs - CPU Instruction Set
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .registers import Registers

if TYPE_CHECKING:
    from ..memory.mmu import MMU

logger = logging.getLogger(__name__)


class CPU:
    """
    CPU LR35902 de la Game Boy.
    
    Gestiona el ciclo de instrucción (Fetch-Decode-Execute) y ejecuta opcodes.
    Mantiene una instancia de Registers y una referencia a la MMU.
    
    El ciclo básico es:
    1. Fetch: Leer opcode de memoria en dirección PC
    2. Increment: Avanzar PC
    3. Decode/Execute: Identificar y ejecutar la operación
    """

    def __init__(self, mmu: MMU) -> None:
        """
        Inicializa la CPU con una referencia a la MMU.
        
        Args:
            mmu: Instancia de MMU para acceso a memoria
        """
        self.registers = Registers()
        self.mmu = mmu
        logger.info("CPU inicializada")

    def fetch_byte(self) -> int:
        """
        Helper para leer el siguiente byte de memoria y avanzar PC automáticamente.
        
        Este método es útil para leer operandos (datos inmediatos) que siguen
        al opcode en memoria.
        
        Returns:
            Byte leído de la dirección actual de PC
        """
        addr = self.registers.get_pc()
        value = self.mmu.read_byte(addr)
        # Avanzar PC al siguiente byte
        self.registers.set_pc((addr + 1) & 0xFFFF)
        return value

    def step(self) -> int:
        """
        Ejecuta una sola instrucción del ciclo Fetch-Decode-Execute.
        
        Pasos:
        1. Fetch: Lee el opcode en la dirección apuntada por PC
        2. Increment: Avanza PC (se hace dentro del fetch_byte)
        3. Decode/Execute: Identifica el opcode con match/case y ejecuta
        
        Returns:
            Número de M-Cycles que tomó ejecutar la instrucción
            
        Raises:
            NotImplementedError: Si el opcode no está implementado
        """
        # Fetch: leer opcode
        opcode = self.fetch_byte()
        
        logger.debug(f"PC=0x{self.registers.get_pc()-1:04X} Opcode=0x{opcode:02X}")
        
        # Decode/Execute: identifica y ejecuta el opcode
        cycles = self._execute_opcode(opcode)
        
        return cycles

    def _execute_opcode(self, opcode: int) -> int:
        """
        Ejecuta el opcode especificado y devuelve los ciclos consumidos.
        
        Args:
            opcode: Código de operación (0x00 a 0xFF)
            
        Returns:
            Número de M-Cycles consumidos
            
        Raises:
            NotImplementedError: Si el opcode no está implementado
        """
        # Usamos if/elif en lugar de match/case para compatibilidad
        # TODO: Migrar a match/case cuando se actualice a Python 3.10+
        # Fuente: Pan Docs - Instruction Set
        
        if opcode == 0x00:
            # NOP (No Operation)
            # No hace nada, solo consume tiempo
            # Ciclos: 1 M-Cycle
            return 1
        
        elif opcode == 0x3E:
            # LD A, d8 (Load immediate value into A)
            # Carga el siguiente byte de memoria en el registro A
            # Ciclos: 2 M-Cycles (fetch opcode + fetch operand)
            operand = self.fetch_byte()
            self.registers.set_a(operand)
            logger.debug(f"LD A, 0x{operand:02X} -> A=0x{self.registers.get_a():02X}")
            return 2
        
        elif opcode == 0x06:
            # LD B, d8 (Load immediate value into B)
            # Carga el siguiente byte de memoria en el registro B
            # Ciclos: 2 M-Cycles (fetch opcode + fetch operand)
            operand = self.fetch_byte()
            self.registers.set_b(operand)
            logger.debug(f"LD B, 0x{operand:02X} -> B=0x{self.registers.get_b():02X}")
            return 2
        
        else:
            # Opcode no implementado
            raise NotImplementedError(
                f"Opcode 0x{opcode:02X} no implementado en PC=0x{self.registers.get_pc():04X}"
            )

