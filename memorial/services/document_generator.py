"""
Document generator: produces Word (.docx) and PDF from a layout config + data.

Layout config schema:
{
  "title": "令和七年 年忌法要 名簿",
  "columns": 1,           // 1 or 2
  "text_direction": "tategaki",  // "tategaki" | "yokogumi"
  "font_family": "MS Mincho",
  "page_orientation": "landscape",  // "landscape" | "portrait"
  "field_separator": "\u3000",
  "widgets": [
    {"type": "title",        "font_size": 36, "bold": true, "align": "center"},
    {"type": "group_header", "font_size": 28, "bold": true, "align": "center",
     "template": "{nenki_name}　{anniversary_date}"},
    {"type": "entry",        "font_size": 18, "align": "left",
     "fields": ["name", "death_date_kanji", ...], "padding": true},
    {"type": "spacer",       "lines": 1}
  ]
}
"""

import io
import unicodedata
from docx import Document
from docx.shared import Pt, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _display_width(text: str) -> int:
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ('F', 'W', 'A') else 1
    return w


def _pad_to_width(text: str, target: int) -> str:
    current = _display_width(text)
    needed = (target - current) // 2
    return text + '\u3000' * needed if needed > 0 else text


def _compute_field_widths(entries: list) -> list:
    if not entries:
        return []
    num = max(len(e) for e in entries)
    widths = [0] * num
    for entry in entries:
        for i, val in enumerate(entry):
            if i < num:
                w = _display_width(str(val) if val else '')
                if w > widths[i]:
                    widths[i] = w
    return [w + (w % 2) for w in widths]


def _set_tategaki(paragraph):
    """Set text direction to tategaki (top-to-bottom)."""
    pPr = paragraph._p.get_or_add_pPr()
    textDir = OxmlElement('w:textDirection')
    textDir.set(qn('w:val'), 'tbRl')
    pPr.append(textDir)


def _set_font(run, font_family: str, size_pt: float, bold: bool = False):
    run.font.name = font_family
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    r = run._r
    rPr = r.get_or_add_rPr()
    rFonts = OxmlElement('w:rFonts')
    rFonts.set(qn('w:eastAsia'), font_family)
    rPr.insert(0, rFonts)


def _set_col_layout(section, num_cols: int):
    sectPr = section._sectPr
    cols = OxmlElement('w:cols')
    cols.set(qn('w:num'), str(num_cols))
    cols.set(qn('w:space'), '720')
    sectPr.append(cols)


DEFAULT_LAYOUT = {
    "title": "年忌法要 名簿",
    "columns": 1,
    "text_direction": "tategaki",
    "font_family": "MS Mincho",
    "page_orientation": "landscape",
    "field_separator": "\u3000",
    "widgets": [
        {"type": "title", "font_size": 36, "bold": True, "align": "center"},
        {"type": "group_header", "font_size": 28, "bold": True, "align": "center",
         "template": "{nenki_name}　{anniversary_date}"},
        {"type": "entry", "font_size": 18, "align": "left", "padding": True},
        {"type": "spacer", "lines": 1},
    ]
}


