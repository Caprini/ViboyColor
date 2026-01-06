#ifndef MMU_HPP
#define MMU_HPP

#include <cstdint>
#include <vector>
#include <map>  // Step 0484: Para joyp_write_distribution_
#include <chrono>  // Step 0409: Para RTC (MBC3)

// Forward declarations para evitar dependencia circular
class PPU;
class Timer;
class Joypad;

/**
 * Step 0404: Hardware Mode - Modo de hardware (DMG vs CGB)
 * 
 * Permite diferenciar claramente entre modos DMG (Game Boy clásico)
 * y CGB (Game Boy Color) para inicializar registros correctamente
 * según el modelo de hardware.
 * 
 * Fuente: Pan Docs - Power Up Sequence, CGB Registers
 */
enum class HardwareMode {
    DMG,  // Game Boy clásico (monocromo)
    CGB   // Game Boy Color
};

/**
 * Step 0487: JOYP Select Label
 * 
 * Etiquetas legibles para los bits de selección de JOYP (bits 4-5).
 * Evita errores de interpretación como "0x30 = buttons selected".
 */
enum JOYPSelectLabel {
    BOTH_SELECTED,      // sel_bits=0b00 (0x00)
    BUTTONS_SELECTED,   // sel_bits=0b01 (0x10) - P14=0
    DPAD_SELECTED,      // sel_bits=0b10 (0x20) - P15=0
    NONE_SELECTED       // sel_bits=0b11 (0x30)
};

/**
 * Step 0489: Estructura para estadísticas de writes a paletas CGB.
 * 
 * Permite rastrear si el juego está escribiendo a paletas CGB y cuándo.
 */
struct CGBPaletteWriteStats {
    // BGPI/BGPD
    uint32_t bgpd_write_count;
    uint16_t last_bgpd_write_pc;
    uint8_t last_bgpd_value;
    uint8_t last_bgpi;
    
    // OBPI/OBPD
    uint32_t obpd_write_count;
    uint16_t last_obpd_write_pc;
    uint8_t last_obpd_value;
    uint8_t last_obpi;
};

/**
 * Step 0490: Estructura para estadísticas de writes a VRAM.
 * Step 0491: Ampliada para separar attempts vs nonzero writes + bank + VBK.
 * 
 * Permite rastrear si el juego está escribiendo a VRAM y si está bloqueado por Mode 3.
 */
struct VRAMWriteStats {
    // Tiledata (0x8000-0x97FF)
    uint32_t tiledata_attempts_bank0;      // Intentos de write a tiledata bank 0
    uint32_t tiledata_attempts_bank1;      // Intentos de write a tiledata bank 1
    uint32_t tiledata_nonzero_writes_bank0;  // Writes no-cero a tiledata bank 0
    uint32_t tiledata_nonzero_writes_bank1;  // Writes no-cero a tiledata bank 1
    
    // Tilemap (0x9800-0x9FFF)
    uint32_t tilemap_attempts_bank0;      // Intentos de write a tilemap bank 0
    uint32_t tilemap_attempts_bank1;      // Intentos de write a tilemap bank 1
    uint32_t tilemap_nonzero_writes_bank0;  // Writes no-cero a tilemap bank 0
    uint32_t tilemap_nonzero_writes_bank1;  // Writes no-cero a tilemap bank 1
    
    // Last nonzero tiledata write
    uint16_t last_nonzero_tiledata_write_pc;
    uint16_t last_nonzero_tiledata_write_addr;
    uint8_t last_nonzero_tiledata_write_val;
    uint8_t last_nonzero_tiledata_write_bank;
    
    // Tracking de VBK
    uint8_t vbk_value_current;              // Valor actual de VBK (0xFF4F)
    uint32_t vbk_write_count;               // Número de writes a VBK
    uint16_t last_vbk_write_pc;             // PC del último write a VBK
    uint8_t last_vbk_write_val;              // Valor escrito a VBK
    
    // Legacy (mantener por compatibilidad)
    uint32_t vram_write_attempts_tiledata;  // Total attempts (bank0 + bank1)
    uint32_t vram_write_attempts_tilemap;   // Total attempts (bank0 + bank1)
    uint32_t vram_write_blocked_mode3_tiledata;
    uint32_t vram_write_blocked_mode3_tilemap;
    uint16_t last_blocked_vram_write_pc;
    uint16_t last_blocked_vram_write_addr;
};

/**
 * Step 0487: Helper function para obtener etiqueta de selección JOYP
 * 
 * @param select_bits Bits 4-5 del valor escrito/leído (0x00, 0x10, 0x20, 0x30)
 * @return Etiqueta legible correspondiente
 */
inline JOYPSelectLabel get_joyp_select_label(uint8_t select_bits) {
    // Extraer bits 4-5
    uint8_t bits_4_5 = (select_bits >> 4) & 0x03;
    switch (bits_4_5) {
        case 0x00: return BOTH_SELECTED;
        case 0x01: return BUTTONS_SELECTED;   // 0x10 escrito → bits 4-5 = 01
        case 0x02: return DPAD_SELECTED;      // 0x20 escrito → bits 4-5 = 10
        case 0x03: return NONE_SELECTED;      // 0x30 escrito → bits 4-5 = 11
        default: return NONE_SELECTED;
    }
}

/**
 * Step 0485: JOYP Access Trace Event
 * Step 0486: Actualizado con estado interno P1 y source tag
 * Step 0487: Actualizado con select_label para evitar errores de interpretación
 * 
 * Estructura para rastrear accesos a JOYP (0xFF00) en un ring-buffer.
 */
struct JOYPTraceEvent {
    enum Type { READ, WRITE };
    enum Source { PROGRAM, CPU_POLL };
    
    Type type;
    Source source;
    uint16_t pc;
    uint8_t value_written;      // Si WRITE
    uint8_t value_read;         // Si READ
    uint8_t p1_reg_before;      // P1 interno antes del write (solo WRITE)
    uint8_t p1_reg_after;       // P1 interno después del write (solo WRITE)
    uint8_t p1_reg_at_read;     // P1 interno en el momento del read (solo READ)
    uint8_t select_bits_at_read;  // Bits 4-5 en el momento del read (solo READ)
    uint8_t low_nibble_at_read;   // Bits 0-3 leídos (solo READ)
    JOYPSelectLabel select_label;  // Step 0487: Etiqueta legible (solo READ)
    JOYPSelectLabel select_label_after;  // Step 0487: Etiqueta después del write (solo WRITE)
    uint32_t timestamp;          // Cycle counter o contador monotónico
    
    JOYPTraceEvent() : type(READ), source(PROGRAM), pc(0xFFFF), value_written(0), value_read(0),
                       p1_reg_before(0), p1_reg_after(0), p1_reg_at_read(0),
                       select_bits_at_read(0), low_nibble_at_read(0),
                       select_label(NONE_SELECTED), select_label_after(NONE_SELECTED), timestamp(0) {}
};

/**
 * Step 0486: FF92 to IE Trace Event
 * 
 * Estructura para rastrear la secuencia FF92 write → FF92 read → IE write.
 */
struct FF92ToIETrace {
    uint8_t ff92_written_val;
    uint8_t ff92_read_val;
    uint8_t ie_written_val;
    uint16_t ff92_write_pc;
    uint16_t ff92_read_pc;
    uint16_t ie_write_pc;
    uint32_t timestamp;
    uint32_t frame;
    
