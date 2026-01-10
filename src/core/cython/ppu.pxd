# distutils: language = c++

"""
Definición Cython de la clase PPU de C++.

Este archivo .pxd declara la interfaz de la clase PPU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t, uint64_t
from libcpp cimport bool
from libcpp.vector cimport vector

# Forward declaration de MMU (ya está definida en mmu.pxd)
cimport mmu

cdef extern from "PPU.hpp":
    # Step 0488: Estructura para estadísticas del framebuffer
    cdef struct FrameBufferStats:
        uint32_t fb_crc32
        uint32_t fb_unique_colors
        uint32_t fb_nonwhite_count
        uint32_t fb_nonblack_count
        uint32_t fb_top4_colors[4]
        uint32_t fb_top4_colors_count[4]
        bool fb_changed_since_last
        uint32_t fb_last_hash
    
    # Step 0489: Estructura para estadísticas de tres buffers (prueba irrefutable)
    cdef struct ThreeBufferStats:
        uint32_t idx_crc32
        uint32_t idx_unique
        uint32_t idx_nonzero
        uint32_t rgb_crc32
        uint32_t rgb_unique_colors_approx
        uint32_t rgb_nonwhite_count
        uint32_t present_crc32
        uint32_t present_nonwhite_count
        uint32_t present_fmt
        uint32_t present_pitch
        uint32_t present_w
        uint32_t present_h
    
    # Step 0489: Estructura para estadísticas de fetch de tiles DMG
    cdef struct DMGTileFetchStats:
        uint32_t tile_bytes_read_nonzero_count
        uint32_t tile_bytes_read_total_count
        uint16_t top_vram_read_addrs[10]
        uint32_t top_vram_read_counts[10]
    
    # Step 0498: Estructura para eventos de BufferTrace con CRC32
    cdef struct BufferTraceEvent:
        uint64_t frame_id
        uint64_t framebuffer_frame_id
        uint32_t front_idx_crc32
        uint32_t front_rgb_crc32
        uint32_t back_idx_crc32
        uint32_t back_rgb_crc32
        uint32_t buffer_uid
    
    # Step 0501: Estructura para estadísticas de modo PPU por frame
    cdef struct PPUModeStats:
        uint32_t mode_entries_count[4]  # Mode 0, 1, 2, 3
        uint32_t mode_cycles[4]         # Ciclos totales en cada modo
        uint8_t ly_min
        uint8_t ly_max
        uint32_t frames_with_mode3_stuck  # Si mode3 dura demasiado
    
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
        bool is_frame_ready() const  # Step 0467: Solo verifica, no resetea
        bool get_frame_ready_and_reset()
        uint8_t* get_framebuffer_ptr()
        uint8_t* get_framebuffer_rgb_ptr()  # Step 0404: Framebuffer RGB888 para CGB
        const uint8_t* get_framebuffer_indices_ptr() const  # Step 0457: Debug API para tests
        const uint8_t* get_presented_framebuffer_indices_ptr()  # Step 0468
        uint64_t get_frame_counter() const  # Step 0291: Contador de frames
        uint64_t get_frame_id() const  # Step 0497: Frame ID único actual
        uint64_t get_framebuffer_frame_id() const  # Step 0497: Frame ID del buffer front
        uint32_t get_vblank_irq_requested_count() const  # Step 0469: Contador VBlank IRQ solicitado
        const FrameBufferStats& get_framebuffer_stats() const  # Step 0488: Estadísticas del framebuffer
        const ThreeBufferStats& get_three_buffer_stats() const  # Step 0489: Estadísticas de tres buffers
        void set_present_stats(uint32_t present_crc32, uint32_t present_nonwhite_count, uint32_t present_fmt, uint32_t present_pitch, uint32_t present_w, uint32_t present_h)  # Step 0489: Actualizar stats de presentación
        const DMGTileFetchStats& get_dmg_tile_fetch_stats() const  # Step 0489: Estadísticas de fetch de tiles DMG
        vector[BufferTraceEvent] get_buffer_trace_ring(size_t max_events) const  # Step 0498: Ring buffer de eventos BufferTrace
        const PPUModeStats& get_ppu_mode_stats() const  # Step 0501: Estadísticas de modo PPU por frame
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

