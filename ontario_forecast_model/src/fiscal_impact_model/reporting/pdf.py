"""Render a docs/*.md page (text, tables, images) to a shareable PDF with reportlab.

    python -m fiscal_impact_model.reporting.pdf docs/03_conclusions.md     -> outputs/docs/conclusions.pdf

The Markdown file stays the single source: the PDF is regenerated from it, so it never
drifts from the docs. Supports the subset our docs use: headings, paragraphs, bullet and
numbered lists, blockquotes, tables, images, bold/italic/code/links. Navigation lines
("[← Methods](...) · [README](...)") are skipped. Fonts: DejaVu Sans (ships with
matplotlib), so →, −, ≈ and ¢ render and the text matches the charts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from fiscal_impact_model import config

INK, INK_2, GRID, ACCENT = "#0b0b0b", "#52514e", "#e6e5e1", "#2a78d6"
PAGE_W, PAGE_H = letter
MARGIN = 0.75 * inch
BODY_W = PAGE_W - 2 * MARGIN


def _register_fonts() -> tuple[str, str]:
    ttf = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    pdfmetrics.registerFont(TTFont("DejaVu", str(ttf / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(ttf / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(ttf / "DejaVuSans-Oblique.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVu-Mono", str(ttf / "DejaVuSansMono.ttf")))
    pdfmetrics.registerFontFamily(
        "DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-Bold"
    )
    return "DejaVu", "DejaVu-Bold"


def _styles() -> dict[str, ParagraphStyle]:
    body, bold = _register_fonts()
    base = ParagraphStyle(
        "body", fontName=body, fontSize=9.5, leading=14, textColor=INK, alignment=TA_LEFT, spaceAfter=8
    )
    return {
        "body": base,
        # keepWithNext: a heading never sits alone at the bottom of a page, apart from its content
        "h1": ParagraphStyle(
            "h1", parent=base, fontName=bold, fontSize=20, leading=24, spaceAfter=10, keepWithNext=1
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName=bold,
            fontSize=13.5,
            leading=17,
            spaceBefore=20,
            spaceAfter=8,
            keepWithNext=1,
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base,
            fontName=bold,
            fontSize=11,
            leading=14,
            spaceBefore=16,
            spaceAfter=6,
            keepWithNext=1,
        ),
        "quote": ParagraphStyle(
            "quote",
            parent=base,
            textColor=INK_2,
            fontSize=9,
            leading=12.5,
            leftIndent=10,
            borderPadding=(6, 6, 6, 8),
            backColor="#f4f3f0",
            spaceBefore=6,
            spaceAfter=14,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.2, leading=10.5, spaceAfter=0),
        "cell_head": ParagraphStyle(
            "cell_head", parent=base, fontName=bold, fontSize=8.2, leading=10.5, spaceAfter=0
        ),
        "caption": ParagraphStyle(
            "caption", parent=base, fontSize=7.5, textColor=INK_2, alignment=1, spaceAfter=2
        ),
    }


# ---- inline Markdown -> reportlab mini-HTML ----------------------------------
def inline(text: str) -> str:
    t = escape(text)
    t = re.sub(r"`([^`]+)`", r'<font face="DejaVu-Mono" size="8">\1</font>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", t)
    # external links stay clickable; links to other repo files become plain text
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", rf'<link href="\2" color="{ACCENT}">\1</link>', t)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return t


# ---- block parsing ------------------------------------------------------------
_IMG = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
_LIST = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")


def _is_nav(line: str) -> bool:
    return line.startswith("[←") or line.startswith("[README]")


BODY_H = PAGE_H - 2 * MARGIN


def _image(path: Path, caption: str, st) -> list:
    """Chart sized to sit WITH its section text instead of filling a page.

    Wide charts are capped at ~33% of the page height (two fit on a page with text), so
    a chart rarely jumps to the next page and leaves a gap. Tall charts (e.g. the
    sensitivity chart with many labels) get up to 62% so their labels stay readable.
    """
    w, h = ImageReader(str(path)).getSize()
    max_h = BODY_H * (0.62 if h / w > 0.8 else 0.33)
    scale = min(BODY_W / w, max_h / h)
    img = Image(str(path), width=w * scale, height=h * scale)
    img.hAlign = "CENTER"
    # Chain spacer -> chart -> caption with keepWithNext. reportlab won't group a heading with a
    # KeepTogether block, so a chain is what lets a heading move with its chart to the next page.
    top = Spacer(1, 4)
    top.keepWithNext = img.keepWithNext = 1
    return [top, img, Paragraph(escape(caption), st["caption"]), Spacer(1, 12)]


def _table(rows: list[list[str]], st) -> Table:
    ncol = len(rows[0])

    # Column widths proportional to the visible text length (markdown markers don't count),
    # capped at 60 characters, with a floor wide enough that a short label like "R1" never wraps.
    def visible(c: str) -> int:
        return len(re.sub(r"[*`]|\[([^\]]*)\]\([^)]*\)", r"\1", c))

    lens = [[min(visible(r[c]) if c < len(r) else 0, 60) for r in rows] for c in range(ncol)]
    per_col = [max(col) for col in lens]
    widths = [BODY_W * x / sum(per_col) for x in per_col]
    # Floor per column: room for its longest word (~6pt per bold character at 8.2pt, plus padding),
    # so words like "Destination" never break mid-word, and never under 7% of the page width.
    longest = [
        max((len(w) for r in rows if c < len(r) for w in re.sub(r"[*`]", "", r[c]).split()), default=0)
        for c in range(ncol)
    ]
    floors = [max(BODY_W * 0.07, 6.0 * n + 10) for n in longest]
    short = [w < f for w, f in zip(widths, floors, strict=True)]
    if any(short) and not all(short):
        spare = BODY_W - sum(f for f, s in zip(floors, short, strict=True) if s)
        rest = sum(w for w, s in zip(widths, short, strict=True) if not s)
        widths = [f if s else w * spare / rest for w, f, s in zip(widths, floors, short, strict=True)]
    padded = [r + [""] * (ncol - len(r)) for r in rows]
    data = [
        [Paragraph(inline(cell), st["cell_head" if i == 0 else "cell"]) for cell in r]
        for i, r in enumerate(padded)
    ]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(INK_2)),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor(GRID)),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _parse_list(lines: list[str], i: int, st) -> tuple[ListFlowable, int]:
    """Parse a (possibly nested) list starting at line i. Deeper-indented items become a
    sub-list attached to the previous item; wrapped continuation lines join their item."""
    indent = len(_LIST.match(lines[i]).group(1))
    numbered = bool(re.match(r"^\s*\d+\.", lines[i]))
    items: list[list] = []
    while i < len(lines):
        m = _LIST.match(lines[i])
        if m and len(m.group(1)) == indent:
            text, i = m.group(3), i + 1
            while (
                i < len(lines)
                and lines[i].strip()
                and not _LIST.match(lines[i])
                and lines[i].startswith(" " * (indent + 2))
            ):
                text += " " + lines[i].strip()
                i += 1
            items.append([Paragraph(inline(text), st["body"])])
        elif m and len(m.group(1)) > indent and items:
            sub, i = _parse_list(lines, i, st)
            items[-1].append(sub)
        else:
            break
    flow = [ListItem(parts if len(parts) > 1 else parts[0]) for parts in items]
    return ListFlowable(
        flow,
        bulletType="1" if numbered else "bullet",
        start="1" if numbered else "•",
        bulletFontName="DejaVu",
        bulletFontSize=8,
        leftIndent=14,
    ), i


def markdown_to_flowables(md: str, base_dir: Path) -> tuple[str, list]:
    """Returns (title, flowables). Images resolve relative to the Markdown file."""
    st = _styles()
    lines = md.splitlines()
    out, title, i = [], "", 0

    block_start = re.compile(r"^(#|>|\||!\[|[-*] |\d+\. )")  # a new block ends the paragraph

    def take_paragraph(start: int) -> tuple[str, int]:
        buf, j = [lines[start].strip()], start + 1
        while j < len(lines) and lines[j].strip() and not block_start.match(lines[j].strip()):
            buf.append(lines[j].strip())
            j += 1
        return " ".join(buf), j

    while i < len(lines):
        raw = lines[i]
        line = raw.strip()
        if not line or _is_nav(line):
            i += 1
        elif line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            text = line[level:].strip()
            if level == 1 and not title:
                title = text
            out.append(Paragraph(inline(text), st[f"h{min(level, 3)}"]))
            i += 1
        elif line.startswith(">"):
            paras, cur = [], []
            while i < len(lines) and lines[i].strip().startswith(">"):
                text = lines[i].strip()[1:].strip()
                if text:
                    cur.append(text)
                elif cur:  # a blank ">" line separates paragraphs inside one quote
                    paras.append(" ".join(cur))
                    cur = []
                i += 1
            paras += [" ".join(cur)] if cur else []
            out += [Paragraph(inline(p), st["quote"]) for p in paras]
        elif line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            lead = Spacer(1, 2)
            lead.keepWithNext = 1  # lets a heading above stay with its table
            out += [lead, _table(rows, st), Spacer(1, 14)]
        elif _IMG.match(line):
            while i < len(lines) and _IMG.match(lines[i].strip()):
                alt, src = _IMG.match(lines[i].strip()).groups()
                path = (base_dir / src).resolve()
                if path.exists():
                    out += _image(path, alt, st)
                i += 1
        elif _LIST.match(raw):
            flowable, i = _parse_list(lines, i, st)
            out.append(flowable)
        else:
            text, i = take_paragraph(i)
            out.append(Paragraph(inline(text), st["body"]))
    return title or "Document", out


SUBTITLE = "Connecting Ontario · Sunstone @ USC Price"


def build_pdf(md_path: Path, out_path: Path, subtitle: str = SUBTITLE) -> Path:
    md_path, out_path = Path(md_path), Path(out_path)
    title, story = markdown_to_flowables(md_path.read_text(encoding="utf-8"), md_path.parent)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("DejaVu", 7.5)
        canvas.setFillColor(colors.HexColor(INK_2))
        canvas.drawString(MARGIN, 0.45 * inch, f"{subtitle} · {title}")
        canvas.drawRightString(PAGE_W - MARGIN, 0.45 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN,
        title=title,
        author="Sunstone team",
        invariant=1,
    )  # invariant: no timestamps, so reruns don't change the file
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(f"  -> {out_path.relative_to(config.ROOT)}")
    return out_path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    paths = [Path(p) for p in args] or [config.ROOT / "docs" / "03_conclusions.md"]
    for p in paths:
        p = p if p.is_absolute() else config.ROOT / p
        # docs are numbered for reading order (03_conclusions.md); the PDF keeps a clean name
        name = re.sub(r"^\d+_", "", p.stem)
        build_pdf(p, config.DOCS_PDF_DIR / f"{name}.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
