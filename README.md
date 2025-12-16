# Viboy Color

Un emulador de Game Boy Color escrito en Python.

## Descripción

Viboy Color es un emulador completo del sistema Game Boy Color desarrollado desde cero en Python. El proyecto tiene como objetivo implementar con precisión la arquitectura del hardware original, incluyendo:

- Procesador Z80 modificado (CPU)
- Sistema de gestión de memoria (MMU)
- Unidad de procesamiento gráfico (GPU)
- Emulación de audio
- Control de entrada/salida

## Instalación

### Requisitos Previos

- Python 3.8 o superior
- pip (gestor de paquetes de Python)

### Pasos de Instalación

1. Clona el repositorio:
```bash
git clone <url-del-repositorio>
cd ViboyColor
```

2. Crea un entorno virtual (recomendado):
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instala las dependencias:
```bash
pip install -r requirements.txt
```

4. Ejecuta el emulador:
```bash
python main.py
```

## Estructura del Proyecto

```
ViboyColor/
├── src/
│   ├── cpu/          # Lógica del procesador
│   ├── memory/       # Gestión de memoria (MMU)
│   └── gpu/          # Renderizado gráfico
├── tests/            # Tests unitarios
├── docs/             # Documentación adicional
├── main.py           # Punto de entrada principal
└── requirements.txt  # Dependencias del proyecto
```

## Estado del Proyecto

Este proyecto está en fase inicial de desarrollo.

