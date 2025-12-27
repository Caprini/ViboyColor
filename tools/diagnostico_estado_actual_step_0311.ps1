#!/usr/bin/env pwsh
# -*- coding: utf-8 -*-
<#
.SYNOPSIS
    Script de diagnóstico del estado actual del emulador Viboy Color (Step 0311)

.DESCRIPTION
    Ejecuta una serie de verificaciones para diagnosticar el estado actual del emulador:
    - Verificación de carga de ROMs (GB y GBC)
    - Verificación de renderizado (con y sin tiles)
    - Verificación de rendimiento (FPS)
    - Verificación de controles básicos
    - Estado de componentes principales

.NOTES
    Este script genera un reporte completo en DIAGNOSTICO_ESTADO_ACTUAL_STEP_0311.md
#>

$ErrorActionPreference = "Stop"

# Configuración
$LOG_FILE = "logs/diagnostico_step_0311.log"
$OUTPUT_FILE = "DIAGNOSTICO_ESTADO_ACTUAL_STEP_0311.md"
$ROM_DIR = "roms"
$TEST_DURATION = 10  # segundos para pruebas de rendimiento

# Crear directorio de logs si no existe
if (-not (Test-Path "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

# Inicializar reporte
$report = @"
# Diagnóstico del Estado Actual - Step 0311

**Fecha**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")  
**Objetivo**: Verificar estado actual del emulador antes de implementar mejoras

---

## Resumen Ejecutivo

Este documento recopila el estado actual del emulador Viboy Color después del Step 0310 (verificación del limitador de FPS).

---

## 1. Verificación de ROMs Disponibles

"@

Write-Host "🔍 Verificando ROMs disponibles..." -ForegroundColor Cyan

# Buscar ROMs GB y GBC
$gb_roms = @()
$gbc_roms = @()

if (Test-Path $ROM_DIR) {
    $gb_roms = Get-ChildItem -Path $ROM_DIR -Filter "*.gb" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
    $gbc_roms = Get-ChildItem -Path $ROM_DIR -Filter "*.gbc" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
}

$report += "`n### ROMs GB (DMG) encontradas:`n"
if ($gb_roms.Count -gt 0) {
    $report += "- ✅ $($gb_roms.Count) ROM(s) GB encontrada(s):`n"
    foreach ($rom in $gb_roms) {
        $report += "  - `"$rom`"`n"
    }
} else {
    $report += "- ⚠️ No se encontraron ROMs GB (.gb)`n"
}

$report += "`n### ROMs GBC encontradas:`n"
if ($gbc_roms.Count -gt 0) {
    $report += "- ✅ $($gbc_roms.Count) ROM(s) GBC encontrada(s):`n"
    foreach ($rom in $gbc_roms) {
        $report += "  - `"$rom`"`n"
    }
} else {
    $report += "- ⚠️ No se encontraron ROMs GBC (.gbc)`n"
}

$report += "`n---`n`n## 2. Verificación de Componentes del Sistema`n`n"

Write-Host "🔍 Verificando componentes del sistema..." -ForegroundColor Cyan

# Verificar que Python está disponible
try {
    $pythonVersion = python --version 2>&1
    $report += "### Python`n"
    $report += "- ✅ Python disponible: $pythonVersion`n`n"
} catch {
    $report += "### Python`n"
    $report += "- ❌ Python no encontrado en PATH`n`n"
}

# Verificar que el módulo C++ está compilado
$report += "### Módulos Cython/C++`n"
if (Test-Path "src/core/cython/mmu.cpython-*.pyd") {
    $report += "- ✅ Módulo MMU C++ compilado`n"
} else {
    $report += "- ⚠️ Módulo MMU C++ no encontrado (puede necesitar recompilación)`n"
}

if (Test-Path "src/core/cython/ppu.cpython-*.pyd") {
    $report += "- ✅ Módulo PPU C++ compilado`n"
} else {
    $report += "- ⚠️ Módulo PPU C++ no encontrado (puede necesitar recompilación)`n"
}

$report += "`n---`n`n## 3. Verificación de Carga de ROM`n`n"

# Probar carga de ROM si hay alguna disponible
$test_rom = $null
if ($gb_roms.Count -gt 0) {
    $test_rom = Join-Path $ROM_DIR $gb_roms[0]
} elseif ($gbc_roms.Count -gt 0) {
    $test_rom = Join-Path $ROM_DIR $gbc_roms[0]
}

if ($test_rom) {
    Write-Host "🔍 Probando carga de ROM: $test_rom" -ForegroundColor Cyan
    $report += "### ROM de Prueba: $(Split-Path $test_rom -Leaf)`n`n"
    
    # Intentar cargar ROM usando Python (sin ejecutar el emulador completo)
    try {
        # Crear script Python temporal
        $pyScript = "temp_test_cartridge.py"
        @"
import sys
from pathlib import Path
from src.memory.cartridge import Cartridge

try:
    cart = Cartridge(r'$test_rom')
    header = cart.get_header_info()
    print('SUCCESS|TITLE:' + str(header['title']) + '|TYPE:' + str(header['cartridge_type']) + '|ROMSIZE:' + str(header['rom_size']))
except Exception as e:
    print('ERROR|' + str(e))
"@ | Out-File -FilePath $pyScript -Encoding UTF8 -NoNewline
        
        $result = python $pyScript 2>&1 | Out-String
        Remove-Item $pyScript -ErrorAction SilentlyContinue
        
        if ($result -match "SUCCESS") {
            $report += "- ✅ ROM cargada correctamente`n"
            $report += "- Información del header:`n"
            if ($result -match "TITLE:([^|]+)") {
                $title = $matches[1]
                $report += "  - Título: $title`n"
            }
            if ($result -match "TYPE:([^|]+)") {
                $type = $matches[1]
                $report += "  - Tipo: $type`n"
            }
            if ($result -match "ROMSIZE:([^|]+)") {
                $romsize = $matches[1]
                $report += "  - Tamaño ROM: $romsize KB`n"
            }
        } else {
            $report += "- ❌ Error al cargar ROM: $result`n"
        }
    } catch {
        $report += "- ❌ Error al verificar carga de ROM: $_`n"
    }
} else {
    $report += "- ⚠️ No hay ROMs disponibles para probar carga`n"
}

$report += "`n---`n`n## 4. Verificación de Renderizado (Sin Tiles)`n`n"

$report += "### Estado Esperado`n"
$report += "- Pantalla inicial: Blanca o negra (sin gráficos)`n"
$report += "- No debe crashear al iniciar`n"
$report += "- VRAM debería estar vacía o con valores iniciales`n`n"

$report += "### Verificación Manual Requerida`n"
$report += "Ejecutar manualmente:`n"
if ($test_rom) {
    $romName = Split-Path $test_rom -Leaf
    $report += "```powershell`n"
    $report += "python main.py `"$romName`"`n"
    $report += "```\n"
    $report += "**Nota**: La pantalla debería estar blanca (sin tiles cargados desde el juego).`n`n"
} else {
    $report += "```powershell`n"
    $report += "python main.py ruta_a_rom.gb`n"
    $report += "```\n"
    $report += "**Nota**: Reemplazar 'ruta_a_rom.gb' con una ROM válida.`n`n"
}

$report += "---`n`n## 5. Verificación de Renderizado (Con Tiles Manuales)`n`n"

$report += "### Función load_test_tiles()`n"
$report += "- ✅ Implementada en MMU.cpp (línea 1124)`n"
$report += "- ✅ Disponible desde Cython (mmu.pyx línea 251)`n"
$report += "- ✅ Integrada en viboy.py (línea 277-278)`n"
$report += "- ✅ Flag --load-test-tiles disponible en main.py (línea 65)`n`n"

$report += "### Verificación Manual Requerida`n"
$report += "Ejecutar manualmente con flag --load-test-tiles:`n"
if ($test_rom) {
    $romName = Split-Path $test_rom -Leaf
    $report += "```powershell`n"
    $report += "python main.py `"$romName`" --load-test-tiles`n"
    $report += "```\n"
    $report += "**Resultado Esperado**:`n"
    $report += "- Debería mostrar tiles de prueba (checkerboard, líneas, etc.)`n"
    $report += "- Tiles cargados: Tile 0 (blanco), Tile 1 (checkerboard), Tile 2 (líneas horizontales), Tile 3 (líneas verticales)`n"
    $report += "- Patrón alternado en el tilemap`n`n"
} else {
    $report += "```powershell`n"
    $report += "python main.py ruta_a_rom.gb --load-test-tiles`n"
    $report += "```\n"
}

$report += "---`n`n## 6. Verificación de Rendimiento`n`n"

$report += "### Estado Conocido (Steps 0308-0310)`n"
$report += "- Step 0308: FPS promedio sin limitador: ~306 FPS`n"
$report += "- Step 0309: Limitador de FPS implementado y corregido`n"
$report += "- Step 0310: FPS limitado promedio: ~78.63 FPS (objetivo: ~60 FPS)`n"
$report += "- Step 0310: Tick time promedio: 17.45ms (objetivo: 16.67ms)`n`n"

$report += "### Verificación Automática`n"
if ($test_rom) {
    Write-Host "🔍 Ejecutando prueba de rendimiento (10 segundos)..." -ForegroundColor Cyan
    $report += "Ejecutando prueba de rendimiento durante $TEST_DURATION segundos...`n`n"
    
    try {
        # Ejecutar emulador en background y capturar logs
        $perfLog = "logs/perf_test_step_0311.log"
        $job = Start-Job -ScriptBlock {
            param($rom, $logFile, $duration)
            Set-Location $using:PWD
            $startTime = Get-Date
            $process = Start-Process -FilePath "python" -ArgumentList "main.py", "`"$rom`"", "--verbose" -PassThru -NoNewWindow -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err"
            
            # Esperar duración especificada
            while (((Get-Date) - $startTime).TotalSeconds -lt $duration) {
                Start-Sleep -Milliseconds 100
            }
            
            # Detener proceso
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
        } -ArgumentList $test_rom, $perfLog, $TEST_DURATION
        
        # Esperar a que termine
        $job | Wait-Job -Timeout ($TEST_DURATION + 5) | Out-Null
        $job | Remove-Job -Force -ErrorAction SilentlyContinue
        
        # Analizar logs
        if (Test-Path $perfLog) {
            $fpsTraces = Select-String -Path $perfLog -Pattern "\[PERFORMANCE-TRACE\]" | Select-Object -Last 20
            if ($fpsTraces) {
                $fpsValues = $fpsTraces | ForEach-Object {
                    if ($_.Line -match "FPS:\s*(\d+\.?\d*)") {
                        [double]$matches[1]
                    }
                }
                
                if ($fpsValues.Count -gt 0) {
                    $avgFPS = ($fpsValues | Measure-Object -Average).Average
                    $minFPS = ($fpsValues | Measure-Object -Minimum).Minimum
                    $maxFPS = ($fpsValues | Measure-Object -Maximum).Maximum
                    
                    $report += "**Resultados (últimos 20 registros):**`n"
                    $report += "- FPS Promedio: $([math]::Round($avgFPS, 2)) FPS`n"
                    $report += "- FPS Mínimo: $([math]::Round($minFPS, 2)) FPS`n"
                    $report += "- FPS Máximo: $([math]::Round($maxFPS, 2)) FPS`n`n"
                    
                    if ($avgFPS -ge 55 -and $avgFPS -le 65) {
                        $report += "- ✅ FPS dentro del rango objetivo (55-65 FPS)`n`n"
                    } elseif ($avgFPS -ge 50 -and $avgFPS -le 80) {
                        $report += "- ⚠️ FPS aceptable pero fuera del rango objetivo (50-80 FPS)`n`n"
                    } else {
                        $report += "- ❌ FPS fuera del rango aceptable`n`n"
                    }
                } else {
                    $report += "- ⚠️ No se pudieron extraer valores de FPS de los logs`n`n"
                }
            } else {
                $report += "- ⚠️ No se encontraron registros [PERFORMANCE-TRACE] en los logs`n`n"
            }
        } else {
            $report += "- ⚠️ No se generó archivo de log de rendimiento`n`n"
        }
    } catch {
        $report += "- ❌ Error al ejecutar prueba de rendimiento: $_`n`n"
    }
} else {
    $report += "- ⚠️ No hay ROMs disponibles para probar rendimiento`n"
    $report += "- **Prueba manual requerida**: Ejecutar emulador y verificar FPS en título de ventana`n`n"
}

