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
        
        # Halted: Estado de bajo consumo de la CPU
        # Cuando HALT está activo, la CPU deja de ejecutar instrucciones hasta que
        # ocurre una interrupción (si IME está activado) o se despierta manualmente.
        # La CPU consume 1 ciclo por cada tick mientras está en HALT (espera activa).
        self.halted: bool = False
        
        # Tabla de despacho (Dispatch Table) para opcodes
        # Mapea cada opcode a su función manejadora
        # Esto es más escalable que if/elif y compatible con Python 3.9+
        self._opcode_table: dict[int, Callable[[], int]] = {
            0x00: self._op_nop,
            0x06: self._op_ld_b_d8,
            0x0E: self._op_ld_c_d8,
            0x16: self._op_ld_d_d8,
            0x1E: self._op_ld_e_d8,
            0x26: self._op_ld_h_d8,
            0x2E: self._op_ld_l_d8,
            0x36: self._op_ld_hl_ptr_d8,
            0x3E: self._op_ld_a_d8,
            0xC6: self._op_add_a_d8,
            0xCE: self._op_adc_a_d8,      # ADC A, d8
            0xD6: self._op_sub_d8,
            0xDE: self._op_sbc_a_d8,      # SBC A, d8
            0xE6: self._op_and_d8,        # AND d8
            0xEE: self._op_xor_d8,        # XOR d8
            0xF6: self._op_or_d8,         # OR d8
            # Rotaciones rápidas del acumulador
            0x07: self._op_rlca,       # RLCA (Rotate Left Circular Accumulator)
            0x0F: self._op_rrca,       # RRCA (Rotate Right Circular Accumulator)
            0x17: self._op_rla,        # RLA (Rotate Left Accumulator through Carry)
            0x1F: self._op_rra,        # RRA (Rotate Right Accumulator through Carry)
            # Saltos (Jumps)
            0xC3: self._op_jp_nn,      # JP nn (Jump absolute)
            0xC2: self._op_jp_nz_nn,   # JP NZ, nn (Jump if Not Zero)
            0xCA: self._op_jp_z_nn,    # JP Z, nn (Jump if Zero)
            0xD2: self._op_jp_nc_nn,   # JP NC, nn (Jump if Not Carry)
            0xDA: self._op_jp_c_nn,    # JP C, nn (Jump if Carry)
            0xE9: self._op_jp_hl,      # JP (HL) (Jump to address in HL)
            0x18: self._op_jr_e,       # JR e (Jump relative unconditional)
            0x20: self._op_jr_nz_e,    # JR NZ, e (Jump relative if Not Zero)
            0x28: self._op_jr_z_e,     # JR Z, e (Jump relative if Zero)
            0x30: self._op_jr_nc_e,    # JR NC, e (Jump relative if Not Carry)
            0x38: self._op_jr_c_e,     # JR C, e (Jump relative if Carry)
            # Stack (Pila)
            0xC5: self._op_push_bc,    # PUSH BC
            0xC1: self._op_pop_bc,     # POP BC
            0xD5: self._op_push_de,    # PUSH DE
            0xD1: self._op_pop_de,     # POP DE
            0xE5: self._op_push_hl,    # PUSH HL
            0xE1: self._op_pop_hl,     # POP HL
            0xF5: self._op_push_af,    # PUSH AF
            0xF1: self._op_pop_af,     # POP AF
            0xCD: self._op_call_nn,     # CALL nn
            0xC4: self._op_call_nz_nn,  # CALL NZ, nn (Call if Not Zero)
            0xCC: self._op_call_z_nn,   # CALL Z, nn (Call if Zero)
            0xD4: self._op_call_nc_nn,  # CALL NC, nn (Call if Not Carry)
            0xDC: self._op_call_c_nn,   # CALL C, nn (Call if Carry)
            0xC9: self._op_ret,         # RET
            0xD9: self._op_reti,        # RETI (Return from Interrupt)
            # Control de Interrupciones
            0xF3: self._op_di,          # DI (Disable Interrupts)
            0xFB: self._op_ei,          # EI (Enable Interrupts)
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
            0x3A: self._op_ldd_a_hl_ptr,   # LD A, (HL-) (LDD A, (HL))
            0x0A: self._op_ld_a_bc_ptr,    # LD A, (BC)
            0x1A: self._op_ld_a_de_ptr,    # LD A, (DE)
            0x02: self._op_ld_bc_ptr_a,    # LD (BC), A
            0x12: self._op_ld_de_ptr_a,    # LD (DE), A
            0xEA: self._op_ld_nn_ptr_a,    # LD (nn), A (direccionamiento directo)
            0xFA: self._op_ld_a_nn_ptr,    # LD A, (nn) (direccionamiento directo)
            # Incremento/Decremento de 8 bits
            0x04: self._op_inc_b,          # INC B
            0x05: self._op_dec_b,          # DEC B
            0x0C: self._op_inc_c,          # INC C
            0x0D: self._op_dec_c,          # DEC C
            0x14: self._op_inc_d,          # INC D
            0x15: self._op_dec_d,          # DEC D
            0x1C: self._op_inc_e,          # INC E
            0x1D: self._op_dec_e,          # DEC E
            0x24: self._op_inc_h,          # INC H
            0x25: self._op_dec_h,          # DEC H
            0x2C: self._op_inc_l,          # INC L
            0x2D: self._op_dec_l,          # DEC L
            0x34: self._op_inc_hl_ptr,     # INC (HL)
            0x35: self._op_dec_hl_ptr,     # DEC (HL)
            0x3C: self._op_inc_a,          # INC A
            0x3D: self._op_dec_a,          # DEC A
            # I/O Access (LDH - Load High)
            0xE0: self._op_ldh_n_a,       # LDH (n), A
            0xE2: self._op_ld_c_a,        # LD (C), A (escribe A en 0xFF00 + C)
            0xF0: self._op_ldh_a_n,       # LDH A, (n)
            0xF2: self._op_ld_a_c,        # LD A, (C) (lee de 0xFF00 + C a A)
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
            # Aritmética de pila con offset (SP+r8)
            0xE8: self._op_add_sp_r8,      # ADD SP, r8
            0xF8: self._op_ld_hl_sp_r8,    # LD HL, SP+r8
            0xF9: self._op_ld_sp_hl,       # LD SP, HL
            # Retornos condicionales
            0xC0: self._op_ret_nz,         # RET NZ
            0xC8: self._op_ret_z,          # RET Z
            0xD0: self._op_ret_nc,         # RET NC
            0xD8: self._op_ret_c,          # RET C
            # Instrucciones misceláneas
            0x27: self._op_daa,            # DAA (Decimal Adjust Accumulator)
            0x2F: self._op_cpl,            # CPL (Complement Accumulator)
            0x37: self._op_scf,            # SCF (Set Carry Flag)
            0x3F: self._op_ccf,            # CCF (Complement Carry Flag)
            # RST (Restart) - Vectores de interrupción
            0xC7: self._op_rst_00,         # RST 00h
            0xCF: self._op_rst_08,         # RST 08h
            0xD7: self._op_rst_10,         # RST 10h
            0xDF: self._op_rst_18,         # RST 18h
            0xE7: self._op_rst_20,         # RST 20h
            0xEF: self._op_rst_28,         # RST 28h
            0xF7: self._op_rst_30,         # RST 30h
            0xFF: self._op_rst_38,         # RST 38h
        }
        
        # Tabla de despacho para opcodes CB (Extended Instructions)
        # El prefijo CB permite acceder a 256 instrucciones adicionales
        # Rango 0x00-0x3F: Rotaciones y shifts (RLC, RRC, RL, RR, SLA, SRA, SRL, SWAP)
        # Rango 0x40-0x7F: BIT b, r (Test bit)
        # Rango 0x80-0xBF: RES b, r (Reset bit)
        # Rango 0xC0-0xFF: SET b, r (Set bit)
        self._cb_opcode_table: dict[int, Callable[[], int]] = {}
        
        # Inicializar tabla CB para rango 0x00-0x3F (rotaciones y shifts)
        self._init_cb_shifts_table()
        
        # Inicializar tabla CB para rango 0x40-0xFF (BIT, RES, SET)
        self._init_cb_bit_res_set_table()
        
        # Inicializar handlers de transferencias LD r, r' (bloque 0x40-0x7F)
        # Esto se hace después de definir todos los métodos helper
        self._init_ld_handlers()
        
        # Inicializar handlers del bloque ALU (0x80-0xBF)
        self._init_alu_handlers()
        
        logger.info("CPU inicializada")
    
    def _init_ld_handlers(self) -> None:
        """
        Inicializa los handlers para todas las transferencias LD r, r' del bloque 0x40-0x7F.
        
        Este método se llama desde __init__ pero los handlers se crearán de forma lazy
        la primera vez que se acceda a ellos, para poder usar los métodos helper que
        se definen después de __init__.
        
        Por ahora, solo reservamos el espacio en la tabla. Los handlers se crearán
        cuando se definan los métodos helper usando un método auxiliar.
        
        Fuente: Pan Docs - CPU Instruction Set (LD r, r' encoding)
        """
        # Los handlers se inicializarán de forma lazy cuando se acceda a ellos
        # por primera vez, usando _init_ld_handler_lazy
        pass
    
    def _init_alu_handlers(self) -> None:
        """
        Inicializa los handlers para el bloque ALU completo (0x80-0xBF).
        
        Este bloque contiene 64 opcodes organizados en 8 filas de 8 operaciones:
        - 0x80-0x87: ADD A, r
        - 0x88-0x8F: ADC A, r
        - 0x90-0x97: SUB A, r
        - 0x98-0x9F: SBC A, r
        - 0xA0-0xA7: AND A, r
        - 0xA8-0xAF: XOR A, r
        - 0xB0-0xB7: OR A, r
        - 0xB8-0xBF: CP A, r
        
        Donde r es: B(0), C(1), D(2), E(3), H(4), L(5), (HL)(6), A(7)
        
        El patrón de codificación es:
        - Bits 6-3: Operación (ADD=0, ADC=1, SUB=2, SBC=3, AND=4, XOR=5, OR=6, CP=7)
        - Bits 2-0: Registro (B=0, C=1, D=2, E=3, H=4, L=5, (HL)=6, A=7)
        
        Fuente: Pan Docs - CPU Instruction Set (ALU block encoding)
        """
        # Operaciones ALU en orden
        operations = [
            self._add,   # 0x80-0x87: ADD
            self._adc,   # 0x88-0x8F: ADC
            self._sub,   # 0x90-0x97: SUB
            self._sbc,   # 0x98-0x9F: SBC
            self._and,   # 0xA0-0xA7: AND
            self._xor,   # 0xA8-0xAF: XOR
            self._or,    # 0xB0-0xB7: OR
            self._cp,    # 0xB8-0xBF: CP
        ]
        
        # Nombres de registros para logging
        reg_names = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
        
        # Generar todos los opcodes del bloque
        for op_idx, op_func in enumerate(operations):
            for reg_idx in range(8):
                # Calcular opcode: base (0x80) + (op_idx * 8) + reg_idx
                opcode = 0x80 + (op_idx * 8) + reg_idx
                
                # Capturar variables en el closure correctamente
                op_func_ref = op_func
                reg_idx_ref = reg_idx
                reg_name_ref = reg_names[reg_idx]
                
                # Crear handler para este opcode específico
                def make_handler(op_func_inner, reg_idx_inner, reg_name_inner):
                    def handler() -> int:
                        # Obtener valor del registro
                        if reg_idx_inner == 6:  # (HL) - Memoria indirecta
                            hl_addr = self.registers.get_hl()
                            value = self.mmu.read_byte(hl_addr)
                            op_func_inner(value)
                            op_name = op_func_inner.__name__.upper().replace('_', ' ')
                            logger.debug(
                                f"{op_name} A, (HL) -> "
                                f"A=0x{self.registers.get_a():02X} (HL)=0x{value:02X}"
                            )
                            return 2  # Acceso a memoria = 2 M-Cycles
                        else:
                            # Obtener valor del registro usando el helper existente
                            value = self._get_register_value(reg_idx_inner)
                            op_func_inner(value)
                            op_name = op_func_inner.__name__.upper().replace('_', ' ')
                            logger.debug(
                                f"{op_name} A, {reg_name_inner} -> "
                                f"A=0x{self.registers.get_a():02X}"
                            )
                            return 1  # Registro = 1 M-Cycle
                    return handler
                
                # Crear y registrar handler
                handler = make_handler(op_func_ref, reg_idx_ref, reg_name_ref)
                self._opcode_table[opcode] = handler
    
    def _init_ld_handler_lazy(self, opcode: int) -> None:
        """
        Inicializa un handler de LD r, r' de forma lazy cuando se accede por primera vez.
        
        Args:
            opcode: Opcode del bloque 0x40-0x7F (excepto 0x76)
        """
        # Decodificar opcode: opcode = (dest_code << 3) | src_code
        dest_code = (opcode >> 3) & 0x07
        src_code = opcode & 0x07
        
        # Crear handler usando _op_ld_r_r (que ya está definido cuando se llama este método)
        def handler() -> int:
            return self._op_ld_r_r(dest_code, src_code)
        
        self._opcode_table[opcode] = handler

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

    def handle_interrupts(self) -> int:
        """
        Maneja las interrupciones pendientes según la prioridad del hardware.
        
        El flujo de interrupción en la Game Boy requiere 3 condiciones simultáneas:
        1. IME (Interrupt Master Enable) debe ser True
        2. El bit correspondiente en IE (Interrupt Enable, 0xFFFF) debe estar activo
        3. El bit correspondiente en IF (Interrupt Flag, 0xFF0F) debe estar activo
        
        Cuando se acepta una interrupción:
        1. IME se desactiva automáticamente (para evitar interrupciones anidadas inmediatas)
        2. Se limpia el bit correspondiente en IF (acknowledgement)
        3. Se guarda PC en la pila (PUSH PC)
        4. Se salta al vector de interrupción (PC = vector)
        5. Consume 5 M-Cycles
        
        Vectores de Interrupción (prioridad de mayor a menor):
        - Bit 0: V-Blank -> 0x0040 (Prioridad más alta)
        - Bit 1: LCD STAT -> 0x0048
        - Bit 2: Timer -> 0x0050
        - Bit 3: Serial -> 0x0058
        - Bit 4: Joypad -> 0x0060 (Prioridad más baja)
        
        Despertar de HALT:
        Si la CPU está en HALT y hay interrupciones pendientes (en IE y IF),
        la CPU debe despertar (halted = False), incluso si IME es False.
        Esto permite que el código pueda verificar manualmente las interrupciones
        mediante polling de IF después de HALT.
        
        Returns:
            Número de M-Cycles consumidos (5 si se procesó una interrupción, 0 si no)
            
        Fuente: Pan Docs - Interrupts, HALT behavior
        """
        # Leer registros de interrupciones desde MMU
        ie = self.mmu.read_byte(0xFFFF)  # Interrupt Enable
        if_reg = self.mmu.read_byte(0xFF0F)  # Interrupt Flag
        
        # Calcular interrupciones pendientes: IE & IF (solo los 5 bits bajos importan)
        pending = (ie & if_reg & 0x1F) & 0x1F
        
        # DIAGNÓSTICO CRÍTICO: Si hay petición V-Blank en IF, identificar por qué no se atiende
        if (if_reg & 0x01):  # Si hay V-Blank pendiente en hardware
            is_enabled_in_ie = (ie & 0x01) != 0
            if not is_enabled_in_ie:
                logging.debug(f"⚠️ V-Blank IGNORADO: No habilitado en IE (IE={ie:02X})")
            elif not self.ime:
                logging.debug(f"⚠️ V-Blank IGNORADO: IME desactivado (DI ejecutado)")
            else:
                # Si llega aquí, debería saltar (pero pending podría ser 0 si IE no tiene el bit)
                pass
        
        # DIAGNÓSTICO: Log cuando IF tiene bits activados pero pending == 0 (IE sin activar)
        if if_reg != 0 and pending == 0:
            logger.debug(
                f"IF activado pero IE no: IF=0x{if_reg:02X} IE=0x{ie:02X} "
                f"IME={self.ime} (interrupciones deshabilitadas en IE)"
            )
        
        # Si no hay interrupciones pendientes, no hacer nada
        if pending == 0:
            return 0
        
        # DIAGNÓSTICO: Log cuando hay interrupciones pendientes
        # Esto ayuda a identificar por qué la CPU no acepta interrupciones
        logger.debug(
            f"Intento de Interrupción: IME={self.ime} IE=0x{ie:02X} IF=0x{if_reg:02X} "
            f"pending=0x{pending:02X} halted={self.halted}"
        )
        
        # Despertar de HALT si hay interrupciones pendientes (incluso si IME es False)
        if self.halted:
            self.halted = False
            logger.debug("HALT: Despertando por interrupción pendiente en IF/IE")
        
        # Si IME no está activado, no procesar la interrupción (solo despertamos)
        if not self.ime:
            logger.debug(f"Interrupción pendiente ignorada: IME=False (IE=0x{ie:02X}, IF=0x{if_reg:02X})")
            return 0
        
        # Buscar el bit de menor peso activo (mayor prioridad)
        # Prioridad: Bit 0 (V-Blank) > Bit 1 (STAT) > Bit 2 (Timer) > Bit 3 (Serial) > Bit 4 (Joypad)
        interrupt_bit = 0
        interrupt_vector = 0x0040  # V-Blank por defecto
        
        if pending & 0x01:  # Bit 0: V-Blank
            interrupt_bit = 0
            interrupt_vector = 0x0040
        elif pending & 0x02:  # Bit 1: LCD STAT
            interrupt_bit = 1
            interrupt_vector = 0x0048
        elif pending & 0x04:  # Bit 2: Timer
            interrupt_bit = 2
            interrupt_vector = 0x0050
        elif pending & 0x08:  # Bit 3: Serial
            interrupt_bit = 3
            interrupt_vector = 0x0058
        elif pending & 0x10:  # Bit 4: Joypad
            interrupt_bit = 4
            interrupt_vector = 0x0060
        
        # Log de interrupción
        interrupt_names = ["V-Blank", "LCD STAT", "Timer", "Serial", "Joypad"]
        logger.info(f"INTERRUPT: {interrupt_names[interrupt_bit]} triggered -> 0x{interrupt_vector:04X}")
        
        # Procesar la interrupción:
        # 1. Desactivar IME (evitar interrupciones anidadas inmediatas)
        self.ime = False
        
        # 2. Limpiar el bit correspondiente en IF (acknowledgement)
        new_if = if_reg & (~(1 << interrupt_bit)) & 0x1F
        self.mmu.write_byte(0xFF0F, new_if)
        
        # 3. Guardar PC actual en la pila (PUSH PC)
        current_pc = self.registers.get_pc()
        self._push_word(current_pc)
        
        # 4. Saltar al vector de interrupción
        self.registers.set_pc(interrupt_vector)
        
        # DIAGNÓSTICO: Log cuando se despacha una interrupción (crítico para debugging)
        logger.info(
            f"⚡ INTERRUPT DISPATCHED! Vector: {interrupt_vector:04X} | "
            f"PC Previo: {current_pc:04X} | Tipo: {interrupt_names[interrupt_bit]}"
        )
        
        # 5. Retornar 5 M-Cycles consumidos
        return 5
    
    def step(self) -> int:
        """
        Ejecuta una sola instrucción del ciclo Fetch-Decode-Execute.
        
        Pasos:
        1. Manejar interrupciones: Comprobar si hay interrupciones pendientes y procesarlas.
           Si se procesa una interrupción, retornar inmediatamente (no ejecutar instrucción normal).
        2. Verificar estado HALT: Si la CPU está en HALT, consumir 1 ciclo y no ejecutar fetch.
        3. Fetch: Lee el opcode en la dirección apuntada por PC
        4. Increment: Avanza PC (se hace dentro del fetch_byte)
        5. Decode/Execute: Identifica el opcode con match/case y ejecuta
        
        Returns:
            Número de M-Cycles que tomó ejecutar la instrucción o procesar la interrupción
            
        Raises:
            NotImplementedError: Si el opcode no está implementado
            
        Fuente: Pan Docs - CPU Instruction Set, Interrupts, HALT behavior
        """
        # Manejar interrupciones AL PRINCIPIO (antes de ejecutar cualquier instrucción)
        # Esto simula el comportamiento del hardware: la CPU comprueba interrupciones
        # entre cada instrucción, antes del fetch del siguiente opcode.
        interrupt_cycles = self.handle_interrupts()
        if interrupt_cycles > 0:
            # Si se procesó una interrupción, la CPU gastó 5 ciclos saltando al vector.
            # No ejecutamos la instrucción normal, retornamos inmediatamente.
            return interrupt_cycles
        
        # Verificar estado HALT (después de manejar interrupciones)
        # Si handle_interrupts() encontró interrupciones pendientes, ya despertó la CPU.
        if self.halted:
            # CPU en HALT, esperando interrupciones
            # Consumir 1 ciclo (espera activa) y NO ejecutar fetch
            return 1
        
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
            # Inicialización lazy: si es un opcode del bloque 0x40-0x7F (excepto 0x76),
            # inicializarlo dinámicamente
            if 0x40 <= opcode <= 0x7F and opcode != 0x76:
                self._init_ld_handler_lazy(opcode)
                handler = self._opcode_table.get(opcode)
            # HALT (0x76) también se inicializa de forma lazy
            elif opcode == 0x76:
                self._opcode_table[0x76] = self._op_halt
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
    
    def _adc(self, value: int) -> None:
        """
        Suma un valor al registro A con carry (ADC: Add with Carry).
        
        ADC es como ADD, pero incluye el flag Carry en la suma:
        A = A + value + Carry
        
        Esta operación es crítica para aritmética de múltiples bytes (16/32 bits).
        Permite encadenar sumas manteniendo el carry de operaciones anteriores.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (es una suma)
        - H (Half-Carry): Si hubo carry del bit 3 al 4 (nibble bajo)
        - C (Carry): Si hubo carry del bit 7 (overflow de 8 bits)
        
        Args:
            value: Valor a sumar (8 bits, se enmascara automáticamente)
            
        Fórmulas:
        - Resultado: A + value + (1 si C está activo, 0 si no)
        - Half-Carry: (A & 0xF) + (value & 0xF) + carry > 0xF
        - Carry: (A + value + carry) > 0xFF
        
        Fuente: Pan Docs - CPU Instruction Set (ADC instruction)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Obtener carry actual (1 si está activo, 0 si no)
        carry = 1 if self.registers.get_flag_c() else 0
        
        # Calcular resultado: A + value + carry
        result = a + value + carry
        
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
        # Verificamos si la suma de los nibbles bajos + carry excede 0xF
        if ((a & 0xF) + (value & 0xF) + carry) > 0xF:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Carry (overflow de 8 bits)
        if result > 0xFF:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    def _sbc(self, value: int) -> None:
        """
        Resta un valor del registro A con borrow (SBC: Subtract with Carry).
        
        SBC es como SUB, pero incluye el flag Carry en la resta:
        A = A - value - Carry
        
        Esta operación es crítica para aritmética de múltiples bytes (16/32 bits).
        Permite encadenar restas manteniendo el borrow de operaciones anteriores.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 1 (es una resta)
        - H (Half-Borrow): Si hubo borrow del bit 4 al 3 (nibble bajo)
        - C (Borrow): Si hubo borrow del bit 7 (underflow de 8 bits)
        
        Args:
            value: Valor a restar (8 bits, se enmascara automáticamente)
            
        Fórmulas:
        - Resultado: A - value - (1 si C está activo, 0 si no)
        - Half-Borrow: (A & 0xF) - (value & 0xF) - carry < 0
        - Borrow: A < (value + carry)
        
        Fuente: Pan Docs - CPU Instruction Set (SBC instruction)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Obtener carry actual (1 si está activo, 0 si no)
        # En restas, el carry se interpreta como "borrow"
        carry = 1 if self.registers.get_flag_c() else 0
        
        # Calcular resultado: A - value - carry
        result = a - value - carry
        
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
        if (a & 0xF) < ((value & 0xF) + carry):
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        
        # C: Borrow (underflow de 8 bits)
        if a < (value + carry):
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    def _and(self, value: int) -> None:
        """
        Realiza la operación lógica AND entre el registro A y un valor.
        
        AND es una operación bit a bit: cada bit del resultado es 1 solo si
        ambos bits correspondientes de A y value son 1.
        
        CRÍTICO: En la Game Boy, AND tiene un comportamiento especial con el flag H:
        **H siempre se pone a 1** después de una operación AND, independientemente
        del resultado. Este es un "quirk" del hardware real.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (no es una resta)
        - H (Half-Carry): **Siempre 1** (quirk del hardware Game Boy)
        - C (Carry): Siempre 0 (no hay carry en operaciones lógicas)
        
        Args:
            value: Valor a combinar con A (8 bits, se enmascara automáticamente)
            
        Fuente: Pan Docs - CPU Instruction Set (AND instruction, H flag quirk)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado: A AND value
        result = a & value
        
        # Actualizar registro A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: resultado es cero
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_N)
        
        # H: **SIEMPRE 1** en AND (quirk del hardware Game Boy)
        self.registers.set_flag(FLAG_H)
        
        # C: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_C)
    
    def _or(self, value: int) -> None:
        """
        Realiza la operación lógica OR entre el registro A y un valor.
        
        OR es una operación bit a bit: cada bit del resultado es 1 si
        al menos uno de los bits correspondientes de A o value es 1.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (no es una resta)
        - H (Half-Carry): Siempre 0 (OR no tiene carry)
        - C (Carry): Siempre 0 (no hay carry en operaciones lógicas)
        
        Args:
            value: Valor a combinar con A (8 bits, se enmascara automáticamente)
            
        Fuente: Pan Docs - CPU Instruction Set (OR instruction)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado: A OR value
        result = a | value
        
        # Actualizar registro A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: resultado es cero
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_N)
        
        # H: siempre 0 en OR
        self.registers.clear_flag(FLAG_H)
        
        # C: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_C)
    
    def _xor(self, value: int) -> None:
        """
        Realiza la operación lógica XOR entre el registro A y un valor.
        
        XOR es una operación bit a bit: cada bit del resultado es 1 si
        los bits correspondientes de A y value son diferentes.
        
        Flags actualizados:
        - Z (Zero): Si el resultado es 0
        - N (Subtract): Siempre 0 (no es una resta)
        - H (Half-Carry): Siempre 0 (XOR no tiene carry)
        - C (Carry): Siempre 0 (no hay carry en operaciones lógicas)
        
        Args:
            value: Valor a combinar con A (8 bits, se enmascara automáticamente)
            
        Fuente: Pan Docs - CPU Instruction Set (XOR instruction)
        """
        a = self.registers.get_a()
        value = value & 0xFF
        
        # Calcular resultado: A XOR value
        result = a ^ value
        
        # Actualizar registro A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: resultado es cero
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_N)
        
        # H: siempre 0 en XOR
        self.registers.clear_flag(FLAG_H)
        
        # C: siempre 0 en operaciones lógicas
        self.registers.clear_flag(FLAG_C)
    
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
    
    def _op_ld_c_d8(self) -> int:
        """
        LD C, d8 (Load immediate value into C) - Opcode 0x0E
        
        Carga el siguiente byte inmediato de memoria en el registro C.
        Este patrón es idéntico al de LD B, d8 y LD A, d8: el operando
        de 8 bits está embebido justo después del opcode.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operando)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, n)
        """
        operand = self.fetch_byte()
        self.registers.set_c(operand)
        logger.debug(f"LD C, 0x{operand:02X} -> C=0x{self.registers.get_c():02X}")
        return 2
    
    def _op_ld_d_d8(self) -> int:
        """
        LD D, d8 (Load immediate value into D) - Opcode 0x16
        
        Carga el siguiente byte inmediato de memoria en el registro D.
        Instrucción típica para inicializar contadores o punteros de trabajo.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operando)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, n)
        """
        operand = self.fetch_byte()
        self.registers.set_d(operand)
        logger.debug(f"LD D, 0x{operand:02X} -> D=0x{self.registers.get_d():02X}")
        return 2
    
    def _op_ld_e_d8(self) -> int:
        """
        LD E, d8 (Load immediate value into E) - Opcode 0x1E
        
        Carga el siguiente byte inmediato de memoria en el registro E.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operando)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, n)
        """
        operand = self.fetch_byte()
        self.registers.set_e(operand)
        logger.debug(f"LD E, 0x{operand:02X} -> E=0x{self.registers.get_e():02X}")
        return 2
    
    def _op_ld_h_d8(self) -> int:
        """
        LD H, d8 (Load immediate value into H) - Opcode 0x26
        
        Carga el siguiente byte inmediato de memoria en el registro H.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operando)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, n)
        """
        operand = self.fetch_byte()
        self.registers.set_h(operand)
        logger.debug(f"LD H, 0x{operand:02X} -> H=0x{self.registers.get_h():02X}")
        return 2
    
    def _op_ld_l_d8(self) -> int:
        """
        LD L, d8 (Load immediate value into L) - Opcode 0x2E
        
        Carga el siguiente byte inmediato de memoria en el registro L.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operando)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, n)
        """
        operand = self.fetch_byte()
        self.registers.set_l(operand)
        logger.debug(f"LD L, 0x{operand:02X} -> L=0x{self.registers.get_l():02X}")
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
    
    def _op_adc_a_d8(self) -> int:
        """
        ADC A, d8 (Add with Carry immediate value to A) - Opcode 0xCE
        
        Suma el siguiente byte de memoria al registro A, más el flag Carry.
        Actualiza flags Z, N, H, C según el resultado.
        
        Esta instrucción es útil para aritmética de precisión múltiple,
        donde el carry de una operación anterior se propaga a la siguiente.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._adc(operand)
        logger.debug(
            f"ADC A, 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} H={self.registers.get_flag_h()} "
            f"C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_sbc_a_d8(self) -> int:
        """
        SBC A, d8 (Subtract with Carry immediate value from A) - Opcode 0xDE
        
        Resta el siguiente byte de memoria del registro A, menos el flag Carry.
        Actualiza flags Z, N, H, C según el resultado.
        
        Esta instrucción es útil para aritmética de precisión múltiple,
        donde el borrow de una operación anterior se propaga a la siguiente.
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._sbc(operand)
        logger.debug(
            f"SBC A, 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()} C={self.registers.get_flag_c()}"
        )
        return 2
    
    def _op_and_d8(self) -> int:
        """
        AND d8 (Logical AND immediate value with A) - Opcode 0xE6
        
        Realiza una operación AND bit a bit entre el registro A y el siguiente
        byte de memoria. El resultado se almacena en A.
        
        Esta instrucción es útil para:
        - Aislar bits específicos (máscaras de bits)
        - Comprobar si ciertos flags están activos
        - Limpiar bits no deseados
        
        Flags:
        - Z: 1 si el resultado es 0
        - N: 0 (siempre)
        - H: 1 (siempre) - Quirk del hardware Game Boy
        - C: 0 (siempre)
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._and(operand)
        logger.debug(
            f"AND 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()} H={self.registers.get_flag_h()}"
        )
        return 2
    
    def _op_or_d8(self) -> int:
        """
        OR d8 (Logical OR immediate value with A) - Opcode 0xF6
        
        Realiza una operación OR bit a bit entre el registro A y el siguiente
        byte de memoria. El resultado se almacena en A.
        
        Esta instrucción es útil para:
        - Activar bits específicos
        - Combinar valores de flags
        - Establecer máscaras de bits
        
        Flags:
        - Z: 1 si el resultado es 0
        - N: 0 (siempre)
        - H: 0 (siempre)
        - C: 0 (siempre)
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._or(operand)
        logger.debug(
            f"OR 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()}"
        )
        return 2
    
    def _op_xor_d8(self) -> int:
        """
        XOR d8 (Logical XOR immediate value with A) - Opcode 0xEE
        
        Realiza una operación XOR bit a bit entre el registro A y el siguiente
        byte de memoria. El resultado se almacena en A.
        
        Esta instrucción es útil para:
        - Invertir bits específicos
        - Comparar valores (XOR con mismo valor da 0)
        - Generar números pseudoaleatorios (usando XOR con valores fijos)
        
        Flags:
        - Z: 1 si el resultado es 0
        - N: 0 (siempre)
        - H: 0 (siempre)
        - C: 0 (siempre)
        
        Returns:
            2 M-Cycles (fetch opcode + fetch operand)
            
        Fuente: Pan Docs - Instruction Set
        """
        operand = self.fetch_byte()
        self._xor(operand)
        logger.debug(
            f"XOR 0x{operand:02X} -> A=0x{self.registers.get_a():02X} "
            f"Z={self.registers.get_flag_z()}"
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

    def _op_jp_nz_nn(self) -> int:
        """
        JP NZ, nn (Jump if Not Zero) - Opcode 0xC2
        
        Salto absoluto condicional. Lee una dirección de 16 bits y salta solo
        si el flag Z (Zero) está desactivado (Z == 0).
        
        Timing condicional:
        - Si Z == 0 (condición verdadera): 4 M-Cycles (salta)
        - Si Z == 1 (condición falsa): 3 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si condición falsa, 4 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (JP NZ, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (Z flag = 0, es decir, Zero flag desactivado)
        if not self.registers.get_flag_z():
            # Condición verdadera: ejecutar salto
            self.registers.set_pc(target_addr)
            logger.debug(
                f"JP NZ, 0x{target_addr:04X} (TAKEN) -> PC=0x{target_addr:04X}"
            )
            return 4
        else:
            # Condición falsa: no ejecutar salto, solo avanzar PC
            logger.debug(f"JP NZ, 0x{target_addr:04X} (NOT TAKEN) -> Z=1")
            return 3

    def _op_jp_z_nn(self) -> int:
        """
        JP Z, nn (Jump if Zero) - Opcode 0xCA
        
        Salto absoluto condicional. Lee una dirección de 16 bits y salta solo
        si el flag Z (Zero) está activado (Z == 1).
        
        Timing condicional:
        - Si Z == 1 (condición verdadera): 4 M-Cycles (salta)
        - Si Z == 0 (condición falsa): 3 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si condición falsa, 4 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (JP Z, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (Z flag = 1, es decir, Zero flag activado)
        if self.registers.get_flag_z():
            # Condición verdadera: ejecutar salto
            self.registers.set_pc(target_addr)
            logger.debug(
                f"JP Z, 0x{target_addr:04X} (TAKEN) -> PC=0x{target_addr:04X}"
            )
            return 4
        else:
            # Condición falsa: no ejecutar salto, solo avanzar PC
            logger.debug(f"JP Z, 0x{target_addr:04X} (NOT TAKEN) -> Z=0")
            return 3

    def _op_jp_nc_nn(self) -> int:
        """
        JP NC, nn (Jump if Not Carry) - Opcode 0xD2
        
        Salto absoluto condicional. Lee una dirección de 16 bits y salta solo
        si el flag C (Carry) está desactivado (C == 0).
        
        Timing condicional:
        - Si C == 0 (condición verdadera): 4 M-Cycles (salta)
        - Si C == 1 (condición falsa): 3 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si condición falsa, 4 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (JP NC, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (C flag = 0, es decir, Carry flag desactivado)
        if not self.registers.get_flag_c():
            # Condición verdadera: ejecutar salto
            self.registers.set_pc(target_addr)
            logger.debug(
                f"JP NC, 0x{target_addr:04X} (TAKEN) -> PC=0x{target_addr:04X}"
            )
            return 4
        else:
            # Condición falsa: no ejecutar salto, solo avanzar PC
            logger.debug(f"JP NC, 0x{target_addr:04X} (NOT TAKEN) -> C=1")
            return 3

    def _op_jp_c_nn(self) -> int:
        """
        JP C, nn (Jump if Carry) - Opcode 0xDA
        
        Salto absoluto condicional. Lee una dirección de 16 bits y salta solo
        si el flag C (Carry) está activado (C == 1).
        
        Timing condicional:
        - Si C == 1 (condición verdadera): 4 M-Cycles (salta)
        - Si C == 0 (condición falsa): 3 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si condición falsa, 4 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (JP C, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (C flag = 1, es decir, Carry flag activado)
        if self.registers.get_flag_c():
            # Condición verdadera: ejecutar salto
            self.registers.set_pc(target_addr)
            logger.debug(
                f"JP C, 0x{target_addr:04X} (TAKEN) -> PC=0x{target_addr:04X}"
            )
            return 4
        else:
            # Condición falsa: no ejecutar salto, solo avanzar PC
            logger.debug(f"JP C, 0x{target_addr:04X} (NOT TAKEN) -> C=0")
            return 3

    def _op_jp_hl(self) -> int:
        """
        JP (HL) (Jump to address in HL) - Opcode 0xE9
        
        Salto indirecto usando el valor del par de registros HL como dirección destino.
        Es equivalente a JP HL, pero la sintaxis oficial es JP (HL).
        
        Esta instrucción es útil para implementar tablas de saltos o llamadas
        a funciones mediante punteros.
        
        Returns:
            1 M-Cycle (solo lectura de registros, no memoria)
            
        Fuente: Pan Docs - Instruction Set (JP (HL))
        """
        target_addr = self.registers.get_hl()
        self.registers.set_pc(target_addr)
        logger.debug(f"JP (HL) -> HL=0x{target_addr:04X}, PC=0x{target_addr:04X}")
        return 1

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

    def _op_jr_z_e(self) -> int:
        """
        JR Z, e (Jump Relative if Zero) - Opcode 0x28
        
        Salto relativo condicional. Lee un byte con signo (offset) y salta solo
        si el flag Z (Zero) está activado (Z == 1).
        
        El offset funciona igual que en JR e (complemento a 2).
        
        Timing condicional:
        - Si Z == 1 (condición verdadera): 3 M-Cycles (salta)
        - Si Z == 0 (condición falsa): 2 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si salta, 2 M-Cycles si no salta
            
        Fuente: Pan Docs - Instruction Set (JR Z, e)
        """
        offset = self._read_signed_byte()
        
        # Verificar condición: Z flag debe estar activado (Z == 1)
        if self.registers.get_flag_z():
            # Condición verdadera: ejecutar salto
            current_pc = self.registers.get_pc()
            new_pc = (current_pc + offset) & 0xFFFF
            self.registers.set_pc(new_pc)
            logger.debug(
                f"JR Z, {offset:+d} (TAKEN) "
                f"PC: 0x{current_pc:04X} -> 0x{new_pc:04X}"
            )
            return 3  # 3 M-Cycles si salta
        else:
            # Condición falsa: no saltar, continuar ejecución
            logger.debug(f"JR Z, {offset:+d} (NOT TAKEN) Z flag not set")
            return 2  # 2 M-Cycles si no salta

    def _op_jr_nc_e(self) -> int:
        """
        JR NC, e (Jump Relative if Not Carry) - Opcode 0x30
        
        Salto relativo condicional. Lee un byte con signo (offset) y salta solo
        si el flag C (Carry) está desactivado (C == 0).
        
        El offset funciona igual que en JR e (complemento a 2).
        
        Timing condicional:
        - Si C == 0 (condición verdadera): 3 M-Cycles (salta)
        - Si C == 1 (condición falsa): 2 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si salta, 2 M-Cycles si no salta
            
        Fuente: Pan Docs - Instruction Set (JR NC, e)
        """
        offset = self._read_signed_byte()
        
        # Verificar condición: C flag debe estar desactivado (C == 0)
        if not self.registers.get_flag_c():
            # Condición verdadera: ejecutar salto
            current_pc = self.registers.get_pc()
            new_pc = (current_pc + offset) & 0xFFFF
            self.registers.set_pc(new_pc)
            logger.debug(
                f"JR NC, {offset:+d} (TAKEN) "
                f"PC: 0x{current_pc:04X} -> 0x{new_pc:04X}"
            )
            return 3  # 3 M-Cycles si salta
        else:
            # Condición falsa: no saltar, continuar ejecución
            logger.debug(f"JR NC, {offset:+d} (NOT TAKEN) C flag set")
            return 2  # 2 M-Cycles si no salta

    def _op_jr_c_e(self) -> int:
        """
        JR C, e (Jump Relative if Carry) - Opcode 0x38
        
        Salto relativo condicional. Lee un byte con signo (offset) y salta solo
        si el flag C (Carry) está activado (C == 1).
        
        El offset funciona igual que en JR e (complemento a 2).
        
        Timing condicional:
        - Si C == 1 (condición verdadera): 3 M-Cycles (salta)
        - Si C == 0 (condición falsa): 2 M-Cycles (no salta, solo lee)
        
        Returns:
            3 M-Cycles si salta, 2 M-Cycles si no salta
            
        Fuente: Pan Docs - Instruction Set (JR C, e)
        """
        offset = self._read_signed_byte()
        
        # Verificar condición: C flag debe estar activado (C == 1)
        if self.registers.get_flag_c():
            # Condición verdadera: ejecutar salto
            current_pc = self.registers.get_pc()
            new_pc = (current_pc + offset) & 0xFFFF
            self.registers.set_pc(new_pc)
            logger.debug(
                f"JR C, {offset:+d} (TAKEN) "
                f"PC: 0x{current_pc:04X} -> 0x{new_pc:04X}"
            )
            return 3  # 3 M-Cycles si salta
        else:
            # Condición falsa: no saltar, continuar ejecución
            logger.debug(f"JR C, {offset:+d} (NOT TAKEN) C flag not set")
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
    
    def _op_push_de(self) -> int:
        """
        PUSH DE (Push DE onto stack) - Opcode 0xD5
        
        Empuja el par de registros DE en la pila.
        El Stack Pointer (SP) se decrementa antes de escribir.
        
        Returns:
            4 M-Cycles (fetch opcode + 2 operaciones de memoria para escribir 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (PUSH DE)
        """
        de_value = self.registers.get_de()
        self._push_word(de_value)
        logger.debug(f"PUSH DE (0x{de_value:04X}) -> SP=0x{self.registers.get_sp():04X}")
        return 4
    
    def _op_pop_de(self) -> int:
        """
        POP DE (Pop from stack into DE) - Opcode 0xD1
        
        Saca un valor de 16 bits de la pila y lo carga en el par DE.
        
        Returns:
            3 M-Cycles (fetch opcode + 2 operaciones de memoria para leer 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (POP DE)
        """
        value = self._pop_word()
        self.registers.set_de(value)
        logger.debug(f"POP DE <- 0x{value:04X} (SP=0x{self.registers.get_sp():04X})")
        return 3
    
    def _op_push_hl(self) -> int:
        """
        PUSH HL (Push HL onto stack) - Opcode 0xE5
        
        Empuja el par de registros HL en la pila.
        El Stack Pointer (SP) se decrementa antes de escribir.
        
        Returns:
            4 M-Cycles (fetch opcode + 2 operaciones de memoria para escribir 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (PUSH HL)
        """
        hl_value = self.registers.get_hl()
        self._push_word(hl_value)
        logger.debug(f"PUSH HL (0x{hl_value:04X}) -> SP=0x{self.registers.get_sp():04X}")
        return 4
    
    def _op_pop_hl(self) -> int:
        """
        POP HL (Pop from stack into HL) - Opcode 0xE1
        
        Saca un valor de 16 bits de la pila y lo carga en el par HL.
        
        Returns:
            3 M-Cycles (fetch opcode + 2 operaciones de memoria para leer 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (POP HL)
        """
        value = self._pop_word()
        self.registers.set_hl(value)
        logger.debug(f"POP HL <- 0x{value:04X} (SP=0x{self.registers.get_sp():04X})")
        return 3
    
    def _op_push_af(self) -> int:
        """
        PUSH AF (Push AF onto stack) - Opcode 0xF5
        
        Empuja el par de registros AF en la pila.
        El Stack Pointer (SP) se decrementa antes de escribir.
        
        Returns:
            4 M-Cycles (fetch opcode + 2 operaciones de memoria para escribir 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (PUSH AF)
        """
        af_value = self.registers.get_af()
        self._push_word(af_value)
        logger.debug(f"PUSH AF (0x{af_value:04X}) -> SP=0x{self.registers.get_sp():04X}")
        return 4
    
    def _op_pop_af(self) -> int:
        """
        POP AF (Pop from stack into AF) - Opcode 0xF1
        
        Saca un valor de 16 bits de la pila y lo carga en el par AF.
        
        CRÍTICO: Los 4 bits bajos del registro F SIEMPRE deben ser cero en hardware real.
        Al recuperar F de la pila, debemos aplicar la máscara 0xF0 para limpiar los bits bajos.
        Si no hacemos esto, juegos como Tetris fallan al comprobar flags porque los bits bajos
        pueden contener "basura" que afecta las comparaciones.
        
        Returns:
            3 M-Cycles (fetch opcode + 2 operaciones de memoria para leer 2 bytes)
            
        Fuente: Pan Docs - Instruction Set (POP AF), Hardware quirks (F register mask)
        """
        value = self._pop_word()
        # CRÍTICO: Aplicar máscara 0xF0 a F antes de guardarlo
        # Esto simula el comportamiento del hardware real donde los bits bajos de F
        # siempre son 0. Si no hacemos esto, los flags pueden tener valores inválidos.
        self.registers.set_af(value)
        logger.debug(
            f"POP AF <- 0x{value:04X} -> A=0x{self.registers.get_a():02X} "
            f"F=0x{self.registers.get_f():02X} (SP=0x{self.registers.get_sp():04X})"
        )
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

    def _op_call_nz_nn(self) -> int:
        """
        CALL NZ, nn (Call if Not Zero) - Opcode 0xC4
        
        Llama a una subrutina solo si el flag Z (Zero) está desactivado.
        
        Si Z=0 (condición verdadera):
            - Ejecuta CALL normalmente (6 M-Cycles)
        Si Z=1 (condición falsa):
            - Lee la dirección pero no la usa (3 M-Cycles)
            - PC avanza normalmente
        
        Returns:
            3 M-Cycles si condición falsa, 6 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (CALL NZ, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (Z flag = 0, es decir, Zero flag desactivado)
        if not self.registers.get_flag_z():
            # Condición verdadera: ejecutar CALL
            return_addr = self.registers.get_pc()
            self._push_word(return_addr)
            self.registers.set_pc(target_addr)
            logger.debug(
                f"CALL NZ, 0x{target_addr:04X} (TAKEN) -> "
                f"PUSH return 0x{return_addr:04X}, PC=0x{target_addr:04X}"
            )
            return 6
        else:
            # Condición falsa: no ejecutar CALL, solo avanzar PC
            logger.debug(f"CALL NZ, 0x{target_addr:04X} (NOT TAKEN) -> Z=1")
            return 3

    def _op_call_z_nn(self) -> int:
        """
        CALL Z, nn (Call if Zero) - Opcode 0xCC
        
        Llama a una subrutina solo si el flag Z (Zero) está activado.
        
        Si Z=1 (condición verdadera):
            - Ejecuta CALL normalmente (6 M-Cycles)
        Si Z=0 (condición falsa):
            - Lee la dirección pero no la usa (3 M-Cycles)
            - PC avanza normalmente
        
        Returns:
            3 M-Cycles si condición falsa, 6 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (CALL Z, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (Z flag = 1, es decir, Zero flag activado)
        if self.registers.get_flag_z():
            # Condición verdadera: ejecutar CALL
            return_addr = self.registers.get_pc()
            self._push_word(return_addr)
            self.registers.set_pc(target_addr)
            logger.debug(
                f"CALL Z, 0x{target_addr:04X} (TAKEN) -> "
                f"PUSH return 0x{return_addr:04X}, PC=0x{target_addr:04X}"
            )
            return 6
        else:
            # Condición falsa: no ejecutar CALL, solo avanzar PC
            logger.debug(f"CALL Z, 0x{target_addr:04X} (NOT TAKEN) -> Z=0")
            return 3

    def _op_call_nc_nn(self) -> int:
        """
        CALL NC, nn (Call if Not Carry) - Opcode 0xD4
        
        Llama a una subrutina solo si el flag C (Carry) está desactivado.
        
        Si C=0 (condición verdadera):
            - Ejecuta CALL normalmente (6 M-Cycles)
        Si C=1 (condición falsa):
            - Lee la dirección pero no la usa (3 M-Cycles)
            - PC avanza normalmente
        
        Returns:
            3 M-Cycles si condición falsa, 6 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (CALL NC, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (C flag = 0, es decir, Carry flag desactivado)
        if not self.registers.get_flag_c():
            # Condición verdadera: ejecutar CALL
            return_addr = self.registers.get_pc()
            self._push_word(return_addr)
            self.registers.set_pc(target_addr)
            logger.debug(
                f"CALL NC, 0x{target_addr:04X} (TAKEN) -> "
                f"PUSH return 0x{return_addr:04X}, PC=0x{target_addr:04X}"
            )
            return 6
        else:
            # Condición falsa: no ejecutar CALL, solo avanzar PC
            logger.debug(f"CALL NC, 0x{target_addr:04X} (NOT TAKEN) -> C=1")
            return 3

    def _op_call_c_nn(self) -> int:
        """
        CALL C, nn (Call if Carry) - Opcode 0xDC
        
        Llama a una subrutina solo si el flag C (Carry) está activado.
        
        Si C=1 (condición verdadera):
            - Ejecuta CALL normalmente (6 M-Cycles)
        Si C=0 (condición falsa):
            - Lee la dirección pero no la usa (3 M-Cycles)
            - PC avanza normalmente
        
        Returns:
            3 M-Cycles si condición falsa, 6 M-Cycles si condición verdadera
            
        Fuente: Pan Docs - Instruction Set (CALL C, nn)
        """
        # Leer dirección objetivo (siempre se lee, incluso si no se usa)
        target_addr = self.fetch_word()
        
        # Comprobar condición (C flag = 1, es decir, Carry flag activado)
        if self.registers.get_flag_c():
            # Condición verdadera: ejecutar CALL
            return_addr = self.registers.get_pc()
            self._push_word(return_addr)
            self.registers.set_pc(target_addr)
            logger.debug(
                f"CALL C, 0x{target_addr:04X} (TAKEN) -> "
                f"PUSH return 0x{return_addr:04X}, PC=0x{target_addr:04X}"
            )
            return 6
        else:
            # Condición falsa: no ejecutar CALL, solo avanzar PC
            logger.debug(f"CALL C, 0x{target_addr:04X} (NOT TAKEN) -> C=0")
            return 3

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

    def _op_reti(self) -> int:
        """
        RETI (Return from Interrupt) - Opcode 0xD9
        
        Retorna de una rutina de interrupción (ISR - Interrupt Service Routine).
        Es igual que RET pero además reactiva IME (Interrupt Master Enable).
        
        Cuando una interrupción se procesa, IME se desactiva automáticamente para
        evitar interrupciones anidadas. RETI reactiva IME para permitir que las
        interrupciones vuelvan a funcionar después de salir de la rutina.
        
        Proceso:
        1. POP dirección de retorno de la pila
        2. Saltar a esa dirección (establecer PC = dirección de retorno)
        3. Reactivar IME (IME = True)
        
        Returns:
            4 M-Cycles (fetch opcode + pop 2 bytes de la pila)
            
        Fuente: Pan Docs - CPU Instruction Set (RETI)
        """
        # Recuperar dirección de retorno de la pila
        return_addr = self._pop_word()
        
        # Saltar a la dirección de retorno
        self.registers.set_pc(return_addr)
        
        # Reactivar IME (esto es lo que diferencia RETI de RET)
        self.ime = True
        
        logger.debug(
            f"RETI -> PC=0x{return_addr:04X}, IME=True "
            f"(SP=0x{self.registers.get_sp():04X})"
        )
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
    
    def _op_ld_hl_ptr_d8(self) -> int:
        """
        LD (HL), d8 (Load immediate value into memory pointed by HL) - Opcode 0x36
        
        Carga un valor inmediato de 8 bits directamente en la dirección de memoria
        apuntada por HL, sin pasar por el acumulador A.
        
        Este modo de direccionamiento es muy potente para bucles de inicialización
        de memoria, porque evita el paso intermedio de cargar el valor en un registro.
        
        Proceso:
        1. Leer operando inmediato (d8) usando fetch_byte()
        2. Escribir ese valor en la dirección HL: MMU[HL] = d8
        
        Returns:
            3 M-Cycles (fetch opcode + fetch operando + escritura en memoria)
            
        Fuente: Pan Docs - CPU Instruction Set (LD (HL), n)
        """
        hl_addr = self.registers.get_hl()
        operand = self.fetch_byte()
        self.mmu.write_byte(hl_addr, operand & 0xFF)
        logger.debug(f"LD (HL), 0x{operand:02X} -> (0x{hl_addr:04X}) = 0x{self.mmu.read_byte(hl_addr):02X}")
        return 3
    
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
    
    def _op_ldd_a_hl_ptr(self) -> int:
        """
        LD A, (HL-) / LDD A, (HL) (Load from (HL) into A and decrement HL) - Opcode 0x3A
        
        Lee el valor de la dirección apuntada por HL y lo carga en A, luego decrementa HL.
        
        Es el complemento de LD (HL-), A. Útil para bucles de lectura rápida que recorren
        la memoria hacia atrás.
        
        Ejemplo:
        - HL = 0xC000
        - Memoria[0xC000] = 0x42
        - Ejecutar LD A, (HL-)
        - Resultado: A = 0x42, HL = 0xBFFF
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LDD A, (HL))
        """
        hl_addr = self.registers.get_hl()
        value = self.mmu.read_byte(hl_addr)
        self.registers.set_a(value)
        # Decrementar HL (wrap-around de 16 bits)
        new_hl = (hl_addr - 1) & 0xFFFF
        self.registers.set_hl(new_hl)
        logger.debug(f"LD A, (HL-) -> A = 0x{value:02X} from (0x{hl_addr:04X}), HL = 0x{new_hl:04X}")
        return 2
    
    def _op_ld_a_bc_ptr(self) -> int:
        """
        LD A, (BC) (Load from memory address pointed by BC into A) - Opcode 0x0A
        
        Lee un byte de la dirección de memoria apuntada por BC y lo carga en A.
        
        Es el gemelo de LD (BC), A: mientras que 0x02 escribe A en memoria,
        0x0A lee de memoria y lo guarda en A.
        
        Similar a LD A, (HL) pero usando BC como puntero. Útil para leer
        datos usando BC como contador o puntero secundario.
        
        Ejemplo:
        - BC = 0xC000
        - Memoria[0xC000] = 0x42
        - Ejecutar LD A, (BC)
        - Resultado: A = 0x42, BC sigue siendo 0xC000
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LD A, (BC))
        """
        bc_addr = self.registers.get_bc()
        value = self.mmu.read_byte(bc_addr)
        self.registers.set_a(value)
        logger.debug(f"LD A, (BC) -> A = 0x{value:02X} from (0x{bc_addr:04X})")
        return 2
    
    def _op_ld_a_de_ptr(self) -> int:
        """
        LD A, (DE) (Load from memory address pointed by DE into A) - Opcode 0x1A
        
        Lee un byte de la dirección de memoria apuntada por DE y lo carga en A.
        
        Es el gemelo de LD (DE), A: mientras que 0x12 escribe A en memoria,
        0x1A lee de memoria y lo guarda en A.
        
        Similar a LD A, (HL) pero usando DE como puntero. Útil para leer
        datos usando DE como puntero de origen en operaciones de copia.
        
        Ejemplo:
        - DE = 0xD000
        - Memoria[0xD000] = 0x55
        - Ejecutar LD A, (DE)
        - Resultado: A = 0x55, DE sigue siendo 0xD000
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LD A, (DE))
        """
        de_addr = self.registers.get_de()
        value = self.mmu.read_byte(de_addr)
        self.registers.set_a(value)
        logger.debug(f"LD A, (DE) -> A = 0x{value:02X} from (0x{de_addr:04X})")
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
    
    def _op_ld_nn_ptr_a(self) -> int:
        """
        LD (nn), A (Load A into absolute memory address) - Opcode 0xEA
        
        Escribe el valor del registro A en una dirección de memoria absoluta de 16 bits
        especificada directamente en el código (direccionamiento directo).
        
        A diferencia de LD (HL), A donde la dirección está en un registro, aquí la
        dirección viene escrita directamente en el código, justo después del opcode.
        Esto permite acceder a variables globales o registros de hardware específicos
        sin usar registros intermedios.
        
        Proceso:
        1. Lee los siguientes 2 bytes (dirección de 16 bits en Little-Endian)
        2. Escribe A en esa dirección
        
        Ejemplo:
        - En memoria: 0xEA 0x00 0xC0 (LD (0xC000), A)
        - A = 0x55
        - Resultado: Memoria[0xC000] = 0x55
        
        Returns:
            4 M-Cycles (fetch opcode + fetch 2 bytes de dirección + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LD (nn), A)
        """
        addr = self.fetch_word()
        a_value = self.registers.get_a()
        self.mmu.write_byte(addr, a_value)
        logger.debug(f"LD (0x{addr:04X}), A -> (0x{addr:04X}) = 0x{a_value:02X}")
        return 4
    
    def _op_ld_a_nn_ptr(self) -> int:
        """
        LD A, (nn) (Load from absolute memory address into A) - Opcode 0xFA
        
        Lee un byte de una dirección de memoria absoluta de 16 bits especificada
        directamente en el código (direccionamiento directo) y lo carga en A.
        
        Es el gemelo de LD (nn), A: mientras que 0xEA escribe A en memoria,
        0xFA lee de memoria y lo guarda en A.
        
        Proceso:
        1. Lee los siguientes 2 bytes (dirección de 16 bits en Little-Endian)
        2. Lee el byte de esa dirección
        3. Guarda el valor en A
        
        Ejemplo:
        - En memoria: 0xFA 0x00 0xC0 (LD A, (0xC000))
        - Memoria[0xC000] = 0x42
        - Resultado: A = 0x42
        
        Returns:
            4 M-Cycles (fetch opcode + fetch 2 bytes de dirección + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LD A, (nn))
        """
        addr = self.fetch_word()
        value = self.mmu.read_byte(addr)
        self.registers.set_a(value)
        logger.debug(f"LD A, (0x{addr:04X}) -> A = 0x{value:02X}")
        return 4
    
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
    
    def _op_inc_d(self) -> int:
        """
        INC D (Increment D) - Opcode 0x14
        
        Incrementa el registro D en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC D)
        """
        new_value = self._inc_n(self.registers.get_d())
        self.registers.set_d(new_value)
        logger.debug(
            f"INC D -> D=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_d(self) -> int:
        """
        DEC D (Decrement D) - Opcode 0x15
        
        Decrementa el registro D en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC D)
        """
        new_value = self._dec_n(self.registers.get_d())
        self.registers.set_d(new_value)
        logger.debug(
            f"DEC D -> D=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_e(self) -> int:
        """
        INC E (Increment E) - Opcode 0x1C
        
        Incrementa el registro E en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC E)
        """
        new_value = self._inc_n(self.registers.get_e())
        self.registers.set_e(new_value)
        logger.debug(
            f"INC E -> E=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_e(self) -> int:
        """
        DEC E (Decrement E) - Opcode 0x1D
        
        Decrementa el registro E en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC E)
        """
        new_value = self._dec_n(self.registers.get_e())
        self.registers.set_e(new_value)
        logger.debug(
            f"DEC E -> E=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_h(self) -> int:
        """
        INC H (Increment H) - Opcode 0x24
        
        Incrementa el registro H en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC H)
        """
        new_value = self._inc_n(self.registers.get_h())
        self.registers.set_h(new_value)
        logger.debug(
            f"INC H -> H=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_h(self) -> int:
        """
        DEC H (Decrement H) - Opcode 0x25
        
        Decrementa el registro H en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC H)
        """
        new_value = self._dec_n(self.registers.get_h())
        self.registers.set_h(new_value)
        logger.debug(
            f"DEC H -> H=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_l(self) -> int:
        """
        INC L (Increment L) - Opcode 0x2C
        
        Incrementa el registro L en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (INC L)
        """
        new_value = self._inc_n(self.registers.get_l())
        self.registers.set_l(new_value)
        logger.debug(
            f"INC L -> L=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_dec_l(self) -> int:
        """
        DEC L (Decrement L) - Opcode 0x2D
        
        Decrementa el registro L en 1.
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - Instruction Set (DEC L)
        """
        new_value = self._dec_n(self.registers.get_l())
        self.registers.set_l(new_value)
        logger.debug(
            f"DEC L -> L=0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 1
    
    def _op_inc_hl_ptr(self) -> int:
        """
        INC (HL) (Increment memory at HL) - Opcode 0x34
        
        Incrementa el valor en la dirección de memoria apuntada por HL en 1.
        Esta es una operación Read-Modify-Write:
        1. Lee el valor de memoria en (HL)
        2. Lo incrementa usando _inc_n (actualiza flags)
        3. Escribe el nuevo valor de vuelta en (HL)
        
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            3 M-Cycles (12 T-Cycles)
            - 1 M-Cycle: Read from (HL)
            - 1 M-Cycle: Write to (HL)
            - 1 M-Cycle: Internal operation
            
        Fuente: Pan Docs - Instruction Set (INC (HL))
        """
        hl_addr = self.registers.get_hl()
        current_value = self.mmu.read_byte(hl_addr)
        new_value = self._inc_n(current_value)
        self.mmu.write_byte(hl_addr, new_value)
        logger.debug(
            f"INC (HL) -> (0x{hl_addr:04X}) = 0x{current_value:02X} -> 0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 3
    
    def _op_dec_hl_ptr(self) -> int:
        """
        DEC (HL) (Decrement memory at HL) - Opcode 0x35
        
        Decrementa el valor en la dirección de memoria apuntada por HL en 1.
        Esta es una operación Read-Modify-Write:
        1. Lee el valor de memoria en (HL)
        2. Lo decrementa usando _dec_n (actualiza flags)
        3. Escribe el nuevo valor de vuelta en (HL)
        
        Actualiza flags Z, N, H. NO afecta al flag C.
        
        Returns:
            3 M-Cycles (12 T-Cycles)
            - 1 M-Cycle: Read from (HL)
            - 1 M-Cycle: Write to (HL)
            - 1 M-Cycle: Internal operation
            
        Fuente: Pan Docs - Instruction Set (DEC (HL))
        """
        hl_addr = self.registers.get_hl()
        current_value = self.mmu.read_byte(hl_addr)
        new_value = self._dec_n(current_value)
        self.mmu.write_byte(hl_addr, new_value)
        logger.debug(
            f"DEC (HL) -> (0x{hl_addr:04X}) = 0x{current_value:02X} -> 0x{new_value:02X} "
            f"Z={self.registers.get_flag_z()} N={self.registers.get_flag_n()} "
            f"H={self.registers.get_flag_h()}"
        )
        return 3
    
    # ========== Handlers de Rotaciones Rápidas del Acumulador ==========
    
    def _op_rlca(self) -> int:
        """
        RLCA (Rotate Left Circular Accumulator) - Opcode 0x07
        
        Rota el registro A hacia la izquierda de forma circular.
        El bit 7 sale y entra por el bit 0. El bit 7 también se copia al flag C.
        
        CRÍTICO: Estas rotaciones rápidas (0x07, 0x0F, 0x17, 0x1F) SIEMPRE ponen:
        - Z = 0 (nunca se activa, incluso si el resultado es 0)
        - N = 0
        - H = 0
        - C = bit 7 original (para RLCA) o bit 0 original (para RRCA)
        
        Esta es una diferencia clave con las rotaciones del prefijo CB (0xCB),
        donde Z se calcula normalmente según el resultado.
        
        Ejemplo:
        - A = 0x80 (10000000)
        - RLCA
        - A = 0x01 (00000001), C = 1
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (RLCA), Flags behavior
        """
        a = self.registers.get_a()
        
        # Extraer bit 7 (el que sale)
        bit7 = (a >> 7) & 0x01
        
        # Rotar: (a << 1) | bit7, enmascarar a 8 bits
        result = ((a << 1) | bit7) & 0xFF
        
        # Actualizar A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: SIEMPRE 0 en rotaciones rápidas (quirk del hardware)
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: siempre 0
        self.registers.clear_flag(FLAG_H)
        # C: bit 7 original
        if bit7:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"RLCA -> A=0x{a:02X} -> 0x{result:02X} "
            f"C={self.registers.get_flag_c()}"
        )
        return 1
    
    def _op_rrca(self) -> int:
        """
        RRCA (Rotate Right Circular Accumulator) - Opcode 0x0F
        
        Rota el registro A hacia la derecha de forma circular.
        El bit 0 sale y entra por el bit 7. El bit 0 también se copia al flag C.
        
        Flags: Z=0, N=0, H=0, C=bit 0 original
        
        Ejemplo:
        - A = 0x01 (00000001)
        - RRCA
        - A = 0x80 (10000000), C = 1
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (RRCA)
        """
        a = self.registers.get_a()
        
        # Extraer bit 0 (el que sale)
        bit0 = a & 0x01
        
        # Rotar: (a >> 1) | (bit0 << 7)
        result = ((a >> 1) | (bit0 << 7)) & 0xFF
        
        # Actualizar A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: SIEMPRE 0 en rotaciones rápidas
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: siempre 0
        self.registers.clear_flag(FLAG_H)
        # C: bit 0 original
        if bit0:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"RRCA -> A=0x{a:02X} -> 0x{result:02X} "
            f"C={self.registers.get_flag_c()}"
        )
        return 1
    
    def _op_rla(self) -> int:
        """
        RLA (Rotate Left Accumulator through Carry) - Opcode 0x17
        
        Rota el registro A hacia la izquierda a través del flag Carry.
        El bit 7 va al flag C, y el *antiguo* flag C entra en el bit 0.
        Es una rotación de 9 bits (8 bits de A + 1 bit de C).
        
        Flags: Z=0, N=0, H=0, C=bit 7 original
        
        Esta instrucción es crítica para generadores de números pseudo-aleatorios
        en juegos como Tetris, que usan RLA para generar secuencias aleatorias.
        
        Ejemplo:
        - A = 0x00, C = 1
        - RLA
        - A = 0x01, C = 0
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (RLA)
        """
        a = self.registers.get_a()
        
        # Obtener carry actual (1 si está activo, 0 si no)
        old_carry = 1 if self.registers.get_flag_c() else 0
        
        # Extraer bit 7 (el que sale)
        bit7 = (a >> 7) & 0x01
        
        # Rotar: (a << 1) | old_carry, enmascarar a 8 bits
        result = ((a << 1) | old_carry) & 0xFF
        
        # Actualizar A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: SIEMPRE 0 en rotaciones rápidas
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: siempre 0
        self.registers.clear_flag(FLAG_H)
        # C: bit 7 original
        if bit7:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"RLA -> A=0x{a:02X} -> 0x{result:02X} "
            f"C={self.registers.get_flag_c()} (old_carry={old_carry})"
        )
        return 1
    
    def _op_rra(self) -> int:
        """
        RRA (Rotate Right Accumulator through Carry) - Opcode 0x1F
        
        Rota el registro A hacia la derecha a través del flag Carry.
        El bit 0 va al flag C, y el *antiguo* flag C entra en el bit 7.
        Es una rotación de 9 bits (8 bits de A + 1 bit de C).
        
        Flags: Z=0, N=0, H=0, C=bit 0 original
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (RRA)
        """
        a = self.registers.get_a()
        
        # Obtener carry actual (1 si está activo, 0 si no)
        old_carry = 1 if self.registers.get_flag_c() else 0
        
        # Extraer bit 0 (el que sale)
        bit0 = a & 0x01
        
        # Rotar: (a >> 1) | (old_carry << 7)
        result = ((a >> 1) | (old_carry << 7)) & 0xFF
        
        # Actualizar A
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: SIEMPRE 0 en rotaciones rápidas
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: siempre 0
        self.registers.clear_flag(FLAG_H)
        # C: bit 0 original
        if bit0:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"RRA -> A=0x{a:02X} -> 0x{result:02X} "
            f"C={self.registers.get_flag_c()} (old_carry={old_carry})"
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
    
    def _op_ld_c_a(self) -> int:
        """
        LD (C), A (Load A into I/O port via C) - Opcode 0xE2
        
        Escribe el valor del registro A en la dirección (0xFF00 + C), donde C es
        el valor del registro C (0x00-0xFF).
        
        Esta es una variante optimizada de LDH (n), A que usa el registro C como
        offset en lugar de leer un byte inmediato. Es útil para inicializar múltiples
        registros de hardware en un bucle (incrementando C).
        
        Ejemplo:
        - A = 0x91
        - C = 0x40
        - Ejecutar LD (C), A
        - Resultado: Memoria[0xFF40] = 0x91 (LCDC)
        
        Returns:
            2 M-Cycles (fetch opcode + write to memory)
            
        Fuente: Pan Docs - Instruction Set (LD (C), A)
        """
        # Obtener valor del registro C
        c_value = self.registers.get_c()
        
        # Calcular dirección I/O: 0xFF00 + C
        io_addr = (0xFF00 + c_value) & 0xFFFF
        
        # Escribir A en la dirección I/O
        a_value = self.registers.get_a()
        self.mmu.write_byte(io_addr, a_value)
        
        logger.debug(
            f"LD (C), A -> (0x{io_addr:04X}) = 0x{a_value:02X} [C=0x{c_value:02X}]"
        )
        return 2
    
    def _op_ld_a_c(self) -> int:
        """
        LD A, (C) (Load from I/O port via C into A) - Opcode 0xF2
        
        Lee el valor de la dirección (0xFF00 + C) y lo carga en el registro A,
        donde C es el valor del registro C (0x00-0xFF).
        
        Es el complemento de LD (C), A. Permite leer de los registros de hardware
        usando C como offset dinámico.
        
        Ejemplo:
        - C = 0x41
        - Memoria[0xFF41] = 0x85 (STAT)
        - Ejecutar LD A, (C)
        - Resultado: A = 0x85
        
        Returns:
            2 M-Cycles (fetch opcode + read from memory)
            
        Fuente: Pan Docs - Instruction Set (LD A, (C))
        """
        # Obtener valor del registro C
        c_value = self.registers.get_c()
        
        # Calcular dirección I/O: 0xFF00 + C
        io_addr = (0xFF00 + c_value) & 0xFFFF
        
        # Leer valor de la dirección I/O y cargar en A
        value = self.mmu.read_byte(io_addr)
        self.registers.set_a(value)
        
        logger.debug(
            f"LD A, (C) -> A = 0x{value:02X} from (0x{io_addr:04X}) [C=0x{c_value:02X}]"
        )
        return 2
    
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
    
    def _cb_res(self, bit: int, value: int) -> int:
        """
        Helper genérico para RES (Reset bit).
        
        Apaga el bit `bit` del valor `value`, poniéndolo a 0.
        
        RES NO afecta a ningún flag. Solo modifica el dato.
        
        Args:
            bit: Número de bit a apagar (0-7)
            value: Valor de 8 bits a modificar
            
        Returns:
            Valor con el bit apagado (8 bits)
            
        Fuente: Pan Docs - CPU Instruction Set (RES b, r)
        """
        value = value & 0xFF
        
        # Crear máscara para apagar el bit: ~(1 << bit)
        # Ejemplo: bit=3 -> ~(0x08) = 0xF7
        bit_mask = ~(1 << bit) & 0xFF
        
        # Aplicar máscara: value & bit_mask
        result = value & bit_mask
        
        return result
    
    def _cb_set(self, bit: int, value: int) -> int:
        """
        Helper genérico para SET (Set bit).
        
        Enciende el bit `bit` del valor `value`, poniéndolo a 1.
        
        SET NO afecta a ningún flag. Solo modifica el dato.
        
        Args:
            bit: Número de bit a encender (0-7)
            value: Valor de 8 bits a modificar
            
        Returns:
            Valor con el bit encendido (8 bits)
            
        Fuente: Pan Docs - CPU Instruction Set (SET b, r)
        """
        value = value & 0xFF
        
        # Crear máscara para encender el bit: (1 << bit)
        # Ejemplo: bit=3 -> 0x08
        bit_mask = 1 << bit
        
        # Aplicar máscara: value | bit_mask
        result = value | bit_mask
        
        return result & 0xFF
    
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
    
    # ========== Helpers para Operaciones CB (Rotaciones, Shifts, SWAP) ==========
    
    def _cb_rlc(self, value: int) -> tuple[int, int]:
        """
        Rotate Left Circular - Helper genérico para CB RLC.
        
        Rota el valor hacia la izquierda de forma circular.
        El bit 7 sale y entra por el bit 0. El bit 7 también se copia al flag C.
        
        DIFERENCIA CRÍTICA con RLCA (0x07):
        - RLCA: Z=0 siempre (quirk del hardware)
        - CB RLC: Z se calcula según el resultado (si resultado==0, Z=1)
        
        Args:
            value: Valor de 8 bits a rotar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor rotado (8 bits)
            - carry: 1 si bit 7 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (RLC r)
        """
        value = value & 0xFF
        
        # Extraer bit 7 (el que sale)
        bit7 = (value >> 7) & 0x01
        
        # Rotar: (value << 1) | bit7, enmascarar a 8 bits
        result = ((value << 1) | bit7) & 0xFF
        
        return (result, bit7)
    
    def _cb_rrc(self, value: int) -> tuple[int, int]:
        """
        Rotate Right Circular - Helper genérico para CB RRC.
        
        Rota el valor hacia la derecha de forma circular.
        El bit 0 sale y entra por el bit 7. El bit 0 también se copia al flag C.
        
        DIFERENCIA CRÍTICA con RRCA (0x0F):
        - RRCA: Z=0 siempre
        - CB RRC: Z se calcula según el resultado
        
        Args:
            value: Valor de 8 bits a rotar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor rotado (8 bits)
            - carry: 1 si bit 0 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (RRC r)
        """
        value = value & 0xFF
        
        # Extraer bit 0 (el que sale)
        bit0 = value & 0x01
        
        # Rotar: (value >> 1) | (bit0 << 7)
        result = ((value >> 1) | (bit0 << 7)) & 0xFF
        
        return (result, bit0)
    
    def _cb_rl(self, value: int) -> tuple[int, int]:
        """
        Rotate Left through Carry - Helper genérico para CB RL.
        
        Rota el valor hacia la izquierda a través del flag Carry.
        El bit 7 va al flag C, y el *antiguo* flag C entra en el bit 0.
        Es una rotación de 9 bits (8 bits de value + 1 bit de C).
        
        DIFERENCIA CRÍTICA con RLA (0x17):
        - RLA: Z=0 siempre
        - CB RL: Z se calcula según el resultado
        
        Args:
            value: Valor de 8 bits a rotar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor rotado (8 bits)
            - carry: 1 si bit 7 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (RL r)
        """
        value = value & 0xFF
        
        # Obtener carry actual (1 si está activo, 0 si no)
        old_carry = 1 if self.registers.get_flag_c() else 0
        
        # Extraer bit 7 (el que sale)
        bit7 = (value >> 7) & 0x01
        
        # Rotar: (value << 1) | old_carry, enmascarar a 8 bits
        result = ((value << 1) | old_carry) & 0xFF
        
        return (result, bit7)
    
    def _cb_rr(self, value: int) -> tuple[int, int]:
        """
        Rotate Right through Carry - Helper genérico para CB RR.
        
        Rota el valor hacia la derecha a través del flag Carry.
        El bit 0 va al flag C, y el *antiguo* flag C entra en el bit 7.
        Es una rotación de 9 bits (8 bits de value + 1 bit de C).
        
        DIFERENCIA CRÍTICA con RRA (0x1F):
        - RRA: Z=0 siempre
        - CB RR: Z se calcula según el resultado
        
        Args:
            value: Valor de 8 bits a rotar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor rotado (8 bits)
            - carry: 1 si bit 0 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (RR r)
        """
        value = value & 0xFF
        
        # Obtener carry actual (1 si está activo, 0 si no)
        old_carry = 1 if self.registers.get_flag_c() else 0
        
        # Extraer bit 0 (el que sale)
        bit0 = value & 0x01
        
        # Rotar: (value >> 1) | (old_carry << 7)
        result = ((value >> 1) | (old_carry << 7)) & 0xFF
        
        return (result, bit0)
    
    def _cb_sla(self, value: int) -> tuple[int, int]:
        """
        Shift Left Arithmetic - Helper genérico para CB SLA.
        
        Desplaza el valor hacia la izquierda (multiplica por 2).
        El bit 7 va al flag C, y el bit 0 entra 0.
        
        Esta operación es equivalente a multiplicar por 2, pero con overflow
        que se captura en el flag C.
        
        Flags:
        - Z: Calculado según el resultado (si resultado==0, Z=1)
        - N: 0
        - H: 0
        - C: Bit 7 original
        
        Args:
            value: Valor de 8 bits a desplazar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor desplazado (8 bits)
            - carry: 1 si bit 7 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (SLA r)
        """
        value = value & 0xFF
        
        # Extraer bit 7 (el que sale)
        bit7 = (value >> 7) & 0x01
        
        # Desplazar: (value << 1), bit 0 entra 0
        result = (value << 1) & 0xFF
        
        return (result, bit7)
    
    def _cb_sra(self, value: int) -> tuple[int, int]:
        """
        Shift Right Arithmetic - Helper genérico para CB SRA.
        
        Desplaza el valor hacia la derecha manteniendo el signo (divide por 2 con signo).
        El bit 0 va al flag C, y el bit 7 se mantiene igual (signo preservado).
        
        Esta operación es equivalente a dividir por 2 con signo:
        - Si el valor es positivo (bit 7 = 0), el bit 7 sigue siendo 0
        - Si el valor es negativo (bit 7 = 1), el bit 7 sigue siendo 1
        
        Ejemplo:
        - 0x80 (-128) -> 0xC0 (-64), C=0
        - 0x40 (64) -> 0x20 (32), C=0
        
        Flags:
        - Z: Calculado según el resultado
        - N: 0
        - H: 0
        - C: Bit 0 original
        
        Args:
            value: Valor de 8 bits a desplazar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor desplazado (8 bits, signo preservado)
            - carry: 1 si bit 0 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (SRA r)
        """
        value = value & 0xFF
        
        # Extraer bit 0 (el que sale)
        bit0 = value & 0x01
        
        # Extraer bit 7 (signo, se preserva)
        bit7 = (value >> 7) & 0x01
        
        # Desplazar: (value >> 1) | (bit7 << 7)
        result = ((value >> 1) | (bit7 << 7)) & 0xFF
        
        return (result, bit0)
    
    def _cb_srl(self, value: int) -> tuple[int, int]:
        """
        Shift Right Logical - Helper genérico para CB SRL.
        
        Desplaza el valor hacia la derecha sin signo (divide por 2 sin signo).
        El bit 0 va al flag C, y el bit 7 entra 0.
        
        Esta operación es equivalente a dividir por 2 sin signo:
        - Siempre trata el valor como positivo
        - El bit 7 siempre entra 0
        
        Ejemplo:
        - 0x80 (128) -> 0x40 (64), C=0
        - 0x01 (1) -> 0x00 (0), C=1
        
        Flags:
        - Z: Calculado según el resultado
        - N: 0
        - H: 0
        - C: Bit 0 original
        
        Args:
            value: Valor de 8 bits a desplazar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor desplazado (8 bits, bit 7 = 0)
            - carry: 1 si bit 0 original era 1, 0 si era 0
            
        Fuente: Pan Docs - CPU Instruction Set (SRL r)
        """
        value = value & 0xFF
        
        # Extraer bit 0 (el que sale)
        bit0 = value & 0x01
        
        # Desplazar: (value >> 1), bit 7 entra 0
        result = (value >> 1) & 0xFF
        
        return (result, bit0)
    
    def _cb_swap(self, value: int) -> tuple[int, int]:
        """
        SWAP - Helper genérico para CB SWAP.
        
        Intercambia los 4 bits altos con los 4 bits bajos (Nibble Swap).
        
        Ejemplo:
        - 0xA5 (10100101) -> 0x5A (01011010)
        - 0xF0 (11110000) -> 0x0F (00001111)
        
        Flags:
        - Z: Calculado según el resultado (si resultado==0, Z=1)
        - N: 0
        - H: 0
        - C: 0
        
        Args:
            value: Valor de 8 bits a intercambiar
            
        Returns:
            Tupla (result, carry) donde:
            - result: Valor con nibbles intercambiados (8 bits)
            - carry: Siempre 0 (SWAP no genera carry)
            
        Fuente: Pan Docs - CPU Instruction Set (SWAP r)
        """
        value = value & 0xFF
        
        # Extraer nibbles
        low_nibble = value & 0x0F
        high_nibble = (value >> 4) & 0x0F
        
        # Intercambiar: low_nibble va arriba, high_nibble va abajo
        result = ((low_nibble << 4) | high_nibble) & 0xFF
        
        return (result, 0)
    
    def _cb_get_register_value(self, reg_index: int) -> int:
        """
        Obtiene el valor de un registro o memoria según el índice.
        
        Índices de registro (según encoding CB):
        - 0: B
        - 1: C
        - 2: D
        - 3: E
        - 4: H
        - 5: L
        - 6: (HL) - Memoria indirecta
        - 7: A
        
        Args:
            reg_index: Índice del registro (0-7)
            
        Returns:
            Valor de 8 bits del registro o memoria
            
        Fuente: Pan Docs - CPU Instruction Set (CB encoding)
        """
        if reg_index == 0:
            return self.registers.get_b()
        elif reg_index == 1:
            return self.registers.get_c()
        elif reg_index == 2:
            return self.registers.get_d()
        elif reg_index == 3:
            return self.registers.get_e()
        elif reg_index == 4:
            return self.registers.get_h()
        elif reg_index == 5:
            return self.registers.get_l()
        elif reg_index == 6:
            # (HL) - Memoria indirecta
            hl_addr = self.registers.get_hl()
            return self.mmu.read_byte(hl_addr)
        elif reg_index == 7:
            return self.registers.get_a()
        else:
            raise ValueError(f"Índice de registro inválido: {reg_index}")
    
    def _cb_set_register_value(self, reg_index: int, value: int) -> None:
        """
        Establece el valor de un registro o memoria según el índice.
        
        Args:
            reg_index: Índice del registro (0-7)
            value: Valor de 8 bits a escribir
            
        Fuente: Pan Docs - CPU Instruction Set (CB encoding)
        """
        value = value & 0xFF
        
        if reg_index == 0:
            self.registers.set_b(value)
        elif reg_index == 1:
            self.registers.set_c(value)
        elif reg_index == 2:
            self.registers.set_d(value)
        elif reg_index == 3:
            self.registers.set_e(value)
        elif reg_index == 4:
            self.registers.set_h(value)
        elif reg_index == 5:
            self.registers.set_l(value)
        elif reg_index == 6:
            # (HL) - Memoria indirecta
            hl_addr = self.registers.get_hl()
            self.mmu.write_byte(hl_addr, value)
        elif reg_index == 7:
            self.registers.set_a(value)
        else:
            raise ValueError(f"Índice de registro inválido: {reg_index}")
    
    def _cb_update_flags(self, result: int, carry: int) -> None:
        """
        Actualiza los flags después de una operación CB (rotación/shift/swap).
        
        DIFERENCIA CRÍTICA con rotaciones rápidas (RLCA, etc.):
        - Rotaciones rápidas: Z=0 siempre
        - Operaciones CB: Z se calcula según el resultado
        
        Flags:
        - Z: 1 si resultado==0, 0 si no
        - N: 0 (siempre)
        - H: 0 (siempre)
        - C: carry (1 o 0)
        
        Args:
            result: Resultado de la operación (8 bits)
            carry: Valor del carry (1 o 0)
            
        Fuente: Pan Docs - CPU Instruction Set (CB operations flags)
        """
        result = result & 0xFF
        
        # Z: Calculado según el resultado (DIFERENCIA con rotaciones rápidas)
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        
        # H: siempre 0
        self.registers.clear_flag(FLAG_H)
        
        # C: carry
        if carry:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
    
    def _init_cb_shifts_table(self) -> None:
        """
        Inicializa la tabla CB para el rango 0x00-0x3F (rotaciones y shifts).
        
        Patrón de encoding CB:
        - 8 operaciones x 8 registros = 64 opcodes (0x00-0x3F)
        - Operaciones (por fila):
          0x00-0x07: RLC r
          0x08-0x0F: RRC r
          0x10-0x17: RL r
          0x18-0x1F: RR r
          0x20-0x27: SLA r
          0x28-0x2F: SRA r
          0x30-0x37: SRL r
          0x38-0x3F: SWAP r
        
        - Registros (por columna):
          0: B
          1: C
          2: D
          3: E
          4: H
          5: L
          6: (HL) - Memoria indirecta (consume 4 M-Cycles en lugar de 2)
          7: A
        
        Fuente: Pan Docs - CPU Instruction Set (CB Prefix encoding)
        """
        # Operaciones en orden
        operations = [
            (self._cb_rlc, "RLC"),
            (self._cb_rrc, "RRC"),
            (self._cb_rl, "RL"),
            (self._cb_rr, "RR"),
            (self._cb_sla, "SLA"),
            (self._cb_sra, "SRA"),
            (self._cb_srl, "SRL"),
            (self._cb_swap, "SWAP"),
        ]
        
        # Generar handlers para cada combinación operación x registro
        for op_row, (op_func, op_name) in enumerate(operations):
            for reg_index in range(8):
                cb_opcode = (op_row * 8) + reg_index
                
                # Crear handler específico para esta combinación
                # IMPORTANTE: Capturar valores por defecto para evitar problemas de closure
                def make_handler(op_func=op_func, op_name=op_name, reg_index=reg_index, cb_opcode=cb_opcode):
                    def handler() -> int:
                        # Leer valor del registro/memoria
                        value = self._cb_get_register_value(reg_index)
                        
                        # Ejecutar operación
                        result, carry = op_func(value)
                        
                        # Escribir resultado
                        self._cb_set_register_value(reg_index, result)
                        
                        # Actualizar flags
                        self._cb_update_flags(result, carry)
                        
                        # Timing: (HL) consume 4 M-Cycles, registros consumen 2
                        cycles = 4 if reg_index == 6 else 2
                        
                        reg_name = ["B", "C", "D", "E", "H", "L", "(HL)", "A"][reg_index]
                        logger.debug(
                            f"CB 0x{cb_opcode:02X} ({op_name} {reg_name}) -> "
                            f"0x{value:02X} -> 0x{result:02X} "
                            f"Z={self.registers.get_flag_z()} C={self.registers.get_flag_c()}"
                        )
                        
                        return cycles
                    
                    return handler
                
                # Añadir handler a la tabla
                self._cb_opcode_table[cb_opcode] = make_handler()
    
    def _init_cb_bit_res_set_table(self) -> None:
        """
        Inicializa la tabla CB para el rango 0x40-0xFF (BIT, RES, SET).
        
        Patrón de encoding CB:
        - 0x40-0x7F: BIT b, r (Test bit) - 8 bits (0-7) x 8 registros = 64 opcodes
        - 0x80-0xBF: RES b, r (Reset bit) - 8 bits (0-7) x 8 registros = 64 opcodes
        - 0xC0-0xFF: SET b, r (Set bit) - 8 bits (0-7) x 8 registros = 64 opcodes
        
        Estructura del opcode CB:
        - Bits 3-5: Número de bit (0-7)
        - Bits 0-2: Índice de registro (0-7: B, C, D, E, H, L, (HL), A)
        - Bits 6-7: Tipo de operación:
          - 01 (0x40-0x7F): BIT
          - 10 (0x80-0xBF): RES
          - 11 (0xC0-0xFF): SET
        
        Ejemplos:
        - 0x40 = 01000000 -> BIT 0, B (bit=0, reg=0)
        - 0x41 = 01000001 -> BIT 0, C (bit=0, reg=1)
        - 0x7C = 01111100 -> BIT 7, H (bit=7, reg=4)
        - 0x80 = 10000000 -> RES 0, B (bit=0, reg=0)
        - 0xC0 = 11000000 -> SET 0, B (bit=0, reg=0)
        
        Flags:
        - BIT: Z=Inverso del bit, N=0, H=1, C=No cambia
        - RES: No afecta flags
        - SET: No afecta flags
        
        Timing:
        - Registros: 2 M-Cycles
        - (HL): 4 M-Cycles (acceso a memoria)
        
        Fuente: Pan Docs - CPU Instruction Set (CB Prefix encoding)
        """
        # Nombres de registros para logging
        reg_names = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
        
        # Generar handlers para BIT (0x40-0x7F)
        for bit in range(8):
            for reg_index in range(8):
                cb_opcode = 0x40 + (bit * 8) + reg_index
                
                def make_bit_handler(bit=bit, reg_index=reg_index, cb_opcode=cb_opcode):
                    def handler() -> int:
                        # Leer valor del registro/memoria
                        value = self._cb_get_register_value(reg_index)
                        
                        # Ejecutar BIT (actualiza flags, no modifica el valor)
                        self._bit(bit, value)
                        
                        # Timing: (HL) consume 4 M-Cycles, registros consumen 2
                        cycles = 4 if reg_index == 6 else 2
                        
                        reg_name = reg_names[reg_index]
                        logger.debug(
                            f"CB 0x{cb_opcode:02X} (BIT {bit}, {reg_name}) -> "
                            f"0x{value:02X} bit{bit}={1 if (value >> bit) & 1 else 0} "
                            f"Z={self.registers.get_flag_z()} H={self.registers.get_flag_h()}"
                        )
                        
                        return cycles
                    
                    return handler
                
                # Añadir handler a la tabla (sobrescribe el manual si existe)
                self._cb_opcode_table[cb_opcode] = make_bit_handler()
        
        # Generar handlers para RES (0x80-0xBF)
        for bit in range(8):
            for reg_index in range(8):
                cb_opcode = 0x80 + (bit * 8) + reg_index
                
                def make_res_handler(bit=bit, reg_index=reg_index, cb_opcode=cb_opcode):
                    def handler() -> int:
                        # Leer valor del registro/memoria
                        value = self._cb_get_register_value(reg_index)
                        
                        # Ejecutar RES (apaga el bit)
                        result = self._cb_res(bit, value)
                        
                        # Escribir resultado
                        self._cb_set_register_value(reg_index, result)
                        
                        # Timing: (HL) consume 4 M-Cycles, registros consumen 2
                        cycles = 4 if reg_index == 6 else 2
                        
                        reg_name = reg_names[reg_index]
                        logger.debug(
                            f"CB 0x{cb_opcode:02X} (RES {bit}, {reg_name}) -> "
                            f"0x{value:02X} -> 0x{result:02X}"
                        )
                        
                        return cycles
                    
                    return handler
                
                # Añadir handler a la tabla
                self._cb_opcode_table[cb_opcode] = make_res_handler()
        
        # Generar handlers para SET (0xC0-0xFF)
        for bit in range(8):
            for reg_index in range(8):
                cb_opcode = 0xC0 + (bit * 8) + reg_index
                
                def make_set_handler(bit=bit, reg_index=reg_index, cb_opcode=cb_opcode):
                    def handler() -> int:
                        # Leer valor del registro/memoria
                        value = self._cb_get_register_value(reg_index)
                        
                        # Ejecutar SET (enciende el bit)
                        result = self._cb_set(bit, value)
                        
                        # Escribir resultado
                        self._cb_set_register_value(reg_index, result)
                        
                        # Timing: (HL) consume 4 M-Cycles, registros consumen 2
                        cycles = 4 if reg_index == 6 else 2
                        
                        reg_name = reg_names[reg_index]
                        logger.debug(
                            f"CB 0x{cb_opcode:02X} (SET {bit}, {reg_name}) -> "
                            f"0x{value:02X} -> 0x{result:02X}"
                        )
                        
                        return cycles
                    
                    return handler
                
                # Añadir handler a la tabla
                self._cb_opcode_table[cb_opcode] = make_set_handler()
    
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

    # ========== Handlers de Aritmética de Pila con Offset (SP+r8) ==========
    
    def _add_sp_offset(self, offset: int) -> tuple[int, bool, bool]:
        """
        Helper para ADD SP, r8 y LD HL, SP+r8.
        
        Calcula SP + offset (donde offset es un entero con signo de 8 bits)
        y devuelve el resultado junto con los flags H y C.
        
        CRÍTICO: Los flags H y C se calculan de forma especial:
        - H (Half-Carry): Se activa si hay carry del bit 3 al 4 (nibble bajo)
        - C (Carry): Se activa si hay carry del bit 7 al 8 (byte bajo)
        
        Esto es diferente a ADD HL, rr porque aquí estamos sumando un valor
        de 8 bits (con signo) a un valor de 16 bits, y los flags se calculan
        solo en el byte bajo de SP.
        
        Args:
            offset: Offset con signo de 8 bits (rango [-128, 127])
            
        Returns:
            Tupla (result, h_flag, c_flag) donde:
            - result: SP + offset (16 bits, con wrap-around)
            - h_flag: True si hay half-carry (bit 3 -> 4)
            - c_flag: True si hay carry (bit 7 -> 8)
            
        Fórmulas:
        - Half-Carry: ((sp & 0xF) + (offset & 0xF)) > 0xF
        - Carry: ((sp & 0xFF) + (offset & 0xFF)) > 0xFF
        
        Fuente: Pan Docs - CPU Instruction Set (ADD SP, r8 / LD HL, SP+r8)
        """
        sp = self.registers.get_sp()
        
        # Convertir offset a unsigned para cálculos de flags
        # Si offset es negativo, lo convertimos a su representación unsigned
        offset_unsigned = offset & 0xFF
        
        # Calcular resultado (16 bits con wrap-around)
        result = (sp + offset) & 0xFFFF
        
        # Calcular flags basándose en el byte bajo de SP
        sp_low = sp & 0xFF
        offset_low = offset_unsigned
        
        # Half-Carry: carry del bit 3 al 4 (nibble bajo)
        h_flag = ((sp_low & 0xF) + (offset_low & 0xF)) > 0xF
        
        # Carry: carry del bit 7 al 8 (byte bajo)
        c_flag = ((sp_low + offset_low) & 0x100) != 0
        
        return (result, h_flag, c_flag)
    
    def _op_add_sp_r8(self) -> int:
        """
        ADD SP, r8 (Add signed 8-bit offset to Stack Pointer) - Opcode 0xE8
        
        Suma un entero con signo de 8 bits al Stack Pointer (SP).
        
        El offset se lee como un byte con signo (Two's Complement):
        - 0x00-0x7F (0-127): Positivos
        - 0x80-0xFF (128-255): Negativos (-128 a -1)
        
        Flags:
        - Z: Siempre 0 (no se toca)
        - N: Siempre 0 (es una suma)
        - H: Se activa si hay carry del bit 3 al 4 (nibble bajo)
        - C: Se activa si hay carry del bit 7 al 8 (byte bajo)
        
        Returns:
            4 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (ADD SP, r8)
        """
        offset = self._read_signed_byte()
        old_sp = self.registers.get_sp()
        
        # Calcular nuevo SP y flags
        new_sp, h_flag, c_flag = self._add_sp_offset(offset)
        
        # Actualizar SP
        self.registers.set_sp(new_sp)
        
        # Actualizar flags
        # Z: siempre 0
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: según cálculo
        if h_flag:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        # C: según cálculo
        if c_flag:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"ADD SP, {offset:+d} -> SP=0x{old_sp:04X} + {offset:+d} = 0x{new_sp:04X} "
            f"H={h_flag} C={c_flag}"
        )
        return 4
    
    def _op_ld_hl_sp_r8(self) -> int:
        """
        LD HL, SP+r8 (Load HL with SP + signed 8-bit offset) - Opcode 0xF8
        
        Calcula SP + offset (donde offset es un entero con signo de 8 bits)
        y almacena el resultado en HL. SP NO se modifica.
        
        El offset se lee como un byte con signo (Two's Complement):
        - 0x00-0x7F (0-127): Positivos
        - 0x80-0xFF (128-255): Negativos (-128 a -1)
        
        Flags:
        - Z: Siempre 0 (no se toca)
        - N: Siempre 0 (es una suma)
        - H: Se activa si hay carry del bit 3 al 4 (nibble bajo)
        - C: Se activa si hay carry del bit 7 al 8 (byte bajo)
        
        Returns:
            3 M-Cycles
            
        Fuente: Pan Docs - Instruction Set (LD HL, SP+r8)
        """
        offset = self._read_signed_byte()
        sp = self.registers.get_sp()
        
        # Calcular HL = SP + offset y flags
        hl_value, h_flag, c_flag = self._add_sp_offset(offset)
        
        # Actualizar HL (SP no cambia)
        self.registers.set_hl(hl_value)
        
        # Actualizar flags
        # Z: siempre 0
        self.registers.clear_flag(FLAG_Z)
        # N: siempre 0
        self.registers.clear_flag(FLAG_N)
        # H: según cálculo
        if h_flag:
            self.registers.set_flag(FLAG_H)
        else:
            self.registers.clear_flag(FLAG_H)
        # C: según cálculo
        if c_flag:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"LD HL, SP{offset:+d} -> HL=0x{hl_value:04X} (SP=0x{sp:04X} no cambia) "
            f"H={h_flag} C={c_flag}"
        )
        return 3

    def _op_ld_sp_hl(self) -> int:
        """
        LD SP, HL (Load Stack Pointer from HL) - Opcode 0xF9
        
        Carga el valor del par de registros HL en el Stack Pointer (SP).
        Esta instrucción es útil para:
        - Resetear la pila a una dirección conocida
        - Cambiar de contexto (cambiar de stack frame)
        - Configurar la pila al inicio de una rutina
        
        Es la operación inversa de LD HL, SP+r8 (0xF8), pero sin offset.
        A diferencia de LD HL, SP+r8, esta instrucción NO modifica flags.
        
        Ejemplo:
        - Si HL = 0xC000
        - Ejecutar LD SP, HL
        - Resultado: SP = 0xC000
        
        Returns:
            2 M-Cycles (fetch opcode + lectura de registros)
            
        Fuente: Pan Docs - Instruction Set (LD SP, HL)
        """
        hl_value = self.registers.get_hl()
        self.registers.set_sp(hl_value)
        
        logger.debug(f"LD SP, HL -> SP=0x{hl_value:04X} (HL=0x{hl_value:04X})")
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
    
    # ========== Helpers para Transferencias LD r, r' ==========
    
    def _get_register_value(self, reg_code: int) -> int:
        """
        Obtiene el valor de un registro según su código.
        
        Códigos de registro (bits 0-2 o 3-5 del opcode):
        - 0 (000): B
        - 1 (001): C
        - 2 (010): D
        - 3 (011): E
        - 4 (100): H
        - 5 (101): L
        - 6 (110): (HL) - Dirección apuntada por HL
        - 7 (111): A
        
        Args:
            reg_code: Código del registro (0-7)
            
        Returns:
            Valor del registro (8 bits) o valor en memoria si es (HL)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, r' encoding)
        """
        if reg_code == 0:  # B
            return self.registers.get_b()
        elif reg_code == 1:  # C
            return self.registers.get_c()
        elif reg_code == 2:  # D
            return self.registers.get_d()
        elif reg_code == 3:  # E
            return self.registers.get_e()
        elif reg_code == 4:  # H
            return self.registers.get_h()
        elif reg_code == 5:  # L
            return self.registers.get_l()
        elif reg_code == 6:  # (HL) - Memoria indirecta
            hl_addr = self.registers.get_hl()
            return self.mmu.read_byte(hl_addr)
        elif reg_code == 7:  # A
            return self.registers.get_a()
        else:
            raise ValueError(f"Código de registro inválido: {reg_code}")
    
    def _set_register_value(self, reg_code: int, value: int) -> None:
        """
        Establece el valor de un registro según su código.
        
        Args:
            reg_code: Código del registro (0-7)
            value: Valor a establecer (8 bits, se enmascara automáticamente)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, r' encoding)
        """
        value = value & 0xFF
        if reg_code == 0:  # B
            self.registers.set_b(value)
        elif reg_code == 1:  # C
            self.registers.set_c(value)
        elif reg_code == 2:  # D
            self.registers.set_d(value)
        elif reg_code == 3:  # E
            self.registers.set_e(value)
        elif reg_code == 4:  # H
            self.registers.set_h(value)
        elif reg_code == 5:  # L
            self.registers.set_l(value)
        elif reg_code == 6:  # (HL) - Memoria indirecta
            hl_addr = self.registers.get_hl()
            self.mmu.write_byte(hl_addr, value)
        elif reg_code == 7:  # A
            self.registers.set_a(value)
        else:
            raise ValueError(f"Código de registro inválido: {reg_code}")
    
    def _op_ld_r_r(self, dest_code: int, src_code: int) -> int:
        """
        Helper genérico para LD r, r' (Load register to register).
        
        Transfiere el valor de un registro (o memoria) a otro registro (o memoria).
        
        IMPORTANTE: LD (HL), (HL) (opcode 0x76) NO EXISTE. Ese opcode es HALT.
        
        Timing:
        - LD r, r: 1 M-Cycle (transferencia entre registros)
        - LD r, (HL) o LD (HL), r: 2 M-Cycles (acceso a memoria)
        
        Args:
            dest_code: Código del registro destino (0-7)
            src_code: Código del registro origen (0-7)
            
        Returns:
            1 M-Cycle si ambos son registros, 2 M-Cycles si alguno es (HL)
            
        Fuente: Pan Docs - CPU Instruction Set (LD r, r')
        """
        # Obtener valor del origen
        src_value = self._get_register_value(src_code)
        
        # Establecer valor en el destino
        self._set_register_value(dest_code, src_value)
        
        # Determinar timing según si hay acceso a memoria
        if dest_code == 6 or src_code == 6:  # (HL) está involucrado
            cycles = 2
            dest_name = "(HL)" if dest_code == 6 else self._get_register_name(dest_code)
            src_name = "(HL)" if src_code == 6 else self._get_register_name(src_code)
            logger.debug(f"LD {dest_name}, {src_name} -> {dest_name}=0x{src_value:02X} (2 M-Cycles)")
        else:
            cycles = 1
            dest_name = self._get_register_name(dest_code)
            src_name = self._get_register_name(src_code)
            logger.debug(f"LD {dest_name}, {src_name} -> {dest_name}=0x{src_value:02X} (1 M-Cycle)")
        
        return cycles
    
    def _get_register_name(self, reg_code: int) -> str:
        """
        Obtiene el nombre legible de un registro según su código.
        
        Args:
            reg_code: Código del registro (0-7)
            
        Returns:
            Nombre del registro (ej: "B", "C", "(HL)", "A")
        """
        names = ["B", "C", "D", "E", "H", "L", "(HL)", "A"]
        return names[reg_code]
    
    # ========== Handlers de Transferencias LD r, r' (Bloque 0x40-0x7F) ==========
    
    def _op_halt(self) -> int:
        """
        HALT (Halt CPU) - Opcode 0x76
        
        Pone la CPU en modo de bajo consumo. La CPU deja de ejecutar instrucciones
        (el PC no avanza) hasta que ocurre una interrupción.
        
        Comportamiento:
        - Si IME está activado (True) y hay interrupciones pendientes, la CPU se
          despierta automáticamente en el siguiente ciclo.
        - Si IME está desactivado (False), la CPU permanece en HALT hasta que
          se active IME y ocurra una interrupción.
        - Mientras está en HALT, la CPU consume 1 ciclo por tick (espera activa).
        
        IMPORTANTE: El opcode 0x76 es HALT, NO LD (HL), (HL). No existe la
        transferencia de memoria a memoria.
        
        Returns:
            1 M-Cycle (la instrucción HALT en sí consume 1 ciclo)
            
        Fuente: Pan Docs - CPU Instruction Set (HALT)
        """
        self.halted = True
        logger.debug("HALT -> CPU en modo de bajo consumo (halted=True)")
        return 1
    
    # ========== Instrucciones Misceláneas (DAA, CPL, SCF, CCF, RST) ==========
    
    def _op_daa(self) -> int:
        """
        DAA (Decimal Adjust Accumulator) - Opcode 0x27
        
        Ajusta el acumulador A para convertir el resultado de una operación
        aritmética binaria a BCD (Binary Coded Decimal).
        
        La Game Boy usa BCD para representar números decimales en pantallas
        (ej: puntuaciones en Tetris). Cuando sumas 9 + 1 en binario, obtienes
        0x0A, pero en BCD queremos 0x10 (que representa el decimal 10).
        
        Algoritmo (basado en Z80/8080, adaptado para Game Boy):
        - Si la última operación fue suma (!N):
            - Si C está activo O A > 0x99: A += 0x60, C = 1
            - Si H está activo O (A & 0x0F) > 9: A += 0x06
        - Si la última operación fue resta (N):
            - Si C está activo: A -= 0x60
            - Si H está activo: A -= 0x06
        
        Flags:
        - Z: Actualizado según el resultado final
        - N: No modificado (mantiene el estado de la operación anterior)
        - H: Siempre se limpia (0)
        - C: Se actualiza según la lógica de ajuste
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (DAA)
        Referencia: Z80/8080 DAA algorithm (adaptado para Game Boy)
        """
        a = self.registers.get_a()
        flags = self.registers.get_f()
        n_flag = (flags & FLAG_N) != 0
        c_flag = (flags & FLAG_C) != 0
        h_flag = (flags & FLAG_H) != 0
        
        correction = 0
        new_c = c_flag
        
        if not n_flag:  # Última operación fue suma
            # Verificar si necesitamos ajustar el nibble alto (decenas)
            if c_flag or a > 0x99:
                correction += 0x60
                new_c = True
            
            # Verificar si necesitamos ajustar el nibble bajo (unidades)
            if h_flag or (a & 0x0F) > 9:
                correction += 0x06
        else:  # Última operación fue resta
            # Verificar si necesitamos ajustar el nibble alto
            if c_flag:
                correction -= 0x60
                new_c = True
            
            # Verificar si necesitamos ajustar el nibble bajo
            if h_flag:
                correction -= 0x06
        
        # Aplicar corrección
        result = (a + correction) & 0xFF
        
        # Actualizar acumulador
        self.registers.set_a(result)
        
        # Actualizar flags
        # Z: según el resultado final
        if result == 0:
            self.registers.set_flag(FLAG_Z)
        else:
            self.registers.clear_flag(FLAG_Z)
        
        # N: no se modifica (mantiene el estado de la operación anterior)
        # H: siempre se limpia
        self.registers.clear_flag(FLAG_H)
        
        # C: según la lógica de ajuste
        if new_c:
            self.registers.set_flag(FLAG_C)
        else:
            self.registers.clear_flag(FLAG_C)
        
        logger.debug(
            f"DAA: A=0x{a:02X} -> 0x{result:02X} "
            f"(correction={correction:+d}, N={n_flag}, C={new_c})"
        )
        return 1
    
    def _op_cpl(self) -> int:
        """
        CPL (Complement Accumulator) - Opcode 0x2F
        
        Invierte todos los bits del acumulador A (complemento a uno).
        
        Operación: A = ~A
        
        Flags:
        - Z: No modificado
        - N: Se activa (1)
        - H: Se activa (1)
        - C: No modificado
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (CPL)
        """
        a = self.registers.get_a()
        result = (~a) & 0xFF  # Complemento a uno (invertir bits)
        
        self.registers.set_a(result)
        
        # Actualizar flags: N=1, H=1
        self.registers.set_flag(FLAG_N)
        self.registers.set_flag(FLAG_H)
        
        logger.debug(f"CPL: A=0x{a:02X} -> 0x{result:02X} (complemento)")
        return 1
    
    def _op_scf(self) -> int:
        """
        SCF (Set Carry Flag) - Opcode 0x37
        
        Activa el flag Carry (C = 1).
        
        Flags:
        - Z: No modificado
        - N: Se limpia (0)
        - H: Se limpia (0)
        - C: Se activa (1)
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (SCF)
        """
        # Activar Carry
        self.registers.set_flag(FLAG_C)
        
        # Limpiar N y H
        self.registers.clear_flag(FLAG_N)
        self.registers.clear_flag(FLAG_H)
        
        logger.debug("SCF: C=1, N=0, H=0")
        return 1
    
    def _op_ccf(self) -> int:
        """
        CCF (Complement Carry Flag) - Opcode 0x3F
        
        Invierte el flag Carry (C = !C).
        
        Flags:
        - Z: No modificado
        - N: Se limpia (0)
        - H: Se limpia (0)
        - C: Se invierte (!C)
        
        Returns:
            1 M-Cycle
            
        Fuente: Pan Docs - CPU Instruction Set (CCF)
        """
        # Invertir Carry
        if self.registers.check_flag(FLAG_C):
            self.registers.clear_flag(FLAG_C)
        else:
            self.registers.set_flag(FLAG_C)
        
        # Limpiar N y H
        self.registers.clear_flag(FLAG_N)
        self.registers.clear_flag(FLAG_H)
        
        new_c = self.registers.check_flag(FLAG_C)
        logger.debug(f"CCF: C={new_c}, N=0, H=0")
        return 1
    
    def _rst(self, vector: int) -> int:
        """
        Helper genérico para RST (Restart) - Opcodes 0xC7, 0xCF, 0xD7, 0xDF, 0xE7, 0xEF, 0xF7, 0xFF
        
        RST es como un CALL pero de 1 solo byte. Hace PUSH PC y salta a una
        dirección fija (vector de interrupción).
        
        Los vectores RST son:
        - RST 00h: 0x0000
        - RST 08h: 0x0008
        - RST 10h: 0x0010
        - RST 18h: 0x0018
        - RST 20h: 0x0020
        - RST 28h: 0x0028
        - RST 30h: 0x0030
        - RST 38h: 0x0038
        
        RST se usa para:
        1. Ahorrar espacio (1 byte vs 3 bytes de CALL)
        2. Interrupciones hardware (cada interrupción tiene su vector RST)
        
        Proceso:
        1. Obtener PC actual (dirección de retorno)
        2. PUSH PC en la pila
        3. Saltar al vector (PC = vector)
        
        Args:
            vector: Dirección del vector de interrupción (0x00, 0x08, 0x10, ..., 0x38)
            
        Returns:
            4 M-Cycles (fetch opcode + push 2 bytes en la pila)
            
        Fuente: Pan Docs - CPU Instruction Set (RST)
        """
        # Obtener PC actual (dirección de retorno = siguiente instrucción)
        return_addr = self.registers.get_pc()
        
        # PUSH PC en la pila
        self._push_word(return_addr)
        
        # Saltar al vector
        self.registers.set_pc(vector)
        
        logger.debug(f"RST 0x{vector:02X}h: PC=0x{return_addr:04X} -> 0x{vector:04X}")
        return 4
    
    def _op_rst_00(self) -> int:
        """RST 00h - Opcode 0xC7"""
        return self._rst(0x0000)
    
    def _op_rst_08(self) -> int:
        """RST 08h - Opcode 0xCF"""
        return self._rst(0x0008)
    
    def _op_rst_10(self) -> int:
        """RST 10h - Opcode 0xD7"""
        return self._rst(0x0010)
    
    def _op_rst_18(self) -> int:
        """RST 18h - Opcode 0xDF"""
        return self._rst(0x0018)
    
    def _op_rst_20(self) -> int:
        """RST 20h - Opcode 0xE7"""
        return self._rst(0x0020)
    
    def _op_rst_28(self) -> int:
        """RST 28h - Opcode 0xEF"""
        return self._rst(0x0028)
    
    def _op_rst_30(self) -> int:
        """RST 30h - Opcode 0xF7"""
        return self._rst(0x0030)
    
    def _op_rst_38(self) -> int:
        """RST 38h - Opcode 0xFF"""
        return self._rst(0x0038)

