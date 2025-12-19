#include "PPU.hpp"
#include "MMU.hpp"

PPU::PPU(MMU* mmu) 
    : mmu_(mmu)
    , ly_(0)
    , clock_(0)
    , mode_(MODE_2_OAM_SEARCH)
    , frame_ready_(false)
    , lyc_(0)
    , stat_interrupt_line_(false)
{
    // Inicialización completa en lista de inicialización
}

PPU::~PPU() {
    // No hay recursos dinámicos que liberar
    // (mmu_ es un puntero que no poseemos)
}

void PPU::step(int cpu_cycles) {
    // CRÍTICO: Verificar si el LCD está encendido (LCDC bit 7)
    // Si el LCD está apagado, la PPU se detiene y LY se mantiene en 0
    uint8_t lcdc = mmu_->read(IO_LCDC);
    bool lcd_enabled = (lcdc & 0x80) != 0;
    
    if (!lcd_enabled) {
        // LCD apagado: PPU detenida, LY se mantiene en 0
        // No acumulamos ciclos ni avanzamos líneas
        return;
    }
    
    // Acumular ciclos en el clock interno (solo si el LCD está encendido)
    clock_ += cpu_cycles;
    
    // Actualizar el modo PPU según el punto actual en la línea
    // Esto debe hacerse ANTES de procesar líneas completas
    update_mode();
    
    // Guardar LY y modo anteriores para detectar cambios
    uint16_t old_ly = ly_;
    uint8_t old_mode = mode_;
    
    // Mientras tengamos suficientes ciclos para completar una línea (456 T-Cycles)
    while (clock_ >= CYCLES_PER_SCANLINE) {
        // Restar los ciclos de una línea completa
        clock_ -= CYCLES_PER_SCANLINE;
        
        // Avanzar a la siguiente línea
        ly_ += 1;
        
        // Al inicio de cada nueva línea, el modo es Mode 2 (OAM Search)
        // Se actualizará automáticamente en la siguiente llamada a update_mode()
        mode_ = MODE_2_OAM_SEARCH;
        
        // CRÍTICO: Cuando LY cambia, reiniciar el flag de interrupción STAT
        // Esto permite que se dispare una nueva interrupción si las condiciones
        // se cumplen en la nueva línea
        stat_interrupt_line_ = false;
        
        // Si llegamos a V-Blank (línea 144), solicitar interrupción y marcar frame listo
        if (ly_ == VBLANK_START) {
            // CRÍTICO: Activar bit 0 del registro IF (Interrupt Flag) en 0xFF0F
            // Este bit corresponde a la interrupción V-Blank.
            //
            // IMPORTANTE: IF se actualiza SIEMPRE cuando ocurre V-Blank,
            // INDEPENDIENTEMENTE del estado de IME (Interrupt Master Enable).
            uint8_t if_val = mmu_->read(IO_IF);
            if_val |= 0x01;  // Set bit 0 (V-Blank interrupt)
            mmu_->write(IO_IF, if_val);
            
            // CRÍTICO: Marcar frame como listo para renderizar
            frame_ready_ = true;
        }
        
        // Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
        if (ly_ > 153) {
            ly_ = 0;
            // Reiniciar flag de interrupción STAT al cambiar de frame
            stat_interrupt_line_ = false;
        }
    }
    
    // Actualizar el modo después de procesar líneas completas
    // (por si quedaron ciclos residuales en la línea actual)
    update_mode();
    
    // Verificar interrupciones STAT si LY cambió o el modo cambió
    if (ly_ != old_ly || mode_ != old_mode) {
        check_stat_interrupt();
    }
}

