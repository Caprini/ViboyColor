#include "Joypad.hpp"
#include "MMU.hpp"  // Step 0379: Necesario para solicitar interrupciones
#include <cstdio>   // Step 0379: Para logs de diagnóstico

Joypad::Joypad() : direction_keys_(0x0F), action_keys_(0x0F), p1_register_(0xCF), mmu_(nullptr) {
    // --- Step 0425: Inicialización spec-correct según Pan Docs ---
    // Inicializar todos los botones como "suelto" (bits a 1)
    // direction_keys_ = 0x0F (todos los bits 0-3 a 1 = todos sueltos)
    // action_keys_ = 0x0F (todos los bits 0-3 a 1 = todos sueltos)
    // p1_register_ = 0xCF (bits 6-7 a 1, bits 4-5 a 0 = ninguna fila seleccionada)
    // Pan Docs: bits 4-5 = 0 cuando no hay selección (valor típico inicial)
    // mmu_ = nullptr (se establecerá mediante setMMU())
    // -------------------------------------------
    
    // --- Step 0381: Log de creación de instancia ---
    printf("[JOYPAD-CONSTRUCTOR] Nueva instancia de Joypad creada en %p\n", (void*)this);
    // -------------------------------------------
}

Joypad::~Joypad() {
    // No hay recursos dinámicos que liberar
}

uint8_t Joypad::read_p1() const {
    // --- Step 0483: Lectura spec-correct de P1 (FF00) según Pan Docs ---
    // Pan Docs: "Both lines may be selected at the same time, in that case the button
    // state is a logic AND of both line states."
    // 
    // Estructura del registro P1:
    // - Bits 7-6: siempre 1 (no usados, implementado en MMU::read(0xFF00))
    // - Bit 5 (P15): 0 = selecciona botones de acción (A, B, Select, Start)
    // - Bit 4 (P14): 0 = selecciona botones de dirección (Right, Left, Up, Down)
    // - Bits 3-0: estado de botones (0 = presionado, 1 = suelto) [read-only]
    //
    // Los bits 4-5 se leen TAL COMO fueron escritos (NO se invierten).
    // -------------------------------------------
    
    uint8_t result = 0xFF;  // Default: todos los bits en 1
    
    // Obtener selección (bits 4-5): bit=0 selecciona (active-low)
    bool select_buttons = !(p1_register_ & 0x10);  // P14 = bit 4 (invertido: 0 = seleccionado)
    bool select_dpad = !(p1_register_ & 0x20);     // P15 = bit 5 (invertido: 0 = seleccionado)
    
    uint8_t low_nibble = 0x0F;  // Default: todos los bits en 1 (no pulsados)
    
    if (select_buttons && select_dpad) {
        // Ambos grupos seleccionados: AND de ambos estados
        low_nibble = action_keys_ & direction_keys_;
    } else if (select_buttons) {
        // Solo botones seleccionados (P14=0)
        low_nibble = action_keys_;
    } else if (select_dpad) {
        // Solo direcciones seleccionadas (P15=0)
        low_nibble = direction_keys_;
    } else {
        // Ningún grupo seleccionado: todos los bits en 1
        low_nibble = 0x0F;
    }
    
    // Combinar: bits 4-5 de p1_register_ (preservar selección), bits 0-3 del estado, bits 6-7 en 1
    result = (p1_register_ & 0xF0) | (low_nibble & 0x0F);
    // Bits 6-7 se pondrán a 1 en MMU::read(0xFF00)
    
    // --- Step 0381: Instrumentación de Lectura de P1 con Estado de Botones ---
    static int read_p1_log_count = 0;
    if (read_p1_log_count < 500) {  // Aumentado de 100 a 500 para capturar frames 60-150
        read_p1_log_count++;
        printf("[JOYPAD-READ-P1] Instance=%p | direction_keys=0x%02X action_keys=0x%02X | "
               "Dir_sel=%s Act_sel=%s | nibble=0x%02X result=0x%02X\n",
               (void*)this, direction_keys_, action_keys_,
                select_dpad ? "YES" : "NO",
                select_buttons ? "YES" : "NO",
                low_nibble, result);
    }
    // -------------------------------------------
    
    return result;
}

void Joypad::write_p1(uint8_t value) {
    // Solo los bits 4 y 5 son escribibles
    // El resto se ignoran
    // Preservamos los bits 6-7 (siempre a 1) y actualizamos solo bits 4-5
    uint8_t old_p1 = p1_register_;
    p1_register_ = (value & 0x30) | 0xC0; // 0x30 = bits 4-5, 0xC0 = bits 6-7 a 1
    
    // --- Step 0380: Instrumentación de Selección de Filas ---
    static int p1_select_count = 0;
    if (p1_select_count < 50 || (old_p1 != p1_register_)) {
        if (p1_select_count < 50) {
            p1_select_count++;
        }
        bool direction_row_selected = (p1_register_ & 0x10) == 0;
        bool action_row_selected = (p1_register_ & 0x20) == 0;
        
        printf("[JOYPAD-P1-SELECT] P1 = 0x%02X | Direction=%s Action=%s\n",
               p1_register_,
               direction_row_selected ? "SEL" : "---",
               action_row_selected ? "SEL" : "---");
    }
    // -------------------------------------------
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
    
    // --- Step 0381: Log ANTES de modificar ---
    printf("[JOYPAD-PRESS-BEFORE] Instance=%p | Button %d | direction_keys=0x%02X action_keys=0x%02X\n",
           (void*)this, button_index, direction_keys_, action_keys_);
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
    
    // --- Step 0381: Log DESPUÉS de modificar ---
    printf("[JOYPAD-PRESS-AFTER] Button %d | direction_keys=0x%02X action_keys=0x%02X\n",
           button_index, direction_keys_, action_keys_);
    // -------------------------------------------
    
    // --- Step 0379/0380: Solicitar Interrupción de Joypad en "Falling Edge" ---
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
    
    // --- Step 0380: Instrumentación de Eventos de Entrada ---
    static int joypad_event_count = 0;
    if (joypad_event_count < 50) {
        joypad_event_count++;
        printf("[JOYPAD-EVENT] Button %d pressed | Direction_row=%s Action_row=%s | "
               "Falling_edge=%s | IRQ_requested=%s\n",
               button_index,
               direction_row_selected ? "SEL" : "---",
               action_row_selected ? "SEL" : "---",
               falling_edge_detected ? "YES" : "NO",
               (falling_edge_detected && mmu_ != nullptr) ? "YES" : "NO");
    }
    // -------------------------------------------
    
    if (falling_edge_detected && mmu_ != nullptr) {
        // Solicitar interrupción de Joypad (bit 4, vector 0x0060)
        mmu_->request_interrupt(0x10);
        
        // Log temporal para diagnóstico (Step 0379/0380)
        static int joypad_interrupt_log_count = 0;
        if (joypad_interrupt_log_count < 20) {
            joypad_interrupt_log_count++;
            printf("[JOYPAD-IRQ] Button %d pressed | Interrupt requested (bit 0x10, vector 0x0060) | Count: %d\n",
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

