"""
Módulo de Entrada/Salida (I/O)

Contiene las clases para manejar los periféricos de entrada/salida de la Game Boy:
- Joypad: Manejo de botones y direcciones (P1, 0xFF00)
- Timer: Sistema de temporización (DIV, TIMA, TMA, TAC)
"""

from .timer import Timer

__all__ = ["Timer"]

