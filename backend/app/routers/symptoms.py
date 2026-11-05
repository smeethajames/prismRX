from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from ..catalog import normalize_symptom_key
from ..deps import PatientDep, SessionDep
from ..models import (
    DailyCheckIn,
    SymptomLog,
    SymptomLogCreate,
    SymptomLogRead,
    SymptomLogUpdate,
    utcnow,
)

router = APIRouter(prefix="/patients/{patient_id}", tags=["symptoms"])


def _upsert(session, patient_id: int, logged_on: date, symptom: str, severity: int, notes: str | None) -> SymptomLog:
    existing = session.exec(
        select(SymptomLog).where(
            SymptomLog.patient_id == patient_id,
            SymptomLog.logged_on == logged_on,
            SymptomLog.symptom == symptom,
        )
    ).first()
    if existing:
        existing.severity = severity
        existing.notes = notes
        existing.updated_at = utcnow()
        session.add(existing)
        return existing
    row = SymptomLog(patient_id=patient_id, logged_on=logged_on, symptom=symptom, severity=severity, notes=notes)
    session.add(row)
    return row


@router.post("/symptoms", response_model=SymptomLogRead, status_code=status.HTTP_201_CREATED)
def log_symptom(body: SymptomLogCreate, patient: PatientDep, session: SessionDep):
    """Log one symptom for a day. Logging the same symptom on the same day again
    replaces the earlier value (one reading per symptom per day)."""
    row = _upsert(session, patient.id, body.logged_on, body.symptom, body.severity, body.notes)
    session.commit()
    session.refresh(row)
    return row


@router.post("/check-ins", response_model=list[SymptomLogRead], status_code=status.HTTP_201_CREATED)
def daily_check_in(body: DailyCheckIn, patient: PatientDep, session: SessionDep):
    """Save a whole day's symptom form in one request (the main mobile flow)."""
    rows = [_upsert(session, patient.id, body.logged_on, e.symptom, e.severity, e.notes) for e in body.entries]
    session.commit()
    for r in rows:
        session.refresh(r)
    return rows


@router.get("/symptoms", response_model=list[SymptomLogRead])
def list_symptoms(
    patient: PatientDep,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    symptom: Annotated[list[str] | None, Query(description="Filter by one or more symptom keys")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(SymptomLog).where(SymptomLog.patient_id == patient.id)
    if start:
        stmt = stmt.where(SymptomLog.logged_on >= start)
    if end:
        stmt = stmt.where(SymptomLog.logged_on <= end)
    if symptom:
        stmt = stmt.where(SymptomLog.symptom.in_([normalize_symptom_key(s) for s in symptom]))
    stmt = stmt.order_by(SymptomLog.logged_on.desc(), SymptomLog.symptom).offset(offset).limit(limit)
    return session.exec(stmt).all()


def _get_log(session, patient_id: int, log_id: int) -> SymptomLog:
    row = session.get(SymptomLog, log_id)
    if not row or row.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Symptom log not found")
    return row


@router.patch("/symptoms/{log_id}", response_model=SymptomLogRead)
def update_symptom(log_id: int, body: SymptomLogUpdate, patient: PatientDep, session: SessionDep):
    row = _get_log(session, patient.id, log_id)
    row.sqlmodel_update(body.model_dump(exclude_unset=True))
    row.updated_at = utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/symptoms/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symptom(log_id: int, patient: PatientDep, session: SessionDep):
    session.delete(_get_log(session, patient.id, log_id))
    session.commit()
