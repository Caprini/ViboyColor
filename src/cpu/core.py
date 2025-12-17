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
        
        # IME (Interrupt Master Enable) - Control de interrupciones
        # No es un registro accesible, sino un "interruptor" interno de la CPU
        # DI lo apaga (False), EI lo enciende (True)
        # Por defecto, después de la boot ROM, IME está activado, pero los juegos
        # suelen desactivarlo explícitamente al inicio con DI
        # Inicializamos en False por seguridad (el juego lo activará si lo necesita)
        self.ime: bool = False
        
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
            # Stack (Pila)
            0xC5: self._op_push_bc,    # PUSH BC
            0xC1: self._op_pop_bc,     # POP BC
            0xCD: self._op_call_nn,     # CALL nn
            0xC9: self._op_ret,         # RET
            # Control de Interrupciones
            0xF3: self._op_di,          # DI (Disable Interrupts)
            0xFB: self._op_ei,          # EI (Enable Interrupts)
            # Operaciones Lógicas
            0xAF: self._op_xor_a,       # XOR A (optimización para poner A a cero)
            # Carga inmediata de 16 bits
            0x31: self._op_ld_sp_d16,   # LD SP, d16
            0x21: self._op_ld_hl_d16,   # LD HL, d16
            0x01: self._op_ld_bc_d16,   # LD BC, d16
            0x11: self._op_ld_de_d16,   # LD DE, d16
            # Memoria Indirecta (HL, BC, DE)
            0x77: self._op_ld_hl_ptr_a,    # LD (HL), A
            0x22: self._op_ldi_hl_a,       # LD (HL+), A (LDI (HL), A)
            0x32: self._op_ldd_hl_a,       # LD (HL-), A (LDD (HL), A)
            0x2A: self._op_ldi_a_hl_ptr,   # LD A, (HL+) (LDI A, (HL))
            0x02: self._op_ld_bc_ptr_a,    # LD (BC), A
            0x12: self._op_ld_de_ptr_a,    # LD (DE), A
            # Incremento/Decremento de 8 bits
            0x04: self._op_inc_b,          # INC B
            0x05: self._op_dec_b,          # DEC B
            0x0C: self._op_inc_c,          # INC C
            0x0D: self._op_dec_c,          # DEC C
            0x3C: self._op_inc_a,          # INC A
            0x3D: self._op_dec_a,          # DEC A
            # I/O Access (LDH - Load High)
            0xE0: self._op_ldh_n_a,       # LDH (n), A
            0xF0: self._op_ldh_a_n,       # LDH A, (n)
            # Prefijo CB (Extended Instructions)
            0xCB: self._handle_cb_prefix,  # CB Prefix
            # Comparaciones (CP)
            0xFE: self._op_cp_d8,          # CP d8
            0xBE: self._op_cp_hl_ptr,      # CP (HL)
            # Incremento/Decremento de 16 bits
            0x03: self._op_inc_bc,         # INC BC
            0x13: self._op_inc_de,         # INC DE
            0x23: self._op_inc_hl,         # INC HL
            0x33: self._op_inc_sp,         # INC SP
            0x0B: self._op_dec_bc,         # DEC BC
            0x1B: self._op_dec_de,         # DEC DE
            0x2B: self._op_dec_hl,         # DEC HL
            0x3B: self._op_dec_sp,         # DEC SP
            # Aritmética de 16 bits (ADD HL, rr)
            0x09: self._op_add_hl_bc,      # ADD HL, BC
            0x19: self._op_add_hl_de,      # ADD HL, DE
            0x29: self._op_add_hl_hl,      # ADD HL, HL
            0x39: self._op_add_hl_sp,      # ADD HL, SP
            # Retornos condicionales
            0xC0: self._op_ret_nz,         # RET NZ
            0xC8: self._op_ret_z,          # RET Z
            0xD0: self._op_ret_nc,         # RET NC
            0xD8: self._op_ret_c,          # RET C
        }
        
        # Tabla de despacho para opcodes CB (Extended Instructions)
        # El prefijo CB permite acceder a 256 instrucciones adicionales
        # Rango 0x40-0x7F: BIT b, r (Test bit)
        self._cb_opcode_table: dict[int, Callable[[], int]] = {
            0x7C: self._op_cb_bit_7_h,    # BIT 7, H
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
    
    # ========== Helpers de Pila (Stack) ==========
    
    def _push_byte(self, value: int) -> None:
        """
        Empuja un byte en la pila (Stack).
        
        La pila crece hacia abajo (de direcciones altas a bajas).
        Al hacer PUSH, el Stack Pointer (SP) se decrementa ANTES de escribir.
        
        Proceso:
        1. Decrementar SP
        2. Escribir byte en la dirección SP
        
        Args:
            value: Valor de 8 bits a empujar (se enmascara automáticamente)
            
        Fuente: Pan Docs - Stack Operations
        """
        # Enmascarar a 8 bits
        value = value & 0xFF
        
        # Obtener SP actual
        sp = self.registers.get_sp()
        
        # Decrementar SP (la pila crece hacia abajo)
        # Wrap-around si SP es 0x0000 -> 0xFFFF
        new_sp = (sp - 1) & 0xFFFF
        self.registers.set_sp(new_sp)
        
        # Escribir byte en la nueva posición de SP
        self.mmu.write_byte(new_sp, value)
        
        logger.debug(f"PUSH byte 0x{value:02X} -> SP: 0x{sp:04X} -> 0x{new_sp:04X}")
    
    def _pop_byte(self) -> int:
        """
        Saca un byte de la pila (Stack).
        
        La pila crece hacia abajo, así que al hacer POP:
        1. Leer byte de la dirección SP
        2. Incrementar SP
        
        Returns:
            Byte leído de la pila (0x00 a 0xFF)
            
        Fuente: Pan Docs - Stack Operations
        """
        # Obtener SP actual
        sp = self.registers.get_sp()
        
        # Leer byte de la dirección SP
        value = self.mmu.read_byte(sp)
        
        # Incrementar SP (la pila crece hacia abajo, así que al sacar subimos)
        # Wrap-around si SP es 0xFFFF -> 0x0000
        new_sp = (sp + 1) & 0xFFFF
        self.registers.set_sp(new_sp)
        
        logger.debug(f"POP byte 0x{value:02X} <- SP: 0x{sp:04X} -> 0x{new_sp:04X}")
        
        return value
    
    def _push_word(self, value: int) -> None:
        """
        Empuja una palabra (16 bits) en la pila.
        
        CRÍTICO: Orden de bytes para mantener Little-Endian correcto.
        
        Para mantener Little-Endian en memoria, al hacer PUSH de 0x1234:
        1. Decrementar SP, escribir 0x12 (High Byte) en SP
        2. Decrementar SP, escribir 0x34 (Low Byte) en SP
        
        Así, en memoria queda: [SP+1]=0x12, [SP]=0x34
        Al leer con read_word(SP), obtenemos 0x1234 correctamente.
        
        Args:
            value: Valor de 16 bits a empujar (se enmascara automáticamente)
            
        Fuente: Pan Docs - Stack Operations, Little-Endian
        """
        # Enmascarar a 16 bits
        value = value & 0xFFFF
        
        # Extraer bytes
        high_byte = (value >> 8) & 0xFF  # Bits 8-15
        low_byte = value & 0xFF          # Bits 0-7
        
        # PUSH: primero el byte alto, luego el bajo
        # Esto asegura que en memoria quede en orden Little-Endian
        self._push_byte(high_byte)  # Decrementa SP y escribe high
        self._push_byte(low_byte)   # Decrementa SP y escribe low
        
        logger.debug(f"PUSH word 0x{value:04X} -> SP final: 0x{self.registers.get_sp():04X}")
    
    def _pop_word(self) -> int:
        """
        Saca una palabra (16 bits) de la pila.
        
        CRÍTICO: Orden de bytes para mantener Little-Endian correcto.
        
        Como PUSH escribe primero high luego low, POP debe leer:
        1. Leer low byte de SP
        2. Incrementar SP
        3. Leer high byte de SP
        4. Incrementar SP
        5. Combinar: (high << 8) | low
        
        Returns:
            Palabra de 16 bits leída de la pila
            
        Fuente: Pan Docs - Stack Operations, Little-Endian
        """
        # POP: primero el byte bajo, luego el alto (orden inverso de PUSH)
        low_byte = self._pop_byte()   # Lee low e incrementa SP
        high_byte = self._pop_byte()  # Lee high e incrementa SP
        
        # Combinar en orden Little-Endian: (high << 8) | low
        value = ((high_byte << 8) | low_byte) & 0xFFFF
        
        logger.debug(f"POP word 0x{value:04X} <- SP final: 0x{self.registers.get_sp():04X}")
        
        return value
    
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
    
    def _cp(self, value: int) -> None:
        """
        Compara (Compare) un valor con el registro A y actualiza los flags.
        
        CP es fundamentalmente una RESTA (SUB), pero con una diferencia crítica:
        **Descarta el resultado numérico** y solo se queda con los **Flags**.
        El registro A NO se modifica.
        
        Se usa para comparaciones en código: "¿A == value?", "¿A < value?", etc.
        
        Flags actualizados:
        - Z (Zero): 1 si A == value (resultado de resta es 0)
        - N (Subtract): Siempre 1 (es una resta)
        - H (Half-Borrow): Si hubo borrow del bit 4 al 3 (nibble bajo)
        - C (Borrow): Si hubo borrow del bit 7 (A < value)
        
        Ejemplos:
        - Si A = 0x10 y value = 0x10: A - value = 0, Z=1, C=0
        - Si A = 0x01 y value = 0x02: A - value necesita borrow, Z=0, C=1
        - Si A = 0x05 y value = 0x03: A - value = 0x02, Z=0, C=0
        
        Args:
            value: Valor a comparar con A (8 bits, se enmascara automáticamente)
            
        Fuente: Pan Docs - CPU Instruction Set (CP instruction)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado (pero NO modificar A)
        result = a - value
        
        # Actualizar flags (igual que en _sub)
        # Z: resultado es cero (A == value)
        if (result & 0xFF) == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 1 en comparación (es una resta)
        self.registers.set_flag(FLAG_N)
        
        # H: Half-Borrow (borrow del bit 4 al 3)
        # Verificamos si necesitamos pedir prestado del nibble alto
        if (a & 0xF) < (value & 0xF):
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Borrow (A < value)
        if a < value:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        # CRÍTICO: A NO se modifica (solo se usó para calcular flags)
    
    def _inc_n(self, value: int) -> int:
        """
        Incrementa un valor de 8 bits y actualiza los flags Z, N, H.
        
        CRÍTICO: INC de 8 bits NO afecta al flag C (Carry).
        Esta es una peculiaridad importante del hardware LR35902.
        Muchos emuladores fallan aquí, rompiendo la lógica condicional que depende
        de mantener el flag C intacto durante operaciones de incremento.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (es una suma, aunque unaria)
        - H (Half-Carry): Si hubo carry del bit 3 al 4 (nibble bajo)
        - C (Carry): NO SE TOCA (permanece como estaba)
        
        El Half-Carry se activa cuando hay desbordamiento del nibble bajo:
        - Ejemplo: 0x0F + 1 = 0x10 -> H = 1 (hubo carry del bit 3 al 4)
        
        Args:
            value: Valor de 8 bits a incrementar (se enmascara automáticamente)
            
        Returns:
            Valor incrementado (8 bits con wrap-around)
            
        Fuente: Pan Docs - CPU Flags (INC instruction behavior)
        """
        value = value & 0xFF
        result = (value + 1) & 0xFF
        
        # Actualizar flags
        # Z: resultado es cero
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en incremento (es una suma)
        self.registers.clear_flag(FLAG_N)
        
        # H: Half-Carry (carry del bit 3 al 4)
        # Verificamos si la suma del nibble bajo excede 0xF
        if ((value & 0xF) + 1) > 0xF:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: NO SE TOCA - Esta es la peculiaridad crítica
        
        return result
    
    def _dec_n(self, value: int) -> int:
        """
        Decrementa un valor de 8 bits y actualiza los flags Z, N, H.
        
        CRÍTICO: DEC de 8 bits NO afecta al flag C (Carry).
        Esta es una peculiaridad importante del hardware LR35902, igual que en INC.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 1 (es una resta, aunque unaria)
        - H (Half-Borrow): Si hubo borrow del bit 4 al 3 (nibble bajo)
        - C (Carry): NO SE TOCA (permanece como estaba)
        
        El Half-Borrow se activa cuando necesitamos pedir prestado del nibble alto:
        - Ejemplo: 0x10 - 1 = 0x0F -> H = 1 (hubo borrow del bit 4 al 3)
        
        Args:
            value: Valor de 8 bits a decrementar (se enmascara automáticamente)
            
        Returns:
            Valor decrementado (8 bits con wrap-around)
            
        Fuente: Pan Docs - CPU Flags (DEC instruction behavior)
        """
        value = value & 0xFF
        result = (value - 1) & 0xFF
        
        # Actualizar flags
        # Z: resultado es cero
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 1 en decremento (es una resta)
        self.registers.set_flag(FLAG_N)
        
        # H: Half-Borrow (borrow del bit 4 al 3)
        # Verificamos si necesitamos pedir prestado del nibble alto
        if (value & 0xF) == 0:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: NO SE TOCA - Esta es la peculiaridad crítica
        
        return result
    
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

    # ========== Handlers de Stack (Pila) ==========

    def _op_push_bc(self) -> int:
        """
        PUSH BC (Push BC onto stack) - Opcode 0xC5
        
        Empuja el par de registros BC en la pila.
        El Stack Pointer (SP) se decrementa antes de escribir.
        
        Proceso:
        1. Obtener valor de BC
        2. PUSH word (BC) en la pila
        
        Returns:
            4 M-Cycles (fetch opcode + 2 operaciones de memoria para escribir 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (PUSH BC)
        """
        bc_value = self.registers.get_bc()
        self._push_word(bc_value)
        logger.debug(f"PUSH BC (0x{bc_value:04X}) -> SP=0x{self.registers.get_sp():04X}")
        return 4

    def _op_pop_bc(self) -> int:
        """
        POP BC (Pop from stack into BC) - Opcode 0xC1
        
        Saca un valor de 16 bits de la pila y lo carga en el par BC.
        El Stack Pointer (SP) se incrementa después de leer.
        
        Proceso:
        1. POP word de la pila
        2. Cargar valor en BC
        
        Returns:
            3 M-Cycles (fetch opcode + 2 operaciones de memoria para leer 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (POP BC)
        """
        value = self._pop_word()
        self.registers.set_bc(value)
        logger.debug(f"POP BC <- 0x{value:04X} (SP=0x{self.registers.get_sp():04X})")
        return 3

    def _op_call_nn(self) -> int:
        """
        CALL nn (Call subroutine at absolute address) - Opcode 0xCD
        
        Llama a una subrutina guardando la dirección de retorno en la pila.
        
        Proceso:
        1. Leer dirección objetivo (nn) de 16 bits (Little-Endian)
        2. Obtener PC actual (dirección de retorno = siguiente instrucción)
        3. PUSH PC en la pila
        4. Saltar a nn (establecer PC = nn)
        
        Importante: El PC que se guarda es el valor DESPUÉS de leer toda la instrucción
        (opcode + 2 bytes de dirección). Esto es la dirección de la siguiente instrucción.
        
        Ejemplo:
        - PC en 0x0100
        - CALL 0x2000 (0xCD 0x00 0x20)
        - Después de leer: PC = 0x0103
        - Se guarda 0x0103 en la pila
        - PC se establece en 0x2000
        
        Returns:
            6 M-Cycles (fetch opcode + fetch 2 bytes dirección + push 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (CALL nn)
        """
        # Leer dirección objetivo (nn)
        target_addr = self.fetch_word()
        
        # Obtener PC actual (dirección de retorno = siguiente instrucción)
        return_addr = self.registers.get_pc()
        
        # Guardar dirección de retorno en la pila
        self._push_word(return_addr)
        
        # Saltar a la dirección objetivo
        self.registers.set_pc(target_addr)
        
        logger.debug(
            f"CALL 0x{target_addr:04X} -> "
            f"PUSH return 0x{return_addr:04X}, PC=0x{target_addr:04X}"
        )
        return 6

    def _op_ret(self) -> int:
        """
        RET (Return from subroutine) - Opcode 0xC9
        
        Retorna de una subrutina recuperando la dirección de retorno de la pila.
        
        Proceso:
        1. POP dirección de retorno de la pila
        2. Saltar a esa dirección (establecer PC = dirección de retorno)
        
        Returns:
            4 M-Cycles (fetch opcode + pop 2 bytes de la pila)
            
        Fuente: Pan Docs - Instruction Set (RET)
        """
        # Recuperar dirección de retorno de la pila
        return_addr = self._pop_word()
        
        # Saltar a la dirección de retorno
        self.registers.set_pc(return_addr)
        
        logger.debug(f"RET -> PC=0x{return_addr:04X} (SP=0x{self.registers.get_sp():04X})")
        return 4

    # ========== Handlers de Control de Interrupciones ==========

    def _op_di(self) -> int:
        """
        DI (Disable Interrupts) - Opcode 0xF3
        
        Desactiva las interrupciones poniendo IME (Interrupt Master Enable) a False.
        
        Esta instrucción es crítica para la inicialización del sistema. Los juegos
        suelen desactivar las interrupciones al inicio para configurar el hardware
        sin que nadie les moleste, y luego las reactivan cuando están listos.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (DI)
        """
        self.ime = False
        logger.debug("DI -> IME=False (interrupciones desactivadas)")
        return 1

    def _op_ei(self) -> int:
        """
        EI (Enable Interrupts) - Opcode 0xFB
        
        Activa las interrupciones poniendo IME (Interrupt Master Enable) a True.
        
        NOTA IMPORTANTE: En hardware real, EI tiene un retraso de 1 instrucción.
        Esto significa que las interrupciones no se activan inmediatamente, sino
        después de ejecutar la siguiente instrucción. Por ahora, implementamos
        la activación inmediata para simplificar. Más adelante, cuando implementemos
        el manejo completo de interrupciones, añadiremos este retraso.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (EI)
        """
        self.ime = True
        logger.debug("EI -> IME=True (interrupciones activadas)")
        return 1

    # ========== Handlers de Operaciones Lógicas ==========

    def _op_xor_a(self) -> int:
        """
        XOR A (XOR A with A) - Opcode 0xAF
        
        Realiza la operación XOR entre el registro A y él mismo: A = A ^ A.
        
        Como cualquier valor XOR consigo mismo siempre es 0, esta instrucción
        pone el registro A a cero de forma eficiente.
        
        Optimización histórica: Los desarrolladores usaban `XOR A` en lugar de
        `LD A, 0` porque:
        - Ocupa menos bytes (1 byte vs 2 bytes)
        - Consume menos ciclos (1 ciclo vs 2 ciclos)
        - Es más rápido en hardware antiguo
        
        Actualización de flags:
        - Z (Zero): Siempre 1 (el resultado siempre es 0)
        - N (Subtract): Siempre 0 (XOR no es una resta)
        - H (Half-Carry): Siempre 0 (XOR no tiene carry)
        - C (Carry): Siempre 0 (XOR no tiene carry)
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (XOR A)
        """
        # A ^ A siempre es 0
        self.registers.set_a(0)
        
        # Actualizar flags
        # Z: siempre 1 (resultado es 0)
        self.registers.set_flag(FLAG_Z)
        # N, H, C: siempre 0 en XOR
        self.registers.clear_flag(FLAG_N)
        self.registers.clear_flag(FLAG_H)
        self.registers.clear_flag(FLAG_C)
        
        logger.debug("XOR A -> A=0x00, Z=1, N=0, H=0, C=0")
        return 1

    # ========== Handlers de Carga Inmediata de 16 bits ==========

    def _op_ld_sp_d16(self) -> int:
        """
        LD SP, d16 (Load immediate 16-bit value into Stack Pointer) - Opcode 0x31
        
        Carga un valor inmediato de 16 bits en el Stack Pointer (SP).
        
        Lee los siguientes 2 bytes de memoria (Little-Endian) y los carga en SP.
        Esta instrucción es crítica para la inicialización del sistema, ya que
        los juegos suelen configurar SP al inicio del programa.
        
        Ejemplo:
        - Si en memoria hay: 0x31 0xFE 0xFF
        - Lee 0xFFFE (Little-Endian de 0xFE 0xFF)
        - SP se establece en 0xFFFE
        
        Returns:
            3 M-Cycles (fetch opcode + fetch 2 bytes de valor)
            
        Fuente: Pan Docs - Instruction Set (LD SP, d16)
        """
        value = self.fetch_word()
        self.registers.set_sp(value)
        logger.debug(f"LD SP, 0x{value:04X} -> SP=0x{self.registers.get_sp():04X}")
        return 3

    def _op_ld_hl_d16(self) -> int:
        """
        LD HL, d16 (Load immediate 16-bit value into HL) - Opcode 0x21
        
        Carga un valor inmediato de 16 bits en el registro par HL.
        
        Lee los siguientes 2 bytes de memoria (Little-Endian) y los carga en HL.
        HL es uno de los pares de registros más usados como puntero de memoria.
        
        Ejemplo:
        - Si en memoria hay: 0x21 0x00 0xC0
        - Lee 0xC000 (Little-Endian de 0x00 0xC0)
        - HL se establece en 0xC000
        
        Returns:
            3 M-Cycles (fetch opcode + fetch 2 bytes de valor)
            
        Fuente: Pan Docs - Instruction Set (LD HL, d16)
        """
        value = self.fetch_word()
        self.registers.set_hl(value)
        logger.debug(f"LD HL, 0x{value:04X} -> HL=0x{self.registers.get_hl():04X}")
        return 3
    
    def _op_ld_bc_d16(self) -> int:
        """
        LD BC, d16 (Load immediate 16-bit value into BC) - Opcode 0x01
        
        Carga un valor inmediato de 16 bits en el registro par BC.
        
        Lee los siguientes 2 bytes de memoria (Little-Endian) y los carga en BC.
        BC se usa frecuentemente como contador o puntero secundario en bucles.
        
        Ejemplo:
        - Si en memoria hay: 0x01 0x34 0x12
        - Lee 0x1234 (Little-Endian de 0x34 0x12)
        - BC se establece en 0x1234 (B=0x12, C=0x34)
        
        Returns:
            3 M-Cycles (fetch opcode + fetch 2 bytes de valor)
            
        Fuente: Pan Docs - Instruction Set (LD BC, d16)
        """
        value = self.fetch_word()
        self.registers.set_bc(value)
        logger.debug(f"LD BC, 0x{value:04X} -> BC=0x{self.registers.get_bc():04X}")
        return 3
    
    def _op_ld_de_d16(self) -> int:
        """
        LD DE, d16 (Load immediate 16-bit value into DE) - Opcode 0x11
        
        Carga un valor inmediato de 16 bits en el registro par DE.
        
        Lee los siguientes 2 bytes de memoria (Little-Endian) y los carga en DE.
        DE se usa frecuentemente como puntero de destino en operaciones de copia de datos.
        
        Ejemplo:
        - Si en memoria hay: 0x11 0x56 0x78
        - Lee 0x7856 (Little-Endian de 0x56 0x78)
        - DE se establece en 0x7856 (D=0x78, E=0x56)
        
        Returns:
            3 M-Cycles (fetch opcode + fetch 2 bytes de valor)
            
        Fuente: Pan Docs - Instruction Set (LD DE, d16)
        """
        value = self.fetch_word()
        self.registers.set_de(value)
        logger.debug(f"LD DE, 0x{value:04X} -> DE=0x{self.registers.get_de():04X}")
        return 3

    # ========== Handlers de Memoria Indirecta (HL) ==========
    
    def _op_ld_hl_ptr_a(self) -> int:
        """
        LD (HL), A (Load A into memory address pointed by HL) - Opcode 0x77
        
        Escribe el valor del registro A en la dirección de memoria apuntada por HL.
        
        Direccionamiento indirecto: HL se usa como puntero, no como valor.
        Es como un puntero en C: escribimos en *HL, no en HL mismo.
        
        Esta instrucción es fundamental para operaciones de memoria como bucles
        de limpieza (memset) y copia de datos.
        
        Ejemplo:
        - HL = 0xC000
        - A = 0x55
        - Ejecutar LD (HL), A
        - Resultado: Memoria[0xC000] = 0x55, HL sigue siendo 0xC000
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LD (HL), A)
        """
        hl_addr = self.registers.get_hl()
        a_value = self.registers.get_a()
        self.mmu.write_byte(hl_addr, a_value)
        logger.debug(f"LD (HL), A -> (0x{hl_addr:04X}) = 0x{a_value:02X}")
        return 2
    
    def _op_ldi_hl_a(self) -> int:
        """
        LD (HL+), A / LDI (HL), A (Load A into (HL) and increment HL) - Opcode 0x22
        
        Escribe el valor del registro A en la dirección apuntada por HL e incrementa HL.
        
        Esta es una "navaja suiza" para bucles de escritura rápida:
        - Escribe un dato
        - Incrementa el puntero automáticamente
        - Todo en una sola instrucción
        
        Es ideal para operaciones como memset o memcpy donde necesitas avanzar
        el puntero después de cada escritura.
        
        Ejemplo:
        - HL = 0xC000
        - A = 0x55
        - Ejecutar LD (HL+), A
        - Resultado: Memoria[0xC000] = 0x55, HL = 0xC001
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LDI (HL), A)
        """
        hl_addr = self.registers.get_hl()
        a_value = self.registers.get_a()
        self.mmu.write_byte(hl_addr, a_value)
        # Incrementar HL (wrap-around de 16 bits)
        new_hl = (hl_addr + 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"LD (HL+), A -> (0x{hl_addr:04X}) = 0x{a_value:02X}, HL = 0x{new_hl:04X}")
        return 2
    
    def _op_ldd_hl_a(self) -> int:
        """
        LD (HL-), A / LDD (HL), A (Load A into (HL) and decrement HL) - Opcode 0x32
        
        Escribe el valor del registro A en la dirección apuntada por HL y decrementa HL.
        
        Similar a LDI, pero decrementa el puntero. Útil para bucles que recorren
        la memoria hacia atrás, como limpieza de memoria desde el final hacia el inicio.
        
        Ejemplo:
        - HL = 0xC000
        - A = 0x55
        - Ejecutar LD (HL-), A
        - Resultado: Memoria[0xC000] = 0x55, HL = 0xBFFF
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LDD (HL), A)
        """
        hl_addr = self.registers.get_hl()
        a_value = self.registers.get_a()
        self.mmu.write_byte(hl_addr, a_value)
        # Decrementar HL (wrap-around de 16 bits)
        new_hl = (hl_addr - 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"LD (HL-), A -> (0x{hl_addr:04X}) = 0x{a_value:02X}, HL = 0x{new_hl:04X}")
        return 2
    
    def _op_ldi_a_hl_ptr(self) -> int:
        """
        LD A, (HL+) / LDI A, (HL) (Load from (HL) into A and increment HL) - Opcode 0x2A
        
        Lee el valor de la dirección apuntada por HL y lo carga en A, luego incrementa HL.
        
        Es el complemento de LD (HL+), A. Útil para bucles de lectura rápida.
        
        Ejemplo:
        - HL = 0xC000
        - Memoria[0xC000] = 0x42
        - Ejecutar LD A, (HL+)
        - Resultado: A = 0x42, HL = 0xC001
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LDI A, (HL))
        """
        hl_addr = self.registers.get_hl()
        value = self.mmu.read_byte(hl_addr)
        self.registers.set_a(value)
        # Incrementar HL (wrap-around de 16 bits)
        new_hl = (hl_addr + 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"LD A, (HL+) -> A = 0x{value:02X} from (0x{hl_addr:04X}), HL = 0x{new_hl:04X}")
        return 2
    
    def _op_ld_bc_ptr_a(self) -> int:
        """
        LD (BC), A (Load A into memory address pointed by BC) - Opcode 0x02
        
        Escribe el valor del registro A en la dirección de memoria apuntada por BC.
        
        Similar a LD (HL), A pero usando BC como puntero. Útil para escribir
        datos usando BC como contador o puntero secundario.
        
        Ejemplo:
        - BC = 0xC000
        - A = 0xAA
        - Ejecutar LD (BC), A
        - Resultado: Memoria[0xC000] = 0xAA, BC sigue siendo 0xC000
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LD (BC), A)
        """
        bc_addr = self.registers.get_bc()
        a_value = self.registers.get_a()
        self.mmu.write_byte(bc_addr, a_value)
        logger.debug(f"LD (BC), A -> (0x{bc_addr:04X}) = 0x{a_value:02X}")
        return 2
    
    def _op_ld_de_ptr_a(self) -> int:
        """
        LD (DE), A (Load A into memory address pointed by DE) - Opcode 0x12
        
        Escribe el valor del registro A en la dirección de memoria apuntada por DE.
        
        Similar a LD (BC), A pero usando DE como puntero. Útil para escribir
        datos usando DE como puntero de destino en operaciones de copia.
        
        Ejemplo:
        - DE = 0xD000
        - A = 0x55
        - Ejecutar LD (DE), A
        - Resultado: Memoria[0xD000] = 0x55, DE sigue siendo 0xD000
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LD (DE), A)
        """
        de_addr = self.registers.get_de()
        a_value = self.registers.get_a()
        self.mmu.write_byte(de_addr, a_value)
        logger.debug(f"LD (DE), A -> (0x{de_addr:04X}) = 0x{a_value:02X}")
        return 2
    
    # ========== Handlers de Incremento/Decremento ==========
    
    def _op_inc_b(self) -> int:
        """
        INC B (Increment B) - Opcode 0x04
        
        Incrementa el registro B en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC B)
        """
        new_value = self._inc_n(self.registers.get_b())
        self.registers.set_b(new_value)
        logger.debug(
            f"INC B -> B=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_b(self) -> int:
        """
        DEC B (Decrement B) - Opcode 0x05
        
        Decrementa el registro B en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC B)
        """
        new_value = self._dec_n(self.registers.get_b())
        self.registers.set_b(new_value)
        logger.debug(
            f"DEC B -> B=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_c(self) -> int:
        """
        INC C (Increment C) - Opcode 0x0C
        
        Incrementa el registro C en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC C)
        """
        new_value = self._inc_n(self.registers.get_c())
        self.registers.set_c(new_value)
        logger.debug(
            f"INC C -> C=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_c(self) -> int:
        """
        DEC C (Decrement C) - Opcode 0x0D
        
        Decrementa el registro C en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC C)
        """
        new_value = self._dec_n(self.registers.get_c())
        self.registers.set_c(new_value)
        logger.debug(
            f"DEC C -> C=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_a(self) -> int:
        """
        INC A (Increment A) - Opcode 0x3C
        
        Incrementa el registro A en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC A)
        """
        new_value = self._inc_n(self.registers.get_a())
        self.registers.set_a(new_value)
        logger.debug(
            f"INC A -> A=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_a(self) -> int:
        """
        DEC A (Decrement A) - Opcode 0x3D
        
        Decrementa el registro A en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC A)
        """
        new_value = self._dec_n(self.registers.get_a())
        self.registers.set_a(new_value)
        logger.debug(
            f"DEC A -> A=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    # ========== Handlers de I/O Access (LDH) ==========
    
    def _op_ldh_n_a(self) -> int:
        """
        LDH (n), A (Load A into I/O port) - Opcode 0xE0
        
        Escribe el valor del registro A en la dirección (0xFF00 + n), donde n es
        el siguiente byte de memoria.
        
        Esta es una optimización para acceder a los registros de hardware (I/O Ports)
        en el rango 0xFF00-0xFFFF. La CPU ahorra espacio usando solo 1 byte de
        dirección (offset) y sumándole 0xFF00 automáticamente.
        
        Ejemplo:
        - A = 0xAA
        - n = 0x80
        - Ejecutar LDH (0x80), A
        - Resultado: Memoria[0xFF80] = 0xAA
        
        Returns:
            3 M-Cycles (fetch opcode + fetch n + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LDH (n), A)
        """
        # Leer offset n (8 bits)
        n = self.fetch_byte()
        
        # Calcular dirección I/O: 0xFF00 + n
        io_addr = (0xFF00 + n) & 0xFFFF
        
        # Escribir A en la dirección I/O
        a_value = self.registers.get_a()
        self.mmu.write_byte(io_addr, a_value)
        
        logger.debug(
            f"LDH (0x{n:02X}), A -> (0x{io_addr:04X}) = 0x{a_value:02X}"
        )
        return 3
    
    def _op_ldh_a_n(self) -> int:
        """
        LDH A, (n) (Load from I/O port into A) - Opcode 0xF0
        
        Lee el valor de la dirección (0xFF00 + n) y lo carga en el registro A,
        donde n es el siguiente byte de memoria.
        
        Es el complemento de LDH (n), A. Permite leer de los registros de hardware.
        
        Ejemplo:
        - n = 0x90
        - Memoria[0xFF90] = 0x42
        - Ejecutar LDH A, (0x90)
        - Resultado: A = 0x42
        
        Returns:
            3 M-Cycles (fetch opcode + fetch n + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LDH A, (n))
        """
        # Leer offset n (8 bits)
        n = self.fetch_byte()
        
        # Calcular dirección I/O: 0xFF00 + n
        io_addr = (0xFF00 + n) & 0xFFFF
        
        # Leer valor de la dirección I/O y cargar en A
        value = self.mmu.read_byte(io_addr)
        self.registers.set_a(value)
        
        logger.debug(
            f"LDH A, (0x{n:02X}) -> A = 0x{value:02X} from (0x{io_addr:04X})"
        )
        return 3
    
    # ========== Handlers del Prefijo CB (Extended Instructions) ==========
    
    def _handle_cb_prefix(self) -> int:
        """
        Maneja el prefijo CB (0xCB) para instrucciones extendidas.
        
        La Game Boy tiene más instrucciones de las que caben en 1 byte (256 opcodes).
        Cuando la CPU lee el opcode 0xCB, sabe que el siguiente byte debe
        interpretarse con una tabla diferente de instrucciones.
        
        El prefijo CB permite acceder a 256 instrucciones adicionales:
        - 0x00-0x3F: Rotaciones y shifts (RLC, RRC, RL, RR, SLA, SRA, SRL, SWAP)
        - 0x40-0x7F: BIT b, r (Test bit)
        - 0x80-0xBF: RES b, r (Reset bit)
        - 0xC0-0xFF: SET b, r (Set bit)
        
        Proceso:
        1. Leer el siguiente byte (opcode CB)
        2. Buscar en la tabla CB (_cb_opcode_table)
        3. Ejecutar la instrucción correspondiente
        4. Sumar los ciclos (normalmente 2 M-Cycles para BIT)
        
        Returns:
            Número de M-Cycles consumidos (normalmente 2 para BIT)
            
        Raises:
            NotImplementedError: Si el opcode CB no está implementado
            
        Fuente: Pan Docs - CPU Instruction Set (CB Prefix)
        """
        # Leer el opcode CB (siguiente byte después de 0xCB)
        cb_opcode = self.fetch_byte()
        
        logger.debug(f"CB Prefix -> CB Opcode=0x{cb_opcode:02X}")
        
        # Buscar handler en la tabla CB
        handler = self._cb_opcode_table.get(cb_opcode)
        if handler is None:
            raise NotImplementedError(
                f"CB Opcode 0x{cb_opcode:02X} no implementado en PC=0x{self.registers.get_pc():04X}"
            )
        
        # Ejecutar la instrucción CB
        return handler()
    
    def _bit(self, bit: int, value: int) -> None:
        """
        Helper genérico para la instrucción BIT (Test bit).
        
        Prueba si el bit `bit` del valor `value` es 0 o 1, y actualiza los flags
        según el resultado.
        
        Flags actualizados:
        - Z (Zero): 1 si el bit es 0, 0 si el bit es 1 (¡Inverso!)
        - N (Subtract): Siempre 0
        - H (Half-Carry): Siempre 1
        - C (Carry): NO SE TOCA (preservado)
        
        La lógica inversa de Z puede ser confusa:
        - Si el bit está encendido (1), Z=0 (no es cero)
        - Si el bit está apagado (0), Z=1 (es cero)
        
        Esto es porque BIT se usa típicamente con saltos condicionales:
        - BIT 7, H seguido de JR Z, label -> salta si el bit está apagado
        
        Args:
            bit: Número de bit a probar (0-7)
            value: Valor de 8 bits a probar
            
        Fuente: Pan Docs - CPU Instruction Set (BIT b, r)
        """
        value = value & 0xFF
        
        # Extraer el bit específico usando máscara
        bit_mask = 1 << bit
        bit_value = (value & bit_mask) >> bit
        
        # Actualizar flags
        # Z: 1 si el bit es 0, 0 si el bit es 1 (lógica inversa)
        if bit_value == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en BIT
        self.registers.clear_flag(FLAG_N)
        
        # H: siempre 1 en BIT
        self.registers.set_flag(FLAG_H)
        
        # C: NO SE TOCA (preservado)
    
    def _op_cb_bit_7_h(self) -> int:
        """
        BIT 7, H (Test bit 7 of H) - CB Opcode 0x7C
        
        Prueba si el bit 7 del registro H está encendido o apagado.
        
        Esta instrucción es crítica para bucles de limpieza de memoria, donde
        se usa para verificar si un puntero ha llegado a un límite (típicamente
        cuando H alcanza 0x80 o más, indicando que se ha completado una región).
        
        Flags:
        - Z: 1 si bit 7 está apagado, 0 si está encendido
        - N: 0 (siempre)
        - H: 1 (siempre)
        - C: Preservado (no cambia)
        
        Ejemplo de uso típico:
        ```
        loop:
            LD (HL+), A    ; Escribir y avanzar puntero
            BIT 7, H       ; Probar bit 7 de H
            JR Z, loop     ; Continuar si bit 7 está apagado (H < 0x80)
        ```
        
        Returns:
            2 M-Cycles (fetch CB prefix + fetch CB opcode + execute)
            
        Fuente: Pan Docs - CPU Instruction Set (BIT 7, H)
        """
        h_value = self.registers.get_h()
        self._bit(7, h_value)
        
        logger.debug(
            f"BIT 7, H -> H=0x{h_value:02X} "
            f"Z={self.registers.get_flag_z()} "
            f"H={self.registers.get_flag_h()} "
            f"N={self.registers.get_flag_n()}"
        )
        return 2
    
    # ========== Handlers de Comparación (CP) ==========
    
    def _op_cp_d8(self) -> int:
        """
        CP d8 (Compare immediate value with A) - Opcode 0xFE
        
        Compara el siguiente byte de memoria con el registro A.
        
        Esta instrucción es fundamental para la lógica condicional en juegos.
        Se usa para tomar decisiones: "¿A == valor?", "¿A < valor?", etc.
        
        La comparación es una resta "fantasma": calcula A - d8, actualiza los flags
        según el resultado, pero NO modifica el registro A.
        
        Flags:
        - Z: 1 si A == d8 (iguales)
        - N: 1 (siempre, es una resta)
        - H: 1 si hubo borrow del nibble bajo
        - C: 1 si A < d8 (hubo borrow)
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set (CP d8)
        """
        operand = self.fetch_byte()
        self._cp(operand)
        logger.debug(
            f"CP 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_cp_hl_ptr(self) -> int:
        """
        CP (HL) (Compare value at (HL) with A) - Opcode 0xBE
        
        Compara el valor en la dirección de memoria apuntada por HL con el registro A.
        
        Similar a CP d8 pero lee el valor a comparar de la memoria en lugar de
        un operando inmediato. Útil para comparar A con valores en arrays o buffers.
        
        La comparación es una resta "fantasma": calcula A - (HL), actualiza los flags
        según el resultado, pero NO modifica el registro A.
        
        Flags:
        - Z: 1 si A == (HL) (iguales)
        - N: 1 (siempre, es una resta)
        - H: 1 si hubo borrow del nibble bajo
        - C: 1 si A < (HL) (hubo borrow)
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (CP (HL))
        """
        hl_addr = self.registers.get_hl()
        value = self.mmu.read_byte(hl_addr)
        self._cp(value)
        logger.debug(
            f"CP (HL) -> A=0x{self.registers.get_a():02X} (HL)=0x{value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2

    # ========== Handlers de Incremento/Decremento de 16 bits ==========
    
    def _op_inc_bc(self) -> int:
        """
        INC BC (Increment BC) - Opcode 0x03
        
        Incrementa el par de registros BC en 1.
        
        CRÍTICO: INC de 16 bits NO afecta a ningún flag. Esta es una diferencia
        clave con respecto a INC de 8 bits (que sí afecta a Z, N, H).
        
        Se usa comúnmente en bucles para avanzar contadores sin corromper
        el estado de flags de una comparación anterior.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (INC BC)
        """
        current_bc = self.registers.get_bc()
        new_bc = (current_bc + 1) & 0xFFFF
        self.registers.set_bc(new_bc)
        logger.debug(f"INC BC -> BC=0x{current_bc:04X} -> 0x{new_bc:04X}")
        return 2
    
    def _op_inc_de(self) -> int:
        """
        INC DE (Increment DE) - Opcode 0x13
        
        Incrementa el par de registros DE en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (INC DE)
        """
        current_de = self.registers.get_de()
        new_de = (current_de + 1) & 0xFFFF
        self.registers.set_de(new_de)
        logger.debug(f"INC DE -> DE=0x{current_de:04X} -> 0x{new_de:04X}")
        return 2
    
    def _op_inc_hl(self) -> int:
        """
        INC HL (Increment HL) - Opcode 0x23
        
        Incrementa el par de registros HL en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (INC HL)
        """
        current_hl = self.registers.get_hl()
        new_hl = (current_hl + 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"INC HL -> HL=0x{current_hl:04X} -> 0x{new_hl:04X}")
        return 2
    
    def _op_inc_sp(self) -> int:
        """
        INC SP (Increment Stack Pointer) - Opcode 0x33
        
        Incrementa el Stack Pointer (SP) en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (INC SP)
        """
        current_sp = self.registers.get_sp()
        new_sp = (current_sp + 1) & 0xFFFF
        self.registers.set_sp(new_sp)
        logger.debug(f"INC SP -> SP=0x{current_sp:04X} -> 0x{new_sp:04X}")
        return 2
    
    def _op_dec_bc(self) -> int:
        """
        DEC BC (Decrement BC) - Opcode 0x0B
        
        Decrementa el par de registros BC en 1.
        
        CRÍTICO: DEC de 16 bits NO afecta a ningún flag. Esta es una diferencia
        clave con respecto a DEC de 8 bits (que sí afecta a Z, N, H).
        
        Se usa comúnmente en bucles para decrementar contadores sin corromper
        el estado de flags de una comparación anterior.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (DEC BC)
        """
        current_bc = self.registers.get_bc()
        new_bc = (current_bc - 1) & 0xFFFF
        self.registers.set_bc(new_bc)
        logger.debug(f"DEC BC -> BC=0x{current_bc:04X} -> 0x{new_bc:04X}")
        return 2
    
    def _op_dec_de(self) -> int:
        """
        DEC DE (Decrement DE) - Opcode 0x1B
        
        Decrementa el par de registros DE en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (DEC DE)
        """
        current_de = self.registers.get_de()
        new_de = (current_de - 1) & 0xFFFF
        self.registers.set_de(new_de)
        logger.debug(f"DEC DE -> DE=0x{current_de:04X} -> 0x{new_de:04X}")
        return 2
    
    def _op_dec_hl(self) -> int:
        """
        DEC HL (Decrement HL) - Opcode 0x2B
        
        Decrementa el par de registros HL en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (DEC HL)
        """
        current_hl = self.registers.get_hl()
        new_hl = (current_hl - 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"DEC HL -> HL=0x{current_hl:04X} -> 0x{new_hl:04X}")
        return 2
    
    def _op_dec_sp(self) -> int:
        """
        DEC SP (Decrement Stack Pointer) - Opcode 0x3B
        
        Decrementa el Stack Pointer (SP) en 1.
        NO afecta a ningún flag.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (DEC SP)
        """
        current_sp = self.registers.get_sp()
        new_sp = (current_sp - 1) & 0xFFFF
        self.registers.set_sp(new_sp)
        logger.debug(f"DEC SP -> SP=0x{current_sp:04X} -> 0x{new_sp:04X}")
        return 2

    # ========== Handlers de Aritmética de 16 bits (ADD HL, rr) ==========
    
    def _add_hl_16bit(self, value: int) -> None:
        """
        Helper para ADD HL, rr (suma un valor de 16 bits a HL).
        
        CRÍTICO: Esta operación tiene un comportamiento especial con los flags:
        - Z: NO SE TOCA (se mantiene como estaba)
        - N: Siempre 0 (es una suma)
        - H: Se activa si hay carry del bit 11 al 12 (Half-Carry de 12 bits)
        - C: Se activa si hay carry del bit 15 (overflow de 16 bits)
        
        El Half-Carry se calcula en los 12 bits bajos (no en 8 como en ADD de 8 bits).
        Esto es porque estamos trabajando con valores de 16 bits, pero el hardware
        verifica el desbordamiento del nibble de 12 bits (bits 0-11).
        
        Args:
            value: Valor de 16 bits a sumar a HL (se enmascara automáticamente)
            
        Fórmulas:
        - Half-Carry: (HL & 0xFFF) + (value & 0xFFF) > 0xFFF
        - Carry: (HL + value) > 0xFFFF
        
        Fuente: Pan Docs - CPU Flags (ADD HL, rr instruction behavior)
        """
        hl = self.registers.get_hl()
        value = value & 0xFFFF
        
        # Calcular resultado
        result = hl + value
        
        # Actualizar HL (wrap-around de 16 bits)
        self.registers.set_hl(result)
        
        # Actualizar flags
        # Z: NO SE TOCA (peculiaridad crítica de ADD HL)
        # N: siempre 0 en suma
        self.registers.clear_flag(FLAG_N)
        
        # H: Half-Carry (carry del bit 11 al 12)
        # Verificamos si la suma de los 12 bits bajos excede 0xFFF
        if ((hl & 0xFFF) + (value & 0xFFF)) > 0xFFF:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Carry (overflow de 16 bits)
        if result > 0xFFFF:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    def _op_add_hl_bc(self) -> int:
        """
        ADD HL, BC (Add BC to HL) - Opcode 0x09
        
        Suma el par BC al par HL y almacena el resultado en HL.
        
        Actualiza flags H y C, pero NO toca Z.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (ADD HL, BC)
        """
        bc_value = self.registers.get_bc()
        old_hl = self.registers.get_hl()
        self._add_hl_16bit(bc_value)
        new_hl = self.registers.get_hl()
        logger.debug(
            f"ADD HL, BC -> HL=0x{old_hl:04X} + BC=0x{bc_value:04X} = 0x{new_hl:04X} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_add_hl_de(self) -> int:
        """
        ADD HL, DE (Add DE to HL) - Opcode 0x19
        
        Suma el par DE al par HL y almacena el resultado en HL.
        
        Actualiza flags H y C, pero NO toca Z.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (ADD HL, DE)
        """
        de_value = self.registers.get_de()
        old_hl = self.registers.get_hl()
        self._add_hl_16bit(de_value)
        new_hl = self.registers.get_hl()
        logger.debug(
            f"ADD HL, DE -> HL=0x{old_hl:04X} + DE=0x{de_value:04X} = 0x{new_hl:04X} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_add_hl_hl(self) -> int:
        """
        ADD HL, HL (Add HL to HL / Double HL) - Opcode 0x29
        
        Suma HL a sí mismo (efectivamente duplica HL).
        
        Actualiza flags H y C, pero NO toca Z.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (ADD HL, HL)
        """
        hl_value = self.registers.get_hl()
        old_hl = hl_value
        self._add_hl_16bit(hl_value)
        new_hl = self.registers.get_hl()
        logger.debug(
            f"ADD HL, HL -> HL=0x{old_hl:04X} * 2 = 0x{new_hl:04X} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_add_hl_sp(self) -> int:
        """
        ADD HL, SP (Add SP to HL) - Opcode 0x39
        
        Suma el Stack Pointer (SP) al par HL y almacena el resultado en HL.
        
        Actualiza flags H y C, pero NO toca Z.
        
        Returns:
            2 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (ADD HL, SP)
        """
        sp_value = self.registers.get_sp()
        old_hl = self.registers.get_hl()
        self._add_hl_16bit(sp_value)
        new_hl = self.registers.get_hl()
        logger.debug(
            f"ADD HL, SP -> HL=0x{old_hl:04X} + SP=0x{sp_value:04X} = 0x{new_hl:04X} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2

    # ========== Handlers de Retornos Condicionales ==========
    
    def _op_ret_nz(self) -> int:
        """
        RET NZ (Return if Not Zero) - Opcode 0xC0
        
        Retorna de una subrutina solo si el flag Z está desactivado (Z == 0).
        
        Si la condición se cumple (Z == 0):
        - POP dirección de retorno de la pila
        - Saltar a esa dirección (establecer PC)
        - Consume 5 M-Cycles (20 T-Cycles)
        
        Si la condición NO se cumple (Z == 1):
        - No hace nada, continúa ejecución normal
        - Consume 2 M-Cycles (8 T-Cycles)
        
        Returns:
            5 M-Cycles si retorna, 2 M-Cycles si no retorna
            
        Fuente: Pan Docs - Instruction Set (RET NZ)
        """
        if not self.registers.get_flag_z():
            # Condición verdadera: retornar
            return_addr = self._pop_word()
            self.registers.set_pc(return_addr)
            logger.debug(
                f"RET NZ (TAKEN) -> PC=0x{return_addr:04X} (SP=0x{self.registers.get_sp():04X})"
            )
            return 5  # 5 M-Cycles cuando se toma el retorno
        else:
            # Condición falsa: no retornar
            logger.debug("RET NZ (NOT TAKEN) Z flag set")
            return 2  # 2 M-Cycles cuando no se toma el retorno
    
    def _op_ret_z(self) -> int:
        """
        RET Z (Return if Zero) - Opcode 0xC8
        
        Retorna de una subrutina solo si el flag Z está activado (Z == 1).
        
        Returns:
            5 M-Cycles si retorna, 2 M-Cycles si no retorna
            
        Fuente: Pan Docs - Instruction Set (RET Z)
        """
        if self.registers.get_flag_z():
            # Condición verdadera: retornar
            return_addr = self._pop_word()
            self.registers.set_pc(return_addr)
            logger.debug(
                f"RET Z (TAKEN) -> PC=0x{return_addr:04X} (SP=0x{self.registers.get_sp():04X})"
            )
            return 5
        else:
            # Condición falsa: no retornar
            logger.debug("RET Z (NOT TAKEN) Z flag not set")
            return 2
    
    def _op_ret_nc(self) -> int:
        """
        RET NC (Return if Not Carry) - Opcode 0xD0
        
        Retorna de una subrutina solo si el flag C está desactivado (C == 0).
        
        Returns:
            5 M-Cycles si retorna, 2 M-Cycles si no retorna
            
        Fuente: Pan Docs - Instruction Set (RET NC)
        """
        if not self.registers.get_flag_c():
            # Condición verdadera: retornar
            return_addr = self._pop_word()
            self.registers.set_pc(return_addr)
            logger.debug(
                f"RET NC (TAKEN) -> PC=0x{return_addr:04X} (SP=0x{self.registers.get_sp():04X})"
            )
            return 5
        else:
            # Condición falsa: no retornar
            logger.debug("RET NC (NOT TAKEN) C flag set")
            return 2
    
    def _op_ret_c(self) -> int:
        """
        RET C (Return if Carry) - Opcode 0xD8
        
        Retorna de una subrutina solo si el flag C está activado (C == 1).
        
        Returns:
            5 M-Cycles si retorna, 2 M-Cycles si no retorna
            
        Fuente: Pan Docs - Instruction Set (RET C)
        """
        if self.registers.get_flag_c():
            # Condición verdadera: retornar
            return_addr = self._pop_word()
            self.registers.set_pc(return_addr)
            logger.debug(
                f"RET C (TAKEN) -> PC=0x{return_addr:04X} (SP=0x{self.registers.get_sp():04X})"
            )
            return 5
        else:
            # Condición falsa: no retornar
            logger.debug("RET C (NOT TAKEN) C flag not set")
            return 2

