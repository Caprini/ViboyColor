"""
GPU (Graphics Processing Unit) - Unidad de Procesamiento Gráfico

Este módulo contiene los componentes relacionados con el renderizado y la gestión
de la pantalla de la Game Boy:
- PPU (Pixel Processing Unit): Motor de renderizado y timing
"""

from .ppu import PPU

__all__ = ["PPU"]

