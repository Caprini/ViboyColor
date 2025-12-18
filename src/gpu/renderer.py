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

# Importar constantes de MMU para acceso a registros I/O
from ..memory.mmu import IO_LCDC, IO_BGP, IO_SCX, IO_SCY, IO_OBP0, IO_OBP1

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
        pygame.display.set_caption("Viboy Color")
        
        # Crear framebuffer interno (160x144 píxeles, tamaño nativo de Game Boy)
        # Este buffer se escribe píxel a píxel y luego se escala a la ventana
        self.buffer = pygame.Surface((GB_WIDTH, GB_HEIGHT))
        
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

    def render_frame(self) -> None:
        """
        Renderiza un frame completo del Background (fondo) de la Game Boy.
        
        Este método implementa el renderizado básico del Background según la configuración
        del registro LCDC (LCD Control, 0xFF40):
        - Bit 7: LCD Enable (si es 0, pantalla blanca)
        - Bit 4: Tile Data Area (0x8000 unsigned o 0x8800 signed)
        - Bit 3: Tile Map Area (0x9800 o 0x9C00)
        - Bit 0: BG Display (si es 0, fondo blanco)
        
        La pantalla muestra 160x144 píxeles, que corresponden a 20x18 tiles (cada tile es 8x8).
        El tilemap es de 32x32 tiles (256x256 píxeles), pero solo se renderiza la ventana visible.
        
        Por ahora, ignoramos Scroll (SCX/SCY) y Window, dibujando asumiendo cámara en (0,0).
        
        Fuente: Pan Docs - LCD Control Register, Background Tile Map
        """
        # Leer registro LCDC
        lcdc = self.mmu.read_byte(IO_LCDC) & 0xFF
        lcdc_bit7 = (lcdc & 0x80) != 0
        
        # Leer registro BGP (Background Palette)
        bgp = self.mmu.read_byte(IO_BGP) & 0xFF
        
        # Logging de diagnóstico (DEBUG para no ralentizar)
        logger.debug(
            f"Render frame: LCDC=0x{lcdc:02X} (bit7={lcdc_bit7}, LCD {'ON' if lcdc_bit7 else 'OFF'}), "
            f"BGP=0x{bgp:02X}"
        )
        
        # Bit 7: LCD Enable
        # Si el LCD está desactivado, pintar pantalla blanca y retornar
        # NOTA: En modo debug, podríamos renderizar VRAM de todas formas, pero
        # por ahora respetamos el comportamiento del hardware real
        if not lcdc_bit7:
            self.buffer.fill((255, 255, 255))
            scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
            self.screen.blit(scaled_buffer, (0, 0))
            pygame.display.flip()
            logger.debug("LCDC: LCD desactivado (bit 7=0), pantalla blanca - 0 tiles dibujados")
            return
        
        # HACK EDUCATIVO: Ignorar Bit 0 de LCDC (BG Display)
        # En Game Boy Color, el Bit 0 no apaga el fondo, sino que cambia la prioridad
        # de sprites vs fondo. Tetris DX escribe LCDC=0x80 (bit 7=1, bit 0=0) esperando
        # que el fondo se dibuje (comportamiento CGB), pero nuestro emulador actúa como
        # DMG estricta y lo apagaría. Para desbloquear la visualización, ignoramos el
        # Bit 0 y dibujamos el fondo siempre que el LCD esté encendido (Bit 7=1).
        # 
        # NOTA: Esta es una simplificación temporal. En el futuro, cuando implementemos
        # modo CGB completo, el Bit 0 deberá funcionar correctamente según la especificación.
        # 
        # Fuente: Pan Docs - LCD Control Register, Game Boy Color differences
        # 
        # Código original (comentado):
        # if (lcdc & 0x01) == 0:
        #     self.screen.fill((255, 255, 255))
        #     pygame.display.flip()
        #     logger.info("LCDC: Background desactivado (bit 0=0), pantalla blanca - 0 tiles dibujados")
        #     return
        
        logger.debug("HACK EDUCATIVO: Ignorando Bit 0 de LCDC para compatibilidad con juegos CGB (LCDC=0x80)")
        
        # Bit 3: Tile Map Area
        # 0 = 0x9800, 1 = 0x9C00
        if (lcdc & 0x08) == 0:
            map_base = 0x9800
        else:
            map_base = 0x9C00
        
        # Bit 4: Tile Data Area
        # 1 = 0x8000 (unsigned: tile IDs 0-255)
        # 0 = 0x8800 (signed: tile IDs -128 a 127, donde 0 está en 0x9000)
        unsigned_addressing = (lcdc & 0x10) != 0
        if unsigned_addressing:
            data_base = 0x8000
        else:
            data_base = 0x8800  # Signed addressing: tile ID 0 está en 0x9000
        
        # Decodificar paleta BGP
        # BGP es un byte donde cada par de bits representa el color para el índice 0-3:
        # Bits 0-1: Color para índice 0
        # Bits 2-3: Color para índice 1
        # Bits 4-5: Color para índice 2
        # Bits 6-7: Color para índice 3
        # Cada par de bits puede ser 0-3, pero en Game Boy original solo hay 4 tonos de gris
        palette = [
            PALETTE_GREYSCALE[(bgp >> 0) & 0x03],
            PALETTE_GREYSCALE[(bgp >> 2) & 0x03],
            PALETTE_GREYSCALE[(bgp >> 4) & 0x03],
            PALETTE_GREYSCALE[(bgp >> 6) & 0x03],
        ]
        
        # Advertencia si BGP es 0x00 (todo blanco) o 0xFF (todo negro)
        if bgp == 0x00:
            logger.warning("BGP=0x00: Paleta completamente blanca - pantalla aparecerá toda blanca")
        elif bgp == 0xFF:
            logger.info("BGP=0xFF: Paleta completamente negra")
        elif bgp == 0xE4:
            logger.debug("BGP=0xE4: Paleta estándar Game Boy (blanco->gris claro->gris oscuro->negro)")
        
        # Leer registros de Scroll (SCX/SCY)
        # SCX (0xFF43): Scroll X - desplazamiento horizontal del fondo
        # SCY (0xFF42): Scroll Y - desplazamiento vertical del fondo
        # Estos registros permiten "mover la cámara" sobre el tilemap de 256x256 píxeles
        scx = self.mmu.read_byte(IO_SCX) & 0xFF
        scy = self.mmu.read_byte(IO_SCY) & 0xFF
        
        logger.debug(f"Scroll: SCX=0x{scx:02X} ({scx}), SCY=0x{scy:02X} ({scy})")
        
        # Limpiar framebuffer con color de fondo (índice 0 de la paleta)
        self.buffer.fill(palette[0])
        
        # DIAGNÓSTICO: Verificar contenido de VRAM y tilemap cuando se renderiza
        # Verificar algunos tiles del tilemap (primeras 16 posiciones = primera fila)
        tilemap_sample = []
        for i in range(16):
            tile_id = self.mmu.read_byte(map_base + i) & 0xFF
            tilemap_sample.append(tile_id)
        
        # Verificar si hay tiles no vacíos (tile_id != 0)
        non_zero_tiles = [t for t in tilemap_sample if t != 0]
        
        # Verificar algunos bytes de VRAM (primeros 32 bytes = 2 tiles)
        vram_sample = []
        for i in range(32):
            vram_byte = self.mmu.read_byte(VRAM_START + i) & 0xFF
            vram_sample.append(vram_byte)
        
        # Verificar si VRAM tiene datos (no todo ceros)
        non_zero_vram = [b for b in vram_sample if b != 0]
        
        # Verificar también en el rango 0x9000-0x9060 (donde están los tiles en modo signed)
        vram_9000_sample = []
        for i in range(32):
            vram_byte = self.mmu.read_byte(0x9000 + i) & 0xFF
            vram_9000_sample.append(vram_byte)
        non_zero_vram_9000 = [b for b in vram_9000_sample if b != 0]
        
        # Log diagnóstico (INFO para que siempre se muestre)
        # Si hay tiles en el tilemap, verificar qué hay en la dirección del tile
        tile_diagnosis = ""
        if len(non_zero_tiles) > 0:
            # Tomar el primer tile no-cero como ejemplo
            example_tile_id = non_zero_tiles[0]
            # Calcular dirección del tile en VRAM
            if unsigned_addressing:
                example_tile_addr = data_base + (example_tile_id * BYTES_PER_TILE)
            else:
                # Modo signed
                if example_tile_id >= 128:
                    signed_id = example_tile_id - 256
                else:
                    signed_id = example_tile_id
                example_tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
            
            # Leer los primeros 4 bytes del tile (2 líneas)
            tile_bytes = []
            for i in range(4):
                tile_byte = self.mmu.read_byte(example_tile_addr + i) & 0xFF
                tile_bytes.append(tile_byte)
            
            tile_diagnosis = (
                f", Tile 0x{example_tile_id:02X} @ 0x{example_tile_addr:04X} = "
                f"{[f'{b:02X}' for b in tile_bytes]}"
            )
        
        logger.debug(
            f"DIAGNÓSTICO VRAM/Tilemap: "
            f"Tilemap[0:16]={[f'{t:02X}' for t in tilemap_sample[:8]]}... "
            f"(tiles no-0: {len(non_zero_tiles)}/16), "
            f"VRAM[0x8000:0x8020]={len(non_zero_vram)} bytes no-0, "
            f"VRAM[0x9000:0x9020]={len(non_zero_vram_9000)} bytes no-0"
            f"{tile_diagnosis}"
        )
        
        # Contador de tiles dibujados
        tiles_drawn = 0
        
        # Bloquear el framebuffer para escritura rápida de píxeles
        # PixelArray permite escribir píxeles como si fuera una matriz 2D
        # Usar context manager para asegurar cierre correcto antes de blit
        with pygame.PixelArray(self.buffer) as pixels:
            # Renderizar píxeles de la pantalla (160x144 píxeles)
            # Para cada píxel de pantalla, calcular qué píxel del tilemap corresponde
            # aplicando el scroll: map_pixel = (screen_pixel + scroll) % 256
            for screen_y in range(GB_HEIGHT):  # 0-143 (144 líneas)
                for screen_x in range(GB_WIDTH):  # 0-159 (160 columnas)
                    # Calcular posición en el tilemap aplicando scroll
                    # Wrap-around a 256 píxeles (tamaño del tilemap)
                    map_x = (screen_x + scx) & 0xFF  # Wrap-around a 256 píxeles
                    map_y = (screen_y + scy) & 0xFF  # Wrap-around a 256 píxeles
                    
                    # Convertir coordenadas de píxel a coordenadas de tile
                    # Cada tile es de 8x8 píxeles
                    tile_map_x = map_x // TILE_SIZE  # 0-31 (32 tiles de ancho)
                    tile_map_y = map_y // TILE_SIZE  # 0-31 (32 tiles de alto)
                    
                    # Calcular posición del píxel dentro del tile (0-7)
                    pixel_in_tile_x = map_x % TILE_SIZE
                    pixel_in_tile_y = map_y % TILE_SIZE
                    
                    # Leer Tile ID del tilemap
                    # El tilemap es de 32x32 bytes, cada byte es un Tile ID
                    map_addr = map_base + (tile_map_y * 32) + tile_map_x
                    tile_id = self.mmu.read_byte(map_addr) & 0xFF
                    
                    # Calcular dirección del tile en VRAM según el modo de direccionamiento
                    signed_id: int | None = None
                    if unsigned_addressing:
                        # Modo unsigned: tile_id es 0-255, dirección = data_base + (tile_id * 16)
                        tile_addr = data_base + (tile_id * BYTES_PER_TILE)
                    else:
                        # Modo signed: tile_id es -128 a 127, donde 0 está en 0x9000
                        # Convertir a signed: si tile_id >= 128, es negativo
                        if tile_id >= 128:
                            signed_id = tile_id - 256  # Convertir a signed (-128 a -1)
                        else:
                            signed_id = tile_id  # 0 a 127
                        # Tile ID 0 está en 0x9000, así que: 0x9000 + (signed_id * 16)
                        tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
                    
                    # Asegurar que la dirección esté en VRAM (0x8000-0x9FFF)
                    if tile_addr < VRAM_START or tile_addr > VRAM_END:
                        # Si está fuera de VRAM, dibujar píxel con color de fondo (índice 0)
                        color = palette[0]
                    else:
                        # Leer el píxel específico del tile
                        # Cada línea del tile ocupa 2 bytes
                        tile_line_addr = tile_addr + (pixel_in_tile_y * 2)
                        byte1 = self.mmu.read_byte(tile_line_addr) & 0xFF
                        byte2 = self.mmu.read_byte(tile_line_addr + 1) & 0xFF
                        
                        # Decodificar el píxel específico de la línea
                        # El píxel está en la posición pixel_in_tile_x (0-7, de izquierda a derecha)
                        # Necesitamos el bit (7 - pixel_in_tile_x) de cada byte
                        bit_pos = 7 - pixel_in_tile_x
                        bit_low = (byte1 >> bit_pos) & 0x01
                        bit_high = (byte2 >> bit_pos) & 0x01
                        color_index = (bit_high << 1) | bit_low
                        color = palette[color_index]
                    
                    # Escribir píxel directamente en el framebuffer
                    # PixelArray permite acceso directo como matriz 2D: pixels[x, y] = color
                    pixels[screen_x, screen_y] = color
                    tiles_drawn += 1
        
        # Escalar el framebuffer a la ventana y hacer blit
        # pygame.transform.scale es rápido porque opera sobre una superficie completa
        scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
        self.screen.blit(scaled_buffer, (0, 0))
        
        # Renderizar sprites (OBJ) encima del fondo
        # Los sprites se dibujan después del fondo para que aparezcan por encima
        sprites_drawn = self.render_sprites()
        
        # Escalar el framebuffer a la ventana y hacer blit
        # pygame.transform.scale es rápido porque opera sobre una superficie completa
        scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
        self.screen.blit(scaled_buffer, (0, 0))
        
        # Actualizar la pantalla
        pygame.display.flip()
        logger.debug(
            f"Frame renderizado: {tiles_drawn} píxeles dibujados, {sprites_drawn} sprites dibujados, "
            f"map_base=0x{map_base:04X}, data_base=0x{data_base:04X}, unsigned={unsigned_addressing}, "
            f"SCX=0x{scx:02X}, SCY=0x{scy:02X}"
        )

    def _draw_tile_with_palette(self, x: int, y: int, tile_addr: int, palette: list[tuple[int, int, int]]) -> None:
        """
        Dibuja un tile de 8x8 píxeles en la posición (x, y) usando una paleta específica.
        
        Args:
            x: Posición X en píxeles (sin escalar)
            y: Posición Y en píxeles (sin escalar)
            tile_addr: Dirección base del tile en VRAM (0x8000-0x9FFF)
            palette: Lista de 4 colores RGB (tuplas de 3 enteros) para índices 0-3
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
                color = palette[color_index]
                
                # Calcular posición en pantalla (aplicar escala)
                screen_x = (x + pixel_x) * self.scale
                screen_y = (y + line) * self.scale
                
                # Dibujar rectángulo escalado
                pygame.draw.rect(
                    self.screen,
                    color,
                    (screen_x, screen_y, self.scale, self.scale)
                )

    def render_sprites(self) -> int:
        """
        Renderiza los sprites (OBJ - Objects) desde OAM (Object Attribute Memory).
        
        OAM está en 0xFE00-0xFE9F (160 bytes = 40 sprites * 4 bytes).
        Cada sprite tiene 4 bytes:
        - Byte 0: Pos Y (posición en pantalla + 16, 0 = oculto)
        - Byte 1: Pos X (posición en pantalla + 8, 0 = oculto)
        - Byte 2: Tile ID (índice del tile en VRAM)
        - Byte 3: Atributos (Bit 7: Prioridad, Bit 6: Y-Flip, Bit 5: X-Flip, Bit 4: Paleta)
        
        Los sprites se dibujan encima del fondo (a menos que su prioridad diga lo contrario).
        El color 0 en un sprite siempre es transparente (no se dibuja).
        
        Fuente: Pan Docs - OAM, Sprite Attributes, Sprite Rendering
        
        Returns:
            Número de sprites dibujados
        """
        # Leer registro LCDC para verificar si los sprites están habilitados
        lcdc = self.mmu.read_byte(IO_LCDC) & 0xFF
        lcdc_bit1 = (lcdc & 0x02) != 0  # Bit 1: OBJ (Sprite) Display Enable
        
        # Si los sprites están deshabilitados, no renderizar nada
        if not lcdc_bit1:
            logger.debug("Sprites deshabilitados (LCDC bit 1=0)")
            return 0
        
        # Leer paletas de sprites
        obp0 = self.mmu.read_byte(IO_OBP0) & 0xFF  # Object Palette 0
        obp1 = self.mmu.read_byte(IO_OBP1) & 0xFF  # Object Palette 1
        
        # Decodificar paletas (igual que BGP)
        palette0 = [
            PALETTE_GREYSCALE[(obp0 >> 0) & 0x03],
            PALETTE_GREYSCALE[(obp0 >> 2) & 0x03],
            PALETTE_GREYSCALE[(obp0 >> 4) & 0x03],
            PALETTE_GREYSCALE[(obp0 >> 6) & 0x03],
        ]
        palette1 = [
            PALETTE_GREYSCALE[(obp1 >> 0) & 0x03],
            PALETTE_GREYSCALE[(obp1 >> 2) & 0x03],
            PALETTE_GREYSCALE[(obp1 >> 4) & 0x03],
            PALETTE_GREYSCALE[(obp1 >> 6) & 0x03],
        ]
        
        # Si las paletas están en 0x00 (todo blanco), usar paleta por defecto
        if obp0 == 0x00:
            palette0 = PALETTE_GREYSCALE
        if obp1 == 0x00:
            palette1 = PALETTE_GREYSCALE
        
        oam_base = 0xFE00  # OAM comienza en 0xFE00
        sprites_per_oam = 40  # 40 sprites máximo
        bytes_per_sprite = 4  # Cada sprite ocupa 4 bytes
        
        sprites_drawn = 0
        
        # Recorrer todos los sprites en OAM
        for sprite_index in range(sprites_per_oam):
            sprite_addr = oam_base + (sprite_index * bytes_per_sprite)
            
            # Leer atributos del sprite
            sprite_y = self.mmu.read_byte(sprite_addr + 0) & 0xFF
            sprite_x = self.mmu.read_byte(sprite_addr + 1) & 0xFF
            tile_id = self.mmu.read_byte(sprite_addr + 2) & 0xFF
            attributes = self.mmu.read_byte(sprite_addr + 3) & 0xFF
            
            # Decodificar atributos
            priority = (attributes & 0x80) != 0  # Bit 7: Prioridad (0 = encima de fondo, 1 = detrás)
            y_flip = (attributes & 0x40) != 0     # Bit 6: Y-Flip (voltear verticalmente)
            x_flip = (attributes & 0x20) != 0     # Bit 5: X-Flip (voltear horizontalmente)
            palette_num = (attributes >> 4) & 0x01  # Bit 4: Paleta (0 = OBP0, 1 = OBP1)
            
            # Seleccionar paleta según bit 4
            palette = palette0 if palette_num == 0 else palette1
            
            # Calcular posición en pantalla
            # Y e X tienen offset: Y = sprite_y - 16, X = sprite_x - 8
            # Si Y o X son 0, el sprite está oculto
            screen_y = sprite_y - 16
            screen_x = sprite_x - 8
            
            # Verificar si el sprite está visible en pantalla
            # Un sprite está oculto si Y=0 o X=0 (o fuera de los límites)
            if sprite_y == 0 or sprite_x == 0:
                continue  # Sprite oculto, saltar
            
            # Verificar si el sprite está dentro de los límites de la pantalla
            if screen_y < -7 or screen_y >= GB_HEIGHT or screen_x < -7 or screen_x >= GB_WIDTH:
                continue  # Sprite fuera de pantalla, saltar
            
            # Calcular dirección del tile en VRAM
            # Los sprites siempre usan direccionamiento unsigned desde 0x8000
            tile_addr = VRAM_START + (tile_id * BYTES_PER_TILE)
            
            # Verificar que el tile esté en VRAM
            if tile_addr < VRAM_START or tile_addr > VRAM_END:
                continue  # Tile fuera de VRAM, saltar
            
            # Dibujar el sprite tile por tile (8x8 píxeles)
            # NOTA: Por ahora solo soportamos sprites de 8x8. Los sprites de 8x16
            # requieren leer 2 tiles consecutivos, pero eso se implementará más adelante.
            with pygame.PixelArray(self.buffer) as pixels:
                for tile_y in range(TILE_SIZE):
                    for tile_x in range(TILE_SIZE):
                        # Calcular posición del píxel dentro del tile
                        # Aplicar flip si es necesario
                        if y_flip:
                            pixel_tile_y = TILE_SIZE - 1 - tile_y
                        else:
                            pixel_tile_y = tile_y
                        
                        if x_flip:
                            pixel_tile_x = TILE_SIZE - 1 - tile_x
                        else:
                            pixel_tile_x = tile_x
                        
                        # Calcular posición final en pantalla
                        final_y = screen_y + tile_y
                        final_x = screen_x + tile_x
                        
                        # Verificar si el píxel está dentro de los límites
                        if final_y < 0 or final_y >= GB_HEIGHT or final_x < 0 or final_x >= GB_WIDTH:
                            continue  # Píxel fuera de pantalla
                        
                        # Leer el píxel del tile
                        tile_line_addr = tile_addr + (pixel_tile_y * 2)
                        byte1 = self.mmu.read_byte(tile_line_addr) & 0xFF
                        byte2 = self.mmu.read_byte(tile_line_addr + 1) & 0xFF
                        
                        # Decodificar el píxel específico
                        bit_pos = 7 - pixel_tile_x
                        bit_low = (byte1 >> bit_pos) & 0x01
                        bit_high = (byte2 >> bit_pos) & 0x01
                        color_index = (bit_high << 1) | bit_low
                        
                        # CRÍTICO: El color 0 en sprites es transparente
                        # No dibujar si color_index == 0
                        if color_index == 0:
                            continue
                        
                        # NOTA: Por ahora ignoramos la prioridad (bit 7 de atributos)
                        # En el futuro, si priority=True, el sprite debe dibujarse detrás
                        # del fondo (excepto color 0 del fondo). Por ahora, todos los sprites
                        # se dibujan encima del fondo.
                        
                        # Obtener color de la paleta
                        color = palette[color_index]
                        
                        # Dibujar píxel en el framebuffer
                        pixels[final_x, final_y] = color
            
            sprites_drawn += 1
        
        logger.debug(f"Sprites renderizados: {sprites_drawn}/40")
        return sprites_drawn

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
        
        IMPORTANTE: En macOS, pygame.event.pump() es necesario para que la ventana se actualice.
        Este método llama automáticamente a pygame.event.pump() para asegurar que la ventana
        se refresque correctamente en todos los sistemas operativos.
        
        Returns:
            True si se debe continuar ejecutando, False si se debe cerrar
        """
        if pygame is None:
            return True
        
        # En macOS (y algunos otros sistemas), pygame.event.pump() es necesario
        # para que la ventana se actualice correctamente
        pygame.event.pump()
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
        
        return True

    def quit(self) -> None:
        """Cierra Pygame limpiamente."""
        if pygame is not None:
            pygame.quit()
            logger.info("Renderer cerrado")

