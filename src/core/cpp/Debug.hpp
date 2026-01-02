/**
 * Debug.hpp - Configuración centralizada de instrumentación de debug
 * 
 * Este archivo controla TODA la instrumentación de debug del core C++.
 * Por defecto, TODA la instrumentación está DESACTIVADA en producción.
 * 
 * Para activar debug:
 * - Compilar con -DVIBOY_DEBUG_ENABLED
 * - O descomentar la línea #define VIBOY_DEBUG_ENABLED abajo
 * 
 * Basado en: Clean Room Development + Zero-Cost Abstractions
 * Autor: Viboy Color Team
 * Licencia: MIT
 */

#ifndef VIBOY_DEBUG_HPP
#define VIBOY_DEBUG_HPP

// ============================================================================
// CONFIGURACIÓN GLOBAL DE DEBUG
// ============================================================================

// Descomentar la siguiente línea para activar TODA la instrumentación de debug
// #define VIBOY_DEBUG_ENABLED

// ============================================================================
// MACROS DE DEBUG CONDICIONAL
// ============================================================================

#ifdef VIBOY_DEBUG_ENABLED
    #include <cstdio>
    
    // Macro para printf condicional (solo si debug está activado)
    #define VIBOY_DEBUG_PRINTF(...) printf(__VA_ARGS__)
    
    // Macro para bloques de código de debug
    #define VIBOY_DEBUG_BLOCK(code) do { code } while(0)
    
#else
    // En producción: macros vacías (zero-cost)
    #define VIBOY_DEBUG_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_BLOCK(code) ((void)0)
#endif

// ============================================================================
// CATEGORÍAS DE DEBUG (para control granular)
// ============================================================================

// Descomentar las categorías específicas que quieras activar
// (solo tienen efecto si VIBOY_DEBUG_ENABLED está activado)

// #define VIBOY_DEBUG_PPU_TIMING      // Timing de PPU (step, scanlines)
// #define VIBOY_DEBUG_PPU_RENDER      // Renderizado de PPU (tiles, sprites)
// #define VIBOY_DEBUG_PPU_VRAM        // Estado de VRAM
// #define VIBOY_DEBUG_PPU_LCD         // Cambios de LCD/LCDC
// #define VIBOY_DEBUG_PPU_STAT        // Interrupciones STAT
// #define VIBOY_DEBUG_PPU_FRAMEBUFFER // Estado del framebuffer
// #define VIBOY_DEBUG_CPU_EXEC        // Ejecución de CPU
// #define VIBOY_DEBUG_MMU_ACCESS      // Accesos a memoria

// ============================================================================
// MACROS DE DEBUG POR CATEGORÍA
// ============================================================================

#ifdef VIBOY_DEBUG_ENABLED

    #ifdef VIBOY_DEBUG_PPU_TIMING
        #define VIBOY_DEBUG_PPU_TIMING_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_TIMING_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_PPU_RENDER
        #define VIBOY_DEBUG_PPU_RENDER_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_RENDER_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_PPU_VRAM
        #define VIBOY_DEBUG_PPU_VRAM_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_VRAM_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_PPU_LCD
        #define VIBOY_DEBUG_PPU_LCD_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_LCD_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_PPU_STAT
        #define VIBOY_DEBUG_PPU_STAT_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_STAT_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_PPU_FRAMEBUFFER
        #define VIBOY_DEBUG_PPU_FRAMEBUFFER_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_PPU_FRAMEBUFFER_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_CPU_EXEC
        #define VIBOY_DEBUG_CPU_EXEC_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_CPU_EXEC_PRINTF(...) ((void)0)
    #endif

    #ifdef VIBOY_DEBUG_MMU_ACCESS
        #define VIBOY_DEBUG_MMU_ACCESS_PRINTF(...) printf(__VA_ARGS__)
    #else
        #define VIBOY_DEBUG_MMU_ACCESS_PRINTF(...) ((void)0)
    #endif

#else
    // En producción: todas las macros de categoría son vacías
    #define VIBOY_DEBUG_PPU_TIMING_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_PPU_RENDER_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_PPU_VRAM_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_PPU_LCD_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_PPU_STAT_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_PPU_FRAMEBUFFER_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_CPU_EXEC_PRINTF(...) ((void)0)
    #define VIBOY_DEBUG_MMU_ACCESS_PRINTF(...) ((void)0)
#endif

// ============================================================================
// GETTERS DE DEBUG (solo disponibles si VIBOY_DEBUG_ENABLED está activado)
// ============================================================================

// Estos getters NO deben usarse en producción, solo para tests/diagnóstico
// Se declaran aquí para documentar su propósito

// Ejemplo de uso en clases:
// #ifdef VIBOY_DEBUG_ENABLED
//     uint32_t get_debug_clock() const { return clock_; }
//     uint8_t get_debug_ly() const { return ly_; }
// #endif

#endif // VIBOY_DEBUG_HPP

