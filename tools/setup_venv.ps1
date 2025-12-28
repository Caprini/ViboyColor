# Script de PowerShell para configurar correctamente el entorno virtual
# Uso: .\tools\setup_venv.ps1

Write-Host "Configuración de Entorno Virtual para Viboy Color" -ForegroundColor Cyan
Write-Host ""

# Verificar que estamos en el directorio correcto
$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $projectRoot "setup.py"))) {
    Write-Host "[ERROR] No se encontró setup.py. Ejecuta este script desde la raíz del proyecto." -ForegroundColor Red
    exit 1
}

Set-Location $projectRoot

# 1. Verificar versión de Python
Write-Host "[1/5] Verificando Python..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Python no está disponible en el PATH" -ForegroundColor Red
    exit 1
}
Write-Host "  $pythonVersion" -ForegroundColor Green

# 2. Crear o recrear venv
Write-Host ""
Write-Host "[2/5] Configurando entorno virtual..." -ForegroundColor Yellow
$venvPath = Join-Path $projectRoot "venv"

if (Test-Path $venvPath) {
    Write-Host "  Venv existente detectado. ¿Recrear? (S/N)" -ForegroundColor Yellow
    $response = Read-Host
    if ($response -eq "S" -or $response -eq "s") {
        Write-Host "  Eliminando venv existente..." -ForegroundColor Gray
        Remove-Item -Path $venvPath -Recurse -Force
        Write-Host "  Creando nuevo venv..." -ForegroundColor Gray
        python -m venv venv --clear
    } else {
        Write-Host "  Usando venv existente" -ForegroundColor Gray
    }
} else {
    Write-Host "  Creando nuevo venv..." -ForegroundColor Gray
    python -m venv venv
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] No se pudo crear el venv" -ForegroundColor Red
    exit 1
}

# 3. Activar venv
Write-Host ""
Write-Host "[3/5] Activando venv..." -ForegroundColor Yellow
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"

# Verificar política de ejecución
$executionPolicy = Get-ExecutionPolicy
if ($executionPolicy -eq "Restricted") {
    Write-Host "  Política de ejecución restrictiva detectada." -ForegroundColor Yellow
    Write-Host "  Configurando política temporal..." -ForegroundColor Gray
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force
}

if (Test-Path $activateScript) {
    & $activateScript
    Write-Host "  ✓ Venv activado" -ForegroundColor Green
} else {
    Write-Host "[ERROR] No se encontró el script de activación" -ForegroundColor Red
    exit 1
}

# 4. Actualizar pip
Write-Host ""
Write-Host "[4/5] Actualizando pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] No se pudo actualizar pip, continuando..." -ForegroundColor Yellow
}

# 5. Instalar dependencias
Write-Host ""
Write-Host "[5/5] Instalando dependencias..." -ForegroundColor Yellow
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Error al instalar dependencias" -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Dependencias instaladas" -ForegroundColor Green

# 6. Compilar módulo C++
Write-Host ""
Write-Host "[EXTRA] Compilando módulo C++ (viboy_core)..." -ForegroundColor Yellow
Write-Host "  Esto puede tardar varios minutos..." -ForegroundColor Gray
python setup.py build_ext --inplace
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Módulo C++ compilado correctamente" -ForegroundColor Green
} else {
    Write-Host "[WARN] Error al compilar módulo C++" -ForegroundColor Yellow
    Write-Host "  El emulador funcionará en modo Python (más lento)" -ForegroundColor Yellow
}

# 7. Verificar instalación
Write-Host ""
Write-Host "[VERIFICACIÓN] Probando importación..." -ForegroundColor Yellow
python -c "import sys; print(f'Python: {sys.version}'); from viboy_core import PyMMU; print('✓ viboy_core importado correctamente')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Todo funciona correctamente!" -ForegroundColor Green
} else {
    Write-Host "  ⚠ viboy_core no disponible (modo Python)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host "Configuración completada!" -ForegroundColor Green
Write-Host "=" * 70 -ForegroundColor Cyan
Write-Host ""
Write-Host "Próximos pasos:" -ForegroundColor Cyan
Write-Host "  1. El venv está activado. Para desactivarlo: deactivate" -ForegroundColor White
Write-Host "  2. Ejecuta el emulador: python main.py roms/tetris.gb" -ForegroundColor White
Write-Host "  3. Si hay problemas, ejecuta: python tools/diagnostico_venv.py" -ForegroundColor White
Write-Host ""

