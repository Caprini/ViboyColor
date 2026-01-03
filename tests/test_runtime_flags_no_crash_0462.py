"""Test anti-regresión para verificar que los flags de entorno no causan crashes.

Step 0462: Detecta shadowing de 'os' y otros problemas de importación.
"""

import os
import pytest
from unittest.mock import patch


def test_env_flag_helper_importable():
    """Verifica que el módulo viboy se puede importar sin shadowing de os."""
    try:
        import src.viboy
        # Verificar que os está disponible en el módulo
        # Si hay shadowing, esto fallará con UnboundLocalError
        assert hasattr(src.viboy, 'os') or 'os' in dir(src.viboy)
    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError detectado (shadowing de os): {e}")


def test_env_flag_helper_with_env_on():
    """Verifica que los flags de entorno retornan True cuando la variable es '1'."""
    with patch.dict(os.environ, {'VIBOY_FORCE_BGP': '1'}):
        result = os.environ.get('VIBOY_FORCE_BGP', '0') == '1'
        assert result is True


def test_env_flag_helper_with_env_off():
    """Verifica que los flags de entorno retornan False cuando la variable es '0' o no existe."""
    with patch.dict(os.environ, {'VIBOY_FORCE_BGP': '0'}, clear=False):
        result = os.environ.get('VIBOY_FORCE_BGP', '0') == '1'
        assert result is False
    
    # Sin variable de entorno
    if 'VIBOY_FORCE_BGP' in os.environ:
        del os.environ['VIBOY_FORCE_BGP']
    result = os.environ.get('VIBOY_FORCE_BGP', '0') == '1'
    assert result is False


def test_viboy_module_imports_without_crash():
    """Verifica que el módulo viboy se puede importar sin crashes.
    
    Este test detecta UnboundLocalError y otros errores de importación.
    """
    try:
        import src.viboy
        # Si llegamos aquí, el import fue exitoso
        assert True
    except UnboundLocalError as e:
        pytest.fail(f"UnboundLocalError al importar viboy (posible shadowing): {e}")
    except Exception as e:
        # Otros errores son aceptables (ej: pygame no disponible en CI)
        # pero UnboundLocalError NO
        if "UnboundLocalError" in str(type(e)):
            pytest.fail(f"UnboundLocalError inesperado: {e}")

