# distutils: language = c++

"""
Definición Cython de la clase CoreRegisters de C++.

Este archivo .pxd declara la interfaz de la clase CoreRegisters para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t
from libcpp cimport bool

cdef extern from "Registers.hpp":
    cdef cppclass CoreRegisters:
        # Miembros públicos (registros de 8 bits)
        uint8_t a
        uint8_t b
        uint8_t c
        uint8_t d
        uint8_t e
        uint8_t h
        uint8_t l
        uint8_t f
        
        # Miembros públicos (registros de 16 bits)
        uint16_t pc
        uint16_t sp
        
        # Constructor
        CoreRegisters() except +
        
        # Pares virtuales de 16 bits
        uint16_t get_af()
        void set_af(uint16_t value)
        uint16_t get_bc()
        void set_bc(uint16_t value)
        uint16_t get_de()
        void set_de(uint16_t value)
        uint16_t get_hl()
        void set_hl(uint16_t value)
        
        # Helpers para Flags
        bool get_flag_z()
        void set_flag_z(bool value)
        bool get_flag_n()
        void set_flag_n(bool value)
        bool get_flag_h()
        void set_flag_h(bool value)
        bool get_flag_c()
        void set_flag_c(bool value)