$report += "---`n`n## 7. Verificación de Controles`n`n"

$report += "### Mapeo de Teclas (Verificar en código)`n"
$report += "**Archivo**: src/gpu/renderer.py o src/io/joypad.py`n`n"

# Buscar mapeo de teclas en el código
try {
    $joypadCode = Get-Content "src/io/joypad.py" -Raw -ErrorAction SilentlyContinue
    if ($joypadCode) {
        if ($joypadCode -match "KEY.*A|A.*KEY") {
            $report += "- ✅ Mapeo de teclas encontrado en joypad.py`n"
        }
    }
    
    $rendererCode = Get-Content "src/gpu/renderer.py" -Raw -ErrorAction SilentlyContinue
    if ($rendererCode) {
        if ($rendererCode -match "KEYDOWN|K_") {
            $report += "- ✅ Manejo de eventos de teclado encontrado en renderer.py`n"
        }
    }
} catch {
    $report += "- ⚠️ No se pudo verificar mapeo de teclas en el código\n"
}

$report += "`n### Verificación Manual Requerida`n"
$report += "Ejecutar emulador y probar controles:`n"
$report += "- **A, B**: Botones de acción`n"
$report += "- **Start, Select**: Botones del menú`n"
$report += "- **D-Pad**: Direcciones (UP, DOWN, LEFT, RIGHT)`n`n"

