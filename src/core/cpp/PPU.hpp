#ifndef PPU_HPP
#define PPU_HPP

#include <cstdint>
#include <vector>

// Forward declaration (evitar includes circulares)
class MMU;

/**
 * Step 0488: Estructura para estadísticas del framebuffer.
 * 
 * Permite diagnosticar si el PPU está generando diversidad de colores
 * o si el framebuffer está uniforme (blanco/negro).
 */
struct FrameBufferStats {
    uint32_t fb_crc32;                    // CRC32 del framebuffer (o hash rápido equivalente)
    uint32_t fb_unique_colors;            // Número de valores distintos en el framebuffer
    uint32_t fb_nonwhite_count;           // Cuenta de píxeles distintos de índice 0 (blanco)
    uint32_t fb_nonblack_count;           // Cuenta de píxeles distintos de índice 3 (negro)
    uint32_t fb_top4_colors[4];           // Los 4 colores más frecuentes (índices 0-3)
    uint32_t fb_top4_colors_count[4];     // Conteo de cada uno
    bool fb_changed_since_last;            // Hash != anterior
    uint32_t fb_last_hash;                // Hash del frame anterior (para comparar)
};

/**
 * Step 0489: Estructura para estadísticas de tres buffers (prueba irrefutable).
 * 
 * Captura CRC32 y estadísticas en 3 puntos del pipeline:
 * - A1) FB_INDEX: Framebuffer de índices (160x144 de índices 0..3)
 * - A2) FB_RGB: Buffer RGB después de mapear paletas (160x144 en RGB/RGBA)
 * - A3) FB_PRESENT_SRC: Buffer exacto que se pasa a SDL/ventana/texture update
 * 
 * Permite diagnosticar si el blanco viene de:
 * - Paletas CGB no aplicadas/no actualizadas (idx_crc32 ≠ 0 pero rgb_crc32 = blanco)
 * - Presentación/blit (rgb_crc32 ≠ 0 pero present_crc32 = blanco/constante)
 * - PPU no genera nada útil (los 3 son "todo blanco")
 */
struct ThreeBufferStats {
    // A1) FB_INDEX (lo que ya medimos: 160x144 de índices 0..3)
    uint32_t idx_crc32;
    uint32_t idx_unique;
    uint32_t idx_nonzero;
    
    // A2) FB_RGB (después de mapear paletas → buffer de 160x144 en RGB/RGBA que debería ir a pantalla)
    uint32_t rgb_crc32;
    uint32_t rgb_unique_colors_approx;  // Aproximación (muestreo)
    uint32_t rgb_nonwhite_count;
    
    // A3) FB_PRESENT_SRC (puntero/bytes EXACTOS que se pasan a SDL/ventana/texture update)
    uint32_t present_crc32;
    uint32_t present_nonwhite_count;
    uint32_t present_fmt;  // Si hay formatos: RGBA/BGRA/ARGB (codificado como número)
    uint32_t present_pitch;
    uint32_t present_w;
    uint32_t present_h;
};

/**
 * Step 0489: Estructura para estadísticas de fetch de tiles DMG.
 * 
 * Permite rastrear si el PPU está leyendo tile data correctamente.
 */
struct DMGTileFetchStats {
    uint32_t tile_bytes_read_nonzero_count;  // Cuántas veces el fetch lee bytes (low/high) NO-cero
    uint32_t tile_bytes_read_total_count;
    uint16_t top_vram_read_addrs[10];  // Top 10 direcciones VRAM leídas por el PPU
    uint32_t top_vram_read_counts[10];
};

/**
 * Step 0498: Estructura para eventos de BufferTrace con CRC32.
 * 
 * Permite rastrear la integridad del contenido del framebuffer a través
 * del pipeline (PPU → RGB → Renderer → Present) usando CRC32.
 */
struct BufferTraceEvent {
    uint64_t frame_id;                    // Frame ID único del frame
    uint64_t framebuffer_frame_id;        // Frame ID del buffer front
    uint32_t front_idx_crc32;             // CRC32 del framebuffer_front_ (índices)
    uint32_t front_rgb_crc32;             // CRC32 del framebuffer_rgb_front_
    uint32_t back_idx_crc32;              // CRC32 del framebuffer_back_ (índices)
    uint32_t back_rgb_crc32;              // CRC32 del framebuffer_rgb_back_ (si existe)
    uint32_t buffer_uid;                   // ID único del buffer (hash del puntero o contenido)
};

