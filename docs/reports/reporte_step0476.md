# Reporte Step 0476: Source-Tagging + Decisión Automática

## Configuración

- Baseline: VIBOY_SIM_BOOT_LOGO=0, VIBOY_DEBUG_IO=1
- Control: VIBOY_SIM_BOOT_LOGO=1 (solo tetris_dx.gbc)

## Tablas por ROM (Baseline OFF)

### tetris_dx.gbc

| Frame | PC | PC_hotspot1 | IF | IE | IME | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | if_writes_program | last_irq_vector | last_if_before | last_if_after | last_if_clear_mask | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | tilemap_nz_9800 | tilemap_nz_9C00 | boot_logo_prefill |
|-------|----|-------------|----|----|-----|------------------|-------------------|-------------------|-------------------|-------------------|-----------------|---------------|---------------|-------------------|--------|--------|---------|-----------|------------|-----------------|-----------------|-------------------|
| 0 | 0x1305 | 0x1383 | 0xE1 | 0x00 | 0 | 49140 | 49131 | 49137 | 49131 | 1 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 60 | 0x1305 | 0x1306 | 0xE1 | 0x00 | 0 | 2968359 | 2968120 | 2968176 | 2968120 | 61 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 120 | 0x1303 | 0x1304 | 0xE1 | 0x00 | 0 | 5887011 | 5886589 | 5886648 | 5886589 | 121 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 180 | 0x1383 | 0x1308 | 0xE1 | 0x00 | 0 | 8762209 | 8761604 | 8761671 | 8761604 | 187 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 145 | 0 | 0x00 | 6409 | 259 | 0 | 0 |

**Disasm hotspot1 (Frame 0)**: 0x1383: NOP

### mario.gbc

| Frame | PC | PC_hotspot1 | IF | IE | IME | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | if_writes_program | last_irq_vector | last_if_before | last_if_after | last_if_clear_mask | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | tilemap_nz_9800 | tilemap_nz_9C00 | boot_logo_prefill |
|-------|----|-------------|----|----|-----|------------------|-------------------|-------------------|-------------------|-------------------|-----------------|---------------|---------------|-------------------|--------|--------|---------|-----------|------------|-----------------|-----------------|-------------------|
| 0 | 0x129D | 0x1290 | 0xE1 | 0x00 | 0 | 27017 | 27010 | 27015 | 27010 | 1 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 145 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 60 | 0x12A0 | 0x12A0 | 0xE3 | 0x00 | 0 | 2219279 | 2218962 | 2219059 | 2218962 | 119 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 145 | 0 | 0x00 | 0 | 1024 | 1024 | 0 |
| 120 | 0x12A0 | 0x12A0 | 0xE3 | 0x00 | 0 | 4411492 | 4410912 | 4411052 | 4410912 | 239 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 145 | 0 | 0x00 | 0 | 1024 | 1024 | 0 |
| 180 | 0x12A0 | 0x12A0 | 0xE3 | 0x00 | 0 | 6603703 | 6602862 | 6603043 | 6602862 | 359 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 145 | 0 | 0x00 | 0 | 1024 | 1024 | 0 |

**Disasm hotspot1 (Frame 0)**: 0x1290: JR NZ, 0x128C (-6)

### tetris.gb

