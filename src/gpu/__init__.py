"""
GPU (Graphics Processing Unit) - Unidad de Procesamiento Gráfico

Este módulo contiene los componentes relacionados con el renderizado y la gestión
de la pantalla de la Game Boy:
- PPU (Pixel Processing Unit): Motor de renderizado y timing
- Renderer: Motor de visualización usando Pygame
"""

from .ppu import PPU

try:
    from .renderer import Renderer, decode_tile_line
    __all__ = ["PPU", "Renderer", "decode_tile_line"]
except ImportError:
    # Si pygame no está instalado, Renderer no estará disponible
    __all__ = ["PPU"]

