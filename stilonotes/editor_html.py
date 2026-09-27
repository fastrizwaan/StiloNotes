# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from stilonotes.const import get_assets_path

def get_editor_html_page(content_html: str = "", is_dark: bool = False, font_size: int = 16) -> str:
    """Load editor.html and inject initial content, theme, and font size."""
    template_path = get_assets_path() / "editor" / "editor.html"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as e:
        template = "<!DOCTYPE html><html><body><div id='editor' contenteditable='true'></div></body></html>"

    theme_class = "dark-theme" if is_dark else "light-theme"
    template = template.replace('class="light-theme"', f'class="{theme_class}"')

    if font_size != 16:
        template = template.replace('--base-font-size: 16pt;', f'--base-font-size: {font_size}pt;')

    clean_content = content_html or "<h1>Untitled Note</h1><div><br></div>"
    marker = '<div id="editor" contenteditable="true" spellcheck="true"></div>'
    replacement = f'<div id="editor" contenteditable="true" spellcheck="true">{clean_content}</div>'
    if marker in template:
        template = template.replace(marker, replacement)

    return template
