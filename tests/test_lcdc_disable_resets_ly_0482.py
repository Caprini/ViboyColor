"""
Step 0482: Test para verificar que LCDC disable resetea LY y estabiliza STAT mode.

Este test valida el comportamiento cuando LCDC bit7 pasa de 1→0 (LCD se apaga):
- LY se resetea a 0
- STAT mode se establece en estado estable (Mode 0 = HBlank)
- lcdc_disable_events se incrementa

Fuente: Pan Docs - LCD Control Register (FF40 - LCDC), LCD Power
"""

import pytest

try:
    from viboy_core import PyMMU, PyPPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)

# Direcciones de registros
IO_LCDC = 0xFF40  # LCD Control
IO_STAT = 0xFF41  # LCD Status


class TestLCDCDisableResetsLY:
    """Tests para verificar que LCDC disable resetea LY y estabiliza STAT mode"""
    
    def test_lcdc_disable_resets_ly(self):
        """
        Test: Verificar que cuando LCDC bit7 pasa de 1→0, LY se resetea a 0 y STAT mode se estabiliza.
        
        1. Inicializar sistema mínimo (MMU/PPU)
        2. Escribir LCDC con bit7=1 (encender LCD)
        3. Dejar correr ciclos suficientes (456 ciclos × 10 scanlines = 4560 ciclos)
        4. Confirmar LY progresa (debe ser > 0)
        5. Escribir LCDC con bit7=0 (apagar LCD)
        6. Dejar correr ciclos suficientes
        7. Verificar:
           - LY → 0 y se estabiliza
           - STAT mode en estado estable (Mode 0 = HBlank)
           - lcdc_disable_events == 1
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        mmu.set_ppu(ppu)
        
        # Paso 1: Escribir LCDC con bit7=1 (encender LCD)
        # LCDC = 0x91 = 10010001 (bit 7=1, bit 4=1, bit 0=1)
        mmu.write(IO_LCDC, 0x91)
        
        # Verificar estado inicial
        assert mmu.get_lcdc_disable_events() == 0, "Inicialmente no debe haber eventos de disable"
        assert ppu.get_ly() == 0, "LY debe iniciar en 0"
        
        # Paso 2: Dejar correr ciclos suficientes (456 ciclos × 10 scanlines = 4560 ciclos)
        # Esto debería hacer que LY progrese
        ppu.step(4560)
        
        # Paso 3: Confirmar LY progresa (debe ser > 0)
        ly_after_10_lines = ppu.get_ly()
        assert ly_after_10_lines > 0, f"LY debe progresar después de 10 scanlines, es {ly_after_10_lines}"
        assert ly_after_10_lines == 10, f"LY debe ser 10 después de 4560 ciclos (10 scanlines), es {ly_after_10_lines}"
        
        # Verificar que aún no hay eventos de disable
        assert mmu.get_lcdc_disable_events() == 0, "No debe haber eventos de disable antes de apagar LCD"
        
        # Paso 4: Escribir LCDC con bit7=0 (apagar LCD)
        # LCDC = 0x11 = 00010001 (bit 7=0, bit 4=1, bit 0=1)
        mmu.write(IO_LCDC, 0x11)
        
        # Paso 5: Dejar correr ciclos suficientes (1000 ciclos para estabilizar)
        ppu.step(1000)
        
        # Paso 6: Verificar resultados
        # - LY → 0 y se estabiliza
        ly_after_disable = ppu.get_ly()
        assert ly_after_disable == 0, f"LY debe resetearse a 0 después de apagar LCD, es {ly_after_disable}"
        
        # Verificar que LY se mantiene en 0
        ppu.step(1000)
        ly_stable = ppu.get_ly()
        assert ly_stable == 0, f"LY debe mantenerse en 0 cuando LCD está apagado, es {ly_stable}"
        
        # - STAT mode en estado estable (Mode 0 = HBlank)
        stat_mode = ppu.get_mode()
        assert stat_mode == 0, f"STAT mode debe ser 0 (HBlank) cuando LCD está apagado, es {stat_mode}"
        
        # Verificar STAT register también refleja modo 0
        stat_register = mmu.read(IO_STAT)
        stat_mode_from_register = stat_register & 0x03
        assert stat_mode_from_register == 0, f"STAT register bits 0-1 deben ser 0 (HBlank), es {stat_mode_from_register}"
        
        # - lcdc_disable_events == 1
        disable_events = mmu.get_lcdc_disable_events()
        assert disable_events == 1, f"Debe haber 1 evento de disable, hay {disable_events}"
        
        # Verificar PC y valor de la última escritura a LCDC
        last_lcdc_write_pc = mmu.get_last_lcdc_write_pc()
        assert last_lcdc_write_pc != 0xFFFF, f"PC de última escritura a LCDC debe ser válido, es 0x{last_lcdc_write_pc:04X}"
        
        last_lcdc_write_value = mmu.get_last_lcdc_write_value()
        assert last_lcdc_write_value == 0x11, f"Valor de última escritura a LCDC debe ser 0x11, es 0x{last_lcdc_write_value:02X}"

