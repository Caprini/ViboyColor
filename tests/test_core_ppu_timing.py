"""
Tests para el motor de timing de la PPU en C++ (Pixel Processing Unit).

Estos tests validan la implementación nativa de la PPU:
- Incremento correcto de LY (Línea actual)
- Activación de interrupción V-Blank cuando LY llega a 144
- Wrap-around de frame (LY vuelve a 0 después de 153)
- Gestión de modos PPU (Mode 0, 1, 2, 3)
- Interrupciones STAT con LYC

Fuente: Pan Docs - LCD Timing, V-Blank, STAT Register
"""

import pytest

try:
    from viboy_core import PyMMU, PyPPU
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="viboy_core no está disponible (compilación requerida)")


class TestCorePPUTiming:
    """Tests para el motor de timing de la PPU en C++."""

    def test_ly_increment(self) -> None:
        """
        Test: LY se incrementa correctamente después de 456 T-Cycles.
        
        Cada línea de escaneo tarda 456 T-Cycles. Después de procesar
        456 ciclos, LY debe incrementarse de 0 a 1.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD (bit 7 de LCDC = 1)
        mmu.write(0xFF40, 0x80)
        
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
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Avanzar solo 100 T-Cycles (menos de una línea)
        ppu.step(100)
        
        # LY debe seguir siendo 0
        assert ppu.get_ly() == 0
        
        # Avanzar más ciclos hasta completar la línea
        ppu.step(356)  # 100 + 356 = 456
        
        # Ahora LY debe ser 1
        assert ppu.get_ly() == 1

    def test_vblank_trigger(self) -> None:
        """
        Test: Se activa la interrupción V-Blank cuando LY llega a 144.
        
        Cuando LY alcanza 144, la PPU debe activar el bit 0 del registro
        IF (0xFF0F) para solicitar una interrupción V-Blank.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Asegurar que IF está limpio
        mmu.write(0xFF0F, 0x00)
        assert mmu.read(0xFF0F) == 0x00
        
        # Avanzar hasta la línea 144 (144 líneas * 456 ciclos = 65,664 ciclos)
        total_cycles = 144 * 456
        ppu.step(total_cycles)
        
        # LY debe ser 144 (inicio de V-Blank)
        assert ppu.get_ly() == 144
        
        # El bit 0 de IF (0xFF0F) debe estar activado
        if_val = mmu.read(0xFF0F)
        assert (if_val & 0x01) == 0x01, f"IF debe tener bit 0 activado, pero es 0x{if_val:02X}"

    def test_frame_wrap(self) -> None:
        """
        Test: LY se reinicia a 0 después de la línea 153 (wrap-around de frame).
        
        Después de la línea 153, LY debe volver a 0 para iniciar un nuevo frame.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Avanzar hasta la línea 153 (153 líneas * 456 ciclos = 69,768 ciclos)
        total_cycles = 153 * 456
        ppu.step(total_cycles)
        
        # LY debe ser 153
        assert ppu.get_ly() == 153
        
        # Avanzar una línea más (456 ciclos adicionales)
        ppu.step(456)
        
        # LY debe haber vuelto a 0 (nuevo frame)
        assert ppu.get_ly() == 0

    def test_ppu_modes(self) -> None:
        """
        Test: Los modos PPU se actualizan correctamente según el timing.
        
        Para líneas visibles (0-143):
        - Mode 2 (OAM Search): 0-79 ciclos
        - Mode 3 (Pixel Transfer): 80-251 ciclos
        - Mode 0 (H-Blank): 252-455 ciclos
        Para líneas 144-153:
        - Mode 1 (V-Blank): toda la línea
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Al inicio de la línea, debe ser Mode 2 (OAM Search)
        assert ppu.get_mode() == 2, "Al inicio debe ser Mode 2 (OAM Search)"
        
        # Avanzar 80 ciclos: debe estar en Mode 3 (Pixel Transfer)
        ppu.step(80)
        assert ppu.get_mode() == 3, "Después de 80 ciclos debe ser Mode 3 (Pixel Transfer)"
        
        # Avanzar 172 ciclos más (total 252): debe estar en Mode 0 (H-Blank)
        ppu.step(172)
        assert ppu.get_mode() == 0, "Después de 252 ciclos debe ser Mode 0 (H-Blank)"
        
        # Avanzar hasta V-Blank (línea 144)
        # Ya estamos en línea 1 después de completar la línea 0
        # Necesitamos avanzar hasta línea 144: 143 líneas más = 143 * 456 = 65,208 ciclos
        # Pero para llegar exactamente a línea 144, necesitamos una línea más (456 ciclos adicionales)
        ppu.step(143 * 456)
        assert ppu.get_ly() == 143  # Estamos en línea 143
        ppu.step(456)  # Avanzar una línea más
        assert ppu.get_ly() == 144
        assert ppu.get_mode() == 1, "En V-Blank debe ser Mode 1"

    def test_lyc_match_stat_interrupt(self) -> None:
        """
        Test: La interrupción STAT se activa cuando LY == LYC.
        
        Cuando LY coincide con LYC y el bit 6 de STAT está activo,
        debe activarse el bit 1 de IF (interrupción STAT).
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        mmu.set_ppu(ppu)  # Necesario para que MMU pueda actualizar STAT correctamente
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Configurar LYC = 10
        ppu.set_lyc(10)
        assert ppu.get_lyc() == 10
        
        # Habilitar interrupción STAT por LYC (bit 6 de STAT)
        mmu.write(0xFF41, 0x40)  # Bit 6 activo (LYC interrupt enable)
        
        # Limpiar IF
        mmu.write(0xFF0F, 0x00)
        
        # Avanzar hasta línea 10
        ppu.step(10 * 456)
        assert ppu.get_ly() == 10
        
        # Verificar que se activó el bit 1 de IF (STAT interrupt)
        if_val = mmu.read(0xFF0F)
        assert (if_val & 0x02) == 0x02, f"IF debe tener bit 1 activado, pero es 0x{if_val:02X}"

    def test_lcd_disabled(self) -> None:
        """
        Test: La PPU no avanza cuando el LCD está deshabilitado.
        
        Cuando el bit 7 de LCDC es 0, la PPU se detiene y LY se mantiene en 0.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # LCD deshabilitado (bit 7 = 0)
        mmu.write(0xFF40, 0x00)
        
        # Avanzar muchos ciclos
        ppu.step(10000)
        
        # LY debe seguir siendo 0
        assert ppu.get_ly() == 0
        
        # Ahora habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Avanzar una línea
        ppu.step(456)
        
        # Ahora LY debe incrementarse
        assert ppu.get_ly() == 1

    def test_multiple_frames(self) -> None:
        """
        Test: La PPU puede procesar múltiples frames completos.
        
        Después de procesar múltiples frames (154 líneas cada uno),
        LY debe ciclar correctamente entre 0 y 153.
        """
        mmu = PyMMU()
        ppu = PyPPU(mmu)
        
        # Habilitar LCD
        mmu.write(0xFF40, 0x80)
        
        # Procesar 3 frames completos
        # 1 frame = 154 líneas * 456 ciclos = 70,224 ciclos
        cycles_per_frame = 154 * 456
        total_cycles = cycles_per_frame * 3
        
        ppu.step(total_cycles)
        
        # Después de 3 frames completos, LY debe volver a 0
        assert ppu.get_ly() == 0

