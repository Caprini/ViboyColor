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

