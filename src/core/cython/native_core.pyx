# distutils: language = c++

"""
Wrapper Cython para NativeCore.

Este módulo expone la clase C++ NativeCore a Python, permitiendo
que el código Python llame a funciones C++ compiladas.

También incluye el módulo MMU para gestión de memoria de alta velocidad.
"""

from libcpp cimport bool

# Declaración de la clase C++ (cdef extern)
# La ruta se resuelve usando include_dirs en setup.py
cdef extern from "NativeCore.hpp":
    cdef cppclass NativeCore:
        NativeCore() except +
        int add(int a, int b)

# Incluir el módulo MMU
include "mmu.pyx"

# Clase Python que envuelve la clase C++
cdef class PyNativeCore:
    """
    Wrapper Python para NativeCore.
    
    Esta clase permite usar NativeCore desde Python manteniendo
    el rendimiento de C++.
    """
    cdef NativeCore* _core
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._core = new NativeCore()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._core != NULL:
            del self._core
    
    def add(self, int a, int b):
        """
        Suma dos enteros usando código C++.
        
        Args:
            a: Primer operando
            b: Segundo operando
            
        Returns:
            Suma de a + b
        """
        return self._core.add(a, b)

