#include "PPU.hpp"
#include "MMU.hpp"
#include <cstdio>

PPU::PPU(MMU* mmu) 
    : mmu_(mmu)
    , ly_(0)
    , clock_(0)
    , mode_(MODE_2_OAM_SEARCH)
    , frame_ready_(false)
    , lyc_(0)
    , stat_interrupt_line_(false)
    , scanline_rendered_(false)
    , framebuffer_(FRAMEBUFFER_SIZE, 0)  // Inicializar a índice 0 (blanco por defecto con paleta estándar)
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
}

PPU::~PPU() {
    // No hay recursos dinámicos que liberar
    // (mmu_ es un puntero que no poseemos)
}

void PPU::step(int cpu_cycles) {
    // DIAGNÓSTICO TEMPORAL: Verificar que el método se ejecuta
    printf("[PPU::step] Iniciando step() con %d ciclos\n", cpu_cycles);
    fflush(stdout);
    
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        printf("[PPU::step CRITICAL] mmu_ es nullptr!\n");
        fflush(stdout);
        // Si mmu_ es nullptr, no podemos avanzar la PPU
        // Esto puede ocurrir si la MMU fue destruida antes que la PPU
        return;
    }
    
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
        // CRÍTICO: Renderizar la línea ANTES de avanzar a la siguiente
        // Esto asegura que renderizamos cada línea visible exactamente una vez
        // cuando completamos los 456 ciclos de esa línea (estamos en H-Blank)
        if (ly_ < VISIBLE_LINES && !scanline_rendered_) {
            render_scanline();
            scanline_rendered_ = true;
            printf("[PPU::step] render_scanline() retornó, continuando...\n");
            fflush(stdout);
        }
        
        printf("[PPU::step] Restando ciclos y avanzando línea...\n");
        fflush(stdout);
        
        // Restar los ciclos de una línea completa
        clock_ -= CYCLES_PER_SCANLINE;
        
        // Avanzar a la siguiente línea
        ly_ += 1;
        
        printf("[PPU::step] LY incrementado a %d\n", ly_);
        fflush(stdout);
        
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
            printf("[PPU::step] V-Blank detectado (LY=144), solicitando interrupción...\n");
            fflush(stdout);
            
            // CRÍTICO: Activar bit 0 del registro IF (Interrupt Flag) en 0xFF0F
            // Este bit corresponde a la interrupción V-Blank.
            //
            // IMPORTANTE: IF se actualiza SIEMPRE cuando ocurre V-Blank,
            // INDEPENDIENTEMENTE del estado de IME (Interrupt Master Enable).
            uint8_t if_val = mmu_->read(IO_IF);
            if_val |= 0x01;  // Set bit 0 (V-Blank interrupt)
            mmu_->write(IO_IF, if_val);
            
            printf("[PPU::step] Interrupción V-Blank escrita\n");
            fflush(stdout);
            
            // CRÍTICO: Marcar frame como listo para renderizar
            frame_ready_ = true;
        }
        
        // Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
        if (ly_ > 153) {
            printf("[PPU::step] Reiniciando LY a 0 (nuevo frame)\n");
            fflush(stdout);
            ly_ = 0;
            // Reiniciar flag de interrupción STAT al cambiar de frame
            stat_interrupt_line_ = false;
        }
        
        printf("[PPU::step] Fin del bucle while, continuando...\n");
        fflush(stdout);
    }
    
    printf("[PPU::step] Saliendo del bucle while, actualizando modo...\n");
    fflush(stdout);
    
    // Actualizar el modo después de procesar líneas completas
    // (por si quedaron ciclos residuales en la línea actual)
    update_mode();
    
    printf("[PPU::step] Modo actualizado, verificando interrupciones STAT...\n");
    fflush(stdout);
    
    // Verificar interrupciones STAT si LY cambió o el modo cambió
    if (ly_ != old_ly || mode_ != old_mode) {
        printf("[PPU::step] LY o modo cambió, llamando a check_stat_interrupt()...\n");
        fflush(stdout);
        check_stat_interrupt();
        printf("[PPU::step] check_stat_interrupt() retornó\n");
        fflush(stdout);
    }
    
    // DIAGNÓSTICO: Confirmar que step() está a punto de retornar
    printf("[PPU::step] step() completado, retornando a Python\n");
    fflush(stdout);
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
    printf("[PPU::check_stat_interrupt] Iniciando...\n");
    fflush(stdout);
    
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    if (mmu_ == nullptr) {
        printf("[PPU::check_stat_interrupt CRITICAL] mmu_ es nullptr!\n");
        fflush(stdout);
        return;
    }
    
    printf("[PPU::check_stat_interrupt] mmu_ es válido, verificando puntero...\n");
    fflush(stdout);
    
    printf("[PPU::check_stat_interrupt] mmu_ puntero: %p\n", (void*)mmu_);
    fflush(stdout);
    
    printf("[PPU::check_stat_interrupt] IO_STAT = 0x%04X\n", IO_STAT);
    fflush(stdout);
    
    printf("[PPU::check_stat_interrupt] Llamando a mmu_->read(IO_STAT)...\n");
    fflush(stdout);
    
    // Leer el registro STAT directamente de memoria
    // Solo leemos los bits configurables (3-7), los bits 0-2 se actualizan dinámicamente
    uint8_t stat_value = mmu_->read(IO_STAT);
    
    printf("[PPU::check_stat_interrupt] STAT leído exitosamente: 0x%02X\n", stat_value);
    fflush(stdout);
    
    printf("[PPU::check_stat_interrupt] STAT leído: 0x%02X\n", stat_value);
    fflush(stdout);
    
    // Inicializar señal de interrupción
    bool signal = false;
    
    // Verificar LYC=LY Coincidence (bit 2 y bit 6)
    bool lyc_match = (ly_ & 0xFF) == (lyc_ & 0xFF);
    
    printf("[PPU::check_stat_interrupt] LY=%d, LYC=%d, match=%d\n", ly_ & 0xFF, lyc_ & 0xFF, lyc_match);
    fflush(stdout);
    
    // Actualizar bit 2 de STAT dinámicamente (LYC=LY Coincidence Flag)
    // Preservamos los bits configurables (3-7) y actualizamos bits 0-2
    if (lyc_match) {
        printf("[PPU::check_stat_interrupt] LYC match, actualizando STAT...\n");
        fflush(stdout);
        
        // Set bit 2 de STAT (LYC=LY Coincidence Flag)
        stat_value = (stat_value & 0xF8) | mode_ | 0x04;  // Set bit 2
        mmu_->write(IO_STAT, stat_value);
        
        printf("[PPU::check_stat_interrupt] STAT escrito: 0x%02X\n", stat_value);
        fflush(stdout);
        
        // Si el bit 6 (LYC Int Enable) está activo, solicitar interrupción
        if ((stat_value & 0x40) != 0) {  // Bit 6 activo
            signal = true;
        }
    } else {
        printf("[PPU::check_stat_interrupt] LYC no match, actualizando STAT...\n");
        fflush(stdout);
        
        // Si LY != LYC, el bit 2 debe estar limpio
        stat_value = (stat_value & 0xF8) | mode_;  // Clear bit 2
        mmu_->write(IO_STAT, stat_value);
        
        printf("[PPU::check_stat_interrupt] STAT escrito: 0x%02X\n", stat_value);
        fflush(stdout);
    }
    
    printf("[PPU::check_stat_interrupt] Verificando otros bits de STAT...\n");
    fflush(stdout);
    
    // Verificar interrupciones por modo PPU
    if (mode_ == MODE_0_HBLANK && (stat_value & 0x08) != 0) {  // Bit 3 activo
        printf("[PPU::check_stat_interrupt] Mode 0 interrupt habilitado\n");
        fflush(stdout);
        signal = true;
    } else if (mode_ == MODE_1_VBLANK && (stat_value & 0x10) != 0) {  // Bit 4 activo
        printf("[PPU::check_stat_interrupt] Mode 1 interrupt habilitado\n");
        fflush(stdout);
        signal = true;
    } else if (mode_ == MODE_2_OAM_SEARCH && (stat_value & 0x20) != 0) {  // Bit 5 activo
        printf("[PPU::check_stat_interrupt] Mode 2 interrupt habilitado\n");
        fflush(stdout);
        signal = true;
    }
    
    printf("[PPU::check_stat_interrupt] signal=%d, stat_interrupt_line_=%d\n", signal, stat_interrupt_line_);
    fflush(stdout);
    
    // Disparar interrupción en rising edge (solo si signal es True y antes era False)
    if (signal && !stat_interrupt_line_) {
        printf("[PPU::check_stat_interrupt] Disparando interrupción STAT...\n");
        fflush(stdout);
        
        // Activar bit 1 del registro IF (Interrupt Flag) en 0xFF0F
        // Este bit corresponde a la interrupción LCD STAT
        uint8_t if_val = mmu_->read(IO_IF);
        printf("[PPU::check_stat_interrupt] IF leído: 0x%02X\n", if_val);
        fflush(stdout);
        
        if_val |= 0x02;  // Set bit 1 (LCD STAT interrupt)
        mmu_->write(IO_IF, if_val);
        
        printf("[PPU::check_stat_interrupt] IF escrito: 0x%02X\n", if_val);
        fflush(stdout);
    }
    
    // Actualizar flag de interrupción STAT
    stat_interrupt_line_ = signal;
    
    printf("[PPU::check_stat_interrupt] Completado, retornando...\n");
    fflush(stdout);
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

