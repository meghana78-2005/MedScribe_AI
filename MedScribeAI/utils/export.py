"""PDF export of a report (uses the reportlab package).

The standard PDF fonts only cover basic Western characters, so unusual symbols in the
text are replaced with simple ones before the PDF is built.
"""

import io
from xml.sax.saxutils import escape

from prompts.prompts import DETECTED_KEYS, DETECTED_LABELS, NOT_PROVIDED
from utils.reports import DISCLAIMER

NAVY, TEAL, LIGHT = "#12355B", "#0F8B8D", "#E6F4F4"
_REPLACEMENTS = {
    "\u2013": "-", "\u2014": "-", "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
    "\u2026": "...", "\u2022": "-", "\u2265": ">=", "\u2264": "<=", "\u00b1": "+/-",
    "\u2192": "->", "\u00a0": " ",
}


class ExportError(Exception):
    """A problem creating the export. The message is safe to show to the user."""


def _clean(text) -> str:
    text = str(text)
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def _para(text) -> str:
    """Text made safe for a reportlab paragraph."""
    return escape(_clean(text)).replace("\n", "<br/>")


def report_to_pdf(report: dict) -> bytes:
    """Build the PDF and return its bytes."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    except ImportError as err:
        raise ExportError("PDF export needs the 'reportlab' package. Run: pip install reportlab") from err

    try:
        note = report["note"]
        base = getSampleStyleSheet()
        body = ParagraphStyle("body", parent=base["BodyText"], fontSize=10, leading=14)
        small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=colors.HexColor("#5B6770"))
        small_next = ParagraphStyle("small_next", parent=small, keepWithNext=1)
        title = ParagraphStyle("title", parent=base["Title"], fontSize=22, textColor=colors.HexColor(NAVY), alignment=0, spaceAfter=2)
        h2 = ParagraphStyle("h2", parent=base["Heading2"], fontSize=13, textColor=colors.HexColor(NAVY), spaceBefore=10, spaceAfter=4, keepWithNext=1)
        item = ParagraphStyle("item", parent=body, leftIndent=12, firstLineIndent=-9)
        cell = ParagraphStyle("cell", parent=body, fontSize=9, leading=12)
        head = ParagraphStyle("head", parent=cell, textColor=colors.HexColor(NAVY), fontName="Helvetica-Bold")

        def bullets(items, empty=NOT_PROVIDED):
            return [Paragraph("- " + _para(i), item) for i in items] or [Paragraph(_para(empty), body)]

        def table(rows, widths, header=True):
            t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
            style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("SPAN", (0, 1), (2, 1)) if not header and len(rows[0]) == 3 and len(rows) == 2 else ("VALIGN", (0, 0), (-1, -1), "TOP"), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CFE0E6")),
                     ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
            if header:
                style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(LIGHT)))
            t.setStyle(TableStyle(style))
            return t

        story = [
            Paragraph("MedScribeAI", title),
            Paragraph("Clinical Documentation Assistant - AI-generated draft", small),
            Spacer(1, 6),
            table([[Paragraph(f"<b>Report</b> {_para(report['id'])}", cell), Paragraph(f"<b>Created</b> {_para(report['created'])}", cell),
                    Paragraph(f"<b>Updates</b> {report.get('update_count', 0)}", cell)],
                   [Paragraph(f"<b>Title</b> {_para(report['title'])}", cell), "", ""]],
                  [70 * mm, 60 * mm, 40 * mm], header=False),
            Paragraph("Clinical Summary", h2), Paragraph(_para(note["clinical_summary"]), body),
        ]

        detected = note.get("information_detected") or {}
        rows = [[Paragraph(_para(DETECTED_LABELS[k]), head), Paragraph(_para(detected.get(k, "Not provided")), cell)] for k in DETECTED_KEYS]
        story += [Paragraph("Information Detected", h2), table(rows, [45 * mm, 125 * mm], header=False)]

        story += [Paragraph("SOAP Note", h2),
                  Paragraph("<b>Subjective</b>", body), *bullets(note["subjective"]),
                  Paragraph("<b>Objective</b>", body), *bullets(note["objective"]),
                  Paragraph("<b>Assessment</b>", body), Paragraph(_para(note["assessment"]), body),
                  Paragraph("<b>Plan</b> (considerations for clinician review)", body), *bullets(note["plan"])]

        story.append(Paragraph("Possible Differential Diagnoses", h2))
        story.append(Paragraph("Possibilities to consider, not confirmed diagnoses.", small_next))
        ddx = note["differential_diagnosis"]
        if ddx:
            rows = [[Paragraph("Possible condition", head), Paragraph("Supporting information", head), Paragraph("Information still needed", head)]]
            rows += [[Paragraph(_para(r["condition"]), cell), Paragraph(_para(r["supporting_information"]), cell),
                      Paragraph(_para(r["missing_helpful_information"]), cell)] for r in ddx]
            story.append(table(rows, [45 * mm, 65 * mm, 60 * mm]))
        else:
            story.append(Paragraph("Not enough information in the dictation to suggest differential diagnoses.", body))

        story += [Paragraph("Missing Information", h2), *bullets(note["information_needing_clarification"], "No further information identified.")]
        if report.get("additions"):
            story += [Paragraph("Additional Information Added Later", h2), *bullets(report["additions"])]
        story += [Paragraph("Safety / Disclaimer", h2), Paragraph(_para(note["safety_note"]), body),
                  Paragraph(_para(DISCLAIMER), small), Spacer(1, 8),
                  Paragraph("Original clinical input", h2), Paragraph(_para(report["dictation"]), small)]

        buffer = io.BytesIO()
        SimpleDocTemplate(buffer, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm, bottomMargin=18 * mm,
                          title=f"MedScribeAI {report['id']}").build(story)
        return buffer.getvalue()
    except ExportError:
        raise
    except Exception as err:
        raise ExportError("The PDF could not be created. You can still download the report as text or JSON.") from err
