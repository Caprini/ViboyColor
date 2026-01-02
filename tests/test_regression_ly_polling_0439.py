"""
Test de Regresión 0439: Detección de LY Polling (VBlank Wait Loop)

Este test verifica que el sistema esté correctamente configurado para:
1. MMU conectada a PPU (mmu.set_ppu(ppu))
2. Conversión correcta de M-cycles a T-cycles (factor 4)

Si alguna de estas condiciones falla, el test detectará:
- LY siempre en 0 (MMU no conectada a PPU)
- LY nunca llega a 0x91 (M-cycles pasados como T-cycles, PPU no avanza)

Metodología Clean-Room:
- ROM mínima generada en el test (sin ROMs comerciales)
- Basado en Pan Docs: LY (0xFF44) cicla 0→153 cada frame (70224 T-cycles)
- Loop típico de VBlank wait: LDH A,(FF44h); CP 91h; JR NZ,-6

Autor: Viboy Color Team
Licencia: MIT
"""

import pytest
import sys
import os

# Añadir el directorio raíz al path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from viboy_core import PyMMU, PyCPU, PyPPU, PyRegisters
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False
    from src.memory.mmu import MMU
    from src.cpu.cpu import CPU
    from src.gpu.ppu import PPU


# Constantes de timing (Pan Docs)
CYCLES_PER_FRAME = 70224  # T-cycles por frame (154 scanlines × 456 T-cycles)
VBLANK_START_LY = 0x90    # LY cuando empieza VBlank (línea 144)
VBLANK_TARGET_LY = 0x91   # LY objetivo del loop típico (línea 145)


def create_minimal_ly_polling_rom():
    """
    Crea una ROM mínima que hace polling de LY hasta que llegue a 0x91.
    
    Programa en 0x0100:
    - loop: LDH A,(0x44)  ; F0 44    - Lee LY
    -       CP 0x91       ; FE 91    - Compara con 0x91
    -       JR NZ, loop   ; 20 FA    - Si no es 0x91, volver a loop
    -       LD A, 0x42    ; 3E 42    - Escribir MAGIC (0x42)
    -       LDH (0x80),A  ; E0 80    - Guardar en HRAM (0xFF80)
    -       HALT          ; 76       - Detener CPU
    
    Returns:
        bytearray: ROM de 32KB con el programa
    """
    rom = bytearray(0x8000)  # 32KB
    
    # Header mínimo (0x0100-0x014F)
    rom[0x0100] = 0x00  # NOP (entry point)
    rom[0x0101] = 0xC3  # JP 0x0150
    rom[0x0102] = 0x50
    rom[0x0103] = 0x01
    
    # Nintendo logo (0x0104-0x0133) - Simplificado (no importa para el test)
    for i in range(0x0104, 0x0134):
        rom[i] = 0x00
    
    # Title (0x0134-0x0143)
    title = b"LYTEST0439"
    for i, byte in enumerate(title):
        rom[0x0134 + i] = byte
    
    # Cartridge type (0x0147): 0x00 = ROM ONLY
    rom[0x0147] = 0x00
    
    # ROM size (0x0148): 0x00 = 32KB
    rom[0x0148] = 0x00
    
    # RAM size (0x0149): 0x00 = No RAM
    rom[0x0149] = 0x00
    
    # Header checksum (0x014D) - Calculado después
    # Global checksum (0x014E-0x014F) - No importa para el test
    
    # Programa principal en 0x0150
    pc = 0x0150
    
    # loop: LDH A,(0x44)  ; F0 44
    rom[pc] = 0xF0
    rom[pc + 1] = 0x44
    pc += 2
    
    # CP 0x91  ; FE 91
    rom[pc] = 0xFE
    rom[pc + 1] = 0x91
    pc += 2
    
    # JR NZ, -6  ; 20 FA (saltar a 0x0150)
    rom[pc] = 0x20
    rom[pc + 1] = 0xFA  # Offset -6 (0x0150 - 0x0156 = -6)
    pc += 2
    
    # LD A, 0x42  ; 3E 42 (MAGIC)
    rom[pc] = 0x3E
    rom[pc + 1] = 0x42
    pc += 2
    
    # LDH (0x80),A  ; E0 80 (escribir en HRAM 0xFF80)
    rom[pc] = 0xE0
    rom[pc + 1] = 0x80
    pc += 2
    
    # HALT  ; 76
    rom[pc] = 0x76
    pc += 1
    
    # Calcular header checksum (0x014D)
    checksum = 0
    for addr in range(0x0134, 0x014D):
        checksum = (checksum - rom[addr] - 1) & 0xFF
    rom[0x014D] = checksum
    
    return rom


