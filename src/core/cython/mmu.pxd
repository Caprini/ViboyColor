# distutils: language = c++

"""
Definición Cython de la clase MMU de C++.

Este archivo .pxd declara la interfaz de la clase MMU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t
from libcpp.vector cimport vector
from libcpp.pair cimport pair

# Forward declarations (evitar dependencia circular)
cdef extern from "PPU.hpp":
    cdef cppclass PPU:
        pass

cdef extern from "Timer.hpp":
    cdef cppclass Timer:
        pass

cdef extern from "Joypad.hpp":
    cdef cppclass Joypad:
        pass

cdef extern from "MMU.hpp":
    # Step 0485: Declarar estructura JOYPTraceEvent (definida fuera de la clase MMU)
    # Step 0486: Actualizado con source tag y estado interno P1
    cdef struct JOYPTraceEvent:
        int type  # READ=0, WRITE=1
        int source  # PROGRAM=0, CPU_POLL=1
        uint16_t pc
        uint8_t value_written
        uint8_t value_read
        uint8_t p1_reg_before  # P1 interno antes del write (solo WRITE)
        uint8_t p1_reg_after   # P1 interno después del write (solo WRITE)
        uint8_t p1_reg_at_read  # P1 interno en el momento del read (solo READ)
        uint8_t select_bits_at_read  # Bits 4-5 en el momento del read (solo READ)
        uint8_t low_nibble_at_read   # Bits 0-3 leídos (solo READ)
        uint32_t timestamp
    
    # Step 0404: Hardware Mode enum
    cdef enum class HardwareMode:
        DMG
        CGB
    
    # Step 0489: Estructura CGBPaletteWriteStats (definida fuera de la clase MMU)
    cdef struct CGBPaletteWriteStats:
        uint32_t bgpd_write_count
        uint16_t last_bgpd_write_pc
        uint8_t last_bgpd_value
        uint8_t last_bgpi
        uint32_t obpd_write_count
        uint16_t last_obpd_write_pc
        uint8_t last_obpd_value
        uint8_t last_obpi
    
    # Step 0494: Estructura IFIETracking (definida fuera de la clase MMU)
    cdef struct IFIETracking:
        uint16_t last_if_write_pc
        uint8_t last_if_write_value
        uint8_t last_if_applied_value
        uint32_t if_write_count
        uint16_t last_ie_write_pc
        uint8_t last_ie_write_value
        uint8_t last_ie_applied_value
        uint32_t ie_write_count
    
    # Step 0494: Estructura HRAMFFC5Tracking (definida fuera de la clase MMU)
    cdef struct HRAMFFC5Tracking:
        uint16_t last_write_pc
        uint8_t last_write_value
        uint32_t write_count
        uint32_t first_write_frame
    
    # Step 0490: Estructura VRAMWriteStats (definida fuera de la clase MMU)
    # Step 0491: Ampliada para separar attempts vs nonzero writes + bank + VBK
    # Step 0492: Ampliada con tracking de Clear VRAM
    cdef struct TiledataWriteEvent:
        uint32_t frame
        uint16_t pc
        uint16_t addr
        uint8_t val
    
    cdef struct VRAMWriteStats:
        # Tiledata (0x8000-0x97FF)
        uint32_t tiledata_attempts_bank0
        uint32_t tiledata_attempts_bank1
        uint32_t tiledata_nonzero_writes_bank0
        uint32_t tiledata_nonzero_writes_bank1
        # Tilemap (0x9800-0x9FFF)
        uint32_t tilemap_attempts_bank0
        uint32_t tilemap_attempts_bank1
        uint32_t tilemap_nonzero_writes_bank0
        uint32_t tilemap_nonzero_writes_bank1
        # Last nonzero tiledata write
        uint16_t last_nonzero_tiledata_write_pc
        uint16_t last_nonzero_tiledata_write_addr
        uint8_t last_nonzero_tiledata_write_val
        uint8_t last_nonzero_tiledata_write_bank
        # Tracking de VBK
        uint8_t vbk_value_current
        uint32_t vbk_write_count
        uint16_t last_vbk_write_pc
        uint8_t last_vbk_write_val
        # Legacy (mantener por compatibilidad)
        uint32_t vram_write_attempts_tiledata
        uint32_t vram_write_attempts_tilemap
        uint32_t vram_write_blocked_mode3_tiledata
        uint32_t vram_write_blocked_mode3_tilemap
        uint16_t last_blocked_vram_write_pc
        uint16_t last_blocked_vram_write_addr
        # Step 0492: Clear VRAM tracking
        uint32_t tiledata_clear_done_frame
        uint32_t tiledata_attempts_after_clear
        uint32_t tiledata_nonzero_after_clear
        uint32_t tiledata_first_nonzero_frame
        uint16_t tiledata_first_nonzero_pc
        uint16_t tiledata_first_nonzero_addr
        uint8_t tiledata_first_nonzero_val
        TiledataWriteEvent tiledata_write_ring_[128]  # TILEDATA_WRITE_RING_SIZE = 128 (con guion bajo para coincidir con C++)
        uint32_t tiledata_write_ring_head_  # Con guion bajo para coincidir con C++
        bint tiledata_write_ring_active_  # Con guion bajo para coincidir con C++
    
    cdef cppclass MMU:
        MMU() except +
        uint8_t read(uint16_t addr)
        void write(uint16_t addr, uint8_t value)
        void load_rom(const uint8_t* data, size_t size)
        void setPPU(PPU* ppu)
        void setTimer(Timer* timer)
        void setJoypad(Joypad* joypad)
        void request_interrupt(uint8_t bit)
        uint16_t debug_current_pc  # Step 0247: PC tracker público
        void load_test_tiles()
        void set_boot_rom(const uint8_t* data, size_t size)  # Step 0401
        int is_boot_rom_enabled()  # Step 0401 (devuelve int para evitar problemas de conversión)
        void enable_bootrom_stub(bool enable, bool cgb_mode)  # Step 0402
        void set_hardware_mode(HardwareMode mode)  # Step 0404
        HardwareMode get_hardware_mode()  # Step 0404
        void initialize_io_registers()  # Step 0404
        void log_dma_vram_summary()  # Step 0410
        # Step 0425: Eliminado set_test_mode_allow_rom_writes() (hack no spec-correct)
        void set_triage_mode(bool active)  # Step 0434
        void set_triage_pc(uint16_t pc)  # Step 0434
        void log_triage_summary()  # Step 0434
        void set_pokemon_loop_trace(bool active)  # Step 0436
        void log_pokemon_loop_trace_summary()  # Step 0436
        void set_current_hl(uint16_t hl_value)  # Step 0436
        uint8_t read_raw(uint16_t addr)  # Step 0450
        void dump_raw_range(uint16_t start, uint16_t length, uint8_t* buffer)  # Step 0450
        void log_mbc_writes_summary()  # Step 0450
        uint32_t get_ie_write_count() const  # Step 0470
        uint32_t get_if_write_count() const  # Step 0470
        uint8_t get_last_ie_written() const  # Step 0470
        uint8_t get_last_if_written() const  # Step 0470
        uint32_t get_io_read_count(uint16_t addr) const  # Step 0470
        uint8_t get_last_ie_write_value() const  # Step 0471
        uint16_t get_last_ie_write_pc() const  # Step 0471
        uint32_t get_last_ie_write_timestamp() const  # Step 0477
        uint8_t get_last_ie_read_value() const  # Step 0471
        uint32_t get_ie_read_count() const  # Step 0471
        uint32_t get_key1_write_count() const  # Step 0472
        uint8_t get_last_key1_write_value() const  # Step 0472
        uint16_t get_last_key1_write_pc() const  # Step 0472
        uint32_t get_joyp_write_count() const  # Step 0472
        uint8_t get_last_joyp_write_value() const  # Step 0472
        uint16_t get_last_joyp_write_pc() const  # Step 0472
        uint32_t get_joyp_read_count_program() const  # Step 0481
        uint16_t get_last_joyp_read_pc() const  # Step 0481
        uint8_t get_last_joyp_read_value() const  # Step 0481
        uint32_t get_if_read_count() const  # Step 0474
        uint16_t get_last_if_write_pc() const  # Step 0474
        uint8_t get_last_if_write_val() const  # Step 0474
        uint32_t get_last_if_write_timestamp() const  # Step 0477
        uint8_t get_last_if_read_val() const  # Step 0474
        uint32_t get_if_writes_0() const  # Step 0474
        uint32_t get_if_writes_nonzero() const  # Step 0474
        uint8_t get_ly_read_min() const  # Step 0474
        uint8_t get_ly_read_max() const  # Step 0474
        uint8_t get_last_ly_read() const  # Step 0474
        uint8_t get_last_stat_read() const  # Step 0474
        void set_irq_poll_active(bool active)  # Step 0475
        uint32_t get_if_reads_program() const  # Step 0475
        uint32_t get_if_reads_cpu_poll() const  # Step 0475
        uint32_t get_if_writes_program() const  # Step 0475
        uint32_t get_ie_reads_program() const  # Step 0475
        uint32_t get_ie_reads_cpu_poll() const  # Step 0475
        uint32_t get_ie_writes_program() const  # Step 0475
        int get_boot_logo_prefill_enabled() const  # Step 0475 (devuelve int para evitar problemas de conversión en Cython)
        void set_waits_on_addr(uint16_t addr)  # Step 0479
        uint32_t get_ly_changes_this_frame() const  # Step 0479
        uint32_t get_stat_mode_changes_count() const  # Step 0479
        uint32_t get_if_bit0_set_count_this_frame() const  # Step 0479
        void add_hram_watch(uint16_t addr)  # Step 0481
        uint32_t get_hram_write_count(uint16_t addr) const  # Step 0481
        uint16_t get_hram_last_write_pc(uint16_t addr) const  # Step 0481
        uint8_t get_hram_last_write_value(uint16_t addr) const  # Step 0481
        uint32_t get_hram_first_write_frame(uint16_t addr) const  # Step 0481
        uint32_t get_hram_read_count_program(uint16_t addr) const  # Step 0481
        uint32_t get_hram_last_write_frame(uint16_t addr) const  # Step 0483
        uint16_t get_hram_last_read_pc(uint16_t addr) const  # Step 0483
        uint8_t get_hram_last_read_value(uint16_t addr) const  # Step 0483
        uint32_t get_lcdc_disable_events() const  # Step 0482
        uint8_t get_lcdc_current() const  # Step 0484
        vector[pair[uint8_t, uint32_t]] get_joyp_write_distribution_top5() const  # Step 0484
        vector[uint16_t] get_joyp_write_pcs_by_value(uint8_t value) const  # Step 0484
        uint8_t get_joyp_last_read_select_bits() const  # Step 0484
        uint8_t get_joyp_last_read_low_nibble() const  # Step 0484
        # Step 0485: JOYP Trace
        vector[JOYPTraceEvent] get_joyp_trace() const
        vector[JOYPTraceEvent] get_joyp_trace_tail(size_t n) const
        uint32_t get_joyp_reads_with_buttons_selected_count() const
        uint32_t get_joyp_reads_with_dpad_selected_count() const
        uint32_t get_joyp_reads_with_none_selected_count() const
        uint16_t get_last_lcdc_write_pc() const  # Step 0482
        uint8_t get_last_lcdc_write_value() const  # Step 0482
        # Step 0486: HRAM FF92 Watch (métodos antiguos, mantener compatibilidad)
        uint16_t get_hram_ff92_last_write_pc() const
        uint8_t get_hram_ff92_last_write_val() const
        uint16_t get_hram_ff92_last_read_pc() const
        uint8_t get_hram_ff92_last_read_val() const
        uint8_t get_hram_ff92_readback_after_write_val() const
        uint32_t get_hram_ff92_write_readback_mismatch_count() const
        # Step 0487: FF92 Single Source of Truth (nuevos métodos)
        uint32_t get_ff92_write_count_total() const
        uint16_t get_ff92_last_write_pc() const
        uint8_t get_ff92_last_write_val() const
        uint32_t get_ff92_read_count_total() const
        uint16_t get_ff92_last_read_pc() const
        uint8_t get_ff92_last_read_val() const
        # Step 0487: IE Write Tracking
        uint8_t get_ie_value_after_write() const
        uint16_t get_ie_last_write_pc() const
        uint32_t get_ie_write_count_total() const
        # Step 0486: JOYP Contadores por Source (métodos antiguos, mantener compatibilidad)
        uint32_t get_joyp_reads_prog_buttons_sel() const
        uint32_t get_joyp_reads_prog_dpad_sel() const
        uint32_t get_joyp_reads_prog_none_sel() const
        uint32_t get_joyp_reads_cpu_poll_buttons_sel() const
        uint32_t get_joyp_reads_cpu_poll_dpad_sel() const
        uint32_t get_joyp_reads_cpu_poll_none_sel() const
        # Step 0487: JOYP Contadores por Selección (nuevos métodos)
        uint32_t get_joyp_write_buttons_selected_total() const
        uint32_t get_joyp_write_dpad_selected_total() const
        uint32_t get_joyp_write_none_selected_total() const
        uint32_t get_joyp_read_buttons_selected_total_prog() const
        uint32_t get_joyp_read_dpad_selected_total_prog() const
        uint32_t get_joyp_read_none_selected_total_prog() const
        uint32_t get_joyp_read_buttons_selected_total_cpu_poll() const
        uint32_t get_joyp_read_dpad_selected_total_cpu_poll() const
        uint32_t get_joyp_read_none_selected_total_cpu_poll() const
        # Step 0489: CGB Palette Write Stats
        CGBPaletteWriteStats get_cgb_palette_write_stats() const
        # Step 0490: VRAM Write Stats
        VRAMWriteStats get_vram_write_stats() const
        # Step 0494: IF/IE y HRAM[0xFFC5] Tracking
        IFIETracking get_if_ie_tracking() const
        HRAMFFC5Tracking get_hram_ffc5_tracking() const
        # Step 0494: Acceso directo a paletas CGB (para decode)
        uint8_t read_bg_palette_data(uint8_t index) const
        uint8_t read_obj_palette_data(uint8_t index) const

