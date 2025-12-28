# Análisis Completo de Sniper Traces - Step 0273

## Resumen Ejecutivo

**Total de trazas capturadas**: 52
- **Trazas [SNIPER]**: 50 (todas en PC:36E3)
- **Trazas [TRIGGER-D732]**: 1 (desde PC:1F80)

## Análisis Detallado

### 1. PC:36E3 - Rutina de Limpieza de VRAM

**Opcodes capturados**: `22 0B 78`

**Desensamblado**:
- `0x22`: `LD (HL+), A` - Escribe A en (HL) e incrementa HL
- `0x0B`: `DEC BC` - Decrementa BC
- `0x78`: `LD A, B` - Carga B en A

**Patrón observado**:
- **BC**: Decrementa de `2000` → `1FFF` → `1FFE` → ... (contador de iteraciones)
- **HL**: Incrementa de `8000` → `8001` → `8002` → ... (dirección de VRAM)
- **A**: Cambia de `00` (primera iteración) a `00` (resto de iteraciones)
- **SP**: Constante en `DFFB` (correcto, está en WRAM)
- **AF**: `0080` (primera) → `0000` (resto) - Flag Z se activa después de la primera iteración

**Interpretación**:
Esta es una rutina de limpieza de VRAM que:
1. Escribe `A` (que contiene `0x00`) en la dirección apuntada por `HL` (VRAM)
2. Incrementa `HL` para avanzar a la siguiente dirección
3. Decrementa `BC` como contador
4. Carga `B` en `A` para la siguiente iteración

**Banco ROM**: 1 (correcto)

**Estado de Interrupciones**:
- **IE (0xFFFF)**: `00` - **TODAS LAS INTERRUPCIONES DESHABILITADAS**
- **IF (0xFF0F)**: `01` - V-Blank pendiente (bit 0 activo)

### 2. PC:1F80 - Escritura a 0xD732

**Trazas capturadas**: 1
- **PC**: `1F80`
- **Banco ROM**: 1
- **Valor escrito**: `00`

**Análisis**:
- El código en `0x1F80` inicializa el flag `0xD732` a `0x00`
- Solo hay UNA escritura, lo que significa que el flag nunca se modifica después
- Esto confirma que ninguna ISR está modificando este flag

### 3. PC:6150 y PC:6152 - Bucle de Espera

**Trazas capturadas**: 0

**Análisis**:
- El juego NO está llegando a estas direcciones durante la ejecución capturada
- Esto sugiere que el juego se queda atascado ANTES de llegar al bucle de espera
- Posible causa: El juego está esperando algo que nunca ocurre, o hay un crash/loop en otra parte

## Hallazgos Críticos

### 1. Interrupciones Deshabilitadas (IE=00)

**Problema crítico identificado**:
- `IE = 0x00` significa que **TODAS las interrupciones están deshabilitadas**
- `IF = 0x01` significa que hay una interrupción V-Blank **PENDIENTE** pero no se puede procesar porque IE=0
- Esto explica por qué el flag `0xD732` nunca cambia: la ISR que debería modificarlo no se puede ejecutar

### 2. Bucle de Limpieza de VRAM

El código en `PC:36E3` está ejecutando un bucle que limpia VRAM escribiendo `0x00` en todas las direcciones desde `0x8000` en adelante. Este bucle:
- Usa `BC` como contador (2000 iteraciones = 8KB de VRAM)
- Usa `HL` como puntero a VRAM
- Escribe `A` (que contiene `0x00`) en cada posición

### 3. Flag 0xD732 Nunca Cambia

- Solo se escribe UNA vez desde `PC:1F80` con valor `0x00`
- Ninguna otra parte del código modifica este flag
- Esto sugiere que una ISR debería modificarlo, pero no se ejecuta porque IE=0

## Hipótesis del Problema

**Causa raíz probable**:
1. El juego deshabilita todas las interrupciones (`IE=0x00`)
2. El juego entra en un bucle de espera que lee `0xD732` repetidamente
3. El juego espera que una ISR (probablemente V-Blank) modifique `0xD732` a un valor distinto de `0x00`
4. Como IE=0, la ISR nunca se ejecuta, y el flag nunca cambia
5. El bucle de espera se vuelve infinito

**Verificación necesaria**:
- Buscar en el código del juego dónde se deshabilita IE
- Verificar si hay código que debería habilitar IE antes del bucle de espera
- Verificar si el bucle de espera en `0x6150`/`0x6152` verifica `0xD732`

## Próximos Pasos

1. **Buscar dónde se deshabilita IE**: Analizar el código antes de `PC:36E3` para encontrar dónde se escribe `0x00` en `0xFFFF`
2. **Verificar el bucle de espera**: Desensamblar el código en `0x6150`/`0x6152` para confirmar que lee `0xD732`
3. **Implementar corrección**: Si el juego debería tener IE habilitado, corregir el código que lo deshabilita incorrectamente

## Opcodes Desensamblados

### PC:36E3
```
36E3: 22        LD (HL+), A    ; Escribe A en (HL), incrementa HL
36E4: 0B        DEC BC         ; Decrementa BC (contador)
36E5: 78        LD A, B        ; Carga B en A
```

Este es un bucle típico de copia/limpieza de memoria que:
- Escribe un byte (A) en memoria (HL)
- Avanza el puntero (HL++)
- Decrementa el contador (BC--)
- Prepara el siguiente byte (A = B)

El bucle probablemente continúa con un salto condicional (JR NZ o similar) que verifica si BC llegó a 0.

