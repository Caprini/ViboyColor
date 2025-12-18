"""
Timer - Sistema de Temporización de la Game Boy

El Timer de la Game Boy incluye varios registros:
- DIV (0xFF04): Divider Register - Contador que incrementa continuamente a 16384 Hz
- TIMA (0xFF05): Timer Counter - Contador configurable que puede generar interrupciones
- TMA (0xFF06): Timer Modulo - Valor de recarga cuando TIMA desborda
- TAC (0xFF07): Timer Control - Controla si TIMA está activo y su frecuencia

Concepto de DIV:
- DIV es un contador interno de 16 bits que incrementa a velocidad fija: 16384 Hz
- El registro DIV (0xFF04) expone solo los 8 bits altos del contador interno
- DIV incrementa cada 256 T-Cycles (4.194304 MHz / 16384 Hz = 256)
- Cualquier escritura en DIV (0xFF04) resetea el contador interno a 0
- Muchos juegos usan DIV para generar números aleatorios (RNG)

Por ahora, implementamos solo DIV. TIMA/TMA/TAC se implementarán más adelante
cuando sean necesarios para juegos específicos.

Fuente: Pan Docs - Timer and Divider Registers
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Constantes de timing
# Frecuencia del sistema: 4.194304 MHz (T-Cycles por segundo)
SYSTEM_FREQ_HZ = 4_194_304
# Frecuencia de DIV: 16384 Hz
DIV_FREQ_HZ = 16_384
# T-Cycles por incremento de DIV: 4194304 / 16384 = 256
DIV_T_CYCLES_PER_INCREMENT = SYSTEM_FREQ_HZ // DIV_FREQ_HZ


class Timer:
    """
    Sistema de temporización de la Game Boy.
    
    Implementa el registro DIV (Divider Register) que incrementa continuamente
    a 16384 Hz. Este registro es crítico para muchos juegos que lo usan como
    fuente de aleatoriedad (RNG).
    
    Por ahora, solo implementa DIV. TIMA/TMA/TAC se añadirán más adelante.
    """
    
    def __init__(self) -> None:
        """
        Inicializa el Timer.
        
        El contador interno DIV se inicializa a 0. En una Game Boy real,
        el contador puede tener un valor aleatorio al encender, pero para
        reproducibilidad en tests, lo inicializamos a 0.
        """
        # Contador interno de 16 bits para DIV
        # Este contador incrementa continuamente
        self._div_counter: int = 0
        
        logger.debug("Timer inicializado (DIV contador interno = 0)")
    
    def tick(self, t_cycles: int) -> None:
        """
        Avanza el Timer según los T-Cycles transcurridos.
        
        DIV incrementa cada 256 T-Cycles. Acumulamos los ciclos y cuando
        alcanzamos 256, incrementamos el contador interno.
        
        Args:
            t_cycles: Número de T-Cycles transcurridos desde la última llamada
        """
        # Acumular ciclos en el contador interno
        # El contador interno es de 16 bits, así que hace wrap-around automáticamente
        self._div_counter = (self._div_counter + t_cycles) & 0xFFFF
    
    def read_div(self) -> int:
        """
        Lee el registro DIV (0xFF04).
        
        DIV expone solo los 8 bits altos del contador interno.
        Es decir: DIV = (div_counter >> 8) & 0xFF
        
        Returns:
            Valor del registro DIV (0x00 a 0xFF)
        """
        # Los 8 bits altos del contador de 16 bits
        div_value = (self._div_counter >> 8) & 0xFF
        return div_value
    
    def write_div(self, value: int) -> None:
        """
        Escribe en el registro DIV (0xFF04).
        
        CRÍTICO: Cualquier escritura en DIV (independientemente del valor escrito)
        resetea el contador interno a 0. Esto es un comportamiento del hardware real.
        
        Args:
            value: Valor escrito (se ignora, solo importa que se escriba)
        """
        # Cualquier escritura resetea el contador interno
        # El valor escrito se ignora completamente
        self._div_counter = 0
        logger.debug(f"Timer: DIV reseteado (escritura en 0xFF04, valor escrito ignorado: 0x{value:02X})")
    
    def get_div_counter(self) -> int:
        """
        Obtiene el valor completo del contador interno (16 bits).
        
        Este método es útil para tests y debugging. No expone el contador
        completo al juego (solo los 8 bits altos a través de read_div).
        
        Returns:
            Valor del contador interno (0x0000 a 0xFFFF)
        """
        return self._div_counter

