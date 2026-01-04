"""Test clean-room para verificar que writes a IE persisten correctamente.

Step 0471: Test "Readback Inmediato" para verificar que writes a IE (0xFFFF)
realmente persisten y no se pierden en write o read.

Este test es más estricto que 0470: verifica readback inmediato después de write.
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


@pytest.mark.skipif(False, reason="Test siempre disponible")
class TestIEWritePersistsReadback:
    """Tests clean-room para verificar que IE writes persisten (readback inmediato)."""
    
    def setup_method(self):
        """Inicializar sistema mínimo (MMU/CPU/PPU)."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.cpu = PyCPU(self.mmu, self.registers)
        self.ppu = PyPPU(self.mmu)
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        
        # Conectar componentes
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
    
    def test_ie_write_readback_immediate_dmg(self):
        """Test Caso 1 (DMG path): Readback inmediato después de write.
        
        - Escribir IE = 0x1F
        - Leer IE → debe ser 0x1F
        - Escribir IE = 0x00
        - Leer IE → debe ser 0x00
        
        Si falla, identifica exactamente dónde se pierde el valor (write vs read).
        """
        # Caso 1a: Escribir 0x1F y verificar readback inmediato
        self.mmu.write(0xFFFF, 0x1F)
        ie_read_1 = self.mmu.read(0xFFFF)
        assert ie_read_1 == 0x1F, \
            f"IE write no persiste (Caso 1a): escribí 0x1F, leí 0x{ie_read_1:02X}"
        
        # Verificar contador de writes
        ie_write_count_1 = self.mmu.get_ie_write_count()
        assert ie_write_count_1 > 0, \
            f"Contador de IE writes no se incrementó (ie_write_count={ie_write_count_1})"
        
        # Verificar último valor escrito
        last_ie_write_value = self.mmu.get_last_ie_write_value()
        assert last_ie_write_value == 0x1F, \
            f"Último valor escrito a IE incorrecto: esperado 0x1F, obtenido 0x{last_ie_write_value:02X}"
        
        # Caso 1b: Escribir 0x00 y verificar readback inmediato
        self.mmu.write(0xFFFF, 0x00)
        ie_read_2 = self.mmu.read(0xFFFF)
        assert ie_read_2 == 0x00, \
            f"IE write no persiste (Caso 1b): escribí 0x00, leí 0x{ie_read_2:02X}"
        
        # Verificar contador de writes incrementado
        ie_write_count_2 = self.mmu.get_ie_write_count()
        assert ie_write_count_2 > ie_write_count_1, \
            f"Contador de IE writes no se incrementó (antes={ie_write_count_1}, después={ie_write_count_2})"
        
        # Verificar último valor escrito
        last_ie_write_value_2 = self.mmu.get_last_ie_write_value()
        assert last_ie_write_value_2 == 0x00, \
            f"Último valor escrito a IE incorrecto: esperado 0x00, obtenido 0x{last_ie_write_value_2:02X}"
        
        # Verificar último valor leído
        last_ie_read_value = self.mmu.get_last_ie_read_value()
        assert last_ie_read_value == 0x00, \
            f"Último valor leído de IE incorrecto: esperado 0x00, obtenido 0x{last_ie_read_value:02X}"
        
        # Verificar contador de reads
        ie_read_count = self.mmu.get_ie_read_count()
        assert ie_read_count >= 2, \
            f"Contador de IE reads insuficiente: esperado >= 2, obtenido {ie_read_count}"
    
    def test_ie_write_readback_immediate_cgb(self):
        """Test Caso 2 (CGB path): Readback inmediato después de write en modo CGB.
        
        - Forzar modo CGB
        - Escribir IE = 0x1F
        - Leer IE → debe ser 0x1F
        - Escribir IE = 0x00
        - Leer IE → debe ser 0x00
        
        Verifica que writes persisten en CGB también.
        """
        # Forzar modo CGB (usando string porque HardwareMode no se exporta directamente)
        self.mmu.set_hardware_mode("CGB")
        self.mmu.initialize_io_registers()
        
        # Caso 2a: Escribir 0x1F y verificar readback inmediato
        self.mmu.write(0xFFFF, 0x1F)
        ie_read_1 = self.mmu.read(0xFFFF)
        assert ie_read_1 == 0x1F, \
            f"IE write no persiste en CGB (Caso 2a): escribí 0x1F, leí 0x{ie_read_1:02X}"
        
        # Caso 2b: Escribir 0x00 y verificar readback inmediato
        self.mmu.write(0xFFFF, 0x00)
        ie_read_2 = self.mmu.read(0xFFFF)
        assert ie_read_2 == 0x00, \
            f"IE write no persiste en CGB (Caso 2b): escribí 0x00, leí 0x{ie_read_2:02X}"
    
    def test_ie_write_readback_multiple_cycles(self):
        """Test: Verificar que IE persiste a través de múltiples writes/reads.
        
        - Escribir múltiples valores
        - Leer después de cada write
        - Verificar que cada readback coincide con el último write
        """
        test_values = [0x01, 0x03, 0x07, 0x0F, 0x1F, 0x00]
        
        for i, value in enumerate(test_values):
            # Escribir valor
            self.mmu.write(0xFFFF, value)
            
            # Readback inmediato
            ie_read = self.mmu.read(0xFFFF)
            assert ie_read == value, \
                f"IE write no persiste (ciclo {i}): escribí 0x{value:02X}, leí 0x{ie_read:02X}"
            
            # Verificar último valor escrito
            last_write = self.mmu.get_last_ie_write_value()
            assert last_write == value, \
                f"Último valor escrito incorrecto (ciclo {i}): esperado 0x{value:02X}, obtenido 0x{last_write:02X}"
            
            # Verificar último valor leído
            last_read = self.mmu.get_last_ie_read_value()
            assert last_read == value, \
                f"Último valor leído incorrecto (ciclo {i}): esperado 0x{value:02X}, obtenido 0x{last_read:02X}"

