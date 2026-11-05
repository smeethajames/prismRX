from fastapi import APIRouter, status
from sqlmodel import select

from ..deps import PatientDep, SessionDep
from ..models import (
    DoseLog,
    LabResult,
    Medication,
    Patient,
    PatientCreate,
    PatientRead,
    PatientUpdate,
    SymptomLog,
)

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(body: PatientCreate, session: SessionDep):
    patient = Patient.model_validate(body)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.get("", response_model=list[PatientRead])
def list_patients(session: SessionDep):
    return session.exec(select(Patient).order_by(Patient.id)).all()


@router.get("/{patient_id}", response_model=PatientRead)
def get_patient(patient: PatientDep):
    return patient


@router.patch("/{patient_id}", response_model=PatientRead)
def update_patient(body: PatientUpdate, patient: PatientDep, session: SessionDep):
    patient.sqlmodel_update(body.model_dump(exclude_unset=True))
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_patient(patient: PatientDep, session: SessionDep):
    """Deletes the patient and all of their logs."""
    for model in (DoseLog, SymptomLog, LabResult, Medication):
        for row in session.exec(select(model).where(model.patient_id == patient.id)).all():
            session.delete(row)
    session.delete(patient)
    session.commit()
