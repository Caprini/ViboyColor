#ifndef TIMER_HPP
#define TIMER_HPP

#include <cstdint>

// Forward declaration para evitar dependencia circular
class MMU;

/**
 * Timer - Subsistema de Temporización de la Game Boy
 * 
 * El Timer es un componente de hardware independiente que se usa para
 * temporización y generación de números aleatorios. Implementa los siguientes
 * registros:
 * 
 * - DIV (Divider, 0xFF04): Contador continuo a 16384 Hz
 * - TIMA (Timer Counter, 0xFF05): Contador programable que se incrementa a frecuencias
 *   configurables (4096Hz, 262144Hz, 65536Hz, o 16384Hz)
 * - TMA (Timer Modulo, 0xFF06): Valor al que se recarga TIMA cuando desborda
 * - TAC (Timer Control, 0xFF07): Control de enable y selección de frecuencia
 * 
 * Cuando TIMA desborda (pasa de 0xFF a 0x00), se recarga automáticamente con TMA
 * y se solicita una interrupción de Timer (bit 2 del registro IF).
 * 
 * Fuente: Pan Docs - Timer and Divider Register, Timer Control, Timer Counter, Timer Modulo
 */
class Timer {
public:
    /**
     * Constructor: Inicializa el contador interno y registros del Timer.
     * 
     * @param mmu Puntero a la MMU para solicitar interrupciones (puede ser nullptr)
     */
    Timer(MMU* mmu);

    /**
     * Destructor.
     */
    ~Timer();

    /**
     * Actualiza el Timer con los T-Cycles consumidos.
     * 
     * Este método debe ser llamado desde el bucle de emulación principal
     * después de cada instrucción de la CPU para mantener la sincronización
     * del tiempo emulado. Actualiza tanto DIV como TIMA según la configuración.
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

    /**
     * Lee el valor del registro TIMA (Timer Counter).
     * 
     * @return Valor actual de TIMA (0x00 a 0xFF)
     */
    uint8_t read_tima() const { return tima_; }

    /**
     * Escribe en el registro TIMA (Timer Counter).
     * 
     * @param value Nuevo valor para TIMA
     */
    void write_tima(uint8_t value) { tima_ = value; }

    /**
     * Lee el valor del registro TMA (Timer Modulo).
     * 
     * @return Valor actual de TMA (0x00 a 0xFF)
     */
    uint8_t read_tma() const { return tma_; }

    /**
     * Escribe en el registro TMA (Timer Modulo).
     * 
     * @param value Nuevo valor para TMA
     */
    void write_tma(uint8_t value) { tma_ = value; }

    /**
     * Lee el valor del registro TAC (Timer Control).
     * 
     * @return Valor actual de TAC (solo bits 0-2 son significativos)
     */
    uint8_t read_tac() const { return tac_; }

    /**
     * Escribe en el registro TAC (Timer Control).
     * 
     * @param value Nuevo valor para TAC (solo bits 0-2 son significativos)
     */
    void write_tac(uint8_t value) { tac_ = value; }

private:
    /**
     * Puntero a la MMU para solicitar interrupciones cuando TIMA desborda.
     */
    MMU* mmu_;

    /**
     * Contador interno de T-Cycles para DIV (16 bits).
     * 
     * Este contador se incrementa continuamente. Los 8 bits altos
     * representan el valor del registro DIV que se lee desde 0xFF04.
     */
    int div_counter_;

    /**
     * Contador interno de T-Cycles para TIMA.
     * 
     * Este contador acumula T-Cycles hasta alcanzar el threshold
     * correspondiente a la frecuencia configurada en TAC.
     */
    int tima_counter_;

    /**
     * Registro TIMA (Timer Counter, 0xFF05).
     * 
     * Contador de 8 bits que se incrementa a la frecuencia seleccionada
     * en TAC. Cuando desborda (0xFF -> 0x00), se recarga con TMA y se
     * solicita una interrupción de Timer.
     */
    uint8_t tima_;

    /**
     * Registro TMA (Timer Modulo, 0xFF06).
     * 
     * Valor al que se recarga TIMA cuando desborda.
     */
    uint8_t tma_;

    /**
     * Registro TAC (Timer Control, 0xFF07).
     * 
     * - Bit 2: Timer Enable (1 = ON, 0 = OFF)
     * - Bits 1-0: Input Clock Select
     *   - 00: 4096 Hz (1024 T-Cycles por incremento)
     *   - 01: 262144 Hz (16 T-Cycles por incremento)
     *   - 10: 65536 Hz (64 T-Cycles por incremento)
     *   - 11: 16384 Hz (256 T-Cycles por incremento)
     */
    uint8_t tac_;

    /**
     * Obtiene el threshold (número de T-Cycles) necesario para incrementar TIMA
     * según la frecuencia configurada en TAC.
     * 
     * @return Número de T-Cycles necesario para un incremento de TIMA
     */
    int get_tima_threshold() const;
};

#endif // TIMER_HPP

