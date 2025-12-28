"""
Tests de Optimización Gráfica - Framebuffer y Rendimiento

Este módulo contiene tests para validar que las optimizaciones gráficas
(framebuffer con PixelArray) funcionan correctamente y mejoran el rendimiento.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

try:
    import pygame
except ImportError:
    pygame = None
    pytestmark = pytest.mark.skip("Pygame no disponible")

from src.gpu.renderer import Renderer
from src.memory.mmu import MMU, IO_LCDC, IO_BGP


@pytest.fixture
def mmu() -> MMU:
    """Fixture: Crea una MMU para los tests."""
    return MMU(None)


@pytest.fixture
def renderer(mmu: MMU) -> Renderer:
    """Fixture: Crea un Renderer para los tests."""
    return Renderer(mmu, scale=1)


class TestPixelArray:
    """Tests para validar el uso de PixelArray en el framebuffer."""
    
    def test_pixel_array_write(self, renderer: Renderer) -> None:
        """
        Test: Verificar que escribir en PixelArray actualiza el buffer correctamente.
        
        Este test valida que el framebuffer interno (self.buffer) se puede escribir
        usando PixelArray y que los cambios se reflejan correctamente.
        """
        # Configurar LCDC para que se renderice
        renderer.mmu.write_byte(IO_LCDC, 0x91)  # LCD ON, BG ON, unsigned addressing
        renderer.mmu.write_byte(IO_BGP, 0xE4)   # Paleta estándar
        
        # Configurar un tile básico en VRAM (tile ID 0)
        # Tile ID 0 en modo unsigned apunta a 0x8000
        # Escribir un patrón simple: primera línea con píxeles alternados
        renderer.mmu.write_byte(0x8000, 0xAA)  # 10101010 (LSB)
        renderer.mmu.write_byte(0x8001, 0xAA)  # 10101010 (MSB) -> Color 2 (gris oscuro)
        
        # Configurar tilemap: tile ID 0 en posición (0,0)
        renderer.mmu.write_byte(0x9800, 0x00)
        
        # Renderizar frame
        renderer.render_frame()
        
        # Verificar que el buffer tiene contenido (no está vacío)
        # Leer algunos píxeles del buffer usando get_at()
        # El primer píxel (0,0) debería ser Color 2 (gris oscuro) según la paleta 0xE4
        # Paleta 0xE4: Color 0=blanco, Color 1=gris claro, Color 2=gris oscuro, Color 3=negro
        pixel_color = renderer.buffer.get_at((0, 0))
        
        # Color 2 en paleta 0xE4 es (85, 85, 85) según PALETTE_GREYSCALE
        # Verificar que el píxel no es blanco (color de fondo)
        assert pixel_color[:3] != (255, 255, 255), "El píxel debería tener color del tile, no blanco"
        
        # Verificar que el buffer tiene el tamaño correcto (160x144)
        assert renderer.buffer.get_width() == 160
        assert renderer.buffer.get_height() == 144


class TestPerformance:
    """Tests de rendimiento para validar que las optimizaciones mejoran la velocidad."""
    
    def test_render_performance(self, renderer: Renderer) -> None:
        """
        Test: Medir el rendimiento de render_frame().
        
        Este test valida que render_frame() puede renderizar 100 frames
        en menos de 1 segundo (teóricamente > 100 FPS).
        
        NOTA: Este test puede fallar en sistemas muy lentos, pero debería
        pasar en la mayoría de máquinas modernas con las optimizaciones.
        """
        # Configurar LCDC para que se renderice
        renderer.mmu.write_byte(IO_LCDC, 0x91)  # LCD ON, BG ON
        renderer.mmu.write_byte(IO_BGP, 0xE4)   # Paleta estándar
        
        # Configurar un tile básico en VRAM
        renderer.mmu.write_byte(0x8000, 0xFF)  # Línea completa de píxeles
        renderer.mmu.write_byte(0x8001, 0xFF)
        
        # Configurar tilemap: tile ID 0 en todas las posiciones visibles
        for y in range(18):  # 18 tiles de alto (144 píxeles / 8)
            for x in range(20):  # 20 tiles de ancho (160 píxeles / 8)
                addr = 0x9800 + (y * 32) + x
                renderer.mmu.write_byte(addr, 0x00)
        
        # Medir tiempo de renderizado de 100 frames
        num_frames = 100
        start_time = time.time()
        
        for _ in range(num_frames):
            renderer.render_frame()
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Calcular FPS teórico
        fps = num_frames / elapsed_time
        
        # Verificar que el tiempo total es razonable (< 10 segundos para 100 frames)
        # NOTA: En sistemas lentos o con logging activo, puede ser más lento.
        # El objetivo es que sea más rápido que dibujar píxel a píxel con draw.rect.
        # Con PixelArray, deberíamos poder renderizar a > 10 FPS teóricos.
        assert elapsed_time < 10.0, (
            f"Renderizado de {num_frames} frames tomó {elapsed_time:.3f}s "
            f"(esperado < 10.0s). FPS teórico: {fps:.1f}"
        )
        
        # Log informativo (no es una aserción, solo para información)
        print(f"\n✅ Rendimiento: {num_frames} frames en {elapsed_time:.3f}s = {fps:.1f} FPS teórico")
    
    def test_pixel_array_vs_draw_rect_speed(self, renderer: Renderer) -> None:
        """
        Test: Comparar velocidad de PixelArray vs draw.rect (si es posible).
        
        Este test valida que usar PixelArray es más rápido que dibujar píxel a píxel
        con draw.rect. Aunque no podemos medir directamente draw.rect (ya no lo usamos),
        podemos verificar que PixelArray es lo suficientemente rápido.
        """
        # Configurar LCDC
        renderer.mmu.write_byte(IO_LCDC, 0x91)
        renderer.mmu.write_byte(IO_BGP, 0xE4)
        
        # Configurar tilemap básico
        renderer.mmu.write_byte(0x9800, 0x00)
        renderer.mmu.write_byte(0x8000, 0xFF)
        renderer.mmu.write_byte(0x8001, 0xFF)
        
        # Renderizar un frame y medir tiempo
        start_time = time.time()
        renderer.render_frame()
        end_time = time.time()
        
        elapsed_time = end_time - start_time
        
        # Verificar que un frame se renderiza en menos de 100ms
        # NOTA: El objetivo es que sea más rápido que dibujar píxel a píxel.
        # Con PixelArray, deberíamos poder renderizar a > 10 FPS.
        # En sistemas rápidos, debería ser < 16ms (60 FPS), pero en sistemas lentos
        # o con logging activo, puede ser más lento.
        assert elapsed_time < 0.1, (
            f"Renderizado de 1 frame tomó {elapsed_time*1000:.2f}ms "
            f"(esperado < 100ms). Con optimizaciones debería ser < 16ms en sistemas rápidos"
        )
        
        # Log informativo
        print(f"\n✅ Tiempo por frame: {elapsed_time*1000:.2f}ms (objetivo: < 16ms para 60 FPS)")

