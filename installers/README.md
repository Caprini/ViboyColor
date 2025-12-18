# Instaladores de Viboy Color

Esta carpeta contiene los archivos de configuración necesarios para crear instaladores profesionales de Viboy Color en diferentes sistemas operativos.

## Windows (Inno Setup)

### Requisitos
- [Inno Setup](https://jrsoftware.org/isinfo.php) instalado

### Uso
1. Compilar el ejecutable:
   ```bash
   python tools/build_release.py
   ```

2. Abrir `installers/windows_setup.iss` en Inno Setup Compiler

3. Compilar el instalador (Build > Compile)

4. El instalador estará en `release/ViboyColor-Setup-0.0.1.exe`

### Personalización
Edita `windows_setup.iss` para:
- Cambiar el nombre de la aplicación
- Añadir licencia
- Modificar rutas de instalación
- Añadir tareas de instalación personalizadas

---

## Linux (Debian/Ubuntu - .deb)

### Requisitos
- `dpkg-deb` (generalmente incluido en sistemas Debian/Ubuntu)

### Uso
1. Compilar el ejecutable:
   ```bash
   python tools/build_release.py
   ```

2. Copiar el ejecutable a la estructura del paquete:
   ```bash
   cp release/ViboyColor installers/linux/debian/usr/bin/viboy-color
   ```

3. Crear el paquete .deb:
   ```bash
   cd installers/linux
   dpkg-deb --build debian viboy-color_0.0.1_all.deb
   ```

4. Instalar (requiere sudo):
   ```bash
   sudo dpkg -i viboy-color_0.0.1_all.deb
   ```

### Estructura del paquete
```
debian/
├── DEBIAN/
│   ├── control      # Metadatos del paquete
│   ├── postinst     # Script post-instalación
│   └── postrm       # Script post-eliminación
└── usr/
    └── bin/
        └── viboy-color  # Ejecutable (copiar manualmente)
```

### Personalización
Edita `debian/DEBIAN/control` para:
- Cambiar dependencias
- Actualizar versión
- Modificar descripción

---

## macOS (.app Bundle)

### Requisitos
- macOS (no se puede compilar en otros sistemas)
- Python 3.10+
- `py2app`: `pip install py2app`

### Uso
1. Navegar al directorio de instaladores:
   ```bash
   cd installers/macos
   ```

2. Compilar el bundle:
   ```bash
   python setup.py py2app
   ```

3. El bundle estará en `dist/ViboyColor.app`

4. Para crear un instalador DMG (opcional):
   ```bash
   hdiutil create -volname "Viboy Color" -srcfolder dist/ViboyColor.app -ov -format UDZO ViboyColor-0.0.1.dmg
   ```

### Personalización
Edita `setup.py` para:
- Cambiar el identificador del bundle
- Añadir/eliminar dependencias
- Modificar metadatos del Info.plist

---

## Notas Importantes

### Clean-Room / Legal
- Este proyecto es educativo y Open Source
- No se distribuyen ROMs comerciales
- Los instaladores solo incluyen el emulador, no ROMs

### Falsos Positivos de Antivirus
Los ejecutables generados por PyInstaller a veces son marcados como sospechosos por antivirus (falsos positivos). Esto es normal y el código es legítimo. Si ocurre:
- Añade una excepción en tu antivirus
- Considera firmar el ejecutable con un certificado de código (Windows/macOS)

### Portabilidad
- Los instaladores deben generarse en el sistema operativo objetivo
- Para Windows: usar Windows o WSL
- Para Linux: usar Linux o WSL
- Para macOS: usar macOS (no hay alternativa fácil)

---

## Próximos Pasos

- [ ] Firmar ejecutables con certificado de código
- [ ] Crear instaladores automáticos con CI/CD
- [ ] Añadir actualizaciones automáticas
- [ ] Crear instaladores para otras distribuciones Linux (.rpm, .AppImage)

