#ifndef MMU_HPP
#define MMU_HPP

#include <cstdint>
#include <vector>

// Forward declarations para evitar dependencia circular
class PPU;
class Timer;
class Joypad;

/**
 * MMU (Memory Management Unit) - Unidad de Gestión de Memoria
 * 
 * Gestiona el espacio de direcciones de 16 bits (0x0000 a 0xFFFF = 65536 bytes)
 * de la Game Boy. En esta primera versión, usa un modelo de memoria plana
 * para máxima velocidad de acceso.
 * 
 * Fuente: Pan Docs - Memory Map
 */
class MMU {
public:
    /**
     * Constructor: Inicializa la memoria a 0.
     */
    MMU();

    /**
     * Destructor.
     */
    ~MMU();

    /**
     * Lee un byte (8 bits) de la dirección especificada.
     * 
     * @param addr Dirección de memoria (0x0000 a 0xFFFF)
     * @return Valor del byte leído (0x00 a 0xFF)
     */
    uint8_t read(uint16_t addr) const;

    /**
     * Escribe un byte (8 bits) en la dirección especificada.
     * 
     * @param addr Dirección de memoria (0x0000 a 0xFFFF)
     * @param value Valor a escribir (se enmascara a 8 bits)
     */
    void write(uint16_t addr, uint8_t value);

    /**
     * Carga datos ROM en memoria, empezando en la dirección 0x0000.
     * 
     * @param data Puntero a los datos ROM
     * @param size Tamaño de los datos en bytes
     */
    void load_rom(const uint8_t* data, size_t size);
    
    /**
     * Establece el puntero a la PPU para permitir lectura dinámica del registro STAT.
     * 
     * El registro STAT (0xFF41) tiene bits de solo lectura (0-2) que son actualizados
     * dinámicamente por la PPU. Para leer el valor correcto, la MMU necesita llamar
     * a PPU::get_stat() cuando se lee 0xFF41.
     * 
     * @param ppu Puntero a la instancia de PPU (puede ser nullptr)
     */
    void setPPU(PPU* ppu);

    /**
     * Establece el puntero al Timer para permitir lectura/escritura del registro DIV.
     * 
     * El registro DIV (0xFF04) es actualizado dinámicamente por el Timer.
     * Para leer el valor correcto, la MMU necesita llamar a Timer::read_div()
     * cuando se lee 0xFF04. Para escribir, llama a Timer::write_div().
     * 
     * @param timer Puntero a la instancia de Timer (puede ser nullptr)
     */
    void setTimer(Timer* timer);

    /**
     * Establece el puntero al Joypad para permitir lectura/escritura del registro P1.
     * 
     * El registro P1 (0xFF00) es controlado por el Joypad. La CPU escribe en P1
     * para seleccionar qué fila de botones leer (direcciones o acciones), y lee
     * el estado de los botones de la fila seleccionada.
     * 
     * @param joypad Puntero a la instancia de Joypad (puede ser nullptr)
     */
    void setJoypad(Joypad* joypad);
    
    /**
     * --- Step 0298: Hack Temporal - Carga Manual de Tiles ---
     * Función temporal que carga tiles básicos en VRAM para pruebas.
     * Esto permite avanzar con el desarrollo mientras se investiga por qué
     * el juego no carga tiles automáticamente.
     * 
     * Carga tiles de prueba en el área de Tile Data (0x8000-0x97FF):
     * - Tile 0: Blanco (todos 0x00)
     * - Tile 1: Patrón simple (cuadros alternados)
     * - Tile 2: Patrón de líneas horizontales
     * - Tile 3: Patrón de líneas verticales
     * 
     * También configura el Tile Map básico (0x9800-0x9BFF) para mostrar los tiles.
     * 
     * NOTA: Esta es una función temporal de desarrollo. Se eliminará una vez
     * que se identifique y corrija el problema real de carga de tiles.
     */
    void load_test_tiles();
    
    /**
     * Solicita una interrupción activando el bit correspondiente en el registro IF (0xFF0F).
     * 
     * Este método permite que componentes del hardware (PPU, Timer, etc.) soliciten
     * interrupciones escribiendo en el registro IF. La CPU procesará estas interrupciones
     * cuando IME esté activo y haya bits activos en IE & IF.
     * 
     * @param bit Número de bit a activar (0-4):
     *            - 0: V-Blank Interrupt
     *            - 1: LCD STAT Interrupt
     *            - 2: Timer Interrupt
     *            - 3: Serial Interrupt
     *            - 4: Joypad Interrupt
     * 
     * Fuente: Pan Docs - Interrupts, Interrupt Flag Register (IF)
     */
    void request_interrupt(uint8_t bit);

