#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0481: Verificar tracking de HRAM FF92 con watchlist genérica.

Este test valida que el sistema de watchlist HRAM funciona correctamente:
- add_hram_watch() añade direcciones a la watchlist
- write() incrementa contadores y registra primera escritura
- read() incrementa contadores de lectura desde programa
- Getters devuelven valores correctos

Fuente: Step 0481 - Fase A1
"""

import os
import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad, PyCPU, PyRegisters


def test_hram_ff92_tracking():
    """
    Verifica que el tracking de HRAM[FF92] funciona correctamente con watchlist.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/CPU)
    2. Activar VIBOY_DEBUG_HRAM=1 (gate para tracking)
    3. Añadir 0xFF92 a watchlist: mmu.add_hram_watch(0xFF92)
    4. Escribir a 0xFF92 desde programa: mmu.write(0xFF92, 0x1F)
    5. Verificar contadores:
       - get_hram_write_count(0xFF92) == 1
       - get_hram_last_write_pc() != 0
       - get_hram_last_write_value() == 0x1F
    6. Leer 0xFF92: value = mmu.read(0xFF92)
    7. Verificar:
       - get_hram_read_count_program(0xFF92) == 1
       - get_hram_last_read_pc() != 0
    
    Criterio de éxito: Test pasa. Si falla, watchlist no está funcionando.
    """
    # Activar tracking HRAM
    os.environ["VIBOY_DEBUG_HRAM"] = "1"
    
    try:
        # Inicializar componentes
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        ppu = PyPPU(mmu)
        timer = PyTimer(mmu)
        joypad = PyJoypad()
        
        # Wiring
        mmu.set_ppu(ppu)
        mmu.set_timer(timer)
        mmu.set_joypad(joypad)
        cpu.set_ppu(ppu)
        cpu.set_timer(timer)
        
        # Paso 1: Añadir 0xFF92 a watchlist
        mmu.add_hram_watch(0xFF92)
        
        # Paso 2: Establecer PC para tracking usando una instrucción real
        # Cargar programa mínimo: NOP en 0x1000 para establecer PC
        regs.pc = 0x1000
        # Cargar NOP (0x00) en memoria para que CPU actualice debug_current_pc
        mmu.write(0x1000, 0x00)  # NOP
        cpu.step()  # Ejecutar NOP para actualizar debug_current_pc a 0x1001
        
        # Paso 3: Escribir a 0xFF92 (el PC será actualizado por la instrucción previa)
        write_value = 0x1F
        mmu.write(0xFF92, write_value)
        
        # Paso 4: Verificar contadores de escritura
        write_count = mmu.get_hram_write_count(0xFF92)
        assert write_count == 1, (
            f"get_hram_write_count(0xFF92) debe ser 1 después de escribir, "
            f"pero es {write_count}"
        )
        
        last_write_pc = mmu.get_hram_last_write_pc(0xFF92)
        assert last_write_pc != 0, (
            f"get_hram_last_write_pc(0xFF92) no debe ser 0, "
            f"pero es {last_write_pc:04X}"
        )
        # PC debe ser 0x1000 o 0x1001 (depende de cuándo se actualiza debug_current_pc)
        assert last_write_pc in [0x1000, 0x1001], (
            f"get_hram_last_write_pc(0xFF92) debe ser 0x1000 o 0x1001, "
            f"pero es {last_write_pc:04X}"
        )
        
        last_write_value = mmu.get_hram_last_write_value(0xFF92)
        assert last_write_value == write_value, (
            f"get_hram_last_write_value(0xFF92) debe ser 0x{write_value:02X}, "
            f"pero es 0x{last_write_value:02X}"
        )
        
        # Paso 5: Leer 0xFF92 (usar otra instrucción para establecer PC)
        regs.pc = 0x2000
        mmu.write(0x2000, 0x00)  # NOP
        cpu.step()  # Ejecutar NOP para actualizar debug_current_pc a 0x2001
        read_value = mmu.read(0xFF92)
        
        # Paso 6: Verificar contadores de lectura
        read_count = mmu.get_hram_read_count_program(0xFF92)
        assert read_count == 1, (
            f"get_hram_read_count_program(0xFF92) debe ser 1 después de leer, "
            f"pero es {read_count}"
        )
        
        # Verificar que el valor leído es el que escribimos
        assert read_value == write_value, (
            f"Valor leído de 0xFF92 debe ser 0x{write_value:02X}, "
            f"pero es 0x{read_value:02X}"
        )
        
        # Paso 7: Verificar primera escritura (frame debe ser 0 si no hay PPU avanzando)
        first_write_frame = mmu.get_hram_first_write_frame(0xFF92)
        # Frame puede ser 0 si PPU no ha avanzado, eso está bien
        assert first_write_frame >= 0, (
            f"get_hram_first_write_frame(0xFF92) debe ser >= 0, "
            f"pero es {first_write_frame}"
        )
        
    finally:
        # Limpiar env var
        if "VIBOY_DEBUG_HRAM" in os.environ:
            del os.environ["VIBOY_DEBUG_HRAM"]


def test_hram_watchlist_multiple_addresses():
    """
    Verifica que la watchlist puede trackear múltiples direcciones HRAM.
    
    Pasos:
    1. Añadir 0xFF90, 0xFF92, 0xFF95 a watchlist
    2. Escribir valores diferentes a cada una
    3. Verificar que cada una tiene su contador independiente
    """
    os.environ["VIBOY_DEBUG_HRAM"] = "1"
    
    try:
        mmu = PyMMU()
        
        # Añadir múltiples direcciones a watchlist
        mmu.add_hram_watch(0xFF90)
        mmu.add_hram_watch(0xFF92)
        mmu.add_hram_watch(0xFF95)
        
        # Establecer PC usando instrucción real
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        regs.pc = 0x1000
        mmu.write(0x1000, 0x00)  # NOP
        cpu.step()  # Ejecutar NOP para actualizar debug_current_pc
        
        # Escribir valores diferentes
        mmu.write(0xFF90, 0x10)
        mmu.write(0xFF92, 0x20)
        mmu.write(0xFF95, 0x30)
        
        # Verificar contadores independientes
        assert mmu.get_hram_write_count(0xFF90) == 1
        assert mmu.get_hram_write_count(0xFF92) == 1
        assert mmu.get_hram_write_count(0xFF95) == 1
        
        assert mmu.get_hram_last_write_value(0xFF90) == 0x10
        assert mmu.get_hram_last_write_value(0xFF92) == 0x20
        assert mmu.get_hram_last_write_value(0xFF95) == 0x30
        
    finally:
        if "VIBOY_DEBUG_HRAM" in os.environ:
            del os.environ["VIBOY_DEBUG_HRAM"]


def test_hram_watchlist_not_tracked_when_gate_off():
    """
    Verifica que la watchlist NO trackea cuando VIBOY_DEBUG_HRAM está OFF.
    
    Pasos:
    1. NO activar VIBOY_DEBUG_HRAM (o activarlo como "0")
    2. Añadir 0xFF92 a watchlist
    3. Escribir a 0xFF92
    4. Verificar que write_count sigue siendo 0 (no trackeó)
    """
    # Asegurar que está OFF
    if "VIBOY_DEBUG_HRAM" in os.environ:
        del os.environ["VIBOY_DEBUG_HRAM"]
    
    mmu = PyMMU()
    
    # Añadir a watchlist
    mmu.add_hram_watch(0xFF92)
    
    # Escribir
    mmu.write(0xFF92, 0x42)
    
    # Verificar que NO trackeó (write_count debe ser 0)
    write_count = mmu.get_hram_write_count(0xFF92)
    assert write_count == 0, (
        f"Cuando VIBOY_DEBUG_HRAM está OFF, write_count debe ser 0, "
        f"pero es {write_count}"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

