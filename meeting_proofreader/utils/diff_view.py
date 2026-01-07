import difflib

def generate_diff_html(original: str, corrected: str) -> tuple[str, int]:
    """
    Generates an HTML representation of the diff.
    Returns: (html_content, change_count)
    """
    matcher = difflib.SequenceMatcher(None, original, corrected)
    html_output = []
    change_count = 0
    
    # Define styles
    style_del = 'background-color:#ffeef0; color:#b31d28; text-decoration:line-through; padding: 0 2px;'
    style_add = 'background-color:#e6ffec; color:#22863a; font-weight:bold; padding: 0 2px;'
    
    import html
    
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            text = html.escape(original[a0:a1])
            text = text.replace('\n', '<br>')
            html_output.append(f'<span>{text}</span>')
            
        elif opcode == 'insert':
            raw_text = corrected[b0:b1]
            text = html.escape(raw_text).replace('\n', '<br>')
            
            # Filter whitespace-only changes
            if raw_text.strip():
                # Assign ID for navigation
                html_output.append(f'<span id="diff-match-{change_count}" style="{style_add}">{text}</span>')
                change_count += 1
            else:
                html_output.append(f'<span style="{style_add}">{text}</span>')
            
        elif opcode == 'delete':
            raw_text = original[a0:a1]
            text = html.escape(raw_text).replace('\n', '<br>')
            
            if raw_text.strip():
                html_output.append(f'<span id="diff-match-{change_count}" style="{style_del}">{text}</span>')
                change_count += 1
            else:
                html_output.append(f'<span style="{style_del}">{text}</span>')
            
        elif opcode == 'replace':
            raw_del = original[a0:a1]
            raw_add = corrected[b0:b1]
            
            del_text = html.escape(raw_del).replace('\n', '<br>')
            add_text = html.escape(raw_add).replace('\n', '<br>')
            
            is_meaningful = raw_del.strip() or raw_add.strip()
            
            if is_meaningful:
                # Add ID to the first element (deletion) to jump to start of change
                html_output.append(f'<span id="diff-match-{change_count}" style="{style_del}">{del_text}</span>')
                html_output.append(f'<span style="{style_add}">{add_text}</span>')
                change_count += 1
            else:
                html_output.append(f'<span style="{style_del}">{del_text}</span>')
                html_output.append(f'<span style="{style_add}">{add_text}</span>')
            
    return "".join(html_output), change_count
