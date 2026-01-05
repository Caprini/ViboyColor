#include "MMU.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include "Joypad.hpp"
#include <cstring>
#include <algorithm>
#include <cstdio>
#include <map>
#include <string>
#include <set>

// --- Step 0327: Variable estática compartida para análisis de limpieza de VRAM ---
static bool tiles_were_loaded_recently_global = false;
// -------------------------------------------

// --- Step 0470: Contadores de writes a IE/IF ---
// Step 0482: ie_write_count convertido a miembro de instancia (ie_write_count_)
// static uint32_t if_write_count = 0;  // Step 0482: Ya no se usa (se usa if_write_count_)
static uint8_t last_ie_written = 0x00;
static uint8_t last_if_written = 0x00;

// --- Step 0471: Instrumentación microscópica de IE ---
static uint16_t last_ie_write_pc = 0x0000;
static uint32_t last_ie_write_timestamp = 0;
static uint8_t last_ie_read_value = 0x00;
static uint32_t ie_read_count = 0;

// --- Step 0472: Instrumentación de KEY1 (0xFF4D) ---
static uint32_t key1_write_count = 0;
static uint8_t last_key1_write_value = 0x00;
static uint16_t last_key1_write_pc = 0x0000;

// --- Step 0472: Instrumentación de JOYP (0xFF00) ---
static uint32_t joyp_write_count = 0;
static uint8_t last_joyp_write_value = 0x00;
static uint16_t last_joyp_write_pc = 0x0000;
// --- Step 0481: Instrumentación de JOYP reads ---
static uint32_t joyp_read_count_program = 0;
static uint8_t last_joyp_read_value = 0x00;
static uint16_t last_joyp_read_pc = 0x0000;

// --- Step 0470: Watch de lecturas de IO (solo contadores) ---
static std::map<uint16_t, uint32_t> io_read_counts;
// -------------------------------------------

// --- Step 0206: Datos del Logo Personalizado "Viboy Color" en Formato Tile (2bpp) ---
// Convertido desde la imagen 'viboy_logo_48x8_debug.png' (48x8px) a formato de Tile (2bpp).
// 
// DIFERENCIA CRÍTICA CON EL STEP 0201:
// - Step 0201: Inyectamos datos de Header (1bpp) directamente en VRAM. Esto era incorrecto.
// - Step 0206: Inyectamos datos de Tile (2bpp) ya descomprimidos, listos para la PPU.
//
// La Boot ROM real lee los datos del header (1bpp) y los descomprime a formato Tile (2bpp)
// antes de copiarlos a la VRAM. Nosotros simulamos este proceso generando los datos
// ya descomprimidos externamente.
//
// Formato Tile (2bpp):
// - 48x8 píxeles = 6 tiles de 8x8
// - Cada tile ocupa 16 bytes (2 bytes por fila, 8 filas)
// - Total: 96 bytes para los 6 tiles
// - Cada píxel usa 2 bits (4 colores posibles: 00=Blanco, 11=Negro)
//
// Fuente: Pan Docs - "Tile Data", "Tile Map"
static const uint8_t VIBOY_LOGO_TILES[96] = {
    0x07, 0x07, 0x38, 0x38, 0x60, 0x60, 0x42, 0x42, 0xC1, 0xC1, 0x40, 0x40, 0x30, 0x30, 0x0F, 0x0F, 
    0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xAD, 0xAD, 0xAD, 0xAD, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 
    0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x7C, 0x7C, 0x28, 0x28, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 
    0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0xCA, 0xCA, 0x8A, 0x8A, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 
    0xFF, 0xFF, 0x00, 0x00, 0x00, 0x00, 0x95, 0x95, 0x93, 0x93, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 
    0xE0, 0xE0, 0x1C, 0x1C, 0x06, 0x06, 0xC3, 0xC3, 0xC3, 0xC3, 0x02, 0x02, 0x0C, 0x0C, 0xF0, 0xF0
};

// --- Tilemap del Logo (32 bytes = 1 fila del mapa de tiles) ---
// Centrado horizontalmente: 7 tiles de padding, 6 tiles del logo (IDs 1-6), resto padding
// El tile 0 se deja como blanco puro. Los tiles 1-6 contienen el logo.
static const uint8_t VIBOY_LOGO_MAP[32] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x00, 0x00, 0x00, 
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
};

MMU::MMU()
    : memory_(MEMORY_SIZE, 0)
    , ppu_(nullptr)
    , timer_(nullptr)
    , joypad_(nullptr)
    , debug_current_pc(0)
    , mbc_type_(MBCType::ROM_ONLY)
    , rom_bank_count_(1)
    , current_rom_bank_(1)
    , bank0_rom_(0)
    , bankN_rom_(1)
    // Step 0425: Eliminado test_mode_allow_rom_writes_
    , mbc1_bank_low5_(1)
    , mbc1_bank_high2_(0)
    , mbc1_mode_(0)
    , mbc3_rtc_reg_(0)
    , mbc3_latch_ready_(false)
    , mbc3_latch_value_(0xFF)
    , rtc_seconds_(0)
    , rtc_minutes_(0)
    , rtc_hours_(0)
    , rtc_day_low_(0)
    , rtc_day_high_(0)
    , rtc_start_time_(std::chrono::steady_clock::now())  // Step 0409: RTC start
    , ram_bank_size_(0x2000)
    , ram_bank_count_(0)
    , ram_bank_(0)
    , ram_enabled_(false)
    , vram_write_total_step382_(0)
    , vram_write_nonzero_step382_(0)
    , vram_tiledata_nonzero_writes_(0)  // Step 0391
    , vram_tilemap_nonzero_writes_(0)   // Step 0391
    , vram_region_summary_count_(0)     // Step 0391
    , oam_dma_count_(0)                 // Step 0410
    , hdma_start_count_(0)              // Step 0410
    , hdma_bytes_transferred_(0)        // Step 0410
    , vram_tiledata_cpu_writes_(0)      // Step 0410
    , vram_tiledata_cpu_nonzero_(0)     // Step 0410
    , vram_tiledata_cpu_log_count_(0)   // Step 0410
    , vram_tiledata_total_writes_(0)    // Step 0414
    , vram_tiledata_blocked_mode3_(0)   // Step 0414
    , vram_tiledata_summary_frames_(0)  // Step 0414
    , irq_req_vblank_count_(0)          // Step 0411
    , irq_req_stat_count_(0)            // Step 0411
    , irq_req_timer_count_(0)           // Step 0411
    , irq_req_serial_count_(0)          // Step 0411
    , irq_req_joypad_count_(0)          // Step 0411
    , irq_req_summary_count_(0)         // Step 0411
    , palette_write_log_count_(0)       // Step 0412
    , waitloop_trace_active_(false)
    , vblank_isr_trace_active_(false)
    , waitloop_mmio_count_(0)
    , waitloop_ram_count_(0)
    , vram_bank0_(0x2000, 0)  // Step 0389: Banco 0 de VRAM (8KB)
    , vram_bank1_(0x2000, 0)  // Step 0389: Banco 1 de VRAM (8KB)
    , vram_bank_(0)           // Step 0389: Banco actual (0 por defecto)
    , hdma1_(0xFF)            // Step 0390: HDMA Source High
    , hdma2_(0xFF)            // Step 0390: HDMA Source Low
    , hdma3_(0xFF)            // Step 0390: HDMA Destination High
    , hdma4_(0xFF)            // Step 0390: HDMA Destination Low
    , hdma5_(0xFF)            // Step 0390: HDMA Length/Mode/Start (0xFF = inactivo)
    , hdma_active_(false)     // Step 0390: HDMA inactivo al inicio
    , hdma_length_remaining_(0) // Step 0390: Sin bytes pendientes
    , bg_palette_index_(0)    // Step 0390: Índice de paleta BG inicial
    , obj_palette_index_(0)   // Step 0390: Índice de paleta OBJ inicial
    , last_lcdc_value_(0xFF)  // Step 0400: Valor inicial inválido
    , last_bgp_value_(0xFF)   // Step 0400: Valor inicial inválido
    , last_ie_value_(0xFF)    // Step 0400: Valor inicial inválido
    , lcdc_change_frame_(-1)  // Step 0400: Sin cambio detectado
    , bgp_change_frame_(-1)   // Step 0400: Sin cambio detectado
    , ie_change_frame_(-1)    // Step 0400: Sin cambio detectado
    , init_sequence_logged_(false)  // Step 0400: Sin log inicial
    , boot_rom_enabled_(false)  // Step 0401: Boot ROM deshabilitada por defecto
    , hardware_mode_(HardwareMode::DMG)  // Step 0404: Modo DMG por defecto
    , current_hl_value_(0)  // Step 0436: Valor temporal de HL para captura VRAM
    , mbc_write_count_(0)  // Step 0450: Contador de writes MBC
    , mbc_write_ring_idx_(0)  // Step 0450: Índice del ring buffer
    , if_write_count_(0)  // Step 0474: Contador de writes a IF
    , if_read_count_(0)  // Step 0474: Contador de reads de IF
    , last_if_write_pc_(0x0000)  // Step 0474: PC del último write a IF
    , last_if_write_val_(0x00)  // Step 0474: Último valor escrito a IF
    , last_if_write_timestamp_(0)  // Step 0477: Timestamp del último write a IF
    , last_if_read_val_(0x00)  // Step 0474: Último valor leído de IF
    , if_writes_0_(0)  // Step 0474: Contador de writes a IF con valor 0
    , if_writes_nonzero_(0)  // Step 0474: Contador de writes a IF con valor no-cero
    , ly_read_min_(0xFF)  // Step 0474: Valor mínimo de LY leído (inicializar alto)
    , ly_read_max_(0x00)  // Step 0474: Valor máximo de LY leído
    , last_ly_read_(0x00)  // Step 0474: Último valor leído de LY
    , last_stat_read_(0x00)  // Step 0474: Último valor leído de STAT
    , irq_poll_active_(false)  // Step 0475: Flag de polling IRQ (OFF por defecto)
    , if_reads_program_(0)  // Step 0475: Contador de lecturas IF desde programa
    , if_reads_cpu_poll_(0)  // Step 0475: Contador de lecturas IF desde polling
    , if_writes_program_(0)  // Step 0475: Contador de escrituras IF desde programa
    , ie_reads_program_(0)  // Step 0475: Contador de lecturas IE desde programa
    , ie_reads_cpu_poll_(0)  // Step 0475: Contador de lecturas IE desde polling
    , ie_writes_program_(0)  // Step 0475: Contador de escrituras IE desde programa
    , ie_write_count_(0)  // Step 0482: Contador de writes a IE (convertido de static a miembro)
    , boot_logo_prefill_enabled_(false)  // Step 0475: Prefill del logo deshabilitado por defecto
    , waits_on_addr_(0x0000)  // Step 0479: I/O esperado (0 = no configurado)
    , waits_on_reads_program_(0)  // Step 0479: Contador de reads desde programa
    , last_waits_on_read_value_(0x00)  // Step 0479: Último valor leído del I/O esperado
    , last_waits_on_read_pc_(0x0000)  // Step 0479: Último PC que leyó el I/O esperado
    , ly_changes_this_frame_(0)  // Step 0479: Contador de cambios de LY por frame
    , stat_mode_changes_count_(0)  // Step 0479: Contador de cambios de modo STAT por frame
    , if_bit0_set_count_this_frame_(0)  // Step 0479: Contador de veces que IF bit0 se pone a 1 por frame
    , hram_ff92_write_count_(0)  // Step 0480: Contador de writes a HRAM[FF92]
    , last_hram_ff92_write_pc_(0x0000)  // Step 0480: PC del último write a HRAM[FF92]
    , last_hram_ff92_write_value_(0x00)  // Step 0480: Último valor escrito a HRAM[FF92]
    , last_hram_ff92_write_timestamp_(0)  // Step 0480: Timestamp del último write a HRAM[FF92]
    , hram_ff92_read_count_program_(0)  // Step 0480: Contador de reads de HRAM[FF92] desde programa
    , last_hram_ff92_read_pc_(0x0000)  // Step 0480: PC del último read de HRAM[FF92]
    , last_hram_ff92_read_value_(0x00)  // Step 0480: Último valor leído de HRAM[FF92]
    , hram_watchlist_()  // Step 0481: Inicializar watchlist vacía
    , lcdc_disable_events_(0), last_lcdc_write_pc_(0xFFFF), last_lcdc_write_value_(0x00)  // Step 0482: LCDC Disable Tracking
    , joyp_last_read_select_bits_(0x00), joyp_last_read_low_nibble_(0x0F)  // Step 0484: JOYP Read Select Bits
    , joyp_reads_with_buttons_selected_count_(0), joyp_reads_with_dpad_selected_count_(0),  // Step 0485: JOYP Trace contadores
      joyp_reads_with_none_selected_count_(0)  // Step 0485
{
    // Step 0450: Inicializar ring buffer de MBC writes
    for (int i = 0; i < 8; i++) {
        mbc_write_addrs_[i] = 0;
        mbc_write_vals_[i] = 0;
        mbc_write_pcs_[i] = 0;
    }
    // Step 0390: Inicializar arrays de paletas CGB a 0xFF (valor inicial)
    std::memset(bg_palette_data_, 0xFF, sizeof(bg_palette_data_));
    std::memset(obj_palette_data_, 0xFF, sizeof(obj_palette_data_));
    
    // Step 0404: Inicializar registros I/O según el modo de hardware
    // Valores de Power Up Sequence (Pan Docs) para DMG/CGB
    initialize_io_registers();
    
    // NOTA: Los siguientes registros se controlan dinámicamente por hardware:
    // - 0xFF04 (DIV): Controlado por Timer
    // - 0xFF05 (TIMA): Controlado por Timer
    // - 0xFF06 (TMA): Controlado por Timer
    // - 0xFF07 (TAC): Controlado por Timer
    // - 0xFF00 (P1): Controlado por Joypad
    
    // --- Step 0206: Pre-cargar VRAM con el logo personalizado "Viboy Color" (Formato Tile 2bpp) ---
    // TEMPORALMENTE COMENTADO PARA STEP 0208: Diagnóstico de Fuerza Bruta
    /*
    // La Boot ROM real lee los datos del header (1bpp) y los descomprime a formato Tile (2bpp)
    // antes de copiarlos a la VRAM. Nosotros simulamos este proceso generando los datos
    // ya descomprimidos externamente.
    //
    // DIFERENCIA CRÍTICA CON EL STEP 0201:
    // - Step 0201: Inyectamos datos de Header (1bpp) directamente → PPU no podía interpretarlos.
    // - Step 0206: Inyectamos datos de Tile (2bpp) ya descomprimidos → PPU puede renderizarlos.
    //
    // Fuente: Pan Docs - "Tile Data", "Tile Map", "Boot ROM Behavior"
    
    // 1. Cargar Tiles del Logo (96 bytes) en VRAM Tile Data (0x8010)
    // Empezamos en 0x8010 (Tile ID 1) para dejar el Tile 0 como blanco puro.
    // 6 tiles x 16 bytes = 96 bytes totales
    for (size_t i = 0; i < sizeof(VIBOY_LOGO_TILES); ++i) {
        memory_[0x8010 + i] = VIBOY_LOGO_TILES[i];
    }
    
    // 2. Cargar Tilemap del Logo en VRAM Map (0x9904 - Fila 8, Columna 4, centrado)
    // CORRECCIÓN Step 0207: Usar 0x9904 para centrar en Fila 8, Columna 4.
    // Antes estaba en 0x9A00 (Fila 16), demasiado abajo y fuera del área visible.
    // Cálculo: 0x9800 (base) + (8 * 32) = 0x9900 (Fila 8) + 4 = 0x9904 (centrado horizontal)
    // 32 bytes = 1 fila completa del mapa de tiles (32 tiles horizontales)
    for (size_t i = 0; i < sizeof(VIBOY_LOGO_MAP); ++i) {
        memory_[0x9904 + i] = VIBOY_LOGO_MAP[i];
    }
    */
    
    // --- Step 0208: DIAGNÓSTICO VRAM FLOOD (Inundación de VRAM) ---
    // COMENTADO EN STEP 0209: El diagnóstico de inundación no funcionó (pantalla siguió blanca).
    // Esto sugiere que la ROM borra la VRAM antes del primer renderizado o que hay un problema
    // de direccionamiento. El Step 0209 prueba un enfoque más radical: interceptar la lectura
    // en la PPU y forzar los bytes a 0xFF directamente.
    //
    // TÉCNICA DE FUERZA BRUTA: Llenar toda el área de Tile Data (0x8000 - 0x97FF) con 0xFF.
    // Si la pantalla se vuelve negra, sabremos que la PPU SÍ lee la VRAM.
    // Si la pantalla sigue blanca, hay un error fundamental en el acceso a memoria de vídeo.
    //
    // Concepto: 0xFF en formato Tile (2bpp) = todos los píxeles en Color 3 (Negro).
    // Como el Tilemap por defecto (0x9800) está inicializado a ceros (Tile ID 0),
    // si convertimos el Tile 0 en un bloque negro, toda la pantalla debería volverse negra.
    //
    // Fuente: Pan Docs - "Tile Data", "Tile Map"
    /*
    printf("[MMU] INUNDANDO VRAM CON 0xFF (NEGRO) PARA DIAGNÓSTICO...\n");
    for (int i = 0x8000; i < 0x9800; ++i) {
        memory_[i] = 0xFF;
    }
    */
    // --- Step 0355: Verificación de Inicialización de VRAM ---
    // Verificar el estado de VRAM inmediatamente después de la inicialización
    int non_zero_bytes = 0;
    for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
        uint8_t byte = memory_[addr];
        if (byte != 0x00) {
            non_zero_bytes++;
        }
    }
    
    printf("[MMU-VRAM-INIT] VRAM initialized | Non-zero bytes: %d/6144 (%.2f%%)\n",
           non_zero_bytes, (non_zero_bytes * 100.0) / 6144);
    
    if (non_zero_bytes < 200) {
        printf("[MMU-VRAM-INIT] ⚠️ ADVERTENCIA: VRAM está vacía después de la inicialización!\n");
    }
    
    // Verificar estado de VRAM en este punto (después de la inicialización)
    // Nota: check_vram_state_at_point() requiere que memory_ esté inicializado,
    // así que lo llamamos después de que todo esté listo
    // -----------------------------------------
}

MMU::~MMU() {
    // std::vector se libera automáticamente
}

