---
name: "Step 0282: Auditoría de Bancos MBC1 y Carga de VRAM"
overview: Investigar por qué Pokémon Red no carga gráficos reales tras la limpieza de VRAM, auditando el mapeo de bancos MBC1 y monitorizando las lecturas de ROM.
todos:
  - id: mmu-rom-read-monitor
    content: Implementar monitor de lectura ROM (0x4000-0x7FFF) en MMU.cpp
    status: completed
  - id: mmu-vram-data-sniper
    content: Añadir Sniper de escritura VRAM (valor != 0) en MMU.cpp
    status: completed
  - id: mmu-bank-mapping-audit
    content: Instrumentar update_bank_mapping en MMU.cpp
    status: completed
  - id: doc-step-0282
    content: Crear entrada de bitácora 0282 y actualizar índice/informe
    status: completed
---

Implementar un monitor en MMU.cpp para rastrear lecturas en el rango 0x4000-0x7FFF (bancos superiores) para verificar que el MBC1 mapea correctamente la ROM.Añadir un Sniper de escritura en VRAM que solo capture valores distintos de 0x00 para detectar cuándo se intentan cargar gráficos reales.