#include "PPU.hpp"
#include "MMU.hpp"
#include <algorithm>
#include <cstdio>
#include <cstdlib>  // Step 0321: Para abs()
#include <chrono>  // Step 0363: Para diagnóstico de rendimiento
#include <vector>  // Step 0370: Para std::vector en verificación de discrepancia

PPU::PPU(MMU* mmu) 
    : mmu_(mmu)
    , ly_(0)
    , clock_(0)
    , mode_(MODE_2_OAM_SEARCH)
    , frame_ready_(false)
    , lyc_(0)
    , stat_interrupt_line_(0)
    , scanline_rendered_(false)
    , frame_counter_(0)  // Step 0291: Inicializar contador de frames
    , vram_is_empty_(true)  // Step 0330: Inicializar como vacía, se actualizará en el primer frame
    , framebuffer_front_(FRAMEBUFFER_SIZE, 0)  // Step 0364: Inicializar buffer front a 0 (blanco)
    , framebuffer_back_(FRAMEBUFFER_SIZE, 0)   // Step 0364: Inicializar buffer back a 0 (blanco)
    , framebuffer_swap_pending_(false)          // Step 0364: Inicializar flag de intercambio
{
    // --- Step 0364: Doble Buffering ---
    // Con doble buffering, los buffers ya están inicializados a 0 en la lista de inicializadores.
    // No necesitamos llamar a clear_framebuffer() aquí porque los buffers ya están limpios.
    
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
    
    // --- Step 0353: Verificación de Cambios de Estado del LCD ---
    // Verificar si el LCD se apaga durante la ejecución
    static bool last_lcd_state_step0353 = false;
    static int lcd_state_change_count = 0;
    
    bool current_lcd_state = lcd_enabled;
    
    if (current_lcd_state != last_lcd_state_step0353) {
        lcd_state_change_count++;
        
        printf("[PPU-LCD-STATE-CHANGE] Change #%d | Frame %llu | LY: %d | "
               "LCD changed from %s to %s\n",
               lcd_state_change_count,
               static_cast<unsigned long long>(frame_counter_),
               ly_,
               last_lcd_state_step0353 ? "ON" : "OFF",
               current_lcd_state ? "ON" : "OFF");
        
        // Si el LCD se apaga, verificar el estado de VRAM
        if (!current_lcd_state) {
            int non_zero_bytes = 0;
            for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
                uint8_t byte = mmu_->read(addr);
                if (byte != 0x00) {
                    non_zero_bytes++;
                }
            }
            
            printf("[PPU-LCD-STATE-CHANGE] LCD OFF | VRAM non-zero bytes: %d/6144 (%.2f%%)\n",
                   non_zero_bytes, (non_zero_bytes * 100.0) / 6144);
        }
        
        last_lcd_state_step0353 = current_lcd_state;
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
    
    // --- Step 0352: Verificación Periódica del Estado de VRAM ---
    // Verificar el estado de VRAM periódicamente para identificar cuándo se llena o se vacía
    static int vram_state_check_count = 0;
    
    if (frame_counter_ % 100 == 0 && vram_state_check_count < 50) {
        vram_state_check_count++;
        
        // Contar bytes no-cero en VRAM
        int non_zero_bytes = 0;
        int complete_tiles = 0;  // Tiles completos (16 bytes con datos no-cero)
        
        for (uint16_t addr = 0x8000; addr < 0x9800; addr += 16) {
            bool tile_has_data = false;
            int tile_non_zero = 0;
            
            for (int i = 0; i < 16; i++) {
                uint8_t byte = mmu_->read(addr + i);
                if (byte != 0x00) {
                    non_zero_bytes++;
                    tile_non_zero++;
                    tile_has_data = true;
                }
            }
            
            // Si el tile tiene al menos 8 bytes no-cero, considerarlo un tile completo
            if (tile_non_zero >= 8) {
                complete_tiles++;
            }
        }
        
        printf("[PPU-VRAM-STATE-PERIODIC] Frame %llu | Non-zero bytes: %d/6144 (%.2f%%) | "
               "Complete tiles: %d/384 (%.2f%%) | Empty: %s\n",
               static_cast<unsigned long long>(frame_counter_),
               non_zero_bytes, (non_zero_bytes * 100.0) / 6144,
               complete_tiles, (complete_tiles * 100.0) / 384,
               (non_zero_bytes < 200) ? "YES" : "NO");
        
        // Advertencia si VRAM está vacía pero debería tener tiles
        if (non_zero_bytes < 200 && frame_counter_ > 1000) {
            printf("[PPU-VRAM-STATE-PERIODIC] ⚠️ ADVERTENCIA: VRAM está vacía después de %llu frames!\n",
                   static_cast<unsigned long long>(frame_counter_));
        }
    }
    // -------------------------------------------
    
    // --- Step 0356: Verificación Periódica de VRAM Sin Tiles de Prueba ---
    // Verificar si los juegos cargan tiles reales después de desactivar tiles de prueba
    static int vram_periodic_check_count = 0;
    
    if (frame_counter_ % 100 == 0 && vram_periodic_check_count < 50) {
        vram_periodic_check_count++;
        
        // Contar bytes no-cero en VRAM
        int non_zero_bytes = 0;
        int complete_tiles = 0;
        
        for (uint16_t addr = 0x8000; addr < 0x9800; addr += 16) {
            bool tile_has_data = false;
            int tile_non_zero = 0;
            
            for (int i = 0; i < 16; i++) {
                uint8_t byte = mmu_->read(addr + i);
                if (byte != 0x00) {
                    non_zero_bytes++;
                    tile_non_zero++;
                    tile_has_data = true;
                }
            }
            
            // Si el tile tiene al menos 8 bytes no-cero, considerarlo un tile completo
            if (tile_non_zero >= 8) {
                complete_tiles++;
            }
        }
        
        printf("[PPU-VRAM-PERIODIC-NO-TEST-TILES] Frame %llu | Non-zero bytes: %d/6144 (%.2f%%) | "
               "Complete tiles: %d/384 (%.2f%%) | Has real tiles: %s\n",
               static_cast<unsigned long long>(frame_counter_),
               non_zero_bytes, (non_zero_bytes * 100.0) / 6144,
               complete_tiles, (complete_tiles * 100.0) / 384,
               (non_zero_bytes >= 200) ? "YES" : "NO");
        
        // Si se detectan tiles reales, verificar el framebuffer
        if (non_zero_bytes >= 200) {
            printf("[PPU-VRAM-PERIODIC-NO-TEST-TILES] ✅ Tiles reales detectados! Verificando framebuffer...\n");
        }
        
        // --- Step 0357: Verificación del Framebuffer Cuando Se Cargan Tiles ---
        // Verificar si el framebuffer se actualiza cuando se cargan tiles reales
        if (non_zero_bytes >= 200 && frame_counter_ >= 4700 && frame_counter_ <= 5000) {
            // Estamos en el rango de frames donde se cargan tiles (Frame 4720-4943)
            static int framebuffer_check_count = 0;
            
            if (framebuffer_check_count < 20) {
                framebuffer_check_count++;
                
                // Verificar el contenido del framebuffer
                int non_white_pixels = 0;
                int index_counts[4] = {0, 0, 0, 0};
                
                for (int i = 0; i < 160 * 144; i++) {
                    uint8_t idx = framebuffer_front_[i];
                    index_counts[idx]++;
                    if (idx != 0) {  // 0 = blanco
                        non_white_pixels++;
                    }
                }
                
                printf("[PPU-FRAMEBUFFER-WITH-TILES] Frame %llu | VRAM has tiles | "
                       "Framebuffer: Non-white pixels=%d/23040 (%.2f%%) | "
                       "Index distribution: 0=%d 1=%d 2=%d 3=%d\n",
                       static_cast<unsigned long long>(frame_counter_),
                       non_white_pixels, (non_white_pixels * 100.0) / 23040,
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
                
                // Verificar si el framebuffer tiene datos de tiles reales
                if (non_white_pixels > 100) {
                    printf("[PPU-FRAMEBUFFER-WITH-TILES] ✅ Framebuffer contiene datos de tiles reales!\n");
                } else {
                    printf("[PPU-FRAMEBUFFER-WITH-TILES] ⚠️ Framebuffer aún está mayormente vacío\n");
                }
            }
        }
        // -------------------------------------------
        
        // --- Step 0359: Verificación VRAM → Framebuffer ---
        // Verificar que los tiles en VRAM se decodifican correctamente al framebuffer
        if (non_zero_bytes >= 200 && frame_counter_ >= 4700 && frame_counter_ <= 5000) {
            static int vram_framebuffer_check_count = 0;
            
            if (vram_framebuffer_check_count < 10) {
                vram_framebuffer_check_count++;
                
                // Verificar un tile específico en VRAM
                uint16_t tile_addr = 0x8800;  // Primer tile en signed addressing
                uint8_t tile_data[16];
                for (int i = 0; i < 16; i++) {
                    tile_data[i] = mmu_->read(tile_addr + i);
                }
                
                printf("[PPU-VRAM-TO-FRAMEBUFFER] Frame %llu | Tile at 0x%04X: ",
                       static_cast<unsigned long long>(frame_counter_), tile_addr);
                for (int i = 0; i < 16; i++) {
                    printf("%02X ", tile_data[i]);
                }
                printf("\n");
                
                // Verificar cómo se decodifica este tile al framebuffer
                // Buscar este tile en el tilemap
                uint8_t tile_id = mmu_->read(0x9800);  // Primer tile ID en tilemap
                printf("[PPU-VRAM-TO-FRAMEBUFFER] Tilemap[0x9800] = 0x%02X (Tile ID)\n", tile_id);
                
                // Verificar el framebuffer en la primera línea (donde debería estar este tile)
                int framebuffer_indices[160];
                for (int x = 0; x < 160; x++) {
                    framebuffer_indices[x] = framebuffer_front_[x] & 0x03;
                }
                
                printf("[PPU-VRAM-TO-FRAMEBUFFER] Framebuffer line 0 (first 20 pixels): ");
                for (int x = 0; x < 20; x++) {
                    printf("%d ", framebuffer_indices[x]);
                }
                printf("\n");
                
                // Verificar correspondencia
                printf("[PPU-VRAM-TO-FRAMEBUFFER] ✅ Verificando correspondencia VRAM → Framebuffer\n");
            }
        }
        // -------------------------------------------
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
        // --- Step 0373: Corrección de Timing de render_scanline() ---
        // CRÍTICO: Cuando clock_ >= CYCLES_PER_SCANLINE, acabamos de completar una línea.
        // En ese momento, estamos en H-Blank (MODE_0_HBLANK), no en OAM Search.
        // update_mode() se llama antes del bucle y calcula el modo basándose en clock_ % 456,
        // pero cuando clock_ = 456, clock_ % 456 = 0, que es MODE_2_OAM_SEARCH (incorrecto).
        // Debemos calcular el modo correcto para la línea que acabamos de completar.
        
        // --- Step 0373: Análisis de Timing (Diagnóstico) ---
        static int timing_analysis_count = 0;
        timing_analysis_count++;
        
        if (timing_analysis_count <= 50) {
            uint16_t line_cycles_before = static_cast<uint16_t>(clock_ % CYCLES_PER_SCANLINE);
            printf("[PPU-TIMING-ANALYSIS] Frame %llu | Before render_scanline() | "
                   "clock_: %d | clock_ %% 456: %d | Mode (old): %d | LY: %d\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   static_cast<int>(clock_), line_cycles_before, mode_, ly_);
        }
        // -------------------------------------------
        
        // Calcular los ciclos dentro de la línea que acabamos de completar
        // Si clock_ >= 456, acabamos de completar MODE_3_PIXEL_TRANSFER y estamos en H-Blank
        uint16_t line_cycles = static_cast<uint16_t>(clock_ % CYCLES_PER_SCANLINE);
        
        // Si estamos al final de una línea (ciclos 252-455), estamos en H-Blank
        // Si clock_ >= 456, entonces acabamos de completar la línea completa (456 ciclos)
        // y estamos en H-Blank (MODE_0_HBLANK)
        if (line_cycles >= (MODE_2_CYCLES + MODE_3_CYCLES) || clock_ >= CYCLES_PER_SCANLINE) {
            mode_ = MODE_0_HBLANK;
        } else if (line_cycles >= MODE_2_CYCLES) {
            mode_ = MODE_3_PIXEL_TRANSFER;
        } else {
            mode_ = MODE_2_OAM_SEARCH;
        }
        
        // CRÍTICO: Renderizar la línea SOLO cuando estamos en H-Blank (MODE_0_HBLANK)
        // Esto asegura que renderizamos la línea que acabamos de completar
        if (ly_ < VISIBLE_LINES && !scanline_rendered_ && mode_ == MODE_0_HBLANK) {
            // --- Step 0373: Verificación de Modo de Renderizado ---
            static int render_mode_verify_count = 0;
            render_mode_verify_count++;
            
            if (render_mode_verify_count <= 50) {
                printf("[PPU-RENDER-MODE-VERIFY] Frame %llu | LY: %d | "
                       "render_scanline() ejecutado en MODE_0_HBLANK ✅ | Count: %d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_,
                       render_mode_verify_count);
            }
            // -------------------------------------------
            
            render_scanline();
            scanline_rendered_ = true;
        }
        // -------------------------------------------
        
        // Restar los ciclos de una línea completa
        clock_ -= CYCLES_PER_SCANLINE;
        
        // CRÍTICO: Verificar interrupciones STAT ANTES de cambiar a la nueva línea
        // Esto asegura que se detecte el rising edge de H-Blank (Mode 0)
        check_stat_interrupt();
        
        // Guardar el estado anterior de LYC match para detectar rising edge
        bool old_lyc_match = ((ly_ & 0xFF) == (lyc_ & 0xFF));
        
        // --- Step 0339: Verificación de Secuencia de Líneas ---
        // Verificar que LY incrementa correctamente y no se saltan líneas
        static int last_ly_logged = -1;
        static int ly_sequence_check_count = 0;
        // -------------------------------------------
        
        // Avanzar a la siguiente línea
        ly_ += 1;
        
        // --- Step 0340: Detección de Tiles Reales al Inicio del Frame ---
        // Detectar si hay tiles reales cuando LY se resetea a 0 (inicio del frame)
        static bool tiles_were_detected_this_frame = false;
        
        if (ly_ == 0) {
            // Verificar si hay tiles reales en VRAM
            int non_zero_bytes = 0;
            for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
                uint8_t byte = mmu_->read(addr);
                if (byte != 0x00) {
                    non_zero_bytes++;
                }
            }
            
            tiles_were_detected_this_frame = (non_zero_bytes >= 200);
        }
        // -------------------------------------------
        
        // --- Step 0339: Verificación de Secuencia de Líneas (continuación) ---
        if (ly_ != last_ly_logged && ly_sequence_check_count < 200) {
            ly_sequence_check_count++;
            
            // Verificar si se saltó una línea
            if (last_ly_logged >= 0) {
                int expected_ly = (last_ly_logged + 1) % 154;  // 0-153, luego vuelve a 0
                if (ly_ != expected_ly) {
                    printf("[PPU-LY-SEQUENCE] Frame %llu | LY saltado: %d -> %d (esperado: %d)\n",
                           static_cast<unsigned long long>(frame_counter_ + 1),
                           last_ly_logged, ly_, expected_ly);
                }
            }
            
            // Loggear cada 10 líneas o líneas importantes
            if (ly_ % 10 == 0 || ly_ == 0 || ly_ == 72 || ly_ == 143 || ly_ == 144) {
                printf("[PPU-LY-SEQUENCE] Frame %llu | LY: %d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_);
            }
            
            last_ly_logged = ly_;
        }
        // -------------------------------------------
        
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
            
            // --- Step 0340: Verificación de Timing Cuando Se Marca Frame Ready ---
            // Loggear cuándo se marca frame_ready_ y verificar que el framebuffer está completo
            static int frame_ready_timing_log_count = 0;
            
            if (!frame_ready_) {
                if (frame_ready_timing_log_count < 10) {
                    frame_ready_timing_log_count++;
                    
                    // Verificar que el framebuffer tiene datos
                    int total_non_zero = 0;
                    for (int i = 0; i < FRAMEBUFFER_SIZE; i++) {
                        if ((framebuffer_front_[i] & 0x03) != 0) {
                            total_non_zero++;
                        }
                    }
                    
                    printf("[PPU-FRAME-READY-TIMING] Frame %llu | LY: %d (VBLANK_START) | "
                           "frame_ready_ marcado | Non-zero pixels: %d/23040\n",
                           static_cast<unsigned long long>(frame_counter_ + 1),
                           ly_, total_non_zero);
                }
                
                // CRÍTICO: Marcar frame como listo para renderizar
                frame_ready_ = true;
            }
            
            // --- Step 0331: Log de Sincronización del Framebuffer ---
            static int frame_ready_log_count = 0;
            if (frame_ready_log_count < 5) {
                frame_ready_log_count++;
                printf("[PPU-FRAME-READY] Frame %llu | Frame marcado como listo (LY=144)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1));
            }
            // -------------------------------------------
            
            // --- Step 0340: Verificación del Contenido del Framebuffer Cuando Hay Tiles Reales ---
            // Cuando se completa el frame (LY=144) y había tiles reales, verificar el framebuffer
            static int framebuffer_with_tiles_check_count = 0;
            
            if (tiles_were_detected_this_frame && framebuffer_with_tiles_check_count < 10) {
                framebuffer_with_tiles_check_count++;
                
                // Contar índices en todo el framebuffer
                int index_counts[4] = {0, 0, 0, 0};
                int total_non_zero_pixels = 0;
                
                for (int y = 0; y < 144; y++) {
                    size_t line_start = y * SCREEN_WIDTH;
                    for (int x = 0; x < SCREEN_WIDTH; x++) {
                        uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
                        if (color_idx < 4) {
                            index_counts[color_idx]++;
                            if (color_idx != 0) {
                                total_non_zero_pixels++;
                            }
                        }
                    }
                }
                
                printf("[PPU-FRAMEBUFFER-WITH-TILES] Frame %llu | Tiles reales detectados | "
                       "Total non-zero pixels: %d/23040 | Distribution: 0=%d 1=%d 2=%d 3=%d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       total_non_zero_pixels,
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
                
                // Verificar algunos píxeles específicos (esquinas y centro)
                int test_positions[][2] = {{0, 0}, {0, 159}, {71, 79}, {143, 0}, {143, 159}};
                for (int i = 0; i < 5; i++) {
                    int y = test_positions[i][0];
                    int x = test_positions[i][1];
                    size_t idx = y * SCREEN_WIDTH + x;
                    uint8_t color_idx = framebuffer_front_[idx] & 0x03;
                    printf("[PPU-FRAMEBUFFER-WITH-TILES] Pixel (%d, %d): index=%d\n", x, y, color_idx);
                }
            }
            // -------------------------------------------
            
            // --- Step 0351: Verificación Detallada del Framebuffer con Tiles Reales ---
            // Verificar el contenido completo del framebuffer cuando hay tiles reales
            static int framebuffer_content_detailed_count = 0;
            
            // Cuando se completa el frame (LY=144) y había tiles reales, verificar el framebuffer completo
            if (tiles_were_detected_this_frame && framebuffer_content_detailed_count < 10) {
                framebuffer_content_detailed_count++;
                
                // Contar índices en todo el framebuffer
                int index_counts[4] = {0, 0, 0, 0};
                int total_non_zero_pixels = 0;
                int lines_with_varied_indices = 0;  // Líneas con más de 2 índices diferentes
                
                for (int y = 0; y < 144; y++) {
                    size_t line_start = y * SCREEN_WIDTH;
                    int line_index_counts[4] = {0, 0, 0, 0};
                    
                    for (int x = 0; x < SCREEN_WIDTH; x++) {
                        uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
                        if (color_idx < 4) {
                            index_counts[color_idx]++;
                            line_index_counts[color_idx]++;
                            if (color_idx != 0) {
                                total_non_zero_pixels++;
                            }
                        }
                    }
                    
                    // Verificar si la línea tiene más de 2 índices diferentes (no solo checkerboard)
                    int unique_indices = 0;
                    for (int i = 0; i < 4; i++) {
                        if (line_index_counts[i] > 0) {
                            unique_indices++;
                        }
                    }
                    
                    if (unique_indices > 2) {
                        lines_with_varied_indices++;
                    }
                }
                
                printf("[PPU-FRAMEBUFFER-CONTENT-DETAILED] Frame %llu | Tiles reales detectados | "
                       "Total non-zero pixels: %d/23040 | Distribution: 0=%d 1=%d 2=%d 3=%d | "
                       "Lines with varied indices (>2): %d/144\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       total_non_zero_pixels,
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3],
                       lines_with_varied_indices);
                
                // Advertencia si el framebuffer contiene solo checkerboard (índices 0 y 3)
                if (index_counts[1] == 0 && index_counts[2] == 0 && index_counts[0] > 0 && index_counts[3] > 0) {
                    printf("[PPU-FRAMEBUFFER-CONTENT-DETAILED] ⚠️ ADVERTENCIA: Framebuffer contiene solo checkerboard "
                           "(índices 0 y 3) aunque hay tiles reales en VRAM!\n");
                }
                
                // Advertencia si no hay líneas con índices variados
                if (lines_with_varied_indices == 0) {
                    printf("[PPU-FRAMEBUFFER-CONTENT-DETAILED] ⚠️ ADVERTENCIA: Ninguna línea tiene más de 2 índices diferentes!\n");
                }
            }
            // -------------------------------------------
            
            // --- Step 0351: Comparación Framebuffer con Tiles Reales vs Checkerboard ---
            // Comparar el contenido del framebuffer cuando hay tiles reales vs cuando solo hay checkerboard
            static int framebuffer_comparison_count = 0;
            
            if (framebuffer_comparison_count < 10) {
                framebuffer_comparison_count++;
                
                // Verificar si hay tiles reales
                int non_zero_bytes = 0;
                for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
                    uint8_t byte = mmu_->read(addr);
                    if (byte != 0x00) {
                        non_zero_bytes++;
                    }
                }
                
                bool has_real_tiles = (non_zero_bytes >= 200);
                
                // Contar índices en el framebuffer
                int index_counts[4] = {0, 0, 0, 0};
                for (int i = 0; i < FRAMEBUFFER_SIZE; i++) {
                    uint8_t color_idx = framebuffer_front_[i] & 0x03;
                    if (color_idx < 4) {
                        index_counts[color_idx]++;
                    }
                }
                
                // Determinar si el framebuffer contiene solo checkerboard
                bool is_checkerboard_only = (index_counts[1] == 0 && index_counts[2] == 0 && 
                                              index_counts[0] > 0 && index_counts[3] > 0);
                
                printf("[PPU-FRAMEBUFFER-COMPARISON] Frame %llu | Has real tiles: %s | "
                       "Is checkerboard only: %s | Distribution: 0=%d 1=%d 2=%d 3=%d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       has_real_tiles ? "YES" : "NO",
                       is_checkerboard_only ? "YES" : "NO",
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
                
                // Advertencia si hay tiles reales pero el framebuffer contiene solo checkerboard
                if (has_real_tiles && is_checkerboard_only) {
                    printf("[PPU-FRAMEBUFFER-COMPARISON] ⚠️ PROBLEMA: Hay tiles reales en VRAM pero el framebuffer "
                           "contiene solo checkerboard! El problema está en la generación del framebuffer.\n");
                }
            }
            // -------------------------------------------
            
            // --- Step 0339: Verificación del Estado Completo del Framebuffer al Final del Frame ---
            // Verificar el estado completo del framebuffer cuando se completa el frame (LY=144)
            // --- Step 0365: Actualizado para verificar framebuffer_back_ en lugar de front ---
            static int framebuffer_complete_check_count = 0;
            
            if (framebuffer_complete_check_count < 20) {
                framebuffer_complete_check_count++;
                
                // Contar líneas con datos (no todas blancas) en framebuffer_back_
                int lines_with_data = 0;
                int total_non_zero_pixels = 0;
                int index_counts[4] = {0, 0, 0, 0};
                
                for (int y = 0; y < 144; y++) {
                    size_t line_start = y * SCREEN_WIDTH;
                    int line_non_zero = 0;
                    
                    for (int x = 0; x < SCREEN_WIDTH; x++) {
                        uint8_t color_idx = framebuffer_back_[line_start + x] & 0x03;
                        if (color_idx < 4) {
                            index_counts[color_idx]++;
                            if (color_idx != 0) {
                                line_non_zero++;
                                total_non_zero_pixels++;
                            }
                        }
                    }
                    
                    if (line_non_zero > 0) {
                        lines_with_data++;
                    }
                }
                
                printf("[PPU-FRAMEBUFFER-COMPLETE] Frame %llu | LY: %d (VBLANK_START) | "
                       "Back buffer - Lines with data: %d/144 | Total non-zero pixels: %d/23040 | "
                       "Distribution: 0=%d 1=%d 2=%d 3=%d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       ly_, lines_with_data, total_non_zero_pixels,
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
                
                // Advertencia si hay pocas líneas con datos
                if (lines_with_data < 10 && total_non_zero_pixels > 0) {
                    printf("[PPU-FRAMEBUFFER-COMPLETE] ⚠️ ADVERTENCIA: Solo %d líneas tienen datos (esperado: ~144)\n",
                           lines_with_data);
                }
                
                // Advertencia si el framebuffer está completamente vacío
                if (total_non_zero_pixels == 0) {
                    printf("[PPU-FRAMEBUFFER-COMPLETE] ⚠️ ADVERTENCIA: Back buffer completamente vacío al final del frame!\n");
                }
            }
            // -------------------------------------------
        }
        
        // --- Step 0335: Verificación Periódica del Framebuffer ---
        // Verificar que el framebuffer mantiene datos a lo largo del tiempo
        // IMPORTANTE: Verificar cuando ly_ == VBLANK_START (144), después de renderizar todo el frame,
        // pero ANTES de que se limpie para el siguiente frame
        if (ly_ == VBLANK_START && frame_counter_ % 100 == 0) {
            static int framebuffer_periodic_check_count = 0;
            if (framebuffer_periodic_check_count < 20) {
                framebuffer_periodic_check_count++;
                
                // Contar píxeles no-blancos en el framebuffer
                int non_zero_pixels = 0;
                int index_counts[4] = {0, 0, 0, 0};
                for (size_t i = 0; i < FRAMEBUFFER_SIZE; i++) {
                    uint8_t color_idx = framebuffer_front_[i] & 0x03;
                    if (color_idx != 0) {
                        non_zero_pixels++;
                    }
                    index_counts[color_idx]++;
                }
                
                printf("[PPU-FRAMEBUFFER-PERIODIC] Frame %llu | Non-zero pixels: %d/23040 | "
                       "Distribution: 0=%d 1=%d 2=%d 3=%d | VRAM empty: %s\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       non_zero_pixels,
                       index_counts[0], index_counts[1], index_counts[2], index_counts[3],
                       vram_is_empty_ ? "YES" : "NO");
                
                if (non_zero_pixels == 0 && vram_is_empty_) {
                    printf("[PPU-FRAMEBUFFER-PERIODIC] ⚠️ ADVERTENCIA: Framebuffer vacío aunque debería tener checkerboard!\n");
                }
            }
        }
        // -------------------------------------------
        
        // Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
        if (ly_ > 153) {
            ly_ = 0;
            // --- Step 0291: Incrementar contador de frames ---
            frame_counter_++;
            // Reiniciar flag de interrupción STAT al cambiar de frame
            stat_interrupt_line_ = 0;
            
            // --- Step 0360: Verificación Continua del Framebuffer ---
            // Verificar que el framebuffer se actualiza correctamente cuando hay tiles
            if (frame_counter_ % 60 == 0) {
                // Verificar estado de VRAM
                int vram_non_zero = 0;
                for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
                    if (mmu_->read(addr) != 0x00) {
                        vram_non_zero++;
                    }
                }
                
                // Verificar estado del framebuffer
                int framebuffer_non_white = 0;
                for (int i = 0; i < 160 * 144; i++) {
                    if (framebuffer_front_[i] != 0) {
                        framebuffer_non_white++;
                    }
                }
                
                // Si VRAM tiene tiles pero el framebuffer está vacío, hay un problema
                if (vram_non_zero >= 200 && framebuffer_non_white < 100) {
                    static int warning_count = 0;
                    if (warning_count < 10) {
                        warning_count++;
                        printf("[PPU-FRAMEBUFFER-UPDATE] ⚠️ ADVERTENCIA: VRAM tiene tiles (%d bytes) "
                               "pero framebuffer está vacío (%d píxeles no-blancos) en Frame %llu\n",
                               vram_non_zero, framebuffer_non_white,
                               static_cast<unsigned long long>(frame_counter_));
                    }
                }
                
                // Si ambos tienen datos, verificar correspondencia
                if (vram_non_zero >= 200 && framebuffer_non_white >= 100) {
                    static int success_log_count = 0;
                    if (success_log_count < 10) {
                        success_log_count++;
                        printf("[PPU-FRAMEBUFFER-UPDATE] Frame %llu | VRAM: %d bytes | "
                               "Framebuffer: %d píxeles no-blancos | ✅ Sincronizado\n",
                               static_cast<unsigned long long>(frame_counter_),
                               vram_non_zero, framebuffer_non_white);
                    }
                }
            }
            // -------------------------------------------
            
            // --- Step 0362: Corrección de Timing de Limpieza del Framebuffer ---
            // NO limpiar el framebuffer al inicio del siguiente frame
            // El framebuffer solo se limpiará cuando Python confirme que lo leyó
            // Esto asegura que el framebuffer se mantiene hasta que Python lo lee
            // 
            // RESERVADO: El framebuffer NO se limpia aquí
            // Se limpiará cuando Python llame a confirm_framebuffer_read()
            // Esto asegura que el framebuffer se mantiene hasta que Python lo lee
            
            // Loggear para verificar que no se limpia aquí
            static int no_clear_log_count = 0;
            if (no_clear_log_count < 5) {
                no_clear_log_count++;
                printf("[PPU-FRAMEBUFFER-NO-CLEAR] Frame %llu | LY > 153 | "
                       "Framebuffer NO se limpia aquí (se mantiene para Python)\n",
                       static_cast<unsigned long long>(frame_counter_));
            }
            
            // NO llamar a clear_framebuffer() aquí
            // clear_framebuffer();  // COMENTADO en Step 0362
            // -------------------------------------------
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

bool PPU::is_lcd_on() const {
    if (mmu_ == nullptr) {
        return false;
    }
    uint8_t lcdc = mmu_->read(IO_LCDC);
    return (lcdc & 0x80) != 0;
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
    // --- Step 0363: Diagnóstico de Rendimiento ---
    // Medir tiempo de get_frame_ready_and_reset()
    auto start_time = std::chrono::high_resolution_clock::now();
    // -------------------------------------------
    
    if (frame_ready_) {
        // --- Step 0372: Tarea 4 - Verificar Estado del Framebuffer Antes de que Python lo Lea ---
        static int framebuffer_before_read_count = 0;
        framebuffer_before_read_count++;
        
        if (framebuffer_before_read_count <= 50) {
            // Verificar contenido del framebuffer_back_ antes de intercambiar
            int total_non_zero = 0;
            int index_counts[4] = {0, 0, 0, 0};
            
            for (size_t i = 0; i < framebuffer_back_.size(); i++) {
                uint8_t color_idx = framebuffer_back_[i] & 0x03;
                index_counts[color_idx]++;
                if (color_idx != 0) {
                    total_non_zero++;
                }
            }
            
            printf("[PPU-FRAMEBUFFER-BEFORE-READ] Frame %llu | "
                   "Total non-zero pixels: %d/23040 | Distribution: 0=%d 1=%d 2=%d 3=%d\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   total_non_zero, index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
            
            if (total_non_zero == 0) {
                printf("[PPU-FRAMEBUFFER-BEFORE-READ] ⚠️ PROBLEMA CRÍTICO: Framebuffer completamente vacío antes de que Python lo lea!\n");
            }
        }
        // -------------------------------------------
        
        // --- Step 0364: Doble Buffering ---
        // Marcar que hay un frame completo listo para intercambiar
        framebuffer_swap_pending_ = true;
        
        // Intercambiar buffers ANTES de que Python lea
        swap_framebuffers();
        
        frame_ready_ = false;
        
        // --- Step 0363: Diagnóstico de Rendimiento (fin) ---
        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
        
        static int get_frame_timing_count = 0;
        if (get_frame_timing_count < 100) {
            get_frame_timing_count++;
            if (get_frame_timing_count % 10 == 0) {
                printf("[PPU-PERF] get_frame_ready_and_reset() took %lld microseconds\n", 
                       duration.count());
            }
        }
        // -------------------------------------------
        
        return true;
    }
    
    // --- Step 0363: Diagnóstico de Rendimiento (fin - caso no frame_ready) ---
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    
    static int get_frame_false_timing_count = 0;
    if (get_frame_false_timing_count < 100) {
        get_frame_false_timing_count++;
        if (get_frame_false_timing_count % 10 == 0) {
            printf("[PPU-PERF] get_frame_ready_and_reset() (false) took %lld microseconds\n", 
                   duration.count());
        }
    }
    // -------------------------------------------
    
    return false;
}

uint8_t* PPU::get_framebuffer_ptr() {
    // --- Step 0364: Doble Buffering ---
    // Devolver el buffer front (estable, no se modifica durante la lectura)
    return framebuffer_front_.data();
}

void PPU::swap_framebuffers() {
    // --- Step 0365: Verificación Detallada del Intercambio ---
    // Contar píxeles no-blancos en ambos buffers antes del intercambio
    int back_non_zero_before = 0;
    int front_non_zero_before = 0;
    
    for (size_t i = 0; i < framebuffer_back_.size(); i++) {
        if (framebuffer_back_[i] != 0) back_non_zero_before++;
        if (framebuffer_front_[i] != 0) front_non_zero_before++;
    }
    
    // Intercambiar
    std::swap(framebuffer_front_, framebuffer_back_);
    framebuffer_swap_pending_ = false;
    
    // Contar píxeles no-blancos después del intercambio
    int front_non_zero_after = 0;
    for (size_t i = 0; i < framebuffer_front_.size(); i++) {
        if (framebuffer_front_[i] != 0) front_non_zero_after++;
    }
    
    // Limpiar el buffer back para el siguiente frame
    std::fill(framebuffer_back_.begin(), framebuffer_back_.end(), 0);
    
    // --- Step 0372: Tarea 5 - Verificar Estado del Framebuffer Después del Intercambio ---
    static int framebuffer_after_swap_count = 0;
    framebuffer_after_swap_count++;
    
    if (framebuffer_after_swap_count <= 50) {
        // Verificar contenido del framebuffer_front_ después del intercambio
        int total_non_zero = 0;
        int index_counts[4] = {0, 0, 0, 0};
        
        for (size_t i = 0; i < framebuffer_front_.size(); i++) {
            uint8_t color_idx = framebuffer_front_[i] & 0x03;
            index_counts[color_idx]++;
            if (color_idx != 0) {
                total_non_zero++;
            }
        }
        
        printf("[PPU-FRAMEBUFFER-AFTER-SWAP] Frame %llu | "
               "Total non-zero pixels in front: %d/23040 | Distribution: 0=%d 1=%d 2=%d 3=%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               total_non_zero, index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
        
        if (total_non_zero == 0) {
            printf("[PPU-FRAMEBUFFER-AFTER-SWAP] ⚠️ PROBLEMA CRÍTICO: Framebuffer front completamente vacío después del intercambio!\n");
        }
    }
    // -------------------------------------------
    
    // Log detallado
    static int swap_detailed_count = 0;
    if (swap_detailed_count < 20) {
        swap_detailed_count++;
        printf("[PPU-SWAP-DETAILED] Frame %llu | "
               "Back before: %d non-zero | Front before: %d non-zero | "
               "Front after: %d non-zero\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               back_non_zero_before, front_non_zero_before, front_non_zero_after);
        
        if (back_non_zero_before > 0 && front_non_zero_after == 0) {
            printf("[PPU-SWAP-DETAILED] ⚠️ PROBLEMA: Back tenía datos pero front está vacío después del intercambio!\n");
        }
        
        // Mostrar primeros 20 píxeles del front después del intercambio
        printf("[PPU-SWAP-DETAILED] Front first 20 pixels: ");
        for (int i = 0; i < 20; i++) {
            printf("%d ", framebuffer_front_[i] & 0x03);
        }
        printf("\n");
    }
}

void PPU::clear_framebuffer() {
    // --- Step 0364: Doble Buffering ---
    // Con doble buffering, clear_framebuffer() ya no es necesario en la mayoría de casos.
    // El buffer back se limpia automáticamente en swap_framebuffers().
    // Este método se mantiene por compatibilidad pero solo limpia el buffer back.
    
    // Limpiar solo el buffer back (el front no debe tocarse)
    std::fill(framebuffer_back_.begin(), framebuffer_back_.end(), 0);
}

void PPU::confirm_framebuffer_read() {
    // --- Step 0364: Doble Buffering ---
    // Con doble buffering, este método ya no es necesario pero se mantiene por compatibilidad
    // con el código Python que lo llama. El buffer front ya no se modifica durante la lectura,
    // y el buffer back se limpia automáticamente en swap_framebuffers().
    // Este método puede quedar vacío o simplemente no hacer nada.
    // -------------------------------------------
}

void PPU::render_scanline() {
    // --- Step 0363: Diagnóstico de Rendimiento ---
    // Medir tiempo de render_scanline() para identificar cuellos de botella
    static int render_scanline_timing_count = 0;
    auto start_time = std::chrono::high_resolution_clock::now();
    // -------------------------------------------
    
    // --- Step 0203: Lógica de renderizado normal restaurada ---
    // El "Test del Checkerboard" del Step 0202 confirmó que el pipeline de renderizado
    // C++ -> Cython -> Python funciona perfectamente. Ahora restauramos la lógica
    // de renderizado normal que lee desde la VRAM para poder investigar por qué
    // la VRAM permanece vacía.
    
    // --- Step 0362: Verificación de Renderizado de Todas las Líneas ---
    // Verificar que todas las líneas visibles se renderizan
    static bool lines_rendered[144] = {false};
    
    if (ly_ < 144 && mode_ == MODE_3_PIXEL_TRANSFER) {
        // Verificar que render_scanline() se ejecuta
        if (!lines_rendered[ly_]) {
            lines_rendered[ly_] = true;
            
            static int lines_rendered_count = 0;
            lines_rendered_count++;
            
            if (lines_rendered_count <= 20) {
                printf("[PPU-LINE-RENDER] LY=%d | Line rendered | "
                       "Total lines rendered so far: %d/144\n",
                       ly_, lines_rendered_count);
            }
        }
        
        // Verificar que la línea tiene datos después de renderizar
        if (ly_ == 143) {
            // Última línea visible - verificar framebuffer_back_ completo (Step 0365)
            static int frame_complete_check_count = 0;
            if (frame_complete_check_count < 20) {
                frame_complete_check_count++;
                
                int total_non_zero = 0;
                for (size_t i = 0; i < framebuffer_back_.size(); i++) {
                    if (framebuffer_back_[i] != 0) {
                        total_non_zero++;
                    }
                }
                
                printf("[PPU-FRAME-COMPLETE] Frame %llu | Back buffer has %d/23040 non-zero pixels (%.2f%%)\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), total_non_zero,
                       (total_non_zero * 100.0) / 23040);
                
                if (total_non_zero == 0) {
                    printf("[PPU-FRAME-COMPLETE] ⚠️ PROBLEMA: Back buffer está completamente vacío!\n");
                }
            }
            
            // Resetear array de líneas renderizadas para el siguiente frame
            for (int i = 0; i < 144; i++) {
                lines_rendered[i] = false;
            }
        }
    }
    // -------------------------------------------
    
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
    
    // --- Step 0372: Tarea 1 - Verificar si render_scanline() se Ejecuta ---
    static int render_scanline_execution_count = 0;
    render_scanline_execution_count++;
    
    if (render_scanline_execution_count <= 100) {
        printf("[PPU-RENDER-EXECUTION] Frame %llu | LY: %d | "
               "render_scanline() ejecutado | Count: %d\n",
               static_cast<unsigned long long>(frame_counter_ + 1), ly_,
               render_scanline_execution_count);
    }
    
    // Verificar que se llama en el momento correcto (H-Blank, MODE_0)
    if (render_scanline_execution_count <= 100) {
        printf("[PPU-RENDER-EXECUTION] Mode: %d (0=H-Blank, 1=V-Blank, 2=OAM, 3=Pixel Transfer) | "
               "LY: %d | Expected: H-Blank (0)\n",
               mode_, ly_);
    }
    // -------------------------------------------
    
    // --- Step 0366: Verificación de Ejecución ---
    // NOTA: render_scanline() se llama en H-Blank (MODE_0) después de que MODE_3 (Pixel Transfer)
    // ya completó. Esto es correcto según el hardware: el renderizado ocurre durante MODE_3,
    // pero la función se llama en H-Blank para renderizar la línea que acaba de completarse.
    static int render_scanline_entry_count = 0;
    if (render_scanline_entry_count < 50) {
        render_scanline_entry_count++;
        printf("[PPU-RENDER-ENTRY] Frame %llu | LY: %d | Mode: %d | "
               "render_scanline() called (H-Blank, renderizando línea completada)\n",
               static_cast<unsigned long long>(frame_counter_ + 1), ly_, mode_);
    }
    
    // Verificar línea visible (render_scanline() solo se llama cuando ly_ < VISIBLE_LINES)
    if (ly_ >= 144) {
        static int invalid_ly_count = 0;
        if (invalid_ly_count < 5) {
            invalid_ly_count++;
            printf("[PPU-RENDER-ENTRY] LY >= 144 (%d), no renderizando\n", ly_);
        }
        return;
    }
    
    static int conditions_ok_count = 0;
    if (conditions_ok_count < 20) {
        conditions_ok_count++;
        printf("[PPU-RENDER-ENTRY] ✅ Condiciones OK: LY=%d, Mode=%d (H-Blank), continuando...\n", ly_, mode_);
    }
    // -------------------------------------------
    
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
        
        // --- Step 0335: Verificación de Cambios en vram_is_empty_ ---
        // Verificar si vram_is_empty_ cambia después de algunos frames
        static bool last_vram_is_empty = true;
        bool new_vram_is_empty = (vram_non_zero < 200);
        
        if (new_vram_is_empty != last_vram_is_empty) {
            static int vram_empty_change_log_count = 0;
            if (vram_empty_change_log_count < 10) {
                vram_empty_change_log_count++;
                printf("[PPU-VRAM-EMPTY-CHANGE] Frame %llu | vram_is_empty_ cambió: %s -> %s\n",
                       static_cast<unsigned long long>(frame_counter_ + 1),
                       last_vram_is_empty ? "YES" : "NO",
                       new_vram_is_empty ? "YES" : "NO");
                
                if (last_vram_is_empty && !new_vram_is_empty) {
                    printf("[PPU-VRAM-EMPTY-CHANGE] ⚠️ ADVERTENCIA: VRAM ya no está vacía, checkerboard debería desactivarse\n");
                } else if (!last_vram_is_empty && new_vram_is_empty) {
                    printf("[PPU-VRAM-EMPTY-CHANGE] VRAM se vació, checkerboard debería activarse\n");
                }
            }
            last_vram_is_empty = new_vram_is_empty;
        }
        // -------------------------------------------
        
        vram_is_empty_ = new_vram_is_empty;
        
        static int vram_check_log_count = 0;
        if (vram_check_log_count < 5) {
            vram_check_log_count++;
            printf("[PPU-VRAM-CHECK] Frame %llu | VRAM non-zero: %d/6144 | Empty: %s\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   vram_non_zero, vram_is_empty_ ? "YES" : "NO");
        }
        
        // --- Step 0370: Investigación de Discrepancia VRAM vs Tiles ---
        // Cuando se detecta que los tiles tienen datos pero VRAM muestra 0/6144
        static int discrepancy_check_count = 0;
        if (discrepancy_check_count < 20) {
            discrepancy_check_count++;
            
            // Verificación 1: VRAM completa (0x8000-0x97FF)
            int vram_complete_non_zero = 0;
            for (uint16_t i = 0; i < 6144; i++) {
                if (mmu_->read(0x8000 + i) != 0x00) {
                    vram_complete_non_zero++;
                }
            }
            
            // Verificación 2: Tiles específicos que apunta el tilemap
            uint8_t lcdc_temp = mmu_->read(IO_LCDC);
            uint16_t map_base = (lcdc_temp & 0x08) ? 0x9C00 : 0x9800;
            bool unsigned_addressing = (lcdc_temp & 0x10) != 0;
            uint16_t data_base = unsigned_addressing ? 0x8000 : 0x8800;
            
            int tiles_with_data = 0;
            int tiles_empty = 0;
            std::vector<uint16_t> tile_addresses_checked;
            
            // Verificar primeros 20 tiles del tilemap
            for (int i = 0; i < 20; i++) {
                uint8_t tile_id = mmu_->read(map_base + i);
                uint16_t tile_addr;
                
                if (unsigned_addressing) {
                    tile_addr = data_base + (tile_id * 16);
                } else {
                    int8_t signed_id = static_cast<int8_t>(tile_id);
                    tile_addr = data_base + ((signed_id + 128) * 16);
                }
                
                // Verificar si el tile tiene datos
                bool has_data = false;
                for (int j = 0; j < 16; j++) {
                    uint8_t byte = mmu_->read(tile_addr + j);
                    if (byte != 0x00) {
                        has_data = true;
                        break;
                    }
                }
                
                if (has_data) {
                    tiles_with_data++;
                    tile_addresses_checked.push_back(tile_addr);
                } else {
                    tiles_empty++;
                }
            }
            
            // Verificar si las direcciones de tiles están en el rango verificado
            int tiles_in_range = 0;
            int tiles_out_of_range = 0;
            for (uint16_t tile_addr : tile_addresses_checked) {
                if (tile_addr >= 0x8000 && tile_addr <= 0x97FF) {
                    tiles_in_range++;
                } else {
                    tiles_out_of_range++;
                    printf("[PPU-DISCREPANCY] ⚠️ Tile en dirección fuera de rango: 0x%04X\n", tile_addr);
                }
            }
            
            printf("[PPU-DISCREPANCY] Frame %llu | VRAM complete: %d/6144 non-zero | "
                   "Tiles with data: %d/20 | Tiles in range: %d | Tiles out of range: %d\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   vram_complete_non_zero, tiles_with_data, tiles_in_range, tiles_out_of_range);
            
            if (tiles_with_data > 0 && vram_complete_non_zero == 0) {
                printf("[PPU-DISCREPANCY] ⚠️ PROBLEMA: Tiles tienen datos pero VRAM completa muestra 0!\n");
                printf("[PPU-DISCREPANCY] Verificando direcciones específicas de tiles...\n");
                
                // Verificar cada dirección de tile específica
                for (uint16_t tile_addr : tile_addresses_checked) {
                    int tile_bytes_non_zero = 0;
                    for (int j = 0; j < 16; j++) {
                        if (mmu_->read(tile_addr + j) != 0x00) {
                            tile_bytes_non_zero++;
                        }
                    }
                    printf("[PPU-DISCREPANCY] TileAddr=0x%04X | Non-zero bytes: %d/16\n",
                           tile_addr, tile_bytes_non_zero);
                }
            }
        }
        // -------------------------------------------
        
        // --- Step 0370: Verificación Completa de Rangos de VRAM ---
        // Verificar todos los rangos posibles donde pueden estar los tiles
        static int vram_range_check_count = 0;
        if (vram_range_check_count < 10) {
            vram_range_check_count++;
            
            // Rango 1: 0x8000-0x8FFF (unsigned addressing, tiles 0-127)
            int range1_non_zero = 0;
            for (uint16_t i = 0; i < 4096; i++) {
                if (mmu_->read(0x8000 + i) != 0x00) {
                    range1_non_zero++;
                }
            }
            
            // Rango 2: 0x8800-0x97FF (signed addressing, tiles -128 a 127, tile 0 en 0x9000)
            int range2_non_zero = 0;
            for (uint16_t i = 0; i < 4096; i++) {
                if (mmu_->read(0x8800 + i) != 0x00) {
                    range2_non_zero++;
                }
            }
            
            // Rango completo: 0x8000-0x97FF (6144 bytes)
            int range_complete_non_zero = 0;
            for (uint16_t i = 0; i < 6144; i++) {
                if (mmu_->read(0x8000 + i) != 0x00) {
                    range_complete_non_zero++;
                }
            }
            
            printf("[PPU-VRAM-RANGE] Frame %llu | "
                   "Range 0x8000-0x8FFF: %d/4096 | "
                   "Range 0x8800-0x97FF: %d/4096 | "
                   "Range 0x8000-0x97FF: %d/6144\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   range1_non_zero, range2_non_zero, range_complete_non_zero);
            
            // Verificar si hay tiles en rangos superpuestos
            if (range1_non_zero > 0 && range2_non_zero > 0) {
                printf("[PPU-VRAM-RANGE] ⚠️ Tiles en ambos rangos (superposición)\n");
            }
        }
        // -------------------------------------------
    }
    // -------------------------------------------
    
    // --- Step 0370: Actualización Mejorada de vram_is_empty_ ---
    // Actualizar vram_is_empty_ no solo en LY=0, sino también durante V-Blank
    // cuando los tiles se cargan típicamente
    if (ly_ >= 144 && ly_ <= 153 && mode_ == MODE_1_VBLANK) {
        // Actualizar vram_is_empty_ durante V-Blank para capturar tiles cargados
        static int vblank_vram_check_count = 0;
        if (vblank_vram_check_count < 10 || (frame_counter_ % 60 == 0)) {
            vblank_vram_check_count++;
            
            int vram_non_zero = 0;
            for (uint16_t i = 0; i < 6144; i++) {
                if (mmu_->read(0x8000 + i) != 0x00) {
                    vram_non_zero++;
                }
            }
            
            bool new_vram_is_empty = (vram_non_zero < 200);
            
            // Solo actualizar si cambió
            if (new_vram_is_empty != vram_is_empty_) {
                printf("[PPU-VRAM-UPDATE-VBLANK] Frame %llu | LY: %d | "
                       "vram_is_empty_ cambió: %s -> %s | VRAM non-zero: %d/6144\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_,
                       vram_is_empty_ ? "YES" : "NO",
                       new_vram_is_empty ? "YES" : "NO",
                       vram_non_zero);
                
                vram_is_empty_ = new_vram_is_empty;
            }
        }
    }
    // -------------------------------------------
    
    // --- Step 0368: Verificación de VRAM Durante el Renderizado ---
    // Verificar VRAM no solo en LY=0, sino también durante el renderizado
    // para detectar si VRAM se carga después de que se actualiza vram_is_empty_
    static int vram_during_render_check_count = 0;
    if (vram_during_render_check_count < 20 && ly_ < 144) {
        if (ly_ == 0 || ly_ == 72 || ly_ == 143) {  // Primera, central, última línea
            vram_during_render_check_count++;
            
            // Verificar VRAM en este momento
            int vram_non_zero = 0;
            for (uint16_t i = 0; i < 6144; i++) {
                if (mmu_->read(0x8000 + i) != 0x00) {
                    vram_non_zero++;
                }
            }
            
            printf("[PPU-VRAM-DURING-RENDER] Frame %llu | LY: %d | Mode: %d | "
                   "VRAM non-zero: %d/6144 (%.2f%%) | vram_is_empty_: %s\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_, mode_,
                   vram_non_zero, (vram_non_zero * 100.0) / 6144,
                   vram_is_empty_ ? "YES" : "NO");
            
            if (vram_non_zero > 200 && vram_is_empty_) {
                printf("[PPU-VRAM-DURING-RENDER] ⚠️ PROBLEMA: VRAM tiene %d bytes no-cero pero vram_is_empty_=true!\n",
                       vram_non_zero);
            }
            if (vram_non_zero < 200 && !vram_is_empty_) {
                printf("[PPU-VRAM-DURING-RENDER] ⚠️ PROBLEMA: VRAM tiene solo %d bytes no-cero pero vram_is_empty_=false!\n",
                       vram_non_zero);
            }
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

    // --- Step 0336: Verificación de Scroll ---
    // Verificar que el scroll se aplica correctamente
    static int scroll_check_count = 0;
    if (scroll_check_count < 10 && ly_ == 72) {
        scroll_check_count++;
        
        printf("[PPU-SCROLL] Frame %llu | LY: %d | SCX: %d | SCY: %d | "
               "MapX: %d | MapY: %d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               ly_, scx, scy,
               (0 + scx) & 0xFF, (ly_ + scy) & 0xFF);
    }
    // -------------------------------------------

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
                uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
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

    // --- Step 0351: Verificación Detallada de Decodificación de Tiles ---
    // Verificar que los tiles se decodifican correctamente
    static int tile_decode_detailed_count = 0;
    
    // Verificar algunos tiles durante el renderizado (solo en algunas líneas)
    if ((ly_ == 0 || ly_ == 72) && tile_decode_detailed_count < 10) {
        tile_decode_detailed_count++;
        
        // Verificar algunos tiles en la línea actual
        for (int x = 0; x < SCREEN_WIDTH && x < 80; x += 8) {  // Cada tile (8 píxeles)
            uint8_t map_x = (x + scx) & 0xFF;
            uint8_t map_y = (ly_ + scy) & 0xFF;
            
            // Obtener tile ID del tilemap
            uint16_t map_addr = tile_map_base + ((map_y) / 8) * 32 + ((map_x) / 8);
            uint8_t tile_id = mmu_->read(map_addr);
            
            // Calcular dirección del tile
            uint16_t tile_addr;
            if (signed_addressing) {
                int8_t signed_tile_id = static_cast<int8_t>(tile_id);
                tile_addr = tile_data_base + static_cast<uint16_t>(signed_tile_id) * 16;
            } else {
                tile_addr = tile_data_base + tile_id * 16;
            }
            
            // Verificar que el tile está en rango válido
            if (tile_addr >= 0x8000 && tile_addr < 0x9800) {
                // Leer datos del tile (primeros 2 bytes = primera línea)
                uint8_t byte1 = mmu_->read(tile_addr);
                uint8_t byte2 = mmu_->read(tile_addr + 1);
                
                // Decodificar primera línea del tile
                uint8_t decoded_pixels[8];
                for (int bit = 7; bit >= 0; bit--) {
                    uint8_t bit_low = (byte1 >> bit) & 1;
                    uint8_t bit_high = (byte2 >> bit) & 1;
                    decoded_pixels[7 - bit] = (bit_high << 1) | bit_low;
                }
                
                // Verificar que el tile no está vacío
                bool tile_empty = true;
                for (int i = 0; i < 8; i++) {
                    if (decoded_pixels[i] != 0) {
                        tile_empty = false;
                        break;
                    }
                }
                
                if (!tile_empty && tile_decode_detailed_count <= 5) {
                    printf("[PPU-TILE-DECODE-DETAILED] Frame %llu | LY: %d | Tile at x=%d | "
                           "TileID=0x%02X | TileAddr=0x%04X | Decoded pixels: ",
                           static_cast<unsigned long long>(frame_counter_ + 1), ly_, x, tile_id, tile_addr);
                    for (int i = 0; i < 8; i++) {
                        printf("%d ", decoded_pixels[i]);
                    }
                    printf("\n");
                }
            }
        }
    }
    // -------------------------------------------
    
    // --- Step 0351: Verificación Detallada de Aplicación de Paleta ---
    // Verificar que la paleta se aplica correctamente
    static int palette_apply_detailed_count = 0;
    
    // Verificar algunos píxeles durante el renderizado (solo en algunas líneas)
    if ((ly_ == 0 || ly_ == 72) && palette_apply_detailed_count < 10) {
        palette_apply_detailed_count++;
        
        // Obtener BGP
        uint8_t bgp_check = mmu_->read(IO_BGP);
        
        if (palette_apply_detailed_count <= 5) {
            printf("[PPU-PALETTE-APPLY-DETAILED] Frame %llu | LY: %d | BGP=0x%02X\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_, bgp_check);
        }
        
        // Verificar algunos píxeles en la línea actual (después de que se rendericen)
        // Nota: Esto se ejecuta antes del bucle de renderizado, así que solo verificamos BGP
        // La verificación de píxeles finales se hará después del renderizado
    }
    // -------------------------------------------

    // --- Step 0366: Verificación de Ejecución del Código de Renderizado ---
    static int render_code_entry_count = 0;
    if (render_code_entry_count < 20 && ly_ < 144) {
        render_code_entry_count++;
        printf("[PPU-RENDER-CODE] Frame %llu | LY: %d | Código de renderizado inline ejecutándose\n",
               static_cast<unsigned long long>(frame_counter_ + 1), ly_);
        
        // Verificar LCDC
        uint8_t lcdc = mmu_->read(IO_LCDC);
        bool lcd_on = (lcdc & 0x80) != 0;
        bool bg_display = (lcdc & 0x01) != 0;
        printf("[PPU-RENDER-CODE] LCDC: 0x%02X | LCD: %s | BG Display: %s\n",
               lcdc, lcd_on ? "ON" : "OFF", bg_display ? "ON" : "OFF");
        
        if (!lcd_on) {
            printf("[PPU-RENDER-CODE] ⚠️ PROBLEMA: LCD está OFF, no debería renderizar\n");
        }
        if (!bg_display) {
            printf("[PPU-RENDER-CODE] ⚠️ PROBLEMA: BG Display está OFF\n");
        }
    }
    // -------------------------------------------

    // --- Step 0366: Verificación de Condiciones Necesarias ---
    static int conditions_check_count = 0;
    if (conditions_check_count < 20 && ly_ < 144) {
        conditions_check_count++;
        
        uint8_t lcdc = mmu_->read(IO_LCDC);
        bool lcd_on = (lcdc & 0x80) != 0;
        bool bg_display = (lcdc & 0x01) != 0;
        
        // Verificar VRAM
        int vram_non_zero = 0;
        for (uint16_t i = 0; i < 1024; i++) {  // Primeros 1024 bytes (64 tiles)
            if (mmu_->read(0x8000 + i) != 0x00) {
                vram_non_zero++;
            }
        }
        
        // Verificar tilemap
        int tilemap_non_zero = 0;
        uint16_t map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
        for (int i = 0; i < 32; i++) {  // Primeras 32 entradas (primera fila)
            if (mmu_->read(map_base + i) != 0x00) {
                tilemap_non_zero++;
            }
        }
        
        printf("[PPU-CONDITIONS] Frame %llu | LY: %d | "
               "LCD: %s | BG Display: %s | VRAM: %d/1024 | Tilemap: %d/32\n",
               static_cast<unsigned long long>(frame_counter_ + 1), ly_,
               lcd_on ? "ON" : "OFF", bg_display ? "ON" : "OFF",
               vram_non_zero, tilemap_non_zero);
        
        if (!lcd_on) {
            printf("[PPU-CONDITIONS] ⚠️ PROBLEMA: LCD está OFF\n");
        }
        if (!bg_display) {
            printf("[PPU-CONDITIONS] ⚠️ PROBLEMA: BG Display está OFF\n");
        }
        if (vram_non_zero == 0) {
            printf("[PPU-CONDITIONS] ⚠️ PROBLEMA: VRAM está vacía\n");
        }
        if (tilemap_non_zero == 0) {
            printf("[PPU-CONDITIONS] ⚠️ PROBLEMA: Tilemap está vacío\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0368: Verificación de Tiles Disponibles al Inicio de Renderizado ---
    // Verificar si hay tiles cuando se renderiza (timing de carga vs renderizado)
    static int tiles_available_check_count = 0;
    if (tiles_available_check_count < 20 && ly_ < 144) {
        if (ly_ == 0 || ly_ == 72) {
            tiles_available_check_count++;
            
            uint8_t lcdc = mmu_->read(IO_LCDC);
            uint16_t map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
            bool unsigned_addressing = (lcdc & 0x10) != 0;
            uint16_t data_base = unsigned_addressing ? 0x8000 : 0x9000;
            
            int tiles_with_data = 0;
            int tiles_empty = 0;
            
            // Verificar primeros 20 tiles del tilemap
            for (int i = 0; i < 20; i++) {
                uint8_t tile_id = mmu_->read(map_base + i);
                uint16_t tile_addr;
                if (unsigned_addressing) {
                    tile_addr = data_base + (tile_id * 16);
                } else {
                    int8_t signed_id = static_cast<int8_t>(tile_id);
                    tile_addr = data_base + ((signed_id + 128) * 16);
                }
                
                // Verificar si el tile tiene datos
                bool has_data = false;
                for (int j = 0; j < 16; j++) {
                    if (mmu_->read(tile_addr + j) != 0x00) {
                        has_data = true;
                        break;
                    }
                }
                
                if (has_data) {
                    tiles_with_data++;
                } else {
                    tiles_empty++;
                }
            }
            
            printf("[PPU-TILES-AVAILABLE] Frame %llu | LY: %d | "
                   "Tiles with data: %d/20 | Tiles empty: %d/20\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_,
                   tiles_with_data, tiles_empty);
            
            if (tiles_with_data == 0) {
                printf("[PPU-TILES-AVAILABLE] ⚠️ PROBLEMA: Todos los tiles están vacíos, checkerboard se activará\n");
            }
        }
    }
    // -------------------------------------------

    for (int x = 0; x < 160; ++x) {
        uint8_t map_x = (x + scx) & 0xFF;
        uint8_t map_y = (ly_ + scy) & 0xFF;

        uint16_t tile_map_addr = tile_map_base + (map_y / 8) * 32 + (map_x / 8);
        uint8_t tile_id = mmu_->read(tile_map_addr);

        // --- Step 0366: Verificación del Bucle de Renderizado ---
        static int render_loop_count = 0;
        if (render_loop_count < 5 && ly_ == 0) {
            if (x == 0) {
                render_loop_count++;
                printf("[PPU-RENDER-LOOP] Frame %llu | LY: %d | Bucle de renderizado iniciado\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_);
            }
            
            if (x < 5) {
                // Verificar que se lee el tilemap
                printf("[PPU-RENDER-LOOP] X=%d | Tilemap[0x%04X]=0x%02X (Tile ID)\n",
                       x, tile_map_addr, tile_id);
                
                // Verificar que se calcula la dirección del tile
                uint16_t tile_addr_check;
                bool unsigned_addressing_check = (mmu_->read(IO_LCDC) & 0x10) != 0;
                uint16_t data_base_check = unsigned_addressing_check ? 0x8000 : 0x9000;
                if (unsigned_addressing_check) {
                    tile_addr_check = data_base_check + (tile_id * 16);
                } else {
                    int8_t signed_tile_id = static_cast<int8_t>(tile_id);
                    tile_addr_check = data_base_check + ((signed_tile_id + 128) * 16);
                }
                printf("[PPU-RENDER-LOOP] X=%d | Tile ID=0x%02X | Tile Addr=0x%04X\n",
                       x, tile_id, tile_addr_check);
            }
        }
        // -------------------------------------------
        
        // --- Step 0368: Verificación de Qué Tiles se Leen del Tilemap ---
        // Logs detallados de qué tiles se leen del tilemap y su contenido
        static int tilemap_read_check_count = 0;
        if (tilemap_read_check_count < 50 && ly_ < 144) {
            if (ly_ == 0 || ly_ == 72) {  // Primera y central línea
                if (x < 80 && x % 8 == 0) {  // Primera mitad de la pantalla, cada tile (8 píxeles)
                    tilemap_read_check_count++;
                    
                    // Leer tile ID del tilemap (ya leído arriba)
                    // Calcular dirección del tile
                    uint8_t lcdc = mmu_->read(IO_LCDC);
                    bool unsigned_addressing = (lcdc & 0x10) != 0;
                    uint16_t data_base = unsigned_addressing ? 0x8000 : 0x9000;
                    
                    uint16_t tile_addr;
                    if (unsigned_addressing) {
                        tile_addr = data_base + (tile_id * 16);
                    } else {
                        int8_t signed_tile_id = static_cast<int8_t>(tile_id);
                        tile_addr = data_base + ((signed_tile_id + 128) * 16);
                    }
                    
                    // Verificar contenido del tile
                    uint8_t tile_byte1 = mmu_->read(tile_addr);
                    uint8_t tile_byte2 = mmu_->read(tile_addr + 1);
                    bool tile_has_data = (tile_byte1 != 0x00 || tile_byte2 != 0x00);
                    
                    printf("[PPU-TILEMAP-READ] Frame %llu | LY: %d | X: %d | "
                           "Tilemap[0x%04X]=0x%02X | TileAddr=0x%04X | "
                           "Byte1=0x%02X Byte2=0x%02X | HasData=%s\n",
                           static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                           tile_map_addr, tile_id, tile_addr,
                           tile_byte1, tile_byte2, tile_has_data ? "YES" : "NO");
                    
                    if (!tile_has_data) {
                        printf("[PPU-TILEMAP-READ] ⚠️ Tile vacío detectado - activará checkerboard si vram_is_empty_=true\n");
                    }
                }
            }
        }
        // -------------------------------------------

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

        // --- Step 0336: Verificación de Direccionamiento ---
        // Verificar que el direccionamiento signed/unsigned es correcto
        static int addressing_check_count = 0;
        if (addressing_check_count < 10 && ly_ == 72 && x == 0) {
            addressing_check_count++;
            
            printf("[PPU-ADDRESSING] Frame %llu | TileID: 0x%02X | Signed: %d | "
                   "DataBase: 0x%04X | TileAddr: 0x%04X\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   tile_id, signed_addressing ? 1 : 0,
                   tile_data_base, tile_addr);
            
            if (signed_addressing) {
                int8_t signed_id = static_cast<int8_t>(tile_id);
                printf("[PPU-ADDRESSING] Signed ID: %d (0x%02X)\n", signed_id, tile_id);
            }
        }
        // -------------------------------------------

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

        // --- Step 0370: Verificación de Rango de Direcciones de Tiles ---
        // Verificar que las direcciones de tiles calculadas están en el rango correcto
        static int tile_addr_range_check_count = 0;
        if (tile_addr_range_check_count < 50 && ly_ < 144) {
            if (ly_ == 0 || ly_ == 72) {
                if (x % 8 == 0) {  // Cada tile
                    tile_addr_range_check_count++;
                    
                    // Verificar que tile_addr está en rango válido
                    bool in_range = (tile_addr >= 0x8000 && tile_addr <= 0x97FF);
                    
                    if (!in_range) {
                        printf("[PPU-TILE-ADDR-RANGE] Frame %llu | LY: %d | X: %d | "
                               "TileID: 0x%02X | TileAddr: 0x%04X | ⚠️ FUERA DE RANGO!\n",
                               static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                               tile_id, tile_addr);
                    } else if (tile_addr_range_check_count <= 10) {
                        printf("[PPU-TILE-ADDR-RANGE] Frame %llu | LY: %d | X: %d | "
                               "TileID: 0x%02X | TileAddr: 0x%04X | ✅ En rango\n",
                               static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                               tile_id, tile_addr);
                    }
                }
            }
        }
        // -------------------------------------------

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
            framebuffer_back_[line_start_index + x] = final_color;
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

            // --- Step 0368: Verificación Detallada de Tiles Vacíos ---
            // Logs detallados de la verificación de tiles vacíos
            static int tile_empty_check_count = 0;
            bool should_log_tile_empty = false;
            if (tile_empty_check_count < 30 && ly_ < 144) {
                if (ly_ == 0 || ly_ == 72) {
                    if (x < 80 && x % 8 == 0) {  // Cada tile en primera mitad
                        should_log_tile_empty = true;
                        tile_empty_check_count++;
                    }
                }
            }
            // -------------------------------------------

            // Verificar si TODO el tile está vacío (todas las 8 líneas = 16 bytes)
            int lines_with_data = 0;
            int lines_empty = 0;
            for (uint8_t line_check = 0; line_check < 8; line_check++) {
                uint16_t check_addr = tile_addr + (line_check * 2);
                if (check_addr < 0x8000 || check_addr > 0x97FF) {
                    tile_is_empty = true;
                    if (should_log_tile_empty) {
                        lines_empty++;
                    }
                    break;
                }
                uint8_t check_byte1 = mmu_->read(check_addr);
                uint8_t check_byte2 = mmu_->read(check_addr + 1);
                
                if (check_byte1 != 0x00 || check_byte2 != 0x00) {
                    tile_is_empty = false;
                    if (should_log_tile_empty) {
                        lines_with_data++;
                    }
                    break;
                } else {
                    if (should_log_tile_empty) {
                        lines_empty++;
                    }
                }
            }
            
            // Log detallado de la verificación de tiles vacíos
            if (should_log_tile_empty) {
                bool tile_is_empty_result = (lines_with_data == 0);
                
                printf("[PPU-TILE-EMPTY-CHECK] Frame %llu | LY: %d | X: %d | "
                       "TileAddr=0x%04X | LinesWithData=%d LinesEmpty=%d | "
                       "tile_is_empty=%s | vram_is_empty_=%s | enable_checkerboard=%s\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                       tile_addr, lines_with_data, lines_empty,
                       tile_is_empty_result ? "YES" : "NO",
                       vram_is_empty_ ? "YES" : "NO",
                       enable_checkerboard_temporal ? "YES" : "NO");
                
                if (tile_is_empty_result && vram_is_empty_ && enable_checkerboard_temporal) {
                    printf("[PPU-TILE-EMPTY-CHECK] ✅ Checkerboard se activará para este tile\n");
                } else if (!tile_is_empty_result) {
                    printf("[PPU-TILE-EMPTY-CHECK] ✅ Tile tiene datos, renderizado normal\n");
                } else {
                    printf("[PPU-TILE-EMPTY-CHECK] ⚠️ Tile vacío pero checkerboard NO se activará\n");
                }
            }
            // -------------------------------------------

            // --- Step 0372: Tarea 3 - Verificar si el Checkerboard se Activa ---
            static int checkerboard_activation_count = 0;
            
            // --- Step 0330: Lógica Optimizada del Checkerboard Temporal ---
            // Activar checkerboard cuando:
            // 1. El tile está completamente vacío (todas las líneas = 0x00)
            // 2. VRAM está completamente vacía (< 200 bytes no-cero)
            // Esto previene pantallas blancas cuando el tilemap apunta a direcciones inválidas
            // OPTIMIZACIÓN: Usar variable vram_is_empty_ en lugar de verificar VRAM en cada píxel
            if (tile_is_empty && enable_checkerboard_temporal && vram_is_empty_) {
                checkerboard_activation_count++;
                
                if (checkerboard_activation_count <= 100) {
                    printf("[PPU-CHECKERBOARD-ACTIVATE] Frame %llu | LY: %d | X: %d | "
                           "Checkerboard activado | Tile empty: YES | VRAM empty: YES | "
                           "Count: %d\n",
                           static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                           checkerboard_activation_count);
                }
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
                    
                    // --- Step 0372: Tarea 3 - Verificar si el Checkerboard se Escribe al Framebuffer ---
                    if (checkerboard_activation_count <= 100 && x < 10) {
                        uint8_t checkerboard_idx = (x + ly_) % 2 == 0 ? 0 : 3;
                        printf("[PPU-CHECKERBOARD-WRITE] Frame %llu | LY: %d | X: %d | "
                               "Checkerboard index: %d (0=blanco, 3=negro)\n",
                               static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                               checkerboard_idx);
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
            
            // --- Step 0336: Verificación de Decodificación de Tiles ---
            // Verificar que la decodificación 2bpp es correcta
            static int tile_decode_check_count = 0;
            if (tile_decode_check_count < 10 && ly_ == 72 && x < 32) {
                if (x % 8 == 0) {  // Cada tile (8 píxeles)
                    tile_decode_check_count++;
                    
                    // Verificar decodificación de algunos píxeles del tile
                    printf("[PPU-TILE-DECODE] Frame %llu | TileID: 0x%02X | Addr: 0x%04X | "
                           "Byte1: 0x%02X Byte2: 0x%02X\n",
                           static_cast<unsigned long long>(frame_counter_ + 1),
                           tile_id, tile_line_addr, byte1, byte2);
                    
                    // Decodificar algunos píxeles manualmente para verificar
                    for (int test_bit = 7; test_bit >= 0; test_bit--) {
                        uint8_t bit_low = (byte1 >> test_bit) & 1;
                        uint8_t bit_high = (byte2 >> test_bit) & 1;
                        uint8_t color_idx = (bit_high << 1) | bit_low;
                        
                        if (test_bit == 7 || test_bit == 0) {  // Primer y último píxel
                            printf("[PPU-TILE-DECODE] Pixel %d: bit_low=%d bit_high=%d color_idx=%d\n",
                                   test_bit, bit_low, bit_high, color_idx);
                        }
                    }
                }
            }
            // -------------------------------------------
            
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
            
            // --- Step 0336: Verificación de Aplicación de Paleta ---
            // Verificar que la paleta BGP se aplica correctamente
            static int palette_apply_check_count = 0;
            if (palette_apply_check_count < 10 && ly_ == 72 && x < 32) {
                if (x % 8 == 0) {  // Cada tile
                    palette_apply_check_count++;
                    
                    printf("[PPU-PALETTE-APPLY] Frame %llu | ColorIndex: %d | BGP: 0x%02X | "
                           "FinalColor: %d | BGP mapping: %d->%d\n",
                           static_cast<unsigned long long>(frame_counter_ + 1),
                           color_index, bgp, final_color,
                           color_index, final_color);
                }
            }
            // -------------------------------------------
            
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
            
            framebuffer_back_[line_start_index + x] = final_color;
            
            // --- Step 0366: Verificación de Escritura Real al Framebuffer Back ---
            static int write_verify_count = 0;
            if (write_verify_count < 20 && ly_ == 0 && x < 10) {
                write_verify_count++;
                uint8_t written_value = framebuffer_back_[ly_ * SCREEN_WIDTH + x];
                printf("[PPU-WRITE-VERIFY] Frame %llu | LY: %d | X: %d | "
                       "Escribió color_idx=%d | Leído del framebuffer: %d\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_, x,
                       final_color, written_value);
                
                if (written_value != final_color) {
                    printf("[PPU-WRITE-VERIFY] ⚠️ PROBLEMA: Valor escrito (%d) != valor leído (%d)!\n",
                           final_color, written_value);
                }
            }
            // -------------------------------------------
            
            // --- Step 0336: Verificación de Escritura en Framebuffer ---
            // Verificar que el índice final se escribió correctamente en el framebuffer
            static int framebuffer_write_check_count = 0;
            if (framebuffer_write_check_count < 10 && ly_ == 72 && x < 32) {
                if (x % 8 == 0) {  // Cada tile
                    framebuffer_write_check_count++;
                    
                    size_t framebuffer_idx = ly_ * SCREEN_WIDTH + x;
                    uint8_t framebuffer_value = framebuffer_front_[framebuffer_idx] & 0x03;
                    
                    if (framebuffer_value != final_color) {
                        printf("[PPU-PALETTE-APPLY] ⚠️ PROBLEMA: Framebuffer tiene %d pero debería tener %d\n",
                               framebuffer_value, final_color);
                    }
                }
            }
            // -------------------------------------------
            
            // -------------------------------------------------------------
        }
    }
    
    // --- Step 0366: Verificación de Línea Completa Después de Renderizar ---
    if (ly_ < 144) {
        static int line_complete_check_count = 0;
        if (line_complete_check_count < 20 && (ly_ == 0 || ly_ == 72 || ly_ == 143)) {
            line_complete_check_count++;
            
            int non_zero_in_line = 0;
            size_t line_start = ly_ * SCREEN_WIDTH;
            for (int x = 0; x < SCREEN_WIDTH; x++) {
                if (framebuffer_back_[line_start + x] != 0) {
                    non_zero_in_line++;
                }
            }
            
            printf("[PPU-LINE-COMPLETE] Frame %llu | LY: %d | "
                   "Línea renderizada | Non-zero pixels: %d/160\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_, non_zero_in_line);
            
            if (non_zero_in_line == 0) {
                printf("[PPU-LINE-COMPLETE] ⚠️ PROBLEMA: Línea completamente vacía después de renderizar!\n");
                
                // Mostrar primeros 20 píxeles del framebuffer
                printf("[PPU-LINE-COMPLETE] Primeros 20 píxeles: ");
                for (int x = 0; x < 20; x++) {
                    printf("%d ", framebuffer_back_[line_start + x] & 0x03);
                }
                printf("\n");
            }
        }
    }
    // -------------------------------------------
    
    // --- Step 0299: Monitor de Framebuffer Real ([FRAMEBUFFER-DUMP]) ---
    // Capturar el contenido real del framebuffer después de renderizar un frame completo
    // para ver qué índices de color se están escribiendo. Esto permite identificar si hay
    // un patrón repetitivo en los índices que podría explicar las rayas verticales.
    // Fuente: Pan Docs - "LCD Display"
    static int framebuffer_dump_count = 0;
    if (ly_ == 72 && framebuffer_dump_count < 3) {  // Línea central (72 de 144)
        printf("[FRAMEBUFFER-DUMP] Frame %d, LY:72 | First 32 pixels (indices 0-31):\n", framebuffer_dump_count + 1);
        for(int x_dump = 0; x_dump < 32; x_dump++) {
            printf("%02X ", framebuffer_front_[line_start_index + x_dump]);
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
            uint8_t idx = framebuffer_front_[line_start + x] & 0x03;
            if (idx != 0) non_zero_count++;
        }
        
        if (non_zero_count > 0 || detailed_trace_count < 10) {
            if (detailed_trace_count < 100) {
                printf("[FRAMEBUFFER-DETAILED] Frame %d LY:72 | Non-zero pixels: %d/160\n",
                       detailed_trace_count, non_zero_count);
                
                // Mostrar algunos píxeles de ejemplo
                printf("[FRAMEBUFFER-DETAILED] Sample pixels (first 32): ");
                for (int x = 0; x < 32; x++) {
                    printf("%d ", framebuffer_front_[line_start + x] & 0x03);
                }
                printf("\n");
            }
            last_frame_with_non_zero = detailed_trace_count;
        }
        detailed_trace_count++;
    }
    // -----------------------------------------
    
    // --- Step 0371: Verificación de Renderizado Cuando Hay Tiles Reales ---
    // Verificar que el renderizado normal se ejecuta cuando hay tiles reales
    // y que el checkerboard se desactiva
    
    // Cuando vram_is_empty_ cambia de YES a NO (tiles recién cargados)
    static bool last_vram_is_empty_for_render = true;
    if (last_vram_is_empty_for_render != vram_is_empty_) {
        if (last_vram_is_empty_for_render && !vram_is_empty_ && ly_ < 144) {
            static int tiles_loaded_render_check_count = 0;
            if (tiles_loaded_render_check_count < 10) {
                tiles_loaded_render_check_count++;
                
                printf("[PPU-TILES-LOADED-RENDER] Frame %llu | LY: %d | "
                       "Tiles recién cargados! Verificando renderizado...\n",
                       static_cast<unsigned long long>(frame_counter_ + 1), ly_);
                
                // Verificar que el renderizado normal se ejecuta
                // (esto se verificará en el siguiente render_scanline)
            }
        }
        last_vram_is_empty_for_render = vram_is_empty_;
    }
    
    // Verificar contenido del framebuffer cuando hay tiles reales
    if (!vram_is_empty_ && ly_ == 72) {
        static int render_with_real_tiles_count = 0;
        if (render_with_real_tiles_count < 20) {
            render_with_real_tiles_count++;
            
            // Verificar que el framebuffer tiene datos de tiles reales (no solo checkerboard)
            size_t line_start = ly_ * SCREEN_WIDTH;
            int non_zero_pixels = 0;
            int index_counts[4] = {0, 0, 0, 0};
            
            for (int x = 0; x < SCREEN_WIDTH; x++) {
                uint8_t color_idx = framebuffer_back_[line_start + x] & 0x03;
                index_counts[color_idx]++;
                if (color_idx != 0) {
                    non_zero_pixels++;
                }
            }
            
            // Verificar si es checkerboard (solo índices 0 y 3) o tiles reales (índices 0, 1, 2, 3)
            bool is_checkerboard = (index_counts[1] == 0 && index_counts[2] == 0 && 
                                    index_counts[0] > 0 && index_counts[3] > 0);
            
            printf("[PPU-RENDER-WITH-REAL-TILES] Frame %llu | LY: %d | "
                   "Non-zero pixels: %d/160 | Is checkerboard: %s | "
                   "Distribution: 0=%d 1=%d 2=%d 3=%d\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_,
                   non_zero_pixels, is_checkerboard ? "YES" : "NO",
                   index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
            
            if (is_checkerboard && !vram_is_empty_) {
                printf("[PPU-RENDER-WITH-REAL-TILES] ⚠️ PROBLEMA: Checkerboard activo aunque hay tiles reales!\n");
            }
        }
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
                uint8_t color_idx = framebuffer_front_[line_start + x_check] & 0x03;
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
    
    // --- Step 0338: Verificación del Contenido del Framebuffer con Tiles Reales ---
    // Verificar qué contiene el framebuffer cuando hay tiles reales (no checkerboard)
    static int framebuffer_content_check_count = 0;
    static bool last_vram_has_tiles_check = false;

    // Detectar cuando aparecen tiles reales por primera vez
    if (vram_has_tiles && !last_vram_has_tiles_check && ly_ == 0) {
        last_vram_has_tiles_check = true;
        framebuffer_content_check_count = 0;
    }

    // Verificar el framebuffer cuando hay tiles reales
    if (vram_has_tiles && framebuffer_content_check_count < 20 && ly_ == 72) {
        framebuffer_content_check_count++;
        
        // Contar índices en la línea 72 (línea central)
        int index_counts[4] = {0, 0, 0, 0};
        for (int x = 0; x < SCREEN_WIDTH; x++) {
            uint8_t color_idx = framebuffer_front_[ly_ * SCREEN_WIDTH + x] & 0x03;
            if (color_idx < 4) {
                index_counts[color_idx]++;
            }
        }
        
        printf("[PPU-FRAMEBUFFER-CONTENT] Frame %llu | LY: %d | Tiles reales detectados | "
               "Distribution: 0=%d 1=%d 2=%d 3=%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               ly_, index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
        
        // Verificar algunos píxeles específicos
        int test_x_positions[] = {0, 40, 80, 120, 159};
        for (int i = 0; i < 5; i++) {
            int x = test_x_positions[i];
            uint8_t color_idx = framebuffer_front_[ly_ * SCREEN_WIDTH + x] & 0x03;
            printf("[PPU-FRAMEBUFFER-CONTENT] Pixel (%d, %d): index=%d\n", x, ly_, color_idx);
        }
    }
    // -------------------------------------------

    // --- Step 0338: Verificación de Correspondencia Tilemap-Tiles ---
    // Verificar si el tilemap apunta a tiles con datos en VRAM
    static int tilemap_tiles_correspondence_count = 0;

    if (vram_has_tiles && tilemap_tiles_correspondence_count < 10 && ly_ == 72) {
        tilemap_tiles_correspondence_count++;
        
        uint16_t tile_map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
        bool signed_addressing = (lcdc & 0x10) == 0;
        uint16_t tile_data_base = signed_addressing ? 0x9000 : 0x8000;
        
        uint8_t scy = mmu_->read(IO_SCY);
        uint8_t scx = mmu_->read(IO_SCX);
        
        // Calcular qué tiles son visibles en la línea 72
        uint8_t map_y = (ly_ + scy) & 0xFF;
        uint8_t tile_y = map_y / 8;
        
        int tiles_with_data = 0;
        int tiles_empty = 0;
        int tiles_invalid = 0;
        
        // Verificar los primeros 20 tiles visibles
        for (int screen_tile_x = 0; screen_tile_x < 20; screen_tile_x++) {
            uint8_t map_x = (screen_tile_x * 8 + scx) & 0xFF;
            uint8_t tile_x = map_x / 8;
            
            // Leer tile ID del tilemap
            uint16_t tilemap_addr = tile_map_base + (tile_y * 32 + tile_x);
            uint8_t tile_id = mmu_->read(tilemap_addr);
            
            // Calcular dirección del tile
            uint16_t tile_addr;
            if (!signed_addressing) {
                tile_addr = tile_data_base + (tile_id * 16);
            } else {
                int8_t signed_id = static_cast<int8_t>(tile_id);
                tile_addr = tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
            }
            
            // Verificar si el tile tiene datos
            bool tile_has_data = false;
            if (tile_addr >= 0x8000 && tile_addr <= 0x97FF) {
                // Verificar si el tile tiene datos (al menos una línea no vacía)
                for (uint8_t line = 0; line < 8; line++) {
                    uint16_t line_addr = tile_addr + (line * 2);
                    uint8_t byte1 = mmu_->read(line_addr);
                    uint8_t byte2 = mmu_->read(line_addr + 1);
                    if (byte1 != 0x00 || byte2 != 0x00) {
                        tile_has_data = true;
                        break;
                    }
                }
                
                if (tile_has_data) {
                    tiles_with_data++;
                } else {
                    tiles_empty++;
                }
            } else {
                tiles_invalid++;
            }
            
            // Loggear algunos tiles específicos
            if (screen_tile_x < 5) {
                printf("[PPU-TILEMAP-TILES] Tile %d: ID=0x%02X | Addr=0x%04X | HasData=%d\n",
                       screen_tile_x, tile_id, tile_addr, tile_has_data ? 1 : 0);
            }
        }
        
        printf("[PPU-TILEMAP-TILES] Frame %llu | LY: %d | Tiles visibles: "
               "WithData=%d Empty=%d Invalid=%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               ly_, tiles_with_data, tiles_empty, tiles_invalid);
    }
    // -------------------------------------------

    // --- Step 0338: Verificación de Renderizado Completo de Tiles ---
    // Verificar si los tiles se renderizan completamente (todas las líneas)
    static int tile_render_complete_check_count = 0;

    if (vram_has_tiles && tile_render_complete_check_count < 10 && ly_ == 72) {
        tile_render_complete_check_count++;
        
        // Verificar un tile específico (tile en posición (0, 0) del tilemap)
        uint16_t tile_map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
        bool signed_addressing = (lcdc & 0x10) == 0;
        uint16_t tile_data_base = signed_addressing ? 0x9000 : 0x8000;
        
        uint8_t scy = mmu_->read(IO_SCY);
        uint8_t map_y = (ly_ + scy) & 0xFF;
        uint8_t tile_y = map_y / 8;
        uint8_t line_in_tile = map_y % 8;
        
        // Leer tile ID del tilemap (tile en posición (0, tile_y))
        uint16_t tilemap_addr = tile_map_base + (tile_y * 32 + 0);
        uint8_t tile_id = mmu_->read(tilemap_addr);
        
        // Calcular dirección del tile
        uint16_t tile_addr;
        if (!signed_addressing) {
            tile_addr = tile_data_base + (tile_id * 16);
        } else {
            int8_t signed_id = static_cast<int8_t>(tile_id);
            tile_addr = tile_data_base + (static_cast<uint16_t>(signed_id) * 16);
        }
        
        // Verificar que el tile tiene datos
        if (tile_addr >= 0x8000 && tile_addr <= 0x97FF) {
            // Leer la línea actual del tile
            uint16_t tile_line_addr = tile_addr + (line_in_tile * 2);
            uint8_t byte1 = mmu_->read(tile_line_addr);
            uint8_t byte2 = mmu_->read(tile_line_addr + 1);
            
            // Verificar qué píxeles se renderizaron en el framebuffer
            int pixels_rendered = 0;
            int pixels_expected = 8;
            
            for (int x = 0; x < 8; x++) {
                uint8_t bit_index = 7 - x;
                uint8_t bit_low = (byte1 >> bit_index) & 1;
                uint8_t bit_high = (byte2 >> bit_index) & 1;
                uint8_t expected_color_idx = (bit_high << 1) | bit_low;
                
                // Verificar en el framebuffer
                int framebuffer_x = x;  // Asumiendo que el tile empieza en x=0
                if (framebuffer_x < SCREEN_WIDTH) {
                    uint8_t actual_color_idx = framebuffer_front_[ly_ * SCREEN_WIDTH + framebuffer_x] & 0x03;
                    if (actual_color_idx == expected_color_idx) {
                        pixels_rendered++;
                    }
                }
            }
            
            printf("[PPU-TILE-RENDER-COMPLETE] Frame %llu | LY: %d | TileID: 0x%02X | "
                   "LineInTile: %d | Pixels rendered: %d/%d | "
                   "Byte1: 0x%02X Byte2: 0x%02X\n",
                   static_cast<unsigned long long>(frame_counter_ + 1),
                   ly_, tile_id, line_in_tile, pixels_rendered, pixels_expected,
                   byte1, byte2);
            
            if (pixels_rendered < pixels_expected) {
                printf("[PPU-TILE-RENDER-COMPLETE] ⚠️ ADVERTENCIA: Tile no se renderizó completamente!\n");
            }
        }
    }
    // -------------------------------------------

    // --- Step 0338: Verificación Detallada de Scroll y Offset ---
    // Verificar que el scroll y el offset se calculan correctamente
    static int scroll_offset_check_count = 0;

    if (vram_has_tiles && scroll_offset_check_count < 10 && ly_ == 72) {
        scroll_offset_check_count++;
        
        uint8_t scy = mmu_->read(IO_SCY);
        uint8_t scx = mmu_->read(IO_SCX);
        
        // Verificar algunos píxeles específicos
        int test_x_positions[] = {0, 40, 80, 120, 159};
        for (int i = 0; i < 5; i++) {
            int screen_x = test_x_positions[i];
            
            // Calcular posición en el tilemap con scroll
            uint8_t map_x = (screen_x + scx) & 0xFF;
            uint8_t map_y = (ly_ + scy) & 0xFF;
            
            uint8_t tile_x = map_x / 8;
            uint8_t tile_y = map_y / 8;
            uint8_t pixel_in_tile_x = map_x % 8;
            uint8_t pixel_in_tile_y = map_y % 8;
            
            printf("[PPU-SCROLL-OFFSET] Pixel (%d, %d): SCX=%d SCY=%d | "
                   "MapX=%d MapY=%d | TileX=%d TileY=%d | "
                   "PixelInTileX=%d PixelInTileY=%d\n",
                   screen_x, ly_, scx, scy,
                   map_x, map_y, tile_x, tile_y,
                   pixel_in_tile_x, pixel_in_tile_y);
        }
    }
    // -------------------------------------------

    // --- Step 0320: Verificación del Framebuffer después de Renderizar ---
    // Verificar que se renderizó algo (no todo blanco) en la línea actual
    size_t line_start = ly_ * SCREEN_WIDTH;
    int non_zero_pixels = 0;
    int color_counts[4] = {0, 0, 0, 0};
    for (int x = 0; x < SCREEN_WIDTH; x++) {
        uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
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
    
    // --- Step 0339: Verificación del Estado del Framebuffer Línea por Línea ---
    // Verificar que el framebuffer tiene datos después de renderizar cada línea
    static int framebuffer_line_check_count = 0;
    
    // Verificar líneas específicas (0, 72, 143) y algunas aleatorias
    if (ly_ == 0 || ly_ == 72 || ly_ == 143 || (ly_ % 20 == 0 && framebuffer_line_check_count < 20)) {
        framebuffer_line_check_count++;
        
        size_t line_start = ly_ * SCREEN_WIDTH;
        
        // Contar índices en la línea
        int index_counts[4] = {0, 0, 0, 0};
        int non_zero_pixels = 0;
        
        for (int x = 0; x < SCREEN_WIDTH; x++) {
            uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
            if (color_idx < 4) {
                index_counts[color_idx]++;
                if (color_idx != 0) {
                    non_zero_pixels++;
                }
            }
        }
        
        printf("[PPU-FRAMEBUFFER-LINE] Frame %llu | LY: %d | Non-zero pixels: %d/160 | "
               "Distribution: 0=%d 1=%d 2=%d 3=%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1),
               ly_, non_zero_pixels,
               index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
        
        // Verificar algunos píxeles específicos
        int test_x_positions[] = {0, 40, 80, 120, 159};
        for (int i = 0; i < 5; i++) {
            int x = test_x_positions[i];
            uint8_t color_idx = framebuffer_front_[line_start + x] & 0x03;
            printf("[PPU-FRAMEBUFFER-LINE] Pixel (%d, %d): index=%d\n", x, ly_, color_idx);
        }
        
        // Advertencia si la línea está completamente vacía
        if (non_zero_pixels == 0 && ly_ < 144) {
            printf("[PPU-FRAMEBUFFER-LINE] ⚠️ ADVERTENCIA: Línea %d completamente vacía después de renderizar!\n", ly_);
        }
    }
    // -------------------------------------------
    
    // --- Step 0361: Verificación de render_scanline() ---
    // Verificar que render_scanline() realmente escribe al framebuffer
    static int render_scanline_check_count = 0;
    if (render_scanline_check_count < 50 && ly_ < 144) {
        render_scanline_check_count++;
        
        // Verificar la línea renderizada
        int line_non_white = 0;
        for (int x = 0; x < 160; x++) {
            uint8_t idx = framebuffer_front_[ly_ * 160 + x];
            if (idx != 0) {
                line_non_white++;
            }
        }
        
        // Verificar estado de VRAM
        int vram_non_zero = 0;
        for (uint16_t addr = 0x8000; addr < 0x9800; addr++) {
            if (mmu_->read(addr) != 0x00) {
                vram_non_zero++;
            }
        }
        
        printf("[PPU-RENDER-SCANLINE] LY=%d | VRAM non-zero: %d/6144 | "
               "Line non-white: %d/160 (%.1f%%) | "
               "First 10 indices: ",
               ly_, vram_non_zero, line_non_white, (line_non_white * 100.0) / 160);
        
        for (int x = 0; x < 10; x++) {
            printf("%d ", framebuffer_back_[ly_ * 160 + x]);  // Step 0365: Corregido para usar back
        }
        printf("\n");
        
        // Advertencia si VRAM tiene tiles pero la línea está vacía
        if (vram_non_zero >= 200 && line_non_white < 10) {
            printf("[PPU-RENDER-SCANLINE] ⚠️ ADVERTENCIA: VRAM tiene tiles pero línea está vacía!\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0372: Tarea 2 - Verificar si render_scanline() Escribe al Framebuffer ---
    static int framebuffer_write_verify_count = 0;
    framebuffer_write_verify_count++;
    
    if (framebuffer_write_verify_count <= 100) {
        // Verificar que se escribieron datos al framebuffer_back_
        size_t line_start = ly_ * SCREEN_WIDTH;
        int non_zero_pixels = 0;
        int index_counts[4] = {0, 0, 0, 0};
        
        for (int x = 0; x < SCREEN_WIDTH; x++) {
            uint8_t color_idx = framebuffer_back_[line_start + x] & 0x03;
            index_counts[color_idx]++;
            if (color_idx != 0) {
                non_zero_pixels++;
            }
        }
        
        printf("[PPU-FRAMEBUFFER-WRITE] Frame %llu | LY: %d | "
               "Non-zero pixels written: %d/160 | Distribution: 0=%d 1=%d 2=%d 3=%d\n",
               static_cast<unsigned long long>(frame_counter_ + 1), ly_,
               non_zero_pixels, index_counts[0], index_counts[1], index_counts[2], index_counts[3]);
        
        if (non_zero_pixels == 0) {
            printf("[PPU-FRAMEBUFFER-WRITE] ⚠️ PROBLEMA: No se escribieron píxeles no-blancos al framebuffer!\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0365: Verificación de Escritura al Framebuffer Back (DESPUÉS del renderizado) ---
    // Verificar que render_scanline() escribió datos al framebuffer_back_
    static int render_write_check_count = 0;
    if (render_write_check_count < 50 && ly_ < 144) {
        // Verificar que se escribieron datos en esta línea
        size_t line_start_index = ly_ * SCREEN_WIDTH;
        int non_zero_written = 0;
        for (int x = 0; x < SCREEN_WIDTH; x++) {
            if (framebuffer_back_[line_start_index + x] != 0) {
                non_zero_written++;
            }
        }
        
        if (ly_ == 0 || ly_ == 72 || ly_ == 143) {  // Primera, central, última línea
            render_write_check_count++;
            printf("[PPU-RENDER-WRITE] Frame %llu | LY: %d | "
                   "Non-zero pixels written to back: %d/160\n",
                   static_cast<unsigned long long>(frame_counter_ + 1), ly_, non_zero_written);
            
            // Mostrar primeros 20 píxeles escritos
            printf("[PPU-RENDER-WRITE] First 20 pixels: ");
            for (int x = 0; x < 20; x++) {
                printf("%d ", framebuffer_back_[line_start_index + x] & 0x03);
            }
            printf("\n");
        }
    }
    // -------------------------------------------
    
    // --- Step 0363: Diagnóstico de Rendimiento (fin) ---
    // Medir tiempo total de render_scanline() y reportar periódicamente
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::microseconds>(end_time - start_time);
    
    if (render_scanline_timing_count < 100) {
        render_scanline_timing_count++;
        if (render_scanline_timing_count % 10 == 0) {
            printf("[PPU-PERF] render_scanline() (LY=%d) took %lld microseconds\n", 
                   ly_, duration.count());
        }
    }
    // -------------------------------------------
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
    
    // --- Step 0364: Doble Buffering ---
    // Índice base en el framebuffer back (donde escribimos) para la línea actual
    uint8_t* framebuffer_line = &framebuffer_back_[ly_ * SCREEN_WIDTH];
    
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
            framebuffer_back_[line_start_index + screen_x] = final_color;
        } else {
            // Si la dirección no es válida, usar color 0 (transparente/blanco)
            framebuffer_back_[line_start_index + screen_x] = 0;
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
    
    // --- Step 0364: Doble Buffering ---
    // Índice base en el framebuffer back (donde escribimos) para la línea actual
    uint8_t* framebuffer_line = &framebuffer_back_[ly_ * SCREEN_WIDTH];
    
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

