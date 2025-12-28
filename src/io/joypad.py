"""
Joypad - Control de Botones y Direcciones

El Joypad de la Game Boy usa un sistema de "Active Low" donde:
- 0 = Botón pulsado
- 1 = Botón soltado

El registro P1 (0xFF00) es de lectura/escritura:
- ESCRITURA: El juego selecciona qué leer (bits 4-5)
  - Bit 4 = 0: Quiere leer Direcciones (Right, Left, Up, Down)
  - Bit 5 = 0: Quiere leer Botones (A, B, Select, Start)
- LECTURA: El juego lee el estado de los botones (bits 0-3)
  - Bit 0: Right / A (depende del selector)
  - Bit 1: Left / B
  - Bit 2: Up / Select
  - Bit 3: Down / Start

Cuando un botón pasa de Soltado (1) a Pulsado (0), se debe activar la interrupción
Joypad (Bit 4 en IF, 0xFF0F).

Fuente: Pan Docs - Joypad Input
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory.mmu import MMU

logger = logging.getLogger(__name__)

# Constantes para el registro IF (Interrupt Flag)
from ..memory.mmu import IO_IF

# Máscaras de bits para el selector en P1
P1_SELECT_DIRECTIONS = 0x10  # Bit 4 = 0 significa "quiere leer direcciones"
P1_SELECT_BUTTONS = 0x20     # Bit 5 = 0 significa "quiere leer botones"

# Máscaras de bits para los botones (Active Low: 0 = pulsado, 1 = soltado)
P1_BIT_RIGHT = 0x01   # Bit 0
P1_BIT_LEFT = 0x02    # Bit 1
P1_BIT_UP = 0x04      # Bit 2
P1_BIT_DOWN = 0x08    # Bit 3
P1_BIT_A = 0x01       # Bit 0 (cuando se seleccionan botones)
P1_BIT_B = 0x02       # Bit 1 (cuando se seleccionan botones)
P1_BIT_SELECT = 0x04  # Bit 2 (cuando se seleccionan botones)
P1_BIT_START = 0x08   # Bit 3 (cuando se seleccionan botones)


class Joypad:
    """
    Controlador del Joypad (botones y direcciones) de la Game Boy.
    
    Implementa la lógica Active Low donde 0 = pulsado y 1 = soltado.
    Maneja el selector de bits 4-5 del registro P1 y solicita interrupciones
    cuando un botón se pulsa.
    """
    
    def __init__(self, mmu: MMU | None = None) -> None:
        """
        Inicializa el Joypad.
        
        Args:
            mmu: Referencia opcional a la MMU para solicitar interrupciones
        """
        # Estado de los botones (True = pulsado, False = soltado)
        # Por defecto, todos los botones están soltados (False)
        self._state: dict[str, bool] = {
            "right": False,
            "left": False,
            "up": False,
            "down": False,
            "a": False,
            "b": False,
            "select": False,
            "start": False,
        }
        
        # Estado anterior (para detectar transiciones)
        self._prev_state: dict[str, bool] = self._state.copy()
        
        # Selector actual (bits 4-5 del registro P1)
        # Por defecto, ningún selector está activo (0xCF = 11001111)
        # Bits 4-5 = 1 significa que NO queremos leer ese grupo
        self._selector: int = 0xCF  # 0xCF = 11001111 (bits 4-5 = 1, bits 0-3 = 1)
        
        # Referencia a la MMU para solicitar interrupciones
        self._mmu = mmu
        
        logger.debug("Joypad inicializado: todos los botones soltados")
    
    def write(self, value: int) -> None:
        """
        Escribe en el registro P1 (selector de lectura).
        
        El juego escribe en P1 para seleccionar qué grupo de botones quiere leer:
        - Bit 4 = 0: Quiere leer Direcciones (Right, Left, Up, Down)
        - Bit 5 = 0: Quiere leer Botones (A, B, Select, Start)
        
        Los bits 0-3 no se usan para escritura (el hardware los ignora).
        
        Args:
            value: Valor a escribir (se enmascara a 8 bits)
        """
        # Enmascarar a 8 bits
        value = value & 0xFF
        
        # Solo los bits 4-5 son significativos para la escritura
        # Los bits 0-3 son de solo lectura (estado de los botones)
        # Guardamos el selector completo (pero solo usaremos bits 4-5)
        self._selector = value
        
        logger.debug(f"Joypad: Selector actualizado a 0x{self._selector:02X}")
    
    def read(self) -> int:
        """
        Lee el registro P1 (estado de los botones según el selector).
        
        Retorna el estado de los botones según el selector actual:
        - Si bit 4 = 0 (selecciona direcciones): bits 0-3 = Right, Left, Up, Down
        - Si bit 5 = 0 (selecciona botones): bits 0-3 = A, B, Select, Start
        
        La lógica es Active Low:
        - 0 = Botón pulsado
        - 1 = Botón soltado
        
        Returns:
            Valor del registro P1 (8 bits) con el estado de los botones
        """
        # Empezar con todos los bits a 1 (todos los botones sueltos)
        result = 0xFF
        
        # Si el bit 4 es 0, el juego quiere leer direcciones
        if (self._selector & P1_SELECT_DIRECTIONS) == 0:
            # Bits 0-3 contienen el estado de las direcciones
            if self._state["right"]:
                result &= ~P1_BIT_RIGHT  # Clear bit 0
            if self._state["left"]:
                result &= ~P1_BIT_LEFT   # Clear bit 1
            if self._state["up"]:
                result &= ~P1_BIT_UP     # Clear bit 2
            if self._state["down"]:
                result &= ~P1_BIT_DOWN   # Clear bit 3
        
        # Si el bit 5 es 0, el juego quiere leer botones
        if (self._selector & P1_SELECT_BUTTONS) == 0:
            # Bits 0-3 contienen el estado de los botones
            if self._state["a"]:
                result &= ~P1_BIT_A      # Clear bit 0
            if self._state["b"]:
                result &= ~P1_BIT_B      # Clear bit 1
            if self._state["select"]:
                result &= ~P1_BIT_SELECT # Clear bit 2
            if self._state["start"]:
                result &= ~P1_BIT_START  # Clear bit 3
        
        # Los bits 4-5 siempre reflejan el selector (lo que escribió el juego)
        # Pero en lectura, el hardware los pone a 1 si no están seleccionados
        # Por ahora, los mantenemos como están en el selector
        
        return result & 0xFF
    
    def press(self, button: str) -> None:
        """
        Marca un botón como pulsado.
        
        Si el botón estaba soltado y ahora está pulsado, solicita la interrupción
        Joypad (Bit 4 en IF, 0xFF0F).
        
        Args:
            button: Nombre del botón ("right", "left", "up", "down", "a", "b", "select", "start")
        """
        if button not in self._state:
            logger.warning(f"Joypad: Botón desconocido '{button}', ignorando")
            return
        
        # Guardar estado anterior
        was_pressed = self._state[button]
        
        # Si ya estaba pulsado, no hacer nada (evitar interrupciones duplicadas)
        if was_pressed:
            return
        
        # Marcar como pulsado
        self._state[button] = True
        
        # El botón pasó de soltado a pulsado, solicitar interrupción
        if self._mmu is not None:
            # Leer IF actual
            if_val = self._mmu.read_byte(IO_IF)
            # Activar bit 4 (Joypad interrupt)
            if_val |= 0x10
            # Escribir de vuelta
            self._mmu.write_byte(IO_IF, if_val)
            logger.debug(f"Joypad: Interrupción solicitada por '{button}' (IF=0x{if_val:02X})")
        
        logger.debug(f"Joypad: '{button}' pulsado")
    
    def release(self, button: str) -> None:
        """
        Marca un botón como soltado.
        
        Args:
            button: Nombre del botón ("right", "left", "up", "down", "a", "b", "select", "start")
        """
        if button not in self._state:
            logger.warning(f"Joypad: Botón desconocido '{button}', ignorando")
            return
        
        self._state[button] = False
        logger.debug(f"Joypad: '{button}' soltado")
    
    def get_state(self, button: str) -> bool:
        """
        Obtiene el estado actual de un botón.
        
        Args:
            button: Nombre del botón
            
        Returns:
            True si el botón está pulsado, False si está soltado
        """
        return self._state.get(button, False)