    FF92ToIETrace() : ff92_written_val(0), ff92_read_val(0), ie_written_val(0),
                     ff92_write_pc(0xFFFF), ff92_read_pc(0xFFFF), ie_write_pc(0xFFFF),
                     timestamp(0), frame(0) {}
};

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
     * Step 0353: Verificación del Estado Inicial de VRAM
     * 
     * Verifica el estado inicial de VRAM cuando se carga la ROM para entender
     * si VRAM tiene datos al inicio (antes de que el juego empiece a ejecutarse).
     */
    void check_initial_vram_state();
    
    /**
     * Step 0355: Verificación de Estado de VRAM en Múltiples Puntos
     * 
     * Verifica el estado de VRAM en diferentes momentos para identificar la discrepancia
     * entre mediciones en diferentes steps.
     */
    void check_vram_state_at_point(const char* point_name);

    /**
     * Step 0382: Obtener estadísticas de escrituras a VRAM.
     * 
     * Permite consultar cuántas escrituras totales y no-cero se han hecho a VRAM
     * desde el inicio de la ejecución.
     * 
     * @param total_writes Referencia para almacenar el total de escrituras a VRAM
     * @param nonzero_writes Referencia para almacenar escrituras no-cero a VRAM
     */
    void get_vram_write_stats(int& total_writes, int& nonzero_writes) const;

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

    /**
     * Step 0385: Activa/desactiva el trazado de MMIO y RAM durante el wait-loop.
     * 
     * Cuando está activo, el MMU loguea accesos a MMIO (0xFF00-0xFFFF),
     * HRAM (0xFF80-0xFFFE) y direcciones repetidas en WRAM (0xC000-0xDFFF).
     * 
     * @param active true para activar trazado, false para desactivar
     */
    void set_waitloop_trace(bool active);
    
    /**
     * Step 0385: Activa/desactiva el trazado de MMIO dentro del ISR VBlank.
     * 
     * Cuando está activo, el MMU loguea accesos a MMIO durante el ISR VBlank,
     * especialmente escrituras a HDMA, VBK, paletas, y clears de IF.
     * 
     * @param active true para activar trazado, false para desactivar
     */
    void set_vblank_isr_trace(bool active);
    
    /**
     * Step 0400: Genera resumen de secuencia de inicialización.
     * Registra cambios de LCDC, BGP, IE/IME con frames.
     */
    void log_init_sequence_summary();
    
    /**
     * Step 0410: Genera resumen completo de actividad DMA/HDMA y escrituras VRAM.
     * Incluye contadores de OAM DMA, HDMA, y escrituras CPU a TileData.
     */
    void log_dma_vram_summary();
    
    /**
     * Step 0411: Genera resumen periódico de IRQ requests reales.
     * Muestra contadores de requests por tipo (VBlank, STAT, Timer, etc.)
     * y el estado actual de IF, IE, IME, LCDC, LY, TAC.
     * 
     * @param frame_count Número de frame actual para referencia
     */
    void log_irq_requests_summary(uint64_t frame_count);
    
    /**
     * Step 0401: Boot ROM opcional (provista por el usuario)
     * 
     * Permite cargar una Boot ROM real (DMG o CGB) que se mapea en el rango
     * 0x0000-0x00FF (DMG: 256 bytes) o 0x0000-0x00FF + 0x0200-0x08FF (CGB: 2304 bytes).
     * 
     * La Boot ROM se deshabilita al escribir cualquier valor != 0 al registro 0xFF50.
     * 
     * @param data Puntero a los datos de la Boot ROM
     * @param size Tamaño en bytes (256 para DMG, 2304 para CGB)
     * 
     * Fuente: Pan Docs - "Boot ROM", "FF50 - BOOT - Boot ROM disable"
     */
    void set_boot_rom(const uint8_t* data, size_t size);
    
    /**
     * Step 0401: Verifica si la Boot ROM está activa
     * 
     * @return 1 si la Boot ROM está habilitada y mapeada, 0 en caso contrario
     */
    int is_boot_rom_enabled() const;
    
    /**
     * Step 0402: Habilita el modo stub de Boot ROM (sin binario propietario)
     * 
     * Este modo permite validar el wiring end-to-end sin depender de un archivo Boot ROM.
     * El stub NO emula instrucciones reales del boot, solo fuerza un conjunto mínimo
     * de estado post-boot documentado (Pan Docs) y marca boot_rom_enabled_=false inmediatamente.
     * 
     * @param enable true para habilitar stub, false para desactivar
     * @param cgb_mode true para modo CGB, false para modo DMG
     * 
     * Nota: Este stub es diferente de "boot real". Solo valida que el pipeline de
     * inicialización y el control de PC no dependen de hacks del PPU.
     */
    void enable_bootrom_stub(bool enable, bool cgb_mode);
    
    /**
     * Step 0404: Configura el modo de hardware (DMG o CGB)
     * 
     * Establece si el emulador debe comportarse como Game Boy clásico (DMG)
     * o Game Boy Color (CGB). Esto afecta la inicialización de registros I/O
     * y el comportamiento de componentes específicos (paletas, banking, etc.).
     * 
     * @param mode Modo de hardware (HardwareMode::DMG o HardwareMode::CGB)
     * 
     * Fuente: Pan Docs - Power Up Sequence, CGB Registers
     */
    void set_hardware_mode(HardwareMode mode);
    
    /**
     * Step 0404: Obtiene el modo de hardware actual
     * 
     * @return Modo de hardware actual (HardwareMode::DMG o HardwareMode::CGB)
     */
    HardwareMode get_hardware_mode() const;
    
    /**
     * Step 0404: Inicializa registros I/O según el modo de hardware
     * 
     * Configura los registros I/O (LCDC, BGP, CGB-specific, etc.) según el modo
     * de hardware actual (DMG o CGB) siguiendo la Power Up Sequence de Pan Docs.
     * 
     * Llamado por:
     * - Constructor MMU() para valores iniciales
     * - set_hardware_mode() cuando se cambia el modo
     * - enable_bootrom_stub() para aplicar estado post-boot
     * 
     * Fuente: Pan Docs - Power Up Sequence
     */
    void initialize_io_registers();
    
    /**
     * Step 0491: Inicializa estado post-boot DMG según Pan Docs
     * 
     * Establece el estado conocido después del boot ROM DMG cuando
     * VIBOY_SIM_BOOT_LOGO=0. Esto asegura que el hardware esté en un
     * estado que permita al juego cargar gráficos correctamente.
     * 
     * Fuente: Pan Docs - Power Up Sequence
     */
    void init_post_boot_dmg_state();
    
    /**
     * Step 0419: Habilita/deshabilita escrituras directas en ROM para unit testing.
     * 
     * En modo normal, las escrituras a 0x0000-0x7FFF se interpretan como comandos
     * MBC (Memory Bank Controller) y no modifican la ROM. Este modo permite a los
     * tests unitarios escribir instrucciones directamente en la ROM para verificar
     * la emulación de la CPU.
     * 
     * ⚠️ SOLO para propósitos de testing. NO usar en emulación normal.
     * 
     * @param allow true para permitir escrituras en ROM, false para modo normal
     * 
     * Fuente: Patrón estándar de testing en emuladores
     */
    void set_test_mode_allow_rom_writes(bool allow);
    
    /**
     * Step 0450: Raw read for diagnostics (bypasses access restrictions).
     * 
     * WARNING: Only for diagnostics/tools, NOT for emulation.
     * This directly reads memory_[] without PPU mode checks, banking, etc.
     * 
     * @param addr Memory address (0x0000-0xFFFF)
     * @return Raw byte value from memory_[]
     */
    uint8_t read_raw(uint16_t addr) const;
    
    /**
     * Step 0458: Método rápido para lectura VRAM desde PPU.
     * 
     * Lee desde los bancos VRAM (vram_bank0_/vram_bank1_) sin restricciones
     * de modo PPU. El PPU necesita acceso directo a VRAM durante el renderizado.
     * 
     * @param addr Dirección VRAM (0x8000-0x9FFF)
     * @return Byte leído del banco VRAM correspondiente
     */
    inline uint8_t read_vram(uint16_t addr) const {
        // Valida 0x8000-0x9FFF
        if (addr < 0x8000 || addr > 0x9FFF) {
            return 0xFF;  // Fuera de rango
        }
        
        // Calcular offset dentro del bank
        uint16_t offset = addr - 0x8000;
        
        // Por defecto usar bank 0 (DMG siempre usa bank 0)
        // TODO: En CGB, el PPU puede necesitar leer de ambos bancos simultáneamente
        // (bank 0 para tile data, bank 1 para atributos)
        uint8_t bank = 0;  // Por defecto bank 0 (DMG)
        
        // Leer desde vram_bank0_ o vram_bank1_
        if (bank == 0) {
            if (offset < vram_bank0_.size()) {
                return vram_bank0_[offset];
            }
        } else if (bank == 1) {
            if (offset < vram_bank1_.size()) {
                return vram_bank1_[offset];
            }
        }
        
        return 0xFF;  // Fuera de rango del bank
    }
    
    /**
     * Step 0450: Dump raw memory range for fast sampling.
     * 
     * WARNING: Only for diagnostics, bypasses restrictions.
     * 
     * @param start Start address
     * @param length Number of bytes to dump
     * @param buffer Output buffer (must be at least 'length' bytes)
     */
    void dump_raw_range(uint16_t start, uint16_t length, uint8_t* buffer) const;

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
    
    // Step 0425: Eliminado test_mode_allow_rom_writes_ (hack no spec-correct)

    // Estado específico de MBC1
    uint8_t mbc1_bank_low5_;
    uint8_t mbc1_bank_high2_;
    uint8_t mbc1_mode_;           // 0 = ROM banking, 1 = RAM banking

    // --- Step 0409: Estado específico de MBC3 + RTC ---
    // Fuente: Pan Docs - MBC3, Real Time Clock
    uint8_t mbc3_rtc_reg_;        // Registro RTC seleccionado (0x08-0x0C)
    bool mbc3_latch_ready_;       // Flag de latch (0x00 → 0x01)
    uint8_t mbc3_latch_value_;    // Último valor escrito a 0x6000-0x7FFF
    
    // Registros RTC latched (capturados tras latch 0x00→0x01)
    // Marcados mutable porque son cache del tiempo real (pueden cambiar durante read())
    mutable uint8_t rtc_seconds_;         // 0x08: Segundos (0-59)
    mutable uint8_t rtc_minutes_;         // 0x09: Minutos (0-59)
    mutable uint8_t rtc_hours_;           // 0x0A: Horas (0-23)
    mutable uint8_t rtc_day_low_;         // 0x0B: Day counter bit 0-7
    mutable uint8_t rtc_day_high_;        // 0x0C: Day counter bit 8, Carry, Halt
                                          //       bit 0: Day bit 8
                                          //       bit 6: Halt (0=active, 1=halted)
                                          //       bit 7: Day Carry (overflow)
    
    // Timestamp de inicio (para calcular tiempo transcurrido)
    mutable std::chrono::steady_clock::time_point rtc_start_time_;

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
    
    // --- Step 0475: Boot Logo Prefill (Gated) ---
    void prefill_boot_logo_vram();
    void configure_mbc_from_header(uint8_t cart_type, uint8_t rom_size_code, uint8_t ram_size_code);
    void allocate_ram_from_header(uint8_t ram_size_code);
    
    // --- Step 0409: Helpers RTC (MBC3) ---
    void rtc_update() const;       // Actualiza registros RTC basado en tiempo transcurrido (const porque es cache)
    void rtc_latch();              // Captura snapshot de RTC (tras latch 0x00→0x01)
    
    // --- Step 0382: Contadores de diagnóstico para VRAM ---
    mutable int vram_write_total_step382_;
    mutable int vram_write_nonzero_step382_;
    
    // --- Step 0391: Contadores por regiones VRAM ---
    mutable int vram_tiledata_nonzero_writes_;  // 0x8000-0x97FF (tile patterns)
    mutable int vram_tilemap_nonzero_writes_;   // 0x9800-0x9FFF (tile maps)
    mutable int vram_region_summary_count_;     // Contador para resúmenes periódicos
    
    // --- Step 0410: Contadores de DMA/HDMA ---
    mutable int oam_dma_count_;                 // Contador de OAM DMA (0xFF46)
    mutable int hdma_start_count_;              // Contador de HDMA starts (0xFF55)
    mutable int hdma_bytes_transferred_;        // Total de bytes transferidos por HDMA
    mutable int vram_tiledata_cpu_writes_;      // Escrituras CPU a 0x8000-0x97FF
    mutable int vram_tiledata_cpu_nonzero_;     // Escrituras CPU no-cero a TileData
    mutable int vram_tiledata_cpu_log_count_;   // Contador de logs de TileData (primeras N)
    
    // --- Step 0414: Métricas de VRAM bloqueada por Mode 3 ---
    mutable int vram_tiledata_total_writes_;    // Total escrituras a TileData (0x8000-0x97FF)
    mutable int vram_tiledata_blocked_mode3_;   // Escrituras bloqueadas por Mode 3
    mutable int vram_tiledata_summary_frames_;  // Frames procesados para resumen periódico
    
    // --- Step 0411: Contadores de IRQ requests reales (independientes de cambios en IF) ---
    mutable int irq_req_vblank_count_;          // Total de requests VBlank (bit 0)
    mutable int irq_req_stat_count_;            // Total de requests STAT (bit 1)
    mutable int irq_req_timer_count_;           // Total de requests Timer (bit 2)
    mutable int irq_req_serial_count_;          // Total de requests Serial (bit 3)
    mutable int irq_req_joypad_count_;          // Total de requests Joypad (bit 4)
    mutable int irq_req_summary_count_;         // Contador de resúmenes periódicos (cada N frames)
    
    // --- Step 0412: Contadores de writes a paletas CGB ---
    mutable int palette_write_log_count_;       // Contador de logs de writes a paletas (primeras N)
    
    // --- Step 0385: Flags de trazado de wait-loop y VBlank ISR ---
    mutable bool waitloop_trace_active_;
    mutable bool vblank_isr_trace_active_;
    mutable int waitloop_mmio_count_;
    mutable int waitloop_ram_count_;
    
    // --- Step 0389: CGB VRAM Banking ---
    // CGB tiene 2 bancos de VRAM (8KB total = 2 x 4KB)
    // - VRAM Bank 0: 0x8000-0x9FFF (4KB) - Tiles + Tilemap
    // - VRAM Bank 1: 0x8000-0x9FFF (4KB) - Tiles alternos + Atributos de Tilemap
    // El registro VBK (0xFF4F) bit 0 selecciona qué banco ve la CPU.
    // El PPU puede acceder a ambos bancos simultáneamente durante el renderizado.
    //
    // Fuente: Pan Docs - CGB Registers, VRAM Banks
    std::vector<uint8_t> vram_bank0_;  // Banco 0 de VRAM (4KB)
    std::vector<uint8_t> vram_bank1_;  // Banco 1 de VRAM (4KB)
    uint8_t vram_bank_;                // Banco actual seleccionado por VBK (0 o 1)
    
    // --- Step 0390: CGB HDMA (0xFF51-0xFF55) ---
    // HDMA permite transferencia de datos desde ROM/RAM a VRAM sin intervención de CPU.
    // Modos: General DMA (inmediato) y HBlank DMA (incremental por línea).
    // Fuente: Pan Docs - CGB Registers, HDMA
    uint8_t hdma1_;                     // 0xFF51: HDMA Source High
    uint8_t hdma2_;                     // 0xFF52: HDMA Source Low
    uint8_t hdma3_;                     // 0xFF53: HDMA Destination High
    uint8_t hdma4_;                     // 0xFF54: HDMA Destination Low
    uint8_t hdma5_;                     // 0xFF55: HDMA Length/Mode/Start
    bool hdma_active_;                  // ¿HDMA en progreso?
    uint16_t hdma_length_remaining_;    // Bytes restantes por transferir
    
    // --- Step 0390: CGB Paletas BG/OBJ (0xFF68-0xFF6B) ---
    // CGB tiene 8 paletas BG y 8 paletas OBJ, cada una con 4 colores de 15 bits (BGR555).
    // Total: 64 bytes por tipo de paleta.
    // Fuente: Pan Docs - CGB Registers, Palettes
    uint8_t bg_palette_data_[0x40];     // 64 bytes: 8 paletas BG × 4 colores × 2 bytes
    uint8_t obj_palette_data_[0x40];    // 64 bytes: 8 paletas OBJ × 4 colores × 2 bytes
    uint8_t bg_palette_index_;          // 0xFF68 (BCPS): Índice actual (0-0x3F) + autoinc (bit 7)
    uint8_t obj_palette_index_;         // 0xFF6A (OCPS): Índice actual (0-0x3F) + autoinc (bit 7)
    
    // --- Step 0400: Tracking de secuencia de inicialización ---
    mutable uint8_t last_lcdc_value_;   // Último valor de LCDC
    mutable uint8_t last_bgp_value_;    // Último valor de BGP
    mutable uint8_t last_ie_value_;     // Último valor de IE
    mutable int lcdc_change_frame_;     // Frame donde cambió LCDC
    mutable int bgp_change_frame_;      // Frame donde cambió BGP
    mutable int ie_change_frame_;       // Frame donde cambió IE
    mutable bool init_sequence_logged_; // Flag para evitar logs repetidos
    
    // --- Step 0401: Boot ROM opcional ---
    std::vector<uint8_t> boot_rom_;     // Datos de la Boot ROM (256 bytes DMG o 2304 bytes CGB)
    bool boot_rom_enabled_;             // ¿Boot ROM habilitada? (se deshabilita al escribir FF50)
    
    // --- Step 0404: Modo de hardware (DMG vs CGB) ---
    HardwareMode hardware_mode_;        // Modo de hardware actual (DMG o CGB)
    
    // --- Step 0434: Triage instrumentado ---
    // Contadores y tracking para entender por qué VRAM está vacía
    struct TriageState {
        bool active;                     // ¿Triage activo?
        int vram_writes;                 // Writes a 0x8000-0x9FFF
        int oam_writes;                  // Writes a 0xFE00-0xFE9F
        int ff40_writes;                 // Writes a LCDC (0xFF40)
        int ff47_writes;                 // Writes a BGP (0xFF47)
        int ff50_writes;                 // Writes a BOOT (0xFF50)
        int ff04_writes;                 // Writes a DIV (0xFF04)
        int ff0f_writes;                 // Writes a IF (0xFF0F)
        int ffff_writes;                 // Writes a IE (0xFFFF)
        int mbc1_bank_writes;            // Writes a 0x2000-0x7FFF (banking MBC1)
        
        // Primeras 32 escrituras para análisis detallado
        struct WriteEvent {
            uint16_t pc;
            uint16_t addr;
            uint8_t val;
        };
        static constexpr int MAX_SAMPLES = 32;
        WriteEvent vram_samples[MAX_SAMPLES];
        WriteEvent io_samples[MAX_SAMPLES];
        WriteEvent mbc_samples[MAX_SAMPLES];
        int vram_sample_count;
        int io_sample_count;
        int mbc_sample_count;
        
        TriageState() : active(false), vram_writes(0), oam_writes(0),
                        ff40_writes(0), ff47_writes(0), ff50_writes(0),
                        ff04_writes(0), ff0f_writes(0), ffff_writes(0),
                        mbc1_bank_writes(0),
                        vram_sample_count(0), io_sample_count(0), mbc_sample_count(0) {
            for (int i = 0; i < MAX_SAMPLES; i++) {
                vram_samples[i] = {0, 0, 0};
                io_samples[i] = {0, 0, 0};
                mbc_samples[i] = {0, 0, 0};
            }
        }
    } triage_;
    
    // --- Step 0436: Pokemon Loop Trace (Fase A) ---
    // Ring buffer específico para writes VRAM cuando PC está en 0x36E2-0x36E7
    // Objetivo: determinar si HL progresa o está atascado
    struct PokemonLoopTrace {
        bool active;                     // ¿Tracing activo?
        static constexpr int RING_SIZE = 64;
        struct VRAMWrite {
            uint16_t pc;
            uint16_t addr;
            uint8_t val;
            uint16_t hl;                 // Valor de HL al momento del write
        };
        VRAMWrite ring_buffer[RING_SIZE];
        int ring_idx;                    // Índice circular
        int total_writes;                // Total de writes capturados
        uint16_t min_addr;               // Mínima dirección escrita
        uint16_t max_addr;               // Máxima dirección escrita
        int unique_addr_count;           // Número de direcciones únicas (bitset o estimación)
        uint8_t addr_bitset[8192 / 8];  // Bitset de 8KB VRAM (1KB = 1024 bits)
        
        PokemonLoopTrace() : active(false), ring_idx(0), total_writes(0),
                             min_addr(0xFFFF), max_addr(0x0000), unique_addr_count(0) {
            for (int i = 0; i < RING_SIZE; i++) {
                ring_buffer[i] = {0, 0, 0, 0};
            }
            for (int i = 0; i < (8192 / 8); i++) {
                addr_bitset[i] = 0;
            }
        }
    } pokemon_loop_trace_;
    
