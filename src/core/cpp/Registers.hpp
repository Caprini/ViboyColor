#ifndef REGISTERS_HPP
#define REGISTERS_HPP

#include <cstdint>

/**
 * CoreRegisters - Implementación de alto rendimiento de los registros de la CPU LR35902.
 * 
 * La Game Boy utiliza una CPU híbrida basada en el Z80/8080. Los registros están
 * organizados en:
 * - Registros de 8 bits: A, B, C, D, E, H, L, F
 * - Registros de 16 bits: PC (Program Counter), SP (Stack Pointer)
 * - Pares virtuales de 16 bits: AF, BC, DE, HL
 * 
 * El registro F (Flags) tiene una peculiaridad hardware:
 * - Los 4 bits bajos siempre son 0 en el hardware real
 * - Solo los bits 7, 6, 5, 4 son válidos (Z, N, H, C respectivamente)
 * 
 * Fuente: Pan Docs - Game Boy CPU Manual
 */

// Constantes para los flags (bits 7, 6, 5, 4 respectivamente)
constexpr uint8_t FLAG_Z = 0x80;  // Zero flag (bit 7)
constexpr uint8_t FLAG_N = 0x40;  // Subtract flag (bit 6)
constexpr uint8_t FLAG_H = 0x20;  // Half Carry flag (bit 5)
constexpr uint8_t FLAG_C = 0x10;  // Carry flag (bit 4)

// Máscara para los bits válidos del registro F (solo bits altos)
constexpr uint8_t REGISTER_F_MASK = 0xF0;

class CoreRegisters {
public:
    // Registros de 8 bits (acceso directo para máximo rendimiento)
    uint8_t a;
    uint8_t b;
    uint8_t c;
    uint8_t d;
    uint8_t e;
    uint8_t h;
    uint8_t l;
    uint8_t f;  // Flags (solo bits altos válidos)
    
    // Registros de 16 bits
    uint16_t pc;  // Program Counter
    uint16_t sp;  // Stack Pointer
    
    /**
     * Constructor: Inicializa todos los registros con valores Post-Boot DMG por defecto.
     */
    CoreRegisters();
    
    /**
     * Step 0411: Aplica estado Post-Boot según el modo de hardware.
     * 
     * Configura los registros según el estado que la Boot ROM deja después de ejecutarse:
     * - DMG: A=0x01, BC=0x0013, DE=0x00D8, HL=0x014D, SP=0xFFFE, PC=0x0100, F=0xB0
     * - CGB: A=0x11, BC=0x0000, DE=0xFF56, HL=0x000D, SP=0xFFFE, PC=0x0100, F=0x80
     * 
     * @param is_cgb_mode true para modo CGB, false para modo DMG
     * 
     * Fuente: Pan Docs - Power Up Sequence, Boot ROM Post-Boot State
     */
    void apply_post_boot_state(bool is_cgb_mode);
    
    // ========== Pares virtuales de 16 bits (inline para rendimiento) ==========
    
    /**
     * Obtiene el par AF (A en bits altos, F en bits bajos).
     * 
     * Aunque F solo tiene 4 bits válidos, se almacena completo
     * en el byte bajo del par de 16 bits.
     * 
     * @return Valor de 16 bits representando AF
     */
    inline uint16_t get_af() const {
        return (static_cast<uint16_t>(a) << 8) | f;
    }
    
    /**
     * Establece el par AF.
     * 
     * A partir de los bits altos, F mantiene su máscara (bits bajos = 0).
     * 
     * @param value Valor de 16 bits para establecer AF
     */
    inline void set_af(uint16_t value) {
        a = (value >> 8) & 0xFF;
        f = (value & 0xFF) & REGISTER_F_MASK;  // Aplicar máscara para F
    }
    
    /**
     * Obtiene el par BC (B en bits altos, C en bits bajos).
     * 
     * @return Valor de 16 bits representando BC
     */
    inline uint16_t get_bc() const {
        return (static_cast<uint16_t>(b) << 8) | c;
    }
    
    /**
     * Establece el par BC.
     * 
     * @param value Valor de 16 bits para establecer BC
     */
    inline void set_bc(uint16_t value) {
        b = (value >> 8) & 0xFF;
        c = value & 0xFF;
    }
    
    /**
     * Obtiene el par DE (D en bits altos, E en bits bajos).
     * 
     * @return Valor de 16 bits representando DE
     */
    inline uint16_t get_de() const {
        return (static_cast<uint16_t>(d) << 8) | e;
    }
    
    /**
     * Establece el par DE.
     * 
     * @param value Valor de 16 bits para establecer DE
     */
    inline void set_de(uint16_t value) {
        d = (value >> 8) & 0xFF;
        e = value & 0xFF;
    }
    
    /**
     * Obtiene el par HL (H en bits altos, L en bits bajos).
     * 
     * @return Valor de 16 bits representando HL
     */
    inline uint16_t get_hl() const {
        return (static_cast<uint16_t>(h) << 8) | l;
    }
    
    /**
     * Establece el par HL.
     * 
     * @param value Valor de 16 bits para establecer HL
     */
    inline void set_hl(uint16_t value) {
        h = (value >> 8) & 0xFF;
        l = value & 0xFF;
    }
    
    // ========== Helpers para Flags (inline para rendimiento) ==========
    
    /**
     * Obtiene el flag Zero (Z).
     * 
     * @return true si el flag Z está activo, false en caso contrario
     */
    inline bool get_flag_z() const {
        return (f & FLAG_Z) != 0;
    }
    
    /**
     * Establece el flag Zero (Z).
     * 
     * @param value true para activar, false para desactivar
     */
    inline void set_flag_z(bool value) {
        if (value) {
            f |= FLAG_Z;
        } else {
            f &= ~FLAG_Z;
        }
        f &= REGISTER_F_MASK;  // Asegurar máscara
    }
    
    /**
     * Obtiene el flag Subtract (N).
     * 
     * @return true si el flag N está activo, false en caso contrario
     */
    inline bool get_flag_n() const {
        return (f & FLAG_N) != 0;
    }
    
    /**
     * Establece el flag Subtract (N).
     * 
     * @param value true para activar, false para desactivar
     */
    inline void set_flag_n(bool value) {
        if (value) {
            f |= FLAG_N;
        } else {
            f &= ~FLAG_N;
        }
        f &= REGISTER_F_MASK;  // Asegurar máscara
    }
    
    /**
     * Obtiene el flag Half Carry (H).
     * 
     * @return true si el flag H está activo, false en caso contrario
     */
    inline bool get_flag_h() const {
        return (f & FLAG_H) != 0;
    }
    
    /**
     * Establece el flag Half Carry (H).
     * 
     * @param value true para activar, false para desactivar
     */
    inline void set_flag_h(bool value) {
        if (value) {
            f |= FLAG_H;
        } else {
            f &= ~FLAG_H;
        }
        f &= REGISTER_F_MASK;  // Asegurar máscara
    }
    
    /**
     * Obtiene el flag Carry (C).
     * 
     * @return true si el flag C está activo, false en caso contrario
     */
    inline bool get_flag_c() const {
        return (f & FLAG_C) != 0;
    }
    
    /**
     * Establece el flag Carry (C).
     * 
     * @param value true para activar, false para desactivar
     */
    inline void set_flag_c(bool value) {
        if (value) {
            f |= FLAG_C;
        } else {
            f &= ~FLAG_C;
        }
        f &= REGISTER_F_MASK;  // Asegurar máscara
    }
};

#endif // REGISTERS_HPP

