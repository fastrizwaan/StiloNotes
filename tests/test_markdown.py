# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
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
        md = "**Bold** and *Italic* and <u>Underline</u> and ==Highlight== and ~~Strike~~ and `Code`"
        html = markdown_to_html(md)
        self.assertIn("<strong>Bold</strong>", html)
        self.assertIn("<em>Italic</em>", html)
        self.assertIn("<u>Underline</u>", html)
        self.assertIn('<mark class="stilo-highlight">Highlight</mark>', html)
        self.assertIn("<del>Strike</del>", html)
        self.assertIn('<code class="stilo-inline-code">Code</code>', html)

        back_md = html_to_markdown(html)
        self.assertIn("**Bold**", back_md)
        self.assertIn("*Italic*", back_md)
        self.assertIn("<u>Underline</u>", back_md)

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

    def test_image_conversion(self):
        md = "# My Note\n\n![diagram](attachment://att-uuid-1234)\n\nSome text"
        html = markdown_to_html(md)
        self.assertIn('<div class="stilo-img-wrapper"><img src="attachment://att-uuid-1234" alt="diagram" class="stilo-img"></div>', html)
        back_md = html_to_markdown(html)
        self.assertIn("![diagram](attachment://att-uuid-1234)", back_md)

    def test_image_resize_roundtrip(self):
        html = '<div class="stilo-img-wrapper" style="width: 320px;"><img src="attachment://att-999" alt="photo" class="stilo-img"></div>'
        md = html_to_markdown(html)
        self.assertEqual(md, "![photo|320](attachment://att-999)")
        html_back = markdown_to_html(md)
        self.assertIn('style="width: 320px;"', html_back)
        self.assertIn('src="attachment://att-999"', html_back)
        self.assertIn('alt="photo"', html_back)

    def test_table_conversion(self):
        md = "| Name | Age |\n| :--- | :--- |\n| Alice | 30 |\n| Bob | 25 |"
        html = markdown_to_html(md)
        self.assertIn("<table", html)
        self.assertIn("<th>Name</th>", html)
        self.assertIn("<td>Alice</td>", html)
        back_md = html_to_markdown(html)
        self.assertIn("| Name | Age |", back_md)
        self.assertIn("| Alice | 30 |", back_md)

if __name__ == "__main__":
    unittest.main()

