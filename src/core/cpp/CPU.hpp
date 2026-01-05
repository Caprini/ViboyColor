#ifndef CPU_HPP
#define CPU_HPP

#include <cstdint>
#include <iostream>
#include <iomanip>  // Para std::hex, std::setw, std::setfill
#include <map>  // Step 0482: Para branch_decisions_
#include <vector>  // Step 0483: Para get_top_exec_pcs y get_top_branch_blockers

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
    
    /**
     * Step 0469: Obtiene el contador de VBlank IRQ servidos.
     * 
     * Este contador se incrementa cada vez que la CPU sirve una interrupción VBlank
     * (cuando IME está activo y se procesa el vector 0x0040). Útil para diagnóstico
     * de por qué los juegos no progresan (si el juego está en HALT esperando VBlank).
     * 
     * @return Número de veces que se ha servido VBlank interrupt
     */
    uint32_t get_vblank_irq_serviced_count() const;
    
    /**
     * Step 0472: Obtiene el contador de ejecuciones de STOP.
     * 
     * @return Número de veces que se ha ejecutado STOP
     */
    uint32_t get_stop_executed_count() const;
    
    /**
     * Step 0472: Obtiene el PC de la última ejecución de STOP.
     * 
     * @return PC de la última ejecución de STOP
     */
    uint16_t get_last_stop_pc() const;
    
    /**
     * Step 0475: Obtiene el vector de la última IRQ servida.
     * 
     * @return Vector de la última IRQ servida (0x40, 0x48, 0x50, 0x58, 0x60)
     */
    uint16_t get_last_irq_serviced_vector() const;
    
    /**
     * Step 0475: Obtiene el timestamp de la última IRQ servida.
     * 
     * @return Timestamp de la última IRQ servida (incrementa cada vez que se sirve una IRQ)
     */
    uint32_t get_last_irq_serviced_timestamp() const;
    
    /**
     * Step 0475: Obtiene el valor de IF antes de servir la última IRQ.
     * 
     * @return Valor de IF antes de servir la última IRQ
     */
    uint8_t get_last_if_before_service() const;
    
    /**
     * Step 0475: Obtiene el valor de IF después de servir la última IRQ.
     * 
     * @return Valor de IF después de servir la última IRQ
     */
    uint8_t get_last_if_after_service() const;
    
    /**
     * Step 0475: Obtiene la máscara del bit limpiado en la última IRQ servida.
     * 
     * @return Máscara del bit limpiado (lowest_pending)
     */
    uint8_t get_last_if_clear_mask() const;

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
    
    // --- Step 0472: Contadores de STOP ---
    uint32_t stop_executed_count_;       // Contador de ejecuciones de STOP
    uint16_t last_stop_pc_;              // PC de la última ejecución de STOP
    
    // --- Step 0475: Tracking de IF Clear on Service ---
    uint16_t last_irq_serviced_vector_;      // Vector de la última IRQ servida (0x40, 0x48, etc.)
    uint32_t last_irq_serviced_timestamp_;   // Timestamp de la última IRQ servida
    uint8_t last_if_before_service_;         // IF antes de servir la IRQ
    uint8_t last_if_after_service_;          // IF después de servir la IRQ
    uint8_t last_if_clear_mask_;             // Máscara del bit limpiado (lowest_pending)
    
    // --- Step 0477: Tracking de Transiciones IME + EI Delayed ---
    uint32_t ime_set_events_count_;         // Contador de veces que IME se activa (después de EI delayed)
    uint16_t last_ime_set_pc_;              // PC donde IME se activó por última vez
    uint32_t last_ime_set_timestamp_;       // Timestamp de la última activación de IME
    uint16_t last_ei_pc_;                   // PC de la última ejecución de EI
    uint16_t last_di_pc_;                   // PC de la última ejecución de DI
    
    // --- Step 0482: Contadores de EI/DI (convertidos de static a miembros de instancia) ---
    uint32_t ei_count_;                     // Contador de ejecuciones de EI
    uint32_t di_count_;                     // Contador de ejecuciones de DI
    
    // --- Step 0482: Branch Decision Counters (gated por VIBOY_DEBUG_BRANCH=1) ---
    struct BranchDecision {
        uint16_t pc;
        uint32_t taken_count;
        uint32_t not_taken_count;
        uint16_t last_target;
        bool last_taken;
        uint8_t last_flags;  // Flags al momento del salto
        
        BranchDecision() : pc(0), taken_count(0), not_taken_count(0), last_target(0), last_taken(false), last_flags(0) {}
    };
    std::map<uint16_t, BranchDecision> branch_decisions_;  // PC -> BranchDecision
    uint16_t last_cond_jump_pc_;  // PC del último salto condicional ejecutado
    uint16_t last_target_;  // Target del último salto condicional
    bool last_taken_;  // Si el último salto fue tomado
    uint8_t last_flags_;  // Flags al momento del último salto
    
    // --- Step 0482: Last Compare/BIT Tracking (gated por VIBOY_DEBUG_BRANCH=1) ---
    uint16_t last_cmp_pc_;  // PC del último CP ejecutado
    uint8_t last_cmp_a_;  // Valor de A antes del CP
    uint8_t last_cmp_imm_;  // Valor inmediato usado en CP
    uint8_t last_cmp_result_flags_;  // Flags después del CP
    uint16_t last_bit_pc_;  // PC del último BIT ejecutado
    uint8_t last_bit_n_;  // Número de bit testeado en BIT
    uint8_t last_bit_value_;  // Valor del bit testeado (0 o 1)
    
    // --- Step 0483: Exec Coverage (gated por VIBOY_DEBUG_BRANCH=1) ---
    std::map<uint16_t, uint32_t> exec_coverage_;  // PC -> ejecution count
    uint16_t coverage_window_start_;  // Inicio de ventana de coverage
    uint16_t coverage_window_end_;  // Fin de ventana de coverage
    
    // --- Step 0483: Last Load A Tracking (gated por VIBOY_DEBUG_BRANCH=1) ---
    uint16_t last_load_a_pc_;  // PC del último LDH A,(a8) o LD A,(a16) ejecutado
    uint16_t last_load_a_addr_;  // Dirección leída
    uint8_t last_load_a_value_;  // Valor leído
    
    // --- Step 0484: LY Distribution Histogram (gated por VIBOY_DEBUG_BRANCH=1) ---
    std::map<uint8_t, uint32_t> ly_read_distribution_;  // valor LY → count
    
    // --- Step 0484: Branch 0x1290 Specific Tracking (gated por VIBOY_DEBUG_BRANCH=1) ---
    struct Branch0x1290Stats {
        uint32_t taken_count;
        uint32_t not_taken_count;
        uint8_t last_flags;  // Z, N, H, C
        bool last_taken;
        
        Branch0x1290Stats() : taken_count(0), not_taken_count(0), last_flags(0x00), last_taken(false) {}
    };
    Branch0x1290Stats branch_0x1290_stats_;
    
    // ========== Estado de Triage (Step 0434) ==========
    // Instrumentación para entender por qué VRAM está vacía
    bool triage_active_;               // Flag para activar triage (limitado por frames)
    int triage_frame_limit_;           // Número máximo de frames para triage
    uint16_t triage_last_pc_;          // Último PC sampled
    int triage_pc_sample_count_;       // Contador de samples de PC
    static constexpr int TRIAGE_PC_SAMPLE_INTERVAL = 1000;  // Sample cada N instrucciones
    
    // ========== Estado de Pokemon Loop Trace (Step 0436 - Fase B) ==========
    // Trace microscópico del loop stuck (PC=0x36E2-0x36E7)
    struct PokemonLoopMicroTrace {
        bool active;                     // ¿Tracing activo?
        static constexpr int MAX_SAMPLES = 128;
        struct InstrTrace {
            uint16_t pc;
            uint8_t opcode;
            uint8_t a, f;                // A y flags
            uint16_t hl;
            uint16_t sp;
            uint8_t ime;
            uint8_t ie;
            uint8_t if_flag;
        };
        InstrTrace samples[MAX_SAMPLES];
        int sample_count;                // Número de samples capturados
        
        PokemonLoopMicroTrace() : active(false), sample_count(0) {
            for (int i = 0; i < MAX_SAMPLES; i++) {
                samples[i] = {0, 0, 0, 0, 0, 0, 0, 0, 0};
            }
        }
    } pokemon_micro_trace_;
    
