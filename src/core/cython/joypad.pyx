# distutils: language = c++

"""
Wrapper Cython para Joypad (Subsistema de Entrada del Usuario).

Este módulo expone la clase C++ Joypad a Python, permitiendo
acceso de alta velocidad al registro P1 sin overhead de Python.
"""

from libc.stdint cimport uint8_t

# Importar la definición de la clase C++ desde el archivo .pxd
cimport joypad

cdef class PyJoypad:
    """
    Wrapper Python para Joypad.
    
    Esta clase permite usar Joypad desde Python manteniendo
    el rendimiento de C++ (acceso directo al estado de botones).
    """
    cdef joypad.Joypad* _joypad
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._joypad = new joypad.Joypad()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._joypad != NULL:
            del self._joypad
    
    def read_p1(self) -> int:
        """
        Lee el valor del registro P1 (0xFF00).
        
        El valor devuelto depende de qué fila esté seleccionada (bits 4-5):
        - Si bit 4 = 0: Devuelve el estado de los botones de dirección
        - Si bit 5 = 0: Devuelve el estado de los botones de acción
        - Si ambos bits = 1: Devuelve 0xCF (ninguna fila seleccionada)
        
        Returns:
            Valor del registro P1 (0x00 a 0xFF)
        """
        return self._joypad.read_p1()
    
    def write_p1(self, uint8_t value):
        """
        Escribe en el registro P1 (selecciona la fila de botones a leer).
        
        Solo los bits 4 y 5 son escribibles. El resto se ignoran.
        
        Args:
            value: Valor a escribir (solo bits 4-5 son relevantes)
        """
        self._joypad.write_p1(value)
    
    def press_button(self, int button_index):
        """
        Simula presionar un botón.
        
        Args:
            button_index: Índice del botón (0-7):
                         - 0-3: Botones de dirección (0=Derecha, 1=Izquierda, 2=Arriba, 3=Abajo)
                         - 4-7: Botones de acción (4=A, 5=B, 6=Select, 7=Start)
        """
        self._joypad.press_button(button_index)
    
    def release_button(self, int button_index):
        """
        Simula soltar un botón.
        
        Args:
            button_index: Índice del botón (0-7)
        """
        self._joypad.release_button(button_index)
    
    # Método para obtener el puntero C++ directamente (forma segura)
    cdef joypad.Joypad* get_cpp_ptr(self):
        """
        Obtiene el puntero C++ interno directamente (para uso en otros módulos Cython).
        
        Este método permite que otros wrappers (PyMMU) extraigan el puntero
        C++ directamente sin necesidad de conversiones intermedias.
        
        Returns:
            Puntero C++ a la instancia de Joypad
        """
        return self._joypad

