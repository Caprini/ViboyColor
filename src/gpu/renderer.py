"""
Renderer - Motor de Renderizado Gráfico

Este módulo se encarga de visualizar el contenido de la VRAM usando Pygame.
En esta primera iteración, implementamos solo la visualización de tiles en modo debug,
decodificando el formato 2bpp de la Game Boy.

Concepto de Tiles 2bpp:
- Los tiles son bloques de 8x8 píxeles.
- Cada tile ocupa 16 bytes (2 bytes por línea).
- Formato 2bpp: 2 bits por píxel = 4 colores posibles (0-3).
- Para cada línea de 8 píxeles:
  - Byte 1: Bits bajos de cada píxel (bit 7 = píxel 0, bit 6 = píxel 1, ...)
  - Byte 2: Bits altos de cada píxel (bit 7 = píxel 0, bit 6 = píxel 1, ...)
  - Color del píxel = (bit_alto << 1) | bit_bajo

Fuente: Pan Docs - Tile Data, 2bpp Format
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore

if TYPE_CHECKING:
    from ..memory.mmu import MMU

logger = logging.getLogger(__name__)

# Constantes de la Game Boy
GB_WIDTH = 160  # Ancho de la pantalla en píxeles
GB_HEIGHT = 144  # Alto de la pantalla en píxeles
TILE_SIZE = 8  # Tamaño de un tile en píxeles (8x8)
BYTES_PER_TILE = 16  # Cada tile ocupa 16 bytes (2 bytes por línea, 8 líneas)
VRAM_START = 0x8000  # Inicio de VRAM
VRAM_END = 0x9FFF  # Fin de VRAM (8KB = 8192 bytes)
VRAM_SIZE = VRAM_END - VRAM_START + 1  # 8192 bytes

# Paleta de grises fija (para modo debug)
# Color 0: Blanco (más claro)
# Color 1: Gris claro
# Color 2: Gris oscuro
# Color 3: Negro (más oscuro)
PALETTE_GREYSCALE = [
    (255, 255, 255),  # Color 0: Blanco
    (170, 170, 170),  # Color 1: Gris claro
    (85, 85, 85),     # Color 2: Gris oscuro
    (0, 0, 0),        # Color 3: Negro
]


def decode_tile_line(byte1: int, byte2: int) -> list[int]:
    """
    Decodifica una línea de 8 píxeles de un tile en formato 2bpp.
    
    Cada línea de tile usa 2 bytes:
    - byte1: Bits bajos de cada píxel (bit 7 = píxel 0, bit 0 = píxel 7)
    - byte2: Bits altos de cada píxel (bit 7 = píxel 0, bit 0 = píxel 7)
    
    El color de cada píxel se calcula como:
    color = (bit_alto << 1) | bit_bajo
    
    Args:
        byte1: Byte con los bits bajos (0x00-0xFF)
        byte2: Byte con los bits altos (0x00-0xFF)
        
    Returns:
        Lista de 8 enteros (0-3) representando los colores de los píxeles de izquierda a derecha
        
    Ejemplo:
        byte1 = 0x3C (00111100)
        byte2 = 0x7E (01111110)
        
        Píxel 0: bit 7 de ambos = 0, 0 -> Color 0
        Píxel 1: bit 6 = 0, 1 -> Color 1
        Píxel 2: bit 5 = 1, 1 -> Color 3
        ...
    """
    # Enmascarar valores a 8 bits
    byte1 = byte1 & 0xFF
    byte2 = byte2 & 0xFF
    
    pixels: list[int] = []
    
    # Recorrer cada bit de izquierda a derecha (bit 7 a bit 0)
    for bit_pos in range(7, -1, -1):
        # Extraer bit bajo (de byte1)
        bit_low = (byte1 >> bit_pos) & 0x01
        
        # Extraer bit alto (de byte2)
        bit_high = (byte2 >> bit_pos) & 0x01
        
        # Calcular color: (bit_alto << 1) | bit_bajo
        # Esto produce: 0 (00), 1 (01), 2 (10), o 3 (11)
        color = (bit_high << 1) | bit_low
        pixels.append(color)
    
    return pixels


class Renderer:
    """
    Motor de renderizado gráfico usando Pygame.
    
    En esta primera iteración, solo implementa el modo debug que visualiza
    el contenido de la VRAM decodificando tiles en formato 2bpp.
    """
    
    def __init__(self, mmu: MMU, scale: int = 3) -> None:
        """
        Inicializa el renderer con Pygame.
        
        Args:
            mmu: Instancia de MMU para acceder a VRAM
            scale: Factor de escala para la ventana (p.ej. 3 = 480x432)
            
        Raises:
            ImportError: Si pygame no está instalado
        """
        if pygame is None:
            raise ImportError(
                "Pygame no está instalado. Instala con: pip install pygame"
            )
        
        self.mmu = mmu
        self.scale = scale
        
        # Dimensiones de la ventana (GB_WIDTH x GB_HEIGHT escalado)
        self.window_width = GB_WIDTH * scale
        self.window_height = GB_HEIGHT * scale
        
        # Inicializar Pygame
        pygame.init()
        
        # Crear ventana
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Viboy Color - VRAM Debug")
        
        logger.info(f"Renderer inicializado: {self.window_width}x{self.window_height} (scale={scale})")

    def render_vram_debug(self) -> None:
        """
        Renderiza el contenido de la VRAM en modo debug.
        
        Decodifica todos los tiles de la VRAM (0x8000-0x9FFF) y los dibuja
        en una rejilla. Cada tile es de 8x8 píxeles.
        
        La VRAM contiene 512 tiles (8192 bytes / 16 bytes por tile).
        Los organizamos en una rejilla de 32 tiles de ancho x 16 tiles de alto.
        """
        # Limpiar pantalla con fondo negro
        self.screen.fill((0, 0, 0))
        
        # Calcular número de tiles que caben en pantalla
        tiles_per_row = 32  # 32 tiles de 8 píxeles = 256 píxeles (más que 160, pero es para debug)
        tiles_per_col = 16  # 16 tiles de 8 píxeles = 128 píxeles (menos que 144, pero suficiente)
        
        # Recorrer cada tile en VRAM
        tile_index = 0
        max_tiles = VRAM_SIZE // BYTES_PER_TILE  # 512 tiles máximo
        
        for tile_y in range(tiles_per_col):
            for tile_x in range(tiles_per_row):
                # Verificar si hemos procesado todos los tiles
                if tile_index >= max_tiles:
                    break
                
                # Calcular dirección base del tile en VRAM
                # Cada tile ocupa 16 bytes
                tile_addr = VRAM_START + (tile_index * BYTES_PER_TILE)
                
                # Decodificar y dibujar el tile
                self._draw_tile(tile_x * TILE_SIZE, tile_y * TILE_SIZE, tile_addr)
                
                tile_index += 1
            
            # Si ya procesamos todos los tiles, salir
            if tile_index >= max_tiles:
                break
        
        # Actualizar la pantalla
        pygame.display.flip()

    def _draw_tile(self, x: int, y: int, tile_addr: int) -> None:
        """
        Dibuja un tile de 8x8 píxeles en la posición (x, y).
        
        Args:
            x: Posición X en píxeles (sin escalar)
            y: Posición Y en píxeles (sin escalar)
            tile_addr: Dirección base del tile en VRAM (0x8000-0x9FFF)
        """
        # Recorrer cada línea del tile (8 líneas)
        for line in range(TILE_SIZE):
            # Cada línea ocupa 2 bytes
            byte1_addr = tile_addr + (line * 2)
            byte2_addr = tile_addr + (line * 2) + 1
            
            # Leer bytes de VRAM
            byte1 = self.mmu.read_byte(byte1_addr)
            byte2 = self.mmu.read_byte(byte2_addr)
            
            # Decodificar la línea
            pixels = decode_tile_line(byte1, byte2)
            
            # Dibujar cada píxel de la línea
            for pixel_x, color_index in enumerate(pixels):
                # Obtener color de la paleta
                color = PALETTE_GREYSCALE[color_index]
                
                # Calcular posición en pantalla (aplicar escala)
                screen_x = (x + pixel_x) * self.scale
                screen_y = (y + line) * self.scale
                
                # Dibujar rectángulo escalado
                pygame.draw.rect(
                    self.screen,
                    color,
                    (screen_x, screen_y, self.scale, self.scale)
                )

    def handle_events(self) -> bool:
        """
        Maneja eventos de Pygame (especialmente pygame.QUIT).
        
        Returns:
            True si se debe continuar ejecutando, False si se debe cerrar
        """
        if pygame is None:
            return True
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        
        return True

    def quit(self) -> None:
        """Cierra Pygame limpiamente."""
        if pygame is not None:
            pygame.quit()
            logger.info("Renderer cerrado")

