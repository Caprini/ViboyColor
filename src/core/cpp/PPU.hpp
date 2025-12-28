#ifndef PPU_HPP
#define PPU_HPP

#include <cstdint>
#include <vector>

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
    static constexpr uint16_t IO_SCY = 0xFF42;   // Scroll Y
    static constexpr uint16_t IO_SCX = 0xFF43;   // Scroll X
    static constexpr uint16_t IO_BGP = 0xFF47;   // Background Palette
    static constexpr uint16_t IO_WY = 0xFF4A;    // Window Y
    static constexpr uint16_t IO_WX = 0xFF4B;    // Window X
    static constexpr uint16_t IO_OBP0 = 0xFF48;  // Object Palette 0
    static constexpr uint16_t IO_OBP1 = 0xFF49;  // Object Palette 1
    
    /**
     * Direcciones de memoria VRAM
     */
    static constexpr uint16_t VRAM_START = 0x8000;    // Inicio de VRAM
    static constexpr uint16_t VRAM_END = 0x9FFF;      // Fin de VRAM (8KB)
    static constexpr uint16_t TILEMAP_0 = 0x9800;     // Tilemap 0 (32x32 tiles)
    static constexpr uint16_t TILEMAP_1 = 0x9C00;     // Tilemap 1 (32x32 tiles)
    static constexpr uint16_t TILE_DATA_0 = 0x8000;   // Tile Data 0 (unsigned addressing)
    static constexpr uint16_t TILE_DATA_1 = 0x8800;   // Tile Data 1 (signed addressing, tile 0 en 0x9000)
    
    /**
     * Direcciones de memoria OAM (Object Attribute Memory)
     */
    static constexpr uint16_t OAM_START = 0xFE00;     // Inicio de OAM
    static constexpr uint16_t OAM_END = 0xFE9F;       // Fin de OAM (160 bytes = 40 sprites * 4 bytes)
    static constexpr uint8_t MAX_SPRITES = 40;        // Máximo de sprites en OAM
    static constexpr uint8_t BYTES_PER_SPRITE = 4;    // Bytes por sprite (Y, X, Tile ID, Attributes)
    
    /**
     * Dimensiones de pantalla
     */
    static constexpr uint16_t SCREEN_WIDTH = 160;     // Ancho en píxeles
    static constexpr uint16_t SCREEN_HEIGHT = 144;    // Alto en píxeles
    static constexpr uint16_t FRAMEBUFFER_SIZE = SCREEN_WIDTH * SCREEN_HEIGHT;  // 23040 píxeles
    
    /**
     * Constantes de tiles
     */
    static constexpr uint8_t TILE_SIZE = 8;           // Tamaño de tile en píxeles (8x8)
    static constexpr uint16_t TILES_PER_LINE = 20;    // Tiles visibles por línea (160/8)
    
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
     * Step 0291: Obtiene el contador de frames actual.
     * Se incrementa cada vez que LY vuelve a 0 (nuevo frame).
     * 
     * @return Número de frame actual (0-based)
     */
    uint64_t get_frame_counter() const;
    
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
     * Implementa un patrón de "máquina de estados de un solo uso": si la bandera
     * está levantada, la devuelve como true e inmediatamente la baja a false.
     * 
     * @return true si hay un frame listo para renderizar, false en caso contrario
     */
    bool get_frame_ready_and_reset();
    
    /**
     * Obtiene un puntero al framebuffer para acceso directo desde Cython.
     * 
     * El framebuffer es un array de uint8_t con índices de color (0-3).
     * Tamaño: 160 * 144 = 23040 píxeles.
     * 
     * @return Puntero al primer elemento del framebuffer
     */
    uint8_t* get_framebuffer_ptr();
    
    /**
     * Limpia el framebuffer, estableciendo todos los píxeles a índice 0 (blanco por defecto).
     * 
     * Este método debe llamarse al inicio de cada fotograma para asegurar que el
     * renderizado comienza desde un estado limpio. En hardware real, esto ocurre
     * implícitamente porque cada píxel se redibuja en cada ciclo, pero en nuestro
     * modelo de emulación, cuando el fondo está apagado (LCDC bit 0 = 0), no se
     * renderiza nada y el framebuffer conserva los datos del fotograma anterior.
     * 
     * Fuente: Práctica estándar de gráficos por ordenador (Back Buffer Clearing).
     */
    void clear_framebuffer();

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
     * Contador de frames: Se incrementa cada vez que LY vuelve a 0 (nuevo frame).
     * Step 0291: Necesario para rastrear el timing de carga de tiles.
     */
    uint64_t frame_counter_;
    
    /**
     * Máscara de bits para rastrear condiciones de interrupción STAT activas.
     * Se usa para implementar "rising edge" detection.
     * 
     * Bits:
     * - Bit 0: LYC=LY Coincidence activa
     * - Bit 1: Mode 0 (H-Blank) activa
     * - Bit 2: Mode 1 (V-Blank) activa
     * - Bit 3: Mode 2 (OAM Search) activa
     */
    uint8_t stat_interrupt_line_;
    
    /**
     * Flag para evitar renderizar múltiples veces la misma línea.
     * Se resetea cuando LY cambia.
     */
    bool scanline_rendered_;
    
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
    
    /**
     * Framebuffer: Array de índices de color (8 bits por píxel).
     * Tamaño: 160 * 144 = 23040 píxeles.
     * Formato: Índices de color 0-3 (4 colores posibles por paleta).
     * Los colores finales se aplican en Python usando la paleta BGP.
     */
    std::vector<uint8_t> framebuffer_;
    
    /**
     * Renderiza la línea de escaneo actual (scanline rendering).
     * 
     * Este método se llama cuando la PPU entra en H-Blank (Mode 0) después
     * de completar el Mode 3 (Pixel Transfer). Renderiza Background y Window
     * para la línea LY actual.
     * 
     * Fuente: Pan Docs - LCD Timing, Background, Window
     */
    void render_scanline();
    
    /**
     * Renderiza la capa de Background para la línea actual.
     * 
     * Lee los registros SCX, SCY, LCDC y BGP para determinar qué tiles
     * dibujar y cómo aplicar scroll y paleta.
     * 
     * Fuente: Pan Docs - Background, Scroll Registers
     */
    void render_bg();
    
    /**
     * Renderiza la capa de Window para la línea actual.
     * 
     * La Window es una capa opaca que se dibuja encima del Background
     * pero debajo de los Sprites. Lee los registros WX, WY y LCDC.
     * 
     * Fuente: Pan Docs - Window
     */
    void render_window();
    
    /**
     * Renderiza los sprites (OBJ - Objects) para la línea actual.
     * 
     * Lee OAM (Object Attribute Memory) en 0xFE00-0xFE9F y dibuja los sprites
     * que intersectan con la línea LY actual. Los sprites se dibujan después
     * del Background y Window, respetando transparencia (color 0) y prioridad.
     * 
     * Cada sprite tiene 4 bytes en OAM:
     * - Byte 0: Y position (pantalla + 16, 0 = oculto)
     * - Byte 1: X position (pantalla + 8, 0 = oculto)
     * - Byte 2: Tile ID (índice del tile en VRAM)
     * - Byte 3: Attributes (Bit 7: Prioridad, Bit 6: Y-Flip, Bit 5: X-Flip, Bit 4: Paleta)
     * 
     * Fuente: Pan Docs - OAM, Sprite Attributes, Sprite Rendering
     */
    void render_sprites();
    
    /**
     * Decodifica una línea de un tile (8 píxeles) desde VRAM.
     * 
     * Los tiles están almacenados en formato 2bpp:
     * - 2 bytes por línea (16 bytes por tile total)
     * - Byte 1: Bits bajos de cada píxel
     * - Byte 2: Bits altos de cada píxel
     * - Color = (bit_alto << 1) | bit_bajo (valores 0-3)
     * 
     * @param tile_addr Dirección base del tile en VRAM
     * @param line Línea dentro del tile (0-7)
     * @return Array de 8 valores de color (0-3)
     */
    void decode_tile_line(uint16_t tile_addr, uint8_t line, uint8_t* output);
    
    /**
     * Step 0320: Verifica si los tiles de prueba siguen en VRAM.
     * 
     * Calcula un checksum de los primeros 4 tiles (0x8000-0x803F) y lo compara
     * con el checksum esperado después de load_test_tiles(). Si los tiles fueron
     * sobrescritos, loggea una advertencia.
     */
    void verify_test_tiles();
    
    /**
     * Step 0321: Verifica si el juego cargó tiles en VRAM.
     * 
     * Calcula un checksum de toda la VRAM (0x8000-0x97FF) y detecta cuando
     * cambia significativamente, indicando que el juego cargó tiles propios.
     */
    void check_game_tiles_loaded();
};

#endif // PPU_HPP

