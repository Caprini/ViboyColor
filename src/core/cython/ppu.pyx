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
    cdef object _mmu_wrapper  # CRÍTICO: Mantener referencia al wrapper para evitar destrucción
    
    def __cinit__(self, PyMMU mmu_wrapper):
        """
        Constructor: crea la instancia C++ con una referencia a MMU.
        
        Args:
            mmu_wrapper: Instancia de PyMMU (debe tener un atributo _mmu válido)
        """
        # CRÍTICO: Verificar que mmu_wrapper y su puntero interno sean válidos
        if mmu_wrapper is None:
            raise ValueError("PyPPU: mmu_wrapper no puede ser None")
        
        # CRÍTICO: Mantener una referencia al wrapper para evitar que se destruya
        # Esto asegura que el objeto MMU C++ siga existiendo mientras PPU lo use
        self._mmu_wrapper = mmu_wrapper
        
        # Extrae el puntero C++ crudo desde el wrapper de la MMU
        cdef mmu.MMU* mmu_ptr = (<PyMMU>mmu_wrapper)._mmu
        
        # Comprobación de seguridad: Asegurarse de que el puntero de la MMU no es nulo
        if mmu_ptr == NULL:
            raise ValueError("Se intentó crear PyPPU con un wrapper de MMU inválido (puntero nulo).")
        
        # --- LÍNEA CRÍTICA ---
        # Crea la instancia de PPU en C++ y asigna el puntero
        self._ppu = new ppu.PPU(mmu_ptr)
        
        # Comprobación de seguridad: Asegurarse de que la creación fue exitosa
        if self._ppu == NULL:
            raise MemoryError("Falló la asignación de memoria para la PPU en C++.")
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._ppu != NULL:
            del self._ppu
            self._ppu = NULL  # Buena práctica para evitar punteros colgantes
    
    def step(self, int cpu_cycles):
        """
        Avanza el motor de timing de la PPU según los ciclos de reloj consumidos.
        
        Este método debe llamarse después de cada instrucción de la CPU, pasando
        los T-Cycles (ciclos de reloj) consumidos.
        
        Args:
            cpu_cycles: Número de T-Cycles (ciclos de reloj) a procesar
        """
        # CRÍTICO: Verificar que el puntero C++ no sea nulo antes de usarlo
        if self._ppu == NULL:
            return
        
        self._ppu.step(cpu_cycles)
    
    def get_ly(self):
        """
        Obtiene el valor actual del registro LY (Línea actual).
        
        Returns:
            Valor de LY (0-153)
        """
        if self._ppu == NULL:
            return 0
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
        if self._ppu == NULL:
            return 0
        return self._ppu.get_mode()
    
    def get_lyc(self):
        """
        Obtiene el valor actual del registro LYC (LY Compare).
        
        Returns:
            Valor de LYC (0-255)
        """
        if self._ppu == NULL:
            return 0
        return self._ppu.get_lyc()
    
    def set_lyc(self, uint8_t value):
        """
        Establece el valor del registro LYC (LY Compare).
        
        Cuando LYC cambia, se verifica inmediatamente si LY == LYC para
        actualizar el bit 2 de STAT y solicitar interrupción si corresponde.
        
        Args:
            value: Valor a escribir en LYC (se enmascara a 8 bits)
        """
        if self._ppu == NULL:
            return
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
        if self._ppu == NULL:
            return False
        return self._ppu.get_frame_ready_and_reset()
    
    # Propiedades para acceso directo (más Pythonic)
    property ly:
        """Propiedad para obtener LY."""
        def __get__(self):
            if self._ppu == NULL:
                return 0
            return self.get_ly()
    
    property mode:
        """Propiedad para obtener el modo PPU."""
        def __get__(self):
            if self._ppu == NULL:
                return 0
            return self.get_mode()
    
    property lyc:
        """Propiedad para obtener/establecer LYC."""
        def __get__(self):
            if self._ppu == NULL:
                return 0
            return self.get_lyc()
        def __set__(self, uint8_t value):
            if self._ppu == NULL:
                return
            self.set_lyc(value)
    
    def get_framebuffer(self):
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
        if self._ppu == NULL:
            # Retornar None si el puntero es NULL
            return None
        
        cdef uint8_t* ptr = self._ppu.get_framebuffer_ptr()
        
        if ptr == NULL:
            return None
        
        cdef unsigned char[:] view = <unsigned char[:144*160]>ptr
        
        return view
    
    def get_framebuffer_rgb(self):
        """
        Step 0404: Obtiene el framebuffer RGB888 como un memoryview (Zero-Copy).
        
        El framebuffer RGB es un array de 160 * 144 * 3 = 69120 bytes (R, G, B por píxel).
        Cada píxel tiene 3 bytes: Red (0-255), Green (0-255), Blue (0-255).
        
        Este framebuffer se usa en modo CGB para renderizar con paletas CGB reales (BGR555 → RGB888).
        En modo DMG, se puede ignorar y usar el framebuffer de índices con BGP.
        
        El framebuffer está organizado en filas: píxel (y, x) está en índice [(y * 160 + x) * 3].
        
        Returns:
            memoryview de uint8_t 1D con 69120 elementos - Zero-Copy directo a memoria C++.
            Python puede leer RGB usando [idx*3+0] (R), [idx*3+1] (G), [idx*3+2] (B).
        """
        if self._ppu == NULL:
            # Retornar None si el puntero es NULL
            return None
        
        cdef uint8_t* ptr = self._ppu.get_framebuffer_rgb_ptr()
        
        if ptr == NULL:
            return None
        
        cdef unsigned char[:] view = <unsigned char[:144*160*3]>ptr
        
        return view
    
    @property
    def framebuffer(self):
        """
        Propiedad para acceso al framebuffer (compatibilidad con tests existentes).
        
        Returns:
            memoryview de uint8_t 1D con 23040 elementos - Zero-Copy directo a memoria C++.
        """
        return self.get_framebuffer()
    
    def clear_framebuffer(self):
        """
        Limpia el framebuffer, estableciendo todos los píxeles a índice 0 (blanco por defecto).
        
        Este método debe llamarse al inicio de cada fotograma para asegurar que el
        renderizado comienza desde un estado limpio. En hardware real, esto ocurre
        implícitamente porque cada píxel se redibuja en cada ciclo, pero en nuestro
        modelo de emulación, cuando el fondo está apagado (LCDC bit 0 = 0), no se
        renderiza nada y el framebuffer conserva los datos del fotograma anterior.
        
        Fuente: Práctica estándar de gráficos por ordenador (Back Buffer Clearing).
        """
        if self._ppu == NULL:
            return
        self._ppu.clear_framebuffer()
    
    def confirm_framebuffer_read(self):
        """
        Step 0360: Confirma que Python leyó el framebuffer.
        
        Este método debe llamarse después de que Python termine de leer el framebuffer.
        Permite que C++ limpie el framebuffer de forma segura sin condiciones de carrera.
        """
        if self._ppu == NULL:
            return
        self._ppu.confirm_framebuffer_read()
    
    # Método para obtener el puntero C++ como entero (DEPRECADO: usar get_cpp_ptr() en su lugar)
    def get_cpp_ptr_as_int(self):
        """Obtiene el puntero C++ interno como entero (para uso en otros módulos Cython)."""
        if self._ppu == NULL:
            return 0
        return <long>self._ppu
    
    # Método para obtener el puntero C++ directamente (forma segura)
    cdef ppu.PPU* get_cpp_ptr(self):
        """Obtiene el puntero C++ interno directamente (para uso en otros módulos Cython)."""
        return self._ppu
    
    def get_framebuffer_snapshot(self):
        """
        Step 0395: Obtiene un snapshot del framebuffer completo como array NumPy.
        
        Returns:
            numpy.ndarray de uint8 con forma (144, 160) - Zero-Copy desde C++
        """
        if self._ppu == NULL:
            return None
        
        import numpy as np
        cdef uint8_t* ptr = self._ppu.get_framebuffer_ptr()
        
        if ptr == NULL:
            return None
        
        # Crear array NumPy desde el memoryview (Zero-Copy)
        cdef unsigned char[:] view = <unsigned char[:144*160]>ptr
        arr = np.asarray(view)
        
        # Reshape a (144, 160) para facilitar análisis
        return arr.reshape((144, 160))