public:
    /**
     * Step 0389: Acceso directo a bancos VRAM para el PPU
     * 
     * El PPU necesita acceso a ambos bancos de VRAM para renderizar correctamente en modo CGB:
     * - VRAM Bank 0: Tile IDs y tile patterns
     * - VRAM Bank 1: Atributos de tiles (paleta, flips, banco de tile)
     * 
     * @param bank Número de banco (0 o 1)
     * @param offset Offset dentro del banco (0x0000-0x1FFF para 8KB)
     * @return Byte leído del banco VRAM
     */
    inline uint8_t read_vram_bank(uint8_t bank, uint16_t offset) const {
        if (bank == 0 && offset < vram_bank0_.size()) {
            return vram_bank0_[offset];
        } else if (bank == 1 && offset < vram_bank1_.size()) {
            return vram_bank1_[offset];
        }
        return 0xFF;  // Fuera de rango
    }
    
    /**
     * Step 0404: Acceso directo a paletas CGB para el PPU (sin efectos colaterales)
     * 
     * El PPU necesita leer las paletas BG y OBJ para renderizar en modo CGB sin
     * tocar los registros BCPS/OCPS (que tienen autoincremento). Esto permite
     * renderizado correcto sin afectar el índice de paleta de la CPU.
     * 
     * @param index Índice en el array de paleta (0x00-0x3F)
     * @return Byte de paleta (RGB555 low/high byte)
     * 
     * Fuente: Pan Docs - CGB Registers, Background Palettes (FF68-FF69), Object Palettes (FF6A-FF6B)
     */
    inline uint8_t read_bg_palette_data(uint8_t index) const {
        if (index < 0x40) {
            return bg_palette_data_[index];
        }
        return 0xFF;
    }
    
    inline uint8_t read_obj_palette_data(uint8_t index) const {
        if (index < 0x40) {
            return obj_palette_data_[index];
        }
        return 0xFF;
    }
    
    /**
     * Step 0434: Activa/desactiva triage mode.
     * @param active true para activar triage, false para desactivar
     */
    void set_triage_mode(bool active);
    
    /**
     * Step 0434: Registra PC actual para triage (llamado desde CPU).
     * @param pc Program counter actual
     */
    void set_triage_pc(uint16_t pc);
    
    /**
     * Step 0434: Genera resumen de triage (debe llamarse después de ejecutar).
     */
    void log_triage_summary();
    
    /**
     * Step 0436: Activa/desactiva Pokemon loop trace (Fase A del Step 0436).
     * Captura writes VRAM cuando PC está en 0x36E2-0x36E7 para determinar si HL progresa.
     * @param active true para activar, false para desactivar
     */
    void set_pokemon_loop_trace(bool active);
    
    /**
     * Step 0436: Genera resumen de Pokemon loop trace (Fase A).
     * Muestra: unique_addr_count, min/max addr, 5 ejemplos (pc,addr,val,hl)
     */
    void log_pokemon_loop_trace_summary();
    
    /**
     * Step 0436: Registra valor actual de HL (llamado desde CPU para captura completa).
     * @param hl_value Valor actual del registro HL
     */
    void set_current_hl(uint16_t hl_value);
    
