"""
Tests para verificar las transiciones de modo de la PPU en C++.

Este test verifica que la PPU cambia correctamente entre los 4 modos:
- Mode 0: H-Blank (CPU puede acceder a VRAM)
- Mode 1: V-Blank (CPU puede acceder a VRAM)
- Mode 2: OAM Search (CPU bloqueada de OAM)
- Mode 3: Pixel Transfer (CPU bloqueada de VRAM y OAM)

Fuente: Pan Docs - LCD Status Register (STAT), LCD Timing
"""

import pytest

try:
    from viboy_core import PyPPU, PyMMU
    CPP_CORE_AVAILABLE = True
except ImportError:
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Saltando tests de PPU C++.", allow_module_level=True)


class TestPPUModes:
    """Tests para verificar las transiciones de modo de la PPU."""
    
    def test_ppu_mode_transitions(self):
        """Verifica las transiciones de modo de la PPU durante una scanline."""
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        mmu.set_ppu(ppu)  # <--- ¡¡ESTA ES LA LÍNEA QUE FALTABA!!
        
        mmu.write(0xFF40, 0x91)  # LCD ON
        
        # Línea 0, Inicio (Ciclos 0-79)
        assert ppu.ly == 0
        assert ppu.mode == 2  # OAMSearch
        
        # Avanzar al modo PixelTransfer
        ppu.step(80)
        assert ppu.mode == 3  # PixelTransfer
        
        # Avanzar al modo HBlank
        ppu.step(172)
        assert ppu.mode == 0  # HBlank
        
        # Avanzar a la siguiente línea
        ppu.step(204)
        assert ppu.ly == 1
        assert ppu.mode == 2  # De vuelta a OAMSearch
    
    def test_ppu_vblank_mode(self):
        """Verifica que la PPU entra en Mode 1 (V-Blank) en la línea 144."""
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Conectar PPU a MMU
        mmu.set_ppu(ppu)
        
        # Activar LCD
        mmu.write(0xFF40, 0x91)
        
        # Avanzar hasta la línea 144 (inicio de V-Blank)
        # 144 líneas * 456 T-Cycles por línea = 65,664 T-Cycles
        for _ in range(144):
            ppu.step(456)  # 456 T-Cycles
        
        assert ppu.ly == 144, f"Esperado LY=144 (V-Blank), obtenido {ppu.ly}"
        assert ppu.mode == 1, f"Esperado Mode 1 (V-Blank), obtenido {ppu.mode}"
    
    def test_ppu_stat_register(self):
        """Verifica que el registro STAT se lee correctamente con los modos PPU."""
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Conectar PPU a MMU (CRÍTICO para lectura de STAT)
        mmu.set_ppu(ppu)
        
        # Activar LCD
        mmu.write(0xFF40, 0x91)
        
        # Escribir bits configurables de STAT (bits 3-6)
        # Bit 3: H-Blank interrupt enable
        # Bit 4: V-Blank interrupt enable
        # Bit 5: OAM interrupt enable
        # Bit 6: LYC=LY interrupt enable
        mmu.write(0xFF41, 0x78)  # Todos los bits de interrupción activos
        
        # Leer STAT - debe incluir el modo actual en bits 0-1
        stat = mmu.read(0xFF41)
        
        # Verificar que los bits 0-1 contienen el modo actual
        mode_from_stat = stat & 0x03
        assert mode_from_stat == ppu.mode, f"Modo en STAT ({mode_from_stat}) no coincide con modo PPU ({ppu.mode})"
        
        # Verificar que los bits configurables (3-6) se preservan
        config_bits = (stat >> 3) & 0x0F
        assert config_bits == 0x0F, f"Bits configurables de STAT no se preservaron correctamente: {config_bits:04b}"
    
    def test_ppu_stat_lyc_coincidence(self):
        """Verifica que el bit 2 de STAT (LYC=LY Coincidence) se actualiza correctamente."""
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Conectar PPU a MMU
        mmu.set_ppu(ppu)
        
        # Activar LCD
        mmu.write(0xFF40, 0x91)
        
        # Establecer LYC a 10
        ppu.lyc = 10
        
        # Avanzar hasta la línea 10
        for _ in range(10):
            ppu.step(456)  # 456 T-Cycles por línea
        
        assert ppu.ly == 10, f"Esperado LY=10, obtenido {ppu.ly}"
        
        # Leer STAT - el bit 2 debe estar activo (LY == LYC)
        stat = mmu.read(0xFF41)
        assert (stat & 0x04) != 0, "Bit 2 de STAT (LYC=LY Coincidence) debe estar activo cuando LY == LYC"
        
        # Avanzar una línea más
        ppu.step(456)  # 456 T-Cycles
        assert ppu.ly == 11, f"Esperado LY=11, obtenido {ppu.ly}"
        
        # Leer STAT - el bit 2 debe estar inactivo (LY != LYC)
        stat = mmu.read(0xFF41)
        assert (stat & 0x04) == 0, "Bit 2 de STAT (LYC=LY Coincidence) debe estar inactivo cuando LY != LYC"