class DocumentGenerator:
    def __init__(self, layout: dict = None):
        self.layout = {**DEFAULT_LAYOUT, **(layout or {})}
        # Merge widgets if explicitly provided
        if layout and 'widgets' in layout:
            self.layout['widgets'] = layout['widgets']

    def generate_word(self, sorted_data: list, available_fields: list) -> bytes:
        """
        sorted_data: list of (nenki_key, [entry_dict, ...])
          where nenki_key = "年忌名|years_offset"
          entry_dict = {'name': ..., 'death_date_kanji': ..., 'anniversary_date_kanji': ...,
                        'nenki_name': ..., ...attributes...}
        available_fields: list of field names user selected to show
        """
        doc = Document()
        section = doc.sections[0]
        cfg = self.layout

        # Page setup
        if cfg['page_orientation'] == 'landscape':
            section.page_width = Inches(11.69)
            section.page_height = Inches(8.27)
        else:
            section.page_width = Inches(8.27)
            section.page_height = Inches(11.69)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

        is_tategaki = cfg['text_direction'] == 'tategaki'
        num_cols = cfg.get('columns', 1)
        font = cfg.get('font_family', 'MS Mincho')
        sep = cfg.get('field_separator', '\u3000')

        if num_cols > 1:
            _set_col_layout(section, num_cols)

        if is_tategaki:
            sectPr = section._sectPr
            textDir = OxmlElement('w:textDirection')
            textDir.set(qn('w:val'), 'tbRl')
            sectPr.append(textDir)

        # Get widget configs
        title_cfg = next((w for w in cfg['widgets'] if w['type'] == 'title'), {})
        header_cfg = next((w for w in cfg['widgets'] if w['type'] == 'group_header'), {})
        entry_cfg = next((w for w in cfg['widgets'] if w['type'] == 'entry'), {})
        spacer_cfg = next((w for w in cfg['widgets'] if w['type'] == 'spacer'), {})

        # Compute field widths globally across all entries
        all_rows = []
        for nenki_key, entries in sorted_data:
            for e in entries:
                row = [str(e.get(f, '')) for f in available_fields if f != '年忌名']
                all_rows.append(row)
        field_widths = _compute_field_widths(all_rows) if entry_cfg.get('padding', True) else []

        # Title
        if title_cfg:
            p = doc.add_paragraph()
            if is_tategaki:
                _set_tategaki(p)
            align_map = {'center': WD_ALIGN_PARAGRAPH.CENTER,
                         'left': WD_ALIGN_PARAGRAPH.LEFT,
                         'right': WD_ALIGN_PARAGRAPH.RIGHT}
            p.alignment = align_map.get(title_cfg.get('align', 'center'), WD_ALIGN_PARAGRAPH.CENTER)
            run = p.add_run(cfg['title'])
            _set_font(run, font, title_cfg.get('font_size', 36), title_cfg.get('bold', True))

        # Groups
        for nenki_key, entries in sorted_data:
            if not entries:
                continue
            nenki_name = entries[0].get('nenki_name', '')
            ann_date = entries[0].get('anniversary_date_kanji', '')

            # Group header
            if header_cfg:
                tmpl = header_cfg.get('template', '{nenki_name}　{anniversary_date}')
                header_text = tmpl.format(nenki_name=nenki_name, anniversary_date=ann_date)
                p = doc.add_paragraph()
                if is_tategaki:
                    _set_tategaki(p)
                p.alignment = align_map.get(header_cfg.get('align', 'center'), WD_ALIGN_PARAGRAPH.CENTER)
                run = p.add_run(header_text)
                _set_font(run, font, header_cfg.get('font_size', 28), header_cfg.get('bold', True))

            # Entries
            for e in entries:
                row = [str(e.get(f, '')) for f in available_fields if f != '年忌名']
                if field_widths and entry_cfg.get('padding', True):
                    padded = [_pad_to_width(row[i], field_widths[i]) if i < len(field_widths) else row[i]
                              for i in range(len(row))]
                    text = sep.join(padded)
                else:
                    text = sep.join(row)

                p = doc.add_paragraph()
                if is_tategaki:
                    _set_tategaki(p)
                entry_align = entry_cfg.get('align', 'left')
                p.alignment = align_map.get(entry_align, WD_ALIGN_PARAGRAPH.LEFT)
                run = p.add_run(text)
                _set_font(run, font, entry_cfg.get('font_size', 18), entry_cfg.get('bold', False))

            # Spacer
            if spacer_cfg:
                for _ in range(spacer_cfg.get('lines', 1)):
                    sp = doc.add_paragraph()
                    if is_tategaki:
                        _set_tategaki(sp)
                    run = sp.add_run('')
                    _set_font(run, font, entry_cfg.get('font_size', 18))

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return buf.read()

    def generate_pdf(self, sorted_data: list, available_fields: list) -> bytes:
        """Fallback: generate PDF using reportlab."""
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import os

        cfg = self.layout
        if cfg['page_orientation'] == 'landscape':
            pagesize = landscape(A4)
        else:
            pagesize = A4

        buf = io.BytesIO()
        c = rl_canvas.Canvas(buf, pagesize=pagesize)
        w, h = pagesize
        margin = 15 * mm
        x = margin
        y = h - margin
        font_size = 12

        title_cfg = next((wg for wg in cfg['widgets'] if wg['type'] == 'title'), {})
        header_cfg = next((wg for wg in cfg['widgets'] if wg['type'] == 'group_header'), {})
        entry_cfg = next((wg for wg in cfg['widgets'] if wg['type'] == 'entry'), {})
        sep = cfg.get('field_separator', '　')

        def write_line(text, size=12, bold=False):
            nonlocal y
            c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
            c.drawString(x, y, text)
            y -= size * 1.5
            if y < margin:
                c.showPage()
                nonlocal_y_reset()

        def nonlocal_y_reset():
            nonlocal y
            y = h - margin

        # Title
        write_line(cfg['title'], title_cfg.get('font_size', 24), title_cfg.get('bold', True))

        for nenki_key, entries in sorted_data:
            if not entries:
                continue
            nenki_name = entries[0].get('nenki_name', '')
            ann_date = entries[0].get('anniversary_date_kanji', '')
            tmpl = header_cfg.get('template', '{nenki_name}　{anniversary_date}')
            header_text = tmpl.format(nenki_name=nenki_name, anniversary_date=ann_date)
            write_line(header_text, header_cfg.get('font_size', 16), header_cfg.get('bold', True))

            for e in entries:
                row = [str(e.get(f, '')) for f in available_fields if f != '年忌名']
                write_line(sep.join(row), entry_cfg.get('font_size', 12))

        c.save()
        buf.seek(0)
        return buf.read()
