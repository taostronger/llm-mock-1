from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "技术报告.md"
OUTPUT = ROOT / "技术报告.pdf"

PAGE_W, PAGE_H = A4
LEFT = 20 * mm
RIGHT = 18 * mm
TOP = 19 * mm
BOTTOM = 18 * mm
CONTENT_W = PAGE_W - LEFT - RIGHT

NAVY = colors.HexColor("#17324D")
BLUE = colors.HexColor("#2D5F88")
ACCENT = colors.HexColor("#C7000B")
LIGHT_BLUE = colors.HexColor("#EAF1F7")
LIGHT_GRAY = colors.HexColor("#F4F6F8")
MID_GRAY = colors.HexColor("#D8DEE5")
TEXT = colors.HexColor("#202832")
MUTED = colors.HexColor("#5A6875")


def register_fonts() -> None:
    pdfmetrics.registerFont(TTFont("SimSun", r"C:\Windows\Fonts\simsun.ttc"))
    pdfmetrics.registerFont(TTFont("SimHei", r"C:\Windows\Fonts\simhei.ttf"))
    pdfmetrics.registerFont(TTFont("Consolas", r"C:\Windows\Fonts\consola.ttf"))
    pdfmetrics.registerFont(TTFont("Consolas-Bold", r"C:\Windows\Fonts\consolab.ttf"))
    pdfmetrics.registerFontFamily(
        "SimSun", normal="SimSun", bold="SimHei", italic="SimSun", boldItalic="SimHei"
    )
    pdfmetrics.registerFontFamily(
        "Consolas", normal="Consolas", bold="Consolas-Bold",
        italic="Consolas", boldItalic="Consolas-Bold"
    )


register_fonts()


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="SimHei", fontSize=32,
            leading=43, textColor=NAVY, alignment=TA_CENTER, spaceAfter=10 * mm,
        ),
        "cover_subtitle": ParagraphStyle(
            "CoverSubtitle", fontName="SimHei", fontSize=15, leading=24,
            textColor=BLUE, alignment=TA_CENTER, spaceAfter=18 * mm,
        ),
        "cover_meta": ParagraphStyle(
            "CoverMeta", fontName="SimSun", fontSize=11, leading=20,
            textColor=TEXT, alignment=TA_CENTER,
        ),
        "cover_note": ParagraphStyle(
            "CoverNote", fontName="SimSun", fontSize=9, leading=15,
            textColor=MUTED, alignment=TA_LEFT, wordWrap="CJK",
        ),
        "caption": ParagraphStyle(
            "FigureCaption", fontName="SimSun", fontSize=8.7, leading=13,
            textColor=MUTED, alignment=TA_CENTER, wordWrap="CJK",
            spaceBefore=1.5 * mm, spaceAfter=3.5 * mm,
        ),
        "h1": ParagraphStyle(
            "Heading1CN", fontName="SimHei", fontSize=20, leading=28,
            textColor=NAVY, spaceBefore=4 * mm, spaceAfter=5 * mm,
            keepWithNext=True, wordWrap="CJK",
        ),
        "h2": ParagraphStyle(
            "Heading2CN", fontName="SimHei", fontSize=15, leading=22,
            textColor=NAVY, spaceBefore=5 * mm, spaceAfter=3 * mm,
            keepWithNext=True, wordWrap="CJK",
        ),
        "h3": ParagraphStyle(
            "Heading3CN", fontName="SimHei", fontSize=12.2, leading=18,
            textColor=BLUE, spaceBefore=4 * mm, spaceAfter=2 * mm,
            keepWithNext=True, wordWrap="CJK",
        ),
        "h4": ParagraphStyle(
            "Heading4CN", fontName="SimHei", fontSize=10.8, leading=16,
            textColor=TEXT, spaceBefore=3 * mm, spaceAfter=1.5 * mm,
            keepWithNext=True, wordWrap="CJK",
        ),
        "body": ParagraphStyle(
            "BodyCN", fontName="SimSun", fontSize=9.6, leading=16.2,
            textColor=TEXT, alignment=TA_JUSTIFY, firstLineIndent=19.2,
            spaceAfter=2.4 * mm, wordWrap="CJK", splitLongWords=True,
        ),
        "bullet": ParagraphStyle(
            "BulletCN", fontName="SimSun", fontSize=9.4, leading=15.5,
            textColor=TEXT, leftIndent=7 * mm, firstLineIndent=0,
            bulletIndent=2 * mm, spaceAfter=1.2 * mm, wordWrap="CJK",
        ),
        "quote": ParagraphStyle(
            "QuoteCN", fontName="SimSun", fontSize=9, leading=15,
            textColor=colors.HexColor("#374957"), leftIndent=1 * mm,
            rightIndent=1 * mm, wordWrap="CJK",
        ),
        "code": ParagraphStyle(
            "Code", fontName="Consolas", fontSize=7.2, leading=10.3,
            textColor=colors.HexColor("#243746"), leftIndent=3 * mm,
            rightIndent=3 * mm, spaceBefore=1 * mm, spaceAfter=2 * mm,
        ),
        "table_head": ParagraphStyle(
            "TableHead", fontName="SimHei", fontSize=8.2, leading=11.2,
            textColor=colors.white, alignment=TA_LEFT, wordWrap="CJK",
        ),
        "table_body": ParagraphStyle(
            "TableBody", fontName="SimSun", fontSize=7.8, leading=11.2,
            textColor=TEXT, alignment=TA_LEFT, wordWrap="CJK", splitLongWords=True,
        ),
        "toc_title": ParagraphStyle(
            "TOCTitle", fontName="SimHei", fontSize=22, leading=30,
            textColor=NAVY, alignment=TA_CENTER, spaceAfter=8 * mm,
        ),
    }


