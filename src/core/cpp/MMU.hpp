#ifndef MMU_HPP
#define MMU_HPP

#include <cstdint>
#include <vector>

// Forward declaration para evitar dependencia circular
class PPU;

/**
 * MMU (Memory Management Unit) - Unidad de Gestión de Memoria
 * 
 * Gestiona el espacio de direcciones de 16 bits (0x0000 a 0xFFFF = 65536 bytes)
 * de la Game Boy. En esta primera versión, usa un modelo de memoria plana
 * para máxima velocidad de acceso.
 * 
 * Fuente: Pan Docs - Memory Map
 */
class MMU {
public:
    /**
     * Constructor: Inicializa la memoria a 0.
     */
    MMU();

    /**
     * Destructor.
     */
    ~MMU();

    /**
     * Lee un byte (8 bits) de la dirección especificada.
     * 
     * @param addr Dirección de memoria (0x0000 a 0xFFFF)
     * @return Valor del byte leído (0x00 a 0xFF)
     */
    uint8_t read(uint16_t addr) const;

    /**
     * Escribe un byte (8 bits) en la dirección especificada.
     * 
     * @param addr Dirección de memoria (0x0000 a 0xFFFF)
     * @param value Valor a escribir (se enmascara a 8 bits)
     */
    void write(uint16_t addr, uint8_t value);

    /**
     * Carga datos ROM en memoria, empezando en la dirección 0x0000.
     * 
     * @param data Puntero a los datos ROM
     * @param size Tamaño de los datos en bytes
     */
    void load_rom(const uint8_t* data, size_t size);
    
    /**
     * Establece el puntero a la PPU para permitir lectura dinámica del registro STAT.
     * 
     * El registro STAT (0xFF41) tiene bits de solo lectura (0-2) que son actualizados
     * dinámicamente por la PPU. Para leer el valor correcto, la MMU necesita llamar
     * a PPU::get_stat() cuando se lee 0xFF41.
     * 
     * @param ppu Puntero a la instancia de PPU (puede ser nullptr)
     */
    void setPPU(PPU* ppu);

private:
    /**
     * Memoria principal: 65536 bytes (64KB)
     * Usamos std::vector para gestión automática de memoria.
     */
    std::vector<uint8_t> memory_;

    /**
     * Tamaño total del espacio de direcciones (16 bits = 65536 bytes)
     */
    static constexpr size_t MEMORY_SIZE = 0x10000;
    
    /**
     * Puntero a la PPU para lectura dinámica del registro STAT (0xFF41).
     * 
     * Este puntero se establece mediante setPPU() y se usa cuando se lee
     * el registro STAT para obtener el valor actualizado de los bits de solo lectura.
     */
    PPU* ppu_;
};

#endif // MMU_HPP

