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
from ppu cimport FrameBufferStats

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
    
    def is_frame_ready(self):
        """
        Step 0467: Verifica si hay un frame listo sin resetear el flag.
        
        Este método permite verificar el estado de frame_ready_ sin afectar
        el estado interno. Útil para tests que necesitan leer el framebuffer
        antes de llamar a get_frame_ready_and_reset().
        
        Returns:
            True si hay un frame listo para renderizar, False en caso contrario
        """
        if self._ppu == NULL:
            return False
        return self._ppu.is_frame_ready()
    
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
    
    def get_framebuffer_indices(self):
        """
        Step 0457: Debug API para tests - Obtiene el framebuffer de índices.
        
        Devuelve memoryview del framebuffer de índices (160×144, valores 0..3).
        
        Returns:
            bytes de 23040 bytes (160*144), valores 0..3 del front buffer
        """
        if self._ppu == NULL:
            return None
        
        cdef const uint8_t* indices_ptr = self._ppu.get_framebuffer_indices_ptr()
        if indices_ptr == NULL:
            return None
        
        # Crear bytes desde el puntero (23040 bytes = 160*144)
        return <bytes>(<uint8_t[:23040]>indices_ptr)
    
    def get_presented_framebuffer_indices(self):
        """
        Step 0468: Obtiene el framebuffer de índices presentado.
        
        Garantiza que devuelve el último frame presentado (hace present automático
        si hay swap pendiente, igual que get_framebuffer()).
        
        Returns:
            bytes de 23040 bytes (160*144), valores 0..3 del frame presentado
        """
        if self._ppu == NULL:
            return None
        
        cdef const uint8_t* indices_ptr = self._ppu.get_presented_framebuffer_indices_ptr()
        if indices_ptr == NULL:
            return None
        
        # Crear bytes desde el puntero (23040 bytes = 160*144)
        return <bytes>(<uint8_t[:23040]>indices_ptr)
    
    def get_vblank_irq_requested_count(self):
        """
        Step 0469: Obtiene el contador de VBlank IRQ solicitados.
        
        Este contador se incrementa cada vez que el PPU solicita una interrupción VBlank
        (cuando LY alcanza 144). Útil para diagnóstico de por qué los juegos no progresan.
        
        Returns:
            Número de veces que se ha solicitado VBlank interrupt
        """
        if self._ppu == NULL:
            return 0
        return self._ppu.get_vblank_irq_requested_count()
    
    def get_framebuffer_stats(self):
        """
        Step 0488: Obtiene estadísticas del framebuffer del último frame.
        
        Devuelve métricas sobre diversidad de colores, cambios entre frames,
        y distribución de índices de color en el framebuffer.
        
        Returns:
            dict con estadísticas del framebuffer o None si no disponible.
            Keys: 'fb_crc32', 'fb_unique_colors', 'fb_nonwhite_count', 
                  'fb_nonblack_count', 'fb_top4_colors', 'fb_top4_colors_count',
                  'fb_changed_since_last'
        """
        if self._ppu == NULL:
            return None
        
        cdef const FrameBufferStats* stats = &self._ppu.get_framebuffer_stats()
        if stats == NULL:
            return None
        
        return {
            'fb_crc32': stats.fb_crc32,
            'fb_unique_colors': stats.fb_unique_colors,
            'fb_nonwhite_count': stats.fb_nonwhite_count,
            'fb_nonblack_count': stats.fb_nonblack_count,
            'fb_top4_colors': [stats.fb_top4_colors[i] for i in range(4)],
            'fb_top4_colors_count': [stats.fb_top4_colors_count[i] for i in range(4)],
            'fb_changed_since_last': stats.fb_changed_since_last,
        }
    
    def get_last_palette_regs_used(self):
        """
        Step 0457: Debug API para tests - Obtiene paleta regs usados en última conversión.
        
        Devuelve paleta regs usados en última llamada a convert_framebuffer_to_rgb().
        
        Returns:
            dict con 'bgp', 'obp0', 'obp1' (valores hex) o None si no disponible
        """
        if self._ppu == NULL:
            return None
        
        try:
            return {
                'bgp': self._ppu.get_last_bgp_used(),
                'obp0': self._ppu.get_last_obp0_used(),
                'obp1': self._ppu.get_last_obp1_used()
            }
        except:
            return None
    
    def get_bg_render_stats(self):
        """
        Step 0458: Debug API para tests - Obtiene estadísticas de renderizado BG.
        
        Devuelve estadísticas de renderizado BG (solo debug, requiere VIBOY_DEBUG_PPU).
        
        Returns:
            dict con 'pixels_written', 'nonzero_seen', 'nonzero_value' o None si no disponible
        """
        if self._ppu == NULL:
            return None
        
        try:
            return {
                'pixels_written': self._ppu.get_bg_pixels_written_count(),
                'nonzero_seen': self._ppu.get_first_nonzero_color_idx_seen(),
                'nonzero_value': self._ppu.get_first_nonzero_color_idx_value()
            }
        except:
            return None
    
    def get_last_tile_bytes_read_info(self):
        """
        Step 0458: Debug API para tests - Obtiene información de bytes VRAM leídos.
        
        Devuelve información de los últimos bytes VRAM leídos por el PPU.
        
        Returns:
            dict con 'bytes' (array de 2 bytes), 'addr', 'valid' o None si no disponible
        """
        if self._ppu == NULL:
            return None
        
        cdef const uint8_t* bytes_ptr
        try:
            bytes_ptr = self._ppu.get_last_tile_bytes_read()
            if bytes_ptr == NULL:
                return None
            
            return {
                'bytes': [bytes_ptr[0], bytes_ptr[1]],
                'addr': self._ppu.get_last_tile_addr_read(),
                'valid': self._ppu.get_last_tile_bytes_valid()
            }
        except:
            return None
    
    def get_last_dmg_convert_samples(self):
        """
        Step 0459: Debug API para tests - Obtiene samples del pipeline idx→shade→rgb.
        
        Devuelve samples del pipeline de conversión (solo debug, requiere VIBOY_DEBUG_PPU).
        
        Returns:
            dict con 'idx', 'shade', 'rgb' (listas), 'count', 'bgp_used' o None si no disponible
        """
        if self._ppu == NULL:
            return None
        
        cdef const uint8_t* idx_ptr
        cdef const uint8_t* shade_ptr
        cdef const uint8_t* rgb_ptr
        cdef int count
        cdef uint8_t bgp
        
        try:
            idx_ptr = self._ppu.get_last_idx_samples()
            shade_ptr = self._ppu.get_last_shade_samples()
            rgb_ptr = self._ppu.get_last_rgb_samples()
            count = self._ppu.get_last_convert_sample_count()
            bgp = self._ppu.get_last_bgp_used_debug()
            
            if idx_ptr == NULL or shade_ptr == NULL or rgb_ptr == NULL:
                return None
            
            idx_list = [idx_ptr[i] for i in range(count)]
            shade_list = [shade_ptr[i] for i in range(count)]
            rgb_list = []
            for i in range(count):
                rgb_list.append((rgb_ptr[i*3], rgb_ptr[i*3+1], rgb_ptr[i*3+2]))
            
            return {
                'idx': idx_list,
                'shade': shade_list,
                'rgb': rgb_list,
                'count': count,
                'bgp_used': bgp
            }
        except:
            return None
    
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

