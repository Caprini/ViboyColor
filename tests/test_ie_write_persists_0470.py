"""Test para verificar que writes a IE persisten correctamente.

Step 0470: Asegura que writes a IE (0xFFFF) realmente persisten
y no se pierden o son pisados por algún modo CGB.
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


class TestIEWritePersists:
    """Tests para verificar que IE writes persisten."""
    
    def setup_method(self):
        """Inicializar sistema mínimo."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.cpu = PyCPU(self.mmu, self.registers)
        self.ppu = PyPPU(self.mmu)
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
    
    def test_ie_write_persists(self):
        """Test: Verificar que write a IE (0xFFFF) persiste.
        
        Escribir 0xFFFF=0x01 y verificar que read 0xFFFF==0x01.
        Esto parece trivial, pero detecta si algún "modo CGB" pisa IE.
        """
        # Escribir IE
        self.mmu.write(0xFFFF, 0x01)
        
        # Verificar que persiste
        ie_read = self.mmu.read(0xFFFF)
        assert ie_read == 0x01, \
            f"IE write no persiste: escribí 0x01, leí 0x{ie_read:02X}"
        
        # Verificar contador de writes
        ie_write_count = self.mmu.get_ie_write_count() if hasattr(self.mmu, 'get_ie_write_count') else 0
        assert ie_write_count > 0, \
            f"Contador de IE writes no se incrementó (ie_write_count={ie_write_count})"
    
    def test_ie_write_multiple_values(self):
        """Test: Verificar que múltiples writes a IE persisten correctamente."""
        # Escribir diferentes valores
        for value in [0x01, 0x03, 0x07, 0x0F]:
            self.mmu.write(0xFFFF, value)
            ie_read = self.mmu.read(0xFFFF)
            assert ie_read == value, \
                f"IE write no persiste: escribí 0x{value:02X}, leí 0x{ie_read:02X}"

