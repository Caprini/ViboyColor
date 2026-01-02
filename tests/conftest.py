"""
Configuración global de pytest para Viboy Color

Este archivo configura el entorno de testing para evitar bloqueos:
- Configura pygame en modo headless (sin ventanas)
- Configura timeouts para evitar tests colgados
- Configura variables de entorno para tests
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz al sys.path para importar módulos
project_root = Path(__file__).parent.parent.absolute()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configurar pygame en modo headless (sin ventanas) para evitar bloqueos
# Esto previene que los tests abran ventanas gráficas que bloqueen pytest
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'

# Configurar variables de entorno para tests
os.environ['VIBOY_TEST_MODE'] = '1'
os.environ['VIBOY_HEADLESS'] = '1'

# Intentar importar y configurar pygame en modo headless
try:
    import pygame
    
    # Inicializar pygame en modo headless si es posible
    # Esto previene que se abran ventanas durante los tests
    try:
        # Intentar inicializar solo los módulos necesarios sin display
        pygame.mixer.pre_init(frequency=22050, size=-16, channels=2, buffer=512)
        # No inicializar pygame.display para evitar ventanas
        # pygame.init() se llamará solo cuando sea necesario en los tests
    except Exception:
        # Si falla, no pasa nada, los tests mockearán pygame
        pass
except ImportError:
    # Pygame no está disponible, los tests que lo requieren se saltarán
    pass


# ============================================================================
# Fixtures para MMU (Step 0422)
# ============================================================================

import pytest

@pytest.fixture
def mmu():
    """
    Fixture estándar para MMU sin ROM-writes habilitados.
    
    Uso: Para tests que ejecutan código desde WRAM (0xC000+) o que no necesitan
    escribir en ROM (0x0000-0x7FFF).
    
    Ejemplo:
        def test_algo(mmu):
            cpu = PyCPU(mmu)
            # cargar programa en WRAM...
    """
    try:
        from viboy_core import PyMMU
        return PyMMU()
    except ImportError:
        pytest.skip("Módulo viboy_core no compilado")


# Step 0425: Eliminado fixture mmu_romw (usaba test_mode_allow_rom_writes no spec-correct)
# Los tests que necesiten ROM personalizada deben usar mmu.load_rom() con bytearray preparado