"""
Módulo de gestión de memoria (MMU - Memory Management Unit)

La MMU gestiona el espacio de direcciones de 16 bits de la Game Boy (0x0000 a 0xFFFF).
Incluye también la clase Cartridge para cargar y parsear ROMs.
"""

from .cartridge import Cartridge
from .mmu import MMU

__all__ = ["MMU", "Cartridge"]

