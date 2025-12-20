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

