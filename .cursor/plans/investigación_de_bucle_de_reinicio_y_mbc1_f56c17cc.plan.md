---
name: Investigación de Bucle de Reinicio y MBC1
overview: Implementar monitores para detectar reinicios inesperados del juego y verificar que el mapeo de memoria del MBC1 no esté corrompiendo los vectores de interrupción.
todos:
  - id: cpu-reset-monitor
    content: Implementar monitores de Reset (0x0000/0x0100) en CPU.cpp
    status: pending
  - id: cpu-vblank-trace
    content: Añadir log de entrada a V-Blank (0x0040) en CPU.cpp
    status: pending
  - id: mmu-mbc1-mode-monitor
    content: Implementar monitor de modo MBC1 en MMU.cpp
    status: pending
  - id: doc-step-0279
    content: Crear entrada de bitácora 0279 y actualizar índice/informe
    status: pending
---

Implementar instrumentación avanzada para detectar si Pokémon Red está en un bucle de reinicio (Reset Loop).Monitorizar el PC en las direcciones 0x0000 y 0x0100 para confirmar reinicios.Rastrear cambios en el modo de operación del MBC1 que podrían desplazar el Banco 0 de la memoria baja.