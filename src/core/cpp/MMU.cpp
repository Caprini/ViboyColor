#include "MMU.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include "Joypad.hpp"
#include <cstring>
#include <algorithm>

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
    , mbc1_bank_low5_(1)
    , mbc1_bank_high2_(0)
    , mbc1_mode_(0)
    , mbc3_rtc_reg_(0)
    , mbc3_latch_ready_(false)
    , ram_bank_size_(0x2000)
    , ram_bank_count_(0)
    , ram_bank_(0)
    , ram_enabled_(false) {
    // Inicializar memoria a 0
    // --- Step 0189: Inicialización de Registros de Hardware (Post-BIOS) ---
    // Estos son los valores que los registros de I/O tienen después de que la
    // Boot ROM finaliza. Los juegos dependen de este estado inicial.
    // Fuente: Pan Docs - "Power Up Sequence"
    
    // PPU / Video
    memory_[0xFF40] = 0x91; // LCDC
    memory_[0xFF41] = 0x85; // STAT (bits escribibles 3-7, bits 0-2 controlados por PPU)
    memory_[0xFF42] = 0x00; // SCY
    memory_[0xFF43] = 0x00; // SCX
    // 0xFF44: LY se controla dinámicamente por la PPU
    memory_[0xFF45] = 0x00; // LYC
    memory_[0xFF46] = 0xFF; // DMA
    memory_[0xFF47] = 0xFC; // BGP (Post-BIOS: 0xFC, aunque muchos juegos esperan 0xE4)
    memory_[0xFF48] = 0xFF; // OBP0
    memory_[0xFF49] = 0xFF; // OBP1
    memory_[0xFF4A] = 0x00; // WY
    memory_[0xFF4B] = 0x00; // WX

    // Sonido (APU) - Valores iniciales
    memory_[0xFF10] = 0x80; // NR10
    memory_[0xFF11] = 0xBF; // NR11
    memory_[0xFF12] = 0xF3; // NR12
    memory_[0xFF14] = 0xBF; // NR14
    memory_[0xFF16] = 0x3F; // NR21
    memory_[0xFF17] = 0x00; // NR22
    memory_[0xFF19] = 0xBF; // NR24
    memory_[0xFF1A] = 0x7F; // NR30
    memory_[0xFF1B] = 0xFF; // NR31
    memory_[0xFF1C] = 0x9F; // NR32
    memory_[0xFF1E] = 0xBF; // NR34
    memory_[0xFF20] = 0xFF; // NR41
    memory_[0xFF21] = 0x00; // NR42
    memory_[0xFF22] = 0x00; // NR43
    memory_[0xFF23] = 0xBF; // NR44
    memory_[0xFF24] = 0x77; // NR50
    memory_[0xFF25] = 0xF3; // NR51
    memory_[0xFF26] = 0xF1; // NR52 (F1 para DMG)

    // Interrupciones
    memory_[0xFF0F] = 0x01; // IF (V-Blank interrupt request)
    memory_[0xFFFF] = 0x00; // IE
    
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
    // -----------------------------------------
}

MMU::~MMU() {
    // std::vector se libera automáticamente
}