/**
 * Step 0501: Estructura para estadísticas de modo PPU por frame.
 * 
 * Permite verificar si el PPU está en el modo correcto y detectar problemas
 * de timing que podrían causar bloqueos de VRAM.
 */
struct PPUModeStats {
    uint32_t mode_entries_count[4];  // Mode 0, 1, 2, 3 - número de veces que se entra en cada modo
    uint32_t mode_cycles[4];         // Ciclos totales en cada modo
    uint8_t ly_min;
    uint8_t ly_max;
    uint32_t frames_with_mode3_stuck;  // Si mode3 dura demasiado (> 456*144 ciclos)
};

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
     * Obtiene el valor interno raw de ly_ sin máscara (para diagnóstico Step 0438).
     * 
     * @return Valor interno de ly_ (puede exceder 153 durante transiciones)
     */
    uint16_t get_ly_internal() const;
    
    /**
     * Obtiene el clock interno de la PPU (para diagnóstico Step 0438).
     * 
     * @return Valor de clock_ (T-cycles acumulados en la PPU)
     */
    uint64_t get_ppu_clock() const;
    
    /**
     * Obtiene el modo PPU actual (0, 1, 2 o 3).
     * 
     * @return Modo PPU actual
     */
    uint8_t get_mode() const;
    
    /**
     * Step 0413: Obtiene el valor dinámico del registro STAT.
     * 
     * Construye STAT combinando:
     * - Bits 0-1: Modo PPU actual (get_mode())
     * - Bit 2: Coincidencia LYC=LY (1 si ly_ == lyc_)
     * - Bits 3-6: Máscaras de interrupción (leídas de MMU memory_[0xFF41])
     * - Bit 7: Siempre 1
     * 
     * Fuente: Pan Docs - LCD Status Register (FF41 - STAT)
     * 
     * @return Valor dinámico de STAT
     */
    uint8_t get_stat() const;
    
    
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
     * Step 0497: Obtiene el frame_id único actual.
     * 
     * El frame_id es un identificador único que se incrementa en cada frame
     * y viaja por todo el pipeline (PPU → RGB → Renderer → Present).
     * Permite rastrear qué frame se está procesando en cada etapa.
     * 
     * @return Frame ID único actual
     */
    uint64_t get_frame_id() const;
    
    /**
     * Step 0497: Obtiene el frame_id del buffer front (listo para leer).
     * 
     * Este frame_id corresponde al último frame que se completó y está
     * disponible en el framebuffer front (el que se presenta).
     * 
     * @return Frame ID del buffer front
     */
    uint64_t get_framebuffer_frame_id() const;
    
    /**
     * Step 0352: Verifica si el LCD está encendido.
     * 
     * Lee el registro LCDC (0xFF40) y verifica el bit 7 (LCD Enable).
     * 
     * @return true si el LCD está encendido, false en caso contrario
     */
    bool is_lcd_on() const;
    
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
     * Step 0413: Maneja el toggle del LCD (LCDC bit 7).
     * 
     * Cuando el LCD se apaga (bit 7 = 0):
     * - LY se fuerza a 0
     * - El modo se establece en MODE_0_HBLANK
     * - El reloj interno se resetea
     * 
     * Cuando el LCD se enciende (bit 7 = 1):
     * - LY se establece en 0
     * - El modo se establece en MODE_2_OAM_SEARCH
     * - El reloj interno se resetea
     * 
     * Fuente: Pan Docs - LCD Control Register (FF40 - LCDC), LCD Power
     * 
     * @param lcd_on true si el LCD se está encendiendo, false si se está apagando
     */
    void handle_lcd_toggle(bool lcd_on);
    
    /**
     * Step 0482: Maneja el disable del LCD (LCDC bit7 pasa de 1→0).
     * 
     * Cuando LCD se apaga:
     * - LY se resetea a 0
     * - STAT mode se establece en estado estable (Mode 0 = HBlank)
     * - No queda frame pending infinito
     */
    void handle_lcd_disable();
    
    /**
     * Step 0467: Verifica si hay un frame listo sin resetear el flag.
     * 
     * Este método permite verificar el estado de frame_ready_ sin afectar
     * el estado interno. Útil para tests que necesitan leer el framebuffer
     * antes de llamar a get_frame_ready_and_reset().
     * 
     * @return true si hay un frame listo para renderizar, false en caso contrario
     */
    bool is_frame_ready() const;
    
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
     * Step 0404: Obtiene un puntero al framebuffer RGB888 para acceso directo desde Cython.
     * 
     * El framebuffer RGB888 es un array de uint8_t con valores RGB (0-255 por canal).
     * Tamaño: 160 * 144 * 3 = 69120 bytes (R, G, B por píxel).
     * 
     * Este framebuffer se usa en modo CGB para renderizar con paletas CGB reales (BGR555).
     * En modo DMG, se puede ignorar y usar el framebuffer de índices con BGP.
     * 
     * @return Puntero al primer elemento del framebuffer RGB888
     */
    uint8_t* get_framebuffer_rgb_ptr();
    
    /**
     * Step 0457: Debug API para tests - Obtiene un puntero al framebuffer de índices.
     * 
     * Devuelve puntero al framebuffer_front_ (índices 0..3).
     * NO debe afectar hot path; es lectura directa de buffer.
     * 
     * @return Puntero al primer elemento del framebuffer de índices (23040 bytes)
     */
    const uint8_t* get_framebuffer_indices_ptr() const;
    
    /**
     * Step 0468: Getter "presented" para framebuffer indices.
     * 
     * Garantiza que devuelve el último frame presentado (hace present automático
     * si hay swap pendiente, igual que get_framebuffer_ptr()).
     * 
     * Contrato: Siempre devuelve el frame más reciente renderizado y presentado.
     * 
     * @return Puntero al framebuffer de índices presentado (23040 bytes)
     */
    const uint8_t* get_presented_framebuffer_indices_ptr();
    
    /**
     * Step 0488: Obtiene estadísticas del framebuffer del último frame.
     * 
     * Devuelve métricas sobre diversidad de colores, cambios entre frames,
     * y distribución de índices de color en el framebuffer.
     * 
     * @return Referencia constante a FrameBufferStats con las estadísticas
     */
    const FrameBufferStats& get_framebuffer_stats() const;
    
    /**
     * Step 0489: Obtiene estadísticas de los tres buffers (prueba irrefutable).
     * 
     * Devuelve métricas sobre FB_INDEX, FB_RGB y FB_PRESENT_SRC para diagnosticar
     * si el blanco viene de paletas, presentación o PPU.
     * 
     * @return Referencia constante a ThreeBufferStats con las estadísticas
     */
    const ThreeBufferStats& get_three_buffer_stats() const;
    
    /**
     * Step 0489: Actualiza estadísticas de presentación desde Python.
     * 
     * Permite que Python actualice present_crc32 y present_nonwhite_count
     * después de capturar el buffer exacto que se pasa a SDL.
     * 
     * @param present_crc32 CRC32 del buffer presentado
     * @param present_nonwhite_count Conteo de píxeles no-blancos en el buffer presentado
     * @param present_fmt Formato del buffer (codificado como número)
     * @param present_pitch Pitch del buffer
     * @param present_w Ancho del buffer
     * @param present_h Alto del buffer
     */
    void set_present_stats(uint32_t present_crc32, uint32_t present_nonwhite_count,
                           uint32_t present_fmt, uint32_t present_pitch,
                           uint32_t present_w, uint32_t present_h);
    
    /**
     * Step 0489: Obtiene estadísticas de fetch de tiles DMG.
     * 
     * Devuelve métricas sobre lecturas de tile data por scanline.
     * 
     * @return Referencia constante a DMGTileFetchStats con las estadísticas
     */
    const DMGTileFetchStats& get_dmg_tile_fetch_stats() const;
    
    /**
     * Step 0501: Obtiene estadísticas de modo PPU por frame.
     * 
     * Devuelve métricas sobre el tiempo que la PPU pasa en cada modo (0-3),
     * número de entradas a cada modo, y detección de problemas de timing.
     * 
     * @return Referencia constante a PPUModeStats con las estadísticas
     */
    const PPUModeStats& get_ppu_mode_stats() const;
    
    /**
     * Step 0498: Obtiene el ring buffer de eventos BufferTrace.
     * 
     * Devuelve los últimos N eventos del ring buffer para análisis de consistencia.
     * 
     * @param max_events Número máximo de eventos a devolver (máximo 128)
     * @return Vector con los últimos eventos BufferTrace
     */
    std::vector<BufferTraceEvent> get_buffer_trace_ring(size_t max_events = 128) const;
    
    /**
     * Step 0469: Obtiene el contador de VBlank IRQ solicitados.
     * 
     * Este contador se incrementa cada vez que el PPU solicita una interrupción VBlank
     * (cuando LY alcanza 144). Útil para diagnóstico de por qué los juegos no progresan.
     * 
     * @return Número de veces que se ha solicitado VBlank interrupt
     */
    uint32_t get_vblank_irq_requested_count() const;
    
    /**
     * Step 0457: Debug - Getters para paleta regs usados en última conversión.
     * 
     * Estos valores se actualizan en convert_framebuffer_to_rgb() y permiten
     * verificar en tests que la paleta usada coincide con la escrita.
     */
    uint8_t get_last_bgp_used() const { return last_bgp_used_; }
    uint8_t get_last_obp0_used() const { return last_obp0_used_; }
    uint8_t get_last_obp1_used() const { return last_obp1_used_; }
    
    /**
     * Step 0458: Debug - Getters para estadísticas de renderizado BG.
     */
