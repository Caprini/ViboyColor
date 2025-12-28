# distutils: language = c++

"""
Wrapper Cython para CoreRegisters (Registros de la CPU).

Este módulo expone la clase C++ CoreRegisters a Python, permitiendo
acceso de alta velocidad a los registros de la CPU sin overhead de Python.
"""

from libc.stdint cimport uint8_t, uint16_t
from libcpp cimport bool

# Importar la definición de la clase C++ desde el archivo .pxd
cimport registers

cdef class PyRegisters:
    """
    Wrapper Python para CoreRegisters.
    
    Esta clase permite usar CoreRegisters desde Python manteniendo
    el rendimiento de C++ (acceso directo a memoria sin overhead).
    
    Expone propiedades Python para acceso intuitivo a los registros.
    """
    cdef registers.CoreRegisters* _regs
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._regs = new registers.CoreRegisters()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._regs != NULL:
            del self._regs
    
    # ========== Propiedades para registros de 8 bits ==========
    
    @property
    def a(self) -> int:
        """Obtiene el registro A (8 bits)."""
        return self._regs.a
    
    @a.setter
    def a(self, int value):
        """Establece el registro A (8 bits, wrap-around)."""
        self._regs.a = <uint8_t>(value & 0xFF)
    
    @property
    def b(self) -> int:
        """Obtiene el registro B (8 bits)."""
        return self._regs.b
    
    @b.setter
    def b(self, int value):
        """Establece el registro B (8 bits, wrap-around)."""
        self._regs.b = <uint8_t>(value & 0xFF)
    
    @property
    def c(self) -> int:
        """Obtiene el registro C (8 bits)."""
        return self._regs.c
    
    @c.setter
    def c(self, int value):
        """Establece el registro C (8 bits, wrap-around)."""
        self._regs.c = <uint8_t>(value & 0xFF)
    
    @property
    def d(self) -> int:
        """Obtiene el registro D (8 bits)."""
        return self._regs.d
    
    @d.setter
    def d(self, int value):
        """Establece el registro D (8 bits, wrap-around)."""
        self._regs.d = <uint8_t>(value & 0xFF)
    
    @property
    def e(self) -> int:
        """Obtiene el registro E (8 bits)."""
        return self._regs.e
    
    @e.setter
    def e(self, int value):
        """Establece el registro E (8 bits, wrap-around)."""
        self._regs.e = <uint8_t>(value & 0xFF)
    
    @property
    def h(self) -> int:
        """Obtiene el registro H (8 bits)."""
        return self._regs.h
    
    @h.setter
    def h(self, int value):
        """Establece el registro H (8 bits, wrap-around)."""
        self._regs.h = <uint8_t>(value & 0xFF)
    
    @property
    def l(self) -> int:
        """Obtiene el registro L (8 bits)."""
        return self._regs.l
    
    @l.setter
    def l(self, int value):
        """Establece el registro L (8 bits, wrap-around)."""
        self._regs.l = <uint8_t>(value & 0xFF)
    
    @property
    def f(self) -> int:
        """Obtiene el registro F (flags, 8 bits, solo bits altos válidos)."""
        return self._regs.f
    
    @f.setter
    def f(self, int value):
        """Establece el registro F (flags, aplica máscara automáticamente)."""
        self._regs.f = <uint8_t>(value & 0xF0)  # Aplicar máscara para F
    
    # ========== Propiedades para registros de 16 bits ==========
    
    @property
    def pc(self) -> int:
        """Obtiene el Program Counter (16 bits)."""
        return self._regs.pc
    
    @pc.setter
    def pc(self, int value):
        """Establece el Program Counter (16 bits, wrap-around)."""
        self._regs.pc = <uint16_t>(value & 0xFFFF)
    
    @property
    def sp(self) -> int:
        """Obtiene el Stack Pointer (16 bits)."""
        return self._regs.sp
    
    @sp.setter
    def sp(self, int value):
        """Establece el Stack Pointer (16 bits, wrap-around)."""
        self._regs.sp = <uint16_t>(value & 0xFFFF)
    
    # ========== Propiedades para pares virtuales de 16 bits ==========
    
    @property
    def af(self) -> int:
        """Obtiene el par AF (A en bits altos, F en bits bajos)."""
        return self._regs.get_af()
    
    @af.setter
    def af(self, int value):
        """Establece el par AF."""
        self._regs.set_af(<uint16_t>(value & 0xFFFF))
    
    @property
    def bc(self) -> int:
        """Obtiene el par BC (B en bits altos, C en bits bajos)."""
        return self._regs.get_bc()
    
    @bc.setter
    def bc(self, int value):
        """Establece el par BC."""
        self._regs.set_bc(<uint16_t>(value & 0xFFFF))
    
    @property
    def de(self) -> int:
        """Obtiene el par DE (D en bits altos, E en bits bajos)."""
        return self._regs.get_de()
    
    @de.setter
    def de(self, int value):
        """Establece el par DE."""
        self._regs.set_de(<uint16_t>(value & 0xFFFF))
    
    @property
    def hl(self) -> int:
        """Obtiene el par HL (H en bits altos, L en bits bajos)."""
        return self._regs.get_hl()
    
    @hl.setter
    def hl(self, int value):
        """Establece el par HL."""
        self._regs.set_hl(<uint16_t>(value & 0xFFFF))
    
    # ========== Propiedades para Flags ==========
    
    @property
    def flag_z(self) -> bool:
        """Obtiene el flag Zero (Z)."""
        return self._regs.get_flag_z()
    
    @flag_z.setter
    def flag_z(self, bool value):
        """Establece el flag Zero (Z)."""
        self._regs.set_flag_z(value)
    
    @property
    def flag_n(self) -> bool:
        """Obtiene el flag Subtract (N)."""
        return self._regs.get_flag_n()
    
    @flag_n.setter
    def flag_n(self, bool value):
        """Establece el flag Subtract (N)."""
        self._regs.set_flag_n(value)
    
    @property
    def flag_h(self) -> bool:
        """Obtiene el flag Half Carry (H)."""
        return self._regs.get_flag_h()
    
    @flag_h.setter
    def flag_h(self, bool value):
        """Establece el flag Half Carry (H)."""
        self._regs.set_flag_h(value)
    
    @property
    def flag_c(self) -> bool:
        """Obtiene el flag Carry (C)."""
        return self._regs.get_flag_c()
    
    @flag_c.setter
    def flag_c(self, bool value):
        """Establece el flag Carry (C)."""
        self._regs.set_flag_c(value)
    
    # NOTA: El miembro _regs es accesible desde otros módulos Cython
    # que incluyan este archivo (como cpu.pyx)

