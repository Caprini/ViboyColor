"""
Test clean-room: Paleta DMG OBP0/OBP1 para sprites (Step 0454)

Valida que OBP0/OBP1 mapean colores en sprites correctamente.
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


def test_dmg_obj_palette_mapping():
    """Valida que OBP0/OBP1 mapean colores en sprites."""
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
    
    regs.pc = 0x0100
    regs.sp = 0xFFFE
    
    # Encender LCD y sprites
    mmu.write(0xFF40, 0x93)  # LCDC: LCD ON, BG ON, OBJ ON, Tile Data 0x8000
    
    # Escribir tile en VRAM con patrón (índices 1,2,3, evitar 0 transparente)
    tile_data = [
        0x00, 0xFF,  # Fila 0: índices 0,1,2,3 (usaremos 1,2,3)
        0x00, 0xFF,  # Fila 1
        0x00, 0xFF,  # Fila 2
        0x00, 0xFF,  # Fila 3
        0x00, 0xFF,  # Fila 4
        0x00, 0xFF,  # Fila 5
        0x00, 0xFF,  # Fila 6
        0x00, 0xFF,  # Fila 7
    ]
    
    for i, byte_val in enumerate(tile_data):
        mmu.write(0x8000 + i, byte_val)
    
    # Crear sprite en OAM (Sprite 0)
    # Y, X, Tile ID, Attributes
    mmu.write(0xFE00, 16 + 10)  # Y = 16 + 10 (visible)
    mmu.write(0xFE01, 8 + 10)   # X = 8 + 10 (visible)
    mmu.write(0xFE02, 0x00)     # Tile ID 0
    mmu.write(0xFE03, 0x00)     # Attributes: paleta 0 (OBP0), sin flips
    
    # Set OBP0=0xE4 (mapeo normal)
    mmu.write(0xFF48, 0xE4)
    
    # Render 1 frame
    cycles_per_frame = 70224
    for _ in range(cycles_per_frame // 4):
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)
    
    # Samplear 2-3 píxeles del sprite (aproximado en posición conocida)
    framebuffer = ppu.get_framebuffer_rgb()
    assert framebuffer is not None
    
    # Píxeles aproximados del sprite (fila 10, columnas 10-12)
    pixels_rgb = []
    for x in [10, 11, 12]:
        idx = (10 * 160 + x) * 3
        if idx + 2 < len(framebuffer):
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            pixels_rgb.append((r, g, b))
    
    # Assert: hay ≥2 colores distintos (no todo transparente o plano)
    unique_colors = set(pixels_rgb)
    assert len(unique_colors) >= 2, f"Sprite plano: solo {len(unique_colors)} colores únicos"
    
    # Cambiar OBP0=0x1B (mapeo invertido)
    mmu.write(0xFF48, 0x1B)
    
    # Render 1 frame más
    for _ in range(cycles_per_frame // 4):
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)
    
    # Samplear mismos píxeles
    framebuffer2 = ppu.get_framebuffer_rgb()
    pixels_rgb2 = []
    for x in [10, 11, 12]:
        idx = (10 * 160 + x) * 3
        if idx + 2 < len(framebuffer2):
            r = framebuffer2[idx]
            g = framebuffer2[idx + 1]
            b = framebuffer2[idx + 2]
            pixels_rgb2.append((r, g, b))
    
    # Assert: al menos 1 píxel cambia
    changed = False
    for i in range(min(len(pixels_rgb), len(pixels_rgb2))):
        if pixels_rgb[i] != pixels_rgb2[i]:
            changed = True
            break
    
    assert changed, "OBP0 no reordena colores en sprite"
    
    print("✅ Test DMG OBP0: paleta mapea colores en sprites y es reordenable")


if __name__ == "__main__":
    test_dmg_obj_palette_mapping()
    print("✅ Test completado")

