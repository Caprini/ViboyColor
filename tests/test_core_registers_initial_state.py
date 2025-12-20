"""
Tests para validar el estado inicial Post-BIOS de los registros de la CPU.

Step 0190: El constructor de CoreRegisters debe inicializar los registros
con los valores exactos que la Boot ROM oficial deja en la CPU antes de
transferir el control al código del cartucho.

Fuente: Pan Docs - "Power Up Sequence", Boot ROM Post-Boot State
"""

import pytest

# Intentar importar el módulo C++ compilado
try:
    from viboy_core import PyRegisters
    CPP_CORE_AVAILABLE = True
except ImportError:
    PyRegisters = None  # type: ignore
    CPP_CORE_AVAILABLE = False
    pytest.skip("viboy_core no disponible. Recompila con: python setup.py build_ext --inplace", allow_module_level=True)


@pytest.mark.skipif(not CPP_CORE_AVAILABLE, reason="viboy_core no disponible")
def test_registers_post_bios_state():
    """
    Verifica que los registros de la CPU se inicializan con sus valores Post-BIOS para DMG.
    
    Valores esperados (según Pan Docs):
    - AF = 0x01B0 (A=0x01 indica DMG, F=0xB0: Z=1, N=0, H=1, C=1)
    - BC = 0x0013
    - DE = 0x00D8
    - HL = 0x014D
    - SP = 0xFFFE
    - PC = 0x0100
    """
    regs = PyRegisters()
    
    # Verificar registros individuales de 8 bits
    assert regs.a == 0x01, f"Registro A debe ser 0x01, obtuvo 0x{regs.a:02X}"
    assert regs.f == 0xB0, f"Registro F debe ser 0xB0, obtuvo 0x{regs.f:02X}"
    
    # Verificar pares de 16 bits
    assert regs.af == 0x01B0, f"Par AF debe ser 0x01B0, obtuvo 0x{regs.af:04X}"
    assert regs.bc == 0x0013, f"Par BC debe ser 0x0013, obtuvo 0x{regs.bc:04X}"
    assert regs.de == 0x00D8, f"Par DE debe ser 0x00D8, obtuvo 0x{regs.de:04X}"
    assert regs.hl == 0x014D, f"Par HL debe ser 0x014D, obtuvo 0x{regs.hl:04X}"
    
    # Verificar registros de 16 bits
    assert regs.sp == 0xFFFE, f"Stack Pointer debe ser 0xFFFE, obtuvo 0x{regs.sp:04X}"
    assert regs.pc == 0x0100, f"Program Counter debe ser 0x0100, obtuvo 0x{regs.pc:04X}"
    
    # Verificar flags individuales (F=0xB0 = 10110000)
    # Bit 7 (Z): 1, Bit 6 (N): 0, Bit 5 (H): 1, Bit 4 (C): 1
    assert regs.flag_z is True, "Flag Z debe estar activo (1)"
    assert regs.flag_n is False, "Flag N debe estar inactivo (0)"
    assert regs.flag_h is True, "Flag H debe estar activo (1)"
    assert regs.flag_c is True, "Flag C debe estar activo (1)"


@pytest.mark.skipif(not CPP_CORE_AVAILABLE, reason="viboy_core no disponible")
def test_registers_post_bios_state_consistency():
    """
    Verifica que los valores de los registros individuales son consistentes
    con los pares de 16 bits.
    """
    regs = PyRegisters()
    
    # Verificar que los pares coinciden con los registros individuales
    assert regs.af == ((regs.a << 8) | regs.f), "Par AF debe coincidir con A y F"
    assert regs.bc == ((regs.b << 8) | regs.c), "Par BC debe coincidir con B y C"
    assert regs.de == ((regs.d << 8) | regs.e), "Par DE debe coincidir con D y E"
    assert regs.hl == ((regs.h << 8) | regs.l), "Par HL debe coincidir con H y L"


@pytest.mark.skipif(not CPP_CORE_AVAILABLE, reason="viboy_core no disponible")
def test_registers_flag_z_critical():
    """
    Verifica que el flag Z está activo, ya que es crítico para las primeras
    comprobaciones condicionales del código de arranque del juego.
    
    Muchos juegos ejecutan instrucciones como `JR Z, some_error_loop` al inicio,
    y si el flag Z no está en el estado correcto, el juego entra en un bucle de error.
    """
    regs = PyRegisters()
    
    # El flag Z debe estar activo (1) para que las primeras comprobaciones
    # condicionales del juego tomen el camino correcto
    assert regs.flag_z is True, (
        "Flag Z debe estar activo (1) para que el código de arranque del juego "
        "tome el camino correcto. Si está inactivo, el juego puede entrar en "
        "un bucle de error."
    )
    
    # Verificar que el registro F tiene el bit 7 activo (Z flag)
    assert (regs.f & 0x80) != 0, "Bit 7 del registro F (Z flag) debe estar activo"

