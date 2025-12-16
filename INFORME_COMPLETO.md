# Bitácora del Proyecto Viboy Color

## 2024-12-19 - Inicio del Proyecto

### Configuración Inicial

Se ha configurado la estructura inicial del proyecto "Viboy Color", un emulador de Game Boy Color escrito en Python.

#### Tareas Completadas:

1. **Inicialización de Git**: Se ha inicializado un repositorio Git en la carpeta del proyecto para control de versiones.

2. **Archivo .gitignore**: Se ha creado un archivo `.gitignore` robusto que incluye:
   - Exclusiones estándar de Python (__pycache__, *.pyc, etc.)
   - Entornos virtuales (.venv, venv/, etc.)
   - Archivos del sistema operativo (.DS_Store para macOS, Thumbs.db para Windows)
   - Archivos de IDEs (.idea/, .vscode/)
   - Archivos temporales y logs
   - ROMs de Game Boy (*.gb, *.gbc) para evitar incluir contenido con derechos de autor

3. **Estructura de Directorios**: Se ha creado la siguiente estructura:
   - `src/`: Carpeta principal del código fuente
   - `src/cpu/`: Para la lógica del procesador (CPU Z80 modificado)
   - `src/memory/`: Para la gestión de memoria (MMU - Memory Management Unit)
   - `src/gpu/`: Para el renderizado gráfico (GPU)
   - `tests/`: Para los tests unitarios
   - `docs/`: Para documentación adicional

4. **Gestión de Dependencias**: Se ha creado el archivo `requirements.txt` con las siguientes dependencias:
   - `pygame-ce>=2.3.0`: Biblioteca para el renderizado gráfico y manejo de entrada
   - `pytest>=7.4.0`: Framework para tests unitarios
   - `pytest-cov>=4.1.0`: Plugin para cobertura de código en tests

5. **Documentación**:
   - `README.md`: Contiene título del proyecto, descripción, instrucciones de instalación y estructura del proyecto
   - `INFORME_COMPLETO.md`: Este archivo, que servirá como bitácora del proyecto

6. **Script de Entrada**: Se ha creado `main.py` en la raíz del proyecto con un mensaje de inicio básico para verificación.

### Próximos Pasos

- Implementación de la CPU (procesador Z80 modificado)
- Desarrollo del sistema de memoria (MMU)
- Implementación de la GPU para renderizado
- Sistema de carga de ROMs
- Tests unitarios básicos

---

