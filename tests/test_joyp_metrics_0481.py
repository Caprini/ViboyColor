#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Step 0481: Verificar métricas completas de JOYP (reads/writes).

Este test valida que el tracking de JOYP funciona correctamente:
- write() incrementa contadores y registra PC/valor
- read() incrementa contadores de lectura desde programa (no cpu_poll)
- Getters devuelven valores correctos

Fuente: Step 0481 - Fase C1
"""

import pytest
from viboy_core import PyMMU, PyPPU, PyTimer, PyJoypad, PyCPU, PyRegisters


def test_joyp_write_tracking():
    """
    Verifica que el tracking de writes a JOYP funciona correctamente.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/Joypad)
    2. Establecer PC para tracking
    3. Escribir JOYP = 0x20 (P15=1, seleccionar botones)
    4. Verificar:
       - get_joyp_last_write_pc() != 0
       - get_joyp_last_write_value() == 0x20
       - get_joyp_write_count() >= 1
    
    Criterio de éxito: Test pasa.
    """
    # Inicializar componentes
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    # Wiring
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Establecer PC para tracking usando instrucción real
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    cpu.set_ppu(ppu)
    cpu.set_timer(timer)
    regs.pc = 0x1500
    mmu.write(0x1500, 0x00)  # NOP
    cpu.step()  # Ejecutar NOP para actualizar debug_current_pc a 0x1501
    
    # Escribir JOYP = 0x20 (P15=1, seleccionar botones)
    write_value = 0x20
    mmu.write(0xFF00, write_value)
    
    # Verificar contadores
    last_write_pc = mmu.get_last_joyp_write_pc()
    assert last_write_pc != 0, (
        f"get_last_joyp_write_pc() no debe ser 0, "
        f"pero es {last_write_pc:04X}"
    )
    
    last_write_value = mmu.get_last_joyp_write_value()
    assert last_write_value == write_value, (
        f"get_last_joyp_write_value() debe ser 0x{write_value:02X}, "
        f"pero es 0x{last_write_value:02X}"
    )
    
    write_count = mmu.get_joyp_write_count()
    assert write_count >= 1, (
        f"get_joyp_write_count() debe ser >= 1, "
        f"pero es {write_count}"
    )


def test_joyp_read_tracking():
    """
    Verifica que el tracking de reads de JOYP funciona correctamente.
    
    Pasos:
    1. Inicializar sistema mínimo (MMU/Joypad)
    2. Establecer PC para tracking y asegurar que NO estamos en irq_poll
    3. Leer JOYP: value = mmu.read(0xFF00)
    4. Verificar:
       - get_joyp_read_count_program() > 0
       - get_last_joyp_read_pc() != 0
       - get_last_joyp_read_value() == value
    
    Criterio de éxito: Test pasa.
    """
    # Inicializar componentes
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    # Wiring
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    # Asegurar que NO estamos en irq_poll (estado por defecto debe ser False)
    mmu.set_irq_poll_active(False)
    
    # Establecer PC para tracking usando instrucción real
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    cpu.set_ppu(ppu)
    cpu.set_timer(timer)
    regs.pc = 0x2500
    mmu.write(0x2500, 0x00)  # NOP
    cpu.step()  # Ejecutar NOP para actualizar debug_current_pc a 0x2501
    
    # Leer JOYP
    read_value = mmu.read(0xFF00)
    
    # Verificar contadores
    read_count = mmu.get_joyp_read_count_program()
    assert read_count > 0, (
        f"get_joyp_read_count_program() debe ser > 0 después de leer, "
        f"pero es {read_count}"
    )
    
    last_read_pc = mmu.get_last_joyp_read_pc()
    assert last_read_pc != 0, (
        f"get_last_joyp_read_pc() no debe ser 0, "
        f"pero es {last_read_pc:04X}"
    )
    
    last_read_value = mmu.get_last_joyp_read_value()
    assert last_read_value == read_value, (
        f"get_last_joyp_read_value() debe ser igual al valor leído (0x{read_value:02X}), "
        f"pero es 0x{last_read_value:02X}"
    )


def test_joyp_read_not_counted_during_irq_poll():
    """
    Verifica que reads de JOYP durante irq_poll NO se cuentan en read_count_program.
    
    Pasos:
    1. Inicializar sistema
    2. Obtener contador inicial (puede haber lecturas previas durante init)
    3. Leer JOYP normalmente (debe contar)
    4. Activar irq_poll: set_irq_poll_active(True)
    5. Leer JOYP de nuevo (NO debe contar)
    6. Desactivar irq_poll: set_irq_poll_active(False)
    7. Leer JOYP de nuevo (debe contar)
    8. Verificar que read_count_program aumentó en 2 (solo las lecturas fuera de irq_poll)
    """
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    mmu.set_irq_poll_active(False)
    
    # Obtener contador inicial (puede haber lecturas durante init)
    count_initial = mmu.get_joyp_read_count_program()
    
    # Establecer PC usando instrucciones reales
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    cpu.set_ppu(ppu)
    cpu.set_timer(timer)
    
    # Primera lectura (fuera de irq_poll, debe contar)
    regs.pc = 0x3000
    mmu.write(0x3000, 0x00)  # NOP
    cpu.step()  # PC ahora es 0x3001
    # Asegurar que NO estamos en irq_poll
    mmu.set_irq_poll_active(False)
    mmu.read(0xFF00)
    count_1 = mmu.get_joyp_read_count_program()
    assert count_1 > count_initial, (
        f"Primera lectura debe incrementar contador de {count_initial}, "
        f"pero count={count_1}"
    )
    increment_1 = count_1 - count_initial
    assert increment_1 >= 1, (
        f"Primera lectura debe incrementar contador al menos en 1, "
        f"pero increment={increment_1}"
    )
    
    # Segunda lectura (durante irq_poll, NO debe contar)
    mmu.set_irq_poll_active(True)  # ACTIVAR irq_poll
    regs.pc = 0x3001
    mmu.write(0x3001, 0x00)  # NOP
    cpu.step()  # PC ahora es 0x3002
    mmu.read(0xFF00)  # Esta lectura NO debe contar
    count_2 = mmu.get_joyp_read_count_program()
    assert count_2 == count_1, (
        f"Lectura durante irq_poll NO debe contar: count={count_2} "
        f"(debe seguir siendo {count_1}, increment={count_2 - count_1})"
    )
    
    # Tercera lectura (fuera de irq_poll, debe contar)
    mmu.set_irq_poll_active(False)  # DESACTIVAR irq_poll
    regs.pc = 0x3002
    mmu.write(0x3002, 0x00)  # NOP
    cpu.step()  # PC ahora es 0x3003
    mmu.read(0xFF00)  # Esta lectura SÍ debe contar
    count_3 = mmu.get_joyp_read_count_program()
    assert count_3 == count_1 + 1, (
        f"Segunda lectura fuera de irq_poll debe incrementar contador: count={count_3} "
        f"(debe ser {count_1 + 1}, increment={count_3 - count_1})"
    )


def test_joyp_write_read_sequence():
    """
    Verifica una secuencia completa write-read de JOYP.
    
    Pasos:
    1. Escribir JOYP = 0x10 (P14=1, seleccionar direcciones)
    2. Leer JOYP (debe reflejar el selector escrito)
    3. Verificar que ambos tracking funcionan correctamente
    """
    mmu = PyMMU()
    ppu = PyPPU(mmu)
    timer = PyTimer(mmu)
    joypad = PyJoypad()
    
    mmu.set_ppu(ppu)
    mmu.set_timer(timer)
    mmu.set_joypad(joypad)
    
    mmu.set_irq_poll_active(False)
    
    # Establecer PC usando instrucciones reales
    regs = PyRegisters()
    cpu = PyCPU(mmu, regs)
    cpu.set_ppu(ppu)
    cpu.set_timer(timer)
    
    # Escribir selector de direcciones
    regs.pc = 0x4000
    mmu.write(0x4000, 0x00)  # NOP
    cpu.step()  # PC ahora es 0x4001
    mmu.write(0xFF00, 0x10)
    
    # Verificar write tracking
    assert mmu.get_last_joyp_write_value() == 0x10
    assert mmu.get_last_joyp_write_pc() != 0
    
    # Leer JOYP
    regs.pc = 0x4001
    mmu.write(0x4001, 0x00)  # NOP
    cpu.step()  # PC ahora es 0x4002
    read_value = mmu.read(0xFF00)
    
    # Verificar read tracking
    assert mmu.get_joyp_read_count_program() > 0
    assert mmu.get_last_joyp_read_pc() != 0
    assert mmu.get_last_joyp_read_value() == read_value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

