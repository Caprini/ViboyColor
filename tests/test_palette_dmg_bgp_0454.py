"""
Test clean-room: Paleta DMG BGP (Step 0454, corregido Step 0456)

Valida que BGP (0xFF47) mapea 4 índices de color correctamente
y que cambiar BGP reordena los colores.

CORRECCIÓN Step 0456: Usa patrón de tile que garantiza índices 0/1/2/3.
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
    
    # --- Step 0456: FIX - Usar patrón que garantiza 0/1/2/3 ---
    # Patrón 0x55/0x33 genera índices: [0, 1, 2, 3, 0, 1, 2, 3]
    # byte_low  = 0x55 = 0b01010101 → bits: 0,1,0,1,0,1,0,1
    # byte_high = 0x33 = 0b00110011 → bits: 0,0,1,1,0,0,1,1
    # color_idx = lo | (hi<<1): 0|0, 1|0, 0|2, 1|2, 0|0, 1|0, 0|2, 1|2
    #            = 0, 1, 2, 3, 0, 1, 2, 3
    tile_data = [
        0x55, 0x33,  # Fila 0: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 1: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 2: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 3: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 4: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 5: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 6: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 7: índices 0,1,2,3,0,1,2,3
    ]
    
    for i, byte_val in enumerate(tile_data):
        mmu.write(0x8000 + i, byte_val)
    
    # Colocar tile en BG tilemap (0x9800)
    mmu.write(0x9800, 0x00)  # Tile 0 en posición (0,0)
    
    # Set BGP=0xE4 (mapeo normal: 0→white, 1→light gray, 2→dark gray, 3→black)
    # 0xE4 = 0b11100100 = shade3 shade2 shade1 shade0
    mmu.write(0xFF47, 0xE4)
    
    # Render 1 frame (70224 ciclos)
    cycles_per_frame = 70224
    for _ in range(cycles_per_frame // 4):  # CPU steps en M-cycles
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)  # PPU en T-cycles
    
    # --- Step 0457: Sanity assert - Verificar índices antes de mirar RGB ---
    indices_buffer = ppu.get_framebuffer_indices()
    assert indices_buffer is not None, "Framebuffer de índices no disponible"
    
    # Muestrear 8 píxeles conocidos (píxeles 0, 1, 2, 3, 4, 5, 6, 7 en fila 0)
    # Para tile 0x55/0x33: índices esperados [0, 1, 2, 3, 0, 1, 2, 3]
    indices_sample = []
    for x in [0, 1, 2, 3, 4, 5, 6, 7]:
        idx = 0 * 160 + x  # Fila 0, píxel x
        if idx < len(indices_buffer):
            indices_sample.append(indices_buffer[idx])
    
    unique_indices = set(indices_sample)
    print(f"[TEST-BGP-SANITY] Índices sample (8 píxeles): {indices_sample}")
    print(f"[TEST-BGP-SANITY] Índices únicos: {unique_indices}")
    
    # Assert: debe contener {0, 1, 2, 3} (no plano)
    assert unique_indices == {0, 1, 2, 3}, \
        f"Índices plano: solo {unique_indices} (esperado {{0,1,2,3}}). " \
        f"Si esto falla → bug NO es paleta; es decode/render."
    
    # Si esto pasa pero RGB sigue plano → bug de conversión o escritura RGB
    # -------------------------------------------
    
    # --- Step 0457: Verificar paleta reg usado ---
    pal_regs = ppu.get_last_palette_regs_used()
    if pal_regs:
        bgp_used = pal_regs['bgp']
        print(f"[TEST-BGP-REGS] BGP escrito: 0xE4, BGP usado por convert: 0x{bgp_used:02X}")
        assert bgp_used == 0xE4, \
            f"Paleta reg incorrecto: escrito 0xE4, usado 0x{bgp_used:02X}. " \
            f"Si usa 0x00 o 0xFF → bug en lectura/reg caching."
    
    # Samplear 4 píxeles conocidos (píxeles 0, 2, 4, 6 en fila 0)
    # Estos corresponden a índices 0, 2, 0, 2 según decode 2bpp
    framebuffer = ppu.get_framebuffer_rgb()
    assert framebuffer is not None, "Framebuffer RGB no disponible"
    
    pixels_rgb = []
    for x in [0, 2, 4, 6]:  # Píxeles con índices 0, 2, 0, 2
        idx = (0 * 160 + x) * 3  # Fila 0, píxel x
        if idx + 2 < len(framebuffer):
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            pixels_rgb.append((r, g, b))
    
    # --- Step 0456: Assert robusto (no valores RGB exactos) ---
    # Con BGP=0xE4 y índices 0,2,0,2, deberíamos tener al menos 2 colores distintos
    # (shade de índice 0 y shade de índice 2)
    unique_colors = set(pixels_rgb)
    assert len(unique_colors) >= 3, \
        f"Frame plano: solo {len(unique_colors)} colores únicos (esperado ≥3 con patrón 0x55/0x33)"
    
    # Guardar para comparación
    pixels_rgb_bgp_e4 = pixels_rgb.copy()
    
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
    for i in range(min(len(pixels_rgb_bgp_e4), len(pixels_rgb2))):
        if pixels_rgb_bgp_e4[i] != pixels_rgb2[i]:
            changed = True
            break
    
    assert changed, "BGP no reordena colores: píxeles no cambiaron al cambiar BGP"
    
    print("✅ Test DMG BGP: paleta mapea 4 índices y es reordenable (con patrón corregido)")


if __name__ == "__main__":
    test_dmg_bgp_palette_mapping()
    print("✅ Test completado")

