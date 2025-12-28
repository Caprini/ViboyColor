# Script de PowerShell para forzar la recompilacion del modulo C++ en Windows
# Uso: .\rebuild_cpp.ps1

Write-Host "Hard Rebuild del modulo C++ de Viboy Color" -ForegroundColor Cyan
Write-Host ""

# 1. Cerrar procesos de Python (opcional, comentado por seguridad)
# Write-Host "CERRANDO PROCESOS DE PYTHON..." -ForegroundColor Yellow
# Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
# Start-Sleep -Seconds 2

# 2. Buscar y renombrar archivos .pyd antiguos
Write-Host "Buscando archivos .pyd antiguos..." -ForegroundColor Yellow
$pydFiles = Get-ChildItem -Path . -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue

if ($pydFiles.Count -gt 0) {
    foreach ($file in $pydFiles) {
        $oldName = $file.FullName
        $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $newName = $oldName + "_OLD_" + $timestamp
        Write-Host "  Renombrando: $($file.Name) -> $($file.Name)_OLD" -ForegroundColor Gray
        try {
            Rename-Item -Path $oldName -NewName $newName -ErrorAction Stop
            Write-Host "  [OK] Renombrado exitosamente" -ForegroundColor Green
        } catch {
            $errorMsg = $_.Exception.Message
            Write-Host "  [WARN] No se pudo renombrar (puede estar en uso): $errorMsg" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "  [INFO] No se encontraron archivos .pyd" -ForegroundColor Gray
}

# 3. Limpiar archivos compilados
Write-Host ""
Write-Host "Limpiando archivos compilados..." -ForegroundColor Yellow
try {
    python setup.py clean --all 2>&1 | Out-Null
    Write-Host "  [OK] Limpieza completada" -ForegroundColor Green
} catch {
    $errorMsg = $_.Exception.Message
    Write-Host "  [WARN] Error en limpieza: $errorMsg" -ForegroundColor Yellow
}

# 4. Recompilar
Write-Host ""
Write-Host "Recompilando modulo C++..." -ForegroundColor Yellow
try {
    python setup.py build_ext --inplace
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[OK] Recompilacion exitosa!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Proximos pasos:" -ForegroundColor Cyan
        Write-Host "  1. Ejecuta el emulador: python main.py roms/tetris.gb" -ForegroundColor White
        Write-Host "  2. Busca el log '[PPU C++] STEP LIVE' en la consola" -ForegroundColor White
        Write-Host "  3. Verifica que la pantalla es blanca (sin punto rojo)" -ForegroundColor White
    } else {
        Write-Host ""
        Write-Host "[ERROR] Error en la recompilacion. Revisa los mensajes anteriores." -ForegroundColor Red
    }
} catch {
    $errorMsg = $_.Exception.Message
    Write-Host ""
    Write-Host "[ERROR] Error: $errorMsg" -ForegroundColor Red
}