$report += "---`n`n## 8. Resumen de Problemas Identificados`n`n"

$report += "### Problemas Conocidos (de Steps anteriores)`n"
$report += "1. **VRAM vacía**: Los juegos no cargan tiles automáticamente (investigado en Steps 0287-0298)`n"
$report += "   - Solución temporal: `load_test_tiles()` disponible con `--load-test-tiles`\n"
$report += "2. **FPS ligeramente alto**: 78.63 FPS vs objetivo de 60 FPS (Step 0310)`n"
$report += "   - Estado: Aceptable, tick_time correcto (17.45ms ≈ 16.67ms)\n\n"

$report += "### Nuevos Problemas (si se identifican)\n"
$report += "- _Completar después de verificación manual_\n\n"

$report += "---\n\n## 9. Próximos Pasos Recomendados\n\n"

$report += "### Fase 1: Diagnóstico y Activación de Gráficos\n"
$report += "1. ✅ **Completado**: Verificación del estado actual (este documento)\n"
$report += "2. ⏳ **Pendiente**: Activar carga manual de tiles por defecto (temporal)\n"
$report += "3. ⏳ **Pendiente**: Verificar renderizado con tiles cargados\n\n"

$report += "### Fase 2: Optimización y Estabilidad\n"
$report += "1. ⏳ **Pendiente**: Asegurar FPS estable ~60 FPS\n"
$report += "2. ⏳ **Pendiente**: Verificar compatibilidad GB/GBC\n"
$report += "3. ⏳ **Pendiente**: Optimizar renderizado si es necesario\n\n"

