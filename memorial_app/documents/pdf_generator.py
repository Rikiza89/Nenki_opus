"""PDF document generator for nenki anniversary tables.

Primary strategy: generate Word document first, then convert to PDF via docx2pdf.
Fallback: generate PDF directly using reportlab with CID fonts.
"""

from pathlib import Path
import tempfile

from memorial_app.documents.word_generator import WordGenerator


class PdfGenerator:
    """Generate PDF documents for nenki anniversary listings.

    Uses Word-to-PDF conversion as the primary method to preserve
    vertical text (tategaki) layout. Falls back to reportlab if
    docx2pdf is not available.
    """

    def create_document(
        self,
        sorted_data: list,
        title: str,
        output_path: Path,
        field_names: list[str] | None = None,
        single_column: bool = True,
    ):
        """Create a PDF nenki document.

        Args:
            sorted_data: List of (key, entries).
            title: Document title.
            output_path: Path to save the PDF.
            field_names: List of field names corresponding to each entry's values.
            single_column: True for single column layout.
        """
        # Try docx2pdf conversion first
        if self._try_docx2pdf(sorted_data, title, output_path, field_names, single_column):
            return

        # Fallback: generate PDF directly with reportlab
        self._generate_reportlab(sorted_data, title, output_path, field_names)

    def _try_docx2pdf(self, sorted_data, title, output_path, field_names, single_column) -> bool:
        """Try to generate PDF by first creating a Word doc then converting."""
        try:
            from docx2pdf import convert
        except ImportError:
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp_docx = Path(tmp.name)

            gen = WordGenerator()
            gen.create_combined_document(
                sorted_data, title, tmp_docx,
                field_names=field_names, single_column=single_column,
            )

            convert(str(tmp_docx), str(output_path))
            tmp_docx.unlink(missing_ok=True)
            return True
        except Exception:
            tmp_docx.unlink(missing_ok=True)
            return False

    def _generate_reportlab(self, sorted_data, title, output_path, field_names=None):
        """Fallback PDF generation using reportlab."""
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import cm, mm
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        )
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        try:
            pdfmetrics.registerFont(UnicodeCIDFont("HeiseiMin-W3"))
            pdfmetrics.registerFont(UnicodeCIDFont("HeiseiKakuGo-W5"))
        except Exception:
            pass

        font_mincho = "HeiseiMin-W3"
        font_gothic = "HeiseiKakuGo-W5"

        title_style = ParagraphStyle(
            "NenkiTitle", fontName=font_gothic, fontSize=16,
            leading=22, alignment=TA_CENTER, spaceAfter=12,
        )
        section_style = ParagraphStyle(
            "NenkiSection", fontName=font_gothic, fontSize=11,
            leading=15, textColor=HexColor("#2C3E50"),
            spaceBefore=10, spaceAfter=6,
        )
        cell_style = ParagraphStyle(
            "NenkiCell", fontName=font_mincho, fontSize=9,
            leading=12, alignment=TA_LEFT,
        )
        header_cell_style = ParagraphStyle(
            "NenkiHeader", fontName=font_gothic, fontSize=9,
            leading=12, alignment=TA_CENTER,
        )

        page = landscape(A4)
        doc = SimpleDocTemplate(
            str(output_path), pagesize=page,
            topMargin=1.5 * cm, bottomMargin=1.5 * cm,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        )

        # Determine column headers
        if field_names:
            headers = field_names
        else:
            headers = ["氏名", "法名", "法要日"]

        num_cols = len(headers)
        elements = []
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 6 * mm))

        for key, entries in sorted_data:
            nenki_name = key.split("|")[0]
            header_text = nenki_name
            elements.append(Paragraph(header_text, section_style))

            # Header row
            table_data = [[Paragraph(h, header_cell_style) for h in headers]]

            for entry in entries:
                if field_names:
                    # entry is a list of field values matching field_names
                    row = [Paragraph(str(v) if v else "", cell_style) for v in entry]
                else:
                    # Legacy: (name, display_name, date_str)
                    name = entry[0]
                    bname = entry[1] if entry[1] != entry[0] else ""
                    date_str = entry[2] if len(entry) > 2 else ""
                    row = [
                        Paragraph(name, cell_style),
                        Paragraph(bname, cell_style),
                        Paragraph(date_str, cell_style),
                    ]
                table_data.append(row)

            page_width = page[0] - 3 * cm
            col_width = page_width / num_cols
            col_widths = [col_width] * num_cols

            table = Table(table_data, colWidths=col_widths)
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), HexColor("#D5D8DC")),
                ("FONTNAME", (0, 0), (-1, 0), font_gothic),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("FONTNAME", (0, 1), (-1, -1), font_mincho),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#BDC3C7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]))

            elements.append(table)
            elements.append(Spacer(1, 8 * mm))

        doc.build(elements)
