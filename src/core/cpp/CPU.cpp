#include "CPU.hpp"
#include "MMU.hpp"
#include "Registers.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include <map>

CPU::CPU(MMU* mmu, CoreRegisters* registers)
    : mmu_(mmu), regs_(registers), ppu_(nullptr), timer_(nullptr), cycles_(0), ime_(false), halted_(false), ime_scheduled_(false),
      in_vblank_handler_(false), vblank_handler_steps_(0), post_delay_trace_active_(false), post_delay_count_(0),
      in_post_cleanup_trace_(false), post_cleanup_trace_count_(0), reg_trace_active_(false),
      last_af_(0xFFFF), last_bc_(0xFFFF), last_de_(0xFFFF), last_hl_(0xFFFF), reg_trace_count_(0),
      jump_trace_active_(false), jump_trace_count_(0), hw_state_trace_active_(false),
      hw_state_samples_(0), hw_state_sample_counter_(0),
      instruction_counter_step382_(0), last_pc_sample_(0xFFFF), pc_repeat_count_(0),
      wait_loop_trace_active_(false), wait_loop_trace_count_(0), wait_loop_detected_(false) {
    // Validación básica (en producción, podríamos usar assert)
    // Por ahora, confiamos en que Python pasa punteros válidos
    // IME inicia en false por seguridad (el juego lo activará si lo necesita)
    // Step 0287: Inicialización de miembros de diagnóstico (reemplazan variables static)
    // Step 0293: Inicialización de monitores de rastreo post-limpieza
    // Step 0382: Inicialización de PC sampler
    // Step 0383: Inicialización de trazado de wait-loop
}

CPU::~CPU() {
    // No liberamos mmu_ ni regs_ porque no los poseemos
    // Python (PyMMU, PyRegisters) es el dueño de la memoria
}

uint8_t CPU::fetch_byte() {
    // Lee el byte de memoria en dirección PC
    uint8_t value = mmu_->read(regs_->pc);
    // Incrementa PC (wrap-around en 16 bits)
    regs_->pc = (regs_->pc + 1) & 0xFFFF;
    return value;
}

uint16_t CPU::fetch_word() {
    // Lee primero el byte bajo (LSB) en formato Little-Endian
    uint8_t low = fetch_byte();
    // Lee luego el byte alto (MSB)
    uint8_t high = fetch_byte();
    // Combina: (high << 8) | low
    return (static_cast<uint16_t>(high) << 8) | static_cast<uint16_t>(low);
}

// ========== Implementación de Helpers de Stack ==========

void CPU::push_byte(uint8_t val) {
    // La pila crece hacia abajo: decrementar SP primero
    regs_->sp = (regs_->sp - 1) & 0xFFFF;  // Wrap-around en 16 bits
    // Escribir el byte en memoria
    mmu_->write(regs_->sp, val);
}

uint8_t CPU::pop_byte() {
    // Leer el byte de memoria en la dirección SP
    uint8_t val = mmu_->read(regs_->sp);
    // Incrementar SP (la pila se "encoge")
    regs_->sp = (regs_->sp + 1) & 0xFFFF;  // Wrap-around en 16 bits
    return val;
}

void CPU::push_word(uint16_t val) {
    // PUSH escribe primero el byte alto (MSB), luego el bajo (LSB)
    // Esto es consistente con el orden de escritura en memoria
    // High byte va en SP-1, low byte va en SP-2
    push_byte((val >> 8) & 0xFF);  // High byte
    push_byte(val & 0xFF);          // Low byte
}

uint16_t CPU::pop_word() {
    // POP lee primero el byte bajo (LSB), luego el alto (MSB)
    // Esto es el orden inverso de PUSH (LIFO - Last In First Out)
    uint8_t low = pop_byte();   // Low byte (se lee primero)
    uint8_t high = pop_byte();  // High byte (se lee segundo)
    // Combinar en formato Little-Endian: (high << 8) | low
    return (static_cast<uint16_t>(high) << 8) | static_cast<uint16_t>(low);
}

// ========== Implementación de Helpers ALU ==========

void CPU::alu_add(uint8_t value) {
    // Suma: A = A + value
    // Guardar A original para calcular flags
    uint8_t a_old = regs_->a;
    uint16_t result = static_cast<uint16_t>(a_old) + static_cast<uint16_t>(value);
    
    // Actualizar registro A (truncar a 8 bits)
    regs_->a = static_cast<uint8_t>(result);
    
    // Calcular flags
    // Z: resultado == 0
    regs_->set_flag_z(regs_->a == 0);
    
    // N: siempre 0 en suma
    regs_->set_flag_n(false);
    
    // H: half-carry (bit 3 -> 4)
    // Fórmula: ((a_old & 0xF) + (value & 0xF)) > 0xF
    // En C++, esto se compila a muy pocas instrucciones de máquina
    uint8_t a_low = a_old & 0x0F;
    uint8_t value_low = value & 0x0F;
    bool half_carry = (a_low + value_low) > 0x0F;
    regs_->set_flag_h(half_carry);
    
    // C: carry completo (overflow 8 bits)
    regs_->set_flag_c(result > 0xFF);
}

void CPU::alu_sub(uint8_t value) {
    // Resta: A = A - value
    uint8_t a_old = regs_->a;
    regs_->a = a_old - value;
    
    // Calcular flags
    // Z: resultado == 0
    regs_->set_flag_z(regs_->a == 0);
    
    // N: siempre 1 en resta
    regs_->set_flag_n(true);
    
    // H: half-borrow (bit 4 -> 3)
    // Fórmula: (a_old & 0xF) < (value & 0xF)
    bool half_borrow = (a_old & 0x0F) < (value & 0x0F);
    regs_->set_flag_h(half_borrow);
    
    // C: borrow completo (underflow)
    regs_->set_flag_c(a_old < value);
}

void CPU::alu_and(uint8_t value) {
    // AND: A = A & value
    regs_->a = regs_->a & value;
    
    // Calcular flags
    // Z: resultado == 0
    regs_->set_flag_z(regs_->a == 0);
    
    // N: siempre 0
    regs_->set_flag_n(false);
    
    // H: QUIRK del hardware - AND siempre pone H=1
    regs_->set_flag_h(true);
    
    // C: siempre 0
    regs_->set_flag_c(false);
}

void CPU::alu_xor(uint8_t value) {
    // XOR: A = A ^ value
    regs_->a = regs_->a ^ value;
    
    // Calcular flags
    // Z: resultado == 0
    regs_->set_flag_z(regs_->a == 0);
    
    // N: siempre 0
    regs_->set_flag_n(false);
    
    // H: siempre 0
    regs_->set_flag_h(false);
    
    // C: siempre 0
    regs_->set_flag_c(false);
}

uint8_t CPU::alu_inc(uint8_t value) {
    // INC: incrementa el valor en 1
    uint8_t result = value + 1;
    
    // Calcular flags
    // Z: resultado == 0
    regs_->set_flag_z(result == 0);
    
    // N: siempre 0 (es incremento)
    regs_->set_flag_n(false);
    
    // H: half-carry (bit 3 -> 4)
    // Ocurre cuando el nibble bajo es 0x0F y al sumar 1 se produce overflow
    // Ejemplo: 0x0F + 1 = 0x10 (hay half-carry)
    regs_->set_flag_h((value & 0x0F) == 0x0F);
    
    // C: NO afectado (preservado) - QUIRK del hardware
    // No modificamos el flag C
    
    return result;
}

uint8_t CPU::alu_dec(uint8_t value) {
    // DEC: decrementa el valor en 1
    uint8_t result = value - 1;
    
    // Calcular flags
    // --- VERIFICACIÓN CRÍTICA (Step 0165) ---
    // La siguiente línea es la que resuelve el deadlock del bucle de inicialización.
    // Asegura que el flag Z se active (set_flag_z(true)) si el resultado del
    // decremento es exactamente 0. Sin esto, los bucles 'JR NZ' serían infinitos.
    // Ejemplo: Si B = 1, DEC B → B = 0, y Z DEBE ser 1 para que JR NZ no salte.
    // Si Z no se activa cuando result == 0, el bucle nunca terminará.
    // Si result == 0, entonces Z = 1 (activado)
    // Si result != 0, entonces Z = 0 (desactivado)
    regs_->set_flag_z(result == 0);
    
    // N: siempre 1 (es decremento)
    regs_->set_flag_n(true);
    
    // H: half-borrow (bit 4 -> 3)
    // Ocurre cuando el nibble bajo es 0x00 y al restar 1 se produce underflow
    // Ejemplo: 0x10 - 1 = 0x0F (hay half-borrow)
    // El Half-Borrow ocurre si el nibble bajo era 0x0, indicando un préstamo del nibble alto.
    regs_->set_flag_h((value & 0x0F) == 0x00);
    
    // C: NO afectado (preservado) - QUIRK del hardware
    // El flag C (Carry) no se modifica en las instrucciones DEC de 8 bits, una peculiaridad del hardware.
    // No modificamos el flag C
    
    return result;
}

void CPU::alu_adc(uint8_t value) {
    // ADC: Add with Carry - A = A + value + C
    uint8_t a_old = regs_->a;
    uint8_t carry = regs_->get_flag_c() ? 1 : 0;
    uint16_t result = static_cast<uint16_t>(a_old) + static_cast<uint16_t>(value) + static_cast<uint16_t>(carry);
    
    // Actualizar registro A
    regs_->a = static_cast<uint8_t>(result);
    
    // Calcular flags
    regs_->set_flag_z(regs_->a == 0);
    regs_->set_flag_n(false);
    
    // H: half-carry (bit 3 -> 4) incluyendo carry
    uint8_t a_low = a_old & 0x0F;
    uint8_t value_low = value & 0x0F;
    bool half_carry = (a_low + value_low + carry) > 0x0F;
    regs_->set_flag_h(half_carry);
    
    // C: carry completo
    regs_->set_flag_c(result > 0xFF);
}

void CPU::alu_sbc(uint8_t value) {
    // SBC: Subtract with Carry - A = A - value - C
    uint8_t a_old = regs_->a;
    uint8_t carry = regs_->get_flag_c() ? 1 : 0;
    uint16_t result = static_cast<uint16_t>(a_old) - static_cast<uint16_t>(value) - static_cast<uint16_t>(carry);
    
    // Actualizar registro A
    regs_->a = static_cast<uint8_t>(result);
    
    // Calcular flags
    regs_->set_flag_z(regs_->a == 0);
    regs_->set_flag_n(true);
    
    // H: half-borrow (bit 4 -> 3) incluyendo carry
    // Ocurre cuando el nibble bajo de A es menor que el nibble bajo de (value + carry)
    uint8_t a_low = a_old & 0x0F;
    uint8_t value_low = value & 0x0F;
    bool half_borrow = (a_low < (value_low + carry));
    regs_->set_flag_h(half_borrow);
    
    // C: borrow completo (underflow)
    // Usar el resultado de 16 bits para detectar underflow de forma segura
    // Si result > 0xFF, significa que hubo underflow (resultado negativo en aritmética con signo)
    regs_->set_flag_c(result > 0xFF);
}

void CPU::alu_or(uint8_t value) {
    // OR: A = A | value
    regs_->a = regs_->a | value;
    
    // Calcular flags
    regs_->set_flag_z(regs_->a == 0);
    regs_->set_flag_n(false);
    regs_->set_flag_h(false);
    regs_->set_flag_c(false);
}

void CPU::alu_cp(uint8_t value) {
    // CP: Compare - realiza A - value pero NO guarda el resultado
    // Es equivalente a SUB pero sin modificar A
    uint8_t a_old = regs_->a;
    uint16_t result = static_cast<uint16_t>(a_old) - static_cast<uint16_t>(value);
    uint8_t result_8bit = static_cast<uint8_t>(result);
    
    // Calcular flags (igual que SUB)
    regs_->set_flag_z(result_8bit == 0);
    regs_->set_flag_n(true);
    
    // H: half-borrow
    bool half_borrow = (a_old & 0x0F) < (value & 0x0F);
    regs_->set_flag_h(half_borrow);
    
    // C: borrow completo
    regs_->set_flag_c(a_old < value);
    
    // IMPORTANTE: A NO se modifica (solo se calculan flags)
}

// ========== Implementación de Helpers de Load ==========

uint8_t* CPU::get_register_ptr(uint8_t reg_code) {
    // Mapeo de códigos de registro a punteros
    // Códigos: 0=B, 1=C, 2=D, 3=E, 4=H, 5=L, 6=(HL), 7=A
    switch (reg_code) {
        case 0: return &regs_->b;
        case 1: return &regs_->c;
        case 2: return &regs_->d;
        case 3: return &regs_->e;
        case 4: return &regs_->h;
        case 5: return &regs_->l;
        case 6: return nullptr;  // (HL) requiere acceso a memoria
        case 7: return &regs_->a;
        default: return nullptr;
    }
}

uint8_t CPU::read_register_or_mem(uint8_t reg_code) {
    if (reg_code == 6) {
        // (HL): leer de memoria en dirección HL
        uint16_t addr = regs_->get_hl();
        return mmu_->read(addr);
    } else {
        // Leer de registro
        uint8_t* reg_ptr = get_register_ptr(reg_code);
        return (reg_ptr != nullptr) ? *reg_ptr : 0;
    }
}

void CPU::write_register_or_mem(uint8_t reg_code, uint8_t value) {
    if (reg_code == 6) {
        // (HL): escribir en memoria en dirección HL
        uint16_t addr = regs_->get_hl();
        mmu_->write(addr, value);
    } else {
        // Escribir en registro
        uint8_t* reg_ptr = get_register_ptr(reg_code);
        if (reg_ptr != nullptr) {
            *reg_ptr = value;
        }
    }
}

void CPU::ld_r_r(uint8_t dest_code, uint8_t src_code) {
    // LD r, r': copiar valor de origen a destino
    // Esta función maneja todo el bloque 0x40-0x7F
    uint8_t value = read_register_or_mem(src_code);
    write_register_or_mem(dest_code, value);
}

// ========== Implementación de Helpers de Aritmética 16-bit ==========

void CPU::inc_16bit(uint8_t reg_pair) {
    // INC rr: incrementa el par de registros
    // IMPORTANTE: NO afecta flags
    switch (reg_pair) {
        case 0: {  // BC
            uint16_t bc = regs_->get_bc();
            bc = (bc + 1) & 0xFFFF;  // Wrap-around en 16 bits
            regs_->set_bc(bc);
            break;
        }
        case 1: {  // DE
            uint16_t de = regs_->get_de();
            de = (de + 1) & 0xFFFF;
            regs_->set_de(de);
            break;
        }
        case 2: {  // HL
            uint16_t hl = regs_->get_hl();
            hl = (hl + 1) & 0xFFFF;
            regs_->set_hl(hl);
            break;
        }
        case 3: {  // SP
            regs_->sp = (regs_->sp + 1) & 0xFFFF;
            break;
        }
    }
}

void CPU::dec_16bit(uint8_t reg_pair) {
    // DEC rr: decrementa el par de registros
    // IMPORTANTE: NO afecta flags
    switch (reg_pair) {
        case 0: {  // BC
            uint16_t bc = regs_->get_bc();
            bc = (bc - 1) & 0xFFFF;  // Wrap-around en 16 bits
            regs_->set_bc(bc);
            break;
        }
        case 1: {  // DE
            uint16_t de = regs_->get_de();
            de = (de - 1) & 0xFFFF;
            regs_->set_de(de);
            break;
        }
        case 2: {  // HL
            uint16_t hl = regs_->get_hl();
            hl = (hl - 1) & 0xFFFF;
            regs_->set_hl(hl);
            break;
        }
        case 3: {  // SP
            regs_->sp = (regs_->sp - 1) & 0xFFFF;
            break;
        }
    }
}

void CPU::add_hl(uint16_t value) {
    // ADD HL, rr: suma un valor de 16 bits a HL
    // Flags: Z no afectado, N=0, H y C se calculan
    uint16_t hl_old = regs_->get_hl();
    uint32_t result = static_cast<uint32_t>(hl_old) + static_cast<uint32_t>(value);
    
    // Actualizar HL (truncar a 16 bits)
    uint16_t hl_new = static_cast<uint16_t>(result);
    regs_->set_hl(hl_new);
    
    // Calcular flags
    // N: siempre 0 (es suma)
    regs_->set_flag_n(false);
    
    // H: half-carry en bit 11 (bit 3 del byte alto)
    // Fórmula: ((hl_old & 0xFFF) + (value & 0xFFF)) > 0xFFF
    uint16_t hl_low = hl_old & 0x0FFF;
    uint16_t value_low = value & 0x0FFF;
    bool half_carry = (hl_low + value_low) > 0x0FFF;
    regs_->set_flag_h(half_carry);
    
    // C: carry completo (overflow 16 bits)
    regs_->set_flag_c(result > 0xFFFF);
    
    // Z: NO afectado (mantiene valor anterior)
}

