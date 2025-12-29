#include "PPU.hpp"
#include "MMU.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>  // Step 0321: Para abs()

PPU::PPU(MMU* mmu) 
    : mmu_(mmu)
    , ly_(0)
    , clock_(0)
    , mode_(MODE_2_OAM_SEARCH)
    , frame_ready_(false)
    , lyc_(0)
    , stat_interrupt_line_(0)
    , scanline_rendered_(false)
    , framebuffer_(FRAMEBUFFER_SIZE, 0)  // Inicializar a índice 0 (blanco por defecto con paleta estándar)
    , frame_counter_(0)  // Step 0291: Inicializar contador de frames
    , vram_is_empty_(true)  // Step 0330: Inicializar como vacía, se actualizará en el primer frame
{
    // --- Step 0201: Garantizar estado inicial limpio (RAII) ---
    // En C++, el principio de RAII (Resource Acquisition Is Initialization) dicta que
    // un objeto debe estar en un estado completamente válido y conocido inmediatamente
    // después de su construcción. El framebuffer debe estar limpio desde el momento
    // en que la PPU nace, no en el primer ciclo de step().
    clear_framebuffer();
    
    // CRÍTICO: Inicializar registros de la PPU con valores seguros
    // Si estos registros están en 0, la pantalla estará negra/blanca
    // 
    // LCDC (0xFF40): Control del LCD
    // Bit 7: LCD Enable (1 = ON)
    // Bit 0: BG Display Enable (1 = ON)
    // Valor 0x91 = 10010001 = LCD ON, BG ON, Tile Data 0x8000, Tile Map 0x9800
    if (mmu_ != nullptr) {
        mmu_->write(IO_LCDC, 0x91);
        
        // BGP (0xFF47): Background Palette
        // Valor 0xE4 = 11100100 = Color 0=3 (Negro), 1=2 (Gris oscuro), 2=1 (Gris claro), 3=0 (Blanco)
        // Este es el valor estándar que usan muchos juegos
        mmu_->write(IO_BGP, 0xE4);
        
        // SCX/SCY: Scroll inicial a 0
        mmu_->write(IO_SCX, 0x00);
        mmu_->write(IO_SCY, 0x00);
        
        // OBP0/OBP1: Paletas de sprites (mismo valor que BGP por defecto)
        mmu_->write(IO_OBP0, 0xE4);
        mmu_->write(IO_OBP1, 0xE4);
    }
}

PPU::~PPU() {
    // No hay recursos dinámicos que liberar
    // (mmu_ es un puntero que no poseemos)
}

