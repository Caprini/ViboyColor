#ifndef JOYPAD_HPP
#define JOYPAD_HPP

#include <cstdint>

// Forward declaration de MMU para solicitar interrupciones
class MMU;

/**
 * Joypad - Subsistema de Entrada del Usuario
 * 
 * El Joypad de la Game Boy es una matriz de 2x4 botones que la CPU debe escanear
 * para leer el estado de los botones. El registro P1 (0xFF00) controla este proceso.
 * 
 * Características del registro P1:
 * - Bits 5 y 4 (Escritura): La CPU escribe aquí para seleccionar qué "fila" de la matriz quiere leer.
 *   - Bit 5 = 0: Selecciona los botones de Acción (A, B, Select, Start).
 *   - Bit 4 = 0: Selecciona los botones de Dirección (Derecha, Izquierda, Arriba, Abajo).
 * - Bits 3-0 (Lectura): La CPU lee estos bits para ver el estado de los botones de la fila seleccionada.
 *   IMPORTANTE: Un bit a 0 significa que el botón está PRESIONADO. Un bit a 1 significa que está SUELTO.
 * 
 * Mapeo de botones:
 * - Direcciones: Bit 0 = Derecha, Bit 1 = Izquierda, Bit 2 = Arriba, Bit 3 = Abajo
 * - Acciones:     Bit 0 = A,      Bit 1 = B,      Bit 2 = Select, Bit 3 = Start
 * 
 * El registro P1 tiene un comportamiento especial:
 * - Los bits 6-7 siempre leen como 1 (no se usan)
 * - Los bits 4-5 son escribibles y controlan la selección de fila
 * - Los bits 0-3 son de lectura y reflejan el estado de los botones de la fila seleccionada
 * 
 * IMPORTANTE - Interrupción de Joypad (Step 0379):
 * - Cuando un botón cambia de "suelto" (1) a "presionado" (0), se solicita la interrupción de Joypad.
 * - La interrupción de Joypad es el bit 4 del registro IF (0xFF0F), vector 0x0060.
 * - Esta interrupción se solicita SOLO si hay un "falling edge" en P14-P17 (bits 0-3 del registro P1).
 * 
 * Fuente: Pan Docs - Joypad Input, P1 Register
 */
class Joypad {
public:
    /**
     * Constructor: Inicializa todos los botones como "suelto" (bits a 1).
     */
    Joypad();

    /**
     * Destructor.
     */
    ~Joypad();

    /**
     * Lee el valor del registro P1 (0xFF00).
     * 
     * El valor devuelto depende de qué fila esté seleccionada (bits 4-5 de p1_register_):
     * - Si bit 4 = 0: Devuelve el estado de los botones de dirección
     * - Si bit 5 = 0: Devuelve el estado de los botones de acción
     * - Si ambos bits = 1: Devuelve 0xCF (ninguna fila seleccionada, todos los botones leen como sueltos)
     * 
     * @return Valor del registro P1 (0x00 a 0xFF)
     */
    uint8_t read_p1() const;

    /**
     * Escribe en el registro P1 (selecciona la fila de botones a leer).
     * 
     * Solo los bits 4 y 5 son escribibles. El resto se ignoran.
     * 
     * @param value Valor a escribir (solo bits 4-5 son relevantes)
     */
    void write_p1(uint8_t value);

    /**
     * Simula presionar un botón.
     * 
     * @param button_index Índice del botón (0-7):
     *                     - 0-3: Botones de dirección (0=Derecha, 1=Izquierda, 2=Arriba, 3=Abajo)
     *                     - 4-7: Botones de acción (4=A, 5=B, 6=Select, 7=Start)
     */
    void press_button(int button_index);

    /**
     * Simula soltar un botón.
     * 
     * @param button_index Índice del botón (0-7)
     */
    void release_button(int button_index);

    /**
     * Establece el puntero a la MMU para poder solicitar interrupciones.
     * 
     * Step 0379: El Joypad necesita acceso a la MMU para solicitar la interrupción de Joypad
     * cuando se presiona un botón (falling edge en P14-P17).
     * 
     * @param mmu Puntero a la instancia de MMU (puede ser nullptr)
     */
    void setMMU(MMU* mmu);
    
    /**
     * Step 0484: Obtiene el valor del registro P1 interno (latch de selección).
     * 
     * @return Valor del registro P1 (bits 4-5 contienen la selección de fila)
     */
    uint8_t get_p1_register() const;

private:
    /**
     * Estado de los botones de dirección (bits 0-3).
     * - Bit 0: Derecha (0=presionado, 1=suelto)
     * - Bit 1: Izquierda (0=presionado, 1=suelto)
     * - Bit 2: Arriba (0=presionado, 1=suelto)
     * - Bit 3: Abajo (0=presionado, 1=suelto)
     * 
     * Inicializado a 0x0F (todos sueltos).
     */
    uint8_t direction_keys_;

    /**
     * Estado de los botones de acción (bits 0-3).
     * - Bit 0: A (0=presionado, 1=suelto)
     * - Bit 1: B (0=presionado, 1=suelto)
     * - Bit 2: Select (0=presionado, 1=suelto)
     * - Bit 3: Start (0=presionado, 1=suelto)
     * 
     * Inicializado a 0x0F (todos sueltos).
     */
    uint8_t action_keys_;

    /**
     * Registro P1 interno (almacena los bits 4-5 de selección de fila).
     * 
     * Inicializado a 0xCF (ninguna fila seleccionada, bits 6-7 siempre a 1).
     */
    uint8_t p1_register_;

    /**
     * Puntero a la MMU para solicitar interrupciones.
     * 
     * Step 0379: Necesario para solicitar la interrupción de Joypad (bit 4, vector 0x0060)
     * cuando se detecta un "falling edge" (botón presionado).
     */
    MMU* mmu_;
};

#endif // JOYPAD_HPP

