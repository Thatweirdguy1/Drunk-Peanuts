"""Fountain screenplay parsing and local exports."""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph


SCENE = re.compile(r"^(?:INT|EXT|EST|INT\.?/EXT|I/E)(?:\.|\s)", re.I)
TITLE_KEYS = {"title", "credit", "author", "authors", "source", "draft date", "contact"}
TYPES = {"scene": "Scene Heading", "action": "Action", "character": "Character",
         "dialogue": "Dialogue", "parenthetical": "Parenthetical", "transition": "Transition",
         "shot": "Shot", "general": "General"}


@dataclass
class Element:
    kind: str
    text: str
    line: int
    dual: bool = False


def parse_fountain(source: str) -> tuple[dict[str, str], list[Element]]:
    lines = source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    title: dict[str, str] = {}
    start = 0
    while start < len(lines):
        match = re.match(r"^([A-Za-z ]+):\s*(.*)$", lines[start])
        if not match or match.group(1).lower() not in TITLE_KEYS:
            break
        key = match.group(1).lower()
        value = match.group(2)
        start += 1
        while start < len(lines) and (lines[start].startswith("   ") or lines[start].startswith("\t")):
            value += "\n" + lines[start].strip()
            start += 1
        title[key] = value
    if title and start < len(lines) and not lines[start].strip():
        start += 1

    elements: list[Element] = []
    previous = ""
    boneyard = False
    for index in range(start, len(lines)):
        raw = lines[index]
        stripped = raw.strip()
        if "/*" in stripped:
            boneyard = True
        if boneyard:
            if "*/" in stripped:
                boneyard = False
            continue
        if not stripped:
            previous = ""
            continue
        if stripped.startswith("#"):
            elements.append(Element("section", stripped.lstrip("# "), index))
            previous = ""
            continue
        if stripped.startswith("="):
            elements.append(Element("synopsis", stripped.lstrip("= "), index))
            previous = ""
            continue
        if stripped.startswith("[[") and stripped.endswith("]]"):
            elements.append(Element("note", stripped[2:-2], index))
            previous = ""
            continue
        text = re.sub(r"\[\[.*?\]\]", "", stripped).strip()
        if not text:
            continue
        dual = text.endswith("^")
        if dual:
            text = text[:-1].rstrip()
        if text.startswith(".") and not text.startswith(".."):
            kind, text = "scene", text[1:]
        elif SCENE.match(text):
            kind = "scene"
        elif text.startswith(">") and text.endswith("<"):
            kind, text = "centered", text[1:-1].strip()
        elif text.startswith(">") or text.upper().endswith("TO:"):
            kind, text = "transition", text.lstrip("> ")
        elif text.startswith("!"):
            kind, text = "action", text[1:]
        elif text.startswith("~"):
            kind, text = "lyric", text[1:]
        elif text.startswith("@"):
            kind, text = "character", text[1:]
        elif (previous in {"character", "dialogue", "parenthetical"} and
              text.startswith("(") and text.endswith(")")):
            kind = "parenthetical"
        elif previous in {"character", "dialogue", "parenthetical"}:
            kind = "dialogue"
        elif (text == text.upper() and any(char.isalpha() for char in text) and
              len(text) <= 40 and index + 1 < len(lines) and lines[index + 1].strip()):
            kind = "character"
        else:
            kind = "action"
        elements.append(Element(kind, text, index, dual))
        previous = kind
    return title, elements


def plain_text(source: str) -> str:
    title, elements = parse_fountain(source)
    lines = [title.get("title", ""), title.get("credit", ""), title.get("author", "")]
    lines.extend(_strip_markup(element.text) for element in elements if element.kind not in {"section", "synopsis", "note"})
    return "\n\n".join(line for line in lines if line) + "\n"


def _runs(text: str):
    for part in re.split(r"(\*\*[^*]+\*\*|\*[^*]+\*|_[^_]+_)", text):
        if part.startswith("**") and part.endswith("**"):
            yield "Bold", part[2:-2]
        elif part.startswith("*") and part.endswith("*"):
            yield "Italic", part[1:-1]
        elif part.startswith("_") and part.endswith("_"):
            yield "Underline", part[1:-1]
        elif part:
            yield "", part


