#ifndef NATIVE_CORE_HPP
#define NATIVE_CORE_HPP

/**
 * NativeCore - Clase base del núcleo de emulación en C++.
 * 
 * Esta es una prueba de concepto para verificar que el pipeline
 * de compilación Python -> Cython -> C++ funciona correctamente.
 * 
 * En la Fase 2, esta clase será expandida para contener la lógica
 * de emulación ciclo a ciclo del Game Boy.
 */
class NativeCore {
public:
    /**
     * Constructor por defecto.
     */
    NativeCore();

    /**
     * Destructor.
     */
    ~NativeCore();

    /**
     * Método de prueba: suma dos enteros.
     * 
     * @param a Primer operando
     * @param b Segundo operando
     * @return Suma de a + b
     */
    int add(int a, int b) const;
};

#endif // NATIVE_CORE_HPP

