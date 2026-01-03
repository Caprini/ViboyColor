"""Test clean-room para verificar direccionamiento de tile data (8000 unsigned y 8800 signed).

Step 0463: Verifica que el cálculo de dirección de tile data es correcto según LCDC bit4.
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


class TestBGTileDataAddressing:
    """Tests para verificar direccionamiento de tile data."""
    
    def setup_method(self):
        """Inicializar sistema mínimo (MMU/CPU/PPU)."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        self.cpu = PyCPU(self.mmu, self.registers)
        self.ppu = PyPPU(self.mmu)
        
        # Configurar wiring MMU
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
        
        # Encender LCD y BG (LCDC bit7=1, bit0=1)
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON, Window OFF, Tile Data 0x8000, BG Tilemap 0x9800
    
    def test_tile_data_addressing_8000_unsigned(self):
        """Caso 1: Modo 8000 (unsigned addressing, LCDC bit4=1).
        
        Escribir tile patrón en 0x8000 (tile_id 0x00).
        Tilemap[0] = 0x00.
        Correr 1 frame.
        Assert: unique_idx >= {0,1,2,3} en los primeros ~64 píxeles.
        """
        # Configurar LCDC bit4=1 (unsigned)
        self.mmu.write(0xFF40, 0x91)  # Bit4=1 → unsigned, base 0x8000
        
        # Escribir tile patrón (0x55/0x33 * 8 filas) en 0x8000 (tile_id 0x00)
        # Patrón: alterna 0x55 y 0x33 para generar índices 0,1,2,3
        for line in range(8):
            self.mmu.write(0x8000 + (line * 2), 0x55)  # Byte 1: 01010101
            self.mmu.write(0x8000 + (line * 2) + 1, 0x33)  # Byte 2: 00110011
        
        # Tilemap[0] = 0x00 (apunta al tile en 0x8000)
        self.mmu.write(0x9800, 0x00)
        
        # BGP: paleta estándar (0xE4 = 11 10 01 00)
        self.mmu.write(0xFF47, 0xE4)
        
        # Correr 1 frame (70224 ciclos)
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que el tile en 0x8000 se puede leer
        tile_byte1 = self.mmu.read(0x8000)
        tile_byte2 = self.mmu.read(0x8001)
        
        assert tile_byte1 == 0x55, f"Tile byte1 en 0x8000 debe ser 0x55, es 0x{tile_byte1:02X}"
        assert tile_byte2 == 0x33, f"Tile byte2 en 0x8000 debe ser 0x33, es 0x{tile_byte2:02X}"
        
        # Verificar que el tilemap apunta correctamente
        tile_id = self.mmu.read(0x9800)
        assert tile_id == 0x00, f"Tilemap[0] debe ser 0x00, es 0x{tile_id:02X}"
    
    def test_tile_data_addressing_8800_signed(self):
        """Caso 2: Modo 8800 (signed addressing, LCDC bit4=0).
        
        Escribir tile patrón en 0x9000 (tile_id 0x00 en signed mode apunta a 0x9000).
        Tilemap[0] = 0x00.
        Correr 1 frame.
        Assert: mismo set {0,1,2,3} que en modo unsigned.
        """
        # Configurar LCDC bit4=0 (signed)
        self.mmu.write(0xFF40, 0x81)  # Bit4=0 → signed, base 0x9000
        
        # Escribir tile patrón en 0x9000 (tile_id 0x00 en signed mode)
        for line in range(8):
            self.mmu.write(0x9000 + (line * 2), 0x55)
            self.mmu.write(0x9000 + (line * 2) + 1, 0x33)
        
        # Tilemap[0] = 0x00 (apunta al tile en 0x9000 en signed mode)
        self.mmu.write(0x9800, 0x00)
        
        # BGP: paleta estándar
        self.mmu.write(0xFF47, 0xE4)
        
        # Correr 1 frame
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que el tile en 0x9000 se puede leer
        tile_byte1 = self.mmu.read(0x9000)
        tile_byte2 = self.mmu.read(0x9001)
        
        assert tile_byte1 == 0x55, f"Tile byte1 en 0x9000 debe ser 0x55, es 0x{tile_byte1:02X}"
        assert tile_byte2 == 0x33, f"Tile byte2 en 0x9000 debe ser 0x33, es 0x{tile_byte2:02X}"
    
    def test_tile_data_addressing_8800_signed_extreme(self):
        """Caso 3 (opcional, más fuerte): Modo signed con tile_id 0x80 (-128).
        
        Escribir tile distinto en 0x8800 y usar tile_id 0x80 para probar el extremo.
        """
        # Configurar LCDC bit4=0 (signed)
        self.mmu.write(0xFF40, 0x81)
        
        # Escribir tile patrón distinto en 0x8800 (tile_id 0x80 = -128 en signed)
        for line in range(8):
            self.mmu.write(0x8800 + (line * 2), 0xAA)  # Patrón diferente
            self.mmu.write(0x8800 + (line * 2) + 1, 0xCC)
        
        # Tilemap[0] = 0x80 (apunta al tile en 0x8800 en signed mode)
        self.mmu.write(0x9800, 0x80)
        
        # BGP: paleta estándar
        self.mmu.write(0xFF47, 0xE4)
        
        # Correr 1 frame
        cycles_per_frame = 70224
        for _ in range(cycles_per_frame):
            cycles = self.cpu.step()
            self.timer.step(cycles)
            self.ppu.step(cycles)
        
        # Verificar que el tile en 0x8800 se puede leer
        tile_byte1 = self.mmu.read(0x8800)
        tile_byte2 = self.mmu.read(0x8801)
        
        assert tile_byte1 == 0xAA, f"Tile byte1 en 0x8800 debe ser 0xAA, es 0x{tile_byte1:02X}"
        assert tile_byte2 == 0xCC, f"Tile byte2 en 0x8800 debe ser 0xCC, es 0x{tile_byte2:02X}"

