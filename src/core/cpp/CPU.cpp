#include "CPU.hpp"
#include "MMU.hpp"
#include "Registers.hpp"

CPU::CPU(MMU* mmu, CoreRegisters* registers)
    : mmu_(mmu), regs_(registers), cycles_(0) {
    // Validación básica (en producción, podríamos usar assert)
    // Por ahora, confiamos en que Python pasa punteros válidos
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

int CPU::step() {
    // Fetch: Leer opcode de memoria
    uint8_t opcode = fetch_byte();

    // Decode/Execute: Switch optimizado por el compilador
    switch (opcode) {
        case 0x00:  // NOP (No Operation)
            // NOP no hace nada, solo consume 1 M-Cycle
            cycles_ += 1;
            return 1;

        case 0x3E:  // LD A, d8 (Load A with immediate 8-bit value)
            // Lee el siguiente byte (d8) y lo guarda en el registro A
            {
                uint8_t value = fetch_byte();
                regs_->a = value;
                cycles_ += 2;  // LD A, d8 consume 2 M-Cycles
                return 2;
            }

        case 0x3C:  // INC A (Increment A)
            // Incrementa A en 1
            {
                uint8_t old_a = regs_->a;
                regs_->a = old_a + 1;
                
                // Flags para INC:
                // Z: resultado == 0
                regs_->set_flag_z(regs_->a == 0);
                // N: siempre 0
                regs_->set_flag_n(false);
                // H: half-carry (bit 3 -> 4)
                regs_->set_flag_h((old_a & 0x0F) == 0x0F);
                // C: no afectado (mantiene valor anterior)
                
                cycles_ += 1;  // INC A consume 1 M-Cycle
                return 1;
            }

        case 0x3D:  // DEC A (Decrement A)
            // Decrementa A en 1
            {
                uint8_t old_a = regs_->a;
                regs_->a = old_a - 1;
                
                // Flags para DEC:
                // Z: resultado == 0
                regs_->set_flag_z(regs_->a == 0);
                // N: siempre 1
                regs_->set_flag_n(true);
                // H: half-borrow (bit 4 -> 3)
                regs_->set_flag_h((old_a & 0x0F) == 0x00);
                // C: no afectado (mantiene valor anterior)
                
                cycles_ += 1;  // DEC A consume 1 M-Cycle
                return 1;
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

        default:
            // Opcode no implementado
            // En producción, esto debería lanzar una excepción o loggear
            // Por ahora, retornamos 0 para indicar error
            // NOTA: No usamos std::cout aquí porque está en el bucle crítico
            return 0;
    }
}

uint32_t CPU::get_cycles() const {
    return cycles_;
}

