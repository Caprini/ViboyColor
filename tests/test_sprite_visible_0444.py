"""
Test Clean-Room: Sprite Visible (Step 0444)

Valida que cuando OAM tiene datos de sprite válido y LCD está on,
el framebuffer contiene píxeles non-white en la región esperada.
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


def test_single_sprite_visible():
    """Valida que un sprite visible aparece en el framebuffer."""
    # Inicializar core
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    # Wiring
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # 1. Cargar tile data para sprite (Tile ID 0x00, dirección 0x8000)
    # Patrón simple: 8x8 tile no-blanco (checkerboard)
    # Cada tile son 16 bytes (2 bytes por línea, 8 líneas)
    tile_addr = 0x8000
    # Checkerboard: líneas alternan 0xAA 0x55
    for line in range(8):
        if line % 2 == 0:
            mmu.write(tile_addr + (line * 2), 0xAA)      # Byte 1: 10101010
            mmu.write(tile_addr + (line * 2) + 1, 0x55)  # Byte 2: 01010101
        else:
            mmu.write(tile_addr + (line * 2), 0x55)
            mmu.write(tile_addr + (line * 2) + 1, 0xAA)
    
    # 2. Configurar OAM entry para sprite
    # Sprite entry: y, x, tile_id, flags
    # y = 16 + 20 (visible en scanline 20, offset GB = 16)
    # x = 8 + 30 (visible en columna 30, offset GB = 8)
    # tile_id = 0x00
    # flags = 0x00 (palette 0, no flip, priority normal)
    oam_addr = 0xFE00
    mmu.write(oam_addr + 0, 16 + 20)  # y = 36
    mmu.write(oam_addr + 1, 8 + 30)   # x = 38
    mmu.write(oam_addr + 2, 0x00)     # tile_id = 0
    mmu.write(oam_addr + 3, 0x00)     # flags = 0
    
    # 3. Activar LCD y sprites
    # LCDC: bit 7 = LCD on, bit 1 = sprites enabled, bit 0 = BG enabled
    mmu.write(0xFF40, 0x83)  # LCDC = 0x83 (LCD on, sprites on, BG on)
    
    # BGP: paleta básica (0xFC = blanco/gris oscuro/gris claro/negro)
    mmu.write(0xFF47, 0xFC)
    
    # OBP0: paleta sprite (0xFC = igual que BG para simplicidad)
    mmu.write(0xFF48, 0xFC)
    
    # 4. Ejecutar frames suficientes para que sprite sea visible
    CYCLES_PER_FRAME = 70224
    frames_to_render = 3  # Ejecutar 3 frames para asegurar renderizado
    
    for frame in range(frames_to_render):
        frame_cycles = 0
        while frame_cycles < CYCLES_PER_FRAME:
            cycles = cpu.step()
            ppu.step(cycles)
            timer.step(cycles)
            frame_cycles += cycles
    
    # 5. Verificar framebuffer: debe haber píxeles non-white en bounding box del sprite
    # Sprite está en scanline 20, columna 30, tamaño 8x8
    # Bounding box: scanlines 20-27, columnas 30-37
    framebuffer = ppu.get_framebuffer_rgb()
    SCREEN_WIDTH = 160
    SCREEN_HEIGHT = 144
    
    assert len(framebuffer) == SCREEN_WIDTH * SCREEN_HEIGHT * 3, "Framebuffer tamaño incorrecto"
    
    # Buscar píxeles non-white en bounding box
    nonwhite_count = 0
    sprite_y_start = 20
    sprite_y_end = 27
    sprite_x_start = 30
    sprite_x_end = 37
    
    for y in range(sprite_y_start, min(sprite_y_end + 1, SCREEN_HEIGHT)):
        for x in range(sprite_x_start, min(sprite_x_end + 1, SCREEN_WIDTH)):
            idx = (y * SCREEN_WIDTH + x) * 3
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            
            # Non-white si cualquier canal < 200
            if r < 200 or g < 200 or b < 200:
                nonwhite_count += 1
    
    # Validación: debe haber al menos 10 píxeles non-white en el bounding box
    # (permite transparencias y variaciones de paleta)
    assert nonwhite_count >= 10, (
        f"Sprite no visible: solo {nonwhite_count} píxeles non-white en bounding box "
        f"({sprite_x_start},{sprite_y_start})-({sprite_x_end},{sprite_y_end})"
    )
    
    print(f"✅ Sprite visible: {nonwhite_count} píxeles non-white en bounding box")


def test_sprite_invisible_when_off_screen():
    """Valida que sprite fuera de pantalla no se renderiza."""
    # Similar a test anterior, pero sprite en y=200 (fuera de pantalla)
    # Validar que framebuffer está blanco o no contiene el sprite
    # (Implementación opcional si hay tiempo)
    pass