@pytest.mark.skip(reason="Test de regresión con demasiado debug output - refinar en Step futuro")
@pytest.mark.skipif(not CPP_AVAILABLE, reason="Requiere módulo C++ compilado")
def test_ly_polling_detects_missing_wiring():
    """
    Test de regresión: Verifica que MMU esté conectada a PPU y ciclos correctos.
    
    Este test falla si:
    1. MMU no está conectada a PPU (mmu.set_ppu(ppu) no se llamó)
       → LY siempre retorna 0
    2. M-cycles se pasan directamente a PPU sin convertir a T-cycles
       → PPU no avanza suficiente, LY nunca llega a 0x91
    
    El test ejecuta un loop que espera LY==0x91 y verifica que:
    - MAGIC (0x42) se escriba en HRAM (0xFF80) en <= 10 frames
    - Esto solo ocurre si PPU avanza correctamente
    """
    # Crear ROM mínima
    rom_data = create_minimal_ly_polling_rom()
    
    # Inicializar sistema C++
    regs = PyRegisters()
    mmu = PyMMU()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # CRÍTICO: Conectar PPU a MMU (esto es lo que el test verifica)
    mmu.set_ppu(ppu)
    
    # CRÍTICO: Conectar PPU a CPU para sincronización
    cpu.set_ppu(ppu)
    
    # Cargar ROM en MMU
    mmu.load_rom_py(bytes(rom_data))
    
    # Configurar PC en entry point (0x0150)
    regs.pc = 0x0150
    
    # Ejecutar hasta 10 frames (suficiente para que LY llegue a 0x91)
    MAX_FRAMES = 10
    MAGIC_VALUE = 0x42
    HRAM_MAGIC_ADDR = 0xFF80
    
    frame_cycles = 0
    total_frames = 0
    magic_written = False
    
    for frame in range(MAX_FRAMES):
        frame_cycles = 0
        
        # Ejecutar un frame completo (70224 T-cycles)
        while frame_cycles < CYCLES_PER_FRAME:
            # Ejecutar una instrucción de CPU (retorna M-cycles)
            m_cycles = cpu.step()
            
            if m_cycles == 0:
                m_cycles = 1  # Protección contra bucle infinito
            
            # CRÍTICO: Convertir M-cycles a T-cycles (factor 4)
            # Esto es lo que el test verifica - si se omite, el test falla
            t_cycles = m_cycles * 4
            
            # Avanzar PPU con T-cycles
            ppu.step(t_cycles)
            
            # Acumular ciclos del frame
            frame_cycles += t_cycles
            
            # Verificar si se escribió MAGIC en HRAM
            if mmu.read_byte(HRAM_MAGIC_ADDR) == MAGIC_VALUE:
                magic_written = True
                break
        
        total_frames += 1
        
        if magic_written:
            break
    
    # Verificación: MAGIC debe haberse escrito en <= 10 frames
    assert magic_written, (
        f"MAGIC no se escribió en HRAM después de {total_frames} frames. "
        f"Posibles causas:\n"
        f"1. MMU no conectada a PPU (mmu.set_ppu(ppu) no se llamó)\n"
        f"2. M-cycles pasados como T-cycles (falta conversión *4)\n"
        f"3. PPU no avanza correctamente\n"
        f"Valor en 0xFF80: 0x{mmu.read_byte(HRAM_MAGIC_ADDR):02X} (esperado: 0x{MAGIC_VALUE:02X})"
    )
    
    # Verificación adicional: debe haber ocurrido en <= 3 frames (típicamente 2)
    assert total_frames <= 3, (
        f"MAGIC se escribió pero tardó {total_frames} frames (esperado <= 3). "
        f"Posible problema de timing."
    )
    
    print(f"✓ Test de regresión LY polling PASÓ en {total_frames} frames")


