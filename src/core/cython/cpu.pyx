# distutils: language = c++

"""
Wrapper Cython para CPU (Procesador LR35902).

Este módulo expone la clase C++ CPU a Python, permitiendo
ejecutar el ciclo de instrucción en código nativo de alta velocidad.
"""

from libc.stdint cimport uint8_t, uint16_t, uint32_t

# Importar las definiciones C++
cimport cpu
cimport mmu
cimport registers

# NOTA: PyMMU y PyRegisters están definidos en mmu.pyx y registers.pyx,
# que están incluidos en native_core.pyx. Los métodos get_c_mmu() y get_c_regs()
# son cpdef, por lo que son accesibles desde aquí.

cdef class PyCPU:
    """
    Wrapper Python para CPU.
    
    Esta clase permite usar CPU desde Python manteniendo
    el rendimiento de C++ (ciclo de instrucción nativo).
    
    Utiliza inyección de dependencias: recibe PyMMU y PyRegisters
    y extrae los punteros C++ subyacentes.
    """
    cdef cpu.CPU* _cpu
    
    def __cinit__(self, PyMMU mmu, PyRegisters regs):
        """
        Constructor: crea la instancia C++ con punteros a MMU y Registros.
        
        Args:
            mmu: Instancia de PyMMU (wrapper de MMU)
            regs: Instancia de PyRegisters (wrapper de CoreRegisters)
        """
        # Extraer los punteros C++ subyacentes directamente
        # Como mmu.pyx y registers.pyx están incluidos en native_core.pyx,
        # podemos acceder a los miembros privados _mmu y _regs
        self._cpu = new cpu.CPU(mmu._mmu, regs._regs)
    
    def __dealloc__(self):
        """Destructor: libera la memoria C++."""
        if self._cpu != NULL:
            del self._cpu
    
    def step(self) -> int:
        """
        Ejecuta un ciclo de instrucción (Fetch-Decode-Execute).
        
        Returns:
            Número de M-Cycles consumidos (0 si hay error)
        """
        return self._cpu.step()
    
    def get_cycles(self) -> int:
        """
        Obtiene el contador de ciclos acumulados.
        
        Returns:
            Total de M-Cycles ejecutados desde la creación
        """
        return self._cpu.get_cycles()

