"""
Registros de la CPU LR35902

La Game Boy utiliza una CPU híbrida basada en el Z80/8080. Tiene:
- Registros de 8 bits: A, B, C, D, E, H, L, F
- Registros de 16 bits: PC (Program Counter), SP (Stack Pointer)
- Pares virtuales de 16 bits: AF, BC, DE, HL (combinaciones de registros de 8 bits)

El registro F (Flags) almacena el estado de la CPU:
- Bit 7 (Z): Zero flag - se activa cuando el resultado de una operación es cero
- Bit 6 (N): Subtract flag - indica si la última operación fue una resta
- Bit 5 (H): Half Carry flag - indica carry del bit 3 al 4 (nibble bajo)
- Bit 4 (C): Carry flag - indica carry del bit 7 (overflow en suma o borrow en resta)

Peculiaridad hardware: Los 4 bits bajos del registro F siempre son 0.
Esto es una característica del hardware real de la Game Boy.

Fuente: Pan Docs - Game Boy CPU Manual
"""

from __future__ import annotations


# Máscaras para los flags (bits 7, 6, 5, 4 respectivamente)
FLAG_Z = 0x80  # Zero flag (bit 7)
FLAG_N = 0x40  # Subtract flag (bit 6)
FLAG_H = 0x20  # Half Carry flag (bit 5)
FLAG_C = 0x10  # Carry flag (bit 4)

# Máscara para los bits válidos del registro F (solo bits altos)
REGISTER_F_MASK = 0xF0


