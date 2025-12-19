# distutils: language = c++

"""
Definición Cython de la clase PPU de C++.

Este archivo .pxd declara la interfaz de la clase PPU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp cimport bool

# Forward declaration de MMU (ya está definida en mmu.pxd)
cimport mmu

cdef extern from "PPU.hpp":
    cdef cppclass PPU:
        # Constantes públicas
        @staticmethod
        const uint16_t CYCLES_PER_SCANLINE
        @staticmethod
        const uint8_t VISIBLE_LINES
        @staticmethod
        const uint8_t VBLANK_START
        @staticmethod
        const uint8_t TOTAL_LINES
        @staticmethod
        const uint8_t MODE_0_HBLANK
        @staticmethod
        const uint8_t MODE_1_VBLANK
        @staticmethod
        const uint8_t MODE_2_OAM_SEARCH
        @staticmethod
        const uint8_t MODE_3_PIXEL_TRANSFER
        
        # Constructor y destructor
        PPU(mmu.MMU* mmu) except +
        
        # Métodos principales
        void step(int cpu_cycles)
        uint8_t get_ly()
        uint8_t get_mode()
        uint8_t get_lyc()
        void set_lyc(uint8_t value)
        bool get_frame_ready_and_reset()
        uint8_t* get_framebuffer_ptr()