int CPU::step() {
    // --- Step 0284: Monitores de Diagnóstico al Inicio (ANTES de early return) ---
    // Capturamos el PC ANTES de procesar interrupciones para que los monitores
    // se ejecuten incluso cuando hay interrupciones que causan early return
    uint16_t original_pc = regs_->pc;
    
    // --- Step 0382: PC Sampler y Detección de Bucles (Diagnóstico H1) ---
    // Muestrea el PC cada N instrucciones para detectar si la CPU está atascada en un bucle
    instruction_counter_step382_++;
    
    // Muestrear cada 10,000 instrucciones (pero solo loggear las primeras 50 muestras)
    static int sample_log_count_step382 = 0;
    if (instruction_counter_step382_ % 10000 == 0 && sample_log_count_step382 < 50) {
        sample_log_count_step382++;
        
        uint8_t ime = ime_ ? 1 : 0;
        uint8_t ie = mmu_->read(0xFFFF);
        uint8_t if_reg = mmu_->read(0xFF0F);
        uint16_t bank = mmu_->get_current_rom_bank();
        
        printf("[CPU-SAMPLE] #%d | Instrs:%d | PC:0x%04X | Bank:%d | IME:%d | IE:0x%02X | IF:0x%02X | HALT:%d\n",
               sample_log_count_step382, instruction_counter_step382_, original_pc, bank,
               ime, ie, if_reg, halted_ ? 1 : 0);
        
        // Detectar bucle: mismo PC repitiéndose
        if (original_pc == last_pc_sample_) {
            pc_repeat_count_++;
            if (pc_repeat_count_ > 3) {
                printf("[CPU-LOOP-DETECT] ⚠️ PC:0x%04X se repite %d veces! Posible bucle de polling.\n",
                       original_pc, pc_repeat_count_);
            }
        } else {
            pc_repeat_count_ = 0;
        }
        last_pc_sample_ = original_pc;
    }
    
    // Detectar transiciones de HALT
    static bool was_halted_step382 = false;
    if (halted_ && !was_halted_step382) {
        printf("[CPU-HALT] Entrando en HALT | PC:0x%04X | IME:%d | IE:0x%02X | IF:0x%02X\n",
               original_pc, ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
    } else if (!halted_ && was_halted_step382) {
        printf("[CPU-HALT] Saliendo de HALT | PC:0x%04X | IME:%d | IE:0x%02X | IF:0x%02X\n",
               original_pc, ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
    }
    was_halted_step382 = halted_;
    // -------------------------------------------
    
    // --- Step 0385: Detector de Wait-Loop Genérico ---
    // Detecta bucles de polling sin asumir banco/PC específico
    // Objetivo: localizar automáticamente el PC más repetido (el bucle donde Zelda DX se queda congelado)
    // Umbral: 5000 repeticiones del mismo PC indica bucle de espera (polling)
    static uint16_t last_pc_for_loop = 0xFFFF;
    static int same_pc_streak = 0;
    static const int WAITLOOP_THRESHOLD = 5000;
    
    if (original_pc == last_pc_for_loop) {
        same_pc_streak++;
        
        // Detectar loop cuando se alcanza el umbral (primera vez)
        if (same_pc_streak == WAITLOOP_THRESHOLD && !wait_loop_detected_) {
            wait_loop_detected_ = true;
            wait_loop_trace_active_ = true;
            wait_loop_trace_count_ = 0;
            
            // Activar trazado de MMIO/RAM en la MMU
            mmu_->set_waitloop_trace(true);
            
            uint16_t bank = mmu_->get_current_rom_bank();
            uint16_t af = regs_->get_af();
            uint16_t hl = regs_->get_hl();
            uint8_t ime = ime_ ? 1 : 0;
            uint8_t ie = mmu_->read(0xFFFF);
            uint8_t if_reg = mmu_->read(0xFF0F);
            
            printf("[WAITLOOP-DETECT] ⚠️ Bucle detectado! PC:0x%04X Bank:%d repetido %d veces\n",
                   original_pc, bank, same_pc_streak);
            printf("[WAITLOOP-DETECT] Estado: AF:0x%04X HL:0x%04X IME:%d IE:0x%02X IF:0x%02X\n",
                   af, hl, ime, ie, if_reg);
            printf("[WAITLOOP-DETECT] Activando trazado de 200 iteraciones...\n");
        }
    } else {
        same_pc_streak = 0;
    }
    last_pc_for_loop = original_pc;
    
    // Trazado activo del loop (máx 200 iteraciones)
    if (wait_loop_trace_active_ && wait_loop_trace_count_ < 200) {
        uint16_t bank = mmu_->get_current_rom_bank();
        uint8_t opcode = mmu_->read(original_pc);
        uint8_t byte1 = (regs_->pc < 0xFFFF) ? mmu_->read(regs_->pc) : 0x00;
        uint8_t byte2 = (regs_->pc < 0xFFFE) ? mmu_->read(regs_->pc + 1) : 0x00;
        
        printf("[WAITLOOP-TRACE] #%d PC:0x%04X Bank:%d OP:%02X %02X %02X | AF:%04X BC:%04X DE:%04X HL:%04X SP:%04X | IME:%d IE:%02X IF:%02X\n",
               wait_loop_trace_count_,
               original_pc, bank,
               opcode, byte1, byte2,
               regs_->get_af(), regs_->get_bc(), regs_->get_de(), regs_->get_hl(), regs_->sp,
               ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
        
        wait_loop_trace_count_++;
        
        if (wait_loop_trace_count_ >= 200) {
            wait_loop_trace_active_ = false;
            // Desactivar trazado de MMIO/RAM en la MMU
            mmu_->set_waitloop_trace(false);
            printf("[WAITLOOP-TRACE] Fin del trazado (200 iteraciones completadas)\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0279: Monitor de Reinicio (Reset Loop Detection) ---
    // Detecta cuando el PC pasa por los vectores de reinicio (0x0000 o 0x0100)
    // Esto indica que el juego está en un bucle de reinicio, posiblemente debido a:
    // - Pila corrupta
    // - Banco ROM mal mapeado (MBC1 en modo incorrecto)
    // - Error fatal que causa un RST 00 o salto a 0x0000
    // Fuente: Pan Docs - "Reset Vectors": 0x0000 (Boot ROM) y 0x0100 (Cartridge Entry)
    if (original_pc == 0x0000 || original_pc == 0x0100) {
        static uint32_t reset_count = 0;
        printf("[RESET-WATCH] Pasando por PC:0x%04X (Contador: %u) | SP:0x%04X Bank:%d | IME:%d IE:%02X IF:%02X\n",
               original_pc, ++reset_count, regs_->sp, mmu_->get_current_rom_bank(),
               ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
    }
    
    // --- Step 0385: Trazado Acotado del Handler de VBlank ---
    // Detecta cuando el código entra al handler de V-Blank (0x0040)
    // y traza las primeras 80 instrucciones del handler (solo para los primeros 3 VBlanks)
    // Objetivo: ver si el VBlank ISR está actualizando los flags que el main-loop espera
    // Fuente: Pan Docs - "Interrupt Vectors": 0x0040 es el vector de V-Blank
    static int vblank_entry_count = 0;
    static bool vblank_isr_trace_active = false;
    static int vblank_isr_trace_count = 0;
    static const int MAX_VBLANK_ENTRIES = 3;
    static const int MAX_ISR_TRACE = 80;
    
    if (original_pc == 0x0040) {
        vblank_entry_count++;
        
        if (vblank_entry_count <= MAX_VBLANK_ENTRIES) {
            printf("[VBLANK-ENTER] #%d Vector 0x%04X alcanzado | SP:0x%04X HL:0x%04X A:0x%02X Bank:%d IME:%d IE:%02X IF:%02X\n",
                   vblank_entry_count,
                   original_pc, regs_->sp, regs_->get_hl(), regs_->a, mmu_->get_current_rom_bank(),
                   ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
            
            // Activar trazado del ISR y de MMIO en la MMU
            vblank_isr_trace_active = true;
            vblank_isr_trace_count = 0;
            mmu_->set_vblank_isr_trace(true);
        }
    }
    
    // Trazado activo del ISR VBlank (máx 80 instrucciones, solo para primeros 3 VBlanks)
    if (vblank_isr_trace_active && vblank_isr_trace_count < MAX_ISR_TRACE) {
        uint16_t bank = mmu_->get_current_rom_bank();
        uint8_t opcode = mmu_->read(original_pc);
        uint8_t byte1 = (regs_->pc < 0xFFFF) ? mmu_->read(regs_->pc) : 0x00;
        uint8_t byte2 = (regs_->pc < 0xFFFE) ? mmu_->read(regs_->pc + 1) : 0x00;
        
        printf("[VBLANK-TRACE] ISR#%d Step#%d PC:0x%04X Bank:%d OP:%02X %02X %02X | AF:%04X HL:%04X SP:%04X\n",
               vblank_entry_count,
               vblank_isr_trace_count,
               original_pc, bank,
               opcode, byte1, byte2,
               regs_->get_af(), regs_->get_hl(), regs_->sp);
        
        vblank_isr_trace_count++;
        
        // Detectar salida del ISR (RETI 0xD9 o RET 0xC9)
        if (opcode == 0xD9 || opcode == 0xC9) {
            vblank_isr_trace_active = false;
            mmu_->set_vblank_isr_trace(false);
            printf("[VBLANK-TRACE] ISR#%d terminado (instrucción %d)\n",
                   vblank_entry_count, vblank_isr_trace_count);
        }
        
        if (vblank_isr_trace_count >= MAX_ISR_TRACE) {
            vblank_isr_trace_active = false;
            mmu_->set_vblank_isr_trace(false);
            printf("[VBLANK-TRACE] ISR#%d trazado completado (80 instrucciones)\n",
                   vblank_entry_count);
        }
    }
    
    // --- Step 0294: Monitor de Verificación de VRAM en ISRs ([ISR-VRAM-CHECK]) ---
    // Verifica si las ISRs acceden a VRAM cuando se ejecutan.
    // Esto ayuda a confirmar si el código de carga está en una ISR.
    static bool in_isr = false;
    static int isr_vram_access_count = 0;
    
    // Detectar entrada a ISR (vectores de interrupción)
    if (original_pc == 0x0040 || original_pc == 0x0048 || original_pc == 0x0050 ||
        original_pc == 0x0058 || original_pc == 0x0060) {
        in_isr = true;
        isr_vram_access_count = 0;
        printf("[ISR-VRAM-CHECK] Entrada a ISR en vector 0x%04X\n", original_pc);
    }
    
    // Detectar accesos a VRAM durante ISR
    if (in_isr) {
        uint8_t op = mmu_->read(original_pc);
        // Verificar si hay escrituras a VRAM en las siguientes instrucciones
        // Detectamos opcodes que escriben a (HL): LD (HL+), A (0x22), LD (HL-), A (0x32), LD (HL), A (0x77)
        if (op == 0x22 || op == 0x32 || op == 0x77) {
            uint16_t hl_val = regs_->get_hl();
            if (hl_val >= 0x8000 && hl_val <= 0x97FF) {
                isr_vram_access_count++;
                printf("[ISR-VRAM-CHECK] ⚠️ ACCESO A VRAM DETECTADO en ISR: PC:0x%04X HL:0x%04X (acceso #%d)\n",
                       original_pc, hl_val, isr_vram_access_count);
            }
        }
        
        // Detectar salida de ISR (RETI)
        if (op == 0xD9) {  // RETI
            printf("[ISR-VRAM-CHECK] Salida de ISR (RETI) en PC:0x%04X | Accesos a VRAM: %d\n",
                   original_pc, isr_vram_access_count);
            in_isr = false;
        }
    }
    
    // --- Step 0294: Monitor de Secuencia de Activación BG ([BG-ENABLE-SEQUENCE]) ---
    // Rastrea la secuencia de ejecución después de habilitar BG Display
    // para ver si el código de carga se ejecuta después.
    static bool bg_enable_trace_active = false;
    static int bg_enable_trace_count = 0;
    static uint16_t bg_enable_pc = 0x0000;
    static uint8_t last_lcdc = 0x00;
    
    // Leer LCDC actual y detectar si BG Display se acaba de habilitar
    uint8_t current_lcdc = mmu_->read(0xFF40);
    bool bg_just_enabled = !(last_lcdc & 0x01) && (current_lcdc & 0x01);
    if (bg_just_enabled) {
        bg_enable_trace_active = true;
        bg_enable_trace_count = 0;
        bg_enable_pc = original_pc;
        printf("[BG-ENABLE-SEQUENCE] ⚠️ BG DISPLAY HABILITADO en PC:0x%04X. Iniciando rastreo de 300 instrucciones...\n",
               original_pc);
    }
    
    if (bg_enable_trace_active && bg_enable_trace_count < 300) {
        uint8_t op = mmu_->read(original_pc);
        uint16_t hl_val = regs_->get_hl();
        
        printf("[BG-ENABLE-SEQUENCE] PC:0x%04X OP:0x%02X | HL:0x%04X | A:0x%02X\n",
               original_pc, op, hl_val, regs_->a);
        
        // Verificar si HL apunta a VRAM
        if (hl_val >= 0x8000 && hl_val <= 0x97FF) {
            printf("[BG-ENABLE-SEQUENCE] ⚠️ HL APUNTA A VRAM (0x%04X) después de habilitar BG\n", hl_val);
        }
        
        bg_enable_trace_count++;
        if (bg_enable_trace_count >= 300) {
            bg_enable_trace_active = false;
            printf("[BG-ENABLE-SEQUENCE] Fin del rastreo de secuencia de activación BG\n");
        }
    }
    
    last_lcdc = current_lcdc;
    
    // --- Step 0295: Monitor Global de Accesos VRAM ([VRAM-ACCESS-GLOBAL]) ---
    // Detecta TODOS los accesos de escritura a VRAM (0x8000-0x9FFF) sin importar
    // dónde ocurran en el flujo de ejecución. Esto permite identificar si hay
    // código que carga tiles en algún momento, incluso fuera de ISRs o flujo principal.
    // 
    // Este monitor verifica si HL apunta a VRAM cuando se ejecutan opcodes de escritura.
    // Fuente: Pan Docs - "Video RAM (VRAM)": 0x8000-0x97FF contiene Tile Data y 0x9800-0x9FFF contiene Tile Maps
    static int vram_access_global_count = 0;
    static bool vram_access_global_active = true;  // Siempre activo
    static std::map<uint16_t, int> pc_vram_access_map;  // Para [PC-VRAM-CORRELATION]
    static int pc_vram_correlation_count = 0;  // Para [PC-VRAM-CORRELATION]
    static uint16_t last_vram_addr = 0xFFFF;  // Para [LOAD-SEQUENCE]
    static uint16_t sequence_start_addr = 0xFFFF;  // Para [LOAD-SEQUENCE]
    static int sequence_length = 0;  // Para [LOAD-SEQUENCE]
    static uint16_t sequence_start_pc = 0x0000;  // Para [LOAD-SEQUENCE]
    static int load_sequence_count = 0;  // Para [LOAD-SEQUENCE]
    static uint64_t instruction_counter = 0;  // Para [TIMING-VRAM]
    
    instruction_counter++;
    
    if (vram_access_global_active && vram_access_global_count < 1000) {
        uint8_t op = mmu_->read(original_pc);
        uint16_t hl_val = regs_->get_hl();
        
        // Detectar opcodes que escriben a memoria apuntada por HL
        bool is_write_op = false;
        uint16_t write_addr = 0x0000;
        uint8_t write_value = 0x00;
        
        if (op == 0x22) {  // LD (HL+), A
            is_write_op = true;
            write_addr = hl_val;
            write_value = regs_->a;
        } else if (op == 0x32) {  // LD (HL-), A
            is_write_op = true;
            write_addr = hl_val;
            write_value = regs_->a;
        } else if (op == 0x77) {  // LD (HL), A
            is_write_op = true;
            write_addr = hl_val;
            write_value = regs_->a;
        } else if (op == 0x36) {  // LD (HL), n
            is_write_op = true;
            write_addr = hl_val;
            write_value = mmu_->read(original_pc + 1);
        } else if (op >= 0x70 && op <= 0x75) {  // LD (HL), r (B, C, D, E, H, L)
            is_write_op = true;
            write_addr = hl_val;
            // Extraer el registro (bits 0-2 del opcode)
            uint8_t reg_idx = op & 0x07;
            switch(reg_idx) {
                case 0: write_value = regs_->b; break;
                case 1: write_value = regs_->c; break;
                case 2: write_value = regs_->d; break;
                case 3: write_value = regs_->e; break;
                case 4: write_value = regs_->h; break;
                case 5: write_value = regs_->l; break;
                default: write_value = 0x00; break;
            }
        }
        
        // Verificar si la dirección de escritura está en VRAM
        if (is_write_op && write_addr >= 0x8000 && write_addr <= 0x9FFF) {
            // Determinar si es Tile Data o Tile Map
            bool is_tile_data = (write_addr >= 0x8000 && write_addr <= 0x97FF);
            bool is_tile_map = (write_addr >= 0x9800 && write_addr <= 0x9FFF);
            
            // Calcular Tile ID aproximado si es Tile Data
            uint8_t tile_id_approx = 0xFF;
            if (is_tile_data) {
                uint16_t tile_offset = write_addr - 0x8000;
                tile_id_approx = tile_offset / 16;
            }
            
            // Verificar si es dato real o limpieza
            bool is_data = (write_value != 0x00 && write_value != 0x7F);
            
            // [VRAM-ACCESS-GLOBAL]: Reportar acceso
            printf("[VRAM-ACCESS-GLOBAL] PC:0x%04X OP:0x%02X | Write %04X=%02X (%s, TileID~%d) | %s | Bank:%d\n",
                   original_pc, op, write_addr, write_value,
                   is_tile_data ? "TileData" : "TileMap",
                   tile_id_approx, is_data ? "DATA" : "CLEAR",
                   mmu_->get_current_rom_bank());
            
            // --- Step 0297: Monitor [TIMELINE-VRAM] - Timeline de Accesos VRAM ---
            // Reportar timeline cuando se detecta acceso a VRAM
            static uint64_t timeline_start_instructions_local = 0;
            static bool timeline_started_local = false;
            static int timeline_samples_local = 0;
            
            if (!timeline_started_local) {
                timeline_start_instructions_local = instruction_counter;
                timeline_started_local = true;
            }
            
            uint64_t relative_instructions = instruction_counter - timeline_start_instructions_local;
            uint64_t approx_seconds = relative_instructions / (4194304 / 4);  // Aproximado: 4.19MHz / 4 ciclos promedio
            
            timeline_samples_local++;
            if (timeline_samples_local <= 200) {  // Limitar muestras
                printf("[TIMELINE-VRAM] T+~%llus | PC:0x%04X | Write %04X=%02X | %s\n",
                       approx_seconds, original_pc, write_addr, write_value,
                       is_data ? "DATA" : "CLEAR");
            }
            
            vram_access_global_count++;
            
            if (vram_access_global_count >= 1000) {
                printf("[VRAM-ACCESS-GLOBAL] Límite alcanzado (1000 accesos). Monitor desactivado.\n");
                vram_access_global_active = false;
            }
            
            // --- Step 0295: Monitor [PC-VRAM-CORRELATION] - Correlación PC-VRAM ---
            // Registrar este PC en el mapa
            pc_vram_access_map[original_pc]++;
            pc_vram_correlation_count++;
            
            // Imprimir inmediatamente si es un PC nuevo o si es dato (no limpieza)
            if (pc_vram_access_map[original_pc] == 1 || is_data) {
                printf("[PC-VRAM-CORRELATION] PC:0x%04X accede a VRAM %04X (acceso #%d) | %s\n",
                       original_pc, write_addr, pc_vram_access_map[original_pc],
                       is_data ? "DATA" : "CLEAR");
            }
            
            // --- Step 0295: Monitor [LOAD-SEQUENCE] - Secuencias de Carga ---
            // Detecta secuencias consecutivas de escrituras a VRAM que podrían ser carga de tiles
            if (write_addr == last_vram_addr + 1 || (last_vram_addr != 0xFFFF && write_addr == last_vram_addr - 1)) {
                sequence_length++;
                if (sequence_length == 1) {
                    sequence_start_addr = write_addr;
                    sequence_start_pc = original_pc;
                }
                
                // Si la secuencia alcanza 16 bytes (un tile completo), reportar
                if (sequence_length == 16) {
                    load_sequence_count++;
                    printf("[LOAD-SEQUENCE] ⚠️ SECUENCIA DE CARGA DETECTADA: PC:0x%04X | Rango: 0x%04X-0x%04X (%d bytes) | Tile completo\n",
                           sequence_start_pc, sequence_start_addr, write_addr, sequence_length);
                }
            } else {
                // Nueva secuencia o secuencia terminada
                if (sequence_length >= 16) {
                    printf("[LOAD-SEQUENCE] Secuencia terminada: %d bytes desde 0x%04X\n",
                           sequence_length, sequence_start_addr);
                }
                sequence_length = 1;
                sequence_start_addr = write_addr;
                sequence_start_pc = original_pc;
            }
            
            last_vram_addr = write_addr;
            
            // --- Step 0295: Monitor [TIMING-VRAM] - Timing de Accesos VRAM ---
            // Rastrea el timing de accesos a VRAM (frame, relación con eventos)
            uint8_t ly = mmu_->read(0xFF44);
            uint8_t lcdc = mmu_->read(0xFF40);
            bool lcd_on = (lcdc & 0x80) != 0;
            bool bg_display = (lcdc & 0x01) != 0;
            
            // Aproximar frame basado en instrucciones (456 ciclos por scanline * 144 scanlines = 65,664 ciclos por frame)
            // Asumiendo ~4 ciclos por instrucción promedio, ~16,416 instrucciones por frame
            uint64_t approx_frame = instruction_counter / 16416;
            
            printf("[TIMING-VRAM] PC:0x%04X | Frame:~%llu | LY:%d | LCD:%s BG:%s | Write %04X=%02X\n",
                   original_pc, approx_frame, ly, lcd_on ? "ON" : "OFF", bg_display ? "ON" : "OFF",
                   write_addr, write_value);
        }
    }
    
    // --- Step 0295: Monitor [ROM-TO-VRAM] - Copias desde ROM ---
    // Detecta cuando se copian datos desde ROM a VRAM usando LDIR (Load, Increment, Repeat)
    // Patrón común: LD HL, <rom_addr> ; LD DE, <vram_addr> ; LD BC, <length> ; LDIR
    static int rom_to_vram_count = 0;
    
    uint8_t op = mmu_->read(original_pc);
    
    // Detectar LDIR (0xED 0xB0) - Copy (HL++) to (DE++), decrement BC, repeat
    if (op == 0xED) {
        uint8_t next_byte = mmu_->read(original_pc + 1);
        if (next_byte == 0xB0) {  // LDIR
            uint16_t hl_val = regs_->get_hl();
            uint16_t de_val = regs_->get_de();
            uint16_t bc_val = regs_->get_bc();
            
            // Verificar si DE apunta a VRAM
            if (de_val >= 0x8000 && de_val <= 0x9FFF) {
                rom_to_vram_count++;
                printf("[ROM-TO-VRAM] ⚠️ LDIR detectado: PC:0x%04X | ROM:0x%04X -> VRAM:0x%04X | Length:%d | Bank:%d\n",
                       original_pc, hl_val, de_val, bc_val, mmu_->get_current_rom_bank());
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0297: Monitor [STATE-CHANGE] - Cambios de Estado del Juego ---
    // Detecta cambios de estado que podrían indicar transiciones a nuevas pantallas
    // o fases del juego donde se cargarían tiles.
    static uint16_t last_pc_range = 0xFFFF;
    static int state_change_count = 0;
    
    // Detectar saltos grandes (posibles cambios de pantalla/fase)
    if (op == 0xC3 || op == 0xCD) {  // JP nn o CALL nn
        uint16_t jump_target = mmu_->read(original_pc + 1) | 
                              (static_cast<uint16_t>(mmu_->read(original_pc + 2)) << 8);
        
        // Detectar saltos grandes (más de 0x1000 bytes)
        uint16_t jump_distance = (jump_target > original_pc) ? 
                                 (jump_target - original_pc) : (original_pc - jump_target);
        
        if (jump_distance > 0x1000) {
            state_change_count++;
            if (state_change_count < 50) {
                printf("[STATE-CHANGE] Salto grande detectado: PC:0x%04X -> 0x%04X (distancia: 0x%04X) | Bank:%d\n",
                       original_pc, jump_target, jump_distance, mmu_->get_current_rom_bank());
            }
        }
    }
    
    // Detectar cambios significativos en registros que podrían indicar cambio de fase
    static uint16_t last_hl_significant = 0x0000;
    uint16_t current_hl = regs_->get_hl();
    uint16_t hl_diff = (current_hl > last_hl_significant) ? 
                       (current_hl - last_hl_significant) : (last_hl_significant - current_hl);
    
    if (hl_diff > 0x1000) {  // Cambio grande en HL
        static int hl_change_count = 0;
        if (hl_change_count < 30) {
            printf("[STATE-CHANGE] Cambio grande en HL: 0x%04X -> 0x%04X | PC:0x%04X\n",
                   last_hl_significant, current_hl, original_pc);
            hl_change_count++;
        }
        last_hl_significant = current_hl;
    }
    
    // --- Step 0297: Monitor [SCREEN-TRANSITION] - Transiciones de Pantalla ---
    // Detecta patrones que indican transiciones de pantalla, que podrían
    // ser momentos donde se cargan nuevos tiles.
    static uint8_t last_scx = 0xFF;
    static uint8_t last_scy = 0xFF;
    static int screen_transition_count = 0;
    static int scx_scy_check_counter = 0;
    
    scx_scy_check_counter++;
    if (scx_scy_check_counter >= 1000) {  // Verificar cada 1000 instrucciones
        scx_scy_check_counter = 0;
        
        uint8_t current_scx = mmu_->read(0xFF43);
        uint8_t current_scy = mmu_->read(0xFF42);
        
        if (current_scx != last_scx || current_scy != last_scy) {
            screen_transition_count++;
            if (screen_transition_count < 20) {
                printf("[SCREEN-TRANSITION] Cambio en Scroll: SCX %02X->%02X SCY %02X->%02X | PC:0x%04X\n",
                       last_scx, current_scx, last_scy, current_scy, original_pc);
            }
            last_scx = current_scx;
            last_scy = current_scy;
        }
    }
    
    // --- Step 0285: Sniper de Ejecución del Handler (MOVIDO AL INICIO) ---
    // Este monitor se ejecuta ANTES de cualquier early return para asegurar
    // que capturamos todas las ejecuciones del handler, incluso cuando hay interrupciones
    // que causan retornos anticipados. Usa original_pc para leer el opcode.
    // --- Step 0287: Refactorizado de static a miembros de clase para aislar tests ---
    
    // Activar flag al entrar en el vector
    if (original_pc == 0x0040) {
        in_vblank_handler_ = true;
        vblank_handler_steps_ = 0;
    }
    
    // Rastrear instrucciones dentro del handler
    // --- Step 0286: Aumentado límite a 500 instrucciones para capturar flujo completo ---
    // --- Step 0287: Filtrar bucle de retardo en HRAM (0xFF86-0xFF87) para reducir ruido ---
    if (in_vblank_handler_ && vblank_handler_steps_ < 500) {
        uint8_t op = mmu_->read(original_pc);
        
        // Filtrar el bucle de retardo DEC A / JR NZ en HRAM para no saturar logs
        // Este bucle es común en handlers de V-Blank y no aporta información útil
        if (original_pc < 0xFF86 || original_pc > 0xFF87) {
            printf("[HANDLER-EXEC] PC:0x%04X OP:0x%02X | A:0x%02X HL:0x%04X | IME:%d\n",
                   original_pc, op, regs_->a, regs_->get_hl(), ime_ ? 1 : 0);
        }
        vblank_handler_steps_++;
        
        // --- Step 0286: Detección de RET (0xC9) además de RETI (0xD9) ---
        // Algunos handlers pueden terminar con RET sin habilitar IME, lo cual es un bug
        // pero debemos detectarlo para entender el flujo completo del handler
        if (op == 0xD9) {
            printf("[HANDLER-EXIT] RETI detectado en PC:0x%04X. Fin del rastreo del handler.\n", original_pc);
            in_vblank_handler_ = false;
        } else if (op == 0xC9) {
            printf("[HANDLER-EXIT] RET detectado en PC:0x%04X (SIN habilitar IME). Fin del rastreo del handler.\n", original_pc);
            in_vblank_handler_ = false;
        }
    }
    // -----------------------------------------
    
    // --- Step 0383: Trazado de Bucle de Espera (Bank 28, PC 0x614D-0x6153) ---
    // Instrumentación exhaustiva del bucle de polling para identificar qué registro/condición
    // está esperando el juego y por qué no avanza. Clean Room: basado en Pan Docs (polling loops).
    // El objetivo es capturar exactamente qué instrucciones se ejecutan y qué accesos a MMIO realiza.
    uint16_t current_rom_bank = mmu_->get_current_rom_bank();
    
    // Detectar entrada en el bucle (Bank 28 + rango de PC)
    if (current_rom_bank == 28 && original_pc >= 0x614D && original_pc <= 0x6153) {
        // Activar trazado la primera vez que detectamos el loop
        if (!wait_loop_detected_) {
            wait_loop_detected_ = true;
            wait_loop_trace_active_ = true;
            wait_loop_trace_count_ = 0;
            printf("[WAIT-LOOP] ===== BUCLE DE ESPERA DETECTADO EN BANK 28, PC 0x%04X =====\n", original_pc);
            printf("[WAIT-LOOP] Comenzando trazado limitado (200 iteraciones)...\n");
        }
        
        // Loguear detalles de cada iteración (limitado a 200)
        if (wait_loop_trace_active_ && wait_loop_trace_count_ < 200) {
            uint8_t opcode = mmu_->read(original_pc);
            uint8_t next_byte1 = mmu_->read((original_pc + 1) & 0xFFFF);
            uint8_t next_byte2 = mmu_->read((original_pc + 2) & 0xFFFF);
            
            printf("[WAIT-LOOP] Iter:%d PC:0x%04X OP:0x%02X %02X %02X | A:0x%02X F:0x%02X HL:0x%04X | IME:%d IE:0x%02X IF:0x%02X\n",
                   wait_loop_trace_count_,
                   original_pc, opcode, next_byte1, next_byte2,
                   regs_->a, regs_->f, regs_->get_hl(),
                   ime_ ? 1 : 0,
                   mmu_->read(0xFFFF),  // IE
                   mmu_->read(0xFF0F)); // IF
            
            wait_loop_trace_count_++;
            
            // Desactivar trazado después de 200 iteraciones
            if (wait_loop_trace_count_ >= 200) {
                wait_loop_trace_active_ = false;
                printf("[WAIT-LOOP] ===== FIN DEL TRAZADO (límite alcanzado) =====\n");
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0293: Monitor [PC-TRACE] - Rastreo de Ejecución Post-Limpieza ---
    // Rastrea la ejecución después de que la rutina de limpieza termina (después de PC:0x36F0)
    // para ver qué código se ejecuta a continuación y si hay código que debería cargar tiles.
    // Activar rastreo cuando salimos de la zona de limpieza
    if (original_pc >= 0x36E0 && original_pc <= 0x36F0) {
        // Estamos en la rutina de limpieza
        in_post_cleanup_trace_ = true;
        post_cleanup_trace_count_ = 0;
    } else if (in_post_cleanup_trace_) {
        // Rastrear las siguientes 500 instrucciones después de la limpieza
        if (post_cleanup_trace_count_ < 500) {
            uint8_t op = mmu_->read(original_pc);
            uint8_t next_byte1 = mmu_->read(original_pc + 1);
            uint8_t next_byte2 = mmu_->read(original_pc + 2);
            
            printf("[PC-TRACE] PC:0x%04X OP:0x%02X %02X %02X | A:0x%02X BC:0x%04X DE:0x%04X HL:0x%04X | SP:0x%04X Bank:%d\n",
                   original_pc, op, next_byte1, next_byte2,
                   regs_->a, regs_->get_bc(), regs_->get_de(), regs_->get_hl(),
                   regs_->sp, mmu_->get_current_rom_bank());
            
            post_cleanup_trace_count_++;
            
            // Detectar posibles cargas de tiles (escrituras a VRAM)
            // Esto se detectará también por [TILE-LOAD-EXTENDED], pero aquí lo marcamos
            if (op == 0x22 || op == 0x32) {  // LD (HL+), A o LD (HL-), A
                uint16_t hl_val = regs_->get_hl();
                if (hl_val >= 0x8000 && hl_val <= 0x97FF) {
                    printf("[PC-TRACE] ⚠️ POSIBLE CARGA DE TILE: LD (HL), A con HL=0x%04X\n", hl_val);
                }
            }
            
            // Desactivar si detectamos un salto muy lejos o retorno
            if (op == 0xC9 || op == 0xC3 || op == 0x18) {  // RET, JP, JR
                if (post_cleanup_trace_count_ > 50) {  // Ya rastreamos suficiente
                    in_post_cleanup_trace_ = false;
                }
            }
        } else {
            in_post_cleanup_trace_ = false;
        }
    }
    // -----------------------------------------
    
    // --- Step 0293: Monitor [REG-TRACE] - Rastreo de Registros Críticos ---
    // Rastrea cambios en registros críticos (AF, BC, DE, HL, SP) y flags después de la limpieza
    // para identificar si hay condiciones que impiden la carga de tiles.
    if (original_pc >= 0x36E0 && original_pc <= 0x36F0) {
        reg_trace_active_ = true;
        last_af_ = regs_->get_af();
        last_bc_ = regs_->get_bc();
        last_de_ = regs_->get_de();
        last_hl_ = regs_->get_hl();
        reg_trace_count_ = 0;
    } else if (reg_trace_active_ && original_pc > 0x36F0) {
        // Solo rastrear cambios significativos
        uint16_t current_af = regs_->get_af();
        uint16_t current_bc = regs_->get_bc();
        uint16_t current_de = regs_->get_de();
        uint16_t current_hl = regs_->get_hl();
        
        bool changed = false;
        if (abs((int16_t)(current_af - last_af_)) > 0x100) changed = true;
        if (abs((int16_t)(current_bc - last_bc_)) > 0x100) changed = true;
        if (abs((int16_t)(current_de - last_de_)) > 0x100) changed = true;
        if (abs((int16_t)(current_hl - last_hl_)) > 0x100) changed = true;
        
        if (changed) {
            if (reg_trace_count_ < 100) {
                printf("[REG-TRACE] PC:0x%04X | AF:%04X BC:%04X DE:%04X HL:%04X SP:%04X | Z:%d N:%d H:%d C:%d\n",
                       original_pc, current_af, current_bc, current_de, current_hl, regs_->sp,
                       regs_->get_flag_z() ? 1 : 0, regs_->get_flag_n() ? 1 : 0,
                       regs_->get_flag_h() ? 1 : 0, regs_->get_flag_c() ? 1 : 0);
                reg_trace_count_++;
                
                last_af_ = current_af;
                last_bc_ = current_bc;
                last_de_ = current_de;
                last_hl_ = current_hl;
            } else {
                reg_trace_active_ = false;
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0293: Monitor [JUMP-TRACE] - Rastreo de Saltos y Llamadas ---
    // Rastrea saltos, llamadas y retornos después de la limpieza para ver si el juego
    // salta a código que debería cargar tiles pero no lo hace.
    // Activar después de la limpieza
    if (original_pc >= 0x36E0 && original_pc <= 0x36F0) {
        jump_trace_active_ = true;
        jump_trace_count_ = 0;
    }
    
    if (jump_trace_active_ && jump_trace_count_ < 200) {
        uint8_t op = mmu_->read(original_pc);
        
        // Detectar opcodes de salto
        if (op == 0xC3 || op == 0xC2 || op == 0xCA || op == 0xD2 || op == 0xDA ||  // JP variants
            op == 0xE9 || op == 0x18 || op == 0x20 || op == 0x28 || op == 0x30 || op == 0x38 ||  // JP HL, JR variants
            op == 0xCD || op == 0xC4 || op == 0xCC || op == 0xD4 || op == 0xDC ||  // CALL variants
            op == 0xC9 || op == 0xC0 || op == 0xC8 || op == 0xD0 || op == 0xD8) {  // RET variants
            
            uint16_t jump_target = 0x0000;
            if (op == 0xC3 || op == 0xCD || op == 0xC2 || op == 0xCA || op == 0xD2 || op == 0xDA ||
                op == 0xC4 || op == 0xCC || op == 0xD4 || op == 0xDC) {
                // JP/CALL nn - 16-bit immediate
                jump_target = mmu_->read(original_pc + 1) | (static_cast<uint16_t>(mmu_->read(original_pc + 2)) << 8);
            } else if (op == 0xE9) {
                // JP HL
                jump_target = regs_->get_hl();
            } else if (op == 0x18 || op == 0x20 || op == 0x28 || op == 0x30 || op == 0x38) {
                // JR e - 8-bit signed relative
                int8_t offset = static_cast<int8_t>(mmu_->read(original_pc + 1));
                jump_target = original_pc + 2 + offset;
            }
            
            printf("[JUMP-TRACE] PC:0x%04X OP:0x%02X -> 0x%04X | Bank:%d | SP:0x%04X\n",
                   original_pc, op, jump_target, mmu_->get_current_rom_bank(), regs_->sp);
            jump_trace_count_++;
        }
    }
    // -----------------------------------------
    
    // --- Step 0293: Monitor [HARDWARE-STATE] - Estado de Hardware Crítico ---
    // Rastrea el estado de registros de hardware críticos (LCDC, BGP, IE, IF, IME) después
    // de la limpieza para ver si hay condiciones que impiden la carga.
    if (original_pc >= 0x36E0 && original_pc <= 0x36F0) {
        hw_state_trace_active_ = true;
        hw_state_samples_ = 0;
        hw_state_sample_counter_ = 0;
    }
    
    if (hw_state_trace_active_ && hw_state_samples_ < 100) {
        // Muestrear cada 10 instrucciones aproximadamente
        hw_state_sample_counter_++;
        if (hw_state_sample_counter_ >= 10) {
            hw_state_sample_counter_ = 0;
            
            uint8_t lcdc = mmu_->read(0xFF40);
            uint8_t bgp = mmu_->read(0xFF47);
            uint8_t ie = mmu_->read(0xFFFF);
            uint8_t if_reg = mmu_->read(0xFF0F);
            bool ime = get_ime();
            
            printf("[HARDWARE-STATE] PC:0x%04X | LCDC:0x%02X BGP:0x%02X IE:0x%02X IF:0x%02X IME:%d | LY:%d\n",
                   original_pc, lcdc, bgp, ie, if_reg, ime ? 1 : 0, mmu_->read(0xFF44));
            
            hw_state_samples_++;
            
            if (hw_state_samples_ >= 100) {
                hw_state_trace_active_ = false;
            }
        }
    }
    // -----------------------------------------
    
    // --- Step 0277: Monitor de Decremento y Salida de Bucle - ANTES de interrupciones ---
    // Capturamos el PC ANTES de procesar interrupciones para poder ver el estado del bucle
    // incluso cuando hay interrupciones que interrumpen la ejecución
    
    // Trigger de salida del bucle (cuando el PC sale del rango 614A-6155)
    // --- Step 0287: Refactorizado de static a miembros de clase para aislar tests ---
    static uint16_t last_pc_in_loop = 0;  // Este puede quedarse static porque solo se usa en este scope
    
    if (last_pc_in_loop >= 0x614A && last_pc_in_loop <= 0x6155 && 
        !(regs_->pc >= 0x614A && regs_->pc <= 0x6155)) {
        printf("[SNIPER-EXIT] ¡LIBERTAD! El bucle de retardo ha terminado en PC:0x%04X. DE:0x%04X\n", 
               regs_->pc, regs_->get_de());
        // Step 0278: Activar trail post-retardo cuando se detecta la salida del bucle
        // --- Step 0287: Usar miembros de clase en lugar de static ---
        post_delay_trace_active_ = true;
        post_delay_count_ = 0;
        printf("[SNIPER-AWAKE] ¡Saliendo del bucle de retardo! Iniciando rastreo de flujo...\n");
    }
    if (regs_->pc >= 0x614A && regs_->pc <= 0x6155) {
        last_pc_in_loop = regs_->pc;
    }
    
    // Step 0278: Trail de ejecución post-retardo (ejecutar incluso si hay interrupciones)
    // --- Step 0287: Usar miembros de clase en lugar de static ---
    if (post_delay_trace_active_ && post_delay_count_ < 200) {
        uint8_t current_op = mmu_->read(regs_->pc);  // Leer opcode del PC actual (antes del fetch)
        printf("[POST-DELAY] PC:%04X OP:%02X | A:%02X HL:%04X | IE:%02X IME:%d\n",
               regs_->pc, current_op, regs_->a, regs_->get_hl(),
               mmu_->read(0xFFFF), ime_ ? 1 : 0);
        post_delay_count_++;
    }
    // -----------------------------------------
    
    // ========== FASE 1: Manejo de Interrupciones (ANTES de cada instrucción) ==========
    // El chequeo de interrupciones ocurre antes de ejecutar la instrucción
    // Esto es crítico para la precisión del timing
    int interrupt_cycles = handle_interrupts();
    cycles_ += interrupt_cycles;
    
    // Si se procesó una interrupción, retornar los ciclos consumidos
    // (la instrucción actual no se ejecuta, la interrupción ya cambió PC)
    if (interrupt_cycles > 0) {
        return interrupt_cycles;
    }
    
    // ========== FASE 2: Gestión de HALT ==========
    // Si la CPU está en HALT, no ejecutar instrucciones
    // Consumimos 1 M-Cycle (el reloj sigue funcionando) y retornamos -1
    // para señalar "avance rápido" (el orquestador puede saltar ciclos).
    // El orquestador debe usar el flag halted_ (get_halted()) para determinar
    // cómo manejar el tiempo, pero el código de retorno -1 indica que se puede
    // avanzar rápidamente sin ejecutar instrucciones.
    if (halted_) {
        cycles_ += 1;
        return -1;  // HALT devuelve -1 para señalar avance rápido
    }
    
    // ========== FASE 3: Gestión de EI retrasado ==========
    // EI (Enable Interrupts) tiene un retraso de 1 instrucción
    // Si ime_scheduled_ es true, activar IME después de procesar esta instrucción
    // --- Step 0294: Monitor de Activación de IME ([IME-ACTIVATE]) ---
    // Rastrea cuándo IME se activa realmente después de que EI se ejecuta.
    // IME se activa después de ejecutar la siguiente instrucción (delay de 1).
    if (ime_scheduled_) {
        printf("[IME-ACTIVATE] IME activado después de delay de EI | PC:0x%04X | IE:0x%02X IF:0x%02X\n",
               regs_->pc, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
        ime_ = true;
        ime_scheduled_ = false;
    }
    
    // ========== FASE 4: Fetch-Decode-Execute ==========
    // Step 0243: Operación Silencio - Eliminado bloque del Francotirador
    // El emulador debe correr a velocidad nativa (60 FPS) sin instrumentación pesada.
    // El monitor GPS (Step 0240) proporciona suficiente información para diagnóstico.
    
    // --- Step 0247: Memory Timeline & PC Tracker ---
    // Actualizar el PC en la MMU antes de ejecutar la instrucción
    // Esto permite que la MMU registre qué instrucción provocó cada operación de memoria
    mmu_->debug_current_pc = regs_->pc;
    // -----------------------------------------
    
    // --- Step 0273: Sniper Trace - Usar PC original capturado al inicio ---
    // El original_pc ya fue capturado al inicio de step() para los monitores de diagnóstico
    bool is_critical_pc = (original_pc == 0x36E3 || original_pc == 0x6150 || original_pc == 0x6152);
    
    // --- Step 0277: Guardar PC original para instrumentación en casos específicos ---
    // Guardamos el PC original (antes del fetch) para usarlo en los casos específicos del switch
    static uint16_t saved_pc_for_instrumentation = 0;
    saved_pc_for_instrumentation = original_pc;
    // -----------------------------------------
    
    // Fetch: Leer opcode de memoria
    uint8_t opcode = fetch_byte();
    
    // --- Step 0273: Sniper Trace - Ejecutar verificación ANTES del switch ---
    // Ejecutamos la verificación aquí para capturar el estado ANTES de ejecutar la instrucción
    if (is_critical_pc) {
        static int sniper_limit = 0;
        if (sniper_limit < 50) {
            // Leer opcodes desde el PC original (donde comenzó la instrucción)
            uint8_t current_op = mmu_->read(original_pc);
            uint8_t next_op1 = mmu_->read(original_pc + 1);
            uint8_t next_op2 = mmu_->read(original_pc + 2);
            
            printf("[SNIPER] PC:%04X Bank:%d | OP: %02X %02X %02X | SP:%04X AF:%04X BC:%04X DE:%04X HL:%04X | IE:%02X IF:%02X\n",
                   original_pc, mmu_->get_current_rom_bank(),
                   current_op, next_op1, next_op2,
                   regs_->sp, regs_->get_af(), regs_->get_bc(), regs_->get_de(), regs_->get_hl(),
                   mmu_->read(0xFFFF), mmu_->read(0xFF0F));
            sniper_limit++;
        }
    }
    // -----------------------------------------
    
    // --- Step 0275: Sniper Trace de la Zona de Muerte (1F54-1F60) ---
    // Queremos ver la secuencia exacta de opcodes que acompañan al apagado de interrupciones.
    // Esta zona es crítica porque contiene DI (0xF3) y la escritura a IE (0xFFFF).
    // Usamos original_pc porque es el PC antes de ejecutar la instrucción.
    if (original_pc >= 0x1F50 && original_pc <= 0x1F65) {
        static int init_trace_count = 0;
        if (init_trace_count < 100) {
            uint8_t current_op = mmu_->read(original_pc);
            uint8_t next_op1 = mmu_->read((original_pc + 1) & 0xFFFF);
            uint8_t next_op2 = mmu_->read((original_pc + 2) & 0xFFFF);
            printf("[SNIPER-INIT] PC:%04X OP:%02X %02X %02X | AF:%04X BC:%04X DE:%04X HL:%04X | IME:%d IE:%02X IF:%02X\n",
                   original_pc, current_op, next_op1, next_op2,
                   regs_->get_af(), regs_->get_bc(), regs_->get_de(), regs_->get_hl(),
                   ime_ ? 1 : 0, mmu_->read(0xFFFF), mmu_->read(0xFF0F));
            init_trace_count++;
        }
    }
    // -----------------------------------------

    // Decode/Execute: Switch optimizado por el compilador
    switch (opcode) {
        case 0x00:  // NOP (No Operation)
            // NOP no hace nada, solo consume 1 M-Cycle
            cycles_ += 1;
            return 1;

        // --- Step 0231: FIX DESALINEAMIENTO ---
        // LD (nn), SP - Guarda el Stack Pointer en la dirección nn
        // Esta instrucción es de 3 bytes. Si falta, la CPU ejecuta los datos
        // de la dirección como instrucciones, corrompiendo el flujo.
        // Fuente: Pan Docs - LD (nn), SP: 5 M-Cycles
        case 0x08:  // LD (nn), SP
            {
                // Step 0243: Operación Silencio - Eliminado marcador radiactivo
                // El código está limpio y funcionando. No necesitamos más instrumentación.
                
                uint16_t addr = fetch_word();  // Consume 2 bytes más (nn en Little-Endian)
                // Escribe SP en formato Little Endian (low byte primero, high byte segundo)
                mmu_->write(addr, regs_->sp & 0xFF);         // Low byte
                mmu_->write(addr + 1, (regs_->sp >> 8) & 0xFF);  // High byte
                cycles_ += 5;  // LD (nn), SP consume 5 M-Cycles
                return 5;
            }
        // -------------------------------------

        // ========== Loads 8-bit (LD r, r' y LD r, n) ==========
        // Bloque 0x40-0x7F: LD r, r'
        // Estructura del opcode: 01DDDSSS
        // DDD (bits 3-5): destino, SSS (bits 0-2): origen
        // 0x76 es HALT (ya implementado), el resto son LD
        
        case 0x40: case 0x41: case 0x42: case 0x43: case 0x44: case 0x45: case 0x47:  // LD B, r
        case 0x48: case 0x49: case 0x4A: case 0x4B: case 0x4C: case 0x4D: case 0x4F:  // LD C, r
        case 0x50: case 0x51: case 0x52: case 0x53: case 0x54: case 0x55: case 0x57:  // LD D, r
        case 0x58: case 0x59: case 0x5A: case 0x5B: case 0x5C: case 0x5D: case 0x5F:  // LD E, r
        case 0x60: case 0x61: case 0x62: case 0x63: case 0x64: case 0x65: case 0x67:  // LD H, r
        case 0x68: case 0x69: case 0x6A: case 0x6B: case 0x6C: case 0x6D: case 0x6F:  // LD L, r
        case 0x70: case 0x71: case 0x72: case 0x73: case 0x74: case 0x75: case 0x77:  // LD (HL), r
        case 0x78: case 0x79: case 0x7A: case 0x7B: case 0x7C: case 0x7D: case 0x7E: case 0x7F:  // LD A, r (0x7E = LD A, (HL))
            {
                // Extraer códigos de destino y origen del opcode
                uint8_t dest_code = (opcode >> 3) & 0x07;  // Bits 3-5
                uint8_t src_code = opcode & 0x07;          // Bits 0-2
                
                // Ejecutar LD r, r'
                ld_r_r(dest_code, src_code);
                
                // Timing: LD r, r consume 1 M-Cycle
                // LD (HL), r consume 2 M-Cycles (destino es memoria)
                // LD r, (HL) consume 2 M-Cycles (origen es memoria)
                int cycles = (dest_code == 6 || src_code == 6) ? 2 : 1;  // (HL) es código 6
                cycles_ += cycles;
                return cycles;
            }

        // LD r, n (Load register with immediate 8-bit value)
        case 0x02:  // LD (BC), A
            {
                uint16_t addr = regs_->get_bc();
                mmu_->write(addr, regs_->a);
                cycles_ += 2;  // LD (BC), A consume 2 M-Cycles
                return 2;
            }

        case 0x12:  // LD (DE), A
            {
                uint16_t addr = regs_->get_de();
                mmu_->write(addr, regs_->a);
                cycles_ += 2;  // LD (DE), A consume 2 M-Cycles
                return 2;
            }

        case 0x0A:  // LD A, (BC)
            {
                uint16_t addr = regs_->get_bc();
                regs_->a = mmu_->read(addr);
                cycles_ += 2;  // LD A, (BC) consume 2 M-Cycles
                return 2;
            }

        case 0x1A:  // LD A, (DE)
            {
                uint16_t addr = regs_->get_de();
                regs_->a = mmu_->read(addr);
                cycles_ += 2;  // LD A, (DE) consume 2 M-Cycles
                return 2;
            }

        case 0x06:  // LD B, d8
            {
                uint8_t value = fetch_byte();
                regs_->b = value;
                cycles_ += 2;  // LD B, d8 consume 2 M-Cycles
                return 2;
            }
        
        case 0x0E:  // LD C, d8
            {
                uint8_t value = fetch_byte();
                regs_->c = value;
                cycles_ += 2;
                return 2;
            }
        
        case 0x16:  // LD D, d8
            {
                uint8_t value = fetch_byte();
                regs_->d = value;
                cycles_ += 2;
                return 2;
            }
        
        case 0x1E:  // LD E, d8
            {
                uint8_t value = fetch_byte();
                regs_->e = value;
                cycles_ += 2;
                return 2;
            }
        
        case 0x26:  // LD H, d8
            {
                uint8_t value = fetch_byte();
                regs_->h = value;
                cycles_ += 2;
                return 2;
            }
        
        case 0x27:  // DAA (Decimal Adjust Accumulator)
            // Ajusta el registro A para que sea un número BCD válido tras una suma/resta
            // Esta es la instrucción más compleja de emular correctamente
            // Fuente: Pan Docs - DAA: 1 M-Cycle (4 cycles)
            {
                uint16_t a = regs_->a;
                bool n = regs_->get_flag_n();
                bool h = regs_->get_flag_h();
                bool c = regs_->get_flag_c();
                
                if (!n) {  // Después de suma
                    if (c || a > 0x99) {
                        a += 0x60;
                        regs_->set_flag_c(true);
                    }
                    if (h || (a & 0x0F) > 0x09) {
                        a += 0x06;
                    }
                } else {  // Después de resta
                    if (c) {
                        a -= 0x60;
                    }
                    if (h) {
                        a -= 0x06;
                    }
                }
                
                regs_->a = static_cast<uint8_t>(a);
                regs_->set_flag_z(regs_->a == 0);
                regs_->set_flag_h(false);  // H siempre se limpia en DAA
                // C se mantiene o se setea si hubo overflow en el ajuste (ya se actualizó arriba)
                
                cycles_ += 1;  // DAA consume 1 M-Cycle
                return 1;
            }
        
        case 0x2E:  // LD L, d8
            {
                uint8_t value = fetch_byte();
                regs_->l = value;
                cycles_ += 2;
                return 2;
            }
        
        case 0x2F:  // CPL (Complement A)
            // Invierte todos los bits del registro A (A = ~A)
            // Fuente: Pan Docs - CPL: 1 M-Cycle (4 cycles)
            {
                regs_->a = ~regs_->a;
                // Flags: Z (preservado), N=1, H=1, C (preservado)
                regs_->set_flag_n(true);
                regs_->set_flag_h(true);
                // Z y C no se modifican
                cycles_ += 1;  // CPL consume 1 M-Cycle
                return 1;
            }

        case 0x3E:  // LD A, d8 (Load A with immediate 8-bit value)
            // Lee el siguiente byte (d8) y lo guarda en el registro A
            {
                uint8_t value = fetch_byte();
                regs_->a = value;
                cycles_ += 2;  // LD A, d8 consume 2 M-Cycles
                return 2;
            }
        
        case 0x3F:  // CCF (Complement Carry Flag)
            // Invierte el flag Carry (C = !C)
            // Fuente: Pan Docs - CCF: 1 M-Cycle (4 cycles)
            {
                // Flags: Z (preservado), N=0, H=0, C=!C
                regs_->set_flag_n(false);
                regs_->set_flag_h(false);
                regs_->set_flag_c(!regs_->get_flag_c());
                // Z no se modifica
                cycles_ += 1;  // CCF consume 1 M-Cycle
                return 1;
            }

        // LD (HL), n (Load memory at HL with immediate 8-bit value)
        case 0x36:  // LD (HL), d8
            {
                uint8_t value = fetch_byte();
                uint16_t addr = regs_->get_hl();
                mmu_->write(addr, value);
                cycles_ += 3;  // LD (HL), d8 consume 3 M-Cycles
                return 3;
            }
        
        case 0x37:  // SCF (Set Carry Flag)
            // Activa el flag Carry (C = 1)
            // Fuente: Pan Docs - SCF: 1 M-Cycle (4 cycles)
            {
                // Flags: Z (preservado), N=0, H=0, C=1
                regs_->set_flag_n(false);
                regs_->set_flag_h(false);
                regs_->set_flag_c(true);
                // Z no se modifica
                cycles_ += 1;  // SCF consume 1 M-Cycle
                return 1;
            }

        // ========== Loads Indirectas con Auto-incremento/Decremento ==========
        case 0x22:  // LDI (HL), A (o LD (HL+), A)
            // Escribe A en la dirección apuntada por HL y luego incrementa HL
            // Fuente: Pan Docs - LDI (HL), A: 2 M-Cycles
            {
                uint16_t addr = regs_->get_hl();
                mmu_->write(addr, regs_->a);
                regs_->set_hl((addr + 1) & 0xFFFF);  // Incrementar HL con wrap-around
                cycles_ += 2;
                return 2;
            }

        case 0x32:  // LDD (HL), A (o LD (HL-), A)
            // Escribe A en la dirección apuntada por HL y luego decrementa HL
            // Fuente: Pan Docs - LDD (HL), A: 2 M-Cycles
            {
                uint16_t addr = regs_->get_hl();
                mmu_->write(addr, regs_->a);
                regs_->set_hl((addr - 1) & 0xFFFF);  // Decrementar HL con wrap-around
                cycles_ += 2;
                return 2;
            }

        case 0x2A:  // LDI A, (HL) (o LD A, (HL+))
            // Lee de (HL) y luego incrementa HL
            {
                uint16_t addr = regs_->get_hl();
                regs_->a = mmu_->read(addr);
                regs_->set_hl((addr + 1) & 0xFFFF);
                cycles_ += 2;  // LDI A, (HL) consume 2 M-Cycles
                return 2;
            }

        case 0x3A:  // LDD A, (HL) (o LD A, (HL-))
            // Lee de (HL) y luego decrementa HL
            {
                uint16_t addr = regs_->get_hl();
                regs_->a = mmu_->read(addr);
                regs_->set_hl((addr - 1) & 0xFFFF);
                cycles_ += 2;  // LDD A, (HL) consume 2 M-Cycles
                return 2;
            }

        // Nota: LD (HL), A (0x77) está implementado en el bloque LD r, r' (0x70-0x77)

        // ========== Loads 16-bit (LD rr, nn) ==========
        case 0x01:  // LD BC, d16
            {
                uint16_t value = fetch_word();
                regs_->set_bc(value);
                cycles_ += 3;  // LD BC, d16 consume 3 M-Cycles
                return 3;
            }
        
        case 0x11:  // LD DE, d16
            {
                uint16_t value = fetch_word();
                regs_->set_de(value);
                
                // --- Step 0277: Capturar carga inicial de DE en PC:0x614A ---
                // saved_pc_for_instrumentation contiene el PC original (antes del fetch)
                if (saved_pc_for_instrumentation == 0x614A) {
                    // El valor se carga desde memoria en formato little-endian
                    // 0x614A: opcode 0x11
                    // 0x614B: LSB del valor
                    // 0x614C: MSB del valor
                    printf("[SNIPER-LOAD] PC:0x614A | Cargando DE con valor: 0x%04X (desde memoria 0x614B:0x%02X 0x614C:0x%02X)\n",
                           value, mmu_->read(0x614B), mmu_->read(0x614C));
                }
                // -----------------------------------------
                
                cycles_ += 3;
                return 3;
            }
        
        case 0x21:  // LD HL, d16
            {
                uint16_t value = fetch_word();
                regs_->set_hl(value);
                cycles_ += 3;
                return 3;
            }
        
        case 0x31:  // LD SP, d16
            {
                uint16_t value = fetch_word();
                regs_->sp = value;
                cycles_ += 3;
                return 3;
            }

        // ========== Aritmética 16-bit (INC/DEC rr) ==========
        case 0x03:  // INC BC
            {
                inc_16bit(0);  // 0 = BC
                cycles_ += 2;  // INC BC consume 2 M-Cycles
                return 2;
            }
        
        case 0x0B:  // DEC BC
            {
                dec_16bit(0);  // 0 = BC
                cycles_ += 2;
                return 2;
            }
        
        case 0x13:  // INC DE
            {
                inc_16bit(1);  // 1 = DE
                cycles_ += 2;
                return 2;
            }
        
        case 0x1B:  // DEC DE
            {
                dec_16bit(1);  // 1 = DE
                
                // --- Step 0277: Monitorizar decremento cada 1000 iteraciones en PC:0x6150 ---
                // saved_pc_for_instrumentation contiene el PC original (antes del fetch)
                if (saved_pc_for_instrumentation == 0x6150) {
                    static uint32_t loop_counter = 0;
                    loop_counter++;
                    if (loop_counter % 1000 == 0) {
                        printf("[SNIPER-DELAY] Iteración:%u | DE:0x%04X | LY:%d DIV:0x%02X\n",
                               loop_counter, regs_->get_de(), 
                               mmu_->read(0xFF44), mmu_->read(0xFF04));
                    }
                }
                // -----------------------------------------
                
                cycles_ += 2;
                return 2;
            }
        
        case 0x23:  // INC HL
            {
                inc_16bit(2);  // 2 = HL
                cycles_ += 2;
                return 2;
            }
        
        case 0x2B:  // DEC HL
            {
                dec_16bit(2);  // 2 = HL
                cycles_ += 2;
                return 2;
            }
        
        case 0x33:  // INC SP
            {
                inc_16bit(3);  // 3 = SP
                cycles_ += 2;
                return 2;
            }
        
        case 0x3B:  // DEC SP
            {
                dec_16bit(3);  // 3 = SP
                cycles_ += 2;
                return 2;
            }

        // ========== ADD HL, rr ==========
        case 0x09:  // ADD HL, BC
            {
                uint16_t bc = regs_->get_bc();
                add_hl(bc);
                cycles_ += 2;  // ADD HL, BC consume 2 M-Cycles
                return 2;
            }
        
        case 0x19:  // ADD HL, DE
            {
                uint16_t de = regs_->get_de();
                add_hl(de);
                cycles_ += 2;
                return 2;
            }
        
        case 0x29:  // ADD HL, HL
            {
                uint16_t hl = regs_->get_hl();
                add_hl(hl);
                cycles_ += 2;
                return 2;
            }
        
        case 0x39:  // ADD HL, SP
            {
                add_hl(regs_->sp);
                cycles_ += 2;
                return 2;
            }

        // ========== Aritmética 8-bit (INC/DEC r) ==========
        // IMPORTANTE: INC y DEC NO modifican el flag C (preservado)
        
        case 0x04:  // INC B
            {
                regs_->b = alu_inc(regs_->b);
                cycles_ += 1;
                return 1;
            }
        
        case 0x0C:  // INC C
            {
                regs_->c = alu_inc(regs_->c);
                cycles_ += 1;
                return 1;
            }
        
        case 0x14:  // INC D
            {
                regs_->d = alu_inc(regs_->d);
                cycles_ += 1;
                return 1;
            }
        
        case 0x1C:  // INC E
            {
                regs_->e = alu_inc(regs_->e);
                cycles_ += 1;
                return 1;
            }
        
        case 0x24:  // INC H
            {
                regs_->h = alu_inc(regs_->h);
                cycles_ += 1;
                return 1;
            }
        
        case 0x2C:  // INC L
            {
                regs_->l = alu_inc(regs_->l);
                cycles_ += 1;
                return 1;
            }
        
        case 0x3C:  // INC A
            {
                regs_->a = alu_inc(regs_->a);
                cycles_ += 1;
                return 1;
            }
        
        case 0x34:  // INC (HL)
            {
                uint16_t addr = regs_->get_hl();
                uint8_t value = mmu_->read(addr);
                uint8_t result = alu_inc(value);
                mmu_->write(addr, result);
                cycles_ += 3;  // INC (HL) consume 3 M-Cycles (lectura + escritura)
                return 3;
            }

        case 0x05:  // DEC B
            {
                regs_->b = alu_dec(regs_->b);
                cycles_ += 1;
                return 1;
            }
        
        case 0x0D:  // DEC C
            {
                regs_->c = alu_dec(regs_->c);
                cycles_ += 1;
                return 1;
            }
        
        case 0x15:  // DEC D
            {
                regs_->d = alu_dec(regs_->d);
                cycles_ += 1;
                return 1;
            }
        
        case 0x1D:  // DEC E
            {
                regs_->e = alu_dec(regs_->e);
                cycles_ += 1;
                return 1;
            }
        
        case 0x25:  // DEC H
            {
                regs_->h = alu_dec(regs_->h);
                cycles_ += 1;
                return 1;
            }
        
        case 0x2D:  // DEC L
            {
                regs_->l = alu_dec(regs_->l);
                cycles_ += 1;
                return 1;
            }
        
        case 0x3D:  // DEC A
            {
                regs_->a = alu_dec(regs_->a);
                cycles_ += 1;
                return 1;
            }
        
        case 0x35:  // DEC (HL)
            {
                uint16_t addr = regs_->get_hl();
                uint8_t value = mmu_->read(addr);
                uint8_t result = alu_dec(value);
                mmu_->write(addr, result);
                cycles_ += 3;  // DEC (HL) consume 3 M-Cycles (lectura + escritura)
                return 3;
            }

        case 0xC6:  // ADD A, d8 (Add immediate 8-bit value to A)
            // Suma el siguiente byte (d8) a A
            {
                uint8_t value = fetch_byte();
                alu_add(value);
                cycles_ += 2;  // ADD A, d8 consume 2 M-Cycles
                return 2;
            }

        case 0xD6:  // SUB d8 (Subtract immediate 8-bit value from A)
            // Resta el siguiente byte (d8) de A
            {
                uint8_t value = fetch_byte();
                alu_sub(value);
                cycles_ += 2;  // SUB d8 consume 2 M-Cycles
                return 2;
            }

        case 0xAF:  // XOR A (XOR A with A - optimización para A=0)
            // XOR A con A siempre da 0 (optimización común)
            // Equivale a: A = A ^ A = 0
            {
                alu_xor(regs_->a);  // XOR A con A mismo
                cycles_ += 1;  // XOR A consume 1 M-Cycle
                return 1;
            }

        // ========== Bloque ALU Completo (0x80-0xBF) ==========
        // Este bloque contiene todas las operaciones aritméticas y lógicas
        // entre A y registros/memoria. Sigue un patrón regular:
        // - Bits 0-2: Registro (0=B, 1=C, 2=D, 3=E, 4=H, 5=L, 6=(HL), 7=A)
        // - Bits 3-5: Operación (0=ADD, 1=ADC, 2=SUB, 3=SBC, 4=AND, 5=XOR, 6=OR, 7=CP)
        
        // ADD A, r (0x80-0x87)
        case 0x80:  // ADD A, B
            {
                alu_add(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0x81:  // ADD A, C
            {
                alu_add(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0x82:  // ADD A, D
            {
                alu_add(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0x83:  // ADD A, E
            {
                alu_add(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0x84:  // ADD A, H
            {
                alu_add(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0x85:  // ADD A, L
            {
                alu_add(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0x86:  // ADD A, (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_add(value);
                cycles_ += 2;  // (HL) consume 2 M-Cycles
                return 2;
            }
        case 0x87:  // ADD A, A
            {
                alu_add(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // ADC A, r (0x88-0x8F)
        case 0x88:  // ADC A, B
            {
                alu_adc(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0x89:  // ADC A, C
            {
                alu_adc(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0x8A:  // ADC A, D
            {
                alu_adc(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0x8B:  // ADC A, E
            {
                alu_adc(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0x8C:  // ADC A, H
            {
                alu_adc(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0x8D:  // ADC A, L
            {
                alu_adc(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0x8E:  // ADC A, (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_adc(value);
                cycles_ += 2;
                return 2;
            }
        case 0x8F:  // ADC A, A
            {
                alu_adc(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // SUB A, r (0x90-0x97)
        case 0x90:  // SUB B
            {
                alu_sub(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0x91:  // SUB C
            {
                alu_sub(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0x92:  // SUB D
            {
                alu_sub(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0x93:  // SUB E
            {
                alu_sub(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0x94:  // SUB H
            {
                alu_sub(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0x95:  // SUB L
            {
                alu_sub(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0x96:  // SUB (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_sub(value);
                cycles_ += 2;
                return 2;
            }
        case 0x97:  // SUB A
            {
                alu_sub(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // SBC A, r (0x98-0x9F)
        case 0x98:  // SBC A, B
            {
                alu_sbc(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0x99:  // SBC A, C
            {
                alu_sbc(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0x9A:  // SBC A, D
            {
                alu_sbc(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0x9B:  // SBC A, E
            {
                alu_sbc(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0x9C:  // SBC A, H
            {
                alu_sbc(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0x9D:  // SBC A, L
            {
                alu_sbc(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0x9E:  // SBC A, (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_sbc(value);
                cycles_ += 2;
                return 2;
            }
        case 0x9F:  // SBC A, A
            {
                alu_sbc(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // AND A, r (0xA0-0xA7)
        case 0xA0:  // AND B
            {
                alu_and(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0xA1:  // AND C
            {
                alu_and(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0xA2:  // AND D
            {
                alu_and(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0xA3:  // AND E
            {
                alu_and(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0xA4:  // AND H
            {
                alu_and(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0xA5:  // AND L
            {
                alu_and(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0xA6:  // AND (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_and(value);
                cycles_ += 2;
                return 2;
            }
        case 0xA7:  // AND A
            {
                alu_and(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // XOR A, r (0xA8-0xAF) - 0xAF ya está implementado arriba
        case 0xA8:  // XOR B
            {
                alu_xor(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0xA9:  // XOR C
            {
                alu_xor(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0xAA:  // XOR D
            {
                alu_xor(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0xAB:  // XOR E
            {
                alu_xor(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0xAC:  // XOR H
            {
                alu_xor(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0xAD:  // XOR L
            {
                alu_xor(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0xAE:  // XOR (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_xor(value);
                cycles_ += 2;
                return 2;
            }

        // OR A, r (0xB0-0xB7)
        case 0xB0:  // OR B
            {
                alu_or(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0xB1:  // OR C
            {
                alu_or(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0xB2:  // OR D
            {
                alu_or(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0xB3:  // OR E
            {
                alu_or(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0xB4:  // OR H
            {
                alu_or(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0xB5:  // OR L
            {
                alu_or(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0xB6:  // OR (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_or(value);
                cycles_ += 2;
                return 2;
            }
        case 0xB7:  // OR A
            {
                alu_or(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // CP A, r (0xB8-0xBF)
        case 0xB8:  // CP B
            {
                alu_cp(regs_->b);
                cycles_ += 1;
                return 1;
            }
        case 0xB9:  // CP C
            {
                alu_cp(regs_->c);
                cycles_ += 1;
                return 1;
            }
        case 0xBA:  // CP D
            {
                alu_cp(regs_->d);
                cycles_ += 1;
                return 1;
            }
        case 0xBB:  // CP E
            {
                alu_cp(regs_->e);
                cycles_ += 1;
                return 1;
            }
        case 0xBC:  // CP H
            {
                alu_cp(regs_->h);
                cycles_ += 1;
                return 1;
            }
        case 0xBD:  // CP L
            {
                alu_cp(regs_->l);
                cycles_ += 1;
                return 1;
            }
        case 0xBE:  // CP (HL)
            {
                uint8_t value = mmu_->read(regs_->get_hl());
                alu_cp(value);
                cycles_ += 2;
                return 2;
            }
        case 0xFE:  // CP d8 (Compare A with immediate 8-bit value)
            {
                // CP d8: Compara A con un valor inmediato de 8 bits
                // Lee el siguiente byte de memoria y lo compara con A
                // No modifica A, solo actualiza flags
                uint8_t value = fetch_byte();
                alu_cp(value);
                cycles_ += 2;  // 1 M-Cycle para opcode, 1 M-Cycle para leer d8
                return 2;
            }
        case 0xBF:  // CP A
            {
                alu_cp(regs_->a);
                cycles_ += 1;
                return 1;
            }

        // ========== Control de Flujo (Jumps) ==========
        // Agrupamos los saltos juntos para ayudar a la predicción de ramas del host

        case 0xC3:  // JP nn (Jump Absolute)
            // Salto absoluto incondicional a dirección de 16 bits
            // Lee dirección en formato Little-Endian y la asigna a PC
            // Fuente: Pan Docs - JP nn: 4 M-Cycles
            {
                uint16_t target = fetch_word();
                regs_->pc = target;
                cycles_ += 4;  // JP nn consume 4 M-Cycles
                return 4;
            }

        // ========== Saltos Absolutos Condicionales (JP cc, nn) ==========
        // Step 0269: Implementación de saltos absolutos condicionales
        
        case 0xC2:  // JP NZ, nn (Jump if Not Zero)
            // Salto absoluto condicional: salta si el flag Z está desactivado (Z=0)
            // SIEMPRE lee nn (para avanzar PC), pero solo salta si la condición es verdadera
            // Fuente: Pan Docs - JP NZ, nn: 4 M-Cycles si salta, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();  // Siempre leer nn para mantener PC alineado
                
                if (!regs_->get_flag_z()) {
                    // Condición verdadera: saltar
                    regs_->pc = target;
                    cycles_ += 4;  // JP NZ consume 4 M-Cycles si salta
                    return 4;
                } else {
                    // Condición falsa: no saltar, continuar ejecución normal
                    cycles_ += 3;  // JP NZ consume 3 M-Cycles si no salta
                    return 3;
                }
            }

        case 0xCA:  // JP Z, nn (Jump if Zero)
            // Salto absoluto condicional: salta si el flag Z está activado (Z=1)
            // Fuente: Pan Docs - JP Z, nn: 4 M-Cycles si salta, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (regs_->get_flag_z()) {
                    regs_->pc = target;
                    cycles_ += 4;
                    return 4;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xD2:  // JP NC, nn (Jump if No Carry)
            // Salto absoluto condicional: salta si el flag C está desactivado (C=0)
            // Fuente: Pan Docs - JP NC, nn: 4 M-Cycles si salta, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (!regs_->get_flag_c()) {
                    regs_->pc = target;
                    cycles_ += 4;
                    return 4;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xDA:  // JP C, nn (Jump if Carry)
            // Salto absoluto condicional: salta si el flag C está activado (C=1)
            // Fuente: Pan Docs - JP C, nn: 4 M-Cycles si salta, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (regs_->get_flag_c()) {
                    regs_->pc = target;
                    cycles_ += 4;
                    return 4;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xE9:  // JP (HL) (Jump to address in HL)
            // Salto indirecto: PC = HL
            // Esta instrucción permite saltar a una dirección calculada dinámicamente
            // Fuente: Pan Docs - JP (HL): 1 M-Cycle
            {
                uint16_t hl = regs_->get_hl();
                regs_->pc = hl;
                cycles_ += 1;  // JP (HL) consume 1 M-Cycle
                return 1;
            }

        case 0x18:  // JR e (Jump Relative)
            // Salto relativo incondicional
            // Lee un byte con signo (int8_t) y lo suma a PC
            // El offset se suma al PC DESPUÉS de leer toda la instrucción
            // Fuente: Pan Docs - JR e: 3 M-Cycles
            {
                uint8_t offset_raw = fetch_byte();
                // Cast a int8_t: C++ maneja automáticamente el complemento a dos
                int8_t offset = static_cast<int8_t>(offset_raw);
                // Sumar offset a PC (el PC ya avanzó 2 posiciones: opcode + offset)
                uint16_t new_pc = (regs_->pc + offset) & 0xFFFF;
                regs_->pc = new_pc;
                cycles_ += 3;  // JR e consume 3 M-Cycles
                return 3;
            }

        case 0x20:  // JR NZ, e (Jump Relative if Not Zero)
            // Salto relativo condicional: salta si el flag Z está desactivado (Z=0)
            // SIEMPRE lee el offset (para avanzar PC), pero solo salta si la condición es verdadera
            // Fuente: Pan Docs - JR NZ, e: 3 M-Cycles si salta, 2 M-Cycles si no salta
            {
                uint8_t offset_raw = fetch_byte();
                
                if (!regs_->get_flag_z()) {
                    // Condición verdadera: saltar
                    int8_t offset = static_cast<int8_t>(offset_raw);
                    uint16_t new_pc = (regs_->pc + offset) & 0xFFFF;
                    regs_->pc = new_pc;
                    cycles_ += 3;  // JR NZ consume 3 M-Cycles si salta
                    return 3;
                } else {
                    // Condición falsa: no saltar, continuar ejecución normal
                    cycles_ += 2;  // JR NZ consume 2 M-Cycles si no salta
                    return 2;
                }
            }

        case 0x28:  // JR Z, e (Jump Relative if Zero)
            // Salto relativo condicional: salta si el flag Z está activado (Z=1)
            // SIEMPRE lee el offset (para avanzar PC), pero solo salta si la condición es verdadera
            // Fuente: Pan Docs - JR Z, e: 3 M-Cycles si salta, 2 M-Cycles si no salta
            {
                uint8_t offset_raw = fetch_byte();
                
                if (regs_->get_flag_z()) {
                    // Condición verdadera: saltar
                    int8_t offset = static_cast<int8_t>(offset_raw);
                    uint16_t new_pc = (regs_->pc + offset) & 0xFFFF;
                    regs_->pc = new_pc;
                    cycles_ += 3;  // JR Z consume 3 M-Cycles si salta
                    return 3;
                } else {
                    // Condición falsa: no saltar, continuar ejecución normal
                    cycles_ += 2;  // JR Z consume 2 M-Cycles si no salta
                    return 2;
                }
            }

        case 0x30:  // JR NC, e (Jump Relative if No Carry)
            // Salto relativo condicional: salta si el flag C está desactivado (C=0)
            // SIEMPRE lee el offset (para avanzar PC), pero solo salta si la condición es verdadera
            // Fuente: Pan Docs - JR NC, e: 3 M-Cycles si salta, 2 M-Cycles si no salta
            {
                uint8_t offset_raw = fetch_byte();
                
                if (!regs_->get_flag_c()) {
                    // Condición verdadera: saltar
                    int8_t offset = static_cast<int8_t>(offset_raw);
                    uint16_t new_pc = (regs_->pc + offset) & 0xFFFF;
                    regs_->pc = new_pc;
                    cycles_ += 3;  // JR NC consume 3 M-Cycles si salta
                    return 3;
                } else {
                    // Condición falsa: no saltar, continuar ejecución normal
                    cycles_ += 2;  // JR NC consume 2 M-Cycles si no salta
                    return 2;
                }
            }

        case 0x38:  // JR C, e (Jump Relative if Carry)
            // Salto relativo condicional: salta si el flag C está activado (C=1)
            // SIEMPRE lee el offset (para avanzar PC), pero solo salta si la condición es verdadera
            // Fuente: Pan Docs - JR C, e: 3 M-Cycles si salta, 2 M-Cycles si no salta
            {
                uint8_t offset_raw = fetch_byte();
                
                if (regs_->get_flag_c()) {
                    // Condición verdadera: saltar
                    int8_t offset = static_cast<int8_t>(offset_raw);
                    uint16_t new_pc = (regs_->pc + offset) & 0xFFFF;
                    regs_->pc = new_pc;
                    cycles_ += 3;  // JR C consume 3 M-Cycles si salta
                    return 3;
                } else {
                    // Condición falsa: no saltar, continuar ejecución normal
                    cycles_ += 2;  // JR C consume 2 M-Cycles si no salta
                    return 2;
                }
            }

        // ========== Operaciones de Stack (Pila) ==========
        // La pila es crítica para llamadas a subrutinas (CALL/RET)

        case 0xC5:  // PUSH BC (Push BC onto stack)
            // Empuja el par de registros BC en la pila
            // La pila crece hacia abajo: SP se decrementa primero
            // Fuente: Pan Docs - PUSH BC: 4 M-Cycles
            {
                uint16_t bc = regs_->get_bc();
                push_word(bc);
                cycles_ += 4;  // PUSH BC consume 4 M-Cycles
                return 4;
            }

        case 0xC1:  // POP BC (Pop from stack into BC)
            // Saca una palabra de la pila y la guarda en BC
            // La pila se "encoge": SP se incrementa después de leer
            // Fuente: Pan Docs - POP BC: 3 M-Cycles
            {
                uint16_t value = pop_word();
                regs_->set_bc(value);
                cycles_ += 3;  // POP BC consume 3 M-Cycles
                return 3;
            }

        case 0xD5:  // PUSH DE (Push DE onto stack)
            // Empuja el par de registros DE en la pila
            // La pila crece hacia abajo: SP se decrementa primero
            // Fuente: Pan Docs - PUSH DE: 4 M-Cycles
            {
                uint16_t de = regs_->get_de();
                push_word(de);
                cycles_ += 4;  // PUSH DE consume 4 M-Cycles
                return 4;
            }

        case 0xD1:  // POP DE (Pop from stack into DE)
            // Saca una palabra de la pila y la guarda en DE
            // La pila se "encoge": SP se incrementa después de leer
            // Fuente: Pan Docs - POP DE: 3 M-Cycles
            {
                uint16_t value = pop_word();
                regs_->set_de(value);
                cycles_ += 3;  // POP DE consume 3 M-Cycles
                return 3;
            }

        case 0xE5:  // PUSH HL (Push HL onto stack)
            // Empuja el par de registros HL en la pila
            // La pila crece hacia abajo: SP se decrementa primero
            // Fuente: Pan Docs - PUSH HL: 4 M-Cycles
            {
                uint16_t hl = regs_->get_hl();
                push_word(hl);
                cycles_ += 4;  // PUSH HL consume 4 M-Cycles
                return 4;
            }

        case 0xE1:  // POP HL (Pop from stack into HL)
            // Saca una palabra de la pila y la guarda en HL
            // La pila se "encoge": SP se incrementa después de leer
            // Fuente: Pan Docs - POP HL: 3 M-Cycles
            {
                uint16_t value = pop_word();
                regs_->set_hl(value);
                cycles_ += 3;  // POP HL consume 3 M-Cycles
                return 3;
            }

        case 0xF5:  // PUSH AF (Push AF onto stack)
            // Empuja el par de registros AF en la pila
            // La pila crece hacia abajo: SP se decrementa primero
            // Fuente: Pan Docs - PUSH AF: 4 M-Cycles
            {
                uint16_t af = regs_->get_af();
                push_word(af);
                cycles_ += 4;  // PUSH AF consume 4 M-Cycles
                return 4;
            }

        case 0xF1:  // POP AF (Pop from stack into AF)
            // Saca una palabra de la pila y la guarda en AF
            // CRÍTICO: Los 4 bits bajos del registro F SIEMPRE deben ser 0
            // El hardware real garantiza que estos bits nunca se pueden escribir
            // Fuente: Pan Docs - POP AF: 3 M-Cycles
            // Nota: set_af() ya aplica REGISTER_F_MASK (0xF0), pero lo hacemos
            // explícito con & 0xFFF0 para mayor claridad y robustez
            {
                uint16_t value = pop_word();
                regs_->set_af(value & 0xFFF0);  // Limpiar bits bajos de F explícitamente
                cycles_ += 3;  // POP AF consume 3 M-Cycles
                return 3;
            }

        case 0xCD:  // CALL nn (Call subroutine at address nn)
            // Llama a una subrutina guardando la dirección de retorno en la pila
            // 1. Lee la dirección destino nn (16 bits, Little-Endian)
            // 2. Empuja PC (dirección de retorno) en la pila
            // 3. Asigna PC = nn (salta a la subrutina)
            // Fuente: Pan Docs - CALL nn: 6 M-Cycles
            {
                uint16_t target = fetch_word();  // Lee dirección destino
                uint16_t return_addr = regs_->pc;  // PC actual es la dirección de retorno
                push_word(return_addr);  // Guardar dirección de retorno en la pila
                regs_->pc = target;  // Saltar a la subrutina
                cycles_ += 6;  // CALL nn consume 6 M-Cycles
                return 6;
            }

        // ========== Llamadas Condicionales (CALL cc, nn) ==========
        // Step 0269: Implementación de llamadas condicionales
        // Estas instrucciones son críticas para evitar desbalance de pila
        
        case 0xC4:  // CALL NZ, nn (Call if Not Zero)
            // Llama a una subrutina si el flag Z está desactivado (Z=0)
            // SIEMPRE lee nn (para avanzar PC), pero solo llama si la condición es verdadera
            // Fuente: Pan Docs - CALL NZ, nn: 6 M-Cycles si se cumple, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();  // Siempre leer nn para mantener PC alineado
                
                if (!regs_->get_flag_z()) {
                    // Condición verdadera: hacer push y saltar
                    uint16_t return_addr = regs_->pc;  // PC actual es la dirección de retorno
                    push_word(return_addr);
                    regs_->pc = target;
                    cycles_ += 6;  // CALL NZ consume 6 M-Cycles si se cumple
                    return 6;
                } else {
                    // Condición falsa: no llamar, continuar ejecución normal
                    cycles_ += 3;  // CALL NZ consume 3 M-Cycles si no se cumple
                    return 3;
                }
            }

        case 0xCC:  // CALL Z, nn (Call if Zero)
            // Llama a una subrutina si el flag Z está activado (Z=1)
            // Fuente: Pan Docs - CALL Z, nn: 6 M-Cycles si se cumple, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (regs_->get_flag_z()) {
                    uint16_t return_addr = regs_->pc;
                    push_word(return_addr);
                    regs_->pc = target;
                    cycles_ += 6;
                    return 6;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xD4:  // CALL NC, nn (Call if No Carry)
            // Llama a una subrutina si el flag C está desactivado (C=0)
            // Fuente: Pan Docs - CALL NC, nn: 6 M-Cycles si se cumple, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (!regs_->get_flag_c()) {
                    uint16_t return_addr = regs_->pc;
                    push_word(return_addr);
                    regs_->pc = target;
                    cycles_ += 6;
                    return 6;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xDC:  // CALL C, nn (Call if Carry)
            // Llama a una subrutina si el flag C está activado (C=1)
            // Fuente: Pan Docs - CALL C, nn: 6 M-Cycles si se cumple, 3 M-Cycles si no
            {
                uint16_t target = fetch_word();
                
                if (regs_->get_flag_c()) {
                    uint16_t return_addr = regs_->pc;
                    push_word(return_addr);
                    regs_->pc = target;
                    cycles_ += 6;
                    return 6;
                } else {
                    cycles_ += 3;
                    return 3;
                }
            }

        case 0xC9:  // RET (Return from subroutine)
            // Retorna de una subrutina recuperando la dirección de retorno de la pila
            // 1. Saca la dirección de retorno de la pila
            // 2. Asigna PC = dirección de retorno
            // Fuente: Pan Docs - RET: 4 M-Cycles
            {
                uint16_t return_addr = pop_word();
                regs_->pc = return_addr;
                cycles_ += 4;  // RET consume 4 M-Cycles
                return 4;
            }

        case 0xD9:  // RETI (Return and Enable Interrupts)
            // Retorna de una rutina de interrupción y reactiva IME
            // Fuente: Pan Docs - RETI: 4 M-Cycles
            {
                uint16_t return_addr = pop_word();
                regs_->pc = return_addr;
                ime_ = true;  // IME se reactiva automáticamente
                cycles_ += 4;  // RETI consume 4 M-Cycles
                return 4;
            }

        // ========== Retornos Condicionales (RET cc) ==========
        // Step 0269: Implementación de retornos condicionales
        // Estas instrucciones son críticas para el flujo de control correcto
        
        case 0xC0:  // RET NZ (Return if Not Zero)
            // Retorna si el flag Z está desactivado (Z=0)
            // Fuente: Pan Docs - RET NZ: 5 M-Cycles si se cumple, 2 M-Cycles si no
            {
                if (!regs_->get_flag_z()) {
                    // Condición verdadera: hacer pop y saltar
                    uint16_t return_addr = pop_word();
                    regs_->pc = return_addr;
                    cycles_ += 5;  // RET NZ consume 5 M-Cycles si se cumple
                    return 5;
                } else {
                    // Condición falsa: no retornar, continuar ejecución
                    cycles_ += 2;  // RET NZ consume 2 M-Cycles si no se cumple
                    return 2;
                }
            }

        case 0xC8:  // RET Z (Return if Zero)
            // Retorna si el flag Z está activado (Z=1)
            // Fuente: Pan Docs - RET Z: 5 M-Cycles si se cumple, 2 M-Cycles si no
            {
                if (regs_->get_flag_z()) {
                    uint16_t return_addr = pop_word();
                    regs_->pc = return_addr;
                    cycles_ += 5;
                    return 5;
                } else {
                    cycles_ += 2;
                    return 2;
                }
            }

        case 0xD0:  // RET NC (Return if No Carry)
            // Retorna si el flag C está desactivado (C=0)
            // Fuente: Pan Docs - RET NC: 5 M-Cycles si se cumple, 2 M-Cycles si no
            {
                if (!regs_->get_flag_c()) {
                    uint16_t return_addr = pop_word();
                    regs_->pc = return_addr;
                    cycles_ += 5;
                    return 5;
                } else {
                    cycles_ += 2;
                    return 2;
                }
            }

        case 0xD8:  // RET C (Return if Carry)
            // Retorna si el flag C está activado (C=1)
            // Fuente: Pan Docs - RET C: 5 M-Cycles si se cumple, 2 M-Cycles si no
            {
                if (regs_->get_flag_c()) {
                    uint16_t return_addr = pop_word();
                    regs_->pc = return_addr;
                    cycles_ += 5;
                    return 5;
                } else {
                    cycles_ += 2;
                    return 2;
                }
            }

        // ========== Control de Interrupciones ==========
        
        case 0xF3:  // DI (Disable Interrupts)
            // Desactiva IME inmediatamente
            // Esta instrucción se usa típicamente al inicio de rutinas críticas
            // Fuente: Pan Docs - DI: 1 M-Cycle
            {
                // --- Step 0274: Monitor de Instrucciones DI ---
                printf("[CPU] DI (Disable Interrupts) en PC:0x%04X\n", (regs_->pc - 1) & 0xFFFF);
                ime_ = false;
                ime_scheduled_ = false;  // Cancelar cualquier EI pendiente
                cycles_ += 1;  // DI consume 1 M-Cycle
                return 1;
            }

        case 0xFB:  // EI (Enable Interrupts)
            // Habilita IME con retraso de 1 instrucción
            // El retraso es un comportamiento del hardware real: IME se activa
            // DESPUÉS de ejecutar la siguiente instrucción
            // Esto permite que la instrucción siguiente a EI se ejecute sin interrupciones
            // Fuente: Pan Docs - EI: 1 M-Cycle
            {
                // --- Step 0294: Monitor de Instrucciones EI ([EI-TRACE]) ---
                // Rastrea cuándo se ejecuta EI y el estado de IE e IME.
                // Esto ayuda a entender cuándo se habilitan las interrupciones.
                uint8_t ie_val = mmu_->read(0xFFFF);
                printf("[EI-TRACE] PC:0x%04X Bank:%d | IE:0x%02X IME:%d -> IME:1 (scheduled)\n",
                       original_pc, mmu_->get_current_rom_bank(), ie_val, ime_ ? 1 : 0);
                
                // Verificar qué interrupciones están habilitadas
                if (ie_val != 0x00) {
                    printf("[EI-TRACE]   Interrupciones habilitadas: ");
                    if (ie_val & 0x01) printf("V-Blank ");
                    if (ie_val & 0x02) printf("LCD-STAT ");
                    if (ie_val & 0x04) printf("Timer ");
                    if (ie_val & 0x08) printf("Serial ");
                    if (ie_val & 0x10) printf("Joypad ");
                    printf("\n");
                } else {
                    printf("[EI-TRACE]   ⚠️ ADVERTENCIA: EI ejecutado pero IE=0x00 (ninguna interrupción habilitada)\n");
                }
                
                ime_scheduled_ = true;  // Activar IME después de la siguiente instrucción
                cycles_ += 1;  // EI consume 1 M-Cycle
                return 1;
            }

        case 0x76:  // HALT
            // Pone la CPU en estado de bajo consumo
            // La CPU deja de ejecutar instrucciones hasta que:
            // - Ocurre una interrupción (si IME está activo)
            // - O se despierta manualmente (si hay interrupción pendiente sin IME)
            // Fuente: Pan Docs - HALT: 1 M-Cycle
            // Retornamos -1 para señalar "avance rápido" (el orquestador puede saltar ciclos).
            {
                // HALT bug: si IME=0 y hay interrupción pendiente (IE & IF != 0),
                // el CPU NO se detiene; simplemente continúa la ejecución.
                constexpr uint16_t ADDR_IF = 0xFF0F;
                constexpr uint16_t ADDR_IE = 0xFFFF;
                uint8_t if_reg = mmu_->read(ADDR_IF) & 0x1F;
                uint8_t ie_reg = mmu_->read(ADDR_IE) & 0x1F;
                bool pending = (if_reg & ie_reg) != 0;

                // --- Step 0275: Watchdog de "HALT of Death" ---
                // Si la CPU hace HALT con IE=0 e IME=0, se cuelga para siempre.
                // Esto es un estado de "huelga de CPU permanente" que bloquea el juego.
                if (!ime_ && ie_reg == 0) {
                    printf("[CRITICAL WARNING] HALT detectado con IE=0 e IME=0 en PC:0x%04X. ¡Huelga de CPU permanente!\n", (regs_->pc - 1) & 0xFFFF);
                }
                // -----------------------------------------

                if (!ime_ && pending) {
                    cycles_ += 1;  // Consume 1 M-Cycle pero no entra en HALT
                    return 1;      // Continúa con la instrucción siguiente (HALT bug)
                }

                halted_ = true;
                cycles_ += 1;  // HALT consume 1 M-Cycle
                return -1;  // HALT devuelve -1 para señalar avance rápido
            }

        // ========== I/O de Memoria Alta (LDH) ==========
        // LDH es una instrucción optimizada para acceder a los registros de hardware
        // en el rango 0xFF00-0xFFFF. Es equivalente a LD pero más rápida (3 M-Cycles vs 4).
        // Fuente: Pan Docs - LDH (n), A y LDH A, (n): 3 M-Cycles
        
        case 0xE0:  // LDH (n), A (Load A to High Memory I/O)
            // Escribe el valor del registro A en la dirección 0xFF00 + n
            // Donde 'n' es el siguiente byte leído de memoria
            // Esta instrucción se usa para configurar registros de hardware (LCDC, BGP, etc.)
            {
                uint8_t offset = fetch_byte();
                uint16_t addr = 0xFF00 + static_cast<uint16_t>(offset);
                mmu_->write(addr, regs_->a);
                cycles_ += 3;  // LDH (n), A consume 3 M-Cycles
                return 3;
            }

        case 0xF0:  // LDH A, (n) (Load from High Memory I/O to A)
            // Lee el valor de la dirección 0xFF00 + n y lo carga en el registro A
            // Donde 'n' es el siguiente byte leído de memoria
            // Esta instrucción se usa para leer registros de hardware (STAT, etc.)
            {
                uint8_t offset = fetch_byte();
                uint16_t addr = 0xFF00 + static_cast<uint16_t>(offset);
                regs_->a = mmu_->read(addr);
                cycles_ += 3;  // LDH A, (n) consume 3 M-Cycles
                return 3;
            }

        case 0xE2:  // LDH (C), A (Load A to 0xFF00 + C)
            {
                uint16_t addr = 0xFF00 + static_cast<uint16_t>(regs_->c);
                mmu_->write(addr, regs_->a);
                cycles_ += 2;  // LDH (C), A consume 2 M-Cycles
                return 2;
            }

        case 0xF2:  // LDH A, (C) (Load from 0xFF00 + C to A)
            {
                uint16_t addr = 0xFF00 + static_cast<uint16_t>(regs_->c);
                regs_->a = mmu_->read(addr);
                cycles_ += 2;  // LDH A, (C) consume 2 M-Cycles
                return 2;
            }

        case 0xEA:  // LD (nn), A (Load A to absolute 16-bit address)
            {
                uint16_t addr = fetch_word();
                mmu_->write(addr, regs_->a);
                cycles_ += 4;  // LD (nn), A consume 4 M-Cycles
                return 4;
            }

        case 0xFA:  // LD A, (nn) (Load from absolute 16-bit address to A)
            {
                uint16_t addr = fetch_word();
                regs_->a = mmu_->read(addr);
                cycles_ += 4;  // LD A, (nn) consume 4 M-Cycles
                return 4;
            }

        // ========== Stack Math (Aritmética de Pila) ==========
        // Step 0268: Implementación de instrucciones de aritmética de pila
        // Estas instrucciones son críticas para el manejo de variables locales en la pila
        
        case 0xE8:  // ADD SP, e (Add signed 8-bit offset to Stack Pointer)
            // Suma un valor con signo de 8 bits al Stack Pointer
            // El offset se lee como un byte con signo (Two's Complement)
            // Flags H y C se calculan basándose en el byte bajo de SP, no en el resultado completo
            // Fuente: Pan Docs - ADD SP, r8: 4 M-Cycles (16 cycles)
            {
                // Leer offset con signo
                uint8_t offset_raw = fetch_byte();
                int8_t offset = static_cast<int8_t>(offset_raw);
                
                // Guardar SP original para cálculo de flags
                uint16_t sp_old = regs_->sp;
                uint8_t sp_low = sp_old & 0xFF;
                
                // Calcular nuevo SP
                uint16_t sp_new = (sp_old + offset) & 0xFFFF;
                regs_->sp = sp_new;
                
                // Calcular flags (CRÍTICO: basados en byte bajo, no resultado completo)
                // Z: siempre 0 (reset)
                regs_->set_flag_z(false);
                
                // N: siempre 0 (es suma)
                regs_->set_flag_n(false);
                
                // H: Half-carry desde bit 3 (nibble bajo)
                // Fórmula: ((sp_low & 0xF) + (offset & 0xF)) > 0xF
                // Convertir offset a unsigned para el cálculo
                uint8_t offset_unsigned = static_cast<uint8_t>(offset_raw);
                uint8_t sp_low_nibble = sp_low & 0x0F;
                uint8_t offset_low_nibble = offset_unsigned & 0x0F;
                bool half_carry = (sp_low_nibble + offset_low_nibble) > 0x0F;
                regs_->set_flag_h(half_carry);
                
                // C: Carry desde bit 7 (byte bajo)
                // Fórmula: ((sp_low + offset_unsigned) & 0x100) != 0
                bool carry = ((static_cast<uint16_t>(sp_low) + static_cast<uint16_t>(offset_unsigned)) & 0x100) != 0;
                regs_->set_flag_c(carry);
                
                cycles_ += 4;  // ADD SP, e consume 4 M-Cycles
                return 4;
            }

        case 0xF8:  // LD HL, SP+e (Load HL with SP + signed 8-bit offset)
            // Calcula SP + offset y almacena el resultado en HL
            // SP NO se modifica (solo se usa para el cálculo)
            // Flags H y C se calculan igual que ADD SP, e
            // Fuente: Pan Docs - LD HL, SP+r8: 3 M-Cycles (12 cycles)
            {
                // Leer offset con signo
                uint8_t offset_raw = fetch_byte();
                int8_t offset = static_cast<int8_t>(offset_raw);
                
                // Guardar SP para cálculo de flags (NO se modifica)
                uint16_t sp = regs_->sp;
                uint8_t sp_low = sp & 0xFF;
                
                // Calcular HL = SP + offset
                uint16_t hl_new = (sp + offset) & 0xFFFF;
                regs_->set_hl(hl_new);
                
                // Calcular flags (idéntico a ADD SP, e)
                // Z: siempre 0 (reset)
                regs_->set_flag_z(false);
                
                // N: siempre 0 (es suma)
                regs_->set_flag_n(false);
                
                // H: Half-carry desde bit 3 (nibble bajo)
                uint8_t offset_unsigned = static_cast<uint8_t>(offset_raw);
                uint8_t sp_low_nibble = sp_low & 0x0F;
                uint8_t offset_low_nibble = offset_unsigned & 0x0F;
                bool half_carry = (sp_low_nibble + offset_low_nibble) > 0x0F;
                regs_->set_flag_h(half_carry);
                
                // C: Carry desde bit 7 (byte bajo)
                bool carry = ((static_cast<uint16_t>(sp_low) + static_cast<uint16_t>(offset_unsigned)) & 0x100) != 0;
                regs_->set_flag_c(carry);
                
                cycles_ += 3;  // LD HL, SP+e consume 3 M-Cycles
                return 3;
            }

        case 0xF9:  // LD SP, HL (Load Stack Pointer from HL)
            // Copia el valor de HL a SP
            // No afecta flags
            // Fuente: Pan Docs - LD SP, HL: 2 M-Cycles (8 cycles)
            {
                uint16_t hl = regs_->get_hl();
                regs_->sp = hl;
                cycles_ += 2;  // LD SP, HL consume 2 M-Cycles
                return 2;
            }

        // ========== Restarts (RST n) ==========
        // Step 0269: Implementación de instrucciones RST
        // Las instrucciones RST son llamadas rápidas de 1 byte que hacen PUSH PC y saltan a una dirección fija
        // Son críticas para Pokémon y otros juegos que las usan para funciones del sistema
        // Fuente: Pan Docs - RST n: 4 M-Cycles
        
        case 0xC7:  // RST 00 (Restart to 0x0000)
            {
                uint16_t return_addr = regs_->pc;  // PC actual es la dirección de retorno
                push_word(return_addr);
                regs_->pc = 0x0000;
                cycles_ += 4;  // RST consume 4 M-Cycles
                return 4;
            }

        case 0xCF:  // RST 08 (Restart to 0x0008)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0008;
                cycles_ += 4;
                return 4;
            }

        case 0xD7:  // RST 10 (Restart to 0x0010)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0010;
                cycles_ += 4;
                return 4;
            }

        case 0xDF:  // RST 18 (Restart to 0x0018)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0018;
                cycles_ += 4;
                return 4;
            }

        case 0xE7:  // RST 20 (Restart to 0x0020)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0020;
                cycles_ += 4;
                return 4;
            }

        case 0xEF:  // RST 28 (Restart to 0x0028)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0028;
                cycles_ += 4;
                return 4;
            }

        case 0xF7:  // RST 30 (Restart to 0x0030)
            {
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0030;
                cycles_ += 4;
                return 4;
            }

        case 0xFF:  // RST 38 (Restart to 0x0038)
            {
                // Diagnóstico puntual: traza la primera vez que se ejecuta 0xFF para
                // identificar el origen del "pantallazo azul" (loop en 0x0038).
                static bool rst38_logged = false;
                if (!rst38_logged) {
                    rst38_logged = true;
                    uint16_t origin_pc = (regs_->pc - 1) & 0xFFFF;  // PC apunta al siguiente byte tras el fetch
                    printf("[RST38-TRACE] opcode FF en PC:%04X SP:%04X AF:%04X BC:%04X DE:%04X HL:%04X IE:%02X IF:%02X IME:%d\n",
                           origin_pc,
                           regs_->sp,
                           regs_->get_af(),
                           regs_->get_bc(),
                           regs_->get_de(),
                           regs_->get_hl(),
                           mmu_->read(0xFFFF),
                           mmu_->read(0xFF0F),
                           ime_ ? 1 : 0);
                }
                uint16_t return_addr = regs_->pc;
                push_word(return_addr);
                regs_->pc = 0x0038;
                cycles_ += 4;
                return 4;
            }

        case 0xCB:  // CB Prefix (Extended Instructions)
            // Prefijo para instrucciones extendidas (256 instrucciones adicionales)
            // El siguiente byte se interpreta con una tabla diferente
            // Incluye: Rotaciones, Shifts, BIT, RES, SET
            // Fuente: Pan Docs - CPU Instruction Set (CB Prefix)
            {
                int cycles = handle_cb();
                cycles_ += cycles;
                return cycles;
            }

        default:
            // --- Step 0169: Revertido a comportamiento silencioso ---
            // El diagnóstico del Step 0168 confirmó que no hay opcodes desconocidos.
            // El deadlock es causado por un bucle lógico con instrucciones válidas.
            // Volvemos a devolver 0 ciclos para permitir que el trazado capture el bucle.
            cycles_ += 0;
            return 0;
    }
    
    // --- Step 0274: Seguimiento Post-Limpieza VRAM ---
    // El bucle de limpieza de VRAM en PC:36E3 termina cuando BC llega a 0.
    // Queremos rastrear qué instrucciones siguen después de que el bucle termine.
    // El bucle probablemente tiene 6 bytes (22 0B 78 + JR NZ), así que la salida
    // debería estar en PC:36E9 (36E3 + 6).
    static bool tracing_after_vram_clear = false;
    static int trace_count = 0;
    
    // Trigger: El bucle en 0x36E3 termina y la ejecución sigue en 0x36E9
    if (regs_->pc == 0x36E9 && !tracing_after_vram_clear) {
        printf("[VRAM-CLEAR-EXIT] El bucle de limpieza ha terminado. Iniciando Trail...\n");
        tracing_after_vram_clear = true;
    }
    
    // Rastrear las siguientes 100 instrucciones después de salir del bucle
    if (tracing_after_vram_clear && trace_count < 100) {
        printf("[TRAIL] PC:%04X OP:%02X AF:%04X BC:%04X DE:%04X HL:%04X IE:%02X IF:%02X\n",
               regs_->pc, mmu_->read(regs_->pc),
               regs_->get_af(), regs_->get_bc(), regs_->get_de(), regs_->get_hl(),
               mmu_->read(0xFFFF), mmu_->read(0xFF0F));
        trace_count++;
    }
    
    // --- Step 0267: SP CORRUPTION WATCHDOG ---
    // El Stack Pointer debe estar siempre en RAM (C000-DFFF o FF80-FFFE)
    // Si baja de C000 (y no es 0000 momentáneo), algo ha ido terriblemente mal.
    // Esta verificación se ejecuta después de cada instrucción para detectar
    // el momento exacto en que el SP se corrompe.
    // Fuente: Pan Docs - Memory Map: Stack debe estar en WRAM (C000-DFFF) o HRAM (FF80-FFFE)
    if (regs_->sp < 0xC000 && regs_->sp != 0x0000) {
        printf("[CRITICAL] SP CORRUPTION DETECTED! SP:%04X at PC:%04X\n", regs_->sp, regs_->pc);
        // Opcional: exit(1) para detenerlo en el acto (comentado para permitir logging)
        // exit(1);
    }
    
}

uint32_t CPU::get_cycles() const {
    return cycles_;
}

bool CPU::get_ime() const {
    return ime_;
}

void CPU::set_ime(bool value) {
    ime_ = value;
}

bool CPU::get_halted() const {
    return halted_;
}

uint8_t CPU::handle_interrupts() {
    // Direcciones de registros de interrupciones
    constexpr uint16_t ADDR_IF = 0xFF0F;  // Interrupt Flag
    constexpr uint16_t ADDR_IE = 0xFFFF;  // Interrupt Enable
    
    // Leer registros de interrupciones
    uint8_t if_reg = mmu_->read(ADDR_IF);
    uint8_t ie_reg = mmu_->read(ADDR_IE);
    
    // Máscara para los 5 bits válidos (bits 0-4)
    constexpr uint8_t INTERRUPT_MASK = 0x1F;
    if_reg &= INTERRUPT_MASK;
    ie_reg &= INTERRUPT_MASK;
    
    // Calcular interrupciones pendientes (bits activos en ambos registros)
    uint8_t pending = ie_reg & if_reg;
    
    // --- Step 0264: HALT WAKEUP FIX (IME=0) ---
    // Según Pan Docs, cuando IME=0 y hay una interrupción pendiente habilitada en IE:
    // 1. La CPU DEBE SALIR DE HALT (despertar).
    // 2. Pero NO salta al vector de interrupción (porque IME=0).
    // 3. Simplemente continúa la ejecución en la siguiente instrucción.
    // 
    // Esto es crítico: si la CPU se queda en HALT eternamente porque IME=0,
    // el juego se congela esperando que la interrupción ocurra.
    // 
    // Fuente: Pan Docs - "HALT Instruction", "Interrupts"
    if (halted_ && pending != 0) {
        halted_ = false;
        // Nota: Si IME es false, no consumimos ciclos extra ni saltamos al vector,
        // simplemente continuamos la ejecución (HALT termina).
    }
    // -----------------------------------------
    
    // Si IME está activo y hay interrupciones pendientes, procesar la de mayor prioridad
    if (ime_ && pending != 0) {
        // Desactivar IME inmediatamente (evita interrupciones anidadas)
        ime_ = false;
        
        // Encontrar el bit de menor peso (mayor prioridad)
        // V-Blank (bit 0) tiene la prioridad más alta
        uint8_t interrupt_bit = 0;
        uint16_t vector = 0x0040;  // Vector base de V-Blank
        
        if (pending & 0x01) {
            interrupt_bit = 0x01;
            vector = 0x0040;  // V-Blank
        } else if (pending & 0x02) {
            interrupt_bit = 0x02;
            vector = 0x0048;  // LCD STAT
        } else if (pending & 0x04) {
            interrupt_bit = 0x04;
            vector = 0x0050;  // Timer
        } else if (pending & 0x08) {
            interrupt_bit = 0x08;
            vector = 0x0058;  // Serial
        } else if (pending & 0x10) {
            interrupt_bit = 0x10;
            vector = 0x0060;  // Joypad
        }
        
        // --- Step 0384: Instrumentar servicio de interrupción ---
        uint16_t prev_pc = regs_->pc;
        uint8_t if_before_clear = if_reg;
        
        // Limpiar el bit en IF (acknowledgement)
        uint8_t new_if = if_reg & ~interrupt_bit;
        mmu_->write(ADDR_IF, new_if);
        
        // Loggear (límite: 50 líneas)
        static int irq_service_log = 0;
        if (irq_service_log < 50) {
            const char* irq_names[] = {"VBlank", "LCD-STAT", "Timer", "Serial", "Joypad"};
            int bit_num = 0;
            for (int i = 0; i < 5; i++) {
                if (interrupt_bit & (1 << i)) {
                    bit_num = i;
                    break;
                }
            }
            
            printf("[IRQ-SERVICE] Vector:0x%04X (%s) | PC:0x%04X->0x%04X | "
                   "IF: 0x%02X->0x%02X | IE:0x%02X | IME:%d\n",
                   vector, (bit_num <= 4) ? irq_names[bit_num] : "Unknown",
                   prev_pc, vector,
                   if_before_clear, new_if, ie_reg, ime_ ? 1 : 0);
            irq_service_log++;
        }
        // -------------------------------------------

        // Guardar PC en la pila (dirección de retorno)
        push_word(prev_pc);
        
        // Saltar al vector de interrupción
        regs_->pc = vector;
        
        // Retornar 5 M-Cycles consumidos por el procesamiento de interrupción
        return 5;
    }
    
    // No hay interrupciones que procesar
    return 0;
}

// ========== Implementación del Prefijo CB (Extended Instructions) ==========

int CPU::handle_cb() {
    // Leer el opcode CB (siguiente byte después de 0xCB)
    uint8_t cb_opcode = fetch_byte();
    
    // Extraer componentes del opcode CB
    uint8_t reg_code = cb_opcode & 0x07;        // Bits 0-2: Registro
    uint8_t bit_index = (cb_opcode >> 3) & 0x07; // Bits 3-5: Índice de bit
    uint8_t op_group = (cb_opcode >> 6) & 0x03;  // Bits 6-7: Grupo de operación
    
    // Determinar si es acceso a memoria (reg_code == 6)
    bool is_memory = (reg_code == 6);
    
    // Leer valor del registro o memoria
    uint8_t value = read_register_or_mem(reg_code);
    uint8_t result = value;
    bool carry = regs_->get_flag_c();  // Preservar C para operaciones que lo usan
    
    // Decodificar y ejecutar operación según el grupo
    switch (op_group) {
        case 0x00: {  // Rotaciones y Shifts (0x00-0x3F)
            // Bits 3-5 determinan la operación específica
            uint8_t shift_op = (cb_opcode >> 3) & 0x07;
            
            switch (shift_op) {
                case 0x00: {  // RLC (Rotate Left Circular)
                    // Bit 7 sale y entra por bit 0, también va a C
                    bool bit7 = (value & 0x80) != 0;
                    result = (value << 1) | (bit7 ? 1 : 0);
                    carry = bit7;
                    // Flags: Z según resultado, N=0, H=0, C=bit7
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x01: {  // RRC (Rotate Right Circular)
                    // Bit 0 sale y entra por bit 7, también va a C
                    bool bit0 = (value & 0x01) != 0;
                    result = (value >> 1) | (bit0 ? 0x80 : 0);
                    carry = bit0;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x02: {  // RL (Rotate Left through Carry)
                    // Bit 7 va a C, antiguo C entra en bit 0
                    bool bit7 = (value & 0x80) != 0;
                    result = (value << 1) | (carry ? 1 : 0);
                    carry = bit7;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x03: {  // RR (Rotate Right through Carry)
                    // Bit 0 va a C, antiguo C entra en bit 7
                    bool bit0 = (value & 0x01) != 0;
                    result = (value >> 1) | (carry ? 0x80 : 0);
                    carry = bit0;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x04: {  // SLA (Shift Left Arithmetic)
                    // Bit 7 va a C, bit 0 entra 0
                    bool bit7 = (value & 0x80) != 0;
                    result = value << 1;
                    carry = bit7;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x05: {  // SRA (Shift Right Arithmetic - preserva signo)
                    // Bit 0 va a C, bit 7 se mantiene (signo preservado)
                    bool bit0 = (value & 0x01) != 0;
                    bool bit7 = (value & 0x80) != 0;  // Signo original
                    result = (value >> 1) | (bit7 ? 0x80 : 0);
                    carry = bit0;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
                case 0x06: {  // SWAP (Swap nibbles)
                    // Intercambia los 4 bits altos con los 4 bits bajos
                    result = ((value & 0x0F) << 4) | ((value & 0xF0) >> 4);
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(false);
                    break;
                }
                case 0x07: {  // SRL (Shift Right Logical - sin signo)
                    // Bit 0 va a C, bit 7 entra 0
                    bool bit0 = (value & 0x01) != 0;
                    result = value >> 1;
                    carry = bit0;
                    regs_->set_flag_z(result == 0);
                    regs_->set_flag_n(false);
                    regs_->set_flag_h(false);
                    regs_->set_flag_c(carry);
                    break;
                }
            }
            break;
        }
        case 0x01: {  // BIT (Test bit) - 0x40-0x7F
            // Testear si el bit 'bit_index' está encendido
            bool bit_set = (value & (1 << bit_index)) != 0;
            // Z = !bit_set (si bit está apagado, Z=1)
            regs_->set_flag_z(!bit_set);
            regs_->set_flag_n(false);
            regs_->set_flag_h(true);  // QUIRK: BIT siempre pone H=1
            // C no se modifica (preservado)
            // No modificamos result (BIT solo testea, no modifica)
            return is_memory ? 4 : 2;  // Retornar aquí porque BIT no escribe
        }
        case 0x02: {  // RES (Reset bit) - 0x80-0xBF
            // Apagar el bit 'bit_index'
            result = value & ~(1 << bit_index);
            // RES no afecta flags (preserva todos)
            break;
        }
        case 0x03: {  // SET (Set bit) - 0xC0-0xFF
            // Encender el bit 'bit_index'
            result = value | (1 << bit_index);
            // SET no afecta flags (preserva todos)
            break;
        }
    }
    
    // Escribir resultado de vuelta al registro o memoria
    write_register_or_mem(reg_code, result);
    
    // Timing: (HL) consume 4 M-Cycles, registros consumen 2
    return is_memory ? 4 : 2;
}

// ========== Implementación de Métodos de Sincronización ==========

void CPU::setPPU(PPU* ppu) {
    ppu_ = ppu;
}

void CPU::setTimer(Timer* timer) {
    timer_ = timer;
}

void CPU::run_scanline() {
    // Si la PPU no está conectada, no podemos ejecutar el bucle de scanline
    if (ppu_ == nullptr) {
        return;
    }
    
    // Constante: 456 T-Cycles por scanline
    // Fuente: Pan Docs - LCD Timing
    const int CYCLES_PER_SCANLINE = 456;
    
    int cycles_this_scanline = 0;
    
    // Bucle de emulación de grano fino: ejecuta instrucciones hasta acumular 456 T-Cycles
    while (cycles_this_scanline < CYCLES_PER_SCANLINE) {
        // Ejecuta UNA instrucción y obtiene los M-Cycles consumidos
        // --- Step 0287: Cambiar a int para manejar correctamente -1 (HALT) ---
        int m_cycles = step();
        
        // Si step() devuelve 0, hay un error (opcode no implementado o similar)
        // Si step() devuelve -1, la CPU está en HALT (avance rápido)
        // En ambos casos, forzamos un avance mínimo para evitar bucles infinitos
        if (m_cycles <= 0) {
            m_cycles = 1;  // Forzar avance mínimo (1 M-Cycle = 4 T-Cycles)
        }
        
        // Verificar si la CPU está en HALT
        if (halted_) {
            // Si la CPU está en HALT, no consumió ciclos de instrucción,
            // pero el tiempo debe avanzar. Avanzamos en la unidad mínima
            // de tiempo (1 M-Cycle = 4 T-Cycles).
            // step() ya se ha encargado de comprobar si debe despertar.
            m_cycles = 1;
        }
        
        // Convertir M-Cycles a T-Cycles (1 M-Cycle = 4 T-Cycles)
        int t_cycles = m_cycles * 4;
        
        // ¡LA CLAVE! Actualiza la PPU después de CADA instrucción
        // Esto permite que la PPU cambie de modo en los ciclos exactos
        // y resuelve los deadlocks de polling
        ppu_->step(t_cycles);
        
        // Actualizar el Timer con los T-Cycles consumidos
        // Esto permite que el registro DIV avance correctamente
        // y la CPU pueda salir de bucles de retardo de tiempo
        if (timer_ != nullptr) {
            timer_->step(t_cycles);
        }
        
        // Acumular ciclos para esta scanline
        cycles_this_scanline += t_cycles;
    }
    
    // Al final de la scanline, hemos acumulado exactamente 456 T-Cycles
    // La PPU ya ha sido actualizada después de cada instrucción, por lo que
    // está sincronizada correctamente con la CPU
}

