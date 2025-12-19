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
    , scanline_rendered_(false)
    , framebuffer_(FRAMEBUFFER_SIZE, 0xFF808080)  // Inicializar a gris (0x80, 0x80, 0x80) para diagnóstico
{
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
    
    // DIAGNÓSTICO: Pintar un píxel ROJO en la esquina superior izquierda (posición 0)
    // Esto nos permitirá verificar que el enlace C++ -> Python funciona
    // Color: 0xFFFF0000 = ARGB (Alpha=FF, Red=FF, Green=00, Blue=00) = Rojo sólido
    framebuffer_[0] = 0xFFFF0000;
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
    
    // CRÍTICO: Renderizar scanline cuando estamos en Mode 0 (H-Blank) dentro de una línea visible
    // Esto asegura que renderizamos incluso si avanzamos muchos ciclos de una vez
    // Usamos un flag para evitar renderizar múltiples veces la misma línea
    if (mode_ == MODE_0_HBLANK && ly_ < VISIBLE_LINES && !scanline_rendered_) {
        render_scanline();
        scanline_rendered_ = true;
    }
    
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
        
        // CRÍTICO: Cuando LY cambia, reiniciar los flags de interrupción y renderizado
        // Esto permite que se dispare una nueva interrupción y renderizado si las condiciones
        // se cumplen en la nueva línea
        stat_interrupt_line_ = false;
        scanline_rendered_ = false;
        
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

uint32_t* PPU::get_framebuffer_ptr() {
    return framebuffer_.data();
}

void PPU::render_scanline() {
    // Solo renderizar si estamos en una línea visible (0-143)
    if (ly_ >= VISIBLE_LINES) {
        return;
    }
    
    // Renderizar Background primero (si está habilitado)
    uint8_t lcdc = mmu_->read(IO_LCDC);
    if ((lcdc & 0x01) != 0) {  // Bit 0: BG Display Enable
        render_bg();
    }
    
    // Renderizar Window encima del Background (si está habilitado)
    if ((lcdc & 0x20) != 0) {  // Bit 5: Window Enable
        render_window();
    }
    
    // Renderizar Sprites encima de Background y Window (si están habilitados)
    if ((lcdc & 0x02) != 0) {  // Bit 1: OBJ (Sprite) Display Enable
        render_sprites();
    }
}

void PPU::render_bg() {
    // Leer registros necesarios
    uint8_t lcdc = mmu_->read(IO_LCDC);
    uint8_t scy = mmu_->read(IO_SCY);
    uint8_t scx = mmu_->read(IO_SCX);
    uint8_t bgp = mmu_->read(IO_BGP);
    
    // Decodificar paleta BGP (cada par de bits representa un color 0-3)
    // Formato: bits 0-1 = color 0, bits 2-3 = color 1, bits 4-5 = color 2, bits 6-7 = color 3
    uint32_t palette[4];
    palette[0] = ((bgp >> 0) & 0x03) == 0 ? 0xFFFFFFFF :  // Blanco
                 ((bgp >> 0) & 0x03) == 1 ? 0xFFAAAAAA :  // Gris claro
                 ((bgp >> 0) & 0x03) == 2 ? 0xFF555555 :  // Gris oscuro
                 0xFF000000;                                // Negro
    palette[1] = ((bgp >> 2) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 2) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 2) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette[2] = ((bgp >> 4) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 4) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 4) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette[3] = ((bgp >> 6) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 6) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 6) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    
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
    uint32_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
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
        
        // Escribir el píxel en el framebuffer
        uint8_t color_idx = cached_tile_line[pixel_in_tile];
        framebuffer_line[screen_x] = palette[color_idx];
    }
}

