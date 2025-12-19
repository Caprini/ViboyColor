# distutils: language = c++

"""
Definición Cython de la clase CPU de C++.

Este archivo .pxd declara la interfaz de la clase CPU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t

# Forward declarations (necesarios para punteros)
cdef extern from "MMU.hpp":
    cdef cppclass MMU:
        pass

cdef extern from "Registers.hpp":
    cdef cppclass CoreRegisters:
        pass

cdef extern from "CPU.hpp":
    cdef cppclass CPU:
        # Constructor: recibe punteros a MMU y CoreRegisters
        CPU(MMU* mmu, CoreRegisters* registers) except +
        
        # Método principal: ejecuta un ciclo de instrucción
        int step()
        
        # Obtiene el contador de ciclos acumulados
        uint32_t get_cycles()

