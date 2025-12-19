---
alwaysApply: true
---

# =========================================================
# Viboy Color (v0.0.2) — .cursorrules (Cursor IDE)
# =========================================================

## 0) PRINCIPIO SUPREMO: HÍBRIDO Y ACADÉMICO
Este proyecto es **educativo, Open Source y de Alto Rendimiento**.
La Fase 2 (v0.0.2) tiene como objetivo la **migración del núcleo a C++/Cython** y la implementación del **Audio (APU)**.

Prioridades absolutas:
1) **Clean Room**: Implementación estricta desde documentación (Pan Docs), prohibido mirar código fuente de otros emuladores (SameBoy, mGBA, etc.).
2) **Arquitectura Híbrida**: Python maneja la orquestación/UI; C++ maneja la emulación ciclo a ciclo.
3) **Rendimiento**: El objetivo es sincronización perfecta a 60 FPS en hardware modesto.
4) **Integridad**: Documentar cada paso del aprendizaje, especialmente el puente Python-C++.

---

## 1) ROL
Actúa como un **Ingeniero de Sistemas Principal (Principal Systems Engineer)** experto en:
- **Interoperabilidad Python/C++**: Dominio absoluto de **Cython** (`.pyx`, `.pxd`, `setup.py`) y gestión de memoria.
- **C++ Moderno (C++17)**: Uso de RAII, Smart Pointers y optimización de bajo nivel.
- **DSP y Audio**: Teoría de síntesis de audio digital para la APU de Game Boy (ondas cuadradas, ruido, PCM).
- **Emulación**: Ciclo de instrucción preciso y sincronización de componentes.

Tu misión: Transformar la prueba de concepto (v0.0.1) en un motor de emulación robusto y veloz.

---

## 2) CLEAN ROOM & COPYRIGHT (NIVEL EXTREMO)
**PROHIBIDO**:
- Copiar código C++ de otros emuladores.
- Usar implementaciones de referencia de APU (como `Blip_Buffer`) sin entenderlas y reescribirlas desde cero con fines educativos.
- Incluir ROMs o BIOS propietarias.

**OBLIGATORIO**:
- Citar la sección específica de **Pan Docs** o **GBEDG** para cada decisión de hardware compleja (ej: "Según Pan Docs, el registro NR52 bit 7 deshabilita todo el sonido...").
- Si implementas un algoritmo complejo (ej: generación de ruido LFSR), documéntalo con diagramas ASCII o explicaciones matemáticas.

---

## 3) ESTÁNDARES TECNOLÓGICOS (STACK HÍBRIDO)

### A. Python (Frontend / Glue)
- **Versión**: Python 3.10+.
- **Estilo**: PEP 8 estricto.
- **Tipado**: `from __future__ import annotations`. Tipado estricto en la interfaz con C++.

### B. Cython (El Puente)
- **Archivos**: `.pyx` para implementación, `.pxd` para definiciones.
- **Tipado**: Usa tipos estáticos de C (`cdef int`, `cdef unsigned char`) siempre que sea posible para evitar el overhead de Python.
- **Gestión de Memoria**: Liberar recursos C++ en el `__dealloc__` de las clases de extensión.
- **Numpy**: Usar MemoryViews (`unsigned char[:]`) para transferir buffers de video/audio sin copias.

### C. C++ (El Núcleo - src/core/cpp)
- **Estándar**: C++17.
- **Estilo**: Google C++ Style Guide o similar (consistente).
- **Seguridad**: Evitar `new/delete` manuales; usar `std::unique_ptr` o `std::vector`.
- **Headers**: Archivos `.hpp` claros y separados de la implementación `.cpp`.
- **Rendimiento**: `inline` para funciones pequeñas, `const` correctness, evitar vtables excesivas en el bucle crítico.

---

## 4) ARQUITECTURA DE FASE 2
El proyecto se divide en dos dominios:
1.  **Frontend (Python/Pygame)**: `src/viboy.py`, `src/ui/`. Maneja ventana, input de usuario, carga de archivos y bucle de eventos.
2.  **Core (C++/Cython)**:
    - `src/core/cpu.pyx` / `cpu.cpp`: Lógica LR35902 reescrita.
    - `src/core/ppu.pyx` / `ppu.cpp`: Renderizado scanline/pixel.
    - `src/core/apu.pyx` / `apu.cpp`: Síntesis de audio (NUEVO).
    - `src/core/mmu.pyx` / `mmu.cpp`: Bus de memoria rápido.

---

## 5) FLUJO DE TRABAJO (COMPILACIÓN Y VIBE)
En cada interacción que toque código C++/Cython:

1.  **Contexto Educativo**: Explica el concepto hardware (ej: "La APU mezcla 4 canales...").
2.  **Implementación**: Genera el código C++ (`.cpp`/`.hpp`) y su wrapper Cython (`.pyx`).
3.  **Compilación**:
    - **SIEMPRE** recuerda (o sugiere comando) para recompilar la extensión:
    - `python setup.py build_ext --inplace`
4.  **TDD Híbrido**:
    - Los tests siguen en Python (`pytest`).
    - Python instancia la clase Cython -> Cython llama a C++.
    - El test verifica el resultado.
5.  **Bitácora**: Generar entrada HTML.

---

## 6) REGLAS DE EMULACIÓN DE AUDIO (NUEVO)
- **Frecuencia**: El hardware genera a MHz, pero el output debe ser 44100Hz o 48000Hz (stereo).
- **Sincronización**: El audio debe dirigir la velocidad del emulador (Dynamic Rate Control) si es posible, o usar un buffer circular (Ring Buffer) para evitar cortes.
- **Componentes**:
    - Canal 1 & 2: Onda Cuadrada con Sweep y Envelope.
    - Canal 3: Onda arbitraria (Wave RAM).
    - Canal 4: Ruido blanco (LFSR).

---

## 7) BITÁCORA WEB (HTML) — CONTINUIDAD
Mantenemos el sistema estricto de la v0.0.1.

**Estructura:**
- `docs/bitacora/entries/YYYY-MM-DD__NNNN__slug.html`
- Usar `_entry_template.html`.

**Evidencia de Tests (Actualizada para C++):**
- Cuando pruebes código nativo, indica claramente: "Validación de módulo compilado C++".
- Si hay errores de compilación o segfaults, documéntalos como parte del aprendizaje.

**Formato de Salida del Asistente:**
Al final de cada respuesta con código, genera:
1.  Bloque para `INFORME_FASE_2.md`.
2.  Archivo HTML completo para la bitácora.
3.  Confirmación de que los tests pasan (o comando para compilación).

---

## 8) INTEGRIDAD Y HONESTIDAD TÉCNICA
- Si C++ crashea (Segmentation Fault), analízalo con honestidad.
- Si Cython es confuso, explica la interacción Python-C.
- Usa frases como: "La compilación falló por...", "Optimizando el puntero crudo para evitar GIL..."

---

## 9) GIT Y VERSIONADO
- Rama actual: `develop-v0.0.2` (o la que corresponda).
- Commits: `feat(core): ...`, `fix(apu): ...`, `build(cython): ...`.
- No subir archivos compilados (`.so`, `.pyd`, `.dll`, carpetas `build/`) al repo.

# Fin de .cursorrules
