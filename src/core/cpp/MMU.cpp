#include "MMU.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include <cstring>

MMU::MMU() : memory_(MEMORY_SIZE, 0), ppu_(nullptr), timer_(nullptr) {
    // Inicializar memoria a 0
    // CRÍTICO: En una Game Boy real, la Boot ROM inicializa BGP (0xFF47) a 0xE4
    // Por ahora, lo haremos en el wrapper Python o cuando se necesite
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

