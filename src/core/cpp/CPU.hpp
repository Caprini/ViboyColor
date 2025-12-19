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

    // ========== Helpers de ALU (Arithmetic Logic Unit) ==========
    // Todos los métodos son inline para máximo rendimiento en el bucle crítico
    
    /**
     * Suma un valor al registro A y actualiza flags.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre, es suma)
     * - H: 1 si hay half-carry (bit 3 -> 4), 0 en caso contrario
     * - C: 1 si hay carry (overflow 8 bits), 0 en caso contrario
     * 
     * @param value Valor a sumar a A
     */
    inline void alu_add(uint8_t value);

    /**
     * Resta un valor del registro A y actualiza flags.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 1 (siempre, es resta)
     * - H: 1 si hay half-borrow (bit 4 -> 3), 0 en caso contrario
     * - C: 1 si hay borrow (underflow), 0 en caso contrario
     * 
     * @param value Valor a restar de A
     */
    inline void alu_sub(uint8_t value);

    /**
     * Operación AND lógica entre A y un valor.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre)
     * - H: 1 (QUIRK del hardware: AND siempre pone H=1)
     * - C: 0 (siempre)
     * 
     * @param value Valor para AND con A
     */
    inline void alu_and(uint8_t value);

    /**
     * Operación XOR lógica entre A y un valor.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre)
     * - H: 0 (siempre)
     * - C: 0 (siempre)
     * 
     * @param value Valor para XOR con A
     */
    inline void alu_xor(uint8_t value);

    // Punteros a componentes (inyección de dependencias)
    MMU* mmu_;              // Puntero a MMU (no poseído)
    CoreRegisters* regs_;   // Puntero a Registros (no poseído)

    // Contador de ciclos acumulados
    uint32_t cycles_;
};

#endif // CPU_HPP

