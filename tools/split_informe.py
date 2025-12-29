#!/usr/bin/env python3
"""
Script para dividir INFORME_FASE_2.md en partes más pequeñas.
Cada parte tendrá aproximadamente 1500-2000 líneas máximo.
"""

import re
from pathlib import Path

# Configuración
MAX_LINES_PER_PART = 1800  # Líneas máximas por parte
INFORME_PATH = Path("INFORME_FASE_2.md")
OUTPUT_DIR = Path("docs/informe_fase_2")
HEADER_LINES = 33  # Líneas de cabecera (hasta antes de "## Entradas de Desarrollo")

def find_step_headers(content_lines):
    """Encuentra todas las líneas que son headers de Steps."""
    step_headers = []
    for i, line in enumerate(content_lines, 1):
        if re.match(r'^### \d{4}-\d{2}-\d{2} - Step \d{4}:', line):
            step_num = extract_step_number(line)
            step_headers.append((i, line, step_num))
    return step_headers

def extract_step_number(header_line):
    """Extrae el número de Step de una línea de header."""
    match = re.search(r'Step (\d{4}):', header_line)
    return int(match.group(1)) if match else None

def split_informe():
    """Divide el informe en partes."""
    # Leer el archivo completo
    with open(INFORME_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Extraer cabecera
    header = ''.join(lines[:HEADER_LINES])
    
    # Encontrar headers de Steps
    step_headers = find_step_headers(lines)
    print(f"Encontradas {len(step_headers)} entradas de Steps")
    
    # Dividir en partes basándose en número de líneas
    parts = []
    # Primera parte empieza después del header (línea 34, que es "## Entradas de Desarrollo\n")
    current_part_start_idx = HEADER_LINES + 1
    current_part_lines = 0
    current_part_steps = []
    part_num = 1
    
    for i in range(len(step_headers)):
        step_line_idx, step_header, step_num = step_headers[i]
        
        # Calcular cuántas líneas tiene este Step
        if i + 1 < len(step_headers):
            next_step_line_idx = step_headers[i + 1][0]
            step_size = next_step_line_idx - step_line_idx
        else:
            step_size = len(lines) - step_line_idx + 1
        
        # Si agregar este Step excede el límite y ya tenemos contenido, crear nueva parte
        if current_part_lines + step_size > MAX_LINES_PER_PART and current_part_lines > 0:
            # Guardar parte actual
            end_idx = step_line_idx - 1
            parts.append({
                'num': part_num,
                'start_idx': current_part_start_idx,
                'end_idx': end_idx,
                'steps': sorted(current_part_steps)  # Ordenar para min/max correctos
            })
            
            # Iniciar nueva parte con este Step (incluir el separador anterior si existe)
            part_num += 1
            current_part_start_idx = step_line_idx - 1
            current_part_lines = step_size
            current_part_steps = [step_num] if step_num else []
        else:
            # Agregar este Step a la parte actual
            current_part_lines += step_size
            if step_num:
                current_part_steps.append(step_num)
    
    # Agregar la última parte
    if current_part_lines > 0:
        parts.append({
            'num': part_num,
            'start_idx': current_part_start_idx,
            'end_idx': len(lines),
            'steps': sorted(current_part_steps)
        })
    
    # Crear directorio de salida
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Escribir cada parte
    part_info = []
    for part in parts:
        if not part['steps']:
            continue  # Saltar si no hay steps
        
        min_step = min(part['steps'])
        max_step = max(part['steps'])
        part_filename = f"parte_{part['num']:02d}_steps_{min_step:04d}_{max_step:04d}.md"
        part_path = OUTPUT_DIR / part_filename
        
        # Escribir parte
        part_content = header
        part_content += '\n\n---\n\n'
        part_content += f'*Esta parte contiene Steps {min_step} a {max_step}*\n\n'
        part_content += '---\n\n'
        # Añadir el contenido desde el inicio de las entradas (línea HEADER_LINES+1 que es "## Entradas de Desarrollo")
        # pero solo desde el índice de inicio de la parte
        part_content += ''.join(lines[part['start_idx']:part['end_idx']])
        
        with open(part_path, 'w', encoding='utf-8') as f:
            f.write(part_content)
        
        part_lines = part['end_idx'] - part['start_idx']
        print(f"Parte {part['num']}: {part_filename} ({part_lines} líneas, Steps {min_step}-{max_step}, {len(part['steps'])} Steps)")
        
        part_info.append({
            'num': part['num'],
            'filename': part_filename,
            'start_step': min_step,
            'end_step': max_step,
            'num_steps': len(part['steps']),
            'lines': part_lines
        })
    
    return part_info

def create_index(part_info):
    """Crea el archivo índice."""
    index_path = OUTPUT_DIR / "index.md"
    
    index_content = """# Índice - Informe de Desarrollo Fase 2 (v0.0.2)

**Objetivo**: Migración del Núcleo a C++/Cython y Audio (APU).

**Estado**: En desarrollo.

---

## Estructura del Informe

Este informe ha sido dividido en varias partes para facilitar la legibilidad y el manejo por los agentes de IA. Cada parte contiene aproximadamente 1500-2000 líneas y agrupa Steps consecutivos.

**Nota**: Las partes mantienen el orden cronológico original (más recientes primero).

---

## Partes del Informe

"""
    
    for part in part_info:
        index_content += f"### Parte {part['num']}: Steps {part['start_step']} - {part['end_step']}\n\n"
        index_content += f"- **Archivo**: [{part['filename']}]({part['filename']})\n"
        index_content += f"- **Rango de Steps**: {part['start_step']} a {part['end_step']}\n"
        index_content += f"- **Número de Steps**: {part['num_steps']}\n"
        index_content += f"- **Líneas**: ~{part['lines']}\n\n"
    
    index_content += """---

## Uso para Agentes

Cuando necesites actualizar el informe:
1. Identifica el Step que necesitas documentar
2. Localiza la parte correspondiente usando este índice
3. Actualiza solo esa parte del informe
4. Si una parte excede 2000 líneas, divídela creando una nueva parte

---

## Reglas de Mantenimiento

- **Tamaño máximo por parte**: 2000 líneas
- **Orden**: Cronológico inverso (más recientes primero)
- **Formato**: Markdown estándar
- **Cabecera**: Todas las partes incluyen la cabecera completa al inicio
"""
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write(index_content)
    
    print(f"\nÍndice creado: {index_path}")

if __name__ == "__main__":
    print("Dividiendo INFORME_FASE_2.md...")
    part_info = split_informe()
    create_index(part_info)
    print("\n¡División completada!")
