"""
Tests para el Joypad (Control de Botones y Direcciones)

Estos tests validan:
- Inicialización del Joypad
- Lógica Active Low (0 = pulsado, 1 = soltado)
- Selector de lectura (bits 4-5)
- Solicitud de interrupciones cuando se pulsa un botón
- Mapeo correcto de botones a bits
"""

import pytest

from src.io.joypad import Joypad
from src.memory.mmu import MMU, IO_P1, IO_IF, IO_IE


class TestJoypad:
    """Tests para la clase Joypad"""
    
    def test_default_palette_init(self) -> None:
        """Test: Verificar que BGP se inicializa a 0xE4 por defecto"""
        mmu = MMU(None)
        bgp = mmu.read_byte(0xFF47)  # IO_BGP
        assert bgp == 0xE4, f"BGP debe ser 0xE4 (paleta estándar), pero es 0x{bgp:02X}"
    
    def test_joypad_initial_state(self) -> None:
        """Test: Verificar que todos los botones están soltados al inicio"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Todos los botones deben estar soltados (False)
        assert joypad.get_state("right") is False
        assert joypad.get_state("left") is False
        assert joypad.get_state("up") is False
        assert joypad.get_state("down") is False
        assert joypad.get_state("a") is False
        assert joypad.get_state("b") is False
        assert joypad.get_state("select") is False
        assert joypad.get_state("start") is False
    
    def test_joypad_read_default(self) -> None:
        """Test: Leer P1 con selector por defecto (todos los botones sueltos)"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Por defecto, el selector es 0xCF (11001111)
        # Ningún grupo está seleccionado, así que todos los bits deben ser 1
        value = joypad.read()
        # El valor debería ser 0xFF (todos los botones sueltos) o similar
        assert (value & 0x0F) == 0x0F, "Bits 0-3 deben ser 1 (todos sueltos)"
    
    def test_joypad_read_directions(self) -> None:
        """Test: Leer direcciones cuando están todas soltadas"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar direcciones (bit 4 = 0)
        joypad.write(0xEF)  # 0xEF = 11101111 (bit 4 = 0)
        
        # Leer P1 (todas las direcciones están soltadas)
        value = joypad.read()
        # Bits 0-3 deben ser 1 (todas soltadas)
        assert (value & 0x0F) == 0x0F
    
    def test_joypad_read_directions_pressed(self) -> None:
        """Test: Leer direcciones cuando Right está pulsado"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar direcciones (bit 4 = 0)
        joypad.write(0xEF)  # 0xEF = 11101111 (bit 4 = 0)
        
        # Pulsar Right
        joypad.press("right")
        
        # Leer P1
        value = joypad.read()
        # Bit 0 debe ser 0 (Right pulsado), bits 1-3 deben ser 1
        assert (value & 0x01) == 0, "Bit 0 (Right) debe ser 0 (pulsado)"
        assert (value & 0x0E) == 0x0E, "Bits 1-3 deben ser 1 (soltados)"
    
    def test_joypad_read_buttons(self) -> None:
        """Test: Leer botones cuando están todos soltados"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar botones (bit 5 = 0)
        joypad.write(0xDF)  # 0xDF = 11011111 (bit 5 = 0)
        
        # Leer P1 (todos los botones están soltados)
        value = joypad.read()
        # Bits 0-3 deben ser 1 (todos soltados)
        assert (value & 0x0F) == 0x0F
    
    def test_joypad_read_buttons_pressed(self) -> None:
        """Test: Leer botones cuando A está pulsado"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar botones (bit 5 = 0)
        joypad.write(0xDF)  # 0xDF = 11011111 (bit 5 = 0)
        
        # Pulsar A
        joypad.press("a")
        
        # Leer P1
        value = joypad.read()
        # Bit 0 debe ser 0 (A pulsado), bits 1-3 deben ser 1
        assert (value & 0x01) == 0, "Bit 0 (A) debe ser 0 (pulsado)"
        assert (value & 0x0E) == 0x0E, "Bits 1-3 deben ser 1 (soltados)"
    
    def test_joypad_press_interrupt(self) -> None:
        """Test: Pulsar un botón debe activar la interrupción Joypad (bit 4 en IF)"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        assert (mmu.read_byte(IO_IF) & 0x10) == 0, "Bit 4 de IF debe estar limpio"
        
        # Pulsar Start
        joypad.press("start")
        
        # Verificar que el bit 4 de IF está activo
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x10) != 0, "Bit 4 de IF debe estar activo después de pulsar un botón"
    
    def test_joypad_release_no_interrupt(self) -> None:
        """Test: Soltar un botón NO debe activar interrupción"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Pulsar Start
        joypad.press("start")
        
        # Limpiar IF manualmente
        mmu.write_byte(IO_IF, 0x00)
        
        # Soltar Start
        joypad.release("start")
        
        # Verificar que IF sigue limpio
        if_val = mmu.read_byte(IO_IF)
        assert (if_val & 0x10) == 0, "Soltar un botón NO debe activar interrupción"
    
    def test_joypad_press_twice_no_double_interrupt(self) -> None:
        """Test: Pulsar un botón dos veces solo activa interrupción la primera vez"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        
        # Pulsar A la primera vez
        joypad.press("a")
        if_val1 = mmu.read_byte(IO_IF)
        assert (if_val1 & 0x10) != 0, "Primera pulsación debe activar IF"
        
        # Limpiar IF manualmente (simula que la CPU procesó la interrupción)
        mmu.write_byte(IO_IF, 0x00)
        
        # Pulsar A la segunda vez (sin soltar antes)
        joypad.press("a")
        if_val2 = mmu.read_byte(IO_IF)
        # La segunda pulsación NO debe activar IF porque ya estaba pulsado
        assert (if_val2 & 0x10) == 0, "Segunda pulsación sin soltar NO debe activar IF"
    
    def test_joypad_press_release_press_interrupt(self) -> None:
        """Test: Pulsar-Soltar-Pulsar debe activar interrupción ambas veces"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        
        # Pulsar A
        joypad.press("a")
        if_val1 = mmu.read_byte(IO_IF)
        assert (if_val1 & 0x10) != 0, "Primera pulsación debe activar IF"
        
        # Limpiar IF
        mmu.write_byte(IO_IF, 0x00)
        
        # Soltar A
        joypad.release("a")
        if_val2 = mmu.read_byte(IO_IF)
        assert (if_val2 & 0x10) == 0, "Soltar no debe activar IF"
        
        # Pulsar A de nuevo
        joypad.press("a")
        if_val3 = mmu.read_byte(IO_IF)
        assert (if_val3 & 0x10) != 0, "Segunda pulsación (después de soltar) debe activar IF"
    
    def test_joypad_mmu_integration(self) -> None:
        """Test: Integración con MMU - leer/escribir P1 funciona correctamente"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        mmu.set_joypad(joypad)
        
        # Escribir selector en P1 (seleccionar direcciones)
        mmu.write_byte(IO_P1, 0xEF)  # Bit 4 = 0
        
        # Pulsar Right
        joypad.press("right")
        
        # Leer P1 a través de MMU
        value = mmu.read_byte(IO_P1)
        # Bit 0 debe ser 0 (Right pulsado)
        assert (value & 0x01) == 0, "MMU.read_byte(IO_P1) debe reflejar botón pulsado"
    
    def test_joypad_all_directions(self) -> None:
        """Test: Leer todas las direcciones cuando están pulsadas"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar direcciones
        joypad.write(0xEF)
        
        # Pulsar todas las direcciones
        joypad.press("right")
        joypad.press("left")
        joypad.press("up")
        joypad.press("down")
        
        # Leer P1
        value = joypad.read()
        # Todos los bits 0-3 deben ser 0 (todos pulsados)
        assert (value & 0x0F) == 0x00, "Todas las direcciones pulsadas deben tener bits 0-3 = 0"
    
    def test_joypad_all_buttons(self) -> None:
        """Test: Leer todos los botones cuando están pulsados"""
        mmu = MMU(None)
        joypad = Joypad(mmu)
        
        # Seleccionar botones
        joypad.write(0xDF)
        
        # Pulsar todos los botones
        joypad.press("a")
        joypad.press("b")
        joypad.press("select")
        joypad.press("start")
        
        # Leer P1
        value = joypad.read()
        # Todos los bits 0-3 deben ser 0 (todos pulsados)
        assert (value & 0x0F) == 0x00, "Todos los botones pulsados deben tener bits 0-3 = 0"

