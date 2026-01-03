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
        uint8_t* get_framebuffer_rgb_ptr()  # Step 0404: Framebuffer RGB888 para CGB
        const uint8_t* get_framebuffer_indices_ptr() const  # Step 0457: Debug API para tests
        void clear_framebuffer()
        void confirm_framebuffer_read()
        void convert_framebuffer_to_rgb()  # Step 0404: Conversión índices → RGB
        uint8_t get_last_bgp_used() const  # Step 0457: Debug - Paleta reg usado
        uint8_t get_last_obp0_used() const  # Step 0457: Debug - Paleta reg usado
        uint8_t get_last_obp1_used() const  # Step 0457: Debug - Paleta reg usado
        # Step 0458: Debug - Estadísticas de renderizado BG
        int get_bg_pixels_written_count() const
        bool get_first_nonzero_color_idx_seen() const
        uint8_t get_first_nonzero_color_idx_value() const
        const uint8_t* get_last_tile_bytes_read() const
        bool get_last_tile_bytes_valid() const
        uint16_t get_last_tile_addr_read() const
        # Step 0459: Debug - Samples del pipeline idx→shade→rgb
        const uint8_t* get_last_idx_samples() const
        const uint8_t* get_last_shade_samples() const
        const uint8_t* get_last_rgb_samples() const
        int get_last_convert_sample_count() const
        uint8_t get_last_bgp_used_debug() const

