# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from teddynotes.const import get_assets_path
from teddynotes.config_manager import ConfigManager

HEADING_SCALE_MAP = {
    "compact": 0.85,
    "normal": 1.0,
    "large": 1.2,
    "xlarge": 1.4,
}

def get_editor_html_page(
    content_html: str = "",
    is_dark: bool = False,
    font_size: int = 16,
    heading_scale: str = "normal",
    code_font_size: int = 14,
    quote_font_size: int = 16,
    zoom_level: float = 1.0,
    font_family: str = "system",
) -> str:
    """Load editor.html and inject initial content, theme, and typography."""
    template_path = get_assets_path() / "editor" / "editor.html"
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception as e:
        template = "<!DOCTYPE html><html><body><div id='editor' contenteditable='true'></div></body></html>"

    theme_class = "dark-theme" if is_dark else "light-theme"
    template = template.replace('class="light-theme"', f'class="{theme_class}"')

    if zoom_level != 1.0:
        font_size = round(16 * zoom_level)
        code_font_size = round(14 * zoom_level)
        quote_font_size = round(16 * zoom_level)

    if font_size != 16:
        template = template.replace('--base-font-size: 16pt;', f'--base-font-size: {font_size}pt;')

    scale_val = HEADING_SCALE_MAP.get(heading_scale, 1.0)
    if scale_val != 1.0:
        template = template.replace('--heading-scale: 1.0;', f'--heading-scale: {scale_val};')

    if code_font_size != 14:
        template = template.replace('--code-font-size: 14px;', f'--code-font-size: {code_font_size}px;')

    if quote_font_size != 16:
        template = template.replace('--quote-font-size: 16pt;', f'--quote-font-size: {quote_font_size}pt;')

    if font_family in ConfigManager.FONT_STACKS and font_family != "system":
        font_stack = ConfigManager.FONT_STACKS[font_family]
        default_stack_css = '--font-stack: -apple-system, BlinkMacSystemFont, "Cantarell", "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;'
        template = template.replace(default_stack_css, f'--font-stack: {font_stack};')

    clean_content = content_html or "<h1>Untitled Note</h1><div><br></div>"
    marker = '<div id="editor" contenteditable="true" spellcheck="true"></div>'
    replacement = f'<div id="editor" contenteditable="true" spellcheck="true">{clean_content}</div>'
    if marker in template:
        template = template.replace(marker, replacement)

    return template
