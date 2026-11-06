"""A day's medication schedule: every scheduled dose slot with its status.

This powers the mobile "Today" screen, so the app doesn't have to reconcile
medications, schedules and dose logs itself.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session, select

from .. import catalog
from ..models import DoseLog, DoseStatus, Medication, MedicationCategory

SlotStatus = Literal["taken", "skipped", "missed", "overdue", "upcoming"]

# How long after the scheduled time a dose still counts as "upcoming" (due soon / now)
# before the app shows it as overdue.
OVERDUE_AFTER = timedelta(hours=1)


class DoseSlot(BaseModel):
    medication_id: int
    name: str
    category: str
    dose: float
    unit: str
    instructions: str | None
    scheduled_time: str  # "HH:MM"
    status: SlotStatus
    dose_log_id: int | None = None
    taken_at: datetime | None = None
    timing_note: str | None = None  # e.g. calcium scheduled too close to thyroid hormone


class AsNeededMed(BaseModel):
    medication_id: int
    name: str
    dose: float
    unit: str
    instructions: str | None
    taken_today: int


class DaySchedule(BaseModel):
    date: date
    slots: list[DoseSlot]
    as_needed: list[AsNeededMed]
    taken: int
    total: int


def _active_on(med: Medication, day: date) -> bool:
    start = med.start_date or med.created_at.date()
    if day < start:
        return False
    if med.end_date and day > med.end_date:
        return False
    # An inactive med with no end date is treated as stopped (it shouldn't show up today).
    return med.active or med.end_date is not None


def _minutes(hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return h * 60 + m


def _timing_note(slot_time: str, thyroid_times: list[str], limit_min: float) -> str | None:
    if any(abs(_minutes(slot_time) - _minutes(t)) < limit_min for t in thyroid_times):
        return (f"Scheduled within {catalog.THYROID_CALCIUM_SEPARATION_HOURS:g} h of thyroid hormone. "
                "Ask your care team about spacing these doses.")
    return None


def day_schedule(session: Session, patient_id: int, day: date, now: datetime | None = None) -> DaySchedule:
    now = now or datetime.now()
    meds = [m for m in session.exec(select(Medication).where(Medication.patient_id == patient_id)).all()
            if _active_on(m, day)]
    logs = session.exec(
        select(DoseLog).where(
            DoseLog.patient_id == patient_id,
            DoseLog.taken_at >= datetime.combine(day, time.min),
            DoseLog.taken_at <= datetime.combine(day, time.max),
        ).order_by(DoseLog.taken_at)
    ).all()

    thyroid_times = [t for m in meds if MedicationCategory(m.category) == MedicationCategory.thyroid_hormone
                     for t in m.times_of_day or []]
    limit_min = catalog.THYROID_CALCIUM_SEPARATION_HOURS * 60

    slots: list[DoseSlot] = []
    as_needed: list[AsNeededMed] = []
    for med in meds:
        med_logs = [l for l in logs if l.medication_id == med.id]
        times = sorted(med.times_of_day or [])
        if not times:
            as_needed.append(AsNeededMed(
                medication_id=med.id, name=med.name, dose=med.dose, unit=med.unit,
                instructions=med.instructions,
                taken_today=sum(1 for l in med_logs if l.status == DoseStatus.taken)))
            continue

        is_calcium = MedicationCategory(med.category) == MedicationCategory.calcium

        # Logs fill slots in time order: the first log of the day goes to the first slot, etc.
        for i, t in enumerate(times):
            log = med_logs[i] if i < len(med_logs) else None
            due = datetime.combine(day, time.fromisoformat(t))
            if log:
                status: SlotStatus = log.status.value if hasattr(log.status, "value") else log.status
            elif day < now.date():
                status = "missed"
            elif day == now.date() and now > due + OVERDUE_AFTER:
                status = "overdue"
            else:
                status = "upcoming"
            slots.append(DoseSlot(
                medication_id=med.id, name=med.name,
                category=MedicationCategory(med.category).value,
                dose=med.dose, unit=med.unit, instructions=med.instructions,
                scheduled_time=t, status=status,
                dose_log_id=log.id if log else None,
                taken_at=log.taken_at if log else None,
                timing_note=_timing_note(t, thyroid_times, limit_min) if is_calcium else None,
            ))

    slots.sort(key=lambda s: (s.scheduled_time, s.name))
    return DaySchedule(
        date=day, slots=slots, as_needed=as_needed,
        taken=sum(1 for s in slots if s.status == "taken"), total=len(slots),
    )