uint8_t MMU::read(uint16_t addr) const {
    // Asegurar que la dirección esté en el rango válido (0x0000-0xFFFF)
    addr &= 0xFFFF;
    
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
    
    // CRÍTICO: El registro P1 (0xFF00) es controlado por el Joypad
    // La CPU escribe en P1 para seleccionar qué fila de botones leer, y lee
    // el estado de los botones de la fila seleccionada
    if (addr == 0xFF00) {
        if (joypad_ != nullptr) {
            return joypad_->read_p1();
        }
        // Si el Joypad no está conectado, devolver valor por defecto (0xCF = ninguna fila seleccionada)
        return 0xCF;
    }
    
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
            // DESCOMENTAR PARA ACTIVAR DEBUG:
            // printf("[MMU] Read LY: %d\n", val);
            return val;
        }
        return 0;
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
                
                // --- Step 0282: Monitor de lecturas en bancos superiores ---
                // COMENTADO EN STEP 0283: Optimización de rendimiento para alcanzar 60 FPS
                // Este log generaba demasiadas líneas y afectaba el rendimiento.
                /*
                static int bank_read_count = 0;
                if (bank_read_count < 20) {
                    printf("[BANK-READ] Read %04X (Bank:%d Offset:%04X) -> %02X en PC:0x%04X\n",
                           addr, bankN_rom_, (uint16_t)(addr - 0x4000), val, debug_current_pc);
                    bank_read_count++;
                }
                */
                
                return val;
            }
            return 0xFF;
        }
    }

    // --- Step 0289: Monitor de Lecturas de VRAM ([VRAM-READ]) ---
    // Captura lecturas de VRAM (0x8000-0x9FFF) para verificar qué valores lee la PPU.
    // Esto permite confirmar si la PPU está leyendo datos válidos o solo ceros.
    // Fuente: Pan Docs - "VRAM (Video RAM)": 0x8000-0x9FFF contiene Tile Data y Tile Maps
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        uint8_t vram_value = memory_[addr];
        static int vram_read_count = 0;
        if (vram_read_count < 100) {  // Límite para evitar saturación
            printf("[VRAM-READ] Read %04X -> %02X (PC:0x%04X Bank:%d)\n",
                   addr, vram_value, debug_current_pc, current_rom_bank_);
            vram_read_count++;
        }
        return vram_value;
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
                    // RTC no implementado todavía
                    return 0x00;
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

    // --- Step 0251: IMPLEMENTACIÓN DMA (OAM TRANSFER) ---
    if (addr == 0xFF46) {
        // --- Step 0286: Monitor de Disparo de OAM DMA ([DMA-TRIGGER]) ---
        // Detecta cuando se activa el DMA para transferir datos a OAM (0xFE00-0xFE9F)
        // El DMA copia 160 bytes desde la dirección (value << 8) a OAM
        // Fuente: Pan Docs - "DMA Transfer": Escritura en 0xFF46 inicia transferencia
        printf("[DMA-TRIGGER] DMA activado: Source=0x%02X00 (0x%04X-0x%04X) -> OAM (0xFE00-0xFE9F) | PC:0x%04X\n",
               value, static_cast<uint16_t>(value) << 8, (static_cast<uint16_t>(value) << 8) + 159, debug_current_pc);
        
        uint16_t source_base = static_cast<uint16_t>(value) << 8;
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

    // --- Step 0275: Monitor de Salto de Banco (Bank Watcher) ---
    // Es posible que el juego cambie de banco y el PC se pierda.
    // Vamos a loguear cualquier escritura en el área de control del MBC (0x2000-0x3FFF).
    if (addr >= 0x2000 && addr <= 0x3FFF) {
        printf("[MBC-WRITE] Cambio de Banco solicitado: 0x%02X en PC:0x%04X (Banco actual: %d)\n", 
               value, debug_current_pc, get_current_rom_bank());
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
                    if (value <= 0x03) {
                        ram_bank_ = value & 0x03;
                        mbc3_rtc_reg_ = 0;
                    } else if (value >= 0x08 && value <= 0x0C) {
                        // RTC registro seleccionado (stub)
                        mbc3_rtc_reg_ = value;
                    }
                    return;
                } else {  // 0x6000-0x7FFF latch clock (stub)
                    mbc3_latch_ready_ = (value == 0x01);
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
                    // RTC no implementado
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

    // --- Step 0274: IE-WRITE - Rastreo del Registro de Habilitación de Interrupciones ---
    // Queremos capturar CADA escritura en el registro IE (0xFFFF) para identificar
    // quién deshabilita las interrupciones y cuándo ocurre.
    if (addr == 0xFFFF) {
        printf("[IE-WRITE] Nuevo valor: 0x%02X desde PC: 0x%04X (Banco:%d)\n",
               value, debug_current_pc, current_rom_bank_);
    }

    // --- Step 0290: Monitor de Cambios en LCDC ([LCDC-CHANGE]) ---
    // Captura todos los cambios en LCDC (0xFF40) para verificar la configuración del LCD.
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
        if (old_lcdc != value) {
            printf("[LCDC-CHANGE] 0x%02X -> 0x%02X en PC:0x%04X (Bank:%d) | LCD:%s BG:%s Window:%s\n",
                   old_lcdc, value, debug_current_pc, current_rom_bank_,
                   (value & 0x80) ? "ON" : "OFF",
                   (value & 0x01) ? "ON" : "OFF",
                   (value & 0x20) ? "ON" : "OFF");
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
    // --- Step 0273: Trigger D732 - Instrumentación de Escritura ---
    // Queremos saber QUIÉN intenta escribir en 0xD732 aunque sea un cero,
    // o si alguien intenta escribir algo distinto de cero.
    if (addr == 0xD732) {
        printf("[TRIGGER-D732] Write %02X from PC:%04X (Bank:%d)\n",
               value, debug_current_pc, current_rom_bank_);
    }

    // --- Step 0290: Monitor de Carga de Tiles ([TILE-LOAD]) ---
    // Detecta escrituras en el área de Tile Data (0x8000-0x97FF) que probablemente
    // sean carga de datos de tiles (distintos de 0x00, que es limpieza).
    // Este monitor es crítico porque los hallazgos del Step 0289 confirmaron que
    // los tiles referenciados por el tilemap están vacíos (solo ceros).
    // Fuente: Pan Docs - "Tile Data": 0x8000-0x97FF contiene 384 tiles de 16 bytes cada uno
    if (addr >= 0x8000 && addr <= 0x97FF) {
        // Filtrar valores comunes de inicialización/borrado para detectar datos reales
        if (value != 0x00 && value != 0x7F) {
            static int tile_load_count = 0;
            if (tile_load_count < 500) {  // Límite alto para capturar actividad completa
                // Calcular Tile ID aproximado basado en la dirección
                // Cada tile ocupa 16 bytes, Tile 0 empieza en 0x8000 (unsigned) o 0x9000 (signed)
                uint16_t tile_offset = addr - 0x8000;
                uint8_t tile_id_approx = tile_offset / 16;
                
                printf("[TILE-LOAD] Write %04X=%02X (TileID~%d, Byte:%d) PC:%04X (Bank:%d)\n",
                       addr, value, tile_id_approx, tile_offset % 16, debug_current_pc, current_rom_bank_);
                tile_load_count++;
            }
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

    memory_[addr] = value;
}

void MMU::load_rom(const uint8_t* data, size_t size) {
    // Copiar toda la ROM a rom_data_
    rom_data_.resize(size);
    std::memcpy(rom_data_.data(), data, size);

    // Copiar Banco 0 a memory_ para compatibilidad
    size_t bank0_size = (size > 0x4000) ? 0x4000 : size;
    std::memcpy(memory_.data(), data, bank0_size);

    // Leer Header para detectar tipo de cartucho / tamaños
    uint8_t cart_type = (size > 0x0147) ? data[0x0147] : 0x00;
    uint8_t rom_size_code = (size > 0x0148) ? data[0x0148] : 0x00;
    uint8_t ram_size_code = (size > 0x0149) ? data[0x0149] : 0x00;

    configure_mbc_from_header(cart_type, rom_size_code, ram_size_code);
    update_bank_mapping();

    printf("[MBC] ROM loaded: %zu bytes (%zu banks) | Type: 0x%02X\n",
           size, rom_bank_count_, cart_type);
}

void MMU::setPPU(PPU* ppu) {
    ppu_ = ppu;
}

void MMU::setTimer(Timer* timer) {
    timer_ = timer;
}

void MMU::setJoypad(Joypad* joypad) {
    joypad_ = joypad;
}

void MMU::request_interrupt(uint8_t bit) {
    // Validar que el bit esté en el rango válido (0-4)
    if (bit > 4) {
        return;  // Bit inválido, ignorar
    }
    
    // Leer el valor actual del registro IF (0xFF0F)
    uint8_t if_reg = read(0xFF0F);
    
    // Activar el bit correspondiente (OR bitwise)
    if_reg |= (1 << bit);
    
    // Escribir el valor actualizado de vuelta a memoria
    write(0xFF0F, if_reg);

    static int irq_log_count = 0;
    if (irq_log_count < 30) {
        printf("[IRQ] Request bit=%u IF:%02X PC:%04X\n", bit, if_reg, debug_current_pc);
        irq_log_count++;
    }
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

uint16_t MMU::normalize_rom_bank(uint16_t bank) const {
    if (rom_bank_count_ == 0) {
        return bank;
    }
    uint16_t normalized = static_cast<uint16_t>(bank % static_cast<uint16_t>(rom_bank_count_));
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
            break;
        }

        case MBCType::MBC3: {
            uint16_t bank = current_rom_bank_;
            if (bank == 0) bank = 1;
            bank0_rom_ = 0;
            bankN_rom_ = normalize_rom_bank(bank);
            break;
        }

        case MBCType::MBC5: {
            bank0_rom_ = 0;
            bankN_rom_ = normalize_rom_bank(current_rom_bank_);
            break;
        }

        case MBCType::MBC2:
        case MBCType::ROM_ONLY:
        default:
            bank0_rom_ = 0;
            bankN_rom_ = 1;
            break;
    }

    // --- Step 0282: Auditoría de índices de bancos ---
    if (old_bank0 != bank0_rom_ || old_bankN != bankN_rom_) {
        printf("[BANK-AUDIT] Cambio de mapeo: Banco0:%d->%d | BancoN:%d->%d (Modo MBC1:%d) en PC:0x%04X\n",
               old_bank0, bank0_rom_, old_bankN, bankN_rom_, mbc1_mode_, debug_current_pc);
    }
}

uint16_t MMU::get_current_rom_bank() const {
    // Retornar el banco mapeado en 0x4000-0x7FFF (bankN_rom_)
    return bankN_rom_;
}