void PPU::render_window() {
    // Leer registros necesarios
    uint8_t lcdc = mmu_->read(IO_LCDC);
    uint8_t wy = mmu_->read(IO_WY);
    uint8_t wx = mmu_->read(IO_WX);
    
    // La Window solo se dibuja si WY <= LY y WX <= 166
    // (WX tiene un offset de 7 píxeles, así que WX=7 significa posición X=0)
    if (ly_ < wy || wx > 166) {
        return;
    }
    
    // Leer paleta BGP (la Window usa la misma paleta que Background)
    uint8_t bgp = mmu_->read(IO_BGP);
    uint32_t palette[4];
    palette[0] = ((bgp >> 0) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 0) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 0) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette[1] = ((bgp >> 2) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 2) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 2) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette[2] = ((bgp >> 4) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 4) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 4) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette[3] = ((bgp >> 6) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((bgp >> 6) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((bgp >> 6) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    
    // Determinar tilemap base para Window (Bit 6 de LCDC)
    uint16_t map_base = (lcdc & 0x40) != 0 ? TILEMAP_1 : TILEMAP_0;
    
    // Determinar tile data base (Bit 4 de LCDC, igual que Background)
    bool unsigned_addressing = (lcdc & 0x10) != 0;
    uint16_t data_base = unsigned_addressing ? TILE_DATA_0 : TILE_DATA_1;
    
    // Calcular posición Y dentro de la Window (sin scroll, siempre desde 0)
    uint8_t y_pos_in_window = ly_ - wy;
    uint8_t tile_y = y_pos_in_window / TILE_SIZE;
    uint8_t line_in_tile = y_pos_in_window % TILE_SIZE;
    
    // Calcular posición X de inicio de la Window (WX - 7)
    int16_t window_x_start = static_cast<int16_t>(wx) - 7;
    if (window_x_start < 0) {
        window_x_start = 0;
    }
    if (window_x_start >= SCREEN_WIDTH) {
        return;  // Window completamente fuera de pantalla
    }
    
    // Índice base en el framebuffer para la línea actual
    uint32_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
    // Buffer temporal para decodificar una línea de tile
    uint8_t tile_line[8];
    
    // Calcular cuántos tiles dibujar
    uint8_t tiles_to_draw = (SCREEN_WIDTH - window_x_start + TILE_SIZE - 1) / TILE_SIZE;
    
    // Renderizar tiles de la Window
    for (uint8_t x = 0; x < tiles_to_draw; x++) {
        uint8_t tile_x = x;
        
        // Obtener tile ID del tilemap
        uint16_t tilemap_addr = map_base + (tile_y * 32 + tile_x);
        uint8_t tile_id = mmu_->read(tilemap_addr);
        
        // Calcular dirección del tile en VRAM
        uint16_t tile_addr;
        if (unsigned_addressing) {
            tile_addr = data_base + (tile_id * 16);
        } else {
            int8_t signed_tile_id = static_cast<int8_t>(tile_id);
            tile_addr = data_base + ((signed_tile_id + 128) * 16);
        }
        
        // Decodificar la línea del tile
        decode_tile_line(tile_addr, line_in_tile, tile_line);
        
        // Escribir píxeles en el framebuffer (sobrescribiendo Background)
        for (uint8_t p = 0; p < TILE_SIZE; p++) {
            uint16_t pixel_x = window_x_start + x * TILE_SIZE + p;
            if (pixel_x < SCREEN_WIDTH) {
                uint8_t color_idx = tile_line[p];
                framebuffer_line[pixel_x] = palette[color_idx];
            }
        }
    }
}

void PPU::decode_tile_line(uint16_t tile_addr, uint8_t line, uint8_t* output) {
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
    // Solo renderizar si estamos en una línea visible (0-143)
    if (ly_ >= VISIBLE_LINES) {
        return;
    }
    
    // Leer paletas de sprites
    uint8_t obp0 = mmu_->read(IO_OBP0);
    uint8_t obp1 = mmu_->read(IO_OBP1);
    
    // Decodificar paletas OBP0 y OBP1 (mismo formato que BGP)
    // Cada par de bits representa un color 0-3
    uint32_t palette0[4];
    palette0[0] = ((obp0 >> 0) & 0x03) == 0 ? 0xFFFFFFFF :  // Blanco
                 ((obp0 >> 0) & 0x03) == 1 ? 0xFFAAAAAA :  // Gris claro
                 ((obp0 >> 0) & 0x03) == 2 ? 0xFF555555 :  // Gris oscuro
                 0xFF000000;                                // Negro
    palette0[1] = ((obp0 >> 2) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp0 >> 2) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp0 >> 2) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette0[2] = ((obp0 >> 4) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp0 >> 4) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp0 >> 4) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette0[3] = ((obp0 >> 6) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp0 >> 6) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp0 >> 6) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    
    uint32_t palette1[4];
    palette1[0] = ((obp1 >> 0) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp1 >> 0) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp1 >> 0) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette1[1] = ((obp1 >> 2) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp1 >> 2) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp1 >> 2) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette1[2] = ((obp1 >> 4) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp1 >> 4) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp1 >> 4) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    palette1[3] = ((obp1 >> 6) & 0x03) == 0 ? 0xFFFFFFFF :
                 ((obp1 >> 6) & 0x03) == 1 ? 0xFFAAAAAA :
                 ((obp1 >> 6) & 0x03) == 2 ? 0xFF555555 :
                 0xFF000000;
    
    // Leer LCDC para determinar altura de sprite
    uint8_t lcdc = mmu_->read(IO_LCDC);
    uint8_t sprite_height = ((lcdc & 0x04) != 0) ? 16 : 8;  // Bit 2: OBJ Size (0=8x8, 1=8x16)
    
    // Índice base en el framebuffer para la línea actual
    uint32_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
    // Buffer temporal para decodificar una línea de tile
    uint8_t tile_line[8];
    
    // Iterar todos los sprites en OAM (0xFE00-0xFE9F)
    for (uint8_t sprite_index = 0; sprite_index < MAX_SPRITES; sprite_index++) {
        uint16_t sprite_addr = OAM_START + (sprite_index * BYTES_PER_SPRITE);
        
        // Leer atributos del sprite
        uint8_t sprite_y = mmu_->read(sprite_addr + 0);
        uint8_t sprite_x = mmu_->read(sprite_addr + 1);
        uint8_t tile_id = mmu_->read(sprite_addr + 2);
        uint8_t attributes = mmu_->read(sprite_addr + 3);
        
        // Decodificar atributos
        bool priority = (attributes & 0x80) != 0;  // Bit 7: Prioridad (0=encima, 1=detrás)
        bool y_flip = (attributes & 0x40) != 0;    // Bit 6: Y-Flip
        bool x_flip = (attributes & 0x20) != 0;    // Bit 5: X-Flip
        uint8_t palette_num = (attributes >> 4) & 0x01;  // Bit 4: Paleta (0=OBP0, 1=OBP1)
        
        // Seleccionar paleta
        uint32_t* palette = (palette_num == 0) ? palette0 : palette1;
        
        // Calcular posición en pantalla (Y y X tienen offset: Y = sprite_y - 16, X = sprite_x - 8)
        // Si Y o X son 0, el sprite está oculto
        if (sprite_y == 0 || sprite_x == 0) {
            continue;  // Sprite oculto
        }
        
        int16_t screen_y = static_cast<int16_t>(sprite_y) - 16;
        int16_t screen_x = static_cast<int16_t>(sprite_x) - 8;
        
        // Verificar si el sprite intersecta con la línea actual (LY)
        // Un sprite de altura H intersecta si: screen_y <= ly < screen_y + H
        // Convertir ly_ a int16_t para comparar correctamente con screen_y (que puede ser negativo)
        int16_t ly_signed = static_cast<int16_t>(ly_);
        if (ly_signed < screen_y || ly_signed >= (screen_y + sprite_height)) {
            continue;  // Sprite no intersecta con esta línea
        }
        
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
        
        // Calcular dirección del tile en VRAM (sprites siempre usan direccionamiento unsigned desde 0x8000)
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
            
            // Obtener índice de color del píxel
            uint8_t color_idx = tile_line[pixel_in_tile];
            
            // CRÍTICO: El color 0 en sprites es transparente (no se dibuja)
            if (color_idx == 0) {
                continue;
            }
            
            // Obtener color de la paleta
            uint32_t sprite_color = palette[color_idx];
            
            // Obtener color actual del framebuffer (background/window)
            uint32_t bg_color = framebuffer_line[final_x];
            
            // Aplicar prioridad: si priority=true, el sprite se dibuja detrás del fondo
            // (excepto si el color del fondo es 0, que es transparente)
            // Para simplificar, si priority=true y el fondo no es blanco (color 0 de BGP),
            // no dibujamos el sprite. En la práctica, necesitamos verificar el color real del fondo.
            // Por ahora, dibujamos el sprite siempre (se puede mejorar después).
            
            // Escribir píxel del sprite en el framebuffer
            framebuffer_line[final_x] = sprite_color;
        }
    }
}

