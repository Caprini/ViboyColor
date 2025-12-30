#include "Joypad.hpp"
#include "MMU.hpp"  // Step 0379: Necesario para solicitar interrupciones
#include <cstdio>   // Step 0379: Para logs de diagnóstico

Joypad::Joypad() : direction_keys_(0x0F), action_keys_(0x0F), p1_register_(0xFF), mmu_(nullptr) {
    // Inicializar todos los botones como "suelto" (bits a 1)
    // direction_keys_ = 0x0F (todos los bits 0-3 a 1 = todos sueltos)
    // action_keys_ = 0x0F (todos los bits 0-3 a 1 = todos sueltos)
    // p1_register_ = 0xFF (bits 6-7 a 1, bits 4-5 a 1 = ninguna fila seleccionada)
    // NOTA: Usamos 0xFF en lugar de 0xCF para que (p1_register_ & 0x10) y (p1_register_ & 0x20) no sean 0
    // mmu_ = nullptr (se establecerá mediante setMMU())
}

Joypad::~Joypad() {
    // No hay recursos dinámicos que liberar
}

uint8_t Joypad::read_p1() const {
    // El registro P1 tiene bits 6-7 siempre a 1 (no se usan)
    // Los bits 4-5 vienen de p1_register_ (selección de fila)
    // Los bits 0-3 dependen de qué fila esté seleccionada
    
    // Empezar con el valor base: bits 6-7 a 1, bits 0-3 a 1 (todos sueltos por defecto)
    uint8_t result = 0xCF; // 1100 1111
    
    // Si bit 4 = 0, se seleccionan los botones de dirección
    // (un bit a 0 en direction_keys_ significa botón presionado)
    if ((p1_register_ & 0x10) == 0) {
        // Bit 4 = 0: seleccionar fila de dirección
        // Construir resultado: bits 6-7=1, bit 4=0, bit 5=1, bits 0-3 desde direction_keys_
        // 0xC0 = bits 6-7=1, 0x20 = bit 5=1, pero 0xC0|0x20 = 0xE0 tiene bit 4=1
        // Necesitamos limpiar bit 4: 0xE0 & 0xDF = 0xC0 (incorrecto, pierde bit 5)
        // Solución: construir directamente 0xD0 (bits 6-7=1, bit 5=1, bit 4=0)
        result = 0xD0; // bits 6-7=1, bit 5=1, bit 4=0
        result |= (direction_keys_ & 0x0F); // bits 0-3 desde direction_keys_
    }
    // Si bit 5 = 0, se seleccionan los botones de acción
    // NOTA: Usamos else if porque solo una fila puede estar seleccionada a la vez
    else if ((p1_register_ & 0x20) == 0) {
        // Bit 5 = 0: seleccionar fila de acción
        // Construir resultado: bits 6-7=1, bit 4=0, bit 5=1, bits 0-3 desde action_keys_
        // NOTA: Los bits 4-5 se leen invertidos cuando se selecciona acción
        // 0xE0 = bits 6-7=1, bit 5=1, bit 4=0
        result = 0xE0; // bits 6-7=1, bit 5=1, bit 4=0
        result |= (action_keys_ & 0x0F); // bits 0-3 desde action_keys_
    }
    // Si ambos bits 4 y 5 son 1, ninguna fila está seleccionada
    // En este caso, todos los bits 0-3 leen como 1 (todos sueltos)
    // Esto ya está garantizado por el valor inicial de result (0xCF)
    
    return result;
}

void Joypad::write_p1(uint8_t value) {
    // Solo los bits 4 y 5 son escribibles
    // El resto se ignoran
    // Preservamos los bits 6-7 (siempre a 1) y actualizamos solo bits 4-5
    p1_register_ = (value & 0x30) | 0xC0; // 0x30 = bits 4-5, 0xC0 = bits 6-7 a 1
}

