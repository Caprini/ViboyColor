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

