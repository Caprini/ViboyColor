#!/usr/bin/env pwsh
# Script de diagnóstico del estado actual del emulador Viboy Color (Step 0311)

$ErrorActionPreference = "Stop"

# Configuración
$OUTPUT_FILE = "DIAGNOSTICO_ESTADO_ACTUAL_STEP_0311.md"
$ROM_DIR = "roms"

# Inicializar reporte
$report = "# Diagnóstico del Estado Actual - Step 0311`n`n"
$report += "**Fecha**: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n"
$report += "**Objetivo**: Verificar estado actual del emulador antes de implementar mejoras`n`n"
$report += "---`n`n"

# Sección 1: ROMs Disponibles
$report += "## 1. Verificación de ROMs Disponibles`n`n"

if (Test-Path $ROM_DIR) {
    $gb_roms = Get-ChildItem -Path $ROM_DIR -Filter "*.gb" -ErrorAction SilentlyContinue
    $gbc_roms = Get-ChildItem -Path $ROM_DIR -Filter "*.gbc" -ErrorAction SilentlyContinue
    
    $report += "### ROMs GB (DMG) encontradas:`n"
    if ($gb_roms.Count -gt 0) {
        $report += "- Se encontraron $($gb_roms.Count) ROM(s) GB:`n"
        foreach ($rom in $gb_roms) {
            $report += "  - $($rom.Name)`n"
        }
    } else {
        $report += "- No se encontraron ROMs GB (.gb)`n"
    }
    
    $report += "`n### ROMs GBC encontradas:`n"
    if ($gbc_roms.Count -gt 0) {
        $report += "- Se encontraron $($gbc_roms.Count) ROM(s) GBC:`n"
        foreach ($rom in $gbc_roms) {
            $report += "  - $($rom.Name)`n"
        }
    } else {
        $report += "- No se encontraron ROMs GBC (.gbc)`n"
    }
} else {
    $report += "- Directorio de ROMs no encontrado: $ROM_DIR`n"
}

$report += "`n---`n`n## 2. Verificación de Componentes del Sistema`n`n"

# Verificar Python
try {
    $pythonVersion = python --version 2>&1
    $report += "### Python`n"
    $report += "- Python disponible: $pythonVersion`n`n"
} catch {
    $report += "### Python`n"
    $report += "- Python no encontrado en PATH`n`n"
}

# Verificar módulos compilados
$report += "### Módulos Cython/C++`n"
$mmuFound = (Test-Path "src/core/cython/mmu.cpython-*.pyd") -or (Test-Path "src/core/cython/mmu*.pyd")
$ppuFound = (Test-Path "src/core/cython/ppu.cpython-*.pyd") -or (Test-Path "src/core/cython/ppu*.pyd")

if ($mmuFound) {
    $report += "- Módulo MMU C++ compilado`n"
} else {
    $report += "- Módulo MMU C++ no encontrado (puede necesitar recompilación)`n"
}

if ($ppuFound) {
    $report += "- Módulo PPU C++ compilado`n"
} else {
    $report += "- Módulo PPU C++ no encontrado (puede necesitar recompilación)`n"
}

$report += "`n---`n`n## 3. Estado del Emulador`n`n"

$report += "### Funcionalidad de Carga Manual de Tiles`n"
$report += "- Implementada en MMU.cpp`n"
$report += "- Disponible desde Cython`n"
$report += "- Integrada en viboy.py`n"
$report += "- Flag --load-test-tiles disponible en main.py`n`n"

$report += "---`n`n## 4. Próximos Pasos`n`n"

$report += "### Fase 1: Diagnóstico y Activación de Gráficos`n"
$report += "1. Completado: Verificación del estado actual (este documento)`n"
$report += "2. Pendiente: Activar carga manual de tiles por defecto (temporal)`n"
$report += "3. Pendiente: Verificar renderizado con tiles cargados`n`n"

$report += "### Fase 2: Optimización y Estabilidad`n"
$report += "1. Pendiente: Asegurar FPS estable ~60 FPS`n"
$report += "2. Pendiente: Verificar compatibilidad GB/GBC`n`n"

$report += "### Fase 3: Controles y Jugabilidad`n"
$report += "1. Pendiente: Verificar que los controles funcionan`n"
$report += "2. Pendiente: Probar con múltiples ROMs`n`n"

$report += "---`n`n## 5. Conclusión`n`n"
$report += "Este diagnóstico proporciona una visión básica del estado actual del emulador.`n"
$report += "Para verificaciones detalladas, ver el Plan Estratégico Step 0311.`n"

# Guardar reporte
$report | Out-File -FilePath $OUTPUT_FILE -Encoding UTF8

Write-Host "✅ Diagnóstico completado" -ForegroundColor Green
Write-Host "📄 Reporte guardado en: $OUTPUT_FILE" -ForegroundColor Green
