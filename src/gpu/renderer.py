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
from pathlib import Path
from typing import TYPE_CHECKING

try:
    import pygame
except ImportError:
    pygame = None  # type: ignore

if TYPE_CHECKING:
    from ..memory.mmu import MMU

# Importar constantes de MMU para acceso a registros I/O
from ..memory.mmu import IO_LCDC, IO_BGP, IO_SCX, IO_SCY, IO_OBP0, IO_OBP1, IO_WX, IO_WY

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
    
    def __init__(self, mmu: MMU, scale: int = 3, use_cpp_ppu: bool = False, ppu = None, joypad = None) -> None:
        """
        Inicializa el renderer con Pygame.
        
        Args:
            mmu: Instancia de MMU para acceder a VRAM (puede ser Python o C++)
            scale: Factor de escala para la ventana (p.ej. 3 = 480x432)
            use_cpp_ppu: Si es True, usa el framebuffer de PPU C++ (más rápido)
            ppu: Instancia de PyPPU (solo necesario si use_cpp_ppu=True)
            
        Raises:
            ImportError: Si pygame no está instalado
        """
        if pygame is None:
            raise ImportError(
                "Pygame no está instalado. Instala con: pip install pygame"
            )
        
        self.mmu = mmu
        self.scale = scale
        self.use_cpp_ppu = use_cpp_ppu
        self.cpp_ppu = ppu
        self.joypad = joypad  # Instancia de PyJoypad (C++) o Joypad (Python)
        
        # Dimensiones de la ventana (GB_WIDTH x GB_HEIGHT escalado)
        self.window_width = GB_WIDTH * scale
        self.window_height = GB_HEIGHT * scale
        
        # Inicializar Pygame
        pygame.init()
        
        # Crear ventana
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("Viboy Color")
        
        # OPTIMIZACIÓN: Tile Caching
        # La Game Boy tiene 384 tiles únicos en VRAM (0x8000-0x97FF = 6KB = 384 tiles * 16 bytes)
        # En lugar de decodificar cada tile píxel a píxel en cada frame, los cacheamos
        # como superficies pygame de 8x8 y solo los actualizamos cuando cambian.
        # Esto reduce el trabajo de ~23k píxeles a ~360 blits (mucho más rápido).
        # Fuente: Pan Docs - VRAM Tile Data
        self.tile_cache: dict[int, pygame.Surface] = {}  # tile_id -> Surface(8x8)
        self.tile_dirty = [True] * 384  # Flags para tiles 0-383 (0x8000-0x97FF)
        
        # BIG BLIT OPTIMIZACIÓN: Buffer persistente para el tilemap completo (256x256 píxeles = 32x32 tiles)
        # Este buffer se construye una vez y solo se actualiza cuando cambian tiles o paleta.
        # En render_frame(), solo hacemos 1-4 blits de este buffer al buffer final (mucho más rápido).
        self.bg_buffer = pygame.Surface((256, 256))
        self.bg_buffer_dirty = True  # Flag para indicar si bg_buffer necesita reconstrucción completa
        self._last_bgp = None  # Última paleta usada (para detectar cambios)
        
        # Cargar y establecer el icono de la aplicación
        # El icono está en assets/
        icon_path = Path(__file__).parent.parent.parent / "assets" / "viboycolor-icon-no-bg.png"
        if icon_path.exists():
            try:
                icon_surface = pygame.image.load(str(icon_path))
                pygame.display.set_icon(icon_surface)
                logger.info(f"Icono de aplicación cargado: {icon_path}")
            except Exception as e:
                logger.warning(f"No se pudo cargar el icono {icon_path}: {e}")
        else:
            logger.warning(f"Icono no encontrado: {icon_path}")
        
        # Crear framebuffer interno (160x144 píxeles, tamaño nativo de Game Boy)
        # Este buffer se escribe píxel a píxel y luego se escala a la ventana
        self.buffer = pygame.Surface((GB_WIDTH, GB_HEIGHT))
        
        # --- FIX STEP 0216: Definición Explícita de Colores ---
        # Game Boy original: 0=Más claro, 3=Más oscuro
        # Paleta estándar de Game Boy (verde/amarillo original)
        self.COLORS = [
            (224, 248, 208),  # 0: Blanco/Verde claro (White)
            (136, 192, 112),  # 1: Gris claro (Light Gray)
            (52, 104, 86),    # 2: Gris oscuro (Dark Gray)
            (8, 24, 32)       # 3: Negro/Verde oscuro (Black)
        ]
        # Paleta actual mapeada (índice -> RGB)
        self.palette = list(self.COLORS)
        
        # Flag para log de depuración (una sola vez)
        self.debug_palette_printed = False
        # ----------------------------------------
        
        logger.info(f"Renderer inicializado: {self.window_width}x{self.window_height} (scale={scale})")
        
        # Mostrar pantalla de carga
        self._show_loading_screen()

    def _show_loading_screen(self, duration: float = 3.5) -> None:
        """
        Muestra una pantalla de carga con el icono de la aplicación y texto animado.
        
        Args:
            duration: Duración de la pantalla de carga en segundos (por defecto 3.5)
        """
        # Cargar el icono para la pantalla de carga
        icon_path = Path(__file__).parent.parent.parent / "assets" / "viboycolor-icon.png"
        icon_surface = None
        if icon_path.exists():
            try:
                icon_surface = pygame.image.load(str(icon_path))
                # Escalar el icono si es necesario (ajustar tamaño según la ventana)
                # Mantener proporción pero limitar tamaño máximo
                max_icon_size = min(self.window_width, self.window_height) // 3
                if icon_surface.get_width() > max_icon_size or icon_surface.get_height() > max_icon_size:
                    # Calcular escala manteniendo proporción
                    scale_factor = max_icon_size / max(icon_surface.get_width(), icon_surface.get_height())
                    new_width = int(icon_surface.get_width() * scale_factor)
                    new_height = int(icon_surface.get_height() * scale_factor)
                    icon_surface = pygame.transform.scale(icon_surface, (new_width, new_height))
            except Exception as e:
                logger.warning(f"No se pudo cargar el icono para la pantalla de carga: {e}")
        
        # Inicializar fuente retro (usar fuente monospace del sistema)
        try:
            # Intentar usar una fuente retro/monospace
            font_size = 24 * self.scale // 3  # Escalar según el factor de escala
            font = pygame.font.Font(pygame.font.get_default_font(), font_size)
            # Si no hay fuente por defecto, usar SysFont monospace
            if font is None:
                font = pygame.font.SysFont("courier", font_size, bold=True)
        except Exception:
            # Fallback a fuente del sistema
            font = pygame.font.SysFont("courier", 24, bold=True)
        
        # Color del texto (blanco o color claro)
        text_color = (255, 255, 255)
        
        # Inicializar reloj para controlar FPS y tiempo
        clock = pygame.time.Clock()
        start_time = pygame.time.get_ticks()
        
        # Bucle de animación
        dot_count = 0
        last_dot_time = 0
        dot_interval = 300  # Cambiar puntos cada 300ms
        
        running = True
        while running:
            current_time = pygame.time.get_ticks()
            elapsed = (current_time - start_time) / 1000.0  # Convertir a segundos
            
            # Salir si ha pasado el tiempo
            if elapsed >= duration:
                break
            
            # Manejar eventos (permitir cerrar durante la carga)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        break
            
            # Actualizar animación de puntos
            if current_time - last_dot_time >= dot_interval:
                dot_count = (dot_count + 1) % 3  # 0, 1, 2 (1, 2, 3 puntos)
                last_dot_time = current_time
            
            # Construir texto con puntos animados (siempre mostrar al menos 1 punto)
            dots = "." * (dot_count + 1)  # 1, 2, o 3 puntos
            loading_text = f"Loading{dots}"
            
            # Limpiar pantalla (fondo negro)
            self.screen.fill((0, 0, 0))
            
            # Dibujar icono centrado
            if icon_surface is not None:
                icon_x = (self.window_width - icon_surface.get_width()) // 2
                icon_y = (self.window_height - icon_surface.get_height()) // 2 - 30
                self.screen.blit(icon_surface, (icon_x, icon_y))
            
            # Renderizar texto "Loading..."
            text_surface = font.render(loading_text, True, text_color)
            text_x = (self.window_width - text_surface.get_width()) // 2
            text_y = self.window_height // 2 + 50
            self.screen.blit(text_surface, (text_x, text_y))
            
            # Actualizar pantalla
            pygame.display.flip()
            
            # Controlar FPS (60 FPS para animación suave)
            clock.tick(60)
        
        # Limpiar pantalla al finalizar
        self.screen.fill((0, 0, 0))
        pygame.display.flip()
    
    def mark_tile_dirty(self, tile_index: int) -> None:
        """
        Marca un tile como "dirty" (sucio) para que se actualice en la caché.
        
        Este método se llama desde la MMU cuando se escribe en VRAM (0x8000-0x97FF).
        Solo los tiles en este rango se cachean (384 tiles = 6KB).
        
        Args:
            tile_index: Índice del tile (0-383) correspondiente a VRAM 0x8000-0x97FF
        """
        if 0 <= tile_index < 384:
            self.tile_dirty[tile_index] = True
            # Marcar bg_buffer como dirty para que se reconstruya en el siguiente frame
            self.bg_buffer_dirty = True
    
    def update_tile_cache(self, palette: list[tuple[int, int, int]]) -> None:
        """
        Actualiza la caché de tiles marcados como "dirty".
        
        Decodifica los tiles sucios desde VRAM y los guarda como superficies pygame
        de 8x8 píxeles. Esto permite usar blits rápidos en lugar de decodificar
        píxel a píxel en cada frame.
        
        Args:
            palette: Paleta de 4 colores RGB para decodificar los tiles
        """
        # Recorrer todos los tiles (0-383)
        for tile_index in range(384):
            if not self.tile_dirty[tile_index]:
                continue  # Tile no ha cambiado, saltar
            
            # Calcular dirección base del tile en VRAM
            # Tiles 0-383 están en 0x8000-0x97FF (6KB)
            tile_addr = VRAM_START + (tile_index * BYTES_PER_TILE)
            
            # Crear superficie de 8x8 píxeles para este tile
            tile_surface = pygame.Surface((TILE_SIZE, TILE_SIZE))
            
            # Decodificar el tile línea por línea
            for line in range(TILE_SIZE):
                # Cada línea ocupa 2 bytes
                byte1_addr = tile_addr + (line * 2)
                byte2_addr = tile_addr + (line * 2) + 1
                
                # Leer bytes de VRAM
                byte1 = self.mmu.read_byte(byte1_addr) & 0xFF
                byte2 = self.mmu.read_byte(byte2_addr) & 0xFF
                
                # Decodificar la línea de 8 píxeles
                pixels = decode_tile_line(byte1, byte2)
                
                # Dibujar cada píxel en la superficie
                for pixel_x, color_index in enumerate(pixels):
                    color = palette[color_index]
                    tile_surface.set_at((pixel_x, line), color)
            
            # Guardar en caché
            self.tile_cache[tile_index] = tile_surface
            
            # Marcar como limpio
            self.tile_dirty[tile_index] = False

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

    def render_frame(self, framebuffer_data: bytearray | None = None) -> None:
        """
        Renderiza un frame completo del Background (fondo) y Window (ventana) de la Game Boy.
        
        Si use_cpp_ppu=True, usa el framebuffer de C++ directamente (Zero-Copy).
        Si use_cpp_ppu=False, calcula tiles desde VRAM (método Python original).
        
        Args:
            framebuffer_data: Opcional. Si se proporciona, usa este bytearray como fuente
                             de datos en lugar de leer desde la PPU. Esto permite pasar
                             un snapshot inmutable del framebuffer (Step 0219).
        
        Este método implementa el renderizado básico del Background y Window según la configuración
        del registro LCDC (LCD Control, 0xFF40):
        - Bit 7: LCD Enable (si es 0, pantalla blanca)
        - Bit 5: Window Enable (si es 1, se dibuja la Window encima del fondo)
        - Bit 4: Tile Data Area (0x8000 unsigned o 0x8800 signed)
        - Bit 3: Tile Map Area (0x9800 o 0x9C00) - para Background
        - Bit 6: Window Tile Map Area (0=0x9800, 1=0x9C00) - para Window
        - Bit 0: BG Display (si es 0, fondo blanco)
        
        La pantalla muestra 160x144 píxeles, que corresponden a 20x18 tiles (cada tile es 8x8).
        El tilemap es de 32x32 tiles (256x256 píxeles), pero solo se renderiza la ventana visible.
        
        La Window es una capa opaca que se dibuja encima del Background pero debajo de los Sprites.
        Se usa para HUDs y menús fijos que no deben moverse con el scroll del fondo.
        
        Fuente: Pan Docs - LCD Control Register, Background Tile Map, Window
        """
        # OPTIMIZACIÓN: Si usamos PPU C++, hacer blit directo del framebuffer
        if self.use_cpp_ppu and self.cpp_ppu is not None:
            try:
                # --- Step 0219: SNAPSHOT INMUTABLE ---
                # Si se proporciona framebuffer_data, usar ese snapshot en lugar de leer desde PPU
                if framebuffer_data is not None:
                    frame_indices = framebuffer_data
                else:
                    # Obtener framebuffer como memoryview (Zero-Copy)
                    # El framebuffer es ahora uint8_t con índices de color (0-3) en formato 1D
                    # Organización: píxel (y, x) está en índice [y * 160 + x]
                    frame_indices = self.cpp_ppu.get_framebuffer()  # 1D array de 23040 elementos
                
                # CRÍTICO: Verificar que el framebuffer sea válido
                if frame_indices is None:
                    logger.error("[Renderer] Framebuffer es None - PPU puede no estar inicializada")
                    return
                
                # Diagnóstico desactivado para producción
                
                # --- Step 0256: DEBUG PALETTE FORCE (HIGH CONTRAST) ---
                # Ignoramos BGP/OBP del hardware para ver los índices crudos de la PPU.
                # Esto nos confirmará si la PPU está dibujando sprites/fondo.
                # 
                # Paleta fija de alto contraste: 0=Blanco, 1=Gris Claro, 2=Gris Oscuro, 3=Negro
                # Formato RGB (Pygame surface)
                debug_palette_map = {
                    0: (255, 255, 255),  # 00: White (Color 0) - Corregido Step 0300
                    1: (136, 192, 112),  # 01: Light Gray (Color 1)
                    2: (52, 104, 86),    # 10: Dark Gray (Color 2)
                    3: (8, 24, 32)       # 11: Black (Color 3)
                }
                
                # Mapeo directo: índice del framebuffer -> color RGB
                # No pasamos por BGP/OBP decodificado, revelamos cualquier píxel con índice > 0
                palette = [
                    debug_palette_map[0],
                    debug_palette_map[1],
                    debug_palette_map[2],
                    debug_palette_map[3]
                ]
                # ----------------------------------------
                
                # Log de paleta desactivado para producción
                
                # --- STEP 0218: IMPLEMENTACIÓN CON DIAGNÓSTICO Y BLIT ESTÁNDAR ---
                # Crear superficie de Pygame para el frame (160x144)
                # Usamos self.surface si existe, sino creamos una nueva
                if not hasattr(self, 'surface'):
                    self.surface = pygame.Surface((GB_WIDTH, GB_HEIGHT))
                
                # Renderizado robusto
                px_array = pygame.PixelArray(self.surface)
                WIDTH, HEIGHT = 160, 144
                
                for y in range(HEIGHT):
                    for x in range(WIDTH):
                        idx = y * WIDTH + x
                        color_index = frame_indices[idx] & 0x03
                        color_rgb = palette[color_index]
                        px_array[x, y] = color_rgb
                
                px_array.close()
                
                # 4. CAMBIO A BLIT ESTÁNDAR (Más seguro que scale con dest)
                # Escalamos a una nueva superficie temporal
                scaled_surface = pygame.transform.scale(self.surface, self.screen.get_size())
                # Copiamos esa superficie a la ventana
                self.screen.blit(scaled_surface, (0, 0))
                # Actualizamos la pantalla
                pygame.display.flip()
                return
            except Exception as e:
                # Fallback a método Python si hay error
                logger.error(f"Error crítico renderizando frame C++: {e}", exc_info=True)
                # Fallback a pantalla roja para indicar error grave
                self.screen.fill((255, 0, 0))
                pygame.display.flip()
                logger.warning(f"Error al usar framebuffer C++: {e}. Usando método Python.")
                self.use_cpp_ppu = False
        
        # Método Python original (calcular tiles desde VRAM)
        # Leer registro LCDC
        lcdc = self.mmu.read_byte(IO_LCDC) & 0xFF
        lcdc_bit7 = (lcdc & 0x80) != 0
        
        # Logs de diagnóstico desactivados para mejorar rendimiento
        
        # --- Step 0256: DEBUG PALETTE FORCE (HIGH CONTRAST) ---
        # Ignoramos BGP/OBP del hardware para ver los índices crudos de la PPU.
        # Esto nos confirmará si la PPU está dibujando sprites/fondo.
        # 
        # Paleta fija de alto contraste: 0=Blanco, 1=Gris Claro, 2=Gris Oscuro, 3=Negro
        # Formato RGB (Pygame surface)
        debug_palette_map = {
            0: (255, 255, 255),  # 00: White (Color 0) - Corregido Step 0300
            1: (136, 192, 112),  # 01: Light Gray (Color 1)
            2: (52, 104, 86),    # 10: Dark Gray (Color 2)
            3: (8, 24, 32)       # 11: Black (Color 3)
        }
        
        # Mapeo directo: índice del framebuffer -> color RGB
        # No pasamos por BGP/OBP decodificado, revelamos cualquier píxel con índice > 0
        palette = [
            debug_palette_map[0],
            debug_palette_map[1],
            debug_palette_map[2],
            debug_palette_map[3]
        ]
        # ----------------------------------------
        
        # Logs de diagnóstico desactivados para mejorar rendimiento
        
        # Comportamiento normal: Si el LCD está apagado (bit 7=0), mostrar pantalla blanca
        # y no renderizar gráficos. Esto es el comportamiento real del hardware.
        if not lcdc_bit7:
            # Pantalla blanca cuando LCD está apagado (comportamiento real del hardware)
            self.buffer.fill((255, 255, 255))
            scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
            self.screen.blit(scaled_buffer, (0, 0))
            pygame.display.flip()
            return
        
        # HACK EDUCATIVO: Ignorar Bit 0 de LCDC (BG Display)
        # En Game Boy Color, el Bit 0 no apaga el fondo, sino que cambia la prioridad
        # de sprites vs fondo. Pokémon Red y otros juegos escriben LCDC=0x80 (bit 7=1, bit 0=0)
        # esperando que el fondo se dibuje (comportamiento CGB), pero nuestro emulador actúa como
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
        
        # CRÍTICO: Asegurar que el fondo se dibuje siempre que LCD esté encendido (Bit 7=1),
        # independientemente del estado del Bit 0. Este hack permite que juegos como Pokémon Red
        # que escriben LCDC=0x80 puedan mostrar gráficos correctamente.
        # No hay ninguna condición que bloquee el renderizado aquí - el código continúa
        # directamente a dibujar el fondo.
        
        # HACK EDUCATIVO: Ignorar Bit 0 de LCDC (BG Display) - mantenido por compatibilidad
        # pero sin logs para mejorar rendimiento
        
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
        
        # Logs de paleta desactivados para mejorar rendimiento
        
        # Leer registros de Scroll (SCX/SCY)
        # SCX (0xFF43): Scroll X - desplazamiento horizontal del fondo
        # SCY (0xFF42): Scroll Y - desplazamiento vertical del fondo
        # Estos registros permiten "mover la cámara" sobre el tilemap de 256x256 píxeles
        scx = self.mmu.read_byte(IO_SCX) & 0xFF
        scy = self.mmu.read_byte(IO_SCY) & 0xFF
        
        # Logs de scroll desactivados para mejorar rendimiento
        
        # Leer registros de Window (WX/WY)
        # WY (0xFF4A): Window Y - Posición Y en pantalla donde empieza la ventana
        # WX (0xFF4B): Window X - Posición X en pantalla + 7 (offset histórico)
        # La Window es una capa opaca que se dibuja encima del fondo pero debajo de los sprites
        wy = self.mmu.read_byte(IO_WY) & 0xFF
        wx = self.mmu.read_byte(IO_WX) & 0xFF
        
        # Leer bits de LCDC para Window
        lcdc_bit5 = (lcdc & 0x20) != 0  # Bit 5: Window Enable
        lcdc_bit6 = (lcdc & 0x40) != 0  # Bit 6: Window Tile Map Area (0=0x9800, 1=0x9C00)
        
        # Determinar tilemap base para Window
        if lcdc_bit6:
            window_map_base = 0x9C00
        else:
            window_map_base = 0x9800
        
        # Logs de window desactivados para mejorar rendimiento
        
        # OPTIMIZACIÓN: Actualizar caché de tiles antes de renderizar
        # Solo decodifica tiles que han cambiado desde el último frame
        self.update_tile_cache(palette)
        
        # FIX: Limpiar framebuffer al principio de cada frame para eliminar artefactos
        # Esto asegura que no queden "fantasmas" de sprites o gráficos anteriores
        self.buffer.fill(palette[0])
        
        # SIMPLIFICACIÓN: Renderizar solo los tiles visibles (20x18 = 360 tiles)
        # En lugar de usar el "Big Blit" que causaba problemas de sincronización,
        # dibujamos directamente los tiles visibles usando la caché (que es rápida).
        # Esto elimina los artefactos de "sprite trailing" y desincronización de fondo.
        #
        # La pantalla muestra 160x144 píxeles = 20x18 tiles (cada tile es 8x8).
        # Aplicamos scroll (SCX/SCY) para determinar qué tiles del tilemap (32x32) dibujar.
        tiles_visible_x = 20  # 160 píxeles / 8 píxeles por tile
        tiles_visible_y = 18   # 144 píxeles / 8 píxeles por tile
        
        # Calcular el tile inicial del tilemap según el scroll
        # SCX/SCY se aplican a nivel de píxel, pero necesitamos saber qué tiles mostrar
        start_tile_x = scx // TILE_SIZE
        start_tile_y = scy // TILE_SIZE
        offset_x = scx % TILE_SIZE  # Offset en píxeles dentro del primer tile
        offset_y = scy % TILE_SIZE  # Offset en píxeles dentro del primer tile
        
        # Renderizar los tiles visibles del fondo
        for screen_tile_y in range(tiles_visible_y + 1):  # +1 para cubrir el offset
            for screen_tile_x in range(tiles_visible_x + 1):  # +1 para cubrir el offset
                # Calcular posición del tile en el tilemap (con wrap-around de 32x32)
                tile_map_x = (start_tile_x + screen_tile_x) % 32
                tile_map_y = (start_tile_y + screen_tile_y) % 32
                
                # Leer Tile ID del tilemap
                map_addr = map_base + (tile_map_y * 32) + tile_map_x
                tile_id = self.mmu.read_byte(map_addr) & 0xFF
                
                # Calcular índice del tile en la caché según el modo de direccionamiento
                if unsigned_addressing:
                    # Modo unsigned: tile_id es 0-255, pero solo cacheamos 0-383 (0x8000-0x97FF)
                    if tile_id < 384:
                        cached_tile_id = tile_id
                    else:
                        # Tile fuera del rango cacheado, decodificar directamente
                        cached_tile_id = None
                        tile_addr = data_base + (tile_id * BYTES_PER_TILE)
                else:
                    # Modo signed: tile_id es -128 a 127, donde 0 está en 0x9000
                    if tile_id >= 128:
                        signed_id = tile_id - 256
                    else:
                        signed_id = tile_id
                    tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
                    # Convertir dirección a índice de caché (0x8000-0x97FF)
                    if VRAM_START <= tile_addr <= 0x97FF:
                        cached_tile_id = (tile_addr - VRAM_START) // BYTES_PER_TILE
                    else:
                        cached_tile_id = None
                
                # Calcular posición en pantalla (aplicar offset de scroll)
                screen_x = (screen_tile_x * TILE_SIZE) - offset_x
                screen_y = (screen_tile_y * TILE_SIZE) - offset_y
                
                # Verificar si el tile está visible en pantalla
                if screen_x < -TILE_SIZE or screen_x >= GB_WIDTH:
                    continue
                if screen_y < -TILE_SIZE or screen_y >= GB_HEIGHT:
                    continue
                
                # Dibujar tile usando caché o decodificar directamente
                if cached_tile_id is not None and cached_tile_id in self.tile_cache:
                    # Blit rápido desde caché
                    self.buffer.blit(self.tile_cache[cached_tile_id], (screen_x, screen_y))
                else:
                    # Tile fuera de caché, decodificar directamente (raro, pero posible)
                    if unsigned_addressing:
                        tile_addr = data_base + (tile_id * BYTES_PER_TILE)
                    else:
                        if tile_id >= 128:
                            signed_id = tile_id - 256
                        else:
                            signed_id = tile_id
                        tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
                    
                    if VRAM_START <= tile_addr <= VRAM_END:
                        # Decodificar tile directamente (fallback)
                        for line in range(TILE_SIZE):
                            byte1_addr = tile_addr + (line * 2)
                            byte2_addr = tile_addr + (line * 2) + 1
                            byte1 = self.mmu.read_byte(byte1_addr) & 0xFF
                            byte2 = self.mmu.read_byte(byte2_addr) & 0xFF
                            pixels = decode_tile_line(byte1, byte2)
                            for pixel_x, color_index in enumerate(pixels):
                                color = palette[color_index]
                                final_x = screen_x + pixel_x
                                final_y = screen_y + line
                                if 0 <= final_x < GB_WIDTH and 0 <= final_y < GB_HEIGHT:
                                    self.buffer.set_at((final_x, final_y), color)
        
        # Renderizar Window encima del fondo (si está habilitada)
        if lcdc_bit5:
            # Renderizar Window tile por tile usando blits
            # La Window se dibuja desde (wx-7, wy) en pantalla
            win_screen_x = wx - 7
            win_screen_y = wy
            
            # Calcular cuántos tiles de Window necesitamos dibujar
            # La Window puede extenderse más allá de la pantalla, así que limitamos
            win_tiles_x = min(32, (GB_WIDTH - max(0, win_screen_x) + TILE_SIZE - 1) // TILE_SIZE)
            win_tiles_y = min(32, (GB_HEIGHT - max(0, win_screen_y) + TILE_SIZE - 1) // TILE_SIZE)
            
            for tile_map_y in range(win_tiles_y):
                for tile_map_x in range(win_tiles_x):
                    # Leer Tile ID del tilemap de Window
                    window_map_addr = window_map_base + (tile_map_y * 32) + tile_map_x
                    tile_id = self.mmu.read_byte(window_map_addr) & 0xFF
                    
                    # Calcular posición en pantalla
                    tile_screen_x = win_screen_x + (tile_map_x * TILE_SIZE)
                    tile_screen_y = win_screen_y + (tile_map_y * TILE_SIZE)
                    
                    # Verificar si el tile está visible en pantalla
                    if tile_screen_x < -TILE_SIZE or tile_screen_x >= GB_WIDTH:
                        continue
                    if tile_screen_y < -TILE_SIZE or tile_screen_y >= GB_HEIGHT:
                        continue
                    
                    # Calcular índice del tile en la caché
                    if unsigned_addressing:
                        if tile_id < 384:
                            cached_tile_id = tile_id
                        else:
                            cached_tile_id = None
                            tile_addr = data_base + (tile_id * BYTES_PER_TILE)
                    else:
                        if tile_id >= 128:
                            signed_id = tile_id - 256
                        else:
                            signed_id = tile_id
                        tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
                        if VRAM_START <= tile_addr <= 0x97FF:
                            cached_tile_id = (tile_addr - VRAM_START) // BYTES_PER_TILE
                        else:
                            cached_tile_id = None
                    
                    # Dibujar tile usando caché o decodificar directamente
                    if cached_tile_id is not None and cached_tile_id in self.tile_cache:
                        # Blit rápido desde caché
                        self.buffer.blit(self.tile_cache[cached_tile_id], (tile_screen_x, tile_screen_y))
                    else:
                        # Tile fuera de caché, decodificar directamente
                        if unsigned_addressing:
                            tile_addr = data_base + (tile_id * BYTES_PER_TILE)
                        else:
                            if tile_id >= 128:
                                signed_id = tile_id - 256
                            else:
                                signed_id = tile_id
                            tile_addr = 0x9000 + (signed_id * BYTES_PER_TILE)
                        
                        if VRAM_START <= tile_addr <= VRAM_END:
                            # Decodificar tile directamente (fallback)
                            for line in range(TILE_SIZE):
                                byte1_addr = tile_addr + (line * 2)
                                byte2_addr = tile_addr + (line * 2) + 1
                                byte1 = self.mmu.read_byte(byte1_addr) & 0xFF
                                byte2 = self.mmu.read_byte(byte2_addr) & 0xFF
                                pixels = decode_tile_line(byte1, byte2)
                                for pixel_x, color_index in enumerate(pixels):
                                    color = palette[color_index]
                                    final_x = tile_screen_x + pixel_x
                                    final_y = tile_screen_y + line
                                    if 0 <= final_x < GB_WIDTH and 0 <= final_y < GB_HEIGHT:
                                        self.buffer.set_at((final_x, final_y), color)
        
        # Renderizar sprites (OBJ) encima del fondo
        # Los sprites se dibujan después del fondo para que aparezcan por encima
        sprites_drawn = self.render_sprites()
        
        # Escalar el framebuffer a la ventana y hacer blit
        # pygame.transform.scale es rápido porque opera sobre una superficie completa
        scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
        self.screen.blit(scaled_buffer, (0, 0))
        
        # Actualizar la pantalla
        pygame.display.flip()
        # Logs de frame desactivados para mejorar rendimiento

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
                return 0
        
        # --- Step 0256: DEBUG PALETTE FORCE (HIGH CONTRAST) ---
        # Ignoramos OBP0/OBP1 del hardware para ver los índices crudos de los sprites.
        # Usamos la misma paleta de debug que el fondo para consistencia visual.
        debug_palette_map = {
            0: (255, 255, 255),  # 00: White (Color 0 - transparente en sprites) - Corregido Step 0300
            1: (136, 192, 112),  # 01: Light Gray (Color 1)
            2: (52, 104, 86),    # 10: Dark Gray (Color 2)
            3: (8, 24, 32)       # 11: Black (Color 3)
        }
        
        # Mapeo directo: índice del sprite -> color RGB
        # No pasamos por OBP0/OBP1 decodificado, revelamos cualquier píxel con índice > 0
        palette0 = [
            debug_palette_map[0],
            debug_palette_map[1],
            debug_palette_map[2],
            debug_palette_map[3]
        ]
        palette1 = [
            debug_palette_map[0],
            debug_palette_map[1],
            debug_palette_map[2],
            debug_palette_map[3]
        ]
        # ----------------------------------------
        
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
        Maneja eventos de Pygame (especialmente pygame.QUIT y teclado para Joypad).
        
        IMPORTANTE: En macOS, pygame.event.pump() es necesario para que la ventana se actualice.
        Este método llama automáticamente a pygame.event.pump() para asegurar que la ventana
        se refresque correctamente en todos los sistemas operativos.
        
        Mapea las teclas de Pygame a los botones del Joypad:
        - Direcciones: Flechas (UP, DOWN, LEFT, RIGHT)
        - Acciones: Z/A (botón A), X/S (botón B), RETURN (Start), RSHIFT (Select)
        
        Returns:
            True si se debe continuar ejecutando, False si se debe cerrar
        """
        if pygame is None:
            return True
        
        # En macOS (y algunos otros sistemas), pygame.event.pump() es necesario
        # para que la ventana se actualice correctamente
        pygame.event.pump()
        
        # Mapeo de teclas a índices de botones del Joypad
        # Direcciones: 0: Derecha, 1: Izquierda, 2: Arriba, 3: Abajo
        # Acciones:    4: A,       5: B,       6: Select, 7: Start
        KEY_MAP = {
            pygame.K_RIGHT: 0,    # Derecha
            pygame.K_LEFT: 1,     # Izquierda
            pygame.K_UP: 2,       # Arriba
            pygame.K_DOWN: 3,     # Abajo
            pygame.K_z: 4,        # A (también pygame.K_a)
            pygame.K_a: 4,        # A (alternativa)
            pygame.K_x: 5,        # B (también pygame.K_s)
            pygame.K_s: 5,        # B (alternativa)
            pygame.K_RSHIFT: 6,   # Select
            pygame.K_RETURN: 7,   # Start
        }
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            # Manejar eventos de teclado para el Joypad
            if self.joypad is not None:
                if event.type == pygame.KEYDOWN:
                    if event.key in KEY_MAP:
                        button_index = KEY_MAP[event.key]
                        self.joypad.press_button(button_index)
                elif event.type == pygame.KEYUP:
                    if event.key in KEY_MAP:
                        button_index = KEY_MAP[event.key]
                        self.joypad.release_button(button_index)
        
        return True

    def quit(self) -> None:
        """Cierra Pygame limpiamente."""
        if pygame is not None:
            pygame.quit()
            logger.info("Renderer cerrado")

