#ifndef MMU_HPP
#define MMU_HPP

#include <cstdint>
#include <vector>

// Forward declarations para evitar dependencia circular
class PPU;
class Timer;
class Joypad;

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

    /**
     * Establece el puntero al Timer para permitir lectura/escritura del registro DIV.
     * 
     * El registro DIV (0xFF04) es actualizado dinámicamente por el Timer.
     * Para leer el valor correcto, la MMU necesita llamar a Timer::read_div()
     * cuando se lee 0xFF04. Para escribir, llama a Timer::write_div().
     * 
     * @param timer Puntero a la instancia de Timer (puede ser nullptr)
     */
    void setTimer(Timer* timer);

    /**
     * Establece el puntero al Joypad para permitir lectura/escritura del registro P1.
     * 
     * El registro P1 (0xFF00) es controlado por el Joypad. La CPU escribe en P1
     * para seleccionar qué fila de botones leer (direcciones o acciones), y lee
     * el estado de los botones de la fila seleccionada.
     * 
     * @param joypad Puntero a la instancia de Joypad (puede ser nullptr)
     */
    void setJoypad(Joypad* joypad);
    
    /**
     * Solicita una interrupción activando el bit correspondiente en el registro IF (0xFF0F).
     * 
     * Este método permite que componentes del hardware (PPU, Timer, etc.) soliciten
     * interrupciones escribiendo en el registro IF. La CPU procesará estas interrupciones
     * cuando IME esté activo y haya bits activos en IE & IF.
     * 
     * @param bit Número de bit a activar (0-4):
     *            - 0: V-Blank Interrupt
     *            - 1: LCD STAT Interrupt
     *            - 2: Timer Interrupt
     *            - 3: Serial Interrupt
     *            - 4: Joypad Interrupt
     * 
     * Fuente: Pan Docs - Interrupts, Interrupt Flag Register (IF)
     */
    void request_interrupt(uint8_t bit);

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

    /**
     * Puntero al Timer para lectura/escritura del registro DIV (0xFF04).
     * 
     * Este puntero se establece mediante setTimer() y se usa cuando se lee
     * o escribe el registro DIV para obtener/actualizar el valor del contador.
     */
    Timer* timer_;

    /**
     * Puntero al Joypad para lectura/escritura del registro P1 (0xFF00).
     * 
     * Este puntero se establece mediante setJoypad() y se usa cuando se lee
     * o escribe el registro P1 para obtener/actualizar el estado de los botones.
     */
    Joypad* joypad_;
};

#endif // MMU_HPP