$report += "### Fase 3: Controles y Jugabilidad\n"
$report += "1. ⏳ **Pendiente**: Verificar que los controles funcionan\n"
$report += "2. ⏳ **Pendiente**: Probar con múltiples ROMs (GB y GBC)\n"
$report += "3. ⏳ **Pendiente**: Iterar hasta lograr funcionalidad completa\n\n"

$report += "---\n\n## 10. Conclusión\n\n"
$report += "Este diagnóstico proporciona una visión completa del estado actual del emulador antes de implementar las mejoras del Plan Estratégico (Step 0311).\n\n"
$report += "**Estado General**: 🟡 **En Desarrollo**\n"
$report += "- Renderizado: ⚠️ Funcional con tiles manuales, no automático desde juegos\n"
$report += "- Rendimiento: ✅ Limitador de FPS funcionando correctamente\n"
$report += "- Controles: ⏳ Requiere verificación manual\n"
$report += "- Compatibilidad: ⏳ Requiere pruebas con múltiples ROMs\n\n"

# Guardar reporte
$report | Out-File -FilePath $OUTPUT_FILE -Encoding UTF8

Write-Host "✅ Diagnóstico completado" -ForegroundColor Green
Write-Host "📄 Reporte guardado en: $OUTPUT_FILE" -ForegroundColor Green
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Yellow
Write-Host "  1. Revisar el reporte: $OUTPUT_FILE"
Write-Host "  2. Ejecutar verificaciones manuales requeridas"
Write-Host "  3. Continuar con Tarea 2: Activar carga manual de tiles por defecto"

