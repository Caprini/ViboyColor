# Changelog

Todos los cambios notables en este proyecto serán documentados en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.1] - 2025-12-18 (Proof of Concept)

### Added
- Core CPU LR35902 emulation (100% opcodes implementados).
- PPU Basic Rendering (Background, Window, Sprites).
- MBC1 Memory Banking support.
- Timer (DIV) implementation.
- Joypad Input support.
- Debugging tools suite (Doctor Viboy, VRAM Viewer).
- Bitácora web completa con documentación educativa del desarrollo.
- Suite completa de tests unitarios e integración.

### Known Issues
- Audio APU not implemented.
- CGB specific features (VRAM banking, Palettes) are stubs.
- Timing accuracy issues in Python causing gameplay instability in sensitive games.

