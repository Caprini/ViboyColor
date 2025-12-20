# distutils: language = c++

"""
Wrapper Cython para Timer (Subsistema de Temporización).

Este módulo expone la clase C++ Timer a Python, permitiendo
acceso de alta velocidad al registro DIV sin overhead de Python.
"""

from libc.stdint cimport uint8_t

# Importar la definición de la clase C++ desde el archivo .pxd
cimport timer

cdef class PyTimer:
    """
    Wrapper Python para Timer.
    
    Esta clase permite usar Timer desde Python manteniendo
    el rendimiento de C++ (acceso directo al contador interno).
    """
    cdef timer.Timer* _timer
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._timer = new timer.Timer()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._timer != NULL:
            del self._timer
    
    def step(self, int t_cycles):
        """
        Actualiza el Timer con los T-Cycles consumidos.
        
        Este método debe ser llamado desde el bucle de emulación principal
        después de cada instrucción de la CPU para mantener la sincronización
        del tiempo emulado.
        
        Args:
            t_cycles: Número de T-Cycles a agregar al contador interno
        """
        self._timer.step(t_cycles)
    
    def read_div(self) -> int:
        """
        Lee el valor del registro DIV (Divider).
        
        DIV es los 8 bits altos del contador interno de 16 bits.
        Se incrementa cada 256 T-Cycles (frecuencia de 16384 Hz).
        
        Returns:
            Valor del registro DIV (0x00 a 0xFF)
        """
        return self._timer.read_div()
    
    def write_div(self):
        """
        Escribe en el registro DIV (resetea el contador).
        
        Cualquier escritura en 0xFF04 tiene el efecto secundario de resetear
        el contador interno a 0. El valor escrito es ignorado.
        """
        self._timer.write_div()
    
    # Método para obtener el puntero C++ directamente (forma segura)
    cdef timer.Timer* get_cpp_ptr(self):
        """
        Obtiene el puntero C++ interno directamente (para uso en otros módulos Cython).
        
        Este método permite que otros wrappers (PyCPU, PyMMU) extraigan el puntero
        C++ directamente sin necesidad de conversiones intermedias.
        
        Returns:
            Puntero C++ a la instancia de Timer
        """
        return self._timer