class Registers:
    """
    Registros de la CPU LR35902 de la Game Boy.
    
    Gestiona los registros de 8 bits, pares de 16 bits, y flags de estado.
    Todas las operaciones aseguran wrap-around para valores fuera del rango válido.
    """

    def __init__(self) -> None:
        """
        Inicializa todos los registros a cero.
        
        Registros de 8 bits:
        - A: Acumulador (registro principal para operaciones aritméticas)
        - B, C, D, E, H, L: Registros de propósito general
        - F: Registro de flags (solo bits altos son válidos)
        
        Registros de 16 bits:
        - PC: Program Counter (puntero de instrucción actual)
        - SP: Stack Pointer (puntero de pila)
        """
        # Registros de 8 bits
        self.a: int = 0
        self.b: int = 0
        self.c: int = 0
        self.d: int = 0
        self.e: int = 0
        self.h: int = 0
        self.l: int = 0
        self.f: int = 0  # Flags (solo bits altos válidos)

        # Registros de 16 bits
        self.pc: int = 0  # Program Counter
        self.sp: int = 0  # Stack Pointer

    # ========== Registros de 8 bits (con wrap-around) ==========

    def set_a(self, value: int) -> None:
        """Establece el registro A (8 bits, wrap-around)"""
        self.a = value & 0xFF

    def get_a(self) -> int:
        """Obtiene el registro A"""
        return self.a

    def set_b(self, value: int) -> None:
        """Establece el registro B (8 bits, wrap-around)"""
        self.b = value & 0xFF

    def get_b(self) -> int:
        """Obtiene el registro B"""
        return self.b

    def set_c(self, value: int) -> None:
        """Establece el registro C (8 bits, wrap-around)"""
        self.c = value & 0xFF

    def get_c(self) -> int:
        """Obtiene el registro C"""
        return self.c

    def set_d(self, value: int) -> None:
        """Establece el registro D (8 bits, wrap-around)"""
        self.d = value & 0xFF

    def get_d(self) -> int:
        """Obtiene el registro D"""
        return self.d

    def set_e(self, value: int) -> None:
        """Establece el registro E (8 bits, wrap-around)"""
        self.e = value & 0xFF

    def get_e(self) -> int:
        """Obtiene el registro E"""
        return self.e

    def set_h(self, value: int) -> None:
        """Establece el registro H (8 bits, wrap-around)"""
        self.h = value & 0xFF

    def get_h(self) -> int:
        """Obtiene el registro H"""
        return self.h

    def set_l(self, value: int) -> None:
        """Establece el registro L (8 bits, wrap-around)"""
        self.l = value & 0xFF

    def get_l(self) -> int:
        """Obtiene el registro L"""
        return self.l

    def set_f(self, value: int) -> None:
        """
        Establece el registro F (flags).
        
        Los 4 bits bajos siempre son 0 en el hardware real.
        Aplicamos máscara 0xF0 para simular este comportamiento.
        
        Fuente: Pan Docs - Hardware quirks
        """
        self.f = value & REGISTER_F_MASK

    def get_f(self) -> int:
        """Obtiene el registro F (flags)"""
        return self.f

    # ========== Pares virtuales de 16 bits ==========

    def get_af(self) -> int:
        """
        Obtiene el par AF (A en bits altos, F en bits bajos).
        
        Aunque F solo tiene 4 bits válidos, se almacena completo
        en el byte bajo del par de 16 bits.
        """
        return ((self.a << 8) | self.f) & 0xFFFF

    def set_af(self, value: int) -> None:
        """
        Establece el par AF.
        
        A partir de los bits altos, F mantiene su máscara (bits bajos = 0).
        """
        value = value & 0xFFFF
        self.a = (value >> 8) & 0xFF
        self.set_f(value & 0xFF)  # Usa set_f para aplicar la máscara

    def get_bc(self) -> int:
        """Obtiene el par BC (B en bits altos, C en bits bajos)"""
        return ((self.b << 8) | self.c) & 0xFFFF

    def set_bc(self, value: int) -> None:
        """Establece el par BC"""
        value = value & 0xFFFF
        self.b = (value >> 8) & 0xFF
        self.c = value & 0xFF

    def get_de(self) -> int:
        """Obtiene el par DE (D en bits altos, E en bits bajos)"""
        return ((self.d << 8) | self.e) & 0xFFFF

    def set_de(self, value: int) -> None:
        """Establece el par DE"""
        value = value & 0xFFFF
        self.d = (value >> 8) & 0xFF
        self.e = value & 0xFF

    def get_hl(self) -> int:
        """Obtiene el par HL (H en bits altos, L en bits bajos)"""
        return ((self.h << 8) | self.l) & 0xFFFF

    def set_hl(self, value: int) -> None:
        """Establece el par HL"""
        value = value & 0xFFFF
        self.h = (value >> 8) & 0xFF
        self.l = value & 0xFF

    # ========== Registros de 16 bits ==========

    def set_pc(self, value: int) -> None:
        """Establece el Program Counter (16 bits, wrap-around)"""
        self.pc = value & 0xFFFF

    def get_pc(self) -> int:
        """Obtiene el Program Counter"""
        return self.pc

    def set_sp(self, value: int) -> None:
        """Establece el Stack Pointer (16 bits, wrap-around)"""
        self.sp = value & 0xFFFF

    def get_sp(self) -> int:
        """Obtiene el Stack Pointer"""
        return self.sp

    # ========== Helpers para Flags ==========

    def set_flag(self, flag: int) -> None:
        """
        Activa un flag específico.
        
        Args:
            flag: Máscara del flag (FLAG_Z, FLAG_N, FLAG_H, FLAG_C)
        """
        self.f = (self.f | flag) & REGISTER_F_MASK

    def clear_flag(self, flag: int) -> None:
        """
        Desactiva un flag específico.
        
        Args:
            flag: Máscara del flag (FLAG_Z, FLAG_N, FLAG_H, FLAG_C)
        """
        self.f = (self.f & ~flag) & REGISTER_F_MASK

    def check_flag(self, flag: int) -> bool:
        """
        Verifica si un flag está activo.
        
        Args:
            flag: Máscara del flag (FLAG_Z, FLAG_N, FLAG_H, FLAG_C)
            
        Returns:
            True si el flag está activo, False en caso contrario
        """
        return (self.f & flag) != 0

    def get_flag_z(self) -> bool:
        """Verifica si el flag Zero está activo"""
        return self.check_flag(FLAG_Z)

    def get_flag_n(self) -> bool:
        """Verifica si el flag Subtract está activo"""
        return self.check_flag(FLAG_N)

    def get_flag_h(self) -> bool:
        """Verifica si el flag Half Carry está activo"""
        return self.check_flag(FLAG_H)

    def get_flag_c(self) -> bool:
        """Verifica si el flag Carry está activo"""
        return self.check_flag(FLAG_C)

