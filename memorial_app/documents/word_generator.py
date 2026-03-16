"""Word document generator for nenki anniversary tables.

Generates .docx files with vertical Japanese text (縦書き / tategaki),
landscape A4 orientation, and proper Japanese formatting.
Field values are padded to fixed widths so that columns align across entries.
Optionally converts to PDF via docx2pdf.
"""

from pathlib import Path
import unicodedata

from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


def _display_width(text: str) -> int:
    """Calculate display width treating fullwidth/CJK chars as 2, others as 1."""
    w = 0
    for ch in text:
        eaw = unicodedata.east_asian_width(ch)
        w += 2 if eaw in ("F", "W", "A") else 1
    return w


def _pad_to_width(text: str, target_width: int) -> str:
    """Pad text with full-width spaces to reach target display width."""
    current = _display_width(text)
    # Each full-width space has display width 2
    needed = (target_width - current) // 2
    if needed > 0:
        return text + "\u3000" * needed
    return text


class WordGenerator:
    """Generate Word documents for nenki anniversary listings with vertical text."""

    FONT_NAME = "MS Mincho"
    # Full-width space used as field separator
    FIELD_SEP = "\u3000"

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

        # Compute global field widths across ALL groups for consistent alignment
        all_entries = []
        for _, people_data in sorted_data:
            all_entries.extend(people_data)
        field_widths = self._compute_field_widths(all_entries, field_names)

        # Each nenki group
        for key, people_data in sorted_data:
            nenki_name = key.split("|")[0]

            if single_column:
                # Subtitle centered on page
                subtitle = doc.add_paragraph()
                subtitle_run = subtitle.add_run(nenki_name)
                subtitle_run.font.size = Pt(20)
                subtitle_run.font.bold = True
                subtitle_run.font.name = self.FONT_NAME
                subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
                subtitle.paragraph_format.space_after = Pt(12)
                self._build_single_column_group(doc, people_data, field_names, field_widths)
            else:
                # Subtitle centered relative to column, not page
                self._build_dual_column_group(doc, nenki_name, people_data, field_names, field_widths)

            # Space between groups
            doc.add_paragraph()

        doc.save(str(output_path))

        # Auto-convert to PDF
        self._convert_to_pdf(output_path)

    def _compute_field_widths(self, all_entries: list, field_names: list[str] | None) -> list[int]:
        """Compute the max display width for each field position across all entries."""
        if not all_entries:
            return []
        num_fields = len(all_entries[0]) if all_entries else 0
        widths = [0] * num_fields

        for entry in all_entries:
            for i, val in enumerate(entry):
                w = _display_width(str(val) if val else "")
                if w > widths[i]:
                    widths[i] = w

        # Round up each width to even number (full-width space alignment)
        widths = [w + (w % 2) for w in widths]
        return widths

    def _format_aligned_entry(self, entry: list, field_widths: list[int]) -> str:
        """Format entry fields padded to fixed widths for alignment."""
        parts = []
        for i, val in enumerate(entry):
            text = str(val) if val else ""
            if i < len(field_widths):
                text = _pad_to_width(text, field_widths[i])
            parts.append(text)
        return self.FIELD_SEP.join(parts)

    def _build_single_column_group(
        self, doc: Document, people_data: list,
        field_names: list[str] | None, field_widths: list[int],
    ):
        """Single column layout: each person on one line, fields aligned."""
        for entry in people_data:
            text = self.FIELD_SEP + self._format_aligned_entry(entry, field_widths)

            para = doc.add_paragraph()
            run = para.add_run(text)
            run.font.size = Pt(14)
            run.font.name = self.FONT_NAME
            para.paragraph_format.left_indent = Inches(1.5)
            para.paragraph_format.space_after = Pt(6)

    def _build_dual_column_group(
        self, doc: Document, nenki_name: str, people_data: list,
        field_names: list[str] | None, field_widths: list[int],
    ):
        """Dual column layout: split people into two halves, fields aligned.

        One subtitle per group, centered relative to the entry line width.
        """
        half = (len(people_data) + 1) // 2
        base_indent = Inches(0.5)

        # Compute total entry line width (in display chars) for centering the subtitle
        # entry line = leading sep(2) + field1 + sep(2) + field2 + ...
        entry_width = 2  # leading separator
        entry_width += sum(field_widths)
        if len(field_widths) > 1:
            entry_width += (len(field_widths) - 1) * 2  # inter-field separators

        # Center nenki_name within entry_width using full-width space padding
        name_width = _display_width(nenki_name)
        total_pad = entry_width - name_width
        left_pad_chars = max(total_pad // 2 // 2, 0)  # full-width spaces (each = width 2)
        centered_name = "\u3000" * left_pad_chars + nenki_name

        # Single subtitle for this group
        subtitle = doc.add_paragraph()
        sub_run = subtitle.add_run(centered_name)
        sub_run.font.size = Pt(16)
        sub_run.font.bold = True
        sub_run.font.name = self.FONT_NAME
        subtitle.paragraph_format.left_indent = base_indent
        subtitle.paragraph_format.space_after = Pt(8)

        # Column 1 entries
        for idx in range(half):
            text = self.FIELD_SEP + self._format_aligned_entry(people_data[idx], field_widths)
            self._add_dual_column_entry(doc, text, base_indent)

        # Spacer between columns
        spacer = doc.add_paragraph()
        spacer_run = spacer.add_run("\u3000\u3000\u3000")
        spacer_run.font.size = Pt(11)
        spacer_run.font.name = self.FONT_NAME

        # Column 2 entries
        for idx in range(half, len(people_data)):
            text = self.FIELD_SEP + self._format_aligned_entry(people_data[idx], field_widths)
            self._add_dual_column_entry(doc, text, base_indent)

    def _add_dual_column_entry(self, doc, text: str, base_indent):
        """Add a single entry in dual column format."""
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
