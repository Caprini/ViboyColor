"""
Tests para el Timer (Sistema de Temporización)

Estos tests validan:
- Inicialización del Timer
- Incremento de DIV cada 256 T-Cycles
- Lectura de DIV (8 bits altos del contador interno)
- Reset de DIV al escribir en 0xFF04
- Integración con MMU
"""

import pytest

from src.io.timer import Timer, DIV_T_CYCLES_PER_INCREMENT
from src.memory.mmu import MMU, IO_DIV


class TestTimer:
    """Tests para la clase Timer"""
    
    def test_timer_initial_state(self) -> None:
        """Test: Verificar que el Timer se inicializa con DIV en 0"""
        timer = Timer()
        
        # DIV debe ser 0 al inicio
        div_value = timer.read_div()
        assert div_value == 0, f"DIV debe ser 0 al inicio, pero es 0x{div_value:02X}"
        
        # El contador interno también debe ser 0
        div_counter = timer.get_div_counter()
        assert div_counter == 0, f"Contador interno debe ser 0, pero es 0x{div_counter:04X}"
    
    def test_div_increment(self) -> None:
        """Test: Verificar que DIV incrementa cada 256 T-Cycles"""
        timer = Timer()
        
        # DIV debe empezar en 0
        assert timer.read_div() == 0
        
        # Avanzar 255 T-Cycles (aún no debe incrementar)
        timer.tick(255)
        assert timer.read_div() == 0, "DIV no debe incrementar con 255 T-Cycles"
        
        # Avanzar 1 T-Cycle más (total 256) -> DIV debe incrementar
        timer.tick(1)
        assert timer.read_div() == 1, f"DIV debe ser 1 después de 256 T-Cycles, pero es {timer.read_div()}"
        
        # Avanzar otros 256 T-Cycles -> DIV debe ser 2
        timer.tick(256)
        assert timer.read_div() == 2, f"DIV debe ser 2 después de 512 T-Cycles, pero es {timer.read_div()}"
    
    def test_div_increment_multiple(self) -> None:
        """Test: Verificar incremento múltiple de DIV"""
        timer = Timer()
        
        # Avanzar 1024 T-Cycles (4 incrementos de 256)
        timer.tick(1024)
        assert timer.read_div() == 4, f"DIV debe ser 4 después de 1024 T-Cycles, pero es {timer.read_div()}"
        
        # Avanzar otros 2560 T-Cycles (10 incrementos más)
        timer.tick(2560)
        assert timer.read_div() == 14, f"DIV debe ser 14 después de 3584 T-Cycles, pero es {timer.read_div()}"
    
    def test_div_wraparound(self) -> None:
        """Test: Verificar que DIV hace wrap-around después de 0xFF"""
        timer = Timer()
        
        # Avanzar hasta que DIV sea 0xFF (255 incrementos = 65280 T-Cycles)
        timer.tick(255 * DIV_T_CYCLES_PER_INCREMENT)
        assert timer.read_div() == 0xFF, f"DIV debe ser 0xFF, pero es 0x{timer.read_div():02X}"
        
        # Avanzar otros 256 T-Cycles -> DIV debe volver a 0 (wrap-around)
        timer.tick(DIV_T_CYCLES_PER_INCREMENT)
        assert timer.read_div() == 0, f"DIV debe hacer wrap-around a 0, pero es 0x{timer.read_div():02X}"
    
    def test_div_reset(self) -> None:
        """Test: Verificar que escribir en DIV resetea el contador interno"""
        timer = Timer()
        
        # Avanzar el Timer para que DIV tenga un valor no cero
        timer.tick(512)  # DIV debería ser 2
        assert timer.read_div() == 2, "DIV debe ser 2 antes del reset"
        
        # Escribir cualquier valor en DIV (el valor se ignora)
        timer.write_div(0x42)  # Valor arbitrario
        
        # DIV debe volver a 0
        assert timer.read_div() == 0, "DIV debe ser 0 después de escribir"
        
        # El contador interno también debe ser 0
        div_counter = timer.get_div_counter()
        assert div_counter == 0, f"Contador interno debe ser 0, pero es 0x{div_counter:04X}"
    
    def test_div_reset_ignores_value(self) -> None:
        """Test: Verificar que el valor escrito en DIV se ignora"""
        timer = Timer()
        
        # Avanzar el Timer
        timer.tick(256)
        assert timer.read_div() == 1
        
        # Escribir diferentes valores en DIV
        timer.write_div(0x00)
        assert timer.read_div() == 0
        
        timer.tick(256)
        assert timer.read_div() == 1
        
        timer.write_div(0xFF)  # Valor diferente
        assert timer.read_div() == 0  # Debe resetear igual
    
    def test_div_counter_internal(self) -> None:
        """Test: Verificar el contador interno de 16 bits"""
        timer = Timer()
        
        # El contador interno es de 16 bits
        # Avanzar hasta que el contador interno sea 0xFFFF
        # DIV expone solo los 8 bits altos, así que cuando el contador es 0xFFFF,
        # DIV es 0xFF
        
        # Avanzar 65535 T-Cycles (casi el máximo de 16 bits)
        timer.tick(65535)
        div_counter = timer.get_div_counter()
        assert div_counter == 65535, f"Contador interno debe ser 65535, pero es {div_counter}"
        
        # DIV debe ser los 8 bits altos: 65535 >> 8 = 255 = 0xFF
        assert timer.read_div() == 0xFF, f"DIV debe ser 0xFF, pero es 0x{timer.read_div():02X}"
        
        # Avanzar 1 T-Cycle más -> wrap-around a 0
        timer.tick(1)
        div_counter = timer.get_div_counter()
        assert div_counter == 0, f"Contador interno debe hacer wrap-around a 0, pero es {div_counter}"
        assert timer.read_div() == 0, "DIV debe ser 0 después del wrap-around"


class TestTimerMMUIntegration:
    """Tests de integración entre Timer y MMU"""
    
    def test_mmu_read_div(self) -> None:
        """Test: Verificar lectura de DIV a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        mmu.set_timer(timer)
        
        # DIV debe ser 0 al inicio
        div_value = mmu.read_byte(IO_DIV)
        assert div_value == 0, f"DIV debe ser 0, pero es 0x{div_value:02X}"
        
        # Avanzar el Timer
        timer.tick(256)
        
        # DIV debe ser 1
        div_value = mmu.read_byte(IO_DIV)
        assert div_value == 1, f"DIV debe ser 1, pero es 0x{div_value:02X}"
    
    def test_mmu_write_div(self) -> None:
        """Test: Verificar escritura en DIV a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        mmu.set_timer(timer)
        
        # Avanzar el Timer
        timer.tick(512)
        assert mmu.read_byte(IO_DIV) == 2, "DIV debe ser 2 antes del reset"
        
        # Escribir en DIV a través de MMU
        mmu.write_byte(IO_DIV, 0x42)  # Valor arbitrario
        
        # DIV debe ser 0
        div_value = mmu.read_byte(IO_DIV)
        assert div_value == 0, f"DIV debe ser 0 después de escribir, pero es 0x{div_value:02X}"
    
    def test_mmu_read_div_without_timer(self) -> None:
        """Test: Verificar que MMU devuelve 0 si no hay Timer conectado"""
        mmu = MMU(None)
        
        # Leer DIV sin Timer conectado
        div_value = mmu.read_byte(IO_DIV)
        assert div_value == 0, "DIV debe ser 0 si no hay Timer conectado"

