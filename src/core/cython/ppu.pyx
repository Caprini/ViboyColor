# distutils: language = c++

"""
Wrapper Cython para PPU (Pixel Processing Unit).

Este módulo expone la clase C++ PPU a Python, permitiendo
acceso de alta velocidad al motor de timing de la PPU.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp cimport bool

# Importar la definición de la clase C++ desde el archivo .pxd
cimport ppu
cimport mmu

# NOTA: PyMMU está definido en mmu.pyx, que está incluido en native_core.pyx
# El atributo _mmu es accesible directamente desde otros módulos Cython

cdef class PyPPU:
    """
    Wrapper Python para PPU.
    
    Esta clase permite usar PPU desde Python manteniendo
    el rendimiento de C++ (ciclo a ciclo sin overhead).
    """
    cdef ppu.PPU* _ppu
    
    def __cinit__(self, PyMMU mmu):
        """
        Constructor: crea la instancia C++ con una referencia a MMU.
        
        Args:
            mmu: Instancia de PyMMU (debe tener un atributo _mmu válido)
        """
        self._ppu = new ppu.PPU(mmu._mmu)
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._ppu != NULL:
            del self._ppu
    
    def step(self, int cpu_cycles):
        """
        Avanza el motor de timing de la PPU según los ciclos de reloj consumidos.
        
        Este método debe llamarse después de cada instrucción de la CPU, pasando
        los T-Cycles (ciclos de reloj) consumidos.
        
        Args:
            cpu_cycles: Número de T-Cycles (ciclos de reloj) a procesar
        """
        self._ppu.step(cpu_cycles)
    
    def get_ly(self):
        """
        Obtiene el valor actual del registro LY (Línea actual).
        
        Returns:
            Valor de LY (0-153)
        """
        return self._ppu.get_ly()
    
    def get_mode(self):
        """
        Obtiene el modo PPU actual (0, 1, 2 o 3).
        
        Returns:
            Modo PPU actual:
            - 0: H-Blank (CPU puede acceder a VRAM)
            - 1: V-Blank (CPU puede acceder a VRAM)
            - 2: OAM Search (CPU bloqueada de OAM)
            - 3: Pixel Transfer (CPU bloqueada de VRAM y OAM)
        """
        return self._ppu.get_mode()
    
    def get_lyc(self):
        """
        Obtiene el valor actual del registro LYC (LY Compare).
        
        Returns:
            Valor de LYC (0-255)
        """
        return self._ppu.get_lyc()
    
    def set_lyc(self, uint8_t value):
        """
        Establece el valor del registro LYC (LY Compare).
        
        Cuando LYC cambia, se verifica inmediatamente si LY == LYC para
        actualizar el bit 2 de STAT y solicitar interrupción si corresponde.
        
        Args:
            value: Valor a escribir en LYC (se enmascara a 8 bits)
        """
        self._ppu.set_lyc(value)
    
    def get_frame_ready_and_reset(self):
        """
        Comprueba si hay un frame listo para renderizar y resetea el flag.
        
        Este método permite desacoplar el renderizado de las interrupciones.
        Implementa un patrón de "máquina de estados de un solo uso": si la bandera
        está levantada, la devuelve como true e inmediatamente la baja a false.
        
        Returns:
            True si hay un frame listo para renderizar, False en caso contrario
        """
        return self._ppu.get_frame_ready_and_reset()
    
    # Propiedades para acceso directo (más Pythonic)
    property ly:
        """Propiedad para obtener LY."""
        def __get__(self):
            return self.get_ly()
    
    property mode:
        """Propiedad para obtener el modo PPU."""
        def __get__(self):
            return self.get_mode()
    
    property lyc:
        """Propiedad para obtener/establecer LYC."""
        def __get__(self):
            return self.get_lyc()
        def __set__(self, uint8_t value):
            self.set_lyc(value)
    
    @property
    def framebuffer(self):
        """
        Obtiene el framebuffer como un memoryview de índices de color (Zero-Copy).
        
        El framebuffer es un array de 160 * 144 = 23040 píxeles con índices de color (0-3).
        Cada píxel es un uint8_t que representa un índice en la paleta BGP.
        Los colores finales se aplican en Python usando la paleta del registro BGP (0xFF47).
        
        El framebuffer está organizado en filas: píxel (y, x) está en índice [y * 160 + x].
        
        Returns:
            memoryview de uint8_t 1D con 23040 elementos - Zero-Copy directo a memoria C++.
            Python puede leer estos índices usando [y * 160 + x] y aplicar la paleta sin copiar los datos.
        """
        cdef uint8_t* ptr = self._ppu.get_framebuffer_ptr()
        cdef unsigned char[:] view = <unsigned char[:144*160]>ptr
        return view

