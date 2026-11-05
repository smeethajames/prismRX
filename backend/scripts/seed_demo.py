"""Populate the database with a realistic demo patient (60 days post-thyroidectomy).

    python -m scripts.seed_demo            # from backend/
    python -m scripts.seed_demo --pdf      # also writes reports_out/demo-summary.pdf
"""

import argparse
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from sqlmodel import Session

from app.database import engine, init_db
from app.models import (
    DoseLog,
    DoseStatus,
    LabResult,
    LabTest,
    Medication,
    MedicationCategory,
    Patient,
    SurgeryType,
    SymptomLog,
)

DAYS = 45


def _clamp(v: float) -> int:
    return max(0, min(10, round(v)))


def seed(session: Session, today: date | None = None, rng: random.Random | None = None) -> Patient:
    today = today or date.today()
    rng = rng or random.Random(42)
    start = today - timedelta(days=DAYS - 1)

    patient = Patient(
        name="Demo Patient",
        date_of_birth=date(1986, 4, 12),
        diagnosis="Papillary thyroid carcinoma",
        surgery_type=SurgeryType.total_thyroidectomy,
        surgery_date=today - timedelta(days=60),
        care_team="Dr. Endo (endocrinology), Dr. Surgeon (ENT)",
    )
    session.add(patient)
    session.flush()

    levo = Medication(patient_id=patient.id, name="Levothyroxine", category=MedicationCategory.thyroid_hormone,
                      dose=112, unit="mcg", times_of_day=["06:30"], start_date=start,
                      instructions="Empty stomach, 30-60 min before breakfast")
    calcium = Medication(patient_id=patient.id, name="Calcium carbonate", category=MedicationCategory.calcium,
                         dose=1250, unit="mg", times_of_day=["11:00", "18:00"], start_date=start)
    calcitriol = Medication(patient_id=patient.id, name="Calcitriol", category=MedicationCategory.vitamin_d,
                            dose=0.25, unit="mcg", times_of_day=["08:00"], start_date=start,
                            end_date=start + timedelta(days=30))
    session.add_all([levo, calcium, calcitriol])
    session.flush()

    for i in range(DAYS):
        day = start + timedelta(days=i)
        progress = i / DAYS
        if rng.random() > 0.1:  # ~10% of days without a check-in
            symptoms = {
                "fatigue": 7 - 4 * progress + rng.gauss(0, 1),
                "tingling": 5 - 5 * progress + rng.gauss(0, 0.8),
                "neck_pain": 4 - 3.5 * progress + rng.gauss(0, 0.6),
                "brain_fog": 5 - 2 * progress + rng.gauss(0, 1),
                "palpitations": 1 + 3 * max(0, progress - 0.5) * 2 + rng.gauss(0, 0.7),
                "insomnia": 2 + 2 * progress + rng.gauss(0, 1),
                "hoarseness": 3 - 2.5 * progress + rng.gauss(0, 0.5),
            }
            for key, val in symptoms.items():
                note = None
                if key == "tingling" and val > 5.5:
                    note = "Tingling around lips in the evening"
                elif key == "palpitations" and val > 4.5:
                    note = "Heart racing after climbing stairs"
                session.add(SymptomLog(patient_id=patient.id, logged_on=day, symptom=key,
                                       severity=_clamp(val), notes=note))

        def dose(med: Medication, hhmm: str, jitter_min: int = 20, miss_p: float = 0.05):
            if med.end_date and day > med.end_date:
                return
            h, m = map(int, hhmm.split(":"))
            at = datetime.combine(day, time(h, m)) + timedelta(minutes=rng.randint(-jitter_min, jitter_min))
            if rng.random() < miss_p:
                return
            session.add(DoseLog(patient_id=patient.id, medication_id=med.id, taken_at=at, status=DoseStatus.taken))

        dose(levo, "06:30", miss_p=0.04)
        # Some mornings calcium is taken early with breakfast -> spacing flag
        dose(calcium, "08:30" if rng.random() < 0.15 else "11:00", miss_p=0.08)
        dose(calcium, "18:00", miss_p=0.12)
        dose(calcitriol, "08:00", miss_p=0.05)

    labs = [
        (LabTest.tsh, [(start, 2.8), (start + timedelta(days=21), 1.4), (today - timedelta(days=2), 0.3)], 0.4, 4.0),
        (LabTest.thyroglobulin, [(start, 1.2), (today - timedelta(days=2), 0.4)], None, None),
        (LabTest.calcium, [(start, 8.1), (start + timedelta(days=21), 8.7), (today - timedelta(days=2), 9.2)], 8.5, 10.2),
    ]
    for test, points, lo, hi in labs:
        for d, v in points:
            session.add(LabResult(patient_id=patient.id, test=test, value=v, collected_on=d,
                                  reference_low=lo, reference_high=hi))
    session.commit()
    session.refresh(patient)
    return patient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", action="store_true", help="also render a sample PDF report")
    args = parser.parse_args()

    init_db()
    with Session(engine) as session:
        patient = seed(session)
        print(f"Seeded patient id={patient.id} ({patient.name})")
        if args.pdf:
            from app.services.report_pdf import render_pdf
            from app.services.summary import build_summary

            end = date.today()
            report = build_summary(session, patient, end - timedelta(days=DAYS - 1), end)
            out = Path(__file__).resolve().parent.parent / "reports_out" / "demo-summary.pdf"
            out.parent.mkdir(exist_ok=True)
            out.write_bytes(render_pdf(report))
            print(f"Wrote {out}")


if __name__ == "__main__":
    main()
