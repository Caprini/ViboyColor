# Scripts de Prueba Manual

Esta carpeta contiene scripts de prueba y diagnóstico desarrollados durante el desarrollo del emulador. Estos scripts son útiles para:

- Probar ROMs específicas (ej. `mario.gbc`)
- Monitorear cambios en registros I/O
- Verificar el renderizado visual
- Diagnosticar problemas de ejecución

## Scripts Disponibles

- `test_mario.py`: Ejecuta mario.gbc y captura errores y logs relevantes
- `test_mario_monitor.py`: Monitorea cambios en LCDC, BGP, SCX, SCY durante la ejecución
- `test_mario_ui.py`: Ejecuta el emulador con UI para pruebas visuales
- `test_mario_visual.py`: Verificación visual del renderizado con información detallada
- `verificar_renderizado_mario.py`: Script completo de verificación de renderizado

## Uso

Todos los scripts esperan encontrar las ROMs en la carpeta `roms/`. Ejecuta desde la raíz del proyecto:

```bash
python tests/manual_scripts/test_mario.py
```

**Nota**: Estos scripts son herramientas de desarrollo y no forman parte de la distribución final del emulador.