def _strip_markup(text: str) -> str:
    return "".join(value for _, value in _runs(text))


def _inline_html(text: str) -> str:
    tags = {"Bold": "b", "Italic": "i", "Underline": "u"}
    return "".join(f"<{tags[style]}>{html.escape(value)}</{tags[style]}>" if style else html.escape(value)
                   for style, value in _runs(text))


def _layout(elements: list[Element]):
    """Pair a second caret-marked speech with the preceding speech."""
    index = 0
    while index < len(elements):
        current = elements[index]
        if current.kind != "character":
            yield current
            index += 1
            continue
        end = index + 1
        while end < len(elements) and elements[end].kind in {"dialogue", "parenthetical"}:
            end += 1
        if end < len(elements) and elements[end].kind == "character" and elements[end].dual:
            other_end = end + 1
            while other_end < len(elements) and elements[other_end].kind in {"dialogue", "parenthetical"}:
                other_end += 1
            yield (elements[index:end], elements[end:other_end])
            index = other_end
        else:
            for element in elements[index:end]:
                yield element
            index = end


def to_fdx(source: str) -> str:
    title, elements = parse_fountain(source)
    root = ET.Element("FinalDraft", DocumentType="Script", Template="No", Version="5")
    if title:
        page = ET.SubElement(root, "TitlePage")
        content = ET.SubElement(page, "Content")
        for key, value in title.items():
            paragraph = ET.SubElement(content, "Paragraph", Type="General")
            ET.SubElement(paragraph, "Text").text = f"{key.title()}: {value}"
    content = ET.SubElement(root, "Content")
    def add(parent, element):
        if element.kind in {"section", "synopsis", "note"}:
            return
        text = element.text
        attrs = {"Type": TYPES.get(element.kind, "Action")}
        if element.kind == "scene" and (match := re.search(r"\s+#([\w.-]+)#$", text)):
            attrs["Number"] = match.group(1)
            text = text[:match.start()]
        paragraph = ET.SubElement(parent, "Paragraph", attrs)
        for style, value in _runs(text):
            attrs = {"Style": style} if style else {}
            ET.SubElement(paragraph, "Text", attrs).text = value

    for item in _layout(elements):
        if isinstance(item, tuple):
            dual = ET.SubElement(ET.SubElement(content, "Paragraph"), "DualDialogue")
            for speech in item:
                for element in speech:
                    add(dual, element)
        else:
            add(content, item)
    ET.indent(root)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode") + "\n"


def from_fdx(source: str) -> str:
    root = ET.fromstring(source)
    if root.tag != "FinalDraft":
        raise ValueError("This is not a Final Draft document.")
    lines = []
    for paragraph in root.findall("./TitlePage/Content/Paragraph"):
        value = "".join(paragraph.itertext()).strip()
        if (match := re.match(r"^([A-Za-z ]+):\s*(.*)$", value)) and match.group(1).lower() in TITLE_KEYS:
            lines.append(value)
    if lines:
        lines.append("")

    def append(paragraph, dual=False):
        kind = paragraph.get("Type", "Action")
        text = "".join(part for node in paragraph.findall("Text") for part in node.itertext()).strip()
        if not text:
            return
        if kind == "Scene Heading" and not SCENE.match(text):
            text = "." + text
        elif kind == "Character":
            text = "@" + text + (" ^" if dual else "")
        elif kind == "Transition" and not text.endswith("TO:"):
            text = ">" + text
        elif kind == "Action" and text == text.upper() and len(text) <= 40:
            text = "!" + text
        if kind == "Scene Heading" and paragraph.get("Number"):
            text += f" #{paragraph.get('Number')}#"
        if kind not in {"Dialogue", "Parenthetical"} and lines and lines[-1]:
            lines.append("")
        lines.append(text)

    for paragraph in root.findall("./Content/Paragraph"):
        dual = paragraph.find("DualDialogue")
        if dual is not None:
            characters = 0
            for child in dual.findall("Paragraph"):
                if child.get("Type") == "Character":
                    characters += 1
                append(child, dual=characters == 2 and child.get("Type") == "Character")
        else:
            append(paragraph)
    return "\n".join(lines).rstrip() + "\n"