STYLES = make_styles()


def strip_md(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    return text.replace("**", "").replace("`", "").strip()


def inline_markup(text: str) -> str:
    value = html.escape(text, quote=True)
    value = re.sub(
        r"\[([^\]]+)\]\(([^\)]+)\)",
        lambda m: f'<link href="{m.group(2)}" color="#2D5F88">{m.group(1)}</link>',
        value,
    )
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(
        r"`([^`]+)`",
        r'<font name="Consolas" size="8" color="#7A1F2B">\1</font>',
        value,
    )
    return value.replace("  ", " ")


def display_len(text: str) -> int:
    return sum(2 if ord(ch) > 255 else 1 for ch in strip_md(text))


def column_widths(rows: list[list[str]]) -> list[float]:
    n = max(len(r) for r in rows)
    weights = []
    for col in range(n):
        longest = max((display_len(r[col]) if col < len(r) else 0) for r in rows)
        weights.append(max(5.5, min(28.0, float(longest))))
    total = sum(weights)
    widths = [CONTENT_W * w / total for w in weights]
    min_width = 24 * mm
    for idx, width in enumerate(widths):
        widths[idx] = max(min_width if n <= 4 else 16 * mm, width)
    scale = CONTENT_W / sum(widths)
    return [w * scale for w in widths]


def markdown_table(lines: list[str]):
    raw_rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    rows = [r for r in raw_rows if not all(re.fullmatch(r":?-{3,}:?", c or "") for c in r)]
    if not rows:
        return Spacer(1, 1)
    cols = max(len(r) for r in rows)
    rows = [r + [""] * (cols - len(r)) for r in rows]
    formatted = []
    for ridx, row in enumerate(rows):
        style = STYLES["table_head"] if ridx == 0 else STYLES["table_body"]
        formatted.append([Paragraph(inline_markup(cell), style) for cell in row])
    table = LongTable(
        formatted, colWidths=column_widths(rows), repeatRows=1,
        hAlign="LEFT", splitByRow=1, spaceBefore=1.5 * mm, spaceAfter=3 * mm,
    )
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, MID_GRAY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for ridx in range(1, len(formatted)):
        if ridx % 2 == 0:
            commands.append(("BACKGROUND", (0, ridx), (-1, ridx), LIGHT_GRAY))
    table.setStyle(TableStyle(commands))
    return table


def code_block(text: str):
    wrapped: list[str] = []
    for line in text.splitlines() or [""]:
        if len(line) <= 92:
            wrapped.append(line)
        else:
            parts = textwrap.wrap(
                line, width=92, subsequent_indent="    ",
                replace_whitespace=False, drop_whitespace=False,
            )
            wrapped.extend(parts or [line])
    pre = Preformatted("\n".join(wrapped), STYLES["code"])
    box = Table([[pre]], colWidths=[CONTENT_W], hAlign="LEFT")
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F4F6")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D1DA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return box


class TechDocTemplate(SimpleDocTemplate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._bookmark_id = 0

    def afterFlowable(self, flowable):
        if not isinstance(flowable, Paragraph):
            return
        style_name = flowable.style.name
        # 正文从 Markdown 二级标题“摘要”开始解析，因此将一级分部标题和
        # 二级章节标题都作为 PDF 书签/目录的顶层，三级标题作为其子级。
        # 这样既保留正文层次，也避免首个书签直接跳到 level=1。
        levels = {"Heading1CN": 0, "Heading2CN": 0, "Heading3CN": 1}
        if style_name not in levels:
            return
        level = levels[style_name]
        text = flowable.getPlainText()
        # multiBuild 会重复排版多轮；书签键必须跨轮次保持稳定，
        # 否则目录会被判定为始终未收敛。
        key = getattr(flowable, "_tech_bookmark_key", None)
        if key is None:
            key = f"h_{self._bookmark_id}"
            flowable._tech_bookmark_key = key
        self._bookmark_id += 1
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=(level == 0))
        self.notify("TOCEntry", (level, text, self.page, key))


def on_page(canvas, doc):
    canvas.saveState()
    page = canvas.getPageNumber()
    if page > 1:
        canvas.setStrokeColor(MID_GRAY)
        canvas.setLineWidth(0.45)
        canvas.line(LEFT, PAGE_H - 13 * mm, PAGE_W - RIGHT, PAGE_H - 13 * mm)
        canvas.setFont("SimSun", 8)
        canvas.setFillColor(MUTED)
        canvas.drawString(LEFT, PAGE_H - 10.2 * mm, "技术报告 · 大模型基础设施工程实践")
        canvas.drawRightString(PAGE_W - RIGHT, PAGE_H - 10.2 * mm, "陶壮")
    canvas.setStrokeColor(MID_GRAY)
    canvas.line(LEFT, 12 * mm, PAGE_W - RIGHT, 12 * mm)
    canvas.setFont("SimSun", 8)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(PAGE_W / 2, 7.8 * mm, str(page))
    canvas.restoreState()


def cover_story() -> list:
    note = (
        "本报告用于博士后出站答辩补充、工程技术评审与工作量说明。"
        "内容已做基本脱敏；内部地址、凭据、员工编号与未公开业务规模不写入本文件。"
    )
    note_box = Table([[Paragraph(note, STYLES["cover_note"])]], colWidths=[145 * mm])
    note_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, colors.HexColor("#9EB6CA")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
    ]))
    story = [
        Spacer(1, 38 * mm),
        HRFlowable(width="30%", thickness=3, color=ACCENT, hAlign="CENTER"),
        Spacer(1, 10 * mm),
        Paragraph("技术报告", STYLES["cover_title"]),
        Paragraph(
            "大模型基础设施工程实践<br/>"
            "OmniPlacement / Omni-EPLB、DataInfra / DataHub 与 Omni-ELB / LiteLLM",
            STYLES["cover_subtitle"],
        ),
        Spacer(1, 8 * mm),
        Paragraph("作者：陶壮", STYLES["cover_meta"]),
        Paragraph("版本：2026-09-22（工程技术版）", STYLES["cover_meta"]),
        Paragraph("工程为主 · 理论为辅 · 证据可追溯", STYLES["cover_meta"]),
        Spacer(1, 30 * mm),
        note_box,
        PageBreak(),
    ]
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle("TOC0", fontName="SimHei", fontSize=10.5, leading=17,
                       leftIndent=0, firstLineIndent=0, textColor=NAVY, spaceBefore=2),
        ParagraphStyle("TOC1", fontName="SimSun", fontSize=9.2, leading=15,
                       leftIndent=12, firstLineIndent=0, textColor=TEXT),
        ParagraphStyle("TOC2", fontName="SimSun", fontSize=8.4, leading=13.5,
                       leftIndent=28, firstLineIndent=0, textColor=MUTED),
    ]
    story.extend([
        Paragraph("目录", STYLES["toc_title"]),
        HRFlowable(width="100%", thickness=0.8, color=ACCENT),
        Spacer(1, 5 * mm),
        toc,
        PageBreak(),
    ])
    return story


