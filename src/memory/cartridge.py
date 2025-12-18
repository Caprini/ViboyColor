"""
Cartridge (Cartucho) - Carga y Parsing de ROMs de Game Boy

Los juegos de Game Boy se distribuyen como archivos binarios (`.gb` o `.gbc`).
Cada ROM tiene una estructura específica que comienza con un **Header (Cabecera)**
ubicado en las direcciones 0x0100 - 0x014F.

El Header contiene información crítica sobre el cartucho:
- Título del juego (0x0134 - 0x0143)
- Tipo de Cartucho / MBC (0x0147)
- Tamaño de ROM (0x0148)
- Tamaño de RAM (0x0149)
- Checksum (0x014D - 0x014E)

En un Game Boy real, al encender la consola, se ejecuta una **Boot ROM** interna
de 256 bytes (0x0000 - 0x00FF) que inicializa el hardware y luego salta a 0x0100
donde comienza el código del cartucho.

Como no tenemos Boot ROM todavía, simularemos el "Post-Boot State":
- PC inicializado a 0x0100 (inicio del código del cartucho)
- Registros inicializados a valores conocidos

Fuente: Pan Docs - Cartridge Header
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class Cartridge:
    """
    Representa un cartucho de Game Boy (ROM).
    
    Carga un archivo `.gb` o `.gbc` y proporciona acceso a los datos de la ROM.
    También parsea el Header para extraer información del cartucho (título, tipo, etc.).
    
    Soporta MBC1 (Memory Bank Controller 1) para ROMs mayores a 32KB.
    El MBC1 permite cambiar de banco ROM mediante escrituras en el rango 0x2000-0x3FFF.
    """

    # Direcciones del Header (según Pan Docs)
    HEADER_START = 0x0100
    HEADER_END = 0x014F
    
    # Tamaño de un banco ROM (16KB = 16384 bytes)
    ROM_BANK_SIZE = 0x4000  # 16384 bytes
    
    # Campos específicos del Header
    TITLE_START = 0x0134
    TITLE_END = 0x0143  # 16 bytes (incluye terminador 0x00)
    CARTRIDGE_TYPE = 0x0147
    ROM_SIZE = 0x0148
    RAM_SIZE = 0x0149

    def __init__(self, rom_path: str | Path) -> None:
        """
        Inicializa el cartucho cargando la ROM desde el archivo especificado.
        
        Args:
            rom_path: Ruta al archivo ROM (`.gb` o `.gbc`)
            
        Raises:
            FileNotFoundError: Si el archivo no existe
            IOError: Si hay un error al leer el archivo
        """
        # Convertir a Path para portabilidad (Windows/Linux/macOS)
        path = Path(rom_path)
        
        if not path.exists():
            raise FileNotFoundError(f"ROM no encontrada: {rom_path}")
        
        # Leer el archivo completo en modo binario
        try:
            with open(path, "rb") as f:
                self._rom_data = bytearray(f.read())
        except IOError as e:
            raise IOError(f"Error al leer ROM: {rom_path}") from e
        
        # Validar tamaño mínimo (debe tener al menos el Header)
        if len(self._rom_data) < self.HEADER_END + 1:
            raise ValueError(
                f"ROM demasiado pequeña: {len(self._rom_data)} bytes "
                f"(mínimo esperado: {self.HEADER_END + 1} bytes)"
            )
        
        logger.info(f"Cartucho cargado: {path.name} ({len(self._rom_data)} bytes)")
        
        # Parsear información del Header
        self._header_info = self._parse_header()
        
        # Inicializar MBC1: banco ROM inicial es 1 (no puede ser 0 en zona switchable)
        # Fuente: Pan Docs - MBC1: "Writing 0x00 to 0x2000-0x3FFF selects ROM bank 1"
        self._rom_bank: int = 1

    def read_byte(self, addr: int) -> int:
        """
        Lee un byte de la ROM en la dirección especificada.
        
        La ROM se mapea en el espacio de direcciones de la Game Boy:
        - 0x0000 - 0x3FFF: ROM Bank 0 (no cambiable, siempre primeros 16KB)
        - 0x4000 - 0x7FFF: ROM Bank N (switchable, apunta al banco seleccionado)
        
        Implementa MBC1: Bank Switching para ROMs mayores a 32KB.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0x7FFF)
            
        Returns:
            Byte leído (0x00 a 0xFF), o 0xFF si está fuera de rango
            
        Fuente: Pan Docs - MBC1 Memory Bank Controller
        """
        # Enmascarar dirección a 16 bits
        addr = addr & 0xFFFF
        
        # Banco 0 (fijo): 0x0000 - 0x3FFF siempre apunta a los primeros 16KB
        if addr < 0x4000:
            offset = addr
            if offset >= len(self._rom_data):
                return 0xFF
            return self._rom_data[offset] & 0xFF
        
        # Banco switchable: 0x4000 - 0x7FFF apunta al banco seleccionado
        if 0x4000 <= addr < 0x8000:
            # Calcular offset: (banco * 16384) + (addr - 0x4000)
            bank_offset = self._rom_bank * self.ROM_BANK_SIZE
            relative_offset = addr - 0x4000
            offset = bank_offset + relative_offset
            
            if offset >= len(self._rom_data):
                return 0xFF
            return self._rom_data[offset] & 0xFF
        
        # Fuera del rango de ROM
        return 0xFF
    
    def write_byte(self, addr: int, value: int) -> None:
        """
        Escribe un byte en el cartucho (comandos MBC).
        
        Aunque la ROM es "Read Only", el MBC1 interpreta escrituras en ciertos rangos
        como comandos para cambiar de banco:
        - 0x2000 - 0x3FFF: Selecciona el banco ROM (solo bits bajos 0-4)
        - 0x0000 - 0x1FFF: (Reservado para RAM enable, no implementado aún)
        - 0x4000 - 0x5FFF: (Reservado para RAM bank / ROM bank upper bits, no implementado aún)
        - 0x6000 - 0x7FFF: (Reservado para mode select, no implementado aún)
        
        Args:
            addr: Dirección de memoria (0x0000 a 0x7FFF)
            value: Valor a escribir (se enmascara a 8 bits)
            
        Fuente: Pan Docs - MBC1 Memory Bank Controller
        """
        # Enmascarar dirección y valor
        addr = addr & 0xFFFF
        value = value & 0xFF
        
        # Rango 0x2000 - 0x3FFF: ROM Bank Number (solo 5 bits bajos)
        if 0x2000 <= addr < 0x4000:
            # Extraer solo los 5 bits bajos (0x1F = 0b00011111)
            bank = value & 0x1F
            
            # Quirk de MBC1: Si el juego pide banco 0, el chip le da banco 1
            # Fuente: Pan Docs - MBC1: "Writing 0x00 to 0x2000-0x3FFF selects ROM bank 1"
            if bank == 0:
                bank = 1
            
            self._rom_bank = bank
            # Obtener tipo de cartucho para el mensaje - COMENTADO para rendimiento
            # cart_type = self._header_info.get("cartridge_type", "0x??")
            # logger.info(f"🏦 MBC: Cambio de Banco ROM a {bank:02X} (tipo {cart_type}, escritura 0x{value:02X} en 0x{addr:04X})")
        
        # Otros rangos (RAM enable, RAM bank, mode select) se ignoran por ahora
        # Deferred to v0.0.2: Implementar RAM banking y mode select cuando sea necesario

    def get_header_info(self) -> dict[str, str | int]:
        """
        Devuelve un diccionario con la información parseada del Header.
        
        Returns:
            Diccionario con:
            - 'title': Título del juego (string)
            - 'cartridge_type': Tipo de cartucho (hex string, ej: '0x00')
            - 'rom_size': Tamaño de ROM (int, en KB)
            - 'ram_size': Tamaño de RAM (int, en KB)
        """
        return self._header_info.copy()

    def _parse_header(self) -> dict[str, str | int]:
        """
        Parsea el Header de la ROM (0x0100 - 0x014F).
        
        Extrae información crítica:
        - Título (0x0134 - 0x0143)
        - Tipo de Cartucho (0x0147)
        - Tamaño de ROM (0x0148)
        - Tamaño de RAM (0x0149)
        
        Returns:
            Diccionario con la información parseada
            
        Fuente: Pan Docs - Cartridge Header
        """
        # Leer título (16 bytes, terminado en 0x00 o 0x80)
        title_bytes = self._rom_data[self.TITLE_START : self.TITLE_END + 1]
        
        # El título termina en 0x00 o 0x80, o puede usar todos los 16 bytes
        # Buscar el primer 0x00 o 0x80 para determinar el final
        title_end = len(title_bytes)
        for i, byte in enumerate(title_bytes):
            if byte == 0x00 or byte == 0x80:
                title_end = i
                break
        
        # Decodificar título como ASCII (puede contener caracteres no imprimibles)
        title = title_bytes[:title_end].decode("ascii", errors="replace").strip()
        
        # Si el título está vacío o solo tiene caracteres no imprimibles, usar "UNKNOWN"
        if not title or not title.isprintable():
            title = "UNKNOWN"
        
        # Leer tipo de cartucho (0x0147)
        cartridge_type = self._rom_data[self.CARTRIDGE_TYPE] & 0xFF
        
        # Leer tamaño de ROM (0x0148)
        rom_size_code = self._rom_data[self.ROM_SIZE] & 0xFF
        # Mapeo según Pan Docs: 0x00 = 32KB, 0x01 = 64KB, etc.
        rom_size_kb = 32 * (2 ** rom_size_code) if rom_size_code <= 0x08 else 0
        
        # Leer tamaño de RAM (0x0149)
        ram_size_code = self._rom_data[self.RAM_SIZE] & 0xFF
        # Mapeo según Pan Docs: 0x00 = No RAM, 0x01 = 2KB, 0x02 = 8KB, etc.
        ram_size_map = {
            0x00: 0,   # No RAM
            0x01: 2,   # 2KB
            0x02: 8,   # 8KB
            0x03: 32,  # 32KB
        }
        ram_size_kb = ram_size_map.get(ram_size_code, 0)
        
        header_info = {
            "title": title,
            "cartridge_type": f"0x{cartridge_type:02X}",
            "rom_size": rom_size_kb,
            "ram_size": ram_size_kb,
        }
        
        logger.debug(f"Header parseado: {header_info}")
        
        return header_info

    def get_rom_size(self) -> int:
        """
        Devuelve el tamaño total de la ROM en bytes.
        
        Returns:
            Tamaño de la ROM en bytes
        """
        return len(self._rom_data)

