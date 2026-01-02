# distutils: language = c++

"""
Definición Cython de la clase MMU de C++.

Este archivo .pxd declara la interfaz de la clase MMU para que Cython
pueda generar el código de enlace correcto.
"""

from libc.stdint cimport uint8_t, uint16_t

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

