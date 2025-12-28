"""
Tests para verificar que el registro IF se actualiza correctamente en V-Blank
incluso cuando IME (Interrupt Master Enable) está deshabilitado.

CRÍTICO: El registro IF (Interrupt Flag) es hardware puro. Cuando ocurre V-Blank,
el hardware activa el bit 0 de IF (0xFF0F) INDEPENDIENTEMENTE del estado de IME.
Esto permite que los juegos hagan "polling" manual de IF para detectar V-Blank
sin usar interrupciones automáticas.

Fuente: Pan Docs - Interrupts, V-Blank Interrupt Flag
"""

import pytest

from src.cpu.core import CPU
from src.gpu.ppu import PPU
from src.memory.mmu import MMU, IO_IF, IO_IE


class TestPPUVBlankPolling:
    """Tests para verificar V-Blank polling (lectura manual de IF)"""

    def test_vblank_sets_if_with_ime_false(self) -> None:
        """
        Test: IF se actualiza cuando ocurre V-Blank, incluso con IME=False.
        
        Este test verifica el comportamiento crítico para juegos que hacen
        polling manual de IF en lugar de usar interrupciones automáticas.
        
        Comportamiento esperado:
        - La PPU activa el bit 0 de IF cuando LY llega a 144 (V-Blank)
        - Esto ocurre SIEMPRE, independientemente del estado de IME
        - El juego puede leer IF y detectar V-Blank manualmente
        """
        mmu = MMU(None)
        cpu = CPU(mmu)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Configurar IME=False (interrupciones automáticas deshabilitadas)
        cpu.ime = False
        assert cpu.ime is False, "IME debe estar deshabilitado"
        
        # Limpiar IF inicialmente
        mmu.write_byte(IO_IF, 0x00)
        assert mmu.read_byte(IO_IF) == 0x00, "IF debe estar limpio inicialmente"
        
        # Avanzar PPU hasta V-Blank (línea 144)
        # 144 líneas * 456 T-Cycles = 65,664 T-Cycles
        total_cycles = 144 * 456
        ppu.step(total_cycles)
        
        # Verificar que LY llegó a 144
        assert ppu.get_ly() == 144, "LY debe ser 144 (inicio de V-Blank)"
        
        # CRÍTICO: IF debe tener el bit 0 activado, incluso con IME=False
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) == 0x01, (
            f"IF debe tener bit 0 activado (V-Blank) incluso con IME=False. "
            f"IF actual: 0x{if_val:02X}"
        )
        
        # Verificar que IME sigue siendo False (no cambió)
        assert cpu.ime is False, "IME debe seguir siendo False"

    def test_vblank_if_persists_until_cleared(self) -> None:
        """
        Test: IF permanece activo hasta que el juego lo limpia manualmente.
        
        El bit 0 de IF se mantiene activo hasta que:
        1. El juego lo lee y lo limpia escribiendo en IF, o
        2. La CPU procesa la interrupción (si IME=True y IE tiene el bit activo)
        
        En este test, simulamos que el juego hace polling: lee IF, detecta V-Blank,
        y luego limpia el bit manualmente.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta V-Blank
        ppu.step(144 * 456)
        assert ppu.get_ly() == 144
        
        # Verificar que IF está activo
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) == 0x01, "IF debe estar activo después de V-Blank"
        
        # Simular que el juego lee IF y lo limpia manualmente
        # (En hardware real, el juego haría: LD A, (0xFF0F) -> BIT 0, A -> RES 0, A -> LD (0xFF0F), A)
        current_if = mmu.read_byte(IO_IF)
        cleared_if = current_if & (~0x01)  # Limpiar bit 0
        mmu.write_byte(IO_IF, cleared_if)
        
        # Verificar que el bit 0 se limpió
        if_val_after = mmu.read_byte(IO_IF)
        assert (if_val_after & 0x01) == 0x00, "El bit 0 de IF debe estar limpio después de limpieza manual"
        
        # Avanzar al siguiente frame y verificar que IF se activa de nuevo
        # Avanzar hasta el siguiente V-Blank (necesitamos completar el frame actual y llegar al siguiente)
        # Frame actual: LY=144, necesitamos llegar a LY=144 del siguiente frame
        # Resto del frame actual: 10 líneas (144-153) = 10 * 456 = 4560 ciclos
        # Frame completo siguiente: 144 líneas = 144 * 456 = 65,664 ciclos
        ppu.step(10 * 456)  # Completar V-Blank actual
        ppu.step(144 * 456)  # Avanzar al siguiente V-Blank
        
        # Verificar que IF se activó de nuevo
        if_val_next = mmu.read_byte(IO_IF)
        assert (if_val_next & 0x01) == 0x01, "IF debe activarse de nuevo en el siguiente V-Blank"

    def test_vblank_if_independent_of_ie(self) -> None:
        """
        Test: IF se actualiza independientemente del registro IE (Interrupt Enable).
        
        IE controla qué interrupciones están "habilitadas" para ser procesadas
        automáticamente por la CPU. Sin embargo, el hardware siempre actualiza IF
        cuando ocurre un evento (V-Blank, Timer, etc.), independientemente de IE.
        
        Esto permite que los juegos hagan polling incluso si IE no tiene el bit activo.
        """
        mmu = MMU(None)
        ppu = PPU(mmu)
        mmu.set_ppu(ppu)
        
        # Configurar IE con el bit 0 deshabilitado (IE = 0x00)
        mmu.write_byte(IO_IE, 0x00)
        assert mmu.read_byte(IO_IE) == 0x00, "IE debe tener bit 0 deshabilitado"
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        
        # Avanzar hasta V-Blank
        ppu.step(144 * 456)
        
        # CRÍTICO: IF debe activarse incluso si IE tiene el bit 0 deshabilitado
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x01) == 0x01, (
            f"IF debe activarse independientemente de IE. "
            f"IF: 0x{if_val:02X}, IE: 0x{mmu.read_byte(IO_IE):02X}"
        )

