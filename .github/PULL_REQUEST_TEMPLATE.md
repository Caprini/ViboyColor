# Pull Request

## 📝 Description / Descripción

A clear and concise description of what this PR does and why. / Una descripción clara y concisa de qué hace este PR y por qué.

**Type of change / Tipo de cambio:**
- [ ] New feature (opcode, hardware component, etc.) / Nueva funcionalidad (opcode, componente de hardware, etc.)
- [ ] Bug fix / Corrección de bug
- [ ] Documentation update / Actualización de documentación
- [ ] Performance optimization / Optimización de rendimiento
- [ ] Code refactoring / Refactorización de código
- [ ] Test addition/improvement / Adición/mejora de tests

---

## 🔍 What Changed? / ¿Qué Cambió?

### Files Modified / Archivos Modificados
- `[list files changed / lista archivos cambiados]`

### Implementation Details / Detalles de Implementación
- [Describe what you implemented and why / Describe qué implementaste y por qué]

### Documentation References / Referencias de Documentación
- [If you referenced Pan Docs, GBEDG, or hardware manuals, include links here / Si referenciaste Pan Docs, GBEDG o manuales de hardware, incluye enlaces aquí]

---

## ✅ Pre-Submission Checklist / Checklist Pre-Envío

**Before submitting this PR, please verify / Antes de enviar este PR, por favor verifica:**

- [ ] I have read `CONTRIBUTING.md` thoroughly / He leído `CONTRIBUTING.md` completamente
- [ ] I strictly followed the **Clean Room Policy** (No copied code from other emulators) / Seguí estrictamente la **Política Clean Room** (Sin código copiado de otros emuladores)
- [ ] I have added unit tests for new features/opcodes / He añadido tests unitarios para nuevas funcionalidades/opcodes
- [ ] `python test_build.py` passes locally / `python test_build.py` pasa localmente
- [ ] `pytest` passes locally (all tests) / `pytest` pasa localmente (todos los tests)
- [ ] I have updated documentation if needed (docstrings, `docs/bitacora/`, etc.) / He actualizado la documentación si fue necesario (docstrings, `docs/bitacora/`, etc.)
- [ ] My code follows the project's style guidelines / Mi código sigue las guías de estilo del proyecto:
  - [ ] Python: PEP 8 compliant / Python: Cumple PEP 8
  - [ ] C++: Google C++ Style Guide (or consistent style) / C++: Google C++ Style Guide (o estilo consistente)
  - [ ] Cython: Proper type annotations and memory management / Cython: Anotaciones de tipo apropiadas y gestión de memoria

---

## 🧪 Testing / Pruebas

**How did you test this change? / ¿Cómo probaste este cambio?**

- [ ] Added new unit tests / Añadí nuevos tests unitarios: `[test file names / nombres de archivos de test]`
- [ ] Ran existing test suite / Ejecuté la suite de tests existente: `pytest` (all passing / todos pasando)
- [ ] Tested with ROM / Probé con ROM: `[ROM name - NO LINKS / nombre de ROM - SIN ENLACES]`
- [ ] Verified build / Verifiqué la compilación: `python test_build.py` (passed / pasó)

**Test Results / Resultados de Tests:**
```
[Paste pytest output here if relevant / Pega salida de pytest aquí si es relevante]
```

---

## 📸 Screenshots/Evidence (if applicable) / Capturas de Pantalla/Evidencia (si aplica)

If this PR affects visual output or behavior, include screenshots or evidence. / Si este PR afecta la salida visual o el comportamiento, incluye capturas de pantalla o evidencia.

---

## 🔗 Related Issues / Issues Relacionados

Closes #[issue number]

---

## 📚 Additional Context / Contexto Adicional

Add any other context about the PR here. / Añade cualquier otro contexto sobre el PR aquí.

**Important Notes / Notas Importantes:**
- If this implements a new opcode, explain which ROM requires it / Si esto implementa un nuevo opcode, explica qué ROM lo requiere
- If this is a bug fix, include reproduction steps and the fix explanation / Si esto es una corrección de bug, incluye pasos de reproducción y la explicación de la corrección
- If this touches C++ code, explain any performance considerations / Si esto toca código C++, explica cualquier consideración de rendimiento

---

## ⚠️ Clean Room Compliance / Cumplimiento Clean Room

**By submitting this PR, I confirm / Al enviar este PR, confirmo:**

- [ ] I did NOT copy code from other emulators (mGBA, SameBoy, Gambatte, etc.) / NO copié código de otros emuladores (mGBA, SameBoy, Gambatte, etc.)
- [ ] I implemented this feature based on official documentation (Pan Docs, GBEDG, hardware manuals) / Implementé esta funcionalidad basándome en documentación oficial (Pan Docs, GBEDG, manuales de hardware)
- [ ] I understand the hardware behavior I'm implementing / Entiendo el comportamiento del hardware que estoy implementando
- [ ] All code is original work or properly attributed / Todo el código es trabajo original o está apropiadamente atribuido

---

## 🙏 Review Notes / Notas para Revisión

Any specific areas you'd like reviewers to focus on? / ¿Alguna área específica en la que te gustaría que los revisores se enfoquen?
