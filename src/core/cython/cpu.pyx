# distutils: language = c++

"""
Wrapper Cython para CPU (Procesador LR35902).

Este módulo expone la clase C++ CPU a Python, permitiendo
ejecutar el ciclo de instrucción en código nativo de alta velocidad.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp cimport bool
from libcpp.vector cimport vector
from libcpp.pair cimport pair

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
    
    # --- Step 0483: Getters para Exec Coverage (gated por VIBOY_DEBUG_BRANCH=1) ---
    def get_exec_count(self, uint16_t pc):
        """
        Step 0483: Obtiene el contador de ejecuciones de un PC específico.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1 y PC está en la ventana de coverage
        
        Args:
            pc: Dirección del PC
        
        Returns:
            Número de veces que se ejecutó (0 si no está en coverage)
        """
        return self._cpu.get_exec_count(pc)
    
    def get_top_exec_pcs(self, uint32_t n):
        """
        Step 0483: Obtiene los top N PCs más ejecutados.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Args:
            n: Número de PCs a retornar
        
        Returns:
            Lista de tuplas (PC, count) ordenadas por count descendente
        """
        cdef vector[pair[uint16_t, uint32_t]] result = self._cpu.get_top_exec_pcs(n)
        py_result = []
        for i in range(result.size()):
            py_result.append((result[i].first, result[i].second))
        return py_result
    
    def set_coverage_window(self, uint16_t start, uint16_t end):
        """
        Step 0483: Establece la ventana de coverage para exec tracking.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Args:
            start: PC inicial de la ventana
            end: PC final de la ventana
        """
        self._cpu.set_coverage_window(start, end)
    # --- Fin Step 0483 (Exec Coverage) ---
    
    # --- Step 0483: Getters para Branch Blockers (gated por VIBOY_DEBUG_BRANCH=1) ---
    def get_top_branch_blockers(self, uint32_t n):
        """
        Step 0483: Obtiene los top N branch blockers (branches con más decisiones).
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Args:
            n: Número de branches a retornar
        
        Returns:
            Lista de tuplas (PC, dict) donde dict contiene:
            - 'taken_count': número de veces tomado
            - 'not_taken_count': número de veces no tomado
            - 'last_target': último target
            - 'last_taken': si el último fue tomado (bool)
            - 'last_flags': flags al momento del último salto
        
        NOTA: Por ahora retorna lista vacía. La implementación completa requiere
        exponer BranchDecision como estructura completa (futura mejora).
        """
        # Por ahora, retornamos lista vacía ya que exponer BranchDecision requiere
        # una definición completa de la estructura en Cython (futura mejora)
        return []
    # --- Fin Step 0483 (Branch Blockers) ---
    
    # --- Step 0483: Getters para Last Load A (gated por VIBOY_DEBUG_BRANCH=1) ---
    def get_last_load_a_pc(self):
        """
        Step 0483: Obtiene el PC del último LDH A,(a8) o LD A,(a16) ejecutado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            PC de la última carga (0xFFFF si ninguna)
        """
        return self._cpu.get_last_load_a_pc()
    
    def get_last_load_a_addr(self):
        """
        Step 0483: Obtiene la dirección leída en el último LDH A,(a8) o LD A,(a16).
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Dirección leída (0xFFFF si ninguna)
        """
        return self._cpu.get_last_load_a_addr()
    
    def get_last_load_a_value(self):
        """
        Step 0483: Obtiene el valor leído en el último LDH A,(a8) o LD A,(a16).
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Valor leído (0x00 si ninguna)
        """
        return self._cpu.get_last_load_a_value()
    # --- Fin Step 0483 (Last Load A) ---
    
    # --- Step 0484: LY Distribution Top 5 ---
    def get_ly_distribution_top5(self):
        """
        Step 0484: Obtiene el top 5 de valores LY leídos (histograma).
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Lista de tuplas (valor LY, count) ordenadas por count descendente (top 5)
        """
        dist = self._cpu.get_ly_distribution_top5()
        return [(val, count) for val, count in dist]
    
    # --- Step 0484: Branch 0x1290 Getters ---
    def get_branch_0x1290_taken_count(self):
        """
        Step 0484: Obtiene el contador de veces que el branch en 0x1290 fue tomado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Número de veces que el branch fue tomado
        """
        return self._cpu.get_branch_0x1290_taken_count()
    
    def get_branch_0x1290_not_taken_count(self):
        """
        Step 0484: Obtiene el contador de veces que el branch en 0x1290 no fue tomado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Número de veces que el branch no fue tomado
        """
        return self._cpu.get_branch_0x1290_not_taken_count()
    
    def get_branch_0x1290_last_flags(self):
        """
        Step 0484: Obtiene los flags del último branch en 0x1290.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            Flags (registro F) al momento del último branch
        """
        return self._cpu.get_branch_0x1290_last_flags()
    
    def get_branch_0x1290_last_taken(self):
        """
        Step 0484: Obtiene si el último branch en 0x1290 fue tomado.
        
        Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
        
        Returns:
            True si el último branch fue tomado, False si no
        """
        return self._cpu.get_branch_0x1290_last_taken()
    # --- Fin Step 0484 ---
    
    # --- Step 0485: Mario Loop LY Watch Getters ---
    def get_mario_loop_ly_reads_total(self):
        """
        Step 0485: Obtiene el contador total de lecturas LY en el loop de Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Número total de lecturas LY en el loop
        """
        return self._cpu.get_mario_loop_ly_reads_total()
    
    def get_mario_loop_ly_eq_0x91_count(self):
        """
        Step 0485: Obtiene el contador de veces que LY==0x91 en el loop de Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Número de veces que LY==0x91
        """
        return self._cpu.get_mario_loop_ly_eq_0x91_count()
    
    def get_mario_loop_ly_last_value(self):
        """
        Step 0485: Obtiene el último valor de LY leído en el loop de Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Último valor de LY leído
        """
        return self._cpu.get_mario_loop_ly_last_value()
    
    def get_mario_loop_ly_last_timestamp(self):
        """
        Step 0485: Obtiene el timestamp del último read de LY en el loop de Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Timestamp (cycle counter) del último read
        """
        return self._cpu.get_mario_loop_ly_last_timestamp()
    
    def get_mario_loop_ly_last_pc(self):
        """
        Step 0485: Obtiene el PC del último read de LY en el loop de Mario.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            PC del último read de LY
        """
        return self._cpu.get_mario_loop_ly_last_pc()
    
    # --- Step 0485: Branch 0x1290 Correlation Getters ---
    def get_branch_0x1290_eval_count(self):
        """
        Step 0485: Obtiene el contador de evaluaciones del branch en 0x1290.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Número de veces que se evaluó el branch
        """
        return self._cpu.get_branch_0x1290_eval_count()
    
    def get_branch_0x1290_taken_count_0485(self):
        """
        Step 0485: Obtiene el contador de veces que el branch en 0x1290 fue tomado.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Número de veces que el branch fue tomado
        """
        return self._cpu.get_branch_0x1290_taken_count_0485()
    
    def get_branch_0x1290_not_taken_count_0485(self):
        """
        Step 0485: Obtiene el contador de veces que el branch en 0x1290 no fue tomado.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Número de veces que el branch no fue tomado
        """
        return self._cpu.get_branch_0x1290_not_taken_count_0485()
    
    def get_branch_0x1290_last_not_taken_ly_value(self):
        """
        Step 0485: Obtiene el valor de LY del último not-taken del branch en 0x1290.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Valor de LY del último not-taken
        """
        return self._cpu.get_branch_0x1290_last_not_taken_ly_value()
    
    def get_branch_0x1290_last_not_taken_flags(self):
        """
        Step 0485: Obtiene los flags del último not-taken del branch en 0x1290.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Flags del último not-taken
        """
        return self._cpu.get_branch_0x1290_last_not_taken_flags()
    
    def get_branch_0x1290_last_not_taken_next_pc(self):
        """
        Step 0485: Obtiene el siguiente PC después del último not-taken del branch en 0x1290.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Siguiente PC después del not-taken
        """
        return self._cpu.get_branch_0x1290_last_not_taken_next_pc()
    
    def get_mario_loop_trace(self):
        """
        Step 0485: Obtiene el trace del loop de Mario (últimos 64 eventos).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_LOOP=1
        
        Returns:
            Lista de eventos del trace (cada evento es un dict con frame, pc, ly_value, flags, taken, timestamp)
        """
        cdef vector[cpu.LoopTraceEvent] trace = self._cpu.get_mario_loop_trace()
        result = []
        for i in range(trace.size()):
            event = trace[i]
            result.append({
                'frame': event.frame,
                'pc': event.pc,
                'ly_value': event.ly_value,
                'flags': event.flags,
                'taken': event.taken,
                'timestamp': event.timestamp
            })
        return result
    # --- Fin Step 0485 ---
    
    # --- Step 0486: LDH Address Watch Getters ---
    def get_last_ldh_pc(self):
        """
        Step 0486: Obtiene el PC de la última ejecución de LDH.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            PC de la última ejecución de LDH (0xFFFF si ninguna)
        """
        return self._cpu.get_last_ldh_pc()
    
    def get_last_ldh_a8_operand(self):
        """
        Step 0486: Obtiene el operando a8 de la última ejecución de LDH.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Operando a8 de la última ejecución de LDH
        """
        return self._cpu.get_last_ldh_a8_operand()
    
    def get_last_ldh_effective_addr(self):
        """
        Step 0486: Obtiene la dirección efectiva calculada en la última ejecución de LDH.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Dirección efectiva calculada (0xFF00 + a8)
        """
        return self._cpu.get_last_ldh_effective_addr()
    
    def get_last_ldh_is_read(self):
        """
        Step 0486: Obtiene si la última ejecución de LDH fue lectura o escritura.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            True si fue LDH A,(a8), False si fue LDH (a8),A
        """
        return self._cpu.get_last_ldh_is_read()
    
    def get_ldh_addr_mismatch_count(self):
        """
        Step 0486: Obtiene el contador de discrepancias de dirección LDH.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Número de veces que effective_addr != (0xFF00 | a8)
        """
        return self._cpu.get_ldh_addr_mismatch_count()
    # --- Fin Step 0486 (LDH Address Watch) ---
    
    # --- Step 0487: FF92 to IE Trace ---
    def get_ff92_ie_trace(self):
        """
        Step 0487: Obtiene el trace completo de FF92/IE (últimos 64 eventos).
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Returns:
            Lista de diccionarios con los eventos del trace
        """
        if self._cpu == NULL:
            return []
        cdef vector[cpu.FF92IETraceEvent] trace = self._cpu.get_ff92_ie_trace()
        result = []
        for event in trace:
            result.append({
                'type': event.type,  # 0=FF92_W, 1=FF92_R, 2=IE_W
                'frame': event.frame,
                'pc': event.pc,
                'a8': event.a8,
                'effective_addr': event.effective_addr,
                'val': event.val
            })
        return result
    
    def get_ff92_ie_trace_tail(self, size_t n):
        """
        Step 0487: Obtiene los últimos N eventos del trace de FF92/IE.
        
        Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
        
        Args:
            n: Número de eventos a retornar
        
        Returns:
            Lista de diccionarios con los últimos N eventos
        """
        if self._cpu == NULL:
            return []
        cdef vector[cpu.FF92IETraceEvent] trace = self._cpu.get_ff92_ie_trace_tail(n)
        result = []
        for event in trace:
            result.append({
                'type': event.type,
                'frame': event.frame,
                'pc': event.pc,
                'a8': event.a8,
                'effective_addr': event.effective_addr,
                'val': event.val
            })
        return result
    # --- Fin Step 0487 (FF92 to IE Trace) ---
    
    # --- Step 0494: Getters para interrupt_taken_counts e IRQ trace ---
    def get_interrupt_taken_counts(self):
        """
        Step 0494: Obtiene contadores reales de interrupt taken por tipo.
        
        Returns:
            Diccionario con contadores por tipo de interrupción:
            - 'vblank': Contador de VBlank interrupts tomadas
            - 'lcd_stat': Contador de LCD-STAT interrupts tomadas
            - 'timer': Contador de Timer interrupts tomadas
            - 'serial': Contador de Serial interrupts tomadas
            - 'joypad': Contador de Joypad interrupts tomadas
        """
        if self._cpu == NULL:
            return None
        
        cdef const uint32_t* counts = self._cpu.get_interrupt_taken_counts()
        return {
            'vblank': counts[0],
            'lcd_stat': counts[1],
            'timer': counts[2],
            'serial': counts[3],
            'joypad': counts[4],
        }
    
    def get_irq_trace_ring(self, size_t n=10):
        """
        Step 0494: Obtiene ring-buffer de eventos IRQ (últimos N eventos).
        Step 0500: Ampliado con campos adicionales (vector_addr, pc_after, ime_after, irq_type, opcode_at_vector).
        
        Args:
            n: Número de eventos a retornar (máximo 64)
        
        Returns:
            Lista de diccionarios con los eventos IRQ (más recientes primero)
        """
        if self._cpu == NULL:
            return []
        
        cdef vector[cpu.IRQTraceEvent] trace = self._cpu.get_irq_trace_ring(n)
        result = []
        for event in trace:
            result.append({
                'frame': event.frame,
                'pc_before': event.pc_before,
                'vector_addr': event.vector_addr,  # Step 0500
                'pc_after': event.pc_after,  # Step 0500
                'vector': event.vector,  # Alias para compatibilidad
                'ie': event.ie,
                'if_before': event.if_before,
                'if_after': event.if_after,
                'ime_before': event.ime_before,
                'ime_after': event.ime_after,  # Step 0500
                'irq_type': event.irq_type,  # Step 0500
                'opcode_at_vector': event.opcode_at_vector,  # Step 0500
                'sp_before': event.sp_before,
                'sp_after': event.sp_after,
                'pushed_pc_low': event.pushed_pc_low,
                'pushed_pc_high': event.pushed_pc_high,
            })
        return result
    
    def get_reti_trace_ring(self, size_t n=10):
        """
        Step 0500: Obtiene ring-buffer de eventos RETI (últimos N eventos).
        
        Args:
            n: Número de eventos a retornar (máximo 64)
        
        Returns:
            Lista de diccionarios con los eventos RETI (más recientes primero)
        """
        if self._cpu == NULL:
            return []
        
        cdef vector[cpu.RETITraceEvent] trace = self._cpu.get_reti_trace_ring(n)
        result = []
        for event in trace:
            result.append({
                'frame': event.frame,
                'pc': event.pc,
                'return_addr': event.return_addr,
                'ime_after': event.ime_after,
                'sp_before': event.sp_before,
                'sp_after': event.sp_after,
            })
        return result
    
    def get_reti_count(self):
        """
        Step 0500: Obtiene el contador total de RETI ejecutados.
        
        Returns:
            Número total de veces que se ha ejecutado RETI
        """
        if self._cpu == NULL:
            return 0
        return self._cpu.get_reti_count()
    # --- Fin Step 0494/0500 ---
    
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

