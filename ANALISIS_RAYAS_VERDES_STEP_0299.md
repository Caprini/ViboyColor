# Análisis de Rayas Verdes - Step 0299

## Objetivo

Analizar los logs generados por los 4 monitores de diagnóstico visual implementados para identificar la causa raíz del patrón de rayas verticales verdes que aparecen en el emulador.

## Monitores Implementados

1. **[FRAMEBUFFER-DUMP]**: Captura los índices de color reales en el framebuffer (línea central, primeros 32 píxeles)
2. **[TILEMAP-DUMP-VISUAL]**: Captura los tile IDs reales leídos del tilemap (línea central, primeros 32 tiles)
3. **[TILEDATA-DUMP-VISUAL]**: Captura los datos reales de los tiles leídos de VRAM (primeros 4 tiles)
4. **[PALETTE-DUMP-VISUAL]**: Captura la aplicación de la paleta BGP (línea central, primeros 32 píxeles)

## Análisis de Logs

**NOTA**: Este documento se completará después de ejecutar el emulador y capturar los logs de los monitores.

### 1. Análisis del Framebuffer ([FRAMEBUFFER-DUMP])

**Qué buscar**:
- ¿Qué índices de color generan las rayas verdes?
- ¿Hay un patrón repetitivo en los índices?
- ¿Los índices alternan entre dos valores?

**Resultados esperados**:
- Si hay rayas, deberíamos ver un patrón repetitivo en los índices
- Los índices deberían ser 0, 1, 2, o 3 (valores válidos de color_index)

**Hallazgos**:
- [Pendiente de ejecución]

---

### 2. Análisis del Tilemap ([TILEMAP-DUMP-VISUAL])

**Qué buscar**:
- ¿Los tile IDs se repiten?
- ¿Forman un patrón?
- ¿Todos los tile IDs son el mismo valor (ej: 0x7F)?

**Resultados esperados**:
- Si hay rayas, podría haber un patrón en los tile IDs
- Los tile IDs deberían variar si hay diferentes tiles en pantalla

**Hallazgos**:
- [Pendiente de ejecución]

---

### 3. Análisis de Datos de Tiles ([TILEDATA-DUMP-VISUAL])

**Qué buscar**:
- ¿Los datos de tiles son uniformes (0x00) o varían?
- ¿Los tiles contienen datos válidos?
- ¿Hay un patrón en los bytes de los tiles?

**Resultados esperados**:
- Si los tiles están vacíos (0x00), todos los píxeles serían color_index 0
- Si los tiles tienen datos, deberíamos ver variación en los bytes

**Hallazgos**:
- [Pendiente de ejecución]

---

### 4. Análisis de Paleta ([PALETTE-DUMP-VISUAL])

**Qué buscar**:
- ¿La aplicación de la paleta genera el patrón?
- ¿Los color_index se mapean correctamente a final_color?
- ¿Hay un patrón en la aplicación de la paleta?

**Resultados esperados**:
- BGP = 0xE4 debería mapear identidad (0->0, 1->1, 2->2, 3->3)
- Si hay rayas, podría ser que la paleta esté generando el patrón

**Hallazgos**:
- [Pendiente de ejecución]

---

## Hipótesis sobre las Rayas Verdes

### Hipótesis A: Tilemap con valores repetidos
**Descripción**: El tilemap contiene valores repetidos (como 0x7F) que generan un patrón
**Cómo verificarlo**: Verificar si [TILEMAP-DUMP-VISUAL] muestra valores repetidos
**Corrección**: Si se confirma, investigar por qué el tilemap tiene valores repetidos

### Hipótesis B: Tiles vacíos con paleta verde
**Descripción**: Los tiles están vacíos (0x00) pero la paleta genera colores verdes
**Cómo verificarlo**: Verificar si [TILEDATA-DUMP-VISUAL] muestra solo 0x00
**Corrección**: Si se confirma, investigar por qué los tiles están vacíos (ya conocido) y por qué la paleta genera verde

### Hipótesis C: Cálculo incorrecto de direcciones
**Descripción**: El cálculo de direcciones de tiles es incorrecto, generando lecturas repetitivas
**Cómo verificarlo**: Verificar si [TILEMAP-DUMP-VISUAL] y [TILEDATA-DUMP-VISUAL] muestran patrones inesperados
**Corrección**: Si se confirma, corregir el cálculo de direcciones

### Hipótesis D: Scroll generando patrón
**Descripción**: El scroll (SCX/SCY) está generando un patrón repetitivo
**Cómo verificarlo**: Verificar si el patrón cambia con diferentes valores de SCX/SCY
**Corrección**: Si se confirma, investigar el cálculo de scroll

---

## Criterios de Éxito

- ✅ Identificar qué índice de color genera el verde oscuro
- ✅ Identificar qué índice de color genera el verde claro
- ✅ Determinar si el patrón viene del tilemap, los tiles, o la paleta
- ✅ Proponer corrección basada en los hallazgos

---

## Próximos Pasos

1. Ejecutar el emulador y capturar los logs de los 4 monitores
2. Analizar los logs para identificar patrones
3. Confirmar o rechazar las hipótesis
4. Implementar corrección si se identifica un problema específico

---

**Fecha de creación**: 2025-12-25
**Step ID**: 0299
**Estado**: Pendiente de ejecución y análisis

