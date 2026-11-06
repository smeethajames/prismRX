from datetime import date, datetime, time
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import select

from ..deps import PatientDep, SessionDep
from ..services.schedule import DaySchedule, day_schedule
from ..models import (
    DoseLog,
    DoseLogCreate,
    DoseLogRead,
    Medication,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
)

router = APIRouter(prefix="/patients/{patient_id}", tags=["medications"])


def _get_med(session, patient_id: int, med_id: int) -> Medication:
    med = session.get(Medication, med_id)
    if not med or med.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="Medication not found")
    return med


# ------------------------------------------------------------------ medications
@router.post("/medications", response_model=MedicationRead, status_code=status.HTTP_201_CREATED)
def add_medication(body: MedicationCreate, patient: PatientDep, session: SessionDep):
    med = Medication.model_validate(body, update={"patient_id": patient.id})
    session.add(med)
    session.commit()
    session.refresh(med)
    return med


@router.get("/medications", response_model=list[MedicationRead])
def list_medications(patient: PatientDep, session: SessionDep, active_only: bool = False):
    stmt = select(Medication).where(Medication.patient_id == patient.id)
    if active_only:
        stmt = stmt.where(Medication.active == True)  # noqa: E712
    return session.exec(stmt.order_by(Medication.id)).all()


@router.get("/medications/{med_id}", response_model=MedicationRead)
def get_medication(med_id: int, patient: PatientDep, session: SessionDep):
    return _get_med(session, patient.id, med_id)


@router.patch("/medications/{med_id}", response_model=MedicationRead)
def update_medication(med_id: int, body: MedicationUpdate, patient: PatientDep, session: SessionDep):
    """Dose changes are common after thyroidectomy. For a dose change, prefer ending
    the old entry (`end_date`, `active=false`) and adding a new one, so the report
    keeps the history."""
    med = _get_med(session, patient.id, med_id)
    med.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(med)
    session.commit()
    session.refresh(med)
    return med


@router.delete("/medications/{med_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_medication(med_id: int, patient: PatientDep, session: SessionDep):
    med = _get_med(session, patient.id, med_id)
    for d in session.exec(select(DoseLog).where(DoseLog.medication_id == med.id)).all():
        session.delete(d)
    session.delete(med)
    session.commit()


# ----------------------------------------------------------------------- schedule
@router.get("/schedule", response_model=DaySchedule)
def get_day_schedule(patient: PatientDep, session: SessionDep, day: Annotated[
        date | None, Query(alias="date", description="Defaults to today (server local time)")] = None):
    """Every scheduled dose for one day with its status (taken / skipped / missed /
    overdue / upcoming), plus as-needed medications. Powers the app's Today screen."""
    return day_schedule(session, patient.id, day or date.today())


# --------------------------------------------------------------------- dose logs
@router.post("/doses", response_model=DoseLogRead, status_code=status.HTTP_201_CREATED)
def log_dose(body: DoseLogCreate, patient: PatientDep, session: SessionDep):
    """Record a pill as taken / skipped / missed."""
    _get_med(session, patient.id, body.medication_id)
    dose = DoseLog.model_validate(body, update={"patient_id": patient.id})
    session.add(dose)
    session.commit()
    session.refresh(dose)
    return dose


@router.get("/doses", response_model=list[DoseLogRead])
def list_doses(
    patient: PatientDep,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    medication_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    stmt = select(DoseLog).where(DoseLog.patient_id == patient.id)
    if start:
        stmt = stmt.where(DoseLog.taken_at >= datetime.combine(start, time.min))
    if end:
        stmt = stmt.where(DoseLog.taken_at <= datetime.combine(end, time.max))
    if medication_id:
        stmt = stmt.where(DoseLog.medication_id == medication_id)
    return session.exec(stmt.order_by(DoseLog.taken_at.desc()).offset(offset).limit(limit)).all()


@router.delete("/doses/{dose_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_dose(dose_id: int, patient: PatientDep, session: SessionDep):
    dose = session.get(DoseLog, dose_id)
    if not dose or dose.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Dose log not found")
    session.delete(dose)
    session.commit()
