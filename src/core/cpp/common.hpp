#ifndef VIBOY_COMMON_HPP
#define VIBOY_COMMON_HPP

#include <cstdlib>
#include <string>

/**
 * Step 0461: Kill-switch global para debug injections.
 * 
 * Por defecto: OFF en runtime normal.
 * Solo activar si VIBOY_DEBUG_INJECTION=1 explícitamente.
 * 
 * Esto previene que patrones de test (checkerboard, etc.) interfieran
 * con el output del emulador durante análisis visual o tests.
 */
inline bool is_debug_injection_enabled() {
    const char* env = std::getenv("VIBOY_DEBUG_INJECTION");
    return (env != nullptr && std::string(env) == "1");
}

#endif // VIBOY_COMMON_HPP

