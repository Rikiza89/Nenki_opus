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
        field_names: list[str] | None = None,
        single_column: bool = True,
    ):
        """Create a combined nenki document with vertical Japanese text.

        Args:
            sorted_data: List of (key, entries).
                key: "年忌名|years_offset|(死亡日era表記没)"
                entries: list of field-value lists (ordered by field_names)
            title: Document title (e.g. "年忌表 - 令和八年の年忌法要")
            output_path: Path to save the .docx file.
            field_names: List of field names corresponding to each entry's values.
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
            nenki_name = key.split("|")[0]

            # Nenki subtitle
            subtitle = doc.add_paragraph()
            subtitle_run = subtitle.add_run(nenki_name)
            subtitle_run.font.size = Pt(20) if single_column else Pt(16)
            subtitle_run.font.bold = True
            subtitle_run.font.name = self.FONT_NAME

            if not single_column:
                subtitle.paragraph_format.left_indent = Inches(0.5)
            else:
                subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

            subtitle.paragraph_format.space_after = Pt(12)

            if single_column:
                self._build_single_column_group(doc, people_data, field_names)
            else:
                self._build_dual_column_group(doc, people_data, field_names)

            # Space between groups
            doc.add_paragraph()

        doc.save(str(output_path))

        # Auto-convert to PDF
        self._convert_to_pdf(output_path)

    def _format_entry_text(self, entry: list, field_names: list[str] | None) -> str:
        """Format a single entry's fields into display text."""
        if field_names:
            # Join all field values with full-width space separator
            parts = [v for v in entry if v]
            return "\u3000".join(parts)
        else:
            # Legacy fallback: (name, display_name, date_str) tuple
            name = entry[1] if entry[1] else entry[0]
            date = entry[2] if len(entry) > 2 else ""
            return f"{date}\u3000{name}" if date else name

    def _build_single_column_group(self, doc: Document, people_data: list, field_names: list[str] | None = None):
        """Single column layout: each person on one line."""
        for entry in people_data:
            text = "\u3000\u3000" + self._format_entry_text(entry, field_names)

            para = doc.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(14)
            run.font.name = self.FONT_NAME
            para.paragraph_format.left_indent = Inches(1.5)
            para.paragraph_format.space_after = Pt(6)

    def _build_dual_column_group(self, doc: Document, people_data: list, field_names: list[str] | None = None):
        """Dual column layout: split people into two halves."""
        # Build text for each entry and find max length for alignment
        texts = []
        max_len = 0
        for entry in people_data:
            text = self._format_entry_text(entry, field_names)
            texts.append(text)
            max_len = max(max_len, len(text))

        half = (len(people_data) + 1) // 2
        base_indent = Inches(0.5)

        # Column 1
        for idx in range(half):
            if idx < len(texts):
                self._add_dual_column_entry(doc, texts[idx], base_indent)

        # Spacer between columns
        spacer = doc.add_paragraph()
        spacer_run = spacer.add_run("\u3000\u3000\u3000")
        spacer_run.font.size = Pt(11)
        spacer_run.font.name = self.FONT_NAME

        # Column 2
        for idx in range(half, len(texts)):
            self._add_dual_column_entry(doc, texts[idx], base_indent)

    def _add_dual_column_entry(self, doc, text: str, base_indent):
        """Add a single entry in dual column format."""
        para = doc.add_paragraph()
        run = para.add_run(f"\u3000\u3000{text}")
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