private:
    // --- Step 0436: Valor temporal de HL para captura en writes VRAM ---
    uint16_t current_hl_value_;
    
    // --- Step 0450: MBC write counters for diagnostics ---
    mutable uint32_t mbc_write_count_;
    uint16_t mbc_write_addrs_[8];  // Ring buffer: últimos 8 addresses
    uint8_t mbc_write_vals_[8];     // Ring buffer: últimos 8 values
    uint16_t mbc_write_pcs_[8];     // Ring buffer: últimos 8 PCs
    int mbc_write_ring_idx_;
    
    // --- Step 0474: Instrumentación quirúrgica de IF (0xFF0F) ---
    mutable uint32_t if_write_count_;
    mutable uint32_t if_read_count_;
    mutable uint16_t last_if_write_pc_;
    mutable uint8_t last_if_write_val_;
    mutable uint32_t last_if_write_timestamp_;  // Step 0477
    mutable uint8_t last_if_read_val_;
    mutable uint32_t if_writes_0_;
    mutable uint32_t if_writes_nonzero_;
    
    // --- Step 0474: Instrumentación quirúrgica de LY (0xFF44) ---
    mutable uint8_t ly_read_min_;
    mutable uint8_t ly_read_max_;
    mutable uint8_t last_ly_read_;
    
    // --- Step 0474: Instrumentación quirúrgica de STAT (0xFF41) ---
    mutable uint8_t last_stat_read_;
    
    // --- Step 0475: Source Tagging para IO Polling ---
    mutable bool irq_poll_active_;  // Flag para distinguir polling interno vs lecturas del programa
    mutable uint32_t if_reads_program_;      // Lecturas de IF desde código del programa
    mutable uint32_t if_reads_cpu_poll_;     // Lecturas de IF desde polling interno de CPU
    mutable uint32_t if_writes_program_;     // Escrituras a IF desde código del programa
    mutable uint32_t ie_reads_program_;      // Lecturas de IE desde código del programa
    mutable uint32_t ie_reads_cpu_poll_;     // Lecturas de IE desde polling interno de CPU
    mutable uint32_t ie_writes_program_;     // Escrituras a IE desde código del programa
    
    // --- Step 0482: Contador de writes a IE (convertido de static a miembro de instancia) ---
    mutable uint32_t ie_write_count_;
    
    // --- Step 0475: Boot Logo Prefill Gated ---
    bool boot_logo_prefill_enabled_;  // Flag para indicar si el prefill del logo está habilitado
    
    // --- Step 0479: Instrumentación gated por I/O esperado ---
    uint16_t waits_on_addr_;          // I/O esperado (del parseo)
    mutable uint32_t waits_on_reads_program_;  // Contador de reads desde programa (no cpu_poll)
    mutable uint8_t last_waits_on_read_value_; // Último valor leído del I/O esperado
    mutable uint16_t last_waits_on_read_pc_;   // Último PC que leyó el I/O esperado
    
    // --- Step 0479: Instrumentación específica LY/STAT/IF ---
    mutable uint32_t ly_changes_this_frame_;      // Contador de cambios de LY por frame
    mutable uint32_t stat_mode_changes_count_;    // Contador de cambios de modo STAT por frame
    mutable uint32_t if_bit0_set_count_this_frame_; // Contador de veces que IF bit0 se pone a 1 por frame
    
    // --- Step 0480: Instrumentación HRAM[FF92] quirúrgica (gated por VIBOY_DEBUG_IO) ---
    mutable uint32_t hram_ff92_write_count_;
    mutable uint16_t last_hram_ff92_write_pc_;
    mutable uint8_t last_hram_ff92_write_value_;
    mutable uint32_t last_hram_ff92_write_timestamp_;
    mutable uint32_t hram_ff92_read_count_program_;
    mutable uint16_t last_hram_ff92_read_pc_;
    mutable uint8_t last_hram_ff92_read_value_;
    
    // --- Step 0486: HRAM FF92 Watch (gated por VIBOY_DEBUG_MARIO_FF92=1) ---
    struct HRAMFF92Watch {
        uint16_t last_write_pc;
        uint8_t last_write_val;
        uint16_t last_read_pc;
        uint8_t last_read_val;
        uint8_t readback_after_write_val;  // Leer inmediatamente tras write SOLO como diagnóstico
        uint32_t write_readback_mismatch_count;
        
        HRAMFF92Watch() : last_write_pc(0xFFFF), last_write_val(0), last_read_pc(0xFFFF),
                         last_read_val(0), readback_after_write_val(0), write_readback_mismatch_count(0) {}
    };
    mutable HRAMFF92Watch hram_ff92_watch_;
    
    // --- Step 0487: HRAM FF92 Single Source of Truth (contadores cumulativos, nunca se resetean) ---
    struct HRAMFF92SingleSource {
        uint32_t ff92_write_count_total;      // Cumulativo, nunca se resetea
        uint16_t ff92_last_write_pc;
        uint8_t ff92_last_write_val;
        uint32_t ff92_read_count_total;       // Cumulativo, nunca se resetea
        uint16_t ff92_last_read_pc;
        uint8_t ff92_last_read_val;
        
        HRAMFF92SingleSource() : ff92_write_count_total(0), ff92_last_write_pc(0xFFFF),
                                ff92_last_write_val(0), ff92_read_count_total(0),
                                ff92_last_read_pc(0xFFFF), ff92_last_read_val(0) {}
    };
    mutable HRAMFF92SingleSource hram_ff92_single_source_;
    
    // --- Step 0487: Tracking de resets no deseados ---
    mutable uint32_t ff92_watch_reset_count_;
    mutable uint16_t ff92_watch_reset_last_pc_;
    
    // --- Step 0487: IE Write Tracking (gated por VIBOY_DEBUG_MARIO_FF92=1) ---
    mutable uint8_t ie_value_after_write_;
    mutable uint16_t ie_last_write_pc_;
    mutable uint32_t ie_write_count_total_;
    
    // --- Step 0486: FF92 to IE Trace (gated por VIBOY_DEBUG_MARIO_FF92=1) ---
    // Estructura movida a public para acceso desde getters
    mutable std::vector<FF92ToIETrace> ff92_to_ie_trace_;
    static constexpr size_t FF92_TO_IE_TRACE_SIZE = 16;
    
    // --- Step 0481: HRAM Watchlist Genérica ---
    // Estructura para tracking quirúrgico de direcciones HRAM
    struct HRAMWatchEntry {
        uint16_t addr;
        uint32_t write_count;
        uint32_t read_count_program;
        uint16_t last_write_pc;
        uint8_t last_write_value;
        uint32_t last_write_timestamp;
        uint32_t last_write_frame;  // Step 0483: Frame de la última escritura
        uint16_t first_write_pc;
        uint8_t first_write_value;
        uint32_t first_write_timestamp;
        uint32_t first_write_frame;
        uint16_t last_read_pc;
        uint8_t last_read_value;
        bool first_write_recorded;
        
        HRAMWatchEntry() : addr(0), write_count(0), read_count_program(0),
                          last_write_pc(0), last_write_value(0), last_write_timestamp(0),
                          last_write_frame(0),  // Step 0483
                          first_write_pc(0), first_write_value(0), first_write_timestamp(0),
                          first_write_frame(0), last_read_pc(0), last_read_value(0),
                          first_write_recorded(false) {}
    };
    mutable std::vector<HRAMWatchEntry> hram_watchlist_;
    
    // --- Step 0482: LCDC Disable Tracking ---
    mutable uint32_t lcdc_disable_events_;  // Contador de eventos de disable (1→0)
    mutable uint16_t last_lcdc_write_pc_;  // PC de la última escritura a LCDC
    mutable uint8_t last_lcdc_write_value_;  // Valor de la última escritura a LCDC
    
    // --- Step 0484: JOYP Write Distribution ---
    mutable std::map<uint8_t, uint32_t> joyp_write_distribution_;  // valor → count
    mutable std::map<uint8_t, std::vector<uint16_t>> joyp_write_pcs_by_value_;  // valor → lista de PCs
    
    // --- Step 0484: JOYP Read Select Bits Tracking ---
    mutable uint8_t joyp_last_read_select_bits_;  // bits 4-5 del latch
    mutable uint8_t joyp_last_read_low_nibble_;  // bits 0-3 leídos
    
    // --- Step 0485: JOYP Access Trace Ring-Buffer (gated por VIBOY_DEBUG_JOYP_TRACE=1) ---
    // JOYPTraceEvent está definida fuera de la clase (arriba) para acceso desde Cython
    mutable std::vector<JOYPTraceEvent> joyp_trace_;
    static constexpr size_t JOYP_TRACE_SIZE = 256;
    
    // --- Step 0485: Contadores por tipo de selección JOYP ---
    mutable uint32_t joyp_reads_with_buttons_selected_count_;  // select buttons bit=0
    mutable uint32_t joyp_reads_with_dpad_selected_count_;     // select dpad bit=0
    mutable uint32_t joyp_reads_with_none_selected_count_;     // 0x30 (ninguno seleccionado)
    
    // --- Step 0487: Contadores JOYP por tipo de selección (writes y reads) ---
    mutable uint32_t joyp_write_buttons_selected_total_;
    mutable uint32_t joyp_write_dpad_selected_total_;
    mutable uint32_t joyp_write_none_selected_total_;
    mutable uint32_t joyp_read_buttons_selected_total_prog_;
    mutable uint32_t joyp_read_dpad_selected_total_prog_;
    mutable uint32_t joyp_read_none_selected_total_prog_;
    mutable uint32_t joyp_read_buttons_selected_total_cpu_poll_;
    mutable uint32_t joyp_read_dpad_selected_total_cpu_poll_;
    mutable uint32_t joyp_read_none_selected_total_cpu_poll_;
    
    // --- Step 0489: Instrumentación de writes a paletas CGB ---
    CGBPaletteWriteStats cgb_palette_write_stats_;
    
    // --- Step 0490: Instrumentación de writes a VRAM ---
    // Step 0491: mutable para permitir actualización desde métodos const (si es necesario)
    mutable VRAMWriteStats vram_write_stats_;
    
    // --- Step 0486: Contadores JOYP por source y selección ---
    mutable uint32_t joyp_reads_prog_buttons_sel_;   // Program reads con buttons selected (bit4=0)
    mutable uint32_t joyp_reads_prog_dpad_sel_;      // Program reads con dpad selected (bit5=0)
    mutable uint32_t joyp_reads_prog_none_sel_;      // Program reads con none selected (bits 4-5 = 11)
    mutable uint32_t joyp_reads_cpu_poll_buttons_sel_;  // CPU polling reads con buttons selected
    mutable uint32_t joyp_reads_cpu_poll_dpad_sel_;     // CPU polling reads con dpad selected
    mutable uint32_t joyp_reads_cpu_poll_none_sel_;     // CPU polling reads con none selected
    
