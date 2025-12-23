#include "MMU.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include "Joypad.hpp"
#include <cstring>

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

MMU::MMU() : memory_(MEMORY_SIZE, 0), ppu_(nullptr), timer_(nullptr), joypad_(nullptr), debug_current_pc(0), current_rom_bank_(1) {
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
    
    // --- Step 0260: MBC1 ROM BANKING ---
    // Implementación básica de MBC1 para soportar cartuchos grandes (>32KB).
    // 
    // MBC1 Banking:
    // - 0x0000-0x3FFF: Siempre mapea al Banco 0 (fijo)
    // - 0x4000-0x7FFF: Mapea al banco seleccionado (current_rom_bank_)
    // 
    // El banco se selecciona escribiendo en 0x2000-0x3FFF (ver método write).
    // Fuente: Pan Docs - "MBC1", "Memory Bank Controllers"
    
    // Si hay datos ROM cargados, usar banking
    if (!rom_data_.empty()) {
        if (addr >= 0x0000 && addr <= 0x3FFF) {
            // Banco 0 fijo: leer desde el principio de la ROM
            if (addr < rom_data_.size()) {
                return rom_data_[addr];
            }
            return 0x00;  // Fuera de rango
        } else if (addr >= 0x4000 && addr <= 0x7FFF) {
            // Banco conmutable: calcular offset
            // Offset = (banco * 0x4000) + (addr - 0x4000)
            size_t bank_offset = static_cast<size_t>(current_rom_bank_) * 0x4000;
            size_t rom_addr = bank_offset + (addr - 0x4000);
            
            // --- Step 0261: Log de seguridad para lecturas fuera de rango ---
            if (rom_addr >= rom_data_.size()) {
                printf("[MBC1 CRITICAL] Intento de lectura fuera de ROM! Offset: %zu, Size: %zu, Bank: %d, Addr: 0x%04X\n", 
                       rom_addr, rom_data_.size(), current_rom_bank_, addr);
                return 0xFF;
            }
            
            return rom_data_[rom_addr];
        }
    }
    
    // Para direcciones fuera de ROM o si no hay ROM cargada, usar memoria normal
    // Acceso directo al array: O(1), sin overhead de Python
    return memory_[addr];
}

