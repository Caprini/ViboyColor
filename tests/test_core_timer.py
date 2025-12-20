"""
Tests para el subsistema Timer (registro DIV) en C++.

Este módulo valida la implementación del registro DIV del Timer,
verificando que se incrementa correctamente cada 256 T-Cycles y
que se resetea cuando se escribe en 0xFF04.
"""

import pytest

# Intentar importar el módulo C++ compilado
try:
    from viboy_core import PyTimer
    CPP_TIMER_AVAILABLE = True
except ImportError:
    PyTimer = None  # type: ignore
    CPP_TIMER_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Ejecuta 'python setup.py build_ext --inplace' primero.", allow_module_level=True)


class TestTimerDIV:
    """Tests para el registro DIV del Timer."""
    
    def test_div_initial_value(self):
        """Verifica que DIV inicia en 0."""
        timer = PyTimer()
        assert timer.read_div() == 0
    
    def test_div_increment_after_256_cycles(self):
        """Verifica que DIV se incrementa cada 256 T-Cycles."""
        timer = PyTimer()
        
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
        timer = PyTimer()
        
        # Acumular 512 T-Cycles en pasos de 4 (simulando instrucciones)
        for _ in range(128):  # 128 * 4 = 512
            timer.step(4)
        
        # DIV debe ser 2 (512 / 256 = 2)
        assert timer.read_div() == 2
    
    def test_div_write_resets(self):
        """Verifica que escribir en DIV lo resetea a 0."""
        timer = PyTimer()
        
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
        timer = PyTimer()
        
        # Avanzar hasta que DIV sea 0xFF (255)
        # 255 * 256 = 65280 T-Cycles
        timer.step(65280)
        assert timer.read_div() == 0xFF
        
        # Un ciclo más debería hacer wrap-around a 0
        timer.step(256)
        assert timer.read_div() == 0
    
    def test_div_frequency_16384_hz(self):
        """Verifica que DIV se incrementa a la frecuencia correcta (16384 Hz)."""
        timer = PyTimer()
        
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

