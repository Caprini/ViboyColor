---
name: Bug Report
about: Create a report to help us improve
title: '[BUG] '
labels: bug
assignees: ''
---

## ⚠️ Compilation Check (REQUIRED - READ THIS FIRST)

**Before reporting a bug, you MUST verify that the C++ core is compiled correctly.**

**Did you run `python test_build.py`? What was the output?**

```
[Paste the FULL output of `python test_build.py` here]
```

**⚠️ If `python test_build.py` failed, DO NOT open a bug report.**
- Check `CONTRIBUTING.md` for compilation instructions
- Verify you have a C++ compiler installed (Visual Studio Build Tools on Windows, GCC/Clang on Linux/macOS)
- Ensure Cython is installed: `pip install cython`

**If the build test passed, continue with the bug report below.**

---

## 🐛 Bug Description

A clear and concise description of what the bug is.

---

## 🔄 Steps to Reproduce

1. ROM Name: `[ROM name here - NO LINKS, NO FILE UPLOADS]`
2. ROM MD5 (optional but helpful): `[MD5 hash if available]`
3. Steps to reproduce:
   ```
   1. ...
   2. ...
   3. ...
   ```

---

## ✅ Expected Behavior

A clear and concise description of what you expected to happen.

---

## ❌ Actual Behavior

A clear and concise description of what actually happened.

---

## 📸 Screenshots/Visual Evidence

If applicable, add screenshots or visual evidence of the bug.

---

## 💻 Environment

Please provide the following information:

- **OS**: [e.g., Windows 11, Ubuntu 22.04, macOS 14.0]
- **Python Version**: [e.g., Python 3.11.5]
- **C++ Compiler**: [e.g., Visual Studio 2022, GCC 11.4, Clang 15.0]
- **Viboy Color Version**: [e.g., v0.0.2-dev, commit hash if from source]

---

## 📋 Logs

If applicable, attach relevant logs:

**CPU Trace (if enabled):**
```
[Paste CPU trace logs here]
```

**Error Messages:**
```
[Paste error messages here]
```

**Console Output:**
```
[Paste console output here]
```

---

## 🔍 Additional Context

Add any other context about the problem here.

---

## ✅ Checklist

- [ ] I have run `python test_build.py` and it **passed**
- [ ] I have read `CONTRIBUTING.md`
- [ ] I have checked existing issues to see if this bug was already reported
- [ ] I have provided all required information above