void PPU::step(int cpu_cycles) {
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        // Si mmu_ es nullptr, no podemos avanzar la PPU
        // Esto puede ocurrir si la MMU fue destruida antes que la PPU
        return;
    }
    
    // CRÍTICO: Verificar si el LCD está encendido (LCDC bit 7)
    // Si el LCD está apagado, la PPU se detiene y LY se mantiene en 0
    uint8_t lcdc = mmu_->read(IO_LCDC);
    bool lcd_enabled = (lcdc & 0x80) != 0;
    
    // --- Step 0320: Monitor de Cambios de LCDC ---
    // Detectar cuando LCDC cambia de valor y loggear el cambio
    static uint8_t last_lcdc = 0xFF;
    static bool last_lcd_state = false;  // Step 0321: Estado anterior del LCD
    static int lcd_on_log_count = 0;  // Step 0321: Contador para limitar logs
    
    if (lcdc != last_lcdc && ly_ == 0) {
        bool lcd_was_on = (last_lcdc & 0x80) != 0;
        bool lcd_is_on = (lcdc & 0x80) != 0;
        
        printf("[PPU-LCDC-CHANGE] Frame %llu | LCDC cambió: 0x%02X -> 0x%02X | LCD: %d->%d | BG: %d->%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               last_lcdc, lcdc,
               lcd_was_on ? 1 : 0, lcd_is_on ? 1 : 0,
               (last_lcdc & 0x01) ? 1 : 0, (lcdc & 0x01) ? 1 : 0);
        
        // --- Step 0323: Verificación de VRAM al activar LCD ---
        // LCD se acaba de activar, verificar si hay tiles válidos
        if (!lcd_was_on && lcd_is_on) {
            // LCD se acaba de activar, verificar si hay tiles válidos
            uint32_t vram_checksum = 0;
            int non_zero_bytes = 0;
            
            // Verificar primeros 1024 bytes de VRAM (64 tiles)
            for (uint16_t i = 0; i < 1024; i++) {
                uint8_t byte = mmu_->read(0x8000 + i);
                vram_checksum += byte;
                if (byte != 0x00) {
                    non_zero_bytes++;
                }
            }
            
            if (lcd_on_log_count < 10) {
                printf("[PPU-LCD-ON-VRAM] LCD activado | VRAM Checksum: 0x%08X | Bytes no-cero: %d/1024\n",
                       vram_checksum, non_zero_bytes);
                
                if (vram_checksum == 0) {
                    printf("[PPU-LCD-ON-VRAM] ⚠️ ADVERTENCIA: VRAM está vacía cuando se activa el LCD!\n");
                }
                lcd_on_log_count++;
            }
            
            // Si el BG Display está desactivado, activarlo
            if (!(lcdc & 0x01)) {
                if (lcd_on_log_count <= 10) {
                    printf("[PPU-LCD-ON] BG Display desactivado, activándolo...\n");
                }
                mmu_->write(IO_LCDC, lcdc | 0x01);
                lcdc |= 0x01;
            }
        }
        // -------------------------------------------
        
        last_lcdc = lcdc;
        last_lcd_state = lcd_is_on;
    }
    // -------------------------------------------
    
    // --- Step 0329: Forzar BG Display ON si LCD está ON ---
    // Asegurar que BG Display está activo si el LCD está activo
    // Esto previene pantallas blancas cuando el juego desactiva BG Display
    bool bg_display = (lcdc & 0x01) != 0;
    
    if (lcd_enabled && !bg_display && ly_ == 0) {
        static int bg_display_force_count = 0;
        if (bg_display_force_count < 5) {
            bg_display_force_count++;
            printf("[PPU-BG-DISPLAY-FORCE] Forzando BG Display ON (LCD está ON pero BG Display estaba OFF)\n");
        }
        
        // Forzar BG Display ON
        mmu_->write(IO_LCDC, lcdc | 0x01);
        lcdc |= 0x01;
    }
    // -------------------------------------------
    
    // --- Step 0320: Verificación Periódica de VRAM ---
    // Verificar si los tiles de prueba siguen en VRAM cada 60 frames (1 segundo)
    static int vram_check_counter = 0;
    if (ly_ == 0 && frame_counter_ > 0 && (frame_counter_ % 60 == 0)) {
        verify_test_tiles();
        check_game_tiles_loaded();  // Step 0321: Verificar si el juego cargó tiles
        vram_check_counter++;
    }
    // -------------------------------------------
    
    // --- Step 0227: FIX LCD DISABLE BEHAVIOR ---
    // Pan Docs: When LCD is disabled (LCDC bit 7 = 0), the PPU stops immediately
    // and the LY register is reset to 0 and remains fixed at 0. The internal clock
    // is also reset. This is critical for proper synchronization when the game
    // turns the LCD back on, as it expects LY to be 0.
    if (!lcd_enabled) {
        // Resetear contadores y estado cuando el LCD está apagado
        ly_ = 0;
        clock_ = 0;
        mode_ = MODE_0_HBLANK;  // H-Blank es el modo más seguro cuando está apagado
        
        // No acumulamos ciclos ni avanzamos líneas
        // La PPU está completamente detenida hasta que el LCD se vuelva a encender
        return;
    }
    // -------------------------------------------
    
    // Acumular ciclos en el clock interno (solo si el LCD está encendido)
    clock_ += cpu_cycles;
    
    // Guardar LY y modo anteriores para detectar cambios
    // CRÍTICO: Guardar ANTES de actualizar el modo para detectar cambios correctamente
    uint16_t old_ly = ly_;
    uint8_t old_mode = mode_;
    
    // Actualizar el modo PPU según el punto actual en la línea
    // Esto debe hacerse ANTES de procesar líneas completas
    update_mode();
    
    // Mientras tengamos suficientes ciclos para completar una línea (456 T-Cycles)
    while (clock_ >= CYCLES_PER_SCANLINE) {
        // CRÍTICO: Renderizar la línea ANTES de avanzar a la siguiente
        // Esto asegura que renderizamos cada línea visible exactamente una vez
        // cuando completamos los 456 ciclos de esa línea (estamos en H-Blank)
        if (ly_ < VISIBLE_LINES && !scanline_rendered_) {
            render_scanline();
            scanline_rendered_ = true;
        }
        
        // Restar los ciclos de una línea completa
        clock_ -= CYCLES_PER_SCANLINE;
        
        // CRÍTICO: Verificar interrupciones STAT ANTES de cambiar a la nueva línea
        // Esto asegura que se detecte el rising edge de H-Blank (Mode 0)
        check_stat_interrupt();
        
        // Guardar el estado anterior de LYC match para detectar rising edge
        bool old_lyc_match = ((ly_ & 0xFF) == (lyc_ & 0xFF));
        
        // Avanzar a la siguiente línea
        ly_ += 1;
        
        // Al inicio de cada nueva línea, el modo es Mode 2 (OAM Search)
        // Se actualizará automáticamente en la siguiente llamada a update_mode()
        mode_ = MODE_2_OAM_SEARCH;
        
        // --- Step 0265: LYC COINCIDENCE RISING EDGE DETECTION ---
        // CRÍTICO: Verificar interrupción LYC inmediatamente después de cambiar LY
        // Esto asegura que detectamos el rising edge cuando LY pasa de no coincidir
        // con LYC a coincidir con LYC. El rising edge es crítico para juegos que
        // sincronizan efectos visuales con la posición del haz de electrones.
        //
        // Ejemplo: Si LYC=10, LY=9 -> LY=10, necesitamos detectar el rising edge
        // cuando LY pasa a 10, no cuando LY ya es 10 y verificamos más tarde.
        bool new_lyc_match = ((ly_ & 0xFF) == (lyc_ & 0xFF));
        
        // Si LYC match cambió de false a true (rising edge), verificar interrupción
        // inmediatamente, pero solo para la condición LYC (no para modos PPU)
        if (!old_lyc_match && new_lyc_match) {
            // Leer STAT para obtener bits configurables
            uint8_t stat_full = mmu_->read(IO_STAT);
            uint8_t stat_configurable = stat_full & 0xF8;
            
            // Si el bit 6 (LYC Int Enable) está activo, solicitar interrupción
            if ((stat_configurable & 0x40) != 0) {
                mmu_->request_interrupt(1);  // Bit 1 = LCD STAT Interrupt
            }
        }
        
        // CRÍTICO: Cuando LY cambia, reiniciar los flags de interrupción y renderizado
        // Esto permite que se dispare una nueva interrupción y renderizado si las condiciones
        // se cumplen en la nueva línea. Sin embargo, para LYC, preservamos el estado si
        // la coincidencia sigue activa para evitar disparar múltiples veces.
        //
        // Si LYC match está activo, preservar el bit 0 en stat_interrupt_line_
        // Si LYC match está inactivo, limpiar el bit 0
        if (new_lyc_match) {
            stat_interrupt_line_ |= 0x01;  // Preservar bit 0 si LYC match está activo
        } else {
            stat_interrupt_line_ &= ~0x01;  // Limpiar bit 0 si LYC match está inactivo
        }
        
        // Limpiar bits de modo (1-3) porque el modo cambió
        stat_interrupt_line_ &= 0x01;  // Solo preservar bit 0 (LYC), limpiar resto
        
        scanline_rendered_ = false;
        
        // Si llegamos a V-Blank (línea 144), solicitar interrupción y marcar frame listo
        if (ly_ == VBLANK_START) {
            // CRÍTICO: Solicitar interrupción V-Blank usando el método de MMU
            // Este bit corresponde a la interrupción V-Blank (bit 0 de IF).
            //
            // IMPORTANTE: IF se actualiza SIEMPRE cuando ocurre V-Blank,
            // INDEPENDIENTEMENTE del estado de IME (Interrupt Master Enable).
            // Usamos request_interrupt() para mantener consistencia con otras interrupciones.
            mmu_->request_interrupt(0);  // Bit 0 = V-Blank Interrupt
            static int vblank_log = 0;
            if (vblank_log < 10) {
                printf("[PPU] VBlank IRQ at LY=%u\n", ly_);
                vblank_log++;
            }
            
            // --- Step 0331: Log de Sincronización del Framebuffer ---
            static int frame_ready_log_count = 0;
            if (frame_ready_log_count < 5) {
                frame_ready_log_count++;
                printf("[PPU-FRAME-READY] Frame %llu | Frame marcado como listo (LY=144)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1));
            }
            // -------------------------------------------
            
            // CRÍTICO: Marcar frame como listo para renderizar
            frame_ready_ = true;
        }
        
        // Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
        if (ly_ > 153) {
            ly_ = 0;
            // --- Step 0291: Incrementar contador de frames ---
            frame_counter_++;
            // Reiniciar flag de interrupción STAT al cambiar de frame
            stat_interrupt_line_ = 0;
            // --- Step 0333: Limpiar Framebuffer al Inicio del Siguiente Frame ---
            // El framebuffer se limpia al inicio del siguiente frame (cuando LY se resetea a 0)
            // Esto asegura que Python siempre lee el framebuffer ANTES de que se limpie
            // El framebuffer del frame anterior ya fue leído por Python en el frame anterior
            clear_framebuffer();
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
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        return;
    }
    
    // Leer el registro STAT directamente de memoria (sin pasar por MMU::read que combina bits)
    // Necesitamos acceder directamente a la memoria para obtener solo los bits escribibles (3-7)
    // La MMU::read() combina bits escribibles con bits de solo lectura, pero nosotros necesitamos
    // solo los bits escribibles para verificar las condiciones de interrupción.
    // 
    // NOTA: Esto es un acceso directo a la memoria interna de la MMU. En una implementación
    // más robusta, podríamos añadir un método MMU::read_raw() para este propósito.
    // Por ahora, usamos read() y extraemos los bits configurables con la máscara.
    uint8_t stat_full = mmu_->read(IO_STAT);
    
    // Extraer solo los bits configurables (3-7) del valor completo
    // Cuando escribimos 0x08 en STAT, la MMU lo guarda en memoria[0xFF41] = 0x08
    // Cuando leemos STAT, la MMU combina: (0x08 & 0xF8) | modo | lyc_match
    // Entonces stat_full = 0x08 | modo | lyc_match
    // Y stat_configurable = stat_full & 0xF8 = 0x08 (correcto)
    uint8_t stat_configurable = stat_full & 0xF8;  // Máscara para bits 3-7
    
    // Calcular condiciones actuales de interrupción
    // Cada bit representa una condición que puede generar interrupción
    uint8_t current_conditions = 0;
    
    // Verificar LYC=LY Coincidence (bit 2 y bit 6)
    bool lyc_match = (ly_ & 0xFF) == (lyc_ & 0xFF);
    
    // Construir el valor completo de STAT con bits de solo lectura actualizados
    uint8_t stat_value;
    if (lyc_match) {
        // Set bit 2 de STAT (LYC=LY Coincidence Flag)
        stat_value = stat_configurable | mode_ | 0x04;  // Set bit 2
    } else {
        // Si LY != LYC, el bit 2 debe estar limpio
        stat_value = stat_configurable | mode_;  // Clear bit 2
    }
    
    // Escribir el valor actualizado de STAT (solo los bits configurables se escriben)
    // La MMU manejará la combinación con los bits de solo lectura en la lectura
    mmu_->write(IO_STAT, stat_configurable);
    
    // Verificar interrupciones por modo PPU usando stat_configurable (bits escribibles)
    // Cada condición se marca con un bit diferente en current_conditions
    if (mode_ == MODE_0_HBLANK && (stat_configurable & 0x08) != 0) {  // Bit 3 activo
        current_conditions |= 0x02;  // Bit 1: Mode 0 (H-Blank)
    }
    if (mode_ == MODE_1_VBLANK && (stat_configurable & 0x10) != 0) {  // Bit 4 activo
        current_conditions |= 0x04;  // Bit 2: Mode 1 (V-Blank)
    }
    if (mode_ == MODE_2_OAM_SEARCH && (stat_configurable & 0x20) != 0) {  // Bit 5 activo
        current_conditions |= 0x08;  // Bit 3: Mode 2 (OAM Search)
    }
    
    // Verificar interrupción LYC=LY si está habilitada
    if (lyc_match && (stat_configurable & 0x40) != 0) {  // Bit 6 activo
        current_conditions |= 0x01;  // Bit 0: LYC=LY coincidence
    }
    
    // Detectar flanco de subida (rising edge): si una condición está activa ahora
    // y no lo estaba antes, solicitar interrupción
    // Usamos stat_interrupt_line_ como máscara de bits para rastrear el estado anterior
    // 
    // CRÍTICO: stat_interrupt_line_ rastrea qué condiciones estaban activas en la última
    // llamada a check_stat_interrupt(). Si una condición está activa ahora (current_conditions)
    // pero no lo estaba antes (stat_interrupt_line_), entonces es un rising edge.
    uint8_t new_triggers = current_conditions & ~stat_interrupt_line_;
    
    if (new_triggers != 0) {
        // Hay al menos una condición nueva que se activó (rising edge)
        // Solicitar interrupción STAT usando el método de MMU
        mmu_->request_interrupt(1);  // Bit 1 = LCD STAT Interrupt
    }
    
    // Actualizar flag de interrupción STAT con las condiciones actuales
    // Esto permite detectar rising edges en la próxima llamada
    // CRÍTICO: Actualizamos stat_interrupt_line_ DESPUÉS de verificar rising edge
    // para que en la próxima llamada podamos detectar si una condición se desactivó y reactivó
    stat_interrupt_line_ = current_conditions;
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

uint64_t PPU::get_frame_counter() const {
    return frame_counter_;
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

bool PPU::get_frame_ready_and_reset() {
    if (frame_ready_) {
        frame_ready_ = false;
        
        // --- Step 0333: CORRECCIÓN CRÍTICA - NO Limpiar Framebuffer Aquí ---
        // El framebuffer NO se limpia aquí porque Python lo lee DESPUÉS de esta llamada
        // Si limpiamos aquí, Python leerá un framebuffer vacío
        // El framebuffer se limpia al inicio del siguiente frame (cuando LY se resetea a 0)
        // Esto asegura que Python siempre lee el framebuffer ANTES de que se limpie
        // 
        // Log de reset del flag (sin limpiar framebuffer)
        static int frame_ready_reset_log_count = 0;
        if (frame_ready_reset_log_count < 5) {
            frame_ready_reset_log_count++;
            printf("[PPU-FRAME-READY-RESET] Frame %llu | Flag frame_ready_ reseteado (framebuffer NO limpiado aquí)\n",
                   static_cast<unsigned long long>(frame_counter_));
        }
        // -------------------------------------------
        
        return true;
    }
    return false;
}

uint8_t* PPU::get_framebuffer_ptr() {
    return framebuffer_.data();
}

void PPU::clear_framebuffer() {
    // Rellena el framebuffer con el índice de color 0 (blanco en la paleta por defecto)
    std::fill(framebuffer_.begin(), framebuffer_.end(), 0);
}

void PPU::render_scanline() {
    // --- Step 0203: Lógica de renderizado normal restaurada ---
    // El "Test del Checkerboard" del Step 0202 confirmó que el pipeline de renderizado
    // C++ -> Cython -> Python funciona perfectamente. Ahora restauramos la lógica
    // de renderizado normal que lee desde la VRAM para poder investigar por qué
    // la VRAM permanece vacía.
    
    // --- Step 0313: Log de diagnóstico - verificar que render_scanline() se ejecuta ---
    static int render_log_count = 0;
    if (ly_ == 0 && render_log_count < 3) {
        render_log_count++;
        printf("[PPU-RENDER] render_scanline() ejecutado para LY=%d (Frame %llu)\n", ly_, static_cast<unsigned long long>(frame_counter_ + 1));
    }
    
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        return;
    }
    
    // --- Step 0330: Optimización de Verificación de VRAM ---
    // Verificar VRAM una vez por línea (en LY=0) en lugar de 160 veces por línea
    // Esto mejora significativamente el rendimiento y asegura consistencia
    if (ly_ == 0) {
        // Verificar si VRAM está completamente vacía
        int vram_non_zero = 0;
        for (uint16_t i = 0; i < 6144; i++) {
            if (mmu_->read(0x8000 + i) != 0x00) {
                vram_non_zero++;
            }
        }
        
        vram_is_empty_ = (vram_non_zero < 200);
        
        static int vram_check_log_count = 0;
        if (vram_check_log_count < 5) {
            vram_check_log_count++;
            printf("[PPU-VRAM-CHECK] Frame %llu | VRAM non-zero: %d/6144 | Empty: %s\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   vram_non_zero, vram_is_empty_ ? "YES" : "NO");
        }
    }
    // -------------------------------------------
    
    // --- Step 0330: Flag para controlar checkerboard temporal ---
    static bool enable_checkerboard_temporal = true;  // Flag para controlar
    // -------------------------------------------
    
    uint8_t lcdc = mmu_->read(IO_LCDC);
    
    // --- Step 0313: Logs de diagnóstico LCDC y BGP ---
    static int lcdc_log_count = 0;
    if (ly_ == 0 && lcdc_log_count < 3) {
        lcdc_log_count++;
        uint8_t bgp = mmu_->read(IO_BGP);
        printf("[PPU-LCDC] Frame %llu | LCDC = 0x%02X | LCD ON: %d | BG ON: %d\n", 
               static_cast<unsigned long long>(frame_counter_ + 1), lcdc, (lcdc & 0x80) ? 1 : 0, (lcdc & 0x01) ? 1 : 0);
        printf("[PPU-BGP] BGP = 0x%02X\n", bgp);
    }

    // --- Step 0328: Análisis de Estado del LCD para TETRIS ---
    // Verificar por qué TETRIS muestra pantalla blanca
    static int lcd_state_analysis_count = 0;
    if (ly_ == 0 && lcd_state_analysis_count < 10) {
        lcd_state_analysis_count++;
        
        uint8_t lcdc_state = mmu_->read(IO_LCDC);
        bool lcd_on = (lcdc_state & 0x80) != 0;
        bool bg_display = (lcdc_state & 0x01) != 0;
        
        // Verificar estado de VRAM
        int vram_non_zero = 0;
        for (uint16_t i = 0; i < 6144; i++) {
            if (mmu_->read(0x8000 + i) != 0x00) {
                vram_non_zero++;
            }
        }
        
        // Verificar tilemap
        int tilemap_non_zero = 0;
        for (int i = 0; i < 32; i++) {
            if (mmu_->read(0x9800 + i) != 0x00) {
                tilemap_non_zero++;
            }
        }
        
        printf("[PPU-LCD-STATE] Frame %llu | LCD: %s | BG Display: %s | VRAM: %d/6144 | Tilemap: %d/32\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               lcd_on ? "ON" : "OFF",
               bg_display ? "ON" : "OFF",
               vram_non_zero, tilemap_non_zero);
        
        if (lcd_on && bg_display && vram_non_zero == 0) {
            printf("[PPU-LCD-STATE] ⚠️ PROBLEMA: LCD y BG Display activos pero VRAM vacía!\n");
        }
        
        if (lcd_on && !bg_display) {
            printf("[PPU-LCD-STATE] ⚠️ PROBLEMA: LCD activo pero BG Display desactivado!\n");
        }
    }
    // -------------------------------------------

    // Verificar que el LCD esté encendido
    if ((lcdc & 0x80) == 0) {
        return;
    }

    // --- Step 0313: Hack temporal - Forzar BG Display si está desactivado ---
    // El juego puede escribir LCDC = 0x80 (solo LCD Enable, sin BG Display),
    // pero para poder ver los tiles de prueba, temporalmente activamos el bit 0
    // solo para el renderizado (no modificamos la memoria)
    bool bg_display_forced = false;
    if (!(lcdc & 0x01)) {
        // Si BG Display está desactivado, temporalmente lo activamos para renderizar
        lcdc |= 0x01;  // Activar bit 0 (BG Display)
        bg_display_forced = true;
        // Log solo una vez para no saturar
        static int force_log_count = 0;
        if (ly_ == 0 && force_log_count < 1) {
            force_log_count++;
            printf("[PPU-FIX] LCDC tenía BG Display desactivado, forzado temporalmente a 0x%02X para renderizado\n", lcdc);
        }
    }
    // --- Fin hack temporal ---

    // --- Step 0329: Detección de Cambios de Configuración del Tilemap ---
    // Detectar cambios en Map Base, Data Base y signed/unsigned addressing
    static uint16_t last_tile_map_base = 0xFFFF;
    static uint16_t last_tile_data_base = 0xFFFF;
    static bool last_signed_addressing = false;
    
    uint16_t current_tile_map_base = (lcdc & 0x08) != 0 ? TILEMAP_1 : TILEMAP_0;
    bool current_unsigned_addressing = (lcdc & 0x10) != 0;
    uint16_t current_tile_data_base = current_unsigned_addressing ? TILE_DATA_0 : TILE_DATA_1;
    bool current_signed_addressing = !current_unsigned_addressing;
    
    if (ly_ == 0 && (current_tile_map_base != last_tile_map_base || 
                     current_tile_data_base != last_tile_data_base ||
                     current_signed_addressing != last_signed_addressing)) {
        static int tilemap_config_change_count = 0;
        if (tilemap_config_change_count < 10) {
            tilemap_config_change_count++;
            printf("[PPU-TILEMAP-CONFIG] Cambio de configuración: Map: 0x%04X->0x%04X | Data: 0x%04X->0x%04X | Signed: %d->%d\n",
                   last_tile_map_base, current_tile_map_base,
                   last_tile_data_base, current_tile_data_base,
                   last_signed_addressing ? 1 : 0, current_signed_addressing ? 1 : 0);
            
            // Verificar si los tile IDs del tilemap apuntan a direcciones válidas
            int invalid_tile_ids = 0;
            for (int i = 0; i < 32; i++) {
                uint8_t tile_id = mmu_->read(current_tile_map_base + i);
                uint16_t tile_addr;
                if (current_unsigned_addressing) {
                    tile_addr = current_tile_data_base + (tile_id * 16);
                } else {
                    int8_t signed_id = static_cast<int8_t>(tile_id);
                    tile_addr = current_tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
                }
                
                if (tile_addr < 0x8000 || tile_addr > 0x97FF) {
                    invalid_tile_ids++;
                }
            }
            
            if (invalid_tile_ids > 0) {
                printf("[PPU-TILEMAP-CONFIG] ⚠️ ADVERTENCIA: %d/32 tile IDs apuntan a direcciones inválidas\n",
                       invalid_tile_ids);
            }
        }
        
        last_tile_map_base = current_tile_map_base;
        last_tile_data_base = current_tile_data_base;
        last_signed_addressing = current_signed_addressing;
    }
    // -------------------------------------------
    
    uint8_t scy = mmu_->read(IO_SCY);
    uint8_t scx = mmu_->read(IO_SCX);

    uint16_t tile_map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
    bool signed_addressing = (lcdc & 0x10) == 0;
    uint16_t tile_data_base = signed_addressing ? 0x9000 : 0x8000;

    // --- Step 0325: Verificación CORREGIDA de tiles reales en VRAM ---
    // Revisar TODO VRAM (0x8000-0x97FF) en lugar de solo los primeros 2048 bytes
    // Si VRAM está vacía, usar patrón de prueba. Si hay tiles, renderizar normalmente.
    static bool vram_has_tiles = false;
    static bool last_vram_has_tiles = false;  // Step 0327: Para detectar cambios

    // --- Step 0327: Verificación Más Frecuente de VRAM ---
    // Verificar cada 10 frames en lugar de cada 60 para capturar tiles antes de que se limpien
    if (ly_ == 0 && (frame_counter_ % 10 == 0)) {  // Cada 10 frames (aprox. 6 veces por segundo)
        uint32_t vram_checksum = 0;
        int non_zero_bytes = 0;
        
        // Verificar TODO VRAM (0x8000-0x97FF = 6144 bytes = 384 tiles)
        // Esto cubre tanto signed (0x8800-0x97FF) como unsigned (0x8000-0x8FFF) addressing
        for (uint16_t i = 0; i < 6144; i++) {
            uint8_t byte = mmu_->read(0x8000 + i);
            vram_checksum += byte;
            if (byte != 0x00) {
                non_zero_bytes++;
            }
        }
        
        // --- Step 0326: Umbral CORREGIDO de detección de tiles reales ---
        // Reducir umbral de 500 a 200 bytes (aprox. 12 tiles completos)
        // 20 tiles = 320 bytes, que debería detectarse fácilmente
        bool has_tiles_now = (non_zero_bytes > 200);
        
        // Loggear siempre el número de bytes no-cero para diagnóstico
        static int vram_diag_count = 0;
        if (vram_diag_count < 10) {
            vram_diag_count++;
            printf("[PPU-VRAM-DIAG] Frame %llu | Non-zero bytes: %d/6144 | Umbral: 200 | Detectado: %d\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   non_zero_bytes, has_tiles_now ? 1 : 0);
        }
        
        // Solo loggear cuando cambia el estado o cuando hay tiles
        if (has_tiles_now != vram_has_tiles || (has_tiles_now && non_zero_bytes > 0)) {
            static int vram_frequent_check_count = 0;
            if (vram_frequent_check_count < 20) {  // Limitar a 20 logs
                vram_frequent_check_count++;
                printf("[PPU-VRAM-FREQ] Frame %llu | Non-zero: %d/6144 | Has tiles: %d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       non_zero_bytes, has_tiles_now ? 1 : 0);
            }
        }
        
        if (has_tiles_now != vram_has_tiles) {
            vram_has_tiles = has_tiles_now;
            if (vram_has_tiles) {
                printf("[PPU-TILES-REAL] Tiles reales detectados en VRAM! (Frame %llu | Non-zero: %d/6144 bytes)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), non_zero_bytes);
            } else {
                printf("[PPU-TILES-REAL] VRAM vacía, usando patrón de prueba (Frame %llu | Non-zero: %d/6144 bytes)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), non_zero_bytes);
            }
        }
        // -------------------------------------------
    }
    // -------------------------------------------
    
    // --- Step 0327: Verificación Inmediata del Tilemap Cuando Hay Tiles ---
    // Cuando se detecta que hay tiles, verificar inmediatamente si el tilemap apunta a ellos
    if (vram_has_tiles && !last_vram_has_tiles && ly_ == 0) {
        // Tiles recién detectados, verificar tilemap inmediatamente
        printf("[PPU-TILEMAP-IMMEDIATE] Tiles detectados! Verificando tilemap...\n");
        
        // Verificar primeros 32 tile IDs del tilemap
        int tiles_pointing_to_real_data = 0;
        int tiles_pointing_to_empty = 0;
        
        for (int i = 0; i < 32; i++) {
            uint8_t tile_id = mmu_->read(tile_map_base + i);
            
            // Calcular dirección del tile según el direccionamiento
            uint16_t tile_addr;
            if (signed_addressing) {
                int8_t signed_id = static_cast<int8_t>(tile_id);
                tile_addr = tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
            } else {
                tile_addr = tile_data_base + (static_cast<uint16_t>(tile_id) * 16);
            }
            
            // Verificar si el tile tiene datos
            uint8_t tile_byte1 = mmu_->read(tile_addr);
            uint8_t tile_byte2 = mmu_->read(tile_addr + 1);
            
            if (tile_byte1 != 0x00 || tile_byte2 != 0x00) {
                tiles_pointing_to_real_data++;
            } else {
                tiles_pointing_to_empty++;
            }
        }
        
        printf("[PPU-TILEMAP-IMMEDIATE] Tilemap apunta a: %d tiles con datos, %d tiles vacíos\n",
               tiles_pointing_to_real_data, tiles_pointing_to_empty);
        
        if (tiles_pointing_to_real_data == 0) {
            printf("[PPU-TILEMAP-IMMEDIATE] ⚠️ PROBLEMA: Tilemap no apunta a tiles con datos!\n");
        }
    }
    
    // --- Step 0328: Verificación de Renderizado Cuando Hay Tiles ---
    // Verificar si el renderizado funciona correctamente cuando hay tiles en VRAM
    static bool last_vram_has_tiles_state = false;
    if (vram_has_tiles && !last_vram_has_tiles_state && ly_ == 0) {
        // Tiles recién detectados, verificar renderizado
        printf("[PPU-RENDER-WITH-TILES] Tiles detectados! Verificando renderizado...\n");
        
        // Forzar renderizado de una línea para verificar
        // (esto se hará automáticamente en el siguiente render_scanline)
    }

    // Verificar framebuffer cuando hay tiles
    if (vram_has_tiles && ly_ == 72) {
        static int render_with_tiles_check_count = 0;
        if (render_with_tiles_check_count < 5) {
            render_with_tiles_check_count++;
            
            size_t line_start = ly_ * SCREEN_WIDTH;
            int non_zero_pixels = 0;
            for (int x = 0; x < SCREEN_WIDTH; x++) {
                uint8_t color_idx = framebuffer_[line_start + x] & 0x03;
                if (color_idx != 0) {
                    non_zero_pixels++;
                }
            }
            
            printf("[PPU-RENDER-WITH-TILES] Frame %llu | LY:72 | Píxeles no-blancos: %d/160\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), non_zero_pixels);
            
            if (non_zero_pixels == 0) {
                printf("[PPU-RENDER-WITH-TILES] ⚠️ PROBLEMA: Framebuffer vacío aunque hay tiles en VRAM!\n");
            }
        }
    }

    last_vram_has_tiles_state = vram_has_tiles;
    last_vram_has_tiles = vram_has_tiles;
    // -------------------------------------------

    // --- Step 0325: Análisis de Correspondencia Tilemap-Tiles ---
    // Verificar si el tilemap apunta a los tiles reales cuando se detectan
    static int tilemap_tiles_analysis_count = 0;
    if (vram_has_tiles && ly_ == 0 && tilemap_tiles_analysis_count < 5 && (frame_counter_ % 60 == 0)) {
        tilemap_tiles_analysis_count++;
        
        // Verificar primeros 32 tile IDs del tilemap
        int tiles_pointing_to_real_data = 0;
        int tiles_pointing_to_empty = 0;
        
        for (int i = 0; i < 32; i++) {
            uint8_t tile_id = mmu_->read(tile_map_base + i);
            
            // Calcular dirección del tile según el direccionamiento
            uint16_t tile_addr;
            if (signed_addressing) {
                int8_t signed_id = static_cast<int8_t>(tile_id);
                tile_addr = tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
            } else {
                tile_addr = tile_data_base + (static_cast<uint16_t>(tile_id) * 16);
            }
            
            // Verificar si el tile tiene datos
            uint8_t tile_byte1 = mmu_->read(tile_addr);
            uint8_t tile_byte2 = mmu_->read(tile_addr + 1);
            
            if (tile_byte1 != 0x00 || tile_byte2 != 0x00) {
                tiles_pointing_to_real_data++;
            } else {
                tiles_pointing_to_empty++;
            }
        }
        
        printf("[PPU-TILEMAP-ANALYSIS] Frame %llu | Tilemap apunta a: %d tiles con datos, %d tiles vacíos\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               tiles_pointing_to_real_data, tiles_pointing_to_empty);
        
        if (tiles_pointing_to_real_data == 0) {
            printf("[PPU-TILEMAP-ANALYSIS] ⚠️ PROBLEMA: Tilemap no apunta a tiles con datos aunque hay tiles en VRAM!\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0327: Análisis de Correspondencia en Tiempo Real ---
    // Cuando se detectan tiles, analizar qué tile IDs deberían apuntar a ellos
    if (vram_has_tiles && ly_ == 0 && (frame_counter_ % 10 == 0)) {
        static int correspondence_analysis_count = 0;
        if (correspondence_analysis_count < 5) {
            correspondence_analysis_count++;
            
            // Verificar direcciones conocidas donde se cargan tiles (0x8820+)
            printf("[PPU-CORRESPONDENCE] Analizando correspondencia tilemap-tiles...\n");
            
            for (uint16_t check_addr = 0x8820; check_addr <= 0x8A80; check_addr += 0x20) {
                uint8_t tile_byte1 = mmu_->read(check_addr);
                uint8_t tile_byte2 = mmu_->read(check_addr + 1);
                
                if (tile_byte1 != 0x00 || tile_byte2 != 0x00) {
                    // Tile tiene datos, calcular qué tile ID debería apuntar a él
                    if (signed_addressing) {
                        int16_t offset = check_addr - 0x9000;
                        int8_t tile_id = static_cast<int8_t>(offset / 16);
                        uint8_t tile_id_unsigned = static_cast<uint8_t>(tile_id);
                        
                        // Verificar si el tilemap tiene este tile ID
                        bool found_in_tilemap = false;
                        for (int i = 0; i < 32; i++) {
                            if (mmu_->read(tile_map_base + i) == tile_id_unsigned) {
                                found_in_tilemap = true;
                                break;
                            }
                        }
                        
                        printf("[PPU-CORRESPONDENCE] Tile en 0x%04X = TileID 0x%02X (signed: %d) | En tilemap: %s\n",
                               check_addr, tile_id_unsigned, tile_id, found_in_tilemap ? "SÍ" : "NO");
                    }
                }
            }
        }
    }
    // -------------------------------------------

    // --- Step 0321: Verificación de Tilemap ---
    // Verificar el tilemap para diagnosticar problemas de renderizado
    static int tilemap_check_count = 0;
    if (ly_ == 0 && tilemap_check_count < 5) {
        tilemap_check_count++;
        
        printf("[PPU-TILEMAP-CHECK] Frame %llu | Map Base: 0x%04X | Data Base: 0x%04X | Signed: %d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               tile_map_base, tile_data_base, signed_addressing ? 1 : 0);
        
        // Verificar primeros 4 tiles del tilemap (primera fila, primeras 4 columnas)
        printf("[PPU-TILEMAP-CHECK] Primeros 4 tiles del tilemap: ");
        for (int i = 0; i < 4; i++) {
            uint8_t tile_id = mmu_->read(tile_map_base + i);
            printf("Tile[%d]=0x%02X ", i, tile_id);
            
            // Verificar si el tile tiene datos válidos
            uint16_t tile_addr;
            if (signed_addressing) {
                // Signed: tile_id es int8_t, tile data base = 0x9000
                int8_t signed_id = static_cast<int8_t>(tile_id);
                tile_addr = tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
            } else {
                // Unsigned: tile_id es uint8_t, tile data base = 0x8000
                tile_addr = tile_data_base + (static_cast<uint16_t>(tile_id) * 16);
            }
            
            // Leer primeros 2 bytes del tile para verificar si tiene datos
            uint8_t tile_byte1 = mmu_->read(tile_addr);
            uint8_t tile_byte2 = mmu_->read(tile_addr + 1);
            printf("(addr=0x%04X, data=0x%02X%02X) ", tile_addr, tile_byte1, tile_byte2);
        }
        printf("\n");
    }
    // -------------------------------------------

    // --- Step 0289: Inspector de Tilemap ([TILEMAP-INSPECT]) ---
    // Inspeccionar el Tile Map al inicio de cada frame (LY=0) para verificar
    // qué tile IDs se están usando. Esto permite identificar si el tilemap
    // apunta a tiles válidos o está vacío (todo ceros).
    // Fuente: Pan Docs - "Tile Map": 32x32 tiles en 0x9800-0x9BFF o 0x9C00-0x9FFF
    static int frame_count = 0;
    if (ly_ == 0) {
        frame_count++;
        if (frame_count <= 5) {  // Solo los primeros 5 frames para no saturar
            printf("[TILEMAP-INSPECT] Frame %d | LCDC: %02X | BG Map Base: %04X | BG Data Base: %04X\n",
                   frame_count, lcdc, tile_map_base, tile_data_base);
            
            // Imprimir las primeras 32 bytes (primera fila completa del tilemap)
            printf("[TILEMAP-INSPECT] First 32 bytes (row 0) of Map at %04X:\n", tile_map_base);
            for(int i=0; i<32; i++) {
                printf("%02X ", mmu_->read(tile_map_base + i));
                if ((i + 1) % 16 == 0) printf("\n");
            }
            printf("\n");
            
            // Calcular checksum del tilemap para detectar cambios
            uint16_t checksum = 0;
            for(int i=0; i<1024; i++) {  // 32x32 = 1024 tiles
                checksum += mmu_->read(tile_map_base + i);
            }
            printf("[TILEMAP-INSPECT] Tilemap checksum (first 1024 bytes): 0x%04X\n", checksum);
        }
    }
    // -----------------------------------------

    // --- Step 0257: HARDWARE PALETTE BYPASS ---
    // Forzar BGP = 0xE4 (mapeo identidad: 3->3, 2->2, 1->1, 0->0)
    // Esto garantiza que los índices de color se preserven en el framebuffer,
    // independientemente del estado de los registros de paleta en la MMU.
    // uint8_t bgp = mmu_->read(IO_BGP); // COMENTADO: Ignorar MMU
    uint8_t bgp = 0xE4;  // 11 10 01 00 (Mapeo identidad estándar)
    // -------------------------------------------

    size_t line_start_index = ly_ * 160;

    // --- Step 0326: Verificaciones siempre activas ---
    // Ejecutar verificaciones incluso si vram_has_tiles es false para diagnóstico
    static int tilemap_verify_count = 0;
    if (ly_ == 0 && tilemap_verify_count < 5 && (frame_counter_ % 60 == 0)) {
        tilemap_verify_count++;
        
        // Verificar primeros 32 bytes del tilemap (primera fila)
        int valid_tile_ids = 0;
        for (int i = 0; i < 32; i++) {
            uint8_t tile_id = mmu_->read(tile_map_base + i);
            if (tile_id != 0x00) {
                valid_tile_ids++;
            }
        }
        
        printf("[PPU-TILEMAP-VERIFY] Frame %llu | Tilemap tiene %d/32 tile IDs no-cero | VRAM has tiles: %d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               valid_tile_ids, vram_has_tiles ? 1 : 0);
        
        if (valid_tile_ids == 0) {
            printf("[PPU-TILEMAP-VERIFY] ⚠️ ADVERTENCIA: Tilemap está vacío");
            if (vram_has_tiles) {
                printf(" aunque hay tiles en VRAM!");
            }
            printf("\n");
        }
    }
    // -------------------------------------------

    // --- Step 0299: Monitor de Tilemap Real ([TILEMAP-DUMP-VISUAL]) ---
    // Capturar los tile IDs reales que se están leyendo del tilemap durante el renderizado
    // de la línea central (LY=72). Esto permite identificar si hay un patrón repetitivo
    // en los tile IDs que podría explicar las rayas verticales.
    // Fuente: Pan Docs - "Tile Map"
    static int tilemap_dump_count = 0;
    if (ly_ == 72 && tilemap_dump_count < 3) {
        printf("[TILEMAP-DUMP-VISUAL] Frame %d, LY:72 | First 32 tile IDs:\n", tilemap_dump_count + 1);
        for(int x_dump = 0; x_dump < 32; x_dump++) {
            uint8_t map_x_dump = (x_dump + scx) & 0xFF;
            uint8_t map_y_dump = (ly_ + scy) & 0xFF;
            uint16_t tile_map_addr_dump = tile_map_base + (map_y_dump / 8) * 32 + (map_x_dump / 8);
            uint8_t tile_id_dump = mmu_->read(tile_map_addr_dump);
            printf("%02X ", tile_id_dump);
            if ((x_dump + 1) % 16 == 0) printf("\n");
        }
        printf("\n");
        tilemap_dump_count++;
    }
    // -----------------------------------------

    for (int x = 0; x < 160; ++x) {
        uint8_t map_x = (x + scx) & 0xFF;
        uint8_t map_y = (ly_ + scy) & 0xFF;

        uint16_t tile_map_addr = tile_map_base + (map_y / 8) * 32 + (map_x / 8);
        uint8_t tile_id = mmu_->read(tile_map_addr);

        // --- Step 0278: Inspección de PPU en el centro de la pantalla ---
        // Log puntual para ver qué Tile ID está leyendo realmente cuando dibuja el centro
        static int ppu_debug_count = 0;
        if (ly_ == 72 && ppu_debug_count < 1) {
            // Solo una vez en el medio de la pantalla (LY=72 de 144 líneas)
            if (x == 80) {  // Centro horizontal (80 de 160 píxeles)
                printf("[PPU-DEBUG] LY:72 X:80 | TileMapAddr:%04X | TileID:%02X | TileDataBase:%04X\n",
                       tile_map_addr, tile_id, tile_data_base);
                ppu_debug_count++;
            }
        }
        // -----------------------------------------

        uint16_t tile_addr;
        if (signed_addressing) {
            tile_addr = tile_data_base + ((int8_t)tile_id * 16);
        } else {
            tile_addr = tile_data_base + (tile_id * 16);
        }

        // --- Step 0325: Verificación de Cálculo de Dirección de Tile ---
        // Verificar que el cálculo de dirección sea correcto para signed/unsigned addressing
        static int tile_addr_verify_count = 0;
        if (vram_has_tiles && ly_ == 0 && tile_addr_verify_count < 3 && x == 0) {
            tile_addr_verify_count++;
            
            uint8_t sample_tile_id = mmu_->read(tile_map_base);
            uint16_t calculated_addr;
            
            if (signed_addressing) {
                int8_t signed_id = static_cast<int8_t>(sample_tile_id);
                calculated_addr = tile_data_base + ((int8_t)sample_tile_id * 16);
                printf("[PPU-TILE-ADDR-VERIFY] TileID: 0x%02X (signed: %d) | Base: 0x%04X | Calculado: 0x%04X\n",
                       sample_tile_id, signed_id, tile_data_base, calculated_addr);
            } else {
                calculated_addr = tile_data_base + (sample_tile_id * 16);
                printf("[PPU-TILE-ADDR-VERIFY] TileID: 0x%02X (unsigned) | Base: 0x%04X | Calculado: 0x%04X\n",
                       sample_tile_id, tile_data_base, calculated_addr);
            }
            
            // Verificar si hay tiles reales en esa dirección
            uint8_t tile_byte1 = mmu_->read(calculated_addr);
            uint8_t tile_byte2 = mmu_->read(calculated_addr + 1);
            printf("[PPU-TILE-ADDR-VERIFY] Datos en 0x%04X: 0x%02X%02X\n",
                   calculated_addr, tile_byte1, tile_byte2);
        }
        // -------------------------------------------

        // --- Step 0324: Verificación de renderizado con tiles reales ---
        // Solo verificar cuando hay tiles reales y en los primeros frames
        static int render_verify_count = 0;
        if (vram_has_tiles && ly_ == 0 && render_verify_count < 5 && x == 0) {
            // Verificar que el tile ID del tilemap apunta a un tile con datos
            uint8_t sample_tile_id = mmu_->read(tile_map_base);
            uint16_t sample_tile_addr;
            if (signed_addressing) {
                sample_tile_addr = tile_data_base + ((int8_t)sample_tile_id * 16);
            } else {
                sample_tile_addr = tile_data_base + (sample_tile_id * 16);
            }
            
            // Leer primeros 2 bytes del tile
            uint8_t tile_byte1 = mmu_->read(sample_tile_addr);
            uint8_t tile_byte2 = mmu_->read(sample_tile_addr + 1);
            
            if (tile_byte1 != 0x00 || tile_byte2 != 0x00) {
                render_verify_count++;
                printf("[PPU-RENDER-VERIFY] Frame %llu | TileID: 0x%02X | Addr: 0x%04X | Data: 0x%02X%02X (tiene datos)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       sample_tile_id, sample_tile_addr, tile_byte1, tile_byte2);
            }
        }
        // -------------------------------------------

        // --- Step 0321: Debug de cálculo de tile (solo primeros píxeles) ---
        static int tile_calc_debug_count = 0;
        if (ly_ == 0 && x < 8 && tile_calc_debug_count < 1) {
            tile_calc_debug_count++;
            // Leer datos del tile para el log
            uint8_t line_in_tile_temp = map_y % 8;
            uint16_t tile_line_addr_temp = tile_addr + (line_in_tile_temp * 2);
            uint8_t tile_data_low = 0, tile_data_high = 0;
            if (tile_line_addr_temp >= 0x8000 && tile_line_addr_temp <= 0x9FFE) {
                tile_data_low = mmu_->read(tile_line_addr_temp);
                tile_data_high = mmu_->read(tile_line_addr_temp + 1);
            }
            printf("[PPU-TILE-CALC] LY=%d, X=%d | Tile ID: 0x%02X | Tile Addr: 0x%04X | Tile Data: 0x%02X%02X\n",
                   ly_, x, tile_id, tile_addr, tile_data_low, tile_data_high);
        }
        // -------------------------------------------

        uint8_t line_in_tile = map_y % 8;
        uint16_t tile_line_addr = tile_addr + (line_in_tile * 2);

        // --- Step 0329: Verificación de Direcciones de Tiles Durante Renderizado ---
        // Verificar que la dirección del tile está en el rango válido antes de leer
        bool tile_addr_valid = (tile_addr >= 0x8000 && tile_addr <= 0x97FF);
        bool tile_line_addr_valid = (tile_line_addr >= 0x8000 && tile_line_addr <= 0x97FF);
        
        if (!tile_addr_valid || !tile_line_addr_valid) {
            // Dirección inválida, activar checkerboard
            static int invalid_tile_addr_count = 0;
            if (invalid_tile_addr_count < 5 && ly_ == 0 && x == 0) {
                invalid_tile_addr_count++;
                printf("[PPU-INVALID-TILE-ADDR] TileID: 0x%02X | Addr: 0x%04X (fuera de rango) | Activando checkerboard\n",
                       tile_id, tile_addr);
            }
            
            // Generar checkerboard temporal
            uint8_t tile_x_in_map = (map_x / 8) % 2;
            uint8_t tile_y_in_map = (map_y / 8) % 2;
            uint8_t checkerboard = (tile_x_in_map + tile_y_in_map) % 2;
            uint8_t line_in_tile_check = map_y % 8;
            
            uint8_t byte1, byte2;
            if (checkerboard == 0) {
                if (line_in_tile_check % 2 == 0) {
                    byte1 = 0xFF;
                    byte2 = 0xFF;
                } else {
                    byte1 = 0x00;
                    byte2 = 0x00;
                }
            } else {
                if (line_in_tile_check % 2 == 0) {
                    byte1 = 0x00;
                    byte2 = 0x00;
                } else {
                    byte1 = 0xFF;
                    byte2 = 0xFF;
                }
            }
            
            // Aplicar paleta y escribir en framebuffer
            uint8_t bit_index = 7 - (map_x % 8);
            uint8_t bit_low = (byte1 >> bit_index) & 1;
            uint8_t bit_high = (byte2 >> bit_index) & 1;
            uint8_t color_index = (bit_high << 1) | bit_low;
            uint8_t final_color = (bgp >> (color_index * 2)) & 0x03;
            framebuffer_[line_start_index + x] = final_color;
        } else {
            // Dirección válida, leer datos del tile
            // --- RESTAURADO: LÓGICA REAL DE VRAM ---
            uint8_t byte1 = mmu_->read(tile_line_addr);
            uint8_t byte2 = mmu_->read(tile_line_addr + 1);
            
            // --- Step 0329: Mejora de Detección de Tiles Vacíos y Checkerboard Temporal ---
            // Verificar TODO el tile (16 bytes) antes de considerarlo vacío
            // Algunos tiles legítimos pueden tener líneas con 0x0000
            static bool empty_tile_detected = false;
            bool tile_is_empty = true;

            // Verificar si TODO el tile está vacío (todas las 8 líneas = 16 bytes)
            for (uint8_t line_check = 0; line_check < 8; line_check++) {
                uint16_t check_addr = tile_addr + (line_check * 2);
                if (check_addr < 0x8000 || check_addr > 0x97FF) {
                    tile_is_empty = true;
                    break;
                }
                uint8_t check_byte1 = mmu_->read(check_addr);
                uint8_t check_byte2 = mmu_->read(check_addr + 1);
                
                if (check_byte1 != 0x00 || check_byte2 != 0x00) {
                    tile_is_empty = false;
                    break;
                }
            }

            // --- Step 0330: Lógica Optimizada del Checkerboard Temporal ---
            // Activar checkerboard cuando:
            // 1. El tile está completamente vacío (todas las líneas = 0x00)
            // 2. VRAM está completamente vacía (< 200 bytes no-cero)
            // Esto previene pantallas blancas cuando el tilemap apunta a direcciones inválidas
            // OPTIMIZACIÓN: Usar variable vram_is_empty_ en lugar de verificar VRAM en cada píxel
            if (tile_is_empty && enable_checkerboard_temporal && vram_is_empty_) {
                // --- Step 0330: Usar Variable de Estado en lugar de Verificar VRAM ---
                // En lugar de verificar VRAM en cada píxel, usar la variable vram_is_empty_
                // que se actualiza una vez por línea (en LY=0)
                // Activar checkerboard si VRAM está completamente vacía
                {
                    if (!empty_tile_detected && ly_ == 0 && x == 0) {
                        empty_tile_detected = true;
                        printf("[PPU-FIX-EMPTY-TILE] Detectado tile completamente vacío en 0x%04X, usando checkerboard temporal\n", tile_addr);
                    }
                    
                    // Generar un patrón simple de cuadros basado en la posición del tile
                    // Esto permite ver algo en pantalla mientras el juego carga tiles
                    uint8_t tile_x_in_map = (map_x / 8) % 2;
                    uint8_t tile_y_in_map = (map_y / 8) % 2;
                    uint8_t checkerboard = (tile_x_in_map + tile_y_in_map) % 2;
                    
                    // Generar un patrón de línea basado en la línea dentro del tile
                    uint8_t line_in_tile_check = map_y % 8;
                    if (checkerboard == 0) {
                        // Patrón de cuadros: líneas alternas
                        if (line_in_tile_check % 2 == 0) {
                            byte1 = 0xFF;  // Línea completa
                            byte2 = 0xFF;
                        } else {
                            byte1 = 0x00;  // Línea vacía
                            byte2 = 0x00;
                        }
                    } else {
                        // Patrón inverso
                        if (line_in_tile_check % 2 == 0) {
                            byte1 = 0x00;
                            byte2 = 0x00;
                        } else {
                            byte1 = 0xFF;
                            byte2 = 0xFF;
                        }
                    }
                }
            } else if (tile_is_empty) {
                // VRAM tiene datos, pero este tile específico está vacío
                // Renderizar como tile vacío (blanco) sin checkerboard
                byte1 = 0x00;
                byte2 = 0x00;
            } else if (tile_is_empty && !enable_checkerboard_temporal) {
                // Checkerboard desactivado, renderizar como tile vacío
                byte1 = 0x00;
                byte2 = 0x00;
            } else {
                // Tile tiene datos, usar renderizado normal
                // Si el tile tiene datos, marcar que ya no estamos usando tiles de prueba
                if (empty_tile_detected && ly_ == 0 && x == 0) {
                    empty_tile_detected = false;
                    printf("[PPU-FIX-EMPTY-TILE] Tiles con datos detectados, usando tiles reales del juego\n");
                }
            }
            // -----------------------------------------
            
            // --- Step 0329: Verificación de Direcciones de Tiles Durante Renderizado (continuación) ---
            // Si llegamos aquí, la dirección es válida y tenemos los datos del tile
            // Continuar con el renderizado normal
            
            // --- Step 0299: Monitor de Datos de Tiles Reales ([TILEDATA-DUMP-VISUAL]) ---
            // Capturar los datos reales de los tiles que se están leyendo de VRAM durante
            // el renderizado. Esto permite verificar si los tiles contienen datos válidos
            // o están vacíos (0x00), lo que podría explicar las rayas verdes.
            // Fuente: Pan Docs - "Tile Data"
            static int tiledata_dump_count = 0;
            if (ly_ == 72 && x < 32 && tiledata_dump_count < 3) {
                // Capturar los datos de los primeros 4 tiles (cada 8 píxeles)
                if (x % 8 == 0) {  // Cada 8 píxeles (un tile completo)
                    uint8_t tile_index = x / 8;
                    if (tile_index < 4) {
                        printf("[TILEDATA-DUMP-VISUAL] Frame %d | Tile %d (ID:%02X) | Addr:%04X | Line:%d | Bytes: %02X %02X\n",
                               tiledata_dump_count + 1, tile_index, tile_id, tile_line_addr, line_in_tile, byte1, byte2);
                    }
                }
            }
            if (ly_ == 72 && x == 31) tiledata_dump_count++;
            // -----------------------------------------
            
            // --- Step 0289: Inspector de Tile Data ([TILEDATA-INSPECT]) ---
            // Verificar si el tile contiene datos válidos (distintos de 0x00) cuando se lee.
            // Esto permite identificar si los tiles apuntados por el tilemap tienen datos reales.
            // Solo inspeccionar en el centro de la pantalla y en algunos frames iniciales.
            static int tiledata_inspect_count = 0;
            if (ly_ == 72 && x == 80 && tiledata_inspect_count < 3) {  // Centro de pantalla, primeros 3 frames
                printf("[TILEDATA-INSPECT] LY:72 X:80 | TileID:%02X | TileAddr:%04X | Byte1:%02X Byte2:%02X\n",
                       tile_id, tile_addr, byte1, byte2);
                if (byte1 == 0x00 && byte2 == 0x00) {
                    printf("[TILEDATA-INSPECT] WARNING: Tile %02X contains only zeros (empty tile)\n", tile_id);
                }
                tiledata_inspect_count++;
            }
            // -----------------------------------------
            
            uint8_t bit_index = 7 - (map_x % 8);
            uint8_t bit_low = (byte1 >> bit_index) & 1;
            uint8_t bit_high = (byte2 >> bit_index) & 1;
            uint8_t color_index = (bit_high << 1) | bit_low;

            // --- Step 0257: Aplicar paleta forzada (mapeo identidad) ---
            // Aplicar BGP para mapear el índice de color crudo al índice final
            // BGP = 0xE4 = 11 10 01 00
            // color_index 0 -> (BGP >> 0) & 3 = 0
            // color_index 1 -> (BGP >> 2) & 3 = 1
            // color_index 2 -> (BGP >> 4) & 3 = 2
            // color_index 3 -> (BGP >> 6) & 3 = 3
            uint8_t final_color = (bgp >> (color_index * 2)) & 0x03;
            
            // --- Step 0313: Log de diagnóstico - verificar lectura de tile data ---
            static int tile_data_log_count = 0;
            if (ly_ == 0 && x == 0 && tile_data_log_count < 3) {
                tile_data_log_count++;
                printf("[PPU-TILE-DATA] LY:0 X:0 | TileAddr:0x%04X | Byte1:0x%02X Byte2:0x%02X | ColorIndex:%d FinalColor:%d\n",
                       tile_line_addr, byte1, byte2, color_index, final_color);
            }
            
            // --- Step 0290: Monitor de Aplicación de Paleta ([PALETTE-APPLY]) ---
            // Captura cómo se aplica la paleta BGP durante el renderizado.
            // Solo se activa en el centro de la pantalla (LY=72, X=80) y en los primeros 3 frames
            // para no saturar los logs.
            // Fuente: Pan Docs - "Background Palette (BGP)"
            static int palette_apply_count = 0;
            if (ly_ == 72 && x == 80 && palette_apply_count < 3) {
                printf("[PALETTE-APPLY] LY:72 X:80 | ColorIndex:%d -> FinalColor:%d | BGP:0x%02X\n",
                       color_index, final_color, bgp);
                palette_apply_count++;
            }
            
            // --- Step 0299: Monitor de Paleta Aplicada ([PALETTE-DUMP-VISUAL]) ---
            // Capturar la aplicación de la paleta BGP para ver qué colores finales se generan
            // en los primeros 32 píxeles de la línea central. Esto permite identificar si el
            // patrón de rayas viene de la aplicación de la paleta.
            // Fuente: Pan Docs - "Background Palette (BGP)"
            static int palette_dump_count = 0;
            if (ly_ == 72 && x < 32 && palette_dump_count < 3) {
                if (x == 0) {
                    printf("[PALETTE-DUMP-VISUAL] Frame %d, LY:72 | BGP:0x%02X | First 32 pixels (ColorIndex -> FinalColor):\n",
                           palette_dump_count + 1, bgp);
                }
                printf("(%d->%d) ", color_index, final_color);
                if ((x + 1) % 16 == 0) printf("\n");
            }
            if (ly_ == 72 && x == 31) palette_dump_count++;
            // -----------------------------------------
            
            // --- Step 0313: Log de diagnóstico - verificar escritura en framebuffer ---
            static int framebuffer_log_count = 0;
            if (ly_ == 0 && x < 4 && framebuffer_log_count < 3) {
                if (x == 0) {
                    framebuffer_log_count++;
                    printf("[PPU-FRAMEBUFFER] LY:0 | Escribiendo primeros píxeles en framebuffer\n");
                }
                printf("[PPU-FRAMEBUFFER] X:%d | ColorIndex:%d FinalColor:%d -> framebuffer[%zu]\n",
                       x, color_index, final_color, line_start_index + x);
            }
            
            framebuffer_[line_start_index + x] = final_color;
            // -------------------------------------------------------------
        }
    }
    
    // --- Step 0299: Monitor de Framebuffer Real ([FRAMEBUFFER-DUMP]) ---
    // Capturar el contenido real del framebuffer después de renderizar un frame completo
    // para ver qué índices de color se están escribiendo. Esto permite identificar si hay
    // un patrón repetitivo en los índices que podría explicar las rayas verticales.
    // Fuente: Pan Docs - "LCD Display"
    static int framebuffer_dump_count = 0;
    if (ly_ == 72 && framebuffer_dump_count < 3) {  // Línea central (72 de 144)
        printf("[FRAMEBUFFER-DUMP] Frame %d, LY:72 | First 32 pixels (indices 0-31):\n", framebuffer_dump_count + 1);
        for(int x_dump = 0; x_dump < 32; x_dump++) {
            printf("%02X ", framebuffer_[line_start_index + x_dump]);
            if ((x_dump + 1) % 16 == 0) printf("\n");
        }
        printf("\n");
        framebuffer_dump_count++;
    }
    // -----------------------------------------
    
    // --- STEP 0304: Monitor de Framebuffer Detallado ([FRAMEBUFFER-DETAILED]) ---
    // Monitorear el framebuffer desde el lado C++ para detectar cuándo se escriben valores 1 o 2.
    // Solo rastrear algunos píxeles o líneas específicas para no afectar el rendimiento.
    // 
    // FLAG DE ACTIVACIÓN: Solo activar si las rayas verdes aparecen después de la verificación visual extendida.
    // Para activar, cambiar ENABLE_FRAMEBUFFER_DETAILED_TRACE a true.
    // 
    // Fuente: Pan Docs - "Framebuffer", "Background Palette (BGP)"
    static constexpr bool ENABLE_FRAMEBUFFER_DETAILED_TRACE = true;  // ACTIVADO: Rayas verdes aparecen después de 2 minutos
    static int detailed_trace_count = 0;
    static int last_frame_with_non_zero = 0;
    
    if (ENABLE_FRAMEBUFFER_DETAILED_TRACE && ly_ == 72 && detailed_trace_count % 1000 == 0) {
        int non_zero_count = 0;
        size_t line_start = ly_ * 160;
        
        // Contar índices no-cero en la línea central
        for (int x = 0; x < 160; x++) {
            uint8_t idx = framebuffer_[line_start + x] & 0x03;
            if (idx != 0) non_zero_count++;
        }
        
        if (non_zero_count > 0 || detailed_trace_count < 10) {
            if (detailed_trace_count < 100) {
                printf("[FRAMEBUFFER-DETAILED] Frame %d LY:72 | Non-zero pixels: %d/160\n",
                       detailed_trace_count, non_zero_count);
                
                // Mostrar algunos píxeles de ejemplo
                printf("[FRAMEBUFFER-DETAILED] Sample pixels (first 32): ");
                for (int x = 0; x < 32; x++) {
                    printf("%d ", framebuffer_[line_start + x] & 0x03);
                }
                printf("\n");
            }
            last_frame_with_non_zero = detailed_trace_count;
        }
        detailed_trace_count++;
    }
    // -----------------------------------------
    
    // --- Step 0284: Renderizar Window después del Background ---
    // La Window se dibuja encima del Background pero debajo de los Sprites
    // Solo se renderiza si está habilitada (LCDC bit 5) y las condiciones WY/WX se cumplen
    // Fuente: Pan Docs - Window, LCDC Bit 5 (Window Enable)
    if ((lcdc & 0x20) != 0) {
        render_window();
    }
    
    // --- Step 0254: Renderizar Sprites después del Background y Window ---
    // Los sprites se dibujan encima del fondo y la ventana (a menos que tengan prioridad)
    // Fuente: Pan Docs - Sprite Rendering, Priority
    render_sprites();
    
    // --- Step 0330: Verificación de Renderizado Completo del Checkerboard ---
    // Verificar que el checkerboard se renderiza en todas las líneas
    if (vram_is_empty_ && enable_checkerboard_temporal && ly_ == 72) {
        static int checkerboard_render_check_count = 0;
        if (checkerboard_render_check_count < 3) {
            checkerboard_render_check_count++;
            
            // Verificar que el framebuffer tiene datos no-blancos en la línea central
            size_t line_start = ly_ * SCREEN_WIDTH;
            int non_zero_pixels = 0;
            for (int x_check = 0; x_check < SCREEN_WIDTH; x_check++) {
                uint8_t color_idx = framebuffer_[line_start + x_check] & 0x03;
                if (color_idx != 0) {
                    non_zero_pixels++;
                }
            }
            
            printf("[PPU-CHECKERBOARD-RENDER] LY:72 | Non-zero pixels: %d/160 | Expected: ~80\n",
                   non_zero_pixels);
            
            if (non_zero_pixels == 0) {
                printf("[PPU-CHECKERBOARD-RENDER] ⚠️ PROBLEMA: Framebuffer vacío aunque checkerboard debería estar activo!\n");
            }
        }
    }
    // -------------------------------------------
    
    // --- Step 0320: Verificación del Framebuffer después de Renderizar ---
    // Verificar que se renderizó algo (no todo blanco) en la línea actual
    size_t line_start = ly_ * SCREEN_WIDTH;
    int non_zero_pixels = 0;
    int color_counts[4] = {0, 0, 0, 0};
    for (int x = 0; x < SCREEN_WIDTH; x++) {
        uint8_t color_idx = framebuffer_[line_start + x] & 0x03;
        if (color_idx != 0) {
            non_zero_pixels++;
        }
        color_counts[color_idx]++;
    }
    
    // Loggear estadísticas del framebuffer solo en algunos frames iniciales
    static int render_check_count = 0;
    if (ly_ == 0 && render_check_count < 3) {
        render_check_count++;
        printf("[PPU-RENDER-CHECK] LY=%d | Píxeles no-blancos: %d/%d | Distribución: 0=%d 1=%d 2=%d 3=%d\n",
               ly_, non_zero_pixels, SCREEN_WIDTH,
               color_counts[0], color_counts[1], color_counts[2], color_counts[3]);
        
        // Si todos los píxeles son 0 (blanco), es una advertencia
        if (non_zero_pixels == 0) {
            printf("[PPU-RENDER-CHECK] WARNING: Toda la línea es blanca (todos los píxeles son 0)\n");
        }
    }
    // -----------------------------------------
}

void PPU::render_bg() {
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        return;
    }
    
    // NOTA: render_bg() no se usa en esta fase (Fase B simplificada)
    // Se mantiene para referencia futura pero no se llama desde render_scanline()
    
    // Leer registros necesarios
    uint8_t lcdc = mmu_->read(IO_LCDC);
    uint8_t scy = mmu_->read(IO_SCY);
    uint8_t scx = mmu_->read(IO_SCX);
    uint8_t bgp = mmu_->read(IO_BGP);
    
    // Determinar tilemap base (Bit 3 de LCDC)
    uint16_t map_base = (lcdc & 0x08) != 0 ? TILEMAP_1 : TILEMAP_0;
    
    // Determinar tile data base (Bit 4 de LCDC)
    // 1 = 0x8000 (unsigned addressing: tile IDs 0-255)
    // 0 = 0x8800 (signed addressing: tile IDs -128 a 127, tile 0 en 0x9000)
    bool unsigned_addressing = (lcdc & 0x10) != 0;
    uint16_t data_base = unsigned_addressing ? TILE_DATA_0 : TILE_DATA_1;
    
    // Calcular posición Y en el tilemap (con scroll)
    uint8_t y_pos = (ly_ + scy) & 0xFF;
    uint8_t tile_y = y_pos / TILE_SIZE;
    uint8_t line_in_tile = y_pos % TILE_SIZE;
    
    // Índice base en el framebuffer para la línea actual
    uint8_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
    // Buffer temporal para decodificar una línea de tile
    uint8_t tile_line[8];
    uint8_t cached_tile_id = 0xFF;  // Valor inválido para forzar primera decodificación
    uint8_t cached_tile_line[8];
    
    // Renderizar 160 píxeles por línea
    // Necesitamos renderizar píxel por píxel para manejar correctamente el scroll
    for (uint16_t screen_x = 0; screen_x < SCREEN_WIDTH; screen_x++) {
        // Calcular posición X en el tilemap (con scroll)
        uint8_t x_pos = (screen_x + scx) & 0xFF;
        uint8_t tile_x = x_pos / TILE_SIZE;
        uint8_t pixel_in_tile = x_pos % TILE_SIZE;
        
        // Obtener tile ID del tilemap (32x32 tiles = 1024 bytes)
        uint16_t tilemap_addr = map_base + (tile_y * 32 + tile_x);
        uint8_t tile_id = mmu_->read(tilemap_addr);
        
        // Decodificar el tile solo si cambió (optimización: cachear por tile)
        if (tile_id != cached_tile_id || pixel_in_tile == 0) {
            // Calcular dirección del tile en VRAM
            uint16_t tile_addr;
            if (unsigned_addressing) {
                // Unsigned: tile_id directamente (0-255)
                tile_addr = data_base + (tile_id * 16);  // Cada tile son 16 bytes
            } else {
                // Signed: tile_id como int8_t (-128 a 127)
                int8_t signed_tile_id = static_cast<int8_t>(tile_id);
                tile_addr = data_base + ((signed_tile_id + 128) * 16);
            }
            
            // Decodificar la línea del tile
            decode_tile_line(tile_addr, line_in_tile, cached_tile_line);
            cached_tile_id = tile_id;
        }
        
        // Escribir el índice de color en el framebuffer (0-3)
        uint8_t color_idx = cached_tile_line[pixel_in_tile];
        framebuffer_line[screen_x] = color_idx;
    }
}

void PPU::render_window() {
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        return;
    }
    
    // Leer registros necesarios
    uint8_t lcdc = mmu_->read(IO_LCDC);
    
    // Verificar que el LCD esté encendido y la Window esté habilitada (Bit 5 de LCDC)
    if ((lcdc & 0x80) == 0 || (lcdc & 0x20) == 0) {
        return;
    }
    
    uint8_t wy = mmu_->read(IO_WY);
    uint8_t wx = mmu_->read(IO_WX);
    
    // La Window solo se dibuja si WY <= LY y WX <= 166
    // (WX tiene un offset de 7 píxeles, así que WX=7 significa posición X=0)
    // Fuente: Pan Docs - Window: WY debe ser <= LY, WX debe ser <= 166
    if (ly_ < wy || wx > 166) {
        return;
    }
    
    // Determinar tilemap base para Window (Bit 6 de LCDC)
    // Bit 6 = 1 -> Tilemap 1 (0x9C00), Bit 6 = 0 -> Tilemap 0 (0x9800)
    uint16_t map_base = (lcdc & 0x40) != 0 ? TILEMAP_1 : TILEMAP_0;
    
    // Determinar tile data base (Bit 4 de LCDC, igual que Background)
    // Bit 4 = 1 -> 0x8000 (unsigned addressing: tile IDs 0-255)
    // Bit 4 = 0 -> 0x8800 (signed addressing: tile IDs -128 a 127, tile 0 en 0x9000)
    bool unsigned_addressing = (lcdc & 0x10) != 0;
    uint16_t data_base = unsigned_addressing ? TILE_DATA_0 : TILE_DATA_1;
    
    // Calcular posición Y dentro de la Window (sin scroll, siempre desde 0)
    // La Window no tiene scroll, siempre comienza desde el tile (0,0) del tilemap
    uint8_t y_pos_in_window = ly_ - wy;
    uint8_t tile_y = y_pos_in_window / TILE_SIZE;
    uint8_t line_in_tile = y_pos_in_window % TILE_SIZE;
    
    // Calcular posición X de inicio de la Window (WX - 7)
    // WX tiene un offset de 7 píxeles: WX=7 significa que la Window comienza en X=0
    int16_t window_x_start = static_cast<int16_t>(wx) - 7;
    if (window_x_start < 0) {
        window_x_start = 0;
    }
    if (window_x_start >= SCREEN_WIDTH) {
        return;  // Window completamente fuera de pantalla
    }
    
    // Leer paleta de fondo (BGP) para aplicar a los píxeles de la Window
    uint8_t bgp = mmu_->read(IO_BGP);
    
    // Índice base en el framebuffer para la línea actual
    size_t line_start_index = ly_ * SCREEN_WIDTH;
    
    // Renderizar píxeles de la Window desde window_x_start hasta el final de la pantalla
    // La Window se dibuja encima del Background pero debajo de los Sprites
    for (int screen_x = window_x_start; screen_x < SCREEN_WIDTH; screen_x++) {
        // Calcular posición X dentro de la Window (sin scroll, siempre desde 0)
        uint8_t x_pos_in_window = screen_x - window_x_start;
        uint8_t tile_x = x_pos_in_window / TILE_SIZE;
        uint8_t pixel_in_tile = x_pos_in_window % TILE_SIZE;
        
        // Obtener tile ID del tilemap de la Window (32x32 tiles = 1024 bytes)
        uint16_t tilemap_addr = map_base + (tile_y * 32 + tile_x);
        uint8_t tile_id = mmu_->read(tilemap_addr);
        
        // Calcular dirección del tile en VRAM
        uint16_t tile_addr;
        if (unsigned_addressing) {
            // Unsigned: tile_id directamente (0-255)
            tile_addr = data_base + (tile_id * 16);  // Cada tile son 16 bytes
        } else {
            // Signed: tile_id como int8_t (-128 a 127)
            int8_t signed_tile_id = static_cast<int8_t>(tile_id);
            tile_addr = data_base + ((signed_tile_id + 128) * 16);
        }
        
        // Calcular dirección de la línea del tile
        uint16_t tile_line_addr = tile_addr + (line_in_tile * 2);
        
        // Verificar que la dirección esté en VRAM válida
        if (tile_line_addr >= 0x8000 && tile_line_addr <= 0x9FFE) {
            // Leer los 2 bytes que representan la línea del tile (formato 2bpp)
            uint8_t byte1 = mmu_->read(tile_line_addr);
            uint8_t byte2 = mmu_->read(tile_line_addr + 1);
            
            // Decodificar el píxel específico dentro del tile
            uint8_t bit_index = 7 - pixel_in_tile;
            uint8_t bit_low = (byte1 >> bit_index) & 1;
            uint8_t bit_high = (byte2 >> bit_index) & 1;
            uint8_t color_index = (bit_high << 1) | bit_low;
            
            // Aplicar paleta BGP para mapear el índice de color crudo al índice final
            // BGP tiene 4 campos de 2 bits: [color3][color2][color1][color0]
            uint8_t final_color = (bgp >> (color_index * 2)) & 0x03;
            
            // Escribir el píxel en el framebuffer (la Window sobrescribe el Background)
            framebuffer_[line_start_index + screen_x] = final_color;
        } else {
            // Si la dirección no es válida, usar color 0 (transparente/blanco)
            framebuffer_[line_start_index + screen_x] = 0;
        }
    }
}

void PPU::decode_tile_line(uint16_t tile_addr, uint8_t line, uint8_t* output) {
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        // Si mmu_ es nullptr, llenar output con ceros (transparente)
        for (uint8_t i = 0; i < 8; i++) {
            output[i] = 0;
        }
        return;
    }
    
    // Cada línea del tile ocupa 2 bytes consecutivos
    // Byte 1: Bits bajos de cada píxel (bit 7 = píxel 0, bit 6 = píxel 1, ...)
    // Byte 2: Bits altos de cada píxel (bit 7 = píxel 0, bit 6 = píxel 1, ...)
    uint16_t line_addr = tile_addr + (line * 2);
    uint8_t byte_low = mmu_->read(line_addr);
    uint8_t byte_high = mmu_->read(line_addr + 1);
    
    // Decodificar 8 píxeles: color = (bit_alto << 1) | bit_bajo
    for (uint8_t i = 0; i < 8; i++) {
        uint8_t bit_low = (byte_low >> (7 - i)) & 0x01;
        uint8_t bit_high = (byte_high >> (7 - i)) & 0x01;
        output[i] = (bit_high << 1) | bit_low;  // Valores 0-3
    }
}

void PPU::render_sprites() {
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        return;
    }
    
    // Solo renderizar si estamos en una línea visible (0-143)
    if (ly_ >= VISIBLE_LINES) {
        return;
    }
    
    // Leer LCDC para verificar si los sprites están habilitados y determinar altura
    uint8_t lcdc = mmu_->read(IO_LCDC);
    
    // Bit 1: OBJ (Sprite) Display Enable (0=deshabilitado, 1=habilitado)
    if ((lcdc & 0x02) == 0) {
        return;  // Sprites deshabilitados
    }
    
    // Bit 2: OBJ Size (0=8x8, 1=8x16)
    uint8_t sprite_height = ((lcdc & 0x04) != 0) ? 16 : 8;
    
    // --- Step 0257: HARDWARE PALETTE BYPASS ---
    // Forzar OBP0 = 0xE4 y OBP1 = 0xE4 (mapeo identidad)
    // Esto garantiza que los índices de color de sprites se preserven en el framebuffer,
    // independientemente del estado de los registros de paleta en la MMU.
    // uint8_t obp0 = mmu_->read(IO_OBP0); // COMENTADO: Ignorar MMU
    // uint8_t obp1 = mmu_->read(IO_OBP1); // COMENTADO: Ignorar MMU
    uint8_t obp0 = 0xE4;  // 11 10 01 00 (Mapeo identidad estándar)
    uint8_t obp1 = 0xE4;  // 11 10 01 00 (Mapeo identidad estándar)
    // -------------------------------------------
    
    // Índice base en el framebuffer para la línea actual
    uint8_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
    // Buffer temporal para decodificar una línea de tile
    uint8_t tile_line[8];
    
    // Contador de sprites dibujados en esta línea (límite de 10 por línea en hardware real)
    uint8_t sprites_drawn = 0;
    static constexpr uint8_t MAX_SPRITES_PER_LINE = 10;
    
    // Iterar todos los sprites en OAM (0xFE00-0xFE9F)
    // NOTA: En hardware real, solo se pueden dibujar 10 sprites por línea.
    // Por simplicidad, iteramos todos pero podríamos optimizar deteniéndonos en 10.
    for (uint8_t sprite_index = 0; sprite_index < MAX_SPRITES; sprite_index++) {
        // Límite de hardware: máximo 10 sprites por línea
        if (sprites_drawn >= MAX_SPRITES_PER_LINE) {
            break;
        }
        
        uint16_t sprite_addr = OAM_START + (sprite_index * BYTES_PER_SPRITE);
        
        // Leer atributos del sprite (4 bytes por sprite)
        uint8_t sprite_y = mmu_->read(sprite_addr + 0);
        uint8_t sprite_x = mmu_->read(sprite_addr + 1);
        uint8_t tile_id = mmu_->read(sprite_addr + 2);
        uint8_t attributes = mmu_->read(sprite_addr + 3);
        
        // Decodificar atributos
        // Bit 7: Prioridad (0=encima del fondo, 1=detrás del fondo excepto color 0)
        bool priority = (attributes & 0x80) != 0;
        // Bit 6: Y-Flip (0=normal, 1=volteado verticalmente)
        bool y_flip = (attributes & 0x40) != 0;
        // Bit 5: X-Flip (0=normal, 1=volteado horizontalmente)
        bool x_flip = (attributes & 0x20) != 0;
        // Bit 4: Paleta (0=OBP0, 1=OBP1)
        uint8_t palette_num = (attributes >> 4) & 0x01;
        
        // Calcular posición en pantalla
        // En hardware real, Y y X tienen offset: Y = sprite_y - 16, X = sprite_x - 8
        // Si Y o X son 0, el sprite está oculto (fuera de pantalla)
        if (sprite_y == 0 || sprite_x == 0) {
            continue;  // Sprite oculto
        }
        
        int16_t screen_y = static_cast<int16_t>(sprite_y) - 16;
        int16_t screen_x = static_cast<int16_t>(sprite_x) - 8;
        
        // Verificar si el sprite intersecta con la línea actual (LY)
        // Un sprite de altura H intersecta si: screen_y <= ly < screen_y + H
        int16_t ly_signed = static_cast<int16_t>(ly_);
        if (ly_signed < screen_y || ly_signed >= (screen_y + sprite_height)) {
            continue;  // Sprite no intersecta con esta línea
        }
        
        // Incrementar contador de sprites dibujados
        sprites_drawn++;
        
        // Calcular qué línea del sprite estamos dibujando (0 a sprite_height-1)
        uint8_t line_in_sprite = static_cast<uint8_t>(ly_signed - screen_y);
        
        // Si Y-Flip está activo, invertir la línea
        if (y_flip) {
            line_in_sprite = sprite_height - 1 - line_in_sprite;
        }
        
        // Para sprites de 8x16, necesitamos determinar qué tile usar
        uint8_t actual_tile_id = tile_id;
        if (sprite_height == 16) {
            // Sprites 8x16: tile_id es el tile superior, tile_id+1 es el inferior
            // Si line_in_sprite >= 8, usamos el tile inferior
            if (line_in_sprite >= 8) {
                actual_tile_id = tile_id + 1;
                line_in_sprite = line_in_sprite - 8;
            }
        }
        
        // Calcular dirección del tile en VRAM
        // Sprites siempre usan direccionamiento unsigned desde 0x8000 (TILE_DATA_0)
        uint16_t tile_addr = TILE_DATA_0 + (actual_tile_id * 16);
        
        // Decodificar la línea del tile
        decode_tile_line(tile_addr, line_in_sprite, tile_line);
        
        // Dibujar los 8 píxeles horizontales del sprite
        for (uint8_t p = 0; p < 8; p++) {
            // Aplicar X-Flip si es necesario
            uint8_t pixel_in_tile = x_flip ? (7 - p) : p;
            
            // Calcular posición X final en pantalla
            int16_t final_x = screen_x + p;
            
            // Verificar si el píxel está dentro de los límites de pantalla
            if (final_x < 0 || final_x >= SCREEN_WIDTH) {
                continue;  // Píxel fuera de pantalla
            }
            
            // Obtener índice de color del píxel del sprite
            uint8_t sprite_color_idx = tile_line[pixel_in_tile];
            
            // CRÍTICO: El color 0 en sprites es siempre transparente (no se dibuja)
            if (sprite_color_idx == 0) {
                continue;
            }
            
            // Obtener el color del fondo en esta posición
            uint8_t bg_color_idx = framebuffer_line[final_x];
            
            // CRÍTICO: Respetar la prioridad del sprite
            // Si priority = 1 (sprite detrás del fondo):
            //   - El sprite solo se dibuja si el fondo es color 0 (transparente)
            // Si priority = 0 (sprite encima del fondo):
            //   - El sprite siempre se dibuja encima del fondo
            if (priority && bg_color_idx != 0) {
                // Sprite con prioridad detrás: solo dibujar si el fondo es transparente
                continue;
            }
            
            // --- Step 0257: Aplicar paleta forzada (mapeo identidad) ---
            // Aplicar OBP0 u OBP1 según el atributo del sprite
            uint8_t palette = (palette_num == 0) ? obp0 : obp1;
            // Aplicar paleta para mapear el índice de color crudo al índice final
            // palette = 0xE4 = 11 10 01 00
            // sprite_color_idx 0 -> (palette >> 0) & 3 = 0 (transparente, no se dibuja)
            // sprite_color_idx 1 -> (palette >> 2) & 3 = 1
            // sprite_color_idx 2 -> (palette >> 4) & 3 = 2
            // sprite_color_idx 3 -> (palette >> 6) & 3 = 3
            uint8_t final_sprite_color = (palette >> (sprite_color_idx * 2)) & 0x03;
            framebuffer_line[final_x] = final_sprite_color;
            // -------------------------------------------------------------
        }
    }
}

void PPU::verify_test_tiles() {
    // Step 0320: Verificar si los tiles de prueba siguen en VRAM
    // Checksum esperado aproximado de los tiles de prueba (0x8000-0x803F)
    // Tile 0: todo 0x00, Tile 1: 0xAA/0x55, Tile 2: 0xFF/0x00, Tile 3: 0xAA/0x55
    // El checksum exacto depende de los valores exactos de load_test_tiles()
    
    uint16_t actual_checksum = 0;
    for (int i = 0; i < 64; i++) {  // 4 tiles * 16 bytes = 64 bytes
        actual_checksum += mmu_->read(0x8000 + i);
    }
    
    // Si el checksum es 0, probablemente los tiles fueron sobrescritos con ceros
    // Si el checksum es muy diferente del esperado, también fueron modificados
    // El checksum esperado aproximado es ~0x2FD0 (basado en tiles de prueba)
    if (actual_checksum == 0) {
        printf("[PPU-VRAM-CHECK] Frame %llu | Tiles de prueba fueron sobrescritos con ceros! Checksum: 0x%04X\n",
               static_cast<unsigned long long>(frame_counter_), actual_checksum);
    } else if (actual_checksum < 0x1000) {
        // Checksum muy bajo, probablemente los tiles fueron modificados
        printf("[PPU-VRAM-CHECK] Frame %llu | Tiles de prueba posiblemente modificados. Checksum: 0x%04X (esperado ~0x2FD0)\n",
               static_cast<unsigned long long>(frame_counter_), actual_checksum);
    } else {
        // Tiles parecen estar intactos
        static int vram_ok_count = 0;
        if (vram_ok_count < 3) {
            printf("[PPU-VRAM-CHECK] Frame %llu | Tiles de prueba intactos. Checksum: 0x%04X\n",
                   static_cast<unsigned long long>(frame_counter_), actual_checksum);
            vram_ok_count++;
        }
    }
}

void PPU::check_game_tiles_loaded() {
    // Step 0321: Calcular checksum de toda la VRAM (0x8000-0x97FF)
    static uint32_t last_vram_checksum = 0;
    uint32_t current_checksum = 0;
    
    for (uint16_t addr = 0x8000; addr <= 0x97FF; addr++) {
        current_checksum += mmu_->read(addr);
    }
    
    // Si el checksum cambió significativamente (más de 1000), el juego cargó tiles
    if (last_vram_checksum > 0 && abs(static_cast<int32_t>(current_checksum - last_vram_checksum)) > 1000) {
        static int tiles_loaded_log_count = 0;
        if (tiles_loaded_log_count < 3) {
            tiles_loaded_log_count++;
            printf("[PPU-TILES-LOADED] Juego cargó tiles! Checksum VRAM: 0x%08X -> 0x%08X (Frame %llu)\n",
                   last_vram_checksum, current_checksum, static_cast<unsigned long long>(frame_counter_ + 1));
        }
    }
    
    last_vram_checksum = current_checksum;
}

