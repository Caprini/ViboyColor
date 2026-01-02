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
# OPTIMIZACIÓN: Desactivar logging a nivel CRITICAL para máximo rendimiento
# Todas las llamadas a logger.debug/info() quedan desactivadas sin overhead
logger.setLevel(logging.CRITICAL)

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

# Registros CGB (Game Boy Color) - Soporte básico
IO_KEY1 = 0xFF4D  # Speed Switch - Control de velocidad doble (CGB)
IO_VBK = 0xFF4F   # VRAM Bank - Selección de banco VRAM (CGB, bit 0)
IO_BCPS = 0xFF68  # Background Color Palette Specification - Índice y autoincremento (CGB)
IO_BCPD = 0xFF69  # Background Color Palette Data - Datos de paleta de fondo (CGB)
IO_OCPS = 0xFF6A  # Object Color Palette Specification - Índice y autoincremento (CGB)
IO_OCPD = 0xFF6B  # Object Color Palette Data - Datos de paleta de sprites (CGB)

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
    
    # Optimización de rendimiento: __slots__ reduce overhead de acceso a atributos
    __slots__ = [
        '_memory', '_cartridge', '_ppu', '_joypad', '_timer', 'vram_write_count', '_renderer',
        '_vram_bank', '_vram_banks', '_bg_palette_index', '_bg_palette_autoinc',
        '_obj_palette_index', '_obj_palette_autoinc', '_bg_palette_data', '_obj_palette_data',
        '_key1_speed_switch'
    ]

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
        
        # CGB: VRAM Banking (0xFF4F)
        # La Game Boy Color tiene 2 bancos de VRAM (8KB cada uno)
        # Bit 0 de 0xFF4F selecciona el banco (0 o 1)
        # Fuente: Pan Docs - CGB Registers, VRAM Banking
        self._vram_bank: int = 0  # Banco actual (0 o 1)
        self._vram_banks: list[bytearray] = [
            bytearray(0x2000),  # Banco 0: 8KB
            bytearray(0x2000),  # Banco 1: 8KB
        ]
        # Inicializar banco 0 con la memoria principal (para compatibilidad DMG)
        # El banco 0 se mapea directamente a _memory[0x8000:0xA000]
        
        # CGB: Paletas de Color (0xFF68-0xFF6B)
        # Background Palette: 8 paletas de 4 colores cada una (32 bytes total)
        # Object Palette: 8 paletas de 4 colores cada una (32 bytes total)
        # Cada color es de 15 bits (RGB555: 5 bits por componente)
        # Fuente: Pan Docs - CGB Registers, Color Palettes
        self._bg_palette_index: int = 0  # Índice actual en paleta de fondo
        self._bg_palette_autoinc: bool = False  # Auto-incremento (bit 7 de BCPS)
        self._bg_palette_data: bytearray = bytearray(64)  # 8 paletas * 4 colores * 2 bytes
        
        self._obj_palette_index: int = 0  # Índice actual en paleta de sprites
        self._obj_palette_autoinc: bool = False  # Auto-incremento (bit 7 de OCPS)
        self._obj_palette_data: bytearray = bytearray(64)  # 8 paletas * 4 colores * 2 bytes
        
        # CGB: Speed Switch (0xFF4D)
        # Permite cambiar entre velocidad normal (1x) y doble (2x)
        # Bit 7: Preparado para cambio (read-only)
        # Bit 0: Velocidad actual (0=normal, 1=doble)
        # Fuente: Pan Docs - CGB Registers, Speed Switch
        self._key1_speed_switch: int = 0  # Por defecto, velocidad normal
        
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
        
        # Referencia al Renderer (se establece después para evitar dependencia circular)
        # El Renderer necesita la MMU para acceder a VRAM, y la MMU necesita el Renderer
        # para marcar tiles como "dirty" cuando se escribe en VRAM (Tile Caching)
        self._renderer = None  # type: ignore
        
        # Contador temporal para diagnóstico de escrituras en VRAM
        # Se usa para limitar el logging a las primeras 10 escrituras
        self.vram_write_count = 0
        
        # Mensaje informativo al inicializar (comentado para rendimiento)
        # logger.info("🔍 Diagnóstico VRAM activo: Se registrarán las primeras 10 escrituras en VRAM (0x8000-0x9FFF)")

    def read_byte(self, addr: int) -> int:
        """
        Lee un byte (8 bits) de la dirección especificada.
        
        OPTIMIZACIÓN: Reordenado para Fast Path - ROM primero (más frecuente).
        El orden de los if/elif está optimizado por frecuencia de acceso:
        1. ROM (0x0000-0x7FFF) - más frecuente (fetch de instrucciones)
        2. WRAM/HRAM (0xC000-0xFFFF) - muy frecuente
        3. IO registers (0xFF00-0xFF7F) - frecuente pero específicos
        4. VRAM (0x8000-0x9FFF) - menos frecuente
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
            
        Raises:
            IndexError: Si la dirección está fuera del rango válido (0x0000-0xFFFF)
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # OPTIMIZACIÓN FAST PATH: ROM primero (más frecuente - fetch de código)
        # Si está en el área de ROM (0x0000 - 0x7FFF), delegar al cartucho
        if addr <= 0x7FFF:
            if self._cartridge is not None:
                return self._cartridge.read_byte(addr)
            else:
                # Si no hay cartucho, leer de memoria interna (útil para tests)
                return self._memory[addr] & 0xFF
        
        # WRAM/HRAM (0xC000-0xFFFF) - muy frecuente, fast path directo
        if 0xC000 <= addr <= 0xFFFF:
            # Interceptar registros I/O específicos primero
            if addr == IO_LY:
                if self._ppu is not None:
                    return self._ppu.get_ly() & 0xFF
                return 0
            if addr == IO_STAT:
                if self._ppu is not None:
                    return self._ppu.get_stat() & 0xFF
                return self._memory[addr] & 0xFF
            if addr == IO_LYC:
                if self._ppu is not None:
                    return self._ppu.get_lyc() & 0xFF
                return 0
            if addr == IO_P1:
                if self._joypad is not None:
                    return self._joypad.read() & 0xFF
                # Sin joypad (tests): leer directamente de memoria
                return self._memory[addr] & 0xFF
            if addr == IO_DIV:
                if self._timer is not None:
                    return self._timer.read_div() & 0xFF
                return 0
            if addr == IO_TIMA:
                if self._timer is not None:
                    return self._timer.read_tima() & 0xFF
                return 0
            if addr == IO_TMA:
                if self._timer is not None:
                    return self._timer.read_tma() & 0xFF
                return 0
            if addr == IO_TAC:
                if self._timer is not None:
                    return self._timer.read_tac() & 0xFF
                return 0
            # CGB: Registros CGB
            if addr == IO_VBK:
                # Bit 0: Banco VRAM seleccionado (0 o 1)
                # Bits 1-7: Siempre 0 (read-only)
                return self._vram_bank & 0x01
            if addr == IO_KEY1:
                # Bit 7: Preparado para cambio (read-only, siempre 0 por ahora)
                # Bit 0: Velocidad actual (0=normal, 1=doble)
                # Bits 1-6: Siempre 0
                return self._key1_speed_switch & 0x01
            if addr == IO_BCPS:
                # Bit 0-5: Índice de paleta (0-63)
                # Bit 6: No usado
                # Bit 7: Auto-incremento
                result = self._bg_palette_index & 0x3F
                if self._bg_palette_autoinc:
                    result |= 0x80
                return result & 0xFF
            if addr == IO_BCPD:
                # Leer byte de datos de paleta de fondo
                idx = self._bg_palette_index & 0x3F
                value = self._bg_palette_data[idx] & 0xFF
                # Auto-incremento si está activado
                if self._bg_palette_autoinc:
                    self._bg_palette_index = (self._bg_palette_index + 1) & 0x3F
                return value
            if addr == IO_OCPS:
                # Bit 0-5: Índice de paleta (0-63)
                # Bit 6: No usado
                # Bit 7: Auto-incremento
                result = self._obj_palette_index & 0x3F
                if self._obj_palette_autoinc:
                    result |= 0x80
                return result & 0xFF
            if addr == IO_OCPD:
                # Leer byte de datos de paleta de sprites
                idx = self._obj_palette_index & 0x3F
                value = self._obj_palette_data[idx] & 0xFF
                # Auto-incremento si está activado
                if self._obj_palette_autoinc:
                    self._obj_palette_index = (self._obj_palette_index + 1) & 0x3F
                return value
            # HRAM o otros (0xFF80-0xFFFF excepto I/O)
            return self._memory[addr] & 0xFF
        
        # VRAM/OAM (0x8000-0xFEFF) - menos frecuente, al final
        # CGB: Si está en VRAM (0x8000-0x9FFF), usar el banco seleccionado
        if 0x8000 <= addr <= 0x9FFF:
            vram_offset = addr - 0x8000
            if self._vram_bank == 0:
                # Banco 0: leer de memoria principal (compatibilidad DMG)
                return self._memory[addr] & 0xFF
            else:
                # Banco 1: leer del banco secundario
                return self._vram_banks[1][vram_offset] & 0xFF
        
        # Para otras regiones (OAM, etc.), leer directamente de memoria interna
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
            # Guardar el valor anterior para comparación
            old_stat = self._memory[addr] & 0xFF
            # SI HAY PPU: Solo guardar bits 3-7 (bits 0-2 son read-only del hardware)
            # SI NO HAY PPU (tests): Guardar el valor completo para permitir verificación
            if self._ppu is not None:
                self._memory[addr] = value & 0xF8  # Solo guardar bits 3-7 (limpiar bits 0-2)
            else:
                self._memory[addr] = value & 0xFF  # Guardar valor completo para tests
            # Instrumentación para diagnóstico: detectar configuración de STAT - COMENTADO para rendimiento
            # CRÍTICO: Detectar si se activa el bit 6 (LYC interrupt enable)
            # lyc_int_enable = (value & 0x40) != 0
            # logger.info(
            #     f"👁️ STAT UPDATE: Old={old_stat:02X} New={value:02X} | "
            #     f"LYC_INT_ENABLE={lyc_int_enable} "
            #     f"(Bit 3 H-Blank: {(value & 0x08) != 0}, "
            #     f"Bit 4 V-Blank: {(value & 0x10) != 0}, "
            #     f"Bit 5 OAM: {(value & 0x20) != 0})"
            # )
            return
        
        # Interceptar escritura al registro LYC (0xFF45)
        # LYC es de lectura/escritura y permite configurar el valor de línea
        # con el que se compara LY para generar interrupciones STAT
        if addr == IO_LYC:
            # Instrumentación para diagnóstico: detectar configuración de LYC - COMENTADO para rendimiento
            # logger.info(f"👁️ LYC SET: {value}")
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
            # PASO ADICIONAL: Escribir también en memoria para compatibilidad con tests
            # que verifican el valor escrito directamente sin usar el joypad
            self._memory[addr] = value & 0xFF
            return
        
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
            # Instrumentación para diagnóstico: detectar configuración del Timer - COMENTADO para rendimiento
            # timer_enable = (value & 0x04) != 0
            # clock_select = value & 0x03
            # clock_names = {0: "4096Hz", 1: "262144Hz", 2: "65536Hz", 3: "16384Hz"}
            # clock_name = clock_names.get(clock_select, "Unknown")
            # logger.info(
            #     f"⏰ TAC UPDATE: {value:02X} (Enable={timer_enable}, Clock={clock_select} "
            #     f"({clock_name}))"
            # )
            if self._timer is not None:
                self._timer.write_tac(value)
                return  # No escribir en memoria, el Timer maneja su propio estado
        
        # CGB: Interceptar escritura a registros CGB
        if addr == IO_VBK:
            # Bit 0: Seleccionar banco VRAM (0 o 1)
            # Bits 1-7: Ignorados (solo bit 0 es válido)
            self._vram_bank = value & 0x01
            # No escribir en memoria, el estado se guarda en _vram_bank
            return
        if addr == IO_KEY1:
            # Bit 0: Velocidad deseada (0=normal, 1=doble)
            # El cambio real requiere una secuencia especial (no implementada aún)
            # Por ahora, solo guardamos el valor
            self._key1_speed_switch = value & 0x01
            # No escribir en memoria, el estado se guarda en _key1_speed_switch
            return
        if addr == IO_BCPS:
            # Bit 0-5: Índice de paleta (0-63)
            # Bit 6: No usado
            # Bit 7: Auto-incremento
            self._bg_palette_index = value & 0x3F
            self._bg_palette_autoinc = (value & 0x80) != 0
            # No escribir en memoria, el estado se guarda en variables internas
            return
        if addr == IO_BCPD:
            # Escribir byte de datos de paleta de fondo
            idx = self._bg_palette_index & 0x3F
            self._bg_palette_data[idx] = value & 0xFF
            # Auto-incremento si está activado
            if self._bg_palette_autoinc:
                self._bg_palette_index = (self._bg_palette_index + 1) & 0x3F
            # No escribir en memoria, los datos se guardan en _bg_palette_data
            return
        if addr == IO_OCPS:
            # Bit 0-5: Índice de paleta (0-63)
            # Bit 6: No usado
            # Bit 7: Auto-incremento
            self._obj_palette_index = value & 0x3F
            self._obj_palette_autoinc = (value & 0x80) != 0
            # No escribir en memoria, el estado se guarda en variables internas
            return
        if addr == IO_OCPD:
            # Escribir byte de datos de paleta de sprites
            idx = self._obj_palette_index & 0x3F
            self._obj_palette_data[idx] = value & 0xFF
            # Auto-incremento si está activado
            if self._obj_palette_autoinc:
                self._obj_palette_index = (self._obj_palette_index + 1) & 0x3F
            # No escribir en memoria, los datos se guardan en _obj_palette_data
            return
        
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
            
            # DIAGNÓSTICO: Validación de fuente antes de copiar
            # Leer el primer byte de la dirección fuente para verificar que hay datos
            first_byte = self.read_byte(source_base)
            
            # Logging detallado del DMA (INFO para visibilidad) - COMENTADO para rendimiento
            # logger.info(
            #     f"💾 DMA START: Fuente=0x{source_base:04X} (Valor[0]=0x{first_byte:02X}) -> "
            #     f"Dest=0x{oam_base:04X} (160 bytes)"
            # )
            
            # Copiar 160 bytes desde la dirección fuente a OAM
            # Usamos slice de bytearray para copia rápida
            for i in range(oam_size):
                source_addr = (source_base + i) & 0xFFFF
                # Leer desde la dirección fuente (puede ser ROM, RAM, VRAM, etc.)
                byte_value = self.read_byte(source_addr)
                # Escribir en OAM
                self._memory[oam_base + i] = byte_value
            
            # DIAGNÓSTICO: Verificar que se copió correctamente (muestra primeros 4 bytes de OAM) - COMENTADO para rendimiento
            # oam_sample = [self._memory[oam_base + i] for i in range(4)]
            # logger.info(
            #     f"💾 DMA COMPLETE: OAM[0:4] = {[f'0x{b:02X}' for b in oam_sample]} "
            #     f"(primer sprite: Y={oam_sample[0]}, X={oam_sample[1]}, Tile={oam_sample[2]}, Flags={oam_sample[3]:02X})"
            # )
            
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
        
        # CGB: Si está en VRAM (0x8000-0x9FFF), escribir en el banco seleccionado
        if 0x8000 <= addr <= 0x9FFF:
            vram_offset = addr - 0x8000
            if self._vram_bank == 0:
                # Banco 0: escribir en memoria principal (compatibilidad DMG)
                self._memory[addr] = value
            else:
                # Banco 1: escribir en el banco secundario
                self._vram_banks[1][vram_offset] = value & 0xFF
                # También actualizar memoria principal para compatibilidad (opcional)
                # self._memory[addr] = value
            
            # OPTIMIZACIÓN: Marcar tile como "dirty" si se escribe en VRAM (Tile Caching)
            # Solo los tiles en 0x8000-0x97FF (384 tiles) se cachean
            # Si se escribe en este rango, calcular el índice del tile y marcarlo como dirty
            if 0x8000 <= addr <= 0x97FF:
                # Calcular índice del tile (0-383)
                # Cada tile ocupa 16 bytes, así que: tile_index = (addr - 0x8000) // 16
                tile_index = (addr - 0x8000) // 16
                if self._renderer is not None:
                    self._renderer.mark_tile_dirty(tile_index)
            
            # Ya escribimos en VRAM, no continuar
            return
        
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
    
    def set_renderer(self, renderer) -> None:  # type: ignore
        """
        Establece la referencia al Renderer para permitir marcado de tiles como "dirty".
        
        Este método se llama después de crear tanto la MMU como el Renderer para evitar
        dependencias circulares en el constructor. Cuando se escribe en VRAM (0x8000-0x97FF),
        la MMU marca el tile correspondiente como "dirty" para que el Renderer lo actualice
        en la caché (Tile Caching).
        
        Args:
            renderer: Instancia de Renderer
        """
        self._renderer = renderer
        # logger.debug("MMU: Renderer conectado para Tile Caching")
    
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
    
    def write_byte_internal(self, addr: int, value: int) -> None:
        """
        Escribe un byte directamente en memoria sin pasar por las restricciones
        de write_byte(). Este método es para uso interno de componentes del sistema
        (como la PPU) que necesitan actualizar registros de hardware sin restricciones.
        
        CRÍTICO: Este método NO debe usarse desde código del juego. Solo para uso
        interno de componentes del emulador (PPU, Timer, etc.).
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (se enmascara a 8 bits)
        
        Fuente: Método interno para permitir actualización de registros por hardware
        """
        addr = addr & 0xFFFF
        value = value & 0xFF
        self._memory[addr] = value

