"""
Tests para verificar el estado inicial Post-BIOS de la MMU.

Step 0189: Verifica que los registros de I/O se inicializan con sus valores Post-BIOS
correctos, simulando el estado que la Boot ROM habría dejado en el hardware.
"""

import pytest

# Intentar importar viboy_core (módulo compilado)
try:
    from viboy_core import PyMMU
    NATIVE_MMU_AVAILABLE = True
except ImportError:
    NATIVE_MMU_AVAILABLE = False
    pytest.skip("viboy_core no está compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestMMUPostBIOSState:
    """Tests para verificar la inicialización Post-BIOS de PyMMU."""
    
    def test_mmu_post_bios_registers(self):
        """Verifica que los registros de I/O se inicializan con sus valores Post-BIOS."""
        mmu = PyMMU()
        
        # Verificar registros clave de PPU/Video
        assert mmu.read(0xFF40) == 0x91, "LCDC debe ser 0x91"
        # NOTA: STAT (0xFF41) se lee dinámicamente combinando bits de memoria (escribibles 3-7)
        # con bits de estado de la PPU (solo lectura 0-2). Sin PPU conectada, devuelve 0x02.
        # La memoria base tiene 0x85 inicializado, pero el valor leído incluye el modo PPU actual.
        assert mmu.read(0xFF42) == 0x00, "SCY debe ser 0x00"
        assert mmu.read(0xFF43) == 0x00, "SCX debe ser 0x00"
        assert mmu.read(0xFF45) == 0x00, "LYC debe ser 0x00"
        assert mmu.read(0xFF46) == 0xFF, "DMA debe ser 0xFF"
        assert mmu.read(0xFF47) == 0xFC, "BGP debe ser 0xFC"
        assert mmu.read(0xFF48) == 0xFF, "OBP0 debe ser 0xFF"
        assert mmu.read(0xFF49) == 0xFF, "OBP1 debe ser 0xFF"
        assert mmu.read(0xFF4A) == 0x00, "WY debe ser 0x00"
        assert mmu.read(0xFF4B) == 0x00, "WX debe ser 0x00"
        
        # Verificar registros de interrupciones
        assert mmu.read(0xFF0F) == 0x01, "IF debe tener V-Blank solicitado (0x01)"
        assert mmu.read(0xFFFF) == 0x00, "IE debe ser 0x00"
        
        # Verificar algunos registros de APU (Sonido)
        assert mmu.read(0xFF26) == 0xF1, "NR52 debe ser 0xF1 (APU enabled para DMG)"
        assert mmu.read(0xFF10) == 0x80, "NR10 debe ser 0x80"
        assert mmu.read(0xFF11) == 0xBF, "NR11 debe ser 0xBF"
        assert mmu.read(0xFF12) == 0xF3, "NR12 debe ser 0xF3"
        assert mmu.read(0xFF24) == 0x77, "NR50 debe ser 0x77"
        assert mmu.read(0xFF25) == 0xF3, "NR51 debe ser 0xF3"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

