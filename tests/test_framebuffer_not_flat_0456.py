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
    mmu.write(0xFF40, 0x91)  # LCDC: LCD ON, BG ON, Tile Data 0x8000
    
    # Escribir tile con patrón que garantiza índices 0/1/2/3
    # Patrón 0x55/0x33 genera índices: [0, 1, 2, 3, 0, 1, 2, 3]
    tile_data = [
        0x55, 0x33,  # Fila 0: índices 0,1,2,3,0,1,2,3
        0x55, 0x33,  # Fila 1
        0x55, 0x33,  # Fila 2
        0x55, 0x33,  # Fila 3
        0x55, 0x33,  # Fila 4
        0x55, 0x33,  # Fila 5
        0x55, 0x33,  # Fila 6
        0x55, 0x33,  # Fila 7
    ]
    
    for i, byte_val in enumerate(tile_data):
        mmu.write(0x8000 + i, byte_val)
    
    # Colocar tile en BG tilemap
    mmu.write(0x9800, 0x00)  # Tile 0 en posición (0,0)
    
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
    
    # Muestrear 16×16 puntos del framebuffer RGB
    grid_size = 16
    unique_colors = set()
    width = 160
    height = 144
    
    grid_step_x = max(1, width // grid_size)
    grid_step_y = max(1, height // grid_size)
    
    for grid_y in range(grid_size):
        for grid_x in range(grid_size):
            x = min(grid_x * grid_step_x, width - 1)
            y = min(grid_y * grid_step_y, height - 1)
            
            idx = (y * width + x) * 3
            if idx + 2 < len(framebuffer):
                r = framebuffer[idx]
                g = framebuffer[idx + 1]
                b = framebuffer[idx + 2]
                unique_colors.add((r, g, b))
    
    # Assert: al menos 3 colores únicos (no plano)
    unique_count = len(unique_colors)
    assert unique_count >= 3, \
        f"Framebuffer plano: solo {unique_count} colores únicos (esperado ≥3). " \
        f"Colores únicos: {unique_colors}"
    
    print(f"✅ Framebuffer no plano: {unique_count} colores únicos detectados")


if __name__ == "__main__":
    test_framebuffer_not_flat()
    print("✅ Test completado")