void MMU::write(uint16_t addr, uint8_t value) {
    // Asegurar que la dirección esté en el rango válido
    addr &= 0xFFFF;
    
    // --- Step 0239: IMPLEMENTACIÓN DE ECHO RAM ---
    // Echo RAM (0xE000-0xFDFF) es un espejo de WRAM (0xC000-0xDDFF)
    // Escribir en el espejo debe modificar la memoria real
    // Fuente: Pan Docs - Memory Map, Echo RAM
    if (addr >= 0xE000 && addr <= 0xFDFF) {
        addr = addr - 0x2000;  // Redirigir a WRAM: 0xE645 -> 0xC645
    }
    // -----------------------------------------
    
    // Enmascarar el valor a 8 bits
    value &= 0xFF;
    
    // --- Step 0251: IMPLEMENTACIÓN DMA (OAM TRANSFER) ---
    // Cuando se escribe un valor XX en 0xFF46, se inicia una transferencia DMA
    // que copia 160 bytes desde la dirección XX00 hasta OAM (0xFE00-0xFE9F)
    // Fuente: Pan Docs - "DMA Transfer"
    // 
    // En hardware real, la transferencia tarda ~160 microsegundos (640 ciclos),
    // pero para simplificar implementamos una copia instantánea.
    // Durante la transferencia real, la CPU solo puede acceder a HRAM (0xFF80-0xFFFE),
    // pero por ahora ignoramos esta restricción.
    if (addr == 0xFF46) {
        // 1. Calcular dirección origen: value * 0x100 (ej: 0xC0 -> 0xC000)
        uint16_t source_base = static_cast<uint16_t>(value) << 8;
        
        // 2. Copiar 160 bytes (0xA0) a OAM (0xFE00-0xFE9F)
        for (int i = 0; i < 160; i++) {
            uint16_t source_addr = source_base + i;
            // Leer desde la dirección fuente (puede ser ROM, RAM, VRAM, etc.)
            uint8_t data = read(source_addr);
            // Escribir directamente en OAM
            // Validar que la dirección de destino esté dentro de los límites
            if ((0xFE00 + i) < MEMORY_SIZE) {
                memory_[0xFE00 + i] = data;
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0259: VRAM WRITE MONITOR ---
    // Monitorizar las primeras 50 escrituras en VRAM para ver qué datos llegan
    // Si la VRAM está vacía (ceros), la PPU renderizará píxeles de índice 0 (verdes/blancos).
    // Si vemos valores distintos de cero, significa que la CPU está copiando datos.
    // Si solo vemos ceros, el problema está en la carga de datos gráficos (posiblemente MBC).
    static int vram_write_counter = 0;
    if (addr >= 0x8000 && addr <= 0x9FFF) {
        if (vram_write_counter < 50) {
            printf("[VRAM] PC:%04X -> Write VRAM [%04X] = %02X\n", debug_current_pc, addr, value);
            vram_write_counter++;
        }
    }
    // -----------------------------------------
    
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
    
    // --- Step 0260: MBC1 ROM BANKING ---
    // En hardware real, la ROM (0x0000-0x7FFF) es de solo lectura.
    // Escribir en este rango no modifica los datos de la ROM, sino que se envía
    // al MBC (Memory Bank Controller) del cartucho para controlar el cambio de bancos.
    // 
    // MBC1 Banking Control:
    // - 0x2000-0x3FFF: Selección de banco ROM (bits 0-4, banco 0 se trata como 1)
    // - 0x0000-0x1FFF: Habilitación/deshabilitación de RAM (ignoramos por ahora)
    // 
    // Fuente: Pan Docs - "MBC1", "Memory Bank Controllers"
    if (addr < 0x8000) {
        // ROM es de solo lectura: NO escribir en memory_
        
        // --- Step 0260: MBC1 ROM BANK SELECTION ---
        // Interceptar escrituras en 0x2000-0x3FFF para cambiar el banco ROM
        // --- Step 0261: MBC ACTIVITY MONITOR ---
        // Instrumentar cambios de banco ROM para diagnosticar si el juego está
        // seleccionando bancos correctamente. Solo logueamos cuando el banco cambia.
        if (addr >= 0x2000 && addr <= 0x3FFF) {
            // Selección de banco ROM (bits 0-4 del valor escrito)
            uint8_t new_bank = value & 0x1F;  // Máscara para bits 0-4
            
            // En MBC1, el banco 0 se trata como banco 1
            if (new_bank == 0) {
                new_bank = 1;
            }
            
            // Validar que el banco no exceda el tamaño de la ROM
            // Cada banco es de 16KB (0x4000 bytes)
            size_t max_banks = rom_data_.size() / 0x4000;
            if (max_banks > 0 && new_bank >= max_banks) {
                new_bank = max_banks - 1;  // Limitar al último banco disponible
            }
            
            // --- Step 0261: Log solo si el banco cambia para no saturar ---
            if (new_bank != current_rom_bank_) {
                printf("[MBC1] PC:%04X -> ROM Bank Switch: %d -> %d\n", 
                       debug_current_pc, current_rom_bank_, new_bank);
            }
            
            current_rom_bank_ = new_bank;
        }
        // -----------------------------------------
        
        // No escribir en memoria para evitar corrupción
        return;
    }
    // -----------------------------------------
    
    // Escritura directa: O(1), sin overhead de Python
    memory_[addr] = value;
}

void MMU::load_rom(const uint8_t* data, size_t size) {
    // --- Step 0260: MBC1 ROM BANKING ---
    // Cargar toda la ROM en rom_data_ para soportar cartuchos grandes (>32KB).
    // El banco 0 se carga también en memory_[0x0000-0x3FFF] para compatibilidad
    // con código que accede directamente a memory_.
    // 
    // Fuente: Pan Docs - "MBC1", "Memory Bank Controllers"
    
    // Redimensionar rom_data_ y copiar toda la ROM
    rom_data_.resize(size);
    std::memcpy(rom_data_.data(), data, size);
    
    // También copiar el banco 0 (primeros 16KB) a memory_ para compatibilidad
    size_t bank0_size = (size > 0x4000) ? 0x4000 : size;
    std::memcpy(memory_.data(), data, bank0_size);
    
    // Inicializar el banco actual a 1 (banco 0 está siempre mapeado en 0x0000-0x3FFF)
    current_rom_bank_ = 1;
    
    printf("[MBC1] ROM loaded: %zu bytes (%zu banks)\n", size, size / 0x4000);
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

