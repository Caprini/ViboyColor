"""
Tests para el motor de timing de la PPU (Pixel Processing Unit).

NOTA STEP 0433: Estos tests legacy están deprecados porque:
1. Usan la clase PPU Python legacy (src.gpu.ppu.PPU) que no es la fuente de verdad
2. El core C++ PPU (PyPPU) es la implementación real y authoritative
3. Los tests equivalentes están en tests/test_core_ppu_timing.py (que usa PyPPU)

Estos tests se mantienen marcados como skip para referencia histórica.
"""

import pytest

from src.gpu.ppu import PPU
from src.memory.mmu import MMU


@pytest.mark.skip(reason="Legacy PPU Python tests - replaced by core PPU tests (Step 0433)")
class TestPPUTiming:
    """Tests para el motor de timing de la PPU."""

    def test_ly_increment(self) -> None:
        """
        Test: LY se incrementa correctamente después de 456 T-Cycles.
        
        Cada línea de escaneo tarda 456 T-Cycles. Después de procesar
        456 ciclos, LY debe incrementarse de 0 a 1.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        
        # Inicialmente LY debe ser 0
        assert ppu.get_ly() == 0
        
        # Avanzar 456 T-Cycles (una línea completa)
        ppu.step(456)
        
        # LY debe haber incrementado a 1
        assert ppu.get_ly() == 1

    def test_ly_increment_partial(self) -> None:
        """
        Test: LY no se incrementa con menos de 456 T-Cycles.
        
        Si avanzamos menos de 456 ciclos, LY debe permanecer en 0.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        
        # Avanzar solo 100 T-Cycles (menos de una línea)
        ppu.step(100)
        
        # LY debe seguir siendo 0
        assert ppu.get_ly() == 0
        
        # El clock interno debe haber acumulado 100 ciclos
        # (no podemos verificar esto directamente, pero podemos inferirlo
        # avanzando más ciclos hasta completar la línea)
        ppu.step(356)  # 100 + 356 = 456
        
        # Ahora LY debe ser 1
        assert ppu.get_ly() == 1

    def test_vblank_trigger(self) -> None:
        """
        Test: Se activa la interrupción V-Blank cuando LY llega a 144.
        
        Cuando LY alcanza 144, la PPU debe activar el bit 0 del registro
        IF (0xFF0F) para solicitar una interrupción V-Blank.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Asegurar que IF está limpio
        mmu.write_byte(0xFF0F, 0x00)
        assert mmu.read_byte(0xFF0F) == 0x00
        
        # Avanzar hasta la línea 144 (144 líneas * 456 ciclos = 65,664 ciclos)
        total_cycles = 144 * 456
        ppu.step(total_cycles)
        
        # LY debe ser 144 (inicio de V-Blank)
        assert ppu.get_ly() == 144
        
        # El bit 0 de IF (0xFF0F) debe estar activado
        if_val = mmu.read_byte(0xFF0F)
        assert (if_val & 0x01) == 0x01, f"IF debe tener bit 0 activado, pero es 0x{if_val:02X}"

    def test_frame_wrap(self) -> None:
        """
        Test: LY se reinicia a 0 después de la línea 153 (wrap-around de frame).
        
        Después de la línea 153, LY debe volver a 0 para iniciar un nuevo frame.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        
        # Avanzar hasta la línea 153 (153 líneas * 456 ciclos = 69,768 ciclos)
        total_cycles = 153 * 456
        ppu.step(total_cycles)
        
        # LY debe ser 153
        assert ppu.get_ly() == 153
        
        # Avanzar una línea más (456 ciclos adicionales)
        ppu.step(456)
        
        # LY debe haber vuelto a 0 (nuevo frame)
        assert ppu.get_ly() == 0

    def test_ly_read_from_mmu(self) -> None:
        """
        Test: La MMU puede leer LY desde la PPU a través del registro 0xFF44.
        
        Cuando se lee la dirección 0xFF44 (registro LY), la MMU debe devolver
        el valor actual de LY desde la PPU, no desde la memoria interna.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Inicialmente LY debe ser 0
        assert mmu.read_byte(0xFF44) == 0
        
        # Avanzar algunas líneas
        ppu.step(456 * 5)  # 5 líneas
        
        # LY debe ser 5
        assert ppu.get_ly() == 5
        
        # La MMU debe devolver el mismo valor
        assert mmu.read_byte(0xFF44) == 5

    def test_ly_write_ignored(self) -> None:
        """
        Test: Escribir en LY (0xFF44) no tiene efecto (registro de solo lectura).
        
        En hardware real, escribir en LY se ignora silenciosamente.
        El valor de LY solo cambia por el timing interno de la PPU.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Avanzar a línea 10
        ppu.step(456 * 10)
        assert ppu.get_ly() == 10
        
        # Intentar escribir en LY (debe ser ignorado)
        mmu.write_byte(0xFF44, 0x99)
        
        # LY debe seguir siendo 10 (no cambió por la escritura)
        assert ppu.get_ly() == 10
        assert mmu.read_byte(0xFF44) == 10

    def test_multiple_frames(self) -> None:
        """
        Test: La PPU puede procesar múltiples frames completos.
        
        Después de procesar múltiples frames (154 líneas cada uno),
        LY debe ciclar correctamente entre 0 y 153.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        
        # Procesar 3 frames completos
        # 1 frame = 154 líneas * 456 ciclos = 70,224 ciclos
        cycles_per_frame = 154 * 456
        total_cycles = cycles_per_frame * 3
        
        ppu.step(total_cycles)
        
        # Después de 3 frames completos, LY debe volver a 0
        assert ppu.get_ly() == 0

    def test_vblank_multiple_frames(self) -> None:
        """
        Test: V-Blank se activa en cada frame.
        
        La interrupción V-Blank debe activarse cada vez que LY llega a 144,
        es decir, una vez por frame.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Limpiar IF
        mmu.write_byte(0xFF0F, 0x00)
        
        # Procesar 2 frames completos
        cycles_per_frame = 154 * 456
        ppu.step(cycles_per_frame * 2)
        
        # Después de 2 frames, LY debe estar en alguna línea del tercer frame
        # (no necesariamente 0, porque puede estar en medio de una línea)
        # Pero lo importante es que V-Blank se haya activado 2 veces
        
        # Verificar que el bit 0 de IF sigue activado (o al menos se activó)
        # (En un frame completo, V-Blank se activa cuando LY=144)
        # Para verificar esto, podemos avanzar hasta LY=144 de nuevo
        current_ly = ppu.get_ly()
        if current_ly < 144:
            # Avanzar hasta LY=144
            cycles_needed = (144 - current_ly) * 456
            ppu.step(cycles_needed)
            assert ppu.get_ly() == 144
            # Verificar que V-Blank se activó
            if_val = mmu.read_byte(0xFF0F)
            assert (if_val & 0x01) == 0x01

