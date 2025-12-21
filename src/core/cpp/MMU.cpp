#include "MMU.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include "Joypad.hpp"
#include <cstring>
#include <cstdio>

// --- Step 0197: Datos del Logo de Nintendo (Post-BIOS) ---
// La Boot ROM copia los datos del logo desde el encabezado del cartucho (0x0104-0x0133)
// a la VRAM. Estos son los 48 bytes estándar del logo de Nintendo que se encuentran
// en el encabezado de todos los cartuchos de Game Boy.
// Fuente: Pan Docs - "Nintendo Logo", Cart Header (0x0104-0x0133)
static const uint8_t NINTENDO_LOGO_DATA[48] = {
    0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B,
    0x03, 0x73, 0x00, 0x83, 0x00, 0x0C, 0x00, 0x0D,
    0x00, 0x08, 0x11, 0x1F, 0x88, 0x89, 0x00, 0x0E,
    0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9, 0x99,
    0xBB, 0xBB, 0x67, 0x63, 0x6E, 0x0E, 0xEC, 0xCC,
    0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33, 0x3E
};

// Tilemap del logo de Nintendo en la pantalla (0x9904-0x9927)
// La Boot ROM configura el tilemap para mostrar el logo centrado en la parte superior.
// 12 tiles en una fila (0x01 a 0x0C) seguidos de tiles vacíos (0x00).
// Fuente: Pan Docs - "Boot ROM Behavior", Tile Map Layout
static const uint8_t NINTENDO_LOGO_TILEMAP[36] = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, // Fila 1: Logo tiles
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, // Fila 2: Vacío
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00  // Fila 3: Vacío
};

MMU::MMU() : memory_(MEMORY_SIZE, 0), ppu_(nullptr), timer_(nullptr), joypad_(nullptr) {
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
    
    // --- Step 0197: Pre-cargar VRAM con el logo de Nintendo (Post-BIOS) ---
    // La Boot ROM copia los datos del logo desde el encabezado del cartucho (0x0104-0x0133)
    // a la VRAM. Estos 48 bytes forman 3 tiles (16 bytes cada uno).
    // La Boot ROM también configura el tilemap para mostrar el logo centrado.
    // Fuente: Pan Docs - "Boot ROM Behavior", "Nintendo Logo"
    
    // Copiar los datos del logo a la VRAM (0x8000-0x802F)
    // Los 48 bytes del logo se organizan como 3 tiles consecutivos
    for (size_t i = 0; i < sizeof(NINTENDO_LOGO_DATA); ++i) {
        memory_[0x8000 + i] = NINTENDO_LOGO_DATA[i];
    }
    
    // Copiar el tilemap a la VRAM (0x9904-0x9927)
    // El tilemap configura qué tiles mostrar en la pantalla (12 tiles del logo en la primera fila)
    for (size_t i = 0; i < sizeof(NINTENDO_LOGO_TILEMAP); ++i) {
        memory_[0x9904 + i] = NINTENDO_LOGO_TILEMAP[i];
    }
}

MMU::~MMU() {
    // std::vector se libera automáticamente
}

uint8_t MMU::read(uint16_t addr) const {
    // Asegurar que la dirección esté en el rango válido (0x0000-0xFFFF)
    addr &= 0xFFFF;
    
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
    
    // Acceso directo al array: O(1), sin overhead de Python
    return memory_[addr];
}

void MMU::write(uint16_t addr, uint8_t value) {
    // Asegurar que la dirección esté en el rango válido
    addr &= 0xFFFF;
    
    // Enmascarar el valor a 8 bits
    value &= 0xFF;
    
    // CRÍTICO: El registro DIV (0xFF04) tiene comportamiento especial
    // Cualquier escritura en 0xFF04 resetea el contador del Timer a 0
    // El valor escrito es ignorado
    if (addr == 0xFF04) {
        if (timer_ != nullptr) {
            timer_->write_div();
        }
        // No escribimos en memoria porque DIV no es un registro de memoria real
        // Es un registro de hardware que se lee/escribe dinámicamente
        return;
    }
    
    // CRÍTICO: Los registros TIMA (0xFF05), TMA (0xFF06) y TAC (0xFF07) son controlados por el Timer
    // Estos registros pueden ser leídos y escritos por el juego, pero están almacenados
    // en el hardware del Timer, no en la memoria
    if (addr == 0xFF05) {
        if (timer_ != nullptr) {
            timer_->write_tima(value);
        }
        // No escribimos en memoria porque TIMA no es un registro de memoria real
        return;
    }
    
    if (addr == 0xFF06) {
        if (timer_ != nullptr) {
            timer_->write_tma(value);
        }
        // No escribimos en memoria porque TMA no es un registro de memoria real
        return;
    }
    
    if (addr == 0xFF07) {
        if (timer_ != nullptr) {
            timer_->write_tac(value);
        }
        // No escribimos en memoria porque TAC no es un registro de memoria real
        return;
    }
    
    // CRÍTICO: El registro P1 (0xFF00) es controlado por el Joypad
    // La CPU escribe en P1 para seleccionar qué fila de botones leer
    if (addr == 0xFF00) {
        if (joypad_ != nullptr) {
            joypad_->write_p1(value);
        }
        // No escribimos en memoria porque P1 no es un registro de memoria real
        // Es un registro de hardware que se lee/escribe dinámicamente
        return;
    }
    
    // Escritura directa: O(1), sin overhead de Python
    memory_[addr] = value;
}

void MMU::load_rom(const uint8_t* data, size_t size) {
    // Validar que los datos no excedan el tamaño de memoria
    size_t copy_size = (size > MEMORY_SIZE) ? MEMORY_SIZE : size;
    
    // Copiar los datos ROM a memoria, empezando en 0x0000
    // Usamos memcpy para máxima velocidad
    std::memcpy(memory_.data(), data, copy_size);
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
}

