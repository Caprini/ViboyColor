# Step 0470 - Decisión Automática: Diagnóstico de PC Stuck y IE/IME

## Datos Recopilados por ROM

### tetris_dx.gbc

**Frame 120:**
- `ie_write_count`: 1
- `ei_count`: 0
- `di_count`: 1
- `IE`: 0x00
- `IME`: 0
- `pc_hotspots_top3`: 0x1304:16227, 0x1305:16227, 0x1306:16227
- `io_reads_top3`: 0xFF0F:11773601 (IF), 0xFFFF:11773238 (IE), 0xFF44:490 (LY)

**Frame 180:**
- `ie_write_count`: 7
- `ei_count`: 2
- `di_count`: 4
- `IE`: 0x00
- `IME`: 0
- `pc_hotspots_top3`: 0x1308:19320, 0x1302:19320, 0x1303:19320
- `io_reads_top3`: 0xFF0F:17523814 (IF), 0xFFFF:17523276 (IE), 0xFF44:15235 (LY)

### mario.gbc

**Frame 120:**
- `ie_write_count`: 42
- `ei_count`: 0
- `di_count`: 0
- `IE`: 0x00
- `IME`: 0
- `pc_hotspots_top3`: 0x12A0:9577, 0x129D:9571, 0x12A2:9570
- `io_reads_top3`: 0xFF0F:8822405 (IF), 0xFFFF:8821965 (IE), 0xFF44:177933 (LY)

**Frame 180:**
- `ie_write_count`: 62
- `ei_count`: 0
- `di_count`: 0
- `IE`: 0x00
- `IME`: 0
- `pc_hotspots_top3`: 0x12A0:14358, 0x129D:14349, 0x12A2:14348
- `io_reads_top3`: 0xFF0F:13206566 (IF), 0xFFFF:13205906 (IE), 0xFF44:262264 (LY)

---

## Decisión Automática por ROM

### tetris_dx.gbc

**Causa Identificada**: **IE writes lost or overwritten** + **EI timing bug**

**Evidencia:**
1. `ie_write_count=7` pero `IE=0x00` → Writes a IE se pierden o son sobrescritos
2. `ei_count=2` pero `IME=0` → EI ejecutado pero IME sigue 0 (posible bug en timing de EI)
3. `io_reads_top3` dominado por `0xFF0F` (IF) y `0xFFFF` (IE) con millones de lecturas → Polling IF/IE stuck
4. `pc_hotspots_top3` en `0x1302-0x1308` → Loop de polling esperando que IE/IF cambien

**Conclusión**: El juego intenta habilitar interrupciones (writes a IE, ejecución de EI), pero:
- Los writes a IE se pierden o son sobrescritos inmediatamente
- EI no surte efecto (IME sigue 0)
- El juego queda atrapado en un loop de polling esperando que IE/IF cambien

**Fix Sugerido**: 
1. Verificar que writes a IE (0xFFFF) persisten correctamente
2. Verificar timing de EI (IME debe activarse después de la siguiente instrucción)
3. Verificar que ningún componente sobrescribe IE después de que el juego lo escribe

### mario.gbc

**Causa Identificada**: **IE writes lost or overwritten** + **EI never executed**

**Evidencia:**
1. `ie_write_count=62` pero `IE=0x00` → Writes a IE se pierden o son sobrescritos
2. `ei_count=0` → EI nunca ejecutado (el juego no intenta habilitar IME)
3. `io_reads_top3` dominado por `0xFF0F` (IF) y `0xFFFF` (IE) con millones de lecturas → Polling IF/IE stuck
4. `pc_hotspots_top3` en `0x129D-0x12A2` → Loop de polling esperando que IE/IF cambien

**Conclusión**: El juego intenta escribir IE múltiples veces (62 writes), pero:
- Los writes a IE se pierden o son sobrescritos inmediatamente
- El juego nunca ejecuta EI (no intenta habilitar IME)
- El juego queda atrapado en un loop de polling esperando que IE/IF cambien

**Fix Sugerido**: 
1. Verificar que writes a IE (0xFFFF) persisten correctamente
2. Verificar que ningún componente sobrescribe IE después de que el juego lo escribe
3. Investigar por qué el juego no ejecuta EI (posible condición de bloqueo antes de llegar a EI)

---

## Decisión Automática Global

**Causa Dominante**: **IE writes lost or overwritten**

**Evidencia Común:**
- Ambos juegos escriben a IE múltiples veces (`ie_write_count > 0`)
- Ambos juegos tienen `IE=0x00` sostenido a pesar de los writes
- Ambos juegos están atrapados en loops de polling esperando que IE/IF cambien

**Hipótesis Principal**: 
Algún componente del sistema (posiblemente relacionado con CGB o modo de hardware) está sobrescribiendo IE (0xFFFF) después de que el juego lo escribe, o los writes no persisten correctamente.

**Próximos Pasos (Step 0471)**:
1. Añadir logging detallado de writes a IE para identificar qué componente sobrescribe IE
2. Verificar que writes a IE persisten correctamente en modo CGB
3. Verificar timing de EI en tetris_dx.gbc (EI ejecutado pero IME sigue 0)

