# distutils: language = c++

"""
Wrapper Cython para Timer (Subsistema de Temporización).

Este módulo expone la clase C++ Timer a Python, permitiendo
acceso de alta velocidad al registro DIV sin overhead de Python.
"""

from libc.stdint cimport uint8_t

# Importar la definición de la clase C++ desde el archivo .pxd
cimport timer

# NOTA: PyMMU está definido en mmu.pyx, que se incluye ANTES de timer.pyx
# en native_core.pyx. Similar a como cpu.pyx usa PyMMU directamente como tipo,
# podemos hacer lo mismo aquí. Cython resolverá PyMMU cuando compile native_core.pyx.

cdef class PyTimer:
    """
    Wrapper Python para Timer.
    
    Esta clase permite usar Timer desde Python manteniendo
    el rendimiento de C++ (acceso directo al contador interno).
    """
    cdef timer.Timer* _timer
    
    def __cinit__(self, PyMMU mmu_wrapper=None):
        """
        Constructor: crea la instancia C++.
        
        Args:
            mmu_wrapper: Instancia opcional de PyMMU para solicitar interrupciones.
                        Si es None, se pasa nullptr (no se pueden solicitar interrupciones).
        """
        cdef timer.MMU* mmu_ptr = NULL
        if mmu_wrapper is not None:
            # Extraer el puntero C++ desde el wrapper PyMMU usando get_cpp_ptr()
            # Como PyMMU está definido en mmu.pyx (incluido antes en native_core.pyx),
            # podemos llamar a get_cpp_ptr() directamente
            mmu_ptr = mmu_wrapper.get_cpp_ptr()
        self._timer = new timer.Timer(mmu_ptr)
    
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
    
    def tick(self, int t_cycles):
        """
        Alias de step() para compatibilidad con SystemClock (Step 0440).
        
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
    
    def read_tima(self) -> int:
        """
        Lee el valor del registro TIMA (Timer Counter, 0xFF05).
        
        TIMA es un contador de 8 bits que se incrementa a la frecuencia
        seleccionada en TAC. Cuando desborda, se recarga con TMA y se
        solicita una interrupción de Timer.
        
        Returns:
            Valor del registro TIMA (0x00 a 0xFF)
        """
        return self._timer.read_tima()
    
    def write_tima(self, int value):
        """
        Escribe en el registro TIMA (Timer Counter, 0xFF05).
        
        Args:
            value: Nuevo valor para TIMA (0x00 a 0xFF)
        """
        self._timer.write_tima(<uint8_t>(value & 0xFF))
    
    def read_tma(self) -> int:
        """
        Lee el valor del registro TMA (Timer Modulo, 0xFF06).
        
        TMA es el valor al que se recarga TIMA cuando desborda.
        
        Returns:
            Valor del registro TMA (0x00 a 0xFF)
        """
        return self._timer.read_tma()
    
    def write_tma(self, int value):
        """
        Escribe en el registro TMA (Timer Modulo, 0xFF06).
        
        Args:
            value: Nuevo valor para TMA (0x00 a 0xFF)
        """
        self._timer.write_tma(<uint8_t>(value & 0xFF))
    
    def read_tac(self) -> int:
        """
        Lee el valor del registro TAC (Timer Control, 0xFF07).
        
        TAC controla el Timer:
        - Bit 2: Timer Enable (1 = ON, 0 = OFF)
        - Bits 1-0: Input Clock Select (frecuencia)
          - 00: 4096 Hz
          - 01: 262144 Hz
          - 10: 65536 Hz
          - 11: 16384 Hz
        
        Returns:
            Valor del registro TAC (solo bits 0-2 son significativos)
        """
        return self._timer.read_tac()
    
    def write_tac(self, int value):
        """
        Escribe en el registro TAC (Timer Control, 0xFF07).
        
        Args:
            value: Nuevo valor para TAC (solo bits 0-2 son significativos)
        """
        self._timer.write_tac(<uint8_t>(value & 0xFF))
    
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

