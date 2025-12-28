# Configuración de SSH para GitHub - ViboyColor

## ⚠️ Acción Requerida

Para completar la configuración de autenticación con GitHub, necesitas agregar tu clave SSH pública a tu cuenta de GitHub.

### Paso 1: Obtener tu Clave SSH Pública

Ejecuta este comando para ver tu clave pública:

```bash
cat ~/.ssh/id_ed25519.pub
```

### Paso 2: Agregar la Clave a GitHub

1. **Copia la salida completa** del comando anterior (debe comenzar con `ssh-ed25519` y terminar con `Caprini@users.noreply.github.com`)

2. **Ve a GitHub:**
   - Abre: https://github.com/settings/keys
   - O: GitHub → Settings → SSH and GPG keys → New SSH key

3. **Agrega la clave:**
   - **Title**: ViboyColor - Linux/Desktop (o el nombre que prefieras)
   - **Key**: Pega la clave pública completa
   - **Key type**: Authentication Key
   - Click en **"Add SSH key"**

### Paso 3: Verificar la Conexión

Una vez agregada la clave, verifica la conexión:

```bash
ssh -T git@github.com
```

Deberías ver: `Hi Caprini! You've successfully authenticated...`

### Paso 4: Cambiar el Remoto a SSH

Una vez verificada la conexión, cambia el remoto a SSH:

```bash
cd /media/fabini/8CD1-4C30/ViboyColor
git remote set-url origin git@github.com:Caprini/ViboyColor.git
```

### Paso 5: Hacer Push

```bash
git push origin develop-v0.0.2
```

## Alternativa: Usar Personal Access Token (HTTPS)

Si prefieres usar HTTPS con un token:

1. **Genera un token:**
   - Ve a: https://github.com/settings/tokens
   - Click en "Generate new token (classic)"
   - Nombre: `ViboyColor - Git Push`
   - Expiración: 90 días (o la que prefieras)
   - Permisos: Marca `repo` (acceso completo a repositorios)
   - Click en "Generate token"
   - **IMPORTANTE**: Copia el token inmediatamente (no lo verás de nuevo)

2. **Configura Git para usar el token:**
   
   ```bash
   # El token se usará como contraseña cuando Git lo solicite
   git push origin develop-v0.0.2
   # Usuario: Caprini
   # Contraseña: [pega el token aquí]
   ```

   O configurar el token en la URL (menos seguro pero más conveniente):

   ```bash
   git remote set-url origin https://TU_TOKEN_AQUI@github.com/Caprini/ViboyColor.git
   ```

3. **Hacer push:**
   ```bash
   git push origin develop-v0.0.2
   ```

## Recomendación

**SSH es más seguro y conveniente** a largo plazo, ya que:
- No necesitas ingresar credenciales cada vez
- Es más seguro que tokens en URLs
- Es el método recomendado por GitHub

## Solución de Problemas

### Error: "Permission denied (publickey)"

- Verifica que agregaste la clave pública (no la privada) a GitHub
- Verifica que el agente SSH está corriendo: `eval "$(ssh-agent -s)"`
- Verifica que la clave está agregada: `ssh-add -l`

### Error: "Host key verification failed"

Ejecuta:

```bash
ssh-keyscan github.com >> ~/.ssh/known_hosts
```

### Error: "Could not resolve hostname github.com"

- Verifica tu conexión a Internet
- Intenta: `ping github.com`

