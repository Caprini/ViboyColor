# distutils: language = c++

"""
Definición Cython de la clase CPU de C++.

Este archivo .pxd declara la interfaz de la clase CPU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp cimport bool

# Forward declarations (necesarios para punteros)
cdef extern from "MMU.hpp":
    cdef cppclass MMU:
        pass

cdef extern from "Registers.hpp":
    cdef cppclass CoreRegisters:
        pass

cdef extern from "PPU.hpp":
    cdef cppclass PPU:
        pass

cdef extern from "Timer.hpp":
    cdef cppclass Timer:
        pass

cdef extern from "CPU.hpp":
    cdef cppclass CPU:
        # Constructor: recibe punteros a MMU y CoreRegisters
        CPU(MMU* mmu, CoreRegisters* registers) except +
        
        # Método principal: ejecuta un ciclo de instrucción
        int step()
        
        # Establece el puntero a la PPU para sincronización ciclo a ciclo
        void setPPU(PPU* ppu)
        
        # Establece el puntero al Timer para actualización del registro DIV
        void setTimer(Timer* timer)
        
        # Ejecuta una scanline completa (456 T-Cycles) con sincronización ciclo a ciclo
        void run_scanline()
        
        # Obtiene el contador de ciclos acumulados
        uint32_t get_cycles()
        
        # Obtiene el estado de IME (Interrupt Master Enable)
        bool get_ime()
        
        # Establece el estado de IME (Interrupt Master Enable)
        void set_ime(bool value)
        
        # Obtiene el estado de HALT
        bool get_halted()
        
        # Step 0469: Obtiene el contador de VBlank IRQ servidos
        uint32_t get_vblank_irq_serviced_count() const
        
        # Step 0434: Triage mode
        void set_triage_mode(bool active, int frame_limit)
        void log_triage_summary()
        
        # Step 0436: Pokemon micro trace
        void set_pokemon_micro_trace(bool active)
        void log_pokemon_micro_trace_summary()
        
        # Step 0470: Contadores de EI/DI
        uint32_t get_ei_count() const
        uint32_t get_di_count() const
        uint32_t get_ime_set_events_count() const
        uint16_t get_last_ime_set_pc() const
        uint32_t get_last_ime_set_timestamp() const
        uint16_t get_last_ei_pc() const
        uint16_t get_last_di_pc() const
        bool get_ei_pending() const
        
        # Step 0472: Contadores de STOP
        uint32_t get_stop_executed_count() const
        uint16_t get_last_stop_pc() const
        # Step 0475: IF Clear on Service Tracking
        uint16_t get_last_irq_serviced_vector() const
        uint32_t get_last_irq_serviced_timestamp() const
        uint8_t get_last_if_before_service() const
        uint8_t get_last_if_after_service() const
        uint8_t get_last_if_clear_mask() const
        # Step 0482: Branch Decision Counters (gated por VIBOY_DEBUG_BRANCH=1)
        uint32_t get_branch_taken_count(uint16_t pc) const
        uint32_t get_branch_not_taken_count(uint16_t pc) const
        uint16_t get_last_cond_jump_pc() const
        uint16_t get_last_target() const
        bool get_last_taken() const
        uint8_t get_last_flags() const
        # Step 0482: Last Compare/BIT Tracking (gated por VIBOY_DEBUG_BRANCH=1)
        uint16_t get_last_cmp_pc() const
        uint8_t get_last_cmp_a() const
        uint8_t get_last_cmp_imm() const
        uint8_t get_last_cmp_result_flags() const
        uint16_t get_last_bit_pc() const
        uint8_t get_last_bit_n() const
        uint8_t get_last_bit_value() const

