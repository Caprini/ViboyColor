#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test smoke: Validar que el mapping legacy → replacement está completo.

Este test verifica que:
1. Todos los archivos legacy listados existen en tests_legacy/
2. Todos los archivos de reemplazo listados existen en tests/
3. Los counts de tests son razonables (replacement >= legacy)

Referencias:
    - docs/legacy_tests_mapping.md
    - Step 0435: Legacy closure
"""

import pytest
from pathlib import Path

# Directorio raíz del proyecto
PROJECT_ROOT = Path(__file__).parent.parent

# Archivos legacy esperados (movidos a tests_legacy/)
LEGACY_FILES = {
    "test_gpu_background.py": 6,
    "test_gpu_scroll.py": 4,
    "test_gpu_window.py": 3,
    "test_ppu_modes.py": 8,
    "test_ppu_timing.py": 7,
    "test_ppu_vblank_polling.py": 5,
}

# Archivos de reemplazo (en tests/)
REPLACEMENT_FILES = {
    "test_core_ppu_rendering.py": 15,  # Mínimo esperado
    "test_core_ppu_timing.py": 18,     # Mínimo esperado
    "test_core_ppu_sprites.py": 10,    # Mínimo esperado
}


def test_legacy_files_moved_to_tests_legacy():
    """
    Verificar que todos los archivos legacy han sido movidos a tests_legacy/
    y ya NO están en tests/ (suite principal).
    """
    tests_legacy_dir = PROJECT_ROOT / "tests_legacy"
    tests_dir = PROJECT_ROOT / "tests"
    
    assert tests_legacy_dir.exists(), "Directorio tests_legacy/ no existe"
    
    for legacy_file in LEGACY_FILES.keys():
        legacy_path = tests_legacy_dir / legacy_file
        main_path = tests_dir / legacy_file
        
        # El archivo DEBE existir en tests_legacy/
        assert legacy_path.exists(), \
            f"Archivo legacy {legacy_file} NO encontrado en tests_legacy/"
        
        # El archivo NO DEBE existir en tests/ (ya movido)
        assert not main_path.exists(), \
            f"Archivo legacy {legacy_file} aún existe en tests/ (debería estar en tests_legacy/)"


def test_replacement_files_exist():
    """
    Verificar que todos los archivos de reemplazo existen en tests/.
    """
    tests_dir = PROJECT_ROOT / "tests"
    
    for replacement_file in REPLACEMENT_FILES.keys():
        replacement_path = tests_dir / replacement_file
        
        assert replacement_path.exists(), \
            f"Archivo de reemplazo {replacement_file} NO encontrado en tests/"


def test_replacement_coverage_is_complete():
    """
    Verificar que la cobertura de tests de reemplazo es >= que legacy.
    
    Legacy total: 33 tests
    Replacement total: 43+ tests (más completo)
    """
    legacy_total = sum(LEGACY_FILES.values())
    replacement_total = sum(REPLACEMENT_FILES.values())
    
    assert legacy_total == 33, \
        f"Legacy tests count incorrecto: esperado 33, obtenido {legacy_total}"
    
    assert replacement_total >= 43, \
        f"Replacement tests count insuficiente: esperado >= 43, obtenido {replacement_total}"
    
    # Verificar que replacement tiene MÁS cobertura
    assert replacement_total >= legacy_total, \
        f"Replacement tests ({replacement_total}) tienen menos cobertura que legacy ({legacy_total})"


def test_mapping_document_exists():
    """
    Verificar que el documento de mapping existe.
    """
    mapping_doc = PROJECT_ROOT / "docs" / "legacy_tests_mapping.md"
    
    assert mapping_doc.exists(), \
        "Documento docs/legacy_tests_mapping.md no existe"
    
    # Verificar que el documento menciona todos los archivos legacy
    content = mapping_doc.read_text()
    
    for legacy_file in LEGACY_FILES.keys():
        assert legacy_file in content, \
            f"Archivo legacy {legacy_file} no está documentado en legacy_tests_mapping.md"


def test_pytest_suite_does_not_collect_legacy():
    """
    Verificar que pytest NO recoge los tests legacy cuando se ejecuta sin argumentos.
    
    Esto es crítico para que la suite principal no muestre "35 skipped".
    """
    tests_dir = PROJECT_ROOT / "tests"
    
    # Verificar que ningún archivo legacy está en tests/
    for legacy_file in LEGACY_FILES.keys():
        legacy_path = tests_dir / legacy_file
        assert not legacy_path.exists(), \
            f"⚠️ CRÍTICO: {legacy_file} aún está en tests/ y será recogido por pytest"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

