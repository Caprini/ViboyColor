# Análisis de Logs Pokémon Red - Búsqueda de Patrones

**Fecha**: 2025-12-25  
**Comando ejecutado**: `python main.py roms/pkmn.gb > pkmn_log_analysis.txt 2>&1`

## Resumen Ejecutivo

Se ejecutó Pokémon Red con el emulador y se analizaron los logs generados buscando los siguientes patrones:
1. **[SNIPER-AWAKE]**: Indica que el bucle de retardo terminó
2. **[POST-DELAY]**: Muestra las siguientes 200 instrucciones después del retardo. Buscar si aparece 0xFB (EI) o escrituras en 0xFFFF
3. **[PPU-DEBUG]**: Muestra el Tile ID leído en el centro de la pantalla

---

## Hallazgos

### 1. [SNIPER-AWAKE] - Bucles de Retardo Detectados

**Total de entradas [SNIPER-AWAKE]**: Se detectaron múltiples salidas del bucle de retardo.

**Ubicación del bucle**: El bucle de retardo está ubicado en `PC:614A-6155` (aproximadamente).

**Ejemplos de salida del bucle**:
```
[SNIPER-EXIT] ¡LIBERTAD! El bucle de retardo ha terminado en PC:0x0040. DE:0x1660
[SNIPER-AWAKE] ¡Saliendo del bucle de retardo! Iniciando rastreo de flujo...
[POST-DELAY] PC:0040 OP:C3 | A:76 HL:64F8 | IE:0D IME:0
```

**Observaciones**:
- El bucle termina frecuentemente debido a interrupciones (salto a `0x0040`, vector de V-Blank)
- El valor de `DE` al salir del bucle varía (ej: `0x1660`, `0x0D94`)
- `IME:0` (interrupciones deshabilitadas) es común justo después de salir del bucle

---

### 2. [POST-DELAY] - Análisis de Instrucciones Post-Retardo

**Total de líneas [POST-DELAY]**: **437,744 líneas**

#### 2.1. Búsqueda de Opcode 0xFB (EI - Enable Interrupts)

**Resultado**: ❌ **NO se encontró el opcode 0xFB en los logs [POST-DELAY]**

**Nota importante**: Aunque aparece el valor `A:FB` (registro A contiene 0xFB) en muchas líneas, esto NO es lo mismo que el opcode `OP:FB`. El opcode 0xFB nunca aparece como instrucción ejecutada.

**Ejemplo de confusión**:
```
[POST-DELAY] PC:6153 OP:20 | A:FB HL:6558 | IE:0D IME:1
```
- `OP:20` es `JR NZ, e` (salto condicional), NO `OP:FB` (EI)
- `A:FB` es solo el valor del registro A

#### 2.2. Búsqueda de Escrituras en 0xFFFF (Registro IE)

**Resultado**: ⚠️ **Se encontraron escrituras a direcciones que terminan en `FF`, pero NO exactamente `0xFFFF`**

**Patrones encontrados**:
```
[POST-DELAY] PC:600A OP:E0 | A:20 HL:64FF | IE:0D IME:1
[POST-DELAY] PC:600E OP:E0 | A:30 HL:64FF | IE:0D IME:1
```

**Análisis**:
- `OP:E0` es `LDH (FF00+a8), A` - una escritura a HRAM
- `HL:64FF` indica que HL apunta a `0x64FF`, no a `0xFFFF`
- Las escrituras son a direcciones como `0xFF20`, `0xFF30` (registros de hardware), NO a `0xFFFF` (IE)

**Conclusión**: No se encontraron escrituras directas al registro IE (0xFFFF) en los logs [POST-DELAY].

#### 2.3. Patrones de Instrucciones Post-Retardo

**Secuencia típica después de salir del bucle**:

1. **Salto a Vector de Interrupción** (`PC:0040`):
   ```
   [POST-DELAY] PC:0040 OP:C3 | A:76 HL:64F8 | IE:0D IME:0
   ```
   - `OP:C3` es `JP nn` (salto absoluto)
   - `IE:0D` indica que las interrupciones V-Blank, LCD y Timer están habilitadas
   - `IME:0` indica que el flag IME está deshabilitado

2. **Rutina de Inicialización/Salvado** (`PC:2024-2045`):
   - Secuencia de `PUSH` (`OP:F5, C5, D5, E5`) para guardar registros
   - Lecturas/escrituras a registros de hardware (`OP:F0, E0, FA, EA`)

3. **Bucles en HRAM** (`PC:FF80-FF87`):
   - Bucle de decremento que escribe valores en HRAM
   - Ejemplo: `PC:FF86 OP:3D` (DEC A) seguido de `PC:FF87 OP:20` (JR NZ, e)

