"""Trends (JSON for in-app charts) and doctor reports (JSON / PDF / PNG)."""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from ..deps import PatientDep, PeriodDep, SessionDep
from ..services import charts, report_pdf, summary, trends

router = APIRouter(prefix="/patients/{patient_id}", tags=["trends & reports"])


@router.get("/trends/symptoms", response_model=trends.SymptomTrendsResponse)
def symptom_trends(
    patient: PatientDep, session: SessionDep, period: PeriodDep,
    symptom: Annotated[list[str] | None, Query(description="Limit to these symptom keys")] = None,
):
    """Per-symptom daily series (with 7-day rolling average) and summary stats."""
    return trends.symptom_trends(session, patient.id, period.start, period.end, symptom)


@router.get("/trends/adherence", response_model=trends.AdherenceResponse)
def adherence_trends(patient: PatientDep, session: SessionDep, period: PeriodDep):
    """Scheduled-dose adherence per medication and per day, plus dose-timing flags."""
    return trends.adherence(session, patient.id, period.start, period.end)


@router.get("/trends/labs", response_model=trends.LabTrendsResponse)
def lab_trends(patient: PatientDep, session: SessionDep, period: PeriodDep):
    return trends.lab_trends(session, patient.id, period.start, period.end)


@router.get("/reports/summary", response_model=summary.SummaryReport)
def report_summary(patient: PatientDep, session: SessionDep, period: PeriodDep):
    """Everything in the doctor report, as JSON (for an in-app preview screen)."""
    return summary.build_summary(session, patient, period.start, period.end)


@router.get("/reports/pdf", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}, "description": "PDF report"}})
def report_pdf_download(patient: PatientDep, session: SessionDep, period: PeriodDep, download: bool = False):
    """Printable report with charts. `download=true` sets Content-Disposition: attachment."""
    report = summary.build_summary(session, patient, period.start, period.end)
    pdf = report_pdf.render_pdf(report)
    filename = f"prismrx-summary-{period.start}-to-{period.end}.pdf"
    disposition = "attachment" if download else "inline"
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'{disposition}; filename="{filename}"'})


@router.get("/reports/charts/{chart}.png", response_class=Response,
            responses={200: {"content": {"image/png": {}}}, 404: {"description": "No data for this chart"}})
def report_chart(chart: Literal["symptoms", "heatmap", "adherence", "labs"],
                 patient: PatientDep, session: SessionDep, period: PeriodDep):
    """Static PNG of a single report chart."""
    report = summary.build_summary(session, patient, period.start, period.end)
    png = charts.CHARTS[chart](report)
    if png is None:
        raise HTTPException(status_code=404, detail="No data in this period for that chart")
    return Response(png, media_type="image/png")
