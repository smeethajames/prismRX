"""Database tables and API schemas.

Pattern per resource: `<X>Base` (shared fields) -> `<X>` (table) / `<X>Create` /
`<X>Read` / `<X>Update`. Validation lives on the Create/Update schemas because
SQLModel table classes skip Pydantic validation.
"""

import re
from datetime import date, datetime, timezone
from enum import Enum

from pydantic import NaiveDatetime, field_validator
from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel

from .catalog import normalize_symptom_key


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# --------------------------------------------------------------------------- enums
class SurgeryType(str, Enum):
    total_thyroidectomy = "total_thyroidectomy"
    lobectomy = "lobectomy"
    completion_thyroidectomy = "completion_thyroidectomy"
    other = "other"


class MedicationCategory(str, Enum):
    thyroid_hormone = "thyroid_hormone"
    calcium = "calcium"
    vitamin_d = "vitamin_d"
    other = "other"


class DoseStatus(str, Enum):
    taken = "taken"
    skipped = "skipped"
    missed = "missed"


class LabTest(str, Enum):
    tsh = "tsh"
    free_t4 = "free_t4"
    free_t3 = "free_t3"
    thyroglobulin = "thyroglobulin"
    tg_antibodies = "tg_antibodies"
    calcium = "calcium"
    pth = "pth"
    vitamin_d = "vitamin_d"
    other = "other"


# ------------------------------------------------------------------------ patients
class PatientBase(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    date_of_birth: date | None = None
    diagnosis: str | None = Field(default=None, max_length=200, description="e.g. Papillary thyroid carcinoma")
    surgery_type: SurgeryType | None = None
    surgery_date: date | None = None
    rai_treatment_date: date | None = Field(default=None, description="Radioactive iodine treatment date, if any")
    care_team: str | None = Field(default=None, max_length=300, description="Endocrinologist / surgeon names")


class Patient(PatientBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class PatientCreate(PatientBase):
    pass


class PatientRead(PatientBase):
    id: int
    created_at: NaiveDatetime


class PatientUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    date_of_birth: date | None = None
    diagnosis: str | None = None
    surgery_type: SurgeryType | None = None
    surgery_date: date | None = None
    rai_treatment_date: date | None = None
    care_team: str | None = None


# ------------------------------------------------------------------------ symptoms
def _symptom_key(v: str) -> str:
    key = normalize_symptom_key(v)
    if not key:
        raise ValueError("symptom must not be blank")
    return key


class SymptomLogBase(SQLModel):
    symptom: str = Field(index=True, min_length=1, max_length=64,
                         description="Catalog key (see /catalog/symptoms) or a custom symptom")
    severity: int = Field(ge=0, le=10, description="0 = none, 10 = worst imaginable")
    logged_on: date = Field(index=True)
    notes: str | None = Field(default=None, max_length=1000)


class SymptomLog(SymptomLogBase, table=True):
    """One row per patient / day / symptom (enforced by a unique constraint)."""

    __tablename__ = "symptom_log"
    __table_args__ = (UniqueConstraint("patient_id", "logged_on", "symptom"),)

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)
    updated_at: NaiveDatetime = Field(default_factory=utcnow)


class SymptomLogCreate(SymptomLogBase):
    @field_validator("symptom")
    @classmethod
    def normalize_symptom(cls, v: str) -> str:
        return _symptom_key(v)


class SymptomLogRead(SymptomLogBase):
    id: int
    patient_id: int
    created_at: NaiveDatetime
    updated_at: NaiveDatetime


class SymptomLogUpdate(SQLModel):
    severity: int | None = Field(default=None, ge=0, le=10)
    notes: str | None = Field(default=None, max_length=1000)


class CheckInEntry(SQLModel):
    symptom: str = Field(min_length=1, max_length=64)
    severity: int = Field(ge=0, le=10)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("symptom")
    @classmethod
    def normalize_symptom(cls, v: str) -> str:
        return _symptom_key(v)


class DailyCheckIn(SQLModel):
    """One screen's worth of symptoms for a single day. Re-submitting the same day
    updates existing entries (upsert per symptom), so the app can simply save the
    whole form each time."""

    logged_on: date
    entries: list[CheckInEntry] = Field(min_length=1)


# --------------------------------------------------------------------- medications
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _validate_times(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    for t in v:
        if not _TIME_RE.match(t):
            raise ValueError(f'invalid time "{t}", expected HH:MM (24h)')
    return sorted(set(v))


class MedicationBase(SQLModel):
    name: str = Field(min_length=1, max_length=120)
    category: MedicationCategory = MedicationCategory.other
    dose: float = Field(gt=0)
    unit: str = Field(default="mcg", max_length=20)
    times_of_day: list[str] = Field(
        default_factory=list, sa_column=Column(JSON),
        description='Scheduled times as "HH:MM" (24h). Empty list = as needed (excluded from adherence).',
    )
    instructions: str | None = Field(default=None, max_length=500)
    start_date: date | None = None
    end_date: date | None = None
    active: bool = True


class Medication(MedicationBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class MedicationCreate(MedicationBase):
    @field_validator("times_of_day")
    @classmethod
    def check_times(cls, v):
        return _validate_times(v)


class MedicationRead(MedicationBase):
    id: int
    patient_id: int
    created_at: NaiveDatetime


class MedicationUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    category: MedicationCategory | None = None
    dose: float | None = Field(default=None, gt=0)
    unit: str | None = None
    times_of_day: list[str] | None = None
    instructions: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool | None = None

    @field_validator("times_of_day")
    @classmethod
    def check_times(cls, v):
        return _validate_times(v)


# ---------------------------------------------------------------------- dose logs
class DoseLogBase(SQLModel):
    medication_id: int = Field(foreign_key="medication.id", index=True)
    status: DoseStatus = DoseStatus.taken
    taken_at: NaiveDatetime = Field(index=True, description="When the dose was taken (or was due, if skipped/missed). Device-local time.")
    dose_amount: float | None = Field(default=None, gt=0, description="Override if different from the prescribed dose")
    notes: str | None = Field(default=None, max_length=500)


class DoseLog(DoseLogBase, table=True):
    __tablename__ = "dose_log"

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class DoseLogCreate(DoseLogBase):
    pass


class DoseLogRead(DoseLogBase):
    id: int
    patient_id: int
    created_at: NaiveDatetime


# ---------------------------------------------------------------------------- labs
class LabResultBase(SQLModel):
    test: LabTest
    test_name: str | None = Field(default=None, max_length=80, description='Required when test = "other"')
    value: float
    unit: str | None = Field(default=None, max_length=20, description="Defaults to the catalog unit")
    collected_on: date = Field(index=True)
    reference_low: float | None = None
    reference_high: float | None = None
    notes: str | None = Field(default=None, max_length=500)


class LabResult(LabResultBase, table=True):
    __tablename__ = "lab_result"

    id: int | None = Field(default=None, primary_key=True)
    patient_id: int = Field(foreign_key="patient.id", index=True)
    created_at: NaiveDatetime = Field(default_factory=utcnow)


class LabResultCreate(LabResultBase):
    pass


class LabResultRead(LabResultBase):
    id: int
    patient_id: int
    created_at: NaiveDatetime
