#ifndef PPU_HPP
#define PPU_HPP

#include <cstdint>

// Forward declaration (evitar includes circulares)
class MMU;

/**
 * PPU (Pixel Processing Unit) - Unidad de Procesamiento de Píxeles
 * 
 * Esta clase implementa el motor de timing y estado de la PPU de la Game Boy.
 * En esta primera fase, solo gestiona:
 * - Estado de líneas (LY) y modos PPU (0-3)
 * - Timing de scanlines (456 T-Cycles por línea)
 * - Interrupciones V-Blank y STAT
 * 
 * El renderizado de píxeles se implementará en una fase posterior.
 * 
 * Fuente: Pan Docs - LCD Timing, V-Blank, STAT Register
 */
class PPU {
public:
    /**
     * Constantes de timing de la PPU
     * Fuente: Pan Docs - LCD Timing
     */
    static constexpr uint16_t CYCLES_PER_SCANLINE = 456;  // T-Cycles por línea
    static constexpr uint8_t VISIBLE_LINES = 144;          // Líneas visibles (0-143)
    static constexpr uint8_t VBLANK_START = 144;           // Inicio de V-Blank
    static constexpr uint8_t TOTAL_LINES = 154;            // Total de líneas por frame
    
    /**
     * Constantes de Modos PPU
     * Fuente: Pan Docs - LCD Status Register (STAT)
     */
    static constexpr uint8_t MODE_0_HBLANK = 0;           // H-Blank
    static constexpr uint8_t MODE_1_VBLANK = 1;           // V-Blank
    static constexpr uint8_t MODE_2_OAM_SEARCH = 2;       // OAM Search
    static constexpr uint8_t MODE_3_PIXEL_TRANSFER = 3;   // Pixel Transfer
    
    /**
     * Timing de modos dentro de una línea visible (en T-Cycles)
     */
    static constexpr uint16_t MODE_2_CYCLES = 80;    // OAM Search: 0-79
    static constexpr uint16_t MODE_3_CYCLES = 172;   // Pixel Transfer: 80-251
    static constexpr uint16_t MODE_0_CYCLES = 204;   // H-Blank: 252-455
    
    /**
     * Direcciones de registros I/O
     */
    static constexpr uint16_t IO_LCDC = 0xFF40;  // LCD Control (bit 7 = LCD enabled)
    static constexpr uint16_t IO_STAT = 0xFF41;  // LCD Status
    static constexpr uint16_t IO_LYC = 0xFF45;   // LY Compare
    static constexpr uint16_t IO_IF = 0xFF0F;    // Interrupt Flag
    
    /**
     * Constructor: Inicializa la PPU con un puntero a la MMU.
     * 
     * La PPU necesita acceso a la MMU para:
     * - Leer configuración del LCD (LCDC, STAT)
     * - Solicitar interrupciones (escribir en IF)
     * 
     * @param mmu Puntero a la MMU (no debe ser nullptr)
     */
    PPU(MMU* mmu);
    
    /**
     * Destructor.
     */
    ~PPU();
    
    /**
     * Avanza el motor de timing de la PPU según los ciclos de reloj consumidos.
     * 
     * Este método debe llamarse después de cada instrucción de la CPU, pasando
     * los T-Cycles (ciclos de reloj) consumidos. La PPU acumula estos ciclos
     * y avanza las líneas de escaneo cuando corresponde.
     * 
     * CRÍTICO: La PPU solo avanza cuando el LCD está encendido (LCDC bit 7 = 1).
     * 
     * @param cpu_cycles Número de T-Cycles (ciclos de reloj) a procesar
     */
    void step(int cpu_cycles);
    
    /**
     * Obtiene el valor actual del registro LY (Línea actual).
     * 
     * @return Valor de LY (0-153)
     */
    uint8_t get_ly() const;
    
    /**
     * Obtiene el modo PPU actual (0, 1, 2 o 3).
     * 
     * @return Modo PPU actual
     */
    uint8_t get_mode() const;
    
    /**
     * Obtiene el valor actual del registro LYC (LY Compare).
     * 
     * @return Valor de LYC (0-255)
     */
    uint8_t get_lyc() const;
    
    /**
     * Establece el valor del registro LYC (LY Compare).
     * 
     * Cuando LYC cambia, se verifica inmediatamente si LY == LYC para
     * actualizar el bit 2 de STAT y solicitar interrupción si corresponde.
     * 
     * @param value Valor a escribir en LYC (se enmascara a 8 bits)
     */
    void set_lyc(uint8_t value);
    
    /**
     * Comprueba si hay un frame listo para renderizar y resetea el flag.
     * 
     * Este método permite desacoplar el renderizado de las interrupciones.
     * 
     * @return true si hay un frame listo para renderizar, false en caso contrario
     */
    bool is_frame_ready();

private:
    /**
     * Puntero a la MMU (inyección de dependencias).
     */
    MMU* mmu_;
    
    /**
     * LY (Línea actual): Registro de solo lectura que indica qué línea se está dibujando.
     * Rango: 0-153 (0-143 visibles, 144-153 V-Blank)
     */
    uint16_t ly_;
    
    /**
     * Clock interno: Contador de T-Cycles acumulados para la línea actual.
     * Cuando llega a 456, avanzamos a la siguiente línea.
     * Usamos uint32_t para evitar overflow (necesitamos poder acumular hasta ~70K ciclos por frame).
     */
    uint32_t clock_;
    
    /**
     * Modo PPU actual: Indica en qué estado está la PPU (Mode 0, 1, 2 o 3).
     */
    uint8_t mode_;
    
    /**
     * Flag para indicar que un frame está listo para renderizar.
     * Se activa cuando LY pasa de 143 a 144 (inicio de V-Blank).
     */
    bool frame_ready_;
    
    /**
     * LYC (LY Compare): Registro de lectura/escritura que almacena el valor de línea
     * con el que se compara LY para generar interrupciones STAT.
     */
    uint8_t lyc_;
    
    /**
     * Flag para evitar disparar múltiples interrupciones STAT en la misma línea.
     * Se usa para implementar "rising edge" detection.
     */
    bool stat_interrupt_line_;
    
    /**
     * Actualiza el modo PPU actual según el punto en la línea (line_cycles) y LY.
     */
    void update_mode();
    
    /**
     * Verifica las condiciones de interrupción STAT y solicita la interrupción si corresponde.
     * 
     * Las interrupciones STAT se pueden generar por:
     * 1. LYC=LY Coincidence (LY == LYC) si el bit 6 de STAT está activo
     * 2. Mode 0 (H-Blank) si el bit 3 de STAT está activo
     * 3. Mode 1 (V-Blank) si el bit 4 de STAT está activo
     * 4. Mode 2 (OAM Search) si el bit 5 de STAT está activo
     */
    void check_stat_interrupt();
};

#endif // PPU_HPP

