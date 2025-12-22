#include "CPU.hpp"
#include "MMU.hpp"
#include "Registers.hpp"
#include "PPU.hpp"
#include "Timer.hpp"
#include <cstdio>  // Step 0236: Francotirador II

CPU::CPU(MMU* mmu, CoreRegisters* registers)
    : mmu_(mmu), regs_(registers), ppu_(nullptr), timer_(nullptr), cycles_(0), ime_(false), halted_(false), ime_scheduled_(false) {
    // Validación básica (en producción, podríamos usar assert)
    // Por ahora, confiamos en que Python pasa punteros válidos
    // IME inicia en false por seguridad (el juego lo activará si lo necesita)
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
    if (ime_scheduled_) {
        ime_ = true;
        ime_scheduled_ = false;
    }
    
    // ========== FASE 4: Fetch-Decode-Execute ==========
    // --- Step 0236: FRANCOTIRADOR EN 0x2B30 ---
    // Analizamos el nuevo punto de bloqueo.
    if (regs_->pc >= 0x2B2A && regs_->pc <= 0x2B35) {
        uint8_t opcode = mmu_->read(regs_->pc);
        
        // Leemos el siguiente byte por si es un LDH (n) o CP n
        uint8_t next_byte = mmu_->read(regs_->pc + 1);
        
        printf("[SNIPER] PC:%04X | OP:%02X %02X | AF:%04X | BC:%04X | DE:%04X | HL:%04X\n", 
               regs_->pc, opcode, next_byte, regs_->af, regs_->get_bc(), regs_->get_de(), regs_->get_hl());
    }
    // ------------------------------------------
    
    // Fetch: Leer opcode de memoria
    uint8_t opcode = fetch_byte();

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
        
        case 0x2E:  // LD L, d8
            {
                uint8_t value = fetch_byte();
                regs_->l = value;
                cycles_ += 2;
                return 2;
            }

        case 0x3E:  // LD A, d8 (Load A with immediate 8-bit value)
            // Lee el siguiente byte (d8) y lo guarda en el registro A
            {
                uint8_t value = fetch_byte();
                regs_->a = value;
                cycles_ += 2;  // LD A, d8 consume 2 M-Cycles
                return 2;
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

        // ========== Control de Interrupciones ==========
        
        case 0xF3:  // DI (Disable Interrupts)
            // Desactiva IME inmediatamente
            // Esta instrucción se usa típicamente al inicio de rutinas críticas
            // Fuente: Pan Docs - DI: 1 M-Cycle
            {
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
    
    // Despertar de HALT si hay interrupción pendiente (incluso sin IME)
    if (halted_ && pending != 0) {
        halted_ = false;
    }
    
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
        
        // Limpiar el bit en IF (acknowledgement)
        uint8_t new_if = if_reg & ~interrupt_bit;
        mmu_->write(ADDR_IF, new_if);
        
        // Guardar PC en la pila (dirección de retorno)
        push_word(regs_->pc);
        
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
        uint8_t m_cycles = step();
        
        // Si step() devuelve 0, hay un error (opcode no implementado o similar)
        // En este caso, forzamos un avance mínimo para evitar bucles infinitos
        if (m_cycles == 0) {
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

