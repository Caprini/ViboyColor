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
    
    def get_vblank_irq_serviced_count(self):
        """
        Step 0469: Obtiene el contador de VBlank IRQ servidos.
        
        Este contador se incrementa cada vez que la CPU sirve una interrupción VBlank
        (cuando IME está activo y se procesa el vector 0x0040). Útil para diagnóstico
        de por qué los juegos no progresan (si el juego está en HALT esperando VBlank).
        
        Returns:
            Número de veces que se ha servido VBlank interrupt
        """
        return self._cpu.get_vblank_irq_serviced_count()
    
    def get_ei_count(self):
        """
        Step 0470: Obtiene el contador de ejecuciones de EI.
        
        Returns:
            Número de veces que se ha ejecutado EI
        """
        return self._cpu.get_ei_count()
    
    def get_di_count(self):
        """
        Step 0470: Obtiene el contador de ejecuciones de DI.
        
        Returns:
            Número de veces que se ha ejecutado DI
        """
        return self._cpu.get_di_count()
    
    def get_ime_set_events_count(self):
        """
        Step 0477: Obtiene el contador de eventos de activación de IME.
        
        Returns:
            Número de veces que IME se ha activado
        """
        return self._cpu.get_ime_set_events_count()
    
    def get_last_ime_set_pc(self):
        """
        Step 0477: Obtiene el PC donde IME se activó por última vez.
        
        Returns:
            PC de la última activación de IME
        """
        return self._cpu.get_last_ime_set_pc()
    
    def get_last_ime_set_timestamp(self):
        """
        Step 0477: Obtiene el timestamp de la última activación de IME.
        
        Returns:
            Timestamp de la última activación de IME
        """
        return self._cpu.get_last_ime_set_timestamp()
    
    def get_last_ei_pc(self):
        """
        Step 0477: Obtiene el PC de la última ejecución de EI.
        
        Returns:
            PC de la última ejecución de EI
        """
        return self._cpu.get_last_ei_pc()
    
    def get_last_di_pc(self):
        """
        Step 0477: Obtiene el PC de la última ejecución de DI.
        
        Returns:
            PC de la última ejecución de DI
        """
        return self._cpu.get_last_di_pc()
    
    def get_ei_pending(self):
        """
        Step 0477: Obtiene el estado de EI pending (delayed enable).
        
        Returns:
            True si EI está pendiente (IME se activará después de la siguiente instrucción)
        """
        return self._cpu.get_ei_pending()
    
    def get_stop_executed_count(self):
        """
        Step 0472: Obtiene el contador de ejecuciones de STOP.
        
        Returns:
            Número de veces que se ha ejecutado STOP
        """
        return self._cpu.get_stop_executed_count()
    
    def get_last_stop_pc(self):
        """
        Step 0472: Obtiene el PC de la última ejecución de STOP.
        
        Returns:
            PC de la última ejecución de STOP
        """
        return self._cpu.get_last_stop_pc()
    
    # --- Step 0475: IF Clear on Service Tracking ---
    def get_last_irq_serviced_vector(self):
        """
        Step 0475: Obtiene el vector de la última IRQ servida.
        
        Returns:
            Vector de la última IRQ servida (0x40, 0x48, 0x50, 0x58, 0x60)
        """
        return self._cpu.get_last_irq_serviced_vector()
    
    def get_last_irq_serviced_timestamp(self):
        """
        Step 0475: Obtiene el timestamp de la última IRQ servida.
        
        Returns:
            Timestamp de la última IRQ servida (incrementa cada vez que se sirve una IRQ)
        """
        return self._cpu.get_last_irq_serviced_timestamp()
    
    def get_last_if_before_service(self):
        """
        Step 0475: Obtiene el valor de IF antes de servir la última IRQ.
        
        Returns:
            Valor de IF antes de servir la última IRQ
        """
        return self._cpu.get_last_if_before_service()
    
    def get_last_if_after_service(self):
        """
        Step 0475: Obtiene el valor de IF después de servir la última IRQ.
        
        Returns:
            Valor de IF después de servir la última IRQ
        """
        return self._cpu.get_last_if_after_service()
    
    def get_last_if_clear_mask(self):
        """
        Step 0475: Obtiene la máscara del bit limpiado en la última IRQ servida.
        
        Returns:
            Máscara del bit limpiado (lowest_pending)
        """
        return self._cpu.get_last_if_clear_mask()
    
    # --- Step 0482: Getters para Branch Decision Counters (gated por VIBOY_DEBUG_BRANCH=1) ---
    def get_branch_taken_count(self, uint16_t pc):
        """
        Step 0482: Obtiene el contador de veces que un salto condicional fue tomado.
        
        Args:
            pc: PC del salto condicional
        
        Returns:
            Número de veces que el salto fue tomado
        """
        return self._cpu.get_branch_taken_count(pc)
    
    def get_branch_not_taken_count(self, uint16_t pc):
        """
        Step 0482: Obtiene el contador de veces que un salto condicional NO fue tomado.
        
        Args:
            pc: PC del salto condicional
        
        Returns:
            Número de veces que el salto NO fue tomado
        """
        return self._cpu.get_branch_not_taken_count(pc)
    
    def get_last_cond_jump_pc(self):
        """
        Step 0482: Obtiene el PC del último salto condicional ejecutado.
        
        Returns:
            PC del último salto condicional (0xFFFF si ninguno)
        """
        return self._cpu.get_last_cond_jump_pc()
    
    def get_last_target(self):
        """
        Step 0482: Obtiene el target del último salto condicional.
        
        Returns:
            Target del último salto condicional
        """
        return self._cpu.get_last_target()
    
    def get_last_taken(self):
        """
        Step 0482: Obtiene si el último salto condicional fue tomado.
        
        Returns:
            1 si fue tomado, 0 si no fue tomado
        """
        cdef bool taken_val = self._cpu.get_last_taken()
        if taken_val:
            return 1
        else:
            return 0
    
    def get_last_flags(self):
        """
        Step 0482: Obtiene los flags al momento del último salto condicional.
        
        Returns:
            Flags (registro F) al momento del último salto
        """
        return self._cpu.get_last_flags()
    
    # --- Step 0482: Getters para Last Compare/BIT Tracking (gated por VIBOY_DEBUG_BRANCH=1) ---
    def get_last_cmp_pc(self):
        """
        Step 0482: Obtiene el PC del último CP ejecutado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            PC del último CP (0xFFFF si ninguno)
        """
        return self._cpu.get_last_cmp_pc()
    
    def get_last_cmp_a(self):
        """
        Step 0482: Obtiene el valor de A antes del último CP.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Valor de A antes del CP
        """
        return self._cpu.get_last_cmp_a()
    
    def get_last_cmp_imm(self):
        """
        Step 0482: Obtiene el valor inmediato usado en el último CP.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Valor inmediato usado en CP
        """
        return self._cpu.get_last_cmp_imm()
    
    def get_last_cmp_result_flags(self):
        """
        Step 0482: Obtiene los flags después del último CP.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Flags (registro F) después del CP
        """
        return self._cpu.get_last_cmp_result_flags()
    
    def get_last_bit_pc(self):
        """
        Step 0482: Obtiene el PC del último BIT ejecutado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            PC del último BIT (0xFFFF si ninguno)
        """
        return self._cpu.get_last_bit_pc()
    
    def get_last_bit_n(self):
        """
        Step 0482: Obtiene el número de bit testeado en el último BIT.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Número de bit (0-7)
        """
        return self._cpu.get_last_bit_n()
    
    def get_last_bit_value(self):
        """
        Step 0482: Obtiene el valor del bit testeado en el último BIT (0 o 1).
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Valor del bit (0 o 1)
        """
        return self._cpu.get_last_bit_value()
    # --- Fin Step 0482 (Branch/Compare/BIT Tracking) ---
    # --- Fin Step 0475 ---
    
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

