#include "MMU.hpp"
#include "PPU.hpp"
#include <cstring>

MMU::MMU() : memory_(MEMORY_SIZE, 0), ppu_(nullptr) {
    // Inicializar memoria a 0
    // CRÍTICO: En una Game Boy real, la Boot ROM inicializa BGP (0xFF47) a 0xE4
    // Por ahora, lo haremos en el wrapper Python o cuando se necesite
}

MMU::~MMU() {
    // std::vector se libera automáticamente
}

uint8_t MMU::read(uint16_t addr) const {
    printf("[MMU::read] Iniciando, addr=0x%04X\n", addr);
    fflush(stdout);
    
    // Asegurar que la dirección esté en el rango válido (0x0000-0xFFFF)
    addr &= 0xFFFF;
    
    printf("[MMU::read] Dirección normalizada: 0x%04X\n", addr);
    fflush(stdout);
    
    // CRÍTICO: El registro STAT (0xFF41) tiene bits de solo lectura (0-2)
    // que son actualizados dinámicamente por la PPU. La MMU es la dueña de la memoria,
    // así que construimos el valor de STAT combinando:
    // - Bits escribibles (3-7) desde la memoria
    // - Bits de solo lectura (0-2) desde el estado actual de la PPU
    if (addr == 0xFF41) {
        printf("[MMU::read] Leyendo STAT (0xFF41)...\n");
        fflush(stdout);
        
        printf("[MMU::read] ppu_ puntero: %p\n", (void*)ppu_);
        fflush(stdout);
        
        if (ppu_ != nullptr) {
            printf("[MMU::read] ppu_ es válido, leyendo stat_base...\n");
            fflush(stdout);
            
            // Leer el valor base de STAT (bits escribibles) de la memoria
            uint8_t stat_base = memory_[addr];
            
            printf("[MMU::read] stat_base leído: 0x%02X\n", stat_base);
            fflush(stdout);
            
            printf("[MMU::read] Llamando a ppu_->get_mode()...\n");
            fflush(stdout);
            
            // Obtener el modo actual de la PPU (bits 0-1)
            uint8_t mode = static_cast<uint8_t>(ppu_->get_mode());
            
            printf("[MMU::read] mode obtenido: %d\n", mode);
            fflush(stdout);
            
            printf("[MMU::read] Llamando a ppu_->get_ly()...\n");
            fflush(stdout);
            
            // Calcular LYC=LY Coincidence Flag (bit 2)
            uint8_t ly = ppu_->get_ly();
            
            printf("[MMU::read] ly obtenido: %d\n", ly);
            fflush(stdout);
            
            printf("[MMU::read] Llamando a ppu_->get_lyc()...\n");
            fflush(stdout);
            
            uint8_t lyc = ppu_->get_lyc();
            
            printf("[MMU::read] lyc obtenido: %d\n", lyc);
            fflush(stdout);
            
            uint8_t lyc_match = ((ly & 0xFF) == (lyc & 0xFF)) ? 0x04 : 0x00;
            
            // Combinar: bits escribibles (3-7) | modo actual (0-1) | LYC match (2)
            // Bit 7 siempre es 1 según Pan Docs
            uint8_t result = (stat_base & 0xF8) | mode | lyc_match | 0x80;
            
            printf("[MMU::read] STAT result: 0x%02X\n", result);
            fflush(stdout);
            
            return result;
        }
        printf("[MMU::read] ppu_ es nullptr, retornando valor por defecto\n");
        fflush(stdout);
        
        // Si la PPU no está conectada, devolver valor por defecto
        // Bit 7 siempre es 1 según Pan Docs
        return 0x80;
    }
    
    printf("[MMU::read] Acceso directo a memoria[0x%04X]...\n", addr);
    fflush(stdout);
    
    // Acceso directo al array: O(1), sin overhead de Python
    uint8_t result = memory_[addr];
    
    printf("[MMU::read] Valor leído: 0x%02X\n", result);
    fflush(stdout);
    
    return result;
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

void MMU::setPPU(PPU* ppu) {
    printf("[MMU::setPPU] Llamado con puntero: %p\n", (void*)ppu);
    fflush(stdout);
    
    if (ppu == nullptr) {
        printf("[MMU::setPPU] ADVERTENCIA: Se está configurando ppu_ a nullptr\n");
        fflush(stdout);
    } else {
        printf("[MMU::setPPU] Puntero válido, asignando...\n");
        fflush(stdout);
    }
    
    ppu_ = ppu;
    
    printf("[MMU::setPPU] ppu_ configurado a: %p\n", (void*)ppu_);
    fflush(stdout);
}

