"""
PPU (Pixel Processing Unit) - Unidad de Procesamiento de Píxeles

La PPU de la Game Boy es responsable de:
1. Generar la señal de video (renderizado de píxeles)
2. Mantener el timing de la pantalla (scanlines, V-Blank)
3. Gestionar interrupciones relacionadas con el video (V-Blank, H-Blank, LYC)

En esta primera iteración, solo implementamos el motor de timing (Timing Engine):
- Registro LY (Línea actual): Indica qué línea se está dibujando (0-153)
- Timing de scanlines: Cada línea tarda 456 T-Cycles (ciclos de reloj)
- Interrupción V-Blank: Se activa cuando LY llega a 144

Concepto de Scanlines:
- La pantalla tiene 144 líneas visibles (0-143)
- Después vienen 10 líneas de V-Blank (144-153)
- Total: 154 líneas por frame
- Cada línea tarda 456 T-Cycles
- Total por frame: 154 * 456 = 70,224 T-Cycles (~59.7 FPS)

El registro LY es de SOLO LECTURA. Los juegos lo leen constantemente para sincronizarse
y saber cuándo pueden actualizar la VRAM de forma segura (durante V-Blank).

Fuente: Pan Docs - LCD Timing, V-Blank, LY Register
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory.mmu import MMU

logger = logging.getLogger(__name__)

# Constantes de timing de la PPU
# Fuente: Pan Docs - LCD Timing
CYCLES_PER_SCANLINE = 456  # T-Cycles por línea
VISIBLE_LINES = 144        # Líneas visibles (0-143)
VBLANK_START = 144         # Inicio de V-Blank (línea 144)
TOTAL_LINES = 154          # Total de líneas por frame (144 visibles + 10 V-Blank)
CYCLES_PER_FRAME = TOTAL_LINES * CYCLES_PER_SCANLINE  # 70,224 T-Cycles


class PPU:
    """
    PPU (Pixel Processing Unit) de la Game Boy.
    
    En esta primera iteración, solo implementa el motor de timing:
    - Mantiene el registro LY (Línea actual)
    - Avanza el timing según los ciclos de reloj
    - Solicita interrupción V-Blank cuando LY llega a 144
    
    El renderizado de píxeles se implementará en pasos posteriores.
    """

    def __init__(self, mmu: MMU) -> None:
        """
        Inicializa la PPU con una referencia a la MMU.
        
        La PPU necesita acceso a la MMU para:
        - Solicitar interrupciones (escribir en IF, 0xFF0F)
        - Leer configuración del LCD (LCDC, STAT, etc.) - futuro
        
        Args:
            mmu: Instancia de MMU para acceso a memoria e I/O
        """
        self.mmu = mmu
        
        # LY (Línea actual): Registro de solo lectura que indica qué línea se está dibujando
        # Rango: 0-153 (0-143 visibles, 144-153 V-Blank)
        # Se inicializa a 0 (primera línea)
        self.ly: int = 0
        
        # Clock interno: Contador de T-Cycles acumulados para la línea actual
        # Cuando llega a 456, avanzamos a la siguiente línea
        self.clock: int = 0
        
        logger.debug("PPU inicializada: LY=0, clock=0")

    def step(self, cycles: int) -> None:
        """
        Avanza el motor de timing de la PPU según los ciclos de reloj consumidos.
        
        Este método debe llamarse después de cada instrucción de la CPU, pasando
        los T-Cycles (ciclos de reloj) consumidos. La PPU acumula estos ciclos
        y avanza las líneas de escaneo cuando corresponde.
        
        Comportamiento:
        1. Acumula ciclos en el clock interno
        2. Si clock >= 456: Resta 456, incrementa LY
        3. Si LY == 144: ¡Entramos en V-Blank! Solicita interrupción (bit 0 en IF)
        4. Si LY > 153: Reinicia LY a 0 (nuevo frame)
        
        Args:
            cycles: Número de T-Cycles (ciclos de reloj) a procesar
                   NOTA: La CPU devuelve M-Cycles, que deben convertirse a T-Cycles
                   multiplicando por 4 antes de llamar a este método.
        
        Fuente: Pan Docs - LCD Timing, V-Blank Interrupt
        """
        # Acumular ciclos en el clock interno
        self.clock += cycles
        
        # Mientras tengamos suficientes ciclos para completar una línea (456 T-Cycles)
        while self.clock >= CYCLES_PER_SCANLINE:
            # Restar los ciclos de una línea completa
            self.clock -= CYCLES_PER_SCANLINE
            
            # Avanzar a la siguiente línea
            self.ly += 1
            
            # Si llegamos a V-Blank (línea 144), solicitar interrupción
            if self.ly == VBLANK_START:
                # Activar bit 0 del registro IF (Interrupt Flag) en 0xFF0F
                # Este bit corresponde a la interrupción V-Blank
                if_val = self.mmu.read_byte(0xFF0F)
                if_val |= 0x01  # Set bit 0 (V-Blank interrupt)
                self.mmu.write_byte(0xFF0F, if_val)
                logger.debug(f"PPU: V-Blank iniciado (LY={self.ly}), interrupción solicitada")
            
            # Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
            if self.ly > 153:
                self.ly = 0
                logger.debug(f"PPU: Nuevo frame iniciado (LY={self.ly})")

    def get_ly(self) -> int:
        """
        Devuelve el valor actual del registro LY (Línea actual).
        
        Este método es usado por la MMU cuando se lee la dirección 0xFF44.
        El registro LY es de solo lectura desde la perspectiva del software.
        
        Returns:
            Valor de LY (0-153)
        """
        return self.ly

