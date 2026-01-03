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
    
    # --- Step 0458: C - Configurar LCDC explícitamente ---
    # LCDC bit 7 = LCD ON
    # LCDC bit 0 = BG ON
    # LCDC bit 4 = Tile Data Table (1 = 0x8000, 0 = 0x8800)
    # LCDC bit 3 = BG Tile Map (1 = 0x9C00, 0 = 0x9800)
    lcdc_value = 0x91  # 0b10010001 = LCD ON, BG ON, Tile Data 0x8000, Tile Map 0x9800
    mmu.write(0xFF40, lcdc_value)
    
    # Verificar que LCDC se escribió correctamente
    lcdc_read = mmu.read(0xFF40)
    assert lcdc_read == lcdc_value, \
        f"LCDC no se escribió correctamente: escrito 0x{lcdc_value:02X}, leído 0x{lcdc_read:02X}"
    
    print(f"[TEST-LCDC] LCDC configurado: 0x{lcdc_value:02X} "
          f"(LCD ON, BG ON, Tile Data 0x8000, Tile Map 0x9800)")
    
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
    
    # --- Step 0458: A2 - Roundtrip lectura VRAM ---
    # Leer desde MMU en Python para asegurar que VRAM contiene 0x55/0x33
    vram_bytes_read = []
    for i in [0, 1]:  # Primeros 2 bytes (fila 0)
        vram_bytes_read.append(mmu.read(0x8000 + i))
    
    print(f"[TEST-VRAM-ROUNDTRIP] Escrito: [0x55, 0x33], Leído desde MMU: {[hex(b) for b in vram_bytes_read]}")
    
    assert vram_bytes_read[0] == 0x55 and vram_bytes_read[1] == 0x33, \
        f"VRAM roundtrip falló: escrito [0x55,0x33], leído {vram_bytes_read}"
    
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
    
    # --- Step 0458: Forzar swap de framebuffers antes de leer ---
    # El swap se hace en get_frame_ready_and_reset(), pero el test necesita leer el framebuffer
    # después de que se complete el frame. Llamar a get_frame_ready_and_reset() para hacer el swap.
    frame_ready = ppu.get_frame_ready_and_reset()
    if not frame_ready:
        # Si no hay frame listo, forzar un frame más para asegurar que se complete
        for _ in range(cycles_per_frame // 4):
            m_cycles = cpu.step()
            ppu.step(m_cycles * 4)
        frame_ready = ppu.get_frame_ready_and_reset()
    
    # --- Step 0458: A1 - Verificar que BG render corre ---
    bg_stats = ppu.get_bg_render_stats()
    if bg_stats:
        pixels_written = bg_stats['pixels_written']
        nonzero_seen = bg_stats['nonzero_seen']
        nonzero_value = bg_stats['nonzero_value']
        print(f"[TEST-BG-RENDER] bg_pixels_written={pixels_written}, "
              f"nonzero_seen={nonzero_seen}, nonzero_value={nonzero_value}")
        
        assert pixels_written > 0, \
            f"BG render no ejecuta: pixels_written=0. " \
            f"Si es 0 → rutina no corre / BG disabled / early-return."
    else:
        print("[TEST-BG-RENDER] Stats no disponibles (VIBOY_DEBUG_PPU no activo)")
    
    # --- Step 0458: A2 - Verificar bytes VRAM leídos por PPU ---
    tile_bytes_info = ppu.get_last_tile_bytes_read_info()
    if tile_bytes_info:
        bytes_read = tile_bytes_info['bytes']
        addr_read = tile_bytes_info['addr']
        print(f"[TEST-PPU-VRAM-READ] PPU leyó desde addr 0x{addr_read:04X}: "
              f"[0x{bytes_read[0]:02X}, 0x{bytes_read[1]:02X}]")
        
        # Comparar con esperado
        if bytes_read[0] != 0x55 or bytes_read[1] != 0x33:
            print(f"⚠️ PPU lee bytes incorrectos: esperado [0x55,0x33], "
                  f"obtenido [0x{bytes_read[0]:02X},0x{bytes_read[1]:02X}]")
            print(f"   Si test escribió 0x55/0x33 pero PPU ve 0x00/0x00 → "
                  f"PPU está leyendo del sitio incorrecto.")
    else:
        print("[TEST-PPU-VRAM-READ] Info no disponible (VIBOY_DEBUG_PPU no activo)")
    
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
    
    # --- Step 0459: Verificar pipeline idx→shade→rgb ---
    samples = ppu.get_last_dmg_convert_samples()
    if samples:
        idx_samples = samples['idx'][:8]  # Primeros 8
        shade_samples = samples['shade'][:8]
        rgb_samples = samples['rgb'][:8]
        bgp_used = samples['bgp_used']
        
        print(f"[TEST-PIPELINE] BGP usado: 0x{bgp_used:02X}")
        print(f"[TEST-PIPELINE] Primeros 8 píxeles:")
        print(f"  idx:   {idx_samples}")
        print(f"  shade: {shade_samples}")
        print(f"  rgb:   {rgb_samples}")
        
        # Assert: idx_samples contiene 0,1,2,3 en los primeros 8
        unique_idx = set(idx_samples)
        assert unique_idx == {0, 1, 2, 3}, \
            f"Índices no contienen {{0,1,2,3}}: {unique_idx}"
        
        # Assert: con BGP=0xE4, shade_samples debe tener ≥3 valores distintos
        # BGP=0xE4 = 0b11100100 → mapea idx 0→shade3, 1→shade2, 2→shade1, 3→shade0
        # Esperamos shade variado (no necesariamente igual a idx, pero sí {0,1,2,3})
        unique_shade = set(shade_samples)
        assert len(unique_shade) >= 3, \
            f"Shade colapsa: solo {unique_shade} únicos (esperado ≥3). " \
            f"Si colapsa aquí → bug en dmg_apply_palette()."
        
        # Assert: rgb produce ≥3 valores distintos
        unique_rgb = set(rgb_samples)
        assert len(unique_rgb) >= 3, \
            f"RGB colapsa: solo {len(unique_rgb)} colores únicos (esperado ≥3). " \
            f"Si shade ok pero RGB colapsa → bug en shade_to_rgb() o escritura."
        
        print(f"✅ Pipeline OK: idx={len(unique_idx)} únicos, "
              f"shade={len(unique_shade)} únicos, rgb={len(unique_rgb)} únicos")
    else:
        print("[TEST-PIPELINE] Samples no disponibles (VIBOY_DEBUG_PPU no activo)")
    
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

