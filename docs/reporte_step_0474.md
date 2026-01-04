# Reporte Step 0474: Identificación de Bucle de Espera del Hotspot

## Resumen Ejecutivo

Se ejecutó `rom_smoke_0442.py` con instrumentación quirúrgica de IF/LY/STAT sobre 3 ROMs:
- `tetris.gb` (DMG)
- `tetris_dx.gbc` (CGB)
- `mario.gbc` (CGB)

**Hallazgo Principal**: Todas las ROMs están en bucles de espera leyendo IF (0xFF0F) obsesivamente, pero IF nunca se limpia (IF_Writes0=0 o muy bajo), lo que sugiere que el juego espera que IF cambie pero nunca lo hace.

---

## tetris.gb (DMG)

### Hotspot
- **PC hotspot #1**: 0x02B4
- **Disasm** (Frame 0):
  ```
  0x02B4: CP 0x94
  0x02B6: JR NZ, 0x02B2 (-6)
  0x02B8: LD A, 0x03
  0x02BA: DB 0xE0
  0x02BB: DB 0x40
  0x02BC: LD A, 0xE4
  0x02BE: DB 0xE0
  0x02BF: DB 0x47
  ```
- **IO tocado**: None (no detectado en disasm básico)

### IF/LY/STAT (Frame 0)
- **IF read count**: 59,525
- **IF write count**: 2
- **IF read val**: 0xE1
- **IF write val**: 0xE1
- **IF write PC**: 0x02B6
- **IF writes 0**: 0
- **IF writes nonzero**: 2
- **LY read min**: 0
- **LY read max**: 148
- **LY last read**: 0
- **STAT last read**: 0x00

### Resultado
**Loop espera en IF**: El juego está en un bucle (0x02B4-0x02B6) leyendo IF obsesivamente (59,525 reads), pero IF nunca se limpia (IF_Writes0=0). El valor de IF es 0xE1 (bits 0, 5, 6, 7 activos), pero el juego espera que cambie.

**Bug en semántica**: IF upper bits (5-7) leen como 1 (correcto según Pan Docs), pero el problema es que IF no se limpia cuando el juego lo espera. El bucle `JR NZ, 0x02B2` sugiere que está esperando que algún bit de IF cambie.

---

## tetris_dx.gbc (CGB)

### Hotspot
- **PC hotspot #1**: 0x1383 (Frame 0-1), 0x1308 (Frame 2)
- **Disasm** (Frame 0):
  ```
  0x1383: NOP
  0x1384: NOP
  0x1385: NOP
  0x1386: DB 0x1B
  0x1387: DB 0x7A
  0x1388: DB 0xB3
  0x1389: JR NZ, 0x1383 (-8)
  ```
- **IO tocado**: None

### IF/LY/STAT (Frame 0)
- **IF read count**: 98,271
- **IF write count**: 1
- **IF read val**: 0xE1
- **IF write val**: 0xE1
- **IF write PC**: 0x1385
- **IF writes 0**: 0
- **IF writes nonzero**: 1
- **LY read min**: 0
- **LY read max**: 144
- **LY last read**: 0
- **STAT last read**: 0x00

### Resultado
**Loop espera en IF**: Similar a tetris.gb. Bucle en 0x1383-0x1389 leyendo IF obsesivamente (98,271 reads), pero IF nunca se limpia (IF_Writes0=0). El valor de IF es 0xE1, pero el juego espera que cambie.

**Bug en semántica**: Mismo problema que tetris.gb. IF no se limpia cuando el juego lo espera.

---

## mario.gbc (CGB)

### Hotspot
- **PC hotspot #1**: 0x1290 (Frame 0), 0x129D (Frame 1-2)
- **Disasm** (Frame 0):
  ```
  0x1290: JR NZ, 0x128C (-6)
  0x1292: LD A, (0xFF40)
  0x1294: AND 0x7F
  0x1296: DB 0xE0
  0x1297: DB 0x40
  0x1298: LD A, (0xFF92)
  0x129A: DB 0xE0
  0x129B: DB 0xFF
  ```
- **IO tocado**: 0xFF40, 0xFF92

### IF/LY/STAT (Frame 0)
- **IF read count**: 54,027
- **IF write count**: 1
- **IF read val**: 0xE1
- **IF write val**: 0xE1
- **IF write PC**: 0x128E
- **IF writes 0**: 0
- **IF writes nonzero**: 1
- **LY read min**: 0
- **LY read max**: 145
- **LY last read**: 0
- **STAT last read**: 0x00

### Resultado
**Loop espera en IF**: Similar a las otras ROMs. Bucle leyendo IF obsesivamente (54,027 reads), pero IF nunca se limpia (IF_Writes0=0). El valor de IF es 0xE1, pero el juego espera que cambie.

**Bug en semántica**: Mismo problema. IF no se limpia cuando el juego lo espera.

---

## Decisión Automática

**Caso IF-bug**: 
- ✅ Hay writes para limpiar IF pero IF no cambia (IF_Writes0=0 o muy bajo)
- ✅ Upper bits correctos (IF lee como 0xE1 = 0xE0 | 0x01, bits 5-7 = 1)
- ❌ **Problema**: IF no se limpia cuando el juego lo espera

**Fix mínimo propuesto**: 
El problema no es la semántica de IF (upper bits leen correctamente), sino que **IF no se limpia automáticamente cuando se procesa una interrupción**. Según Pan Docs, cuando la CPU procesa una interrupción, debe limpiar el bit correspondiente en IF. Si esto no ocurre, el juego queda en un bucle infinito esperando que IF cambie.

**Próximo paso**: Verificar que cuando la CPU procesa una interrupción (VBlank, STAT, etc.), se limpia el bit correspondiente en IF.

---

## Evidencia de Tests

Todos los tests clean-room pasan:
- ✅ `test_if_upper_bits_read_as_1_0474.py` - Verifica que bits 5-7 leen como 1
- ✅ `test_if_clear_0474.py` - Verifica que IF puede limpiarse manualmente
- ✅ `test_ly_progresses_0474.py` - Verifica que LY progresa correctamente

**Validación de módulo compilado C++**: ✅ Todos los getters funcionan correctamente.
