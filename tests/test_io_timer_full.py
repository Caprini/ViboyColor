"""
Tests completos para el Timer (TIMA, TMA, TAC)

Estos tests validan:
- Lectura/escritura de TIMA, TMA y TAC
- Incremento de TIMA según la frecuencia configurada en TAC
- Overflow de TIMA y recarga con TMA
- Solicitud de interrupción Timer cuando TIMA hace overflow
- Integración con MMU
"""

import pytest

from src.io.timer import Timer, TAC_T_CYCLES_4096, TAC_T_CYCLES_262144, TAC_T_CYCLES_65536, TAC_T_CYCLES_16384
from src.memory.mmu import MMU, IO_TIMA, IO_TMA, IO_TAC, IO_IF


class TestTimerTIMA:
    """Tests para el registro TIMA (Timer Counter)"""
    
    def test_tima_initial_state(self) -> None:
        """Test: Verificar que TIMA se inicializa en 0"""
        timer = Timer()
        
        assert timer.read_tima() == 0, "TIMA debe ser 0 al inicio"
    
    def test_tima_read_write(self) -> None:
        """Test: Verificar lectura/escritura de TIMA"""
        timer = Timer()
        
        # Escribir valores en TIMA
        timer.write_tima(0x42)
        assert timer.read_tima() == 0x42, "TIMA debe ser 0x42"
        
        timer.write_tima(0xFF)
        assert timer.read_tima() == 0xFF, "TIMA debe ser 0xFF"
        
        timer.write_tima(0x00)
        assert timer.read_tima() == 0x00, "TIMA debe ser 0x00"
    
    def test_tima_increment_disabled(self) -> None:
        """Test: Verificar que TIMA no incrementa si el Timer está desactivado (TAC bit 2 = 0)"""
        timer = Timer()
        
        # Configurar TAC con Timer desactivado (bit 2 = 0)
        timer.write_tac(0x00)  # Enable=0, Freq=00 (4096Hz)
        
        # Inicializar TIMA a un valor conocido
        timer.write_tima(0x10)
        
        # Avanzar muchos ciclos
        timer.tick(10000)
        
        # TIMA no debe haber cambiado
        assert timer.read_tima() == 0x10, "TIMA no debe incrementar si el Timer está desactivado"
    
    def test_tima_increment_4096hz(self) -> None:
        """Test: Verificar incremento de TIMA a 4096 Hz (TAC bits 1-0 = 00)"""
        timer = Timer()
        
        # Configurar TAC: Enable=1, Freq=00 (4096Hz)
        timer.write_tac(0x04)  # Bit 2=1 (Enable), Bits 1-0=00 (4096Hz)
        
        # Inicializar TIMA
        timer.write_tima(0x00)
        
        # Avanzar 1023 T-Cycles (aún no debe incrementar)
        timer.tick(1023)
        assert timer.read_tima() == 0x00, "TIMA no debe incrementar con 1023 T-Cycles"
        
        # Avanzar 1 T-Cycle más (total 1024) -> TIMA debe incrementar
        timer.tick(1)
        assert timer.read_tima() == 0x01, f"TIMA debe ser 1 después de 1024 T-Cycles, pero es {timer.read_tima()}"
        
        # Avanzar otros 1024 T-Cycles -> TIMA debe ser 2
        timer.tick(1024)
        assert timer.read_tima() == 0x02, f"TIMA debe ser 2 después de 2048 T-Cycles, pero es {timer.read_tima()}"
    
    def test_tima_increment_262144hz(self) -> None:
        """Test: Verificar incremento de TIMA a 262144 Hz (TAC bits 1-0 = 01)"""
        timer = Timer()
        
        # Configurar TAC: Enable=1, Freq=01 (262144Hz)
        timer.write_tac(0x05)  # Bit 2=1 (Enable), Bits 1-0=01 (262144Hz)
        
        timer.write_tima(0x00)
        
        # Avanzar 15 T-Cycles (aún no debe incrementar)
        timer.tick(15)
        assert timer.read_tima() == 0x00, "TIMA no debe incrementar con 15 T-Cycles"
        
        # Avanzar 1 T-Cycle más (total 16) -> TIMA debe incrementar
        timer.tick(1)
        assert timer.read_tima() == 0x01, f"TIMA debe ser 1 después de 16 T-Cycles, pero es {timer.read_tima()}"
    
    def test_tima_increment_65536hz(self) -> None:
        """Test: Verificar incremento de TIMA a 65536 Hz (TAC bits 1-0 = 10)"""
        timer = Timer()
        
        # Configurar TAC: Enable=1, Freq=10 (65536Hz)
        timer.write_tac(0x06)  # Bit 2=1 (Enable), Bits 1-0=10 (65536Hz)
        
        timer.write_tima(0x00)
        
        # Avanzar 63 T-Cycles (aún no debe incrementar)
        timer.tick(63)
        assert timer.read_tima() == 0x00, "TIMA no debe incrementar con 63 T-Cycles"
        
        # Avanzar 1 T-Cycle más (total 64) -> TIMA debe incrementar
        timer.tick(1)
        assert timer.read_tima() == 0x01, f"TIMA debe ser 1 después de 64 T-Cycles, pero es {timer.read_tima()}"
    
    def test_tima_increment_16384hz(self) -> None:
        """Test: Verificar incremento de TIMA a 16384 Hz (TAC bits 1-0 = 11)"""
        timer = Timer()
        
        # Configurar TAC: Enable=1, Freq=11 (16384Hz)
        timer.write_tac(0x07)  # Bit 2=1 (Enable), Bits 1-0=11 (16384Hz)
        
        timer.write_tima(0x00)
        
        # Avanzar 255 T-Cycles (aún no debe incrementar)
        timer.tick(255)
        assert timer.read_tima() == 0x00, "TIMA no debe incrementar con 255 T-Cycles"
        
        # Avanzar 1 T-Cycle más (total 256) -> TIMA debe incrementar
        timer.tick(1)
        assert timer.read_tima() == 0x01, f"TIMA debe ser 1 después de 256 T-Cycles, pero es {timer.read_tima()}"
    
    def test_tima_overflow_reload(self) -> None:
        """Test: Verificar que TIMA se recarga con TMA cuando hace overflow"""
        timer = Timer()
        
        # Configurar TMA
        timer.write_tma(0x42)
        
        # Configurar TAC: Enable=1, Freq=00 (4096Hz)
        timer.write_tac(0x04)
        
        # Inicializar TIMA a 0xFF (próximo incremento causará overflow)
        timer.write_tima(0xFF)
        
        # Avanzar 1024 T-Cycles -> TIMA debe hacer overflow y recargarse con TMA
        timer.tick(1024)
        
        assert timer.read_tima() == 0x42, f"TIMA debe recargarse con TMA (0x42) después de overflow, pero es 0x{timer.read_tima():02X}"
    
    def test_tima_overflow_multiple(self) -> None:
        """Test: Verificar múltiples overflows de TIMA"""
        timer = Timer()
        
        timer.write_tma(0x10)
        timer.write_tac(0x04)  # 4096Hz
        timer.write_tima(0xFE)
        
        # Primer incremento: 0xFE -> 0xFF
        timer.tick(1024)
        assert timer.read_tima() == 0xFF, "TIMA debe ser 0xFF"
        
        # Segundo incremento: 0xFF -> overflow -> 0x10 (TMA)
        timer.tick(1024)
        assert timer.read_tima() == 0x10, f"TIMA debe recargarse con TMA (0x10) después de overflow, pero es 0x{timer.read_tima():02X}"
        
        # Continuar incrementando
        timer.tick(1024)
        assert timer.read_tima() == 0x11, "TIMA debe continuar incrementando después del overflow"


