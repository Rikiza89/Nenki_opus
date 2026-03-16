"""Word document generator for nenki anniversary tables.

Generates .docx files with vertical Japanese text (縦書き / tategaki),
landscape A4 orientation, and proper Japanese formatting.
Optionally converts to PDF via docx2pdf.
"""

from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


class WordGenerator:
    """Generate Word documents for nenki anniversary listings with vertical text."""

    FONT_NAME = "MS Mincho"

    def create_combined_document(
        self,
        sorted_data: list,
        title: str,
        output_path: Path,
        single_column: bool = True,
    ):
        """Create a combined nenki document with vertical Japanese text.

        Args:
            sorted_data: List of (key, entries) from ResultsPage._get_sorted_data().
                key: "年忌名|years_offset|(死亡日era表記没)"
                entries: list of (name, display_name, date_str)
            title: Document title (e.g. "年忌表 - 令和八年の年忌法要")
            output_path: Path to save the .docx file.
            single_column: True for single column, False for dual column layout.
        """
        doc = Document()

        # Landscape A4
        section = doc.sections[0]
        section.page_width = Inches(11.69)
        section.page_height = Inches(8.27)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(0.5)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

        # Set vertical text direction (tategaki)
        sectPr = section._sectPr
        textDirection = OxmlElement("w:textDirection")
        textDirection.set(qn("w:val"), "tbRl")
        sectPr.append(textDirection)

        # Set default font
        style = doc.styles["Normal"]
        style.font.name = self.FONT_NAME
        rPr = style.element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = rPr.makeelement(qn("w:rFonts"), {})
            rPr.insert(0, rFonts)
        rFonts.set(qn("w:eastAsia"), self.FONT_NAME)

        # Main title
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(title)
        title_run.font.size = Pt(36)
        title_run.font.bold = True
        title_run.font.name = self.FONT_NAME
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        doc.add_paragraph()

        # Each nenki group
        for key, people_data in sorted_data:
            parts = key.split("|")
            nenki_name = parts[0]
            death_year = parts[2]

            # Nenki subtitle
            subtitle = doc.add_paragraph()
            subtitle_run = subtitle.add_run(f"{nenki_name}{death_year}")
            subtitle_run.font.size = Pt(20) if single_column else Pt(16)
            subtitle_run.font.bold = True
            subtitle_run.font.name = self.FONT_NAME

            if not single_column:
                subtitle.paragraph_format.left_indent = Inches(0.5)
            else:
                subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

            subtitle.paragraph_format.space_after = Pt(12)

            if single_column:
                self._build_single_column_group(doc, people_data)
            else:
                self._build_dual_column_group(doc, people_data)

            # Space between groups
            doc.add_paragraph()

        doc.save(str(output_path))

        # Auto-convert to PDF
        self._convert_to_pdf(output_path)

    def _build_single_column_group(self, doc: Document, people_data: list):
        """Single column layout: each person on one line."""
        for person in people_data:
            name = person[1] if person[1] else person[0]
            date = person[2]
            text = f"\u3000\u3000{date}\u3000{name}" if date else f"\u3000\u3000{name}"

            para = doc.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(14)
            run.font.name = self.FONT_NAME
            para.paragraph_format.left_indent = Inches(1.5)
            para.paragraph_format.space_after = Pt(6)

    def _build_dual_column_group(self, doc: Document, people_data: list):
        """Dual column layout: split people into two halves with date padding."""
        # Calculate max date length for alignment
        max_date_length = 0
        for person in people_data:
            date = person[2]
            if date:
                max_date_length = max(max_date_length, len(date))

        # Minimum 6 chars width (e.g. 十二月三十日)
        if max_date_length < 6:
            max_date_length = 6

        half = (len(people_data) + 1) // 2
        base_indent = Inches(0.5)

        # Column 1
        for idx in range(half):
            if idx < len(people_data):
                self._add_dual_column_person(
                    doc, people_data[idx], max_date_length, base_indent
                )

        # Spacer between columns
        spacer = doc.add_paragraph()
        spacer_run = spacer.add_run("\u3000\u3000\u3000")
        spacer_run.font.size = Pt(11)
        spacer_run.font.name = self.FONT_NAME

        # Column 2
        for idx in range(half, len(people_data)):
            self._add_dual_column_person(
                doc, people_data[idx], max_date_length, base_indent
            )

    def _add_dual_column_person(self, doc, person, max_date_length, base_indent):
        """Add a single person entry in dual column format."""
        name = person[1] if person[1] else person[0]
        date = person[2] if person[2] else ""

        date_length = len(date) if date else 0
        padding_needed = max_date_length - date_length
        padding = "\u3000" * padding_needed
        text = f"\u3000\u3000{date}{padding}\u3000{name}"

        para = doc.add_paragraph()
        run = para.add_run(text)
        run.font.size = Pt(11)
        run.font.name = self.FONT_NAME
        para.paragraph_format.left_indent = base_indent
        para.paragraph_format.space_after = Pt(4)

    def _convert_to_pdf(self, docx_path: Path):
        """Try to convert .docx to .pdf using docx2pdf."""
        try:
            from docx2pdf import convert
            pdf_path = docx_path.with_suffix(".pdf")
            convert(str(docx_path), str(pdf_path))
        except Exception:
            pass
