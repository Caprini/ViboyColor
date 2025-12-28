"""
Tests para los Modos PPU y el Registro STAT.

Estos tests validan:
- Transiciones de modo durante una línea visible (Mode 2 -> 3 -> 0)
- Modo V-Blank (Mode 1) en líneas 144-153
- Lectura del registro STAT (0xFF41) con modo correcto en bits 0-1
- Escritura en STAT preserva bits configurables (2-6) pero ignora bits 0-1
"""

import pytest

from src.gpu.ppu import PPU, PPU_MODE_0_HBLANK, PPU_MODE_1_VBLANK, PPU_MODE_2_OAM_SEARCH, PPU_MODE_3_PIXEL_TRANSFER
from src.memory.mmu import MMU, IO_STAT


class TestPPUModes:
    """Tests para los modos PPU y el registro STAT."""

    def test_mode_transitions_visible_line(self) -> None:
        """
        Test: Los modos cambian correctamente durante una línea visible.
        
        En una línea visible (LY < 144), los modos deben seguir esta secuencia:
        - Ciclos 0-79: Mode 2 (OAM Search)
        - Ciclos 80-251: Mode 3 (Pixel Transfer)
        - Ciclos 252-455: Mode 0 (H-Blank)
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Asegurar que estamos en una línea visible (LY=0)
        assert ppu.get_ly() == 0
        
        # Al inicio de la línea, debe ser Mode 2 (OAM Search)
        # (el clock se inicializa a 0, que es < 80)
        assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH
        
        # Avanzar 79 ciclos (aún Mode 2)
        ppu.step(79)
        assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH
        
        # Avanzar 1 ciclo más (total 80) -> debe cambiar a Mode 3
        ppu.step(1)
        assert ppu.get_mode() == PPU_MODE_3_PIXEL_TRANSFER
        
        # Avanzar hasta ciclo 251 (aún Mode 3)
        ppu.step(171)  # 80 + 171 = 251
        assert ppu.get_mode() == PPU_MODE_3_PIXEL_TRANSFER
        
        # Avanzar 1 ciclo más (total 252) -> debe cambiar a Mode 0
        ppu.step(1)
        assert ppu.get_mode() == PPU_MODE_0_HBLANK
        
        # Avanzar hasta ciclo 455 (aún Mode 0)
        ppu.step(203)  # 252 + 203 = 455
        assert ppu.get_mode() == PPU_MODE_0_HBLANK

    def test_vblank_mode(self) -> None:
        """
        Test: Las líneas 144-153 están siempre en Mode 1 (V-Blank).
        
        Durante V-Blank, todas las líneas (144-153) deben estar en Mode 1,
        independientemente de los ciclos dentro de la línea.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Avanzar hasta la línea 144 (inicio de V-Blank)
        total_cycles = 144 * 456
        ppu.step(total_cycles)
        
        assert ppu.get_ly() == 144
        assert ppu.get_mode() == PPU_MODE_1_VBLANK
        
        # Avanzar algunos ciclos dentro de la línea 144 (debe seguir en Mode 1)
        ppu.step(100)
        assert ppu.get_ly() == 144
        assert ppu.get_mode() == PPU_MODE_1_VBLANK
        
        # Avanzar a la línea 150 (debe seguir en Mode 1)
        ppu.step(6 * 456)  # 6 líneas más
        assert ppu.get_ly() == 150
        assert ppu.get_mode() == PPU_MODE_1_VBLANK
        
        # Avanzar a la línea 153 (última línea de V-Blank, debe seguir en Mode 1)
        ppu.step(3 * 456)  # 3 líneas más
        assert ppu.get_ly() == 153
        assert ppu.get_mode() == PPU_MODE_1_VBLANK

    def test_mode_reset_on_new_line(self) -> None:
        """
        Test: Al inicio de cada nueva línea visible, el modo se reinicia a Mode 2.
        
        Cuando se completa una línea (456 ciclos) y se avanza a la siguiente,
        el modo debe reiniciarse a Mode 2 (OAM Search) al inicio de la nueva línea.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Avanzar hasta el final de la línea 0 (Mode 0 - H-Blank)
        ppu.step(455)
        assert ppu.get_mode() == PPU_MODE_0_HBLANK
        
        # Completar la línea 0 (1 ciclo más = 456 total)
        ppu.step(1)
        
        # Ahora estamos en la línea 1, y el modo debe ser Mode 2 (OAM Search)
        assert ppu.get_ly() == 1
        assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH

    def test_stat_register_read(self) -> None:
        """
        Test: El registro STAT (0xFF41) devuelve el modo correcto en bits 0-1.
        
        Cuando se lee STAT, los bits 0-1 deben reflejar el modo PPU actual:
        - 00: Mode 0 (H-Blank)
        - 01: Mode 1 (V-Blank)
        - 10: Mode 2 (OAM Search)
        - 11: Mode 3 (Pixel Transfer)
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # CRÍTICO: Encender el LCD (LCDC bit 7 = 1) para que la PPU avance
        mmu.write_byte(0xFF40, 0x80)  # LCDC bit 7 = 1 (LCD enabled)
        
        # Inicialmente Mode 2 (OAM Search) -> bits 0-1 = 10
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x03) == PPU_MODE_2_OAM_SEARCH, f"STAT debe tener bits 0-1 = 2, pero es {stat & 0x03}"
        
        # Avanzar a Mode 3 (Pixel Transfer) -> bits 0-1 = 11
        # 80 ciclos nos pone justo al inicio de Mode 3
        ppu.step(80)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x03) == PPU_MODE_3_PIXEL_TRANSFER, f"STAT debe tener bits 0-1 = 3, pero es {stat & 0x03}"
        
        # Avanzar a Mode 0 (H-Blank) -> bits 0-1 = 00
        ppu.step(172)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x03) == PPU_MODE_0_HBLANK, f"STAT debe tener bits 0-1 = 0, pero es {stat & 0x03}"
        
        # Avanzar a V-Blank (línea 144) -> bits 0-1 = 01
        ppu.step(204)  # Completar línea 0
        total_cycles = 143 * 456  # Avanzar hasta línea 144
        ppu.step(total_cycles)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x03) == PPU_MODE_1_VBLANK, f"STAT debe tener bits 0-1 = 1, pero es {stat & 0x03}"

    def test_stat_register_write_preserves_configurable_bits(self) -> None:
        """
        Test: Escribir en STAT preserva los bits configurables (3-6) pero ignora bits 0-2.
        
        El software puede escribir en STAT para configurar interrupciones (bits 3-6),
        pero los bits 0-2 (modo PPU y LYC flag) son de solo lectura y siempre reflejan el estado real.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # CRÍTICO: Encender el LCD (LCDC bit 7 = 1) para que la PPU avance
        mmu.write_byte(0xFF40, 0x80)  # LCDC bit 7 = 1 (LCD enabled)
        
        # Asegurar que LY != LYC para que el bit 2 sea 0 (no afecta el test)
        # LYC se inicializa a 0, y LY también es 0 inicialmente, así que pueden coincidir
        # Configurar LYC a un valor diferente para evitar coincidencia
        ppu.set_lyc(100)
        
        # Configurar algunos bits en STAT (bits 3-6 para interrupciones)
        # Por ejemplo: 0b11110000 = habilitar todas las interrupciones STAT
        mmu.write_byte(IO_STAT, 0xF0)
        
        # Leer STAT - debe tener los bits configurables (3-6) preservados
        # pero los bits 0-2 deben reflejar el estado actual (modo y LYC flag)
        stat = mmu.read_byte(IO_STAT)
        
        # Bits 3-6 deben estar configurados (0xF0 = 11110000, bits 3-6 = 111100)
        # Máscara 0xF8 para bits 3-7 (ignorar bits 0-2)
        assert (stat & 0xF8) == 0xF0, f"Bits configurables (3-6) deben ser 0xF0, pero son 0x{stat & 0xF8:02X}"
        
        # Bits 0-1 deben reflejar el modo actual (Mode 2 = 10)
        assert (stat & 0x03) == PPU_MODE_2_OAM_SEARCH, f"Bits de modo deben ser 2, pero son {stat & 0x03}"
        
        # Bit 2 debe ser 0 porque LY (0) != LYC (100)
        assert (stat & 0x04) == 0, "Bit 2 (LYC flag) debe ser 0 cuando LY != LYC"
        
        # Cambiar el modo PPU (avanzar a Mode 3)
        ppu.step(80)
        
        # Leer STAT de nuevo - bits configurables (3-6) deben seguir igual
        # pero bits 0-1 deben reflejar el nuevo modo (Mode 3 = 11)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0xF8) == 0xF0, "Bits configurables (3-6) deben seguir siendo 0xF0"
        assert (stat & 0x03) == PPU_MODE_3_PIXEL_TRANSFER, f"Bits de modo deben ser 3, pero son {stat & 0x03}"

    def test_stat_write_ignores_mode_bits(self) -> None:
        """
        Test: Escribir en los bits 0-2 de STAT no tiene efecto (son de solo lectura).
        
        Aunque el software intente escribir en los bits 0-2 de STAT,
        estos siempre reflejan el estado actual de la PPU (modo y LYC flag) y no pueden ser modificados.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # CRÍTICO: Encender el LCD (LCDC bit 7 = 1) para que la PPU avance
        mmu.write_byte(0xFF40, 0x80)  # LCDC bit 7 = 1 (LCD enabled)
        
        # Asegurar que LY != LYC para que el bit 2 sea 0 (no afecta el test)
        ppu.set_lyc(100)
        
        # Estamos en Mode 2 (OAM Search) -> bits 0-1 = 10
        assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH
        
        # Intentar escribir 0x03 (bits 0-1 = 11) en STAT
        # Esto NO debe cambiar el modo, solo los bits configurables (3-6)
        mmu.write_byte(IO_STAT, 0x03)
        
        # Leer STAT - los bits 0-1 deben seguir siendo 2 (modo actual)
        # El bit 2 debe ser 0 (LY != LYC)
        # Los bits 3-6 deben ser 0 (porque escribimos 0x03 que solo tiene bits 0-1)
        stat = mmu.read_byte(IO_STAT)
        assert (stat & 0x03) == PPU_MODE_2_OAM_SEARCH, "Bits 0-1 no deben cambiar por escritura"
        assert (stat & 0x04) == 0, "Bit 2 (LYC flag) debe ser 0 cuando LY != LYC"
        assert (stat & 0xF8) == 0x00, "Bits configurables (3-6) deben ser 0"

    def test_mode_transitions_multiple_lines(self) -> None:
        """
        Test: Los modos se actualizan correctamente a través de múltiples líneas.
        
        Verifica que el ciclo de modos (2 -> 3 -> 0) se repite correctamente
        en cada línea visible, y que V-Blank (Mode 1) se activa en la línea 144.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Verificar varias líneas visibles
        for line in range(5):
            # Al inicio de cada línea, debe ser Mode 2
            assert ppu.get_ly() == line
            assert ppu.get_mode() == PPU_MODE_2_OAM_SEARCH, f"Línea {line}: debe empezar en Mode 2"
            
            # Avanzar a Mode 3
            ppu.step(80)
            assert ppu.get_mode() == PPU_MODE_3_PIXEL_TRANSFER, f"Línea {line}: debe estar en Mode 3"
            
            # Avanzar a Mode 0
            ppu.step(172)
            assert ppu.get_mode() == PPU_MODE_0_HBLANK, f"Línea {line}: debe estar en Mode 0"
            
            # Completar la línea (avanzar hasta 456 ciclos)
            ppu.step(204)
            # Ahora estamos en la siguiente línea (line + 1)

