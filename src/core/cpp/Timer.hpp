#ifndef TIMER_HPP
#define TIMER_HPP

#include <cstdint>

/**
 * Timer - Subsistema de Temporización de la Game Boy
 * 
 * El Timer es un componente de hardware independiente que se usa para
 * temporización y generación de números aleatorios. Su componente más básico
 * es el registro DIV (Divider, en 0xFF04).
 * 
 * Características del registro DIV:
 * - Es un contador que se incrementa constantemente a una frecuencia fija de 16384 Hz
 * - Dado que el reloj principal es de 4.194304 MHz, DIV se incrementa cada 256 T-Cycles
 *   (4194304 / 16384 = 256)
 * - Es de solo lectura desde la perspectiva del juego, pero escribir CUALQUIER valor
 *   en 0xFF04 tiene el efecto secundario de resetear el contador a 0
 * - El BIOS lo usa para generar retardos de tiempo precisos durante el arranque
 * 
 * Fuente: Pan Docs - Timer and Divider Register
 */
class Timer {
public:
    /**
     * Constructor: Inicializa el contador interno a 0.
     */
    Timer();

    /**
     * Destructor.
     */
    ~Timer();

    /**
     * Actualiza el Timer con los T-Cycles consumidos.
     * 
     * Este método debe ser llamado desde el bucle de emulación principal
     * después de cada instrucción de la CPU para mantener la sincronización
     * del tiempo emulado.
     * 
     * @param t_cycles Número de T-Cycles a agregar al contador interno
     */
    void step(int t_cycles);

    /**
     * Lee el valor del registro DIV (Divider).
     * 
     * DIV es los 8 bits altos del contador interno de 16 bits.
     * Se incrementa cada 256 T-Cycles (frecuencia de 16384 Hz).
     * 
     * @return Valor del registro DIV (0x00 a 0xFF)
     */
    uint8_t read_div() const;

    /**
     * Escribe en el registro DIV (resetea el contador).
     * 
     * Cualquier escritura en 0xFF04 tiene el efecto secundario de resetear
     * el contador interno a 0. El valor escrito es ignorado.
     */
    void write_div();

private:
    /**
     * Contador interno de T-Cycles (16 bits).
     * 
     * Este contador se incrementa continuamente. Los 8 bits altos
     * representan el valor del registro DIV que se lee desde 0xFF04.
     */
    int div_counter_;
};

#endif // TIMER_HPP

