#include "Registers.hpp"

/**
 * Implementación de CoreRegisters.
 * 
 * Los métodos inline están definidos en el header para máximo rendimiento.
 * Aquí implementamos el constructor con inicialización Post-BIOS.
 * 
 * CRÍTICO: El estado inicial de los registros de la CPU debe coincidir
 * exactamente con el estado que la Boot ROM oficial deja después de ejecutarse.
 * Si los registros (especialmente los flags) no coinciden, el juego puede
 * entrar en un bucle de error en lugar de mostrar el logo.
 * 
 * Fuente: Pan Docs - "Power Up Sequence", Boot ROM Post-Boot State
 * Valores para DMG (Game Boy Clásica):
 * - AF = 0x01B0 (A=0x01 indica DMG, F=0xB0: Z=1, N=0, H=1, C=1)
 * - BC = 0x0013
 * - DE = 0x00D8
 * - HL = 0x014D
 * - SP = 0xFFFE
 * - PC = 0x0100
 */

CoreRegisters::CoreRegisters() :
    a(0x01),
    b(0x00),
    c(0x13),
    d(0x00),
    e(0xD8),
    h(0x01),
    l(0x4D),
    f(0xB0),  // Flags: Z=1, N=0, H=1, C=1 (0xB0 = 10110000)
    pc(0x0100),
    sp(0xFFFE)
{
    // Inicialización Post-BIOS completada en la lista de inicialización
    // Estos valores simulan el estado exacto que la Boot ROM deja en la CPU
    // antes de transferir el control al código del cartucho en 0x0100
}