    /**
     * Step 0273: Sniper Traces - Getter para banco ROM actual
     * 
     * Retorna el banco ROM actualmente mapeado en el rango 0x4000-0x7FFF.
     * Este método es necesario para la instrumentación de diagnóstico que
     * necesita saber en qué banco de ROM se está ejecutando el código.
     * 
     * @return Número del banco ROM actual (1-based)
     */
    uint16_t get_current_rom_bank() const;
    
    /**
     * Step 0291: Inspección de Estado Inicial de VRAM
     * 
     * Verifica el estado inicial de VRAM después de cargar la ROM
     * para entender si el juego espera que VRAM tenga datos desde el inicio
     * o si la carga es responsabilidad del juego.
     */
    void inspect_vram_initial_state();
    
    /**
     * Step 0297: Dump Inicial de VRAM
     * 
     * Crea un dump detallado del estado inicial de VRAM después de cargar la ROM
     * para verificar si hay datos pre-cargados. Muestra los primeros bytes de
     * Tile Data y Tile Map en formato hexadecimal.
     */
    void dump_vram_initial_state();

    /**
     * Step 0247: Memory Timeline & PC Tracker
     * 
     * Campo público para rastrear el Program Counter (PC) actual de la CPU.
     * La CPU actualiza este campo antes de ejecutar cada instrucción, permitiendo
     * que la MMU registre qué instrucción provocó cada operación de memoria.
     * 
     * Este campo se usa únicamente para diagnóstico y depuración.
     */
    uint16_t debug_current_pc;

private:
    /**
     * Memoria principal: 65536 bytes (64KB)
     * Usamos std::vector para gestión automática de memoria.
     */
    std::vector<uint8_t> memory_;

    /**
     * Tamaño total del espacio de direcciones (16 bits = 65536 bytes)
     */
    static constexpr size_t MEMORY_SIZE = 0x10000;
    
    /**
     * Tipos de MBC soportados.
     */
    enum class MBCType {
        ROM_ONLY,
        MBC1,
        MBC2,
        MBC3,
        MBC5
    };

    /**
     * --- Gestión de ROM / MBC ---
     */
    std::vector<uint8_t> rom_data_;
    MBCType mbc_type_;
    size_t rom_bank_count_;
    uint16_t current_rom_bank_;   // Hasta 9 bits (MBC5)
    uint16_t bank0_rom_;          // Banco mapeado en 0x0000-0x3FFF
    uint16_t bankN_rom_;          // Banco mapeado en 0x4000-0x7FFF

    // Estado específico de MBC1
    uint8_t mbc1_bank_low5_;
    uint8_t mbc1_bank_high2_;
    uint8_t mbc1_mode_;           // 0 = ROM banking, 1 = RAM banking

    // Estado específico de MBC3 (RTC sin implementar, solo stub)
    uint8_t mbc3_rtc_reg_;
    bool mbc3_latch_ready_;

    /**
     * --- Gestión de RAM externa ---
     */
    std::vector<uint8_t> ram_data_;
    size_t ram_bank_size_;
    size_t ram_bank_count_;
    uint8_t ram_bank_;
    bool ram_enabled_;
    
    /**
     * Puntero a la PPU para lectura dinámica del registro STAT (0xFF41).
     * 
     * Este puntero se establece mediante setPPU() y se usa cuando se lee
     * el registro STAT para obtener el valor actualizado de los bits de solo lectura.
     */
    PPU* ppu_;

    /**
     * Puntero al Timer para lectura/escritura del registro DIV (0xFF04).
     * 
     * Este puntero se establece mediante setTimer() y se usa cuando se lee
     * o escribe el registro DIV para obtener/actualizar el valor del contador.
     */
    Timer* timer_;

    /**
     * Puntero al Joypad para lectura/escritura del registro P1 (0xFF00).
     * 
     * Este puntero se establece mediante setJoypad() y se usa cuando se lee
     * o escribe el registro P1 para obtener/actualizar el estado de los botones.
     */
    Joypad* joypad_;

    // Helpers internos de MBC
    void update_bank_mapping();
    uint16_t normalize_rom_bank(uint16_t bank) const;
    void configure_mbc_from_header(uint8_t cart_type, uint8_t rom_size_code, uint8_t ram_size_code);
    void allocate_ram_from_header(uint8_t ram_size_code);
};

#endif // MMU_HPP

