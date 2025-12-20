"""
Tests para el subsistema Timer (registros DIV, TIMA, TMA, TAC) en C++.

Este módulo valida la implementación completa del Timer:
- DIV: Contador continuo a 16384 Hz
- TIMA: Contador programable con interrupciones
- TMA: Valor de recarga cuando TIMA desborda
- TAC: Control de enable y selección de frecuencia
"""

import pytest

# Intentar importar el módulo C++ compilado
try:
    from viboy_core import PyTimer, PyMMU
    CPP_TIMER_AVAILABLE = True
except ImportError:
    PyTimer = None  # type: ignore
    PyMMU = None  # type: ignore
    CPP_TIMER_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Ejecuta 'python setup.py build_ext --inplace' primero.", allow_module_level=True)


class TestTimerDIV:
    """Tests para el registro DIV del Timer."""
    
    def test_div_initial_value(self):
        """Verifica que DIV inicia en 0."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        assert timer.read_div() == 0
    
    def test_div_increment_after_256_cycles(self):
        """Verifica que DIV se incrementa cada 256 T-Cycles."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # DIV debe ser 0 después de 255 ciclos
        timer.step(255)
        assert timer.read_div() == 0
        
        # DIV debe ser 1 después de 1 ciclo más (256 total)
        timer.step(1)
        assert timer.read_div() == 1
        
        # DIV debe ser 2 después de 256 ciclos más (512 total)
        timer.step(256)
        assert timer.read_div() == 2
    
    def test_div_increment_multiple_steps(self):
        """Verifica que DIV se incrementa correctamente en múltiples pasos."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Acumular 512 T-Cycles en pasos de 4 (simulando instrucciones)
        for _ in range(128):  # 128 * 4 = 512
            timer.step(4)
        
        # DIV debe ser 2 (512 / 256 = 2)
        assert timer.read_div() == 2
    
    def test_div_write_resets(self):
        """Verifica que escribir en DIV lo resetea a 0."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Avanzar el contador
        timer.step(500)
        assert timer.read_div() > 0
        
        # Resetear escribiendo en DIV
        timer.write_div()
        assert timer.read_div() == 0
        
        # Verificar que el contador sigue funcionando después del reset
        timer.step(256)
        assert timer.read_div() == 1
    
    def test_div_wraps_around(self):
        """Verifica que DIV hace wrap-around después de 0xFF."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Avanzar hasta que DIV sea 0xFF (255)
        # 255 * 256 = 65280 T-Cycles
        timer.step(65280)
        assert timer.read_div() == 0xFF
        
        # Un ciclo más debería hacer wrap-around a 0
        timer.step(256)
        assert timer.read_div() == 0
    
    def test_div_frequency_16384_hz(self):
        """Verifica que DIV se incrementa a la frecuencia correcta (16384 Hz)."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # El reloj principal es 4.194304 MHz
        # DIV se incrementa cada 256 T-Cycles (4194304 / 16384 = 256)
        # Después de 256 T-Cycles, DIV debe ser 1
        timer.step(256)
        assert timer.read_div() == 1
        
        # Después de 512 T-Cycles, DIV debe ser 2
        timer.step(256)
        assert timer.read_div() == 2
        
        # Después de 768 T-Cycles, DIV debe ser 3
        timer.step(256)
        assert timer.read_div() == 3


