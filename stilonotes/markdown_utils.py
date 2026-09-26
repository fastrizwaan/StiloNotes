# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import html
import re
import time
from typing import List, Tuple

def format_relative_date(timestamp: float) -> str:
    """Return a human-friendly relative date string."""
    if not timestamp:
        return "Unknown"

    now = time.time()
    diff = max(0, int(now - timestamp))

    if diff < 60:
        return "Just now"
    elif diff < 3600:
        mins = max(1, diff // 60)
        return f"{mins}m ago"
    elif diff < 86400:
        hours = diff // 3600
        return f"{hours}h ago"
    elif diff < 172800:
        return "Yesterday"
    elif diff < 604800:
        days = diff // 86400
        return f"{days}d ago"
    else:
        # e.g., "Sep 24" or "Sep 24, 2025"
        t = time.localtime(timestamp)
        now_t = time.localtime(now)
        if t.tm_year == now_t.tm_year:
            return time.strftime("%b %d", t)
        else:
            return time.strftime("%b %d, %Y", t)


def check_has_todo(content: str) -> bool:
    """Check if content has todo checklist items."""
    if not content:
        return False
    return bool(
        re.search(r'class=["\']stilo-task', content)
        or re.search(r'class=["\']stilo-checkbox', content)
        or re.search(r'^[-*]\s+\[[ xX]\]', content, re.MULTILINE)
    )


def extract_tags(text: str) -> List[str]:
    """Deprecated tag extractor; returns empty list as app is category-based."""
    return []


def strip_markdown(text: str) -> str:
    """Clean plain text extraction from Markdown/HTML."""
    if not text:
        return ""
    s = text
    # Remove HTML tags
    s = re.sub(r'<[^>]+>', ' ', s)
    # Headings
    s = re.sub(r'#+\s*', '', s)
    # Tasks and lists
    s = re.sub(r'[-*]\s+\[[ xX]\]\s*', '', s)
    s = re.sub(r'^[-*+]\s+', '', s, flags=re.MULTILINE)
    s = re.sub(r'^\d+\.\s+', '', s, flags=re.MULTILINE)
    # Quotes and dividers
    s = re.sub(r'>\s*', '', s)
    s = re.sub(r'(?:---|\*\*\*|___)', '', s)
    # Code fences and inline code
    s = re.sub(r'```.*?```', '', s, flags=re.DOTALL)
    s = re.sub(r'`([^`]+)`', r'\1', s)
    # Links & Images
    s = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', s)
    s = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', s)
    # Formatting asterisks / underscores / highlights / strikethroughs
    s = re.sub(r'\*{1,3}([^*]+)\*{1,3}', r'\1', s)
    s = re.sub(r'_{1,3}([^_]+)_{1,3}', r'\1', s)
    s = re.sub(r'~~([^~]+)~~', r'\1', s)
    s = re.sub(r'==([^=]+)==', r'\1', s)
    # Strip any stray asterisks or markdown symbols
    s = re.sub(r'[*_~`#]', '', s)
    # Unescape HTML
    s = html.unescape(s)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', s).strip()


def extract_title_and_excerpt(markdown_text: str = "", html_text: str = "") -> Tuple[str, str]:
    """Extract first non-empty line as title, and subsequent text as excerpt."""
    title = "Untitled Note"
    excerpt = ""

    lines = []
    if markdown_text:
        lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    elif html_text:
        clean = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\1\n', html_text, flags=re.DOTALL)
        clean = re.sub(r'<div[^>]*>', '\n', clean)
        clean = re.sub(r'<p[^>]*>', '\n', clean)
        clean = re.sub(r'<br\s*/?>', '\n', clean)
        clean = re.sub(r'<[^>]+>', ' ', clean)
        lines = [line.strip() for line in html.unescape(clean).splitlines() if line.strip()]

    if lines:
        title = strip_markdown(lines[0]) or "Untitled Note"
        if len(lines) > 1:
            raw_excerpt = " ".join(lines[1:5])
            excerpt = strip_markdown(raw_excerpt)[:160]

    return title, excerpt


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown text to Stilo rich HTML."""
    if not md_text:
        return "<h1>Untitled Note</h1><div><br></div>"

    def format_inline(text: str) -> str:
        s = html.escape(text)

        # Bold & Italic
        s = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<strong><em>\1</em></strong>', s)
        s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
        s = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', s)
        s = re.sub(r'(?<!_)_([^_]+)_(?!_)', r'<em>\1</em>', s)

        # Highlight
        s = re.sub(r'==([^=]+)==', r'<mark class="stilo-highlight">\1</mark>', s)

        # Strikethrough
        s = re.sub(r'~~([^~]+)~~', r'<del>\1</del>', s)

        # Inline code
        s = re.sub(r'`([^`]+)`', r'<code class="stilo-inline-code">\1</code>', s)

        # Links
        s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2" class="stilo-link" target="_blank">\1</a>', s)

        return s

    lines = md_text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    html_lines = []

    in_ul = False
    in_ol = False
    in_code_block = False
    code_lang = ""
    code_lines = []
    in_table = False
    table_rows = []

    def close_lists():
        nonlocal in_ul, in_ol
        res = []
        if in_ul:
            res.append("</ul>")
            in_ul = False
        if in_ol:
            res.append("</ol>")
            in_ol = False
        return "\n".join(res)

    def close_table():
        nonlocal in_table, table_rows
        if not in_table or not table_rows:
            in_table = False
            table_rows = []
            return ""

        out = ['<table class="stilo-table">']
        is_first = True
        for row in table_rows:
            cells = [c.strip() for c in row.split('|')[1:-1]]
            if not cells or all(re.match(r'^[-:]+$', c) for c in cells):
                continue
            if is_first:
                out.append('<thead><tr>' + ''.join(f'<th>{format_inline(c)}</th>' for c in cells) + '</tr></thead><tbody>')
                is_first = False
            else:
                out.append('<tr>' + ''.join(f'<td>{format_inline(c)}</td>' for c in cells) + '</tr>')

        out.append('</tbody></table>')
        in_table = False
        table_rows = []
        return "\n".join(out)

    for line in lines:
        # Code block fences
        code_fence = re.match(r'^```(\w*)\s*$', line)
        if code_fence:
            if in_code_block:
                escaped_code = html.escape("\n".join(code_lines))
                lang_attr = f' data-lang="{code_lang}"' if code_lang else ''
                html_lines.append(f'<pre class="stilo-code-block"{lang_attr}><code>{escaped_code}\n</code></pre><div><br></div>')
                in_code_block = False
                code_lines = []
            else:
                html_lines.append(close_lists())
                in_code_block = True
                code_lang = code_fence.group(1)
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Tables
        if re.match(r'^\|(.+)\|$', line.strip()):
            html_lines.append(close_lists())
            in_table = True
            table_rows.append(line.strip())
            continue
        elif in_table:
            html_lines.append(close_table())

        # Empty line
        if not line.strip():
            html_lines.append(close_lists())
            html_lines.append("<div><br></div>")
            continue

        # Headings
        if line.startswith("# "):
            html_lines.append(close_lists())
            html_lines.append(f"<h1>{format_inline(line[2:])}</h1>")
            continue
        elif line.startswith("## "):
            html_lines.append(close_lists())
            html_lines.append(f"<h2>{format_inline(line[3:])}</h2>")
            continue
        elif line.startswith("### "):
            html_lines.append(close_lists())
            html_lines.append(f"<h3>{format_inline(line[4:])}</h3>")
            continue
        elif line.startswith("#### "):
            html_lines.append(close_lists())
            html_lines.append(f"<h4>{format_inline(line[5:])}</h4>")
            continue

        # Horizontal Rule
        if re.match(r'^(?:---|\*\*\*|___)\s*$', line):
            html_lines.append(close_lists())
            html_lines.append('<hr class="stilo-hr">')
            continue

        # Todo checklist: - [ ] or - [x]
        todo_match = re.match(r'^[-*]\s+\[([ xX])\]\s*(.*)', line)
        if todo_match:
            html_lines.append(close_lists())
            checked = todo_match.group(1).lower() == 'x'
            checked_attr = 'checked="checked"' if checked else ''
            done_class = ' completed' if checked else ''
            item_text = format_inline(todo_match.group(2))
            html_lines.append(
                f'<div class="stilo-task{done_class}">'
                f'<input type="checkbox" class="stilo-checkbox" {checked_attr}>'
                f'<span class="task-text">{item_text}</span>'
                f'</div>'
            )
            continue

        # Blockquote
        if line.startswith("> "):
            html_lines.append(close_lists())
            html_lines.append(f'<blockquote class="stilo-quote">{format_inline(line[2:])}</blockquote>')
            continue

        # Unordered list: - or *
        if re.match(r'^[*-]\s+', line):
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append('<ul class="stilo-list">')
                in_ul = True
            content = re.sub(r'^[*-]\s+', '', line)
            html_lines.append(f"<li>{format_inline(content)}</li>")
            continue

        # Ordered list: 1.
        ol_match = re.match(r'^\d+\.\s+(.*)', line)
        if ol_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append('<ol class="stilo-numbered-list">')
                in_ol = True
            html_lines.append(f"<li>{format_inline(ol_match.group(1))}</li>")
            continue

        # Regular paragraph/div
        html_lines.append(close_lists())
        html_lines.append(f"<div>{format_inline(line)}</div>")

    if in_code_block:
        escaped_code = html.escape("\n".join(code_lines))
        html_lines.append(f'<pre class="stilo-code-block"><code>{escaped_code}\n</code></pre>')
    if in_table:
        html_lines.append(close_table())
    html_lines.append(close_lists())

    return "\n".join(html_lines)


def html_to_markdown(html_content: str) -> str:
    """Convert Stilo rich HTML back to clean Markdown."""
    if not html_content:
        return ""

    s = html_content
    s = s.replace('\r\n', '\n').replace('\r', '\n')

    # Convert Stilo Tasks
    def replace_task(m):
        checked = 'checked' in m.group(1)
        text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        mark = 'x' if checked else ' '
        return f"- [{mark}] {text}\n"

    s = re.sub(
        r'<div class="stilo-task[^"]*"[^>]*>\s*<input[^>]*type="checkbox"([^>]*)>\s*<span[^>]*>(.*?)</span>\s*</div>',
        replace_task,
        s,
        flags=re.DOTALL
    )

    # Convert Headings
    s = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n\n', s, flags=re.DOTALL)
    s = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n\n', s, flags=re.DOTALL)
    s = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n\n', s, flags=re.DOTALL)
    s = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n\n', s, flags=re.DOTALL)

    # Convert Horizontal Rules
    s = re.sub(r'<hr[^>]*>', '\n---\n\n', s)

    # Convert Code Blocks
    def replace_code_block(m):
        lang = m.group(1) or ""
        code = html.unescape(m.group(2))
        return f"\n```{lang}\n{code}\n```\n\n"

    s = re.sub(r'<pre[^>]*data-lang=["\'](.*?)["\'][^>]*><code[^>]*>(.*?)</code></pre>', replace_code_block, s, flags=re.DOTALL)
    s = re.sub(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', lambda m: f"\n```\n{html.unescape(m.group(1))}\n```\n\n", s, flags=re.DOTALL)

    # Convert Blockquotes
    s = re.sub(r'<blockquote[^>]*>(.*?)</blockquote>', lambda m: f"> {re.sub(r'<[^>]+>', '', m.group(1)).strip()}\n\n", s, flags=re.DOTALL)

    # Convert Tables
    def replace_table(m):
        table_html = m.group(0)
        headers = re.findall(r'<th[^>]*>(.*?)</th>', table_html, flags=re.DOTALL)
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, flags=re.DOTALL)

        md_table = []
        if headers:
            clean_headers = [re.sub(r'<[^>]+>', '', h).strip() for h in headers]
            md_table.append("| " + " | ".join(clean_headers) + " |")
            md_table.append("| " + " | ".join([":---" for _ in clean_headers]) + " |")

        for r in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', r, flags=re.DOTALL)
            if cells:
                clean_cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                md_table.append("| " + " | ".join(clean_cells) + " |")

        return "\n" + "\n".join(md_table) + "\n\n"

    s = re.sub(r'<table[^>]*>.*?</table>', replace_table, s, flags=re.DOTALL)

    # Convert Lists
    s = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', s, flags=re.DOTALL)
    s = re.sub(r'<ul[^>]*>', '\n', s)
    s = re.sub(r'</ul>', '\n', s)
    s = re.sub(r'<ol[^>]*>', '\n', s)
    s = re.sub(r'</ol>', '\n', s)

    # Convert Images
    s = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>', r'![\2](\1)\n', s)
    s = re.sub(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>', r'![](\1)\n', s)

    # Convert Links
    s = re.sub(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', lambda m: f"[{re.sub(r'<[^>]+>', '', m.group(2)).strip()}]({m.group(1)})", s, flags=re.DOTALL)

    # Inline formatting
    s = re.sub(r'<strong[^>]*><em>(.*?)</em></strong>', r'***\1***', s, flags=re.DOTALL)
    s = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', s, flags=re.DOTALL)
    s = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', s, flags=re.DOTALL)
    s = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', s, flags=re.DOTALL)
    s = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', s, flags=re.DOTALL)
    s = re.sub(r'<u[^>]*>(.*?)</u>', r'_\1_', s, flags=re.DOTALL)
    s = re.sub(r'<del[^>]*>(.*?)</del>', r'~~\1~~', s, flags=re.DOTALL)
    s = re.sub(r'<mark[^>]*>(.*?)</mark>', r'==\1==', s, flags=re.DOTALL)
    s = re.sub(r'<code[^>]*>(.*?)</code>', r'`\1`', s, flags=re.DOTALL)

    # Convert paragraphs and divs
    s = re.sub(r'<div[^>]*><br[^>]*></div>', '\n\n', s)
    s = re.sub(r'<div[^>]*>(.*?)</div>', r'\1\n', s, flags=re.DOTALL)
    s = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', s, flags=re.DOTALL)
    s = re.sub(r'<br[^>]*>', '\n', s)

    # Strip tags and unescape
    s = re.sub(r'<[^>]+>', '', s)
    s = html.unescape(s)

    # Collapse blank lines
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()
