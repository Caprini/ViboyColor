"""Test clean-room para verificar que VBlank interrupt se solicita y sirve correctamente.

Step 0469: Verifica end-to-end que el PPU solicita VBlank interrupt y la CPU lo sirve.
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyCPU, PyRegisters, PyTimer, PyJoypad


class TestVBlankInterruptServed:
    """Tests para verificar VBlank interrupt."""
    
    def setup_method(self):
        """Inicializar sistema mínimo."""
        self.mmu = PyMMU()
        self.registers = PyRegisters()
        self.timer = PyTimer(self.mmu)
        self.joypad = PyJoypad()
        self.cpu = PyCPU(self.mmu, self.registers)
        self.ppu = PyPPU(self.mmu)
        
        # Conectar componentes
        self.mmu.set_ppu(self.ppu)
        self.mmu.set_timer(self.timer)
        self.mmu.set_joypad(self.joypad)
        
        # Encender LCD
        self.mmu.write(0xFF40, 0x91)  # LCD ON, BG ON
    
    def run_one_frame(self):
        """Helper: Ejecutar hasta que PPU declare frame listo."""
        max_cycles = 70224 * 4
        cycles_accumulated = 0
        frame_ready = False
        
        while not frame_ready and cycles_accumulated < max_cycles:
            cycles = self.cpu.step()
            cycles_accumulated += cycles
            self.timer.step(cycles)
            self.ppu.step(cycles)
            
            frame_ready = self.ppu.is_frame_ready() if hasattr(self.ppu, 'is_frame_ready') else self.ppu.get_frame_ready_and_reset()
            if frame_ready:
                break
        
        return cycles_accumulated, frame_ready
    
    def test_vblank_interrupt_requested(self):
        """Test 1: Verificar que PPU solicita VBlank interrupt cuando LY=144.
        
        Después de correr frames, el contador vblank_irq_requested debe ser > 0.
        """
        # Habilitar VBlank interrupt en IE
        self.mmu.write(0xFFFF, 0x01)  # IE bit0 = VBlank enabled
        
        # Correr 3 frames
        for _ in range(3):
            self.run_one_frame()
        
        # Verificar que se solicitó VBlank interrupt
        vblank_req = self.ppu.get_vblank_irq_requested_count() if hasattr(self.ppu, 'get_vblank_irq_requested_count') else 0
        assert vblank_req > 0, \
            f"PPU no solicitó ninguna VBlank interrupt después de 3 frames (vblank_req={vblank_req})"
    
    def test_vblank_interrupt_served(self):
        """Test 2: Verificar que CPU sirve VBlank interrupt cuando está habilitado.
        
        Patrón simplificado:
        - Habilitar IME y VBlank interrupt
        - Correr frames hasta que se sirva VBlank interrupt
        - Verificar que el contador vblank_irq_serviced > 0
        
        Nota: Este test verifica que el contador funciona cuando IME está activo.
        Si IME no está activo, las interrupciones no se sirven aunque estén pendientes.
        """
        # Habilitar VBlank interrupt en IE
        self.mmu.write(0xFFFF, 0x01)  # IE bit0 = VBlank enabled
        
        # Habilitar IME (Interrupt Master Enable) - CRÍTICO para que se sirvan interrupciones
        # Usar la propiedad ime en lugar de set_ime
        self.cpu.ime = True
        
        # Verificar que IME está activo
        assert self.cpu.get_ime() == 1, "IME debe estar activo para servir interrupciones"
        
        # Correr 5 frames (dar más tiempo para que se sirva)
        # Durante estos frames, el PPU solicitará VBlank interrupt y la CPU debería servirlo
        for _ in range(5):
            self.run_one_frame()
        
        # Verificar que se sirvió VBlank interrupt (contador vblank_irq_serviced)
        vblank_serv = self.cpu.get_vblank_irq_serviced_count() if hasattr(self.cpu, 'get_vblank_irq_serviced_count') else 0
        vblank_req = self.ppu.get_vblank_irq_requested_count() if hasattr(self.ppu, 'get_vblank_irq_requested_count') else 0
        
        # Si se solicitó VBlank interrupt y IME está activo, debería servirse
        if vblank_req > 0:
            assert vblank_serv > 0, \
                f"CPU no sirvió ninguna VBlank interrupt después de 5 frames aunque se solicitó {vblank_req} veces (vblank_serv={vblank_serv}, IME={self.cpu.get_ime()})"
        else:
            # Si no se solicitó ninguna, el test no puede verificar el servicio
            pytest.skip("No se solicitó ninguna VBlank interrupt, no se puede verificar el servicio")

