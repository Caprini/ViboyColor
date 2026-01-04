# distutils: language = c++

"""
Wrapper Cython para MMU (Memory Management Unit).

Este módulo expone la clase C++ MMU a Python, permitiendo
acceso de alta velocidad a la memoria del Game Boy.
"""

from libc.stdint cimport uint8_t, uint16_t
from libc.stdlib cimport malloc, free
from libcpp cimport bool

# Importar la definición de la clase C++ desde el archivo .pxd
cimport mmu
cimport ppu
cimport timer
cimport joypad

# NOTA: PyPPU se define en ppu.pyx, pero como native_core.pyx incluye ambos módulos,
# PyPPU estará disponible en tiempo de ejecución. Para evitar dependencia circular,
# declaramos PyPPU como forward declaration aquí.
cdef class PyMMU:
    """
    Wrapper Python para MMU.
    
    Esta clase permite usar MMU desde Python manteniendo
    el rendimiento de C++ (acceso directo a memoria sin overhead).
    """
    cdef mmu.MMU* _mmu
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._mmu = new mmu.MMU()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._mmu != NULL:
            del self._mmu
    
    def read(self, uint16_t addr):
        """
        Lee un byte (8 bits) de la dirección especificada.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
        """
        return self._mmu.read(addr)
    
    def write(self, uint16_t addr, uint8_t value):
        """
        Escribe un byte (8 bits) en la dirección especificada.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (0x00 a 0xFF)
        """
        self._mmu.write(addr, value)
    
    def load_rom_py(self, bytes rom_data):
        """
        Carga datos ROM en memoria, empezando en la dirección 0x0000.
        
        Este método recibe bytes de Python, obtiene su puntero y longitud,
        y llama al método C++ load_rom.
        
        Args:
            rom_data: Bytes de Python con los datos ROM
        """
        # Obtener puntero y longitud de los bytes de Python
        cdef const uint8_t* data_ptr = <const uint8_t*>rom_data
        cdef size_t data_size = len(rom_data)
        
        # Llamar al método C++
        self._mmu.load_rom(data_ptr, data_size)
    
    # ============================================================
    # MÉTODOS DE COMPATIBILIDAD CON API PYTHON ANTIGUA
    # ============================================================
    # El código Python existente (renderer.py, cpu/core.py) espera
    # métodos read_byte/write_byte/read_word/write_word.
    # Estos métodos son alias que mantienen la retrocompatibilidad.
    
    def read_byte(self, uint16_t addr):
        """
        Alias de read() para compatibilidad con código Python antiguo.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
        """
        return self.read(addr)
    
    def write_byte(self, uint16_t addr, uint8_t value):
        """
        Alias de write() para compatibilidad con código Python antiguo.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (0x00 a 0xFF)
        """
        self.write(addr, value)
    
    def read_word(self, uint16_t addr):
        """
        Lee una palabra (16 bits) usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian:
        - LSB en addr, MSB en addr+1
        - Resultado: (MSB << 8) | LSB
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE)
            
        Returns:
            Valor de 16 bits leído (0x0000 a 0xFFFF)
        """
        # Leer LSB (menos significativo) en addr
        cdef uint8_t lsb = self.read(addr)
        
        # Leer MSB (más significativo) en addr+1 (con wrap-around)
        cdef uint8_t msb = self.read((addr + 1) & 0xFFFF)
        
        # Combinar en Little-Endian: (MSB << 8) | LSB
        return ((msb << 8) | lsb) & 0xFFFF
    
    def write_word(self, uint16_t addr, uint16_t value):
        """
        Escribe una palabra (16 bits) usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian:
        - LSB se escribe en addr
        - MSB se escribe en addr+1
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE)
            value: Valor de 16 bits a escribir
        """
        # Extraer LSB y MSB
        cdef uint8_t lsb = value & 0xFF
        cdef uint8_t msb = (value >> 8) & 0xFF
        
        # Escribir en orden Little-Endian
        self.write(addr, lsb)
        self.write((addr + 1) & 0xFFFF, msb)
    
    def set_ppu(self, object ppu_wrapper):
        """
        Conecta la PPU a la MMU.
        
        Esta es la forma correcta y segura de pasar punteros entre objetos envueltos.
        El puntero PPU* se extrae directamente del wrapper PyPPU sin conversiones
        intermedias a enteros, evitando la corrupción de la dirección de memoria.
        
        Args:
            ppu_wrapper: Instancia de PyPPU
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        if ppu_wrapper is None:
            raise ValueError("Se intentó conectar una PPU nula a la MMU.")

        # --- CORRECCIÓN CRÍTICA ---
        # Extrae el puntero PPU* directamente del objeto wrapper PyPPU
        # usando el método get_cpp_ptr() que devuelve el puntero directamente
        # sin pasar por conversión a int (que corrompía la dirección de memoria)
        # PyPPU está declarado como forward declaration a nivel de módulo
        cdef ppu.PPU* ppu_ptr = NULL
        
        # Hacer el cast a PyPPU y llamar al método get_cpp_ptr()
        ppu_ptr = (<PyPPU>ppu_wrapper).get_cpp_ptr()

        # Llama al método C++ con el puntero C++ correcto
        self._mmu.setPPU(ppu_ptr)
    
    def set_timer(self, object timer_wrapper):
        """
        Conecta el Timer a la MMU para permitir lectura/escritura del registro DIV.
        
        El registro DIV (0xFF04) es actualizado dinámicamente por el Timer.
        Para leer el valor correcto, la MMU necesita llamar a Timer::read_div()
        cuando se lee 0xFF04. Para escribir, llama a Timer::write_div().
        
        Args:
            timer_wrapper: Instancia de PyTimer (debe tener un método get_cpp_ptr() válido) o None
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        if timer_wrapper is None:
            raise ValueError("Se intentó conectar un Timer nulo a la MMU.")
        
        # Extrae el puntero Timer* directamente del objeto wrapper PyTimer
        # usando el método get_cpp_ptr() que devuelve el puntero directamente
        cdef timer.Timer* timer_ptr = NULL
        
        # Hacer el cast a PyTimer y llamar al método get_cpp_ptr()
        timer_ptr = (<PyTimer>timer_wrapper).get_cpp_ptr()
        
        # Llama al método C++ con el puntero C++ correcto
        self._mmu.setTimer(timer_ptr)
    
    def set_joypad(self, object joypad_wrapper):
        """
        Conecta el Joypad a la MMU para permitir lectura/escritura del registro P1.
        
        El registro P1 (0xFF00) es controlado por el Joypad. La CPU escribe en P1
        para seleccionar qué fila de botones leer (direcciones o acciones), y lee
        el estado de los botones de la fila seleccionada.
        
        Args:
            joypad_wrapper: Instancia de PyJoypad (debe tener un método get_cpp_ptr() válido) o None
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        if joypad_wrapper is None:
            raise ValueError("Se intentó conectar un Joypad nulo a la MMU.")
        
        # Extrae el puntero Joypad* directamente del objeto wrapper PyJoypad
        # usando el método get_cpp_ptr() que devuelve el puntero directamente
        cdef joypad.Joypad* joypad_ptr = NULL
        
        # Hacer el cast a PyJoypad y llamar al método get_cpp_ptr()
        joypad_ptr = (<PyJoypad>joypad_wrapper).get_cpp_ptr()
        
        # Llama al método C++ con el puntero C++ correcto
        self._mmu.setJoypad(joypad_ptr)
    
    def request_interrupt(self, uint8_t bit):
        """
        Solicita una interrupción activando el bit correspondiente en el registro IF (0xFF0F).
        
        Este método permite que componentes del hardware (PPU, Timer, etc.) soliciten
        interrupciones escribiendo en el registro IF. La CPU procesará estas interrupciones
        cuando IME esté activo y haya bits activos en IE & IF.
        
        Args:
            bit: Número de bit a activar (0-4):
                - 0: V-Blank Interrupt
                - 1: LCD STAT Interrupt
                - 2: Timer Interrupt
                - 3: Serial Interrupt
                - 4: Joypad Interrupt
        """
        self._mmu.request_interrupt(bit)
    
    # --- Step 0298: Hack Temporal - Carga Manual de Tiles ---
    def load_test_tiles(self):
        """
        Carga tiles básicos de prueba en VRAM para poder avanzar con el desarrollo
        del emulador mientras se investiga por qué el juego no carga tiles automáticamente.
        
        Esta es una función temporal de desarrollo. Se eliminará una vez que se identifique
        y corrija el problema real de carga de tiles.
        
        Carga:
        - Tile 0: Blanco (todos 0x00)
        - Tile 1: Patrón de cuadros alternados (checkerboard)
        - Tile 2: Líneas horizontales
        - Tile 3: Líneas verticales
        
        También configura el Tile Map básico para mostrar los tiles.
        """
        self._mmu.load_test_tiles()
    # --- Fin Step 0298 ---
    
    # --- Step 0401: Boot ROM opcional ---
    def set_boot_rom(self, bytes boot_rom_data):
        """
        Carga una Boot ROM opcional (provista por el usuario, no incluida en el repo).
        
        La Boot ROM se mapea sobre el rango de la ROM del cartucho:
        - DMG (256 bytes): 0x0000-0x00FF
        - CGB (2304 bytes): 0x0000-0x00FF + 0x0200-0x08FF
        
        La Boot ROM se deshabilita al escribir cualquier valor != 0 al registro 0xFF50.
        
        Args:
            boot_rom_data: Bytes de Python con los datos de la Boot ROM
                          (256 bytes para DMG, 2304 bytes para CGB)
        
        Fuente: Pan Docs - "Boot ROM", "FF50 - BOOT - Boot ROM disable"
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        # Obtener puntero y longitud de los bytes de Python
        cdef const uint8_t* data_ptr = <const uint8_t*>boot_rom_data
        cdef size_t data_size = len(boot_rom_data)
        
        # Llamar al método C++
        self._mmu.set_boot_rom(data_ptr, data_size)
    
    def is_boot_rom_enabled(self):
        """
        Verifica si la Boot ROM está habilitada y mapeada.
        
        Returns:
            1 si la Boot ROM está habilitada, 0 en caso contrario (compatible con bool de Python)
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        # El método C++ ahora devuelve int directamente para evitar problemas de conversión
        return self._mmu.is_boot_rom_enabled()
    # --- Fin Step 0401 ---
    
    # --- Step 0402: Modo stub de Boot ROM ---
    def enable_bootrom_stub(self, bool enable, bool cgb_mode=False):
        """
        Habilita el modo stub de Boot ROM (sin binario propietario).
        
        El stub NO emula instrucciones reales del boot. Solo fuerza un conjunto mínimo
        de estado post-boot documentado (Pan Docs) y marca boot_rom_enabled_=false
        inmediatamente.
        
        Args:
            enable: True para habilitar stub, False para desactivar
            cgb_mode: True para modo CGB, False para modo DMG
        
        Nota: Este stub es diferente de "boot real". Solo valida que el pipeline de
        inicialización y el control de PC no dependen de hacks del PPU.
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.enable_bootrom_stub(enable, cgb_mode)
    # --- Fin Step 0402 ---
    
    # --- Step 0404: Hardware Mode Management ---
    def set_hardware_mode(self, str mode):
        """
        Configura el modo de hardware (DMG o CGB).
        
        Establece si el emulador debe comportarse como Game Boy clásico (DMG)
        o Game Boy Color (CGB). Esto afecta la inicialización de registros I/O
        y el comportamiento de componentes específicos (paletas, banking, etc.).
        
        Args:
            mode: String "DMG" o "CGB"
        
        Raises:
            ValueError: Si el modo no es "DMG" o "CGB"
            MemoryError: Si la instancia de MMU en C++ no existe
        
        Fuente: Pan Docs - Power Up Sequence, CGB Registers
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        if mode.upper() == "DMG":
            self._mmu.set_hardware_mode(mmu.HardwareMode.DMG)
        elif mode.upper() == "CGB":
            self._mmu.set_hardware_mode(mmu.HardwareMode.CGB)
        else:
            raise ValueError(f"Modo de hardware inválido: {mode}. Debe ser 'DMG' o 'CGB'")
    
    def get_hardware_mode(self):
        """
        Obtiene el modo de hardware actual.
        
        Returns:
            String "DMG" o "CGB" según el modo actual
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        cdef mmu.HardwareMode mode = self._mmu.get_hardware_mode()
        return "CGB" if mode == mmu.HardwareMode.CGB else "DMG"
    
    def initialize_io_registers(self):
        """
        Inicializa registros I/O según el modo de hardware actual.
        
        Configura los registros I/O (LCDC, BGP, CGB-specific, etc.) según el modo
        de hardware actual (DMG o CGB) siguiendo la Power Up Sequence de Pan Docs.
        
        Llamado automáticamente por:
        - Constructor MMU() para valores iniciales
        - set_hardware_mode() cuando se cambia el modo
        - enable_bootrom_stub() para aplicar estado post-boot
        
        También puede llamarse manualmente para reinicializar registros.
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        
        Fuente: Pan Docs - Power Up Sequence
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.initialize_io_registers()
    # --- Fin Step 0404 ---
    
    # --- Step 0425: Eliminado set_test_mode_allow_rom_writes() (hack no spec-correct) ---
    # Los tests que necesiten ROM personalizada deben usar load_rom() con bytearray preparado.
    # -------------------------------------------
    
    # --- Step 0410: Resumen de DMA/VRAM ---
    def log_dma_vram_summary(self):
        """
        Genera resumen completo de actividad DMA/HDMA y escrituras VRAM.
        
        Muestra contadores de:
        - OAM DMA (0xFF46)
        - HDMA (0xFF51-0xFF55)
        - Escrituras CPU a TileData (0x8000-0x97FF)
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.log_dma_vram_summary()
    # --- Fin Step 0410 ---
    
    # --- Step 0434: Triage Mode ---
    def set_triage_mode(self, bool active):
        """
        Activa/desactiva triage mode para diagnóstico.
        
        Args:
            active: True para activar, False para desactivar
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.set_triage_mode(active)
    
    def log_triage_summary(self):
        """
        Genera resumen de triage (debe llamarse después de ejecutar).
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.log_triage_summary()
    # --- Fin Step 0434 ---
    
    # --- Step 0436: Pokemon Loop Trace ---
    def set_pokemon_loop_trace(self, bool active):
        """
        Activa/desactiva Pokemon loop trace (Fase A del Step 0436).
        Captura writes VRAM cuando PC está en 0x36E2-0x36E7.
        
        Args:
            active: True para activar, False para desactivar
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.set_pokemon_loop_trace(active)
    
    def log_pokemon_loop_trace_summary(self):
        """
        Genera resumen de Pokemon loop trace (Fase A).
        Muestra unique_addr_count, min/max addr, 5 ejemplos (pc,addr,val,hl).
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.log_pokemon_loop_trace_summary()
    
    def set_current_hl(self, uint16_t hl_value):
        """
        Registra valor actual de HL (llamado desde CPU para captura completa).
        
        Args:
            hl_value: Valor actual del registro HL
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.set_current_hl(hl_value)
    # --- Fin Step 0436 ---
    
    # --- Step 0450: Raw read for diagnostics ---
    def get_ie_write_count(self):
        """
        Step 0470: Obtiene el contador de writes a IE (0xFFFF).
        
        Returns:
            Número de veces que se ha escrito a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_write_count()
    
    def get_if_write_count(self):
        """
        Step 0470: Obtiene el contador de writes a IF (0xFF0F).
        
        Returns:
            Número de veces que se ha escrito a IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_write_count()
    
    def get_last_ie_written(self):
        """
        Step 0470: Obtiene el último valor escrito a IE (0xFFFF).
        
        Returns:
            Último valor escrito a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ie_written()
    
    def get_last_if_written(self):
        """
        Step 0470: Obtiene el último valor escrito a IF (0xFF0F).
        
        Returns:
            Último valor escrito a IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_if_written()
    
    def get_io_read_count(self, uint16_t addr):
        """
        Step 0470: Obtiene el contador de lecturas de una dirección IO específica.
        
        Args:
            addr: Dirección IO (0xFF00, 0xFF41, 0xFF44, 0xFF0F, 0xFFFF, 0xFF4D, 0xFF4F, 0xFF70)
        
        Returns:
            Número de veces que se ha leído esa dirección
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_io_read_count(addr)
    
    def get_last_ie_write_value(self):
        """
        Step 0471: Obtiene el último valor escrito a IE (0xFFFF).
        
        Returns:
            Último valor escrito a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ie_write_value()
    
    def get_last_ie_write_pc(self):
        """
        Step 0471: Obtiene el PC del último write a IE (0xFFFF).
        
        Returns:
            PC del último write a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ie_write_pc()
    
    def get_last_ie_read_value(self):
        """
        Step 0471: Obtiene el último valor leído de IE (0xFFFF).
        
        Returns:
            Último valor leído de IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ie_read_value()
    
    def get_ie_read_count(self):
        """
        Step 0471: Obtiene el contador de lecturas de IE (0xFFFF).
        
        Returns:
            Número de veces que se ha leído IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_read_count()
    
    def get_key1_write_count(self):
        """
        Step 0472: Obtiene el contador de writes a KEY1 (0xFF4D).
        
        Returns:
            Número de veces que se ha escrito a KEY1
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_key1_write_count()
    
    def get_last_key1_write_value(self):
        """
        Step 0472: Obtiene el último valor escrito a KEY1 (0xFF4D).
        
        Returns:
            Último valor escrito a KEY1
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_key1_write_value()
    
    def get_last_key1_write_pc(self):
        """
        Step 0472: Obtiene el PC del último write a KEY1 (0xFF4D).
        
        Returns:
            PC del último write a KEY1
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_key1_write_pc()
    
    def get_joyp_write_count(self):
        """
        Step 0472: Obtiene el contador de writes a JOYP (0xFF00).
        
        Returns:
            Número de veces que se ha escrito a JOYP
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_write_count()
    
    def get_last_joyp_write_value(self):
        """
        Step 0472: Obtiene el último valor escrito a JOYP (0xFF00).
        
        Returns:
            Último valor escrito a JOYP
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_joyp_write_value()
    
    def get_last_joyp_write_pc(self):
        """
        Step 0472: Obtiene el PC del último write a JOYP (0xFF00).
        
        Returns:
            PC del último write a JOYP
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_joyp_write_pc()
    
    def read_raw(self, uint16_t addr):
        """
        Raw read for diagnostics (bypasses access restrictions).
        
        WARNING: Only for diagnostics/tools, NOT for emulation.
        This directly reads memory_[] without PPU mode checks, banking, etc.
        
        Args:
            addr: Memory address (0x0000-0xFFFF)
        
        Returns:
            Raw byte value from memory_[]
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        return self._mmu.read_raw(addr)
    
    def dump_raw_range(self, uint16_t start, uint16_t length):
        """
        Dump raw memory range for fast sampling.
        
        WARNING: Only for diagnostics, bypasses restrictions.
        
        Args:
            start: Start address
            length: Number of bytes to dump
        
        Returns:
            bytes object with raw memory dump
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe o falla la asignación
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        # Allocate buffer in C
        cdef uint8_t* buffer = <uint8_t*>malloc(length)
        if buffer == NULL:
            raise MemoryError("Failed to allocate buffer")
        
        try:
            self._mmu.dump_raw_range(start, length, buffer)
            # Convert to Python bytes by creating a list and converting to bytes
            # This avoids issues with buffer lifetime
            result_list = []
            for i in range(length):
                result_list.append(buffer[i])
            return bytes(result_list)
        finally:
            free(buffer)
    
    def log_mbc_writes_summary(self):
        """
        Log summary of MBC writes (debug-gated).
        
        Muestra contadores y últimos 8 writes a rangos MBC (0x0000-0x7FFF).
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        self._mmu.log_mbc_writes_summary()
    # --- Fin Step 0450 ---
    
    # Método para obtener el puntero C++ directamente (forma segura)
    cdef mmu.MMU* get_cpp_ptr(self):
        """
        Obtiene el puntero C++ interno directamente (para uso en otros módulos Cython).
        
        Este método permite que otros wrappers (PyTimer, etc.) extraigan el puntero
        C++ directamente sin necesidad de conversiones intermedias.
        
        Returns:
            Puntero C++ a la instancia de MMU
        """
        return self._mmu
    
    # NOTA: El miembro _mmu es accesible desde otros módulos Cython
    # que incluyan este archivo (como cpu.pyx), pero es mejor usar get_cpp_ptr()
    # para mantener consistencia con otros wrappers