#ifdef VIBOY_DEBUG_PPU
    int get_bg_pixels_written_count() const { return bg_pixels_written_count_; }
    bool get_first_nonzero_color_idx_seen() const { return first_nonzero_color_idx_seen_; }
    uint8_t get_first_nonzero_color_idx_value() const { return first_nonzero_color_idx_value_; }
    const uint8_t* get_last_tile_bytes_read() const { return last_tile_bytes_read_; }
    bool get_last_tile_bytes_valid() const { return last_tile_bytes_valid_; }
    uint16_t get_last_tile_addr_read() const { return last_tile_addr_read_; }
    
    /**
     * Step 0459: Debug - Getters para samples del pipeline idx→shade→rgb.
     */
    const uint8_t* get_last_idx_samples() const { return last_idx_samples_; }
    const uint8_t* get_last_shade_samples() const { return last_shade_samples_; }
    const uint8_t* get_last_rgb_samples() const { return reinterpret_cast<const uint8_t*>(last_rgb_samples_); }
    int get_last_convert_sample_count() const { return last_convert_sample_count_; }
    uint8_t get_last_bgp_used_debug() const { return last_bgp_used_debug_; }
#endif
    
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
    
    /**
     * Step 0364: Intercambia los framebuffers front y back.
     * 
     * Este método intercambia los buffers cuando se completa un frame completo (LY=144).
     * Solo debe llamarse desde get_frame_ready_and_reset() cuando frame_ready_ es true.
     * Thread-safe: solo intercambia punteros internos de std::vector, no copia datos.
     */
    void swap_framebuffers();
    
    /**
     * Step 0364: Confirma que Python leyó el framebuffer (mantenido por compatibilidad).
     * 
     * Con doble buffering, este método ya no es necesario pero se mantiene por compatibilidad
     * con el código Python que lo llama. El buffer front ya no se modifica durante la lectura.
     */
    void confirm_framebuffer_read();

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
     * Step 0497: Frame ID único que viaja por todo el pipeline.
     * Se incrementa en cada frame (cuando ly_ > 153) y se asocia al buffer front
     * en swap_framebuffers(). Permite rastrear qué frame se está procesando
     * en cada etapa del pipeline (PPU → RGB → Renderer → Present).
     */
    uint64_t frame_id_;
    
    /**
     * Step 0497: Frame ID del buffer front (el que se presenta).
     * Se actualiza en swap_framebuffers() con el frame_id_ actual.
     * Permite verificar que el renderer presenta el frame correcto.
     */
    uint64_t framebuffer_frame_id_;
    
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
     * Step 0330: Estado de VRAM para optimización.
     * Indica si VRAM está completamente vacía (< 200 bytes no-cero).
     * Se actualiza una vez por línea (en LY=0) para evitar verificaciones repetitivas.
     */
    bool vram_is_empty_;
    
    /**
     * Step 0397: Estado unificado de detección de tiles en VRAM.
     * Indica si VRAM tiene tiles completos no-vacíos.
     * Se actualiza una vez por frame (en LY=0) usando helpers dual-bank.
     * Reemplaza la variable estática vram_has_tiles en render_bg().
     */
    bool vram_has_tiles_;
    
    /**
     * Step 0394: Estado del checkerboard determinista.
     * Indica si el checkerboard está actualmente activo (renderizándose).
     * Se activa cuando vram_is_empty_ es true y tile es vacío.
     * Se desactiva cuando vram_is_empty_ cambia a false.
     */
    bool checkerboard_active_;
    
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
     * Step 0364: Doble Buffering para eliminar condiciones de carrera.
     * 
     * framebuffer_front_: Buffer que Python lee (público, estable, no se modifica durante renderizado).
     * framebuffer_back_: Buffer donde C++ escribe (privado, se modifica durante renderizado).
     * 
     * Tamaño de cada buffer: 160 * 144 = 23040 píxeles.
     * Formato: Índices de color 0-3 (4 colores posibles por paleta).
     * Los colores finales se aplican en Python usando la paleta BGP.
     * 
     * El intercambio solo ocurre cuando se completa un frame completo (LY=144).
     */
    std::vector<uint8_t> framebuffer_front_;  // Buffer que Python lee (estable)
    std::vector<uint8_t> framebuffer_back_;   // Buffer donde C++ escribe (se modifica)
    bool framebuffer_swap_pending_;           // Flag para indicar intercambio pendiente
    
    /**
     * Step 0404: Framebuffer RGB888 para modo CGB
     * 
     * framebuffer_rgb_front_: Buffer RGB que Python lee (160*144*3 bytes = 69120 bytes)
     * framebuffer_rgb_back_: Buffer RGB donde C++ escribe durante renderizado
     * 
     * Formato: RGB888 (3 bytes por píxel: R, G, B). Cada canal es 0-255.
     * Organización: [R0, G0, B0, R1, G1, B1, ..., R23039, G23039, B23039]
     * 
     * Se usa en modo CGB para renderizar con paletas CGB reales (BGR555 convertido a RGB888).
     * En modo DMG, este buffer puede ignorarse (usar framebuffer de índices + BGP).
     */
    std::vector<uint8_t> framebuffer_rgb_front_;  // Buffer RGB que Python lee
    std::vector<uint8_t> framebuffer_rgb_back_;   // Buffer RGB donde C++ escribe
    
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
    
    /**
     * Step 0394: Helpers para conteo de VRAM dual-bank.
     * Cuentan bytes no-cero en cada región de VRAM usando read_vram_bank().
     */
    int count_vram_nonzero_bank0_tiledata() const;
    int count_vram_nonzero_bank0_tilemap() const;
    
    /**
     * Step 0408: Helpers para conteo de TileData en VRAM bank 1 (CGB).
     * Permiten detectar si un juego CGB carga tiles en bank 1.
     */
    int count_vram_nonzero_bank1_tiledata() const;
    int count_complete_nonempty_tiles_bank(int bank) const;
    
    /**
     * Step 0397: Helper para detección mejorada de tiles completos.
     * Cuenta tiles completos (16 bytes) que tienen al menos 8 bytes no-cero.
     * Esto identifica tiles reales, no solo bytes sueltos.
     */
    int count_complete_nonempty_tiles() const;
    
    /**
     * Step 0399: Helper para contar tile IDs únicos en el tilemap.
     * Mide la diversidad de tiles en el tilemap activo (no solo conteo de bytes).
     * Retorna: número de tile IDs únicos (0-256).
     * Fuente: Pan Docs - Tile Maps (0x9800-0x9BFF, 0x9C00-0x9FFF).
     */
    int count_unique_tile_ids_in_tilemap() const;
    
    /**
     * Step 0399: Helper para determinar si el juego está en estado jugable.
     * Combina múltiples métricas: TileData con datos + diversidad de tilemap + tiles completos.
     * Retorna: true si el juego está en estado jugable, false si está en inicialización.
     */
    bool is_gameplay_state() const;
    
    /**
     * Step 0395: Diagnóstico Visual: Snapshot del Framebuffer.
     * Captura distribución de valores del framebuffer en frames clave.
     */
    void dump_framebuffer_snapshot();
    
    /**
     * Step 0395: Verificar correspondencia tilemap → framebuffer.
     * Valida que los tiles referenciados por el tilemap se renderizan correctamente.
     */
    void verify_tilemap_to_framebuffer(uint16_t screen_x, uint8_t tile_id, 
                                       uint16_t tile_addr, uint8_t line_in_tile,
                                       uint8_t pixel_in_tile, uint8_t* cached_tile_line);
    
    /**
     * Step 0395: Verificar scroll y wrap-around.
     * Detecta si la fragmentación visual proviene de scroll incorrecto.
     */
    void verify_scroll_wraparound(uint16_t screen_x);
    
    /**
     * Step 0395: Verificar aplicación de paleta BGP.
     * Confirma que la paleta mapea correctamente los índices de color.
     */
    void verify_palette_bgp(uint8_t tile_id, uint16_t tile_addr, 
                            uint8_t line_in_tile, uint8_t color_index);
    
    /**
     * Step 0398: Analizar tile IDs del tilemap de Zelda DX.
     * Identifica qué tiles están referenciados y dónde deberían estar en VRAM.
     */
    void analyze_tilemap_tile_ids();
    
    /**
     * Step 0398: Verificar DMA/HDMA activo.
     * Detecta si hay transferencias DMA/HDMA cargando tiles desde ROM.
     */
    void check_dma_hdma_activity();
    
    /**
     * Step 0398: Analizar timing de carga (tilemap vs tiles).
     * Detecta cuándo se carga el tilemap y cuándo se cargan los tiles.
     */
    void analyze_load_timing();
    
    /**
     * Step 0400: Captura snapshot de ejecución para análisis comparativo.
     * Registra estado de registros críticos en frames clave.
     */
    void capture_execution_snapshot();
    
    /**
     * Step 0400: Análisis de progresión de VRAM para comparación entre juegos.
     * Registra evolución de tiledata, tilemap y unique_tile_ids cada 120 frames.
     */
    void analyze_vram_progression();
    
    /**
     * Step 0404: Convierte el framebuffer de índices (0-3) a RGB888 usando paletas CGB.
     * 
     * Esta función toma el framebuffer front de índices y lo convierte a RGB888 usando las
     * paletas CGB almacenadas en la MMU (bg_palette_data_[]). Por ahora, usa un enfoque
     * simplificado que aplica la paleta 0 de BG a todos los píxeles.
     * 
     * TODO (futuro): Leer tile attributes (VRAM bank 1) para determinar qué paleta usar por tile.
     * 
     * Fuente: Pan Docs - CGB Registers, Background Palettes (FF68-FF69)
     */
    void convert_framebuffer_to_rgb();
    
    /**
     * Step 0400: Variables de tracking para progresión de VRAM.
     */
    uint64_t vram_progression_last_frame_;  // Último frame donde se registró progresión
    int vram_progression_tiledata_threshold_;  // Frame donde tiledata cambia >5%
    int vram_progression_tilemap_threshold_;   // Frame donde tilemap cambia >5%
    int vram_progression_unique_tiles_threshold_;  // Frame donde unique_tiles >10
    
    /**
     * Step 0457: Debug - Paleta regs usados en última conversión.
     * Se actualizan en convert_framebuffer_to_rgb() para verificación en tests.
     */
    mutable uint8_t last_bgp_used_;   // BGP usado en última conversión
    mutable uint8_t last_obp0_used_;   // OBP0 usado en última conversión
    mutable uint8_t last_obp1_used_;  // OBP1 usado en última conversión
    
    /**
     * Step 0458: Debug - Contadores para verificar que BG render ejecuta.
     */
