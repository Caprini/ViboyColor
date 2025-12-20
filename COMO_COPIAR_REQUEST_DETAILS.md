# Cómo Copiar Request Details de Errores en Cursor

## 📋 Cuando Aparece un Error de Conexión

Cuando Cursor muestra un error "Connection failed", verás una notificación en la parte inferior de la ventana con:

- Mensaje: "Connection failed. If the problem persists, please check your internet connection or VPN"
- Request ID visible
- Botón **"Copy Request Details"**

## 🔍 Pasos para Obtener Información Detallada

### Paso 1: Localizar la Notificación

La notificación aparece en la parte inferior de la ventana de Cursor, generalmente en color amarillo/naranja.

### Paso 2: Copiar los Detalles

1. **Haz clic en "Copy Request Details"** en la notificación
2. Esto copiará información detallada al portapapeles
3. La información incluye:
   - Request ID completo
   - Timestamp del error
   - Comando que se estaba ejecutando
   - Stack trace (si está disponible)
   - Contexto del error

### Paso 3: Guardar la Información

1. Abre un editor de texto (Notepad, VS Code, etc.)
2. Pega la información copiada (`Ctrl + V`)
3. Guarda el archivo con un nombre descriptivo:
   - `cursor_error_2024-12-20_request_cb24c924.txt`
   - O simplemente `cursor_error_details.txt`

### Paso 4: Incluir en el Reporte

Cuando reportes el problema a Cursor o en el foro, incluye:
- El Request ID
- La información completa copiada de "Request Details"
- Descripción de qué estabas haciendo cuando ocurrió el error

## 📝 Ejemplo de Información Copiada

La información copiada típicamente incluye algo como:

```
Request ID: cb24c924-61d9-47fa-89c6-40c907a40665
Timestamp: 2024-12-20T...
Command: python main.py roms/tetris.gb
Error: Connection failed
Context: Terminal execution
...
```

## 🎯 Request IDs Documentados

Si copias los detalles de un error, documenta el Request ID:

1. Agrega el Request ID a `REPORTE_ERROR_CURSOR.md`
2. Incluye el contexto (qué comando se estaba ejecutando)
3. Guarda los detalles completos en un archivo de texto

## 💡 Consejos

- **No ignores el botón "Copy Request Details"** - contiene información valiosa
- **Copia los detalles inmediatamente** - la notificación puede desaparecer
- **Guarda múltiples errores** - si tienes varios Request IDs, guárdalos todos
- **Incluye contexto** - anota qué estabas haciendo cuando ocurrió cada error

## 🔗 Archivos Relacionados

- `REPORTE_ERROR_CURSOR.md` - Reporte principal con Request IDs conocidos
- `SOLUCION_ERRORES_CURSOR.md` - Guía completa de solución de problemas

---

**Nota:** La información de "Request Details" es muy útil para el equipo de Cursor para diagnosticar el problema específico.