class TestTimerTMA:
    """Tests para el registro TMA (Timer Modulo)"""
    
    def test_tma_initial_state(self) -> None:
        """Test: Verificar que TMA se inicializa en 0"""
        timer = Timer()
        
        assert timer.read_tma() == 0, "TMA debe ser 0 al inicio"
    
    def test_tma_read_write(self) -> None:
        """Test: Verificar lectura/escritura de TMA"""
        timer = Timer()
        
        timer.write_tma(0x42)
        assert timer.read_tma() == 0x42, "TMA debe ser 0x42"
        
        timer.write_tma(0xFF)
        assert timer.read_tma() == 0xFF, "TMA debe ser 0xFF"


class TestTimerTAC:
    """Tests para el registro TAC (Timer Control)"""
    
    def test_tac_initial_state(self) -> None:
        """Test: Verificar que TAC se inicializa en 0 (Timer desactivado)"""
        timer = Timer()
        
        # TAC debe tener bits 0-2 en 0, pero bits 3-7 siempre son 1
        tac_value = timer.read_tac()
        assert (tac_value & 0x07) == 0x00, "TAC bits 0-2 deben ser 0 al inicio"
        assert (tac_value & 0xF8) == 0xF8, "TAC bits 3-7 deben ser 1"
    
    def test_tac_read_write(self) -> None:
        """Test: Verificar lectura/escritura de TAC"""
        timer = Timer()
        
        # Escribir TAC con Enable=1, Freq=00 (4096Hz)
        timer.write_tac(0x04)
        tac_value = timer.read_tac()
        assert (tac_value & 0x07) == 0x04, "TAC debe tener Enable=1, Freq=00"
        
        # Escribir TAC con Enable=1, Freq=01 (262144Hz)
        timer.write_tac(0x05)
        tac_value = timer.read_tac()
        assert (tac_value & 0x07) == 0x05, "TAC debe tener Enable=1, Freq=01"
    
    def test_tac_enable_disable(self) -> None:
        """Test: Verificar que TIMA solo incrementa cuando TAC Enable está activo"""
        timer = Timer()
        
        timer.write_tima(0x00)
        
        # Activar Timer
        timer.write_tac(0x04)  # Enable=1, Freq=00 (4096Hz)
        timer.tick(1024)
        assert timer.read_tima() == 0x01, "TIMA debe incrementar cuando Timer está activo"
        
        # Desactivar Timer
        timer.write_tac(0x00)  # Enable=0
        timer.tick(1024)
        assert timer.read_tima() == 0x01, "TIMA no debe incrementar cuando Timer está desactivado"
        
        # Reactivar Timer
        timer.write_tac(0x04)  # Enable=1
        timer.tick(1024)
        assert timer.read_tima() == 0x02, "TIMA debe continuar incrementando cuando se reactiva"