void Joypad::press_button(int button_index) {
    // Validar índice
    if (button_index < 0 || button_index > 7) {
        return; // Índice inválido, ignorar
    }
    
    // --- Step 0379: Guardar estado anterior para detectar "falling edge" ---
    uint8_t old_direction_keys = direction_keys_;
    uint8_t old_action_keys = action_keys_;
    // -------------------------------------------
    
    if (button_index < 4) {
        // Botones de dirección (0-3)
        // Poner el bit correspondiente a 0 (presionado)
        direction_keys_ &= ~(1 << button_index);
    } else {
        // Botones de acción (4-7)
        // Convertir a índice 0-3 dentro de action_keys_
        int action_index = button_index - 4;
        // Poner el bit correspondiente a 0 (presionado)
        action_keys_ &= ~(1 << action_index);
    }
    
    // --- Step 0379: Solicitar Interrupción de Joypad en "Falling Edge" ---
    // Según Pan Docs: "The Joypad Interrupt is requested when a button changes from high to low"
    // Es decir, cuando un botón pasa de 1 (suelto) a 0 (presionado).
    // 
    // Detectar falling edge:
    // - Estado anterior: bit = 1 (suelto)
    // - Estado nuevo: bit = 0 (presionado)
    // 
    // La interrupción se solicita SOLO si la fila correspondiente está seleccionada (P1 bit 4 o 5 = 0)
    bool direction_row_selected = (p1_register_ & 0x10) == 0;
    bool action_row_selected = (p1_register_ & 0x20) == 0;
    
    bool falling_edge_detected = false;
    
    if (button_index < 4) {
        // Botón de dirección
        // Falling edge: old_direction_keys tiene bit=1 y direction_keys_ tiene bit=0
        bool old_state = (old_direction_keys & (1 << button_index)) != 0;
        bool new_state = (direction_keys_ & (1 << button_index)) != 0;
        if (old_state && !new_state && direction_row_selected) {
            falling_edge_detected = true;
        }
    } else {
        // Botón de acción
        int action_index = button_index - 4;
        bool old_state = (old_action_keys & (1 << action_index)) != 0;
        bool new_state = (action_keys_ & (1 << action_index)) != 0;
        if (old_state && !new_state && action_row_selected) {
            falling_edge_detected = true;
        }
    }
    
    if (falling_edge_detected && mmu_ != nullptr) {
        // Solicitar interrupción de Joypad (bit 4, vector 0x0060)
        mmu_->request_interrupt(0x10);
        
        // Log temporal para diagnóstico (Step 0379)
        static int joypad_interrupt_log_count = 0;
        if (joypad_interrupt_log_count < 20) {
            joypad_interrupt_log_count++;
            printf("[JOYPAD-INT] Button %d pressed | Interrupt requested (bit 0x10, vector 0x0060) | Count: %d\n",
                   button_index, joypad_interrupt_log_count);
        }
    }
    // -------------------------------------------
}

void Joypad::release_button(int button_index) {
    // Validar índice
    if (button_index < 0 || button_index > 7) {
        return; // Índice inválido, ignorar
    }
    
    if (button_index < 4) {
        // Botones de dirección (0-3)
        // Poner el bit correspondiente a 1 (suelto)
        direction_keys_ |= (1 << button_index);
    } else {
        // Botones de acción (4-7)
        // Convertir a índice 0-3 dentro de action_keys_
        int action_index = button_index - 4;
        // Poner el bit correspondiente a 1 (suelto)
        action_keys_ |= (1 << action_index);
    }
    
    // --- Step 0379: NOTA sobre Interrupción al Soltar ---
    // Según Pan Docs, la interrupción de Joypad se solicita SOLO en "falling edge" (presionar),
    // NO en "rising edge" (soltar). Por lo tanto, no solicitamos interrupción aquí.
    // -------------------------------------------
}

void Joypad::setMMU(MMU* mmu) {
    // --- Step 0379: Establecer puntero a MMU para solicitar interrupciones ---
    mmu_ = mmu;
    
    // Log temporal para diagnóstico (Step 0379)
    static bool log_once = true;
    if (log_once && mmu_ != nullptr) {
        log_once = false;
        printf("[JOYPAD-INIT] MMU connected to Joypad | Interrupt requests enabled\n");
    }
    // -------------------------------------------
}

