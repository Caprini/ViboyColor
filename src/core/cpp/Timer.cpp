#include "Timer.hpp"

Timer::Timer() : div_counter_(0) {
    // Inicializar el contador interno a 0
    // En una Game Boy real, DIV inicia en un valor aleatorio,
    // pero para simplicidad lo inicializamos a 0
}

Timer::~Timer() {
    // No hay recursos dinámicos que liberar
}

void Timer::step(int t_cycles) {
    // Acumular los T-Cycles en el contador interno
    // El contador puede desbordarse (wrap-around), lo cual es correcto
    // ya que solo usamos los 8 bits altos para DIV
    div_counter_ += t_cycles;
    
    // Asegurar que el contador no exceda 16 bits (aunque en la práctica
    // puede ser mayor, solo usamos los bits relevantes)
    // No limitamos explícitamente para permitir wrap-around natural
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

