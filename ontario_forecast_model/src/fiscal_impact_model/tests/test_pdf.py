"""Markdown -> PDF: every block type our docs use converts, and a PDF is written."""

from reportlab.platypus import Image, ListFlowable, Paragraph, Table

from fiscal_impact_model.reporting.pdf import build_pdf, inline, markdown_to_flowables

SAMPLE = """# Conclusions

[← Methods](02_methods.md) · [README](../README.md)

> **Key:** R1 Career Pathways · R2 Stay +1

Bottom line: **76¢** back per $1 −
continued on a second line.

| Group | Return |
|---|---|
| R4 + R1→R4 | **$1.11** |

1. First step
   wraps here
2. Second step
   - nested bullet under step 2

- bullet with `code` and a [link](https://example.com)

![chart](chart.png)
"""


def test_inline_markup():
    assert inline("**a** and *b* `c`") == '<b>a</b> and <i>b</i> <font face="DejaVu-Mono" size="8">c</font>'
    assert inline("[doc](02_methods.md)") == "doc"  # repo links become plain text
    assert 'href="https://x.org"' in inline("[x](https://x.org)")
    assert inline("a < b & c") == "a &lt; b &amp; c"


def test_blocks_convert_and_nav_is_skipped(tmp_path):
    title, flow = markdown_to_flowables(SAMPLE, tmp_path)  # chart.png missing -> skipped, not an error
    assert title == "Conclusions"
    assert sum(isinstance(f, Table) for f in flow) == 1
    assert sum(isinstance(f, ListFlowable) for f in flow) == 2  # nested bullet stays inside the numbered list
    texts = " ".join(f.text for f in flow if isinstance(f, Paragraph))
    assert "README" not in texts  # navigation line dropped
    assert "continued on a second line" in texts  # wrapped paragraph joined
    assert not any(isinstance(f, Image) for f in flow)


def test_build_pdf_writes_file(tmp_path, monkeypatch):
    md = tmp_path / "doc.md"
    md.write_text("# Title\n\nBody with → and −\n\n| a | b |\n|---|---|\n| 1 | 2 |\n", encoding="utf-8")
    monkeypatch.setattr("fiscal_impact_model.config.ROOT", tmp_path)
    out = build_pdf(md, tmp_path / "out" / "doc.pdf")
    assert out.exists() and out.read_bytes().startswith(b"%PDF")
