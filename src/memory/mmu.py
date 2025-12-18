"""
MMU (Memory Management Unit) - Unidad de Gestión de Memoria

La Game Boy tiene un espacio de direcciones de 16 bits (0x0000 a 0xFFFF = 65536 bytes).
Este espacio está dividido en diferentes regiones que mapean a diferentes componentes:

- 0x0000 - 0x3FFF: ROM Bank 0 (Cartucho, no cambiable)
- 0x4000 - 0x7FFF: ROM Bank N (Cartucho, switchable)
- 0x8000 - 0x9FFF: VRAM (Video RAM, 8KB)
- 0xA000 - 0xBFFF: External RAM (Cartucho, switchable)
- 0xC000 - 0xCFFF: WRAM Bank 0 (Working RAM, 4KB)
- 0xD000 - 0xDFFF: WRAM Bank 1-7 (Working RAM, switchable, 4KB)
- 0xE000 - 0xFDFF: Echo RAM (mirror de 0xC000-0xDDFF, no usar)
- 0xFE00 - 0xFE9F: OAM (Object Attribute Memory, 160 bytes)
- 0xFEA0 - 0xFEFF: No usable (prohibido)
- 0xFF00 - 0xFF7F: I/O Ports (Entrada/Salida)
- 0xFF80 - 0xFFFE: HRAM (High RAM, 127 bytes)
- 0xFFFF: IE (Interrupt Enable Register)

En esta primera iteración, usamos un bytearray lineal de 65536 bytes para simular toda la memoria.
Más adelante separaremos las regiones y añadiremos mapeo específico para cada componente.

CRÍTICO: La Game Boy usa Little-Endian para valores de 16 bits.
Esto significa que el byte menos significativo (LSB) está en la dirección más baja.

Fuente: Pan Docs - Memory Map
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cartridge import Cartridge
    from ..gpu.ppu import PPU
    from ..io.joypad import Joypad
    from ..io.timer import Timer

logger = logging.getLogger(__name__)
# Permitir INFO para diagnóstico de MBC (bank switching) y VRAM
# CRÍTICO: Establecer nivel INFO explícitamente para que los mensajes de VRAM WRITE se muestren
# independientemente del nivel del logger raíz
logger.setLevel(logging.INFO)  # Forzar INFO para diagnóstico de VRAM y MBC

# ========== Constantes de Registros de Hardware (I/O Ports) ==========
# La Game Boy controla sus periféricos escribiendo en direcciones específicas
# del rango 0xFF00-0xFF7F (Memory Mapped I/O).
# Fuente: Pan Docs - Memory Map / I/O Ports

# Registros de LCD (Pantalla)
IO_LCDC = 0xFF40  # LCD Control - Enciende/Apaga pantalla, configuración de fondo/sprites
IO_STAT = 0xFF41  # LCD Status - Estado actual del LCD (modo, flags de interrupción)
IO_SCY = 0xFF42   # Scroll Y - Posición vertical del fondo
IO_SCX = 0xFF43   # Scroll X - Posición horizontal del fondo
IO_LY = 0xFF44    # LY (Línea actual) - Solo lectura, indica qué línea se está dibujando (0-153)
IO_LYC = 0xFF45   # LYC (LY Compare) - Comparador para interrupciones de línea
IO_DMA = 0xFF46   # DMA Transfer - Inicia transferencia DMA de OAM
IO_BGP = 0xFF47   # Background Palette Data - Paleta de colores para fondo
IO_OBP0 = 0xFF48  # Object Palette 0 - Paleta de colores para sprites (prioridad 0)
IO_OBP1 = 0xFF49  # Object Palette 1 - Paleta de colores para sprites (prioridad 1)
IO_WY = 0xFF4A    # Window Y - Posición Y de la ventana
IO_WX = 0xFF4B    # Window X - Posición X de la ventana

# Registros de Interrupciones
IO_IF = 0xFF0F    # Interrupt Flag - Flags de interrupciones pendientes
IO_IE = 0xFFFF    # Interrupt Enable - Máscara de interrupciones habilitadas

# Registros de Timer
IO_DIV = 0xFF04   # Divider Register - Contador de división (incrementa continuamente)
IO_TIMA = 0xFF05  # Timer Counter - Contador del timer
IO_TMA = 0xFF06   # Timer Modulo - Valor de recarga del timer
IO_TAC = 0xFF07   # Timer Control - Control del timer (enable, frecuencia)

# Registros de Audio (APU - Audio Processing Unit)
IO_NR10 = 0xFF10  # Channel 1 Sweep
IO_NR11 = 0xFF11  # Channel 1 Length & Duty
IO_NR12 = 0xFF12  # Channel 1 Volume & Envelope
IO_NR13 = 0xFF13  # Channel 1 Frequency Low
IO_NR14 = 0xFF14  # Channel 1 Frequency High
IO_NR21 = 0xFF16  # Channel 2 Length & Duty
IO_NR22 = 0xFF17  # Channel 2 Volume & Envelope
IO_NR23 = 0xFF18  # Channel 2 Frequency Low
IO_NR24 = 0xFF19  # Channel 2 Frequency High
IO_NR30 = 0xFF1A  # Channel 3 DAC Enable
IO_NR31 = 0xFF1B  # Channel 3 Length
IO_NR32 = 0xFF1C  # Channel 3 Output Level
IO_NR33 = 0xFF1D  # Channel 3 Frequency Low
IO_NR34 = 0xFF1E  # Channel 3 Frequency High
IO_NR41 = 0xFF20  # Channel 4 Length
IO_NR42 = 0xFF21  # Channel 4 Volume & Envelope
IO_NR43 = 0xFF22  # Channel 4 Polynomial Counter
IO_NR44 = 0xFF23  # Channel 4 Counter/Consecutive
IO_NR50 = 0xFF24  # Master Volume & VIN
IO_NR51 = 0xFF25  # Sound Panning
IO_NR52 = 0xFF26  # Sound On/Off

# Registros de Joypad
IO_P1 = 0xFF00    # Joypad Input - Estado de botones y direcciones

# Mapeo de direcciones a nombres de registros (para logging)
IO_REGISTER_NAMES: dict[int, str] = {
    IO_LCDC: "LCDC",
    IO_STAT: "STAT",
    IO_SCY: "SCY",
    IO_SCX: "SCX",
    IO_LY: "LY",
    IO_LYC: "LYC",
    IO_DMA: "DMA",
    IO_BGP: "BGP",
    IO_OBP0: "OBP0",
    IO_OBP1: "OBP1",
    IO_WY: "WY",
    IO_WX: "WX",
    IO_IF: "IF",
    IO_IE: "IE",
    IO_DIV: "DIV",
    IO_TIMA: "TIMA",
    IO_TMA: "TMA",
    IO_TAC: "TAC",
    IO_NR10: "NR10",
    IO_NR11: "NR11",
    IO_NR12: "NR12",
    IO_NR13: "NR13",
    IO_NR14: "NR14",
    IO_NR21: "NR21",
    IO_NR22: "NR22",
    IO_NR23: "NR23",
    IO_NR24: "NR24",
    IO_NR30: "NR30",
    IO_NR31: "NR31",
    IO_NR32: "NR32",
    IO_NR33: "NR33",
    IO_NR34: "NR34",
    IO_NR41: "NR41",
    IO_NR42: "NR42",
    IO_NR43: "NR43",
    IO_NR44: "NR44",
    IO_NR50: "NR50",
    IO_NR51: "NR51",
    IO_NR52: "NR52",
    IO_P1: "P1",
}


class MMU:
    """
    Unidad de Gestión de Memoria (MMU) de la Game Boy.
    
    Gestiona el espacio de direcciones de 16 bits (0x0000 a 0xFFFF).
    Proporciona métodos para leer y escribir bytes (8 bits) y palabras (16 bits).
    
    En esta primera iteración, usa un almacenamiento lineal simple (bytearray).
    Más adelante se implementará mapeo específico por regiones de memoria.
    """

    # Tamaño total del espacio de direcciones (16 bits = 65536 bytes)
    MEMORY_SIZE = 0x10000  # 65536 bytes

    def __init__(self, cartridge: Cartridge | None = None) -> None:
        """
        Inicializa la MMU con un bytearray de 65536 bytes, todos inicializados a 0.
        
        CRÍTICO: La paleta BGP (0xFF47) debe inicializarse a 0xE4 para que los gráficos
        sean visibles. En una Game Boy real, la Boot ROM configura este valor antes de
        saltar al código del cartucho. Sin esta inicialización, la paleta queda en 0x00
        (todo blanco) y no se puede ver nada en pantalla.
        
        Fuente: Pan Docs - Boot ROM, BGP Register (Background Palette)
        
        Args:
            cartridge: Instancia opcional de Cartridge para mapear la ROM en memoria
        """
        # Usamos bytearray para simular la memoria completa
        # Inicializamos todos los bytes a 0
        self._memory: bytearray = bytearray(self.MEMORY_SIZE)
        
        # CRÍTICO: Inicializar paleta BGP a 0xE4 (paleta estándar Game Boy)
        # 0xE4 = 11100100 en binario:
        # - Bits 0-1 (Color 0): 00 = Blanco (0)
        # - Bits 2-3 (Color 1): 01 = Gris claro (1)
        # - Bits 4-5 (Color 2): 10 = Gris oscuro (2)
        # - Bits 6-7 (Color 3): 11 = Negro (3)
        # Esta es la configuración estándar que deja la Boot ROM
        self._memory[IO_BGP] = 0xE4
        
        # Referencia al cartucho (si está insertado)
        self._cartridge: Cartridge | None = cartridge
        
        # Referencia a la PPU (se establece después de crear ambas para evitar dependencia circular)
        # La PPU necesita la MMU para solicitar interrupciones, y la MMU necesita la PPU
        # para leer el registro LY (0xFF44)
        self._ppu: PPU | None = None
        
        # Referencia al Joypad (se establece después para evitar dependencia circular)
        # El Joypad necesita la MMU para solicitar interrupciones
        self._joypad = None  # type: ignore
        
        # Referencia al Timer (se establece después para evitar dependencia circular)
        # El Timer necesita la MMU para leer/escribir DIV
        self._timer = None  # type: ignore
        
        # Contador temporal para diagnóstico de escrituras en VRAM
        # Se usa para limitar el logging a las primeras 10 escrituras
        self.vram_write_count = 0
        
        # Mensaje informativo al inicializar (comentado para rendimiento)
        # logger.info("🔍 Diagnóstico VRAM activo: Se registrarán las primeras 10 escrituras en VRAM (0x8000-0x9FFF)")

    def read_byte(self, addr: int) -> int:
        """
        Lee un byte (8 bits) de la dirección especificada.
        
        El mapeo de memoria es:
        - 0x0000 - 0x7FFF: ROM Area (Cartucho)
        - 0x8000 - 0xFFFF: Otras regiones (VRAM, WRAM, I/O, etc.)
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
            
        Raises:
            IndexError: Si la dirección está fuera del rango válido (0x0000-0xFFFF)
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # Si está en el área de ROM (0x0000 - 0x7FFF), delegar al cartucho
        if addr <= 0x7FFF:
            if self._cartridge is not None:
                return self._cartridge.read_byte(addr)
            else:
                # Si no hay cartucho, leer de memoria interna (útil para tests)
                # En hardware real esto sería ROM del cartucho, pero para tests
                # permitimos escribir/leer directamente en memoria
                return self._memory[addr] & 0xFF
        
        # Interceptar lectura del registro LY (0xFF44)
        # LY es un registro de solo lectura que indica qué línea se está dibujando
        # Su valor viene de la PPU, no de la memoria interna
        if addr == IO_LY:
            if self._ppu is not None:
                return self._ppu.get_ly() & 0xFF
            else:
                # Si no hay PPU conectada, devolver 0 (comportamiento por defecto)
                return 0
        
        # Interceptar lectura del registro STAT (0xFF41)
        # STAT es un registro de lectura/escritura que indica el estado actual del LCD
        # Los bits 0-1 (modo PPU) son de solo lectura y vienen de la PPU
        # Los bits 2-6 son configurables por el software
        if addr == IO_STAT:
            if self._ppu is not None:
                return self._ppu.get_stat() & 0xFF
            else:
                # Si no hay PPU conectada, devolver el valor de memoria (puede tener bits configurables)
                return self._memory[addr] & 0xFF
        
        # Interceptar lectura del registro LYC (0xFF45)
        # LYC es un registro de lectura/escritura que almacena el valor de línea
        # con el que se compara LY para generar interrupciones STAT
        if addr == IO_LYC:
            if self._ppu is not None:
                return self._ppu.get_lyc() & 0xFF
            else:
                # Si no hay PPU conectada, devolver 0 (comportamiento por defecto)
                return 0
        
        # Interceptar lectura del registro P1 (0xFF00) - Joypad Input
        # El Joypad maneja su propia lógica de lectura (Active Low, selector de bits 4-5)
        if addr == IO_P1:
            if self._joypad is not None:
                return self._joypad.read() & 0xFF
            else:
                # Si no hay Joypad conectado, devolver 0xFF (todos los botones sueltos)
                # 0xFF = 11111111 = todos los bits a 1 = todos los botones sueltos
                return 0xFF
        
        # Interceptar lectura del registro DIV (0xFF04) - Timer Divider
        # DIV expone los 8 bits altos del contador interno del Timer
        if addr == IO_DIV:
            if self._timer is not None:
                return self._timer.read_div() & 0xFF
            else:
                # Si no hay Timer conectado, devolver 0 (comportamiento por defecto)
                return 0
        
        # Interceptar lectura del registro TIMA (0xFF05) - Timer Counter
        if addr == IO_TIMA:
            if self._timer is not None:
                return self._timer.read_tima() & 0xFF
            else:
                return 0
        
        # Interceptar lectura del registro TMA (0xFF06) - Timer Modulo
        if addr == IO_TMA:
            if self._timer is not None:
                return self._timer.read_tma() & 0xFF
            else:
                return 0
        
        # Interceptar lectura del registro TAC (0xFF07) - Timer Control
        if addr == IO_TAC:
            if self._timer is not None:
                return self._timer.read_tac() & 0xFF
            else:
                return 0
        
        # Para otras regiones, leer de la memoria interna
        return self._memory[addr] & 0xFF

    def write_byte(self, addr: int, value: int) -> None:
        """
        Escribe un byte (8 bits) en la dirección especificada.
        
        Si la dirección está en el rango I/O (0xFF00-0xFF7F), se registra un log
        informativo con el nombre del registro de hardware (si es conocido).
        
        Si la dirección está en el rango ROM (0x0000-0x7FFF), la escritura se envía
        al cartucho para comandos MBC (Memory Bank Controller). Esto permite que
        el juego cambie de banco ROM escribiendo en direcciones que normalmente
        serían de solo lectura.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (se enmascara a 8 bits)
            
        Raises:
            IndexError: Si la dirección está fuera del rango válido (0x0000-0xFFFF)
            
        Fuente: Pan Docs - MBC1 Memory Bank Controller
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # Enmascaramos el valor a 8 bits (asegura que esté en rango 0x00-0xFF)
        value = value & 0xFF
        
        # Si está en el área de ROM (0x0000 - 0x7FFF), enviar al cartucho para comandos MBC
        # Aunque la ROM es "Read Only", el MBC interpreta escrituras como comandos
        if addr <= 0x7FFF:
            if self._cartridge is not None:
                # Logging para diagnóstico: escrituras en rango de cambio de banco (comentado para rendimiento)
                # if 0x2000 <= addr < 0x4000:
                #     logger.info(f"MMU: Escritura en rango MBC (0x{addr:04X}) = 0x{value:02X} -> Cartucho")
                self._cartridge.write_byte(addr, value)
                return
            # Si no hay cartucho, permitir escritura directa en memoria (útil para tests)
            self._memory[addr] = value
            return
        
        # Si está en el rango I/O (0xFF00-0xFF7F), registrar log de debug (comentado para rendimiento)
        # if 0xFF00 <= addr <= 0xFF7F:
        #     reg_name = IO_REGISTER_NAMES.get(addr, f"IO_0x{addr:04X}")
        #     logger.debug(f"IO WRITE: {reg_name} = 0x{value:02X} (addr: 0x{addr:04X})")
        
        # Interceptar escritura al registro LY (0xFF44)
        # LY es de solo lectura, pero algunos juegos intentan escribir en él
        # En hardware real, escribir en LY no tiene efecto (se ignora silenciosamente)
        if addr == IO_LY:
            # logger.debug(f"IO WRITE: LY (solo lectura, ignorado) = 0x{value:02X}")
            return  # Ignorar escritura a LY
        
        # HACK TEMPORAL: Interceptar escritura a BGP (0xFF47) para forzar paleta visible
        # Algunos juegos (especialmente Dual Mode CGB/DMG) escriben 0x00 en BGP,
        # lo que hace que toda la pantalla sea blanca (paleta completamente blanca).
        # Este hack fuerza BGP a 0xE4 (paleta estándar Game Boy) cuando se intenta
        # escribir 0x00, permitiendo ver los gráficos mientras investigamos por qué
        # el juego está escribiendo 0x00.
        # 
        # NOTA: Este es un hack temporal para diagnóstico. En el futuro, cuando
        # implementemos soporte completo para CGB, el juego debería poder escribir
        # su propia paleta sin interferencia.
        # 
        # Fuente: Pan Docs - BGP Register (Background Palette)
        if addr == IO_BGP:
            if value == 0x00:
                # Forzar paleta visible (0xE4 = paleta estándar Game Boy)
                # 0xE4 = 11100100: Color 0=Blanco, Color 1=Gris claro, Color 2=Gris oscuro, Color 3=Negro
                value = 0xE4
                # Logging comentado para rendimiento (solo activar si es necesario para diagnóstico)
                # logging.warning(
                #     f"🔥 HACK: Forzando BGP 0x00 -> 0xE4 para visibilidad "
                #     f"(el juego intentó escribir paleta blanca, forzamos paleta estándar)"
                # )
        
        # Interceptar escritura al registro STAT (0xFF41)
        # STAT es de lectura/escritura, pero los bits 0-2 (modo PPU y LYC flag) son de solo lectura
        # Solo los bits 3-6 pueden ser escritos por el software
        # Los bits 0-2 siempre reflejan el estado actual de la PPU
        if addr == IO_STAT:
            # Guardar el valor escrito en memoria (para los bits configurables 3-6)
            # Los bits 0-2 se ignoran porque son de solo lectura
            # En hardware real, escribir en bits 0-2 no tiene efecto
            self._memory[addr] = value & 0xF8  # Solo guardar bits 3-7 (limpiar bits 0-2)
            # logger.debug(f"IO WRITE: STAT = 0x{value:02X} (bits 0-2 ignorados, solo 3-7 guardados)")
            return
        
        # Interceptar escritura al registro LYC (0xFF45)
        # LYC es de lectura/escritura y permite configurar el valor de línea
        # con el que se compara LY para generar interrupciones STAT
        if addr == IO_LYC:
            if self._ppu is not None:
                self._ppu.set_lyc(value)
            # También guardar en memoria para consistencia (aunque la PPU es la fuente de verdad)
            self._memory[addr] = value & 0xFF
            return
        
        # Interceptar escritura al registro P1 (0xFF00) - Joypad Input
        # El juego escribe en P1 para seleccionar qué leer (bits 4-5)
        if addr == IO_P1:
            if self._joypad is not None:
                self._joypad.write(value)
                return  # No escribir en memoria, el Joypad maneja su propio estado
        
        # Interceptar escritura al registro DIV (0xFF04) - Timer Divider
        # Cualquier escritura en DIV resetea el contador interno del Timer a 0
        if addr == IO_DIV:
            if self._timer is not None:
                self._timer.write_div(value)
                return  # No escribir en memoria, el Timer maneja su propio estado
        
        # Interceptar escritura al registro TIMA (0xFF05) - Timer Counter
        if addr == IO_TIMA:
            if self._timer is not None:
                self._timer.write_tima(value)
                return  # No escribir en memoria, el Timer maneja su propio estado
        
        # Interceptar escritura al registro TMA (0xFF06) - Timer Modulo
        if addr == IO_TMA:
            if self._timer is not None:
                self._timer.write_tma(value)
                return  # No escribir en memoria, el Timer maneja su propio estado
        
        # Interceptar escritura al registro TAC (0xFF07) - Timer Control
        if addr == IO_TAC:
            if self._timer is not None:
                self._timer.write_tac(value)
                return  # No escribir en memoria, el Timer maneja su propio estado
        
        # CRÍTICO: Trampa de diagnóstico para LCDC (comentada para rendimiento)
        # if addr == IO_LCDC:
        #     old_value = self.read_byte(IO_LCDC)
        #     logging.critical(f"[TRAP LCDC] INTENTO DE CAMBIO LCDC: {old_value:02X} -> {value:02X}")
        
        # DIAGNÓSTICO: Log cuando se escribe en IE (comentado para rendimiento)
        # if addr == IO_IE:
        #     logging.info(f"SET IE REGISTER: {value:02X} (habilitando interrupciones: V-Blank={bool(value & 0x01)}, STAT={bool(value & 0x02)}, Timer={bool(value & 0x04)})")
        
        # Interceptar escritura al registro DMA (0xFF46) - DMA Transfer
        # Cuando se escribe un valor XX en 0xFF46, se inicia una transferencia DMA
        # que copia 160 bytes desde la dirección XX00 hasta OAM (0xFE00-0xFE9F)
        # La transferencia es inmediata y bloquea el acceso a OAM durante la copia
        # Fuente: Pan Docs - DMA Transfer
        if addr == IO_DMA:
            # El valor escrito (XX) forma la dirección fuente alta: XX00
            source_base = (value << 8) & 0xFFFF  # XX00 (ej: 0xC0 -> 0xC000)
            oam_base = 0xFE00  # OAM comienza en 0xFE00
            oam_size = 160  # OAM tiene 160 bytes (40 sprites * 4 bytes)
            
            # logger.debug(f"DMA: Copiando {oam_size} bytes desde 0x{source_base:04X} a 0x{oam_base:04X}")
            
            # Copiar 160 bytes desde la dirección fuente a OAM
            # Usamos slice de bytearray para copia rápida
            for i in range(oam_size):
                source_addr = (source_base + i) & 0xFFFF
                # Leer desde la dirección fuente (puede ser ROM, RAM, VRAM, etc.)
                byte_value = self.read_byte(source_addr)
                # Escribir en OAM
                self._memory[oam_base + i] = byte_value
            
            # logger.debug(f"DMA: Transferencia completada (160 bytes copiados)")
            # Escribir el valor en el registro DMA (se mantiene el valor escrito)
            self._memory[addr] = value
            return
        
        # DIAGNÓSTICO TEMPORAL: Logging de escrituras en VRAM (comentado para rendimiento)
        # Esto nos permite verificar si el juego está intentando escribir gráficos
        # y si la MMU está bloqueando estas escrituras por alguna razón
        # Solo logueamos las primeras 10 escrituras para no saturar la consola
        # IMPORTANTE: Este código debe estar ANTES de cualquier return que pueda
        # interceptar la escritura, pero DESPUÉS de los returns de registros especiales
        # if 0x8000 <= addr <= 0x9FFF:
        #     self.vram_write_count += 1
        #     if self.vram_write_count <= 10:
        #         # Usar print() además de logger para asegurar visibilidad
        #         # flush=True para asegurar que se muestre inmediatamente
        #         print(f"💾 VRAM WRITE #{self.vram_write_count}: {value:02X} en {addr:04X}", flush=True)
        #         logger.info(f"💾 VRAM WRITE #{self.vram_write_count}: {value:02X} en {addr:04X}")
        #     elif self.vram_write_count == 11:
        #         # Mensaje informativo cuando se alcanza el límite
        #         print(f"💾 VRAM WRITE: (se han detectado más de 10 escrituras, ocultando el resto)", flush=True)
        #         logger.info(f"💾 VRAM WRITE: (se han detectado más de 10 escrituras, ocultando el resto)")
        
        # Escribimos el byte en la memoria
        # NOTA: No hay restricción de escritura en VRAM basada en modo PPU.
        # En hardware real, escribir en VRAM durante Mode 3 puede causar artefactos,
        # pero el hardware no bloquea físicamente el acceso. Los juegos deben
        # hacer polling de STAT para evitar escribir durante Pixel Transfer.
        # Fuente: Pan Docs - VRAM Access Restrictions
        self._memory[addr] = value

    def read_word(self, addr: int) -> int:
        """
        Lee una palabra (16 bits) de la dirección especificada usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian, lo que significa:
        - El byte en `addr` es el menos significativo (LSB)
        - El byte en `addr+1` es el más significativo (MSB)
        - Resultado: (byte[addr+1] << 8) | byte[addr]
        
        Ejemplo:
        - Si en 0x1000 hay 0xCD y en 0x1001 hay 0xAB
        - read_word(0x1000) devuelve 0xABCD
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE, ya que lee 2 bytes)
            
        Returns:
            Valor de 16 bits leído (0x0000 a 0xFFFF)
            
        Raises:
            IndexError: Si addr+1 está fuera del rango válido
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # Leemos el byte menos significativo (LSB) en addr
        lsb = self.read_byte(addr)
        
        # Leemos el byte más significativo (MSB) en addr+1
        # Si addr es 0xFFFF, addr+1 hace wrap-around a 0x0000
        msb = self.read_byte((addr + 1) & 0xFFFF)
        
        # Combinamos los bytes en orden Little-Endian: (MSB << 8) | LSB
        return ((msb << 8) | lsb) & 0xFFFF

    def write_word(self, addr: int, value: int) -> None:
        """
        Escribe una palabra (16 bits) en la dirección especificada usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian, lo que significa:
        - El byte menos significativo (LSB) se escribe en `addr`
        - El byte más significativo (MSB) se escribe en `addr+1`
        
        Ejemplo:
        - write_word(0x1000, 0x1234)
        - Escribe 0x34 en 0x1000 y 0x12 en 0x1001
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE, ya que escribe 2 bytes)
            value: Valor de 16 bits a escribir (se enmascara a 16 bits)
            
        Raises:
            IndexError: Si addr+1 está fuera del rango válido
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # Enmascaramos el valor a 16 bits
        value = value & 0xFFFF
        
        # Extraemos el byte menos significativo (LSB): bits 0-7
        lsb = value & 0xFF
        
        # Extraemos el byte más significativo (MSB): bits 8-15
        msb = (value >> 8) & 0xFF
        
        # Escribimos en orden Little-Endian: LSB en addr, MSB en addr+1
        self.write_byte(addr, lsb)
        # Si addr es 0xFFFF, addr+1 hace wrap-around a 0x0000
        self.write_byte((addr + 1) & 0xFFFF, msb)

    def set_ppu(self, ppu: PPU) -> None:
        """
        Establece la referencia a la PPU para permitir lectura del registro LY.
        
        Este método se llama después de crear tanto la MMU como la PPU para evitar
        dependencias circulares en el constructor.
        
        Args:
            ppu: Instancia de PPU
        """
        self._ppu = ppu
        # logger.debug("MMU: PPU conectada para lectura de LY")
    
    def set_joypad(self, joypad: Joypad) -> None:
        """
        Establece la referencia al Joypad para permitir lectura/escritura del registro P1.
        
        Este método se llama después de crear tanto la MMU como el Joypad para evitar
        dependencias circulares en el constructor.
        
        Args:
            joypad: Instancia de Joypad
        """
        self._joypad = joypad
        # logger.debug("MMU: Joypad conectado para lectura/escritura de P1")
    
    def set_timer(self, timer: Timer) -> None:
        """
        Establece la referencia al Timer para permitir lectura/escritura del registro DIV.
        
        Este método se llama después de crear tanto la MMU como el Timer para evitar
        dependencias circulares en el constructor.
        
        Args:
            timer: Instancia de Timer
        """
        self._timer = timer
        # logger.debug("MMU: Timer conectado para lectura/escritura de DIV")
    
    def get_vram_write_count(self) -> int:
        """
        Devuelve el número de escrituras en VRAM detectadas (para diagnóstico).
        
        Returns:
            Número de escrituras en VRAM detectadas desde la inicialización
        """
        return self.vram_write_count
    
    def get_vram_checksum(self) -> int:
        """
        Calcula la suma (checksum) de todos los bytes en VRAM (0x8000-0x9FFF).
        
        Este método es útil para diagnóstico: si la VRAM está vacía (todo ceros),
        el checksum será 0. Si hay datos gráficos, el checksum será > 0.
        
        Returns:
            Suma de todos los bytes en VRAM (0x8000-0x9FFF)
        """
        return sum(self._memory[0x8000:0xA000])

