from datetime import date

from fastapi import APIRouter, HTTPException, status
from sqlmodel import select

from .. import catalog
from ..deps import PatientDep, SessionDep
from ..models import LabResult, LabResultCreate, LabResultRead, LabTest

router = APIRouter(prefix="/patients/{patient_id}/labs", tags=["labs"])


@router.post("", response_model=LabResultRead, status_code=status.HTTP_201_CREATED)
def add_lab(body: LabResultCreate, patient: PatientDep, session: SessionDep):
    if body.test == LabTest.other and not body.test_name:
        raise HTTPException(status_code=422, detail='test_name is required when test is "other"')
    unit = body.unit or catalog.LAB_TESTS.get(body.test.value, {}).get("default_unit")
    lab = LabResult.model_validate(body, update={"patient_id": patient.id, "unit": unit})
    session.add(lab)
    session.commit()
    session.refresh(lab)
    return lab


@router.get("", response_model=list[LabResultRead])
def list_labs(patient: PatientDep, session: SessionDep, test: LabTest | None = None,
              start: date | None = None, end: date | None = None):
    stmt = select(LabResult).where(LabResult.patient_id == patient.id)
    if test:
        stmt = stmt.where(LabResult.test == test)
    if start:
        stmt = stmt.where(LabResult.collected_on >= start)
    if end:
        stmt = stmt.where(LabResult.collected_on <= end)
    return session.exec(stmt.order_by(LabResult.collected_on.desc())).all()


@router.delete("/{lab_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lab(lab_id: int, patient: PatientDep, session: SessionDep):
    lab = session.get(LabResult, lab_id)
    if not lab or lab.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="Lab result not found")
    session.delete(lab)
    session.commit()