def parse_markdown(source: str) -> list:
    lines = source.splitlines()
    start = next((i for i, line in enumerate(lines) if line.strip() == "## 摘要"), 0)
    lines = lines[start:]
    story: list = []
    para: list[str] = []

    def flush_paragraph():
        nonlocal para
        if para:
            text = " ".join(x.strip() for x in para).strip()
            if text:
                story.append(Paragraph(inline_markup(text), STYLES["body"]))
            para = []

    def make_figure(image_path: Path, alt_text: str, caption_text: str | None):
        if not image_path.exists():
            raise FileNotFoundError(f"Markdown image not found: {image_path}")
        pixel_w, pixel_h = ImageReader(str(image_path)).getSize()
        max_w = CONTENT_W - 8 * mm
        max_h = 205 * mm
        scale = min(max_w / pixel_w, max_h / pixel_h)
        draw_w = pixel_w * scale
        draw_h = pixel_h * scale
        picture = RLImage(str(image_path), width=draw_w, height=draw_h)
        picture.hAlign = "CENTER"
        frame = Table([[picture]], colWidths=[draw_w + 5 * mm], hAlign="CENTER")
        frame.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.55, MID_GRAY),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ]))
        items = [Spacer(1, 2 * mm), frame]
        caption = caption_text or alt_text
        if caption:
            items.append(Paragraph(inline_markup(caption), STYLES["caption"]))
        items.append(Spacer(1, 2 * mm))
        return KeepTogether(items)

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        image_match = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if image_match:
            flush_paragraph()
            alt_text = image_match.group(1).strip()
            image_ref = image_match.group(2).strip()
            image_path = (ROOT / image_ref).resolve()
            try:
                image_path.relative_to(ROOT.resolve())
            except ValueError as exc:
                raise ValueError(f"Image path escapes docs directory: {image_ref}") from exc

            caption_text = None
            next_i = i + 1
            while next_i < len(lines) and not lines[next_i].strip():
                next_i += 1
            if next_i < len(lines):
                caption_match = re.match(r"^\*(图\s*[^*]+)\*$", lines[next_i].strip())
                if caption_match:
                    caption_text = caption_match.group(1).strip()
                    i = next_i
            story.append(make_figure(image_path, alt_text, caption_text))
            i += 1
            continue

        if stripped.startswith("```"):
            flush_paragraph()
            i += 1
            block: list[str] = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i].rstrip("\n"))
                i += 1
            story.append(code_block("\n".join(block)))
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        if stripped.startswith("|"):
            flush_paragraph()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            story.append(markdown_table(table_lines))
            continue

        heading = re.match(r"^(#{1,4})\s+(.+)$", stripped)
        if heading:
            flush_paragraph()
            level = len(heading.group(1))
            text = strip_md(heading.group(2))
            if level == 1 and story and not isinstance(story[-1], PageBreak):
                story.append(PageBreak())
            style = STYLES[f"h{level}"]
            story.append(Paragraph(html.escape(text), style))
            i += 1
            continue

        if stripped == "---":
            flush_paragraph()
            story.extend([
                Spacer(1, 2 * mm),
                HRFlowable(width="100%", thickness=0.7, color=MID_GRAY),
                Spacer(1, 3 * mm),
            ])
            i += 1
            continue

        if stripped.startswith(">"):
            flush_paragraph()
            quote_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote_lines.append(lines[i].strip()[1:].strip())
                i += 1
            q = Paragraph(inline_markup(" ".join(quote_lines)), STYLES["quote"])
            box = Table([[q]], colWidths=[CONTENT_W - 5 * mm], hAlign="LEFT")
            box.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), LIGHT_BLUE),
                ("LINEBEFORE", (0, 0), (0, -1), 3, BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.extend([box, Spacer(1, 2 * mm)])
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if bullet or numbered:
            flush_paragraph()
            if bullet:
                story.append(Paragraph(inline_markup(bullet.group(1)), STYLES["bullet"], bulletText="•"))
            else:
                story.append(
                    Paragraph(inline_markup(numbered.group(2)), STYLES["bullet"],
                              bulletText=f"{numbered.group(1)}.")
                )
            i += 1
            continue

        if not stripped:
            flush_paragraph()
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_paragraph()
    return story


def build() -> None:
    markdown = SOURCE.read_text(encoding="utf-8")
    story = cover_story() + parse_markdown(markdown)
    doc = TechDocTemplate(
        str(OUTPUT), pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
        topMargin=TOP, bottomMargin=BOTTOM,
        title="技术报告", author="陶壮",
        subject="OmniPlacement、DataInfra 与 Omni-ELB 工程技术报告",
    )
    doc.multiBuild(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"generated: {OUTPUT}")


if __name__ == "__main__":
    build()
