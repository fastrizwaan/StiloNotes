# SPDX-FileCopyrightText: 2026 Mohammed Asif Ali Rizvan
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from stilonotes.markdown_utils import (
    compute_note_stats,
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

    def test_underline_variants(self):
        md1 = "<u>Text One</u>"
        md2 = "<ins>Text Two</ins>"
        md3 = "++Text Three++"
        self.assertIn("<u>Text One</u>", markdown_to_html(md1))
        self.assertIn("<u>Text Two</u>", markdown_to_html(md2))
        self.assertIn("<u>Text Three</u>", markdown_to_html(md3))

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

        # Attribute order variations
        html2 = '<div class="stilo-img-wrapper" contenteditable="false" style="width: 480px;"><img alt="sunset" draggable="false" class="stilo-img" src="file:///sunset.jpg"></div>'
        md2 = html_to_markdown(html2)
        self.assertEqual(md2, "![sunset|480](file:///sunset.jpg)")

    def test_table_conversion(self):
        md = "| Name | Age |\n| :--- | :--- |\n| Alice | 30 |\n| Bob | 25 |"
        html = markdown_to_html(md)
        self.assertIn("<table", html)
        self.assertIn("<th>Name</th>", html)
        self.assertIn("<td>Alice</td>", html)
        back_md = html_to_markdown(html)
        self.assertIn("| Name | Age |", back_md)
        self.assertIn("| Alice | 30 |", back_md)

    def test_compute_note_stats(self):
        html = "<h1>Meeting Notes</h1><div>Discussed project roadmap and deadlines.</div>"
        stats_html = compute_note_stats(content_html=html)
        self.assertEqual(stats_html["words"], 7)
        self.assertEqual(stats_html["paragraphs"], 2)
        self.assertTrue(stats_html["chars"] > 0)
        self.assertEqual(stats_html["readTime"], "1 min")

        md = "# Project Plan\n\nPhase 1 begins next week."
        stats_md = compute_note_stats(content_markdown=md)
        self.assertEqual(stats_md["words"], 7)
        self.assertEqual(stats_md["paragraphs"], 2)

        stats_empty = compute_note_stats("", "")
        self.assertEqual(stats_empty["words"], 0)
        self.assertEqual(stats_empty["paragraphs"], 0)
        self.assertEqual(stats_empty["chars"], 0)
        self.assertEqual(stats_empty["readTime"], "1 min")

    def test_all_heading_levels(self):
        md = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        html = markdown_to_html(md)
        self.assertIn("<h1>H1</h1>", html)
        self.assertIn("<h2>H2</h2>", html)
        self.assertIn("<h3>H3</h3>", html)
        self.assertIn("<h4>H4</h4>", html)
        self.assertIn("<h5>H5</h5>", html)
        self.assertIn("<h6>H6</h6>", html)

        back = html_to_markdown(html)
        self.assertIn("# H1", back)
        self.assertIn("###### H6", back)

    def test_heading_ids(self):
        md = "### My Great Heading {#custom-id}"
        html = markdown_to_html(md)
        self.assertIn('<h3 id="custom-id">My Great Heading</h3>', html)

        back = html_to_markdown(html)
        self.assertIn("### My Great Heading {#custom-id}", back)

    def test_setext_headings(self):
        md = "Major Header\n===\n\nMinor Header\n---"
        html = markdown_to_html(md)
        self.assertIn("<h1>Major Header</h1>", html)
        self.assertIn("<h2>Minor Header</h2>", html)

    def test_subscript_and_superscript(self):
        md = "H~2~O and X^2^ and ~sub~ and ^sup^ and ~~strike~~"
        html = markdown_to_html(md)
        self.assertIn("H<sub>2</sub>O", html)
        self.assertIn("X<sup>2</sup>", html)
        self.assertIn("<sub>sub</sub>", html)
        self.assertIn("<sup>sup</sup>", html)
        self.assertIn("<del>strike</del>", html)

        back = html_to_markdown(html)
        self.assertIn("H~2~O", back)
        self.assertIn("X^2^", back)
        self.assertIn("~~strike~~", back)

    def test_footnotes(self):
        md = "Here is a statement with a footnote. [^1]\n\n[^1]: This is the footnote text."
        html = markdown_to_html(md)
        self.assertIn('class="stilo-footnote-ref"', html)
        self.assertIn('id="fn-1"', html)
        self.assertIn("This is the footnote text.", html)

        back = html_to_markdown(html)
        self.assertIn("[^1]", back)
        self.assertIn("[^1]: This is the footnote text.", back)

    def test_definition_list(self):
        md = "Apple\n: A sweet red fruit\n\nBanana\n: A curved yellow fruit"
        html = markdown_to_html(md)
        self.assertIn('<dl class="stilo-dl">', html)
        self.assertIn('<dt>Apple</dt>', html)
        self.assertIn('<dd>A sweet red fruit</dd>', html)

        back = html_to_markdown(html)
        self.assertIn("Apple", back)
        self.assertIn(": A sweet red fruit", back)

    def test_table_alignment(self):
        md = "| Left | Center | Right |\n| :--- | :---: | ---: |\n| A | B | C |"
        html = markdown_to_html(md)
        self.assertIn('style="text-align: center;"', html)
        self.assertIn('style="text-align: right;"', html)

        back = html_to_markdown(html)
        self.assertIn(":---:", back)
        self.assertIn("---:", back)

    def test_emoji_shortcodes(self):
        md = "That is so funny! :joy: Here is love :heart: and star :star:"
        html = markdown_to_html(md)
        self.assertIn("😂", html)
        self.assertIn("❤️", html)
        self.assertIn("⭐", html)

    def test_autolinks_and_titles(self):
        md = "Visit <https://www.markdownguide.org> or write to <test@example.com>\n[Guide](https://example.com \"My Title\")"
        html = markdown_to_html(md)
        self.assertIn('href="https://www.markdownguide.org"', html)
        self.assertIn('href="mailto:test@example.com"', html)
        self.assertIn('title="My Title"', html)

        back = html_to_markdown(html)
        self.assertIn('[Guide](https://example.com "My Title")', back)

    def test_nested_blockquotes(self):
        md = "> Level 1\n>> Level 2"
        html = markdown_to_html(md)
        self.assertIn('<blockquote class="stilo-quote"><blockquote class="stilo-quote">', html)

    def test_tilde_code_block(self):
        md = "~~~python\nprint('hello')\n~~~"
        html = markdown_to_html(md)
        self.assertIn('class="stilo-code-block" data-lang="python"', html)
        self.assertIn("print(&#x27;hello&#x27;)", html)
        back = html_to_markdown(html)
        self.assertIn("print('hello')", back)

    def test_plus_lists_and_tasks(self):
        md = "+ Item One\n+ Item Two\n+ [ ] Task One\n+ [x] Task Two"
        html = markdown_to_html(md)
        self.assertIn("<li>Item One</li>", html)
        self.assertIn("<li>Item Two</li>", html)
        self.assertIn('class="stilo-task"', html)
        self.assertIn('class="stilo-task completed"', html)

if __name__ == "__main__":
    unittest.main()