class TestTimerTIMA:
    """Tests para los registros TIMA, TMA y TAC del Timer."""
    
    def test_tima_initial_value(self):
        """Verifica que TIMA, TMA y TAC inician en 0."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        assert timer.read_tima() == 0
        assert timer.read_tma() == 0
        assert timer.read_tac() == 0
    
    def test_tima_read_write(self):
        """Verifica que TIMA se puede leer y escribir correctamente."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Escribir y leer TIMA
        timer.write_tima(0xAB)
        assert timer.read_tima() == 0xAB
        
        timer.write_tima(0x42)
        assert timer.read_tima() == 0x42
    
    def test_tma_read_write(self):
        """Verifica que TMA se puede leer y escribir correctamente."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Escribir y leer TMA
        timer.write_tma(0xCD)
        assert timer.read_tma() == 0xCD
        
        timer.write_tma(0x33)
        assert timer.read_tma() == 0x33
    
    def test_tac_read_write(self):
        """Verifica que TAC se puede leer y escribir correctamente."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Escribir y leer TAC
        timer.write_tac(0x07)  # Timer ON, frecuencia 16384 Hz
        assert timer.read_tac() == 0x07
        
        timer.write_tac(0x04)  # Timer ON, frecuencia 4096 Hz
        assert timer.read_tac() == 0x04
    
    def test_tima_increment_when_enabled(self):
        """Verifica que TIMA se incrementa cuando el Timer está activado."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Configurar TIMA y activar Timer (frecuencia 4096 Hz = threshold 1024)
        timer.write_tima(0x00)
        timer.write_tac(0x04)  # Timer ON, frecuencia 4096 Hz
        
        # Avanzar 1024 T-Cycles (debería incrementar TIMA)
        timer.step(1024)
        assert timer.read_tima() == 0x01
    
    def test_tima_not_increment_when_disabled(self):
        """Verifica que TIMA NO se incrementa cuando el Timer está desactivado."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Configurar TIMA y desactivar Timer
        timer.write_tima(0x00)
        timer.write_tac(0x00)  # Timer OFF
        
        # Avanzar muchos T-Cycles (TIMA no debería cambiar)
        timer.step(10000)
        assert timer.read_tima() == 0x00
    
    def test_tima_frequencies(self):
        """Verifica que TIMA se incrementa a las frecuencias correctas."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Frecuencia 262144 Hz (threshold 16 T-Cycles)
        timer.write_tima(0x00)
        timer.write_tac(0x05)  # Timer ON, frecuencia 262144 Hz
        timer.step(16)
        assert timer.read_tima() == 0x01, "TIMA debería incrementarse después de 16 T-Cycles a 262144 Hz"
        
        # Frecuencia 65536 Hz (threshold 64 T-Cycles)
        timer.write_tima(0x00)
        timer.write_tac(0x06)  # Timer ON, frecuencia 65536 Hz
        timer.step(64)
        assert timer.read_tima() == 0x01, "TIMA debería incrementarse después de 64 T-Cycles a 65536 Hz"
        
        # Frecuencia 16384 Hz (threshold 256 T-Cycles)
        timer.write_tima(0x00)
        timer.write_tac(0x07)  # Timer ON, frecuencia 16384 Hz
        timer.step(256)
        assert timer.read_tima() == 0x01, "TIMA debería incrementarse después de 256 T-Cycles a 16384 Hz"
    
    def test_tima_overflow_reloads_tma(self):
        """Verifica que cuando TIMA desborda, se recarga con TMA."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        mmu.set_timer(timer)  # Conectar Timer a MMU para interrupciones
        
        # Configurar TMA y TIMA cerca del desbordamiento
        timer.write_tma(0xAB)
        timer.write_tima(0xFF)
        timer.write_tac(0x04)  # Timer ON, frecuencia 4096 Hz
        
        # Avanzar 1024 T-Cycles (debería causar desbordamiento y recarga)
        timer.step(1024)
        
        # TIMA debería haberse recargado con el valor de TMA
        assert timer.read_tima() == 0xAB, "TIMA debería haberse recargado con TMA después del desbordamiento"
    
    def test_tima_overflow_requests_interrupt(self):
        """Verifica que cuando TIMA desborda, se solicita una interrupción de Timer."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        mmu.set_timer(timer)  # Conectar Timer a MMU para interrupciones
        
        # Configurar TIMA cerca del desbordamiento
        timer.write_tima(0xFF)
        timer.write_tac(0x04)  # Timer ON, frecuencia 4096 Hz
        
        # Avanzar 1024 T-Cycles (debería causar desbordamiento)
        timer.step(1024)
        
        # Verificar que se solicitó una interrupción de Timer (bit 2 del registro IF)
        if_reg = mmu.read(0xFF0F)
        assert (if_reg & 0x04) != 0, "Se debería haber solicitado una interrupción de Timer (bit 2 de IF)"
    
    def test_tima_overflow_multiple_increments(self):
        """Verifica que TIMA maneja correctamente múltiples incrementos en un solo step()."""
        mmu = PyMMU()
        timer = PyTimer(mmu)
        
        # Configurar Timer con frecuencia alta (16 T-Cycles por incremento)
        timer.write_tima(0xFD)
        timer.write_tac(0x05)  # Timer ON, frecuencia 262144 Hz (threshold 16)
        
        # Avanzar 48 T-Cycles (debería incrementar TIMA 3 veces: 0xFD -> 0xFE -> 0xFF -> 0x00)
        timer.step(48)
        
        # TIMA debería haber hecho wrap-around y estar en 0x00
        assert timer.read_tima() == 0x00, "TIMA debería haber hecho wrap-around después de múltiples incrementos"

