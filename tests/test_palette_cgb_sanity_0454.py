"""
Test sanity: CGB Palettes (Step 0454)

Valida que CGB palettes permiten más de 1 color.
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters, PyPPU, PyTimer, PyJoypad


@pytest.mark.xfail(reason="CGB palettes no implementadas aún")
def test_cgb_palette_sanity():
    """Valida que CGB palettes permiten más de 1 color."""
    # Verificar si CGB mode está soportado
    try:
        # Intentar activar CGB mode (ajustar según API disponible)
        # Por ahora, asumir que si el test se ejecuta, CGB está disponible
        pass
    except Exception as e:
        pytest.xfail(f"CGB mode no disponible: {e}")
    
    # Inicializar core CGB
    mmu = PyMMU()
    # ... (setup similar a test BGP)
    
    # Activar CGB mode (ajustar según API)
    # mmu.set_hardware_mode(HardwareMode.CGB)  # Si existe
    
    # Escribir 2 colores distintos en BG palette via FF68/FF69
    # Palette 0, color 0: blanco
    # Palette 0, color 1: gris
    
    # Render tile con índices 0/1
    # ...
    
    # Assert unique_rgb_count >= 2
    # ...


if __name__ == "__main__":
    test_cgb_palette_sanity()

