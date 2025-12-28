#!/usr/bin/env python3
"""
Script para corregir el formato de las entradas de la bitácora.
Convierte el formato nuevo (desde 0220) al formato antiguo (como 0219 y anteriores).
"""

import re
from pathlib import Path

def fix_bitacora_index():
    """Corrige el formato de las entradas en index.html."""
    index_path = Path(__file__).parent.parent / "docs" / "bitacora" / "index.html"
    
    print(f"Leyendo {index_path}...")
    with open(index_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    entries_fixed = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Buscar entradas con formato nuevo: <li class="entry-item">
        if '<li class="entry-item">' in line:
            # Leer la entrada completa
            entry_lines = [line]
            i += 1
            
            # Leer hasta encontrar </li>
            while i < len(lines) and '</li>' not in lines[i]:
                entry_lines.append(lines[i])
                i += 1
            
            if i < len(lines):
                entry_lines.append(lines[i])  # Incluir el </li>
            
            entry_text = ''.join(entry_lines)
            
            # Extraer información usando regex más flexible
            # Buscar el comentario anterior (puede estar en líneas anteriores)
            comment_line = ""
            if i - len(entry_lines) > 0:
                # Buscar comentario en las líneas anteriores
                for j in range(max(0, i - len(entry_lines) - 5), i - len(entry_lines)):
                    if '<!-- Entrada' in lines[j]:
                        comment_line = lines[j].strip()
                        break
            
            # Extraer datos de la entrada
            date_match = re.search(r'<span class="meta">(\d{4}-\d{2}-\d{2})</span>', entry_text)
            step_id_match = re.search(r'<span class="tag">(\d{4})</span>', entry_text)
            href_match = re.search(r'<a href="(entries/[^"]+)" class="title">', entry_text)
            title_match = re.search(r'class="title">([^<]+)</a>', entry_text)
            summary_match = re.search(r'<p class="summary">([^<]+)</p>', entry_text)
            status_match = re.search(r'<span class="status-badge (status-verified|status-draft)">(VERIFIED|DRAFT)</span>', entry_text)
            
            if date_match and step_id_match and href_match and title_match and summary_match and status_match:
                date = date_match.group(1)
                step_id = step_id_match.group(1)
                href = href_match.group(1)
                title = title_match.group(1)
                summary = summary_match.group(1)
                status_class = status_match.group(1)
                status_text = status_match.group(2)
                
                # Verificar si el Step ID es >= 0220
                if int(step_id) >= 220:
                    # Determinar la clase del tag según el estado
                    if status_class == 'status-verified':
                        tag_class = 'tag-verified'
                    else:
                        tag_class = 'tag-draft'
                    
                    # Si no hay comentario, generarlo
                    if not comment_line:
                        comment_line = f'<!-- Entrada {step_id} - {title} -->'
                    
                    # Construir el formato antiguo
                    old_format = f"""                    {comment_line}
                    <li>
                        <div class="entry-header">
                            <h3 class="entry-title">
                                <a href="{href}" class="entry-link">
                                    {title}
                                </a>
                            </h3>
                        </div>
                        <div class="entry-meta-index">
                            <strong>Fecha:</strong> {date} | 
                            <strong>Step ID:</strong> {step_id} | 
                            <strong>Estado:</strong> <span class="tag {tag_class}">{status_text}</span>
                        </div>
                        <p class="entry-summary">
                            {summary}
                        </p>
                    </li>
"""
                    new_lines.append(old_format)
                    entries_fixed += 1
                else:
                    # Mantener el formato original si Step ID < 0220
                    new_lines.extend(entry_lines)
            else:
                # Si no se puede parsear, mantener el original
                new_lines.extend(entry_lines)
        else:
            new_lines.append(line)
        
        i += 1
    
    print(f"Encontradas y corregidas {entries_fixed} entradas (Step ID >= 0220)")
    
    if entries_fixed > 0:
        # Guardar el archivo
        print(f"Guardando cambios en {index_path}...")
        with open(index_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"[OK] Corregidas {entries_fixed} entradas.")
    else:
        print("No hay entradas para corregir.")

if __name__ == "__main__":
    fix_bitacora_index()
