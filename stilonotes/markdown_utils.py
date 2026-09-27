# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import html
import re
import time
from typing import List, Tuple

# Pre-compiled regular expressions for high performance

# check_has_todo
RE_TODO_STILO_TASK = re.compile(r'class=["\']stilo-task')
RE_TODO_STILO_CB = re.compile(r'class=["\']stilo-checkbox')
RE_TODO_MD = re.compile(r'^[-*]\s+\[[ xX]\]', re.MULTILINE)

# strip_markdown
RE_HTML_TAGS = re.compile(r'<[^>]+>')
RE_HEADINGS = re.compile(r'#+\s*')
RE_TASK_BOXES = re.compile(r'[-*]\s+\[[ xX]\]\s*')
RE_LIST_BULLETS = re.compile(r'^[-*+]\s+', re.MULTILINE)
RE_LIST_NUMBERS = re.compile(r'^\d+\.\s+', re.MULTILINE)
RE_BLOCKQUOTES = re.compile(r'>\s*')
RE_DIVIDERS = re.compile(r'(?:---|\*\*\*|___)')
RE_CODE_FENCES = re.compile(r'```.*?```', re.DOTALL)
RE_INLINE_CODE = re.compile(r'`([^`]+)`')
RE_IMAGES = re.compile(r'!\[([^\]]*)\]\([^)]+\)')
RE_LINKS = re.compile(r'\[([^\]]+)\]\([^)]+\)')
RE_BOLD_ITALIC = re.compile(r'\*{1,3}([^*]+)\*{1,3}')
RE_UNDERSCORE = re.compile(r'_{1,3}([^_]+)_{1,3}')
RE_STRIKE = re.compile(r'~~([^~]+)~~')
RE_HIGHLIGHT = re.compile(r'==([^=]+)==')
RE_STRAY_SYMBOLS = re.compile(r'[*_~`#]')
RE_WHITESPACE = re.compile(r'\s+')

# extract_title_and_excerpt
RE_H1_TAG = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
RE_DIV_TAG = re.compile(r'<div[^>]*>')
RE_P_TAG = re.compile(r'<p[^>]*>')
RE_BR_TAG = re.compile(r'<br\s*/?>')

# markdown_to_html inline formatting
RE_MD_BOLD_ITALIC = re.compile(r'\*\*\*([^*]+)\*\*\*')
RE_MD_BOLD = re.compile(r'\*\*([^*]+)\*\*')
RE_MD_ITALIC_STAR = re.compile(r'(?<!\*)\*([^*]+)\*(?!\*)')
RE_MD_ITALIC_UNDER = re.compile(r'(?<!_)_([^_]+)_(?!_)')
RE_MD_UNDERLINE = re.compile(r'&lt;u&gt;(.*?)&lt;/u&gt;', re.IGNORECASE)
RE_MD_INS = re.compile(r'&lt;ins&gt;(.*?)&lt;/ins&gt;', re.IGNORECASE)
RE_MD_HIGHLIGHT = re.compile(r'==([^=]+)==')
RE_MD_STRIKE = re.compile(r'~~([^~]+)~~')
RE_MD_CODE = re.compile(r'`([^`]+)`')
RE_MD_IMAGE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
RE_MD_LINK = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')

# markdown_to_html block formatting
RE_BLOCK_CODE_FENCE = re.compile(r'^```(\w*)\s*$')
RE_BLOCK_TABLE_ROW = re.compile(r'^\|(.+)\|$')
RE_BLOCK_TABLE_SEP = re.compile(r'^[-:]+$')
RE_BLOCK_HR = re.compile(r'^(?:---|\*\*\*|___)\s*$')
RE_BLOCK_TODO = re.compile(r'^[-*]\s+\[([ xX])\]\s*(.*)')
RE_BLOCK_UL = re.compile(r'^[*-]\s+')
RE_BLOCK_OL = re.compile(r'^\d+\.\s+(.*)')

