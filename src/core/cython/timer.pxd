# distutils: language = c++

"""
Definición Cython de la clase Timer de C++.

Este archivo .pxd declara la interfaz de la clase Timer para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t

cdef extern from "Timer.hpp":
    cdef cppclass Timer:
        # Constructor
        Timer() except +
        
        # Actualiza el Timer con los T-Cycles consumidos
        void step(int t_cycles)
        
        # Lee el valor del registro DIV (Divider)
        uint8_t read_div()
        
        # Escribe en el registro DIV (resetea el contador)
        void write_div()

