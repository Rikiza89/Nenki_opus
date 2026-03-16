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
        single_column: bool = True,
    ):
        """Create a PDF nenki document.

        Args:
            sorted_data: List of (key, entries) from ResultsPage._get_sorted_data().
            title: Document title.
            output_path: Path to save the PDF.
            single_column: True for single column layout.
        """
        # Try docx2pdf conversion first
        if self._try_docx2pdf(sorted_data, title, output_path, single_column):
            return

        # Fallback: generate PDF directly with reportlab
        self._generate_reportlab(sorted_data, title, output_path)

    def _try_docx2pdf(self, sorted_data, title, output_path, single_column) -> bool:
        """Try to generate PDF by first creating a Word doc then converting."""
        try:
            from docx2pdf import convert
        except ImportError:
            return False

        try:
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp_docx = Path(tmp.name)

            gen = WordGenerator()
            gen.create_combined_document(sorted_data, title, tmp_docx, single_column)

            convert(str(tmp_docx), str(output_path))
            tmp_docx.unlink(missing_ok=True)
            return True
        except Exception:
            tmp_docx.unlink(missing_ok=True)
            return False

    def _generate_reportlab(self, sorted_data, title, output_path):
        """Fallback PDF generation using reportlab."""
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import cm, mm
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
        )
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
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

        elements = []
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 6 * mm))

        for key, entries in sorted_data:
            nenki_name, _, death_info = key.split("|", 2)
            header_text = f"{nenki_name}　{death_info}"
            elements.append(Paragraph(header_text, section_style))

            table_data = [[
                Paragraph("氏名", header_cell_style),
                Paragraph("法名", header_cell_style),
                Paragraph("法要日", header_cell_style),
            ]]
            for name, display_name, date_str in entries:
                bname = display_name if display_name != name else ""
                table_data.append([
                    Paragraph(name, cell_style),
                    Paragraph(bname, cell_style),
                    Paragraph(date_str, cell_style),
                ])

            page_width = page[0] - 3 * cm
            col_widths = [page_width * 0.30, page_width * 0.35, page_width * 0.35]

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
