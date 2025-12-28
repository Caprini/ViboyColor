# Solución de Problemas: Error "Connection failed" en Cursor

## 🔍 Diagnóstico del Problema

El error `Connection failed: Request ID: ...` que aparece al ejecutar comandos en la terminal de Cursor puede tener varias causas. Este documento te ayudará a diagnosticar y resolver el problema.

## ✅ Soluciones Rápidas (Prueba en este orden)

### 1. Reiniciar Cursor
- Cierra completamente Cursor (no solo la ventana)
- Vuelve a abrirlo
- Intenta ejecutar el comando nuevamente

### 2. Verificar la Terminal Integrada
- Abre una nueva terminal: `Ctrl + Shift + \`` (backtick)
- O usa: `Terminal > New Terminal`
- Prueba ejecutar un comando simple: `python --version`

### 3. Cambiar el Shell de la Terminal
Si estás usando PowerShell y tienes problemas:

1. Abre la configuración de Cursor: `Ctrl + ,`
2. Busca: `terminal.integrated.defaultProfile.windows`
3. Cambia a:
   - `Command Prompt` (cmd)
   - O `Git Bash` si lo tienes instalado

Alternativamente, en `settings.json`:
```json
{
  "terminal.integrated.defaultProfile.windows": "Command Prompt"
}
```

### 4. Verificar Entorno Virtual de Python
Si estás usando un entorno virtual (venv), puede estar causando conflictos:

**Opción A: Desactivar el venv temporalmente**
```powershell
# Si tienes un venv activo, desactívalo
deactivate

# Prueba ejecutar un comando simple
python --version
```

**Opción B: Verificar que el venv esté correctamente configurado**
```powershell
# Verifica que Python esté en el PATH
where.exe python

# Verifica la versión
python --version

# Si no funciona, reinstala el venv
python -m venv venv --clear
.\venv\Scripts\activate
```

### 5. Verificar Políticas de Ejecución de PowerShell
PowerShell puede tener restricciones que bloquean la ejecución:

```powershell
# Verifica la política actual
Get-ExecutionPolicy

# Si está en "Restricted", cámbiala temporalmente (solo para esta sesión)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# O para el usuario actual (más permanente)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 6. Limpiar Caché de Cursor
1. Cierra Cursor completamente
2. Elimina la carpeta de caché (puede estar en):
   - `%APPDATA%\Cursor\Cache`
   - `%APPDATA%\Cursor\CachedData`
3. Reinicia Cursor

### 7. Verificar Conectividad de Red
El error puede estar relacionado con servicios de Cursor que requieren conexión:

```powershell
# Verifica conectividad básica
Test-NetConnection -ComputerName api.cursor.sh -Port 443

# O prueba con ping
ping api.cursor.sh
```

### 8. Desactivar Extensiones Problemáticas
Algunas extensiones pueden interferir con la terminal:

1. Ve a `View > Extensions`
2. Desactiva temporalmente extensiones relacionadas con:
   - Terminal
   - Python
   - Git
3. Reinicia Cursor y prueba nuevamente

### 9. Usar Terminal Externa
Como solución temporal, puedes usar una terminal externa:

1. Abre PowerShell o CMD fuera de Cursor
2. Navega al directorio del proyecto:
   ```powershell
   cd C:\Users\fabin\Desktop\ViboyColor
   ```
3. Ejecuta tus comandos desde ahí

### 10. Verificar Configuración de Proxy/Firewall
Si estás detrás de un proxy o firewall corporativo:

1. Verifica la configuración de proxy en Cursor
2. Revisa si el firewall está bloqueando conexiones
3. Considera usar una VPN si es necesario

## 🔧 Soluciones Avanzadas

### Verificar Logs de Cursor
Los logs pueden darte más información sobre el error:

1. Abre la paleta de comandos: `Ctrl + Shift + P`
2. Ejecuta: `Developer: Show Logs`
3. Busca errores relacionados con "connection" o "terminal"

### Reinstalar Cursor
Si nada funciona, considera reinstalar Cursor:

1. Desinstala Cursor
2. Elimina las carpetas de configuración:
   - `%APPDATA%\Cursor`
   - `%LOCALAPPDATA%\Cursor`
3. Reinstala desde [cursor.sh](https://cursor.sh)

## 📝 Comandos de Diagnóstico

Ejecuta estos comandos para obtener información del sistema:

```powershell
# Información del sistema
$PSVersionTable
python --version
pip --version

