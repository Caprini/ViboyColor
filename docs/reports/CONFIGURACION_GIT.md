# Configuración de Git para ViboyColor

Este documento describe la configuración de Git y GitHub para el proyecto ViboyColor.

## Estado Actual

- **Repositorio Remoto**: `https://github.com/Caprini/ViboyColor`
- **Rama Actual**: `develop-v0.0.2`
- **Ramas Remotas**: `main`, `develop-v0.0.2`

## Configuración Rápida

### 1. Ejecutar Script de Configuración

```bash
bash .gitconfig-setup.sh
```

Este script configurará:
- Usuario de Git (nombre)
- Email de Git
- Verificación del remoto
- Configuración de la rama por defecto

### 2. Configuración Manual (Alternativa)

Si prefieres configurar manualmente:

```bash
# Configurar usuario (solo para este repositorio)
git config user.name "Tu Nombre"
git config user.email "tu.email@example.com"

# Verificar remoto
git remote -v

# Si necesitas agregar el remoto (no debería ser necesario)
git remote add origin https://github.com/Caprini/ViboyColor.git

# Configurar rama upstream
git branch --set-upstream-to=origin/develop-v0.0.2 develop-v0.0.2
```

## Verificación de Configuración

Para verificar que todo está configurado correctamente:

```bash
# Ver configuración de usuario
git config user.name
git config user.email

# Ver remotos
git remote -v

# Ver estado
git status

# Ver ramas
git branch -a
```

## Flujo de Trabajo

### Hacer Push de Cambios

```bash
# Ver commits pendientes
git log origin/develop-v0.0.2..HEAD --oneline

# Hacer push
git push origin develop-v0.0.2

# O si la rama upstream está configurada
git push
```

### Hacer Commit de Cambios

```bash
# Agregar cambios
git add .

# Hacer commit
git commit -m "tipo: descripción del cambio"

# Push
git push origin develop-v0.0.2
```

## Convenciones de Commits

Siguiendo las reglas del proyecto, los commits deben seguir este formato:

- `feat(componente): descripción` - Nueva funcionalidad
- `fix(componente): descripción` - Corrección de bug
- `build(herramienta): descripción` - Cambios en build system
- `docs(archivo): descripción` - Cambios en documentación
- `test(archivo): descripción` - Cambios en tests
- `refactor(componente): descripción` - Refactorización

Ejemplos:
- `feat(core): implementación de APU`
- `fix(ppu): corrección de renderizado de sprites`
- `build(cython): actualización de setup.py`

## Autenticación con GitHub

Para hacer push a GitHub, necesitas autenticarte. Opciones:

### 1. Personal Access Token (HTTPS)

1. Generar un token en GitHub: Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Usar el token como contraseña cuando Git lo solicite
3. O configurar el token en la URL:

```bash
git remote set-url origin https://TU_TOKEN@github.com/Caprini/ViboyColor.git
```

### 2. SSH (Recomendado)

1. Generar clave SSH:
```bash
ssh-keygen -t ed25519 -C "tu.email@example.com"
```

2. Agregar clave a ssh-agent:
```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

3. Agregar clave pública a GitHub: Settings → SSH and GPG keys → New SSH key

4. Cambiar remoto a SSH:
```bash
git remote set-url origin git@github.com:Caprini/ViboyColor.git
```

5. Verificar conexión:
```bash
ssh -T git@github.com
```

## Solución de Problemas

### Error: "remote: Permission denied"

- Verificar autenticación con GitHub (token o SSH)
- Verificar permisos en el repositorio

### Error: "fatal: No configured push destination"

```bash
git push --set-upstream origin develop-v0.0.2
```

### Error: "Your branch is ahead of 'origin/develop-v0.0.2' by N commits"

Esto es normal. Simplemente haz push:

```bash
git push origin develop-v0.0.2
```

### Ver últimos commits no pusheados

```bash
git log origin/develop-v0.0.2..HEAD --oneline
```

## Recursos

- [Documentación oficial de Git](https://git-scm.com/doc)
- [GitHub Help - Configurar Git](https://help.github.com/en/articles/set-up-git)
- [GitHub Help - Autenticación](https://help.github.com/en/articles/about-authentication-to-github)

