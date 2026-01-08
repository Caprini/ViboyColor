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
    
    # --- Step 0481: Exponer debug_current_pc para tests ---
    property debug_current_pc:
        """Step 0481: Acceso al PC actual para tracking en tests."""
        def __get__(self):
            if self._mmu == NULL:
                return 0
            return self._mmu.debug_current_pc
        
        def __set__(self, uint16_t value):
            if self._mmu != NULL:
                self._mmu.debug_current_pc = value
    # --- Fin Step 0481 ---
    
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
            self._mmu.set_hardware_mode(<mmu.HardwareMode>0)  # HardwareMode::DMG = 0
        elif mode.upper() == "CGB":
            self._mmu.set_hardware_mode(<mmu.HardwareMode>1)  # HardwareMode::CGB = 1
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
        
        cdef int mode = <int>self._mmu.get_hardware_mode()
        return "CGB" if mode == 1 else "DMG"  # HardwareMode::CGB = 1, HardwareMode::DMG = 0
    
    def get_dmg_compat_mode(self):
        """
        Step 0495: Obtiene si está en modo compatibilidad DMG dentro de CGB.
        
        En modo CGB, si LCDC bit 0 = 0 (LCD OFF), el hardware opera en modo
        compatibilidad DMG, usando paletas DMG en lugar de paletas CGB.
        
        Returns:
            True si está en modo compatibilidad DMG (LCDC bit 0 = 0), False en caso contrario
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        
        Fuente: Pan Docs - CGB Registers, LCDC (0xFF40)
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        # El método C++ devuelve int directamente (1 = true, 0 = false)
        # Python convertirá automáticamente a bool cuando sea necesario
        return self._mmu.get_dmg_compat_mode() != 0
    
    def get_rom_header_cgb_flag(self):
        """
        Step 0495: Obtiene el byte 0x0143 del header de la ROM (CGB flag).
        
        Returns:
            Byte 0x0143 del header de la ROM (0x80 o 0xC0 = CGB, 0x00 = DMG)
        
        Raises:
            MemoryError: Si la instancia de MMU en C++ no existe
        """
        if self._mmu == NULL:
            raise MemoryError("La instancia de MMU en C++ no existe.")
        
        return self._mmu.get_rom_header_cgb_flag()
    
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
    
    def get_last_ie_write_timestamp(self):
        """
        Step 0477: Obtiene el timestamp del último write a IE (0xFFFF).
        
        Returns:
            Timestamp del último write a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ie_write_timestamp()
    
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
    
    def get_joyp_read_count_program(self):
        """
        Step 0481: Obtiene el contador de reads de JOYP desde programa.
        
        Returns:
            Número de reads de JOYP desde código del programa
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_count_program()
    
    def get_last_joyp_read_pc(self):
        """
        Step 0481: Obtiene el PC del último read de JOYP.
        
        Returns:
            PC del último read de JOYP
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_joyp_read_pc()
    
    def get_last_joyp_read_value(self):
        """
        Step 0481: Obtiene el último valor leído de JOYP.
        
        Returns:
            Último valor leído de JOYP
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_joyp_read_value()
    
    # --- Step 0482: Getters para LCDC Disable Tracking ---
    def get_lcdc_disable_events(self):
        """
        Step 0482: Obtiene el contador de eventos de disable de LCDC (1→0).
        
        Returns:
            Número de veces que LCDC bit7 pasó de 1 a 0
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_lcdc_disable_events()
    
    # --- Step 0484: LCDC Current Getter ---
    def get_lcdc_current(self):
        """
        Step 0484: Obtiene el valor actual de LCDC (0xFF40).
        
        Returns:
            Valor actual de LCDC
        """
        return self._mmu.get_lcdc_current()
    
    # --- Step 0484: JOYP Write Distribution ---
    def get_joyp_write_distribution_top5(self):
        """
        Step 0484: Obtiene el top 5 de valores JOYP escritos (histograma).
        
        Returns:
            Lista de tuplas (valor, count) ordenadas por count descendente (top 5)
        """
        dist = self._mmu.get_joyp_write_distribution_top5()
        return [(val, count) for val, count in dist]
    
    def get_joyp_write_pcs_by_value(self, uint8_t value):
        """
        Step 0484: Obtiene la lista de PCs donde se escribió un valor JOYP específico.
        
        Args:
            value: Valor JOYP
        
        Returns:
            Lista de PCs (máximo 10)
        """
        pcs = self._mmu.get_joyp_write_pcs_by_value(value)
        return [pc for pc in pcs]
    
    # --- Step 0484: JOYP Read Select Bits ---
    def get_joyp_last_read_select_bits(self):
        """
        Step 0484: Obtiene los bits de selección (4-5) del último read de JOYP.
        
        Returns:
            Bits 4-5 del latch en el momento de la lectura
        """
        return self._mmu.get_joyp_last_read_select_bits()
    
    def get_joyp_last_read_low_nibble(self):
        """
        Step 0484: Obtiene el low nibble (bits 0-3) del último read de JOYP.
        
        Returns:
            Bits 0-3 leídos
        """
        return self._mmu.get_joyp_last_read_low_nibble()
    
    # --- Step 0485: JOYP Trace Getters ---
    def get_joyp_trace(self):
        """
        Step 0485: Obtiene el trace completo de JOYP (últimos 256 eventos).
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Lista de eventos del trace (cada evento es un dict con type, pc, value_written, value_read, select_bits, low_nibble_read, timestamp)
        """
        cdef vector[mmu.JOYPTraceEvent] trace = self._mmu.get_joyp_trace()
        result = []
        for i in range(trace.size()):
            event = trace[i]
            result.append({
                'type': 'READ' if event.type == 0 else 'WRITE',
                'pc': event.pc,
                'value_written': event.value_written,
                'value_read': event.value_read,
                'select_bits': event.select_bits,
                'low_nibble_read': event.low_nibble_read,
                'timestamp': event.timestamp
            })
        return result
    
    def get_joyp_trace_tail(self, size_t n):
        """
        Step 0485: Obtiene los últimos N eventos del trace de JOYP.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Args:
            n: Número de eventos a retornar
        
        Returns:
            Lista de los últimos N eventos
        """
        cdef vector[mmu.JOYPTraceEvent] trace = self._mmu.get_joyp_trace_tail(n)
        result = []
        for i in range(trace.size()):
            event = trace[i]
            result.append({
                'type': 'READ' if event.type == 0 else 'WRITE',
                'pc': event.pc,
                'value_written': event.value_written,
                'value_read': event.value_read,
                'select_bits': event.select_bits,
                'low_nibble_read': event.low_nibble_read,
                'timestamp': event.timestamp
            })
        return result
    
    def get_joyp_reads_with_buttons_selected_count(self):
        """
        Step 0485: Obtiene el contador de reads de JOYP con botones seleccionados.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads con botones seleccionados (P14=0)
        """
        return self._mmu.get_joyp_reads_with_buttons_selected_count()
    
    def get_joyp_reads_with_dpad_selected_count(self):
        """
        Step 0485: Obtiene el contador de reads de JOYP con dpad seleccionado.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads con dpad seleccionado (P15=0)
        """
        return self._mmu.get_joyp_reads_with_dpad_selected_count()
    
    def get_joyp_reads_with_none_selected_count(self):
        """
        Step 0485: Obtiene el contador de reads de JOYP sin selección (0x30).
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads sin selección (0x30)
        """
        return self._mmu.get_joyp_reads_with_none_selected_count()
    # --- Fin Step 0485 ---
    # --- Fin Step 0484 ---
    
    # --- Step 0486: HRAM FF92 Watch Getters ---
    def get_hram_ff92_last_write_pc(self):
        """
        Step 0486: Obtiene el PC del último write a HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC del último write a HRAM[FF92] (0xFFFF si ninguno)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_hram_ff92_last_write_pc()
    
    def get_hram_ff92_last_write_val(self):
        """
        Step 0486: Obtiene el último valor escrito a HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Último valor escrito a HRAM[FF92]
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_ff92_last_write_val()
    
    def get_hram_ff92_last_read_pc(self):
        """
        Step 0486: Obtiene el PC del último read de HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC del último read de HRAM[FF92] (0xFFFF si ninguno)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_hram_ff92_last_read_pc()
    
    def get_hram_ff92_last_read_val(self):
        """
        Step 0486: Obtiene el último valor leído de HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Último valor leído de HRAM[FF92]
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_ff92_last_read_val()
    
    def get_hram_ff92_readback_after_write_val(self):
        """
        Step 0486: Obtiene el valor leído inmediatamente después del último write a HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Valor leído después del write (solo diagnóstico)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_ff92_readback_after_write_val()
    
    def get_hram_ff92_write_readback_mismatch_count(self):
        """
        Step 0486: Obtiene el contador de discrepancias write-readback en HRAM[FF92].
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Número de veces que readback != write_val
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_ff92_write_readback_mismatch_count()
    
    # --- Step 0487: HRAM FF92 Single Source of Truth ---
    def get_ff92_write_count_total(self):
        """
        Step 0487: Obtiene el contador total de writes a FF92 (cumulativo, nunca se resetea).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Número total de writes a FF92
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ff92_write_count_total()
    
    def get_ff92_last_write_pc(self):
        """
        Step 0487: Obtiene el PC del último write a FF92.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC del último write a FF92 (0xFFFF si ninguno)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_ff92_last_write_pc()
    
    def get_ff92_last_write_val(self):
        """
        Step 0487: Obtiene el último valor escrito a FF92.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Último valor escrito a FF92
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ff92_last_write_val()
    
    def get_ff92_read_count_total(self):
        """
        Step 0487: Obtiene el contador total de reads de FF92 (cumulativo, nunca se resetea).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Número total de reads de FF92
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ff92_read_count_total()
    
    def get_ff92_last_read_pc(self):
        """
        Step 0487: Obtiene el PC del último read de FF92.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC del último read de FF92 (0xFFFF si ninguno)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_ff92_last_read_pc()
    
    def get_ff92_last_read_val(self):
        """
        Step 0487: Obtiene el último valor leído de FF92.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Último valor leído de FF92
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ff92_last_read_val()
    
    def get_ie_value_after_write(self):
        """
        Step 0487: Obtiene el valor de IE después del último write.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Valor de IE después del último write
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_value_after_write()
    
    def get_ie_last_write_pc(self):
        """
        Step 0487: Obtiene el PC del último write a IE.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC del último write a IE (0xFFFF si ninguno)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_ie_last_write_pc()
    
    def get_ie_write_count_total(self):
        """
        Step 0487: Obtiene el contador total de writes a IE (cumulativo).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Número total de writes a IE
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_write_count_total()
    # --- Fin Step 0487 (HRAM FF92 Single Source of Truth + IE Tracking) ---
    
    def get_ff92_to_ie_trace(self):
        """
        Step 0486: Obtiene el trace completo de FF92→IE (últimos 16 eventos).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Lista de eventos del trace (cada evento es un dict con ff92_written_val, ff92_read_val, ie_written_val, etc.)
        """
        if self._mmu == NULL:
            return []
        # TODO: Necesitamos exponer FF92ToIETrace struct en mmu.pxd
        # Por ahora retornamos lista vacía
        return []
    # --- Fin Step 0486 (HRAM FF92 Watch) ---
    
    # --- Step 0486: JOYP Contadores por Source Getters ---
    def get_joyp_reads_prog_buttons_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde programa con botones seleccionados.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa con botones seleccionados (P14=0)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_prog_buttons_sel()
    
    def get_joyp_reads_prog_dpad_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde programa con dpad seleccionado.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa con dpad seleccionado (P15=0)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_prog_dpad_sel()
    
    def get_joyp_reads_prog_none_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde programa sin selección (0x30).
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa sin selección (0x30)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_prog_none_sel()
    
    def get_joyp_reads_cpu_poll_buttons_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde CPU polling con botones seleccionados.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling con botones seleccionados (P14=0)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_cpu_poll_buttons_sel()
    
    def get_joyp_reads_cpu_poll_dpad_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde CPU polling con dpad seleccionado.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling con dpad seleccionado (P15=0)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_cpu_poll_dpad_sel()
    
    def get_joyp_reads_cpu_poll_none_sel(self):
        """
        Step 0486: Obtiene el contador de reads de JOYP desde CPU polling sin selección (0x30).
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling sin selección (0x30)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_reads_cpu_poll_none_sel()
    # --- Fin Step 0486 (JOYP Contadores por Source) ---
    
    # --- Step 0487: JOYP Contadores por Tipo de Selección ---
    def get_joyp_write_buttons_selected_total(self):
        """
        Step 0487: Obtiene el contador de writes a JOYP con buttons selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de writes con buttons selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_write_buttons_selected_total()
    
    def get_joyp_write_dpad_selected_total(self):
        """
        Step 0487: Obtiene el contador de writes a JOYP con dpad selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de writes con dpad selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_write_dpad_selected_total()
    
    def get_joyp_write_none_selected_total(self):
        """
        Step 0487: Obtiene el contador de writes a JOYP con none selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de writes con none selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_write_none_selected_total()
    
    def get_joyp_read_buttons_selected_total_prog(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde programa con buttons selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa con buttons selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_buttons_selected_total_prog()
    
    def get_joyp_read_dpad_selected_total_prog(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde programa con dpad selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa con dpad selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_dpad_selected_total_prog()
    
    def get_joyp_read_none_selected_total_prog(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde programa con none selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde programa con none selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_none_selected_total_prog()
    
    def get_joyp_read_buttons_selected_total_cpu_poll(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con buttons selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling con buttons selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_buttons_selected_total_cpu_poll()
    
    def get_joyp_read_dpad_selected_total_cpu_poll(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con dpad selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling con dpad selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_dpad_selected_total_cpu_poll()
    
    def get_joyp_read_none_selected_total_cpu_poll(self):
        """
        Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con none selected.
        
        Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
        
        Returns:
            Número de reads desde CPU polling con none selected
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_joyp_read_none_selected_total_cpu_poll()
    # --- Fin Step 0487 (JOYP Contadores por Tipo de Selección) ---
    
    def get_cgb_palette_write_stats(self):
        """
        Step 0489: Obtiene estadísticas de writes a paletas CGB.
        
        Devuelve métricas sobre escrituras a BGPI/BGPD y OBPI/OBPD.
        
        Returns:
            dict con estadísticas de writes a paletas CGB o None si no disponible.
            Keys: 'bgpd_write_count', 'last_bgpd_write_pc', 'last_bgpd_value', 'last_bgpi',
                  'obpd_write_count', 'last_obpd_write_pc', 'last_obpd_value', 'last_obpi'
        """
        if self._mmu == NULL:
            return None
        
        cdef mmu.CGBPaletteWriteStats stats = self._mmu.get_cgb_palette_write_stats()
        
        return {
            'bgpd_write_count': stats.bgpd_write_count,
            'last_bgpd_write_pc': stats.last_bgpd_write_pc,
            'last_bgpd_value': stats.last_bgpd_value,
            'last_bgpi': stats.last_bgpi,
            'obpd_write_count': stats.obpd_write_count,
            'last_obpd_write_pc': stats.last_obpd_write_pc,
            'last_obpd_value': stats.last_obpd_value,
            'last_obpi': stats.last_obpi,
        }
    
    def get_vram_write_stats(self):
        """
        Step 0490: Obtiene estadísticas de writes a VRAM.
        Step 0491: Ampliada para separar attempts vs nonzero writes + bank + VBK.
        Step 0492: Ampliada con tracking de Clear VRAM y writes después del clear.
        
        Devuelve métricas sobre intentos de escritura a VRAM y bloqueos por Mode 3.
        
        Returns:
            dict con estadísticas de writes a VRAM o None si no disponible.
        """
        if self._mmu == NULL:
            return None
        
        cdef mmu.VRAMWriteStats stats = self._mmu.get_vram_write_stats()
        
        # Extraer ring buffer (últimos N eventos)
        cdef uint32_t start = 0
        cdef uint32_t ring_size = 128  # TILEDATA_WRITE_RING_SIZE
        cdef uint32_t i, idx
        ring_events = []
        if stats.tiledata_write_ring_active_:
            if stats.tiledata_write_ring_head_ > ring_size:
                start = stats.tiledata_write_ring_head_ - ring_size
            for i in range(start, stats.tiledata_write_ring_head_):
                idx = i % ring_size
                ring_events.append({
                    'frame': stats.tiledata_write_ring_[idx].frame,
                    'pc': stats.tiledata_write_ring_[idx].pc,
                    'addr': stats.tiledata_write_ring_[idx].addr,
                    'val': stats.tiledata_write_ring_[idx].val,
                })
        
        return {
            'tiledata_attempts_bank0': stats.tiledata_attempts_bank0,
            'tiledata_attempts_bank1': stats.tiledata_attempts_bank1,
            'tiledata_nonzero_writes_bank0': stats.tiledata_nonzero_writes_bank0,
            'tiledata_nonzero_writes_bank1': stats.tiledata_nonzero_writes_bank1,
            'tilemap_attempts_bank0': stats.tilemap_attempts_bank0,
            'tilemap_attempts_bank1': stats.tilemap_attempts_bank1,
            'tilemap_nonzero_writes_bank0': stats.tilemap_nonzero_writes_bank0,
            'tilemap_nonzero_writes_bank1': stats.tilemap_nonzero_writes_bank1,
            'last_nonzero_tiledata_write_pc': stats.last_nonzero_tiledata_write_pc,
            'last_nonzero_tiledata_write_addr': stats.last_nonzero_tiledata_write_addr,
            'last_nonzero_tiledata_write_val': stats.last_nonzero_tiledata_write_val,
            'last_nonzero_tiledata_write_bank': stats.last_nonzero_tiledata_write_bank,
            'vbk_value_current': stats.vbk_value_current,
            'vbk_write_count': stats.vbk_write_count,
            'last_vbk_write_pc': stats.last_vbk_write_pc,
            'last_vbk_write_val': stats.last_vbk_write_val,
            # Legacy
            'vram_write_attempts_tiledata': stats.vram_write_attempts_tiledata,
            'vram_write_attempts_tilemap': stats.vram_write_attempts_tilemap,
            'vram_write_blocked_mode3_tiledata': stats.vram_write_blocked_mode3_tiledata,
            'vram_write_blocked_mode3_tilemap': stats.vram_write_blocked_mode3_tilemap,
            'last_blocked_vram_write_pc': stats.last_blocked_vram_write_pc,
            'last_blocked_vram_write_addr': stats.last_blocked_vram_write_addr,
            # Step 0492: Clear VRAM tracking
            'tiledata_clear_done_frame': stats.tiledata_clear_done_frame,
            'tiledata_attempts_after_clear': stats.tiledata_attempts_after_clear,
            'tiledata_nonzero_after_clear': stats.tiledata_nonzero_after_clear,
            'tiledata_first_nonzero_frame': stats.tiledata_first_nonzero_frame,
            'tiledata_first_nonzero_pc': stats.tiledata_first_nonzero_pc,
            'tiledata_first_nonzero_addr': stats.tiledata_first_nonzero_addr,
            'tiledata_first_nonzero_val': stats.tiledata_first_nonzero_val,
            'tiledata_write_ring': ring_events,  # Últimos N eventos
        }
    
    def get_if_ie_tracking(self):
        """
        Step 0494: Obtiene tracking de writes a IF/IE.
        
        Returns:
            dict con tracking de writes a IF/IE o None si no disponible.
            Keys: 'last_if_write_pc', 'last_if_write_value', 'last_if_applied_value', 'if_write_count',
                  'last_ie_write_pc', 'last_ie_write_value', 'last_ie_applied_value', 'ie_write_count'
        """
        if self._mmu == NULL:
            return None
        
        cdef mmu.IFIETracking tracking = self._mmu.get_if_ie_tracking()
        
        return {
            'last_if_write_pc': tracking.last_if_write_pc,
            'last_if_write_value': tracking.last_if_write_value,
            'last_if_applied_value': tracking.last_if_applied_value,
            'if_write_count': tracking.if_write_count,
            'last_ie_write_pc': tracking.last_ie_write_pc,
            'last_ie_write_value': tracking.last_ie_write_value,
            'last_ie_applied_value': tracking.last_ie_applied_value,
            'ie_write_count': tracking.ie_write_count,
        }
    
    def get_hram_ffc5_tracking(self):
        """
        Step 0494: Obtiene tracking de writes a HRAM[0xFFC5].
        
        Returns:
            dict con tracking de writes a HRAM[0xFFC5] o None si no disponible.
            Keys: 'last_write_pc', 'last_write_value', 'write_count', 'first_write_frame'
        """
        if self._mmu == NULL:
            return None
        
        cdef mmu.HRAMFFC5Tracking tracking = self._mmu.get_hram_ffc5_tracking()
        
        return {
            'last_write_pc': tracking.last_write_pc,
            'last_write_value': tracking.last_write_value,
            'write_count': tracking.write_count,
            'first_write_frame': tracking.first_write_frame,
        }
    
    def get_io_watch_ff68_ff6b(self):
        """
        Step 0495: Obtiene tracking de writes/reads a registros CGB palette (FF68-FF6B).
        
        Returns:
            dict con tracking de writes/reads a FF68-FF6B o None si no disponible.
            Keys: bgpi_*, bgpd_*, obpi_*, obpd_* (write_count, last_write_pc, last_write_value,
                  read_count, last_read_pc, last_read_value para cada registro)
        """
        if self._mmu == NULL:
            return None
        
        cdef mmu.IOWatchFF68FF6B watch = self._mmu.get_io_watch_ff68_ff6b()
        
        return {
            # FF68 (BGPI/BCPS)
            'bgpi_write_count': watch.bgpi_write_count,
            'bgpi_last_write_pc': watch.bgpi_last_write_pc,
            'bgpi_last_write_value': watch.bgpi_last_write_value,
            'bgpi_read_count': watch.bgpi_read_count,
            'bgpi_last_read_pc': watch.bgpi_last_read_pc,
            'bgpi_last_read_value': watch.bgpi_last_read_value,
            # FF69 (BGPD/BCPD)
            'bgpd_write_count': watch.bgpd_write_count,
            'bgpd_last_write_pc': watch.bgpd_last_write_pc,
            'bgpd_last_write_value': watch.bgpd_last_write_value,
            'bgpd_read_count': watch.bgpd_read_count,
            'bgpd_last_read_pc': watch.bgpd_last_read_pc,
            'bgpd_last_read_value': watch.bgpd_last_read_value,
            # FF6A (OBPI/OCPS)
            'obpi_write_count': watch.obpi_write_count,
            'obpi_last_write_pc': watch.obpi_last_write_pc,
            'obpi_last_write_value': watch.obpi_last_write_value,
            'obpi_read_count': watch.obpi_read_count,
            'obpi_last_read_pc': watch.obpi_last_read_pc,
            'obpi_last_read_value': watch.obpi_last_read_value,
            # FF6B (OBPD/OCPD)
            'obpd_write_count': watch.obpd_write_count,
            'obpd_last_write_pc': watch.obpd_last_write_pc,
            'obpd_last_write_value': watch.obpd_last_write_value,
            'obpd_read_count': watch.obpd_read_count,
            'obpd_last_read_pc': watch.obpd_last_read_pc,
            'obpd_last_read_value': watch.obpd_last_read_value,
        }
    
    def read_bg_palette_data(self, uint8_t index):
        """
        Step 0494: Lee un byte de la paleta BG CGB.
        
        Args:
            index: Índice en el array de paleta (0x00-0x3F)
        
        Returns:
            Byte de paleta (RGB555 low/high byte)
        """
        if self._mmu == NULL:
            return 0xFF
        return self._mmu.read_bg_palette_data(index)
    
    def read_obj_palette_data(self, uint8_t index):
        """
        Step 0494: Lee un byte de la paleta OBJ CGB.
        
        Args:
            index: Índice en el array de paleta (0x00-0x3F)
        
        Returns:
            Byte de paleta (RGB555 low/high byte)
        """
        if self._mmu == NULL:
            return 0xFF
        return self._mmu.read_obj_palette_data(index)
    
    def get_last_lcdc_write_pc(self):
        """
        Step 0482: Obtiene el PC de la última escritura a LCDC.
        
        Returns:
            PC de la última escritura a LCDC (0xFFFF si ninguna)
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_last_lcdc_write_pc()
    
    def get_last_lcdc_write_value(self):
        """
        Step 0482: Obtiene el valor de la última escritura a LCDC.
        
        Returns:
            Valor de la última escritura a LCDC
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_lcdc_write_value()
    # --- Fin Step 0482 (LCDC Disable Tracking) ---
    
    # --- Step 0474: Getters para instrumentación quirúrgica de IF/LY/STAT ---
    def get_if_read_count(self):
        """
        Step 0474: Obtiene el contador de lecturas de IF (0xFF0F).
        
        Returns:
            Número de veces que se ha leído IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_read_count()
    
    def get_last_if_write_pc(self):
        """
        Step 0474: Obtiene el PC del último write a IF (0xFF0F).
        
        Returns:
            PC del último write a IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_if_write_pc()
    
    def get_last_if_write_val(self):
        """
        Step 0474: Obtiene el último valor escrito a IF (0xFF0F).
        
        Returns:
            Último valor escrito a IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_if_write_val()
    
    def get_last_if_write_timestamp(self):
        """
        Step 0477: Obtiene el timestamp del último write a IF (0xFF0F).
        
        Returns:
            Timestamp del último write a IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_if_write_timestamp()
    
    def get_last_if_read_val(self):
        """
        Step 0474: Obtiene el último valor leído de IF (0xFF0F).
        
        Returns:
            Último valor leído de IF
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_if_read_val()
    
    def get_if_writes_0(self):
        """
        Step 0474: Obtiene el contador de writes a IF con valor 0.
        
        Returns:
            Número de writes a IF con valor 0
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_writes_0()
    
    def get_if_writes_nonzero(self):
        """
        Step 0474: Obtiene el contador de writes a IF con valor no-cero.
        
        Returns:
            Número de writes a IF con valor no-cero
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_writes_nonzero()
    
    def get_ly_read_min(self):
        """
        Step 0474: Obtiene el valor mínimo de LY leído.
        
        Returns:
            Valor mínimo de LY leído
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ly_read_min()
    
    def get_ly_read_max(self):
        """
        Step 0474: Obtiene el valor máximo de LY leído.
        
        Returns:
            Valor máximo de LY leído
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ly_read_max()
    
    def get_last_ly_read(self):
        """
        Step 0474: Obtiene el último valor leído de LY (0xFF44).
        
        Returns:
            Último valor leído de LY
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_ly_read()
    
    def get_last_stat_read(self):
        """
        Step 0474: Obtiene el último valor leído de STAT (0xFF41).
        
        Returns:
            Último valor leído de STAT
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_last_stat_read()
    # --- Fin Step 0474 ---
    
    # --- Step 0475: Source Tagging para IO Polling ---
    def set_irq_poll_active(self, bool active):
        """
        Step 0475: Establece el flag de polling de IRQ activo.
        
        Este método permite a la CPU marcar cuando está ejecutando
        polling interno de interrupciones, permitiendo distinguir
        lecturas de IO desde código del programa vs polling interno.
        
        Args:
            active: true si estamos en polling interno, false si no
        """
        if self._mmu == NULL:
            return
        self._mmu.set_irq_poll_active(active)
    
    def get_if_reads_program(self):
        """
        Step 0475: Obtiene el contador de lecturas de IF desde código del programa.
        
        Returns:
            Número de lecturas de IF desde código del programa
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_reads_program()
    
    def get_if_reads_cpu_poll(self):
        """
        Step 0475: Obtiene el contador de lecturas de IF desde polling interno de CPU.
        
        Returns:
            Número de lecturas de IF desde polling interno
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_reads_cpu_poll()
    
    def get_if_writes_program(self):
        """
        Step 0475: Obtiene el contador de escrituras a IF desde código del programa.
        
        Returns:
            Número de escrituras a IF desde código del programa
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_writes_program()
    
    def get_ie_reads_program(self):
        """
        Step 0475: Obtiene el contador de lecturas de IE desde código del programa.
        
        Returns:
            Número de lecturas de IE desde código del programa
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_reads_program()
    
    def get_ie_reads_cpu_poll(self):
        """
        Step 0475: Obtiene el contador de lecturas de IE desde polling interno de CPU.
        
        Returns:
            Número de lecturas de IE desde polling interno
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_reads_cpu_poll()
    
    def get_ie_writes_program(self):
        """
        Step 0475: Obtiene el contador de escrituras a IE desde código del programa.
        
        Returns:
            Número de escrituras a IE desde código del programa
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ie_writes_program()
    
    def get_boot_logo_prefill_enabled(self):
        """
        Step 0475: Obtiene el estado del prefill del logo de boot.
        
        Returns:
            1 si el prefill del logo está habilitado, 0 en caso contrario
            (compatible con bool de Python)
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_boot_logo_prefill_enabled()
    # --- Fin Step 0475 ---
    
    # --- Step 0479: Instrumentación gated por I/O esperado ---
    def set_waits_on_addr(self, uint16_t addr):
        """
        Step 0479: Configura el I/O esperado para instrumentación gated.
        
        Args:
            addr: Dirección I/O esperada (0xFF44, 0xFF41, etc.)
        """
        if self._mmu == NULL:
            return
        self._mmu.set_waits_on_addr(addr)
    
    def get_ly_changes_this_frame(self):
        """
        Step 0479: Obtiene el contador de cambios de LY por frame.
        
        Returns:
            Número de cambios de LY en el frame actual
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_ly_changes_this_frame()
    
    def get_stat_mode_changes_count(self):
        """
        Step 0479: Obtiene el contador de cambios de modo STAT por frame.
        
        Returns:
            Número de cambios de modo STAT en el frame actual
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_stat_mode_changes_count()
    
    def get_if_bit0_set_count_this_frame(self):
        """
        Step 0479: Obtiene el contador de veces que IF bit0 se pone a 1 por frame.
        
        Returns:
            Número de veces que IF bit0 se activó en el frame actual
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_if_bit0_set_count_this_frame()
    # --- Fin Step 0479 ---
    
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
    
    # --- Step 0481: HRAM Watchlist Genérica ---
    def add_hram_watch(self, uint16_t addr):
        """
        Step 0481: Añade una dirección HRAM a la watchlist para tracking.
        
        Args:
            addr: Dirección HRAM (0xFF80-0xFFFE)
        """
        if self._mmu == NULL:
            return
        self._mmu.add_hram_watch(addr)
    
    def get_hram_write_count(self, uint16_t addr):
        """
        Step 0481: Obtiene el contador de writes a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Número de writes, o 0 si no está en watchlist
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_write_count(addr)
    
    def get_hram_last_write_pc(self, uint16_t addr):
        """
        Step 0481: Obtiene el PC del último write a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            PC del último write, o 0 si no está en watchlist
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_last_write_pc(addr)
    
    def get_hram_last_write_value(self, uint16_t addr):
        """
        Step 0481: Obtiene el último valor escrito a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Último valor escrito, o 0 si no está en watchlist
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_last_write_value(addr)
    
    def get_hram_first_write_frame(self, uint16_t addr):
        """
        Step 0481: Obtiene el frame de la primera escritura a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Frame de la primera escritura, o 0 si no se ha escrito
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_first_write_frame(addr)
    
    def get_hram_read_count_program(self, uint16_t addr):
        """
        Step 0481: Obtiene el contador de reads desde programa a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Número de reads desde programa, o 0 si no está en watchlist
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_read_count_program(addr)
    
    def get_hram_last_write_frame(self, uint16_t addr):
        """
        Step 0483: Obtiene el frame de la última escritura a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Frame de la última escritura, o 0 si no se ha escrito
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_last_write_frame(addr)
    
    def get_hram_last_read_pc(self, uint16_t addr):
        """
        Step 0483: Obtiene el PC del último read a una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            PC del último read, o 0xFFFF si no está en watchlist
        """
        if self._mmu == NULL:
            return 0xFFFF
        return self._mmu.get_hram_last_read_pc(addr)
    
    def get_hram_last_read_value(self, uint16_t addr):
        """
        Step 0483: Obtiene el último valor leído de una dirección HRAM en watchlist.
        
        Args:
            addr: Dirección HRAM
        
        Returns:
            Último valor leído, o 0 si no está en watchlist
        """
        if self._mmu == NULL:
            return 0
        return self._mmu.get_hram_last_read_value(addr)
    # --- Fin Step 0481 ---
    # --- Fin Step 0483 (HRAM last_write_frame, last_read_pc, last_read_value) ---
    
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