# Verificar PATH
$env:PATH -split ';'

# Verificar procesos de Python
Get-Process python -ErrorAction SilentlyContinue

# Verificar permisos del directorio
Get-Acl . | Format-List
```

## 🎯 Solución Específica para ViboyColor

### Problema: Emulador no funciona dentro de venv

**Síntoma:** El emulador funciona fuera del venv pero no dentro de él.

**Causa:** El módulo C++ compilado (`viboy_core.pyd`) está compilado para una versión específica de Python y puede no ser compatible con el Python del venv.

### Solución Rápida

1. **Ejecuta el diagnóstico:**
   ```powershell
   python tools/diagnostico_venv.py
   ```
   Esto te dirá exactamente qué está mal.

2. **Recompila el módulo C++ dentro del venv:**
   ```powershell
   # Activa el venv primero
   .\venv\Scripts\activate
   
   # Recompila el módulo
   python setup.py build_ext --inplace
   ```

3. **O usa el script de configuración automática:**
   ```powershell
   .\tools\setup_venv.ps1
   ```
   Este script configura todo automáticamente.

### Solución Manual Paso a Paso

1. **Asegúrate de estar en el directorio correcto:**
   ```powershell
   cd C:\Users\fabin\Desktop\ViboyColor
   ```

2. **Activa el venv:**
   ```powershell
   .\venv\Scripts\activate
   ```

3. **Verifica la versión de Python:**
   ```powershell
   python --version
   ```
   Debe coincidir con la versión usada para compilar el .pyd original.

4. **Instala/actualiza dependencias:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Recompila el módulo C++:**
   ```powershell
   python setup.py build_ext --inplace
   ```

6. **Verifica que funcione:**
   ```powershell
   python -c "from viboy_core import PyMMU; print('OK')"
   ```

### Si el Problema Persiste

- **Opción 1:** Usa el emulador sin venv (funciona fuera del venv)
- **Opción 2:** Recrea el venv desde cero:
  ```powershell
  Remove-Item -Recurse -Force venv
  python -m venv venv
  .\venv\Scripts\activate
  pip install -r requirements.txt
  python setup.py build_ext --inplace
  ```

## 💡 Prevención

Para evitar este problema en el futuro:

1. **Mantén Cursor actualizado** - Las versiones más recientes suelen tener menos bugs
2. **Usa terminal externa para comandos críticos** - Para compilaciones importantes, usa PowerShell/CMD externo
3. **Configura un shell estable** - Usa Command Prompt si PowerShell da problemas
4. **Evita múltiples instancias de venv** - Asegúrate de tener solo un venv activo a la vez

## 📞 Si el Problema Persiste

Si después de probar todas estas soluciones el problema continúa:

1. **Reporta el error a Cursor:**
   - Abre la paleta: `Ctrl + Shift + P`
   - Ejecuta: `Help: Report Issue`
   - Incluye el Request ID del error
   - **Request ID conocido:** `031c996e-ca1d-4a99-b5fa-961cae8e4b54`
   - Ver archivo `REPORTE_ERROR_CURSOR.md` para plantilla completa de reporte

2. **Comunidad:**
   - Busca en [GitHub Issues de Cursor](https://github.com/getcursor/cursor/issues)
   - Busca problemas similares con el mismo Request ID
   - Foro de Cursor: https://forum.cursor.com/

3. **Workaround temporal:**
   - Usa una terminal externa para todos los comandos
   - O usa el modo "Run in Terminal" de Cursor en lugar de ejecutar comandos directamente

## 📋 Request IDs Conocidos

Si recibes un Request ID, documenta el error:

**Request IDs Reportados:**
1. `031c996e-ca1d-4a99-b5fa-961cae8e4b54`  
   - **Problema:** Connection failed al ejecutar pytest en venv  
   - **Estado:** Reportado

2. `cb24c924-61d9-47fa-89c6-40c907a40665`  
   - **Problema:** Connection failed durante ejecución de comandos Python  
   - **Estado:** Reportado  
   - **Contexto:** Error apareció al ejecutar `python main.py roms/tetris.gb`

**Cómo obtener más información:**
- Cuando aparece el error, haz clic en **"Copy Request Details"** en la notificación
- Esto copiará información detallada del error
- Incluye esta información al reportar el problema

**Ver:** `REPORTE_ERROR_CURSOR.md` para detalles completos y plantilla de reporte

## 🧪 Solución para Bloqueos de pytest en Cursor

### Problema: pytest se bloquea al ejecutar tests

**Síntoma:** Cursor se bloquea o se queda colgado al ejecutar `pytest`.

**Causas comunes:**
1. Tests que abren ventanas gráficas (pygame) y esperan eventos
2. Tests que se quedan en bucles infinitos
3. Tests que esperan input del usuario
4. Falta de timeouts en tests

### Solución Implementada

Se ha creado una configuración completa de pytest que previene bloqueos:

1. **Archivo `pytest.ini`** - Configuración con timeouts y opciones optimizadas
2. **Archivo `tests/conftest.py`** - Configuración global que:
   - Configura pygame en modo headless (sin ventanas)
   - Establece variables de entorno para modo test
   - Previene inicialización de displays gráficos

3. **pytest-timeout** - Plugin instalado que mata tests que tardan más de 10 segundos

### Uso

```powershell
# Activar venv
.\venv\Scripts\activate.ps1

