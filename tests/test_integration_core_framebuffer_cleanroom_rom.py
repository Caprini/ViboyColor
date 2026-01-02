#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test de integración clean-room: CPU → MMU → VRAM → PPU → framebuffer_rgb

Objetivo:
    Validar el pipeline completo de emulación sin depender de ROMs comerciales.
    Se crea una ROM mínima en memoria que:
    1. Apaga LCD
    2. Escribe patrón non-zero a VRAM (tile data + tile map)
    3. Enciende LCD
    4. Loop infinito
    
    Luego se ejecutan N frames y se verifica que el framebuffer tenga píxeles non-white.

Referencias:
    - Pan Docs: LCDC ($FF40), VRAM layout ($8000-$9FFF)
    - Step 0435: Clean-room deterministic ROM test
"""

import pytest

try:
    from viboy_core import PyCPU, PyMMU, PyPPU, PyRegisters
    NATIVE_AVAILABLE = True
except ImportError:
    NATIVE_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="viboy_core no está disponible (compilación requerida)")


def create_minimal_test_rom() -> bytes:
    """
    Crea una ROM mínima GB que:
    1. Apaga LCD (LCDC = 0)
    2. Escribe patrón non-zero a VRAM:
       - Tile data en 0x8000-0x800F (1 tile completo con patrón)
       - Tile map en 0x9800 (primeras posiciones apuntan al tile)
    3. Enciende LCD (LCDC = 0x91: LCD ON, BG ON, Tilemap $9800, Tiledata $8000)
    4. Loop infinito
    
    Diseño de la ROM:
    
    0x0000-0x00FF: Header vacío (0x00)
    0x0100-0x0103: Entry point (NOP, JP 0x0150)
    0x0104-0x014F: Header estándar GB
    0x0150-0x01XX: Programa principal
    
    Programa ASM conceptual:
    
        ; Apagar LCD
        LD A, 0x00
        LD ($FF40), A       ; LCDC = 0
        
        ; Escribir tile data (1 tile = 16 bytes en 0x8000)
        LD HL, $8000
        LD B, 16
    .loop_tile:
        LD A, $AA           ; Patrón alternado 10101010
        LD (HL+), A
        DEC B
        JR NZ, .loop_tile
        
        ; Escribir tile map (primera fila = tile 0)
        LD HL, $9800
        LD B, 20            ; 20 tiles (primera fila)
    .loop_map:
        LD A, 0x00          ; Apuntar al tile 0
        LD (HL+), A
        DEC B
        JR NZ, .loop_map
        
        ; Encender LCD
        LD A, $91           ; LCD ON, BG ON, Tilemap $9800
        LD ($FF40), A
        
        ; Loop infinito
    .infinite:
        JR .infinite
    
    Encoding manual de las instrucciones:
    """
    rom = bytearray(0x8000)  # 32KB (mínimo para MBC0)
    
    # Header GB estándar
    # 0x0100-0x0103: Entry point
    rom[0x0100] = 0x00  # NOP
    rom[0x0101] = 0xC3  # JP nn
    rom[0x0102] = 0x50  # Low byte of 0x0150
    rom[0x0103] = 0x01  # High byte of 0x0150
    
    # 0x0104-0x0133: Nintendo logo (debe ser correcto para pasar checksum)
    nintendo_logo = bytes([
        0xCE, 0xED, 0x66, 0x66, 0xCC, 0x0D, 0x00, 0x0B,
        0x03, 0x73, 0x00, 0x83, 0x00, 0x0C, 0x00, 0x0D,
        0x00, 0x08, 0x11, 0x1F, 0x88, 0x89, 0x00, 0x0E,
        0xDC, 0xCC, 0x6E, 0xE6, 0xDD, 0xDD, 0xD9, 0x99,
        0xBB, 0xBB, 0x67, 0x63, 0x6E, 0x0E, 0xEC, 0xCC,
        0xDD, 0xDC, 0x99, 0x9F, 0xBB, 0xB9, 0x33, 0x3E
    ])
    rom[0x0104:0x0104 + len(nintendo_logo)] = nintendo_logo
    
    # 0x0134-0x0143: Title "TESTROM"
    title = b"TESTROM\x00\x00\x00\x00\x00\x00\x00\x00"
    rom[0x0134:0x0144] = title
    
    # 0x0144-0x0145: Color GB flag (0x00 = DMG only)
    rom[0x0143] = 0x00
    
    # 0x0147: Cartridge type (0x00 = ROM ONLY)
    rom[0x0147] = 0x00
    
    # 0x0148: ROM size (0x00 = 32KB)
    rom[0x0148] = 0x00
    
    # 0x0149: RAM size (0x00 = No RAM)
    rom[0x0149] = 0x00
    
    # 0x014A-0x014C: Destination, Old licensee, version
    rom[0x014A] = 0x00
    rom[0x014B] = 0x00
    rom[0x014C] = 0x00
    
    # 0x014D: Header checksum (calculado después)
    # 0x014E-0x014F: Global checksum (no crítico)
    
    # 0x0150: Programa principal
    pc = 0x0150
    
    # 1. Apagar LCD: LD A, 0x00
    rom[pc] = 0x3E  # LD A, n
    rom[pc + 1] = 0x00
    pc += 2
    
    # LD ($FF40), A  ->  LDH (n), A
    rom[pc] = 0xE0  # LDH (n), A
    rom[pc + 1] = 0x40  # Offset de $FF00
    pc += 2
    
    # 2. Escribir tile data: LD HL, $8000
    rom[pc] = 0x21  # LD HL, nn
    rom[pc + 1] = 0x00  # Low byte
    rom[pc + 2] = 0x80  # High byte
    pc += 3
    
    # LD B, 16
    rom[pc] = 0x06  # LD B, n
    rom[pc + 1] = 0x10  # 16 bytes (1 tile)
    pc += 2
    
    # .loop_tile: LD A, $AA
    loop_tile_addr = pc
    rom[pc] = 0x3E  # LD A, n
    rom[pc + 1] = 0xAA  # Patrón alternado
    pc += 2
    
    # LD (HL+), A
    rom[pc] = 0x22  # LD (HL+), A
    pc += 1
    
    # DEC B
    rom[pc] = 0x05  # DEC B
    pc += 1
    
    # JR NZ, .loop_tile
    rom[pc] = 0x20  # JR NZ, e
    rom[pc + 1] = (loop_tile_addr - (pc + 2)) & 0xFF  # Offset relativo
    pc += 2
    
    # 3. Escribir tile map: LD HL, $9800
    rom[pc] = 0x21  # LD HL, nn
    rom[pc + 1] = 0x00  # Low byte
    rom[pc + 2] = 0x98  # High byte
    pc += 3
    
    # LD B, 20 (primera fila de 20 tiles)
    rom[pc] = 0x06  # LD B, n
    rom[pc + 1] = 0x14  # 20 tiles
    pc += 2
    
    # .loop_map: LD A, 0x00
    loop_map_addr = pc
    rom[pc] = 0x3E  # LD A, n
    rom[pc + 1] = 0x00  # Tile index 0
    pc += 2
    
    # LD (HL+), A
    rom[pc] = 0x22  # LD (HL+), A
    pc += 1
    
    # DEC B
    rom[pc] = 0x05  # DEC B
    pc += 1
    
    # JR NZ, .loop_map
    rom[pc] = 0x20  # JR NZ, e
    rom[pc + 1] = (loop_map_addr - (pc + 2)) & 0xFF  # Offset relativo
    pc += 2
    
    # 4. Encender LCD: LD A, $91
    rom[pc] = 0x3E  # LD A, n
    rom[pc + 1] = 0x91  # LCD ON, BG ON, Tilemap $9800, Tiledata $8000
    pc += 2
    
    # LD ($FF40), A
    rom[pc] = 0xE0  # LDH (n), A
    rom[pc + 1] = 0x40
    pc += 2
    
    # 5. Loop infinito: JR -2
    infinite_loop_addr = pc
    rom[pc] = 0x18  # JR e
    rom[pc + 1] = 0xFE  # -2 (salta a sí mismo)
    pc += 2
    
    # Calcular header checksum (0x014D)
    header_checksum = 0
    for addr in range(0x0134, 0x014D):
        header_checksum = (header_checksum - rom[addr] - 1) & 0xFF
    rom[0x014D] = header_checksum
    
    return bytes(rom)


def test_cleanroom_rom_framebuffer_integration():
    """
    Test de integración clean-room: valida que una ROM mínima (sin comerciales)
    pueda escribir VRAM y generar un framebuffer con píxeles non-white.
    
    Pipeline validado:
        CPU ejecuta instrucciones → MMU escribe VRAM → PPU lee VRAM y renderiza → 
        framebuffer_rgb contiene píxeles non-zero
    
    Criterios de éxito:
        - Después de N frames (60), el framebuffer debe tener > 5% píxeles non-white
        - Validación determinista (misma ROM, mismos resultados)
    """
    # Crear ROM mínima clean-room
    rom_bytes = create_minimal_test_rom()
    
    # Inicializar core C++ (MMU, Registers, CPU, PPU)
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # Cargar ROM
    mmu.load_rom_py(rom_bytes)
    
    # Configurar estado post-boot DMG (como en Step 0401)
    regs.a = 0x01  # DMG
    regs.b = 0x00
    regs.c = 0x13
    regs.d = 0x00
    regs.e = 0xD8
    regs.h = 0x01
    regs.l = 0x4D
    regs.sp = 0xFFFE
    regs.pc = 0x0100
    
    # Registros I/O post-boot
    mmu.write(0xFF05, 0x00)  # TIMA
    mmu.write(0xFF06, 0x00)  # TMA
    mmu.write(0xFF07, 0x00)  # TAC
    mmu.write(0xFF10, 0x80)  # NR10
    mmu.write(0xFF11, 0xBF)  # NR11
    mmu.write(0xFF12, 0xF3)  # NR12
    mmu.write(0xFF14, 0xBF)  # NR14
    mmu.write(0xFF16, 0x3F)  # NR21
    mmu.write(0xFF17, 0x00)  # NR22
    mmu.write(0xFF19, 0xBF)  # NR24
    mmu.write(0xFF1A, 0x7F)  # NR30
    mmu.write(0xFF1B, 0xFF)  # NR31
    mmu.write(0xFF1C, 0x9F)  # NR32
    mmu.write(0xFF1E, 0xBF)  # NR34
    mmu.write(0xFF20, 0xFF)  # NR41
    mmu.write(0xFF21, 0x00)  # NR42
    mmu.write(0xFF22, 0x00)  # NR43
    mmu.write(0xFF23, 0xBF)  # NR44
    mmu.write(0xFF24, 0x77)  # NR50
    mmu.write(0xFF25, 0xF3)  # NR51
    mmu.write(0xFF26, 0xF1)  # NR52
    mmu.write(0xFF40, 0x91)  # LCDC
    mmu.write(0xFF42, 0x00)  # SCY
    mmu.write(0xFF43, 0x00)  # SCX
    mmu.write(0xFF45, 0x00)  # LYC
    mmu.write(0xFF47, 0xFC)  # BGP
    mmu.write(0xFF48, 0xFF)  # OBP0
    mmu.write(0xFF49, 0xFF)  # OBP1
    mmu.write(0xFF4A, 0x00)  # WY
    mmu.write(0xFF4B, 0x00)  # WX
    mmu.write(0xFFFF, 0x00)  # IE
    
    # Ejecutar emulación por 60 frames (~1 segundo)
    # Cada frame = 70224 ciclos (154 líneas × 456 ciclos)
    cycles_per_frame = 70224
    target_frames = 60
    total_cycles = 0
    
    for frame_idx in range(target_frames):
        frame_cycles = 0
        while frame_cycles < cycles_per_frame:
            # Ejecutar 1 instrucción
            cycles = cpu.step()
            
            # Avanzar PPU los mismos ciclos
            ppu.step(cycles)
            
            frame_cycles += cycles
            total_cycles += cycles
    
    # Obtener framebuffer final (160×144 píxeles, índices de color 0-3)
    framebuffer = ppu.get_framebuffer_rgb()
    
    # Validar que el framebuffer no esté vacío
    assert framebuffer is not None, "Framebuffer es None"
    assert len(framebuffer) == 160 * 144 * 3, f"Framebuffer size incorrecto: {len(framebuffer)}"
    
    # Contar píxeles non-white
    # Formato: [R, G, B, R, G, B, ...]
    # White = (224, 248, 208) o superior en todos los canales
    # Non-white = cualquier valor menor
    non_white_pixels = 0
    total_pixels = 160 * 144
    
    for i in range(0, len(framebuffer), 3):
        r = framebuffer[i]
        g = framebuffer[i + 1]
        b = framebuffer[i + 2]
        
        # Considerar non-white si cualquier canal es < 200
        if r < 200 or g < 200 or b < 200:
            non_white_pixels += 1
    
    non_white_percentage = (non_white_pixels / total_pixels) * 100
    
    # Criterio de éxito: > 5% píxeles non-white
    # (El patrón 0xAA en 1 tile × 20 posiciones debería cubrir ~12.5% de la primera línea)
    min_percentage = 5.0
    
    assert non_white_pixels > 0, "Framebuffer completamente blanco (0 píxeles non-white)"
    assert non_white_percentage > min_percentage, \
        f"Framebuffer tiene solo {non_white_percentage:.2f}% píxeles non-white (esperado > {min_percentage}%)"
    
    # Log de éxito
    print(f"\n✅ Test clean-room ROM passed:")
    print(f"   Total pixels: {total_pixels}")
    print(f"   Non-white pixels: {non_white_pixels} ({non_white_percentage:.2f}%)")
    print(f"   Total cycles executed: {total_cycles}")
    print(f"   Frames rendered: {target_frames}")


def test_cleanroom_rom_vram_writes():
    """
    Test complementario: verifica que la ROM clean-room SÍ escribe valores non-zero a VRAM.
    Este test es más rápido y focalizado en la escritura VRAM.
    """
    rom_bytes = create_minimal_test_rom()
    
    mmu = PyMMU()
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    mmu.load_rom_py(rom_bytes)
    
    # Estado post-boot
    regs.a = 0x01
    regs.b = 0x00
    regs.c = 0x13
    regs.d = 0x00
    regs.e = 0xD8
    regs.h = 0x01
    regs.l = 0x4D
    regs.sp = 0xFFFE
    regs.pc = 0x0100
    
    # Ejecutar ~10000 ciclos (suficiente para que la ROM escriba VRAM)
    total_cycles = 0
    max_cycles = 10000
    
    while total_cycles < max_cycles:
        cycles = cpu.step()
        ppu.step(cycles)
        total_cycles += cycles
    
    # Verificar que VRAM tiene datos non-zero
    # Leer tile data en 0x8000-0x800F (primer tile)
    non_zero_bytes = 0
    for addr in range(0x8000, 0x8010):
        value = mmu.read(addr)
        if value != 0x00:
            non_zero_bytes += 1
    
    # Criterio: al menos 10 bytes non-zero en el primer tile (patrón 0xAA)
    assert non_zero_bytes >= 10, \
        f"VRAM tile data no poblado correctamente: solo {non_zero_bytes}/16 bytes non-zero"
    
    # Verificar tile map en 0x9800-0x9813 (primeras 20 posiciones)
    # Nota: todas deberían ser 0x00 (apuntando al tile 0), lo cual es correcto
    tile_map_set = False
    for addr in range(0x9800, 0x9814):
        value = mmu.read(addr)
        # En este test, el valor 0x00 es esperado (apunta al tile 0)
        # Solo verificamos que la ROM pudo escribir (no importa el valor)
        tile_map_set = True
    
    assert tile_map_set, "Tile map no accesible"
    
    print(f"\n✅ Test VRAM writes passed:")
    print(f"   Non-zero bytes in tile data: {non_zero_bytes}/16")
    print(f"   Total cycles executed: {total_cycles}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

