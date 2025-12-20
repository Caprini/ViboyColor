# Cómo Compartir Información sobre Bloqueos de pytest

## 📋 Información que Necesito

Para diagnosticar el problema de bloqueo de pytest en Cursor, necesito:

### 1. Ejecutar el Diagnóstico

```powershell
# Activar venv
.\venv\Scripts\activate.ps1

# Ejecutar diagnóstico
python tools/diagnostico_pytest.py
```

Esto generará un archivo `pytest_diagnostico_report.txt` con información útil.

### 2. Capturar la Salida cuando se Bloquea

Cuando Cursor se bloquee al ejecutar pytest:

1. **Espera 30 segundos** (para confirmar que está bloqueado)
2. **Presiona Ctrl+C** para cancelar
3. **Copia toda la salida** de la terminal de Cursor
4. **Guarda la salida** en un archivo de texto

### 3. Información del Sistema

Ejecuta estos comandos y comparte la salida:

```powershell
# Versión de Python
python --version

# Versión de pytest
pytest --version

# Plugins instalados
pytest --collect-only -q 2>&1 | Select-String "plugin"

# Variables de entorno relevantes
$env:SDL_VIDEODRIVER
$env:PYGAME_HIDE_SUPPORT_PROMPT
```

### 4. Logs de Cursor

1. Abre la paleta de comandos: `Ctrl + Shift + P`
2. Ejecuta: `Developer: Show Logs`
3. Busca errores relacionados con:
   - pytest
   - python
   - terminal
   - timeout
4. Copia los errores relevantes

### 5. Comando Exacto que Bloquea

Indica:
- ¿Qué comando ejecutaste exactamente? (ej: `pytest tests/ -v`)
- ¿En qué momento se bloquea? (al iniciar, durante recolección, durante ejecución)
- ¿Aparece algún mensaje antes de bloquearse?

## 🔧 Soluciones Temporales

Mientras diagnosticamos el problema, puedes usar estas alternativas:

### Opción 1: Terminal Externa

Ejecuta pytest desde PowerShell o CMD fuera de Cursor:

```powershell
# Abre PowerShell fuera de Cursor
cd C:\Users\fabin\Desktop\ViboyColor
.\venv\Scripts\activate.ps1
pytest tests/ -v
```

### Opción 2: Ejecutar Tests Específicos

En lugar de ejecutar todos los tests, ejecuta solo algunos:

```powershell
# Solo tests de registros
pytest tests/test_core_registers.py -v

# Solo tests de MMU
pytest tests/test_core_mmu.py -v

# Con timeout más corto
pytest tests/test_core_registers.py -v --timeout=5
```

### Opción 3: Modo de Recolección Solo

Para ver qué tests se encuentran sin ejecutarlos:

```powershell
pytest --collect-only -q
```

### Opción 4: Desactivar Plugins Problemáticos

Si el problema es con algún plugin:

```powershell
# Sin coverage
pytest tests/ -v --no-cov

# Sin timeout (no recomendado, pero para probar)
pytest tests/ -v --timeout=0
```

## 📤 Cómo Compartir la Información

Puedes compartir la información de estas formas:

### Opción A: Archivo de Texto

1. Crea un archivo `pytest_bloqueo_info.txt`
2. Copia toda la información relevante
3. Compártelo en el chat

### Opción B: Copiar y Pegar Directamente

Copia y pega directamente en el chat:
- Salida del diagnóstico
- Salida de pytest cuando se bloquea
- Logs de Cursor
- Información del sistema

### Opción C: Captura de Pantalla

Si es más fácil, toma capturas de pantalla de:
- La terminal cuando se bloquea
- Los logs de Cursor
- La configuración de pytest

## 🎯 Información Más Útil

La información más útil para diagnosticar es:

1. **El comando exacto** que causa el bloqueo
2. **El momento exacto** en que se bloquea (recolección vs ejecución)
3. **La salida completa** de la terminal antes del bloqueo
4. **Los logs de Cursor** relacionados con el error
5. **Si funciona en terminal externa** o solo falla en Cursor

## 🔍 Diagnóstico Avanzado

Si quieres hacer un diagnóstico más profundo:

```powershell
# Ejecutar con máxima verbosidad
pytest tests/test_core_registers.py -vv --tb=long --capture=no

# Ejecutar con profiling
pytest tests/test_core_registers.py -v --durations=10

# Ejecutar con debug
pytest tests/test_core_registers.py -v --pdb
```

---

**Nota:** Comparte la información que puedas y trabajaremos juntos para resolver el problema.

