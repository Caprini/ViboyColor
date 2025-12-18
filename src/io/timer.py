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

Concepto de TIMA/TMA/TAC:
- TIMA (Timer Counter): Contador de 8 bits que incrementa a la velocidad definida por TAC
- TMA (Timer Modulo): Valor de recarga cuando TIMA hace overflow (pasa de 255 a 0)
- TAC (Timer Control): Control del Timer
  - Bit 2: Enable (1=Timer encendido, 0=Timer apagado)
  - Bits 1-0: Velocidad (00=4096Hz, 01=262144Hz, 10=65536Hz, 11=16384Hz)
- Cuando TIMA hace overflow (pasa de 255 a 0):
  1. TIMA se recarga con el valor de TMA
  2. Se solicita una Interrupción Timer (Bit 2 de IF, 0xFF0F)

Frecuencias del Timer (según bits 1-0 de TAC):
- 00: 4096 Hz -> 4194304 / 4096 = 1024 T-Cycles por incremento
- 01: 262144 Hz -> 4194304 / 262144 = 16 T-Cycles por incremento
- 10: 65536 Hz -> 4194304 / 65536 = 64 T-Cycles por incremento
- 11: 16384 Hz -> 4194304 / 16384 = 256 T-Cycles por incremento

Fuente: Pan Docs - Timer and Divider Registers
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..memory.mmu import MMU

logger = logging.getLogger(__name__)

# Constantes de timing
# Frecuencia del sistema: 4.194304 MHz (T-Cycles por segundo)
SYSTEM_FREQ_HZ = 4_194_304
# Frecuencia de DIV: 16384 Hz
DIV_FREQ_HZ = 16_384
# T-Cycles por incremento de DIV: 4194304 / 16384 = 256
DIV_T_CYCLES_PER_INCREMENT = SYSTEM_FREQ_HZ // DIV_FREQ_HZ

# Frecuencias del Timer (TAC bits 1-0)
TAC_FREQ_4096_HZ = 4096
TAC_FREQ_262144_HZ = 262_144
TAC_FREQ_65536_HZ = 65_536
TAC_FREQ_16384_HZ = 16_384

# T-Cycles por incremento de TIMA según frecuencia
TAC_T_CYCLES_4096 = SYSTEM_FREQ_HZ // TAC_FREQ_4096_HZ  # 1024
TAC_T_CYCLES_262144 = SYSTEM_FREQ_HZ // TAC_FREQ_262144_HZ  # 16
TAC_T_CYCLES_65536 = SYSTEM_FREQ_HZ // TAC_FREQ_65536_HZ  # 64
TAC_T_CYCLES_16384 = SYSTEM_FREQ_HZ // TAC_FREQ_16384_HZ  # 256

# Máscaras de bits para TAC
TAC_ENABLE_MASK = 0x04  # Bit 2: Enable
TAC_FREQ_MASK = 0x03  # Bits 1-0: Frecuencia


