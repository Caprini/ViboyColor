---
name: Bug Report / Reporte de Bug
about: Create a report to help us improve / Crear un reporte para ayudarnos a mejorar
title: '[BUG] '
labels: bug
assignees: ''
---

## ⚠️ Compilation Check / Verificación de Compilación (REQUIRED - READ THIS FIRST / OBLIGATORIO - LEE ESTO PRIMERO)

**Before reporting a bug, you MUST verify that the C++ core is compiled correctly. / Antes de reportar un bug, DEBES verificar que el núcleo C++ esté compilado correctamente.**

**Did you run `python test_build.py`? What was the output? / ¿Ejecutaste `python test_build.py`? ¿Cuál fue la salida?**

```
[Paste the FULL output of `python test_build.py` here / Pega la salida COMPLETA de `python test_build.py` aquí]
```

**⚠️ If `python test_build.py` failed, DO NOT open a bug report. / Si `python test_build.py` falló, NO abras un reporte de bug.**
- Check `CONTRIBUTING.md` for compilation instructions / Revisa `CONTRIBUTING.md` para instrucciones de compilación
- Verify you have a C++ compiler installed (Visual Studio Build Tools on Windows, GCC/Clang on Linux/macOS) / Verifica que tengas un compilador C++ instalado (Visual Studio Build Tools en Windows, GCC/Clang en Linux/macOS)
- Ensure Cython is installed: `pip install cython` / Asegúrate de que Cython esté instalado: `pip install cython`

**If the build test passed, continue with the bug report below. / Si la prueba de compilación pasó, continúa con el reporte de bug abajo.**

---

## 🐛 Bug Description / Descripción del Bug

A clear and concise description of what the bug is. / Una descripción clara y concisa de qué es el bug.

---

## 🔄 Steps to Reproduce / Pasos para Reproducir

1. ROM Name / Nombre de ROM: `[ROM name here - NO LINKS, NO FILE UPLOADS / nombre de ROM aquí - SIN ENLACES, SIN SUBIR ARCHIVOS]`
2. ROM MD5 (optional but helpful / opcional pero útil): `[MD5 hash if available / hash MD5 si está disponible]`
3. Steps to reproduce / Pasos para reproducir:
   ```
   1. ...
   2. ...
   3. ...
   ```

---

## ✅ Expected Behavior / Comportamiento Esperado

A clear and concise description of what you expected to happen. / Una descripción clara y concisa de lo que esperabas que sucediera.

---

## ❌ Actual Behavior / Comportamiento Actual

A clear and concise description of what actually happened. / Una descripción clara y concisa de lo que realmente sucedió.

---

## 📸 Screenshots/Visual Evidence / Capturas de Pantalla/Evidencia Visual

If applicable, add screenshots or visual evidence of the bug. / Si aplica, añade capturas de pantalla o evidencia visual del bug.

---

## 💻 Environment / Entorno

Please provide the following information / Por favor proporciona la siguiente información:

- **OS / SO**: [e.g., Windows 11, Ubuntu 22.04, macOS 14.0]
- **Python Version / Versión de Python**: [e.g., Python 3.11.5]
- **C++ Compiler / Compilador C++**: [e.g., Visual Studio 2022, GCC 11.4, Clang 15.0]
- **Viboy Color Version / Versión de Viboy Color**: [e.g., v0.0.2-dev, commit hash if from source / hash de commit si es desde fuente]

---

## 📋 Logs

If applicable, attach relevant logs / Si aplica, adjunta logs relevantes:

**CPU Trace (if enabled) / Traza de CPU (si está habilitada):**
```
[Paste CPU trace logs here / Pega logs de traza de CPU aquí]
```

**Error Messages / Mensajes de Error:**
```
[Paste error messages here / Pega mensajes de error aquí]
```

**Console Output / Salida de Consola:**
```
[Paste console output here / Pega salida de consola aquí]
```

---

## 🔍 Additional Context / Contexto Adicional

Add any other context about the problem here. / Añade cualquier otro contexto sobre el problema aquí.

---

## ✅ Checklist

- [ ] I have run `python test_build.py` and it **passed** / Ejecuté `python test_build.py` y **pasó**
- [ ] I have read `CONTRIBUTING.md` / He leído `CONTRIBUTING.md`
- [ ] I have checked existing issues to see if this bug was already reported / He revisado issues existentes para ver si este bug ya fue reportado
- [ ] I have provided all required information above / He proporcionado toda la información requerida arriba