uint8_t MMU::read(uint16_t addr) const {
    // Asegurar que la dirección esté en el rango válido (0x0000-0xFFFF)
    addr &= 0xFFFF;
    
    // --- Step 0401: Boot ROM Mapping ---
    // Si la Boot ROM está habilitada, mapearla sobre el rango de la ROM del cartucho
    if (boot_rom_enabled_ && !boot_rom_.empty()) {
        // DMG Boot ROM: 256 bytes (0x0000-0x00FF)
        if (boot_rom_.size() == 256 && addr < 0x0100) {
            return boot_rom_[addr];
        }
        // CGB Boot ROM: 2304 bytes (0x0000-0x00FF + 0x0200-0x08FF)
        else if (boot_rom_.size() == 2304) {
            if (addr < 0x0100) {
                return boot_rom_[addr];
            } else if (addr >= 0x0200 && addr < 0x0900) {
                // Offset en Boot ROM: primeros 256 bytes están en 0x0000-0x00FF
                // siguientes 2048 bytes están en 0x0200-0x08FF
                return boot_rom_[256 + (addr - 0x0200)];
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0239: IMPLEMENTACIÓN DE ECHO RAM ---
    // Echo RAM (0xE000-0xFDFF) es un espejo de WRAM (0xC000-0xDDFF)
    // En el hardware real, acceder a 0xE000-0xFDFF accede físicamente a 0xC000-0xDDFF
    // Fuente: Pan Docs - Memory Map, Echo RAM
    if (addr >= 0xE000 && addr <= 0xFDFF) {
        addr = addr - 0x2000;  // Redirigir a WRAM: 0xE645 -> 0xC645
    }
    // -----------------------------------------
    
    // CRÍTICO: El registro STAT (0xFF41) tiene bits de solo lectura (0-2)
    // que son actualizados dinámicamente por la PPU. La MMU es la dueña de la memoria,
    // así que construimos el valor de STAT combinando:
    // - Bits escribibles (3-7) desde la memoria
    // - Bits de solo lectura (0-2) desde el estado actual de la PPU
    if (addr == 0xFF41) {
        if (ppu_ != nullptr) {
            // Leer el valor base de STAT (bits escribibles 3-7) de la memoria
            // Los bits 0-2 son de solo lectura y se actualizan dinámicamente
            uint8_t stat_base = memory_[addr];
            
            // Obtener el modo actual de la PPU (bits 0-1)
            uint8_t mode = static_cast<uint8_t>(ppu_->get_mode()) & 0x03;
            
            // Calcular LYC=LY Coincidence Flag (bit 2)
            uint8_t ly = ppu_->get_ly();
            uint8_t lyc = ppu_->get_lyc();
            uint8_t lyc_match = ((ly & 0xFF) == (lyc & 0xFF)) ? 0x04 : 0x00;
            
            // Combinar: bits escribibles (3-7) | modo actual (0-1) | LYC match (2)
            // Preservamos los bits 3-7 de la memoria (configurables por el software)
            // y actualizamos los bits 0-2 dinámicamente desde la PPU
            uint8_t result = (stat_base & 0xF8) | mode | lyc_match;
            
            return result;
        }
        
        // Si la PPU no está conectada, devolver valor por defecto
        // (modo 2 = OAM Search, que es el estado inicial)
        return 0x02;
    }
    
    // CRÍTICO: El registro DIV (0xFF04) es actualizado dinámicamente por el Timer
    // La MMU es la dueña de la memoria, así que leemos el valor desde el Timer
    if (addr == 0xFF04) {
        // --- Step 0276: Monitor de Registros de Tiempo (DIV) ---
        // Si el juego está esperando que el registro DIV cambie, necesitamos confirmar
        // que nuestro Timer lo está incrementando. Solo registramos las primeras 10
        // lecturas para no saturar el log.
        static int div_read_count = 0;
        if (div_read_count < 10) {
            // printf("[TIMER-READ] DIV leido en PC:0x%04X\n", debug_current_pc);
            div_read_count++;
        }
        // -----------------------------------------
        
        if (timer_ != nullptr) {
            return timer_->read_div();
        }
        // Si el Timer no está conectado, devolver valor por defecto
        return 0x00;
    }
    
    // CRÍTICO: Los registros TIMA (0xFF05), TMA (0xFF06) y TAC (0xFF07) son controlados por el Timer
    // Estos registros pueden ser leídos y escritos por el juego, pero están almacenados
    // en el hardware del Timer, no en la memoria
    if (addr == 0xFF05) {
        if (timer_ != nullptr) {
            return timer_->read_tima();
        }
        return 0x00;
    }
    
    if (addr == 0xFF06) {
        if (timer_ != nullptr) {
            return timer_->read_tma();
        }
        return 0x00;
    }
    
    if (addr == 0xFF07) {
        if (timer_ != nullptr) {
            return timer_->read_tac();
        }
        return 0x00;
    }
    
    // --- Step 0470: Watch de lecturas de IO (solo contadores) ---
    // Direcciones IO a monitorear
    const uint16_t io_addrs[] = {
        0xFF00,  // JOYP
        0xFF41,  // STAT
        0xFF44,  // LY
        0xFF0F,  // IF
        0xFFFF,  // IE
        0xFF4D,  // KEY1 (CGB)
        0xFF4F,  // VBK (CGB)
        0xFF70   // SVBK (CGB)
    };
    
    for (uint16_t io_addr : io_addrs) {
        if (addr == io_addr) {
            io_read_counts[io_addr]++;
            break;  // Solo contar una vez
        }
    }
    // -----------------------------------------
    
    // CRÍTICO: El registro P1 (0xFF00) es controlado por el Joypad
    // La CPU escribe en P1 para seleccionar qué fila de botones leer, y lee
    // el estado de los botones de la fila seleccionada
    if (addr == 0xFF00) {
        // --- Step 0480: Fix mínimo JOYP - bits 6-7 siempre leen como 1 ---
        uint8_t p1_value = 0xFF;  // Default: todos los bits en 1 (no presionados)
        
        if (joypad_ != nullptr) {
            p1_value = joypad_->read_p1();
            // Asegurar bits 6-7 siempre en 1 (según Pan Docs)
            p1_value |= 0xC0;
        }
        
        // --- Step 0380: Instrumentación de Lecturas de P1 (0xFF00) ---
        static int p1_read_count = 0;
        if (p1_read_count < 50) {
            p1_read_count++;
            printf("[MMU-JOYP-READ] PC:0x%04X | Read P1 = 0x%02X\n",
                   debug_current_pc, p1_value);
        }
        // -------------------------------------------
        
        // --- Step 0481: Tracking de JOYP reads desde programa ---
        if (!irq_poll_active_) {  // Solo reads desde programa, no desde cpu_poll
            joyp_read_count_program++;
            last_joyp_read_pc = debug_current_pc;
            last_joyp_read_value = p1_value;
        }
        // -----------------------------------------
        
        // --- Step 0484: JOYP Read Select Bits Tracking ---
        if (joypad_ != nullptr) {
            // Obtener bits de selección del latch actual (del Joypad)
            uint8_t latch = joypad_->get_p1_register();
            joyp_last_read_select_bits_ = (latch >> 4) & 0x03;  // bits 4-5
        }
        joyp_last_read_low_nibble_ = p1_value & 0x0F;  // bits 0-3
        // -----------------------------------------
        
        // --- Step 0485: JOYP Access Trace (gated por VIBOY_DEBUG_JOYP_TRACE=1) ---
        bool debug_joyp_trace = (std::getenv("VIBOY_DEBUG_JOYP_TRACE") != nullptr && 
                                  std::string(std::getenv("VIBOY_DEBUG_JOYP_TRACE")) == "1");
        if (debug_joyp_trace && !irq_poll_active_) {  // Solo program, no CPU polling
            JOYPTraceEvent event;
            event.type = JOYPTraceEvent::READ;
            event.pc = debug_current_pc;
            event.value_read = p1_value;
            
            // Obtener bits de selección del latch actual (del Joypad)
            if (joypad_ != nullptr) {
                uint8_t latch = joypad_->get_p1_register();
                event.select_bits = (latch >> 4) & 0x03;  // Bits 4-5
            } else {
                event.select_bits = 0x03;  // Ninguno seleccionado por defecto
            }
            
            event.low_nibble_read = p1_value & 0x0F;  // Bits 0-3
            event.timestamp = 0;  // TODO: Necesitamos exponer total_cycles_ o usar otro contador
            
            joyp_trace_.push_back(event);
            if (joyp_trace_.size() > JOYP_TRACE_SIZE) {
                joyp_trace_.erase(joyp_trace_.begin());
            }
            
            // Contadores por tipo de selección
            if (event.select_bits == 0x00) {  // Ambos seleccionados (P14=0, P15=0)
                // No contamos ambos, solo uno u otro
            } else if ((event.select_bits & 0x01) == 0) {  // P14=0 (buttons)
                joyp_reads_with_buttons_selected_count_++;
            } else if ((event.select_bits & 0x02) == 0) {  // P15=0 (dpad)
                joyp_reads_with_dpad_selected_count_++;
            } else {  // 0x03 (ninguno seleccionado)
                joyp_reads_with_none_selected_count_++;
            }
        }
        // -----------------------------------------
        
        return p1_value;
    }
    
    // --- Step 0383: Instrumentación de MMIO Crítica (Solo en Wait-Loop Bank 28) ---
    // Detectar si estamos en el bucle de espera (Bank 28, PC 0x614D-0x6153)
    // y loguear accesos a registros clave que podrían ser la condición de salida.
    // Clean Room: basado en Pan Docs (secciones de interrupciones, timer, PPU).
    bool in_wait_loop = (current_rom_bank_ == 28 && debug_current_pc >= 0x614D && debug_current_pc <= 0x6153);
    
    if (in_wait_loop) {
        static int mmio_read_count_step383 = 0;
        bool should_log = (mmio_read_count_step383 < 220);  // Límite para no saturar
        
        // Registros críticos de PPU
        if (addr == 0xFF44 && should_log) {  // LY
            uint8_t ly_val = (ppu_ != nullptr) ? ppu_->get_ly() : memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> LY(0xFF44) = 0x%02X (%d)\n", debug_current_pc, ly_val, ly_val);
            mmio_read_count_step383++;
        } else if (addr == 0xFF41 && should_log) {  // STAT
            uint8_t stat_val = memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> STAT(0xFF41) = 0x%02X (Mode:%d)\n", 
                   debug_current_pc, stat_val, stat_val & 0x03);
            mmio_read_count_step383++;
        } else if (addr == 0xFF40 && should_log) {  // LCDC
            printf("[WAIT-MMIO-READ] PC:0x%04X -> LCDC(0xFF40) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        }
        // Registros de interrupciones
        else if (addr == 0xFF0F && should_log) {  // IF
            printf("[WAIT-MMIO-READ] PC:0x%04X -> IF(0xFF0F) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        } else if (addr == 0xFFFF && should_log) {  // IE
            printf("[WAIT-MMIO-READ] PC:0x%04X -> IE(0xFFFF) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        }
        // Registros de Timer (Step 0414: usar métodos del Timer para valores reales)
        else if (addr == 0xFF04 && should_log) {  // DIV
            uint8_t div_val = (timer_ != nullptr) ? timer_->read_div() : memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> DIV(0xFF04) = 0x%02X (%d)\n", debug_current_pc, div_val, div_val);
            mmio_read_count_step383++;
        } else if (addr == 0xFF05 && should_log) {  // TIMA
            uint8_t tima_val = (timer_ != nullptr) ? timer_->read_tima() : memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> TIMA(0xFF05) = 0x%02X\n", debug_current_pc, tima_val);
            mmio_read_count_step383++;
        } else if (addr == 0xFF06 && should_log) {  // TMA
            uint8_t tma_val = (timer_ != nullptr) ? timer_->read_tma() : memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> TMA(0xFF06) = 0x%02X\n", debug_current_pc, tma_val);
            mmio_read_count_step383++;
        } else if (addr == 0xFF07 && should_log) {  // TAC
            uint8_t tac_val = (timer_ != nullptr) ? timer_->read_tac() : memory_[addr];
            printf("[WAIT-MMIO-READ] PC:0x%04X -> TAC(0xFF07) = 0x%02X\n", debug_current_pc, tac_val);
            mmio_read_count_step383++;
        }
        // DMA y Serial
        else if (addr == 0xFF46 && should_log) {  // DMA
            printf("[WAIT-MMIO-READ] PC:0x%04X -> DMA(0xFF46) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        } else if (addr == 0xFF01 && should_log) {  // SB (Serial Data)
            printf("[WAIT-MMIO-READ] PC:0x%04X -> SB(0xFF01) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        } else if (addr == 0xFF02 && should_log) {  // SC (Serial Control)
            printf("[WAIT-MMIO-READ] PC:0x%04X -> SC(0xFF02) = 0x%02X\n", debug_current_pc, memory_[addr]);
            mmio_read_count_step383++;
        }
    }
    // -----------------------------------------
    
    // --- Step 0226: DEBUG DE LY (Registro 0xFF44) ---
    // Instrumentación para verificar si la CPU está leyendo correctamente el registro LY
    // y si este valor cambia con el tiempo. Esto ayudará a diagnosticar por qué el
    // bucle de espera de V-Blank nunca termina.
    // 
    // IMPORTANTE: Este printf generará MUCHAS líneas de salida. Para activarlo,
    // descomenta la siguiente línea y redirige la salida a un archivo:
    // python main.py roms/tetris.gb > ly_log.txt 2>&1
    //
    // Fuente: Pan Docs - "LCD Y-Coordinate (LY)"
    if (addr == 0xFF44) {
        if (ppu_ != nullptr) {
            uint8_t val = ppu_->get_ly();
            
            // --- Step 0438 T2: Ring buffer de LY interno vs retornado ---
            // Capturar cuando PC está en el loop de Pokémon (0x006B, 0x006D, 0x006F)
            if (debug_current_pc == 0x006B || debug_current_pc == 0x006D || debug_current_pc == 0x006F) {
                struct LYReadSample {
                    uint16_t pc;
                    uint64_t global_cycles;  // Ciclos globales (si disponible)
                    uint64_t ppu_clock;      // Clock interno de PPU
                    uint16_t ly_internal;    // ly_ raw
                    uint8_t ly_returned;     // Valor retornado
                };
                
                static LYReadSample ring_buffer[64];
                static int ring_idx = 0;
                static uint32_t sample_count = 0;
                static bool summary_printed = false;
                
                // Capturar muestra
                ring_buffer[ring_idx].pc = debug_current_pc;
                ring_buffer[ring_idx].global_cycles = 0;  // No tenemos acceso directo a ciclos globales aquí
                ring_buffer[ring_idx].ppu_clock = ppu_->get_ppu_clock();
                ring_buffer[ring_idx].ly_internal = ppu_->get_ly_internal();
                ring_buffer[ring_idx].ly_returned = val;
                
                ring_idx = (ring_idx + 1) % 64;
                sample_count++;
                
                // Imprimir resumen cada 10000 lecturas
                if (sample_count % 10000 == 0 && !summary_printed) {
                    printf("\n[STEP0438-T2-LY-RING] ========== RING BUFFER SUMMARY (sample #%u) ==========\n", sample_count);
                    
                    // Calcular estadísticas
                    std::set<uint8_t> unique_ly_returned;
                    std::set<uint16_t> unique_ly_internal;
                    uint8_t min_ly = 255, max_ly = 0;
                    
                    for (int i = 0; i < 64; i++) {
                        unique_ly_returned.insert(ring_buffer[i].ly_returned);
                        unique_ly_internal.insert(ring_buffer[i].ly_internal);
                        if (ring_buffer[i].ly_returned < min_ly) min_ly = ring_buffer[i].ly_returned;
                        if (ring_buffer[i].ly_returned > max_ly) max_ly = ring_buffer[i].ly_returned;
                    }
                    
                    printf("[STEP0438-T2-LY-RING] Unique LY returned: %zu | Range: %u..%u\n",
                           unique_ly_returned.size(), min_ly, max_ly);
                    printf("[STEP0438-T2-LY-RING] Unique LY internal: %zu\n", unique_ly_internal.size());
                    printf("[STEP0438-T2-LY-RING] Includes 0x91 (145)? %s\n",
                           unique_ly_returned.count(0x91) > 0 ? "YES" : "NO");
                    
                    // Mostrar 5 muestras representativas
                    printf("[STEP0438-T2-LY-RING] 5 samples from ring buffer:\n");
                    printf("[STEP0438-T2-LY-RING] PC    PPU_CLK  LY_INT  LY_RET\n");
                    for (int i = 0; i < 5; i++) {
                        int idx = (ring_idx - 5 + i + 64) % 64;
                        printf("[STEP0438-T2-LY-RING] %04X  %6llu   %3u     %3u (0x%02X)\n",
                               ring_buffer[idx].pc,
                               ring_buffer[idx].ppu_clock,
                               ring_buffer[idx].ly_internal,
                               ring_buffer[idx].ly_returned,
                               ring_buffer[idx].ly_returned);
                    }
                    printf("[STEP0438-T2-LY-RING] =======================================================\n\n");
                    
                    // Solo imprimir hasta 3 veces
                    if (sample_count >= 30000) {
                        summary_printed = true;
                    }
                }
            }
            // -----------------------------------------
            
            // DESCOMENTAR PARA ACTIVAR DEBUG:
            // printf("[MMU] Read LY: %d\n", val);
            
            // --- Step 0474: Instrumentación quirúrgica de LY ---
            last_ly_read_ = val;
            if (val < ly_read_min_) {
                ly_read_min_ = val;
            }
            if (val > ly_read_max_) {
                ly_read_max_ = val;
            }
            
            // --- Step 0479: Contador de cambios de LY por frame ---
            static uint32_t last_ly_frame = 0;
            uint32_t current_frame = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
            if (current_frame != last_ly_frame) {
                ly_changes_this_frame_ = 0;
                last_ly_frame = current_frame;
            }
            ly_changes_this_frame_++;
            // -----------------------------------------
            
            // Log gated (solo si VIBOY_DEBUG_IO=1)
            bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                             std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
            if (debug_io) {
                static int ly_track_log_count = 0;
                if (ly_track_log_count < 50) {
                    ly_track_log_count++;
                    printf("[LY-TRACK] min=%u max=%u last=%u\n", 
                           ly_read_min_, ly_read_max_, last_ly_read_);
                }
            }
            
            return val;
        }
        return 0;
    }
    
    // --- Step 0413: STAT dinámico (Registro 0xFF41) ---
    // STAT debe reflejar el modo actual de la PPU (bits 0-1) y la coincidencia LYC=LY (bit 2).
    // Los bits 3-6 son máscaras de interrupción escritas por la CPU, y el bit 7 es siempre 1.
    // Fuente: Pan Docs - "LCD Status Register (FF41 - STAT)"
    if (addr == 0xFF41) {
        uint8_t stat_value;
        if (ppu_ != nullptr) {
            stat_value = ppu_->get_stat();
        } else {
            // Si no hay PPU, devolver valor por defecto (modo 0, sin coincidencia, bit 7 = 1)
            stat_value = (memory_[addr] & 0xF8) | 0x80;
        }
        
        // --- Step 0474: Instrumentación quirúrgica de STAT ---
        last_stat_read_ = stat_value;
        
        // --- Step 0479: Contador de cambios de modo STAT por frame ---
        static uint32_t last_stat_mode_frame = 0;
        static uint8_t last_stat_mode = 0;
        uint32_t current_frame = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
        uint8_t current_mode = stat_value & 0x03;
        
        if (current_frame != last_stat_mode_frame) {
            stat_mode_changes_count_ = 0;
            last_stat_mode_frame = current_frame;
            last_stat_mode = current_mode;
        } else if (current_mode != last_stat_mode) {
            stat_mode_changes_count_++;
            last_stat_mode = current_mode;
        }
        // -----------------------------------------
        
        // Log gated (solo si VIBOY_DEBUG_IO=1)
        bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                         std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
        if (debug_io) {
            static int stat_track_log_count = 0;
            if (stat_track_log_count < 50) {
                stat_track_log_count++;
                printf("[STAT-TRACK] last=0x%02X\n", stat_value);
            }
        }
        
        return stat_value;
    }
    
    // --- ROM / Banking ---
    if (!rom_data_.empty()) {
        if (addr < 0x4000) {
            size_t rom_addr = static_cast<size_t>(bank0_rom_) * 0x4000 + addr;
            if (rom_addr < rom_data_.size()) {
                return rom_data_[rom_addr];
            }
            return 0xFF;
        } else if (addr < 0x8000) {
            size_t rom_addr = static_cast<size_t>(bankN_rom_) * 0x4000 + (addr - 0x4000);
            if (rom_addr < rom_data_.size()) {
                uint8_t val = rom_data_[rom_addr];
                
                // --- Step 0407: Monitor acotado de reads de ROM banqueada ---
                // Reactivado pero con límite estricto para diagnóstico de banking
                // Solo logueamos cuando hay cambios de banco o en muestra inicial
                // Fuente: Pan Docs - "ROM Banking"
                static int bank_read_count = 0;
                static uint16_t last_logged_bank = 0xFFFF;
                const int BANK_READ_LIMIT = 150;  // Límite para evitar saturación
                
                if (bank_read_count < BANK_READ_LIMIT) {
                    // Loguear: (1) primeras 30 lecturas, (2) cuando bank cambia (primeras 5 de cada bank)
                    bool should_log = (bank_read_count < 30) || 
                                     (bankN_rom_ != last_logged_bank && bank_read_count < 100);
                    
                    if (should_log) {
                        printf("[BANK-READ-0407] addr:0x%04X bank:%d offset:0x%04X -> val:0x%02X | PC:0x%04X\n",
                               addr, bankN_rom_, (uint16_t)(addr - 0x4000), val, debug_current_pc);
                        bank_read_count++;
                        last_logged_bank = bankN_rom_;
                    }
                }
                
                return val;
            }
            return 0xFF;
        }
    }

    // --- Step 0389: CGB VRAM Banking ---
    // VRAM (0x8000-0x9FFF) tiene 2 bancos en CGB.
    // El registro VBK (0xFF4F) bit 0 selecciona qué banco ve la CPU.
    // Fuente: Pan Docs - CGB Registers, VRAM Banks
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        uint16_t offset = addr - 0x8000;  // Offset dentro del banco (0x0000-0x1FFF)
        uint8_t vram_value = (vram_bank_ == 0) ? vram_bank0_[offset] : vram_bank1_[offset];
        
        // --- Step 0289: Monitor de Lecturas de VRAM ([VRAM-READ]) ---
        static int vram_read_count = 0;
        if (vram_read_count < 100) {  // Límite para evitar saturación
            printf("[VRAM-READ] Read %04X -> %02X (PC:0x%04X Bank:%d VRAMBank:%d)\n",
                   addr, vram_value, debug_current_pc, current_rom_bank_, vram_bank_);
            vram_read_count++;
        }
        return vram_value;
    }
    
    // --- Step 0389: Registro VBK (0xFF4F) - VRAM Bank Select ---
    // Lectura de VBK devuelve 0xFE | banco_actual (bit 0)
    // Bits 1-7: siempre 1 (no implementados)
    // Bit 0: banco actual (0 o 1)
    // Fuente: Pan Docs - CGB Registers, FF4F - VBK
    if (addr == 0xFF4F) {
        return 0xFE | (vram_bank_ & 0x01);
    }
    
    // --- Step 0390: Lectura de Registros HDMA (0xFF51-0xFF55) ---
    // Fuente: Pan Docs - CGB Registers, HDMA
    if (addr >= 0xFF51 && addr <= 0xFF54) {
        // HDMA1-4 son write-only; lectura retorna 0xFF
        return 0xFF;
    }
    if (addr == 0xFF55) {
        // HDMA5: Retorna estado del DMA
        // - Si HDMA inactivo: 0xFF
        // - Si HDMA activo: bits 0-6 = bloques restantes - 1, bit 7 = 0
        if (hdma_active_) {
            uint8_t blocks_remaining = (hdma_length_remaining_ / 0x10);
            if (blocks_remaining > 0) blocks_remaining--;
            return (blocks_remaining & 0x7F);  // bit 7 = 0 indica activo
        }
        return 0xFF;  // Inactivo
    }
    
    // --- Step 0390: Lectura de Paletas CGB (0xFF68-0xFF6B) ---
    // Fuente: Pan Docs - CGB Registers, Palettes
    if (addr == 0xFF68) {
        // BCPS (BG Color Palette Specification)
        // Retorna: índice actual (bits 0-5) + autoincrement (bit 7) + bit 6 = 1
        return bg_palette_index_ | 0x40;
    }
    if (addr == 0xFF69) {
        // BCPD (BG Color Palette Data)
        // Retorna el byte actual de la paleta BG
        uint8_t index = bg_palette_index_ & 0x3F;
        return bg_palette_data_[index];
    }
    if (addr == 0xFF6A) {
        // OCPS (OBJ Color Palette Specification)
        // Retorna: índice actual (bits 0-5) + autoincrement (bit 7) + bit 6 = 1
        return obj_palette_index_ | 0x40;
    }
    if (addr == 0xFF6B) {
        // OCPD (OBJ Color Palette Data)
        // Retorna el byte actual de la paleta OBJ
        uint8_t index = obj_palette_index_ & 0x3F;
        return obj_palette_data_[index];
    }
    
    // --- RAM Externa (0xA000-0xBFFF) ---
    if (addr >= 0xA000 && addr <= 0xBFFF) {
        if (!ram_enabled_ || ram_data_.empty()) {
            return 0xFF;
        }

        size_t bank_index = 0;
        switch (mbc_type_) {
            case MBCType::MBC1:
                bank_index = (mbc1_mode_ == 1) ? ram_bank_ : 0;
                break;
            case MBCType::MBC3:
                if (mbc3_rtc_reg_ >= 0x08 && mbc3_rtc_reg_ <= 0x0C) {
                    // --- Step 0409: RTC Read ---
                    rtc_update();  // Actualizar RTC antes de leer
                    switch (mbc3_rtc_reg_) {
                        case 0x08: return rtc_seconds_;
                        case 0x09: return rtc_minutes_;
                        case 0x0A: return rtc_hours_;
                        case 0x0B: return rtc_day_low_;
                        case 0x0C: return rtc_day_high_;
                        default:   return 0xFF;
                    }
                }
                bank_index = ram_bank_;
                break;
            case MBCType::MBC5:
                bank_index = ram_bank_;
                break;
            case MBCType::MBC2:
                bank_index = 0;
                break;
            default:
                bank_index = 0;
                break;
        }

        size_t offset = bank_index * ram_bank_size_ + (addr - 0xA000);
        if (offset < ram_data_.size()) {
            if (mbc_type_ == MBCType::MBC2) {
                // RAM de 4 bits: los bits altos suelen leerse como 1
                return 0xF0 | (ram_data_[offset] & 0x0F);
            }
            return ram_data_[offset];
        }
        return 0xFF;
    }

    static int d732_read_log_count = 0;
    if (addr == 0xD732 && d732_read_log_count < 20) {
        printf("[WRAM] Read  D732 -> %02X PC:%04X\n", memory_[addr], debug_current_pc);
        d732_read_log_count++;
    }

    // --- Step 0385: Trazado de MMIO/RAM durante Wait-Loop ---
    // Loguear accesos a MMIO, HRAM y WRAM (direcciones repetidas) cuando el wait-loop está activo
    if (waitloop_trace_active_) {
        // MMIO (0xFF00-0xFFFF) - máx 300 líneas
        if (addr >= 0xFF00 && addr <= 0xFFFF && waitloop_mmio_count_ < 300) {
            uint8_t val = memory_[addr];
            // Nombres de registros clave (Pan Docs)
            const char* reg_name = "";
            if (addr == 0xFF44) reg_name = "LY";
            else if (addr == 0xFF41) reg_name = "STAT";
            else if (addr == 0xFF40) reg_name = "LCDC";
            else if (addr == 0xFF0F) reg_name = "IF";
            else if (addr == 0xFFFF) reg_name = "IE";
            else if (addr == 0xFF04) reg_name = "DIV";
            else if (addr == 0xFF05) reg_name = "TIMA";
            else if (addr == 0xFF4F) reg_name = "VBK";
            else if (addr == 0xFF4D) reg_name = "KEY1";
            else if (addr >= 0xFF51 && addr <= 0xFF55) reg_name = "HDMA";
            else if (addr == 0xFF68 || addr == 0xFF69) reg_name = "BGPAL";
            else if (addr == 0xFF6A || addr == 0xFF6B) reg_name = "OBPAL";
            
            printf("[WAITLOOP-MMIO] Read 0x%04X (%s) -> 0x%02X\n", addr, reg_name, val);
            waitloop_mmio_count_++;
        }
        
        // HRAM (0xFF80-0xFFFE) - máx 200 líneas
        else if (addr >= 0xFF80 && addr <= 0xFFFE && waitloop_ram_count_ < 200) {
            uint8_t val = memory_[addr];
            printf("[WAITLOOP-RAM] Read HRAM 0x%04X -> 0x%02X\n", addr, val);
            waitloop_ram_count_++;
        }
        
        // WRAM (0xC000-0xDFFF) - solo direcciones "calientes" (top 8), máx 200 líneas totales
        else if (addr >= 0xC000 && addr <= 0xDFFF && waitloop_ram_count_ < 200) {
            // Mantener un contador simple de accesos por dirección (solo las primeras 8 distintas)
            static std::map<uint16_t, int> wram_access_map;
            wram_access_map[addr]++;
            
            // Solo loguear si es una de las primeras 8 direcciones distintas accedidas
            if (wram_access_map.size() <= 8) {
                uint8_t val = memory_[addr];
                printf("[WAITLOOP-RAM] Read WRAM 0x%04X -> 0x%02X (accesos: %d)\n",
                       addr, val, wram_access_map[addr]);
                waitloop_ram_count_++;
            }
        }
    }
    
    // Trazado de MMIO durante VBlank ISR (similarsolo MMIO, sin límite interno aquí)
    if (vblank_isr_trace_active_) {
        if (addr >= 0xFF00 && addr <= 0xFFFF) {
            uint8_t val = memory_[addr];
            const char* reg_name = "";
            if (addr == 0xFF44) reg_name = "LY";
            else if (addr == 0xFF41) reg_name = "STAT";
            else if (addr == 0xFF40) reg_name = "LCDC";
            else if (addr == 0xFF0F) reg_name = "IF";
            else if (addr == 0xFFFF) reg_name = "IE";
            else if (addr == 0xFF4F) reg_name = "VBK";
            else if (addr == 0xFF4D) reg_name = "KEY1";
            else if (addr >= 0xFF51 && addr <= 0xFF55) reg_name = "HDMA";
            else if (addr == 0xFF68 || addr == 0xFF69) reg_name = "BGPAL";
            else if (addr == 0xFF6A || addr <= 0xFF6B) reg_name = "OBPAL";
            
            printf("[VBLANK-ISR-MMIO] Read 0x%04X (%s) -> 0x%02X\n", addr, reg_name, val);
        }
    }
    // -------------------------------------------
    
    // --- Step 0471: Instrumentación microscópica de IE read ---
    // --- Step 0475: Source Tagging para IE read ---
    if (addr == 0xFFFF) {  // IE
        uint8_t ie_value = memory_[addr];
        last_ie_read_value = ie_value;
        ie_read_count++;
        
        // Step 0475: Separar contadores según source (program vs cpu_poll)
        if (irq_poll_active_) {
            ie_reads_cpu_poll_++;
        } else {
            ie_reads_program_++;
        }
        
        // Comprobación debug (solo si VIBOY_DEBUG_PPU=1): Si hay writes pero el valor leído es 0x00, loggear
        // Step 0474: Eliminado [IE-DROP] por falsos positivos (ver plan Step 0474)
        
        return ie_value;
    }
    // -----------------------------------------
    
    // --- Step 0474: Instrumentación quirúrgica de IF (0xFF0F) read ---
    if (addr == 0xFF0F) {  // IF
        uint8_t if_value = memory_[addr];
        
        // CRÍTICO: Verificar que bits 5-7 leen como 1 (según Pan Docs, upper bits siempre leen 1)
        // Si memory_[0xFF0F] tiene bits 5-7 = 0, es un bug
        uint8_t upper_bits = if_value & 0xE0;  // Bits 5-7
        if (upper_bits != 0xE0) {
            // Bug detectado: upper bits no son 1
            static int if_upper_bits_bug_count = 0;
            if (if_upper_bits_bug_count < 10) {
                if_upper_bits_bug_count++;
                printf("[IF-BUG] Upper bits (5-7) no son 1: 0x%02X (debería ser 0x%02X)\n",
                       if_value, (if_value & 0x1F) | 0xE0);
            }
            // Corregir el valor leído (forzar bits 5-7 = 1)
            if_value = (if_value & 0x1F) | 0xE0;
        }
        
        if_read_count_++;
        last_if_read_val_ = if_value;
        
        // Step 0475: Separar contadores según source (program vs cpu_poll)
        if (irq_poll_active_) {
            if_reads_cpu_poll_++;
        } else {
            if_reads_program_++;
        }
        
        // Log gated (solo si VIBOY_DEBUG_IO=1 o VIBOY_DEBUG_IRQ=1)
        bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                         std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
        bool debug_irq = (std::getenv("VIBOY_DEBUG_IRQ") != nullptr && 
                          std::string(std::getenv("VIBOY_DEBUG_IRQ")) == "1");
        if (debug_io || debug_irq) {
            static int if_track_log_count = 0;
            if (if_track_log_count < 50) {
                if_track_log_count++;
                printf("[IF-TRACK] read: count=%u last=0x%02X | write: count=%u last=0x%02X PC=0x%04X\n",
                       if_read_count_, if_value, if_write_count_, last_if_write_val_, last_if_write_pc_);
            }
        }
        
        return if_value;
    }
    // -----------------------------------------
    
    // --- Step 0479: Instrumentación gated por I/O esperado ---
    // Solo si VIBOY_DEBUG_IO=1 y addr es el esperado
    bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                     std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
    if (debug_io && waits_on_addr_ != 0x0000 && addr == waits_on_addr_) {
        // Contador de reads desde programa (no cpu_poll)
        if (!irq_poll_active_) {
            waits_on_reads_program_++;
            last_waits_on_read_value_ = memory_[addr];
            last_waits_on_read_pc_ = debug_current_pc;
        }
    }
    // -----------------------------------------
    
    // --- Step 0480: Instrumentación HRAM[FF92] quirúrgica (gated por VIBOY_DEBUG_IO) ---
    // Mantener compatibilidad con tracking hardcoded
    if (addr == 0xFF92) {
        bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                         std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
        if (debug_io && !irq_poll_active_) {  // Solo reads desde programa
            hram_ff92_read_count_program_++;
            last_hram_ff92_read_pc_ = debug_current_pc;
            last_hram_ff92_read_value_ = memory_[addr];
        }
    }
    // -----------------------------------------
    
    // --- Step 0481: HRAM Watchlist Genérica (gated por VIBOY_DEBUG_HRAM) ---
    bool debug_hram = (std::getenv("VIBOY_DEBUG_HRAM") != nullptr && 
                       std::string(std::getenv("VIBOY_DEBUG_HRAM")) == "1");
    if (debug_hram && addr >= 0xFF80 && addr <= 0xFFFE && !irq_poll_active_) {
        // Verificar si addr está en watchlist
        for (auto& entry : hram_watchlist_) {
            if (entry.addr == addr) {
                entry.read_count_program++;
                entry.last_read_pc = debug_current_pc;
                entry.last_read_value = memory_[addr];
                break;
            }
        }
    }
    // -----------------------------------------
    
    // Resto de direcciones: memoria plana
    return memory_[addr];
}

void MMU::write(uint16_t addr, uint8_t value) {
    // Asegurar que la dirección esté en el rango válido
    addr &= 0xFFFF;

    // --- Step 0239: IMPLEMENTACIÓN DE ECHO RAM ---
    if (addr >= 0xE000 && addr <= 0xFDFF) {
        addr = addr - 0x2000;  // Redirigir a WRAM
    }

    value &= 0xFF;
    
    // --- Step 0436: Pokemon Loop Trace (Fase A) ---
    // Captura writes VRAM cuando PC está en el rango del loop stuck (0x36E2-0x36E7)
    if (pokemon_loop_trace_.active && addr >= 0x8000 && addr <= 0x9FFF) {
        uint16_t pc = debug_current_pc;
        if (pc >= 0x36E2 && pc <= 0x36E7) {
            // Actualizar ring buffer
            int idx = pokemon_loop_trace_.ring_idx;
            pokemon_loop_trace_.ring_buffer[idx] = {pc, addr, value, current_hl_value_};
            pokemon_loop_trace_.ring_idx = (idx + 1) % pokemon_loop_trace_.RING_SIZE;
            pokemon_loop_trace_.total_writes++;
            
            // Actualizar métricas
            if (addr < pokemon_loop_trace_.min_addr) {
                pokemon_loop_trace_.min_addr = addr;
            }
            if (addr > pokemon_loop_trace_.max_addr) {
                pokemon_loop_trace_.max_addr = addr;
            }
            
            // Actualizar bitset para unique addresses
            uint16_t offset = addr - 0x8000;  // 0x0000-0x1FFF
            int byte_idx = offset / 8;
            int bit_idx = offset % 8;
            if (byte_idx < (8192 / 8)) {
                uint8_t old_byte = pokemon_loop_trace_.addr_bitset[byte_idx];
                uint8_t new_bit = (1 << bit_idx);
                if ((old_byte & new_bit) == 0) {
                    // Nuevo bit único
                    pokemon_loop_trace_.unique_addr_count++;
                    pokemon_loop_trace_.addr_bitset[byte_idx] = old_byte | new_bit;
                }
            }
        }
    }
    
    // --- Step 0434: Instrumentación de Triage ---
    if (triage_.active) {
        // VRAM writes (0x8000-0x9FFF)
        if (addr >= 0x8000 && addr <= 0x9FFF) {
            triage_.vram_writes++;
            if (triage_.vram_sample_count < triage_.MAX_SAMPLES) {
                triage_.vram_samples[triage_.vram_sample_count++] = {debug_current_pc, addr, value};
            }
        }
        // OAM writes (0xFE00-0xFE9F)
        else if (addr >= 0xFE00 && addr <= 0xFE9F) {
            triage_.oam_writes++;
        }
        // IO writes críticos
        else if (addr >= 0xFF00 && addr <= 0xFFFF) {
            if (addr == 0xFF40) triage_.ff40_writes++;       // LCDC
            else if (addr == 0xFF47) triage_.ff47_writes++;  // BGP
            else if (addr == 0xFF50) triage_.ff50_writes++;  // BOOT
            else if (addr == 0xFF04) triage_.ff04_writes++;  // DIV
            else if (addr == 0xFF0F) triage_.ff0f_writes++;  // IF
            else if (addr == 0xFFFF) triage_.ffff_writes++;  // IE
            
            if (triage_.io_sample_count < triage_.MAX_SAMPLES) {
                triage_.io_samples[triage_.io_sample_count++] = {debug_current_pc, addr, value};
            }
        }
        // MBC1 banking writes (0x2000-0x7FFF)
        else if (addr >= 0x2000 && addr <= 0x7FFF) {
            triage_.mbc1_bank_writes++;
            if (triage_.mbc_sample_count < triage_.MAX_SAMPLES) {
                triage_.mbc_samples[triage_.mbc_sample_count++] = {debug_current_pc, addr, value};
            }
        }
    }
    
    // --- Step 0387: Trazado de Escrituras a FE00-FEFF (OAM/Unusable) ---
    // Detectar escrituras a la región OAM/no usable para diagnosticar corrupción
    static int fe_write_count = 0;
    if (addr >= 0xFE00 && addr <= 0xFEFF && fe_write_count < 60) {
        printf("[MMU-FE-WRITE] PC=0x%04X addr=0x%04X value=0x%02X Bank=%d",
               debug_current_pc, addr, value, get_current_rom_bank());
        
        // Distinguir entre OAM válido (FE00-FE9F) y región no usable (FEA0-FEFF)
        if (addr >= 0xFEA0) {
            printf(" ⚠️ UNUSABLE REGION\n");
        } else {
            printf(" (OAM valid)\n");
        }
        fe_write_count++;
    }
    // -------------------------------------------
    
    // --- Step 0385: Trazado de Escrituras durante Wait-Loop y VBlank ISR ---
    // Loguear escrituras a MMIO, HRAM y WRAM cuando los trazados están activos
    if (waitloop_trace_active_) {
        // MMIO (0xFF00-0xFFFF) - máx 300 líneas
        if (addr >= 0xFF00 && addr <= 0xFFFF && waitloop_mmio_count_ < 300) {
            const char* reg_name = "";
            if (addr == 0xFF44) reg_name = "LY";
            else if (addr == 0xFF41) reg_name = "STAT";
            else if (addr == 0xFF40) reg_name = "LCDC";
            else if (addr == 0xFF0F) reg_name = "IF";
            else if (addr == 0xFFFF) reg_name = "IE";
            else if (addr == 0xFF04) reg_name = "DIV";
            else if (addr == 0xFF4F) reg_name = "VBK";
            else if (addr == 0xFF4D) reg_name = "KEY1";
            else if (addr >= 0xFF51 && addr <= 0xFF55) reg_name = "HDMA";
            else if (addr == 0xFF68 || addr == 0xFF69) reg_name = "BGPAL";
            else if (addr == 0xFF6A || addr == 0xFF6B) reg_name = "OBPAL";
            
            printf("[WAITLOOP-MMIO] Write 0x%04X (%s) <- 0x%02X\n", addr, reg_name, value);
            waitloop_mmio_count_++;
        }
        
        // HRAM (0xFF80-0xFFFE) - máx 200 líneas
        else if (addr >= 0xFF80 && addr <= 0xFFFE && waitloop_ram_count_ < 200) {
            printf("[WAITLOOP-RAM] Write HRAM 0x%04X <- 0x%02X\n", addr, value);
            waitloop_ram_count_++;
        }
        
        // WRAM (0xC000-0xDFFF) - solo direcciones "calientes", máx 200 líneas totales
        else if (addr >= 0xC000 && addr <= 0xDFFF && waitloop_ram_count_ < 200) {
            static std::map<uint16_t, int> wram_write_map;
            wram_write_map[addr]++;
            
            if (wram_write_map.size() <= 8) {
                printf("[WAITLOOP-RAM] Write WRAM 0x%04X <- 0x%02X (accesos: %d)\n",
                       addr, value, wram_write_map[addr]);
                waitloop_ram_count_++;
            }
        }
    }
    
    // Trazado de escrituras durante VBlank ISR (especialmente HDMA, VBK, paletas, IF clears)
    if (vblank_isr_trace_active_) {
        if (addr >= 0xFF00 && addr <= 0xFFFF) {
            const char* reg_name = "";
            if (addr == 0xFF40) reg_name = "LCDC";
            else if (addr == 0xFF0F) reg_name = "IF";
            else if (addr == 0xFFFF) reg_name = "IE";
            else if (addr == 0xFF4F) reg_name = "VBK";
            else if (addr == 0xFF4D) reg_name = "KEY1";
            else if (addr >= 0xFF51 && addr <= 0xFF55) reg_name = "HDMA";
            else if (addr == 0xFF68 || addr == 0xFF69) reg_name = "BGPAL";
            else if (addr == 0xFF6A || addr == 0xFF6B) reg_name = "OBPAL";
            
            printf("[VBLANK-ISR-MMIO] Write 0x%04X (%s) <- 0x%02X\n", addr, reg_name, value);
        }
        
        // Escrituras a HRAM/WRAM (flags del engine)
        if ((addr >= 0xFF80 && addr <= 0xFFFE) || (addr >= 0xC000 && addr <= 0xDFFF)) {
            const char* zone = (addr >= 0xFF80) ? "HRAM" : "WRAM";
            printf("[VBLANK-ISR-RAM] Write %s 0x%04X <- 0x%02X\n", zone, addr, value);
        }
    }
    // -------------------------------------------
    
    // --- Step 0383: Instrumentación de Escrituras MMIO Críticas (Solo en Wait-Loop Bank 28) ---
    // Detectar escrituras a registros críticos cuando estamos en el bucle de espera.
    // Clean Room: basado en Pan Docs (secciones de interrupciones, timer, PPU).
    bool in_wait_loop_write = (current_rom_bank_ == 28 && debug_current_pc >= 0x614D && debug_current_pc <= 0x6153);
    
    if (in_wait_loop_write && addr >= 0xFF00) {  // Solo MMIO
        static int mmio_write_count_step383 = 0;
        bool should_log = (mmio_write_count_step383 < 220);
        
        // Registros críticos de PPU
        if ((addr == 0xFF40 || addr == 0xFF41 || addr == 0xFF44) && should_log) {
            printf("[WAIT-MMIO-WRITE] PC:0x%04X -> Addr(0x%04X) = 0x%02X\n", debug_current_pc, addr, value);
            mmio_write_count_step383++;
        }
        // Registros de interrupciones
        else if ((addr == 0xFF0F || addr == 0xFFFF) && should_log) {
            printf("[WAIT-MMIO-WRITE] PC:0x%04X -> Addr(0x%04X) = 0x%02X (Interrupts)\n", debug_current_pc, addr, value);
            mmio_write_count_step383++;
        }
        // Registros de Timer
        else if ((addr >= 0xFF04 && addr <= 0xFF07) && should_log) {
            printf("[WAIT-MMIO-WRITE] PC:0x%04X -> Addr(0x%04X) = 0x%02X (Timer)\n", debug_current_pc, addr, value);
            mmio_write_count_step383++;
        }
        // DMA y Serial
        else if ((addr == 0xFF46 || addr == 0xFF01 || addr == 0xFF02) && should_log) {
            printf("[WAIT-MMIO-WRITE] PC:0x%04X -> Addr(0x%04X) = 0x%02X\n", debug_current_pc, addr, value);
            mmio_write_count_step383++;
        }
    }
    // -----------------------------------------
    
    // --- Step 0470: Contadores de writes a IE/IF ---
    // --- Step 0475: Source Tagging para IE write (siempre PROGRAM) ---
    if (addr == 0xFFFF) {  // IE
        ie_write_count_++;  // Step 0482: Usar miembro de instancia en lugar de static
        last_ie_written = value;
        ie_writes_program_++;  // Step 0475: Escrituras siempre son desde programa
        
        // --- Step 0471: Instrumentación microscópica de IE write ---
        last_ie_write_pc = debug_current_pc;
        last_ie_write_timestamp++;
        
        // Log gated (solo si VIBOY_DEBUG_PPU=1)
        bool debug_ppu = (std::getenv("VIBOY_DEBUG_PPU") != nullptr && 
                           std::string(std::getenv("VIBOY_DEBUG_PPU")) == "1");
        if (debug_ppu) {
            static int ie_write_log_count = 0;
            if (ie_write_log_count < 20) {
                ie_write_log_count++;
                printf("[MMU-IE-WRITE] PC:0x%04X | IE write #%u | Value: 0x%02X\n",
                       debug_current_pc, ie_write_count_, value);
            }
        }
    }
    
    // --- Step 0474: Instrumentación quirúrgica de IF (0xFF0F) ---
    // --- Step 0475: Source Tagging para IF write (siempre PROGRAM) ---
    if (addr == 0xFF0F) {  // IF
        if_write_count_++;
        last_if_write_pc_ = debug_current_pc;
        last_if_write_val_ = value;
        last_if_write_timestamp_++;  // Step 0477: Incrementar timestamp
        if_writes_program_++;  // Step 0475: Escrituras siempre son desde programa
        
        // Histograma simple
        if (value == 0) {
            if_writes_0_++;
        } else {
            if_writes_nonzero_++;
        }
        
        // Log gated (solo si VIBOY_DEBUG_IO=1 o VIBOY_DEBUG_IRQ=1)
        bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                         std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
        bool debug_irq = (std::getenv("VIBOY_DEBUG_IRQ") != nullptr && 
                          std::string(std::getenv("VIBOY_DEBUG_IRQ")) == "1");
        if (debug_io || debug_irq) {
            static int if_track_log_count = 0;
            if (if_track_log_count < 50) {
                if_track_log_count++;
                printf("[IF-TRACK] write: PC=0x%04X val=0x%02X | read: count=%u last=0x%02X\n",
                       debug_current_pc, value, if_read_count_, last_if_read_val_);
            }
        }
        
        // Step 0482: if_write_count_ ya se incrementa arriba (línea ~1260), no necesitamos mantener esta línea redundante
        // last_if_written es static pero solo guarda último valor (no acumula), no causa problemas entre tests
    }
    // -----------------------------------------
    
    // --- Step 0472: Contadores de writes a KEY1 (0xFF4D) ---
    if (addr == 0xFF4D) {  // KEY1 (CGB Speed Switch)
        key1_write_count++;
        last_key1_write_value = value;
        last_key1_write_pc = debug_current_pc;
    }
    // -----------------------------------------
    
    // --- Step 0472: Contadores de writes a JOYP (0xFF00) ---
    if (addr == 0xFF00) {  // JOYP (Joypad)
        joyp_write_count++;
        last_joyp_write_value = value;
        last_joyp_write_pc = debug_current_pc;
        
        // --- Step 0484: JOYP Write Distribution ---
        joyp_write_distribution_[value]++;
        joyp_write_pcs_by_value_[value].push_back(debug_current_pc);
        // Limitar tamaño de listas (top 10 PCs por valor)
        if (joyp_write_pcs_by_value_[value].size() > 10) {
            joyp_write_pcs_by_value_[value].erase(joyp_write_pcs_by_value_[value].begin());
        }
        // -----------------------------------------
        
        // --- Step 0485: JOYP Access Trace (gated por VIBOY_DEBUG_JOYP_TRACE=1) ---
        bool debug_joyp_trace = (std::getenv("VIBOY_DEBUG_JOYP_TRACE") != nullptr && 
                                  std::string(std::getenv("VIBOY_DEBUG_JOYP_TRACE")) == "1");
        if (debug_joyp_trace && !irq_poll_active_) {  // Solo program, no CPU polling
            JOYPTraceEvent event;
            event.type = JOYPTraceEvent::WRITE;
            event.pc = debug_current_pc;
            event.value_written = value;
            event.select_bits = (value >> 4) & 0x03;  // Bits 4-5
            event.timestamp = 0;  // TODO: Necesitamos exponer total_cycles_ o usar otro contador
            
            joyp_trace_.push_back(event);
            if (joyp_trace_.size() > JOYP_TRACE_SIZE) {
                joyp_trace_.erase(joyp_trace_.begin());
            }
        }
        // -----------------------------------------
    }
    // -----------------------------------------
    
    // --- Step 0401: Boot ROM Disable (0xFF50) ---
    // Escribir cualquier valor != 0 al registro 0xFF50 deshabilita la Boot ROM permanentemente
    // (hasta el próximo reset). Este registro es write-only y se lee como 0xFF.
    // Fuente: Pan Docs - "FF50 - BOOT - Disable boot ROM"
    if (addr == 0xFF50) {
        if (value != 0 && boot_rom_enabled_) {
            boot_rom_enabled_ = false;
            printf("[BOOTROM] Boot ROM deshabilitada por escritura a 0xFF50 = 0x%02X | PC:0x%04X\n",
                   value, debug_current_pc);
        }
        // El registro 0xFF50 es write-only y se lee como 0xFF
        // No lo escribimos en memoria para evitar confusión
        return;
    }
    // -----------------------------------------

    // --- Step 0251: IMPLEMENTACIÓN DMA (OAM TRANSFER) ---
    if (addr == 0xFF46) {
        // --- Step 0410: Instrumentación mejorada de OAM DMA ---
        // Detecta cuando se activa el DMA para transferir datos a OAM (0xFE00-0xFE9F)
        // El DMA copia 160 bytes desde la dirección (value << 8) a OAM
        // Fuente: Pan Docs - "DMA Transfer": Escritura en 0xFF46 inicia transferencia
        oam_dma_count_++;
        
        uint16_t source_base = static_cast<uint16_t>(value) << 8;
        uint16_t source_end = source_base + 159;
        
        // Determinar región de origen
        const char* source_region = "Unknown";
        if (source_base >= 0x0000 && source_base < 0x4000) source_region = "ROM Bank 0";
        else if (source_base >= 0x4000 && source_base < 0x8000) source_region = "ROM Bank N";
        else if (source_base >= 0x8000 && source_base < 0xA000) source_region = "VRAM";
        else if (source_base >= 0xA000 && source_base < 0xC000) source_region = "ExtRAM";
        else if (source_base >= 0xC000 && source_base < 0xE000) source_region = "WRAM";
        
        if (oam_dma_count_ <= 50) {
            printf("[DMA] #%d | PC:0x%04X Bank:%d | Src:0x%04X-0x%04X (%s) -> OAM(0xFE00-0xFE9F)\n",
                   oam_dma_count_, debug_current_pc, current_rom_bank_, 
                   source_base, source_end, source_region);
        }
        
        // Ejecutar transferencia
        for (int i = 0; i < 160; i++) {
            uint16_t source_addr = source_base + i;
            uint8_t data = read(source_addr);
            if ((0xFE00 + i) < MEMORY_SIZE) {
                memory_[0xFE00 + i] = data;
            }
        }
        
        // Escribir también el valor en el registro DMA
        memory_[addr] = value;
        return;
    }

    // --- Step 0259: VRAM WRITE MONITOR --- (comentado)

    // Registros especiales del Timer
    if (addr == 0xFF04) {
        if (timer_ != nullptr) {
            timer_->write_div();
        }
        return;
    }

    if (addr == 0xFF05) {
        if (timer_ != nullptr) {
            timer_->write_tima(value);
        }
        return;
    }

    if (addr == 0xFF06) {
        if (timer_ != nullptr) {
            timer_->write_tma(value);
        }
        return;
    }

    if (addr == 0xFF07) {
        if (timer_ != nullptr) {
            timer_->write_tac(value);
        }
        return;
    }

    // Joypad P1
    if (addr == 0xFF00) {
        // --- Step 0380: Instrumentación de Escrituras a P1 (0xFF00) ---
        // Loggear escrituras a P1 para verificar si el juego está polleando el Joypad
        static int p1_write_count = 0;
        static uint8_t last_p1_write = 0xFF;
        
        if (p1_write_count < 50 || value != last_p1_write) {
            if (p1_write_count < 50) {
                p1_write_count++;
            }
            printf("[MMU-JOYP-WRITE] PC:0x%04X | Write P1 = 0x%02X | Bit4=%d Bit5=%d | IE=0x%02X IF=0x%02X IME=%d\n",
                   debug_current_pc, value, 
                   (value & 0x10) ? 1 : 0,  // Bit 4 (Direction row)
                   (value & 0x20) ? 1 : 0,  // Bit 5 (Action row)
                   memory_[0xFFFF], memory_[0xFF0F], 
                   0);  // IME no está disponible en MMU, usar 0
            last_p1_write = value;
        }
        // -------------------------------------------
        
        if (joypad_ != nullptr) {
            joypad_->write_p1(value);
        }
        return;
    }

    // LYC se propaga a la PPU
    if (addr == 0xFF45) {
        if (ppu_ != nullptr) {
            ppu_->set_lyc(value);
        }
        memory_[addr] = value & 0xFF;
        return;
    }
    
    // --- Step 0425: Eliminado bypass test_mode_allow_rom_writes (no spec-correct) ---
    // Las escrituras en ROM (0x0000-0x7FFF) SIEMPRE se interpretan como comandos MBC.
    // Los tests que necesiten ROM personalizada deben usar load_rom() con bytearray preparado.
    // -------------------------------------------

    // --- Step 0450: Count MBC writes (debug-gated) ---
    // Detectar writes a rangos MBC (0x0000-0x7FFF) para diagnóstico
    if (addr >= 0x0000 && addr <= 0x7FFF) {
        mbc_write_count_++;
        
        // Ring buffer: guardar últimos 8 writes
        mbc_write_ring_idx_ = (mbc_write_ring_idx_ + 1) % 8;
        mbc_write_addrs_[mbc_write_ring_idx_] = addr;
        mbc_write_vals_[mbc_write_ring_idx_] = value;
        mbc_write_pcs_[mbc_write_ring_idx_] = debug_current_pc;
        
        // Log limitado (primeras 20)
        static int mbc_log_count = 0;
        if (mbc_log_count < 20) {
            const char* range = (addr <= 0x1FFF) ? "RAM_EN" :
                               (addr <= 0x3FFF) ? "ROM_BANK" :
                               (addr <= 0x5FFF) ? "RAM_BANK" : "MODE";
            printf("[MBC-WRITE] #%u | PC:0x%04X | Addr:0x%04X | Val:0x%02X | Range:%s\n",
                   mbc_write_count_, debug_current_pc, addr, value, range);
            mbc_log_count++;
        }
    }
    
    // --- Step 0275: Monitor de Salto de Banco (Bank Watcher) ---
    // --- Step 0407: Monitor completo de MBC writes (0x0000-0x7FFF) ---
    // Instrumentación acotada para diagnosticar problemas de banking en pkmn.gb y Oro.gbc
    // Fuente: Pan Docs - "Memory Bank Controllers (MBC1/MBC3/MBC5)"
    if (addr < 0x8000) {
        static int mbc_write_count = 0;
        const int MBC_WRITE_LIMIT = 200;  // Límite para evitar saturación

        if (mbc_write_count < MBC_WRITE_LIMIT) {
            const char* range_name = nullptr;
            if (addr < 0x2000) {
                range_name = "RAM-ENABLE";
            } else if (addr < 0x4000) {
                range_name = "BANK-LOW";
            } else if (addr < 0x6000) {
                range_name = "BANK-HIGH/RAM";
            } else {
                range_name = "MODE/LATCH";
            }

            printf("[MBC-WRITE-0407] %s | addr:0x%04X val:0x%02X | PC:0x%04X | "
                   "MBC:%d | bank0:%d bankN:%d | mode:%d\n",
                   range_name, addr, value, debug_current_pc,
                   static_cast<int>(mbc_type_), bank0_rom_, bankN_rom_, mbc1_mode_);
            mbc_write_count++;
        }
    }
    // -----------------------------------------

    // --- Control de MBC / ROM banking ---
    if (addr < 0x8000) {
        switch (mbc_type_) {
            case MBCType::MBC1:
                if (addr < 0x2000) {
                    ram_enabled_ = ((value & 0x0F) == 0x0A);
                } else if (addr < 0x4000) {
                    mbc1_bank_low5_ = value & 0x1F;
                    if ((mbc1_bank_low5_ & 0x1F) == 0) {
                        mbc1_bank_low5_ = 1;  // banco 0 se mapea a 1
                    }
                    update_bank_mapping();
                } else if (addr < 0x6000) {
                    mbc1_bank_high2_ = value & 0x03;
                    update_bank_mapping();
                } else {  // 0x6000-0x7FFF
                    // --- Step 0279: Monitor de Cambio de Modo MBC1 ---
                    // El MBC1 tiene dos modos:
                    // - Modo 0: Banco 0 siempre mapeado en 0x0000-0x3FFF (ROM banking)
                    // - Modo 1: Banco 0 puede ser reemplazado por RAM banking
                    // Si el modo 1 se activa accidentalmente, el Banco 0 podría desaparecer
                    // de 0x0000-0x3FFF, rompiendo los vectores de interrupción (0x0000, 0x0040, etc.)
                    // Fuente: Pan Docs - "MBC1": Modo 0/1 controla si 0x0000-0x3FFF es ROM o RAM
                    uint8_t new_mode = value & 0x01;
                    if (mbc1_mode_ != new_mode) {
                        printf("[MBC1-MODE] Cambio de modo detectado: %d -> %d en PC:0x%04X | Bank0:%d BankN:%d\n",
                               mbc1_mode_, new_mode, debug_current_pc, bank0_rom_, bankN_rom_);
                    }
                    // -----------------------------------------
                    mbc1_mode_ = new_mode;
                    update_bank_mapping();
                }
                return;

            case MBCType::MBC2:
                if (addr < 0x2000) {
                    ram_enabled_ = ((value & 0x0F) == 0x0A);
                } else if (addr < 0x4000) {
                    uint16_t bank = value & 0x0F;
                    if (bank == 0) bank = 1;
                    current_rom_bank_ = bank;
                    update_bank_mapping();
                }
                return;

            case MBCType::MBC3:
                if (addr < 0x2000) {
                    ram_enabled_ = ((value & 0x0F) == 0x0A);
                    return;
                } else if (addr < 0x4000) {
                    uint16_t bank = value & 0x7F;
                    if (bank == 0) bank = 1;
                    current_rom_bank_ = bank;
                    update_bank_mapping();
                    return;
                } else if (addr < 0x6000) {
                    // 0x4000-0x5FFF: RAM Bank / RTC Register select
                    if (value <= 0x03) {
                        ram_bank_ = value & 0x03;
                        mbc3_rtc_reg_ = 0;
                    } else if (value >= 0x08 && value <= 0x0C) {
                        // RTC registro seleccionado
                        mbc3_rtc_reg_ = value;
                    }
                    return;
                } else {  
                    // --- Step 0409: 0x6000-0x7FFF Latch Clock ---
                    // Secuencia requerida: escribir 0x00, luego 0x01 → captura snapshot RTC
                    // Fuente: Pan Docs - MBC3, Latch Clock Data
                    if (mbc3_latch_value_ == 0x00 && value == 0x01) {
                        rtc_latch();
                        printf("[RTC] Latch triggered: %02d:%02d:%02d Day=%d\n",
                               rtc_hours_, rtc_minutes_, rtc_seconds_,
                               rtc_day_low_ | ((rtc_day_high_ & 0x01) << 8));
                    }
                    mbc3_latch_value_ = value;
                    return;
                }

            case MBCType::MBC5:
                if (addr < 0x2000) {
                    ram_enabled_ = ((value & 0x0F) == 0x0A);
                    return;
                } else if (addr < 0x3000) {
                    uint16_t lower = value;
                    current_rom_bank_ = (current_rom_bank_ & 0x100) | lower;
                    update_bank_mapping();
                    return;
                } else if (addr < 0x4000) {
                    uint16_t high = value & 0x01;
                    current_rom_bank_ = (current_rom_bank_ & 0xFF) | (high << 8);
                    update_bank_mapping();
                    return;
                } else if (addr < 0x6000) {
                    ram_bank_ = value & 0x0F;
                    return;
                } else {
                    return;
                }

            case MBCType::ROM_ONLY:
            default:
                // Step 0425: ROM es SIEMPRE read-only (spec-correct según Pan Docs).
                // Las escrituras en ROM (0x0000-0x7FFF) se ignoran (o se interpretan como MBC).
                // NO permitir escrituras incluso si rom_data_ está vacío.
                return;
        }
    }

    // --- RAM Externa (0xA000-0xBFFF) ---
    if (addr >= 0xA000 && addr <= 0xBFFF) {
        if (!ram_enabled_ || ram_data_.empty()) {
            return;
        }

        size_t bank_index = 0;
        switch (mbc_type_) {
            case MBCType::MBC1:
                bank_index = (mbc1_mode_ == 1) ? ram_bank_ : 0;
                break;
            case MBCType::MBC3:
                if (mbc3_rtc_reg_ >= 0x08 && mbc3_rtc_reg_ <= 0x0C) {
                    // --- Step 0409: RTC Write ---
                    switch (mbc3_rtc_reg_) {
                        case 0x08: rtc_seconds_ = value; break;
                        case 0x09: rtc_minutes_ = value; break;
                        case 0x0A: rtc_hours_ = value; break;
                        case 0x0B: rtc_day_low_ = value; break;
                        case 0x0C: 
                            rtc_day_high_ = value;
                            // Si se setea HALT (bit 6), actualizar start_time para "congelar" el reloj
                            if (value & 0x40) {
                                rtc_start_time_ = std::chrono::steady_clock::now();
                            }
                            break;
                    }
                    return;
                }
                bank_index = ram_bank_;
                break;
            case MBCType::MBC5:
                bank_index = ram_bank_;
                break;
            case MBCType::MBC2:
                bank_index = 0;
                break;
            default:
                bank_index = 0;
                break;
        }

        size_t offset = bank_index * ram_bank_size_ + (addr - 0xA000);
        if (offset < ram_data_.size()) {
            if (mbc_type_ == MBCType::MBC2) {
                ram_data_[offset] = value & 0x0F;
            } else {
                ram_data_[offset] = value;
            }
        }
        return;
    }

    // --- Step 0384: Monitor de Escrituras a IF (0xFF0F) ---
    // ELIMINADO en Step 0474: Reemplazado por instrumentación quirúrgica más completa
    // El código antiguo está comentado para referencia histórica
    /*
    if (addr == 0xFF0F) {
        uint8_t old_if = memory_[addr];
        uint8_t new_if = value;
        
        static int if_write_count = 0;
        if (if_write_count < 100) {
            if_write_count++;
            
            // Detectar si se están limpiando bits (clear)
            bool clearing_bits = (new_if & ~old_if) == 0 && new_if != old_if;
            uint8_t cleared_bits = old_if & ~new_if;
            
            printf("[IF-WRITE] PC:0x%04X | IF: 0x%02X -> 0x%02X | %s",
                   debug_current_pc, old_if, new_if,
                   clearing_bits ? "CLEARING" : "SETTING");
            
            if (clearing_bits && cleared_bits != 0) {
                printf(" | Cleared bits: ");
                if (cleared_bits & 0x01) printf("VBlank ");
                if (cleared_bits & 0x02) printf("LCD-STAT ");
                if (cleared_bits & 0x04) printf("Timer ");
                if (cleared_bits & 0x08) printf("Serial ");
                if (cleared_bits & 0x10) printf("Joypad ");
            }
            printf("\n");
        }
    }
    */
    // -------------------------------------------
    
    // --- Step 0294: Monitor Detallado de IE ([IE-WRITE-TRACE]) ---
    // Rastrea cambios en IE con desglose de bits para ver qué interrupciones
    // se habilitan y cuándo.
    // Fuente: Pan Docs - "Interrupt Enable Register (IE)"
    if (addr == 0xFFFF) {
        uint8_t old_ie = memory_[addr];
        uint8_t new_ie = value;
        
        if (old_ie != new_ie) {
            printf("[IE-WRITE-TRACE] PC:0x%04X Bank:%d | 0x%02X -> 0x%02X\n",
                   debug_current_pc, current_rom_bank_, old_ie, new_ie);
            
            // Desglosar qué interrupciones se habilitan/deshabilitan
            if (new_ie != 0x00) {
                printf("[IE-WRITE-TRACE]   Interrupciones habilitadas: ");
                if (new_ie & 0x01) printf("V-Blank ");
                if (new_ie & 0x02) printf("LCD-STAT ");
                if (new_ie & 0x04) printf("Timer ");
                if (new_ie & 0x08) printf("Serial ");
                if (new_ie & 0x10) printf("Joypad ");
                printf("\n");
            } else {
                printf("[IE-WRITE-TRACE]   ⚠️ TODAS las interrupciones DESHABILITADAS\n");
            }
            
            // Alerta especial si V-Blank se habilita
            if (!(old_ie & 0x01) && (new_ie & 0x01)) {
                printf("[IE-WRITE-TRACE] ⚠️ V-BLANK INTERRUPT HABILITADA en PC:0x%04X\n", debug_current_pc);
            }
            
            // --- Step 0400: Tracking de cambios para análisis comparativo ---
            if (last_ie_value_ != new_ie) {
                last_ie_value_ = new_ie;
                if (ppu_ != nullptr) {
                    ie_change_frame_ = static_cast<int>(ppu_->get_frame_counter());
                }
            }
            // -------------------------------------------
        }
    }

    // --- Step 0294: Monitor Detallado de LCDC ([LCDC-TRACE]) ---
    // Rastrea todos los cambios en LCDC con desglose detallado de bits para ver
    // cuándo se habilita BG Display (bit 0).
    // LCDC controla el estado del LCD y las características de renderizado:
    // - Bit 7: LCD Enable (1=ON, 0=OFF)
    // - Bit 6: Window Tile Map (0=0x9800, 1=0x9C00)
    // - Bit 5: Window Display Enable (1=ON, 0=OFF)
    // - Bit 4: Tile Data Base (0=0x8800 signed, 1=0x8000 unsigned)
    // - Bit 3: BG Tile Map (0=0x9800, 1=0x9C00)
    // - Bit 2: Sprite Size (0=8x8, 1=8x16)
    // - Bit 1: Sprite Display Enable (1=ON, 0=OFF)
    // - Bit 0: BG Display Enable (1=ON, 0=OFF)
    // Fuente: Pan Docs - "LCD Control Register (LCDC)"
    if (addr == 0xFF40) {
        uint8_t old_lcdc = memory_[addr];
        uint8_t new_lcdc = value;
        
        if (old_lcdc != new_lcdc) {
            // Desglosar bits significativos
            bool lcd_on_old = (old_lcdc & 0x80) != 0;
            bool lcd_on_new = (new_lcdc & 0x80) != 0;
            bool bg_display_old = (old_lcdc & 0x01) != 0;
            bool bg_display_new = (new_lcdc & 0x01) != 0;
            bool window_display_old = (old_lcdc & 0x20) != 0;
            bool window_display_new = (new_lcdc & 0x20) != 0;
            
            printf("[LCDC-TRACE] PC:0x%04X Bank:%d | 0x%02X -> 0x%02X\n",
                   debug_current_pc, current_rom_bank_, old_lcdc, new_lcdc);
            printf("[LCDC-TRACE]   LCD: %s -> %s | BG: %s -> %s | Window: %s -> %s\n",
                   lcd_on_old ? "ON" : "OFF", lcd_on_new ? "ON" : "OFF",
                   bg_display_old ? "ON" : "OFF", bg_display_new ? "ON" : "OFF",
                   window_display_old ? "ON" : "OFF", window_display_new ? "ON" : "OFF");
            
            // Alerta especial si BG Display se habilita
            if (!bg_display_old && bg_display_new) {
                printf("[LCDC-TRACE] ⚠️ BG DISPLAY HABILITADO en PC:0x%04X\n", debug_current_pc);
            }
            
            // --- Step 0482: LCDC Disable Tracking ---
            last_lcdc_write_pc_ = debug_current_pc;
            last_lcdc_write_value_ = value;
            
            // Detectar disable (1→0)
            if (lcd_on_old && !lcd_on_new) {
                lcdc_disable_events_++;
                if (ppu_ != nullptr) {
                    ppu_->handle_lcd_disable();
                }
            }
            // -------------------------------------------
            
            // --- Step 0413: Detectar toggle del LCD (bit 7) ---
            if (lcd_on_old != lcd_on_new && ppu_ != nullptr) {
                ppu_->handle_lcd_toggle(lcd_on_new);
            }
            // -------------------------------------------
            
            // --- Step 0400: Tracking de cambios para análisis comparativo ---
            if (last_lcdc_value_ != new_lcdc) {
                last_lcdc_value_ = new_lcdc;
                if (ppu_ != nullptr) {
                    lcdc_change_frame_ = static_cast<int>(ppu_->get_frame_counter());
                }
            }
            // -------------------------------------------
        }
    }

    // --- Step 0283: Monitor de Cambios en BGP (Background Palette) ---
    // El registro BGP (0xFF47) controla la paleta de colores del fondo.
    // Queremos capturar TODOS los cambios en este registro para verificar
    // si el juego está configurando la paleta correctamente.
    // Fuente: Pan Docs - "LCD Monochrome Palettes (BGP, OBP0, OBP1)"
    if (addr == 0xFF47) {
        uint8_t old_bgp = memory_[addr];
        if (old_bgp != value) {
            printf("[BGP-CHANGE] 0x%02X -> 0x%02X en PC:0x%04X (Bank:%d)\n",
                   old_bgp, value, debug_current_pc, current_rom_bank_);
            
            // --- Step 0400: Tracking de cambios para análisis comparativo ---
            if (last_bgp_value_ != value) {
                last_bgp_value_ = value;
                if (ppu_ != nullptr) {
                    bgp_change_frame_ = static_cast<int>(ppu_->get_frame_counter());
                }
            }
            // -------------------------------------------
        }
    }

    // Escritura directa
    static int d732_log_count = 0;
    if (addr == 0xD732 && d732_log_count < 20) {
        printf("[WRAM] Write D732=%02X PC:%04X\n", value, debug_current_pc);
        d732_log_count++;
    }
    
    // --- Step 0273: Trigger D732 - Instrumentación de Escritura ---
    // Queremos saber QUIÉN intenta escribir en 0xD732 aunque sea un cero,
    // o si alguien intenta escribir algo distinto de cero.
    if (addr == 0xD732) {
        printf("[TRIGGER-D732] Write %02X from PC:%04X (Bank:%d)\n",
               value, debug_current_pc, current_rom_bank_);
    }
    
    // --- Step 0328: Variables estáticas para análisis de limpieza de VRAM ---
    // Declarar fuera del bloque condicional para que estén disponibles en todo el scope
    static uint64_t last_tile_loaded_frame = 0;
    static int tiles_loaded_count = 0;
    
    // --- Step 0352: Verificación Detallada de Escrituras a VRAM ---
    // Verificar todas las escrituras a VRAM durante la ejecución
    static int vram_write_detailed_count = 0;
    static int vram_write_total_count = 0;
    static int vram_write_non_zero_count = 0;
    static int vram_write_tile_sequences = 0;  // Secuencias de 16 bytes consecutivos
    static std::map<uint16_t, uint8_t> vram_last_value;  // Último valor escrito en cada dirección (Tarea 4)
    static int vram_erase_count = 0;
    static int vram_erase_after_write_count = 0;
    
    // Verificar si la escritura es a VRAM (0x8000-0x97FF)
    if (addr >= 0x8000 && addr < 0x9800) {
        // --- Step 0355: Monitoreo de Escrituras desde el Inicio de la Ejecución del CPU ---
        // Monitorear todas las escrituras a VRAM desde el primer ciclo del CPU
        static int vram_write_from_cpu_start_count = 0;
        static int vram_write_non_zero_from_cpu_start = 0;
        static bool cpu_started = false;
        
        // Detectar cuando el CPU empieza a ejecutar (primera escritura a cualquier dirección)
        if (!cpu_started) {
            cpu_started = true;
            printf("[MMU-VRAM-CPU-START] CPU started executing | Monitoring VRAM writes from now\n");
            
            // Verificar estado de VRAM cuando el CPU empieza
            int non_zero_bytes = 0;
            for (uint16_t check_addr = 0x8000; check_addr < 0x9800; check_addr++) {
                uint8_t byte = memory_[check_addr];
                if (byte != 0x00) {
                    non_zero_bytes++;
                }
            }
            
            printf("[MMU-VRAM-CPU-START] VRAM state when CPU starts | Non-zero bytes: %d/6144 (%.2f%%)\n",
                   non_zero_bytes, (non_zero_bytes * 100.0) / 6144);
            
            // Verificar estado de VRAM en este punto
            check_vram_state_at_point("CPU Start");
        }
        
        vram_write_from_cpu_start_count++;
        
        if (value != 0x00) {
            vram_write_non_zero_from_cpu_start++;
            
            // Loggear todas las escrituras no-cero (no solo las primeras 100)
            if (vram_write_non_zero_from_cpu_start <= 500) {
                // Obtener PC del CPU (ya está disponible en debug_current_pc)
                uint16_t pc = debug_current_pc;
                
                // Obtener frame desde PPU (si está disponible)
                uint64_t frame = 0;
                if (ppu_ != nullptr) {
                    frame = ppu_->get_frame_counter();
                }
                
                printf("[MMU-VRAM-WRITE-FROM-CPU-START] Non-zero write #%d | Addr=0x%04X | Value=0x%02X | "
                       "PC=0x%04X | Frame %llu | Total writes=%d\n",
                       vram_write_non_zero_from_cpu_start, addr, value, pc,
                       static_cast<unsigned long long>(frame),
                       vram_write_from_cpu_start_count);
            }
        }
        
        // Loggear estadísticas cada 1000 escrituras
        if (vram_write_from_cpu_start_count > 0 && vram_write_from_cpu_start_count % 1000 == 0) {
            printf("[MMU-VRAM-WRITE-FROM-CPU-START-STATS] Total writes=%d | Non-zero writes=%d | "
                   "Non-zero ratio=%.2f%%\n",
                   vram_write_from_cpu_start_count, vram_write_non_zero_from_cpu_start,
                   (vram_write_non_zero_from_cpu_start * 100.0) / vram_write_from_cpu_start_count);
        }
        // -------------------------------------------
        
        // --- Step 0353: Monitoreo Desde el Inicio ---
        // Monitorear VRAM desde el inicio de la ejecución, no solo después de activar logs
        static int vram_write_from_start_count = 0;
        static int vram_write_non_zero_from_start = 0;
        static bool vram_monitoring_initialized = false;
        
        if (!vram_monitoring_initialized) {
            vram_monitoring_initialized = true;
            printf("[MMU-VRAM-MONITOR-INIT] Monitoreo de VRAM inicializado desde el inicio\n");
        }
        
        vram_write_from_start_count++;
        
        if (value != 0x00) {
            vram_write_non_zero_from_start++;
            
            // Loggear todas las escrituras no-cero (no solo las primeras 100)
            if (vram_write_non_zero_from_start <= 200) {
                // Obtener PC del CPU (si está disponible)
                uint16_t pc = debug_current_pc;
                
                // Obtener estado del LCD desde PPU (si está disponible)
                bool lcd_is_on = false;
                if (ppu_ != nullptr) {
                    lcd_is_on = ppu_->is_lcd_on();
                }
                
                printf("[MMU-VRAM-WRITE-FROM-START] Non-zero write #%d | Addr=0x%04X | Value=0x%02X | "
                       "PC=0x%04X | LCD=%s | Total writes=%d\n",
                       vram_write_non_zero_from_start, addr, value, pc,
                       lcd_is_on ? "ON" : "OFF", vram_write_from_start_count);
            }
        }
        
        // Loggear estadísticas cada 1000 escrituras
        if (vram_write_from_start_count > 0 && vram_write_from_start_count % 1000 == 0) {
            printf("[MMU-VRAM-WRITE-FROM-START-STATS] Total writes=%d | Non-zero writes=%d | "
                   "Non-zero ratio=%.2f%%\n",
                   vram_write_from_start_count, vram_write_non_zero_from_start,
                   (vram_write_non_zero_from_start * 100.0) / vram_write_from_start_count);
        }
        // -------------------------------------------
        
        vram_write_total_count++;
        
        if (value != 0x00) {
            vram_write_non_zero_count++;
        }
        
        // Tarea 1: Loggear las primeras 100 escrituras detalladamente
        if (vram_write_detailed_count < 100) {
            vram_write_detailed_count++;
            
            // Obtener PC del CPU (ya está disponible en debug_current_pc)
            uint16_t pc = debug_current_pc;
            
            printf("[MMU-VRAM-WRITE-DETAILED] Write #%d | Addr=0x%04X | Value=0x%02X | "
                   "PC=0x%04X | Total writes=%d | Non-zero writes=%d\n",
                   vram_write_detailed_count, addr, value, pc,
                   vram_write_total_count, vram_write_non_zero_count);
        }
        
        // Tarea 1: Verificar si esta escritura es parte de una secuencia de 16 bytes (tile completo)
        if ((addr & 0x0F) == 0x00) {
            // Estamos en el inicio de un tile (cada tile es 16 bytes)
            // Verificar si las siguientes 15 direcciones también tienen datos no-cero
            bool is_tile_sequence = true;
            for (int i = 0; i < 16; i++) {
                uint16_t check_addr = (addr & 0xFFF0) + i;
                if (check_addr < 0x9800) {
                    uint8_t byte = memory_[check_addr];
                    if (i == 0 && byte == 0x00 && value == 0x00) {
                        is_tile_sequence = false;
                        break;
                    }
                }
            }
            
            if (is_tile_sequence && vram_write_tile_sequences < 20) {
                vram_write_tile_sequences++;
                printf("[MMU-VRAM-WRITE-DETAILED] Tile sequence detected at 0x%04X (sequence #%d)\n",
                       addr, vram_write_tile_sequences);
            }
        }
        
        // Loggear estadísticas cada 1000 escrituras
        if (vram_write_total_count > 0 && vram_write_total_count % 1000 == 0) {
            printf("[MMU-VRAM-WRITE-STATS] Total writes=%d | Non-zero writes=%d | "
                   "Tile sequences=%d | Non-zero ratio=%.2f%%\n",
                   vram_write_total_count, vram_write_non_zero_count, vram_write_tile_sequences,
                   (vram_write_non_zero_count * 100.0) / vram_write_total_count);
        }
        
        // --- Step 0353: Verificación de Restricciones de Acceso a VRAM ---
        // Verificar si hay restricciones de acceso a VRAM cuando LCD=ON
        // Obtener estado del LCD desde PPU (si está disponible)
        bool lcd_is_on = false;
        bool in_vblank = false;
        
        if (ppu_ != nullptr) {
            lcd_is_on = ppu_->is_lcd_on();
            // Verificar si estamos en VBLANK (LY >= 144)
            uint8_t ly = ppu_->get_ly();
            in_vblank = (ly >= 144);
        }
        
        // Verificar si el acceso está restringido
        bool access_restricted = lcd_is_on && !in_vblank;
        
        if (access_restricted && value != 0x00) {
            static int restricted_access_count = 0;
            restricted_access_count++;
            
            if (restricted_access_count <= 50) {
                // Obtener PC del CPU (si está disponible)
                uint16_t pc = debug_current_pc;
                
                printf("[MMU-VRAM-ACCESS-RESTRICTED] Write #%d | Addr=0x%04X | Value=0x%02X | "
                       "PC=0x%04X | LCD=ON, not in VBLANK | Access should be restricted\n",
                       restricted_access_count, addr, value, pc);
            }
        }
        // TODO: Implementar restricciones de acceso a VRAM cuando LCD=ON (excepto VBLANK)
        // -------------------------------------------
        
        // Tarea 3: Verificación de Timing de Escrituras a VRAM (LCD Apagado vs Encendido)
        static int vram_write_lcd_timing_count = 0;
        if (vram_write_lcd_timing_count < 50) {
            vram_write_lcd_timing_count++;
            
            // Obtener estado del LCD desde PPU (si está disponible)
            bool lcd_is_on_timing = false;
            if (ppu_ != nullptr) {
                lcd_is_on_timing = ppu_->is_lcd_on();
            }
            
            // Obtener PC del CPU (ya está disponible en debug_current_pc)
            uint16_t pc = debug_current_pc;
            
            printf("[MMU-VRAM-WRITE-LCD-TIMING] Write #%d | Addr=0x%04X | Value=0x%02X | "
                   "LCD=%s | PC=0x%04X\n",
                   vram_write_lcd_timing_count, addr, value,
                   lcd_is_on_timing ? "ON" : "OFF", pc);
            
            // Advertencia si se escribe a VRAM cuando el LCD está encendido
            if (lcd_is_on_timing && value != 0x00) {
                printf("[MMU-VRAM-WRITE-LCD-TIMING] ⚠️ ADVERTENCIA: Escritura a VRAM cuando LCD está encendido!\n");
            }
        }
        
        // Tarea 4: Detección de Borrado de Tiles
        // Verificar si esta dirección tenía un valor no-cero antes
        if (vram_last_value.find(addr) != vram_last_value.end()) {
            uint8_t last_value = vram_last_value[addr];
            
            // Si el último valor era no-cero y ahora se escribe 0x00, es un borrado
            if (last_value != 0x00 && value == 0x00) {
                vram_erase_count++;
                vram_erase_after_write_count++;
                
                if (vram_erase_after_write_count <= 20) {
                    // Obtener PC del CPU (ya está disponible en debug_current_pc)
                    uint16_t pc = debug_current_pc;
                    
                    printf("[MMU-VRAM-ERASE] Erase #%d | Addr=0x%04X | Last value=0x%02X | "
                           "PC=0x%04X | Total erases=%d\n",
                           vram_erase_after_write_count, addr, last_value, pc, vram_erase_count);
                }
            }
        }
        
        // Actualizar último valor
        vram_last_value[addr] = value;
        
        // Loggear estadísticas de borrado cada 1000 escrituras
        static int vram_write_stats_count = 0;
        vram_write_stats_count++;
        if (vram_write_stats_count % 1000 == 0) {
            printf("[MMU-VRAM-ERASE-STATS] Total writes=%d | Total erases=%d | "
                   "Erase ratio=%.2f%%\n",
                   vram_write_stats_count, vram_erase_count,
                   (vram_erase_count * 100.0) / vram_write_stats_count);
        }
        
        // --- Step 0357: Monitoreo Detallado para TETRIS y Mario ---
        // Monitorear TODAS las escrituras a VRAM (incluyendo ceros) para entender por qué no cargan tiles
        static int vram_write_all_count = 0;
        static int vram_write_all_log_count = 0;
        
        vram_write_all_count++;
        
        // Loggear las primeras 1000 escrituras (incluyendo ceros) para TETRIS y Mario
        if (vram_write_all_log_count < 1000) {
            vram_write_all_log_count++;
            
            // Obtener información del estado
            uint16_t pc = debug_current_pc;
            bool lcd_is_on = false;
            bool in_vblank = false;
            uint64_t frame = 0;
            uint8_t ly = 0;
            
            if (ppu_ != nullptr) {
                lcd_is_on = ppu_->is_lcd_on();
                ly = ppu_->get_ly();
                in_vblank = (ly >= 144);
                frame = ppu_->get_frame_counter();
            }
            
            printf("[MMU-VRAM-WRITE-ALL] Write #%d | Addr=0x%04X | Value=0x%02X | "
                   "PC=0x%04X | Frame %llu | LY=%d | LCD=%s | VBLANK=%s\n",
                   vram_write_all_log_count, addr, value, pc,
                   static_cast<unsigned long long>(frame), ly,
                   lcd_is_on ? "ON" : "OFF",
                   in_vblank ? "YES" : "NO");
        }
        
        // Loggear estadísticas cada 1000 escrituras
        if (vram_write_all_count > 0 && vram_write_all_count % 1000 == 0) {
            int non_zero_count = 0;
            // Contar escrituras no-cero en las últimas 1000
            // (simplificado: contar todas las escrituras no-cero hasta ahora)
            // Nota: Este contador se actualiza en el bloque anterior
            printf("[MMU-VRAM-WRITE-ALL-STATS] Total writes=%d | Non-zero writes=%d\n",
                   vram_write_all_count, vram_write_non_zero_count);
        }
        // -------------------------------------------
    }
    // -------------------------------------------
    
    // --- Step 0323: Monitor de Accesos a VRAM ---
    // Detectar cuando el juego escribe en VRAM (0x8000-0x97FF) para entender el patrón de carga de tiles
    if (addr >= 0x8000 && addr <= 0x97FF) {
        static int vram_write_count = 0;
        static uint8_t last_vram_value = 0xFF;
        
        // Solo loggear los primeros 100 accesos y cuando hay cambios significativos
        if (vram_write_count < 100 || (value != 0x00 && last_vram_value == 0x00)) {
            if (vram_write_count < 100) {
                printf("[VRAM-WRITE] PC:0x%04X | Addr:0x%04X | Value:0x%02X\n", 
                       debug_current_pc, addr, value);
                vram_write_count++;
            }
        }
        last_vram_value = value;
        
        // --- Step 0328: Análisis Detallado de Limpieza de VRAM ---
        // Investigar por qué el juego limpia VRAM después de cargar tiles
        
        // Cuando se detecta [TILE-LOADED], marcar que se cargaron tiles
        // (esto se hace en la sección de verificación de tile completo más abajo)
        // tiles_were_loaded_recently_global se actualiza en la sección de [TILE-LOADED]
        
        // Cuando se escribe 0x00 en VRAM después de cargar tiles
        if (addr >= 0x8000 && addr <= 0x97FF && value == 0x00 && tiles_were_loaded_recently_global) {
            static int vram_clean_detailed_count = 0;
            if (vram_clean_detailed_count < 20) {
                vram_clean_detailed_count++;
                
                // Verificar si se está limpiando desde el inicio de VRAM
                if (addr == 0x8000) {
                    printf("[VRAM-CLEAN-DETAILED] ⚠️ INICIO DE LIMPIEZA: PC:0x%04X | Banco ROM: %d | Tiles cargados antes: %d\n",
                           debug_current_pc, get_current_rom_bank(), tiles_loaded_count);
                }
                
                // Verificar si se está limpiando cerca del final de VRAM
                if (addr >= 0x97F0) {
                    printf("[VRAM-CLEAN-DETAILED] ⚠️ FIN DE LIMPIEZA: PC:0x%04X | VRAM completamente limpiada\n",
                           debug_current_pc);
                    
                    // Verificar estado del tilemap después de limpiar
                    int tilemap_non_zero = 0;
                    for (int i = 0; i < 32; i++) {
                        if (memory_[0x9800 + i] != 0x00) {
                            tilemap_non_zero++;
                        }
                    }
                    printf("[VRAM-CLEAN-DETAILED] Tilemap después de limpiar: %d/32 tile IDs no-cero\n",
                           tilemap_non_zero);
                    
                    tiles_were_loaded_recently_global = false;
                    tiles_loaded_count = 0;  // Resetear contador
                }
            }
        }
        
        // Verificar si hay escrituras al tilemap después de limpiar VRAM
        if (addr >= 0x9800 && addr <= 0x9FFF && tiles_were_loaded_recently_global) {
            static int tilemap_update_after_clean_count = 0;
            if (tilemap_update_after_clean_count < 10) {
                tilemap_update_after_clean_count++;
                printf("[VRAM-CLEAN-DETAILED] Tilemap actualizado después de cargar tiles: PC:0x%04X | Addr:0x%04X | Value:0x%02X\n",
                       debug_current_pc, addr, value);
            }
        }
        // -------------------------------------------
    }
    
    // --- Step 0325: Monitor de Cambios en Tilemap ---
    // Detectar cuando el juego actualiza el tilemap para apuntar a tiles reales
    if ((addr >= 0x9800 && addr <= 0x9BFF) || (addr >= 0x9C00 && addr <= 0x9FFF)) {
        static int tilemap_update_count = 0;
        static uint8_t last_tilemap_value = 0xFF;
        
        // Solo loggear los primeros 100 cambios y cuando hay cambios significativos
        if (tilemap_update_count < 100 || (value != 0x00 && last_tilemap_value == 0x00)) {
            if (tilemap_update_count < 100) {
                printf("[TILEMAP-UPDATE] PC:0x%04X | Addr:0x%04X | TileID:0x%02X (cambió de 0x%02X)\n", 
                       debug_current_pc, addr, value, last_tilemap_value);
                tilemap_update_count++;
            }
        }
        last_tilemap_value = value;
    }
    // -------------------------------------------
    
    // --- Step 0326: Análisis de Secuencia de Actualización de Tilemap ---
    // Detectar si el tilemap se actualiza después de cargar tiles
    // Usar el mismo mecanismo que [TILE-LOADED] para detectar cuando se cargan tiles
    static bool tiles_were_loaded = false;
    
    // Detectar cuando se cargan tiles (verificar si hay datos válidos en VRAM)
    if (addr >= 0x8000 && addr <= 0x97FF && value != 0x00) {
        // Verificar si el tile completo tiene datos (no solo este byte)
        uint16_t tile_base = (addr / 16) * 16;
        bool tile_has_data = false;
        for (int i = 0; i < 16; i++) {
            if (tile_base + i < 0x9800 && memory_[tile_base + i] != 0x00) {
                tile_has_data = true;
                break;
            }
        }
        if (tile_has_data) {
            tiles_were_loaded = true;
        }
    }
    
    // Si el tilemap se actualiza con un tile ID no-cero después de cargar tiles
    if ((addr >= 0x9800 && addr <= 0x9BFF) || (addr >= 0x9C00 && addr <= 0x9FFF)) {
        static int tilemap_update_after_tiles = 0;
        
        if (tiles_were_loaded && value != 0x00 && tilemap_update_after_tiles < 10) {
            tilemap_update_after_tiles++;
            printf("[TILEMAP-SEQ] Tilemap actualizado DESPUÉS de cargar tiles! PC:0x%04X | Addr:0x%04X | TileID:0x%02X\n",
                   debug_current_pc, addr, value);
        }
    }
    // -------------------------------------------
    
    // --- Step 0291: Rastreo de Rutina de Limpieza VRAM (PC:0x36E3) ---
    // Rastrear la ejecución alrededor de PC:0x36E3 para entender
    // qué hace esta rutina y si hay código después que carga tiles.
    // El Step 0288 identificó que PC:0x36E3 está escribiendo ceros en VRAM.
    if (debug_current_pc >= 0x36E0 && debug_current_pc <= 0x36F0) {
        static int cleanup_trace_count = 0;
        if (cleanup_trace_count < 200) {
            uint8_t op = read(debug_current_pc);
            printf("[CLEANUP-TRACE] PC:0x%04X OP:0x%02X | Bank:%d\n",
                   debug_current_pc, op, current_rom_bank_);
            cleanup_trace_count++;
        }
    }
    
    // --- Step 0291: Monitor de Escrituras en Bloque ([BLOCK-WRITE]) ---
    // Detecta escrituras consecutivas en VRAM que podrían ser carga de tiles
    // en bloque (como un loop de copia).
    if (addr >= 0x8000 && addr <= 0x97FF) {
        static uint16_t last_vram_addr = 0xFFFF;
        static int consecutive_writes = 0;
        if (addr == last_vram_addr + 1) {
            consecutive_writes++;
            if (consecutive_writes == 16) {  // Un tile completo
                printf("[BLOCK-WRITE] Posible carga de tile en bloque: 0x%04X-0x%04X desde PC:0x%04X\n",
                       addr - 15, addr, debug_current_pc);
            }
        } else {
            consecutive_writes = 0;
        }
        last_vram_addr = addr;
    }

    // --- Step 0291: Monitor Extendido de Carga de Tiles ([TILE-LOAD-EXTENDED]) ---
    // Extensión del monitor [TILE-LOAD] para capturar TODAS las escrituras en Tile Data,
    // incluyendo limpieza (0x00) pero marcándolas diferente, y rastrear el frame/scanline
    // cuando ocurren usando un contador de frames.
    // Fuente: Pan Docs - "Tile Data": 0x8000-0x97FF contiene 384 tiles de 16 bytes cada uno
    if (addr >= 0x8000 && addr <= 0x97FF) {
        // Obtener contador de frames desde PPU si está disponible
        uint64_t frame_counter = 0;
        if (ppu_ != nullptr) {
            frame_counter = ppu_->get_frame_counter();
        }
        
        // Marcar el fin de la inicialización (aproximadamente después de 100 escrituras)
        static int write_count = 0;
        static bool is_initialization = true;
        write_count++;
        if (write_count > 100) {
            is_initialization = false;
        }
        
        // Capturar TODAS las escrituras, marcando si son limpieza o datos reales
        static int tile_load_extended_count = 0;
        if (tile_load_extended_count < 1000) {  // Límite más alto
            bool is_data = (value != 0x00 && value != 0x7F);
            uint16_t tile_offset = addr - 0x8000;
            uint8_t tile_id_approx = tile_offset / 16;
            
            printf("[TILE-LOAD-EXT] %s | Write %04X=%02X (TileID~%d) PC:%04X Frame:%llu Init:%s\n",
                   is_data ? "DATA" : "CLEAR",
                   addr, value, tile_id_approx, debug_current_pc, frame_counter,
                   is_initialization ? "YES" : "NO");
            tile_load_extended_count++;
        }
    }

    // --- Step 0285: Monitor Liberal de Escrituras en VRAM ([VRAM-VIBE]) ---
    // Detecta cargas de gráficos reales (distintos de 0x00 y 0x7F) en el rango 0x8000-0x9FFF.
    // Este monitor es "liberal" porque filtra valores comunes de inicialización (0x00, 0x7F)
    // y solo reporta valores que probablemente sean datos de gráficos reales.
    // Fuente: Pan Docs - "VRAM (Video RAM)": 0x8000-0x9FFF contiene Tile Data y Tile Maps
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        // Filtrar valores comunes de inicialización/borrado
        if (value != 0x00 && value != 0x7F) {
            static int vram_vibe_count = 0;
            if (vram_vibe_count < 200) {  // Límite más alto para capturar más actividad
                printf("[VRAM-VIBE] Write %04X=%02X PC:%04X (Bank:%d)\n", 
                       addr, value, debug_current_pc, current_rom_bank_);
                vram_vibe_count++;
            }
        }
        
        // --- Step 0286: Monitor Temporal Sin Filtros para VRAM ([VRAM-TOTAL]) ---
        // Captura TODAS las escrituras en VRAM sin filtros para detectar cualquier actividad sospechosa.
        // Este monitor es temporal y se usa para diagnóstico cuando hay problemas con la carga de gráficos.
        // Fuente: Pan Docs - "VRAM (Video RAM)": 0x8000-0x9FFF contiene Tile Data y Tile Maps
        static int vram_total_count = 0;
        if (vram_total_count < 500) {  // Límite alto para capturar actividad completa
            printf("[VRAM-TOTAL] Write %04X=%02X PC:%04X (Bank:%d)\n", 
                   addr, value, debug_current_pc, current_rom_bank_);
            vram_total_count++;
        }
        
        // Asegurar que la escritura se realiza correctamente en la memoria
        // para que el PPU pueda leerla. La escritura directa en memory_[addr] 
        // se hace al final de la función, pero aquí verificamos que el rango es válido.
        // NOTA: No hay restricción de escritura en VRAM basada en modo PPU en este emulador.
    }
    
    // --- Step 0287: Monitor de Escrituras en HRAM ([HRAM-WRITE]) ---
    // HRAM (High RAM) es un área de 127 bytes (0xFF80-0xFFFE) usada para rutinas de alta velocidad.
    // Los juegos suelen copiar rutinas críticas (como handlers de interrupciones) a HRAM
    // para ejecutarlas más rápido, ya que HRAM es accesible en todos los ciclos de memoria.
    // Este monitor detecta escrituras en HRAM para entender cuándo y qué se copia ahí.
    // Fuente: Pan Docs - "HRAM (High RAM)": 0xFF80-0xFFFE, accesible en todos los ciclos
    if (addr >= 0xFF80 && addr <= 0xFFFE) {
        static int hram_write_count = 0;
        if (hram_write_count < 200) {  // Límite para evitar saturación
            printf("[HRAM-WRITE] Write %04X=%02X PC:%04X (Bank:%d)\n",
                   addr, value, debug_current_pc, current_rom_bank_);
            hram_write_count++;
        }
    }

    // --- Step 0354: Investigación de Borrado de Datos Iniciales en VRAM ---
    // Detectar cuándo y quién borra los datos iniciales en VRAM
    if (addr >= 0x8000 && addr < 0x9800) {
        // Variables estáticas para detección de borrado
        static int vram_non_zero_bytes = 0;
        static bool vram_initial_state_checked = false;
        static int vram_erase_detection_count = 0;
        static int erase_by_game_count = 0;
        static int erase_by_emulator_count = 0;
        
        // Verificar estado inicial de VRAM una vez
        if (!vram_initial_state_checked) {
            vram_initial_state_checked = true;
            
            // Contar bytes no-cero en VRAM
            for (uint16_t check_addr = 0x8000; check_addr < 0x9800; check_addr++) {
                uint8_t byte = memory_[check_addr];
                if (byte != 0x00) {
                    vram_non_zero_bytes++;
                }
            }
            
            printf("[MMU-VRAM-ERASE-DETECTION] Initial VRAM state | Non-zero bytes: %d/6144 (%.2f%%)\n",
                   vram_non_zero_bytes, (vram_non_zero_bytes * 100.0) / 6144);
        }
        
        // Obtener valor anterior antes de escribir
        uint8_t old_value = memory_[addr];
        
        // Detectar cuando se borran datos (escritura de 0x00 a una dirección que tenía datos)
        if (value == 0x00 && old_value != 0x00) {
            vram_non_zero_bytes--;
            vram_erase_detection_count++;
            
            // Obtener PC del CPU
            uint16_t pc = debug_current_pc;
            
            // Obtener frame y estado del LCD desde PPU (si está disponible)
            uint64_t frame = 0;
            uint8_t ly = 0;
            bool lcd_is_on = false;
            bool in_vblank = false;
            
            if (ppu_ != nullptr) {
                frame = ppu_->get_frame_counter();
                ly = ppu_->get_ly();
                lcd_is_on = ppu_->is_lcd_on();
                in_vblank = (ly >= 144);
            }
            
            // Determinar si es el juego (ROM) o el emulador quien borra
            bool is_game_code = (pc >= 0x0000 && pc < 0x8000);
            bool is_boot_rom = (pc >= 0x0000 && pc < 0x0100);
            
            if (is_game_code && !is_boot_rom) {
                erase_by_game_count++;
            } else {
                erase_by_emulator_count++;
            }
            
            // Loggear los primeros 100 borrados
            if (vram_erase_detection_count <= 100) {
                printf("[MMU-VRAM-ERASE-DETECTION] Erase #%d | Addr=0x%04X | Old value=0x%02X | "
                       "PC=0x%04X | Frame %llu | LY: %d | LCD=%s | VBLANK=%s | "
                       "Remaining non-zero: %d/6144 (%.2f%%)\n",
                       vram_erase_detection_count, addr, old_value, pc,
                       static_cast<unsigned long long>(frame), ly,
                       lcd_is_on ? "ON" : "OFF",
                       in_vblank ? "YES" : "NO",
                       vram_non_zero_bytes, (vram_non_zero_bytes * 100.0) / 6144);
            }
            
            // Loggear quién borra los datos (primeros 20 de cada tipo)
            if (erase_by_game_count <= 20 && is_game_code && !is_boot_rom) {
                printf("[MMU-VRAM-ERASE-SOURCE] Erase by GAME | PC=0x%04X | Addr=0x%04X | "
                       "Old value=0x%02X | Total game erases=%d\n",
                       pc, addr, old_value, erase_by_game_count);
            } else if (erase_by_emulator_count <= 20 && (!is_game_code || is_boot_rom)) {
                printf("[MMU-VRAM-ERASE-SOURCE] Erase by EMULATOR/BOOT | PC=0x%04X | Addr=0x%04X | "
                       "Old value=0x%02X | Total emulator erases=%d\n",
                       pc, addr, old_value, erase_by_emulator_count);
            }
            
            // Loggear estadísticas cada 100 borrados
            int total_erases = erase_by_game_count + erase_by_emulator_count;
            if (total_erases > 0 && total_erases % 100 == 0) {
                printf("[MMU-VRAM-ERASE-SOURCE-STATS] Total erases=%d | By game=%d (%.2f%%) | "
                       "By emulator/boot=%d (%.2f%%)\n",
                       total_erases,
                       erase_by_game_count, (erase_by_game_count * 100.0) / total_erases,
                       erase_by_emulator_count, (erase_by_emulator_count * 100.0) / total_erases);
            }
            
            // Loggear timing del borrado (primeros 50)
            static int erase_timing_count = 0;
            erase_timing_count++;
            if (erase_timing_count <= 50) {
                printf("[MMU-VRAM-ERASE-TIMING] Erase #%d | Frame %llu | LY: %d | "
                       "LCD=%s | VBLANK=%s | PC=0x%04X | Addr=0x%04X\n",
                       erase_timing_count,
                       static_cast<unsigned long long>(frame), ly,
                       lcd_is_on ? "ON" : "OFF",
                       in_vblank ? "YES" : "NO",
                       pc, addr);
            }
            
            // Advertencia si VRAM se está vaciando significativamente
            if (vram_non_zero_bytes < 200 && vram_erase_detection_count > 50) {
                static bool warning_printed = false;
                if (!warning_printed) {
                    warning_printed = true;
                    printf("[MMU-VRAM-ERASE-DETECTION] ⚠️ ADVERTENCIA: VRAM se está vaciando! "
                           "Non-zero bytes: %d/6144 (%.2f%%)\n",
                           vram_non_zero_bytes, (vram_non_zero_bytes * 100.0) / 6144);
                }
            }
        }
    }
    // -------------------------------------------
    
    // --- Step 0356: Monitoreo de Escrituras No-Cero a VRAM ---
    // Monitorear si los juegos cargan tiles después de desactivar tiles de prueba
    if (addr >= 0x8000 && addr < 0x9800 && value != 0x00) {
        static int vram_non_zero_write_count = 0;
        static int vram_tile_sequences_detected = 0;
        
        vram_non_zero_write_count++;
        
        // Loggear todas las escrituras no-cero (no solo las primeras 100)
        if (vram_non_zero_write_count <= 500) {
            // Obtener PC del CPU (si está disponible)
            uint16_t pc = debug_current_pc;
            
            // Obtener estado del LCD desde PPU (si está disponible)
            bool lcd_is_on = false;
            bool in_vblank = false;
            uint64_t frame = 0;
            
            if (ppu_ != nullptr) {
                lcd_is_on = ppu_->is_lcd_on();
                uint8_t ly = ppu_->get_ly();
                in_vblank = (ly >= 144);
                frame = ppu_->get_frame_counter();
            }
            
            printf("[MMU-VRAM-NON-ZERO-WRITE] Write #%d | Addr=0x%04X | Value=0x%02X | "
                   "PC=0x%04X | Frame %llu | LCD=%s | VBLANK=%s\n",
                   vram_non_zero_write_count, addr, value, pc,
                   static_cast<unsigned long long>(frame),
                   lcd_is_on ? "ON" : "OFF",
                   in_vblank ? "YES" : "NO");
        }
        
        // --- Step 0368: Logs de Timing de Carga de Tiles vs Renderizado ---
        // Agregar logs de timing cuando se escriben tiles no-cero a VRAM
        static int vram_write_timing_count = 0;
        if (vram_write_timing_count < 50 && addr >= 0x8000 && addr <= 0x97FF && value != 0x00) {
            vram_write_timing_count++;
            
            // Obtener estado desde PPU
            uint64_t frame_counter_from_ppu = 0;
            uint8_t ly_from_ppu = 0;
            uint8_t mode_from_ppu = 0;
            
            if (ppu_ != nullptr) {
                frame_counter_from_ppu = ppu_->get_frame_counter();
                ly_from_ppu = ppu_->get_ly();
                mode_from_ppu = ppu_->get_mode();
            }
            
            printf("[MMU-VRAM-WRITE-TIMING] PC:0x%04X | Addr:0x%04X | Value:0x%02X | "
                   "Frame: %llu | LY: %d | Mode: %d\n",
                   debug_current_pc, addr, value,
                   static_cast<unsigned long long>(frame_counter_from_ppu),
                   ly_from_ppu, mode_from_ppu);
        }
        // -------------------------------------------
        
        // Verificar si esta escritura es parte de una secuencia de 16 bytes (tile completo)
        if ((addr & 0x0F) == 0x00) {
            // Estamos en el inicio de un tile (cada tile es 16 bytes)
            // Verificar si las siguientes 15 direcciones también tienen datos no-cero
            bool is_tile_sequence = true;
            uint64_t frame = 0;
            if (ppu_ != nullptr) {
                frame = ppu_->get_frame_counter();
            }
            
            for (int i = 0; i < 16; i++) {
                uint16_t check_addr = (addr & 0xFFF0) + i;
                if (check_addr < 0x9800) {
                    uint8_t byte = memory_[check_addr - 0x8000];
                    if (i == 0 && byte == 0x00 && value == 0x00) {
                        is_tile_sequence = false;
                        break;
                    }
                }
            }
            
            if (is_tile_sequence && vram_tile_sequences_detected < 50) {
                vram_tile_sequences_detected++;
                printf("[MMU-VRAM-TILE-SEQUENCE] Tile sequence detected #%d | Addr=0x%04X | Frame %llu\n",
                       vram_tile_sequences_detected, addr,
                       static_cast<unsigned long long>(frame));
            }
        }
        
        // Loggear estadísticas cada 1000 escrituras
        if (vram_non_zero_write_count > 0 && vram_non_zero_write_count % 1000 == 0) {
            printf("[MMU-VRAM-NON-ZERO-WRITE-STATS] Total non-zero writes=%d | Tile sequences=%d\n",
                   vram_non_zero_write_count, vram_tile_sequences_detected);
        }
    }
    // -------------------------------------------
    
    // --- Step 0382: Instrumentación de Escrituras a VRAM (Diagnóstico H1/H2) ---
    // Detecta y registra escrituras a VRAM para determinar si:
    // - H1: CPU no escribe a VRAM (flujo atascado)
    // - H2: CPU escribe pero las escrituras se bloquean/no aplican
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        vram_write_total_step382_++;
        if (value != 0x00) {
            vram_write_nonzero_step382_++;
        }
        
        // --- Step 0391: Conteo por regiones VRAM ---
        // Tiledata: 0x8000-0x97FF (tile patterns, 6KB)
        // Tilemap: 0x9800-0x9FFF (tile maps, 2KB)
        
        // --- Step 0414: Métricas de VRAM TileData bloqueada por Mode 3 ---
        bool is_tiledata_write = (addr >= 0x8000 && addr <= 0x97FF);
        if (is_tiledata_write) {
            vram_tiledata_total_writes_++;
            
            // Verificar si estaría bloqueada por Mode 3
            if (ppu_ != nullptr && ppu_->get_mode() == 3) {
                vram_tiledata_blocked_mode3_++;
            }
        }
        // -------------------------------------------
        
        if (value != 0x00) {
            if (addr >= 0x8000 && addr <= 0x97FF) {
                vram_tiledata_nonzero_writes_++;
                
                // --- Step 0407: Correlación TileData con ROM banking ---
                // Loguear las primeras escrituras no-cero a TileData para ver
                // si correlacionan con cambios de banco ROM
                static int tiledata_correlation_count = 0;
                const int TILEDATA_CORRELATION_LIMIT = 50;
                if (tiledata_correlation_count < TILEDATA_CORRELATION_LIMIT) {
                    printf("[TILEDATA-0407] addr:0x%04X val:0x%02X | PC:0x%04X | "
                           "bank0:%d bankN:%d | MBC:%d | count:%d\n",
                           addr, value, debug_current_pc, bank0_rom_, bankN_rom_,
                           static_cast<int>(mbc_type_), vram_tiledata_nonzero_writes_);
                    tiledata_correlation_count++;
                }
                // -------------------------------------------
            } else if (addr >= 0x9800 && addr <= 0x9FFF) {
                vram_tilemap_nonzero_writes_++;
            }
        }
        
        // Resumen cada 3000 escrituras (máx 10)
        vram_region_summary_count_++;
        if (vram_region_summary_count_ % 3000 == 0 && vram_region_summary_count_ <= 30000) {
            printf("[VRAM-SUMMARY] tiledata_nonzero=%d tilemap_nonzero=%d total=%d\n",
                   vram_tiledata_nonzero_writes_, 
                   vram_tilemap_nonzero_writes_,
                   vram_write_total_step382_);
        }
        
        // --- Step 0414: Resumen periódico cada 120 frames (máx 10 líneas) ---
        if (ppu_ != nullptr) {
            uint64_t current_frame = ppu_->get_frame_counter();
            if (current_frame > 0 && current_frame != vram_tiledata_summary_frames_) {
                if ((current_frame % 120) == 0 && (current_frame / 120) <= 10) {
                    uint8_t vram_bank_actual = vram_bank_;
                    float blocked_ratio = (vram_tiledata_total_writes_ > 0) 
                        ? (vram_tiledata_blocked_mode3_ * 100.0f) / vram_tiledata_total_writes_ 
                        : 0.0f;
                    
                    printf("[VRAM-MODE3-SUMMARY] Frame:%lu | TileData: total=%d nonzero=%d blocked_mode3=%d (%.2f%%) | Bank:%d\n",
                           current_frame, 
                           vram_tiledata_total_writes_, 
                           vram_tiledata_nonzero_writes_,
                           vram_tiledata_blocked_mode3_,
                           blocked_ratio,
                           vram_bank_actual);
                }
                vram_tiledata_summary_frames_ = current_frame;
            }
        }
        // -------------------------------------------
        
        // Loggear solo las primeras 50 escrituras con detalle completo
        static int vram_log_count_step382 = 0;
        if (vram_log_count_step382 < 50) {
            vram_log_count_step382++;
            
            // Obtener información de PPU si está disponible
            uint8_t ppu_mode = 0;
            uint8_t ly = 0;
            uint8_t lcdc = memory_[0xFF40];
            bool write_would_be_blocked = false;
            
            if (ppu_ != nullptr) {
                ppu_mode = static_cast<uint8_t>(ppu_->get_mode());
                ly = ppu_->get_ly();
                
                // En hardware real, VRAM no es accesible en Mode 3 (pixel transfer)
                // Algunos emuladores también bloquean en Mode 2 (OAM search)
                write_would_be_blocked = (ppu_mode == 3);
            }
            
            printf("[MMU-VRAM-WRITE] #%d | PC:0x%04X | Addr:0x%04X | Val:0x%02X | "
                   "Mode:%d | LY:%d | LCDC:0x%02X | Blocked:%s\n",
                   vram_log_count_step382, debug_current_pc, addr, value,
                   ppu_mode, ly, lcdc,
                   write_would_be_blocked ? "YES" : "NO");
        }
        
        // Resumen cada 1000 escrituras
        if (vram_write_total_step382_ > 0 && vram_write_total_step382_ % 1000 == 0) {
            printf("[MMU-VRAM-WRITE-SUMMARY] Total:%d | NonZero:%d | Ratio:%.2f%%\n",
                   vram_write_total_step382_, vram_write_nonzero_step382_,
                   (vram_write_nonzero_step382_ * 100.0) / vram_write_total_step382_);
        }
    }
    // -------------------------------------------
    
    // --- Step 0410: Instrumentación mejorada de HDMA (0xFF51-0xFF55) ---
    // Fuente: Pan Docs - CGB Registers, HDMA
    if (addr >= 0xFF51 && addr <= 0xFF54) {
        // HDMA1-4: Configurar source y destination
        if (addr == 0xFF51) hdma1_ = value;
        else if (addr == 0xFF52) hdma2_ = value;
        else if (addr == 0xFF53) hdma3_ = value;
        else if (addr == 0xFF54) hdma4_ = value;
        return;
    }
    if (addr == 0xFF55) {
        // HDMA5: Iniciar transferencia DMA
        uint16_t source = ((hdma1_ << 8) | (hdma2_ & 0xF0));
        uint16_t dest = 0x8000 | (((hdma3_ & 0x1F) << 8) | (hdma4_ & 0xF0));
        uint16_t length = ((value & 0x7F) + 1) * 0x10;  // Bloques de 16 bytes
        
        bool is_hblank_dma = (value & 0x80) != 0;
        
        hdma_start_count_++;
        
        // Determinar destino en VRAM
        const char* dest_region = "Unknown";
        if (dest >= 0x8000 && dest < 0x9800) dest_region = "TileData";
        else if (dest >= 0x9800 && dest < 0xA000) dest_region = "TileMap";
        
        // Determinar origen
        const char* source_region = "Unknown";
        if (source >= 0x0000 && source < 0x4000) source_region = "ROM0";
        else if (source >= 0x4000 && source < 0x8000) source_region = "ROMN";
        else if (source >= 0xA000 && source < 0xC000) source_region = "ExtRAM";
        else if (source >= 0xC000 && source < 0xE000) source_region = "WRAM";
        
        if (hdma_start_count_ <= 50) {
            printf("[HDMA] #%d | PC:0x%04X Bank:%d | Mode:%s | Src:0x%04X(%s) -> Dst:0x%04X(%s) | Len:%d bytes\n",
                   hdma_start_count_, debug_current_pc, current_rom_bank_,
                   is_hblank_dma ? "HBlank" : "General",
                   source, source_region, dest, dest_region, length);
        }
        
        // Step 0390: Implementación mínima - ejecutar como General DMA inmediato
        // TODO: Implementar HBlank DMA real en step futuro
        if (is_hblank_dma && hdma_start_count_ <= 10) {
            printf("[HDMA-MODE] HBlank DMA solicitado, ejecutando como General DMA (compatibilidad)\n");
        }
        
        // Copiar datos inmediatamente
        int bytes_copied = 0;
        int nonzero_bytes = 0;
        for (uint16_t i = 0; i < length; i++) {
            uint8_t byte = read(source + i);
            if (byte != 0) nonzero_bytes++;
            
            // Escribir a VRAM usando el sistema de banking
            uint16_t vram_addr = dest + i;
            if (vram_addr >= 0x8000 && vram_addr <= 0x9FFF) {
                uint16_t offset = vram_addr - 0x8000;
                // HDMA siempre escribe a VRAM bank seleccionado
                if (vram_bank_ == 0) {
                    vram_bank0_[offset] = byte;
                } else {
                    vram_bank1_[offset] = byte;
                }
                bytes_copied++;
                
                // Loggear primeras 10 copias de las primeras 3 transferencias
                if (hdma_start_count_ <= 3 && i < 10) {
                    printf("[HDMA-COPY] [%d/%d] 0x%04X -> VRAM[%d]:0x%04X = 0x%02X\n",
                           i+1, length, source+i, vram_bank_, vram_addr, byte);
                }
            }
        }
        
        hdma_bytes_transferred_ += bytes_copied;
        
        if (hdma_start_count_ <= 50) {
            printf("[HDMA-DONE] Transferidos %d bytes (nonzero:%d) | Total acumulado: %d bytes\n",
                   bytes_copied, nonzero_bytes, hdma_bytes_transferred_);
        }
        
        hdma5_ = 0xFF;  // Marcar como completo
        hdma_active_ = false;
        hdma_length_remaining_ = 0;
        return;
    }
    
    // --- Step 0390/0412: Escritura de Paletas CGB (0xFF68-0xFF6B) ---
    // Fuente: Pan Docs - CGB Registers, Palettes
    if (addr == 0xFF68) {
        // BCPS (BG Color Palette Specification)
        // Bits 0-5: índice (0-0x3F), Bit 7: auto-increment
        bg_palette_index_ = value;
        // Step 0412: Log limitado de writes a paletas (primeras 200)
        if (palette_write_log_count_ < 200) {
            printf("[PALETTE-WRITE] PC:0x%04X Bank:%d | FF68(BCPS) <- 0x%02X | Index:%d AutoInc:%d\n",
                   debug_current_pc, bankN_rom_, value, value & 0x3F, (value & 0x80) >> 7);
            palette_write_log_count_++;
        }
        return;
    }
    if (addr == 0xFF69) {
        // BCPD (BG Color Palette Data)
        uint8_t index = bg_palette_index_ & 0x3F;
        bg_palette_data_[index] = value;
        
        // Step 0412: Log limitado de writes a paletas (primeras 200)
        if (palette_write_log_count_ < 200) {
            printf("[PALETTE-WRITE] PC:0x%04X Bank:%d | FF69(BCPD)[0x%02X] <- 0x%02X | Pal:%d Color:%d\n",
                   debug_current_pc, bankN_rom_, index, value, index / 8, (index % 8) / 2);
            palette_write_log_count_++;
        }
        
        // Auto-increment si bit 7 de BCPS está activo
        if (bg_palette_index_ & 0x80) {
            bg_palette_index_ = 0x80 | ((index + 1) & 0x3F);
        }
        return;
    }
    if (addr == 0xFF6A) {
        // OCPS (OBJ Color Palette Specification)
        obj_palette_index_ = value;
        // Step 0412: Log limitado de writes a paletas (primeras 200)
        if (palette_write_log_count_ < 200) {
            printf("[PALETTE-WRITE] PC:0x%04X Bank:%d | FF6A(OCPS) <- 0x%02X | Index:%d AutoInc:%d\n",
                   debug_current_pc, bankN_rom_, value, value & 0x3F, (value & 0x80) >> 7);
            palette_write_log_count_++;
        }
        return;
    }
    if (addr == 0xFF6B) {
        // OCPD (OBJ Color Palette Data)
        uint8_t index = obj_palette_index_ & 0x3F;
        obj_palette_data_[index] = value;
        
        // Step 0412: Log limitado de writes a paletas (primeras 200)
        if (palette_write_log_count_ < 200) {
            printf("[PALETTE-WRITE] PC:0x%04X Bank:%d | FF6B(OCPD)[0x%02X] <- 0x%02X | Pal:%d Color:%d\n",
                   debug_current_pc, bankN_rom_, index, value, index / 8, (index % 8) / 2);
            palette_write_log_count_++;
        }
        
        // Auto-increment si bit 7 de OCPS está activo
        if (obj_palette_index_ & 0x80) {
            obj_palette_index_ = 0x80 | ((index + 1) & 0x3F);
        }
        return;
    }
    
    // --- Step 0389: Manejo de Escritura a VBK (0xFF4F) ---
    // VBK selecciona qué banco de VRAM es visible para la CPU (bit 0)
    // Fuente: Pan Docs - CGB Registers, FF4F - VBK
    if (addr == 0xFF4F) {
        vram_bank_ = value & 0x01;  // Solo bit 0 es utilizado
        static int vbk_write_count = 0;
        if (vbk_write_count < 50) {
            printf("[VBK-WRITE] PC:0x%04X | VBK <- 0x%02X | VRAM Bank: %d\n",
                   debug_current_pc, value, vram_bank_);
            vbk_write_count++;
        }
        // No escribir en memory_[], VBK no está en el espacio de memoria normal
        return;
    }
    // -------------------------------------------
    
    // --- Step 0389: CGB VRAM Banking - Escrituras ---
    // Redirigir escrituras a VRAM (0x8000-0x9FFF) al banco seleccionado
    // Fuente: Pan Docs - CGB Registers, VRAM Banks
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        // --- Step 0410: Instrumentación de escrituras CPU a TileData ---
        // Contar escrituras por CPU (no por DMA/HDMA) al área de TileData
        if (addr >= 0x8000 && addr <= 0x97FF) {
            vram_tiledata_cpu_writes_++;
            if (value != 0x00) {
                vram_tiledata_cpu_nonzero_++;
            }
            
            // Loggear primeras 50 escrituras con detalles completos
            if (vram_tiledata_cpu_log_count_ < 50) {
                printf("[TILEDATA-CPU] Write #%d | PC:0x%04X Bank:%d VRAMBank:%d | Addr:0x%04X <- 0x%02X\n",
                       vram_tiledata_cpu_writes_, debug_current_pc, current_rom_bank_,
                       vram_bank_, addr, value);
                vram_tiledata_cpu_log_count_++;
            }
            
            // Resumen periódico cada 1000 escrituras
            if (vram_tiledata_cpu_writes_ % 1000 == 0 && vram_tiledata_cpu_writes_ > 0) {
                printf("[TILEDATA-CPU-SUMMARY] Total:%d Nonzero:%d (%.1f%%)\n",
                       vram_tiledata_cpu_writes_, vram_tiledata_cpu_nonzero_,
                       (vram_tiledata_cpu_nonzero_ * 100.0) / vram_tiledata_cpu_writes_);
            }
        }
        // -----------------------------------------
        
        uint16_t offset = addr - 0x8000;
        if (vram_bank_ == 0) {
            vram_bank0_[offset] = value;
        } else {
            vram_bank1_[offset] = value;
        }
        // No escribir en memory_[], VRAM ahora está en bancos separados
        return;
    }
    // -------------------------------------------
    
    // --- Step 0465: IO write trace (gated) para SCX/SCY ---
    // Instrumentación gated para diagnosticar si "stripes bajando" son por writes del juego o bug
    bool debug_ppu = (std::getenv("VIBOY_DEBUG_PPU") != nullptr && 
                       std::string(std::getenv("VIBOY_DEBUG_PPU")) == "1");
    bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                     std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
    
    if ((debug_ppu || debug_io) && (addr == 0xFF42 || addr == 0xFF43)) {
        uint8_t old_val = memory_[addr];
        uint8_t new_val = value;
        
        // Obtener LY si PPU está disponible
        uint8_t ly = 0;
        if (ppu_ != nullptr) {
            ly = ppu_->get_ly();
        }
        
        const char* reg_name = (addr == 0xFF42) ? "SCY" : "SCX";
        printf("[IO-SCROLL-WRITE] addr=0x%04X %s old=%d new=%d LY=%d\n",
               addr, reg_name, old_val, new_val, ly);
    }
    
    // Opcional: también para LCDC si debug_io está activo
    if (debug_io && addr == 0xFF40) {
        uint8_t old_val = memory_[addr];
        uint8_t new_val = value;
        printf("[IO-LCDC-WRITE] addr=0x%04X LCDC old=0x%02X new=0x%02X\n",
               addr, old_val, new_val);
    }
        // -------------------------------------------
    
    // --- Step 0480: Instrumentación HRAM[FF92] quirúrgica (gated por VIBOY_DEBUG_IO) ---
    // Mantener compatibilidad con tracking hardcoded
    if (addr == 0xFF92) {
        bool debug_io = (std::getenv("VIBOY_DEBUG_IO") != nullptr && 
                         std::string(std::getenv("VIBOY_DEBUG_IO")) == "1");
        if (debug_io) {
            hram_ff92_write_count_++;
            last_hram_ff92_write_pc_ = debug_current_pc;
            last_hram_ff92_write_value_ = value;
            last_hram_ff92_write_timestamp_++;
        }
    }
    // -----------------------------------------
    
    // --- Step 0481: HRAM Watchlist Genérica (gated por VIBOY_DEBUG_HRAM) ---
    bool debug_hram = (std::getenv("VIBOY_DEBUG_HRAM") != nullptr && 
                       std::string(std::getenv("VIBOY_DEBUG_HRAM")) == "1");
    if (debug_hram && addr >= 0xFF80 && addr <= 0xFFFE) {
        // Verificar si addr está en watchlist
        for (auto& entry : hram_watchlist_) {
            if (entry.addr == addr) {
                entry.write_count++;
                entry.last_write_pc = debug_current_pc;
                entry.last_write_value = value;
                entry.last_write_timestamp++;
                
                // Step 0483: Actualizar frame de última escritura
                if (ppu_ != nullptr) {
                    entry.last_write_frame = static_cast<uint32_t>(ppu_->get_frame_counter());
                }
                
                // Registrar primera escritura
                if (!entry.first_write_recorded) {
                    entry.first_write_pc = debug_current_pc;
                    entry.first_write_value = value;
                    entry.first_write_timestamp = entry.last_write_timestamp;
                    if (ppu_ != nullptr) {
                        entry.first_write_frame = static_cast<uint32_t>(ppu_->get_frame_counter());
                    }
                    entry.first_write_recorded = true;
                }
                break;
            }
        }
    }
    // -----------------------------------------
    
    memory_[addr] = value;
    
    // --- Step 0323: Verificación de Tile Completo después de escribir ---
    // Verificar si el tile que acabamos de escribir tiene datos válidos
    // Solo verificamos cuando pasamos al último byte del tile (offset 15)
    if (addr >= 0x8000 && addr <= 0x97FF) {
        uint16_t tile_base = (addr / 16) * 16;
        uint8_t offset_in_tile = addr - tile_base;
        
        // Si estamos en el último byte del tile (offset 15), verificar si el tile completo tiene datos
        if (offset_in_tile == 15) {
            bool tile_has_data = false;
            for (int i = 0; i < 16; i++) {
                if (memory_[tile_base + i] != 0x00) {
                    tile_has_data = true;
                    break;
                }
            }
            
            if (tile_has_data) {
                static int tiles_loaded_log = 0;
                if (tiles_loaded_log < 20) {  // Aumentar límite para capturar más tiles
                    printf("[TILE-LOADED] Tile en 0x%04X cargado con datos válidos (PC:0x%04X)\n", 
                           tile_base, debug_current_pc);
                    tiles_loaded_log++;
                }
                
                // --- Step 0336: Análisis de Velocidad de Carga de Tiles ---
                // Analizar cuándo y cómo se cargan los tiles
                static uint64_t first_tile_loaded_frame = 0;
                static int tiles_loaded_total = 0;
                static int tiles_loaded_this_second = 0;
                static uint64_t last_second_frame = 0;
                
                // Obtener frame_counter desde PPU si está disponible
                uint64_t current_frame = 0;
                if (ppu_ != nullptr) {
                    current_frame = ppu_->get_frame_counter();
                }
                
                tiles_loaded_total++;
                
                if (first_tile_loaded_frame == 0) {
                    first_tile_loaded_frame = current_frame;
                    printf("[TILE-LOAD-TIMING] Primer tile cargado en Frame %llu (PC:0x%04X)\n",
                           static_cast<unsigned long long>(first_tile_loaded_frame), debug_current_pc);
                }
                
                // Contar tiles cargados por segundo (aproximado: 60 frames = 1 segundo)
                if (current_frame / 60 != last_second_frame / 60) {
                    if (tiles_loaded_this_second > 0) {
                        printf("[TILE-LOAD-TIMING] Segundo %llu: %d tiles cargados (Total: %d)\n",
                               static_cast<unsigned long long>(current_frame / 60), 
                               tiles_loaded_this_second, tiles_loaded_total);
                    }
                    tiles_loaded_this_second = 0;
                    last_second_frame = current_frame;
                }
                tiles_loaded_this_second++;
                // -------------------------------------------
                
                // --- Step 0327: Verificación Inmediata de VRAM al Cargar Tiles ---
                // Cuando se detecta que se cargó un tile, verificar inmediatamente el estado de VRAM
                // Esto captura el momento en que hay tiles antes de que se limpien
                static int immediate_vram_check_count = 0;
                if (immediate_vram_check_count < 5) {
                    immediate_vram_check_count++;
                    
                    // Verificar estado inmediato de VRAM
                    int non_zero_bytes = 0;
                    for (uint16_t i = 0; i < 6144; i++) {
                        if (memory_[0x8000 + i] != 0x00) {
                            non_zero_bytes++;
                        }
                    }
                    
                    printf("[VRAM-IMMEDIATE] PC:0x%04X | Tile cargado en 0x%04X | VRAM tiene %d bytes no-cero\n",
                           debug_current_pc, tile_base, non_zero_bytes);
                    
                    // Notificar a la PPU que hay tiles cargados (si hay acceso a PPU)
                    // Por ahora, solo loggear
                }
                // -------------------------------------------
                
                // Marcar que se cargaron tiles para el análisis de limpieza
                // (usado en la sección de análisis de limpieza de VRAM)
                tiles_were_loaded_recently_global = true;
                tiles_loaded_count++;
                // last_tile_loaded_frame se actualizaría desde frame_counter si está disponible
                // Por ahora, usar un contador de tiles cargados
            }
        }
    }
    // -------------------------------------------
}

void MMU::load_rom(const uint8_t* data, size_t size) {
    // Copiar toda la ROM a rom_data_
    rom_data_.resize(size);
    std::memcpy(rom_data_.data(), data, size);

    // Copiar Banco 0 a memory_ para compatibilidad
    size_t bank0_size = (size > 0x4000) ? 0x4000 : size;
    std::memcpy(memory_.data(), data, bank0_size);

    // --- Step 0409: Header & MBC Detection Logging ---
    // Leer Header para detectar tipo de cartucho / tamaños
    uint8_t cart_type = (size > 0x0147) ? data[0x0147] : 0x00;
    uint8_t rom_size_code = (size > 0x0148) ? data[0x0148] : 0x00;
    uint8_t ram_size_code = (size > 0x0149) ? data[0x0149] : 0x00;
    uint8_t cgb_flag = (size > 0x0143) ? data[0x0143] : 0x00;
    
    // Extraer título de la ROM (0x0134-0x0143, sanitizado)
    char title[17] = {0};
    for (int i = 0; i < 16 && (0x0134 + i) < size; ++i) {
        uint8_t c = data[0x0134 + i];
        // Sanitizar: solo ASCII imprimible o espacio
        title[i] = (c >= 0x20 && c <= 0x7E) ? c : '.';
        if (c == 0x00) break;  // Fin de título
    }
    
    // Detectar modo CGB (0x80 o 0xC0 = CGB compatible/only)
    bool is_cgb_rom = (cgb_flag == 0x80 || cgb_flag == 0xC0);
    
    // Configurar MBC y hardware mode
    configure_mbc_from_header(cart_type, rom_size_code, ram_size_code);
    update_bank_mapping();
    
    if (is_cgb_rom) {
        set_hardware_mode(HardwareMode::CGB);
    } else {
        set_hardware_mode(HardwareMode::DMG);
    }
    
    // Mapear MBC type a string
    const char* mbc_name = "UNKNOWN";
    switch (mbc_type_) {
        case MBCType::ROM_ONLY: mbc_name = "ROM_ONLY"; break;
        case MBCType::MBC1:     mbc_name = "MBC1"; break;
        case MBCType::MBC2:     mbc_name = "MBC2"; break;
        case MBCType::MBC3:     mbc_name = "MBC3"; break;
        case MBCType::MBC5:     mbc_name = "MBC5"; break;
    }
    
    // Log completo del header y MBC detectado
    printf("[MBC] ========== ROM HEADER INFO ==========\n");
    printf("[MBC] Title:         \"%s\"\n", title);
    printf("[MBC] Cart Type:     0x%02X\n", cart_type);
    printf("[MBC] CGB Flag:      0x%02X (%s)\n", cgb_flag, is_cgb_rom ? "CGB" : "DMG");
    printf("[MBC] ROM Size Code: 0x%02X\n", rom_size_code);
    printf("[MBC] RAM Size Code: 0x%02X\n", ram_size_code);
    printf("[MBC] Detected MBC:  %s\n", mbc_name);
    printf("[MBC] ROM Banks:     %zu (%zu bytes total)\n", rom_bank_count_, size);
    printf("[MBC] =====================================\n");
    
    // --- Step 0355: Verificación de Carga de Datos Iniciales desde la ROM ---
    // Verificar el estado de VRAM después de cargar la ROM
    int non_zero_bytes = 0;
    for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
        uint8_t byte = memory_[addr];
        if (byte != 0x00) {
            non_zero_bytes++;
        }
    }
    
    printf("[MMU-VRAM-AFTER-ROM-LOAD] VRAM after ROM load | Non-zero bytes: %d/6144 (%.2f%%)\n",
           non_zero_bytes, (non_zero_bytes * 100.0) / 6144);
    
    if (non_zero_bytes < 200) {
        printf("[MMU-VRAM-AFTER-ROM-LOAD] ⚠️ ADVERTENCIA: VRAM está vacía después de cargar la ROM!\n");
    }
    
    // Verificar si la ROM contiene datos que deberían cargarse en VRAM
    // (Nota: Las ROMs de Game Boy generalmente no tienen datos iniciales en VRAM,
    // pero algunos juegos pueden tener datos en áreas específicas)
    // -----------------------------------------
    
    // --- Step 0291: Inspección de Estado Inicial de VRAM ---
    // Verificar el estado inicial de VRAM después de cargar la ROM
    // para entender si el juego espera que VRAM tenga datos desde el inicio
    // o si la carga es responsabilidad del juego.
    inspect_vram_initial_state();
    
    // --- Step 0297: Dump Inicial de VRAM ---
    // Crear un dump detallado del estado inicial de VRAM
    dump_vram_initial_state();
    
    // --- Step 0353: Verificación del Estado Inicial de VRAM ---
    // Verificar el estado inicial de VRAM cuando se carga la ROM
    check_initial_vram_state();
    
    // --- Step 0355: Verificación de Estado de VRAM en Múltiples Puntos ---
    // Verificar el estado de VRAM después de cargar la ROM
    check_vram_state_at_point("After ROM Load");
}

void MMU::setPPU(PPU* ppu) {
    ppu_ = ppu;
}

void MMU::setTimer(Timer* timer) {
    timer_ = timer;
}

void MMU::setJoypad(Joypad* joypad) {
    joypad_ = joypad;
    
    // --- Step 0379: Conexión bidireccional MMU <-> Joypad ---
    // El Joypad necesita acceso a la MMU para solicitar interrupciones cuando
    // se presiona un botón (falling edge). Establecer el puntero bidireccional.
    if (joypad_ != nullptr) {
        joypad_->setMMU(this);
    }
    // -------------------------------------------
}

void MMU::set_waitloop_trace(bool active) {
    // --- Step 0385: Activar/desactivar trazado de MMIO/RAM durante wait-loop ---
    waitloop_trace_active_ = active;
    if (active) {
        waitloop_mmio_count_ = 0;
        waitloop_ram_count_ = 0;
    }
}

void MMU::set_vblank_isr_trace(bool active) {
    // --- Step 0385: Activar/desactivar trazado de MMIO durante VBlank ISR ---
    vblank_isr_trace_active_ = active;
}

void MMU::request_interrupt(uint8_t bit) {
    // Validar que el bit esté en el rango válido (0-4)
    if (bit > 4) {
        return;  // Bit inválido, ignorar
    }
    
    // --- Step 0411: Contadores de IRQ requests reales (independientes de cambios en IF) ---
    // Incrementar contador según el bit (siempre, sin importar si IF cambia o no)
    switch (bit) {
        case 0: irq_req_vblank_count_++; break;
        case 1: irq_req_stat_count_++; break;
        case 2: irq_req_timer_count_++; break;
        case 3: irq_req_serial_count_++; break;
        case 4: irq_req_joypad_count_++; break;
    }
    // -------------------------------------------
    
    // --- Step 0479: Contador de veces que IF bit0 se pone a 1 por frame ---
    if (bit == 0) {  // VBlank
        static uint32_t last_if_bit0_frame = 0;
        uint32_t current_frame = (ppu_ != nullptr) ? ppu_->get_frame_counter() : 0;
        if (current_frame != last_if_bit0_frame) {
            if_bit0_set_count_this_frame_ = 0;
            last_if_bit0_frame = current_frame;
        }
        if_bit0_set_count_this_frame_++;
    }
    // -------------------------------------------
    
    // --- Step 0384: Instrumentación de request_interrupt ---
    // Leer el valor actual del registro IF (0xFF0F)
    uint8_t if_before = read(0xFF0F);
    
    // Activar el bit correspondiente (OR bitwise)
    uint8_t if_after = if_before | (1 << bit);
    
    // Escribir el valor actualizado de vuelta a memoria
    write(0xFF0F, if_after);

    // Loggear (límite: 50 líneas)
    static int irq_req_log_count = 0;
    if (irq_req_log_count < 50) {
        const char* irq_names[] = {"VBlank", "LCD-STAT", "Timer", "Serial", "Joypad"};
        printf("[IRQ-REQ] PC:0x%04X | Bit:%u (%s) | IF: 0x%02X -> 0x%02X\n", 
               debug_current_pc, bit, 
               (bit <= 4) ? irq_names[bit] : "Unknown",
               if_before, if_after);
        irq_req_log_count++;
    }
    // -------------------------------------------
}

void MMU::configure_mbc_from_header(uint8_t cart_type, uint8_t rom_size_code, uint8_t ram_size_code) {
    // Detectar tipo de MBC según el header
    if (cart_type == 0x00 || cart_type == 0x08 || cart_type == 0x09) {
        mbc_type_ = MBCType::ROM_ONLY;
    } else if (cart_type >= 0x01 && cart_type <= 0x03) {
        mbc_type_ = MBCType::MBC1;
    } else if (cart_type == 0x05 || cart_type == 0x06) {
        mbc_type_ = MBCType::MBC2;
    } else if (cart_type >= 0x0F && cart_type <= 0x13) {
        mbc_type_ = MBCType::MBC3;
    } else if (cart_type >= 0x19 && cart_type <= 0x1E) {
        mbc_type_ = MBCType::MBC5;
    } else {
        mbc_type_ = MBCType::ROM_ONLY;
    }

    // Calcular número de bancos de ROM disponibles
    rom_bank_count_ = std::max<size_t>(1, (rom_data_.size() + 0x3FFF) / 0x4000);

    // Reset de estado MBC
    current_rom_bank_ = 1;
    bank0_rom_ = 0;
    bankN_rom_ = 1;
    mbc1_bank_low5_ = 1;
    mbc1_bank_high2_ = 0;
    mbc1_mode_ = 0;
    mbc3_rtc_reg_ = 0;
    mbc3_latch_ready_ = false;
    mbc3_latch_value_ = 0xFF;  // Step 0409: Ningún latch previo
    ram_bank_ = 0;
    ram_enabled_ = false;

    allocate_ram_from_header(ram_size_code);
}

void MMU::allocate_ram_from_header(uint8_t ram_size_code) {
    ram_bank_size_ = 0x2000;  // 8KB por banco (estándar)
    ram_bank_count_ = 0;

    if (mbc_type_ == MBCType::MBC2) {
        // MBC2 tiene RAM interna de 512 x 4 bits
        ram_bank_size_ = 0x200;
        ram_bank_count_ = 1;
    } else {
        switch (ram_size_code) {
            case 0x00:  // No RAM
                ram_bank_count_ = 0;
                break;
            case 0x01:  // 2KB
                ram_bank_size_ = 0x800;
                ram_bank_count_ = 1;
                break;
            case 0x02:  // 8KB
                ram_bank_size_ = 0x2000;
                ram_bank_count_ = 1;
                break;
            case 0x03:  // 32KB (4 bancos)
                ram_bank_size_ = 0x2000;
                ram_bank_count_ = 4;
                break;
            case 0x04:  // 128KB (16 bancos)
                ram_bank_size_ = 0x2000;
                ram_bank_count_ = 16;
                break;
            case 0x05:  // 64KB (8 bancos)
                ram_bank_size_ = 0x2000;
                ram_bank_count_ = 8;
                break;
            default:
                ram_bank_count_ = 0;
                break;
        }
    }

    if (ram_bank_count_ == 0) {
        ram_data_.clear();
    } else {
        ram_data_.assign(ram_bank_size_ * ram_bank_count_, 0);
    }
}

// --- Step 0409: Implementación RTC (MBC3) ---
// Fuente: Pan Docs - MBC3, Real Time Clock

void MMU::rtc_update() const {
    // Si RTC está halted (bit 6 de rtc_day_high_), no actualizar
    if (rtc_day_high_ & 0x40) {
        return;
    }
    
    // Calcular tiempo transcurrido desde rtc_start_time_
    auto now = std::chrono::steady_clock::now();
    auto elapsed = std::chrono::duration_cast<std::chrono::seconds>(now - rtc_start_time_);
    int64_t total_seconds = elapsed.count();
    
    // Convertir a segundos, minutos, horas, días
    int seconds = (total_seconds % 60);
    int minutes = ((total_seconds / 60) % 60);
    int hours = ((total_seconds / 3600) % 24);
    int days = (total_seconds / 86400);  // 86400 segundos por día
    
    rtc_seconds_ = static_cast<uint8_t>(seconds);
    rtc_minutes_ = static_cast<uint8_t>(minutes);
    rtc_hours_ = static_cast<uint8_t>(hours);
    
    // Days: máximo 9 bits (0-511), después se activa Carry
    if (days > 511) {
        days = 511;
        rtc_day_high_ |= 0x80;  // Activar Day Carry (bit 7)
    }
    
    rtc_day_low_ = static_cast<uint8_t>(days & 0xFF);
    rtc_day_high_ = (rtc_day_high_ & 0xFE) | ((days >> 8) & 0x01);  // Bit 0 = day bit 8
}

void MMU::rtc_latch() {
    // Capturar snapshot actual del RTC
    // Los juegos leen el snapshot latched para obtener tiempo consistente
    rtc_update();
    
    // NOTA: Los valores ya están en rtc_seconds_, rtc_minutes_, etc.
    // El latch simplemente "congela" estos valores hasta el próximo latch.
    // En nuestra implementación simplificada, los valores se actualizan
    // en cada lectura, pero el latch se requiere para que el juego funcione.
}

uint16_t MMU::normalize_rom_bank(uint16_t bank) const {
    if (rom_bank_count_ == 0) {
        return bank;
    }
    
    // --- Step 0407: Normalización robusta con warning para out-of-range ---
    // Fuente: Pan Docs - "MBC1": Banking modulo rom_bank_count_
    if (bank >= rom_bank_count_) {
        static int normalize_warn_count = 0;
        if (normalize_warn_count < 10) {
            printf("[MBC-WARN-0407] Banco solicitado %d >= rom_bank_count_ %zu (normalizado a %d)\n",
                   bank, rom_bank_count_, bank % rom_bank_count_);
            normalize_warn_count++;
        }
    }
    
    uint16_t normalized = static_cast<uint16_t>(bank % static_cast<uint16_t>(rom_bank_count_));
    
    // CRÍTICO: Si el banco normalizado es 0, NO debe usarse en 0x4000-0x7FFF
    // Esto se maneja en update_bank_mapping(), pero aquí validamos
    // (update_bank_mapping ya convierte 0 -> 1 para los bits bajos de MBC1)
    
    return normalized;
}

void MMU::update_bank_mapping() {
    uint16_t old_bank0 = bank0_rom_;
    uint16_t old_bankN = bankN_rom_;

    switch (mbc_type_) {
        case MBCType::MBC1: {
            uint8_t low = mbc1_bank_low5_ & 0x1F;
            if (low == 0) {
                low = 1;  // Banco 0 -> 1
            }
            uint8_t high = mbc1_bank_high2_ & 0x03;

            if (mbc1_mode_ == 0) {
                // Mode 0: upper bits se suman al banco conmutable, banco0 fijo
                bank0_rom_ = 0;
                bankN_rom_ = normalize_rom_bank(static_cast<uint16_t>((high << 5) | low));
            } else {
                // Mode 1: upper bits seleccionan banco para 0x0000-0x3FFF y RAM bank
                bank0_rom_ = normalize_rom_bank(static_cast<uint16_t>(high << 5));
                bankN_rom_ = normalize_rom_bank(static_cast<uint16_t>(low));
            }
            
            // --- Step 0407: CRÍTICO - bankN nunca debe ser 0 ---
            // Si por alguna razón bankN_rom_ resulta 0 después de normalize, forzar a 1
            // Fuente: Pan Docs - "MBC1": El área 0x4000-0x7FFF nunca debe mapear banco 0
            if (bankN_rom_ == 0) {
                bankN_rom_ = 1;
                static int bankN_zero_fix_count = 0;
                if (bankN_zero_fix_count < 5) {
                    printf("[MBC-FIX-0407] bankN_rom_ era 0, forzado a 1 (mode:%d low:%d high:%d)\n",
                           mbc1_mode_, low, high);
                    bankN_zero_fix_count++;
                }
            }
            break;
        }

        case MBCType::MBC3: {
            uint16_t bank = current_rom_bank_;
            if (bank == 0) bank = 1;
            bank0_rom_ = 0;
            bankN_rom_ = normalize_rom_bank(bank);
            
            // --- Step 0407: Asegurar bankN != 0 ---
            if (bankN_rom_ == 0) {
                bankN_rom_ = 1;
            }
            break;
        }

        case MBCType::MBC5: {
            bank0_rom_ = 0;
            bankN_rom_ = normalize_rom_bank(current_rom_bank_);
            
            // --- Step 0407: MBC5 permite banco 0 en 0x4000-0x7FFF, pero si rom_bank_count==1, forzar ---
            if (bankN_rom_ == 0 && rom_bank_count_ > 1) {
                bankN_rom_ = 1;
            }
            break;
        }

        case MBCType::MBC2:
        case MBCType::ROM_ONLY:
        default:
            bank0_rom_ = 0;
            bankN_rom_ = 1;
            break;
    }
    
    // --- Step 0407: Validación post-normalización ---
    // Asegurar que los bancos estén en el rango válido
    if (rom_bank_count_ > 0) {
        if (bank0_rom_ >= rom_bank_count_) {
            bank0_rom_ = 0;  // Fallback seguro
        }
        if (bankN_rom_ >= rom_bank_count_) {
            bankN_rom_ = 1;  // Fallback seguro
            static int bankN_clamp_count = 0;
            if (bankN_clamp_count < 5) {
                printf("[MBC-CLAMP-0407] bankN_rom_ >= rom_bank_count_, clamped a 1\n");
                bankN_clamp_count++;
            }
        }
    }

    // --- Step 0282: Auditoría de índices de bancos ---
    if (old_bank0 != bank0_rom_ || old_bankN != bankN_rom_) {
        printf("[BANK-AUDIT] Cambio de mapeo: Banco0:%d->%d | BancoN:%d->%d (Modo MBC1:%d) en PC:0x%04X\n",
               old_bank0, bank0_rom_, old_bankN, bankN_rom_, mbc1_mode_, debug_current_pc);
    }
    
    // --- Step 0293: Monitor [BANK-CHANGE] - Cambios de Banco ROM Post-Limpieza ---
    // Detecta cambios de banco ROM después de la limpieza para verificar
    // si el código que carga tiles está en otro banco.
    // Solo activar si estamos después de la rutina de limpieza (PC > 0x36F0)
    if (debug_current_pc > 0x36F0) {
        static int bank_change_count = 0;
        if (bank_change_count < 50) {
            if (old_bankN != bankN_rom_) {
                printf("[BANK-CHANGE] Banco ROM: %d -> %d en PC:0x%04X\n",
                       old_bankN, bankN_rom_, debug_current_pc);
                bank_change_count++;
            }
        }
    }
}

uint16_t MMU::get_current_rom_bank() const {
    // Retornar el banco mapeado en 0x4000-0x7FFF (bankN_rom_)
    return bankN_rom_;
}

// --- Step 0291: Inspección de Estado Inicial de VRAM ---
// Verificar el estado inicial de VRAM después de cargar la ROM
// y en el constructor para ver si hay datos o está vacía.
// Esto ayuda a entender si el juego espera que VRAM tenga datos
// desde el inicio o si la carga es responsabilidad del juego.
void MMU::inspect_vram_initial_state() {
    // Verificar si VRAM tiene datos no-cero
    int non_zero_count = 0;
    uint16_t first_non_zero_addr = 0xFFFF;
    for (uint16_t addr = 0x8000; addr <= 0x97FF; addr++) {
        if (memory_[addr] != 0x00 && memory_[addr] != 0x7F) {
            non_zero_count++;
            if (first_non_zero_addr == 0xFFFF) {
                first_non_zero_addr = addr;
            }
        }
    }
    
    printf("[VRAM-INIT] Estado inicial de VRAM: %d bytes no-cero (0x8000-0x97FF)\n", non_zero_count);
    if (first_non_zero_addr != 0xFFFF) {
        printf("[VRAM-INIT] Primer byte no-cero en: 0x%04X (valor: 0x%02X)\n",
               first_non_zero_addr, memory_[first_non_zero_addr]);
    } else {
        printf("[VRAM-INIT] VRAM está completamente vacía (solo ceros)\n");
    }
    
    // Verificar checksum del tilemap inicial
    uint16_t tilemap_checksum = 0;
    for (int i = 0; i < 1024; i++) {
        tilemap_checksum += memory_[0x9800 + i];
    }
    printf("[VRAM-INIT] Checksum del tilemap (0x9800): 0x%04X\n", tilemap_checksum);
}

// --- Step 0297: Dump Inicial de VRAM ([VRAM-INIT-DUMP]) ---
// Crea un dump del estado inicial de VRAM después de cargar la ROM
// para verificar si hay datos pre-cargados.
void MMU::dump_vram_initial_state() {
    printf("[VRAM-INIT-DUMP] Dump inicial de VRAM después de cargar ROM:\n");
    printf("[VRAM-INIT-DUMP] Tile Data (0x8000-0x807F):\n");
    for (int i = 0; i < 128; i++) {  // Primeros 128 bytes (8 tiles)
        if (i % 16 == 0) {
            printf("[VRAM-INIT-DUMP] %04X: ", 0x8000 + i);
        }
        printf("%02X ", memory_[0x8000 + i]);
        if ((i + 1) % 16 == 0) {
            printf("\n");
        }
    }
    
    printf("[VRAM-INIT-DUMP] Tile Map (0x9800-0x983F):\n");
    for (int i = 0; i < 64; i++) {  // Primeros 64 bytes del tilemap
        if (i % 16 == 0) {
            printf("[VRAM-INIT-DUMP] %04X: ", 0x9800 + i);
        }
        printf("%02X ", memory_[0x9800 + i]);
        if ((i + 1) % 16 == 0) {
            printf("\n");
        }
    }
    
    printf("[VRAM-INIT-DUMP] Fin del dump inicial\n");
}

// --- Step 0353: Verificación del Estado Inicial de VRAM ---
// --- Step 0356: Verificación de Orden de Ejecución ---
void MMU::check_initial_vram_state() {
    static bool already_called = false;
    
    if (!already_called) {
        already_called = true;
        printf("[MMU-VRAM-INITIAL-STATE-CALL] check_initial_vram_state() called\n");
    }
    // -------------------------------------------
    
    int non_zero_bytes = 0;
    int complete_tiles = 0;
    
    for (uint16_t addr = 0x8000; addr < 0x9800; addr += 16) {
        bool tile_has_data = false;
        int tile_non_zero = 0;
        
        for (int i = 0; i < 16; i++) {
            // Step 0379: Corrección crítica - NO restar 0x8000, leer directamente de VRAM
            // BUG: memory_[addr - 0x8000 + i] leía desde ROM en lugar de VRAM
            uint8_t byte = memory_[addr + i];
            if (byte != 0x00) {
                non_zero_bytes++;
                tile_non_zero++;
                tile_has_data = true;
            }
        }
        
        if (tile_non_zero >= 8) {
            complete_tiles++;
        }
    }
    
    printf("[MMU-VRAM-INITIAL-STATE] VRAM initial state | Non-zero bytes: %d/6144 (%.2f%%) | "
           "Complete tiles: %d/384 (%.2f%%)\n",
           non_zero_bytes, (non_zero_bytes * 100.0) / 6144,
           complete_tiles, (complete_tiles * 100.0) / 384);
    
    if (non_zero_bytes > 200) {
        printf("[MMU-VRAM-INITIAL-STATE] ✅ VRAM tiene datos iniciales (posiblemente desde ROM)\n");
    } else {
        printf("[MMU-VRAM-INITIAL-STATE] ⚠️ VRAM está vacía al inicio\n");
    }
}
// -------------------------------------------

// --- Step 0355: Verificación de Estado de VRAM en Múltiples Puntos ---
// Verificar el estado de VRAM en diferentes momentos para identificar la discrepancia
void MMU::check_vram_state_at_point(const char* point_name) {
    static std::map<std::string, bool> checked_points;
    
    if (checked_points.find(point_name) == checked_points.end()) {
        checked_points[point_name] = true;
        
        int non_zero_bytes = 0;
        int complete_tiles = 0;
        
        for (uint16_t addr = 0x8000; addr < 0x9800; addr += 16) {
            bool tile_has_data = false;
            int tile_non_zero = 0;
            
            for (int i = 0; i < 16; i++) {
                // Step 0379: Corrección crítica - NO restar 0x8000, leer directamente de VRAM
                // BUG: memory_[addr - 0x8000 + i] leía desde ROM en lugar de VRAM
                uint8_t byte = memory_[addr + i];
                if (byte != 0x00) {
                    non_zero_bytes++;
                    tile_non_zero++;
                    tile_has_data = true;
                }
            }
            
            if (tile_non_zero >= 8) {
                complete_tiles++;
            }
        }
        
        printf("[MMU-VRAM-STATE-POINT] Point: %s | Non-zero bytes: %d/6144 (%.2f%%) | "
               "Complete tiles: %d/384 (%.2f%%)\n",
               point_name,
               non_zero_bytes, (non_zero_bytes * 100.0) / 6144,
               complete_tiles, (complete_tiles * 100.0) / 384);
    }
}
// -------------------------------------------

// --- Step 0298: Hack Temporal - Carga Manual de Tiles ---
void MMU::load_test_tiles() {
    // Esta función carga tiles básicos de prueba en VRAM para poder avanzar
    // con el desarrollo del emulador mientras se investiga por qué el juego
    // no carga tiles automáticamente.
    //
    // Fuente: Pan Docs - "Tile Data", "Tile Map"
    // Formato Tile: 2bpp, 8x8 píxeles, 16 bytes por tile
    
    // --- Step 0313: Logs de diagnóstico ---
    printf("[LOAD-TEST-TILES] Función llamada\n");
    printf("[LOAD-TEST-TILES] VRAM antes: primer byte = 0x%02X\n", memory_[0x8000]);
    printf("[LOAD-TEST-TILES] Cargando tiles de prueba en VRAM...\n");
    
    // Tile 0 (0x8000-0x800F): Blanco puro (todos 0x00)
    // Ya está inicializado a 0x00, no necesitamos hacer nada
    
    // Tile 1 (0x8010-0x801F): Patrón de cuadros alternados (checkerboard)
    // Cada línea alterna entre 0xAA (10101010) y 0x55 (01010101)
    uint8_t tile1_data[16] = {
        0xAA, 0x55,  // Línea 0: 10101010, 01010101
        0xAA, 0x55,  // Línea 1
        0xAA, 0x55,  // Línea 2
        0xAA, 0x55,  // Línea 3
        0xAA, 0x55,  // Línea 4
        0xAA, 0x55,  // Línea 5
        0xAA, 0x55,  // Línea 6
        0xAA, 0x55,  // Línea 7
    };
    for (int i = 0; i < 16; i++) {
        memory_[0x8010 + i] = tile1_data[i];
    }
    
    // Tile 2 (0x8020-0x802F): Líneas horizontales
    // Líneas pares: 0xFF (negro), líneas impares: 0x00 (blanco)
    uint8_t tile2_data[16] = {
        0xFF, 0xFF,  // Línea 0: negra
        0x00, 0x00,  // Línea 1: blanca
        0xFF, 0xFF,  // Línea 2: negra
        0x00, 0x00,  // Línea 3: blanca
        0xFF, 0xFF,  // Línea 4: negra
        0x00, 0x00,  // Línea 5: blanca
        0xFF, 0xFF,  // Línea 6: negra
        0x00, 0x00,  // Línea 7: blanca
    };
    for (int i = 0; i < 16; i++) {
        memory_[0x8020 + i] = tile2_data[i];
    }
    
    // Tile 3 (0x8030-0x803F): Líneas verticales
    // Columnas alternadas: 0xAA (10101010) para columnas impares, 0x55 para pares
    uint8_t tile3_data[16] = {
        0xAA, 0x55,  // Línea 0: columnas alternadas
        0xAA, 0x55,  // Línea 1
        0xAA, 0x55,  // Línea 2
        0xAA, 0x55,  // Línea 3
        0xAA, 0x55,  // Línea 4
        0xAA, 0x55,  // Línea 5
        0xAA, 0x55,  // Línea 6
        0xAA, 0x55,  // Línea 7
    };
    for (int i = 0; i < 16; i++) {
        memory_[0x8030 + i] = tile3_data[i];
    }
    
    // Configurar Tile Map básico (0x9800-0x9BFF)
    // Llenar las primeras filas con los tiles de prueba
    // Tile ID 0 = blanco, Tile ID 1 = checkerboard, Tile ID 2 = líneas horizontales, Tile ID 3 = líneas verticales
    for (int y = 0; y < 18; y++) {  // 18 filas visibles
        for (int x = 0; x < 20; x++) {  // 20 columnas visibles
            uint16_t map_addr = 0x9800 + (y * 32) + x;
            // Patrón simple: alternar tiles
            uint8_t tile_id = ((x + y) % 4);
            memory_[map_addr] = tile_id;
        }
    }
    
    // --- Step 0314: Corrección de direccionamiento de tiles ---
    // LCDC bit 4 = 1 para unsigned addressing (tile data base = 0x8000)
    // Esto coincide con donde se cargan los tiles (0x8000-0x803F)
    // Si bit 4 = 0 (signed addressing), la PPU buscaría en 0x9000+ y no encontraría los tiles
    // --- Step 0313: Configurar LCDC para habilitar BG Display ---
    // El juego puede sobrescribir LCDC a 0x80 (solo LCD Enable, sin BG Display),
    // así que lo forzamos a 0x99 (LCD Enable + Unsigned addressing + BG Display) después de cargar tiles
    uint8_t current_lcdc = memory_[0xFF40];
    memory_[0xFF40] = 0x99;  // LCD Enable (bit 7) + Unsigned addressing (bit 4) + BG Display (bit 0)
    printf("[LOAD-TEST-TILES] LCDC configurado: 0x%02X -> 0x99 (Unsigned addressing + BG Display habilitado)\n", current_lcdc);
    
    // También asegurar BGP tiene un valor válido
    if (memory_[0xFF47] == 0x00) {
        memory_[0xFF47] = 0xE4;  // Paleta estándar
        printf("[LOAD-TEST-TILES] BGP configurado: 0x00 -> 0xE4 (paleta estándar)\n");
    }
    
    // --- Step 0313: Verificación después de cargar ---
    printf("[LOAD-TEST-TILES] VRAM después: primer byte = 0x%02X\n", memory_[0x8000]);
    printf("[LOAD-TEST-TILES] Tile 1 (0x8010) = 0x%02X 0x%02X\n", memory_[0x8010], memory_[0x8011]);
    printf("[LOAD-TEST-TILES] Tiles de prueba cargados:\n");
    printf("[LOAD-TEST-TILES]   Tile 0 (0x8000): Blanco\n");
    printf("[LOAD-TEST-TILES]   Tile 1 (0x8010): Checkerboard\n");
    printf("[LOAD-TEST-TILES]   Tile 2 (0x8020): Lineas horizontales\n");
    printf("[LOAD-TEST-TILES]   Tile 3 (0x8030): Lineas verticales\n");
    printf("[LOAD-TEST-TILES]   Tile Map configurado con patron alternado\n");
}
// --- Fin Step 0298 ---

// --- Step 0382: Estadísticas de escrituras a VRAM ---
void MMU::get_vram_write_stats(int& total_writes, int& nonzero_writes) const {
    total_writes = vram_write_total_step382_;
    nonzero_writes = vram_write_nonzero_step382_;
}
// --- Fin Step 0382 ---

// --- Step 0400: Análisis Comparativo - Secuencia de Inicialización ---
void MMU::log_init_sequence_summary() {
    // Solo loguear una vez cada 720 frames (12 segundos a 60 FPS)
    if (init_sequence_logged_) {
        return;
    }
    
    // Obtener frame actual del PPU (si está disponible)
    int current_frame = 0;
    if (ppu_ != nullptr) {
        current_frame = static_cast<int>(ppu_->get_frame_counter());
    }
    
    // Solo loguear después de 720 frames
    if (current_frame < 720) {
        return;
    }
    
    init_sequence_logged_ = true;
    
    printf("[INIT-SEQUENCE] ========================================\n");
    printf("[INIT-SEQUENCE] Resumen de Secuencia de Inicialización (primeros 720 frames)\n");
    printf("[INIT-SEQUENCE] LCDC: último valor=0x%02X, cambió en frame=%d\n",
           last_lcdc_value_, lcdc_change_frame_);
    printf("[INIT-SEQUENCE] BGP: último valor=0x%02X, cambió en frame=%d\n",
           last_bgp_value_, bgp_change_frame_);
    printf("[INIT-SEQUENCE] IE: último valor=0x%02X, cambió en frame=%d\n",
           last_ie_value_, ie_change_frame_);
    printf("[INIT-SEQUENCE] ========================================\n");
}
// --- Fin Step 0400 ---

// --- Step 0410: Resumen de Actividad DMA/HDMA y VRAM ---
void MMU::log_dma_vram_summary() {
    printf("\n");
    printf("========================================\n");
    printf("[DMA/VRAM SUMMARY] Step 0410 - Diagnóstico DMA/HDMA\n");
    printf("========================================\n");
    
    // OAM DMA
    printf("[DMA/VRAM] OAM DMA (0xFF46):\n");
    printf("[DMA/VRAM]   Total de transferencias: %d\n", oam_dma_count_);
    printf("[DMA/VRAM]   Bytes transferidos: %d (160 bytes × %d)\n", oam_dma_count_ * 160, oam_dma_count_);
    
    // HDMA
    printf("[DMA/VRAM] CGB HDMA (0xFF51-0xFF55):\n");
    printf("[DMA/VRAM]   Total de starts: %d\n", hdma_start_count_);
    printf("[DMA/VRAM]   Bytes transferidos: %d\n", hdma_bytes_transferred_);
    
    // Escrituras CPU a TileData
    printf("[DMA/VRAM] Escrituras CPU a TileData (0x8000-0x97FF):\n");
    printf("[DMA/VRAM]   Total escrituras: %d\n", vram_tiledata_cpu_writes_);
    printf("[DMA/VRAM]   Escrituras no-cero: %d\n", vram_tiledata_cpu_nonzero_);
    if (vram_tiledata_cpu_writes_ > 0) {
        printf("[DMA/VRAM]   Porcentaje no-cero: %.2f%%\n",
               (vram_tiledata_cpu_nonzero_ * 100.0) / vram_tiledata_cpu_writes_);
    }
    
    // Análisis
    printf("[DMA/VRAM] Análisis:\n");
    if (oam_dma_count_ == 0 && hdma_start_count_ == 0 && vram_tiledata_cpu_writes_ == 0) {
        printf("[DMA/VRAM]   ⚠️  NO HAY ACTIVIDAD DE CARGA DE GRÁFICOS\n");
        printf("[DMA/VRAM]   El juego no ha intentado cargar tiles por ningún método.\n");
    } else if (hdma_start_count_ > 0 && hdma_bytes_transferred_ == 0) {
        printf("[DMA/VRAM]   ⚠️  HDMA START SIN TRANSFERENCIA\n");
        printf("[DMA/VRAM]   Se intentó HDMA pero no se transfirieron bytes.\n");
    } else if (vram_tiledata_cpu_writes_ > 0 && vram_tiledata_cpu_nonzero_ == 0) {
        printf("[DMA/VRAM]   ⚠️  ESCRITURAS CPU PERO TODOS CEROS\n");
        printf("[DMA/VRAM]   Se escribió a TileData pero todos los valores son 0x00.\n");
    } else if (hdma_bytes_transferred_ > 0 || vram_tiledata_cpu_nonzero_ > 0) {
        printf("[DMA/VRAM]   ✓ HAY ACTIVIDAD DE CARGA DE GRÁFICOS\n");
        printf("[DMA/VRAM]   El juego ha cargado datos no-cero en VRAM.\n");
    }
    
    printf("========================================\n\n");
}
// --- Fin Step 0410 ---

// --- Step 0411: Resumen periódico de IRQ requests ---
void MMU::log_irq_requests_summary(uint64_t frame_count) {
    // Limitar número de resúmenes (máximo 10)
    if (irq_req_summary_count_ >= 10) {
        return;
    }
    irq_req_summary_count_++;
    
    // Leer estado actual de registros relevantes
    uint8_t ie = read(0xFFFF);
    uint8_t if_reg = read(0xFF0F);
    uint8_t lcdc = read(0xFF40);
    uint8_t ly = read(0xFF44);
    uint8_t tac = read(0xFF07);
    
    printf("\n");
    printf("========================================\n");
    printf("[IRQ-SUMMARY] Step 0411 - Frame %llu\n", static_cast<unsigned long long>(frame_count));
    printf("========================================\n");
    
    // Contadores de requests reales (independientes de cambios en IF)
    printf("[IRQ-SUMMARY] Requests generados (totales):\n");
    printf("[IRQ-SUMMARY]   VBlank (bit 0): %d\n", irq_req_vblank_count_);
    printf("[IRQ-SUMMARY]   STAT   (bit 1): %d\n", irq_req_stat_count_);
    printf("[IRQ-SUMMARY]   Timer  (bit 2): %d\n", irq_req_timer_count_);
    printf("[IRQ-SUMMARY]   Serial (bit 3): %d\n", irq_req_serial_count_);
    printf("[IRQ-SUMMARY]   Joypad (bit 4): %d\n", irq_req_joypad_count_);
    
    // Estado actual de registros
    printf("[IRQ-SUMMARY] Estado actual:\n");
    printf("[IRQ-SUMMARY]   IE (0xFFFF): 0x%02X ", ie);
    if (ie) {
        printf("(");
        if (ie & 0x01) printf("VBlank ");
        if (ie & 0x02) printf("STAT ");
        if (ie & 0x04) printf("Timer ");
        if (ie & 0x08) printf("Serial ");
        if (ie & 0x10) printf("Joypad");
        printf(")");
    }
    printf("\n");
    
    printf("[IRQ-SUMMARY]   IF (0xFF0F): 0x%02X ", if_reg);
    if (if_reg) {
        printf("(");
        if (if_reg & 0x01) printf("VBlank ");
        if (if_reg & 0x02) printf("STAT ");
        if (if_reg & 0x04) printf("Timer ");
        if (if_reg & 0x08) printf("Serial ");
        if (if_reg & 0x10) printf("Joypad");
        printf(")");
    }
    printf("\n");
    
    printf("[IRQ-SUMMARY]   LCDC (0xFF40): 0x%02X (LCD %s)\n", 
           lcdc, (lcdc & 0x80) ? "ON" : "OFF");
    printf("[IRQ-SUMMARY]   LY (0xFF44): %d\n", ly);
    printf("[IRQ-SUMMARY]   TAC (0xFF07): 0x%02X (Timer %s)\n",
           tac, (tac & 0x04) ? "ON" : "OFF");
    
    // Análisis
    printf("[IRQ-SUMMARY] Análisis:\n");
    if (irq_req_vblank_count_ == 0 && irq_req_timer_count_ == 0) {
        printf("[IRQ-SUMMARY]   ⚠️  NO HAY REQUESTS DE IRQS PRINCIPALES\n");
        printf("[IRQ-SUMMARY]   VBlank y Timer no han generado requests.\n");
        
        if (!(lcdc & 0x80)) {
            printf("[IRQ-SUMMARY]   Causa probable: LCD APAGADO (LCDC bit7=0)\n");
            printf("[IRQ-SUMMARY]   Sin LCD, no hay VBlank. LY permanece en 0.\n");
        }
        
        if (!(tac & 0x04)) {
            printf("[IRQ-SUMMARY]   Causa probable: TIMER APAGADO (TAC bit2=0)\n");
            printf("[IRQ-SUMMARY]   Sin Timer, no hay Timer IRQ.\n");
        }
    } else if (irq_req_vblank_count_ > 0 && if_reg == 0x00) {
        printf("[IRQ-SUMMARY]   ⚠️  REQUESTS GENERADOS PERO IF=0x00\n");
        printf("[IRQ-SUMMARY]   Las IRQs se generan pero IF se limpia inmediatamente.\n");
        printf("[IRQ-SUMMARY]   Posible causa: El juego limpia IF en loop sin procesar.\n");
    } else if (irq_req_vblank_count_ > 0 && (ie & if_reg) == 0) {
        printf("[IRQ-SUMMARY]   ⚠️  REQUESTS GENERADOS PERO IE NO COINCIDE CON IF\n");
        printf("[IRQ-SUMMARY]   IF tiene bits activos pero IE no los habilita.\n");
    } else if (irq_req_vblank_count_ > 0 && (ie & if_reg) != 0) {
        printf("[IRQ-SUMMARY]   ✓ HAY INTERRUPCIONES PENDIENTES\n");
        printf("[IRQ-SUMMARY]   IE & IF = 0x%02X (IME debe estar activo para servir)\n", ie & if_reg);
    }
    
    printf("========================================\n\n");
}
// --- Fin Step 0411 ---

// --- Step 0401: Boot ROM opcional ---
void MMU::set_boot_rom(const uint8_t* data, size_t size) {
    if (data == nullptr || size == 0) {
        printf("[BOOTROM] Error: datos inválidos (data=%p, size=%zu)\n", 
               static_cast<const void*>(data), size);
        return;
    }
    
    // Validar tamaño (256 bytes para DMG, 2304 bytes para CGB)
    if (size != 256 && size != 2304) {
        printf("[BOOTROM] Advertencia: tamaño no estándar (%zu bytes). ", size);
        printf("Esperado: 256 (DMG) o 2304 (CGB)\n");
        // Aceptar de todos modos para flexibilidad
    }
    
    // Copiar datos de Boot ROM
    boot_rom_.assign(data, data + size);
    boot_rom_enabled_ = true;
    
    printf("[BOOTROM] Boot ROM cargada: %zu bytes (tipo: %s)\n", 
           size, 
           size == 256 ? "DMG" : (size == 2304 ? "CGB" : "Custom"));
    printf("[BOOTROM] Boot ROM habilitada. Se deshabilitará al escribir 0xFF50.\n");
}

int MMU::is_boot_rom_enabled() const {
    return boot_rom_enabled_ ? 1 : 0;
}
// --- Fin Step 0401 ---

// --- Step 0404: Hardware Mode Management ---
void MMU::set_hardware_mode(HardwareMode mode) {
    hardware_mode_ = mode;
    printf("[MMU] Modo de hardware configurado: %s\n", 
           (mode == HardwareMode::CGB) ? "CGB" : "DMG");
    
    // Reinicializar registros I/O según el nuevo modo
    initialize_io_registers();
}

HardwareMode MMU::get_hardware_mode() const {
    return hardware_mode_;
}

void MMU::initialize_io_registers() {
    // --- Step 0404: Inicialización de Registros de Hardware según Modo ---
    // Valores de Power Up Sequence según Pan Docs para DMG y CGB.
    // Los juegos dependen de este estado inicial.
    // Fuente: Pan Docs - "Power Up Sequence", "CGB Registers"
    
    bool is_cgb = (hardware_mode_ == HardwareMode::CGB);
    
    // ===== PPU / Video =====
    memory_[0xFF40] = 0x91; // LCDC (LCD ON, BG ON, Window OFF, BG Tilemap 0x9800)
    memory_[0xFF41] = 0x85; // STAT (bits escribibles 3-7, bits 0-2 controlados por PPU)
    memory_[0xFF42] = 0x00; // SCY (Scroll Y)
    memory_[0xFF43] = 0x00; // SCX (Scroll X)
    // 0xFF44: LY se controla dinámicamente por la PPU
    memory_[0xFF45] = 0x00; // LYC (LY Compare)
    memory_[0xFF46] = 0xFF; // DMA (inactivo)
    memory_[0xFF47] = 0xFC; // BGP (Paleta BG: 11221100 = 0xFC)
    memory_[0xFF48] = 0xFF; // OBP0 (Paleta OBJ 0)
    memory_[0xFF49] = 0xFF; // OBP1 (Paleta OBJ 1)
    memory_[0xFF4A] = 0x00; // WY (Window Y)
    memory_[0xFF4B] = 0x00; // WX (Window X)
    
    // ===== CGB-Specific Registers =====
    if (is_cgb) {
        // VBK (0xFF4F): VRAM Bank Select (CGB only)
        // DMG: No existe este registro
        // CGB: 0x00 al inicio (banco 0 por defecto)
        memory_[0xFF4F] = 0x00;
        
        // KEY1 (0xFF4D): Prepare Speed Switch (CGB only)
        // DMG: No existe
        // CGB: 0x00 al inicio (modo normal, no double-speed)
        memory_[0xFF4D] = 0x00;
        
        // SVBK (0xFF70): WRAM Bank Select (CGB only)
        // DMG: No existe
        // CGB: 0x01 al inicio (banco 1 por defecto, banco 0 siempre mapeado en 0xC000-0xCFFF)
        memory_[0xFF70] = 0x01;
        
        // BCPS/BCPD (0xFF68/0xFF69): BG Palette Specification/Data (CGB only)
        memory_[0xFF68] = 0x00; // BCPS: Índice 0, no auto-increment
        memory_[0xFF69] = 0x00; // BCPD: Dato inicial
        
        // OCPS/OCPD (0xFF6A/0xFF6B): OBJ Palette Specification/Data (CGB only)
        memory_[0xFF6A] = 0x00; // OCPS: Índice 0, no auto-increment
        memory_[0xFF6B] = 0x00; // OCPD: Dato inicial
        
        // HDMA Registers (0xFF51-0xFF55): CGB DMA (Horizontal/General)
        memory_[0xFF51] = 0xFF; // HDMA1: Source High (inactivo)
        memory_[0xFF52] = 0xFF; // HDMA2: Source Low (inactivo)
        memory_[0xFF53] = 0xFF; // HDMA3: Destination High (inactivo)
        memory_[0xFF54] = 0xFF; // HDMA4: Destination Low (inactivo)
        memory_[0xFF55] = 0xFF; // HDMA5: Length/Mode/Start (inactivo)
        
        // --- Step 0412: Inicialización post-boot realista de paletas CGB ---
        // Sin bootrom real, inicializamos las paletas a un gradiente gris determinista
        // (equivalente a DMG) para evitar pantalla blanca total.
        // Clean-room: NO pretende copiar la bootrom, solo evita estado basura.
        // Fuente: Pan Docs - CGB Registers, Background Palettes (FF68-FF69), Object Palettes (FF6A-FF6B)
        
        // Gradiente gris DMG-equivalente en BGR555:
        // Color 0 (Blanco): RGB(255,255,255) → BGR555 = 0x7FFF
        // Color 1 (Gris claro): RGB(192,192,192) → BGR555 = 0x6318
        // Color 2 (Gris oscuro): RGB(96,96,96) → BGR555 = 0x318C
        // Color 3 (Negro): RGB(0,0,0) → BGR555 = 0x0000
        
        // Paleta 0 (más usada): Gradiente gris completo
        const uint16_t dmg_gray[4] = {0x7FFF, 0x6318, 0x318C, 0x0000};
        
        // Inicializar las 8 paletas BG con el gradiente gris
        for (int pal = 0; pal < 8; pal++) {
            for (int color = 0; color < 4; color++) {
                int idx = pal * 8 + color * 2;
                uint16_t bgr555 = dmg_gray[color];
                bg_palette_data_[idx + 0] = bgr555 & 0xFF;        // Low byte
                bg_palette_data_[idx + 1] = (bgr555 >> 8) & 0xFF; // High byte
            }
        }
        
        // Inicializar las 8 paletas OBJ con el gradiente gris
        for (int pal = 0; pal < 8; pal++) {
            for (int color = 0; color < 4; color++) {
                int idx = pal * 8 + color * 2;
                uint16_t bgr555 = dmg_gray[color];
                obj_palette_data_[idx + 0] = bgr555 & 0xFF;        // Low byte
                obj_palette_data_[idx + 1] = (bgr555 >> 8) & 0xFF; // High byte
            }
        }
        
        printf("[MMU-PALETTE-INIT] CGB paletas inicializadas con gradiente gris DMG-equivalente (post-boot stub)\n");
    }

    // ===== Sonido (APU) - Valores iniciales =====
    memory_[0xFF10] = 0x80; // NR10 (Channel 1 Sweep)
    memory_[0xFF11] = 0xBF; // NR11 (Channel 1 Length/Duty)
    memory_[0xFF12] = 0xF3; // NR12 (Channel 1 Envelope)
    memory_[0xFF14] = 0xBF; // NR14 (Channel 1 Frequency Hi)
    memory_[0xFF16] = 0x3F; // NR21 (Channel 2 Length/Duty)
    memory_[0xFF17] = 0x00; // NR22 (Channel 2 Envelope)
    memory_[0xFF19] = 0xBF; // NR24 (Channel 2 Frequency Hi)
    memory_[0xFF1A] = 0x7F; // NR30 (Channel 3 DAC Enable)
    memory_[0xFF1B] = 0xFF; // NR31 (Channel 3 Length)
    memory_[0xFF1C] = 0x9F; // NR32 (Channel 3 Output Level)
    memory_[0xFF1E] = 0xBF; // NR34 (Channel 3 Frequency Hi)
    memory_[0xFF20] = 0xFF; // NR41 (Channel 4 Length)
    memory_[0xFF21] = 0x00; // NR42 (Channel 4 Envelope)
    memory_[0xFF22] = 0x00; // NR43 (Channel 4 Polynomial Counter)
    memory_[0xFF23] = 0xBF; // NR44 (Channel 4 Control)
    memory_[0xFF24] = 0x77; // NR50 (Master Volume & VIN Panning)
    memory_[0xFF25] = 0xF3; // NR51 (Sound Panning)
    
    // NR52 (Sound ON/OFF) varía según hardware
    // DMG: 0xF1 (Sound ON, todos los canales activos)
    // CGB: 0xF0 o 0xF1 según modelo
    memory_[0xFF26] = is_cgb ? 0xF0 : 0xF1;

    // ===== Interrupciones =====
    memory_[0xFF0F] = 0x01; // IF (V-Blank interrupt request inicial)
    memory_[0xFFFF] = 0x00; // IE (Sin interrupciones habilitadas inicialmente)
    
    // NOTA: Los siguientes registros se controlan dinámicamente por hardware:
    // - 0xFF04 (DIV): Controlado por Timer
    // - 0xFF05 (TIMA): Controlado por Timer
    // - 0xFF06 (TMA): Controlado por Timer
    // - 0xFF07 (TAC): Controlado por Timer
    // - 0xFF00 (P1): Controlado por Joypad
    
    printf("[MMU] Registros I/O inicializados para modo %s\n", is_cgb ? "CGB" : "DMG");
}
// --- Fin Step 0404 ---

// --- Step 0402: Modo stub de Boot ROM ---
void MMU::enable_bootrom_stub(bool enable, bool cgb_mode) {
    if (!enable) {
        boot_rom_enabled_ = false;
        boot_rom_.clear();
        printf("[BOOTROM-STUB] Desactivado\n");
        return;
    }
    
    // El stub NO emula instrucciones reales del boot.
    // Solo fuerza un estado post-boot mínimo y documentado (Pan Docs).
    // Luego marca boot_rom_enabled_=false inmediatamente para que el CPU
    // comience en 0x0100 (inicio del código del cartucho).
    
    printf("[BOOTROM-STUB] Activando modo stub (%s)\n", cgb_mode ? "CGB" : "DMG");
    
    // 1. Establecer registros I/O al estado post-boot
    // Según Pan Docs, la Boot ROM configura estos registros antes de transferir control
    
    // LCDC (0xFF40): Boot ROM activa LCD con configuración estándar
    // DMG: 0x91 (LCD ON, BG ON, Window OFF, BG Tilemap 0x9800)
    // CGB: Similar, varía según modelo
    memory_[0xFF40] = 0x91;
    
    // BGP (0xFF47): Paleta de fondo estándar
    // DMG/CGB en modo DMG: 0xFC (00=blanco, 11=negro, estándar)
    memory_[0xFF47] = 0xFC;
    
    // SCX/SCY (0xFF42/0xFF43): Scroll a (0,0)
    memory_[0xFF42] = 0x00;  // SCY
    memory_[0xFF43] = 0x00;  // SCX
    
    // OBP0/OBP1 (0xFF48/0xFF49): Paletas de sprites
    memory_[0xFF48] = 0xFF;  // OBP0
    memory_[0xFF49] = 0xFF;  // OBP1
    
    // IE (0xFFFF): Interrupciones habilitadas por defecto
    // DMG: VBlank habilitado (0x01)
    memory_[0xFFFF] = 0x01;
    
    // 2. Escribir 0xFF50 = 1 para simular que la Boot ROM terminó
    // Esto deshabilita la Boot ROM sin que el CPU la ejecute
    memory_[0xFF50] = 0x01;
    boot_rom_enabled_ = false;
    boot_rom_.clear();
    
    printf("[BOOTROM-STUB] Estado post-boot aplicado:\n");
    printf("  LCDC=0x%02X | BGP=0x%02X | SCY=%d | SCX=%d\n", 
           memory_[0xFF40], memory_[0xFF47], memory_[0xFF42], memory_[0xFF43]);
    printf("  OBP0=0x%02X | OBP1=0x%02X | IE=0x%02X | FF50=0x%02X\n",
           memory_[0xFF48], memory_[0xFF49], memory_[0xFFFF], memory_[0xFF50]);
    printf("[BOOTROM-STUB] Boot ROM deshabilitada. CPU comenzará en 0x0100.\n");
}
// --- Fin Step 0402 ---

// --- Step 0425: Eliminado set_test_mode_allow_rom_writes() (hack no spec-correct) ---
// Los tests que necesiten ROM personalizada deben usar load_rom() con bytearray preparado.
// -------------------------------------------

// --- Step 0434: Triage Mode ---

void MMU::set_triage_mode(bool active) {
    triage_.active = active;
    if (active) {
        // Reset contadores
        triage_.vram_writes = 0;
        triage_.oam_writes = 0;
        triage_.ff40_writes = 0;
        triage_.ff47_writes = 0;
        triage_.ff50_writes = 0;
        triage_.ff04_writes = 0;
        triage_.ff0f_writes = 0;
        triage_.ffff_writes = 0;
        triage_.mbc1_bank_writes = 0;
        triage_.vram_sample_count = 0;
        triage_.io_sample_count = 0;
        triage_.mbc_sample_count = 0;
        
        printf("[TRIAGE-MMU] Triage mode ACTIVADO\n");
    } else {
        printf("[TRIAGE-MMU] Triage mode DESACTIVADO\n");
    }
}

void MMU::set_triage_pc(uint16_t pc) {
    debug_current_pc = pc;
}

void MMU::log_triage_summary() {
    if (!triage_.active) {
        return;
    }
    
    printf("\n[TRIAGE-MMU] ========================================\n");
    printf("[TRIAGE-MMU] Resumen de Triage - MMU\n");
    printf("[TRIAGE-MMU] VRAM writes: %d\n", triage_.vram_writes);
    printf("[TRIAGE-MMU] OAM writes: %d\n", triage_.oam_writes);
    printf("[TRIAGE-MMU] IO writes:\n");
    printf("[TRIAGE-MMU]   FF40 (LCDC): %d\n", triage_.ff40_writes);
    printf("[TRIAGE-MMU]   FF47 (BGP): %d\n", triage_.ff47_writes);
    printf("[TRIAGE-MMU]   FF50 (BOOT): %d\n", triage_.ff50_writes);
    printf("[TRIAGE-MMU]   FF04 (DIV): %d\n", triage_.ff04_writes);
    printf("[TRIAGE-MMU]   FF0F (IF): %d\n", triage_.ff0f_writes);
    printf("[TRIAGE-MMU]   FFFF (IE): %d\n", triage_.ffff_writes);
    printf("[TRIAGE-MMU] MBC1 banking writes: %d\n", triage_.mbc1_bank_writes);
    
    // Mostrar primeras 3 escrituras VRAM
    printf("[TRIAGE-MMU] Primeras %d escrituras VRAM:\n", 
           std::min(3, triage_.vram_sample_count));
    for (int i = 0; i < std::min(3, triage_.vram_sample_count); i++) {
        printf("[TRIAGE-MMU]   PC=0x%04X addr=0x%04X val=0x%02X\n",
               triage_.vram_samples[i].pc, triage_.vram_samples[i].addr, 
               triage_.vram_samples[i].val);
    }
    
    // Mostrar primeras 3 escrituras IO
    printf("[TRIAGE-MMU] Primeras %d escrituras IO:\n", 
           std::min(3, triage_.io_sample_count));
    for (int i = 0; i < std::min(3, triage_.io_sample_count); i++) {
        printf("[TRIAGE-MMU]   PC=0x%04X addr=0x%04X val=0x%02X\n",
               triage_.io_samples[i].pc, triage_.io_samples[i].addr, 
               triage_.io_samples[i].val);
    }
    
    // Mostrar primeras 3 escrituras MBC
    printf("[TRIAGE-MMU] Primeras %d escrituras MBC:\n", 
           std::min(3, triage_.mbc_sample_count));
    for (int i = 0; i < std::min(3, triage_.mbc_sample_count); i++) {
        printf("[TRIAGE-MMU]   PC=0x%04X addr=0x%04X val=0x%02X\n",
               triage_.mbc_samples[i].pc, triage_.mbc_samples[i].addr, 
               triage_.mbc_samples[i].val);
    }
    
    printf("[TRIAGE-MMU] ========================================\n\n");
}

// --- Fin Step 0434 ---

// ============================================================
// Step 0436: Pokemon Loop Trace (Fase A) - Ring Buffer VRAM
// ============================================================

void MMU::set_pokemon_loop_trace(bool active) {
    pokemon_loop_trace_.active = active;
    if (active) {
        // Reset del trace
        pokemon_loop_trace_.ring_idx = 0;
        pokemon_loop_trace_.total_writes = 0;
        pokemon_loop_trace_.min_addr = 0xFFFF;
        pokemon_loop_trace_.max_addr = 0x0000;
        pokemon_loop_trace_.unique_addr_count = 0;
        for (int i = 0; i < (8192 / 8); i++) {
            pokemon_loop_trace_.addr_bitset[i] = 0;
        }
        printf("[POKEMON-LOOP-TRACE] Activado - Capturando writes VRAM cuando PC en 0x36E2-0x36E7\n");
    } else {
        printf("[POKEMON-LOOP-TRACE] Desactivado\n");
    }
}

void MMU::set_current_hl(uint16_t hl_value) {
    current_hl_value_ = hl_value;
}

void MMU::log_pokemon_loop_trace_summary() {
    if (!pokemon_loop_trace_.active && pokemon_loop_trace_.total_writes == 0) {
        printf("[POKEMON-LOOP-TRACE] No hay datos capturados\n");
        return;
    }
    
    printf("\n[POKEMON-LOOP-TRACE] ========================================\n");
    printf("[POKEMON-LOOP-TRACE] Resumen de Writes VRAM en Loop (PC=0x36E2-0x36E7)\n");
    printf("[POKEMON-LOOP-TRACE] Total writes: %d\n", pokemon_loop_trace_.total_writes);
    printf("[POKEMON-LOOP-TRACE] Unique addresses: %d\n", pokemon_loop_trace_.unique_addr_count);
    printf("[POKEMON-LOOP-TRACE] Address range: 0x%04X - 0x%04X\n", 
           pokemon_loop_trace_.min_addr, pokemon_loop_trace_.max_addr);
    
    // Mostrar 5 ejemplos (primeros 5 del ring buffer, o menos si no hay tantos)
    int samples_to_show = std::min(5, pokemon_loop_trace_.total_writes);
    printf("[POKEMON-LOOP-TRACE] Primeros %d writes:\n", samples_to_show);
    
    for (int i = 0; i < samples_to_show; i++) {
        auto& sample = pokemon_loop_trace_.ring_buffer[i];
        printf("[POKEMON-LOOP-TRACE]   PC=0x%04X addr=0x%04X val=0x%02X HL=0x%04X\n",
               sample.pc, sample.addr, sample.val, sample.hl);
    }
    
    // Inferencia basada en unique_addr_count
    printf("[POKEMON-LOOP-TRACE] ========================================\n");
    if (pokemon_loop_trace_.unique_addr_count >= 1 && pokemon_loop_trace_.unique_addr_count <= 4) {
        printf("[POKEMON-LOOP-TRACE] ⚠️ INFERENCIA: HL NO CAMBIA o addressing ROTO\n");
        printf("[POKEMON-LOOP-TRACE]    → Posible bug en HL+/HL- (0x22/0x32) o INC/DEC HL\n");
    } else if (pokemon_loop_trace_.unique_addr_count > 100) {
        printf("[POKEMON-LOOP-TRACE] ✅ INFERENCIA: HL progresa correctamente\n");
        printf("[POKEMON-LOOP-TRACE]    → El loop recorre VRAM, se reinicia o condición de salida rota\n");
    } else {
        printf("[POKEMON-LOOP-TRACE] ❓ INFERENCIA: Datos ambiguos (%d unique addresses)\n", 
               pokemon_loop_trace_.unique_addr_count);
    }
    printf("[POKEMON-LOOP-TRACE] ========================================\n\n");
}

// --- Fin Step 0436 Fase A ---

// --- Step 0450: Raw read for diagnostics ---
uint8_t MMU::read_raw(uint16_t addr) const {
    // Direct access to memory_[] without any restrictions
    // WARNING: This bypasses PPU mode restrictions, banking, etc.
    // Use ONLY for diagnostics, not for emulation
    
    // Step 0452: VRAM está en bancos separados (vram_bank0_, vram_bank1_)
    // Para diagnóstico confiable, read_raw() debe leer de los bancos VRAM
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        uint16_t offset = addr - 0x8000;
        if (vram_bank_ == 0 && offset < vram_bank0_.size()) {
            return vram_bank0_[offset];
        } else if (vram_bank_ == 1 && offset < vram_bank1_.size()) {
            return vram_bank1_[offset];
        }
        return 0xFF;
    }
    
    if (addr >= MEMORY_SIZE) {
        return 0xFF;
    }
    return memory_[addr];
}

void MMU::dump_raw_range(uint16_t start, uint16_t length, uint8_t* buffer) const {
    // Dump raw memory range to buffer (for fast sampling)
    // WARNING: Only for diagnostics, bypasses restrictions
    if (buffer == nullptr) {
        return;
    }
    
    uint16_t end = std::min(static_cast<uint16_t>(start + length), static_cast<uint16_t>(MEMORY_SIZE));
    uint16_t actual_length = end - start;
    
    for (uint16_t i = 0; i < actual_length; i++) {
        buffer[i] = memory_[start + i];
    }
    
    // Fill rest with 0xFF if requested length exceeds memory
    for (uint16_t i = actual_length; i < length; i++) {
        buffer[i] = 0xFF;
    }
}

void MMU::log_mbc_writes_summary() const {
    printf("[MBC-SUMMARY] Total writes: %u\n", mbc_write_count_);
    
    if (mbc_write_count_ > 0) {
        printf("[MBC-SUMMARY] Last 8 writes:\n");
        for (int i = 0; i < 8; i++) {
            int idx = (mbc_write_ring_idx_ - 7 + i + 8) % 8;
            uint16_t addr = mbc_write_addrs_[idx];
            const char* range = (addr <= 0x1FFF) ? "RAM_EN" :
                               (addr <= 0x3FFF) ? "ROM_BANK" :
                               (addr <= 0x5FFF) ? "RAM_BANK" : "MODE";
            printf("[MBC-SUMMARY]   [%d] PC:0x%04X | Addr:0x%04X (%s) | Val:0x%02X\n",
                   i, mbc_write_pcs_[idx], addr, range, mbc_write_vals_[idx]);
        }
    }
}
// --- Fin Step 0450 ---

// --- Step 0470: Implementación de getters para contadores IE/IF writes ---
uint32_t MMU::get_ie_write_count() const {
    return ie_write_count_;  // Step 0482: Retornar miembro de instancia
}

uint32_t MMU::get_if_write_count() const {
    // Step 0474: Usar nueva variable miembro (mantener compatibilidad con código antiguo)
    return if_write_count_;
}

uint8_t MMU::get_last_ie_written() const {
    return last_ie_written;
}

uint8_t MMU::get_last_if_written() const {
    return last_if_written;
}

uint32_t MMU::get_io_read_count(uint16_t addr) const {
    auto it = io_read_counts.find(addr);
    return (it != io_read_counts.end()) ? it->second : 0;
}
// --- Fin Step 0470 ---

// --- Step 0471: Getters para instrumentación microscópica de IE ---
uint8_t MMU::get_last_ie_write_value() const {
    return last_ie_written;
}

uint16_t MMU::get_last_ie_write_pc() const {
    return last_ie_write_pc;
}

uint32_t MMU::get_last_ie_write_timestamp() const {
    return last_ie_write_timestamp;
}

uint8_t MMU::get_last_ie_read_value() const {
    return last_ie_read_value;
}

uint32_t MMU::get_ie_read_count() const {
    return ie_read_count;
}
// --- Fin Step 0471 ---

// --- Step 0472: Implementación de getters para KEY1 ---
uint32_t MMU::get_key1_write_count() const {
    return key1_write_count;
}

uint8_t MMU::get_last_key1_write_value() const {
    return last_key1_write_value;
}

uint16_t MMU::get_last_key1_write_pc() const {
    return last_key1_write_pc;
}
// --- Fin Step 0472 (KEY1) ---

// --- Step 0472: Implementación de getters para JOYP ---
uint32_t MMU::get_joyp_write_count() const {
    return joyp_write_count;
}

uint8_t MMU::get_last_joyp_write_value() const {
    return last_joyp_write_value;
}

uint16_t MMU::get_last_joyp_write_pc() const {
    return last_joyp_write_pc;
}

// --- Step 0481: Getters para tracking de JOYP reads ---
uint32_t MMU::get_joyp_read_count_program() const {
    return joyp_read_count_program;
}

uint16_t MMU::get_last_joyp_read_pc() const {
    return last_joyp_read_pc;
}

uint8_t MMU::get_last_joyp_read_value() const {
    return last_joyp_read_value;
}
// --- Fin Step 0472 (JOYP) ---

// --- Step 0482: Implementación de getters para LCDC Disable Tracking ---
uint32_t MMU::get_lcdc_disable_events() const {
    return lcdc_disable_events_;
}

uint16_t MMU::get_last_lcdc_write_pc() const {
    return last_lcdc_write_pc_;
}

uint8_t MMU::get_last_lcdc_write_value() const {
    return last_lcdc_write_value_;
}

// --- Step 0484: LCDC Current Getter ---
uint8_t MMU::get_lcdc_current() const {
    return memory_[0xFF40];
}

// --- Step 0484: JOYP Write Distribution Top 5 ---
std::vector<std::pair<uint8_t, uint32_t>> MMU::get_joyp_write_distribution_top5() const {
    std::vector<std::pair<uint8_t, uint32_t>> sorted(joyp_write_distribution_.begin(), joyp_write_distribution_.end());
    std::sort(sorted.begin(), sorted.end(),
              [](const auto& a, const auto& b) { return a.second > b.second; });
    if (sorted.size() > 5) {
        sorted.resize(5);
    }
    return sorted;
}

// --- Step 0484: JOYP Write PCs By Value ---
std::vector<uint16_t> MMU::get_joyp_write_pcs_by_value(uint8_t value) const {
    auto it = joyp_write_pcs_by_value_.find(value);
    if (it != joyp_write_pcs_by_value_.end()) {
        return it->second;
    }
    return std::vector<uint16_t>();
}

// --- Step 0484: JOYP Read Select Bits ---
uint8_t MMU::get_joyp_last_read_select_bits() const {
    return joyp_last_read_select_bits_;
}

// --- Step 0484: JOYP Read Low Nibble ---
uint8_t MMU::get_joyp_last_read_low_nibble() const {
    return joyp_last_read_low_nibble_;
}
// --- Fin Step 0484 (JOYP) ---

// --- Step 0485: JOYP Trace Getters ---
std::vector<JOYPTraceEvent> MMU::get_joyp_trace() const {
    return joyp_trace_;
}

std::vector<JOYPTraceEvent> MMU::get_joyp_trace_tail(size_t n) const {
    if (n >= joyp_trace_.size()) {
        return joyp_trace_;
    }
    return std::vector<JOYPTraceEvent>(joyp_trace_.end() - n, joyp_trace_.end());
}

uint32_t MMU::get_joyp_reads_with_buttons_selected_count() const {
    return joyp_reads_with_buttons_selected_count_;
}

uint32_t MMU::get_joyp_reads_with_dpad_selected_count() const {
    return joyp_reads_with_dpad_selected_count_;
}

uint32_t MMU::get_joyp_reads_with_none_selected_count() const {
    return joyp_reads_with_none_selected_count_;
}
// --- Fin Step 0485 (JOYP Trace) ---
// --- Fin Step 0484 ---
// --- Fin Step 0482 (LCDC Disable Tracking) ---

// --- Step 0474: Implementación de getters para instrumentación quirúrgica de IF/LY/STAT ---
uint32_t MMU::get_if_read_count() const {
    return if_read_count_;
}

uint16_t MMU::get_last_if_write_pc() const {
    return last_if_write_pc_;
}

uint8_t MMU::get_last_if_write_val() const {
    return last_if_write_val_;
}

uint32_t MMU::get_last_if_write_timestamp() const {
    return last_if_write_timestamp_;
}

uint8_t MMU::get_last_if_read_val() const {
    return last_if_read_val_;
}

uint32_t MMU::get_if_writes_0() const {
    return if_writes_0_;
}

uint32_t MMU::get_if_writes_nonzero() const {
    return if_writes_nonzero_;
}

uint8_t MMU::get_ly_read_min() const {
    return ly_read_min_;
}

uint8_t MMU::get_ly_read_max() const {
    return ly_read_max_;
}

uint8_t MMU::get_last_ly_read() const {
    return last_ly_read_;
}

uint8_t MMU::get_last_stat_read() const {
    return last_stat_read_;
}
// --- Fin Step 0474 ---

// --- Step 0475: Source Tagging para IO Polling ---
void MMU::set_irq_poll_active(bool active) {
    irq_poll_active_ = active;
}

uint32_t MMU::get_if_reads_program() const {
    return if_reads_program_;
}

uint32_t MMU::get_if_reads_cpu_poll() const {
    return if_reads_cpu_poll_;
}

uint32_t MMU::get_if_writes_program() const {
    return if_writes_program_;
}

uint32_t MMU::get_ie_reads_program() const {
    return ie_reads_program_;
}

uint32_t MMU::get_ie_reads_cpu_poll() const {
    return ie_reads_cpu_poll_;
}

uint32_t MMU::get_ie_writes_program() const {
    return ie_writes_program_;
}

void MMU::prefill_boot_logo_vram() {
    // Step 0475: Prefill del logo del boot en VRAM (gated por VIBOY_SIM_BOOT_LOGO)
    // La Boot ROM real lee los datos del header (1bpp) y los descomprime a formato Tile (2bpp)
    // antes de copiarlos a la VRAM. Nosotros simulamos este proceso generando los datos
    // ya descomprimidos externamente.
    //
    // Fuente: Pan Docs - "Tile Data", "Tile Map", "Boot ROM Behavior"
    
    // 1. Cargar Tiles del Logo (96 bytes) en VRAM Tile Data (0x8010)
    // Empezamos en 0x8010 (Tile ID 1) para dejar el Tile 0 como blanco puro.
    // 6 tiles x 16 bytes = 96 bytes totales
    for (size_t i = 0; i < sizeof(VIBOY_LOGO_TILES); ++i) {
        memory_[0x8010 + i] = VIBOY_LOGO_TILES[i];
    }
    
    // 2. Cargar Tilemap del Logo en VRAM Map (0x9904 - Fila 8, Columna 4, centrado)
    // CORRECCIÓN Step 0207: Usar 0x9904 para centrar en Fila 8, Columna 4.
    // Antes estaba en 0x9A00 (Fila 16), demasiado abajo y fuera del área visible.
    // Cálculo: 0x9800 (base) + (8 * 32) = 0x9900 (Fila 8) + 4 = 0x9904 (centrado horizontal)
    // 32 bytes = 1 fila completa del mapa de tiles (32 tiles horizontales)
    for (size_t i = 0; i < sizeof(VIBOY_LOGO_MAP); ++i) {
        memory_[0x9904 + i] = VIBOY_LOGO_MAP[i];
    }
}

int MMU::get_boot_logo_prefill_enabled() const {
    return boot_logo_prefill_enabled_ ? 1 : 0;
}

// --- Step 0479: Instrumentación gated por I/O esperado ---
void MMU::set_waits_on_addr(uint16_t addr) {
    waits_on_addr_ = addr;
}

uint32_t MMU::get_ly_changes_this_frame() const {
    return ly_changes_this_frame_;
}

uint32_t MMU::get_stat_mode_changes_count() const {
    return stat_mode_changes_count_;
}

uint32_t MMU::get_if_bit0_set_count_this_frame() const {
    return if_bit0_set_count_this_frame_;
}
// --- Fin Step 0479 ---

// --- Step 0480: Getters para instrumentación HRAM[FF92] ---
uint32_t MMU::get_hram_ff92_write_count() const {
    return hram_ff92_write_count_;
}

uint16_t MMU::get_last_hram_ff92_write_pc() const {
    return last_hram_ff92_write_pc_;
}

uint8_t MMU::get_last_hram_ff92_write_value() const {
    return last_hram_ff92_write_value_;
}

uint32_t MMU::get_last_hram_ff92_write_timestamp() const {
    return last_hram_ff92_write_timestamp_;
}

uint32_t MMU::get_hram_ff92_read_count_program() const {
    return hram_ff92_read_count_program_;
}

uint16_t MMU::get_last_hram_ff92_read_pc() const {
    return last_hram_ff92_read_pc_;
}

uint8_t MMU::get_last_hram_ff92_read_value() const {
    return last_hram_ff92_read_value_;
}
// --- Fin Step 0480 ---

// --- Step 0481: Métodos de HRAM Watchlist Genérica ---
void MMU::add_hram_watch(uint16_t addr) {
    // Validar que es HRAM (0xFF80-0xFFFE)
    if (addr < 0xFF80 || addr > 0xFFFE) {
        return;  // No es HRAM, ignorar
    }
    
    // Verificar si ya está en watchlist
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return;  // Ya está en watchlist
        }
    }
    
    // Añadir nueva entrada
    HRAMWatchEntry entry;
    entry.addr = addr;
    entry.write_count = 0;
    entry.read_count_program = 0;
    entry.first_write_recorded = false;
    hram_watchlist_.push_back(entry);
}

uint32_t MMU::get_hram_write_count(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.write_count;
        }
    }
    return 0;
}

uint16_t MMU::get_hram_last_write_pc(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.last_write_pc;
        }
    }
    return 0;
}

uint8_t MMU::get_hram_last_write_value(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.last_write_value;
        }
    }
    return 0;
}

uint32_t MMU::get_hram_first_write_frame(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.first_write_frame;
        }
    }
    return 0;
}

uint32_t MMU::get_hram_read_count_program(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.read_count_program;
        }
    }
    return 0;
}

uint32_t MMU::get_hram_last_write_frame(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.last_write_frame;
        }
    }
    return 0;
}

uint16_t MMU::get_hram_last_read_pc(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.last_read_pc;
        }
    }
    return 0xFFFF;
}

uint8_t MMU::get_hram_last_read_value(uint16_t addr) const {
    for (const auto& entry : hram_watchlist_) {
        if (entry.addr == addr) {
            return entry.last_read_value;
        }
    }
    return 0;
}
// --- Fin Step 0481 ---
// --- Fin Step 0483 (HRAM last_write_frame, last_read_pc, last_read_value) ---

// --- Fin Step 0475 ---

