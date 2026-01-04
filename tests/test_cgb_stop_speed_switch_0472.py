#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test para Step 0472: Verificación de STOP + KEY1 Speed Switch (CGB).

Este test verifica que la instrucción STOP ejecuta correctamente el speed switch
cuando KEY1 bit0 == 1 (preparado para speed switch).

Fuente: Pan Docs - CGB Registers, KEY1 (FF4D), STOP instruction
https://gbdev.gg8.se/wiki/articles/CGB_Registers#FF4D_-_KEY1_-_CGB_Mode_Only_-_Prepare_Speed_Switch
"""

import pytest
from viboy_core import PyMMU, PyCPU, PyRegisters
from tests.helpers_cpu import load_program, TEST_EXEC_BASE


def test_cgb_stop_speed_switch():
    """
    Verifica que STOP ejecuta speed switch cuando KEY1 bit0 == 1.
    
    Flujo esperado:
    1. Escribir KEY1 = 0x01 (preparar speed switch)
    2. Ejecutar opcode STOP (0x10)
    3. Verificar que KEY1 bit0 == 0 (limpiado)
    4. Verificar que KEY1 bit7 toggled (velocidad cambiada)
    """
    mmu = PyMMU()
    mmu.set_hardware_mode("CGB")
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # Estado inicial: KEY1 = 0x00
    assert mmu.read(0xFF4D) == 0x00, "KEY1 debe iniciar en 0x00"
    
    # Preparar speed switch: escribir KEY1 = 0x01 (bit0 = 1, preparado)
    mmu.write(0xFF4D, 0x01)
    assert mmu.read(0xFF4D) == 0x01, "KEY1 debe ser 0x01 después de escribir"
    
    # Cargar opcode STOP (0x10) en WRAM usando load_program
    load_program(mmu, regs, [0x10])  # STOP opcode
    
    # Ejecutar STOP
    cycles = cpu.step()
    
    # Verificar que STOP se ejecutó (contador incrementado)
    stop_count = cpu.get_stop_executed_count()
    assert stop_count == 1, f"STOP debe haberse ejecutado 1 vez, pero count={stop_count}"
    
    # Verificar que KEY1 bit0 fue limpiado
    key1_after = mmu.read(0xFF4D)
    assert (key1_after & 0x01) == 0x00, f"KEY1 bit0 debe ser 0 después de STOP, pero KEY1=0x{key1_after:02X}"
    
    # Verificar que KEY1 bit7 fue toggled (0x00 -> 0x80 o 0x01 -> 0x81)
    # El bit7 debe cambiar: si era 0x01 (bit7=0), ahora debe ser 0x80 (bit7=1, bit0=0)
    expected_key1 = 0x80  # bit7=1, bit0=0
    assert key1_after == expected_key1, f"KEY1 debe ser 0x{expected_key1:02X} después de speed switch, pero es 0x{key1_after:02X}"
    
    # Verificar que el PC de STOP fue guardado
    last_stop_pc = cpu.get_last_stop_pc()
    assert last_stop_pc == TEST_EXEC_BASE, f"last_stop_pc debe ser 0x{TEST_EXEC_BASE:04X}, pero es 0x{last_stop_pc:04X}"


def test_cgb_stop_normal_when_key1_bit0_not_set():
    """
    Verifica que STOP se comporta normalmente cuando KEY1 bit0 != 1.
    
    Cuando KEY1 bit0 == 0, STOP no debe hacer speed switch.
    """
    mmu = PyMMU()
    mmu.set_hardware_mode("CGB")
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # Estado inicial: KEY1 = 0x00 (bit0 = 0)
    assert mmu.read(0xFF4D) == 0x00, "KEY1 debe iniciar en 0x00"
    
    # Cargar opcode STOP (0x10) en WRAM usando load_program
    load_program(mmu, regs, [0x10])  # STOP opcode
    
    # Ejecutar STOP
    cycles = cpu.step()
    
    # Verificar que STOP se ejecutó (contador incrementado)
    stop_count = cpu.get_stop_executed_count()
    assert stop_count == 1, f"STOP debe haberse ejecutado 1 vez, pero count={stop_count}"
    
    # Verificar que KEY1 NO cambió (no hay speed switch)
    key1_after = mmu.read(0xFF4D)
    assert key1_after == 0x00, f"KEY1 no debe cambiar cuando bit0=0, pero es 0x{key1_after:02X}"


def test_dmg_stop_does_not_affect_key1():
    """
    Verifica que STOP en modo DMG no afecta KEY1 (que no existe en DMG).
    
    En DMG, el registro KEY1 no existe, así que STOP no debe intentar
    acceder a él.
    """
    mmu = PyMMU()
    mmu.set_hardware_mode("DMG")
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    
    # Cargar opcode STOP (0x10) en WRAM usando load_program
    load_program(mmu, regs, [0x10])  # STOP opcode
    
    # Ejecutar STOP
    cycles = cpu.step()
    
    # Verificar que STOP se ejecutó (contador incrementado)
    stop_count = cpu.get_stop_executed_count()
    assert stop_count == 1, f"STOP debe haberse ejecutado 1 vez, pero count={stop_count}"
    
    # En DMG, KEY1 no existe, así que no deberíamos verificar nada relacionado con él
    # Solo verificamos que STOP se ejecutó sin errores


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

