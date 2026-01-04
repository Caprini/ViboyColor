"""Test clean-room para verificar selección de BG tilemap base y scroll.

Step 0465: Tests corregidos con asserts de framebuffer reales (no placeholders).
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


class TestBGTilemapBaseAndScroll:
    """Tests para verificar tilemap base y scroll."""
    
    def setup_method(self):
        """Inicializar sistema mínimo."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        self.cpu = PyCPU(self.mmu, self.registers)
        self.ppu = PyPPU(self.mmu)
        
        # Conectar componentes
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
        
        # Encender LCD y BG
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON, Window OFF, Tile Data 0x8000, BG Tilemap 0x9800
        self.mmu.write(0xFF47, 0xE4)  # BGP estándar
    
    def run_one_frame(self):
        """Helper: Ejecutar hasta que PPU declare frame listo.
        
        No usa 70224 como verdad universal. Step hasta que frame_ready == True.
        Pone un cap (máximo 4 frames-worth) para evitar loops infinitos.
        """
        max_cycles = 70224 * 4  # Cap: máximo 4 frames-worth
        cycles_accumulated = 0
        frame_ready = False
        
        while not frame_ready and cycles_accumulated < max_cycles:
            cycles = self.cpu.step()
            cycles_accumulated += cycles
            self.timer.step(cycles)
            self.ppu.step(cycles)
            
            # Verificar si hay frame listo
            frame_ready = self.ppu.get_frame_ready_and_reset()
        
        # Assert que se completó un frame
        assert frame_ready, \
            f"Frame no se completó después de {cycles_accumulated} ciclos (máximo {max_cycles})"
        
        return cycles_accumulated
    
    def test_tilemap_base_select_9800(self):
        """Test 1: tilemap base select (0x9800 vs 0x9C00) - Caso 0x9800.
        
        Tile0 produce patrón P0 en primeros 8 px: [0,1,2,3,0,1,2,3]
        Tile1 produce patrón P1 distinto: [3,2,1,0,3,2,1,0]
        
        Escribir:
        - 0x9800 lleno de tile0
        - 0x9C00 lleno de tile1
        - LCDC bit3=0 → assert fila0 px[0..7] == P0
        """
        # Crear tile 0 con patrón P0: [0,1,2,3,0,1,2,3] por línea
        # Codificar patrón en tile data (cada línea = 2 bytes)
        # Patrón: índices 0,1,2,3,0,1,2,3 → bytes: 0x00, 0x11, 0x22, 0x33, 0x00, 0x11, 0x22, 0x33
        pattern_p0_bytes = [0x00, 0x11, 0x22, 0x33, 0x00, 0x11, 0x22, 0x33]
        for line in range(8):
            # Codificar: byte1 = bits bajos (píxeles 0-3), byte2 = bits altos (píxeles 4-7)
            # Para índice i: bit bajo = (i & 0x01), bit alto = ((i >> 1) & 0x01)
            # Patrón [0,1,2,3,0,1,2,3] → bits bajos: 0,1,0,1,0,1,0,1 = 0x55
            #                          → bits altos: 0,0,1,1,0,0,1,1 = 0x33
            byte1 = 0x55  # Bits bajos: 0,1,0,1,0,1,0,1
            byte2 = 0x33  # Bits altos: 0,0,1,1,0,0,1,1
            self.mmu.write(0x8000 + (line * 2), byte1)
            self.mmu.write(0x8000 + (line * 2) + 1, byte2)
        
        # Crear tile 1 con patrón P1: [3,2,1,0,3,2,1,0] por línea
        # Patrón [3,2,1,0,3,2,1,0] → bits bajos: 1,0,1,0,1,0,1,0 = 0xAA
        #                          → bits altos: 1,1,0,0,1,1,0,0 = 0xCC
        for line in range(8):
            byte1 = 0xAA  # Bits bajos: 1,0,1,0,1,0,1,0
            byte2 = 0xCC  # Bits altos: 1,1,0,0,1,1,0,0
            self.mmu.write(0x8010 + (line * 2), byte1)
            self.mmu.write(0x8010 + (line * 2) + 1, byte2)
        
        # Poner en 0x9800: tile IDs = 0
        for i in range(32 * 32):
            self.mmu.write(0x9800 + i, 0x00)
        
        # Poner en 0x9C00: tile IDs = 1
        for i in range(32 * 32):
            self.mmu.write(0x9C00 + i, 0x01)
        
        # Setear LCDC bit3=0 (tilemap base 0x9800)
        self.mmu.write(0xFF40, 0x91)  # Bit3=0 → 0x9800
        self.mmu.write(0xFF43, 0x00)  # SCX=0
        self.mmu.write(0xFF42, 0x00)  # SCY=0
        
        # Sanity check: Verificar que VRAM contiene lo escrito (usando read_raw)
        assert self.mmu.read_raw(0x8000) == 0x55, \
            f"Tile 0 byte1 en 0x8000 debe ser 0x55, es 0x{self.mmu.read_raw(0x8000):02X}"
        assert self.mmu.read_raw(0x8001) == 0x33, \
            f"Tile 0 byte2 en 0x8001 debe ser 0x33, es 0x{self.mmu.read_raw(0x8001):02X}"
        
        assert self.mmu.read_raw(0x9800) == 0x00, \
            f"Tilemap 0x9800[0] debe ser 0x00, es 0x{self.mmu.read_raw(0x9800):02X}"
        assert self.mmu.read_raw(0x9C00) == 0x01, \
            f"Tilemap 0x9C00[0] debe ser 0x01, es 0x{self.mmu.read_raw(0x9C00):02X}"
        
        # Correr 1 frame (usar helper que espera frame_ready)
        cycles = self.run_one_frame()
        
        # Assert frame_ready antes de leer framebuffer
        # (Nota: get_frame_ready_and_reset() ya fue llamado en run_one_frame(), así que debe ser False)
        assert self.ppu.get_frame_ready_and_reset() == False, \
            "Frame ya fue consumido, pero debería haber estado listo"
        
        # Verificar framebuffer: fila0 px[0..7] == P0
        indices = self.ppu.get_framebuffer_indices()
        assert indices is not None, "Framebuffer indices no disponible"
        assert len(indices) == 23040, f"Framebuffer debe tener 23040 bytes, tiene {len(indices)}"
        
        # Verificar que no está todo en 0
        non_zero_count = sum(1 for i in range(160 * 144) if (indices[i] & 0x03) != 0)
        assert non_zero_count > 0, \
            f"Framebuffer está todo en 0 ({non_zero_count} píxeles no-cero de {160*144})"
        
        row0_start = 0 * 160  # Primera fila
        
        expected_p0 = [0, 1, 2, 3, 0, 1, 2, 3]  # Patrón P0
        for i in range(8):
            actual_idx = indices[row0_start + i] & 0x03
            expected_idx = expected_p0[i]
            assert actual_idx == expected_idx, \
                f"Tilemap base 0x9800: Pixel {i} en fila 0: esperado {expected_idx}, obtenido {actual_idx}"
    
    def test_tilemap_base_select_9C00(self):
        """Test 2: tilemap base select (0x9800 vs 0x9C00) - Caso 0x9C00.
        
        LCDC bit3=1 → assert fila0 px[0..7] == P1
        """
        # Setup idéntico al anterior (tile0=P0, tile1=P1, 0x9800=tile0, 0x9C00=tile1)
        # Crear tile 0 con patrón P0
        for line in range(8):
            byte1 = 0x55
            byte2 = 0x33
            self.mmu.write(0x8000 + (line * 2), byte1)
            self.mmu.write(0x8000 + (line * 2) + 1, byte2)
        
        # Crear tile 1 con patrón P1
        for line in range(8):
            byte1 = 0xAA
            byte2 = 0xCC
            self.mmu.write(0x8010 + (line * 2), byte1)
            self.mmu.write(0x8010 + (line * 2) + 1, byte2)
        
        # Poner en 0x9800: tile IDs = 0
        for i in range(32 * 32):
            self.mmu.write(0x9800 + i, 0x00)
        
        # Poner en 0x9C00: tile IDs = 1
        for i in range(32 * 32):
            self.mmu.write(0x9C00 + i, 0x01)
        
        # Setear LCDC bit3=1 (tilemap base 0x9C00)
        self.mmu.write(0xFF40, 0x99)  # Bit3=1 → 0x9C00
        self.mmu.write(0xFF43, 0x00)  # SCX=0
        self.mmu.write(0xFF42, 0x00)  # SCY=0
        
        # Sanity check: Verificar que VRAM contiene lo escrito
        assert self.mmu.read_raw(0x9800) == 0x00, \
            f"Tilemap 0x9800[0] debe ser 0x00, es 0x{self.mmu.read_raw(0x9800):02X}"
        assert self.mmu.read_raw(0x9C00) == 0x01, \
            f"Tilemap 0x9C00[0] debe ser 0x01, es 0x{self.mmu.read_raw(0x9C00):02X}"
        
        # Correr 1 frame
        cycles = self.run_one_frame()
        
        # Verificar framebuffer: fila0 px[0..7] == P1
        indices = self.ppu.get_framebuffer_indices()
        assert indices is not None, "Framebuffer indices no disponible"
        assert len(indices) == 23040, f"Framebuffer debe tener 23040 bytes, tiene {len(indices)}"
        
        # Verificar que no está todo en 0
        non_zero_count = sum(1 for i in range(160 * 144) if (indices[i] & 0x03) != 0)
        assert non_zero_count > 0, \
            f"Framebuffer está todo en 0 ({non_zero_count} píxeles no-cero de {160*144})"
        
        row0_start = 0 * 160
        
        expected_p1 = [3, 2, 1, 0, 3, 2, 1, 0]  # Patrón P1
        for i in range(8):
            actual_idx = indices[row0_start + i] & 0x03
            expected_idx = expected_p1[i]
            assert actual_idx == expected_idx, \
                f"Tilemap base 0x9C00: Pixel {i} en fila 0: esperado {expected_idx}, obtenido {actual_idx}"
    
    def test_scx_pixel_scroll_0_to_7(self):
        """Test 3: SCX pixel scroll 0..7.
        
        Tilemap fijo (todo tile0 con patrón P0), SCY=0
        Para scx=0..7:
        - Render 1 frame
        - Assert fila0 px[0..7] == P0[(x+scx)&7]
        """
        # Crear tile 0 con patrón P0
        for line in range(8):
            byte1 = 0x55
            byte2 = 0x33
            self.mmu.write(0x8000 + (line * 2), byte1)
            self.mmu.write(0x8000 + (line * 2) + 1, byte2)
        
        # Llenar tilemap 0x9800 con tile 0
        for i in range(32 * 32):
            self.mmu.write(0x9800 + i, 0x00)
        
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON, tilemap 0x9800
        self.mmu.write(0xFF42, 0x00)  # SCY=0
        
        # Test para cada SCX de 0 a 7
        pattern_p0_indices = [0, 1, 2, 3, 0, 1, 2, 3]  # Índices del patrón P0
        
        for scx in range(8):
            self.mmu.write(0xFF43, scx)  # SCX
            
            # Correr 1 frame
            cycles = self.run_one_frame()
            
            # Verificar framebuffer: fila0 px[0..7] == P0[(x+scx)&7]
            indices = self.ppu.get_framebuffer_indices()
            assert indices is not None, "Framebuffer indices no disponible"
            assert len(indices) == 23040, f"Framebuffer debe tener 23040 bytes, tiene {len(indices)}"
            
            # Verificar que no está todo en 0
            non_zero_count = sum(1 for i in range(160 * 144) if (indices[i] & 0x03) != 0)
            assert non_zero_count > 0, \
                f"SCX={scx}: Framebuffer está todo en 0 ({non_zero_count} píxeles no-cero de {160*144})"
            
            row0_start = 0 * 160
            
            for x in range(8):
                expected_idx = pattern_p0_indices[(x + scx) % 8]
                actual_idx = indices[row0_start + x] & 0x03
                assert actual_idx == expected_idx, \
                    f"SCX={scx}, Pixel {x}: esperado {expected_idx}, obtenido {actual_idx}"