class TestTimerInterrupt:
    """Tests para interrupciones del Timer"""
    
    def test_tima_overflow_interrupt(self) -> None:
        """Test: Verificar que se solicita interrupción cuando TIMA hace overflow"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        
        # Configurar Timer
        timer.write_tma(0x42)
        timer.write_tac(0x04)  # Enable=1, Freq=00 (4096Hz)
        timer.write_tima(0xFF)
        
        # Verificar que IF bit 2 está desactivado inicialmente
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) == 0, "IF bit 2 debe estar desactivado inicialmente"
        
        # Avanzar hasta overflow
        timer.tick(1024)
        
        # Verificar que IF bit 2 se activó
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) != 0, f"IF bit 2 debe estar activado después de overflow, pero IF=0x{if_val:02X}"
    
    def test_tima_overflow_interrupt_multiple(self) -> None:
        """Test: Verificar múltiples interrupciones de Timer"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        
        timer.write_tma(0x00)
        timer.write_tac(0x04)  # 4096Hz
        timer.write_tima(0xFE)
        
        # Primer overflow
        timer.tick(1024)  # 0xFE -> 0xFF
        timer.tick(1024)  # 0xFF -> overflow -> 0x00
        
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) != 0, "IF bit 2 debe estar activado después del primer overflow"
        
        # Limpiar IF bit 2 (simular que la CPU procesó la interrupción)
        mmu.write_byte(IO_IF, if_val & ~0x04)
        
        # Segundo overflow
        timer.tick(1024 * 256)  # Avanzar hasta el siguiente overflow
        
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) != 0, "IF bit 2 debe estar activado después del segundo overflow"


class TestTimerMMUIntegration:
    """Tests de integración entre Timer y MMU para TIMA/TMA/TAC"""
    
    def test_mmu_read_tima(self) -> None:
        """Test: Verificar lectura de TIMA a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        mmu.set_timer(timer)
        
        timer.write_tima(0x42)
        
        tima_value = mmu.read_byte(IO_TIMA)
        assert tima_value == 0x42, f"TIMA debe ser 0x42, pero es 0x{tima_value:02X}"
    
    def test_mmu_write_tima(self) -> None:
        """Test: Verificar escritura en TIMA a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        mmu.set_timer(timer)
        
        mmu.write_byte(IO_TIMA, 0x42)
        
        assert timer.read_tima() == 0x42, "TIMA debe ser 0x42 después de escribir a través de MMU"
    
    def test_mmu_read_write_tma(self) -> None:
        """Test: Verificar lectura/escritura de TMA a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        mmu.set_timer(timer)
        
        mmu.write_byte(IO_TMA, 0x10)
        tma_value = mmu.read_byte(IO_TMA)
        assert tma_value == 0x10, f"TMA debe ser 0x10, pero es 0x{tma_value:02X}"
    
    def test_mmu_read_write_tac(self) -> None:
        """Test: Verificar lectura/escritura de TAC a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        mmu.set_timer(timer)
        
        mmu.write_byte(IO_TAC, 0x04)  # Enable=1, Freq=00
        tac_value = mmu.read_byte(IO_TAC)
        assert (tac_value & 0x07) == 0x04, f"TAC debe tener Enable=1, Freq=00, pero es 0x{tac_value:02X}"
    
    def test_mmu_timer_full_cycle(self) -> None:
        """Test: Verificar ciclo completo de Timer a través de MMU"""
        mmu = MMU(None)
        timer = Timer()
        timer.set_mmu(mmu)
        mmu.set_timer(timer)
        
        # Configurar Timer a través de MMU
        mmu.write_byte(IO_TMA, 0x20)
        mmu.write_byte(IO_TAC, 0x04)  # Enable=1, Freq=00 (4096Hz)
        mmu.write_byte(IO_TIMA, 0xFF)
        
        # Avanzar hasta overflow
        timer.tick(1024)
        
        # Verificar que TIMA se recargó con TMA
        tima_value = mmu.read_byte(IO_TIMA)
        assert tima_value == 0x20, f"TIMA debe recargarse con TMA (0x20), pero es 0x{tima_value:02X}"
        
        # Verificar que se solicitó interrupción
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x04) != 0, f"IF bit 2 debe estar activado, pero IF=0x{if_val:02X}"