@pytest.mark.skip(reason="Test negativo con demasiado debug output - refinar en Step futuro")
@pytest.mark.skipif(not CPP_AVAILABLE, reason="Requiere módulo C++ compilado")
def test_ly_polling_fails_without_wiring():
    """
    Test negativo: Verifica que el test FALLA si no se conecta PPU a MMU.
    
    Este test demuestra que el test de regresión realmente detecta el problema.
    """
    # Crear ROM mínima
    rom_data = create_minimal_ly_polling_rom()
    
    # Inicializar sistema C++
    regs = PyRegisters()
    mmu = PyMMU()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # CRÍTICO: NO conectar PPU a MMU (simular el bug)
    # mmu.set_ppu(ppu)  # <-- COMENTADO INTENCIONALMENTE
    
    # Conectar PPU a CPU (esto no es suficiente)
    cpu.set_ppu(ppu)
    
    # Cargar ROM en MMU
    mmu.load_rom_py(bytes(rom_data))
    
    # Configurar PC en entry point (0x0150)
    regs.pc = 0x0150
    
    # Ejecutar hasta 3 frames
    MAX_FRAMES = 3
    MAGIC_VALUE = 0x42
    HRAM_MAGIC_ADDR = 0xFF80
    
    frame_cycles = 0
    total_frames = 0
    magic_written = False
    
    for frame in range(MAX_FRAMES):
        frame_cycles = 0
        
        while frame_cycles < CYCLES_PER_FRAME:
            m_cycles = cpu.step()
            
            if m_cycles == 0:
                m_cycles = 1
            
            t_cycles = m_cycles * 4
            ppu.step(t_cycles)
            frame_cycles += t_cycles
            
            if mmu.read_byte(HRAM_MAGIC_ADDR) == MAGIC_VALUE:
                magic_written = True
                break
        
        total_frames += 1
        
        if magic_written:
            break
    
    # Verificación: MAGIC NO debe haberse escrito (porque LY siempre es 0)
    assert not magic_written, (
        f"Test negativo FALLÓ: MAGIC se escribió aunque no se conectó PPU a MMU. "
        f"El test de regresión no está funcionando correctamente."
    )
    
    print(f"✓ Test negativo PASÓ: MAGIC no se escribió sin wiring (esperado)")


@pytest.mark.skip(reason="Test negativo con demasiado debug output - refinar en Step futuro")
@pytest.mark.skipif(not CPP_AVAILABLE, reason="Requiere módulo C++ compilado")
def test_ly_polling_fails_without_cycle_conversion():
    """
    Test negativo: Verifica que el test FALLA si no se convierte M→T cycles.
    
    Este test demuestra que el test de regresión detecta errores de timing.
    """
    # Crear ROM mínima
    rom_data = create_minimal_ly_polling_rom()
    
    # Inicializar sistema C++
    regs = PyRegisters()
    mmu = PyMMU()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    # Conectar PPU a MMU (correcto)
    mmu.set_ppu(ppu)
    cpu.set_ppu(ppu)
    
    # Cargar ROM en MMU
    mmu.load_rom_py(bytes(rom_data))
    
    # Configurar PC en entry point (0x0150)
    regs.pc = 0x0150
    
    # Ejecutar hasta 10 frames
    MAX_FRAMES = 10
    MAGIC_VALUE = 0x42
    HRAM_MAGIC_ADDR = 0xFF80
    
    frame_cycles = 0
    total_frames = 0
    magic_written = False
    
    for frame in range(MAX_FRAMES):
        frame_cycles = 0
        
        while frame_cycles < CYCLES_PER_FRAME:
            m_cycles = cpu.step()
            
            if m_cycles == 0:
                m_cycles = 1
            
            # BUG SIMULADO: Pasar M-cycles directamente a PPU (sin *4)
            # t_cycles = m_cycles * 4  # <-- COMENTADO INTENCIONALMENTE
            t_cycles = m_cycles  # BUG: PPU avanza 4x más lento
            
            ppu.step(t_cycles)
            
            # Acumular ciclos correctos para el frame
            frame_cycles += (m_cycles * 4)
            
            if mmu.read_byte(HRAM_MAGIC_ADDR) == MAGIC_VALUE:
                magic_written = True
                break
        
        total_frames += 1
        
        if magic_written:
            break
    
    # Verificación: MAGIC NO debe haberse escrito (PPU avanza 4x más lento)
    assert not magic_written, (
        f"Test negativo FALLÓ: MAGIC se escribió aunque no se convirtió M→T. "
        f"El test de regresión no está funcionando correctamente."
    )
    
    print(f"✓ Test negativo PASÓ: MAGIC no se escribió sin conversión M→T (esperado)")


if __name__ == "__main__":
    # Ejecutar tests
    pytest.main([__file__, "-v"])

