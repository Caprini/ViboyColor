---

## Roadmap Estratégico de Viboy Color (Actualizado a Step 0197)

**Filosofía:** Un emulador educativo, de alto rendimiento y desarrollado bajo la metodología "Clean Room".

### ✅ FASE 1: La Base Académica (v0.0.1) — [100% COMPLETADO]

**Objetivo:** Construir una prueba de concepto (PoC) en Python puro para aprender la arquitectura fundamental de la Game Boy desde cero.

*   **Logros:**
    *   ✅ **CPU Completa:** Implementación de todos los opcodes (incluyendo prefijo CB) en Python.
    *   ✅ **MMU Funcional:** Mapeo de memoria, MBC1 para bank switching.
    *   ✅ **PPU Funcional:** Renderizado de Background, Window y Sprites.
    *   ✅ **Timer e Interrupciones:** Sistema de timing y eventos de hardware funcionales.
    *   ✅ **Suite de Tests Robusta:** Cientos de tests unitarios validando cada componente.
    *   ✅ **Bitácora Educativa:** 90+ entradas documentando el proceso de aprendizaje.
*   **Resultado Clave:** Éxito académico total. Se demostró que el sistema funciona a nivel lógico, pero se descubrió la limitación crítica: **Python puro es demasiado lento para la sincronización ciclo a ciclo precisa que exige la jugabilidad en tiempo real.**

---

### 🚧 FASE 2: El Núcleo de Alto Rendimiento (v0.0.2) — [EN PROGRESO]

**Objetivo:** Migrar los componentes críticos del emulador a C++/Cython para eliminar los cuellos de botella de rendimiento y lograr una sincronización precisa a 60 FPS.

#### **Progreso Realizado hasta Ahora:**

*   `[✅]` **Infraestructura de Build Híbrida:** Pipeline `setup.py` + Cython + C++ completamente funcional.
*   `[✅]` **Componentes Críticos Migrados:** `CoreMMU`, `CoreRegisters`, `Timer` completo (`DIV`, `TIMA`, `TMA`, `TAC`) y `Joypad` ya se ejecutan a velocidad nativa en C++.
*   `[✅]` **CPU Casi Completa:**
    *   El bucle de emulación nativo (`run_scanline`) garantiza la sincronización ciclo a ciclo.
    *   Sistema de interrupciones (`DI`, `EI`, `HALT`) y ALU (`ADD/ADC/SUB/SBC`) completamente funcionales.
    *   La gran mayoría de opcodes de control de flujo, carga y memoria están implementados.
*   `[✅]` **PPU Sincronizada y Funcional (Parcial):**
    *   Motor de timing (`LY`), máquina de estados (Modos PPU) y sistema de interrupciones `STAT` funcionales.
    *   Renderizador de *background* y `framebuffer` implementados en C++.
    *   Tubería de datos C++ -> Python validada con el "Test del Checkerboard".
*   `[✅]` **¡HITO DE SINCRONIZACIÓN ALCANZADO!** Se han resuelto todos los `deadlocks` de hardware (`polling`, `HALT`, `Timer`, `Checksum`). El emulador se ejecuta de forma estable y el contador `LY` cicla correctamente.

#### **SITUACIÓN TÁCTICA ACTUAL (Step 0197):**

*   `[🎯]` **El Último Obstáculo:** A pesar de la sincronización perfecta, la pantalla sigue en blanco. El diagnóstico final ha revelado la causa: nuestro emulador no simula la acción principal de la **Boot ROM (BIOS)**, que es **pre-cargar los datos gráficos del logo de Nintendo en la VRAM**. El juego asume que el logo ya está ahí y, al no encontrarlo, entra en un bucle de fallo seguro.

#### **Próximos Pasos Inmediatos (Lo que haremos AHORA):**

*   `[🎯]` **Simular el "Estado del GÉNESIS":** Implementar la pre-carga de los datos de tiles y del tilemap del logo de Nintendo en el constructor de la `MMU` en C++ para replicar el estado final de la memoria que deja la Boot ROM.
*   `[ ]` **Completar la migración de la CPU C++**: Implementar los opcodes restantes (principalmente el **prefijo CB**).
*   `[ ]` **Completar la migración de la PPU C++**: Implementar el renderizado de **Sprites (OBJ)** y la **Window**, incluyendo la lógica de prioridades.
*   `[ ]` **Migrar el Cartucho (MBC1) a C++**: Mover el último componente del bucle de emulación al núcleo nativo.

---

### 🚀 FASE 3: La Experiencia Sensorial (v0.0.3) — [PENDIENTE]

**Objetivo:** Alcanzar la paridad completa con el hardware original, implementando el audio y mejorando la interfaz de usuario para una experiencia de juego completa.

#### 🔊 **Implementación del Audio (APU - Audio Processing Unit):**

*   `[ ]` **Canal 1:** Onda cuadrada con *Sweep* y *Envelope*.
*   `[ ]` **Canal 2:** Onda cuadrada con *Envelope*.
*   `[ ]` **Canal 3:** Onda de tabla de ondas (Wavetable) leída desde RAM.
*   `[ ]` **Canal 4:** Generador de ruido blanco.
*   `[ ]` **Mezclador y Salida:** Mezclar los 4 canales y enviarlos a la tarjeta de sonido a 44.1kHz usando un **Ring Buffer** para evitar chasquidos y desincronización.

#### 🎮 **Interfaz Gráfica (GUI) y Controles:**

*   `[ ]` **Menú Principal:** Implementar un menú nativo (`tkinter` o `PyQt`) para funciones como "Abrir ROM...", "Guardar/Cargar Estado", "Configuración".
*   `[ ]` **Mapeo de Controles:** Permitir al usuario configurar las teclas y/o un gamepad.
*   `[ ]` **Manejo de Joypad Nativo:** Migrar la lectura de input al núcleo C++ para minimizar la latencia.
*   `[ ]` **Mejoras Visuales:** Opciones de escalado de ventana, capturas de pantalla y, potencialmente, filtros de shaders simples (ej. "LCD Dot Matrix").

---

### 🔮 FASE 4: El Kit de Herramientas del Desarrollador (v0.0.4) — [VISIÓN A FUTURO]

**Objetivo:** Extender el emulador más allá del simple juego, convirtiéndolo en una potente herramienta para el desarrollo, la depuración y la experimentación.

#### 🔬 **Herramientas de Depuración Avanzadas (API de Debug):**

*   `[ ]` **Debugger Visual:** Crear una interfaz (usando `Dear ImGui` o similar) que permita inspeccionar en tiempo real: VRAM, OAM, paletas, etc.
*   `[ ]` **Desensamblador en Tiempo Real:** Mostrar las instrucciones que la CPU está ejecutando.
*   `[ ]` **Puntos de Ruptura (Breakpoints):** Permitir pausar la emulación en direcciones de memoria específicas.

#### 🔌 **APIs y Extensibilidad:**

*   `[ ]` **Implementación de un GDB Stub:** Permitir conectar herramientas de depuración externas como GDB.
*   `[ ]` **API de Scripting (Lua o Python):** Exponer funciones del emulador para *Tool-Assisted Speedruns* (TAS), bots, o entrenamiento de IAs.
*   `[ ]` **Netplay (Juego en Red):** Como objetivo muy a largo plazo, explorar la sincronización de dos instancias a través de internet.