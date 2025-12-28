"""
Tests para interrupciones STAT y registro LYC

Estos tests validan:
- Comparación LY == LYC y actualización del bit 2 de STAT
- Solicitud de interrupción STAT cuando LY == LYC y bit 6 está activo
- Interrupciones STAT por cambio de modo (H-Blank, V-Blank, OAM Search)
- Rising edge detection (solo dispara cuando la condición pasa de False a True)
"""

import pytest

from src.gpu.ppu import PPU, PPU_MODE_0_HBLANK, PPU_MODE_1_VBLANK, PPU_MODE_2_OAM_SEARCH
from src.memory.mmu import MMU, IO_STAT, IO_LYC, IO_IF, IO_LCDC


class TestPPUStat:
    """Tests para interrupciones STAT y registro LYC"""

    def test_lyc_coincidence_flag(self) -> None:
        """
        Test: El bit 2 de STAT se activa cuando LY == LYC.
        
        Verifica que cuando LY coincide con LYC, el bit 2 de STAT se pone a 1.
        Cuando LY != LYC, el bit 2 debe estar a 0.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD (LCDC bit 7 = 1)
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Configurar LYC = 10
        mmu.write_byte(IO_LYC, 10)
        assert ppu.get_lyc() == 10
        
        # Avanzar PPU hasta LY = 10 (10 líneas * 456 ciclos = 4560 ciclos)
        ppu.step(4560)
        assert ppu.get_ly() == 10
        
        # Verificar que el bit 2 de STAT está activo (LY == LYC)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x04) != 0, "Bit 2 de STAT debe estar activo cuando LY == LYC"
        
        # Avanzar una línea más (LY = 11)
        ppu.step(456)
        assert ppu.get_ly() == 11
        
        # Verificar que el bit 2 de STAT está inactivo (LY != LYC)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x04) == 0, "Bit 2 de STAT debe estar inactivo cuando LY != LYC"

    def test_stat_interrupt_lyc_coincidence(self) -> None:
        """
        Test: Interrupción STAT se solicita cuando LY == LYC y bit 6 está activo.
        
        Verifica que cuando LY coincide con LYC y el bit 6 de STAT (LYC Int Enable)
        está activo, se activa el bit 1 de IF (LCD STAT interrupt).
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Configurar LYC = 20
        mmu.write_byte(IO_LYC, 20)
        
        # Habilitar interrupción LYC (STAT bit 6 = 1)
        mmu.write_byte(IO_STAT, 0x40)  # Bit 6 activo
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar PPU hasta LY = 20
        ppu.step(20 * 456)
        assert ppu.get_ly() == 20
        
        # Verificar que se solicitó interrupción STAT (bit 1 de IF)
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x02) != 0, "Bit 1 de IF debe estar activo (STAT interrupt)"

    def test_stat_interrupt_rising_edge(self) -> None:
        """
        Test: Interrupción STAT solo se dispara en rising edge.
        
        Verifica que la interrupción STAT solo se dispara cuando la condición
        pasa de False a True, no mientras permanece True en la misma línea.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Configurar LYC = 15
        mmu.write_byte(IO_LYC, 15)
        
        # Habilitar interrupción LYC (STAT bit 6 = 1)
        mmu.write_byte(IO_STAT, 0x40)
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta LY = 15
        ppu.step(15 * 456)
        assert ppu.get_ly() == 15
        
        # Verificar que se disparó la interrupción
        if_val_1 = mmu.read_byte(IO_IF)
        assert (if_val_1 & 0x02) != 0, "Primera interrupción debe dispararse"
        
        # Limpiar IF manualmente (simulando que la CPU procesó la interrupción)
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar dentro de la misma línea (LY sigue siendo 15)
        # No debería disparar otra interrupción porque la condición sigue siendo True
        ppu.step(200)  # Avanzar dentro de la línea 15
        assert ppu.get_ly() == 15
        
        # Verificar que NO se disparó otra interrupción
        if_val_2 = mmu.read_byte(IO_IF)
        assert (if_val_2 & 0x02) == 0, "No debe disparar otra interrupción en la misma línea"

    def test_stat_interrupt_mode_hblank(self) -> None:
        """
        Test: Interrupción STAT se solicita cuando entra en H-Blank y bit 3 está activo.
        
        Verifica que cuando la PPU entra en Mode 0 (H-Blank) y el bit 3 de STAT
        está activo, se solicita interrupción STAT.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Habilitar interrupción H-Blank (STAT bit 3 = 1)
        mmu.write_byte(IO_STAT, 0x08)  # Bit 3 activo
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta entrar en H-Blank (Mode 0)
        # En una línea visible, H-Blank ocurre después de 252 ciclos
        ppu.step(252)
        
        # Verificar que estamos en H-Blank
        assert ppu.get_mode() == PPU_MODE_0_HBLANK
        
        # Verificar que se solicitó interrupción STAT
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x02) != 0, "Bit 1 de IF debe estar activo (STAT interrupt por H-Blank)"

    def test_stat_interrupt_mode_vblank(self) -> None:
        """
        Test: Interrupción STAT se solicita cuando entra en V-Blank y bit 4 está activo.
        
        Verifica que cuando la PPU entra en Mode 1 (V-Blank) y el bit 4 de STAT
        está activo, se solicita interrupción STAT.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Habilitar interrupción V-Blank (STAT bit 4 = 1)
        mmu.write_byte(IO_STAT, 0x10)  # Bit 4 activo
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta V-Blank (línea 144)
        ppu.step(144 * 456)
        assert ppu.get_ly() == 144
        assert ppu.get_mode() == PPU_MODE_1_VBLANK
        
        # Verificar que se solicitó interrupción STAT
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x02) != 0, "Bit 1 de IF debe estar activo (STAT interrupt por V-Blank)"

    def test_stat_interrupt_mode_oam_search(self) -> None:
        """
        Test: Interrupción STAT se solicita cuando entra en OAM Search y bit 5 está activo.
        
        Verifica que cuando la PPU entra en Mode 2 (OAM Search) y el bit 5 de STAT
        está activo, se solicita interrupción STAT.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Habilitar interrupción OAM Search (STAT bit 5 = 1)
        mmu.write_byte(IO_STAT, 0x20)  # Bit 5 activo
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta el inicio de una nueva línea (Mode 2)
        # Al inicio de cada línea, el modo es Mode 2 (OAM Search)
        ppu.step(456)  # Avanzar una línea completa
        ppu.step(1)    # Avanzar 1 ciclo para estar en Mode 2
        
        # Verificar que estamos en OAM Search
        assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH
        
        # Verificar que se solicitó interrupción STAT
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x02) != 0, "Bit 1 de IF debe estar activo (STAT interrupt por OAM Search)"

    def test_lyc_write_triggers_check(self) -> None:
        """
        Test: Escribir en LYC verifica inmediatamente si LY == LYC.
        
        Verifica que cuando se escribe en LYC, se verifica inmediatamente
        si LY coincide con el nuevo valor de LYC y se solicita interrupción si corresponde.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Encender LCD
        mmu.write_byte(IO_LCDC, 0x80)
        
        # Avanzar hasta LY = 5
        ppu.step(5 * 456)
        assert ppu.get_ly() == 5
        
        # Habilitar interrupción LYC (STAT bit 6 = 1)
        mmu.write_byte(IO_STAT, 0x40)
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Escribir LYC = 5 (coincide con LY actual)
        mmu.write_byte(IO_LYC, 5)
        
        # Verificar que se solicitó interrupción STAT inmediatamente
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x02) != 0, "Bit 1 de IF debe estar activo (STAT interrupt por LYC write)"