#### 2.4. Estado de Interrupciones

**Patrón observado**:
- **Al salir del bucle**: `IME:0` (interrupciones deshabilitadas)
- **Después de procesar interrupciones**: `IME:1` cuando el PC está en el bucle principal (`PC:614D-6153`)
- **IE (0xFFFF)**: Consistente en `IE:0D` (habilitadas: V-Blank, LCD, Timer)

**Observación crítica**: Aunque `IE:0D` indica que las interrupciones están habilitadas, `IME:0` significa que el hardware no procesará interrupciones hasta que se ejecute `EI` (opcode 0xFB). Como NO se encontró `OP:FB` en los logs [POST-DELAY], el juego puede estar atrapado sin poder procesar interrupciones correctamente.

**Nota adicional**: Se encontró un log `[CPU] EI (Enable Interrupts) en PC:0x60A6` en la línea 207 del log completo, lo que indica que `EI` SÍ se ejecuta en el juego, pero ANTES del bucle de retardo, no dentro de las 200 instrucciones posteriores capturadas por [POST-DELAY].

---

### 3. [PPU-DEBUG] - Tile ID en Centro de Pantalla

**Total de entradas [PPU-DEBUG]**: **1 entrada**

**Ubicación en log**: Línea 209

**Contenido**:
```
[PPU-DEBUG] LY:72 X:80 | TileMapAddr:992A | TileID:7F | TileDataBase:9000
```

**Análisis**:
- **LY:72**: Línea de escaneo 72 (dentro del rango visible, que es 0-143)
- **X:80**: Posición horizontal 80 (centro de la pantalla es ~80 en modo 160x144)
- **TileMapAddr:992A**: Dirección en el Tile Map desde donde se lee el Tile ID
- **TileID:7F**: ID del tile leído (hexadecimal 0x7F = decimal 127)
- **TileDataBase:9000**: Base de datos de tiles (modo signed, tiles 0-127 y 128-255)

**Interpretación**: El PPU está leyendo correctamente el Tile ID desde el Tile Map en el centro de la pantalla. El Tile ID `0x7F` indica un tile válido en el rango 0-127 (modo signed).

---

## Conclusiones

1. **Bucle de Retardo**: El juego ejecuta múltiples bucles de retardo en `PC:614A-6155`, saliendo frecuentemente debido a interrupciones.

2. **Opcode 0xFB (EI) ejecutado ANTES del bucle**: 
   - Se encontró `[CPU] EI (Enable Interrupts) en PC:0x60A6` en la línea 207 del log completo
   - `EI` se ejecuta **ANTES** de entrar al bucle de retardo (`PC:0x614A`)
   - `EI` **NO aparece** en los logs [POST-DELAY] (200 instrucciones posteriores) porque el rastreo captura solo las instrucciones después de salir del bucle
   - Esto es normal: el juego habilita interrupciones antes del bucle, las interrupciones se procesan durante el bucle (saltando a `0x0040`), y después del bucle el código continúa

3. **Escrituras a 0xFFFF NO encontradas en [POST-DELAY]**: No se encontraron escrituras directas al registro IE (0xFFFF) en los logs [POST-DELAY]. El registro IE permanece en `0x0D` (interrupciones V-Blank, LCD y Timer habilitadas).

4. **PPU Funcionando**: El PPU está leyendo correctamente tiles desde el Tile Map (TileID:7F en LY:72, X:80), lo que indica que el hardware gráfico está operativo.

5. **Flujo Normal**: El patrón observado es consistente con un flujo normal de ejecución:
   - `DI` en `PC:0x609E` (deshabilita interrupciones)
   - `EI` en `PC:0x60A6` (habilita interrupciones)
   - Entrada al bucle de retardo en `PC:0x614A`
   - Durante el bucle, las interrupciones se procesan (salto a `0x0040`)
   - Después del bucle, el código continúa normalmente

---

## Recomendaciones

1. **Buscar `EI` en otras partes del código**: Ampliar la búsqueda para encontrar dónde se ejecuta `EI` fuera de los logs [POST-DELAY].

2. **Analizar el código en `PC:0040` (Vector V-Blank)**: Verificar si el vector de interrupción debería habilitar IME automáticamente.

3. **Verificar la implementación de `EI`**: Confirmar que la instrucción `EI` está correctamente implementada y que realmente habilita IME.

4. **Analizar el flujo completo**: Revisar un trace más largo para ver si `EI` aparece más adelante en la ejecución.

---

## Archivos Relacionados

- Log completo: `pkmn_log_analysis.txt`
- Código fuente del detector: `src/core/cpp/CPU.cpp` (líneas 440-459)

