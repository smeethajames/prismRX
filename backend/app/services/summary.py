"""Builds the doctor-facing summary (JSON). The PDF renderer consumes the same object,
so what the app shows on screen and what gets printed never disagree."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel
from sqlmodel import Session, select

from .. import catalog
from ..models import Patient, PatientRead, SymptomLog
from . import trends

DISCLAIMER = (
    "This summary was generated from patient-entered data in PrismRX. It is intended to "
    "support a conversation with your care team and is not a diagnosis or medical advice."
)


class NotableEntry(BaseModel):
    date: date
    symptom: str
    label: str
    severity: int
    notes: str | None


class SummaryReport(BaseModel):
    generated_at: datetime
    patient: PatientRead
    start: date
    end: date
    days_in_period: int
    days_with_checkins: int
    days_since_surgery: int | None
    observations: list[str]
    symptoms: trends.SymptomTrendsResponse
    adherence: trends.AdherenceResponse
    labs: trends.LabTrendsResponse
    notable_entries: list[NotableEntry]
    disclaimer: str = DISCLAIMER


def build_summary(session: Session, patient: Patient, start: date, end: date) -> SummaryReport:
    sym = trends.symptom_trends(session, patient.id, start, end)
    adh = trends.adherence(session, patient.id, start, end)
    labs = trends.lab_trends(session, patient.id, start, end)

    logs = session.exec(
        select(SymptomLog).where(
            SymptomLog.patient_id == patient.id,
            SymptomLog.logged_on >= start,
            SymptomLog.logged_on <= end,
        ).order_by(SymptomLog.logged_on)
    ).all()
    checkin_days = {l.logged_on for l in logs}
    notable = [
        NotableEntry(date=l.logged_on, symptom=l.symptom, label=catalog.symptom_label(l.symptom),
                     severity=l.severity, notes=l.notes)
        for l in logs
        if l.notes or l.severity >= catalog.FLAG_SEVERITY_THRESHOLD
    ]

    days_since = (end - patient.surgery_date).days if patient.surgery_date else None
    return SummaryReport(
        generated_at=datetime.now(),
        patient=PatientRead.model_validate(patient),
        start=start,
        end=end,
        days_in_period=(end - start).days + 1,
        days_with_checkins=len(checkin_days),
        days_since_surgery=days_since,
        observations=_observations(sym, adh, labs, len(checkin_days), (end - start).days + 1),
        symptoms=sym,
        adherence=adh,
        labs=labs,
        notable_entries=notable[-25:],
    )


def _observations(
    sym: trends.SymptomTrendsResponse,
    adh: trends.AdherenceResponse,
    labs: trends.LabTrendsResponse,
    checkin_days: int,
    period_days: int,
) -> list[str]:
    """Plain-language, factual bullets. Describes the data; never interprets it clinically."""
    out: list[str] = [f"Symptoms were logged on {checkin_days} of {period_days} days."]

    top = [s for s in sym.symptoms if s.average > 0][:3]
    if top:
        out.append("Highest average severity: " + ", ".join(f"{s.label} ({s.average}/10)" for s in top) + ".")

    worse = [s.label for s in sym.symptoms if s.direction == "worsening"]
    better = [s.label for s in sym.symptoms if s.direction == "improving"]
    if worse:
        out.append("Trending worse over the period: " + ", ".join(worse) + ".")
    if better:
        out.append("Trending better over the period: " + ", ".join(better) + ".")

    calcium_flags = [s.label for s in sym.symptoms
                     if s.symptom in catalog.HYPOCALCEMIA_SYMPTOMS and s.max >= 5]
    if calcium_flags:
        out.append(
            "Reported " + " and ".join(calcium_flags).lower()
            + " at moderate or higher severity (symptoms sometimes associated with low calcium)."
        )

    if adh.overall_pct is not None:
        out.append(f"Overall scheduled-dose adherence: {adh.overall_pct}%.")
        for m in adh.medications:
            if m.adherence_pct is not None and m.adherence_pct < 90:
                out.append(f"{m.name}: {m.taken_doses} of {m.expected_doses} scheduled doses logged ({m.adherence_pct}%).")

    if adh.spacing_warnings:
        days = len({w.date for w in adh.spacing_warnings})
        out.append(
            f"On {days} day(s), thyroid hormone was logged within "
            f"{catalog.THYROID_CALCIUM_SEPARATION_HOURS:g} hours of a calcium supplement."
        )

    for lab in labs.labs:
        if lab.latest:
            unit = f" {lab.latest.unit}" if lab.latest.unit else ""
            flag = " (outside the entered reference range)" if lab.latest.out_of_range else ""
            out.append(f"Latest {lab.label}: {lab.latest.value:g}{unit} on {lab.latest.date:%b %d}{flag}.")
    return out
