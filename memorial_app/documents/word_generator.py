"""Word document generator for nenki anniversary tables.

Generates .docx files with Japanese formatting using python-docx.
Supports single and dual column layouts with vertical section headers.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn


class WordGenerator:
    """Generate Word documents for nenki anniversary listings."""

    FONT_NAME = "游明朝"
    FALLBACK_FONT = "MS 明朝"

    def create_combined_document(
        self,
        sorted_data: list,
        title: str,
        output_path: Path,
        single_column: bool = True,
    ):
        """Create a combined nenki document.

        Args:
            sorted_data: List of (key, entries) from ResultsPage._get_sorted_data().
                key: "年忌名|years_offset|(死亡日era表記没)"
                entries: list of (name, display_name, date_str)
            title: Document title (e.g. "年忌表 - 令和八年の年忌法要")
            output_path: Path to save the .docx file.
            single_column: True for single column, False for dual column layout.
        """
        doc = Document()

        self._setup_styles(doc)
        self._set_page_margins(doc)

        # Title
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(title)
        run.font.size = Pt(18)
        run.font.bold = True
        self._set_font(run)

        doc.add_paragraph()  # spacer

        if single_column:
            self._build_single_column(doc, sorted_data)
        else:
            self._build_dual_column(doc, sorted_data)

        doc.save(str(output_path))

    def _setup_styles(self, doc: Document):
        """Configure default document styles for Japanese text."""
        style = doc.styles["Normal"]
        font = style.font
        font.size = Pt(10.5)
        font.name = self.FONT_NAME
        # Set East Asian font
        rPr = style.element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = rPr.makeelement(qn("w:rFonts"), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), self.FONT_NAME)

    def _set_page_margins(self, doc: Document):
        """Set A4 page with comfortable margins."""
        section = doc.sections[0]
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    def _set_font(self, run):
        """Apply Japanese font to a run."""
        run.font.name = self.FONT_NAME
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = rPr.makeelement(qn("w:rFonts"), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), self.FONT_NAME)

    def _build_single_column(self, doc: Document, sorted_data: list):
        """Build single-column layout with tables per nenki group."""
        for key, entries in sorted_data:
            nenki_name, _, death_info = key.split("|", 2)

            # Section header
            p = doc.add_paragraph()
            run = p.add_run(f"■ {nenki_name}　{death_info}")
            run.font.size = Pt(12)
            run.font.bold = True
            run.font.color.rgb = RGBColor(0x2C, 0x3E, 0x50)
            self._set_font(run)

            # Table
            table = doc.add_table(rows=1, cols=3)
            table.style = "Table Grid"
            table.alignment = WD_TABLE_ALIGNMENT.CENTER

            # Header row
            hdr = table.rows[0]
            for cell, text in zip(hdr.cells, ["氏名", "法名", "法要日"]):
                cell.text = text
                self._style_header_cell(cell)

            # Data rows
            for name, display_name, date_str in entries:
                row = table.add_row()
                row.cells[0].text = name
                row.cells[1].text = display_name if display_name != name else ""
                row.cells[2].text = date_str
                for cell in row.cells:
                    self._style_data_cell(cell)

            doc.add_paragraph()  # spacer between groups

    def _build_dual_column(self, doc: Document, sorted_data: list):
        """Build dual-column layout: two nenki groups side by side."""
        # Process in pairs
        for i in range(0, len(sorted_data), 2):
            left = sorted_data[i]
            right = sorted_data[i + 1] if i + 1 < len(sorted_data) else None

            # Create a 2-column table as layout container
            cols = 2 if right else 1
            outer = doc.add_table(rows=1, cols=cols)
            outer.alignment = WD_TABLE_ALIGNMENT.CENTER

            # Remove borders from outer layout table
            for row in outer.rows:
                for cell in row.cells:
                    self._remove_borders(cell)

            # Left group
            self._fill_group_cell(outer.rows[0].cells[0], left)

            # Right group
            if right:
                self._fill_group_cell(outer.rows[0].cells[1], right)

            doc.add_paragraph()

    def _fill_group_cell(self, cell, group_data):
        """Fill a layout cell with one nenki group's data."""
        key, entries = group_data
        nenki_name, _, death_info = key.split("|", 2)

        # Header
        p = cell.paragraphs[0]
        p.clear()
        run = p.add_run(f"■ {nenki_name}　{death_info}")
        run.font.size = Pt(11)
        run.font.bold = True
        self._set_font(run)

        # Entries as simple text lines
        for name, display_name, date_str in entries:
            p = cell.add_paragraph()
            bname = display_name if display_name != name else ""
            text = f"  {name}"
            if bname:
                text += f"（{bname}）"
            text += f"　{date_str}"
            run = p.add_run(text)
            run.font.size = Pt(9.5)
            self._set_font(run)

    def _style_header_cell(self, cell):
        """Style a table header cell."""
        for paragraph in cell.paragraphs:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in paragraph.runs:
                run.font.bold = True
                run.font.size = Pt(10)
                self._set_font(run)
        # Light gray background
        shading = cell._element.get_or_add_tcPr()
        shd = shading.makeelement(qn("w:shd"), {
            qn("w:val"): "clear",
            qn("w:color"): "auto",
            qn("w:fill"): "D5D8DC",
        })
        shading.append(shd)

    def _style_data_cell(self, cell):
        """Style a table data cell."""
        for paragraph in cell.paragraphs:
            for run in paragraph.runs:
                run.font.size = Pt(10)
                self._set_font(run)

    def _remove_borders(self, cell):
        """Remove all borders from a table cell."""
        tcPr = cell._element.get_or_add_tcPr()
        borders = tcPr.makeelement(qn("w:tcBorders"), {})
        for edge in ("top", "left", "bottom", "right"):
            el = borders.makeelement(qn(f"w:{edge}"), {
                qn("w:val"): "none",
                qn("w:sz"): "0",
                qn("w:space"): "0",
                qn("w:color"): "auto",
            })
            borders.append(el)
        tcPr.append(borders)
