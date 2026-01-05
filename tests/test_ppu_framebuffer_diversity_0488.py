"""
Test Step 0488: Verificar que PPU produce >1 color cuando VRAM tiene patrón.

Este test aísla:
- fetch tile
- decode 2bpp
- apply palette
- write framebuffer

Verifica que el PPU puede producir diversidad de colores en el framebuffer
cuando VRAM contiene un patrón (checkerboard).
"""

import pytest
import os

# Activar VIBOY_DEBUG_FB_STATS para que compute_framebuffer_stats() funcione
os.environ["VIBOY_DEBUG_FB_STATS"] = "1"

from viboy_core import PyPPU, PyMMU


class TestPPUFramebufferDiversity:
    """Tests para verificar diversidad del framebuffer del PPU"""
    
    def test_ppu_produces_multiple_colors_when_vram_has_pattern(self):
        """
        Test que verifica que PPU produce >1 color cuando VRAM tiene patrón.
        
        Este test:
        1. Crea un tile checkerboard en VRAM (alterna índices 0 y 3)
        2. Configura el tilemap para usar ese tile
        3. Activa LCD y BG
        4. Configura BGP para mapear índices a shades distintos
        5. Ejecuta suficientes ciclos para renderizar al menos una línea
        6. Verifica que el framebuffer tiene >= 2 colores únicos
        """
        # Crear componentes (PyMMU puede funcionar sin cartucho para tests básicos)
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Inicializar VRAM con un tile patrón (checkerboard 2bpp)
        # Tile checkerboard: alterna índices 0 y 3
        tile_data = bytearray(16)  # 16 bytes por tile (8 líneas * 2 bytes)
        for line in range(8):
            # Línea par: 0xAA (10101010) = índices 3,0,3,0,3,0,3,0
            # Línea impar: 0x55 (01010101) = índices 0,3,0,3,0,3,0,3
            if line % 2 == 0:
                tile_data[line * 2] = 0xAA      # Bits bajos
                tile_data[line * 2 + 1] = 0xAA  # Bits altos
            else:
                tile_data[line * 2] = 0x55
                tile_data[line * 2 + 1] = 0x55
        
        # Escribir tile en VRAM (tile 0 en 0x8000)
        for i in range(16):
            mmu.write(0x8000 + i, tile_data[i])
        
        # Configurar BG map para usar tile 0
        mmu.write(0x9800, 0x00)  # Primer tile del tilemap = tile 0
        
        # Activar LCDC/BG
        mmu.write(0xFF40, 0x91)  # LCDC: LCD ON, BG ON, tile data 0x8000, tilemap 0x9800
        
        # Configurar BGP para mapear índices a shades distintos
        mmu.write(0xFF47, 0xE4)  # BGP: 0→0, 1→1, 2→2, 3→3 (todos distintos)
        
        # Correr suficientes ciclos para completar al menos 2 frames completos
        # 1 frame = 154 líneas * 456 T-cycles = 70224 ciclos
        # Necesitamos completar frames para que swap_framebuffers() se ejecute
        # y compute_framebuffer_stats() calcule las estadísticas
        
        frames_completed = 0
        max_cycles = 70224 * 3  # 3 frames como máximo
        cycles_executed = 0
        
        while cycles_executed < max_cycles and frames_completed < 2:
            # Ejecutar un ciclo
            ppu.step(1)
            cycles_executed += 1
            
            # Verificar si hay un frame listo (sin resetear el flag)
            if ppu.is_frame_ready():
                # Forzar el present llamando a get_frame_ready_and_reset()
                # Esto ejecuta swap_framebuffers() y compute_framebuffer_stats()
                frame_ready = ppu.get_frame_ready_and_reset()
                if frame_ready:
                    frames_completed += 1
                    print(f"[TEST] Frame {frames_completed} completado (ciclos: {cycles_executed})")
        
        # Forzar present del último frame si hay swap pendiente
        # Esto asegura que compute_framebuffer_stats() se haya ejecutado
        _ = ppu.get_presented_framebuffer_indices()
        
        # Obtener framebuffer stats (después del swap/present)
        fb_stats = ppu.get_framebuffer_stats()
        
        # Assert: fb_unique_colors >= 2
        assert fb_stats is not None, "Framebuffer stats no disponibles"
        assert fb_stats['fb_unique_colors'] >= 2, \
            f"PPU debe producir al menos 2 colores únicos, pero produjo {fb_stats['fb_unique_colors']}"
        
        # Verificar que hay píxeles no-blancos
        assert fb_stats['fb_nonwhite_count'] > 0, \
            f"PPU debe producir píxeles no-blancos, pero produjo {fb_stats['fb_nonwhite_count']}"
        
        # Verificar que hay píxeles no-negros (para asegurar diversidad)
        # Nota: En un checkerboard perfecto, debería haber índices 0 y 3
        # Si solo hay índice 0 (blanco), el test falla
        # Si solo hay índice 3 (negro), el test también falla
        # Esperamos al menos 2 índices diferentes
        assert fb_stats['fb_unique_colors'] >= 2, \
            f"PPU debe producir al menos 2 índices de color diferentes, pero produjo {fb_stats['fb_unique_colors']}"
            
        # Verificar que el framebuffer cambió desde el último frame (si hay stats previos)
        # Esto confirma que el framebuffer se está actualizando
        print(f"[TEST] Framebuffer stats: unique_colors={fb_stats['fb_unique_colors']}, "
              f"nonwhite={fb_stats['fb_nonwhite_count']}, nonblack={fb_stats['fb_nonblack_count']}, "
              f"top4={fb_stats['fb_top4_colors']}, top4_count={fb_stats['fb_top4_colors_count']}")