bool PPU::get_frame_ready_and_reset() {
    if (frame_ready_) {
        frame_ready_ = false;
        return true;
    }
    return false;
}

uint8_t* PPU::get_framebuffer_ptr() {
    printf("[PPU::get_framebuffer_ptr] Llamado, framebuffer_.size()=%zu\n", framebuffer_.size());
    fflush(stdout);
    
    uint8_t* ptr = framebuffer_.data();
    
    if (ptr == nullptr) {
        printf("[PPU::get_framebuffer_ptr CRITICAL] framebuffer_.data() retornó nullptr!\n");
        fflush(stdout);
    } else {
        printf("[PPU::get_framebuffer_ptr] Puntero válido: %p\n", (void*)ptr);
        fflush(stdout);
    }
    
    return ptr;
}

void PPU::render_scanline() {
    // DIAGNÓSTICO TEMPORAL: Verificar que el método se ejecuta
    printf("[PPU::render_scanline] Iniciando render_scanline() para LY=%d\n", ly_);
    fflush(stdout);
    
    // CRÍTICO: Verificar que mmu_ no sea nullptr antes de acceder
    // Si mmu_ es nullptr, no podemos renderizar (esto no debería ocurrir si la PPU se creó correctamente)
    if (this->mmu_ == nullptr) {
        printf("[PPU::render_scanline CRITICAL] mmu_ es nullptr!\n");
        fflush(stdout);
        return;
    }
    
    printf("[PPU::render_scanline] mmu_ es válido\n");
    fflush(stdout);
    
    // Solo renderizar si estamos en una línea visible (0-143)
    if (ly_ >= VISIBLE_LINES) {
        printf("[PPU::render_scanline] LY >= VISIBLE_LINES, retornando\n");
        fflush(stdout);
        return;
    }
    
    printf("[PPU::render_scanline] LY es visible, continuando...\n");
    fflush(stdout);
    
    // FASE C: Renderizado real de Background desde VRAM
    // Este método lee los datos de tiles desde la VRAM que la CPU del juego
    // ha escrito y los renderiza en el framebuffer.
    
    printf("[PPU::render_scanline] Leyendo LCDC...\n");
    fflush(stdout);
    
    // Leer registro LCDC para verificar si el LCD está habilitado y configuraciones
    uint8_t lcdc = mmu_->read(IO_LCDC);
    
    printf("[PPU::render_scanline] LCDC leído: 0x%02X\n", lcdc);
    fflush(stdout);
    if (!(lcdc & 0x80)) {  // Bit 7: LCD Display Enable
        printf("[PPU::render_scanline] LCD deshabilitado, retornando\n");
        fflush(stdout);
        return;
    }
    
    printf("[PPU::render_scanline] LCD habilitado, leyendo registros de scroll...\n");
    fflush(stdout);
    
    // Leer registros de scroll
    uint8_t scy = mmu_->read(IO_SCY);
    uint8_t scx = mmu_->read(IO_SCX);
    
    printf("[PPU::render_scanline] SCY=0x%02X, SCX=0x%02X\n", scy, scx);
    fflush(stdout);
    
    // Determinar base de tilemap (Bit 3 de LCDC)
    uint16_t tile_map_base = (lcdc & 0x08) ? 0x9C00 : 0x9800;
    
    // Determinar base de tile data (Bit 4 de LCDC)
    // 1 = 0x8000 (unsigned addressing: tile IDs 0-255)
    // 0 = 0x8800 (signed addressing: tile IDs -128 a 127, tile 0 en 0x9000)
    uint16_t tile_data_base = (lcdc & 0x10) ? 0x8000 : 0x8800;
    bool signed_addressing = !(lcdc & 0x10);
    
    // Índice base en el framebuffer para esta línea
    int line_start_index = static_cast<int>(ly_) * SCREEN_WIDTH;
    
    printf("[PPU::render_scanline] line_start_index=%d\n", line_start_index);
    fflush(stdout);
    
    // Calcular posición Y en el tilemap (con scroll)
    uint8_t map_y = static_cast<uint8_t>((ly_ + scy) & 0xFF);
    uint8_t tile_y_offset = map_y % 8;
    
    printf("[PPU::render_scanline] map_y=%d, tile_y_offset=%d\n", map_y, tile_y_offset);
    fflush(stdout);
    
    printf("[PPU::render_scanline] Iniciando bucle de renderizado (160 píxeles)...\n");
    fflush(stdout);
    
    // Renderizar 160 píxeles (una línea completa)
    for (int x = 0; x < SCREEN_WIDTH; ++x) {
        if (x == 0) {
            printf("[PPU::render_scanline] Primer píxel (x=0)\n");
            fflush(stdout);
        }
        // Calcular posición X en el tilemap (con scroll)
        uint8_t map_x = static_cast<uint8_t>((x + scx) & 0xFF);
        
        // Calcular dirección en el tilemap (32 tiles por línea)
        uint16_t tile_map_addr = tile_map_base + (map_y / 8) * 32 + (map_x / 8);
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: tile_map_addr=0x%04X\n", tile_map_addr);
            fflush(stdout);
        }
        
        // Leer tile ID del tilemap
        uint8_t tile_id = mmu_->read(tile_map_addr);
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: tile_id=0x%02X\n", tile_id);
            fflush(stdout);
        }
        
        // Calcular dirección del tile en VRAM
        uint16_t tile_addr;
        if (signed_addressing) {
            // Signed: tile_id como int8_t, tile 0 está en 0x9000
            // NOTA: Cuando signed_addressing es true, tile_data_base es 0x8800,
            // pero el tile 0 está en 0x9000, no en 0x8800.
            // Fórmula: 0x9000 + (signed_tile_id * 16)
            int8_t signed_tile_id = static_cast<int8_t>(tile_id);
            tile_addr = 0x9000 + (static_cast<int16_t>(signed_tile_id) * 16);
        } else {
            // Unsigned: tile_id directamente (0-255), base en 0x8000
            tile_addr = tile_data_base + (tile_id * 16);
        }
        
        // CRÍTICO: Validar que la dirección del tile esté dentro de VRAM (0x8000-0x9FFF)
        // Esto previene Segmentation Faults por accesos fuera de límites
        // En modo signed, tile_addr puede ser < 0x8000 si signed_tile_id es muy negativo
        // En modo unsigned, tile_addr puede ser > 0x9FFF si tile_id es muy grande
        if (tile_addr < VRAM_START || tile_addr > (VRAM_END - 15)) {
            // Si la dirección está fuera de VRAM, usar color 0 (transparente)
            // Restamos 15 porque un tile completo son 16 bytes (0-15)
            framebuffer_[line_start_index + x] = 0;
            continue;
        }
        
        // Validar que la dirección de la línea del tile también esté dentro de VRAM
        // Cada línea del tile ocupa 2 bytes, así que necesitamos verificar tile_line_addr y tile_line_addr+1
        uint16_t tile_line_addr = tile_addr + tile_y_offset * 2;
        // Verificar que tanto tile_line_addr como tile_line_addr+1 estén dentro de VRAM
        if (tile_line_addr < VRAM_START || tile_line_addr > (VRAM_END - 1) || 
            (tile_line_addr + 1) < VRAM_START || (tile_line_addr + 1) > VRAM_END) {
            // Si la línea del tile está fuera de VRAM, usar color 0 (transparente)
            framebuffer_[line_start_index + x] = 0;
            continue;
        }
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: tile_line_addr=0x%04X\n", tile_line_addr);
            fflush(stdout);
        }
        
        // Leer los dos bytes que forman la línea del tile
        uint8_t byte1 = mmu_->read(tile_line_addr);
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: byte1 leído=0x%02X\n", byte1);
            fflush(stdout);
        }
        
        uint8_t byte2 = mmu_->read(tile_line_addr + 1);
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: byte2 leído=0x%02X\n", byte2);
            fflush(stdout);
        }
        
        // Decodificar el píxel específico (bit position dentro del tile)
        uint8_t bit_pos = 7 - (map_x % 8);
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: bit_pos=%d, map_x=%d\n", bit_pos, map_x);
            fflush(stdout);
        }
        
        uint8_t lsb = (byte1 >> bit_pos) & 1;
        uint8_t msb = (byte2 >> bit_pos) & 1;
        uint8_t color_index = (msb << 1) | lsb;  // Valor 0-3
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: lsb=%d, msb=%d, color_index=%d\n", lsb, msb, color_index);
            fflush(stdout);
        }
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: framebuffer_.size()=%zu, line_start_index+x=%d\n", framebuffer_.size(), line_start_index + x);
            fflush(stdout);
        }
        
        // Escribir índice de color en el framebuffer
        framebuffer_[line_start_index + x] = color_index;
        
        if (x == 0) {
            printf("[PPU::render_scanline] x=0: Escritura al framebuffer completada\n");
            fflush(stdout);
        }
        
        if (x == 1) {
            printf("[PPU::render_scanline] x=1: Segundo píxel procesado\n");
            fflush(stdout);
        }
    }
    
    printf("[PPU::render_scanline] Bucle completado, retornando...\n");
    fflush(stdout);
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
    uint8_t wy = mmu_->read(IO_WY);
    uint8_t wx = mmu_->read(IO_WX);
    
    // La Window solo se dibuja si WY <= LY y WX <= 166
    // (WX tiene un offset de 7 píxeles, así que WX=7 significa posición X=0)
    if (ly_ < wy || wx > 166) {
        return;
    }
    
    // NOTA: render_window() no se usa en esta fase (Fase B simplificada)
    // Se mantiene para referencia futura pero no se llama desde render_scanline()
    
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
    
    // NOTA: render_window() no se usa en esta fase (Fase B simplificada)
    // El código completo se implementará en la siguiente fase
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
    
    // NOTA: render_sprites() no se usa en esta fase (Fase B simplificada)
    // Se mantiene para referencia futura pero no se llama desde render_scanline()
    
    // Leer LCDC para determinar altura de sprite
    uint8_t lcdc = mmu_->read(IO_LCDC);
    uint8_t sprite_height = ((lcdc & 0x04) != 0) ? 16 : 8;  // Bit 2: OBJ Size (0=8x8, 1=8x16)
    
    // Índice base en el framebuffer para la línea actual
    uint8_t* framebuffer_line = &framebuffer_[ly_ * SCREEN_WIDTH];
    
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
            
            // Escribir índice de color en el framebuffer (0-3)
            // La paleta se aplicará en Python
            framebuffer_line[final_x] = color_idx;
        }
    }
}

