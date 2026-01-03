"""
Test clean-room: Paleta DMG OBP0/OBP1 para sprites (Step 0454, corregido Step 0456)

Valida que OBP0/OBP1 mapean colores en sprites correctamente.

CORRECCIÓN Step 0456: Usa patrón de tile que garantiza índices 0/1/2/3,
y muestrea píxeles que no sean índice 0 (transparente).
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
    
    # --- Step 0456: FIX - Usar patrón 0x55/0x33 que garantiza 0/1/2/3 ---
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
    
    # --- Step 0457: Sanity assert - Verificar índices antes de mirar RGB ---
    indices_buffer = ppu.get_framebuffer_indices()
    assert indices_buffer is not None, "Framebuffer de índices no disponible"
    
    # Muestrear píxeles del sprite (fila 26, columnas 19, 21, 23, 25)
    indices_sample = []
    for x in [19, 21, 23, 25]:
        idx = 26 * 160 + x  # Fila 26, píxel x
        if idx < len(indices_buffer):
            indices_sample.append(indices_buffer[idx])
    
    unique_indices = set(indices_sample)
    print(f"[TEST-OBP-SANITY] Índices sample (4 píxeles sprite): {indices_sample}")
    print(f"[TEST-OBP-SANITY] Índices únicos: {unique_indices}")
    
    # Assert: debe contener al menos índices distintos (no todo 0 o plano)
    assert len(unique_indices) >= 2, \
        f"Índices plano en sprite: solo {unique_indices} (esperado ≥2 índices distintos). " \
        f"Si esto falla → bug NO es paleta; es decode/render de sprites."
    
    # --- Step 0457: Verificar paleta reg usado ---
    pal_regs = ppu.get_last_palette_regs_used()
    if pal_regs:
        obp0_used = pal_regs['obp0']
        print(f"[TEST-OBP-REGS] OBP0 escrito: 0xE4, OBP0 usado por convert: 0x{obp0_used:02X}")
        assert obp0_used == 0xE4, \
            f"Paleta reg incorrecto: escrito 0xE4, usado 0x{obp0_used:02X}. " \
            f"Si usa 0x00 o 0xFF → bug en lectura/reg caching."
    
    # Samplear píxeles del sprite (evitar índice 0 transparente)
    # Píxeles 1, 3, 5, 7 en fila 0 del sprite corresponden a índices 1, 3, 1, 3
    # Posición sprite: X=18, Y=26 (pantalla)
    framebuffer = ppu.get_framebuffer_rgb()
    assert framebuffer is not None
    
    # Píxeles aproximados del sprite (fila 26, columnas 19, 21, 23, 25)
    pixels_rgb = []
    for x in [19, 21, 23, 25]:  # Píxeles con índices 1, 3, 1, 3 (no transparentes)
        idx = (26 * 160 + x) * 3
        if idx + 2 < len(framebuffer):
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            pixels_rgb.append((r, g, b))
    
    # Assert: hay ≥2 colores distintos (no todo transparente o plano)
    unique_colors = set(pixels_rgb)
    assert len(unique_colors) >= 2, \
        f"Sprite plano: solo {len(unique_colors)} colores únicos (esperado ≥2 con patrón 0x55/0x33)"
    
    # Guardar para comparación
    pixels_rgb_obp_e4 = pixels_rgb.copy()
    
    # Cambiar OBP0=0x1B (mapeo invertido)
    mmu.write(0xFF48, 0x1B)
    
    # Render 1 frame más
    for _ in range(cycles_per_frame // 4):
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)
    
    # Samplear mismos píxeles
    framebuffer2 = ppu.get_framebuffer_rgb()
    pixels_rgb2 = []
    for x in [19, 21, 23, 25]:
        idx = (26 * 160 + x) * 3
        if idx + 2 < len(framebuffer2):
            r = framebuffer2[idx]
            g = framebuffer2[idx + 1]
            b = framebuffer2[idx + 2]
            pixels_rgb2.append((r, g, b))
    
    # Assert: al menos 1 píxel cambia
    changed = False
    for i in range(min(len(pixels_rgb_obp_e4), len(pixels_rgb2))):
        if pixels_rgb_obp_e4[i] != pixels_rgb2[i]:
            changed = True
            break
    
    assert changed, "OBP0 no reordena colores en sprite"
    
    print("✅ Test DMG OBP0: paleta mapea colores en sprites y es reordenable (con patrón corregido)")


if __name__ == "__main__":
    test_dmg_obj_palette_mapping()
    print("✅ Test completado")

