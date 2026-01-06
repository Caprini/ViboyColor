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

# --- Step 0346: Verificación y Configuración del Logger ---
# Verificar que el logger está configurado correctamente
if logger.level == logging.NOTSET:
    # Si el logger no tiene nivel configurado, configurarlo explícitamente
    logger.setLevel(logging.INFO)

# Verificar que el logger tiene handlers
if not logger.handlers:
    # Si no tiene handlers, agregar uno básico
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Loggear que el logger está configurado
logger.info(f"[Renderer-Logger-Config] Logger configurado: level={logger.level}, handlers={len(logger.handlers)}")
print(f"[Renderer-Logger-Config] Logger configurado: level={logger.level}, handlers={len(logger.handlers)}")
# -------------------------------------------

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
        
        # --- Step 0446: Usar pygame.SCALED para escalado automático (más rápido que transform.scale) ---
        # pygame.SCALED requiere Pygame 2.0+, hacer fallback si no está disponible
        try:
            # Verificar si SCALED está disponible (Pygame 2.0+)
            if hasattr(pygame, 'SCALED'):
                # Usar SCALED: SDL escala automáticamente (mucho más rápido que transform.scale manual)
                self.screen = pygame.display.set_mode((GB_WIDTH, GB_HEIGHT), pygame.SCALED | pygame.RESIZABLE)
                self._use_scaled = True
            else:
                # Fallback para Pygame < 2.0
                self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
                self._use_scaled = False
        except Exception as e:
            # Si SCALED falla, usar método tradicional
            logger.warning(f"[Renderer-Init] pygame.SCALED no disponible, usando escalado manual: {e}")
            self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
            self._use_scaled = False
        pygame.display.set_caption("ViboyColor")
        
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
        # --- Step 0461: Gate framebuffer trace con kill-switch ---
        import os
        self._framebuffer_trace_enabled = os.environ.get('VIBOY_FRAMEBUFFER_TRACE', '0') == '1'
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

    def _calculate_unique_rgb_count_surface(self, surface: pygame.Surface, grid_size: int = 16) -> dict:
        """
        Calcula unique_rgb_count muestreando surface con grid (Step 0454).
        
        Args:
            surface: Surface de Pygame (160x144)
            grid_size: Tamaño del grid (16x16 = 256 muestras)
        
        Returns:
            Dict con unique_rgb_count, dominant_ratio
        """
        unique_colors = set()
        color_freq = {}
        
        width, height = surface.get_size()
        grid_step_x = max(1, width // grid_size)
        grid_step_y = max(1, height // grid_size)
        
        for grid_y in range(grid_size):
            for grid_x in range(grid_size):
                x = min(grid_x * grid_step_x, width - 1)
                y = min(grid_y * grid_step_y, height - 1)
                
                rgb = surface.get_at((x, y))[:3]  # (R, G, B)
                unique_colors.add(rgb)
                color_freq[rgb] = color_freq.get(rgb, 0) + 1
        
        max_freq = max(color_freq.values()) if color_freq else 0
        total_samples = grid_size * grid_size
        dominant_ratio = max_freq / total_samples if total_samples > 0 else 1.0
        
        return {
            'unique_rgb_count': len(unique_colors),
            'dominant_ratio': dominant_ratio
        }
    
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
            
            # Manejar eventos (permitir cerrar durante la carga y redimensionar)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    break
                elif event.type == pygame.VIDEORESIZE:
                    self.window_width = event.w
                    self.window_height = event.h
                    # Actualizar el tamaño de la superficie de la ventana
                    self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
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

    def render_frame(self, framebuffer_data: bytearray | None = None, rgb_view = None, metrics: dict | None = None) -> None:
        """
        Renderiza un frame completo del Background (fondo) y Window (ventana) de la Game Boy.
        
        Si use_cpp_ppu=True, usa el framebuffer de C++ directamente (Zero-Copy).
        Si use_cpp_ppu=False, calcula tiles desde VRAM (método Python original).
        
        Args:
            framebuffer_data: Opcional. Si se proporciona, usa este bytearray como fuente
                             de datos de índices de color (DMG mode). Esto permite pasar
                             un snapshot inmutable del framebuffer (Step 0219).
            rgb_view: Opcional (Step 0406). Si se proporciona, usa este memoryview RGB888
                     directamente (CGB mode). Tamaño esperado: 69120 bytes (160×144×3).
            metrics: Opcional (Step 0448). Diccionario con métricas del core:
                    {'pc': int, 'vram_nonzero': int, 'lcdc': int, 'bgp': int, 'ly': int}
        
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
        
        # --- Step 0445: Path Identification ---
        if not hasattr(self, '_path_log_count'):
            self._path_log_count = 0
            self._path_log_frames = []
        
        # Log primeros 5 frames y luego cada 120 frames
        should_log = (self._path_log_count < 5) or (self._path_log_count % 120 == 0)
        
        if should_log:
            import time
            import hashlib
            frame_start_ms = time.time() * 1000
            
            # Identificar path
            render_path = "unknown"
            buffer_len = 0
            buffer_shape = "unknown"
            nonwhite_sample = 0
            frame_hash_sample = "none"
            
            # --- Step 0448: Obtener métricas del core (si están disponibles) ---
            pc = metrics.get('pc', 0) if metrics else 0
            vram_nonzero = metrics.get('vram_nonzero', 0) if metrics else 0
            lcdc = metrics.get('lcdc', 0) if metrics else 0
            bgp = metrics.get('bgp', 0) if metrics else 0
            ly = metrics.get('ly', 0) if metrics else 0
            
            if rgb_view is not None:
                render_path = "cpp_rgb_view"
                buffer_len = len(rgb_view)
                buffer_shape = "rgb_view"
                # --- Step 0448: Muestreo serio grid 16×16 = 256 puntos ---
                try:
                    import numpy as np
                    rgb_array = np.frombuffer(rgb_view, dtype=np.uint8)
                    if len(rgb_array) == 69120:
                        rgb_array = rgb_array.reshape((GB_HEIGHT, GB_WIDTH, 3))
                        
                        # Grid 16×16 = 256 puntos (no 3 píxeles)
                        nonwhite_count = 0
                        sample_count = 0
                        for y in range(0, GB_HEIGHT, GB_HEIGHT // 16):  # 16 filas
                            for x in range(0, GB_WIDTH, GB_WIDTH // 16):  # 16 columnas
                                if y < GB_HEIGHT and x < GB_WIDTH:
                                    r = rgb_array[y, x, 0]
                                    g = rgb_array[y, x, 1]
                                    b = rgb_array[y, x, 2]
                                    if r < 200 or g < 200 or b < 200:
                                        nonwhite_count += 1
                                    sample_count += 1
                        
                        # Estimación: multiplicar por densidad (69120 / sample_count)
                        nonwhite_sample = int((nonwhite_count / sample_count) * (GB_WIDTH * GB_HEIGHT)) if sample_count > 0 else 0
                        
                        # Hash de muestra (primeros 1000 bytes)
                        frame_hash_sample = hashlib.md5(rgb_view[:min(1000, len(rgb_view))]).hexdigest()[:8]
                except:
                    pass
            elif framebuffer_data is not None:
                render_path = "cpp_framebuffer_data"
                buffer_len = len(framebuffer_data)
                buffer_shape = f"framebuffer_{buffer_len}"
            else:
                render_path = "legacy_fallback"
                buffer_len = 0
                buffer_shape = "legacy"
            
            frame_end_ms = time.time() * 1000
            frame_time_ms = frame_end_ms - frame_start_ms
            
            log_entry = {
                'frame': self._path_log_count,
                'path': render_path,
                'buffer_len': buffer_len,
                'buffer_shape': buffer_shape,
                'nonwhite_sample': nonwhite_sample,
                'frame_hash': frame_hash_sample,
                'frame_time_ms': frame_time_ms,
                'fps': 1000.0 / frame_time_ms if frame_time_ms > 0 else 0
            }
            self._path_log_frames.append(log_entry)
            
            # --- Step 0448: Log mejorado con métricas del core ---
            print(f"[UI-PATH] F{self._path_log_count} | Path={render_path} | "
                  f"PC={pc:04X} | LCDC={lcdc:02X} | BGP={bgp:02X} | LY={ly:02X} | "
                  f"VRAMnz={vram_nonzero} | NonWhite={nonwhite_sample} | "
                  f"Hash={frame_hash_sample} | wall={frame_time_ms:.1f}ms")
        
        self._path_log_count += 1
        # -------------------------------------------
        
        # --- Step 0408: CGB RGB Pipeline (CORRECCIÓN) ---
        # --- Step 0445: Verificación de formato exacto y eliminación de copias ---
        # --- Step 0446: Profiling por etapas + Fixes de rendimiento ---
        # Si rgb_view está disponible, renderizar directamente desde RGB (modo CGB)
        if rgb_view is not None:
            try:
                import numpy as np
                import time
                import os
                
                # --- Step 0446: Flag de debug (no asserts permanentes en hot path) ---
                VIBOY_DEBUG_UI = os.environ.get('VIBOY_DEBUG_UI', '0') == '1'
                
                # --- Step 0448: Profiling por etapas (solo si FPS < 30 o en frames loggeados) ---
                # Calcular si debemos hacer profiling (solo si FPS bajo o en frames loggeados)
                should_profile = should_log or (hasattr(self, '_last_fps') and self._last_fps < 30)
                
                # --- Step 0448: Tiempo de inicio del frame completo (wall-clock) ---
                if should_profile:
                    frame_wall_start = time.time() * 1000
                
                # Convertir memoryview RGB888 (69120 bytes) a array numpy
                # C++ genera el buffer como: fb_index = y * SCREEN_WIDTH + x
                # Formato: [R0,G0,B0, R1,G1,B1, ...] row-major (fila por fila)
                
                # Etapa 1: frombuffer/reshape/swap (preparación array)
                if should_profile:
                    stage_start = time.time() * 1000
                
                rgb_array = np.frombuffer(rgb_view, dtype=np.uint8)
                
                # --- Step 0446: Checks detrás de flag (no asserts permanentes) ---
                if should_log or VIBOY_DEBUG_UI:
                    if rgb_array.flags['OWNDATA']:
                        logger.warning("[UI-DEBUG] np.frombuffer creó copia (debería ser vista)")
                
                # Verificar tamaño
                if len(rgb_array) != 69120:
                    logger.warning(f"[Renderer-RGB-CGB] RGB buffer tamaño incorrecto: {len(rgb_array)} (esperado 69120)")
                    return
                
                # CORRECCIÓN Step 0408: Reshape directamente a (144, 160, 3)
                # El buffer C++ está en orden row-major: fila 0 completa, fila 1 completa, etc.
                # Necesitamos (height=144, width=160, channels=3)
                rgb_array = rgb_array.reshape((GB_HEIGHT, GB_WIDTH, 3))
                
                # --- Step 0446: Checks detrás de flag (no asserts permanentes) ---
                if should_log or VIBOY_DEBUG_UI:
                    if rgb_array.flags['OWNDATA']:
                        logger.warning("[UI-DEBUG] reshape creó copia (debería ser vista)")
                    if rgb_array.shape != (GB_HEIGHT, GB_WIDTH, 3):
                        logger.warning(f"[UI-DEBUG] Shape incorrecto: {rgb_array.shape}")
                
                # --- Step 0414: Verificación RGB real (CGB) ---
                # Chequear si el buffer contiene datos no-blancos
                # Límite: máximo 10 logs para evitar saturación
                if not hasattr(self, '_rgb_check_count'):
                    self._rgb_check_count = 0
                
                if self._rgb_check_count < 10:
                    # Muestra de píxeles: verificar algunos píxeles distribuidos
                    sample_positions = [
                        (72, 80),   # Centro
                        (10, 10),   # Esquina superior izquierda
                        (133, 149), # Esquina inferior derecha
                        (50, 50),   # Centro-superior
                        (100, 100)  # Centro-inferior
                    ]
                    
                    non_white_found = False
                    sample_info = []
                    for y, x in sample_positions:
                        if y < GB_HEIGHT and x < GB_WIDTH:
                            r, g, b = rgb_array[y, x]
                            # Considerar blanco si R,G,B están cerca de máximo (>240)
                            is_white = (r > 240 and g > 240 and b > 240)
                            if not is_white:
                                non_white_found = True
                            sample_info.append(f"({y},{x})=RGB({r},{g},{b})")
                    
                    print(f"[CGB-RGB-CHECK] Frame check #{self._rgb_check_count + 1} | "
                          f"Non-white pixels: {'YES' if non_white_found else 'NO'} | "
                          f"Samples: {' | '.join(sample_info[:3])}")  # Mostrar solo 3 primeros
                    self._rgb_check_count += 1
                # -------------------------------------------
                
                # --- Step 0446: Verificar contiguidad ANTES de swapaxes ---
                # swapaxes puede requerir contiguidad, pero solo copiar si es necesario
                if not rgb_array.flags['C_CONTIGUOUS']:
                    rgb_array = np.ascontiguousarray(rgb_array)  # Esto SÍ copia si no es contiguo
                
                # --- Step 0446: Intentar evitar swapaxes si es posible ---
                # pygame.surfarray.blit_array() espera (width, height, channels) = (160, 144, 3)
                # Necesitamos swapaxes(0, 1) para intercambiar height↔width
                rgb_array_swapped = np.swapaxes(rgb_array, 0, 1)  # (160, 144, 3)
                
                # --- Step 0446: Check detrás de flag (no assert permanente) ---
                if should_log or VIBOY_DEBUG_UI:
                    if rgb_array_swapped.shape != (GB_WIDTH, GB_HEIGHT, 3):
                        logger.warning(f"[UI-DEBUG] Shape después de swapaxes incorrecto: {rgb_array_swapped.shape}")
                
                if should_profile:
                    frombuffer_ms = (time.time() * 1000) - stage_start
                
                # --- Step 0448: Verificación nonwhite antes del blit (ya calculado en logging) ---
                # Nonwhite se calcula arriba con grid 16×16, reutilizamos nonwhite_sample
                
                # Verificación acotada (máx 10 frames) de 3 píxeles para debug
                if not hasattr(self, '_rgb_verify_count'):
                    self._rgb_verify_count = 0
                
                self._rgb_verify_count += 1
                if self._rgb_verify_count <= 10:
                    # Verificar píxeles (0,0), (80,72), (159,143)
                    p1 = rgb_array_swapped[0, 0]  # Top-left
                    p2 = rgb_array_swapped[80, 72]  # Center
                    p3 = rgb_array_swapped[159, 143]  # Bottom-right
                    logger.info(f"[Renderer-RGB-CGB-Verify] Frame {self._rgb_verify_count} | "
                               f"Pixel(0,0)={tuple(p1)} | Pixel(80,72)={tuple(p2)} | Pixel(159,143)={tuple(p3)}")
                
                # Crear superficie base si no existe (160x144)
                if not hasattr(self, 'surface'):
                    self.surface = pygame.Surface((GB_WIDTH, GB_HEIGHT))
                
                # Etapa 2: blit_array
                if should_profile:
                    stage_start = time.time() * 1000
                
                pygame.surfarray.blit_array(self.surface, rgb_array_swapped)
                
                if should_profile:
                    blit_ms = (time.time() * 1000) - stage_start
                
                # --- Step 0448: Verificación nonwhite después del blit con muestreo decente (64 puntos) ---
                # --- Step 0454: Métricas robustas después del blit ---
                if should_log or (hasattr(self, '_last_fps') and self._last_fps < 30):
                    try:
                        # Muestreo decente: grid 8×8 = 64 puntos
                        nonwhite_after = 0
                        sample_positions = []
                        
                        for y_step in range(0, GB_HEIGHT, GB_HEIGHT // 8):  # 8 filas
                            for x_step in range(0, GB_WIDTH, GB_WIDTH // 8):  # 8 columnas
                                x = min(x_step, GB_WIDTH - 1)
                                y = min(y_step, GB_HEIGHT - 1)
                                sample_positions.append((x, y))
                        
                        for x, y in sample_positions:
                            pixel = self.surface.get_at((x, y))
                            r, g, b = pixel[0], pixel[1], pixel[2]
                            if r < 200 or g < 200 or b < 200:
                                nonwhite_after += 1
                        
                        # Estimación total (similar al cálculo de nonwhite_before)
                        nonwhite_after_total = int((nonwhite_after / len(sample_positions)) * (GB_WIDTH * GB_HEIGHT))
                        
                        print(f"[UI-DEBUG] Nonwhite antes del blit: {nonwhite_sample} (grid 16×16) | "
                              f"después del blit: {nonwhite_after_total} (grid 8×8, {nonwhite_after}/{len(sample_positions)} puntos)")
                        
                        # Detectar pérdida significativa
                        if nonwhite_sample > 1000 and nonwhite_after_total < 100:
                            logger.warning(f"[UI-DEBUG] ⚠️ Pérdida significativa de nonwhite: {nonwhite_sample} → {nonwhite_after_total}")
                        
                        # Step 0454: Calcular métricas robustas después del blit
                        metrics_after = self._calculate_unique_rgb_count_surface(self.surface, grid_size=16)
                        
                        print(f"[UI-ROBUST-METRICS] Frame {self._path_log_count} | "
                              f"unique_rgb_after_blit={metrics_after['unique_rgb_count']} | "
                              f"dominant_ratio={metrics_after['dominant_ratio']:.3f}")
                    except Exception as e:
                        logger.error(f"[UI-DEBUG] Error en verificación post-blit: {e}")
                
                # Etapa 3: escalado y blit a pantalla
                if should_profile:
                    stage_start = time.time() * 1000
                
                # --- Step 0446: Usar pygame.SCALED (escalado automático por SDL) ---
                # Si usamos SCALED, no necesitamos escalado manual
                if hasattr(self, '_use_scaled') and self._use_scaled:
                    # Blit directo a screen (SDL escala automáticamente)
                    self.screen.blit(self.surface, (0, 0))
                else:
                    # Fallback: escalado manual (para Pygame < 2.0)
                    if self.scale != 1:
                        scaled_surface = pygame.transform.scale(
                            self.surface,
                            (self.window_width, self.window_height)
                        )
                        self.screen.blit(scaled_surface, (0, 0))
                    else:
                        self.screen.blit(self.surface, (0, 0))
                
                if should_profile:
                    scale_blit_ms = (time.time() * 1000) - stage_start
                
                # Etapa 4: flip
                if should_profile:
                    stage_start = time.time() * 1000
                
                # --- Step 0489: Capturar FB_PRESENT_SRC antes de flip() ---
                import os
                if os.environ.get('VIBOY_DEBUG_PRESENT_TRACE') == '1' and self.cpp_ppu is not None:
                    try:
                        import zlib
                        # Capturar buffer exacto que se pasa a SDL (self.surface)
                        # self.surface es 160x144 en RGB
                        present_buffer = pygame.surfarray.array3d(self.surface)  # (160, 144, 3)
                        present_buffer_flat = present_buffer.flatten()  # (160*144*3,)
                        present_buffer_bytes = present_buffer_flat.tobytes()
                        
                        # Calcular CRC32 y stats
                        present_crc32 = zlib.crc32(present_buffer_bytes) & 0xFFFFFFFF
                        present_nonwhite = sum(1 for i in range(0, len(present_buffer_bytes), 3) 
                                              if present_buffer_bytes[i] < 240 or 
                                                 present_buffer_bytes[i+1] < 240 or 
                                                 present_buffer_bytes[i+2] < 240)
                        
                        # Obtener formato/pitch de la surface
                        present_fmt = 0  # RGBA8888 codificado como 0
                        present_pitch = 160 * 3  # RGB888
                        present_w = 160
                        present_h = 144
                        
                        # Actualizar stats en PPU
                        self.cpp_ppu.set_present_stats(
                            present_crc32, present_nonwhite,
                            present_fmt, present_pitch,
                            present_w, present_h
                        )
                    except Exception as e:
                        logger.warning(f"[Renderer-Present-Stats] Error capturando present stats: {e}")
                # -------------------------------------------
                
                pygame.display.flip()
                
                if should_profile:
                    flip_ms = (time.time() * 1000) - stage_start
                    
                    # --- Step 0448: Profiling correcto: calcular stages, wall, pacing por separado ---
                    # Tiempo total del frame (wall-clock)
                    frame_wall_end = time.time() * 1000
                    frame_wall_ms = frame_wall_end - frame_wall_start
                    
                    # Suma de etapas (solo trabajo de render)
                    stage_sum_ms = frombuffer_ms + blit_ms + scale_blit_ms + flip_ms
                    
                    # Pacing (tiempo de espera/clocks/tick)
                    pacing_ms = max(0, frame_wall_ms - stage_sum_ms)
                    
                    # Log profiling correcto
                    print(f"[UI-PROFILING] Frame {self._path_log_count} | "
                          f"stages={stage_sum_ms:.1f}ms (frombuf={frombuffer_ms:.2f} blit={blit_ms:.2f} "
                          f"scale={scale_blit_ms:.2f} flip={flip_ms:.2f}) | "
                          f"wall={frame_wall_ms:.1f}ms | pacing={pacing_ms:.1f}ms")
                
                # Guardar FPS para siguiente frame (para decidir si hacer profiling)
                if should_log:
                    self._last_fps = log_entry['fps']
                elif hasattr(self, '_path_log_frames') and len(self._path_log_frames) > 0:
                    self._last_fps = self._path_log_frames[-1]['fps']
                
                if self._rgb_verify_count <= 5:
                    logger.info("[Renderer-RGB-CGB] Frame renderizado correctamente desde RGB888")
                return
            except Exception as e:
                logger.error(f"[Renderer-RGB-CGB] Error en renderizado RGB: {e}")
                import traceback
                traceback.print_exc()
                # Fallback: continuar con renderizado normal
        # -------------------------------------------
        # --- Step 0346: Logs de Diagnóstico al Inicio de render_frame() ---
        # Verificar que render_frame() se ejecuta usando tanto logger como print()
        if not hasattr(self, '_render_frame_entry_debug_count'):
            self._render_frame_entry_debug_count = 0
        
        self._render_frame_entry_debug_count += 1
        
        # Usar tanto logger como print() para asegurar que el log aparezca
        debug_msg = (f"[Renderer-Frame-Entry] Frame {self._render_frame_entry_debug_count} | "
                    f"render_frame() ejecutado | framebuffer_data is None: {framebuffer_data is None}")
        
        # Loggear con logger
        logger.info(debug_msg)
        
        # Loggear con print() como fallback
        print(debug_msg)
        
        # Loggear también a stderr para asegurar que se capture
        import sys
        print(debug_msg, file=sys.stderr)
        
        if self._render_frame_entry_debug_count <= 20:
            if framebuffer_data is not None:
                logger.info(f"[Renderer-Frame-Entry] framebuffer_data length: {len(framebuffer_data)}")
                print(f"[Renderer-Frame-Entry] framebuffer_data length: {len(framebuffer_data)}")
        # -------------------------------------------
        
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
            # --- Step 0374: Verificación de Entrada al Bloque C++ PPU ---
            if not hasattr(self, '_cpp_ppu_entry_verify_count'):
                self._cpp_ppu_entry_verify_count = 0
            
            self._cpp_ppu_entry_verify_count += 1
            
            if self._cpp_ppu_entry_verify_count <= 10:
                logger.info(f"[Renderer-CPP-PPU-Entry] Frame {self._cpp_ppu_entry_verify_count} | "
                           f"Entrando al bloque C++ PPU | use_cpp_ppu={self.use_cpp_ppu} | cpp_ppu is None: {self.cpp_ppu is None}")
                print(f"[Renderer-CPP-PPU-Entry] Frame {self._cpp_ppu_entry_verify_count} | "
                      f"Entrando al bloque C++ PPU | use_cpp_ppu={self.use_cpp_ppu} | cpp_ppu is None: {self.cpp_ppu is None}")
            # -------------------------------------------
            
            try:
                # --- Step 0375: Tarea 3 - Verificación de Framebuffer Recibido ---
                # Verificar que el framebuffer recibido tiene datos válidos
                if framebuffer_data is not None:
                    if not hasattr(self, '_framebuffer_received_verify_count'):
                        self._framebuffer_received_verify_count = 0
                    
                    self._framebuffer_received_verify_count += 1
                    
                    if self._framebuffer_received_verify_count <= 10:
                        # Verificar que frame_indices no es None y tiene 23040 elementos
                        first_20_indices = [framebuffer_data[i] & 0x03 for i in range(min(20, len(framebuffer_data)))]
                        non_zero_count = sum(1 for i in range(len(framebuffer_data)) if (framebuffer_data[i] & 0x03) != 0)
                        
                        logger.info(f"[Renderer-Framebuffer-Received] Frame {self._framebuffer_received_verify_count} | "
                                   f"Length: {len(framebuffer_data)} | "
                                   f"First 20 indices: {first_20_indices} | "
                                   f"Non-zero pixels: {non_zero_count}/23040 ({non_zero_count*100/23040:.2f}%)")
                        print(f"[Renderer-Framebuffer-Received] Frame {self._framebuffer_received_verify_count} | "
                              f"Length: {len(framebuffer_data)} | "
                              f"First 20 indices: {first_20_indices} | "
                              f"Non-zero pixels: {non_zero_count}/23040 ({non_zero_count*100/23040:.2f}%)")
                        
                        if len(framebuffer_data) != 23040:
                            logger.warning(f"[Renderer-Framebuffer-Received] ⚠️ PROBLEMA: Framebuffer tiene {len(framebuffer_data)} elementos, esperado 23040!")
                            print(f"[Renderer-Framebuffer-Received] ⚠️ PROBLEMA: Framebuffer tiene {len(framebuffer_data)} elementos, esperado 23040!")
                        
                        if non_zero_count == 0:
                            logger.warning("[Renderer-Framebuffer-Received] ⚠️ PROBLEMA: Framebuffer completamente blanco (todos los índices son 0)!")
                            print("[Renderer-Framebuffer-Received] ⚠️ PROBLEMA: Framebuffer completamente blanco (todos los índices son 0)!")
                # -------------------------------------------
                
                # --- STEP 0308: SNAPSHOT INMUTABLE OPTIMIZADO ---
                # Si se proporciona framebuffer_data, usar ese snapshot en lugar de leer desde PPU
                diagnostic_data = None  # Inicializar para diagnóstico
                
                if framebuffer_data is not None:
                    # Ya es un snapshot inmutable (bytearray)
                    frame_indices = framebuffer_data
                    # --- Step 0350: Guardar frame_indices en Variable de Instancia ---
                    # Guardar frame_indices en una variable de instancia para que esté disponible en todo el método
                    self._current_frame_indices = frame_indices
                    # --- Step 0350: Log de Guardado de frame_indices ---
                    if not hasattr(self, '_frame_indices_saved_count'):
                        self._frame_indices_saved_count = 0
                    
                    self._frame_indices_saved_count += 1
                    
                    if self._frame_indices_saved_count <= 10:
                        logger.info(f"[Renderer-Frame-Indices-Saved] Frame {self._frame_indices_saved_count} | "
                                   f"frame_indices guardado en self._current_frame_indices (length={len(self._current_frame_indices)})")
                        print(f"[Renderer-Frame-Indices-Saved] Frame {self._frame_indices_saved_count} | "
                              f"frame_indices guardado en self._current_frame_indices (length={len(self._current_frame_indices)})")
                    # -------------------------------------------
                    snapshot_time = 0.0  # No hay overhead si ya viene como snapshot
                    diagnostic_data = framebuffer_data  # Usar framebuffer_data para diagnóstico
                    
                    # --- STEP 0333: Verificación de Ejecución del Código de Diagnóstico (si framebuffer_data fue proporcionado) ---
                    print(f"[Renderer-Diagnostic-Entry] Framebuffer recibido como parámetro, longitud: {len(framebuffer_data)}")
                    logger.info(f"[Renderer-Diagnostic-Entry] Framebuffer recibido como parámetro, longitud: {len(framebuffer_data)}")
                    # -------------------------------------------
                    
                    # --- Step 0343: Logs de Diagnóstico Adicionales (cuando framebuffer_data es proporcionado) ---
                    # --- Step 0365: Verificación de Renderizado en Python ---
                    if framebuffer_data is not None:
                        # Verificar contenido del framebuffer recibido
                        first_20_indices = [framebuffer_data[i] & 0x03 for i in range(min(20, len(framebuffer_data)))]
                        non_zero_count = sum(1 for i in range(len(framebuffer_data)) if (framebuffer_data[i] & 0x03) != 0)
                        
                        if not hasattr(self, '_renderer_check_count'):
                            self._renderer_check_count = 0
                        if self._renderer_check_count < 20:
                            self._renderer_check_count += 1
                            log_msg = f"[Renderer-Received] Frame {self._renderer_check_count} | " \
                                     f"First 20 indices: {first_20_indices} | " \
                                     f"Non-zero pixels: {non_zero_count}/23040 ({non_zero_count*100/23040:.2f}%)"
                            print(log_msg, flush=True)
                            logger.info(log_msg)
                            
                            if non_zero_count == 0:
                                log_msg = f"[Renderer-Received] ⚠️ PROBLEMA: Renderizador recibe framebuffer completamente vacío!"
                                print(log_msg, flush=True)
                                logger.warning(log_msg)
                            
                            # Verificar conversión RGB para los primeros píxeles
                            if len(framebuffer_data) > 0:
                                # Obtener paleta (BGP) desde MMU (registro I/O 0xFF47)
                                bgp = self.mmu.read(IO_BGP) if self.mmu else 0xE4
                                palette_map = {
                                    0: ((bgp >> 0) & 0x03),
                                    1: ((bgp >> 2) & 0x03),
                                    2: ((bgp >> 4) & 0x03),
                                    3: ((bgp >> 6) & 0x03)
                                }
                                # Mapeo de índices de paleta a RGB (simplificado)
                                rgb_map = {0: (255, 255, 255), 1: (192, 192, 192), 2: (96, 96, 96), 3: (0, 0, 0)}
                                sample_rgb = []
                                for i in range(min(10, len(framebuffer_data))):
                                    idx = framebuffer_data[i] & 0x03
                                    palette_idx = palette_map.get(idx, 0)
                                    rgb = rgb_map.get(palette_idx, (255, 255, 255))
                                    sample_rgb.append(rgb)
                                log_msg = f"[Renderer-RGB] First 10 RGB values: {sample_rgb}"
                                print(log_msg, flush=True)
                                logger.info(log_msg)
                    
                    if not hasattr(self, '_render_frame_entry_count'):
                        self._render_frame_entry_count = 0

                    self._render_frame_entry_count += 1

                    if self._render_frame_entry_count <= 20:
                        print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                              f"framebuffer_data is None: {framebuffer_data is None} | "
                              f"frame_indices is None: {frame_indices is None}")
                        logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                   f"framebuffer_data is None: {framebuffer_data is None} | "
                                   f"frame_indices is None: {frame_indices is None}")
                        
                        if frame_indices is not None:
                            print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                  f"frame_indices length: {len(frame_indices)}")
                            logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                       f"frame_indices length: {len(frame_indices)}")
                        elif framebuffer_data is not None:
                            print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                  f"framebuffer_data length: {len(framebuffer_data)}")
                            logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                       f"framebuffer_data length: {len(framebuffer_data)}")
                    # -------------------------------------------
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
                    
                    # --- Step 0350: Guardar frame_indices en Variable de Instancia ---
                    # Guardar frame_indices en una variable de instancia para que esté disponible en todo el método
                    self._current_frame_indices = frame_indices
                    # --- Step 0350: Log de Guardado de frame_indices ---
                    if not hasattr(self, '_frame_indices_saved_count'):
                        self._frame_indices_saved_count = 0
                    
                    self._frame_indices_saved_count += 1
                    
                    if self._frame_indices_saved_count <= 10:
                        logger.info(f"[Renderer-Frame-Indices-Saved] Frame {self._frame_indices_saved_count} | "
                                   f"frame_indices guardado en self._current_frame_indices (length={len(self._current_frame_indices)})")
                        print(f"[Renderer-Frame-Indices-Saved] Frame {self._frame_indices_saved_count} | "
                              f"frame_indices guardado en self._current_frame_indices (length={len(self._current_frame_indices)})")
                    # -------------------------------------------
                    
                    snapshot_time = (time.time() - snapshot_start) * 1000  # en milisegundos
                    
                    # --- STEP 0333: Verificación de Ejecución del Código de Diagnóstico (después de obtener frame_indices) ---
                    # Verificar que el código de diagnóstico se ejecuta
                    if frame_indices is not None:
                        print(f"[Renderer-Diagnostic-Entry] Framebuffer obtenido desde PPU, longitud: {len(frame_indices)}")
                        logger.info(f"[Renderer-Diagnostic-Entry] Framebuffer obtenido desde PPU, longitud: {len(frame_indices)}")
                        diagnostic_data = frame_indices  # Usar frame_indices para diagnóstico
                    else:
                        print("[Renderer-Diagnostic-Entry] ⚠️ Framebuffer es None después de obtener desde PPU!")
                        logger.warning("[Renderer-Diagnostic-Entry] ⚠️ Framebuffer es None después de obtener desde PPU!")
                    # -------------------------------------------
                    
                    # --- Step 0343: Logs de Diagnóstico Adicionales ---
                    # Verificar que render_frame() se ejecuta y que frame_indices está disponible
                    if not hasattr(self, '_render_frame_entry_count'):
                        self._render_frame_entry_count = 0

                    self._render_frame_entry_count += 1

                    if self._render_frame_entry_count <= 20:
                        print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                              f"framebuffer_data is None: {framebuffer_data is None} | "
                              f"frame_indices is None: {frame_indices is None}")
                        logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                   f"framebuffer_data is None: {framebuffer_data is None} | "
                                   f"frame_indices is None: {frame_indices is None}")
                        
                        if frame_indices is not None:
                            print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                  f"frame_indices length: {len(frame_indices)}")
                            logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                       f"frame_indices length: {len(frame_indices)}")
                        elif framebuffer_data is not None:
                            print(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                  f"framebuffer_data length: {len(framebuffer_data)}")
                            logger.info(f"[Renderer-Entry] Frame {self._render_frame_entry_count} | "
                                       f"framebuffer_data length: {len(framebuffer_data)}")
                    # -------------------------------------------
                # ----------------------------------------
                
                # --- Step 0346: Verificación de Condiciones de los Logs ---
                # Verificar que frame_indices está disponible antes de los bloques de diagnóstico
                if 'frame_indices' not in locals():
                    logger.warning("[Renderer-Conditions] frame_indices no está definido")
                    print("[Renderer-Conditions] frame_indices no está definido")
                elif frame_indices is None:
                    logger.warning("[Renderer-Conditions] frame_indices es None")
                    print("[Renderer-Conditions] frame_indices es None")
                elif len(frame_indices) == 0:
                    logger.warning(f"[Renderer-Conditions] frame_indices está vacío (length=0)")
                    print(f"[Renderer-Conditions] frame_indices está vacío (length=0)")
                else:
                    logger.info(f"[Renderer-Conditions] frame_indices disponible: length={len(frame_indices)}")
                    print(f"[Renderer-Conditions] frame_indices disponible: length={len(frame_indices)}")
                
                # --- Step 0357: Verificación del Renderizado Cuando Hay Tiles Reales ---
                # Verificar si el renderizado funciona correctamente cuando hay tiles reales
                if frame_indices and len(frame_indices) == 23040:
                    # Contar píxeles no-blancos
                    non_white_count = sum(1 for idx in frame_indices[:1000] if idx != 0)
                    
                    if non_white_count > 50:
                        # Hay tiles reales en el framebuffer
                        if not hasattr(self, '_renderer_with_tiles_log_count'):
                            self._renderer_with_tiles_log_count = 0
                        
                        if self._renderer_with_tiles_log_count < 10:
                            self._renderer_with_tiles_log_count += 1
                            
                            logger.info(f"[Renderer-With-Tiles] Framebuffer received with tiles | "
                                       f"Non-white pixels in first 1000: {non_white_count}/1000")
                            print(f"[Renderer-With-Tiles] Framebuffer received with tiles | "
                                  f"Non-white pixels in first 1000: {non_white_count}/1000")
                            
                            # Verificar conversión de índices a RGB
                            # Obtener paleta desde BGP
                            bgp = self.mmu.read(IO_BGP)
                            palette_map = {
                                0: (bgp >> 0) & 0x03,
                                1: (bgp >> 2) & 0x03,
                                2: (bgp >> 4) & 0x03,
                                3: (bgp >> 6) & 0x03,
                            }
                            
                            sample_indices = list(frame_indices[0:20])
                            sample_rgb = [PALETTE_GREYSCALE[palette_map[idx]] for idx in sample_indices]
                            
                            logger.info(f"[Renderer-With-Tiles] Sample indices: {sample_indices[:10]}")
                            logger.info(f"[Renderer-With-Tiles] Sample RGB: {sample_rgb[:10]}")
                            print(f"[Renderer-With-Tiles] Sample indices: {sample_indices[:10]}")
                            print(f"[Renderer-With-Tiles] Sample RGB: {sample_rgb[:10]}")
                            
                            # Verificar que los píxeles se dibujan
                            logger.info(f"[Renderer-With-Tiles] ✅ Renderizando framebuffer con tiles reales")
                            print(f"[Renderer-With-Tiles] ✅ Renderizando framebuffer con tiles reales")
                # -------------------------------------------
                # -------------------------------------------
                
                # --- Step 0342: Verificación del Tamaño Real del Framebuffer ---
                # Verificar el tamaño real del framebuffer cuando se recibe
                if not hasattr(self, '_framebuffer_size_check_count'):
                    self._framebuffer_size_check_count = 0

                if frame_indices is not None and self._framebuffer_size_check_count < 20:
                    self._framebuffer_size_check_count += 1
                    
                    actual_size = len(frame_indices)
                    expected_size = 160 * 144  # 23040
                    
                    print(f"[Renderer-Framebuffer-Size] Frame {self._framebuffer_size_check_count} | "
                          f"Actual size: {actual_size} | Expected: {expected_size} | "
                          f"Type: {type(frame_indices)}")
                    logger.info(f"[Renderer-Framebuffer-Size] Frame {self._framebuffer_size_check_count} | "
                               f"Actual size: {actual_size} | Expected: {expected_size} | "
                               f"Type: {type(frame_indices)}")
                    
                    if actual_size != expected_size:
                        logger.warning(f"[Renderer-Framebuffer-Size] ⚠️ Tamaño inesperado! "
                                      f"Actual: {actual_size}, Expected: {expected_size}")
                        
                        # Si el tamaño es menor, verificar cuántos píxeles faltan
                        if actual_size < expected_size:
                            missing_pixels = expected_size - actual_size
                            logger.warning(f"[Renderer-Framebuffer-Size] ⚠️ Faltan {missing_pixels} píxeles "
                                          f"({missing_pixels / expected_size * 100:.1f}% del framebuffer)")
                        
                        # Si el tamaño es mayor, verificar cuántos píxeles extra hay
                        if actual_size > expected_size:
                            extra_pixels = actual_size - expected_size
                            logger.warning(f"[Renderer-Framebuffer-Size] ⚠️ Hay {extra_pixels} píxeles extra "
                                          f"({extra_pixels / expected_size * 100:.1f}% del framebuffer)")
                    else:
                        logger.info(f"[Renderer-Framebuffer-Size] ✅ Tamaño correcto: {actual_size} píxeles")
                # -------------------------------------------
                
                # --- Step 0342: Verificación del Orden de Lectura y Dibujo de Píxeles ---
                # Verificar que el orden de los píxeles es correcto (formato [y * 160 + x])
                if not hasattr(self, '_pixel_order_verification_count'):
                    self._pixel_order_verification_count = 0

                if frame_indices is not None and len(frame_indices) > 0 and \
                   self._pixel_order_verification_count < 10:
                    self._pixel_order_verification_count += 1
                    
                    print(f"[Renderer-Pixel-Order-Verification] Frame {self._pixel_order_verification_count} | "
                          f"Verificando orden de píxeles:")
                    logger.info(f"[Renderer-Pixel-Order-Verification] Frame {self._pixel_order_verification_count} | "
                               f"Verificando orden de píxeles:")
                    
                    # Verificar píxeles adyacentes horizontalmente (misma línea, x consecutivos)
                    test_y = 0
                    test_x_start = 0
                    test_x_count = 5
                    
                    logger.info(f"[Renderer-Pixel-Order-Verification] Verificando píxeles adyacentes horizontalmente (y={test_y}):")
                    for x in range(test_x_start, test_x_start + test_x_count):
                        idx = test_y * 160 + x
                        if idx < len(frame_indices):
                            color_idx = frame_indices[idx] & 0x03
                            logger.info(f"[Renderer-Pixel-Order-Verification] Pixel (x={x}, y={test_y}): "
                                       f"idx={idx}, color_idx={color_idx}")
                            
                            # Verificar que el índice es correcto
                            expected_idx = test_y * 160 + x
                            if idx != expected_idx:
                                logger.warning(f"[Renderer-Pixel-Order-Verification] ⚠️ Índice incorrecto! "
                                             f"Expected: {expected_idx}, Actual: {idx}")
                    
                    # Verificar píxeles adyacentes verticalmente (misma columna, y consecutivos)
                    test_x = 0
                    test_y_start = 0
                    test_y_count = 5
                    
                    logger.info(f"[Renderer-Pixel-Order-Verification] Verificando píxeles adyacentes verticalmente (x={test_x}):")
                    for y in range(test_y_start, test_y_start + test_y_count):
                        idx = y * 160 + test_x
                        if idx < len(frame_indices):
                            color_idx = frame_indices[idx] & 0x03
                            logger.info(f"[Renderer-Pixel-Order-Verification] Pixel (x={test_x}, y={y}): "
                                       f"idx={idx}, color_idx={color_idx}")
                            
                            # Verificar que el índice es correcto
                            expected_idx = y * 160 + test_x
                            if idx != expected_idx:
                                logger.warning(f"[Renderer-Pixel-Order-Verification] ⚠️ Índice incorrecto! "
                                             f"Expected: {expected_idx}, Actual: {idx}")
                            
                            # Verificar que la diferencia entre índices consecutivos es 160
                            if y > test_y_start:
                                prev_idx = (y - 1) * 160 + test_x
                                idx_diff = idx - prev_idx
                                if idx_diff != 160:
                                    logger.warning(f"[Renderer-Pixel-Order-Verification] ⚠️ Diferencia incorrecta! "
                                                 f"Expected: 160, Actual: {idx_diff}")
                # -------------------------------------------
                
                # Diagnóstico desactivado para producción
                
                # --- Step 0335: Verificación Periódica del Renderizador ---
                # Verificar que el renderizador sigue dibujando después de los primeros frames
                if not hasattr(self, '_renderer_periodic_check_count'):
                    self._renderer_periodic_check_count = 0
                
                if self._renderer_periodic_check_count % 100 == 0:
                    if self._renderer_periodic_check_count < 200:  # Limitar a 200 logs
                        if frame_indices is not None and len(frame_indices) > 0:
                            # Contar índices en el framebuffer recibido
                            index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                            for idx in range(min(100, len(frame_indices))):
                                color_idx = frame_indices[idx] & 0x03
                                if color_idx in index_counts:
                                    index_counts[color_idx] += 1
                            
                            print(f"[Renderer-Periodic] Frame {self._renderer_periodic_check_count} | "
                                  f"Index counts (first 100): 0={index_counts[0]} 1={index_counts[1]} "
                                  f"2={index_counts[2]} 3={index_counts[3]}")
                            logger.info(f"[Renderer-Periodic] Frame {self._renderer_periodic_check_count} | "
                                       f"Index counts (first 100): 0={index_counts[0]} 1={index_counts[1]} "
                                       f"2={index_counts[2]} 3={index_counts[3]}")
                            
                            if index_counts[0] == 100 and index_counts[3] == 0:
                                print(f"[Renderer-Periodic] ⚠️ ADVERTENCIA: Framebuffer completamente blanco en frame {self._renderer_periodic_check_count}!")
                                logger.warning(f"[Renderer-Periodic] ⚠️ ADVERTENCIA: Framebuffer completamente blanco en frame {self._renderer_periodic_check_count}!")
                
                self._renderer_periodic_check_count += 1
                # -------------------------------------------
                
                # --- Step 0347: Verificación del Framebuffer Completo ---
                # Verificar todas las líneas del framebuffer, no solo líneas específicas
                if not hasattr(self, '_framebuffer_complete_check_count'):
                    self._framebuffer_complete_check_count = 0

                if frame_indices is not None and len(frame_indices) == 23040 and \
                   self._framebuffer_complete_check_count < 10:
                    self._framebuffer_complete_check_count += 1
                    
                    # Contar líneas con datos (no todas blancas)
                    lines_with_data = 0
                    lines_empty = 0
                    total_non_zero_pixels = 0
                    index_counts = [0, 0, 0, 0]
                    
                    for y in range(144):
                        line_start = y * 160
                        line_non_zero = 0
                        
                        for x in range(160):
                            idx = line_start + x
                            if idx < len(frame_indices):
                                color_idx = frame_indices[idx] & 0x03
                                if color_idx < 4:
                                    index_counts[color_idx] += 1
                                    if color_idx != 0:
                                        line_non_zero += 1
                                        total_non_zero_pixels += 1
                        
                        if line_non_zero > 0:
                            lines_with_data += 1
                        else:
                            lines_empty += 1
                    
                    logger.info(f"[Renderer-Framebuffer-Complete] Frame {self._framebuffer_complete_check_count} | "
                               f"Lines with data: {lines_with_data}/144 | Lines empty: {lines_empty}/144 | "
                               f"Total non-zero pixels: {total_non_zero_pixels}/23040 | "
                               f"Distribution: 0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                    print(f"[Renderer-Framebuffer-Complete] Frame {self._framebuffer_complete_check_count} | "
                          f"Lines with data: {lines_with_data}/144 | Lines empty: {lines_empty}/144 | "
                          f"Total non-zero pixels: {total_non_zero_pixels}/23040 | "
                          f"Distribution: 0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                    
                    # Advertencia si hay muchas líneas vacías
                    if lines_empty > 10:
                        logger.warning(f"[Renderer-Framebuffer-Complete] ⚠️ {lines_empty} líneas están vacías!")
                        print(f"[Renderer-Framebuffer-Complete] ⚠️ {lines_empty} líneas están vacías!")
                    
                    # Identificar líneas problemáticas (vacías cuando deberían tener datos)
                    if lines_empty > 0 and self._framebuffer_complete_check_count <= 5:
                        empty_lines = []
                        for y in range(144):
                            line_start = y * 160
                            line_non_zero = 0
                            for x in range(160):
                                idx = line_start + x
                                if idx < len(frame_indices):
                                    color_idx = frame_indices[idx] & 0x03
                                    if color_idx != 0:
                                        line_non_zero += 1
                            if line_non_zero == 0:
                                empty_lines.append(y)
                        
                        if empty_lines:
                            logger.warning(f"[Renderer-Framebuffer-Complete] ⚠️ Líneas vacías: {empty_lines[:20]}")
                            print(f"[Renderer-Framebuffer-Complete] ⚠️ Líneas vacías: {empty_lines[:20]}")
                # -------------------------------------------
                
                # --- Step 0337: Verificación de Formato del Framebuffer ---
                if not hasattr(self, '_framebuffer_format_check_count'):
                    self._framebuffer_format_check_count = 0
                
                if self._framebuffer_format_check_count < 5:
                    self._framebuffer_format_check_count += 1
                    
                    # Verificar tipo y tamaño del framebuffer
                    print(f"[Renderer-Framebuffer-Format] Frame {self._framebuffer_format_check_count} | "
                          f"Type: {type(frame_indices)} | Length: {len(frame_indices)} | "
                          f"Expected: 23040 (160*144)")
                    logger.info(f"[Renderer-Framebuffer-Format] Frame {self._framebuffer_format_check_count} | "
                               f"Type: {type(frame_indices)} | Length: {len(frame_indices)} | "
                               f"Expected: 23040 (160*144)")
                    
                    # Verificar algunos índices del framebuffer
                    test_indices = [0, 80, 11520, 23039]  # Primer píxel, centro, mitad, último
                    for idx in test_indices:
                        if idx < len(frame_indices):
                            color_index = frame_indices[idx] & 0x03
                            x = idx % 160
                            y = idx // 160
                            
                            print(f"[Renderer-Framebuffer-Format] Index {idx} (x={x}, y={y}): "
                                  f"Raw value={frame_indices[idx]} | Color index={color_index}")
                            logger.info(f"[Renderer-Framebuffer-Format] Index {idx} (x={x}, y={y}): "
                                       f"Raw value={frame_indices[idx]} | Color index={color_index}")
                    
                    # Verificar distribución de índices
                    index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                    for idx in range(min(1000, len(frame_indices))):  # Primeros 1000 píxeles
                        color_idx = frame_indices[idx] & 0x03
                        if color_idx in index_counts:
                            index_counts[color_idx] += 1
                    
                    print(f"[Renderer-Framebuffer-Format] Distribution (first 1000 pixels): "
                          f"0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                    logger.info(f"[Renderer-Framebuffer-Format] Distribution (first 1000 pixels): "
                               f"0={index_counts[0]} 1={index_counts[1]} 2={index_counts[2]} 3={index_counts[3]}")
                # -------------------------------------------
                
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
                
                # --- Step 0337: Verificación de Paleta Debug vs Real ---
                if not hasattr(self, '_palette_debug_check_count'):
                    self._palette_debug_check_count = 0
                
                if self._palette_debug_check_count < 10:
                    self._palette_debug_check_count += 1
                    
                    print(f"[Renderer-Palette-Debug] Frame {self._palette_debug_check_count} | "
                          f"Palette used: {palette}")
                    logger.info(f"[Renderer-Palette-Debug] Frame {self._palette_debug_check_count} | "
                               f"Palette used: {palette}")
                    
                    # Verificar que la paleta tiene 4 colores
                    if len(palette) != 4:
                        print(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Paleta tiene {len(palette)} colores, esperado 4")
                        logger.warning(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Paleta tiene {len(palette)} colores, esperado 4")
                    
                    # Verificar que cada color es una tupla RGB válida
                    for i, color in enumerate(palette):
                        if not isinstance(color, tuple) or len(color) != 3:
                            print(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Color {i} inválido: {color}")
                            logger.warning(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Color {i} inválido: {color}")
                        elif not all(0 <= c <= 255 for c in color):
                            print(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Color {i} fuera de rango: {color}")
                            logger.warning(f"[Renderer-Palette-Debug] ⚠️ PROBLEMA: Color {i} fuera de rango: {color}")
                # -------------------------------------------
                
                # --- Step 0341: Verificación Detallada de Conversión de Índices a RGB ---
                # Verificar que la conversión de índices a RGB es correcta
                if not hasattr(self, '_rgb_conversion_check_count'):
                    self._rgb_conversion_check_count = 0
                
                if frame_indices is not None and len(frame_indices) > 0 and self._rgb_conversion_check_count < 10:
                    # Agregar verificación de tamaño
                    if len(frame_indices) != 23040:
                        logger.warning(f"[Renderer-RGB-Conversion] ⚠️ Tamaño inesperado: {len(frame_indices)} (esperado: 23040)")
                    
                    self._rgb_conversion_check_count += 1
                    
                    # Verificar que la paleta tiene los valores correctos
                    logger.info(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_check_count} | "
                               f"Palette: 0={palette[0]}, 1={palette[1]}, 2={palette[2]}, 3={palette[3]}")
                    
                    # Verificar algunos píxeles específicos
                    test_pixels = [
                        (0, 0),      # Esquina superior izquierda
                        (80, 72),    # Centro
                        (159, 143),  # Esquina inferior derecha
                        (10, 10),    # Píxel aleatorio
                        (150, 100)   # Píxel aleatorio
                    ]
                    
                    logger.info(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_check_count} | "
                               f"Verificando conversión de índices a RGB:")
                    for x, y in test_pixels:
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            color_index = frame_indices[idx] & 0x03
                            rgb_color = palette[color_index]
                            
                            logger.info(f"[Renderer-RGB-Conversion] Pixel (x={x}, y={y}): "
                                       f"idx={idx}, color_index={color_index}, RGB={rgb_color}")
                            
                            # Verificar que el índice está en rango válido
                            if color_index > 3:
                                logger.warning(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: Índice fuera de rango: {color_index}")
                            
                            # Verificar que el RGB es válido
                            if not isinstance(rgb_color, tuple) or len(rgb_color) != 3:
                                logger.warning(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: RGB inválido: {rgb_color}")
                            elif not all(0 <= c <= 255 for c in rgb_color):
                                logger.warning(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: RGB fuera de rango: {rgb_color}")
                # -------------------------------------------
                
                # --- Step 0374: Tarea 2 - Verificar Conversión de Índices a RGB ---
                # Verificar que los índices se convierten correctamente a RGB usando BGP
                if frame_indices is not None and len(frame_indices) > 0:
                    if not hasattr(self, '_rgb_conversion_verify_count'):
                        self._rgb_conversion_verify_count = 0
                    
                    self._rgb_conversion_verify_count += 1
                    
                    if self._rgb_conversion_verify_count <= 50:
                        # Obtener paleta (BGP) desde MMU (registro I/O 0xFF47)
                        bgp = self.mmu.read(IO_BGP) if self.mmu else 0xE4
                        palette_map = {
                            0: ((bgp >> 0) & 0x03),
                            1: ((bgp >> 2) & 0x03),
                            2: ((bgp >> 4) & 0x03),
                            3: ((bgp >> 6) & 0x03)
                        }
                        
                        # Mapeo de índices de paleta a RGB (grayscale)
                        rgb_map = {0: (255, 255, 255), 1: (192, 192, 192), 2: (96, 96, 96), 3: (0, 0, 0)}
                        
                        # Verificar primeros 20 píxeles
                        sample_indices = []
                        sample_rgb = []
                        
                        for i in range(min(20, len(frame_indices))):
                            idx = frame_indices[i] & 0x03
                            palette_idx = palette_map.get(idx, 0)
                            rgb = rgb_map.get(palette_idx, (255, 255, 255))
                            sample_indices.append(idx)
                            sample_rgb.append(rgb)
                        
                        logger.info(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_verify_count} | "
                                   f"Sample indices: {sample_indices} | Sample RGB: {sample_rgb}")
                        print(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_verify_count} | "
                              f"Sample indices: {sample_indices} | Sample RGB: {sample_rgb}")
                        
                        # Verificar que el índice 3 se convierte a negro
                        if 3 in sample_indices:
                            idx_3_pos = sample_indices.index(3)
                            rgb_3 = sample_rgb[idx_3_pos]
                            if rgb_3 != (0, 0, 0):
                                logger.warning(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: Índice 3 no se convierte a negro! RGB: {rgb_3}")
                                print(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: Índice 3 no se convierte a negro! RGB: {rgb_3}")
                # -------------------------------------------
                # ----------------------------------------
                
                # --- STEP 0333: Verificación de Ejecución del Código de Diagnóstico ---
                # Verificar que el código de diagnóstico se ejecuta
                # NOTA: frame_indices se define más abajo, así que verificamos después de obtenerlo
                # -------------------------------------------
                
                # --- Step 0340: Verificación de Correspondencia Entre Framebuffer y Visualización ---
                # Verificar el contenido del framebuffer cuando se renderiza
                if not hasattr(self, '_framebuffer_visualization_check_count'):
                    self._framebuffer_visualization_check_count = 0
                
                if framebuffer_data is not None and self._framebuffer_visualization_check_count < 10:
                    self._framebuffer_visualization_check_count += 1
                    
                    # Verificar primeros 20 píxeles
                    first_20 = [framebuffer_data[i] & 0x03 for i in range(min(20, len(framebuffer_data)))]
                    
                    # Contar índices en los primeros 100 píxeles
                    index_counts = [0, 0, 0, 0]
                    non_zero_pixels = 0
                    for i in range(min(100, len(framebuffer_data))):
                        idx = framebuffer_data[i] & 0x03
                        if idx < 4:
                            index_counts[idx] += 1
                            if idx != 0:
                                non_zero_pixels += 1
                    
                    logger.info(f"[Renderer-Framebuffer-Visualization] Frame {self._framebuffer_visualization_check_count} | "
                               f"First 20 indices: {first_20}")
                    logger.info(f"[Renderer-Framebuffer-Visualization] Frame {self._framebuffer_visualization_check_count} | "
                               f"Index counts (first 100): 0={index_counts[0]} 1={index_counts[1]} "
                               f"2={index_counts[2]} 3={index_counts[3]} | Non-zero: {non_zero_pixels}/100")
                    
                    # Verificar algunos píxeles específicos (esquinas y centro)
                    test_positions = [(0, 0), (0, 159), (71, 79), (143, 0), (143, 159)]
                    for y, x in test_positions:
                        idx = y * 160 + x
                        if idx < len(framebuffer_data):
                            color_idx = framebuffer_data[idx] & 0x03
                            logger.info(f"[Renderer-Framebuffer-Visualization] Pixel ({x}, {y}): index={color_idx}")
                # -------------------------------------------
                
                # --- Step 0341: Verificación del Orden de Píxeles en el Framebuffer ---
                # Verificar que el orden de los píxeles es correcto (formato [y * 160 + x])
                if not hasattr(self, '_pixel_order_check_count'):
                    self._pixel_order_check_count = 0
                
                if frame_indices is not None and len(frame_indices) > 0 and self._pixel_order_check_count < 10:
                    # Agregar verificación de tamaño
                    if len(frame_indices) != 23040:
                        logger.warning(f"[Renderer-Pixel-Order] ⚠️ Tamaño inesperado: {len(frame_indices)} (esperado: 23040)")
                    
                    self._pixel_order_check_count += 1
                    
                    # Verificar píxeles en una línea horizontal (y=0, x=0 a x=10)
                    logger.info(f"[Renderer-Pixel-Order] Frame {self._pixel_order_check_count} | "
                               f"Verificando orden de píxeles en línea y=0:")
                    for x in range(10):
                        idx = 0 * 160 + x  # y=0, x variable
                        if idx < len(frame_indices):
                            color_idx = frame_indices[idx] & 0x03
                            logger.info(f"[Renderer-Pixel-Order] Pixel (x={x}, y=0): idx={idx}, color_idx={color_idx}")
                    
                    # Verificar píxeles en una columna vertical (x=0, y=0 a y=10)
                    logger.info(f"[Renderer-Pixel-Order] Frame {self._pixel_order_check_count} | "
                               f"Verificando orden de píxeles en columna x=0:")
                    for y in range(10):
                        idx = y * 160 + 0  # y variable, x=0
                        if idx < len(frame_indices):
                            color_idx = frame_indices[idx] & 0x03
                            logger.info(f"[Renderer-Pixel-Order] Pixel (x=0, y={y}): idx={idx}, color_idx={color_idx}")
                    
                    # Verificar patrón checkerboard esperado
                    # Si el framebuffer tiene un patrón checkerboard, los píxeles deberían alternar
                    # Verificar algunos píxeles adyacentes
                    test_positions = [
                        (0, 0), (1, 0), (0, 1), (1, 1),  # Esquina superior izquierda
                        (79, 0), (80, 0), (79, 1), (80, 1),  # Centro superior
                        (159, 0), (158, 0), (159, 1), (158, 1),  # Esquina superior derecha
                    ]
                    
                    logger.info(f"[Renderer-Pixel-Order] Frame {self._pixel_order_check_count} | "
                               f"Verificando patrón checkerboard en píxeles adyacentes:")
                    for x, y in test_positions:
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            color_idx = frame_indices[idx] & 0x03
                            logger.info(f"[Renderer-Pixel-Order] Pixel (x={x}, y={y}): idx={idx}, color_idx={color_idx}")
                # -------------------------------------------
                
                # --- STEP 0332: Diagnóstico de Framebuffer Recibido ---
                # Verificar qué índices recibe el renderizador del framebuffer
                # Usar diagnostic_data que puede ser framebuffer_data o frame_indices
                if diagnostic_data is not None and len(diagnostic_data) > 0:
                    if not hasattr(self, '_framebuffer_diagnostic_count'):
                        self._framebuffer_diagnostic_count = 0
                    if self._framebuffer_diagnostic_count < 5:
                        self._framebuffer_diagnostic_count += 1
                        
                        # Contar índices en el framebuffer
                        index_counts = {0: 0, 1: 0, 2: 0, 3: 0}
                        for idx in range(min(100, len(diagnostic_data))):  # Primeros 100 píxeles
                            color_idx = diagnostic_data[idx] & 0x03
                            if color_idx in index_counts:
                                index_counts[color_idx] += 1
                        
                        # --- Step 0333: Logs con print() como fallback ---
                        log_msg = f"[Renderer-Framebuffer-Diagnostic] Frame {self._framebuffer_diagnostic_count} | " \
                                  f"Index counts (first 100): 0={index_counts[0]} 1={index_counts[1]} " \
                                  f"2={index_counts[2]} 3={index_counts[3]}"
                        print(log_msg)  # Fallback a print()
                        logger.info(log_msg)  # Logger normal
                        # -------------------------------------------
                        
                        # Verificar primeros 20 píxeles
                        first_20 = [diagnostic_data[i] & 0x03 for i in range(min(20, len(diagnostic_data)))]
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
                
                # --- STEP 0333: Verificación de Dibujo de Píxeles ---
                # Verificar que los píxeles se dibujan con los colores correctos
                if not hasattr(self, '_pixel_draw_check_count'):
                    self._pixel_draw_check_count = 0
                if self._pixel_draw_check_count < 5:
                    self._pixel_draw_check_count += 1
                    
                    # Verificar algunos píxeles específicos antes de dibujar
                    test_pixels = [(0, 0), (80, 72), (159, 143)]
                    for x, y in test_pixels:
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            color_index = frame_indices[idx] & 0x03
                            rgb_color = palette[color_index]
                            print(f"[Renderer-Pixel-Draw] Pixel ({x}, {y}): index={color_index} -> RGB={rgb_color}")
                            logger.info(f"[Renderer-Pixel-Draw] Pixel ({x}, {y}): index={color_index} -> RGB={rgb_color}")
                # -------------------------------------------
                
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
                
                # --- Step 0337: Verificación de Conversión de Índices a RGB ---
                # Verificar que los índices se convierten correctamente a RGB
                if not hasattr(self, '_index_to_rgb_check_count'):
                    self._index_to_rgb_check_count = 0
                
                if self._index_to_rgb_check_count < 20:
                    self._index_to_rgb_check_count += 1
                    
                    # Verificar algunos píxeles específicos
                    test_pixels = [
                        (0, 0),      # Esquina superior izquierda
                        (80, 72),    # Centro
                        (159, 143),  # Esquina inferior derecha
                        (10, 10),    # Píxel aleatorio
                        (150, 100)   # Píxel aleatorio
                    ]
                    
                    for x, y in test_pixels:
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            color_index = frame_indices[idx] & 0x03
                            rgb_color = palette[color_index]
                            
                            print(f"[Renderer-Index-to-RGB] Frame {self._index_to_rgb_check_count} | "
                                  f"Pixel ({x}, {y}): index={color_index} -> RGB={rgb_color} | "
                                  f"Palette[{color_index}]={palette[color_index]}")
                            logger.info(f"[Renderer-Index-to-RGB] Frame {self._index_to_rgb_check_count} | "
                                       f"Pixel ({x}, {y}): index={color_index} -> RGB={rgb_color} | "
                                       f"Palette[{color_index}]={palette[color_index]}")
                            
                            # Verificar que el índice está en rango válido
                            if color_index > 3:
                                print(f"[Renderer-Index-to-RGB] ⚠️ PROBLEMA: Índice fuera de rango: {color_index}")
                                logger.warning(f"[Renderer-Index-to-RGB] ⚠️ PROBLEMA: Índice fuera de rango: {color_index}")
                            
                            # Verificar que la paleta tiene valores válidos
                            if not isinstance(rgb_color, tuple) or len(rgb_color) != 3:
                                print(f"[Renderer-Index-to-RGB] ⚠️ PROBLEMA: RGB inválido: {rgb_color}")
                                logger.warning(f"[Renderer-Index-to-RGB] ⚠️ PROBLEMA: RGB inválido: {rgb_color}")
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
                    
                    # --- Step 0375: Tarea 4 - Verificación de Conversión RGB ---
                    # Verificar que los primeros 20 píxeles del rgb_array tienen los valores RGB correctos
                    if not hasattr(self, '_rgb_conversion_verify_count'):
                        self._rgb_conversion_verify_count = 0
                    
                    self._rgb_conversion_verify_count += 1
                    
                    if self._rgb_conversion_verify_count <= 10:
                        # Verificar los primeros 20 píxeles
                        first_20_rgb = []
                        first_20_indices_original = []
                        for i in range(min(20, len(frame_indices))):
                            idx = frame_indices[i] & 0x03
                            first_20_indices_original.append(idx)
                            expected_rgb = palette[idx]
                            # rgb_array está en formato (144, 160, 3), así que necesitamos calcular (y, x)
                            y = i // 160
                            x = i % 160
                            if y < 144 and x < 160:
                                actual_rgb = tuple(rgb_array[y, x])
                                first_20_rgb.append(actual_rgb)
                                
                                if actual_rgb != expected_rgb:
                                    logger.warning(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: Pixel {i} (x={x}, y={y}) | "
                                                  f"Index={idx} | Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                                    print(f"[Renderer-RGB-Conversion] ⚠️ PROBLEMA: Pixel {i} (x={x}, y={y}) | "
                                          f"Index={idx} | Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                        
                        logger.info(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_verify_count} | "
                                   f"First 20 indices: {first_20_indices_original} | "
                                   f"First 20 RGB: {first_20_rgb}")
                        print(f"[Renderer-RGB-Conversion] Frame {self._rgb_conversion_verify_count} | "
                              f"First 20 indices: {first_20_indices_original} | "
                              f"First 20 RGB: {first_20_rgb}")
                    # -------------------------------------------
                    
                    # --- Step 0337: Verificación de Aplicación de Paleta en NumPy ---
                    if not hasattr(self, '_numpy_palette_check_count'):
                        self._numpy_palette_check_count = 0
                    
                    if self._numpy_palette_check_count < 10:
                        self._numpy_palette_check_count += 1
                        
                        # Verificar algunos píxeles antes y después del mapeo
                        test_indices = [(0, 0), (80, 72), (159, 143)]
                        for y, x in test_indices:
                            idx = y * 160 + x
                            if idx < len(frame_indices):
                                original_index = frame_indices[idx] & 0x03
                                expected_rgb = palette[original_index]
                                
                                # Verificar en el array numpy después del mapeo
                                if y < 144 and x < 160:
                                    actual_rgb = tuple(rgb_array[y, x])
                                    
                                    print(f"[Renderer-NumPy-Palette] Frame {self._numpy_palette_check_count} | "
                                          f"Pixel ({x}, {y}): index={original_index} | "
                                          f"Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                                    logger.info(f"[Renderer-NumPy-Palette] Frame {self._numpy_palette_check_count} | "
                                               f"Pixel ({x}, {y}): index={original_index} | "
                                               f"Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                                    
                                    if actual_rgb != expected_rgb:
                                        print(f"[Renderer-NumPy-Palette] ⚠️ PROBLEMA: RGB no coincide!")
                                        logger.warning(f"[Renderer-NumPy-Palette] ⚠️ PROBLEMA: RGB no coincide!")
                    # -------------------------------------------
                    
                    # Blit directo usando surfarray - necesita formato (width, height, channels)
                    # surfarray espera (width, height, channels), así que necesitamos (160, 144, 3)
                    rgb_array_swapped = np.swapaxes(rgb_array, 0, 1)  # (160, 144, 3)
                    surfarray.blit_array(self.surface, rgb_array_swapped)
                    
                    # --- Step 0375: Tarea 5 - Verificación de Superficie Después de NumPy Blit ---
                    # Verificar que self.surface tiene los píxeles correctos después de surfarray.blit_array()
                    if not hasattr(self, '_surface_after_numpy_verify_count'):
                        self._surface_after_numpy_verify_count = 0
                    
                    self._surface_after_numpy_verify_count += 1
                    
                    if self._surface_after_numpy_verify_count <= 10:
                        # Leer los primeros 20 píxeles de self.surface y comparar con los valores esperados del rgb_array
                        surface_pixels = []
                        expected_pixels = []
                        for x in range(min(20, 160)):
                            pixel_color = self.surface.get_at((x, 0)) if hasattr(self.surface, 'get_at') else None
                            if pixel_color:
                                surface_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
                            
                            # Obtener el valor esperado del rgb_array_swapped (formato width, height, channels)
                            if x < 160:
                                expected_rgb = tuple(rgb_array_swapped[x, 0])
                                expected_pixels.append(expected_rgb)
                        
                        logger.info(f"[Renderer-Surface-After-NumPy] Frame {self._surface_after_numpy_verify_count} | "
                                   f"Surface pixels (first 20): {surface_pixels} | "
                                   f"Expected pixels (first 20): {expected_pixels}")
                        print(f"[Renderer-Surface-After-NumPy] Frame {self._surface_after_numpy_verify_count} | "
                              f"Surface pixels (first 20): {surface_pixels} | "
                              f"Expected pixels (first 20): {expected_pixels}")
                        
                        # Verificar discrepancias
                        discrepancies = []
                        for i in range(min(len(surface_pixels), len(expected_pixels))):
                            if surface_pixels[i] != expected_pixels[i]:
                                discrepancies.append((i, surface_pixels[i], expected_pixels[i]))
                        
                        if discrepancies:
                            logger.warning(f"[Renderer-Surface-After-NumPy] ⚠️ PROBLEMA: {len(discrepancies)} discrepancias encontradas: {discrepancies}")
                            print(f"[Renderer-Surface-After-NumPy] ⚠️ PROBLEMA: {len(discrepancies)} discrepancias encontradas: {discrepancies}")
                    # -------------------------------------------
                    
                    # --- Step 0375: Tarea 3 - Verificar que los Píxeles se Dibujan en la Superficie (NumPy) ---
                    # Verificar que los píxeles se dibujan correctamente en la superficie después de dibujar
                    if hasattr(self, 'surface') and self.surface is not None:
                        if not hasattr(self, '_pixel_draw_verify_count'):
                            self._pixel_draw_verify_count = 0
                        
                        self._pixel_draw_verify_count += 1
                        
                        if self._pixel_draw_verify_count <= 50:
                            # Verificar píxeles en la superficie (primeros 20 píxeles de la primera línea)
                            surface_pixels = []
                            for x in range(min(20, 160)):
                                pixel_color = self.surface.get_at((x, 0)) if hasattr(self.surface, 'get_at') else None
                                if pixel_color:
                                    surface_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
                            
                            logger.info(f"[Renderer-Pixel-Draw] Frame {self._pixel_draw_verify_count} | "
                                       f"Surface pixels (first 20): {surface_pixels}")
                            print(f"[Renderer-Pixel-Draw] Frame {self._pixel_draw_verify_count} | "
                                  f"Surface pixels (first 20): {surface_pixels}")
                            
                            # Verificar que hay píxeles negros (índice 3 → RGB(0,0,0))
                            black_pixels = [p for p in surface_pixels if p == (0, 0, 0)]
                            # Obtener sample_indices del framebuffer para comparar
                            if frame_indices is not None and len(frame_indices) >= 20:
                                sample_indices_check = [frame_indices[i] & 0x03 for i in range(min(20, len(frame_indices)))]
                                if any(idx == 3 for idx in sample_indices_check) and len(black_pixels) == 0:
                                    logger.warning("[Renderer-Pixel-Draw] ⚠️ PROBLEMA: No hay píxeles negros en la superficie aunque el framebuffer tiene índice 3!")
                                    print("[Renderer-Pixel-Draw] ⚠️ PROBLEMA: No hay píxeles negros en la superficie aunque el framebuffer tiene índice 3!")
                    # -------------------------------------------
                    
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
                    
                    # --- Step 0337: Verificación de Aplicación de Paleta en PixelArray ---
                    if not hasattr(self, '_pixelarray_palette_check_count'):
                        self._pixelarray_palette_check_count = 0
                    
                    if self._pixelarray_palette_check_count < 10:
                        self._pixelarray_palette_check_count += 1
                        
                        # Verificar algunos píxeles después de escribir en PixelArray
                        test_pixels = [(0, 0), (80, 72), (159, 143)]
                        for x, y in test_pixels:
                            idx = y * 160 + x
                            if idx < len(frame_indices):
                                original_index = frame_indices[idx] & 0x03
                                expected_rgb = palette[original_index]
                                
                                # Leer el color del PixelArray después de escribirlo
                                actual_rgb = self._px_array_surface.get_at((x, y))
                                
                                print(f"[Renderer-PixelArray-Palette] Frame {self._pixelarray_palette_check_count} | "
                                      f"Pixel ({x}, {y}): index={original_index} | "
                                      f"Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                                logger.info(f"[Renderer-PixelArray-Palette] Frame {self._pixelarray_palette_check_count} | "
                                           f"Pixel ({x}, {y}): index={original_index} | "
                                           f"Expected RGB={expected_rgb} | Actual RGB={actual_rgb}")
                                
                                if actual_rgb != expected_rgb:
                                    print(f"[Renderer-PixelArray-Palette] ⚠️ PROBLEMA: RGB no coincide!")
                                    logger.warning(f"[Renderer-PixelArray-Palette] ⚠️ PROBLEMA: RGB no coincide!")
                    # -------------------------------------------
                    
                    px_array.close()
                    self.surface = self._px_array_surface
                    
                    # --- Step 0375: Tarea 3 - Verificar que los Píxeles se Dibujan en la Superficie (PixelArray) ---
                    # Verificar que los píxeles se dibujan correctamente en la superficie después de dibujar
                    if hasattr(self, 'surface') and self.surface is not None:
                        if not hasattr(self, '_pixel_draw_verify_count_pxarray'):
                            self._pixel_draw_verify_count_pxarray = 0
                        
                        self._pixel_draw_verify_count_pxarray += 1
                        
                        if self._pixel_draw_verify_count_pxarray <= 50:
                            # Verificar píxeles en la superficie (primeros 20 píxeles de la primera línea)
                            surface_pixels = []
                            for x in range(min(20, 160)):
                                pixel_color = self.surface.get_at((x, 0)) if hasattr(self.surface, 'get_at') else None
                                if pixel_color:
                                    surface_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
                            
                            logger.info(f"[Renderer-Pixel-Draw] Frame {self._pixel_draw_verify_count_pxarray} (PixelArray) | "
                                       f"Surface pixels (first 20): {surface_pixels}")
                            print(f"[Renderer-Pixel-Draw] Frame {self._pixel_draw_verify_count_pxarray} (PixelArray) | "
                                  f"Surface pixels (first 20): {surface_pixels}")
                            
                            # Verificar que hay píxeles negros (índice 3 → RGB(0,0,0))
                            black_pixels = [p for p in surface_pixels if p == (0, 0, 0)]
                            # Obtener sample_indices del framebuffer para comparar
                            if frame_indices is not None and len(frame_indices) >= 20:
                                sample_indices_check = [frame_indices[i] & 0x03 for i in range(min(20, len(frame_indices)))]
                                if any(idx == 3 for idx in sample_indices_check) and len(black_pixels) == 0:
                                    logger.warning("[Renderer-Pixel-Draw] ⚠️ PROBLEMA: No hay píxeles negros en la superficie aunque el framebuffer tiene índice 3!")
                                    print("[Renderer-Pixel-Draw] ⚠️ PROBLEMA: No hay píxeles negros en la superficie aunque el framebuffer tiene índice 3!")
                    # -------------------------------------------
                
                render_time = (time.time() - render_start) * 1000  # en milisegundos
                
                # --- Step 0365: Verificación de la Superficie Después de Dibujar ---
                # Verificar que los píxeles se dibujan correctamente en la superficie
                if not hasattr(self, '_renderer_check_count'):
                    self._renderer_check_count = 0
                if self._renderer_check_count <= 20 and hasattr(self, 'surface') and self.surface is not None:
                    # Verificar que la superficie tiene datos
                    sample_pixels = []
                    for y in range(min(5, 144)):  # SCREEN_HEIGHT = 144
                        for x in range(min(5, 160)):  # SCREEN_WIDTH = 160
                            pixel = self.surface.get_at((x, y))
                            sample_pixels.append(pixel)
                    
                    log_msg = f"[Renderer-Surface] First 25 pixels on surface: {sample_pixels}"
                    print(log_msg, flush=True)
                    logger.info(log_msg)
                    
                    # Verificar que no todos son blancos
                    white_count = sum(1 for p in sample_pixels if p == (255, 255, 255))
                    if white_count == len(sample_pixels):
                        log_msg = f"[Renderer-Surface] ⚠️ PROBLEMA: Todos los píxeles en la superficie son blancos!"
                        print(log_msg, flush=True)
                        logger.warning(log_msg)
                # ----------------------------------------
                
                # --- Step 0363: Diagnóstico de Rendimiento en Renderer ---
                # Reportar tiempo de renderizado cada 60 frames
                if not hasattr(self, '_render_perf_frame_count'):
                    self._render_perf_frame_count = 0
                self._render_perf_frame_count += 1
                
                if self._render_perf_frame_count % 60 == 0:
                    logger.info(f"[Viboy-Perf] Frame {self._render_perf_frame_count} | "
                               f"Render: {render_time:.2f}ms")
                    print(f"[Viboy-Perf] Frame {self._render_perf_frame_count} | "
                          f"Render: {render_time:.2f}ms", flush=True)
                # ----------------------------------------
                
                # --- Step 0341: Verificación del Dibujo de Píxeles en Pygame ---
                # Verificar que los píxeles se dibujan correctamente en la superficie
                if not hasattr(self, '_pixel_draw_check_count_step0341'):
                    self._pixel_draw_check_count_step0341 = 0
                
                if hasattr(self, 'surface') and self.surface is not None and self._pixel_draw_check_count_step0341 < 10:
                    self._pixel_draw_check_count_step0341 += 1
                    
                    # Verificar algunos píxeles después de dibujarlos
                    test_pixels = [
                        (0, 0),      # Esquina superior izquierda
                        (80, 72),    # Centro
                        (159, 143),  # Esquina inferior derecha
                    ]
                    
                    logger.info(f"[Renderer-Pixel-Draw] Frame {self._pixel_draw_check_count_step0341} | "
                               f"Verificando píxeles dibujados en la superficie:")
                    for x, y in test_pixels:
                        # Leer el color de la superficie después de dibujar
                        surface_color = self.surface.get_at((x, y))
                        
                        # Obtener el índice original del framebuffer
                        idx = y * 160 + x
                        if idx < len(frame_indices):
                            original_index = frame_indices[idx] & 0x03
                            expected_rgb = palette[original_index]
                            
                            logger.info(f"[Renderer-Pixel-Draw] Pixel (x={x}, y={y}): "
                                       f"original_index={original_index}, expected_RGB={expected_rgb}, "
                                       f"surface_RGB={surface_color}")
                            
                            # Verificar que el color coincide (tolerancia pequeña para interpolación)
                            if abs(surface_color[0] - expected_rgb[0]) > 5 or \
                               abs(surface_color[1] - expected_rgb[1]) > 5 or \
                               abs(surface_color[2] - expected_rgb[2]) > 5:
                                logger.warning(f"[Renderer-Pixel-Draw] ⚠️ PROBLEMA: Color no coincide! "
                                             f"Expected: {expected_rgb}, Actual: {surface_color}")
                # -------------------------------------------
                
                # --- Step 0347: Verificación Línea por Línea de la Visualización ---
                # Verificar cada línea de la superficie después de dibujar
                if not hasattr(self, '_line_by_line_check_count'):
                    self._line_by_line_check_count = 0

                if hasattr(self, 'surface') and self.surface is not None and \
                   frame_indices is not None and len(frame_indices) == 23040 and \
                   self._line_by_line_check_count < 5:
                    self._line_by_line_check_count += 1
                    
                    # Verificar algunas líneas específicas
                    test_lines = [0, 36, 72, 108, 143]  # Distribuidas uniformemente
                    
                    logger.info(f"[Renderer-Line-by-Line] Frame {self._line_by_line_check_count} | "
                               f"Verificando líneas: {test_lines}")
                    print(f"[Renderer-Line-by-Line] Frame {self._line_by_line_check_count} | "
                          f"Verificando líneas: {test_lines}")
                    
                    for y in test_lines:
                        line_start = y * 160
                        matches = 0
                        mismatches = 0
                        
                        # Verificar primeros 10 píxeles de la línea
                        for x in range(min(10, 160)):
                            idx = line_start + x
                            if idx < len(frame_indices):
                                # Índice del framebuffer
                                framebuffer_idx = frame_indices[idx] & 0x03
                                expected_rgb = palette[framebuffer_idx]
                                
                                # Color en la superficie
                                if x < self.surface.get_width() and y < self.surface.get_height():
                                    surface_color = self.surface.get_at((x, y))
                                    
                                    # Comparar (tolerancia pequeña)
                                    if abs(surface_color[0] - expected_rgb[0]) <= 5 and \
                                       abs(surface_color[1] - expected_rgb[1]) <= 5 and \
                                       abs(surface_color[2] - expected_rgb[2]) <= 5:
                                        matches += 1
                                    else:
                                        mismatches += 1
                                        if mismatches <= 3:  # Solo loggear primeros 3 desajustes
                                            logger.warning(f"[Renderer-Line-by-Line] Line {y}, Pixel ({x}, {y}): "
                                                         f"Mismatch! Expected={expected_rgb}, Actual={surface_color}")
                                            print(f"[Renderer-Line-by-Line] Line {y}, Pixel ({x}, {y}): "
                                                  f"Mismatch! Expected={expected_rgb}, Actual={surface_color}")
                        
                        logger.info(f"[Renderer-Line-by-Line] Line {y}: Matches={matches}/10, Mismatches={mismatches}/10")
                        print(f"[Renderer-Line-by-Line] Line {y}: Matches={matches}/10, Mismatches={mismatches}/10")
                # -------------------------------------------
                
                # --- Step 0342: Verificación de Correspondencia Entre Framebuffer y Visualización ---
                # Verificar que el contenido del framebuffer se refleja correctamente en la visualización
                if not hasattr(self, '_framebuffer_visualization_correspondence_count'):
                    self._framebuffer_visualization_correspondence_count = 0

                if hasattr(self, 'surface') and self.surface is not None and \
                   frame_indices is not None and len(frame_indices) > 0 and \
                   self._framebuffer_visualization_correspondence_count < 20:
                    self._framebuffer_visualization_correspondence_count += 1
                    
                    # Verificar algunas líneas horizontales completas
                    test_lines = [0, 72, 143]  # Primera línea, línea central, última línea
                    
                    print(f"[Renderer-Framebuffer-Visualization-Correspondence] Frame {self._framebuffer_visualization_correspondence_count} | "
                          f"Verificando correspondencia entre framebuffer y visualización:")
                    logger.info(f"[Renderer-Framebuffer-Visualization-Correspondence] Frame {self._framebuffer_visualization_correspondence_count} | "
                               f"Verificando correspondencia entre framebuffer y visualización:")
                    
                    for y in test_lines:
                        if y * 160 < len(frame_indices):
                            # Leer primeros 10 píxeles de la línea del framebuffer
                            line_start = y * 160
                            framebuffer_line = [frame_indices[line_start + x] & 0x03 
                                               for x in range(min(10, 160, len(frame_indices) - line_start))]
                            
                            # Leer los mismos píxeles de la superficie después de dibujar
                            surface_line = []
                            for x in range(min(10, 160)):
                                if x < self.surface.get_width() and y < self.surface.get_height():
                                    surface_color = self.surface.get_at((x, y))
                                    # Convertir RGB a índice aproximado (buscar en la paleta)
                                    surface_line.append(surface_color)
                            
                            logger.info(f"[Renderer-Framebuffer-Visualization-Correspondence] Line {y} | "
                                       f"Framebuffer (first 10): {framebuffer_line} | "
                                       f"Surface (first 10): {surface_line}")
                            
                            # Verificar que los colores coinciden (tolerancia para interpolación)
                            matches = 0
                            for x in range(min(10, len(framebuffer_line), len(surface_line))):
                                expected_rgb = palette[framebuffer_line[x]]
                                actual_rgb = surface_line[x]
                                
                                if abs(actual_rgb[0] - expected_rgb[0]) <= 5 and \
                                   abs(actual_rgb[1] - expected_rgb[1]) <= 5 and \
                                   abs(actual_rgb[2] - expected_rgb[2]) <= 5:
                                    matches += 1
                            
                            logger.info(f"[Renderer-Framebuffer-Visualization-Correspondence] Line {y} | "
                                       f"Matches: {matches}/10 píxeles coinciden")
                            
                            if matches < 8:
                                logger.warning(f"[Renderer-Framebuffer-Visualization-Correspondence] ⚠️ "
                                             f"Solo {matches}/10 píxeles coinciden en línea {y}!")
                # -------------------------------------------
                
                # --- STEP 0334: CORRECCIÓN CRÍTICA - Actualizar Cache en Cada Frame ---
                # PROBLEMA: El cache de escalado solo se actualizaba si cambiaba el tamaño de pantalla,
                # no cuando cambiaba el contenido. Esto causaba que se mostrara el primer frame
                # (checkerboard) y luego pantalla blanca cuando el contenido cambiaba.
                # 
                # SOLUCIÓN: Actualizar el cache en cada frame para reflejar el contenido actual
                current_screen_size = self.screen.get_size()
                
                # Siempre reescalar la superficie actualizada (el contenido cambia en cada frame)
                self._scaled_surface_cache = pygame.transform.scale(self.surface, current_screen_size)
                self._cache_screen_size = current_screen_size
                
                # --- Step 0375: Tarea 6 - Verificación de Superficie Escalada ---
                # Verificar que self._scaled_surface_cache tiene los píxeles correctos después del escalado
                if not hasattr(self, '_surface_scaled_verify_count'):
                    self._surface_scaled_verify_count = 0
                
                self._surface_scaled_verify_count += 1
                
                if self._surface_scaled_verify_count <= 10:
                    # Leer algunos píxeles de la superficie escalada y comparar con la superficie original
                    test_pixels = [(0, 0), (80, 72), (159, 143)]
                    scale_x = current_screen_size[0] / 160
                    scale_y = current_screen_size[1] / 144
                    
                    for x, y in test_pixels:
                        # Color de la superficie original
                        original_color = self.surface.get_at((x, y))[:3] if hasattr(self.surface, 'get_at') else None
                        
                        # Color de la superficie escalada (escalar las coordenadas)
                        scaled_x = int(x * scale_x)
                        scaled_y = int(y * scale_y)
                        if scaled_x < current_screen_size[0] and scaled_y < current_screen_size[1]:
                            scaled_color = self._scaled_surface_cache.get_at((scaled_x, scaled_y))[:3] if hasattr(self._scaled_surface_cache, 'get_at') else None
                            
                            logger.info(f"[Renderer-Surface-Scaled] Frame {self._surface_scaled_verify_count} | "
                                       f"Pixel ({x}, {y}) → ({scaled_x}, {scaled_y}) | "
                                       f"Original: {original_color} | Scaled: {scaled_color}")
                            print(f"[Renderer-Surface-Scaled] Frame {self._surface_scaled_verify_count} | "
                                  f"Pixel ({x}, {y}) → ({scaled_x}, {scaled_y}) | "
                                  f"Original: {original_color} | Scaled: {scaled_color}")
                            
                            # Verificar que el escalado no está corrompiendo los datos (deben ser similares)
                            if original_color and scaled_color:
                                # Permitir pequeñas diferencias debido al escalado (interpolación)
                                diff = sum(abs(original_color[i] - scaled_color[i]) for i in range(3))
                                if diff > 50:  # Umbral de diferencia aceptable
                                    logger.warning(f"[Renderer-Surface-Scaled] ⚠️ PROBLEMA: Diferencia grande en pixel ({x}, {y}): diff={diff}")
                                    print(f"[Renderer-Surface-Scaled] ⚠️ PROBLEMA: Diferencia grande en pixel ({x}, {y}): diff={diff}")
                # -------------------------------------------
                
                # --- Step 0337: Verificación de Escalado ---
                if not hasattr(self, '_scale_check_count'):
                    self._scale_check_count = 0
                
                if self._scale_check_count < 10:
                    self._scale_check_count += 1
                    
                    # Verificar algunos píxeles antes y después del escalado
                    test_pixels = [(0, 0), (80, 72), (159, 143)]
                    for x, y in test_pixels:
                        # Color antes del escalado (superficie original 160x144)
                        original_color = self.surface.get_at((x, y))
                        
                        # Calcular posición escalada
                        scale_x = int(x * self.screen.get_width() / 160)
                        scale_y = int(y * self.screen.get_height() / 144)
                        
                        # Color después del escalado (superficie escalada)
                        if hasattr(self, '_scaled_surface_cache'):
                            scaled_color = self._scaled_surface_cache.get_at((scale_x, scale_y))
                            
                            print(f"[Renderer-Scale] Frame {self._scale_check_count} | "
                                  f"Pixel ({x}, {y}) -> ({scale_x}, {scale_y}) | "
                                  f"Original RGB={original_color} | Scaled RGB={scaled_color}")
                            logger.info(f"[Renderer-Scale] Frame {self._scale_check_count} | "
                                       f"Pixel ({x}, {y}) -> ({scale_x}, {scale_y}) | "
                                       f"Original RGB={original_color} | Scaled RGB={scaled_color}")
                            
                            # Verificar que los colores son similares (pueden diferir ligeramente por interpolación)
                            if abs(original_color[0] - scaled_color[0]) > 10 or \
                               abs(original_color[1] - scaled_color[1]) > 10 or \
                               abs(original_color[2] - scaled_color[2]) > 10:
                                print(f"[Renderer-Scale] ⚠️ ADVERTENCIA: Diferencia significativa en RGB después del escalado")
                                logger.warning(f"[Renderer-Scale] ⚠️ ADVERTENCIA: Diferencia significativa en RGB después del escalado")
                # -------------------------------------------
                
                # --- Step 0341: Verificación del Escalado y Visualización Final ---
                # Verificar que el escalado no causa artefactos
                if not hasattr(self, '_scale_visualization_check_count'):
                    self._scale_visualization_check_count = 0
                
                if hasattr(self, '_scaled_surface_cache') and self._scaled_surface_cache is not None and \
                   frame_indices is not None and len(frame_indices) > 0 and \
                   self._scale_visualization_check_count < 10:
                    # Agregar verificación de tamaño
                    if len(frame_indices) != 23040:
                        logger.warning(f"[Renderer-Scale-Visualization] ⚠️ Tamaño inesperado: {len(frame_indices)} (esperado: 23040)")
                    
                    self._scale_visualization_check_count += 1
                    
                    # Verificar algunos píxeles antes y después del escalado
                    test_pixels = [
                        (0, 0),      # Esquina superior izquierda
                        (80, 72),    # Centro
                        (159, 143),  # Esquina inferior derecha
                    ]
                    
                    logger.info(f"[Renderer-Scale-Visualization] Frame {self._scale_visualization_check_count} | "
                               f"Verificando escalado:")
                    for x, y in test_pixels:
                        # Color antes del escalado (superficie original 160x144)
                        original_color = self.surface.get_at((x, y))
                        
                        # Calcular posición escalada
                        scale_x = int(x * self.screen.get_width() / 160)
                        scale_y = int(y * self.screen.get_height() / 144)
                        
                        # Color después del escalado (superficie escalada)
                        scaled_color = self._scaled_surface_cache.get_at((scale_x, scale_y))
                        
                        logger.info(f"[Renderer-Scale-Visualization] Pixel (x={x}, y={y}): "
                                   f"original_RGB={original_color}, scaled_RGB={scaled_color}, "
                                   f"scale_pos=({scale_x}, {scale_y})")
                        
                        # Verificar que el color escalado es similar al original (tolerancia para interpolación)
                        if abs(original_color[0] - scaled_color[0]) > 20 or \
                           abs(original_color[1] - scaled_color[1]) > 20 or \
                           abs(original_color[2] - scaled_color[2]) > 20:
                            logger.warning(f"[Renderer-Scale-Visualization] ⚠️ PROBLEMA: Color escalado muy diferente! "
                                         f"Original: {original_color}, Scaled: {scaled_color}")
                # -------------------------------------------
                
                # Usar superficie escalada actualizada
                # --- Step 0359: Verificación Renderizado Python ---
                # Verificar que el renderizado funciona correctamente
                if frame_indices and len(frame_indices) == 23040:
                    non_white_count = sum(1 for idx in frame_indices[:1000] if idx != 0)
                    
                    if non_white_count > 50:
                        # Hay tiles reales
                        if not hasattr(self, '_renderer_verify_count'):
                            self._renderer_verify_count = 0
                        
                        if self._renderer_verify_count < 10:
                            self._renderer_verify_count += 1
                            
                            logger.info(f"[Renderer-Verify] Framebuffer con tiles | "
                                       f"Non-white pixels (first 1000): {non_white_count}/1000")
                            
                            # Verificar conversión de índices a RGB
                            # Usar la misma paleta que se usa en el renderizado (debug_palette_map)
                            debug_palette_map = {
                                0: (255, 255, 255),  # 00: White
                                1: (170, 170, 170),  # 01: Light Gray
                                2: (85, 85, 85),     # 10: Dark Gray
                                3: (8, 24, 32)       # 11: Black
                            }
                            palette_used = [
                                debug_palette_map[0],
                                debug_palette_map[1],
                                debug_palette_map[2],
                                debug_palette_map[3]
                            ]
                            sample_indices = list(frame_indices[0:20])
                            sample_rgb = [palette_used[idx] for idx in sample_indices]
                            
                            logger.info(f"[Renderer-Verify] Sample indices: {sample_indices[:10]}")
                            logger.info(f"[Renderer-Verify] Sample RGB: {sample_rgb[:10]}")
                            
                            # Verificar que los colores RGB no son todos blancos
                            all_white = all(rgb == (255, 255, 255) for rgb in sample_rgb[:10])
                            if all_white:
                                logger.warning(f"[Renderer-Verify] ⚠️ ADVERTENCIA: Todos los colores son blancos!")
                            
                            # Verificar que los píxeles se dibujaron en la superficie
                            if hasattr(self, 'surface') and self.surface is not None:
                                sample_pixels = []
                                for i in range(10):
                                    x, y = i % 160, i // 160
                                    if x < self.surface.get_width() and y < self.surface.get_height():
                                        pixel_color = self.surface.get_at((x, y))
                                        sample_pixels.append(pixel_color[:3])  # RGB sin alpha
                                
                                logger.info(f"[Renderer-Verify] Sample pixels from surface: {sample_pixels[:10]}")
                                
                                # Comparar con RGB esperado
                                matches = sum(1 for i in range(min(10, len(sample_pixels))) 
                                            if sample_pixels[i] == sample_rgb[i])
                                logger.info(f"[Renderer-Verify] Pixel verification: {matches}/10 matches")
                            
                            # Verificar que el escalado y blit funcionan
                            if hasattr(self, '_scaled_surface_cache') and self._scaled_surface_cache is not None:
                                screen_pixels = []
                                for i in range(10):
                                    x, y = (i % 160) * self.scale, (i // 160) * self.scale
                                    if x < self.screen.get_width() and y < self.screen.get_height():
                                        pixel_color = self.screen.get_at((x, y))
                                        screen_pixels.append(pixel_color[:3])
                                
                                logger.info(f"[Renderer-Verify] Sample pixels from screen (before flip): {screen_pixels[:10]}")
                # -------------------------------------------
                
                self.screen.blit(self._scaled_surface_cache, (0, 0))
                
                # --- Step 0375: Tarea 4 - Verificar Escalado y Blit ---
                # Verificar que los píxeles se copian correctamente a la pantalla después del escalado y blit
                if not hasattr(self, '_scale_blit_verify_count'):
                    self._scale_blit_verify_count = 0
                
                self._scale_blit_verify_count += 1
                
                if self._scale_blit_verify_count <= 50:
                    # Verificar píxeles en la pantalla después del blit (primeros 20 píxeles escalados)
                    screen_pixels = []
                    scale_x = self.window_width // 160
                    scale_y = self.window_height // 144
                    
                    for x in range(min(20, 160)):
                        screen_x = x * scale_x
                        if screen_x < self.window_width:
                            pixel_color = self.screen.get_at((screen_x, 0)) if hasattr(self.screen, 'get_at') else None
                            if pixel_color:
                                screen_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
                    
                    logger.info(f"[Renderer-Scale-Blit] Frame {self._scale_blit_verify_count} | "
                               f"Screen pixels after blit (first 20): {screen_pixels}")
                    print(f"[Renderer-Scale-Blit] Frame {self._scale_blit_verify_count} | "
                          f"Screen pixels after blit (first 20): {screen_pixels}")
                    
                    # Verificar que hay píxeles negros en la pantalla
                    black_pixels = [p for p in screen_pixels if p == (0, 0, 0)]
                    if len(black_pixels) == 0:
                        logger.warning("[Renderer-Scale-Blit] ⚠️ PROBLEMA: No hay píxeles negros en la pantalla después del blit!")
                        print("[Renderer-Scale-Blit] ⚠️ PROBLEMA: No hay píxeles negros en la pantalla después del blit!")
                # -------------------------------------------
                
                # Actualizamos la pantalla
                pygame.display.flip()
                
                # --- Step 0359: Verificación Después del Flip ---
                # Verificar que la pantalla se actualizó correctamente después del flip
                if frame_indices and len(frame_indices) == 23040:
                    non_white_count = sum(1 for idx in frame_indices[:1000] if idx != 0)
                    
                    if non_white_count > 50:
                        if hasattr(self, '_renderer_verify_count') and self._renderer_verify_count <= 10:
                            # Usar la misma paleta que se usa en el renderizado (debug_palette_map)
                            debug_palette_map = {
                                0: (255, 255, 255),  # 00: White
                                1: (170, 170, 170),  # 01: Light Gray
                                2: (85, 85, 85),     # 10: Dark Gray
                                3: (8, 24, 32)       # 11: Black
                            }
                            palette_used = [
                                debug_palette_map[0],
                                debug_palette_map[1],
                                debug_palette_map[2],
                                debug_palette_map[3]
                            ]
                            sample_indices = list(frame_indices[0:20])
                            sample_rgb = [palette_used[idx] for idx in sample_indices]
                            
                            # Verificar después del flip
                            screen_pixels_after = []
                            for i in range(10):
                                x, y = (i % 160) * self.scale, (i // 160) * self.scale
                                if x < self.screen.get_width() and y < self.screen.get_height():
                                    pixel_color = self.screen.get_at((x, y))
                                    screen_pixels_after.append(pixel_color[:3])
                            
                            logger.info(f"[Renderer-Verify] Sample pixels after flip: {screen_pixels_after[:10]}")
                            
                            # Comparar
                            matches_after = sum(1 for i in range(min(10, len(screen_pixels_after))) 
                                              if screen_pixels_after[i] == sample_rgb[i])
                            logger.info(f"[Renderer-Verify] Screen verification: {matches_after}/10 matches")
                # -------------------------------------------
                # ----------------------------------------
                
                # --- Step 0347: Verificación del Escalado y Blit ---
                # Verificar que el escalado y blit funcionan correctamente
                if not hasattr(self, '_scale_blit_check_count'):
                    self._scale_blit_check_count = 0

                if hasattr(self, '_scaled_surface_cache') and self._scaled_surface_cache is not None and \
                   hasattr(self, 'surface') and self.surface is not None and \
                   self._scale_blit_check_count < 10:
                    self._scale_blit_check_count += 1
                    
                    # Verificar tamaño de la superficie escalada
                    scaled_size = self._scaled_surface_cache.get_size()
                    screen_size = self.screen.get_size()
                    
                    logger.info(f"[Renderer-Scale-Blit] Frame {self._scale_blit_check_count} | "
                               f"Scaled surface size: {scaled_size} | Screen size: {screen_size}")
                    print(f"[Renderer-Scale-Blit] Frame {self._scale_blit_check_count} | "
                          f"Scaled surface size: {scaled_size} | Screen size: {screen_size}")
                    
                    # Verificar algunos píxeles antes y después del escalado
                    test_pixels = [(0, 0), (80, 72), (159, 143)]
                    
                    for x, y in test_pixels:
                        # Color en la superficie original (160x144)
                        if x < self.surface.get_width() and y < self.surface.get_height():
                            original_color = self.surface.get_at((x, y))
                            
                            # Calcular posición escalada
                            scale_x = int(x * screen_size[0] / 160)
                            scale_y = int(y * screen_size[1] / 144)
                            
                            # Color en la superficie escalada
                            if scale_x < scaled_size[0] and scale_y < scaled_size[1]:
                                scaled_color = self._scaled_surface_cache.get_at((scale_x, scale_y))
                                
                                # Color en la pantalla después del blit
                                screen_color = self.screen.get_at((scale_x, scale_y))
                                
                                logger.info(f"[Renderer-Scale-Blit] Pixel ({x}, {y}): "
                                           f"Original={original_color} | Scaled={scaled_color} | Screen={screen_color}")
                                print(f"[Renderer-Scale-Blit] Pixel ({x}, {y}): "
                                      f"Original={original_color} | Scaled={scaled_color} | Screen={screen_color}")
                                
                                # Verificar que los colores son similares (tolerancia para interpolación)
                                if abs(original_color[0] - scaled_color[0]) > 20 or \
                                   abs(original_color[1] - scaled_color[1]) > 20 or \
                                   abs(original_color[2] - scaled_color[2]) > 20:
                                    logger.warning(f"[Renderer-Scale-Blit] ⚠️ Color escalado muy diferente!")
                                    print(f"[Renderer-Scale-Blit] ⚠️ Color escalado muy diferente!")
                                
                                if abs(scaled_color[0] - screen_color[0]) > 5 or \
                                   abs(scaled_color[1] - screen_color[1]) > 5 or \
                                   abs(scaled_color[2] - screen_color[2]) > 5:
                                    logger.warning(f"[Renderer-Scale-Blit] ⚠️ Color en pantalla diferente al escalado!")
                                    print(f"[Renderer-Scale-Blit] ⚠️ Color en pantalla diferente al escalado!")
                # -------------------------------------------
                
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
                
                # --- Step 0348: Verificación de Actualización de Pantalla (dentro del bloque PPU C++) ---
                # Verificar que la pantalla se actualiza correctamente después de flip()
                # NOTA: Este código debe ejecutarse ANTES del return para que se ejecute cuando se usa PPU C++
                if not hasattr(self, '_screen_update_entry_count'):
                    self._screen_update_entry_count = 0
                
                self._screen_update_entry_count += 1
                if self._screen_update_entry_count <= 5:
                    logger.info(f"[Renderer-Screen-Update-Entry] Frame {self._screen_update_entry_count} | "
                               f"Entrando a verificación de pantalla")
                    print(f"[Renderer-Screen-Update-Entry] Frame {self._screen_update_entry_count} | "
                          f"Entrando a verificación de pantalla")
                
                if not hasattr(self, '_screen_update_check_count'):
                    self._screen_update_check_count = 0
                
                # --- Step 0350: Debug de Condiciones de Verificación de Pantalla ---
                if not hasattr(self, '_screen_update_debug_count'):
                    self._screen_update_debug_count = 0
                
                self._screen_update_debug_count += 1
                if self._screen_update_debug_count <= 5:
                    has_screen = hasattr(self, 'screen') and self.screen is not None
                    has_frame_indices = hasattr(self, '_current_frame_indices') and self._current_frame_indices is not None
                    logger.info(f"[Renderer-Screen-Update-Debug] Frame {self._screen_update_debug_count} | "
                               f"has_screen={has_screen}, has_frame_indices={has_frame_indices}, "
                               f"check_count={self._screen_update_check_count}")
                    print(f"[Renderer-Screen-Update-Debug] Frame {self._screen_update_debug_count} | "
                          f"has_screen={has_screen}, has_frame_indices={has_frame_indices}, "
                          f"check_count={self._screen_update_check_count}")
                # -------------------------------------------
                
                if hasattr(self, 'screen') and self.screen is not None and \
                   hasattr(self, '_current_frame_indices') and self._current_frame_indices is not None and \
                   self._screen_update_check_count < 10:
                    self._screen_update_check_count += 1
                    
                    # Verificar algunos píxeles en la pantalla después de flip()
                    test_pixels = [(0, 0), (80, 72), (159, 143)]
                    
                    logger.info(f"[Renderer-Screen-Update] Frame {self._screen_update_check_count} | "
                               f"Verificando pantalla después de flip():")
                    print(f"[Renderer-Screen-Update] Frame {self._screen_update_check_count} | "
                          f"Verificando pantalla después de flip():")
                    
                    # Usar self._current_frame_indices en lugar de frame_indices
                    frame_indices = self._current_frame_indices
                    
                    for x, y in test_pixels:
                        # Calcular posición escalada
                        scale_x = int(x * self.screen.get_width() / 160)
                        scale_y = int(y * self.screen.get_height() / 144)
                        
                        # Color en la pantalla después de flip()
                        if scale_x < self.screen.get_width() and scale_y < self.screen.get_height():
                            screen_color = self.screen.get_at((scale_x, scale_y))
                            
                            # Obtener índice original del framebuffer
                            idx = y * 160 + x
                            if idx < len(frame_indices):
                                framebuffer_idx = frame_indices[idx] & 0x03
                                expected_rgb = palette[framebuffer_idx]
                                
                                logger.info(f"[Renderer-Screen-Update] Pixel ({x}, {y}): "
                                           f"Framebuffer index={framebuffer_idx}, Expected RGB={expected_rgb}, "
                                           f"Screen RGB={screen_color}")
                                print(f"[Renderer-Screen-Update] Pixel ({x}, {y}): "
                                      f"Framebuffer index={framebuffer_idx}, Expected RGB={expected_rgb}, "
                                      f"Screen RGB={screen_color}")
                                
                                # Verificar que los colores coinciden (tolerancia para interpolación)
                                if abs(screen_color[0] - expected_rgb[0]) > 10 or \
                                   abs(screen_color[1] - expected_rgb[1]) > 10 or \
                                   abs(screen_color[2] - expected_rgb[2]) > 10:
                                    logger.warning(f"[Renderer-Screen-Update] ⚠️ Color en pantalla no coincide!")
                                    print(f"[Renderer-Screen-Update] ⚠️ Color en pantalla no coincide!")
                # -------------------------------------------
                
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
        
        # --- Step 0374: Tarea 6 - Verificar si el Buffer se Llena con Blanco Antes de Dibujar ---
        # Verificar el orden: buffer.fill() debe ejecutarse ANTES de dibujar los píxeles
        if not hasattr(self, '_buffer_fill_verify_count'):
            self._buffer_fill_verify_count = 0
        
        self._buffer_fill_verify_count += 1
        
        if self._buffer_fill_verify_count <= 50:
            logger.info(f"[Renderer-Buffer-Fill] Frame {self._buffer_fill_verify_count} | "
                       f"Verificando orden de buffer.fill() y dibujo de píxeles")
            print(f"[Renderer-Buffer-Fill] Frame {self._buffer_fill_verify_count} | "
                  f"Verificando orden de buffer.fill() y dibujo de píxeles")
            # NOTA: buffer.fill() se ejecuta ANTES de dibujar (línea siguiente), esto es correcto
        # -------------------------------------------
        
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
        
        # --- Step 0374: Tarea 3 (Método Python) - Verificar que los Píxeles se Dibujan en el Buffer ---
        # Verificar que los píxeles se dibujan correctamente en self.buffer después de dibujar
        if hasattr(self, 'buffer') and self.buffer is not None:
            if not hasattr(self, '_pixel_draw_verify_count_python'):
                self._pixel_draw_verify_count_python = 0
            
            self._pixel_draw_verify_count_python += 1
            
            if self._pixel_draw_verify_count_python <= 50:
                # Verificar píxeles en el buffer (primeros 20 píxeles de la primera línea)
                buffer_pixels = []
                for x in range(min(20, 160)):
                    pixel_color = self.buffer.get_at((x, 0)) if hasattr(self.buffer, 'get_at') else None
                    if pixel_color:
                        buffer_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
                
                logger.info(f"[Renderer-Pixel-Draw-Python] Frame {self._pixel_draw_verify_count_python} | "
                           f"Buffer pixels (first 20): {buffer_pixels}")
                print(f"[Renderer-Pixel-Draw-Python] Frame {self._pixel_draw_verify_count_python} | "
                      f"Buffer pixels (first 20): {buffer_pixels}")
                
                # Verificar que hay píxeles negros (índice 3 → RGB(0,0,0))
                black_pixels = [p for p in buffer_pixels if p == (0, 0, 0)]
                if len(black_pixels) == 0:
                    logger.warning("[Renderer-Pixel-Draw-Python] ⚠️ PROBLEMA: No hay píxeles negros en el buffer después de dibujar!")
                    print("[Renderer-Pixel-Draw-Python] ⚠️ PROBLEMA: No hay píxeles negros en el buffer después de dibujar!")
        # -------------------------------------------
        
        # Escalar el framebuffer a la ventana y hacer blit
        # pygame.transform.scale es rápido porque opera sobre una superficie completa
        scaled_buffer = pygame.transform.scale(self.buffer, (self.window_width, self.window_height))
        self.screen.blit(scaled_buffer, (0, 0))
        
        # --- Step 0374: Tarea 4 (Método Python) - Verificar Escalado y Blit ---
        # Verificar que los píxeles se copian correctamente a la pantalla después del escalado y blit
        if not hasattr(self, '_scale_blit_verify_count_python'):
            self._scale_blit_verify_count_python = 0
        
        self._scale_blit_verify_count_python += 1
        
        if self._scale_blit_verify_count_python <= 50:
            # Verificar píxeles en la pantalla después del blit (primeros 20 píxeles escalados)
            screen_pixels = []
            scale_x = self.window_width // 160
            scale_y = self.window_height // 144
            
            for x in range(min(20, 160)):
                screen_x = x * scale_x
                if screen_x < self.window_width:
                    pixel_color = self.screen.get_at((screen_x, 0)) if hasattr(self.screen, 'get_at') else None
                    if pixel_color:
                        screen_pixels.append(pixel_color[:3])  # Solo RGB, ignorar alpha
            
            logger.info(f"[Renderer-Scale-Blit-Python] Frame {self._scale_blit_verify_count_python} | "
                       f"Screen pixels after blit (first 20): {screen_pixels}")
            print(f"[Renderer-Scale-Blit-Python] Frame {self._scale_blit_verify_count_python} | "
                  f"Screen pixels after blit (first 20): {screen_pixels}")
            
            # Verificar que hay píxeles negros en la pantalla
            black_pixels = [p for p in screen_pixels if p == (0, 0, 0)]
            if len(black_pixels) == 0:
                logger.warning("[Renderer-Scale-Blit-Python] ⚠️ PROBLEMA: No hay píxeles negros en la pantalla después del blit!")
                print("[Renderer-Scale-Blit-Python] ⚠️ PROBLEMA: No hay píxeles negros en la pantalla después del blit!")
        # -------------------------------------------
        
        # Actualizar la pantalla
        pygame.display.flip()
        
        # --- Step 0374: Tarea 5 - Verificar Actualización de Pantalla ---
        # Verificar que pygame.display.flip() se ejecuta y actualiza la pantalla
        if not hasattr(self, '_screen_update_verify_count'):
            self._screen_update_verify_count = 0
        
        self._screen_update_verify_count += 1
        
        if self._screen_update_verify_count <= 50:
            logger.info(f"[Renderer-Screen-Update] Frame {self._screen_update_verify_count} | "
                       f"pygame.display.flip() ejecutado")
            print(f"[Renderer-Screen-Update] Frame {self._screen_update_verify_count} | "
                  f"pygame.display.flip() ejecutado")
        # -------------------------------------------
        
        # --- Step 0348: Verificación de Actualización de Pantalla ---
        # Verificar que la pantalla se actualiza correctamente después de flip()
        if not hasattr(self, '_screen_update_check_count'):
            self._screen_update_check_count = 0
        
        # --- Step 0350: Debug de Condiciones de Verificación de Pantalla ---
        if not hasattr(self, '_screen_update_debug_count'):
            self._screen_update_debug_count = 0
        
        self._screen_update_debug_count += 1
        if self._screen_update_debug_count <= 5:
            has_screen = hasattr(self, 'screen') and self.screen is not None
            has_frame_indices = hasattr(self, '_current_frame_indices') and self._current_frame_indices is not None
            logger.info(f"[Renderer-Screen-Update-Debug] Frame {self._screen_update_debug_count} | "
                       f"has_screen={has_screen}, has_frame_indices={has_frame_indices}, "
                       f"check_count={self._screen_update_check_count}")
            print(f"[Renderer-Screen-Update-Debug] Frame {self._screen_update_debug_count} | "
                  f"has_screen={has_screen}, has_frame_indices={has_frame_indices}, "
                  f"check_count={self._screen_update_check_count}")
        # -------------------------------------------
        
        if hasattr(self, 'screen') and self.screen is not None and \
           hasattr(self, '_current_frame_indices') and self._current_frame_indices is not None and \
           self._screen_update_check_count < 10:
            self._screen_update_check_count += 1
            
            # Verificar algunos píxeles en la pantalla después de flip()
            test_pixels = [(0, 0), (80, 72), (159, 143)]
            
            logger.info(f"[Renderer-Screen-Update] Frame {self._screen_update_check_count} | "
                       f"Verificando pantalla después de flip():")
            print(f"[Renderer-Screen-Update] Frame {self._screen_update_check_count} | "
                  f"Verificando pantalla después de flip():")
            
            # Usar self._current_frame_indices en lugar de frame_indices
            frame_indices = self._current_frame_indices
            
            for x, y in test_pixels:
                # Calcular posición escalada
                scale_x = int(x * self.screen.get_width() / 160)
                scale_y = int(y * self.screen.get_height() / 144)
                
                # Color en la pantalla después de flip()
                if scale_x < self.screen.get_width() and scale_y < self.screen.get_height():
                    screen_color = self.screen.get_at((scale_x, scale_y))
                    
                    # Obtener índice original del framebuffer
                    idx = y * 160 + x
                    if idx < len(frame_indices):
                        framebuffer_idx = frame_indices[idx] & 0x03
                        expected_rgb = palette[framebuffer_idx]
                        
                        logger.info(f"[Renderer-Screen-Update] Pixel ({x}, {y}): "
                                   f"Framebuffer index={framebuffer_idx}, Expected RGB={expected_rgb}, "
                                   f"Screen RGB={screen_color}")
                        print(f"[Renderer-Screen-Update] Pixel ({x}, {y}): "
                              f"Framebuffer index={framebuffer_idx}, Expected RGB={expected_rgb}, "
                              f"Screen RGB={screen_color}")
                        
                        # Verificar que los colores coinciden (tolerancia para interpolación)
                        if abs(screen_color[0] - expected_rgb[0]) > 10 or \
                           abs(screen_color[1] - expected_rgb[1]) > 10 or \
                           abs(screen_color[2] - expected_rgb[2]) > 10:
                            logger.warning(f"[Renderer-Screen-Update] ⚠️ Color en pantalla no coincide!")
                            print(f"[Renderer-Screen-Update] ⚠️ Color en pantalla no coincide!")
        # -------------------------------------------
        
        # --- Step 0348: Contar Frames Mostrados ---
        # Contar cuántos frames se muestran
        if not hasattr(self, '_frames_displayed_count'):
            self._frames_displayed_count = 0
        
        self._frames_displayed_count += 1
        
        if self._frames_displayed_count <= 20:
            logger.info(f"[Renderer-Frames-Displayed] Frame {self._frames_displayed_count} mostrado")
            print(f"[Renderer-Frames-Displayed] Frame {self._frames_displayed_count} mostrado")
        # -------------------------------------------
        
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
            
            # Manejar redimensionamiento de ventana
            elif event.type == pygame.VIDEORESIZE:
                self.window_width = event.w
                self.window_height = event.h
                # Actualizar el tamaño de la superficie de la ventana
                self.screen = pygame.display.set_mode((self.window_width, self.window_height), pygame.RESIZABLE)
            
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

