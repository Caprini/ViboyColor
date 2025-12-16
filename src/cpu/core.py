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
from typing import TYPE_CHECKING, Callable

from .registers import FLAG_C, FLAG_H, FLAG_N, FLAG_Z, Registers

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
        
        # Tabla de despacho (Dispatch Table) para opcodes
        # Mapea cada opcode a su función manejadora
        # Esto es más escalable que if/elif y compatible con Python 3.9+
        self._opcode_table: dict[int, Callable[[], int]] = {
            0x00: self._op_nop,
            0x06: self._op_ld_b_d8,
            0x3E: self._op_ld_a_d8,
            0xC6: self._op_add_a_d8,
            0xD6: self._op_sub_d8,
            # Saltos (Jumps)
            0xC3: self._op_jp_nn,      # JP nn (Jump absolute)
            0x18: self._op_jr_e,       # JR e (Jump relative unconditional)
            0x20: self._op_jr_nz_e,    # JR NZ, e (Jump relative if Not Zero)
        }
        
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

    def fetch_word(self) -> int:
        """
        Helper para leer la siguiente palabra (16 bits) de memoria y avanzar PC.
        
        Lee dos bytes consecutivos en formato Little-Endian y avanza PC en 2.
        Útil para leer direcciones de 16 bits (ej: en instrucciones JP nn).
        
        Returns:
            Palabra de 16 bits leída (Little-Endian)
            
        Fuente: Pan Docs - Memory Map (Little-Endian)
        """
        addr = self.registers.get_pc()
        value = self.mmu.read_word(addr)
        # Avanzar PC en 2 bytes
        self.registers.set_pc((addr + 2) & 0xFFFF)
        return value

    def _read_signed_byte(self) -> int:
        """
        Lee un byte de memoria y lo convierte a entero con signo (Two's Complement).
        
        En la Game Boy, los offsets de salto relativo (JR) usan representación
        de complemento a 2 (Two's Complement) en 8 bits:
        - Valores 0x00-0x7F (0-127): Positivos
        - Valores 0x80-0xFF (128-255): Negativos (-128 a -1)
        
        Ejemplo:
        - 0xFF = 255 en unsigned, pero -1 en signed
        - 0xFE = 254 en unsigned, pero -2 en signed
        - 0x80 = 128 en unsigned, pero -128 en signed
        
        Fórmula: val if val < 128 else val - 256
        
        Returns:
            Entero con signo en el rango [-128, 127]
            
        Fuente: Pan Docs - CPU Instruction Set (JR instructions)
        """
        unsigned_val = self.fetch_byte()
        # Convertir a signed: si >= 128, restar 256
        return unsigned_val if unsigned_val < 128 else unsigned_val - 256

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
        Ejecuta el opcode especificado usando la tabla de despacho.
        
        Usa un diccionario (dispatch table) en lugar de if/elif para mejor
        escalabilidad y rendimiento. Compatible con Python 3.9+.
        
        Args:
            opcode: Código de operación (0x00 a 0xFF)
            
        Returns:
            Número de M-Cycles consumidos
            
        Raises:
            NotImplementedError: Si el opcode no está implementado
            
        Fuente: Pan Docs - Instruction Set
        """
        handler = self._opcode_table.get(opcode)
        if handler is None:
            raise NotImplementedError(
                f"Opcode 0x{opcode:02X} no implementado en PC=0x{self.registers.get_pc():04X}"
            )
        return handler()
    
    # ========== Helpers ALU (Aritmética y Flags) ==========
    
    def _add(self, value: int) -> None:
        """
        Suma un valor al registro A y actualiza los flags correctamente.
        
        Esta es la operación aritmética básica de la ALU. Actualiza:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (es una suma)
        - H (Half-Carry): Si hubo carry del bit 3 al 4 (nibble bajo)
        - C (Carry): Si hubo carry del bit 7 (overflow de 8 bits)
        
        El Half-Carry es crítico para la instrucción DAA (Decimal Adjust Accumulator)
        que convierte números binarios a BCD (Binary Coded Decimal). Sin H correcto,
        los números decimales en juegos (puntuaciones, vidas) se mostrarán corruptos.
        
        Args:
            value: Valor a sumar (8 bits, se enmascara automáticamente)
            
        Fórmulas:
        - Half-Carry: (A & 0xF) + (value & 0xF) > 0xF
        - Carry: (A + value) > 0xFF
        
        Fuente: Pan Docs - CPU Flags, Z80/8080 Architecture Manual
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado
        result = a + value
        
        # Actualizar registro A (wrap-around de 8 bits)
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: resultado es cero
        if (result & 0xFF) == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en suma
        self.registers.clear_flag(FLAG_N)
        
        # H: Half-Carry (carry del bit 3 al 4)
        # Verificamos si la suma de los nibbles bajos excede 0xF
        if ((a & 0xF) + (value & 0xF)) > 0xF:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Carry (overflow de 8 bits)
        if result > 0xFF:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    def _sub(self, value: int) -> None:
        """
        Resta un valor del registro A y actualiza los flags correctamente.
        
        Similar a _add pero para restas. Actualiza:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 1 (es una resta)
        - H (Half-Borrow): Si hubo borrow del bit 4 al 3 (nibble bajo)
        - C (Borrow): Si hubo borrow del bit 7 (underflow de 8 bits)
        
        Args:
            value: Valor a restar (8 bits, se enmascara automáticamente)
            
        Fórmulas:
        - Half-Borrow: (A & 0xF) - (value & 0xF) < 0
        - Borrow: A < value
        
        Fuente: Pan Docs - CPU Flags, Z80/8080 Architecture Manual
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado
        result = a - value
        
        # Actualizar registro A (wrap-around de 8 bits)
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: resultado es cero
        if (result & 0xFF) == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 1 en resta
        self.registers.set_flag(FLAG_N)
        
        # H: Half-Borrow (borrow del bit 4 al 3)
        # Verificamos si necesitamos pedir prestado del nibble alto
        if (a & 0xF) < (value & 0xF):
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Borrow (underflow de 8 bits)
        if a < value:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    # ========== Handlers de Opcodes ==========
    
    def _op_nop(self) -> int:
        """
        NOP (No Operation) - Opcode 0x00
        
        No hace nada, solo consume tiempo. Útil para sincronización
        y alineamiento de instrucciones.
        
        Returns:
            1 M-Cycle
        """
        return 1
    
    def _op_ld_a_d8(self) -> int:
        """
        LD A, d8 (Load immediate value into A) - Opcode 0x3E
        
        Carga el siguiente byte de memoria en el registro A.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
        """
        operand = self.fetch_byte()
        self.registers.set_a(operand)
        logger.debug(f"LD A, 0x{operand:02X} -> A=0x{self.registers.get_a():02X}")
        return 2
    
    def _op_ld_b_d8(self) -> int:
        """
        LD B, d8 (Load immediate value into B) - Opcode 0x06
        
        Carga el siguiente byte de memoria en el registro B.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
        """
        operand = self.fetch_byte()
        self.registers.set_b(operand)
        logger.debug(f"LD B, 0x{operand:02X} -> B=0x{self.registers.get_b():02X}")
        return 2
    
    def _op_add_a_d8(self) -> int:
        """
        ADD A, d8 (Add immediate value to A) - Opcode 0xC6
        
        Suma el siguiente byte de memoria al registro A.
        Actualiza flags Z, N, H, C según el resultado.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._add(operand)
        logger.debug(
            f"ADD A, 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} H={self.registers.get_flag_h()} "
            f"C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_sub_d8(self) -> int:
        """
        SUB d8 (Subtract immediate value from A) - Opcode 0xD6
        
        Resta el siguiente byte de memoria del registro A.
        Actualiza flags Z, N, H, C según el resultado.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._sub(operand)
        logger.debug(
            f"SUB 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2

    # ========== Handlers de Saltos (Jumps) ==========

    def _op_jp_nn(self) -> int:
        """
        JP nn (Jump to absolute address) - Opcode 0xC3
        
        Salta incondicionalmente a la dirección absoluta especificada.
        Lee una dirección de 16 bits (Little-Endian) y la carga en PC.
        
        Ejemplo:
        - Si en memoria hay: 0xC3 0x00 0xC0
        - Lee 0x00C0 (Little-Endian de 0x00 0xC0)
        - PC se establece en 0xC000
        
        Returns:
            4 M-Cycles (fetch opcode + fetch 2 bytes de dirección)
            
        Fuente: Pan Docs - Instruction Set (JP nn)
        """
        target_addr = self.fetch_word()
        self.registers.set_pc(target_addr)
        logger.debug(f"JP 0x{target_addr:04X} -> PC=0x{self.registers.get_pc():04X}")
        return 4

    def _op_jr_e(self) -> int:
        """
        JR e (Jump Relative) - Opcode 0x18
        
        Salto relativo incondicional. Lee un byte con signo (offset) y lo suma
        al PC actual (después de leer la instrucción completa).
        
        El offset se interpreta como complemento a 2:
        - 0x00-0x7F: Saltos hacia adelante (0 a +127 bytes)
        - 0x80-0xFF: Saltos hacia atrás (-128 a -1 bytes)
        
        Importante: El offset se suma al PC DESPUÉS de leer toda la instrucción
        (opcode + offset). Si PC está en 0x0100 y leemos JR 5:
        - PC después de leer opcode: 0x0101
        - PC después de leer offset: 0x0102
        - PC final: 0x0102 + 5 = 0x0107
        
        Returns:
            3 M-Cycles (fetch opcode + fetch offset + ejecutar salto)
            
        Fuente: Pan Docs - Instruction Set (JR e)
        """
        offset = self._read_signed_byte()
        current_pc = self.registers.get_pc()
        new_pc = (current_pc + offset) & 0xFFFF
        self.registers.set_pc(new_pc)
        logger.debug(
            f"JR {offset:+d} (0x{offset & 0xFF:02X}) "
            f"PC: 0x{current_pc:04X} -> 0x{new_pc:04X}"
        )
        return 3

    def _op_jr_nz_e(self) -> int:
        """
        JR NZ, e (Jump Relative if Not Zero) - Opcode 0x20
        
        Salto relativo condicional. Lee un byte con signo (offset) y salta solo
        si el flag Z (Zero) está desactivado (Z == 0).
        
        El offset funciona igual que en JR e (complemento a 2).
        
        Timing condicional:
        - Si Z == 0 (condición verdadera): 3 M-Cycles (salta)
        - Si Z == 1 (condición falsa): 2 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si salta, 2 M-Cycles si no salta
            
        Fuente: Pan Docs - Instruction Set (JR NZ, e)
        """
        offset = self._read_signed_byte()
        
        # Verificar condición: Z flag debe estar desactivado (Z == 0)
        if not self.registers.get_flag_z():
            # Condición verdadera: ejecutar salto
            current_pc = self.registers.get_pc()
            new_pc = (current_pc + offset) & 0xFFFF
            self.registers.set_pc(new_pc)
            logger.debug(
                f"JR NZ, {offset:+d} (TAKEN) "
                f"PC: 0x{current_pc:04X} -> 0x{new_pc:04X}"
            )
            return 3  # 3 M-Cycles si salta
        else:
            # Condición falsa: no saltar, continuar ejecución
            logger.debug(f"JR NZ, {offset:+d} (NOT TAKEN) Z flag set")
            return 2  # 2 M-Cycles si no salta

