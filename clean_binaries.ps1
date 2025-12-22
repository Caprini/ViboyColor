# Script de limpieza agresiva de binarios compilados
# Step 0232: Hard Reset del Binario

Write-Host "=== Limpieza Agresiva de Binarios ===" -ForegroundColor Yellow
Write-Host ""

# 1. Cerrar procesos Python
Write-Host "1. Cerrando procesos Python..." -ForegroundColor Cyan
$pythonProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcesses) {
    Write-Host "   Encontrados $($pythonProcesses.Count) proceso(s) Python" -ForegroundColor Yellow
    $pythonProcesses | Stop-Process -Force
    Write-Host "   Procesos Python cerrados" -ForegroundColor Green
} else {
    Write-Host "   No hay procesos Python activos" -ForegroundColor Green
}

Start-Sleep -Seconds 1

# 2. Eliminar carpeta build
Write-Host ""
Write-Host "2. Eliminando carpeta build/..." -ForegroundColor Cyan
if (Test-Path "build") {
    Remove-Item -Recurse -Force "build"
    Write-Host "   Carpeta build/ eliminada" -ForegroundColor Green
} else {
    Write-Host "   Carpeta build/ no existe" -ForegroundColor Green
}

# 3. Eliminar archivos .pyd
Write-Host ""
Write-Host "3. Eliminando archivos .pyd..." -ForegroundColor Cyan
$pydFiles = Get-ChildItem -Recurse -Filter "*.pyd" -ErrorAction SilentlyContinue
if ($pydFiles) {
    Write-Host "   Encontrados $($pydFiles.Count) archivo(s) .pyd" -ForegroundColor Yellow
    $pydFiles | Remove-Item -Force
    Write-Host "   Archivos .pyd eliminados" -ForegroundColor Green
} else {
    Write-Host "   No se encontraron archivos .pyd" -ForegroundColor Green
}

# 4. Eliminar archivos .so (por si acaso, para compatibilidad con otros sistemas)
Write-Host ""
Write-Host "4. Eliminando archivos .so..." -ForegroundColor Cyan
$soFiles = Get-ChildItem -Recurse -Filter "*.so" -ErrorAction SilentlyContinue
if ($soFiles) {
    Write-Host "   Encontrados $($soFiles.Count) archivo(s) .so" -ForegroundColor Yellow
    $soFiles | Remove-Item -Force
    Write-Host "   Archivos .so eliminados" -ForegroundColor Green
} else {
    Write-Host "   No se encontraron archivos .so" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== Limpieza Completada ===" -ForegroundColor Green
Write-Host ""
Write-Host "Ahora puedes ejecutar: .\rebuild_cpp.ps1" -ForegroundColor Yellow

