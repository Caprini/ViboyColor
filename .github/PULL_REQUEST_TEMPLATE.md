# Pull Request

## 📝 Description

A clear and concise description of what this PR does and why.

**Type of change:**
- [ ] New feature (opcode, hardware component, etc.)
- [ ] Bug fix
- [ ] Documentation update
- [ ] Performance optimization
- [ ] Code refactoring
- [ ] Test addition/improvement

---

## 🔍 What Changed?

### Files Modified
- `[list files changed]`

### Implementation Details
- [Describe what you implemented and why]

### Documentation References
- [If you referenced Pan Docs, GBEDG, or hardware manuals, include links here]

---

## ✅ Pre-Submission Checklist

**Before submitting this PR, please verify:**

- [ ] I have read `CONTRIBUTING.md` thoroughly
- [ ] I strictly followed the **Clean Room Policy** (No copied code from other emulators)
- [ ] I have added unit tests for new features/opcodes
- [ ] `python test_build.py` passes locally
- [ ] `pytest` passes locally (all tests)
- [ ] I have updated documentation if needed (docstrings, `docs/bitacora/`, etc.)
- [ ] My code follows the project's style guidelines:
  - [ ] Python: PEP 8 compliant
  - [ ] C++: Google C++ Style Guide (or consistent style)
  - [ ] Cython: Proper type annotations and memory management

---

## 🧪 Testing

**How did you test this change?**

- [ ] Added new unit tests: `[test file names]`
- [ ] Ran existing test suite: `pytest` (all passing)
- [ ] Tested with ROM: `[ROM name - NO LINKS]`
- [ ] Verified build: `python test_build.py` (passed)

**Test Results:**
```
[Paste pytest output here if relevant]
```

---

## 📸 Screenshots/Evidence (if applicable)

If this PR affects visual output or behavior, include screenshots or evidence.

---

## 🔗 Related Issues

Closes #[issue number]

---

## 📚 Additional Context

Add any other context about the PR here.

**Important Notes:**
- If this implements a new opcode, explain which ROM requires it
- If this is a bug fix, include reproduction steps and the fix explanation
- If this touches C++ code, explain any performance considerations

---

## ⚠️ Clean Room Compliance

**By submitting this PR, I confirm:**

- [ ] I did NOT copy code from other emulators (mGBA, SameBoy, Gambatte, etc.)
- [ ] I implemented this feature based on official documentation (Pan Docs, GBEDG, hardware manuals)
- [ ] I understand the hardware behavior I'm implementing
- [ ] All code is original work or properly attributed

---

## 🙏 Review Notes

Any specific areas you'd like reviewers to focus on?