public:
    /**
     * Step 0400: Genera resumen de interrupciones para análisis comparativo.
     * Registra requests/services por tipo de interrupción.
     */
    void log_irq_summary();
    
    /**
     * Step 0434: Activa/desactiva triage mode.
     * @param active true para activar triage, false para desactivar
     * @param frame_limit número máximo de frames para capturar (default 120)
     */
    void set_triage_mode(bool active, int frame_limit = 120);
    
    /**
     * Step 0434: Genera resumen de triage (debe llamarse después de ejecutar).
     */
    void log_triage_summary();
    
    /**
     * Step 0436: Activa/desactiva Pokemon micro trace (Fase B del Step 0436).
     * Captura 128 iteraciones del loop con PC/opcode/regs/flags.
     * @param active true para activar, false para desactivar
     */
    void set_pokemon_micro_trace(bool active);
    
    /**
     * Step 0436: Genera resumen de Pokemon micro trace (Fase B).
     * Muestra 10 líneas representativas del trace + conclusión.
     */
    void log_pokemon_micro_trace_summary();
    
    /**
     * Step 0470: Obtiene el contador de ejecuciones de EI.
     * 
     * @return Número de veces que se ha ejecutado EI
     */
    uint32_t get_ei_count() const;
    
    /**
     * Step 0470: Obtiene el contador de ejecuciones de DI.
     * 
     * @return Número de veces que se ha ejecutado DI
     */
    uint32_t get_di_count() const;
    
    /**
     * Step 0477: Obtiene el contador de eventos de activación de IME.
     * 
     * IME se activa después de ejecutar EI (delayed enable). Este contador
     * cuenta cuántas veces IME se ha activado realmente.
     * 
     * @return Número de veces que IME se ha activado
     */
    uint32_t get_ime_set_events_count() const;
    
    /**
     * Step 0477: Obtiene el PC donde IME se activó por última vez.
     * 
     * @return PC de la última activación de IME
     */
    uint16_t get_last_ime_set_pc() const;
    
    /**
     * Step 0477: Obtiene el timestamp de la última activación de IME.
     * 
     * @return Timestamp de la última activación de IME
     */
    uint32_t get_last_ime_set_timestamp() const;
    
    /**
     * Step 0477: Obtiene el PC de la última ejecución de EI.
     * 
     * @return PC de la última ejecución de EI
     */
    uint16_t get_last_ei_pc() const;
    
    /**
     * Step 0477: Obtiene el PC de la última ejecución de DI.
     * 
     * @return PC de la última ejecución de DI
     */
    uint16_t get_last_di_pc() const;
    
    /**
     * Step 0477: Obtiene el estado de EI pending (delayed enable).
     * 
     * @return true si EI está pendiente (IME se activará después de la siguiente instrucción)
     */
    bool get_ei_pending() const;
    
    /**
     * Step 0482: Obtiene el contador de veces que un salto condicional en PC fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @param pc Dirección del salto condicional
     * @return Número de veces que el salto fue tomado (0 si no existe)
     */
    uint32_t get_branch_taken_count(uint16_t pc) const;
    
    /**
     * Step 0482: Obtiene el contador de veces que un salto condicional en PC no fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @param pc Dirección del salto condicional
     * @return Número de veces que el salto no fue tomado (0 si no existe)
     */
    uint32_t get_branch_not_taken_count(uint16_t pc) const;
    
    /**
     * Step 0482: Obtiene el PC del último salto condicional ejecutado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return PC del último salto condicional (0xFFFF si ninguno)
     */
    uint16_t get_last_cond_jump_pc() const;
    
    /**
     * Step 0482: Obtiene el target del último salto condicional.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Target del último salto condicional
     */
    uint16_t get_last_target() const;
    
    /**
     * Step 0482: Obtiene si el último salto condicional fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return true si el último salto fue tomado, false si no
     */
    bool get_last_taken() const;
    
    /**
     * Step 0482: Obtiene los flags al momento del último salto condicional.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Flags (registro F) al momento del último salto
     */
    uint8_t get_last_flags() const;
    
    /**
     * Step 0482: Obtiene el PC del último CP ejecutado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return PC del último CP (0xFFFF si ninguno)
     */
    uint16_t get_last_cmp_pc() const;
    
    /**
     * Step 0482: Obtiene el valor de A antes del último CP.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Valor de A antes del CP
     */
    uint8_t get_last_cmp_a() const;
    
    /**
     * Step 0482: Obtiene el valor inmediato usado en el último CP.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Valor inmediato usado en CP
     */
    uint8_t get_last_cmp_imm() const;
    
    /**
     * Step 0482: Obtiene los flags después del último CP.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Flags (registro F) después del CP
     */
    uint8_t get_last_cmp_result_flags() const;
    
    /**
     * Step 0482: Obtiene el PC del último BIT ejecutado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return PC del último BIT (0xFFFF si ninguno)
     */
    uint16_t get_last_bit_pc() const;
    
    /**
     * Step 0482: Obtiene el número de bit testeado en el último BIT.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Número de bit (0-7)
     */
    uint8_t get_last_bit_n() const;
    
    /**
     * Step 0482: Obtiene el valor del bit testeado en el último BIT (0 o 1).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Valor del bit (0 o 1)
     */
    uint8_t get_last_bit_value() const;
    
    /**
     * Step 0483: Obtiene el contador de ejecuciones de un PC específico.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1 y PC está en la ventana de coverage
     * 
     * @param pc Dirección del PC
     * @return Número de veces que se ejecutó (0 si no está en coverage)
     */
    uint32_t get_exec_count(uint16_t pc) const;
    
    /**
     * Step 0483: Obtiene los top N PCs más ejecutados.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @param n Número de PCs a retornar
     * @return Vector de pares (PC, count) ordenados por count descendente
     */
    std::vector<std::pair<uint16_t, uint32_t>> get_top_exec_pcs(uint32_t n) const;
    
    /**
     * Step 0483: Establece la ventana de coverage para exec tracking.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @param start PC inicial de la ventana
     * @param end PC final de la ventana
     */
    void set_coverage_window(uint16_t start, uint16_t end);
    
    /**
     * Step 0483: Obtiene los top N branch blockers (branches con más decisiones).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @param n Número de branches a retornar
     * @return Vector de pares (PC, BranchDecision) ordenados por total decisiones descendente
     */
    std::vector<std::pair<uint16_t, BranchDecision>> get_top_branch_blockers(uint32_t n) const;
    
    /**
     * Step 0483: Obtiene el PC del último LDH A,(a8) o LD A,(a16) ejecutado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return PC de la última carga (0xFFFF si ninguna)
     */
    uint16_t get_last_load_a_pc() const;
    
    /**
     * Step 0483: Obtiene la dirección leída en el último LDH A,(a8) o LD A,(a16).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Dirección leída (0xFFFF si ninguna)
     */
    uint16_t get_last_load_a_addr() const;
    
    /**
     * Step 0483: Obtiene el valor leído en el último LDH A,(a8) o LD A,(a16).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Valor leído (0x00 si ninguna)
     */
    uint8_t get_last_load_a_value() const;
    
    /**
     * Step 0484: Obtiene el top 5 de valores LY leídos (histograma).
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Vector de pares (valor LY, count) ordenados por count descendente (top 5)
     */
    std::vector<std::pair<uint8_t, uint32_t>> get_ly_distribution_top5() const;
    
    /**
     * Step 0484: Obtiene el contador de veces que el branch en 0x1290 fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Número de veces que el branch fue tomado
     */
    uint32_t get_branch_0x1290_taken_count() const;
    
    /**
     * Step 0484: Obtiene el contador de veces que el branch en 0x1290 no fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Número de veces que el branch no fue tomado
     */
    uint32_t get_branch_0x1290_not_taken_count() const;
    
    /**
     * Step 0484: Obtiene los flags del último branch en 0x1290.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return Flags (registro F) al momento del último branch
     */
    uint8_t get_branch_0x1290_last_flags() const;
    
    /**
     * Step 0484: Obtiene si el último branch en 0x1290 fue tomado.
     * 
     * Gate: Solo funciona si VIBOY_DEBUG_BRANCH=1
     * 
     * @return true si el último branch fue tomado, false si no
     */
    bool get_branch_0x1290_last_taken() const;
};

#endif // CPU_HPP

