# distutils: language = c++

"""
Definición Cython de la clase MMU de C++.

Este archivo .pxd declara la interfaz de la clase MMU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t

cdef extern from "MMU.hpp":
    cdef cppclass MMU:
        MMU() except +
        uint8_t read(uint16_t addr)
        void write(uint16_t addr, uint8_t value)
        void load_rom(const uint8_t* data, size_t size)