# Ejecutar todos los tests (con timeout automático)
pytest tests/ -v

# Ejecutar un test específico
pytest tests/test_core_registers.py -v

# Ejecutar con timeout personalizado
pytest tests/ -v --timeout=5

# Ejecutar sin timeout (no recomendado)
pytest tests/ -v --timeout=0
```

### Verificación

Si pytest se bloquea, verifica:

1. **Que pytest-timeout esté instalado:**
   ```powershell
   pip list | Select-String "timeout"
   ```

2. **Que el conftest.py esté en la carpeta tests:**
   ```powershell
   Test-Path tests/conftest.py
   ```

3. **Que las variables de entorno estén configuradas:**
   ```powershell
   $env:SDL_VIDEODRIVER = 'dummy'
   pytest tests/ -v
   ```

### Si el Problema Persiste

1. **Ejecuta el diagnóstico completo:**
   ```powershell
   python tools/diagnostico_pytest.py
   ```
   Esto generará un reporte en `pytest_diagnostico_report.txt`

2. **Ejecuta pytest con más verbosidad:**
   ```powershell
   pytest tests/ -vv --tb=long
   ```

3. **Ejecuta un test específico para aislar el problema:**
   ```powershell
   pytest tests/test_core_registers.py -v
   ```

4. **Revisa los logs de Cursor:**
   - Abre la paleta: `Ctrl + Shift + P`
   - Ejecuta: `Developer: Show Logs`
   - Busca errores relacionados con pytest o pygame

5. **Usa terminal externa como workaround:**
   ```powershell
   # Abre PowerShell fuera de Cursor
   cd C:\Users\fabin\Desktop\ViboyColor
   .\venv\Scripts\activate.ps1
   pytest tests/ -v
   ```

6. **Comparte información para diagnóstico:**
   - Ver archivo `COMO_COMPARTIR_INFO_PYTEST.md` para instrucciones detalladas
   - Ejecuta el diagnóstico y comparte el reporte generado

---

**Última actualización:** 2024-12-20
**Versión de Cursor:** Verifica en `Help > About`