def merge_fdx(original: bytes, before: str, after: str) -> bytes:
    """Change supported paragraph text while retaining unrelated FDX XML nodes."""
    if b"<!DOCTYPE" in original.upper():
        raise ValueError("FDX with a document type declaration cannot be merged safely.")
    old_title, old_elements = parse_fountain(before)
    new_title, new_elements = parse_fountain(after)
    old_elements = [item for item in old_elements if item.kind not in {"section", "synopsis", "note"}]
    new_elements = [item for item in new_elements if item.kind not in {"section", "synopsis", "note"}]
    if (len(old_elements) != len(new_elements) or
            any((a.kind, a.dual) != (b.kind, b.dual) for a, b in zip(old_elements, new_elements)) or
            old_title.keys() != new_title.keys()):
        raise ValueError("Added, removed, or retyped elements cannot be merged without risking FDX metadata.")
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    root = ET.fromstring(original, parser=parser)
    if root.tag != "FinalDraft":
        raise ValueError("This is not a Final Draft document.")
    content = root.find("Content")
    if content is None:
        raise ValueError("FDX has no screenplay content.")
    paragraphs = []
    for paragraph in content.findall("Paragraph"):
        dual = paragraph.find("DualDialogue")
        paragraphs.extend(dual.findall("Paragraph") if dual is not None else [paragraph])
    paragraphs = [p for p in paragraphs if any((t.text or "").strip() for t in p.findall("Text"))]
    if len(paragraphs) != len(old_elements):
        raise ValueError("FDX paragraph structure cannot be mapped safely to this draft.")

    def replace_text(paragraph: ET.Element, value: str) -> None:
        nodes = paragraph.findall("Text")
        if len(nodes) != 1:
            raise ValueError("A changed paragraph has multiple styled text runs; its formatting cannot be preserved safely.")
        nodes[0].text = value

    for paragraph, old, new in zip(paragraphs, old_elements, new_elements):
        if old.text == new.text:
            continue
        value = _strip_markup(new.text)
        if new.kind == "scene" and (match := re.search(r"\s+#([\w.-]+)#$", value)):
            paragraph.set("Number", match.group(1))
            value = value[:match.start()]
        elif new.kind == "scene":
            paragraph.attrib.pop("Number", None)
        replace_text(paragraph, value)

    title_content = root.find("./TitlePage/Content")
    for key, old_value in old_title.items():
        if old_value == new_title[key]:
            continue
        if title_content is None:
            raise ValueError("FDX title page cannot be mapped safely to this draft.")
        matches = [p for p in title_content.findall("Paragraph")
                   if "".join(p.itertext()).strip().lower().startswith(key + ":")]
        if len(matches) != 1:
            raise ValueError(f"FDX title field {key} cannot be mapped safely.")
        replace_text(matches[0], f"{key.title()}: {new_title[key]}")
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8") + b"\n"


def to_html(source: str) -> str:
    title, elements = parse_fountain(source)
    body = []
    if title:
        body.append('<section class="title-page">')
        for key in ("title", "credit", "author", "source", "contact", "draft date"):
            if title.get(key):
                body.append(f'<p class="title-{key.replace(" ", "-")}">{html.escape(title[key])}</p>')
        body.append("</section>")
    def paragraph(element):
        return f'<p class="{element.kind}">{_inline_html(element.text)}</p>'

    for item in _layout(elements):
        if isinstance(item, tuple):
            body.append('<div class="dual"><div>' + "".join(map(paragraph, item[0])) +
                        '</div><div>' + "".join(map(paragraph, item[1])) + '</div></div>')
        elif item.kind not in {"section", "synopsis", "note"}:
            body.append(paragraph(item))
    return ("<!doctype html><html><head><meta charset=\"utf-8\"><title>Screenplay</title>"
            "<style>@page{size:letter;margin:1in 1in 1in 1.5in}body{font:12pt Courier New,Courier,monospace;max-width:6in;margin:1in auto}"
            "p{margin:0 0 1em;white-space:pre-wrap}.scene,.shot{text-transform:uppercase}.character{margin-left:2.2in;margin-bottom:0}"
            ".dialogue{margin-left:1in;margin-right:1in}.parenthetical{margin-left:1.6in;margin-bottom:0}"
            ".transition{text-align:right;text-transform:uppercase}.centered{text-align:center}.dual{display:flex;gap:.25in}"
            ".dual>div{width:50%}.dual .character,.dual .dialogue,.dual .parenthetical{margin-left:0;margin-right:0}"
            ".title-page{text-align:center;break-after:page;min-height:8in}"
            ".title-title{padding-top:2.7in;text-transform:uppercase}.title-contact{text-align:left;padding-top:2in}"
            "</style></head><body>" + "\n".join(body) + "</body></html>")