# html_to_markdown
RE_HTM_TASK = re.compile(
    r'<div class="stilo-task[^"]*"[^>]*>\s*<input[^>]*type="checkbox"([^>]*)>\s*<span[^>]*>(.*?)</span>\s*</div>',
    re.DOTALL
)
RE_HTM_H1 = re.compile(r'<h1[^>]*>(.*?)</h1>', re.DOTALL)
RE_HTM_H2 = re.compile(r'<h2[^>]*>(.*?)</h2>', re.DOTALL)
RE_HTM_H3 = re.compile(r'<h3[^>]*>(.*?)</h3>', re.DOTALL)
RE_HTM_H4 = re.compile(r'<h4[^>]*>(.*?)</h4>', re.DOTALL)
RE_HTM_HR = re.compile(r'<hr[^>]*>')
RE_HTM_CODE_LANG = re.compile(r'<pre[^>]*data-lang=["\'](.*?)["\'][^>]*><code[^>]*>(.*?)</code></pre>', re.DOTALL)
RE_HTM_CODE_NO_LANG = re.compile(r'<pre[^>]*><code[^>]*>(.*?)</code></pre>', re.DOTALL)
RE_HTM_QUOTE = re.compile(r'<blockquote[^>]*>(.*?)</blockquote>', re.DOTALL)
RE_HTM_TABLE = re.compile(r'<table[^>]*>.*?</table>', re.DOTALL)
RE_HTM_TH = re.compile(r'<th[^>]*>(.*?)</th>', re.DOTALL)
RE_HTM_TR = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
RE_HTM_TD = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
RE_HTM_LI = re.compile(r'<li[^>]*>(.*?)</li>', re.DOTALL)
RE_HTM_UL_START = re.compile(r'<ul[^>]*>')
RE_HTM_OL_START = re.compile(r'<ol[^>]*>')
RE_HTM_IMG_WITH_WRAPPER = re.compile(
    r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*style=["\'][^"\']*width:\s*(\d+)px[^"\']*["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>\s*</div>',
    re.DOTALL
)
RE_HTM_IMG_WITH_WRAPPER_NO_ALT = re.compile(
    r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*style=["\'][^"\']*width:\s*(\d+)px[^"\']*["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)["\'][^>]*>\s*</div>',
    re.DOTALL
)
RE_HTM_IMG_WRAPPER_PLAIN = re.compile(
    r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>\s*</div>',
    re.DOTALL
)
RE_HTM_IMG_WRAPPER_PLAIN_NO_ALT = re.compile(
    r'<div[^>]*class=["\'][^"\']*stilo-img-wrapper[^"\']*["\'][^>]*>\s*<img[^>]+src=["\']([^"\']+)["\'][^>]*>\s*</div>',
    re.DOTALL
)
RE_HTM_IMG_ALT = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\'][^>]*>')
RE_HTM_IMG_NO_ALT = re.compile(r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>')
RE_HTM_LINK = re.compile(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', re.DOTALL)

RE_HTM_STRONG_EM = re.compile(r'<strong[^>]*><em>(.*?)</em></strong>', re.DOTALL)
RE_HTM_STRONG = re.compile(r'<strong[^>]*>(.*?)</strong>', re.DOTALL)
RE_HTM_B = re.compile(r'<b[^>]*>(.*?)</b>', re.DOTALL)
RE_HTM_EM = re.compile(r'<em[^>]*>(.*?)</em>', re.DOTALL)
RE_HTM_I = re.compile(r'<i[^>]*>(.*?)</i>', re.DOTALL)
RE_HTM_U = re.compile(r'<u[^>]*>(.*?)</u>', re.DOTALL)
RE_HTM_INS = re.compile(r'<ins[^>]*>(.*?)</ins>', re.DOTALL)
RE_HTM_DEL = re.compile(r'<del[^>]*>(.*?)</del>', re.DOTALL)
RE_HTM_MARK = re.compile(r'<mark[^>]*>(.*?)</mark>', re.DOTALL)
RE_HTM_CODE = re.compile(r'<code[^>]*>(.*?)</code>', re.DOTALL)

RE_HTM_DIV_BR = re.compile(r'<div[^>]*><br[^>]*></div>')
RE_HTM_DIV = re.compile(r'<div[^>]*>(.*?)</div>', re.DOTALL)
RE_HTM_P = re.compile(r'<p[^>]*>(.*?)</p>', re.DOTALL)
RE_HTM_BR = re.compile(r'<br[^>]*>')
RE_HTM_MULTI_NEWLINES = re.compile(r'\n{3,}')

MD_SPECIAL_CHARS = set("#*_`[<~=-")


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
        RE_TODO_STILO_TASK.search(content)
        or RE_TODO_STILO_CB.search(content)
        or RE_TODO_MD.search(content)
    )


def extract_tags(text: str) -> List[str]:
    """Deprecated tag extractor; returns empty list as app is category-based."""
    return []


def strip_markdown(text: str) -> str:
    """Clean plain text extraction from Markdown/HTML."""
    if not text:
        return ""
    # Fast path: if no markdown or HTML characters exist, just return stripped text
    if not any(c in MD_SPECIAL_CHARS for c in text):
        return text.strip()

    s = text.replace('\u200b', '')
    s = RE_HTML_TAGS.sub(' ', s)
    s = RE_HEADINGS.sub('', s)
    s = RE_TASK_BOXES.sub('', s)
    s = RE_LIST_BULLETS.sub('', s)
    s = RE_LIST_NUMBERS.sub('', s)
    s = RE_BLOCKQUOTES.sub('', s)
    s = RE_DIVIDERS.sub('', s)
    s = RE_CODE_FENCES.sub('', s)
    s = RE_INLINE_CODE.sub(r'\1', s)
    s = RE_IMAGES.sub(r'\1', s)
    s = RE_LINKS.sub(r'\1', s)
    s = RE_BOLD_ITALIC.sub(r'\1', s)
    s = RE_UNDERSCORE.sub(r'\1', s)
    s = RE_STRIKE.sub(r'\1', s)
    s = RE_HIGHLIGHT.sub(r'\1', s)
    s = RE_STRAY_SYMBOLS.sub('', s)
    s = html.unescape(s)
    return RE_WHITESPACE.sub(' ', s).strip()


def extract_title_and_excerpt(markdown_text: str = "", html_text: str = "") -> Tuple[str, str]:
    """Extract first non-empty line as title, and subsequent text as excerpt."""
    title = "Untitled Note"
    excerpt = ""

    lines = []
    if markdown_text:
        lines = [line.strip() for line in markdown_text.splitlines() if line.strip()]
    elif html_text:
        clean = RE_H1_TAG.sub(r'\1\n', html_text)
        clean = RE_DIV_TAG.sub('\n', clean)
        clean = RE_P_TAG.sub('\n', clean)
        clean = RE_BR_TAG.sub('\n', clean)
        clean = RE_HTML_TAGS.sub(' ', clean)
        lines = [line.strip() for line in html.unescape(clean).splitlines() if line.strip()]

    if lines:
        title = strip_markdown(lines[0]) or "Untitled Note"
        if len(lines) > 1:
            raw_excerpt = " ".join(lines[1:5])
            excerpt = strip_markdown(raw_excerpt)[:160]

    return title, excerpt


def _format_md_image(match: re.Match) -> str:
    alt = match.group(1)
    src = match.group(2)
    width_style = ""
    clean_alt = alt
    if "|" in alt:
        parts = alt.rsplit("|", 1)
        w_str = parts[1].strip()
        if w_str.endswith("px"):
            w_str = w_str[:-2].strip()
        if w_str.isdigit():
            width_style = f' style="width: {w_str}px;"'
            clean_alt = parts[0].strip()
    return f'<div class="stilo-img-wrapper"{width_style}><img src="{src}" alt="{clean_alt}" class="stilo-img"></div>'


def markdown_to_html(md_text: str) -> str:
    """Convert Markdown text to Stilo rich HTML."""
    if not md_text:
        return "<h1>Untitled Note</h1><div><br></div>"

    def format_inline(text: str) -> str:
        s = html.escape(text)
        s = RE_MD_IMAGE.sub(_format_md_image, s)
        s = RE_MD_BOLD_ITALIC.sub(r'<strong><em>\1</em></strong>', s)
        s = RE_MD_BOLD.sub(r'<strong>\1</strong>', s)
        s = RE_MD_ITALIC_STAR.sub(r'<em>\1</em>', s)
        s = RE_MD_ITALIC_UNDER.sub(r'<em>\1</em>', s)
        s = RE_MD_UNDERLINE.sub(r'<u>\1</u>', s)
        s = RE_MD_INS.sub(r'<u>\1</u>', s)
        s = RE_MD_HIGHLIGHT.sub(r'<mark class="stilo-highlight">\1</mark>', s)
        s = RE_MD_STRIKE.sub(r'<del>\1</del>', s)
        s = RE_MD_CODE.sub(r'<code class="stilo-inline-code">\1</code>', s)
        s = RE_MD_LINK.sub(r'<a href="\2" class="stilo-link" target="_blank">\1</a>', s)
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
            if not cells or all(RE_BLOCK_TABLE_SEP.match(c) for c in cells):
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
        code_fence = RE_BLOCK_CODE_FENCE.match(line)
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
        if RE_BLOCK_TABLE_ROW.match(line.strip()):
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
        if RE_BLOCK_HR.match(line):
            html_lines.append(close_lists())
            html_lines.append('<hr class="stilo-hr">')
            continue

        # Todo checklist: - [ ] or - [x]
        todo_match = RE_BLOCK_TODO.match(line)
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
        if RE_BLOCK_UL.match(line):
            if in_ol:
                html_lines.append("</ol>")
                in_ol = False
            if not in_ul:
                html_lines.append('<ul class="stilo-list">')
                in_ul = True
            content = RE_BLOCK_UL.sub('', line)
            html_lines.append(f"<li>{format_inline(content)}</li>")
            continue

        # Ordered list: 1.
        ol_match = RE_BLOCK_OL.match(line)
        if ol_match:
            if in_ul:
                html_lines.append("</ul>")
                in_ul = False
            if not in_ol:
                html_lines.append('<ol class="stilo-numbered-list">')
                in_ol = True
            html_lines.append(f"<li>{format_inline(ol_match.group(1))}</li>")
            continue

        # Standalone Image line: ![alt](url)
        img_match = RE_MD_IMAGE.match(line.strip())
        if img_match:
            html_lines.append(close_lists())
            html_lines.append(_format_md_image(img_match))
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

    s = html_content.replace('\r\n', '\n').replace('\r', '\n')

    # Convert Stilo Tasks
    def replace_task(m):
        checked = 'checked' in m.group(1)
        text = RE_HTML_TAGS.sub('', m.group(2)).strip()
        mark = 'x' if checked else ' '
        return f"- [{mark}] {text}\n"

    s = RE_HTM_TASK.sub(replace_task, s)

    # Convert Headings
    s = RE_HTM_H1.sub(r'# \1\n\n', s)
    s = RE_HTM_H2.sub(r'## \1\n\n', s)
    s = RE_HTM_H3.sub(r'### \1\n\n', s)
    s = RE_HTM_H4.sub(r'#### \1\n\n', s)

    # Convert Horizontal Rules
    s = RE_HTM_HR.sub('\n---\n\n', s)

    # Convert Code Blocks
    def replace_code_block(m):
        lang = m.group(1) or ""
        code = html.unescape(m.group(2))
        return f"\n```{lang}\n{code}\n```\n\n"

    s = RE_HTM_CODE_LANG.sub(replace_code_block, s)
    s = RE_HTM_CODE_NO_LANG.sub(lambda m: f"\n```\n{html.unescape(m.group(1))}\n```\n\n", s)

    # Convert Blockquotes
    s = RE_HTM_QUOTE.sub(lambda m: f"> {RE_HTML_TAGS.sub('', m.group(1)).strip()}\n\n", s)

    # Convert Tables
    def replace_table(m):
        table_html = m.group(0)
        headers = RE_HTM_TH.findall(table_html)
        rows = RE_HTM_TR.findall(table_html)

        md_table = []
        if headers:
            clean_headers = [RE_HTML_TAGS.sub('', h).strip() for h in headers]
            md_table.append("| " + " | ".join(clean_headers) + " |")
            md_table.append("| " + " | ".join([":---" for _ in clean_headers]) + " |")

        for r in rows:
            cells = RE_HTM_TD.findall(r)
            if cells:
                clean_cells = [RE_HTML_TAGS.sub('', c).strip() for c in cells]
                md_table.append("| " + " | ".join(clean_cells) + " |")

        return "\n" + "\n".join(md_table) + "\n\n"

    s = RE_HTM_TABLE.sub(replace_table, s)

    # Convert Lists
    s = RE_HTM_LI.sub(r'- \1\n', s)
    s = RE_HTM_UL_START.sub('\n', s)
    s = s.replace('</ul>', '\n')
    s = RE_HTM_OL_START.sub('\n', s)
    s = s.replace('</ol>', '\n')

    # Convert Images
    s = RE_HTM_IMG_WITH_WRAPPER.sub(r'![\3|\1](\2)\n', s)
    s = RE_HTM_IMG_WITH_WRAPPER_NO_ALT.sub(r'![|\1](\2)\n', s)
    s = RE_HTM_IMG_WRAPPER_PLAIN.sub(r'![\2](\1)\n', s)
    s = RE_HTM_IMG_WRAPPER_PLAIN_NO_ALT.sub(r'![](\1)\n', s)
    s = RE_HTM_IMG_ALT.sub(r'![\2](\1)\n', s)
    s = RE_HTM_IMG_NO_ALT.sub(r'![](\1)\n', s)

    # Convert Links
    s = RE_HTM_LINK.sub(lambda m: f"[{RE_HTML_TAGS.sub('', m.group(2)).strip()}]({m.group(1)})", s)

    # Inline formatting
    s = RE_HTM_STRONG_EM.sub(r'***\1***', s)
    s = RE_HTM_STRONG.sub(r'**\1**', s)
    s = RE_HTM_B.sub(r'**\1**', s)
    s = RE_HTM_EM.sub(r'*\1*', s)
    s = RE_HTM_I.sub(r'*\1*', s)
    s = RE_HTM_U.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', s)
    s = RE_HTM_INS.sub(r'@@STILO_U_START@@\1@@STILO_U_END@@', s)
    s = RE_HTM_DEL.sub(r'~~\1~~', s)
    s = RE_HTM_MARK.sub(r'==\1==', s)
    s = RE_HTM_CODE.sub(r'`\1`', s)

    # Convert paragraphs and divs
    s = RE_HTM_DIV_BR.sub('\n\n', s)
    s = RE_HTM_DIV.sub(r'\1\n', s)
    s = RE_HTM_P.sub(r'\1\n\n', s)
    s = RE_HTM_BR.sub('\n', s)

    # Strip remaining tags and unescape
    s = RE_HTML_TAGS.sub('', s)
    s = html.unescape(s)
    s = s.replace('@@STILO_U_START@@', '<u>').replace('@@STILO_U_END@@', '</u>')
    s = s.replace('\u200b', '')

    # Collapse blank lines
    s = RE_HTM_MULTI_NEWLINES.sub('\n\n', s)
    return s.strip()
