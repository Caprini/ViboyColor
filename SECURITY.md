# Security Policy

**[ 🇬🇧 English ](#security-policy) | [ 🇪🇸 Español ](#política-de-seguridad)**

---

# Security Policy

## Supported Versions

This is an **educational project** currently in development (v0.0.2-dev). The project is not intended for production use and should be run locally for educational purposes only.

| Version | Supported          |
| ------- | ------------------ |
| v0.0.2-dev | :white_check_mark: |
| v0.0.1   | :x: (Archived)     |

## Security Considerations

**Important**: This is an educational project running locally. Security vulnerabilities usually imply crashing the emulator stack or unexpected behavior during emulation. This project is not designed to be exposed to the internet or used in production environments.

### What Constitutes a Security Issue

Security issues in this context include:

- **Stack overflows** or memory corruption that could crash the host system
- **Buffer overflows** in C++ code that could lead to arbitrary code execution
- **Resource exhaustion** (memory leaks, infinite loops) that could freeze the system
- **File system access** vulnerabilities (unauthorized file reading/writing)
- **Code injection** risks in the Python-C++ bridge (Cython)

### What Does NOT Constitute a Security Issue

The following are **not** considered security issues and should be reported as regular bugs:

- Game Boy ROMs not loading correctly
- Emulation accuracy issues (incorrect CPU behavior, graphics glitches)
- Performance problems (slow emulation, frame drops)
- Build/compilation errors
- Test failures

## Reporting a Vulnerability

If you discover a security vulnerability, please report it via **GitHub Issues** using the **'Bug'** label.

### How to Report

1. **Create a new GitHub Issue** with the `Bug` label
2. **Title**: Use a clear, descriptive title (e.g., "Security: Buffer overflow in CPU.cpp")
3. **Description**: Include:
   - A clear description of the vulnerability
   - Steps to reproduce (if applicable)
   - Potential impact
   - Suggested fix (if you have one)
4. **Do NOT** create a public pull request for security vulnerabilities until they are addressed

### Response Time

As this is an educational project maintained by volunteers, response times may vary. We will do our best to:

- Acknowledge the report within 7 days
- Provide an initial assessment within 14 days
- Keep you informed of the progress

## Security Best Practices for Contributors

When contributing code, especially C++ components:

- **Avoid raw pointers** when possible; use smart pointers (`std::unique_ptr`, `std::shared_ptr`)
- **Validate bounds** before array/vector access
- **Use RAII** for resource management
- **Avoid `new/delete`** in favor of containers and smart pointers
- **Test memory safety** with tools like Valgrind or AddressSanitizer
- **Document assumptions** about buffer sizes and memory layouts

## Disclaimer

**This project is provided "as is" for educational purposes only. Do not use this project in production environments exposed to the internet.**

The maintainers are not responsible for any damage or security issues that may arise from using this software. Users should exercise caution when running any emulator software, especially when loading untrusted ROM files.

---

# Política de Seguridad

## Versiones Soportadas

Este es un **proyecto educativo** actualmente en desarrollo (v0.0.2-dev). El proyecto no está destinado para uso en producción y debe ejecutarse localmente solo con fines educativos.

| Versión | Soportada          |
| ------- | ------------------ |
| v0.0.2-dev | :white_check_mark: |
| v0.0.1   | :x: (Archivada)     |

## Consideraciones de Seguridad

**Importante**: Este es un proyecto educativo que se ejecuta localmente. Las vulnerabilidades de seguridad generalmente implican crasheos del stack del emulador o comportamiento inesperado durante la emulación. Este proyecto no está diseñado para estar expuesto a internet o usarse en entornos de producción.

### Qué Constituye un Problema de Seguridad

Los problemas de seguridad en este contexto incluyen:

- **Desbordamientos de pila** o corrupción de memoria que podrían crashear el sistema host
- **Desbordamientos de buffer** en código C++ que podrían llevar a ejecución arbitraria de código
- **Agotamiento de recursos** (fugas de memoria, bucles infinitos) que podrían congelar el sistema
- **Vulnerabilidades de acceso al sistema de archivos** (lectura/escritura no autorizada de archivos)
- **Riesgos de inyección de código** en el puente Python-C++ (Cython)

### Qué NO Constituye un Problema de Seguridad

Lo siguiente **no** se considera un problema de seguridad y debe reportarse como bugs regulares:

- ROMs de Game Boy que no cargan correctamente
- Problemas de precisión de emulación (comportamiento incorrecto de CPU, glitches gráficos)
- Problemas de rendimiento (emulación lenta, caídas de frames)
- Errores de compilación/build
- Fallos de tests

## Reportar una Vulnerabilidad

Si descubres una vulnerabilidad de seguridad, por favor repórtala vía **GitHub Issues** usando la etiqueta **'Bug'**.

### Cómo Reportar

1. **Crea un nuevo GitHub Issue** con la etiqueta `Bug`
2. **Título**: Usa un título claro y descriptivo (ej: "Security: Buffer overflow en CPU.cpp")
3. **Descripción**: Incluye:
   - Una descripción clara de la vulnerabilidad
   - Pasos para reproducir (si aplica)
   - Impacto potencial
   - Corrección sugerida (si tienes una)
4. **NO** crees un pull request público para vulnerabilidades de seguridad hasta que sean abordadas

### Tiempo de Respuesta

Como este es un proyecto educativo mantenido por voluntarios, los tiempos de respuesta pueden variar. Haremos nuestro mejor esfuerzo para:

- Reconocer el reporte dentro de 7 días
- Proporcionar una evaluación inicial dentro de 14 días
- Mantenerte informado del progreso

## Mejores Prácticas de Seguridad para Contribuidores

Al contribuir código, especialmente componentes C++:

- **Evita punteros crudos** cuando sea posible; usa smart pointers (`std::unique_ptr`, `std::shared_ptr`)
- **Valida límites** antes de acceder a arrays/vectores
- **Usa RAII** para gestión de recursos
- **Evita `new/delete`** en favor de contenedores y smart pointers
- **Prueba la seguridad de memoria** con herramientas como Valgrind o AddressSanitizer
- **Documenta suposiciones** sobre tamaños de buffers y layouts de memoria

## Descargo de Responsabilidad

**Este proyecto se proporciona "tal cual" solo con fines educativos. No uses este proyecto en entornos de producción expuestos a internet.**

Los mantenedores no son responsables de ningún daño o problema de seguridad que pueda surgir del uso de este software. Los usuarios deben tener precaución al ejecutar cualquier software emulador, especialmente al cargar archivos ROM no confiables.