def to_markdown(source: str) -> str:
    title, elements = parse_fountain(source)
    lines = [f"# {title['title']}", ""] if title.get("title") else []
    for element in elements:
        text = element.text
        if element.kind == "section":
            lines.append(f"## {text}")
        elif element.kind == "synopsis":
            lines.append(f"> {text}")
        elif element.kind == "scene":
            lines.append(f"### {text}")
        elif element.kind == "character":
            lines.append(f"**{text}**" + (" ↔" if element.dual else ""))
        elif element.kind == "parenthetical":
            lines.append(f"*{text}*")
        elif element.kind != "note":
            lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def to_pdf(source: str, target: Path, layout_fdx: bytes | None = None) -> None:
    title, elements = parse_fountain(source)
    width, height = letter
    layout = None
    styles = {}
    if layout_fdx:
        root = ET.fromstring(layout_fdx)
        layout = root.find("PageLayout")
        styles = {node.get("Type"): node for node in root.findall("ElementSettings")}

    def number(value, default, minimum, maximum):
        try:
            result = float(value)
            return result if minimum <= result <= maximum else default
        except (ValueError, TypeError):
            return default

    if layout is not None:
        size = layout.find("PageSize")
        if size is not None:
            width = 72 * number(size.get("Width"), width / 72, 5, 20)
            height = 72 * number(size.get("Height"), height / 72, 5, 20)
    top_margin = number(layout.get("TopMargin") if layout is not None else None, 72, 18, 216)
    bottom_margin = number(layout.get("BottomMargin") if layout is not None else None, 72, 18, 216)
    document = canvas.Canvas(str(target), pagesize=(width, height), pageCompression=1)
    document.setTitle(title.get("title", "Screenplay"))
    if title:
        document.setFont("Courier-Bold", 12)
        document.drawCentredString(width / 2, height * 0.65, title.get("title", "").upper())
        document.setFont("Courier", 12)
        for offset, key in enumerate(("credit", "author", "source")):
            if title.get(key):
                document.drawCentredString(width / 2, height * 0.59 - offset * 18, title[key])
        if title.get("contact"):
            document.drawString(108, 100, title["contact"].splitlines()[0])
        if title.get("draft date"):
            document.drawRightString(width - 72, 100, title["draft date"])
        document.showPage()
    page = 1
    y = height - top_margin
    locations = {"scene": (108, 432), "shot": (108, 432), "action": (108, 432),
                 "character": (252, 280), "dialogue": (180, 252), "parenthetical": (216, 216),
                 "transition": (108, 432), "centered": (108, 432), "lyric": (180, 252),
                 "general": (108, 432)}

    def new_page():
        nonlocal page, y
        document.showPage()
        page += 1
        y = height - top_margin
        document.setFont("Courier", 12)
        document.drawRightString(width - 72, height - 45, f"{page}.")

    def block(element: Element, column_width: float | None = None):
        x, available = locations.get(element.kind, (108, 432))
        spec = styles.get(TYPES.get(element.kind))
        paragraph_spec = spec.find("ParagraphSpec") if spec is not None else None
        font_spec = spec.find("FontSpec") if spec is not None else None
        behavior = spec.find("Behavior") if spec is not None else None
        if paragraph_spec is not None:
            left = number(paragraph_spec.get("LeftIndent"), x / 72, 0.25, width / 72 - 1)
            right = number(paragraph_spec.get("RightIndent"), (x + available) / 72, left + .5, width / 72 - .25)
            x, available = left * 72, (right - left) * 72
        if column_width is not None:
            available = column_width
        size = number(font_spec.get("Size") if font_spec is not None else None, 12, 8, 18)
        spacing = number(paragraph_spec.get("Spacing") if paragraph_spec is not None else None, 1, .8, 3)
        alignment = paragraph_spec.get("Alignment") if paragraph_spec is not None else ""
        align = {"Left": 0, "Center": 1, "Centered": 1, "Right": 2, "Justified": 4}.get(
            alignment, 2 if element.kind == "transition" else 1 if element.kind == "centered" else 0)
        style = ParagraphStyle("script", fontName="Courier-Bold" if element.kind in {"scene", "character", "transition"} else "Courier",
                               fontSize=size, leading=size * spacing, alignment=align)
        paragraph = Paragraph(_inline_html(element.text) or "&nbsp;", style)
        _, block_height = paragraph.wrap(available, height)
        before = number(paragraph_spec.get("SpaceBefore") if paragraph_spec is not None else None,
                        0 if element.kind in {"dialogue", "parenthetical"} else 12, 0, 72)
        starts_page = behavior is not None and paragraph_spec is not None and paragraph_spec.get("StartsNewPage") == "Yes"
        return paragraph, block_height, before, x, available, starts_page

    def draw_block(element: Element):
        nonlocal y
        paragraph, block_height, before, x, available, starts_page = block(element)
        if starts_page and y < height - top_margin:
            new_page()
        if y - before - min(block_height, 24) < bottom_margin:
            new_page()
        y -= before
        pending = [paragraph]
        while pending:
            current = pending.pop(0)
            _, current_height = current.wrap(available, height)
            if current_height > y - bottom_margin:
                parts = current.split(available, y - bottom_margin)
                if len(parts) < 2:
                    if y == height - top_margin:
                        raise ValueError("A screenplay paragraph cannot fit on the selected page size.")
                    new_page()
                    pending.insert(0, current)
                    continue
                pending = parts + pending
                continue
            current.drawOn(document, x, y - current_height)
            y -= current_height
            if pending:
                new_page()

    items = [item for item in _layout(elements) if isinstance(item, tuple) or item.kind not in {"section", "synopsis", "note"}]
    for index, item in enumerate(items):
        if isinstance(item, tuple):
            columns = [[block(element, 205) for element in speech] for speech in item]
            needed = max(sum(block_height + before for _, block_height, before, *_ in column) for column in columns)
            if needed > height - top_margin - bottom_margin:
                # ponytail: overlong dual speeches become sequential so no text is clipped.
                for speech in item:
                    for element in speech:
                        draw_block(element)
                continue
            if y - needed < bottom_margin:
                new_page()
            for x, column in zip((108, 333), columns):
                top = y
                for paragraph, block_height, before, *_ in column:
                    top -= before
                    paragraph.drawOn(document, x, top - block_height)
                    top -= block_height
            y -= needed
            continue
        if item.kind in {"scene", "character"} and index + 1 < len(items) and not isinstance(items[index + 1], tuple):
            following = items[index + 1]
            if (item.kind == "scene" and following.kind == "action" or
                    item.kind == "character" and following.kind in {"dialogue", "parenthetical"}):
                needed = sum(block(piece)[1] + block(piece)[2] for piece in (item, following))
                if needed <= height - top_margin - bottom_margin and y - needed < bottom_margin:
                    new_page()
        draw_block(item)
    document.save()


EXPORTS = {".fountain": lambda text: text, ".fdx": to_fdx, ".txt": plain_text,
           ".html": to_html, ".md": to_markdown}


def export_script(source: str, target: Path, layout_fdx: bytes | None = None) -> None:
    if target.exists():
        raise FileExistsError(f"Output already exists: {target.name}")
    if target.suffix.lower() == ".pdf":
        to_pdf(source, target, layout_fdx)
    elif target.suffix.lower() in EXPORTS:
        target.write_text(EXPORTS[target.suffix.lower()](source), encoding="utf-8")
    else:
        raise ValueError("Choose PDF, Fountain, FDX, TXT, HTML, or Markdown.")
