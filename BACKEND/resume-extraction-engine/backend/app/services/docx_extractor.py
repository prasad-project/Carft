"""DOCX extraction with python-docx: header/footer, paragraphs, headings, tables, bullets, hyperlinks,
text boxes (appended at the end because their position cannot be recovered)."""
from __future__ import annotations

import re

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..utils.text_utils import is_bullet, normalize_line
from .models import Line, PageContent

_NS_R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _para_text(p: Paragraph) -> str:
    text = p.text
    el = p._p
    is_list = el.find(qn("w:pPr") + "/" + qn("w:numPr")) is not None or (
        p.style is not None and p.style.name and p.style.name.lower().startswith("list")
    )
    if is_list and text.strip() and not is_bullet(text):
        text = "• " + text
    return text


def _para_links(p: Paragraph, part) -> list:
    out = []
    for h in p._p.iter(qn("w:hyperlink")):
        rid = h.get(_NS_R)
        if rid and rid in part.rels and part.rels[rid].is_external:
            out.append(part.rels[rid].target_ref)
    return out


def _iter_block(doc, parent_el, part, links: list):
    for child in parent_el.iterchildren():
        if child.tag == qn("w:p"):
            p = Paragraph(child, doc)
            links.extend(_para_links(p, part))
            yield _para_text(p)
        elif child.tag == qn("w:tbl"):
            t = Table(child, doc)
            seen = set()
            for row in t.rows:
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    for cp in cell.paragraphs:
                        links.extend(_para_links(cp, part))
                        yield _para_text(cp)
                    for nt in cell.tables:  # one level of nesting
                        for nrow in nt.rows:
                            for ncell in nrow.cells:
                                for np_ in ncell.paragraphs:
                                    yield _para_text(np_)


def extract_docx(path):
    """Returns (pages, links, metadata, image_blobs). DOCX has no fixed pages -> one logical page."""
    d = docx.Document(str(path))
    links: list = []
    texts: list = []
    for sec in d.sections:
        for p in list(sec.header.paragraphs) + list(sec.first_page_header.paragraphs):
            if p.text.strip() and p.text.strip() not in texts:
                texts.append(p.text)
    body_texts = list(_iter_block(d, d.element.body, d.part, links))
    texts.extend(body_texts)

    seen_tb = set()
    for tb in d.element.body.iter(qn("w:txbxContent")):
        for p in tb.iter(qn("w:p")):
            t = "".join(x.text or "" for x in p.iter(qn("w:t")))
            if t.strip() and t not in seen_tb and t not in texts:
                seen_tb.add(t)
                texts.append(t)

    lines = []
    for t in texts:
        for piece in t.splitlines():
            n = normalize_line(piece)
            if n:
                lines.append(Line(n, 1, "docx"))
    page = PageContent(page=1, lines=lines, method="embedded")
    page.char_count = len(re.sub(r"\s", "", page.text))
    cp = d.core_properties
    meta = {k: str(v) for k, v in {"author": cp.author, "title": cp.title}.items() if v}
    blobs = [
        rel.target_part.blob
        for rel in d.part.rels.values()
        if "image" in rel.reltype and not rel.is_external
    ]
    return [page], links, meta, blobs