| Frame | PC | PC_hotspot1 | IF | IE | IME | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | if_writes_program | last_irq_vector | last_if_before | last_if_after | last_if_clear_mask | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | tilemap_nz_9800 | tilemap_nz_9C00 | boot_logo_prefill |
|-------|----|-------------|----|----|-----|------------------|-------------------|-------------------|-------------------|-------------------|-----------------|---------------|---------------|-------------------|--------|--------|---------|-----------|------------|-----------------|-----------------|-------------------|
| 0 | 0x02EA | 0x02B4 | 0xE1 | 0x01 | 0 | 29766 | 29759 | 29763 | 29759 | 2 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 148 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 60 | 0x036C | 0x036C | 0xE0 | 0x09 | 1 | 1837836 | 1837658 | 1837660 | 1837658 | 120 | 0x0040 | 0x01 | 0x00 | 0x01 | 0 | 148 | 118 | 0x00 | 0 | 1024 | 0 | 0 |
| 120 | 0x036C | 0x036C | 0xE0 | 0x09 | 1 | 3639098 | 3638798 | 3638742 | 3638798 | 240 | 0x0040 | 0x01 | 0x00 | 0x01 | 0 | 148 | 118 | 0x00 | 0 | 1024 | 0 | 0 |
| 180 | 0x036C | 0x036F | 0xE0 | 0x09 | 1 | 5440361 | 5439938 | 5439825 | 5439938 | 360 | 0x0040 | 0x01 | 0x00 | 0x01 | 0 | 148 | 118 | 0x00 | 0 | 1024 | 0 | 0 |

**Disasm hotspot1 (Frame 0)**: 0x02B4: CP 0x94

## Comparativa Logo Prefill ON vs OFF (Solo tetris_dx.gbc)

### tetris_dx.gbc - OFF (Baseline)

### tetris_dx.gbc OFF

| Frame | PC | PC_hotspot1 | IF | IE | IME | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | if_writes_program | last_irq_vector | last_if_before | last_if_after | last_if_clear_mask | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | tilemap_nz_9800 | tilemap_nz_9C00 | boot_logo_prefill |
|-------|----|-------------|----|----|-----|------------------|-------------------|-------------------|-------------------|-------------------|-----------------|---------------|---------------|-------------------|--------|--------|---------|-----------|------------|-----------------|-----------------|-------------------|
| 0 | 0x1305 | 0x1383 | 0xE1 | 0x00 | 0 | 49140 | 49131 | 49137 | 49131 | 1 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 60 | 0x1305 | 0x1306 | 0xE1 | 0x00 | 0 | 2968359 | 2968120 | 2968176 | 2968120 | 61 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 120 | 0x1303 | 0x1304 | 0xE1 | 0x00 | 0 | 5887011 | 5886589 | 5886648 | 5886589 | 121 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |

**Disasm hotspot1 (Frame 0)**: 0x1383: NOP


### tetris_dx.gbc - ON (Contaminado)

### tetris_dx.gbc ON

| Frame | PC | PC_hotspot1 | IF | IE | IME | if_reads_program | if_reads_cpu_poll | ie_reads_program | ie_reads_cpu_poll | if_writes_program | last_irq_vector | last_if_before | last_if_after | last_if_clear_mask | LY_min | LY_max | LY_last | STAT_last | fb_nonzero | tilemap_nz_9800 | tilemap_nz_9C00 | boot_logo_prefill |
|-------|----|-------------|----|----|-----|------------------|-------------------|-------------------|-------------------|-------------------|-----------------|---------------|---------------|-------------------|--------|--------|---------|-----------|------------|-----------------|-----------------|-------------------|
| 0 | 0x1305 | 0x1383 | 0xE1 | 0x00 | 0 | 49140 | 49131 | 49137 | 49131 | 1 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 60 | 0x1305 | 0x1306 | 0xE1 | 0x00 | 0 | 2968359 | 2968120 | 2968176 | 2968120 | 61 | 0x0000 | 0x00 | 0x00 | 0x00 | 0 | 144 | 0 | 0x00 | 0 | 0 | 0 | 0 |
| 120 | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

**Disasm hotspot1 (Frame 0)**: 0x1383: NOP


**Análisis**:
- Frame 0 - TilemapNZ_9800: OFF=0, ON=0
- No hay contaminación significativa

## Decisión Automática

### Caso Identificado: 2

**Condición observada**: if_reads_program alto (5887011) y PC_hotspot1 estable

**Conclusión**: El juego SÍ está polleando IF, pero el bit esperado no aparece.

**Siguiente paso mínimo (0477)**: Verificar si PPU/Timer están generando IF correctamente, o si defaults post-boot están mal
