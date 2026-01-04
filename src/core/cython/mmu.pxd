# distutils: language = c++

"""
Definición Cython de la clase MMU de C++.

Este archivo .pxd declara la interfaz de la clase MMU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t

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
    # Step 0404: Hardware Mode enum
    cdef enum class HardwareMode:
        DMG
        CGB
    
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

