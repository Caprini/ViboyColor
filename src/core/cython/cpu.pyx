# distutils: language = c++

"""
Wrapper Cython para CPU (Procesador LR35902).

Este módulo expone la clase C++ CPU a Python, permitiendo
ejecutar el ciclo de instrucción en código nativo de alta velocidad.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp cimport bool

# Importar las definiciones C++
cimport cpu
cimport mmu
cimport registers
cimport ppu
cimport timer

# NOTA: PyMMU, PyRegisters y PyPPU están definidos en mmu.pyx, registers.pyx y ppu.pyx,
# que están incluidos en native_core.pyx. Como native_core.pyx incluye todos los módulos,
# PyPPU estará disponible en tiempo de ejecución sin necesidad de forward declaration.
# Simplemente importamos el tipo cuando sea necesario usando un cast.

cdef class PyCPU:
    """
    Wrapper Python para CPU.
    
    Esta clase permite usar CPU desde Python manteniendo
    el rendimiento de C++ (ciclo de instrucción nativo).
    
    Utiliza inyección de dependencias: recibe PyMMU y PyRegisters
    y extrae los punteros C++ subyacentes.
    """
    cdef cpu.CPU* _cpu
    cdef PyRegisters _registers_ref  # Referencia al objeto PyRegisters para acceso desde Python
    
    def __cinit__(self, PyMMU mmu, PyRegisters regs):
        """
        Constructor: crea la instancia C++ con punteros a MMU y Registros.
        
        Args:
            mmu: Instancia de PyMMU (wrapper de MMU)
            regs: Instancia de PyRegisters (wrapper de CoreRegisters)
        """
        # Extraer los punteros C++ subyacentes directamente
        # Como mmu.pyx y registers.pyx están incluidos en native_core.pyx,
        # podemos acceder a los miembros privados _mmu y _regs
        self._cpu = new cpu.CPU(mmu._mmu, regs._regs)
        # STEP 0440: Guardar referencia a PyRegisters para exposición a Python
        self._registers_ref = regs
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._cpu != NULL:
            del self._cpu
    
    def step(self) -> int:
        """
        Ejecuta un ciclo de instrucción (Fetch-Decode-Execute).
        
        Returns:
            Número de M-Cycles consumidos (0 si hay error)
        """
        return self._cpu.step()
    
    def get_cycles(self) -> int:
        """
        Obtiene el contador de ciclos acumulados.
        
        Returns:
            Total de M-Cycles ejecutados desde la creación
        """
        return self._cpu.get_cycles()
    
    def get_ime(self):
        """
        Obtiene el estado de IME (Interrupt Master Enable).
        
        Returns:
            1 si las interrupciones están habilitadas, 0 en caso contrario
        """
        cdef bool ime_val = self._cpu.get_ime()
        if ime_val:
            return 1
        else:
            return 0
    
    def get_halted(self):
        """
        Obtiene el estado de HALT.
        
        Returns:
            1 si la CPU está en estado HALT, 0 en caso contrario
        """
        cdef bool halted_val = self._cpu.get_halted()
        if halted_val:
            return 1
        else:
            return 0
    
    # Propiedades para acceso directo (compatibilidad con tests)
    @property
    def registers(self):
        """
        Propiedad para acceder al objeto Registers desde Python.
        
        STEP 0440: Expuesto para compatibilidad con tests de integración.
        
        Returns:
            PyRegisters: Objeto de registros de la CPU
        """
        return self._registers_ref
    
    @property
    def regs(self):
        """
        Alias de registers para compatibilidad.
        
        Returns:
            PyRegisters: Objeto de registros de la CPU
        """
        return self._registers_ref
    
    @property
    def ime(self):
        """
        Propiedad para acceder al estado de IME.
        
        Returns:
            True si las interrupciones están habilitadas, False en caso contrario
        """
        return self._cpu.get_ime()
    
    @ime.setter
    def ime(self, bint value):
        """
        Propiedad para establecer el estado de IME.
        
        Args:
            value: True para habilitar interrupciones, False para deshabilitarlas
        """
        self._cpu.set_ime(value)
    
    @property
    def halted(self):
        """
        Propiedad para acceder al estado de HALT.
        
        Returns:
            True si la CPU está en estado HALT, False en caso contrario
        """
        return self._cpu.get_halted()
    
    cpdef set_ppu(self, object ppu_wrapper):
        """
        Conecta la PPU a la CPU para permitir sincronización ciclo a ciclo.
        
        Este método permite que run_scanline() actualice la PPU después de cada
        instrucción, resolviendo deadlocks de polling mediante sincronización precisa.
        
        Args:
            ppu_wrapper: Instancia de PyPPU (debe tener un atributo _ppu válido) o None
        """
        cdef PyPPU ppu_obj
        if ppu_wrapper is None:
            # Si se pasa None, desconectamos la PPU
            self._cpu.setPPU(NULL)
        else:
            # Extraer el puntero C++ subyacente desde el wrapper
            # Hacer el cast a PyPPU y acceder al atributo _ppu directamente
            ppu_obj = <PyPPU>ppu_wrapper
            self._cpu.setPPU(ppu_obj._ppu)
    
    cpdef set_timer(self, object timer_wrapper):
        """
        Conecta el Timer a la CPU para permitir actualización del registro DIV.
        
        Este método permite que run_scanline() actualice el Timer después de cada
        instrucción, permitiendo que el registro DIV avance correctamente y la CPU
        pueda salir de bucles de retardo de tiempo.
        
        Args:
            timer_wrapper: Instancia de PyTimer (debe tener un método get_cpp_ptr() válido) o None
        """
        cdef timer.Timer* timer_ptr = NULL
        if timer_wrapper is None:
            # Si se pasa None, desconectamos el Timer
            self._cpu.setTimer(NULL)
        else:
            # Extraer el puntero C++ subyacente desde el wrapper
            # Hacer el cast a PyTimer y llamar al método get_cpp_ptr()
            timer_ptr = (<PyTimer>timer_wrapper).get_cpp_ptr()
            self._cpu.setTimer(timer_ptr)
    
    def run_scanline(self):
        """
        Ejecuta una scanline completa (456 T-Cycles) con sincronización ciclo a ciclo.
        
        Este método encapsula el bucle de emulación de grano fino que ejecuta
        instrucciones de la CPU y actualiza la PPU después de cada instrucción.
        Esto permite una sincronización precisa que resuelve deadlocks de polling.
        
        CRÍTICO: La PPU debe estar conectada previamente mediante set_ppu().
        """
        self._cpu.run_scanline()
    
    def set_triage_mode(self, bool active, int frame_limit=120):
        """
        Step 0434: Activa/desactiva triage mode para diagnóstico.
        
        Args:
            active: True para activar, False para desactivar
            frame_limit: Número máximo de frames para capturar (default 120)
        """
        self._cpu.set_triage_mode(active, frame_limit)
    
    def log_triage_summary(self):
        """
        Step 0434: Genera resumen de triage (debe llamarse después de ejecutar).
        """
        self._cpu.log_triage_summary()
    
    # --- Step 0436: Pokemon Micro Trace ---
    def set_pokemon_micro_trace(self, bool active):
        """
        Step 0436: Activa/desactiva Pokemon micro trace (Fase B del Step 0436).
        Captura 128 iteraciones del loop con PC/opcode/regs/flags.
        
        Args:
            active: True para activar, False para desactivar
        """
        self._cpu.set_pokemon_micro_trace(active)
    
    def log_pokemon_micro_trace_summary(self):
        """
        Step 0436: Genera resumen de Pokemon micro trace (Fase B).
        Muestra 10 líneas representativas del trace + conclusión.
        """
        self._cpu.log_pokemon_micro_trace_summary()
    # --- Fin Step 0436 ---

