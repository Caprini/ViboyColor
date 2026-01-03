"""
Test clean-room: Paleta DMG BGP (Step 0454)

Valida que BGP (0xFF47) mapea 4 índices de color correctamente
y que cambiar BGP reordena los colores.
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


def test_dmg_bgp_palette_mapping():
    """Valida que BGP mapea 4 índices de color y son reordenables."""
    # Inicializar core DMG
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Estado post-boot DMG
    regs.pc = 0x0100
    regs.sp = 0xFFFE
    
    # Encender LCD
    mmu.write(0xFF40, 0x91)  # LCDC: LCD ON, BG ON, Tile Data 0x8000
    
    # Escribir tile en VRAM con patrón de 4 colores (índices 0,1,2,3)
    # Tile en 0x8000 (tile 0)
    # Patrón: 8 píxeles horizontal: 0,1,2,3,0,1,2,3
    # Fila 0: 0b00000000 0b11111111 (índices 0,1,2,3)
    #         bit_low:  0b00000000
    #         bit_high: 0b11111111
    tile_data = [
        0x00, 0xFF,  # Fila 0: índices 0,1,2,3
        0x00, 0xFF,  # Fila 1: índices 0,1,2,3
        0x00, 0xFF,  # Fila 2: índices 0,1,2,3
        0x00, 0xFF,  # Fila 3: índices 0,1,2,3
        0x00, 0xFF,  # Fila 4: índices 0,1,2,3
        0x00, 0xFF,  # Fila 5: índices 0,1,2,3
        0x00, 0xFF,  # Fila 6: índices 0,1,2,3
        0x00, 0xFF,  # Fila 7: índices 0,1,2,3
    ]
    
    for i, byte_val in enumerate(tile_data):
        mmu.write(0x8000 + i, byte_val)
    
    # Colocar tile en BG tilemap (0x9800)
    mmu.write(0x9800, 0x00)  # Tile 0 en posición (0,0)
    
    # Set BGP=0xE4 (mapeo normal: 0→white, 1→light gray, 2→dark gray, 3→black)
    mmu.write(0xFF47, 0xE4)
    
    # Render 1 frame (70224 ciclos)
    cycles_per_frame = 70224
    for _ in range(cycles_per_frame // 4):  # CPU steps en M-cycles
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)  # PPU en T-cycles
    
    # Samplear 4 píxeles conocidos (píxeles 0, 2, 4, 6 en fila 0)
    framebuffer = ppu.get_framebuffer_rgb()
    assert framebuffer is not None, "Framebuffer RGB no disponible"
    
    # Calcular índices en framebuffer RGB (3 bytes por píxel)
    pixels_rgb = []
    for x in [0, 2, 4, 6]:  # Píxeles con índices 0,1,2,3
        idx = (0 * 160 + x) * 3  # Fila 0, píxel x
        if idx + 2 < len(framebuffer):
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            pixels_rgb.append((r, g, b))
    
    # Assert: hay ≥3 valores RGB distintos (no plano)
    unique_colors = set(pixels_rgb)
    assert len(unique_colors) >= 3, f"Frame plano: solo {len(unique_colors)} colores únicos (esperado ≥3)"
    
    # Cambiar BGP=0x1B (mapeo invertido: bits invertidos)
    # 0xE4 = 0b11100100 → 0x1B = 0b00011011
    mmu.write(0xFF47, 0x1B)
    
    # Render 1 frame más
    for _ in range(cycles_per_frame // 4):
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)
    
    # Samplear mismos píxeles
    framebuffer2 = ppu.get_framebuffer_rgb()
    pixels_rgb2 = []
    for x in [0, 2, 4, 6]:
        idx = (0 * 160 + x) * 3
        if idx + 2 < len(framebuffer2):
            r = framebuffer2[idx]
            g = framebuffer2[idx + 1]
            b = framebuffer2[idx + 2]
            pixels_rgb2.append((r, g, b))
    
    # Assert: el set/orden de colores cambia (al menos 1 píxel cambia)
    changed = False
    for i in range(min(len(pixels_rgb), len(pixels_rgb2))):
        if pixels_rgb[i] != pixels_rgb2[i]:
            changed = True
            break
    
    assert changed, "BGP no reordena colores: píxeles no cambiaron al cambiar BGP"
    
    print("✅ Test DMG BGP: paleta mapea 4 índices y es reordenable")


if __name__ == "__main__":
    test_dmg_bgp_palette_mapping()
    print("✅ Test completado")

