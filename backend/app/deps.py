"""Shared FastAPI dependencies."""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Annotated

from fastapi import Depends, HTTPException, Query
from sqlmodel import Session

from . import config
from .database import get_session
from .models import Patient

SessionDep = Annotated[Session, Depends(get_session)]


def get_patient(patient_id: int, session: SessionDep) -> Patient:
    # TODO(auth): once accounts exist, also check the patient belongs to the caller.
    patient = session.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient


PatientDep = Annotated[Patient, Depends(get_patient)]


@dataclass
class Period:
    start: date
    end: date


def get_period(
    start: Annotated[date | None, Query(description="Inclusive start date (YYYY-MM-DD)")] = None,
    end: Annotated[date | None, Query(description="Inclusive end date; defaults to today")] = None,
    days: Annotated[int | None, Query(ge=1, le=730, description="Lookback window ending at `end` (ignored if `start` is set)")] = None,
) -> Period:
    end = end or date.today()
    if start is None:
        start = end - timedelta(days=(days or config.DEFAULT_PERIOD_DAYS) - 1)
    if start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    if (end - start).days > 730:
        raise HTTPException(status_code=422, detail="period may not exceed 2 years")
    return Period(start=start, end=end)


PeriodDep = Annotated[Period, Depends(get_period)]
