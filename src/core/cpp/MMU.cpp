#include "MMU.hpp"
#include <cstring>

MMU::MMU() : memory_(MEMORY_SIZE, 0) {
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
    
    // Acceso directo al array: O(1), sin overhead de Python
    return memory_[addr];
}

void MMU::write(uint16_t addr, uint8_t value) {
    // Asegurar que la dirección esté en el rango válido
    addr &= 0xFFFF;
    
    // Enmascarar el valor a 8 bits
    value &= 0xFF;
    
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

