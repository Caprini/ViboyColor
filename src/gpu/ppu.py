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

# Constantes de Modos PPU
# Fuente: Pan Docs - LCD Status Register (STAT)
# Cada línea de 456 ciclos se divide en 3 modos (para líneas visibles):
# - Mode 2 (OAM Search): 0-79 ciclos (80 ciclos) - La PPU busca sprites en OAM
# - Mode 3 (Pixel Transfer): 80-251 ciclos (172 ciclos) - La PPU dibuja píxeles (CPU bloqueada de VRAM)
# - Mode 0 (H-Blank): 252-455 ciclos (204 ciclos) - Descanso horizontal (CPU puede tocar VRAM)
# - Mode 1 (V-Blank): Líneas 144-153 completas (10 líneas) - Descanso vertical
PPU_MODE_0_HBLANK = 0      # H-Blank (CPU puede acceder a VRAM)
PPU_MODE_1_VBLANK = 1      # V-Blank (CPU puede acceder a VRAM)
PPU_MODE_2_OAM_SEARCH = 2  # OAM Search (CPU bloqueada de OAM)
PPU_MODE_3_PIXEL_TRANSFER = 3  # Pixel Transfer (CPU bloqueada de VRAM y OAM)

# Timing de modos dentro de una línea visible (en T-Cycles)
MODE_2_CYCLES = 80   # OAM Search: primeros 80 ciclos
MODE_3_CYCLES = 172  # Pixel Transfer: siguientes 172 ciclos (80-251)
MODE_0_CYCLES = 204  # H-Blank: resto (252-455)


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
        - Leer configuración del LCD (LCDC, STAT, etc.)
        
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
        
        # Modo PPU actual: Indica en qué estado está la PPU (Mode 0, 1, 2 o 3)
        # Se actualiza dinámicamente en step() según el timing de la línea
        # Inicialmente Mode 2 (OAM Search) al inicio de la primera línea
        self.mode: int = PPU_MODE_2_OAM_SEARCH
        
        # Flag para indicar que un frame está listo para renderizar
        # Se activa cuando LY pasa de 143 a 144 (inicio de V-Blank)
        # Permite desacoplar el renderizado de las interrupciones
        self.frame_ready: bool = False
        
        # LYC (LY Compare): Registro de lectura/escritura que almacena el valor de línea
        # con el que se compara LY para generar interrupciones STAT
        # Rango: 0-153 (aunque típicamente se usa 0-143 para líneas visibles)
        # Se inicializa a 0
        self.lyc: int = 0
        
        # Flag para evitar disparar múltiples interrupciones STAT en la misma línea
        # Se usa para implementar "rising edge" detection: solo se dispara cuando
        # la condición pasa de False a True, no mientras permanece True
        self.stat_interrupt_line: bool = False
        
        # logger.debug("PPU inicializada: LY=0, clock=0, mode=2 (OAM Search)")

    def step(self, cycles: int) -> None:
        """
        Avanza el motor de timing de la PPU según los ciclos de reloj consumidos.
        
        Este método debe llamarse después de cada instrucción de la CPU, pasando
        los T-Cycles (ciclos de reloj) consumidos. La PPU acumula estos ciclos
        y avanza las líneas de escaneo cuando corresponde, actualizando dinámicamente
        el modo PPU (Mode 0, 1, 2 o 3) según el timing de la línea.
        
        CRÍTICO: La PPU solo avanza cuando el LCD está encendido (LCDC bit 7 = 1).
        Cuando el LCD está apagado (LCDC bit 7 = 0), la PPU se detiene y LY se
        mantiene en 0. Esto es crítico porque muchos juegos encienden el LCD y
        luego esperan V-Blank para configurar los gráficos.
        
        Comportamiento:
        1. Verificar si el LCD está encendido (LCDC bit 7)
        2. Si está apagado, no avanzar (LY se mantiene en 0)
        3. Si está encendido, acumular ciclos en el clock interno
        4. Actualizar el modo PPU según el punto en la línea actual (line_cycles)
        5. Si clock >= 456: Resta 456, incrementa LY, reinicia modo a Mode 2
        6. Si LY == 144: ¡Entramos en V-Blank! Solicita interrupción (bit 0 en IF)
        7. Si LY > 153: Reinicia LY a 0 (nuevo frame)
        
        Args:
            cycles: Número de T-Cycles (ciclos de reloj) a procesar
                   NOTA: La CPU devuelve M-Cycles, que deben convertirse a T-Cycles
                   multiplicando por 4 antes de llamar a este método.
        
        Fuente: Pan Docs - LCD Timing, V-Blank Interrupt, STAT Register, LCD Control Register
        """
        # CRÍTICO: Verificar si el LCD está encendido (LCDC bit 7)
        # Si el LCD está apagado, la PPU se detiene y LY se mantiene en 0
        lcdc = self.mmu.read_byte(0xFF40) & 0xFF
        lcd_enabled = (lcdc & 0x80) != 0
        
        if not lcd_enabled:
            # LCD apagado: PPU detenida, LY se mantiene en 0
            # No acumulamos ciclos ni avanzamos líneas
            return
        
        # Acumular ciclos en el clock interno (solo si el LCD está encendido)
        self.clock += cycles
        
        # Actualizar el modo PPU según el punto actual en la línea
        # Esto debe hacerse ANTES de procesar líneas completas para que
        # el modo sea correcto durante toda la línea
        self._update_mode()
        
        # Guardar LY anterior para detectar cambios
        old_ly = self.ly
        old_mode = self.mode
        
        # Mientras tengamos suficientes ciclos para completar una línea (456 T-Cycles)
        while self.clock >= CYCLES_PER_SCANLINE:
            # Restar los ciclos de una línea completa
            self.clock -= CYCLES_PER_SCANLINE
            
            # Avanzar a la siguiente línea
            self.ly += 1
            
            # Al inicio de cada nueva línea, el modo es Mode 2 (OAM Search)
            # Se actualizará automáticamente en la siguiente llamada a _update_mode()
            self.mode = PPU_MODE_2_OAM_SEARCH
            
            # CRÍTICO: Cuando LY cambia, reiniciar el flag de interrupción STAT
            # Esto permite que se dispare una nueva interrupción si las condiciones
            # se cumplen en la nueva línea
            self.stat_interrupt_line = False
            
            # Si llegamos a V-Blank (línea 144), solicitar interrupción y marcar frame listo
            if self.ly == VBLANK_START:
                # CRÍTICO: Activar bit 0 del registro IF (Interrupt Flag) en 0xFF0F
                # Este bit corresponde a la interrupción V-Blank.
                #
                # IMPORTANTE: IF se actualiza SIEMPRE cuando ocurre V-Blank,
                # INDEPENDIENTEMENTE del estado de IME (Interrupt Master Enable).
                # Esto permite que los juegos hagan "polling" manual de IF para
                # detectar V-Blank sin usar interrupciones automáticas.
                #
                # Comportamiento hardware:
                # - El hardware activa IF cuando ocurre el evento (V-Blank)
                # - IME solo controla si la CPU procesa la interrupción automáticamente
                # - Los juegos pueden leer IF manualmente incluso con IME=False
                #
                # Fuente: Pan Docs - Interrupts, V-Blank Interrupt Flag
                if_val = self.mmu.read_byte(0xFF0F)
                if_val |= 0x01  # Set bit 0 (V-Blank interrupt)
                self.mmu.write_byte(0xFF0F, if_val)
                
                # CRÍTICO: Marcar frame como listo para renderizar
                # Esto permite desacoplar el renderizado de las interrupciones.
                # El bucle principal puede comprobar este flag independientemente
                # del estado de IME o si se procesan interrupciones.
                self.frame_ready = True
                
                # Log para diagnóstico (comentado para rendimiento)
                # logger.info(f"🎯 PPU: V-Blank iniciado (LY={self.ly}), IF actualizado a 0x{if_val:02X}")
            
            # Si pasamos la última línea (153), reiniciar a 0 (nuevo frame)
            if self.ly > 153:
                self.ly = 0
                # Reiniciar flag de interrupción STAT al cambiar de frame
                self.stat_interrupt_line = False
                # logger.debug(f"PPU: Nuevo frame iniciado (LY={self.ly})")
        
        # Actualizar el modo después de procesar líneas completas
        # (por si quedaron ciclos residuales en la línea actual)
        self._update_mode()
        
        # Verificar interrupciones STAT si LY cambió o el modo cambió
        if self.ly != old_ly or self.mode != old_mode:
            self._check_stat_interrupt()

    def _update_mode(self) -> None:
        """
        Actualiza el modo PPU actual según el punto en la línea (line_cycles) y LY.
        
        Lógica de estados:
        - Si LY >= 144: Mode 1 (V-Blank) - Líneas 144-153 completas
        - Si LY < 144 (línea visible):
            - Si line_cycles < 80: Mode 2 (OAM Search)
            - Si line_cycles < 252: Mode 3 (Pixel Transfer)
            - Si line_cycles < 456: Mode 0 (H-Blank)
        
        Fuente: Pan Docs - LCD Status Register (STAT), PPU Modes
        """
        old_mode = self.mode
        
        # Si estamos en V-Blank (líneas 144-153), siempre Mode 1
        if self.ly >= VBLANK_START:
            self.mode = PPU_MODE_1_VBLANK
        else:
            # Para líneas visibles (0-143), el modo depende de los ciclos dentro de la línea
            # line_cycles es el contador de ciclos dentro de la línea actual (0-455)
            line_cycles = self.clock
            
            if line_cycles < MODE_2_CYCLES:
                # Primeros 80 ciclos: Mode 2 (OAM Search)
                self.mode = PPU_MODE_2_OAM_SEARCH
            elif line_cycles < (MODE_2_CYCLES + MODE_3_CYCLES):
                # Siguientes 172 ciclos (80-251): Mode 3 (Pixel Transfer)
                self.mode = PPU_MODE_3_PIXEL_TRANSFER
            else:
                # Resto (252-455): Mode 0 (H-Blank)
                self.mode = PPU_MODE_0_HBLANK
        
        # Si el modo cambió, verificar interrupciones STAT
        # (Nota: también se verifica desde step() cuando LY cambia)
        if self.mode != old_mode:
            self._check_stat_interrupt()
    
    def _check_stat_interrupt(self) -> None:
        """
        Verifica las condiciones de interrupción STAT y solicita la interrupción si corresponde.
        
        Las interrupciones STAT se pueden generar por:
        1. LYC=LY Coincidence (LY == LYC) si el bit 6 de STAT está activo
        2. Mode 0 (H-Blank) si el bit 3 de STAT está activo
        3. Mode 1 (V-Blank) si el bit 4 de STAT está activo
        4. Mode 2 (OAM Search) si el bit 5 de STAT está activo
        
        CRÍTICO: La interrupción se dispara en "rising edge", es decir, solo cuando
        la condición pasa de False a True. Si la condición permanece True, no se
        dispara múltiples veces. Esto se controla con el flag `stat_interrupt_line`.
        
        Fuente: Pan Docs - LCD Status Register (STAT), STAT Interrupt
        """
        # Leer el registro STAT directamente de memoria (evita recursión)
        stat_value = self.mmu._memory[0xFF41] & 0xFF
        
        # Inicializar señal de interrupción
        signal = False
        
        # Verificar LYC=LY Coincidence (bit 2 y bit 6)
        lyc_match = (self.ly & 0xFF) == (self.lyc & 0xFF)
        if lyc_match:
            # Set bit 2 de STAT (LYC=LY Coincidence Flag)
            # Este bit es de solo lectura desde el hardware, pero se actualiza aquí
            # El bit 2 se combina con los bits configurables en get_stat() 
            # Si el bit 6 (LYC Int Enable) está activo, solicitar interrupción
            if (stat_value & 0x40) != 0:  # Bit 6 activo
                signal = True
                # Instrumentación para diagnóstico: detectar señal STAT activa por LYC
                logger.info(
                    f"🚨 STAT SIGNAL ACTIVE! (LYC Match) "
                    f"Mode={self.mode} LY={self.ly} LYC={self.lyc} "
                    f"STAT={stat_value:02X} (Bit 6 LYC Int Enable: True)"
                )
        else:
            # Si LY != LYC, el bit 2 debe estar limpio
            # (se maneja en get_stat() combinando con el valor de memoria)
            pass
        
        # Verificar interrupciones por modo PPU
        if self.mode == PPU_MODE_0_HBLANK and (stat_value & 0x08) != 0:  # Bit 3 activo
            signal = True
            # Instrumentación para diagnóstico: detectar señal STAT activa por H-Blank
            logger.info(
                f"🚨 STAT SIGNAL ACTIVE! (H-Blank) "
                f"Mode={self.mode} LY={self.ly} LYC={self.lyc} "
                f"STAT={stat_value:02X} (Bit 3 H-Blank Int Enable: True)"
            )
        elif self.mode == PPU_MODE_1_VBLANK and (stat_value & 0x10) != 0:  # Bit 4 activo
            signal = True
            # Instrumentación para diagnóstico: detectar señal STAT activa por V-Blank
            logger.info(
                f"🚨 STAT SIGNAL ACTIVE! (V-Blank) "
                f"Mode={self.mode} LY={self.ly} LYC={self.lyc} "
                f"STAT={stat_value:02X} (Bit 4 V-Blank Int Enable: True)"
            )
        elif self.mode == PPU_MODE_2_OAM_SEARCH and (stat_value & 0x20) != 0:  # Bit 5 activo
            signal = True
            # Instrumentación para diagnóstico: detectar señal STAT activa por OAM Search
            logger.info(
                f"🚨 STAT SIGNAL ACTIVE! (OAM Search) "
                f"Mode={self.mode} LY={self.ly} LYC={self.lyc} "
                f"STAT={stat_value:02X} (Bit 5 OAM Int Enable: True)"
            )
        
        # Disparar interrupción en rising edge (solo si signal es True y antes era False)
        if signal and not self.stat_interrupt_line:
            # Activar bit 1 del registro IF (Interrupt Flag) en 0xFF0F
            # Este bit corresponde a la interrupción LCD STAT
            if_val = self.mmu.read_byte(0xFF0F)
            if_val |= 0x02  # Set bit 1 (LCD STAT interrupt)
            self.mmu.write_byte(0xFF0F, if_val)
            
            # Log para diagnóstico (activado temporalmente para debugging)
            logger.info(f"🎯 PPU: STAT interrupt triggered (LY={self.ly}, LYC={self.lyc}, mode={self.mode}), IF actualizado a 0x{if_val:02X}")
        
        # Actualizar flag de interrupción STAT
        self.stat_interrupt_line = signal

    def get_ly(self) -> int:
        """
        Devuelve el valor actual del registro LY (Línea actual).
        
        Este método es usado por la MMU cuando se lee la dirección 0xFF44.
        El registro LY es de solo lectura desde la perspectiva del software.
        
        Returns:
            Valor de LY (0-153)
        """
        return self.ly

    def get_mode(self) -> int:
        """
        Devuelve el modo PPU actual (0, 1, 2 o 3).
        
        Este método es usado por la MMU cuando se lee el registro STAT (0xFF41)
        para obtener los bits 0-1 que indican el modo actual.
        
        Returns:
            Modo PPU actual:
            - 0: H-Blank (CPU puede acceder a VRAM)
            - 1: V-Blank (CPU puede acceder a VRAM)
            - 2: OAM Search (CPU bloqueada de OAM)
            - 3: Pixel Transfer (CPU bloqueada de VRAM y OAM)
        """
        return self.mode
    
    def get_lyc(self) -> int:
        """
        Devuelve el valor actual del registro LYC (LY Compare).
        
        Este método es usado por la MMU cuando se lee la dirección 0xFF45.
        El registro LYC es de lectura/escritura desde la perspectiva del software.
        
        Returns:
            Valor de LYC (0-153)
        """
        return self.lyc & 0xFF
    
    def set_lyc(self, value: int) -> None:
        """
        Establece el valor del registro LYC (LY Compare).
        
        Este método es usado por la MMU cuando se escribe en la dirección 0xFF45.
        El registro LYC es de lectura/escritura desde la perspectiva del software.
        
        Cuando LYC cambia, se debe verificar inmediatamente si LY == LYC para
        actualizar el bit 2 de STAT y solicitar interrupción si corresponde.
        
        Args:
            value: Valor a escribir en LYC (se enmascara a 8 bits, rango 0-255)
        
        Fuente: Pan Docs - LYC Register (0xFF45)
        """
        old_lyc = self.lyc
        self.lyc = value & 0xFF
        
        # Log para diagnóstico (activado temporalmente para debugging)
        logger.info(f"📝 PPU: LYC escrito = {self.lyc} (LY actual = {self.ly})")
        
        # Si LYC cambió, verificar interrupciones STAT inmediatamente
        # (el bit 2 de STAT puede cambiar si LY == nuevo LYC)
        if self.lyc != old_lyc:
            self._check_stat_interrupt()

    def is_frame_ready(self) -> bool:
        """
        Comprueba si hay un frame listo para renderizar y resetea el flag.
        
        Este método permite desacoplar el renderizado de las interrupciones.
        Cuando LY pasa de 143 a 144 (inicio de V-Blank), se activa el flag
        `frame_ready`. El bucle principal puede comprobar este flag y renderizar
        independientemente del estado de IME o si se procesan interrupciones.
        
        IMPORTANTE: Este método resetea el flag a False después de leerlo.
        Esto asegura que cada frame solo se renderiza una vez.
        
        Returns:
            True si hay un frame listo para renderizar, False en caso contrario
        """
        if self.frame_ready:
            self.frame_ready = False
            return True
        return False
    
    def get_stat(self) -> int:
        """
        Devuelve el valor del registro STAT (0xFF41) combinando el modo actual
        con los bits configurados por el software.
        
        El registro STAT tiene la siguiente estructura:
        - Bits 0-1: Modo PPU actual (00=H-Blank, 01=V-Blank, 10=OAM Search, 11=Pixel Transfer)
        - Bit 2: LYC=LY Coincidence Flag (LY == LYC) - DE SOLO LECTURA (hardware)
        - Bit 3: Mode 0 (H-Blank) Interrupt Enable
        - Bit 4: Mode 1 (V-Blank) Interrupt Enable
        - Bit 5: Mode 2 (OAM Search) Interrupt Enable
        - Bit 6: LYC=LY Coincidence Interrupt Enable
        - Bit 7: No usado (siempre 0)
        
        Los bits 3-6 son configurables por el software escribiendo en STAT.
        Los bits 0-2 son de solo lectura y reflejan el estado actual de la PPU.
        
        CRÍTICO: No usar mmu.read_byte(0xFF41) aquí porque causaría recursión infinita.
        En su lugar, accedemos directamente a la memoria interna de la MMU.
        
        Returns:
            Valor del registro STAT (0x00-0xFF)
        
        Fuente: Pan Docs - LCD Status Register (STAT)
        """
        # Leer el valor de STAT directamente de la memoria interna (evita recursión)
        # La MMU guarda los bits configurables (3-6) en _memory[0xFF41]
        # Accedemos directamente a través de un método interno o atributo
        # NOTA: Esto requiere acceso a _memory, que es un detalle de implementación
        # pero es necesario para evitar recursión
        stat_value = self.mmu._memory[0xFF41] & 0xFF
        
        # Limpiar los bits 0-2 (modo actual y LYC flag) y reemplazarlos con los valores reales
        # Bits 0-1: Modo PPU actual
        stat_value = (stat_value & 0xF8) | self.mode
        
        # Bit 2: LYC=LY Coincidence Flag (LY == LYC)
        # Este bit es de solo lectura y se actualiza dinámicamente por el hardware
        if (self.ly & 0xFF) == (self.lyc & 0xFF):
            stat_value |= 0x04  # Set bit 2
        else:
            stat_value &= 0xFB  # Clear bit 2
        
        return stat_value & 0xFF

