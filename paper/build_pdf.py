"""Render a note's README.md to a PDF with reportlab.

    python paper/build_pdf.py paper/01-where-not-whether where-not-whether-v0.1.pdf

Deliberately small: it handles the Markdown these notes use (headings, paragraphs,
bullets, pipe tables, fenced code, images, bold/italic/inline code) and nothing else."""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent
SOURCE = HERE / "README.md"
OUTPUT = HERE / (sys.argv[2] if len(sys.argv) > 2 else "note.pdf")

styles = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=styles["Normal"], fontName="Helvetica", fontSize=9.5, leading=13, alignment=TA_JUSTIFY, spaceAfter=6)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=10.5, alignment=0)
TITLE = ParagraphStyle("title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=21, spaceAfter=8)
AUTHOR = ParagraphStyle("author", parent=BODY, fontSize=10, alignment=1, spaceAfter=2)
META = ParagraphStyle("meta", parent=BODY, fontSize=8, alignment=1, textColor=colors.HexColor("#444444"), spaceAfter=10)
H2 = ParagraphStyle("h2", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("h3", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10, leading=13, spaceBefore=6, spaceAfter=3)
CODE = ParagraphStyle("code", parent=styles["Code"], fontName="Courier", fontSize=7.5, leading=9.5, leftIndent=6, backColor=colors.HexColor("#f4f4f4"), spaceAfter=6)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=7.8, leading=9.8, alignment=0, spaceAfter=0)
CELL_HEAD = ParagraphStyle("cellhead", parent=CELL, fontName="Helvetica-Bold")
CAPTION = ParagraphStyle("caption", parent=SMALL, alignment=TA_JUSTIFY, spaceBefore=3, spaceAfter=8)


def inline(text: str) -> str:
    """Markdown inline -> reportlab paragraph markup."""
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r'<font face="Courier" size="8.3">\1</font>', text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*([^*]+)\*(?![\w*])", r"<i>\1</i>", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<link href="\2" color="#1a4d8f">\1</link>', text)
    text = re.sub(r"(?<![\"'>])(https?://[^\s<]+)", r'<link href="\1" color="#1a4d8f">\1</link>', text)
    return text


def table(lines: list[str], width: float) -> Table:
    rows = []
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    rows = [r for r in rows if not all(re.fullmatch(r":?-{2,}:?", c) for c in r)]
    ncols = max(len(r) for r in rows)
    data = []
    for i, r in enumerate(rows):
        r = r + [""] * (ncols - len(r))
        data.append([Paragraph(inline(c), CELL_HEAD if i == 0 else CELL) for c in r])
    # first column a little narrower than the rest unless it is the only wide one
    col = width / ncols
    widths = [col * 0.85] + [(width - col * 0.85) / (ncols - 1)] * (ncols - 1) if ncols > 1 else [width]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 0.4, colors.black),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def build() -> Path:
    text = SOURCE.read_text(encoding="utf-8").splitlines()
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
        title=SOURCE.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip(), author="Ava Kim",
    )
    width = A4[0] - 40 * mm
    story = []
    i = 0
    para: list[str] = []
    bullets: list[str] = []

    def flush_para() -> None:
        if para:
            story.append(Paragraph(inline(" ".join(para)), BODY))
            para.clear()

    def flush_bullets() -> None:
        if bullets:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(inline(b), BODY), leftIndent=10) for b in bullets],
                    bulletType="bullet", start="•", leftIndent=12, bulletFontSize=8,
                )
            )
            bullets.clear()

    while i < len(text):
        line = text[i]
        stripped = line.strip()
        if stripped.startswith("# "):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped[2:]), TITLE))
        elif stripped.startswith("## "):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped[3:]), H2))
        elif stripped.startswith("### "):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped[4:]), H3))
        elif stripped.startswith("```"):
            flush_para(); flush_bullets()
            block = []
            i += 1
            while i < len(text) and not text[i].strip().startswith("```"):
                block.append(text[i])
                i += 1
            story.append(Preformatted("\n".join(block), CODE))
        elif stripped.startswith("|"):
            flush_para(); flush_bullets()
            block = []
            while i < len(text) and text[i].strip().startswith("|"):
                block.append(text[i])
                i += 1
            story.append(table(block, width))
            story.append(Spacer(1, 4))
            continue
        elif stripped.startswith("- "):
            flush_para()
            bullets.append(stripped[2:])
        elif stripped.startswith("!["):
            flush_para(); flush_bullets()
            m = re.match(r"!\[[^\]]*\]\(([^)]+)\)", stripped)
            if m:
                img_path = HERE / m.group(1)
                img = Image(str(img_path))
                ratio = width / img.imageWidth
                img.drawWidth = width
                img.drawHeight = img.imageHeight * ratio
                story.append(img)
        elif stripped.startswith("**Ava Kim**"):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped), AUTHOR))
        elif stripped.startswith("Repository:"):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped), META))
        elif stripped.startswith("**Figure") or stripped.startswith("**Table"):
            flush_para(); flush_bullets()
            story.append(Paragraph(inline(stripped), CAPTION))
        elif stripped == "":
            flush_para(); flush_bullets()
        else:
            if bullets and line.startswith("  "):
                bullets[-1] += " " + stripped
            else:
                flush_bullets()
                para.append(stripped)
        i += 1
    flush_para(); flush_bullets()
    doc.build(story)
    return OUTPUT


if __name__ == "__main__":
    print(build())
