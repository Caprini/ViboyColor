#ifndef CPU_HPP
#define CPU_HPP

#include <cstdint>
#include <iostream>
#include <iomanip>  // Para std::hex, std::setw, std::setfill

// Forward declarations (evitar includes circulares)
class MMU;
class CoreRegisters;
class PPU;
class Timer;

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
     * Establece el puntero a la PPU para permitir sincronización ciclo a ciclo.
     * 
     * Este método permite conectar la PPU a la CPU, permitiendo que run_scanline()
     * actualice la PPU después de cada instrucción.
     * 
     * @param ppu Puntero a la instancia de PPU (puede ser nullptr)
     */
    void setPPU(PPU* ppu);

    /**
     * Establece el puntero al Timer para permitir actualización del registro DIV.
     * 
     * Este método permite conectar el Timer a la CPU, permitiendo que run_scanline()
     * actualice el Timer después de cada instrucción.
     * 
     * @param timer Puntero a la instancia de Timer (puede ser nullptr)
     */
    void setTimer(Timer* timer);

    /**
     * Ejecuta una scanline completa (456 T-Cycles) con sincronización ciclo a ciclo.
     * 
     * Este método encapsula el bucle de emulación de grano fino que ejecuta
     * instrucciones de la CPU y actualiza la PPU después de cada instrucción.
     * Esto permite una sincronización precisa que resuelve deadlocks de polling.
     * 
     * El método:
     * 1. Ejecuta instrucciones de la CPU hasta acumular 456 T-Cycles
     * 2. Después de cada instrucción, actualiza la PPU con los ciclos consumidos
     * 3. Esto garantiza que la PPU cambie de modo en los ciclos exactos
     * 
     * CRÍTICO: Este método debe ser llamado desde Python para cada scanline.
     * La PPU debe estar conectada previamente mediante setPPU().
     * 
     * Fuente: Pan Docs - LCD Timing, System Clock
     */
    void run_scanline();

    /**
     * Obtiene el contador de ciclos acumulados.
     * 
     * @return Total de M-Cycles ejecutados desde la creación
     */
    uint32_t get_cycles() const;

    /**
     * Obtiene el estado de IME (Interrupt Master Enable).
     * 
     * @return true si las interrupciones están habilitadas, false en caso contrario
     */
    bool get_ime() const;

    /**
     * Establece el estado de IME (Interrupt Master Enable).
     * 
     * Este método permite modificar IME desde el exterior (útil para tests).
     * 
     * @param value true para habilitar interrupciones, false para deshabilitarlas
     */
    void set_ime(bool value);

    /**
     * Obtiene el estado de HALT.
     * 
     * @return true si la CPU está en estado HALT, false en caso contrario
     */
    bool get_halted() const;

