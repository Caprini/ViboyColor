#include "Timer.hpp"
#include "MMU.hpp"
#include <cstdio>

Timer::Timer(MMU* mmu) : mmu_(mmu), div_counter_(0), tima_counter_(0), tima_(0), tma_(0), tac_(0) {
    // Inicializar el contador interno a 0
    // En una Game Boy real, DIV inicia en un valor aleatorio,
    // pero para simplicidad lo inicializamos a 0
    // TIMA, TMA y TAC se inicializan a 0 (Timer desactivado por defecto)
}

Timer::~Timer() {
    // No hay recursos dinámicos que liberar
    // MMU es propiedad de otra clase, no se libera aquí
}

void Timer::step(int t_cycles) {
    // Actualizar DIV: acumular los T-Cycles en el contador interno
    // El contador puede desbordarse (wrap-around), lo cual es correcto
    // ya que solo usamos los 8 bits altos para DIV
    div_counter_ += t_cycles;
    
    // Actualizar TIMA si el Timer está activado (TAC bit 2)
    if ((tac_ & 0x04) != 0) {
        tima_counter_ += t_cycles;
        int threshold = get_tima_threshold();

        // Manejar múltiples incrementos si los T-Cycles exceden el threshold
        // (puede ocurrir si una instrucción toma muchos ciclos)
        while (tima_counter_ >= threshold) {
            tima_counter_ -= threshold;
            
            // Incrementar TIMA, manejando el desbordamiento
            if (tima_ == 0xFF) {
                // --- Step 0384: Instrumentar Timer IRQ ---
                uint8_t tima_before = tima_;
                uint8_t tma_value = tma_;
                
                // TIMA desborda: recargar con TMA y solicitar interrupción
                tima_ = tma_;
                
                // Solicitar interrupción de Timer (bit 2 del registro IF)
                if (mmu_ != nullptr) {
                    uint8_t if_before = mmu_->read(0xFF0F);
                    mmu_->request_interrupt(2);
                    uint8_t if_after = mmu_->read(0xFF0F);
                    
                    // Loggear (límite: 30 líneas)
                    static int timer_irq_log = 0;
                    if (timer_irq_log < 30) {
                        printf("[TIMER-IRQ] TIMA overflow | TIMA:0x%02X->0x%02X (TMA) | "
                               "IF: 0x%02X->0x%02X\n",
                               tima_before, tma_value, if_before, if_after);
                        timer_irq_log++;
                    }
                }
                // -------------------------------------------
            } else {
                // Incremento normal de TIMA
                tima_++;
            }
        }
    }
}

uint8_t Timer::read_div() const {
    // DIV es los 8 bits altos del contador interno de 16 bits
    // Dividimos por 256 (equivalente a shift right 8 bits)
    // y enmascaramos a 8 bits
    return (div_counter_ >> 8) & 0xFF;
}

void Timer::write_div() {
    // Cualquier escritura en 0xFF04 resetea el contador a 0
    // El valor escrito es ignorado (no se pasa como parámetro)
    div_counter_ = 0;
}

void Timer::write_tima(uint8_t value) {
    // --- Step 0384: Log de configuración de TIMA ---
    static int tima_write_log = 0;
    if (tima_write_log < 20) {
        printf("[TIMER-CFG] TIMA write: 0x%02X\n", value);
        tima_write_log++;
    }
    // -------------------------------------------
    tima_ = value;
}

void Timer::write_tac(uint8_t value) {
    // --- Step 0384: Log de configuración de TAC ---
    static int tac_write_log = 0;
    if (tac_write_log < 20) {
        bool enabled = (value & 0x04) != 0;
        int freq_select = value & 0x03;
        const char* freq_names[] = {"4096Hz", "262144Hz", "65536Hz", "16384Hz"};
        
        printf("[TIMER-CFG] TAC write: 0x%02X | Enabled:%s | Freq:%s\n",
               value, enabled ? "YES" : "NO", freq_names[freq_select]);
        tac_write_log++;
    }
    // -------------------------------------------
    tac_ = value;
}

int Timer::get_tima_threshold() const {
    // Obtener la frecuencia seleccionada de los bits 1-0 de TAC
    // El threshold es el número de T-Cycles necesarios para incrementar TIMA una vez
    switch (tac_ & 0x03) {
        case 0: return 1024;  // 4096 Hz: 4194304 / 4096 = 1024 T-Cycles
        case 1: return 16;    // 262144 Hz: 4194304 / 262144 = 16 T-Cycles
        case 2: return 64;    // 65536 Hz: 4194304 / 65536 = 64 T-Cycles
        case 3: return 256;   // 16384 Hz: 4194304 / 16384 = 256 T-Cycles
        default: return 1024; // Default (nunca debería llegar aquí)
    }
}