public:
    /**
     * Step 0450: Log summary of MBC writes (debug-gated).
     * 
     * Muestra contadores y últimos 8 writes a rangos MBC (0x0000-0x7FFF).
     */
    void log_mbc_writes_summary() const;
    
    /**
     * Step 0470: Obtiene el contador de writes a IE (0xFFFF).
     * 
     * @return Número de veces que se ha escrito a IE
     */
    uint32_t get_ie_write_count() const;
    
    /**
     * Step 0470: Obtiene el contador de writes a IF (0xFF0F).
     * 
     * @return Número de veces que se ha escrito a IF
     */
    uint32_t get_if_write_count() const;
    
    /**
     * Step 0470: Obtiene el último valor escrito a IE (0xFFFF).
     * 
     * @return Último valor escrito a IE
     */
    uint8_t get_last_ie_written() const;
    
    /**
     * Step 0470: Obtiene el último valor escrito a IF (0xFF0F).
     * 
     * @return Último valor escrito a IF
     */
    uint8_t get_last_if_written() const;
    
    /**
     * Step 0470: Obtiene el contador de lecturas de una dirección IO específica.
     * 
     * @param addr Dirección IO (0xFF00, 0xFF41, 0xFF44, 0xFF0F, 0xFFFF, 0xFF4D, 0xFF4F, 0xFF70)
     * @return Número de veces que se ha leído esa dirección
     */
    uint32_t get_io_read_count(uint16_t addr) const;
    
    /**
     * Step 0471: Obtiene el último valor escrito a IE (0xFFFF).
     * 
     * @return Último valor escrito a IE
     */
    uint8_t get_last_ie_write_value() const;
    
    /**
     * Step 0471: Obtiene el PC del último write a IE (0xFFFF).
     * 
     * @return PC del último write a IE
     */
    uint16_t get_last_ie_write_pc() const;
    
    /**
     * Step 0477: Obtiene el timestamp del último write a IE (0xFFFF).
     * 
     * @return Timestamp del último write a IE
     */
    uint32_t get_last_ie_write_timestamp() const;
    
    /**
     * Step 0471: Obtiene el último valor leído de IE (0xFFFF).
     * 
     * @return Último valor leído de IE
     */
    uint8_t get_last_ie_read_value() const;
    
    /**
     * Step 0471: Obtiene el contador de lecturas de IE (0xFFFF).
     * 
     * @return Número de veces que se ha leído IE
     */
    uint32_t get_ie_read_count() const;
    
    /**
     * Step 0472: Obtiene el contador de writes a KEY1 (0xFF4D).
     * 
     * @return Número de veces que se ha escrito a KEY1
     */
    uint32_t get_key1_write_count() const;
    
    /**
     * Step 0472: Obtiene el último valor escrito a KEY1 (0xFF4D).
     * 
     * @return Último valor escrito a KEY1
     */
    uint8_t get_last_key1_write_value() const;
    
    /**
     * Step 0472: Obtiene el PC del último write a KEY1 (0xFF4D).
     * 
     * @return PC del último write a KEY1
     */
    uint16_t get_last_key1_write_pc() const;
    
    /**
     * Step 0472: Obtiene el contador de writes a JOYP (0xFF00).
     * 
     * @return Número de veces que se ha escrito a JOYP
     */
    uint32_t get_joyp_write_count() const;
    
    /**
     * Step 0472: Obtiene el último valor escrito a JOYP (0xFF00).
     * 
     * @return Último valor escrito a JOYP
     */
    uint8_t get_last_joyp_write_value() const;
    
    /**
     * Step 0472: Obtiene el PC del último write a JOYP (0xFF00).
     * 
     * @return PC del último write a JOYP
     */
    uint16_t get_last_joyp_write_pc() const;
    
    /**
     * Step 0481: Obtiene el contador de reads de JOYP desde programa.
     * 
     * @return Número de reads de JOYP desde código del programa
     */
    uint32_t get_joyp_read_count_program() const;
    
    /**
     * Step 0481: Obtiene el PC del último read de JOYP.
     * 
     * @return PC del último read de JOYP
     */
    uint16_t get_last_joyp_read_pc() const;
    
    /**
     * Step 0481: Obtiene el último valor leído de JOYP.
     * 
     * @return Último valor leído de JOYP
     */
    uint8_t get_last_joyp_read_value() const;
    
    /**
     * Step 0482: Obtiene el contador de eventos de disable de LCDC (1→0).
     * 
     * @return Número de veces que LCDC bit7 pasó de 1 a 0
     */
    uint32_t get_lcdc_disable_events() const;
    
    /**
     * Step 0482: Obtiene el PC de la última escritura a LCDC.
     * 
     * @return PC de la última escritura a LCDC (0xFFFF si ninguna)
     */
    uint16_t get_last_lcdc_write_pc() const;
    
    /**
     * Step 0482: Obtiene el valor de la última escritura a LCDC.
     * 
     * @return Valor de la última escritura a LCDC
     */
    uint8_t get_last_lcdc_write_value() const;
    
    /**
     * Step 0474: Obtiene el contador de lecturas de IF (0xFF0F).
     * 
     * @return Número de veces que se ha leído IF
     */
    uint32_t get_if_read_count() const;
    
    /**
     * Step 0474: Obtiene el PC del último write a IF (0xFF0F).
     * 
     * @return PC del último write a IF
     */
    uint16_t get_last_if_write_pc() const;
    
    /**
     * Step 0474: Obtiene el último valor escrito a IF (0xFF0F).
     * 
     * @return Último valor escrito a IF
     */
    uint8_t get_last_if_write_val() const;
    
    /**
     * Step 0477: Obtiene el timestamp del último write a IF (0xFF0F).
     * 
     * @return Timestamp del último write a IF
     */
    uint32_t get_last_if_write_timestamp() const;
    
    /**
     * Step 0474: Obtiene el último valor leído de IF (0xFF0F).
     * 
     * @return Último valor leído de IF
     */
    uint8_t get_last_if_read_val() const;
    
    /**
     * Step 0474: Obtiene el contador de writes a IF con valor 0.
     * 
     * @return Número de writes a IF con valor 0
     */
    uint32_t get_if_writes_0() const;
    
    /**
     * Step 0474: Obtiene el contador de writes a IF con valor no-cero.
     * 
     * @return Número de writes a IF con valor no-cero
     */
    uint32_t get_if_writes_nonzero() const;
    
    /**
     * Step 0474: Obtiene el valor mínimo de LY leído.
     * 
     * @return Valor mínimo de LY leído
     */
    uint8_t get_ly_read_min() const;
    
    /**
     * Step 0474: Obtiene el valor máximo de LY leído.
     * 
     * @return Valor máximo de LY leído
     */
    uint8_t get_ly_read_max() const;
    
    /**
     * Step 0474: Obtiene el último valor leído de LY (0xFF44).
     * 
     * @return Último valor leído de LY
     */
    uint8_t get_last_ly_read() const;
    
    /**
     * Step 0474: Obtiene el último valor leído de STAT (0xFF41).
     * 
     * @return Último valor leído de STAT
     */
    uint8_t get_last_stat_read() const;
    
    /**
     * Step 0475: Establece el flag de polling de IRQ activo.
     * 
     * Este método permite a la CPU marcar cuando está ejecutando
     * polling interno de interrupciones, permitiendo distinguir
     * lecturas de IO desde código del programa vs polling interno.
     * 
     * @param active true si estamos en polling interno, false si no
     */
    void set_irq_poll_active(bool active);
    
    /**
     * Step 0475: Obtiene el contador de lecturas de IF desde código del programa.
     * 
     * @return Número de lecturas de IF desde código del programa
     */
    uint32_t get_if_reads_program() const;
    
    /**
     * Step 0475: Obtiene el contador de lecturas de IF desde polling interno de CPU.
     * 
     * @return Número de lecturas de IF desde polling interno
     */
    uint32_t get_if_reads_cpu_poll() const;
    
    /**
     * Step 0475: Obtiene el contador de escrituras a IF desde código del programa.
     * 
     * @return Número de escrituras a IF desde código del programa
     */
    uint32_t get_if_writes_program() const;
    
    /**
     * Step 0475: Obtiene el contador de lecturas de IE desde código del programa.
     * 
     * @return Número de lecturas de IE desde código del programa
     */
    uint32_t get_ie_reads_program() const;
    
    /**
     * Step 0475: Obtiene el contador de lecturas de IE desde polling interno de CPU.
     * 
     * @return Número de lecturas de IE desde polling interno
     */
    uint32_t get_ie_reads_cpu_poll() const;
    
    /**
     * Step 0475: Obtiene el contador de escrituras a IE desde código del programa.
     * 
     * @return Número de escrituras a IE desde código del programa
     */
    uint32_t get_ie_writes_program() const;
    
    /**
     * Step 0475: Obtiene el estado del prefill del logo de boot.
     * 
     * @return 1 si el prefill del logo está habilitado, 0 en caso contrario
     *         (devuelve int para evitar problemas de conversión en Cython)
     */
    int get_boot_logo_prefill_enabled() const;
    
    /**
     * Step 0479: Configura el I/O esperado para instrumentación gated.
     * 
     * @param addr Dirección I/O esperada (0xFF44, 0xFF41, etc.)
     */
    void set_waits_on_addr(uint16_t addr);
    
    /**
     * Step 0479: Obtiene el contador de cambios de LY por frame.
     * 
     * @return Número de cambios de LY en el frame actual
     */
    uint32_t get_ly_changes_this_frame() const;
    
    /**
     * Step 0479: Obtiene el contador de cambios de modo STAT por frame.
     * 
     * @return Número de cambios de modo STAT en el frame actual
     */
    uint32_t get_stat_mode_changes_count() const;
    
    /**
     * Step 0479: Obtiene el contador de veces que IF bit0 se pone a 1 por frame.
     * 
     * @return Número de veces que IF bit0 se activó en el frame actual
     */
    uint32_t get_if_bit0_set_count_this_frame() const;
    
    /**
     * Step 0480: Obtiene el contador de writes a HRAM[FF92].
     * 
     * @return Número de veces que se ha escrito a HRAM[FF92]
     */
    uint32_t get_hram_ff92_write_count() const;
    
    /**
     * Step 0480: Obtiene el PC del último write a HRAM[FF92].
     * 
     * @return PC del último write a HRAM[FF92]
     */
    uint16_t get_last_hram_ff92_write_pc() const;
    
    /**
     * Step 0480: Obtiene el último valor escrito a HRAM[FF92].
     * 
     * @return Último valor escrito a HRAM[FF92]
     */
    uint8_t get_last_hram_ff92_write_value() const;
    
    /**
     * Step 0480: Obtiene el timestamp del último write a HRAM[FF92].
     * 
     * @return Timestamp del último write a HRAM[FF92]
     */
    uint32_t get_last_hram_ff92_write_timestamp() const;
    
    /**
     * Step 0480: Obtiene el contador de reads de HRAM[FF92] desde programa.
     * 
     * @return Número de lecturas de HRAM[FF92] desde código del programa
     */
    uint32_t get_hram_ff92_read_count_program() const;
    
    /**
     * Step 0480: Obtiene el PC del último read de HRAM[FF92].
     * 
     * @return PC del último read de HRAM[FF92]
     */
    uint16_t get_last_hram_ff92_read_pc() const;
    
    /**
     * Step 0480: Obtiene el último valor leído de HRAM[FF92].
     * 
     * @return Último valor leído de HRAM[FF92]
     */
    uint8_t get_last_hram_ff92_read_value() const;
    
    /**
     * Step 0486: Obtiene el PC del último write a HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return PC del último write a HRAM[FF92] (0xFFFF si ninguno)
     */
    uint16_t get_hram_ff92_last_write_pc() const;
    
    /**
     * Step 0486: Obtiene el último valor escrito a HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Último valor escrito a HRAM[FF92]
     */
    uint8_t get_hram_ff92_last_write_val() const;
    
    /**
     * Step 0486: Obtiene el PC del último read de HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return PC del último read de HRAM[FF92] (0xFFFF si ninguno)
     */
    uint16_t get_hram_ff92_last_read_pc() const;
    
    /**
     * Step 0486: Obtiene el último valor leído de HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Último valor leído de HRAM[FF92]
     */
    uint8_t get_hram_ff92_last_read_val() const;
    
    /**
     * Step 0486: Obtiene el valor leído inmediatamente después del último write a HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Valor leído después del write (solo diagnóstico)
     */
    uint8_t get_hram_ff92_readback_after_write_val() const;
    
    /**
     * Step 0486: Obtiene el contador de discrepancias write-readback en HRAM[FF92].
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Número de veces que readback != write_val
     */
    uint32_t get_hram_ff92_write_readback_mismatch_count() const;
    
    /**
     * Step 0487: Obtiene el contador total de writes a FF92 (cumulativo, nunca se resetea).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Número total de writes a FF92
     */
    uint32_t get_ff92_write_count_total() const;
    
    /**
     * Step 0487: Obtiene el PC del último write a FF92.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return PC del último write a FF92 (0xFFFF si ninguno)
     */
    uint16_t get_ff92_last_write_pc() const;
    
    /**
     * Step 0487: Obtiene el último valor escrito a FF92.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Último valor escrito a FF92
     */
    uint8_t get_ff92_last_write_val() const;
    
    /**
     * Step 0487: Obtiene el contador total de reads de FF92 (cumulativo, nunca se resetea).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Número total de reads de FF92
     */
    uint32_t get_ff92_read_count_total() const;
    
    /**
     * Step 0487: Obtiene el PC del último read de FF92.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return PC del último read de FF92 (0xFFFF si ninguno)
     */
    uint16_t get_ff92_last_read_pc() const;
    
    /**
     * Step 0487: Obtiene el último valor leído de FF92.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Último valor leído de FF92
     */
    uint8_t get_ff92_last_read_val() const;
    
    /**
     * Step 0487: Obtiene el valor de IE después del último write.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Valor de IE después del último write
     */
    uint8_t get_ie_value_after_write() const;
    
    /**
     * Step 0487: Obtiene el PC del último write a IE.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return PC del último write a IE (0xFFFF si ninguno)
     */
    uint16_t get_ie_last_write_pc() const;
    
    /**
     * Step 0487: Obtiene el contador total de writes a IE (cumulativo).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Número total de writes a IE
     */
    uint32_t get_ie_write_count_total() const;
    
    /**
     * Step 0486: Obtiene el trace completo de FF92→IE (últimos 16 eventos).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_MARIO_FF92=1
     * 
     * @return Vector de eventos del trace
     */
    std::vector<FF92ToIETrace> get_ff92_to_ie_trace() const;
    
    /**
     * Step 0481: Añade una dirección HRAM a la watchlist para tracking.
     * 
     * @param addr Dirección HRAM (0xFF80-0xFFFE)
     */
    void add_hram_watch(uint16_t addr);
    
    /**
     * Step 0481: Obtiene el contador de writes a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Número de writes, o 0 si no está en watchlist
     */
    uint32_t get_hram_write_count(uint16_t addr) const;
    
    /**
     * Step 0481: Obtiene el PC del último write a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return PC del último write, o 0 si no está en watchlist
     */
    uint16_t get_hram_last_write_pc(uint16_t addr) const;
    
    /**
     * Step 0481: Obtiene el último valor escrito a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Último valor escrito, o 0 si no está en watchlist
     */
    uint8_t get_hram_last_write_value(uint16_t addr) const;
    
    /**
     * Step 0481: Obtiene el frame de la primera escritura a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Frame de la primera escritura, o 0 si no se ha escrito
     */
    uint32_t get_hram_first_write_frame(uint16_t addr) const;
    
    /**
     * Step 0481: Obtiene el contador de reads desde programa a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Número de reads desde programa, o 0 si no está en watchlist
     */
    uint32_t get_hram_read_count_program(uint16_t addr) const;
    
    /**
     * Step 0483: Obtiene el frame de la última escritura a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Frame de la última escritura, o 0 si no se ha escrito
     */
    uint32_t get_hram_last_write_frame(uint16_t addr) const;
    
    /**
     * Step 0483: Obtiene el PC del último read a una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return PC del último read, o 0xFFFF si no está en watchlist
     */
    uint16_t get_hram_last_read_pc(uint16_t addr) const;
    
    /**
     * Step 0483: Obtiene el último valor leído de una dirección HRAM en watchlist.
     * 
     * @param addr Dirección HRAM
     * @return Último valor leído, o 0 si no está en watchlist
     */
    uint8_t get_hram_last_read_value(uint16_t addr) const;
    
    /**
     * Step 0484: Obtiene el valor actual de LCDC (0xFF40).
     * 
     * @return Valor actual de LCDC
     */
    uint8_t get_lcdc_current() const;
    
    /**
     * Step 0484: Obtiene el top 5 de valores JOYP escritos (histograma).
     * 
     * @return Vector de pares (valor, count) ordenados por count descendente (top 5)
     */
    std::vector<std::pair<uint8_t, uint32_t>> get_joyp_write_distribution_top5() const;
    
    /**
     * Step 0484: Obtiene la lista de PCs donde se escribió un valor JOYP específico.
     * 
     * @param value Valor JOYP
     * @return Vector de PCs (máximo 10)
     */
    std::vector<uint16_t> get_joyp_write_pcs_by_value(uint8_t value) const;
    
    /**
     * Step 0484: Obtiene los bits de selección (4-5) del último read de JOYP.
     * 
     * @return Bits 4-5 del latch en el momento de la lectura
     */
    uint8_t get_joyp_last_read_select_bits() const;
    
    /**
     * Step 0484: Obtiene el low nibble (bits 0-3) del último read de JOYP.
     * 
     * @return Bits 0-3 leídos
     */
    uint8_t get_joyp_last_read_low_nibble() const;
    
    /**
     * Step 0485: Obtiene el trace completo de JOYP (últimos 256 eventos).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Vector de eventos del trace
     */
    std::vector<JOYPTraceEvent> get_joyp_trace() const;
    
    /**
     * Step 0485: Obtiene los últimos N eventos del trace de JOYP.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @param n Número de eventos a retornar
     * @return Vector de los últimos N eventos
     */
    std::vector<JOYPTraceEvent> get_joyp_trace_tail(size_t n) const;
    
    /**
     * Step 0485: Obtiene el contador de reads de JOYP con botones seleccionados.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads con botones seleccionados (P14=0)
     */
    uint32_t get_joyp_reads_with_buttons_selected_count() const;
    
    /**
     * Step 0485: Obtiene el contador de reads de JOYP con dpad seleccionado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads con dpad seleccionado (P15=0)
     */
    uint32_t get_joyp_reads_with_dpad_selected_count() const;
    
    /**
     * Step 0485: Obtiene el contador de reads de JOYP sin selección (0x30).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads sin selección (0x30)
     */
    uint32_t get_joyp_reads_with_none_selected_count() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde programa con botones seleccionados.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa con botones seleccionados (P14=0)
     */
    uint32_t get_joyp_reads_prog_buttons_sel() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde programa con dpad seleccionado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa con dpad seleccionado (P15=0)
     */
    uint32_t get_joyp_reads_prog_dpad_sel() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde programa sin selección (0x30).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa sin selección (0x30)
     */
    uint32_t get_joyp_reads_prog_none_sel() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde CPU polling con botones seleccionados.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling con botones seleccionados (P14=0)
     */
    uint32_t get_joyp_reads_cpu_poll_buttons_sel() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde CPU polling con dpad seleccionado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling con dpad seleccionado (P15=0)
     */
    uint32_t get_joyp_reads_cpu_poll_dpad_sel() const;
    
    /**
     * Step 0486: Obtiene el contador de reads de JOYP desde CPU polling sin selección (0x30).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling sin selección (0x30)
     */
    uint32_t get_joyp_reads_cpu_poll_none_sel() const;
    
    /**
     * Step 0487: Obtiene el contador de writes a JOYP con buttons selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de writes con buttons selected
     */
    uint32_t get_joyp_write_buttons_selected_total() const;
    
    /**
     * Step 0487: Obtiene el contador de writes a JOYP con dpad selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de writes con dpad selected
     */
    uint32_t get_joyp_write_dpad_selected_total() const;
    
    /**
     * Step 0487: Obtiene el contador de writes a JOYP con none selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de writes con none selected
     */
    uint32_t get_joyp_write_none_selected_total() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde programa con buttons selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa con buttons selected
     */
    uint32_t get_joyp_read_buttons_selected_total_prog() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde programa con dpad selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa con dpad selected
     */
    uint32_t get_joyp_read_dpad_selected_total_prog() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde programa con none selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde programa con none selected
     */
    uint32_t get_joyp_read_none_selected_total_prog() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con buttons selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling con buttons selected
     */
    uint32_t get_joyp_read_buttons_selected_total_cpu_poll() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con dpad selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling con dpad selected
     */
    uint32_t get_joyp_read_dpad_selected_total_cpu_poll() const;
    
    /**
     * Step 0487: Obtiene el contador de reads de JOYP desde CPU polling con none selected.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_JOYP_TRACE=1
     * 
     * @return Número de reads desde CPU polling con none selected
     */
    uint32_t get_joyp_read_none_selected_total_cpu_poll() const;
    
    /**
     * Step 0489: Obtiene estadísticas de writes a paletas CGB.
     * 
     * Devuelve métricas sobre escrituras a BGPI/BGPD y OBPI/OBPD.
     * 
     * @return Referencia constante a CGBPaletteWriteStats con las estadísticas
     */
    const CGBPaletteWriteStats& get_cgb_palette_write_stats() const;
    
    /**
     * Step 0490: Obtiene estadísticas de writes a VRAM.
     * 
     * Devuelve métricas sobre intentos de escritura a VRAM y bloqueos por Mode 3.
     * 
     * @return Referencia constante a VRAMWriteStats con las estadísticas
     */
    const VRAMWriteStats& get_vram_write_stats() const;
};

#endif // MMU_HPP