private:
    /**
     * Lee un byte de memoria en la dirección PC e incrementa PC.
     * 
     * Helper interno para el ciclo Fetch.
     * 
     * @return Byte leído de memoria
     */
    uint8_t fetch_byte();

    /**
     * Lee una palabra (16 bits) de memoria en la dirección PC en formato Little-Endian.
     * 
     * Lee primero el byte bajo (LSB) y luego el byte alto (MSB), y los combina.
     * PC se incrementa 2 veces.
     * 
     * Helper interno para instrucciones que requieren direcciones de 16 bits
     * (ej: JP nn, CALL nn).
     * 
     * @return Palabra de 16 bits leída de memoria (Little-Endian)
     */
    uint16_t fetch_word();

    // ========== Helpers de Stack (Pila) ==========
    // La pila crece hacia abajo (direcciones decrecientes)
    // PUSH: decrementa SP, luego escribe
    // POP: lee, luego incrementa SP
    // Little-Endian: PUSH escribe high byte en SP-1, low byte en SP-2
    
    /**
     * Empuja un byte en la pila.
     * 
     * Decrementa SP primero, luego escribe el byte en memoria.
     * La pila crece hacia abajo (SP decrece).
     * 
     * @param val Byte a empujar en la pila
     */
    inline void push_byte(uint8_t val);

    /**
     * Saca un byte de la pila.
     * 
     * Lee el byte de memoria en la dirección SP, luego incrementa SP.
     * 
     * @return Byte leído de la pila
     */
    inline uint8_t pop_byte();

    /**
     * Empuja una palabra (16 bits) en la pila.
     * 
     * Empuja primero el byte alto (MSB) y luego el byte bajo (LSB).
     * Esto es consistente con el formato Little-Endian de la Game Boy.
     * 
     * @param val Palabra de 16 bits a empujar en la pila
     */
    inline void push_word(uint16_t val);

    /**
     * Saca una palabra (16 bits) de la pila.
     * 
     * Lee primero el byte bajo (LSB) y luego el byte alto (MSB),
     * y los combina en formato Little-Endian.
     * 
     * @return Palabra de 16 bits leída de la pila
     */
    inline uint16_t pop_word();

    /**
     * Maneja las interrupciones pendientes según la prioridad del hardware.
     * 
     * Este método se ejecuta ANTES de cada instrucción. Verifica si hay
     * interrupciones pendientes y las procesa si IME está activado.
     * 
     * Flujo de interrupción:
     * 1. Lee IE (0xFFFF) e IF (0xFF0F)
     * 2. Si CPU está en HALT y hay interrupción pendiente, despierta (halted = false)
     * 3. Si IME está activo y hay bits activos en IE & IF:
     *    - Desactiva IME
     *    - Encuentra el bit de menor peso (prioridad)
     *    - Limpia el bit en IF
     *    - Guarda PC en la pila
     *    - Salta al vector de interrupción
     *    - Retorna 5 M-Cycles
     * 
     * Vectores de Interrupción (prioridad de mayor a menor):
     * - Bit 0: V-Blank -> 0x0040
     * - Bit 1: LCD STAT -> 0x0048
     * - Bit 2: Timer -> 0x0050
     * - Bit 3: Serial -> 0x0058
     * - Bit 4: Joypad -> 0x0060
     * 
     * @return Número de M-Cycles consumidos (5 si se procesó una interrupción, 0 si no)
     * 
     * Fuente: Pan Docs - Interrupts, HALT behavior
     */
    uint8_t handle_interrupts();

    /**
     * Maneja el prefijo CB (Extended Instructions).
     * 
     * Cuando la CPU lee el opcode 0xCB, el siguiente byte se interpreta
     * con una tabla diferente de instrucciones. El prefijo CB permite
     * acceder a 256 instrucciones adicionales:
     * 
     * - 0x00-0x3F: Rotaciones y shifts (RLC, RRC, RL, RR, SLA, SRA, SRL, SWAP)
     * - 0x40-0x7F: BIT b, r (Test bit)
     * - 0x80-0xBF: RES b, r (Reset bit)
     * - 0xC0-0xFF: SET b, r (Set bit)
     * 
     * Estructura del opcode CB:
     * - Bits 0-2: Registro (0=B, 1=C, 2=D, 3=E, 4=H, 5=L, 6=(HL), 7=A)
     * - Bits 3-5: Índice de Bit (0-7) para BIT/SET/RES
     * - Bits 6-7: Operación (00=Rotaciones/Shifts, 01=BIT, 10=RES, 11=SET)
     * 
     * Timing:
     * - Registro: 2 M-Cycles (8 T-Cycles)
     * - (HL): 4 M-Cycles (16 T-Cycles) - requiere leer memoria, modificar, escribir
     * 
     * @return Número de M-Cycles consumidos
     * 
     * Fuente: Pan Docs - CPU Instruction Set (CB Prefix)
     */
    int handle_cb();

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

    /**
     * Incrementa un valor de 8 bits y actualiza flags.
     * 
     * IMPORTANTE: El flag C NO se modifica (preservado).
     * Esta es una peculiaridad del hardware de la Game Boy.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre, es incremento)
     * - H: 1 si hay half-carry (bit 3 -> 4), 0 en caso contrario
     * - C: NO afectado (mantiene valor anterior)
     * 
     * @param value Valor a incrementar
     * @return Resultado incrementado
     * 
     * Fuente: Pan Docs - INC r: "C flag is not affected"
     */
    uint8_t alu_inc(uint8_t value);

    /**
     * Decrementa un valor de 8 bits y actualiza flags.
     * 
     * IMPORTANTE: El flag C NO se modifica (preservado).
     * Esta es una peculiaridad del hardware de la Game Boy.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 1 (siempre, es decremento)
     * - H: 1 si hay half-borrow (bit 4 -> 3), 0 en caso contrario
     * - C: NO afectado (mantiene valor anterior)
     * 
     * @param value Valor a decrementar
     * @return Resultado decrementado
     * 
     * Fuente: Pan Docs - DEC r: "C flag is not affected"
     */
    uint8_t alu_dec(uint8_t value);

    /**
     * Suma un valor al registro A con carry y actualiza flags (ADC).
     * 
     * ADC: A = A + value + C
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre, es suma)
     * - H: 1 si hay half-carry (bit 3 -> 4) incluyendo carry, 0 en caso contrario
     * - C: 1 si hay carry (overflow 8 bits), 0 en caso contrario
     * 
     * @param value Valor a sumar a A (con carry)
     * 
     * Fuente: Pan Docs - ADC A, r
     */
    inline void alu_adc(uint8_t value);

    /**
     * Resta un valor del registro A con carry y actualiza flags (SBC).
     * 
     * SBC: A = A - value - C
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 1 (siempre, es resta)
     * - H: 1 si hay half-borrow (bit 4 -> 3) incluyendo carry, 0 en caso contrario
     * - C: 1 si hay borrow (underflow), 0 en caso contrario
     * 
     * @param value Valor a restar de A (con carry)
     * 
     * Fuente: Pan Docs - SBC A, r
     */
    inline void alu_sbc(uint8_t value);

    /**
     * Operación OR lógica entre A y un valor.
     * 
     * Flags actualizados:
     * - Z: 1 si resultado == 0, 0 en caso contrario
     * - N: 0 (siempre)
     * - H: 0 (siempre)
     * - C: 0 (siempre)
     * 
     * @param value Valor para OR con A
     * 
     * Fuente: Pan Docs - OR A, r
     */
    inline void alu_or(uint8_t value);

    /**
     * Compara A con un valor sin modificar A (CP).
     * 
     * CP realiza A - value pero NO guarda el resultado.
     * Solo actualiza flags. Es equivalente a SUB pero sin modificar A.
     * 
     * Flags actualizados:
     * - Z: 1 si A == value, 0 en caso contrario
     * - N: 1 (siempre, es resta)
     * - H: 1 si hay half-borrow (bit 4 -> 3), 0 en caso contrario
     * - C: 1 si A < value, 0 en caso contrario
     * 
     * @param value Valor a comparar con A
     * 
     * Fuente: Pan Docs - CP A, r
     */
    inline void alu_cp(uint8_t value);

    // ========== Helpers de Load (Transferencia de Datos) ==========
    
    /**
     * Obtiene un puntero a un registro de 8 bits según el código de registro.
     * 
     * Códigos de registro (bits 0-2 del opcode):
     * - 0: B
     * - 1: C
     * - 2: D
     * - 3: E
     * - 4: H
     * - 5: L
     * - 6: (HL) - retorna nullptr (requiere acceso a memoria)
     * - 7: A
     * 
     * @param reg_code Código de registro (0-7)
     * @return Puntero al registro, o nullptr si es (HL)
     */
    inline uint8_t* get_register_ptr(uint8_t reg_code);
    
    /**
     * Lee el valor de un registro o memoria según el código.
     * 
     * Si reg_code == 6, lee de memoria en dirección HL.
     * En caso contrario, lee del registro correspondiente.
     * 
     * @param reg_code Código de registro (0-7)
     * @return Valor leído (8 bits)
     */
    inline uint8_t read_register_or_mem(uint8_t reg_code);
    
    /**
     * Escribe un valor en un registro o memoria según el código.
     * 
     * Si reg_code == 6, escribe en memoria en dirección HL.
     * En caso contrario, escribe en el registro correspondiente.
     * 
     * @param reg_code Código de registro (0-7)
     * @param value Valor a escribir (8 bits)
     */
    inline void write_register_or_mem(uint8_t reg_code, uint8_t value);
    
    /**
     * Copia un valor de un registro/memoria a otro (LD r, r').
     * 
     * Esta función maneja el bloque completo 0x40-0x7F de instrucciones LD.
     * 
     * @param dest_code Código de registro destino (bits 3-5 del opcode)
     * @param src_code Código de registro origen (bits 0-2 del opcode)
     */
    inline void ld_r_r(uint8_t dest_code, uint8_t src_code);

    // ========== Helpers de Aritmética 16-bit ==========
    
    /**
     * Incrementa un par de registros de 16 bits.
     * 
     * IMPORTANTE: INC rr NO afecta flags en la Game Boy.
     * Solo incrementa el valor del par.
     * 
     * @param reg_pair Código del par (0=BC, 1=DE, 2=HL, 3=SP)
     */
    inline void inc_16bit(uint8_t reg_pair);
    
    /**
     * Decrementa un par de registros de 16 bits.
     * 
     * IMPORTANTE: DEC rr NO afecta flags en la Game Boy.
     * Solo decrementa el valor del par.
     * 
     * @param reg_pair Código del par (0=BC, 1=DE, 2=HL, 3=SP)
     */
    inline void dec_16bit(uint8_t reg_pair);
    
    /**
     * Suma un valor de 16 bits a HL y actualiza flags.
     * 
     * Flags actualizados:
     * - Z: NO afectado (mantiene valor anterior)
     * - N: 0 (siempre, es suma)
     * - H: 1 si hay half-carry en bit 11 (bit 3 del byte alto)
     * - C: 1 si hay carry (overflow 16 bits)
     * 
     * @param value Valor de 16 bits a sumar a HL
     */
    inline void add_hl(uint16_t value);

    // Punteros a componentes (inyección de dependencias)
    MMU* mmu_;              // Puntero a MMU (no poseído)
    CoreRegisters* regs_;   // Puntero a Registros (no poseído)
    PPU* ppu_;              // Puntero a PPU (no poseído, opcional)
    Timer* timer_;          // Puntero a Timer (no poseído, opcional)

    // Contador de ciclos acumulados
    uint32_t cycles_;

    // ========== Estado de Interrupciones ==========
    bool ime_;              // Interrupt Master Enable (habilitación global de interrupciones)
    bool halted_;           // Estado HALT (CPU dormida)
    bool ime_scheduled_;    // Flag para retraso de EI (se activa después de la siguiente instrucción)

    // ========== Estado de Diagnóstico (Step 0287) ==========
    // Estos miembros reemplazan las variables static para aislar el estado entre tests
    bool in_vblank_handler_;      // Flag que indica si estamos ejecutando el handler de V-Blank
    int vblank_handler_steps_;    // Contador de pasos dentro del handler
    bool post_delay_trace_active_; // Flag para activar trail post-retardo
    int post_delay_count_;        // Contador de instrucciones rastreadas post-retardo
    
    // ========== Estado de Diagnóstico (Step 0293) ==========
    // Monitores de rastreo post-limpieza de VRAM
    bool in_post_cleanup_trace_;  // Flag para activar rastreo post-limpieza
    int post_cleanup_trace_count_; // Contador de instrucciones rastreadas
    bool reg_trace_active_;       // Flag para activar rastreo de registros
    uint16_t last_af_, last_bc_, last_de_, last_hl_; // Valores anteriores de registros
    int reg_trace_count_;         // Contador de muestras de registros
    bool jump_trace_active_;      // Flag para activar rastreo de saltos
    int jump_trace_count_;        // Contador de saltos rastreados
    bool hw_state_trace_active_;  // Flag para activar rastreo de estado de hardware
    int hw_state_samples_;        // Contador de muestras de hardware
    int hw_state_sample_counter_; // Contador interno para muestreo
    
    // ========== Estado de Diagnóstico (Step 0382) ==========
    // PC sampler y detección de bucles
    int instruction_counter_step382_;  // Contador de instrucciones ejecutadas
    uint16_t last_pc_sample_;          // Último PC muestreado
    int pc_repeat_count_;              // Contador de repeticiones del mismo PC
    
    // --- Step 0409: Wait-Loop Detector Genérico ---
    uint16_t waitloop_pc_;             // PC del loop detectado
    int waitloop_iterations_;          // Iteraciones del mismo PC
    static constexpr int WAITLOOP_THRESHOLD = 5000;  // Umbral de detección
    
    // ========== Estado de Diagnóstico (Step 0383) ==========
    // Trazado de bucle de espera (Bank 28, PC 0x614D-0x6153)
    bool wait_loop_trace_active_;      // Flag para activar trazado del wait-loop
    int wait_loop_trace_count_;        // Contador de iteraciones trazadas (límite 200)
    bool wait_loop_detected_;          // Flag para indicar que ya se detectó el loop una vez
    
    // ========== Estado de Diagnóstico (Step 0387) ==========
    // Ring buffer para capturar últimas N instrucciones antes de crash
    struct InstrSnapshot {
        uint16_t pc;
        uint16_t sp;
        uint16_t af, bc, de, hl;
        uint8_t bank;
        uint8_t op;
        uint8_t op1;
        uint8_t op2;
        uint8_t ime;
        uint8_t ie;
        uint8_t if_flag;
    };
    static constexpr int RING_SIZE = 64;
    InstrSnapshot ring_buffer_[RING_SIZE];
    int ring_idx_;
    bool crash_dumped_;
    
    // ========== Estado de Diagnóstico (Step 0400) ==========
    // Contadores de interrupciones por tipo
    int irq_vblank_requests_;
    int irq_vblank_services_;
    int irq_stat_requests_;
    int irq_stat_services_;
    int irq_timer_requests_;
    int irq_timer_services_;
    int irq_serial_requests_;
    int irq_serial_services_;
    int irq_joypad_requests_;
    int irq_joypad_services_;
    uint64_t first_vblank_request_frame_;
    uint64_t first_vblank_service_frame_;
    bool irq_summary_logged_;
    
public:
    /**
     * Step 0400: Genera resumen de interrupciones para análisis comparativo.
     * Registra requests/services por tipo de interrupción.
     */
    void log_irq_summary();
};

#endif // CPU_HPP

