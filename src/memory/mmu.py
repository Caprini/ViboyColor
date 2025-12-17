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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .cartridge import Cartridge


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
        
        Args:
            cartridge: Instancia opcional de Cartridge para mapear la ROM en memoria
        """
        # Usamos bytearray para simular la memoria completa
        # Inicializamos todos los bytes a 0
        self._memory: bytearray = bytearray(self.MEMORY_SIZE)
        
        # Referencia al cartucho (si está insertado)
        self._cartridge: Cartridge | None = cartridge

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
        
        # Para otras regiones, leer de la memoria interna
        return self._memory[addr] & 0xFF

    def write_byte(self, addr: int, value: int) -> None:
        """
        Escribe un byte (8 bits) en la dirección especificada.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (se enmascara a 8 bits)
            
        Raises:
            IndexError: Si la dirección está fuera del rango válido (0x0000-0xFFFF)
        """
        # Aseguramos que la dirección esté en el rango válido
        addr = addr & 0xFFFF
        
        # Enmascaramos el valor a 8 bits (asegura que esté en rango 0x00-0xFF)
        value = value & 0xFF
        
        # Escribimos el byte en la memoria
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

