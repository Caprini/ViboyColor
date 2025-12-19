"""
Tests de integración para Instrucciones de Escritura Indirecta en Memoria (CPU C++).

Este módulo prueba las operaciones de escritura indirecta con auto-incremento/decremento:
- LDI (HL), A (0x22): Escribe A en (HL) y luego incrementa HL
- LDD (HL), A (0x32): Escribe A en (HL) y luego decrementa HL
- LD (HL), A (0x77): Escribe A en (HL) sin modificar HL

Estas instrucciones son críticas para operaciones de copia de memoria (memcpy)
y llenado de buffers (memset), especialmente durante la inicialización de VRAM
y el copiado de tiles y datos gráficos.

Fuente: Pan Docs - CPU Instruction Set (LD instructions)
"""

import pytest

# Importar los módulos nativos compilados
try:
    from viboy_core import PyMMU, PyRegisters, PyCPU
except ImportError:
    pytest.skip("Módulo viboy_core no compilado. Ejecuta: python setup.py build_ext --inplace", allow_module_level=True)


class TestLDIndirectWrites:
    """Tests para instrucciones de escritura indirecta en memoria"""

    def test_ldi_hl_a(self):
        """
        Test 1: Verificar LDI (HL), A (0x22).
        
        LDI (HL), A escribe el valor de A en la dirección de memoria apuntada por HL,
        y luego incrementa HL en 1. Es equivalente a:
        - *HL = A; HL++
        
        Esta instrucción es muy común en bucles de copia de memoria:
        ```
        loop:
            LD A, (DE)     ; Leer de origen
            LDI (HL), A    ; Escribir en destino e incrementar HL
            ; ... continuar bucle
        ```
        
        Verificaciones:
        - El valor de A debe estar en la memoria en dirección HL
        - HL debe haberse incrementado en 1
        - PC debe haber avanzado 1 byte (solo el opcode)
        - Debe consumir 2 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        # Inicializar PC
        regs.pc = 0x8000
        
        # Configurar A y HL
        regs.a = 0xBE
        regs.hl = 0xC000
        
        # Escribir opcode en memoria
        mmu.write(0x8000, 0x22)  # LDI (HL), A
        
        # Ejecutar instrucción
        cycles = cpu.step()
        
        # Verificaciones
        assert mmu.read(0xC000) == 0xBE, f"El valor de A (0xBE) debería estar en memoria en 0xC000, pero se encontró 0x{mmu.read(0xC000):02X}"
        assert regs.hl == 0xC001, f"HL debería haberse incrementado a 0xC001, pero es 0x{regs.hl:04X}"
        assert regs.pc == 0x8001, f"PC debería haber avanzado 1 byte a 0x8001, pero es 0x{regs.pc:04X}"
        assert cycles == 2, f"LDI (HL), A debe consumir 2 M-Cycles, pero consumió {cycles}"
    
    def test_ldi_hl_a_wrap_around(self):
        """
        Test 2: Verificar que LDI (HL), A maneja correctamente el wrap-around de HL.
        
        Cuando HL = 0xFFFF y se incrementa, debe envolver a 0x0000.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        regs.a = 0x42
        regs.hl = 0xFFFF  # HL en el límite superior
        
        mmu.write(0x8000, 0x22)  # LDI (HL), A
        
        cycles = cpu.step()
        
        # Verificaciones
        assert mmu.read(0xFFFF) == 0x42, "El valor debería estar en 0xFFFF"
        assert regs.hl == 0x0000, f"HL debería envolver a 0x0000, pero es 0x{regs.hl:04X}"
        assert cycles == 2
    
    def test_ldd_hl_a(self):
        """
        Test 3: Verificar LDD (HL), A (0x32).
        
        LDD (HL), A escribe el valor de A en la dirección de memoria apuntada por HL,
        y luego decrementa HL en 1. Es equivalente a:
        - *HL = A; HL--
        
        Esta instrucción es menos común que LDI, pero se usa en algunos algoritmos
        que copian datos en dirección inversa.
        
        Verificaciones:
        - El valor de A debe estar en la memoria en dirección HL
        - HL debe haberse decrementado en 1
        - PC debe haber avanzado 1 byte
        - Debe consumir 2 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        regs.a = 0x55
        regs.hl = 0xC100
        
        mmu.write(0x8000, 0x32)  # LDD (HL), A
        
        cycles = cpu.step()
        
        # Verificaciones
        assert mmu.read(0xC100) == 0x55, f"El valor de A (0x55) debería estar en memoria en 0xC100, pero se encontró 0x{mmu.read(0xC100):02X}"
        assert regs.hl == 0xC0FF, f"HL debería haberse decrementado a 0xC0FF, pero es 0x{regs.hl:04X}"
        assert regs.pc == 0x8001, f"PC debería haber avanzado 1 byte a 0x8001, pero es 0x{regs.pc:04X}"
        assert cycles == 2, f"LDD (HL), A debe consumir 2 M-Cycles, pero consumió {cycles}"
    
    def test_ldd_hl_a_wrap_around(self):
        """
        Test 4: Verificar que LDD (HL), A maneja correctamente el wrap-around de HL.
        
        Cuando HL = 0x0000 y se decrementa, debe envolver a 0xFFFF.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        regs.a = 0x99
        regs.hl = 0x0000  # HL en el límite inferior
        
        mmu.write(0x8000, 0x32)  # LDD (HL), A
        
        cycles = cpu.step()
        
        # Verificaciones
        assert mmu.read(0x0000) == 0x99, "El valor debería estar en 0x0000"
        assert regs.hl == 0xFFFF, f"HL debería envolver a 0xFFFF, pero es 0x{regs.hl:04X}"
        assert cycles == 2
    
    def test_ld_hl_a(self):
        """
        Test 5: Verificar LD (HL), A (0x77).
        
        LD (HL), A escribe el valor de A en la dirección de memoria apuntada por HL,
        pero NO modifica HL. Es equivalente a:
        - *HL = A
        
        Esta es la instrucción más común para escribir en memoria indirecta.
        A diferencia de LDI/LDD, no modifica el puntero, lo que es útil cuando
        se quiere escribir en una dirección fija.
        
        Verificaciones:
        - El valor de A debe estar en la memoria en dirección HL
        - HL NO debe modificarse
        - PC debe haber avanzado 1 byte
        - Debe consumir 2 M-Cycles
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        regs.a = 0xAA
        regs.hl = 0xD000
        
        mmu.write(0x8000, 0x77)  # LD (HL), A
        
        cycles = cpu.step()
        
        # Verificaciones
        assert mmu.read(0xD000) == 0xAA, f"El valor de A (0xAA) debería estar en memoria en 0xD000, pero se encontró 0x{mmu.read(0xD000):02X}"
        assert regs.hl == 0xD000, f"HL NO debería haberse modificado (0xD000), pero es 0x{regs.hl:04X}"
        assert regs.pc == 0x8001, f"PC debería haber avanzado 1 byte a 0x8001, pero es 0x{regs.pc:04X}"
        assert cycles == 2, f"LD (HL), A debe consumir 2 M-Cycles, pero consumió {cycles}"
    
    def test_ldi_sequence(self):
        """
        Test 6: Verificar una secuencia de LDI (HL), A para simular un bucle de copia.
        
        Este test simula un bucle típico de copia de memoria que usa LDI:
        ```
        loop:
            LD A, (DE)
            LDI (HL), A
            ; ... verificar si continuar
        ```
        
        Verificamos que múltiples ejecuciones de LDI funcionan correctamente
        en secuencia, escribiendo datos consecutivos en memoria.
        """
        mmu = PyMMU()
        regs = PyRegisters()
        cpu = PyCPU(mmu, regs)
        
        regs.pc = 0x8000
        regs.hl = 0xC000
        
        # Escribir secuencia de instrucciones LDI (HL), A con diferentes valores de A
        # En un caso real, A cambiaría entre instrucciones, pero para este test
        # lo simularemos ejecutando múltiples LDI con A cambiado manualmente
        
        # Primera escritura
        regs.a = 0x11
        mmu.write(0x8000, 0x22)  # LDI (HL), A
        cycles1 = cpu.step()
        
        assert mmu.read(0xC000) == 0x11
        assert regs.hl == 0xC001
        assert cycles1 == 2
        
        # Segunda escritura (HL ya está en 0xC001)
        regs.a = 0x22
        mmu.write(0x8001, 0x22)  # LDI (HL), A
        cycles2 = cpu.step()
        
        assert mmu.read(0xC001) == 0x22
        assert regs.hl == 0xC002
        assert cycles2 == 2
        
        # Tercera escritura (HL ya está en 0xC002)
        regs.a = 0x33
        mmu.write(0x8002, 0x22)  # LDI (HL), A
        cycles3 = cpu.step()
        
        assert mmu.read(0xC002) == 0x33
        assert regs.hl == 0xC003
        assert cycles3 == 2

