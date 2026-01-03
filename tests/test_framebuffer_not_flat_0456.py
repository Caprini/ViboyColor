"""
Test anti-regresión: Framebuffer no plano (Step 0456)

Valida que el framebuffer RGB no es plano (1 color único).
Este test evita que en el futuro volvamos a pasar "por casualidad" con todo un color.
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


def test_framebuffer_not_flat():
    """Valida que el framebuffer RGB tiene al menos 3 colores únicos."""
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
    
    # Encender LCD
    lcdc_value = 0x91  # LCD ON, BG ON, Tile Data 0x8000, Tile Map 0x9800
    mmu.write(0xFF40, lcdc_value)
    
    # --- Step 0460: D - Reutilizar mismo setup que test BGP ---
    # Escribir tile data completo con patrón 0x55/0x33
    tile_index = 0
    tile_base_addr = 0x8000 + (tile_index * 16)
    
    for row in range(8):
        addr_low = tile_base_addr + (row * 2)
        addr_high = addr_low + 1
        mmu.write(addr_low, 0x55)
        mmu.write(addr_high, 0x33)
    
    # Llenar tilemap completo (32×32 = 1024 bytes)
    tilemap_base = 0x9800
    for i in range(32 * 32):
        mmu.write(tilemap_base + i, tile_index)
    
    # Set BGP (cualquier valor que mapee índices a shades distintos)
    mmu.write(0xFF47, 0xE4)  # 0xE4 mapea índices a shades distintos
    
    # Render 1 frame
    cycles_per_frame = 70224
    for _ in range(cycles_per_frame // 4):
        m_cycles = cpu.step()
        ppu.step(m_cycles * 4)
    
    # Obtener framebuffer RGB
    framebuffer = ppu.get_framebuffer_rgb()
    assert framebuffer is not None, "Framebuffer RGB no disponible"
    
    # Muestrear primeros 100 píxeles (suficiente para capturar el patrón 0,1,2,3 repetido)
    unique_colors = set()
    width = 160
    height = 144
    sample_count = min(100, width * height)
    
    for i in range(sample_count):
        x = i % width
        y = i // width
        idx = (y * width + x) * 3
        if idx + 2 < len(framebuffer):
            r = framebuffer[idx]
            g = framebuffer[idx + 1]
            b = framebuffer[idx + 2]
            unique_colors.add((r, g, b))
    
    # --- Step 0460: D - Con tilemap completo, exigir >=4 colores únicos ---
    unique_count = len(unique_colors)
    assert unique_count >= 4, \
        f"Framebuffer plano: solo {unique_count} colores únicos (esperado ≥4). " \
        f"Con tilemap completo debería ser 4. Colores únicos: {unique_colors}"
    
    print(f"✅ Framebuffer no plano: {unique_count} colores únicos detectados (esperado ≥4)")


if __name__ == "__main__":
    test_framebuffer_not_flat()
    print("✅ Test completado")

