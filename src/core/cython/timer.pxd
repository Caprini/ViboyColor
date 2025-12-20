# distutils: language = c++

"""
Definición Cython de la clase Timer de C++.

Este archivo .pxd declara la interfaz de la clase Timer para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t

# Forward declaration de MMU para el constructor
cdef extern from "MMU.hpp":
    cdef cppclass MMU:
        pass

cdef extern from "Timer.hpp":
    cdef cppclass Timer:
        # Constructor (ahora requiere MMU*)
        Timer(MMU* mmu) except +
        
        # Actualiza el Timer con los T-Cycles consumidos
        void step(int t_cycles)
        
        # Lee el valor del registro DIV (Divider)
        uint8_t read_div()
        
        # Escribe en el registro DIV (resetea el contador)
        void write_div()
        
        # Lee el valor del registro TIMA (Timer Counter)
        uint8_t read_tima()
        
        # Escribe en el registro TIMA (Timer Counter)
        void write_tima(uint8_t value)
        
        # Lee el valor del registro TMA (Timer Modulo)
        uint8_t read_tma()
        
        # Escribe en el registro TMA (Timer Modulo)
        void write_tma(uint8_t value)
        
        # Lee el valor del registro TAC (Timer Control)
        uint8_t read_tac()
        
        # Escribe en el registro TAC (Timer Control)
        void write_tac(uint8_t value)

