"""Renders a SummaryReport into a printable PDF (US Letter) with ReportLab."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import charts
from .summary import SummaryReport

INK = colors.HexColor("#0b0b0b")
MUTED = colors.HexColor("#52514e")
RULE = colors.HexColor("#e4e3df")
HEADER_BG = colors.HexColor("#f1f0ec")
ACCENT = colors.HexColor("#2a78d6")

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_styles["Title"], fontSize=18, alignment=0, textColor=INK, spaceAfter=2)
H2 = ParagraphStyle("H2", parent=_styles["Heading2"], fontSize=12.5, textColor=INK, spaceBefore=12, spaceAfter=6)
BODY = ParagraphStyle("Body", parent=_styles["BodyText"], fontSize=9.5, leading=13, textColor=INK)
SMALL = ParagraphStyle("Small", parent=BODY, fontSize=8, leading=10.5, textColor=MUTED)
CELL = ParagraphStyle("Cell", parent=BODY, fontSize=8.5, leading=11)

DIRECTION_LABEL = {
    "improving": "Improving",
    "worsening": "Worsening",
    "stable": "Stable",
    "insufficient_data": "Too few entries",
}


def _table(rows: list[list], col_widths: list[float]) -> Table:
    wrapped = [[c if not isinstance(c, str) else Paragraph(escape(c), CELL) for c in r] for r in rows]
    t = Table(wrapped, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _chart(png: bytes | None, width: float = 7.0 * inch) -> Image | None:
    if not png:
        return None
    img = Image(io.BytesIO(png))
    ratio = img.imageHeight / img.imageWidth
    img.drawWidth, img.drawHeight = width, width * ratio
    return img


def _fmt(v: float | None) -> str:
    return "-" if v is None else f"{v:g}"


def _ref_range(lo: float | None, hi: float | None) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g} - {hi:g}"
    if hi is not None:
        return f"< {hi:g}"
    if lo is not None:
        return f"> {lo:g}"
    return "-"


def render_pdf(report: SummaryReport) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.7 * inch,
        title=f"PrismRX summary - {report.patient.name}", author="PrismRX",
    )
    p = report.patient
    story: list = [
        Paragraph("PrismRX Patient Summary", H1),
        Paragraph(
            f"{report.start:%b %d, %Y} - {report.end:%b %d, %Y} ({report.days_in_period} days) "
            f"&nbsp;·&nbsp; Generated {report.generated_at:%b %d, %Y %I:%M %p}", SMALL),
        Spacer(1, 8),
    ]

    info = [
        ["Patient", p.name, "Date of birth", f"{p.date_of_birth:%b %d, %Y}" if p.date_of_birth else "-"],
        ["Diagnosis", p.diagnosis or "-", "Surgery",
         (p.surgery_type.value.replace("_", " ").capitalize() if p.surgery_type else "-")
         + (f" on {p.surgery_date:%b %d, %Y}" if p.surgery_date else "")],
        ["Days since surgery", _fmt(report.days_since_surgery), "RAI treatment",
         f"{p.rai_treatment_date:%b %d, %Y}" if p.rai_treatment_date else "-"],
        ["Care team", p.care_team or "-", "Check-in days", f"{report.days_with_checkins} / {report.days_in_period}"],
    ]
    t = Table([[Paragraph(f"<b>{escape(str(c))}</b>" if i % 2 == 0 else escape(str(c)), CELL)
                for i, c in enumerate(r)] for r in info],
              colWidths=[1.2 * inch, 2.3 * inch, 1.2 * inch, 2.3 * inch])
    t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, RULE), ("INNERGRID", (0, 0), (-1, -1), 0.3, RULE),
                           ("BACKGROUND", (0, 0), (0, -1), HEADER_BG), ("BACKGROUND", (2, 0), (2, -1), HEADER_BG)]))
    story.append(t)

    # Key observations
    story.append(Paragraph("Key observations", H2))
    story.append(ListFlowable(
        [ListItem(Paragraph(escape(o), BODY), leftIndent=10) for o in report.observations],
        bulletType="bullet", bulletColor=ACCENT, leftIndent=12,
    ))

    # Symptoms
    story.append(Paragraph("Symptoms", H2))
    sym = report.symptoms.symptoms
    if sym:
        for png in (charts.symptom_trend_chart(report), charts.symptom_heatmap(report)):
            img = _chart(png)
            if img:
                story += [img, Spacer(1, 6)]
        rows = [["Symptom", "Avg", "Avg when noticed", "Max", "Days noticed", "First week", "Last week", "Trend"]]
        for s in sym:
            rows.append([s.label, f"{s.average:g}", _fmt(s.average_when_noticed), str(s.max),
                         f"{s.days_noticed} / {s.days_tracked}",
                         _fmt(s.first_week_avg), _fmt(s.last_week_avg),
                         DIRECTION_LABEL[s.direction]
                         + (f"; flare ~{s.peak_date:%b %d}" if s.flare else "")])
        story.append(_table(rows, [1.55 * inch, 0.5 * inch, 0.8 * inch, 0.45 * inch, 0.8 * inch,
                                   0.7 * inch, 0.7 * inch, 1.5 * inch]))
        story.append(Paragraph(
            "Severity is self-reported on a 1-10 scale (1 = low, 10 = worst). Patients leave a symptom blank "
            "when they don't notice it, so on check-in days a blank counts as 0 (not noticed). "
            "Avg includes those days; Avg when noticed does not. Days noticed = days rated / check-in days "
            "while the symptom was tracked. Trend = slope of daily values across the period. "
            "Flare = the 7-day average rose 2+ points above both the first and last week.", SMALL))
    else:
        story.append(Paragraph("No symptoms were logged in this period.", BODY))

    # Medications
    story.append(Paragraph("Medications &amp; adherence", H2))
    meds = report.adherence.medications
    if meds:
        img = _chart(charts.adherence_chart(report))
        if img:
            story += [img, Spacer(1, 6)]
        rows = [["Medication", "Dose", "Schedule", "Doses logged", "Adherence"]]
        for m in meds:
            rows.append([
                m.name, f"{m.dose:g} {m.unit}", ", ".join(m.times_of_day) or "As needed",
                f"{m.taken_doses} / {m.expected_doses}" if m.expected_doses else str(m.taken_doses),
                f"{m.adherence_pct:g}%" if m.adherence_pct is not None else "-",
            ])
        story.append(_table(rows, [2.1 * inch, 1.1 * inch, 1.5 * inch, 1.2 * inch, 1.1 * inch]))
    else:
        story.append(Paragraph("No medications on file.", BODY))

    warnings = report.adherence.spacing_warnings
    if warnings:
        rows = [["Date", "Thyroid hormone", "Calcium", "Hours apart"]]
        for w in warnings[:15]:
            rows.append([f"{w.date:%b %d}", f"{w.thyroid_med} at {w.thyroid_taken_at:%I:%M %p}",
                         f"{w.other_med} at {w.other_taken_at:%I:%M %p}", f"{w.hours_apart:g}"])
        story.append(KeepTogether([
            Paragraph("Dose timing: thyroid hormone near calcium", H2),
            _table(rows, [1.0 * inch, 2.4 * inch, 2.4 * inch, 1.2 * inch]),
        ]))

    # Labs
    if report.labs.labs:
        heading = Paragraph("Lab results", H2)
        img = _chart(charts.lab_chart(report))
        # Keep the heading on the same page as the (tall) chart.
        story.append(KeepTogether([heading, img, Spacer(1, 6)]) if img else heading)
        rows = [["Test", "Date", "Value", "Reference range"]]
        for lab in report.labs.labs:
            for pt in lab.series:
                ref = _ref_range(pt.reference_low, pt.reference_high)
                flag = " *" if pt.out_of_range else ""
                rows.append([lab.label, f"{pt.date:%b %d, %Y}", f"{pt.value:g} {pt.unit or ''}{flag}", ref])
        story.append(_table(rows, [2.0 * inch, 1.5 * inch, 1.8 * inch, 1.7 * inch]))
        story.append(Paragraph("* outside the reference range entered with the result.", SMALL))

    # Patient notes
    if report.notable_entries:
        story.append(Paragraph("Patient notes &amp; high-severity entries", H2))
        rows = [["Date", "Symptom", "Severity", "Notes"]]
        for e in report.notable_entries:
            rows.append([f"{e.date:%b %d}", e.label, str(e.severity), e.notes or ""])
        story.append(_table(rows, [0.8 * inch, 1.6 * inch, 0.8 * inch, 3.8 * inch]))

    story += [Spacer(1, 14), Paragraph(escape(report.disclaimer), SMALL)]

    def _footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.6 * inch, 0.4 * inch, f"PrismRX · {p.name} · patient-reported data")
        canvas.drawRightString(LETTER[0] - 0.6 * inch, 0.4 * inch, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
