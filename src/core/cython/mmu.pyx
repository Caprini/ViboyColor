# distutils: language = c++

"""
Wrapper Cython para MMU (Memory Management Unit).

Este módulo expone la clase C++ MMU a Python, permitiendo
acceso de alta velocidad a la memoria del Game Boy.
"""

from libc.stdint cimport uint8_t, uint16_t
from libcpp cimport bool

# Importar la definición de la clase C++ desde el archivo .pxd
cimport mmu
cimport ppu

# NOTA: PyPPU se define en ppu.pyx, pero como native_core.pyx incluye ambos módulos,
# PyPPU estará disponible en tiempo de ejecución. Para evitar dependencia circular,
# usamos una función helper que accede al atributo _ppu directamente.

cdef class PyMMU:
    """
    Wrapper Python para MMU.
    
    Esta clase permite usar MMU desde Python manteniendo
    el rendimiento de C++ (acceso directo a memoria sin overhead).
    """
    cdef mmu.MMU* _mmu
    
    def __cinit__(self):
        """Constructor: crea la instancia C++."""
        self._mmu = new mmu.MMU()
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._mmu != NULL:
            del self._mmu
    
    def read(self, uint16_t addr):
        """
        Lee un byte (8 bits) de la dirección especificada.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
        """
        return self._mmu.read(addr)
    
    def write(self, uint16_t addr, uint8_t value):
        """
        Escribe un byte (8 bits) en la dirección especificada.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (0x00 a 0xFF)
        """
        self._mmu.write(addr, value)
    
    def load_rom_py(self, bytes rom_data):
        """
        Carga datos ROM en memoria, empezando en la dirección 0x0000.
        
        Este método recibe bytes de Python, obtiene su puntero y longitud,
        y llama al método C++ load_rom.
        
        Args:
            rom_data: Bytes de Python con los datos ROM
        """
        # Obtener puntero y longitud de los bytes de Python
        cdef const uint8_t* data_ptr = <const uint8_t*>rom_data
        cdef size_t data_size = len(rom_data)
        
        # Llamar al método C++
        self._mmu.load_rom(data_ptr, data_size)
    
    # ============================================================
    # MÉTODOS DE COMPATIBILIDAD CON API PYTHON ANTIGUA
    # ============================================================
    # El código Python existente (renderer.py, cpu/core.py) espera
    # métodos read_byte/write_byte/read_word/write_word.
    # Estos métodos son alias que mantienen la retrocompatibilidad.
    
    def read_byte(self, uint16_t addr):
        """
        Alias de read() para compatibilidad con código Python antiguo.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            
        Returns:
            Valor del byte leído (0x00 a 0xFF)
        """
        return self.read(addr)
    
    def write_byte(self, uint16_t addr, uint8_t value):
        """
        Alias de write() para compatibilidad con código Python antiguo.
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFF)
            value: Valor a escribir (0x00 a 0xFF)
        """
        self.write(addr, value)
    
    def read_word(self, uint16_t addr):
        """
        Lee una palabra (16 bits) usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian:
        - LSB en addr, MSB en addr+1
        - Resultado: (MSB << 8) | LSB
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE)
            
        Returns:
            Valor de 16 bits leído (0x0000 a 0xFFFF)
        """
        # Leer LSB (menos significativo) en addr
        cdef uint8_t lsb = self.read(addr)
        
        # Leer MSB (más significativo) en addr+1 (con wrap-around)
        cdef uint8_t msb = self.read((addr + 1) & 0xFFFF)
        
        # Combinar en Little-Endian: (MSB << 8) | LSB
        return ((msb << 8) | lsb) & 0xFFFF
    
    def write_word(self, uint16_t addr, uint16_t value):
        """
        Escribe una palabra (16 bits) usando Little-Endian.
        
        CRÍTICO: La Game Boy usa Little-Endian:
        - LSB se escribe en addr
        - MSB se escribe en addr+1
        
        Args:
            addr: Dirección de memoria (0x0000 a 0xFFFE)
            value: Valor de 16 bits a escribir
        """
        # Extraer LSB y MSB
        cdef uint8_t lsb = value & 0xFF
        cdef uint8_t msb = (value >> 8) & 0xFF
        
        # Escribir en orden Little-Endian
        self.write(addr, lsb)
        self.write((addr + 1) & 0xFFFF, msb)
    
    def set_ppu(self, object ppu_obj):
        """
        Establece el puntero a la PPU para permitir lectura dinámica del registro STAT.
        
        El registro STAT (0xFF41) tiene bits de solo lectura (0-2) que son actualizados
        dinámicamente por la PPU. Para leer el valor correcto, la MMU necesita llamar
        a PPU::get_stat() cuando se lee 0xFF41.
        
        Args:
            ppu_obj: Instancia de PyPPU (debe tener un método get_cpp_ptr_as_int())
        """
        # Usar object en lugar de PyPPU para evitar dependencia circular en tiempo de compilación
        # En tiempo de ejecución, ppu_obj será una instancia de PyPPU
        cdef ppu.PPU* c_ppu = NULL
        cdef long ptr_int
        if ppu_obj is not None:
            # Llamar al método get_cpp_ptr_as_int() que devuelve el puntero como entero
            # Luego convertimos el entero de vuelta a puntero C++
            ptr_int = ppu_obj.get_cpp_ptr_as_int()
            c_ppu = <ppu.PPU*>ptr_int
        self._mmu.setPPU(c_ppu)
    
    # NOTA: El miembro _mmu es accesible desde otros módulos Cython
    # que incluyan este archivo (como cpu.pyx)

