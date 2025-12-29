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
        
        # --- STEP 0307: Cache de Scaling ---
        # Cache para evitar recalcular pygame.transform.scale() si el tamaño no cambia
        self._scaled_surface_cache = None
        self._cache_screen_size = None
        self._cache_source_hash = None  # Hash del contenido del framebuffer
        # ----------------------------------------
        
        # --- FIX STEP 0216: Definición Explícita de Colores ---
        # Game Boy original: 0=Más claro, 3=Más oscuro
        # Paleta estándar de Game Boy (verde/amarillo original)
        # --- FIX STEP 0301: Corrección de Color 0 de Verde a Blanco ---
        # --- FIX STEP 0303: Corrección de Índices 1 y 2 de Verde a Gris ---
        self.COLORS = [
            (255, 255, 255),  # 0: White (Color 0) - Corregido Step 0301
            (170, 170, 170),  # 1: Gris claro (Light Gray) - Corregido Step 0303
            (85, 85, 85),     # 2: Gris oscuro (Dark Gray) - Corregido Step 0303
            (8, 24, 32)       # 3: Negro/Verde oscuro (Black)
        ]
        # Paleta actual mapeada (índice -> RGB)
        # Usar _palette para permitir monitor de cambios
        self._palette = list(self.COLORS)
        
        # Flag para log de depuración (una sola vez)
        self.debug_palette_printed = False
        # ----------------------------------------
        
        # --- STEP 0301: Monitores de Diagnóstico ---
        # Variables estáticas para monitores (persisten entre frames)
        self._palette_trace_count = 0
        self._last_use_cpp_ppu = None
        # ----------------------------------------
        
        # --- STEP 0304: Monitor de Framebuffer ([FRAMEBUFFER-INDEX-TRACE]) ---
        # Flag de activación: Solo activar si las rayas verdes aparecen después de la verificación visual
        # Para activar, cambiar a True después de confirmar que las rayas aparecen
        self._framebuffer_trace_enabled = True  # ACTIVADO: Rayas verdes aparecen después de 2 minutos
        self._framebuffer_trace_count = 0
        # ----------------------------------------
        
        # --- STEP 0305: Monitores de Renderizado Python ---
        # Monitor de paleta en tiempo real ([PALETTE-VERIFY])
        self._palette_verify_count = 0
        # Monitor de PixelArray y scaling ([PIXEL-VERIFY])
        self._pixel_verify_count = 0
        # Monitor de modificaciones de paleta ([PALETTE-MODIFIED])
        self._original_debug_palette = {
            0: (255, 255, 255),
            1: (170, 170, 170),
            2: (85, 85, 85),
            3: (8, 24, 32)
        }
        self._last_palette_checked = None
        # ----------------------------------------
        
        # --- STEP 0306: Monitor de Rendimiento ([PERFORMANCE-TRACE]) ---
        # Flag de activación: Solo activar si se necesita investigar rendimiento
        # Step 0316: DESACTIVADO por defecto para mejorar rendimiento (FPS bajo identificado)
        self._performance_trace_enabled = False  # DESACTIVADO para Step 0316 (optimización FPS)
        self._performance_trace_count = 0
        # Step 0309: Guardar tiempo del frame anterior para calcular tiempo entre frames
        self._last_frame_end_time = None
        # ----------------------------------------
        
        # --- STEP 0308: Verificación de NumPy ---
        # Verificar si NumPy está disponible para renderizado vectorizado
        try:
            import numpy as np
            logger.info(f"[RENDER-OPTIMIZATION] NumPy {np.__version__} disponible - usando renderizado vectorizado")
        except ImportError:
            logger.warning("[RENDER-OPTIMIZATION] NumPy NO disponible - usando fallback PixelArray")
        # ----------------------------------------
        
        logger.info(f"Renderer inicializado: {self.window_width}x{self.window_height} (scale={scale})")
        
        # Mostrar pantalla de carga
        self._show_loading_screen()
    
    @property
    def palette(self):
        """Getter para self.palette (usado por monitores Step 0301)."""
        return self._palette
    
    @palette.setter
    def palette(self, value):
        """Setter para self.palette con monitor de cambios (Step 0301)."""
        old_0 = self._palette[0] if self._palette else None
        self._palette = value
        new_0 = value[0] if value else None
        if old_0 != new_0:
            import traceback
            print(f"[PALETTE-SELF-CHANGE] self.palette[0] cambió: {old_0} -> {new_0}")
            print(f"[PALETTE-SELF-CHANGE] Stack trace:")
            traceback.print_stack(limit=5)

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
        # --- STEP 0308: Monitor de Rendimiento Mejorado ([PERFORMANCE-TRACE]) ---
        import time
        frame_start = None
        snapshot_time = 0.0
        render_time = 0.0
        hash_time = 0.0
        numpy_used = False
        
        if self._performance_trace_enabled:
            frame_start = time.time()
        # ----------------------------------------
        
        # OPTIMIZACIÓN: Si usamos PPU C++, hacer blit directo del framebuffer
        if self.use_cpp_ppu and self.cpp_ppu is not None:
            try:
                # --- STEP 0308: SNAPSHOT INMUTABLE OPTIMIZADO ---
                # Si se proporciona framebuffer_data, usar ese snapshot en lugar de leer desde PPU
                if framebuffer_data is not None:
                    # Ya es un snapshot inmutable (bytearray)
                    frame_indices = framebuffer_data
                    snapshot_time = 0.0  # No hay overhead si ya viene como snapshot
                else:
                    # Obtener framebuffer como memoryview (Zero-Copy)
                    # El framebuffer es ahora uint8_t con índices de color (0-3) en formato 1D
                    # Organización: píxel (y, x) está en índice [y * 160 + x]
                    frame_indices_mv = self.cpp_ppu.get_framebuffer()  # 1D array de 23040 elementos
                    
                    # CRÍTICO: Verificar que el framebuffer sea válido
                    if frame_indices_mv is None:
                        logger.error("[Renderer] Framebuffer es None - PPU puede no estar inicializada")
                        return
                    
                    # Medir tiempo de snapshot para análisis de rendimiento
                    snapshot_start = time.time()
                    
                    # Usar bytearray en lugar de list() para mejor rendimiento
                    # bytearray es más eficiente que list() para datos binarios
                    # CRÍTICO: El memoryview de Cython puede no tener tobytes(), usar bytes() directamente
                    try:
                        frame_indices = bytearray(frame_indices_mv.tobytes())  # Snapshot inmutable optimizado
                    except AttributeError:
                        # Fallback: convertir memoryview a bytes usando bytes() constructor
                        frame_indices = bytearray(bytes(frame_indices_mv))  # Snapshot inmutable optimizado
                    
                    snapshot_time = (time.time() - snapshot_start) * 1000  # en milisegundos
                # ----------------------------------------
                
                # Diagnóstico desactivado para producción
                
                # --- Step 0256: DEBUG PALETTE FORCE (HIGH CONTRAST) ---
                # Ignoramos BGP/OBP del hardware para ver los índices crudos de la PPU.
                # Esto nos confirmará si la PPU está dibujando sprites/fondo.
                # 
                # Paleta fija de alto contraste: 0=Blanco, 1=Gris Claro, 2=Gris Oscuro, 3=Negro
                # Formato RGB (Pygame surface)
                debug_palette_map = {
                    0: (255, 255, 255),  # 00: White (Color 0) - Corregido Step 0300
                    1: (170, 170, 170),  # 01: Light Gray (Color 1) - Corregido Step 0303
                    2: (85, 85, 85),     # 10: Dark Gray (Color 2) - Corregido Step 0303
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
                
                # --- STEP 0332: Diagnóstico de Framebuffer Recibido ---
                # Verificar qué índices recibe el renderizador del framebuffer
                if framebuffer_data is not None and len(framebuffer_data) > 0:
                    if not hasattr(self, '_framebuffer_diagnostic_count'):
                        self._framebuffer_diagnostic_count = 0
                    if self._framebuffer_diagnostic_count < 5:
                        self._framebuffer_diagnostic_count += 1
                        
                        # Contar índices en el framebuffer
                        index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                        for idx in range(min(100, len(framebuffer_data))):  # Primeros 100 píxeles
                            color_idx = framebuffer_data[idx] & 0x03
                            if color_idx in index_counts:
                                index_counts[color_idx] += 1
                        
                        logger.info(f"[Renderer-Framebuffer-Diagnostic] Frame {self._framebuffer_diagnostic_count} | "
                                   f"Index counts (first 100): 0={index_counts[0]} 1={index_counts[1]} "
                                   f"2={index_counts[2]} 3={index_counts[3]}")
                        
                        # Verificar primeros 20 píxeles
                        first_20 = [framebuffer_data[i] & 0x03 for i in range(min(20, len(framebuffer_data)))]
                        logger.info(f"[Renderer-Framebuffer-Diagnostic] First 20 indices: {first_20}")
                        
                        # Verificar que el índice 3 se convierte a negro
                        if index_counts[3] > 0:
                            test_index = 3
                            test_color = palette[test_index]
                            logger.info(f"[Renderer-Framebuffer-Diagnostic] Index 3 -> RGB: {test_color} (should be black: (8, 24, 32))")
                            if test_color != (8, 24, 32):
                                logger.warning(f"[Renderer-Framebuffer-Diagnostic] ⚠️ PROBLEMA: Index 3 no se convierte a negro!")
                # -------------------------------------------
                
                # --- STEP 0305: Monitor de Paleta en Tiempo Real ([PALETTE-VERIFY]) ---
                if self._palette_verify_count % 1000 == 0 or self._palette_verify_count < 10:
                    if self._palette_verify_count < 100:
                        print(f"[PALETTE-VERIFY] Frame {self._palette_verify_count} | "
                              f"Palette[0]={palette[0]} Palette[1]={palette[1]} "
                              f"Palette[2]={palette[2]} Palette[3]={palette[3]}")
                    self._palette_verify_count += 1
                else:
                    self._palette_verify_count += 1
                # ----------------------------------------
                
                # --- STEP 0305: Verificación de Modificaciones de Paleta ([PALETTE-MODIFIED]) ---
                if self._last_palette_checked is not None:
                    if self._last_palette_checked != debug_palette_map:
                        print(f"[PALETTE-MODIFIED] Paleta modificada detectada!")
                        print(f"  Original: {self._original_debug_palette}")
                        print(f"  Actual: {debug_palette_map}")
                        import traceback
                        traceback.print_stack(limit=10)
                self._last_palette_checked = dict(debug_palette_map)  # Copia para comparación
                # ----------------------------------------
                
                # --- STEP 0301: Monitor de Uso de Paleta ([PALETTE-USE-TRACE]) ---
                if self._palette_trace_count < 100 or (self._palette_trace_count % 1000 == 0):
                    use_cpp = self.use_cpp_ppu
                    palette_0_debug = palette[0]  # Paleta debug local
                    palette_0_self = self._palette[0]  # self.palette
                    print(f"[PALETTE-USE-TRACE] Frame {self._palette_trace_count} | use_cpp_ppu={use_cpp} | debug_palette[0]={palette_0_debug} | self.palette[0]={palette_0_self}")
                self._palette_trace_count += 1
                # ----------------------------------------
                
                # --- STEP 0304: Monitor de Framebuffer ([FRAMEBUFFER-INDEX-TRACE]) ---
                # Rastrear qué índices tiene el framebuffer en cada frame para detectar cuándo cambia
                # de tener solo índices 0 a tener índices 1 o 2.
                # Solo activar si las rayas verdes aparecen después de la verificación visual extendida.
                if self._framebuffer_trace_enabled and frame_indices is not None:
                    # Contar índices en el framebuffer
                    index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                    for idx in range(len(frame_indices)):
                        color_idx = frame_indices[idx] & 0x03
                        if color_idx in index_counts:
                            index_counts[color_idx] += 1
                    
                    # Detectar si hay valores 1 o 2 (no solo 0)
                    has_non_zero = index_counts[1] > 0 or index_counts[2] > 0 or index_counts[3] > 0
                    
                    # Rastrear solo cuando hay cambio o cada 1000 frames
                    if has_non_zero or self._framebuffer_trace_count % 1000 == 0:
                        if self._framebuffer_trace_count < 100:  # Limitar a 100 registros
                            print(f"[FRAMEBUFFER-INDEX-TRACE] Frame {self._framebuffer_trace_count} | "
                                  f"Index counts: 0={index_counts[0]} 1={index_counts[1]} "
                                  f"2={index_counts[2]} 3={index_counts[3]} | "
                                  f"Has non-zero: {has_non_zero}")
                        self._framebuffer_trace_count += 1
                    else:
                        self._framebuffer_trace_count += 1
                # ----------------------------------------
                
                # --- STEP 0301: Monitor de Cambios en use_cpp_ppu ([CPP-PPU-TOGGLE]) ---
                if self._last_use_cpp_ppu is None:
                    self._last_use_cpp_ppu = self.use_cpp_ppu
                elif self._last_use_cpp_ppu != self.use_cpp_ppu:
                    print(f"[CPP-PPU-TOGGLE] use_cpp_ppu cambió: {self._last_use_cpp_ppu} -> {self.use_cpp_ppu}")
                    self._last_use_cpp_ppu = self.use_cpp_ppu
                # ----------------------------------------
                
                # Log de paleta desactivado para producción
                
                # --- STEP 0307: RENDERIZADO OPTIMIZADO ---
                # Crear superficie de Pygame para el frame (160x144)
                # Usamos self.surface si existe, sino creamos una nueva
                if not hasattr(self, 'surface'):
                    self.surface = pygame.Surface((GB_WIDTH, GB_HEIGHT))
                
                WIDTH, HEIGHT = 160, 144
                
                # --- STEP 0332: Verificación de Aplicación de Paleta ---
                # Verificar que la paleta se aplica correctamente al dibujar píxeles
                if not hasattr(self, '_palette_apply_check_count'):
                    self._palette_apply_check_count = 0
                if self._palette_apply_check_count < 5:
                    self._palette_apply_check_count += 1
                    
                    # Verificar algunos píxeles específicos
                    test_pixels = [
                        (0, 0),    # Esquina superior izquierda
                        (80, 72),  # Centro de pantalla
                        (159, 143) # Esquina inferior derecha
                    ]
                    
                    for x, y in test_pixels:
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            color_index = frame_indices[idx] & 0x03
                            rgb_color = palette[color_index]
                            logger.info(f"[Renderer-Palette-Apply] Pixel ({x}, {y}): index={color_index} -> RGB={rgb_color}")
                            
                            if color_index == 3 and rgb_color != (8, 24, 32):
                                logger.warning(f"[Renderer-Palette-Apply] ⚠️ PROBLEMA: Index 3 no se convierte a negro en ({x}, {y})!")
                # -------------------------------------------
                
                # --- STEP 0305: Verificación de PixelArray y Scaling ([PIXEL-VERIFY]) ---
                if self._pixel_verify_count < 10:
                    # Verificar píxel central antes de PixelArray
                    center_idx = (72 * 160 + 80)  # Línea 72, columna 80
                    center_color_idx = frame_indices[center_idx] & 0x03
                    center_color_rgb = palette[center_color_idx]
                    print(f"[PIXEL-VERIFY] Frame {self._pixel_verify_count} | "
                          f"Center pixel: idx={center_idx} color_idx={center_color_idx} "
                          f"rgb={center_color_rgb}")
                    self._pixel_verify_count += 1
                else:
                    self._pixel_verify_count += 1
                # ----------------------------------------
                
                # --- STEP 0308: RENDERIZADO VECTORIZADO CON MEDICIÓN ---
                # Medir tiempo de renderizado NumPy vs fallback
                render_start = time.time()
                numpy_used = False
                
                # Intentar usar numpy para renderizado vectorizado (más rápido)
                try:
                    import numpy as np
                    import pygame.surfarray as surfarray
                    numpy_used = True
                    
                    # Crear array numpy con índices (144x160) - formato (y, x)
                    # frame_indices está en formato [y * 160 + x], así que reshape es (144, 160)
                    indices_array = np.array(frame_indices, dtype=np.uint8).reshape(144, 160)
                    
                    # Crear array RGB (144x160x3) - formato (height, width, channels)
                    rgb_array = np.zeros((144, 160, 3), dtype=np.uint8)
                    
                    # Mapear índices a RGB usando operaciones vectorizadas
                    for i, rgb in enumerate(palette):
                        mask = indices_array == i
                        rgb_array[mask] = rgb
                    
                    # Blit directo usando surfarray - necesita formato (width, height, channels)
                    # surfarray espera (width, height, channels), así que necesitamos (160, 144, 3)
                    rgb_array_swapped = np.swapaxes(rgb_array, 0, 1)  # (160, 144, 3)
                    surfarray.blit_array(self.surface, rgb_array_swapped)
                    
                except ImportError:
                    # Fallback: PixelArray optimizado (más rápido que bucle simple)
                    # Crear PixelArray una sola vez y reutilizarlo
                    if not hasattr(self, '_px_array_surface'):
                        self._px_array_surface = pygame.Surface((160, 144))
                    
                    px_array = pygame.PixelArray(self._px_array_surface)
                    
                    # Renderizar en chunks para mejor rendimiento
                    for y in range(HEIGHT):
                        row_start = y * WIDTH
                        row_indices = frame_indices[row_start:row_start + WIDTH]
                        for x in range(WIDTH):
                            color_index = row_indices[x] & 0x03
                            px_array[x, y] = palette[color_index]
                    
                    px_array.close()
                    self.surface = self._px_array_surface
                
                render_time = (time.time() - render_start) * 1000  # en milisegundos
                # ----------------------------------------
                
                # --- STEP 0308: CACHE DE SCALING OPTIMIZADO ---
                # Medir tiempo de hash para análisis de rendimiento
                hash_start = time.time()
                
                # Cachear la superficie escalada para evitar recalcular cuando el tamaño no cambia
                current_screen_size = self.screen.get_size()
                
                # OPTIMIZACIÓN: Deshabilitar hash temporalmente para medir impacto
                # Solo reescalar si el tamaño cambió (sin validación de contenido)
                source_hash = None  # Deshabilitado temporalmente para Step 0308
                # source_hash = hash(tuple(frame_indices[:100]))  # Comentado para medir overhead
                
                hash_time = (time.time() - hash_start) * 1000  # en milisegundos
                
                # Solo reescalar si el tamaño cambió (hash deshabilitado temporalmente)
                if (self._cache_screen_size != current_screen_size or 
                    self._scaled_surface_cache is None):
                    
                    self._scaled_surface_cache = pygame.transform.scale(self.surface, current_screen_size)
                    self._cache_screen_size = current_screen_size
                    self._cache_source_hash = source_hash
                
                # Usar superficie cacheada
                self.screen.blit(self._scaled_surface_cache, (0, 0))
                # Actualizamos la pantalla
                pygame.display.flip()
                # ----------------------------------------
                
                # --- STEP 0309: Monitor de Rendimiento Corregido ([PERFORMANCE-TRACE]) ---
                # Step 0309: Calcular tiempo entre frames (incluye tiempo de espera del clock.tick())
                if self._performance_trace_enabled and frame_start is not None:
                    frame_end = time.time()
                    frame_time = (frame_end - frame_start) * 1000  # Tiempo de renderizado en ms
                    
                    # Step 0309: Calcular tiempo entre frames consecutivos (incluye clock.tick())
                    time_between_frames = None
                    fps_limited = None
                    if self._last_frame_end_time is not None:
                        time_between_frames = (frame_end - self._last_frame_end_time) * 1000  # ms
                        fps_limited = 1000.0 / time_between_frames if time_between_frames > 0 else 0
                    self._last_frame_end_time = frame_end
                    
                    if self._performance_trace_count % 10 == 0:  # Cada 10 frames (más datos)
                        fps_render = 1000.0 / frame_time if frame_time > 0 else 0
                        # Step 0309: Reportar FPS limitado (tiempo entre frames) si está disponible
                        if fps_limited is not None:
                            # Incluir tiempos por componente y FPS limitado
                            print(f"[PERFORMANCE-TRACE] Frame {self._performance_trace_count} | "
                                  f"Frame time (render): {frame_time:.2f}ms | FPS (render): {fps_render:.1f} | "
                                  f"Time between frames: {time_between_frames:.2f}ms | FPS (limited): {fps_limited:.1f} | "
                                  f"Snapshot: {snapshot_time:.3f}ms | "
                                  f"Render: {render_time:.2f}ms ({'NumPy' if numpy_used else 'PixelArray'}) | "
                                  f"Hash: {hash_time:.3f}ms")
                        else:
                            # Primer frame: no hay tiempo entre frames todavía
                            print(f"[PERFORMANCE-TRACE] Frame {self._performance_trace_count} | "
                                  f"Frame time (render): {frame_time:.2f}ms | FPS (render): {fps_render:.1f} | "
                                  f"Snapshot: {snapshot_time:.3f}ms | "
                                  f"Render: {render_time:.2f}ms ({'NumPy' if numpy_used else 'PixelArray'}) | "
                                  f"Hash: {hash_time:.3f}ms")
                    self._performance_trace_count += 1
                # ----------------------------------------
                
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
            1: (170, 170, 170),  # 01: Light Gray (Color 1) - Corregido Step 0303
            2: (85, 85, 85),     # 10: Dark Gray (Color 2) - Corregido Step 0303
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
        
        # --- STEP 0301: Monitor de Uso de Paleta ([PALETTE-USE-TRACE]) ---
        if self._palette_trace_count < 100 or (self._palette_trace_count % 1000 == 0):
            use_cpp = self.use_cpp_ppu
            palette_0_debug = palette[0]  # Paleta debug local
            palette_0_self = self._palette[0]  # self.palette
            print(f"[PALETTE-USE-TRACE] Frame {self._palette_trace_count} | use_cpp_ppu={use_cpp} | debug_palette[0]={palette_0_debug} | self.palette[0]={palette_0_self}")
        self._palette_trace_count += 1
        # ----------------------------------------
        
        # --- STEP 0301: Monitor de Cambios en use_cpp_ppu ([CPP-PPU-TOGGLE]) ---
        if self._last_use_cpp_ppu is None:
            self._last_use_cpp_ppu = self.use_cpp_ppu
        elif self._last_use_cpp_ppu != self.use_cpp_ppu:
            print(f"[CPP-PPU-TOGGLE] use_cpp_ppu cambió: {self._last_use_cpp_ppu} -> {self.use_cpp_ppu}")
            self._last_use_cpp_ppu = self.use_cpp_ppu
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
        
        # --- STEP 0309: Monitor de Rendimiento Corregido ([PERFORMANCE-TRACE]) ---
        if self._performance_trace_enabled and frame_start is not None:
            frame_end = time.time()
            frame_time = (frame_end - frame_start) * 1000  # Tiempo de renderizado en ms
            
            # Step 0309: Calcular tiempo entre frames consecutivos (incluye clock.tick())
            time_between_frames = None
            fps_limited = None
            if self._last_frame_end_time is not None:
                time_between_frames = (frame_end - self._last_frame_end_time) * 1000  # ms
                fps_limited = 1000.0 / time_between_frames if time_between_frames > 0 else 0
            self._last_frame_end_time = frame_end
            
            if self._performance_trace_count % 10 == 0:  # Cada 10 frames (más datos)
                fps_render = 1000.0 / frame_time if frame_time > 0 else 0
                # Step 0309: Reportar FPS limitado si está disponible
                if fps_limited is not None:
                    print(f"[PERFORMANCE-TRACE] Frame {self._performance_trace_count} | "
                          f"Frame time (render): {frame_time:.2f}ms | FPS (render): {fps_render:.1f} | "
                          f"Time between frames: {time_between_frames:.2f}ms | FPS (limited): {fps_limited:.1f} | "
                          f"Snapshot: {snapshot_time:.3f}ms | "
                          f"Render: {render_time:.2f}ms ({'NumPy' if numpy_used else 'PixelArray'}) | "
                          f"Hash: {hash_time:.3f}ms")
                else:
                    print(f"[PERFORMANCE-TRACE] Frame {self._performance_trace_count} | "
                          f"Frame time (render): {frame_time:.2f}ms | FPS (render): {fps_render:.1f} | "
                          f"Snapshot: {snapshot_time:.3f}ms | "
                          f"Render: {render_time:.2f}ms ({'NumPy' if numpy_used else 'PixelArray'}) | "
                          f"Hash: {hash_time:.3f}ms")
            self._performance_trace_count += 1
        # ----------------------------------------
        
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
            1: (170, 170, 170),  # 01: Light Gray (Color 1) - Corregido Step 0303
            2: (85, 85, 85),     # 10: Dark Gray (Color 2) - Corregido Step 0303
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

