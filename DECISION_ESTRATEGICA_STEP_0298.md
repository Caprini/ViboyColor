# Decisión Estratégica - Step 0298

## Fecha
2025-12-25

## Contexto
Después de ejecutar el emulador con Pokémon Red durante 60 segundos con simulación de entrada del usuario, se analizaron los logs para determinar si el juego carga tiles en VRAM.

## Resultados del Análisis

### Ejecución con Simulación de Entrada (60 segundos)
- **Total de líneas en log**: 1,882,587
- **Líneas [SIM-INPUT]**: 0 (la simulación no generó logs visibles)
- **Líneas [VRAM-ACCESS-GLOBAL.*DATA]**: 0 (ningún acceso con datos != 0x00)
- **Líneas [ROM-TO-VRAM]**: 0 (ninguna copia desde ROM)
- **Líneas [LOAD-SEQUENCE]**: 1 (solo la rutina de limpieza en PC:0x36E3)
- **Líneas [TIMELINE-VRAM]**: 200 (todos accesos de limpieza)
- **Líneas [STATE-CHANGE]**: 79 (saltos grandes de PC detectados)
- **Líneas [SCREEN-TRANSITION]**: 1 (una transición de pantalla)

### Hallazgos Clave
1. **Todos los accesos VRAM son de limpieza**: Todos los accesos detectados escriben 0x00 desde PC:0x36E3
2. **No hay carga de datos reales**: En 60 segundos, no se detectó ningún acceso VRAM con datos != 0x00
3. **El juego ejecuta código normalmente**: Se detectaron 79 cambios de estado (saltos grandes de PC) y 1 transición de pantalla
4. **La simulación de entrada no generó logs**: Esto sugiere que el código de simulación puede no estar ejecutándose o no está generando logs visibles

## Evaluación de Escenarios

### Escenario A: Se Detectan Accesos con Datos
**Estado**: ❌ **NO OCURRIÓ**
- No se detectaron accesos VRAM con datos reales en 60 segundos
- Todos los accesos son de limpieza (0x00)

### Escenario B: NO se Detectan Accesos con Datos (Incluso con Interacción y 60+ segundos)
**Estado**: ✅ **CONFIRMADO**
- No se detectaron accesos con datos incluso después de 60 segundos
- La simulación de entrada no generó logs visibles, pero el juego ejecutó código normalmente

## Opciones Estratégicas

### Opción 1: Investigar Desensamblado del Juego
**Descripción**: Analizar el código desensamblado de Pokémon Red para identificar manualmente las rutinas de carga de tiles.

**Pros**:
- Identificaría la causa raíz del problema
- Permitiría entender cómo el juego realmente carga tiles
- Podría revelar bugs sutiles en la emulación

**Contras**:
- Requiere tiempo significativo de investigación
- Puede requerir herramientas especializadas de desensamblado
- No garantiza una solución rápida

**Recomendación**: Implementar en paralelo con Opción 2

### Opción 2: Implementar Carga Manual de Tiles (Hack Temporal)
**Descripción**: Crear una función que cargue tiles básicos en VRAM manualmente para permitir probar el renderizado sin depender del código del juego.

**Pros**:
- Permite avanzar con el desarrollo del emulador
- Facilita probar el renderizado y otras funcionalidades
- Ya existe la función `load_test_tiles()` en MMU.cpp
- Se puede activar con `--load-test-tiles`

**Contras**:
- Es un hack temporal, no una solución real
- No resuelve el problema fundamental
- Puede enmascarar bugs reales

**Recomendación**: ✅ **IMPLEMENTAR INMEDIATAMENTE** como hack temporal

### Opción 3: Aceptar que el Juego No Carga Tiles en Esta Fase
**Descripción**: Aceptar que Pokémon Red no carga tiles en la fase inicial (pantalla de título/menú) y continuar con otras funcionalidades del emulador.

**Pros**:
- Permite avanzar con otras funcionalidades (audio, otros juegos, etc.)
- Evita quedarse bloqueado en este problema específico

**Contras**:
- No resuelve el problema
- Limita la capacidad de probar el renderizado
- Puede indicar un bug más fundamental en la emulación

**Recomendación**: No recomendado como única opción, pero válido como estrategia a largo plazo

### Opción 4: Investigar Bug Sutil en la Emulación
**Descripción**: Investigar si hay un bug sutil en la emulación que impide que el juego llegue a la rutina de carga de tiles.

**Pros**:
- Podría revelar problemas fundamentales en la emulación
- Resolvería el problema de raíz

**Contras**:
- Requiere investigación profunda
- Puede ser difícil de identificar
- No garantiza una solución rápida

**Recomendación**: Implementar en paralelo con Opción 2

## Decisión Estratégica

### Decisión Principal: **Opción 2 - Implementar Carga Manual de Tiles (Hack Temporal)**

**Justificación**:
1. Ya existe la función `load_test_tiles()` en MMU.cpp, solo necesita ser verificada y documentada
2. Permite avanzar con el desarrollo del emulador sin quedarse bloqueado
3. Facilita probar el renderizado y otras funcionalidades
4. Se puede activar/desactivar fácilmente con `--load-test-tiles`
5. No interfiere con la investigación del problema real (Opción 1 y 4)

### Estrategia Paralela
1. **Corto plazo (Inmediato)**: Implementar y verificar la carga manual de tiles
2. **Medio plazo (En paralelo)**: Investigar desensamblado del juego (Opción 1)
3. **Medio plazo (En paralelo)**: Investigar posibles bugs sutiles en la emulación (Opción 4)
4. **Largo plazo**: Una vez identificada la causa, eliminar el hack temporal y corregir el problema real

## Próximos Pasos

1. ✅ Verificar que `load_test_tiles()` funciona correctamente
2. ✅ Documentar el uso de `--load-test-tiles` en la documentación
3. ✅ Crear entrada de bitácora documentando esta decisión
4. 🔄 Continuar con otras funcionalidades del emulador mientras se investiga el problema en paralelo

## Notas Adicionales

- La simulación de entrada no generó logs visibles, lo que sugiere que puede haber un problema con el código de simulación o que el emulador se ejecuta en modo headless sin renderer
- El juego ejecuta código normalmente (79 cambios de estado, 1 transición de pantalla), lo que sugiere que la emulación básica funciona
- El problema parece ser específico de la carga de tiles, no un problema general de emulación

