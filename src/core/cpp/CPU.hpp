#ifndef CPU_HPP
#define CPU_HPP

#include <cstdint>

// Forward declarations (evitar includes circulares)
class MMU;
class CoreRegisters;

/**
 * CPU - Procesador LR35902 de la Game Boy
 * 
 * Esta clase implementa el ciclo de instrucción (Fetch-Decode-Execute)
 * de la CPU de la Game Boy. Utiliza inyección de dependencias:
 * - NO posee (own) la MMU ni los Registros
 * - Solo mantiene punteros a ellos para manipularlos
 * 
 * El ciclo básico es:
 * 1. Fetch: Lee el opcode de memoria en dirección PC
 * 2. Increment: Avanza PC
 * 3. Decode/Execute: Identifica y ejecuta la operación
 * 
 * Fuente: Pan Docs - CPU Instruction Set
 */
class CPU {
public:
    /**
     * Constructor: Inicializa la CPU con punteros a MMU y Registros.
     * 
     * @param mmu Puntero a la MMU (no debe ser nullptr)
     * @param registers Puntero a los Registros (no debe ser nullptr)
     */
    CPU(MMU* mmu, CoreRegisters* registers);

    /**
     * Destructor.
     */
    ~CPU();

    /**
     * Ejecuta un ciclo de instrucción (Fetch-Decode-Execute).
     * 
     * Este método:
     * 1. Lee el opcode de memoria en dirección PC
     * 2. Incrementa PC
     * 3. Ejecuta la instrucción correspondiente
     * 
     * @return Número de M-Cycles consumidos (0 si hay error)
     */
    int step();

    /**
     * Obtiene el contador de ciclos acumulados.
     * 
     * @return Total de M-Cycles ejecutados desde la creación
     */
    uint32_t get_cycles() const;

private:
    /**
     * Lee un byte de memoria en la dirección PC e incrementa PC.
     * 
     * Helper interno para el ciclo Fetch.
     * 
     * @return Byte leído de memoria
     */
    uint8_t fetch_byte();

    // Punteros a componentes (inyección de dependencias)
    MMU* mmu_;              // Puntero a MMU (no poseído)
    CoreRegisters* regs_;   // Puntero a Registros (no poseído)

    // Contador de ciclos acumulados
    uint32_t cycles_;
};

#endif // CPU_HPP

