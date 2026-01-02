"""
Test de Regresión 0440: LY Polling (Detección de Wiring MMU↔PPU y Ciclos M→T)

Versión COMPACTA (Step 0440):
- Des-skip: Tests habilitados para CI
- Determinista: ROM mínima (<20 bytes), límite de ciclos estricto
- Silencioso: Sin prints innecesarios

Valida:
1. MMU conectada a PPU (mmu.set_ppu(ppu))
2. Conversión correcta M-cycles → T-cycles (factor 4)

ROM: loop: LDH A,(44h); CP 91h; JR NZ,loop; LD A,42h; LDH (80h),A; HALT
→ Escribe MAGIC (0x42) en 0xFF80 cuando LY==0x91

Pan Docs: LY (0xFF44) cicla 0→153 cada 70224 T-cycles
"""
import pytest
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from viboy_core import PyMMU, PyCPU, PyPPU, PyRegisters
    CPP_AVAILABLE = True
except ImportError:
    CPP_AVAILABLE = False


def _create_ly_rom():
    """ROM mínima: loop hasta LY==0x91, escribe 0x42 en FF80, HALT"""
    rom = bytearray(0x8000)
    rom[0x100:0x104] = [0x00, 0xC3, 0x50, 0x01]  # NOP; JP 0x0150
    rom[0x147:0x14A] = [0x00, 0x00, 0x00]  # ROM ONLY, 32KB, No RAM
    # Header checksum (simplificado, no importa para test interno)
    rom[0x14D] = 0xB0
    # Programa en 0x150: F0 44 FE 91 20 FA 3E 42 E0 80 76
    rom[0x150:0x15B] = [0xF0, 0x44, 0xFE, 0x91, 0x20, 0xFA, 0x3E, 0x42, 0xE0, 0x80, 0x76]
    return bytes(rom)


def _run_ly_test(connect_mmu_ppu, convert_m_to_t, max_frames=5):
    """Helper: ejecuta ROM LY con configuración controlada"""
    rom = _create_ly_rom()
    regs = PyRegisters()
    mmu = PyMMU()
    cpu = PyCPU(mmu, regs)
    ppu = PyPPU(mmu)
    
    if connect_mmu_ppu:
        mmu.set_ppu(ppu)
    cpu.set_ppu(ppu)
    mmu.load_rom_py(rom)
    regs.pc = 0x0150
    
    MAGIC_ADDR = 0xFF80
    CYCLES_PER_FRAME = 70224
    
    for frame in range(max_frames):
        cycles = 0
        while cycles < CYCLES_PER_FRAME:
            m = cpu.step()
            if m == 0:
                m = 1  # Temporary hack (será eliminado en Fase C)
            t = (m * 4) if convert_m_to_t else m
            ppu.step(t)
            cycles += (m * 4)  # Contador de frame siempre correcto
            if mmu.read_byte(MAGIC_ADDR) == 0x42:
                return True, frame + 1
    return False, max_frames


@pytest.mark.skipif(not CPP_AVAILABLE, reason="Requiere módulo C++ compilado")
def test_ly_polling_pass():
    """Test PASS: Wiring correcto + conversión M→T correcta"""
    magic_ok, frames = _run_ly_test(connect_mmu_ppu=True, convert_m_to_t=True, max_frames=5)
    assert magic_ok, "MAGIC no se escribió: falta wiring o conversión M→T"
    assert frames <= 3, f"Timing incorrecto: {frames} frames (esperado ≤3)"


@pytest.mark.skipif(not CPP_AVAILABLE, reason="Requiere módulo C++ compilado")
def test_ly_polling_fail_no_wiring():
    """Test FAIL controlado: Sin mmu.set_ppu(ppu) → LY siempre 0"""
    magic_ok, _ = _run_ly_test(connect_mmu_ppu=False, convert_m_to_t=True, max_frames=3)
    assert not magic_ok, "Test negativo FALLÓ: MAGIC se escribió sin wiring"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

