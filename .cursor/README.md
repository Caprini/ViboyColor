# Directorio de Configuración de Cursor

Este directorio contiene la configuración y documentación para Cursor IDE específica del proyecto Viboy Color.

## Estructura

```
.cursor/
├── README.md              # Este archivo
├── docs.md                # Documentación de tecnologías (formato Markdown)
├── docs.json              # Documentación de tecnologías (formato JSON)
├── rules/                 # Reglas del proyecto
│   ├── reglas-proyecto.mdc
│   ├── reglas-asistente.mdc
│   └── modo-planificador.mdc
├── plans/                 # Planes de desarrollo guardados
└── ViboyColor.code-workspace  # Configuración del workspace
```

## Archivos de Documentación

### `docs.md` y `docs.json`

Contienen enlaces a la documentación oficial de todas las tecnologías utilizadas en el proyecto:

- **Lenguajes**: Python 3.11+, C++17
- **Interoperabilidad**: Cython 3.0+
- **Bibliotecas**: Pygame CE, pytest, NumPy
- **Compiladores**: GCC, Clang
- **Sistema Operativo**: Ubuntu Linux
- **Hardware**: Pan Docs, GBEDG
- **Futuro**: tkinter/PyQt, Dear ImGui, GDB, Lua, OpenGL

Estos archivos están diseñados para ser indexados automáticamente por Cursor IDE, permitiendo que el asistente acceda rápidamente a la documentación relevante durante el desarrollo.

## Uso

Cursor IDE indexará automáticamente estos archivos cuando trabajes en el proyecto. Los enlaces están organizados por categorías para facilitar la búsqueda y referencia.

**Última actualización**: 2025-12-29