#ifdef VIBOY_DEBUG_PPU
    mutable int bg_pixels_written_count_;
    mutable bool first_nonzero_color_idx_seen_;
    mutable uint8_t first_nonzero_color_idx_value_;
    mutable uint8_t last_tile_bytes_read_[2];  // Últimos 2 bytes leídos del tile
    mutable bool last_tile_bytes_valid_;
    mutable uint16_t last_tile_addr_read_;
    
    /**
     * Step 0459: Debug - Samples del pipeline idx→shade→rgb.
     * Captura los primeros N píxeles del pipeline de conversión para diagnóstico.
     */
    static constexpr int MAX_CONVERT_SAMPLES = 32;
    mutable uint8_t last_idx_samples_[MAX_CONVERT_SAMPLES];
    mutable uint8_t last_shade_samples_[MAX_CONVERT_SAMPLES];
    mutable uint8_t last_rgb_samples_[MAX_CONVERT_SAMPLES][3];  // R, G, B
    mutable int last_convert_sample_count_;
    mutable uint8_t last_bgp_used_debug_;  // BGP usado en última conversión (duplicado para debug)
#endif
    
    /**
     * Step 0488: Estadísticas del framebuffer.
     * Se actualizan al final de cada frame (después de swap_framebuffers).
     */
    FrameBufferStats framebuffer_stats_;
    
    /**
     * Step 0489: Estadísticas de los tres buffers (prueba irrefutable).
     * Se actualizan al final de cada frame (después de swap_framebuffers).
     */
    ThreeBufferStats three_buffer_stats_;
    DMGTileFetchStats dmg_tile_fetch_stats_;
    
    /**
     * Step 0501: Estadísticas de modo PPU por frame.
     * Se actualizan en cada llamada a update_mode() y step().
     */
    PPUModeStats ppu_mode_stats_;
    
    /**
     * Step 0498: Ring buffer para eventos BufferTrace con CRC32.
     * Permite rastrear la integridad del contenido del framebuffer a través
     * del pipeline (PPU → RGB → Renderer → Present).
     */
    static constexpr size_t BUFFER_TRACE_RING_SIZE = 128;
    BufferTraceEvent buffer_trace_ring_[BUFFER_TRACE_RING_SIZE];
    size_t buffer_trace_ring_head_;
    
    /**
     * Step 0488: Calcula estadísticas del framebuffer actual.
     * 
     * Analiza el framebuffer presentado (front) y calcula:
     * - Número de colores únicos (índices 0-3)
     * - Conteo de píxeles no-blancos y no-negros
     * - Top 4 colores más frecuentes
     * - Hash/CRC32 para detectar cambios entre frames
     * 
     * Gateado por VIBOY_DEBUG_FB_STATS=1 para no penalizar rendimiento.
     */
    void compute_framebuffer_stats();
    
    /**
     * Step 0489: Calcula estadísticas de los tres buffers (prueba irrefutable).
     * 
     * Analiza FB_INDEX, FB_RGB y FB_PRESENT_SRC para diagnosticar
     * si el blanco viene de paletas, presentación o PPU.
     * 
     * Gateado por VIBOY_DEBUG_PRESENT_TRACE=1 para no penalizar rendimiento.
     */
    void compute_three_buffer_stats();
    
    /**
     * Step 0498: Calcula CRC32 de un buffer completo.
     * 
     * Usa el algoritmo CRC32 estándar (polinomio 0xEDB88320) para calcular
     * el checksum de un buffer de datos.
     * 
     * @param data Vector con los datos a calcular
     * @param size Tamaño en bytes a procesar
     * @return CRC32 del buffer
     */
    uint32_t compute_crc32_full(const std::vector<uint8_t>& data, size_t size) const;
    
    /**
     * Step 0498: Calcula un ID único del buffer (hash simple).
     * 
     * Usa un hash simple de los primeros 100 bytes para identificar
     * la identidad del buffer (para detectar si es el mismo buffer).
     * 
     * @param data Vector con los datos del buffer
     * @return Hash único del buffer
     */
    uint32_t compute_buffer_uid(const std::vector<uint8_t>& data) const;
};

#endif // PPU_HPP