void PPU::update_mode() {
    // Si estamos en V-Blank (líneas 144-153), siempre Mode 1
    if (ly_ >= VBLANK_START) {
        mode_ = MODE_1_VBLANK;
    } else {
        // Para líneas visibles (0-143), el modo depende de los ciclos dentro de la línea
        // clock_ es el contador de ciclos dentro de la línea actual (0-455)
        // Enmascaramos a uint16_t para la comparación (solo necesitamos los últimos 456 ciclos)
        uint16_t line_cycles = static_cast<uint16_t>(clock_ % CYCLES_PER_SCANLINE);
        
        if (line_cycles < MODE_2_CYCLES) {
            // Primeros 80 ciclos: Mode 2 (OAM Search)
            mode_ = MODE_2_OAM_SEARCH;
        } else if (line_cycles < (MODE_2_CYCLES + MODE_3_CYCLES)) {
            // Siguientes 172 ciclos (80-251): Mode 3 (Pixel Transfer)
            mode_ = MODE_3_PIXEL_TRANSFER;
        } else {
            // Resto (252-455): Mode 0 (H-Blank)
            mode_ = MODE_0_HBLANK;
        }
    }
}

void PPU::check_stat_interrupt() {
    // Leer el registro STAT directamente de memoria
    // Solo leemos los bits configurables (3-7), los bits 0-2 se actualizan dinámicamente
    uint8_t stat_value = mmu_->read(IO_STAT);
    
    // Inicializar señal de interrupción
    bool signal = false;
    
    // Verificar LYC=LY Coincidence (bit 2 y bit 6)
    bool lyc_match = (ly_ & 0xFF) == (lyc_ & 0xFF);
    
    // Actualizar bit 2 de STAT dinámicamente (LYC=LY Coincidence Flag)
    // Preservamos los bits configurables (3-7) y actualizamos bits 0-2
    if (lyc_match) {
        // Set bit 2 de STAT (LYC=LY Coincidence Flag)
        stat_value = (stat_value & 0xF8) | mode_ | 0x04;  // Set bit 2
        mmu_->write(IO_STAT, stat_value);
        
        // Si el bit 6 (LYC Int Enable) está activo, solicitar interrupción
        if ((stat_value & 0x40) != 0) {  // Bit 6 activo
            signal = true;
        }
    } else {
        // Si LY != LYC, el bit 2 debe estar limpio
        stat_value = (stat_value & 0xF8) | mode_;  // Clear bit 2
        mmu_->write(IO_STAT, stat_value);
    }
    
    // Verificar interrupciones por modo PPU
    if (mode_ == MODE_0_HBLANK && (stat_value & 0x08) != 0) {  // Bit 3 activo
        signal = true;
    } else if (mode_ == MODE_1_VBLANK && (stat_value & 0x10) != 0) {  // Bit 4 activo
        signal = true;
    } else if (mode_ == MODE_2_OAM_SEARCH && (stat_value & 0x20) != 0) {  // Bit 5 activo
        signal = true;
    }
    
    // Disparar interrupción en rising edge (solo si signal es True y antes era False)
    if (signal && !stat_interrupt_line_) {
        // Activar bit 1 del registro IF (Interrupt Flag) en 0xFF0F
        // Este bit corresponde a la interrupción LCD STAT
        uint8_t if_val = mmu_->read(IO_IF);
        if_val |= 0x02;  // Set bit 1 (LCD STAT interrupt)
        mmu_->write(IO_IF, if_val);
    }
    
    // Actualizar flag de interrupción STAT
    stat_interrupt_line_ = signal;
}

uint8_t PPU::get_ly() const {
    return static_cast<uint8_t>(ly_ & 0xFF);
}

uint8_t PPU::get_mode() const {
    return mode_;
}

uint8_t PPU::get_lyc() const {
    return lyc_;
}

void PPU::set_lyc(uint8_t value) {
    uint8_t old_lyc = lyc_;
    lyc_ = value & 0xFF;
    
    // Si LYC cambió, verificar interrupciones STAT inmediatamente
    // (el bit 2 de STAT puede cambiar si LY == nuevo LYC)
    if (lyc_ != old_lyc) {
        check_stat_interrupt();
    }
}

bool PPU::is_frame_ready() {
    if (frame_ready_) {
        frame_ready_ = false;
        return true;
    }
    return false;
}