class Timer:
    """
    Sistema de temporización de la Game Boy.
    
    Implementa todos los registros del Timer:
    - DIV (Divider Register): Contador continuo a 16384 Hz
    - TIMA (Timer Counter): Contador configurable con interrupciones
    - TMA (Timer Modulo): Valor de recarga cuando TIMA desborda
    - TAC (Timer Control): Control de enable y frecuencia
    
    El Timer puede generar interrupciones cuando TIMA hace overflow.
    """
    
    def __init__(self) -> None:
        """
        Inicializa el Timer.
        
        El contador interno DIV se inicializa a 0. En una Game Boy real,
        el contador puede tener un valor aleatorio al encender, pero para
        reproducibilidad en tests, lo inicializamos a 0.
        
        TIMA, TMA y TAC se inicializan a 0 (Timer desactivado por defecto).
        """
        # Contador interno de 16 bits para DIV
        # Este contador incrementa continuamente
        self._div_counter: int = 0
        
        # Registros del Timer
        self._tima: int = 0  # Timer Counter (8 bits, 0x00-0xFF)
        self._tma: int = 0  # Timer Modulo (8 bits, 0x00-0xFF)
        self._tac: int = 0  # Timer Control (8 bits, pero solo bits 0-2 importan)
        
        # Contador interno para TIMA (acumula T-Cycles hasta el siguiente incremento)
        # Usamos un acumulador para manejar fracciones de ciclo
        self._tima_accumulator: int = 0
        
        # Referencia a MMU para solicitar interrupciones (se establece después)
        self._mmu: MMU | None = None
        
        logger.debug("Timer inicializado (DIV=0, TIMA=0, TMA=0, TAC=0)")
    
    def tick(self, t_cycles: int) -> None:
        """
        Avanza el Timer según los T-Cycles transcurridos.
        
        DIV incrementa cada 256 T-Cycles continuamente.
        TIMA incrementa según la frecuencia configurada en TAC (si está activo).
        Cuando TIMA hace overflow (pasa de 255 a 0), se recarga con TMA y se
        solicita una interrupción Timer.
        
        Args:
            t_cycles: Número de T-Cycles transcurridos desde la última llamada
        """
        # Acumular ciclos en el contador interno de DIV
        # El contador interno es de 16 bits, así que hace wrap-around automáticamente
        self._div_counter = (self._div_counter + t_cycles) & 0xFFFF
        
        # Procesar TIMA solo si el Timer está activo (TAC bit 2 = 1)
        if (self._tac & TAC_ENABLE_MASK) != 0:
            # Obtener la frecuencia configurada (bits 1-0 de TAC)
            freq_select = self._tac & TAC_FREQ_MASK
            
            # Determinar cuántos T-Cycles se necesitan para un incremento de TIMA
            tima_threshold = self._get_tima_threshold(freq_select)
            
            # Acumular ciclos en el acumulador de TIMA
            self._tima_accumulator += t_cycles
            
            # Incrementar TIMA cada vez que alcancemos el umbral
            while self._tima_accumulator >= tima_threshold:
                self._tima_accumulator -= tima_threshold
                
                # Verificar overflow ANTES de incrementar: si TIMA es 0xFF, el siguiente será 0
                if self._tima == 0xFF:
                    # OVERFLOW: Recargar TIMA con TMA
                    self._tima = self._tma & 0xFF
                    # Solicitar interrupción Timer (Bit 2 de IF, 0xFF0F)
                    self._request_timer_interrupt()
                else:
                    # Incremento normal
                    self._tima = (self._tima + 1) & 0xFF
    
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
    
    def _get_tima_threshold(self, freq_select: int) -> int:
        """
        Obtiene el umbral de T-Cycles para incrementar TIMA según la frecuencia.
        
        Args:
            freq_select: Bits 1-0 de TAC (0-3)
            
        Returns:
            Número de T-Cycles necesarios para un incremento de TIMA
        """
        match freq_select:
            case 0:  # 4096 Hz
                return TAC_T_CYCLES_4096
            case 1:  # 262144 Hz
                return TAC_T_CYCLES_262144
            case 2:  # 65536 Hz
                return TAC_T_CYCLES_65536
            case 3:  # 16384 Hz
                return TAC_T_CYCLES_16384
            case _:
                # No debería ocurrir, pero por seguridad
                return TAC_T_CYCLES_4096
    
    def _request_timer_interrupt(self) -> None:
        """
        Solicita una interrupción Timer activando el bit 2 del registro IF (0xFF0F).
        
        Este método se llama cuando TIMA hace overflow. La interrupción será
        procesada por la CPU si IME está activo y el bit 2 de IE también está activo.
        """
        if self._mmu is not None:
            if_val = self._mmu.read_byte(0xFF0F)
            if_val |= 0x04  # Set bit 2 (Timer interrupt)
            self._mmu.write_byte(0xFF0F, if_val)
            logger.debug(f"Timer: Interrupción solicitada (TIMA overflow, IF=0x{if_val:02X})")
    
    def read_tima(self) -> int:
        """
        Lee el registro TIMA (0xFF05).
        
        Returns:
            Valor del registro TIMA (0x00 a 0xFF)
        """
        return self._tima & 0xFF
    
    def write_tima(self, value: int) -> None:
        """
        Escribe en el registro TIMA (0xFF05).
        
        CRÍTICO: Según la documentación, escribir en TIMA durante el ciclo
        en que hace overflow puede tener comportamiento especial. Por ahora,
        implementamos escritura directa.
        
        Args:
            value: Valor a escribir (se enmascara a 8 bits)
        """
        self._tima = value & 0xFF
        logger.debug(f"Timer: TIMA escrito = 0x{self._tima:02X}")
    
    def read_tma(self) -> int:
        """
        Lee el registro TMA (0xFF06).
        
        Returns:
            Valor del registro TMA (0x00 a 0xFF)
        """
        return self._tma & 0xFF
    
    def write_tma(self, value: int) -> None:
        """
        Escribe en el registro TMA (0xFF06).
        
        TMA es el valor con el que se recarga TIMA cuando hace overflow.
        
        Args:
            value: Valor a escribir (se enmascara a 8 bits)
        """
        self._tma = value & 0xFF
        logger.debug(f"Timer: TMA escrito = 0x{self._tma:02X}")
    
    def read_tac(self) -> int:
        """
        Lee el registro TAC (0xFF07).
        
        Solo los bits 0-2 son significativos:
        - Bit 2: Enable (1=Timer activo, 0=Timer apagado)
        - Bits 1-0: Frecuencia (00=4096Hz, 01=262144Hz, 10=65536Hz, 11=16384Hz)
        
        Returns:
            Valor del registro TAC (solo bits 0-2 significativos)
        """
        # Solo los bits 0-2 son significativos, los demás siempre son 1
        return (self._tac & 0x07) | 0xF8
    
    def write_tac(self, value: int) -> None:
        """
        Escribe en el registro TAC (0xFF07).
        
        Solo los bits 0-2 son significativos. Los bits 3-7 se ignoran.
        
        CRÍTICO: Si se desactiva el Timer (bit 2 pasa de 1 a 0), el acumulador
        de TIMA se mantiene, pero TIMA deja de incrementar. Si se reactiva,
        TIMA continúa desde donde estaba.
        
        Args:
            value: Valor a escribir (solo bits 0-2 se usan)
        """
        # Solo los bits 0-2 son significativos
        self._tac = value & 0x07
        logger.debug(f"Timer: TAC escrito = 0x{self._tac:02X} (Enable={bool(self._tac & TAC_ENABLE_MASK)}, Freq={self._tac & TAC_FREQ_MASK})")
    
    def set_mmu(self, mmu: MMU) -> None:
        """
        Establece la referencia a la MMU para permitir solicitar interrupciones.
        
        Este método se llama después de crear tanto el Timer como la MMU para evitar
        dependencias circulares en el constructor.
        
        Args:
            mmu: Instancia de MMU
        """
        self._mmu = mmu
        logger.debug("Timer: MMU conectada para solicitar interrupciones")

