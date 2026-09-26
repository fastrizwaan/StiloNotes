# SPDX-FileCopyrightText: 2026 Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.markdown_utils import (
    markdown_to_html,
    html_to_markdown,
    extract_title_and_excerpt,
    extract_tags,
    check_has_todo,
    format_relative_date,
)

class TestMarkdown(unittest.TestCase):
    def test_headings_conversion(self):
        md = "# Heading 1\n## Heading 2\n### Heading 3"
        html = markdown_to_html(md)
        self.assertIn("<h1>Heading 1</h1>", html)
        self.assertIn("<h2>Heading 2</h2>", html)
        self.assertIn("<h3>Heading 3</h3>", html)

        back_md = html_to_markdown(html)
        self.assertIn("# Heading 1", back_md)
        self.assertIn("## Heading 2", back_md)

    def test_tasks_conversion(self):
        md = "- [ ] Unfinished task\n- [x] Finished task"
        html = markdown_to_html(md)
        self.assertIn('class="stilo-task"', html)
        self.assertIn('class="stilo-task completed"', html)
        self.assertIn('checked="checked"', html)
        self.assertTrue(check_has_todo(html))

        back_md = html_to_markdown(html)
        self.assertIn("- [ ] Unfinished task", back_md)
        self.assertIn("- [x] Finished task", back_md)

    def test_inline_formatting(self):
        md = "**Bold** and *Italic* and ==Highlight== and ~~Strike~~ and `Code`"
        html = markdown_to_html(md)
        self.assertIn("<strong>Bold</strong>", html)
        self.assertIn("<em>Italic</em>", html)
        self.assertIn('<mark class="stilo-highlight">Highlight</mark>', html)
        self.assertIn("<del>Strike</del>", html)
        self.assertIn('<code class="stilo-inline-code">Code</code>', html)

    def test_title_and_excerpt_extraction(self):
        md = "# My Great Journey\nHere is what happened today on the road.\nIt was amazing."
        title, excerpt = extract_title_and_excerpt(markdown_text=md)
        self.assertEqual(title, "My Great Journey")
        self.assertIn("Here is what happened today", excerpt)

    def test_relative_date(self):
        import time
        now = time.time()
        self.assertEqual(format_relative_date(now - 10), "Just now")
        self.assertEqual(format_relative_date(now - 120), "2m ago")
        self.assertEqual(format_relative_date(now - 7200), "2h ago")

if __name__ == "__main__":
    unittest.main()
