#include "Registers.hpp"

/**
 * Implementación de CoreRegisters.
 * 
 * Los métodos inline están definidos en el header para máximo rendimiento.
 * Aquí solo implementamos el constructor.
 */

CoreRegisters::CoreRegisters() :
    a(0),
    b(0),
    c(0),
    d(0),
    e(0),
    h(0),
    l(0),
    f(0),
    pc(0),
    sp(0)
{
    // Todos los registros se inicializan a cero en la lista de inicialización
    // Esto es más eficiente que asignar en el cuerpo del constructor
}

