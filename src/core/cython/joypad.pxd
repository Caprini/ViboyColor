# distutils: language = c++

"""
Definición Cython de la clase Joypad de C++.

Este archivo .pxd declara la interfaz de la clase Joypad para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t

cdef extern from "Joypad.hpp":
    cdef cppclass Joypad:
        # Constructor
        Joypad() except +
        
        # Lee el valor del registro P1 (0xFF00)
        uint8_t read_p1()
        
        # Escribe en el registro P1 (selecciona la fila de botones a leer)
        void write_p1(uint8_t value)
        
        # Simula presionar un botón
        void press_button(int button_index)
        
        # Simula soltar un botón
        void release_button(int button_index)

