"""Trend computations shared by the /trends endpoints, the JSON summary, and the PDF.

Everything here is pure aggregation over the patient's own logs. Nothing in this
module makes clinical judgements; "direction" only describes whether logged
severity numbers went up or down over the window.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from statistics import mean

from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from .. import catalog
from ..models import (
    DoseLog,
    DoseStatus,
    LabResult,
    Medication,
    MedicationCategory,
    SymptomLog,
)

# Thresholds for calling a trend up or down: slope in severity points per week, or
# the change between the first and last week's averages (catches late-onset changes
# that a whole-period slope dilutes).
TREND_THRESHOLD_PER_WEEK = 0.5
TREND_THRESHOLD_WEEK_DELTA = 1.5
MIN_POINTS_FOR_TREND = 3
# A "flare" is a temporary rise in the middle of the period that start-vs-end
# comparisons miss: the 7-day average peaks this many points above BOTH the first
# and the last week's averages.
FLARE_THRESHOLD = 2.0


# --------------------------------------------------------------------- schemas
class SeriesPoint(BaseModel):
    date: date
    value: float  # 1-10 when noticed; 0 = checked in that day but left this symptom blank
    noticed: bool = True
    rolling_avg_7d: float | None = None


class SymptomTrend(BaseModel):
    symptom: str
    label: str
    category: str
    days_tracked: int  # check-in days since the patient started tracking this symptom
    days_noticed: int  # of those, days the symptom was actually rated
    average: float  # over tracked days, with not-noticed days counted as 0
    average_when_noticed: float | None  # over noticed days only
    max: int
    min: int
    first_week_avg: float | None
    last_week_avg: float | None
    slope_per_week: float | None
    direction: str  # improving | worsening | stable | insufficient_data
    peak_rolling_avg: float | None = None
    peak_date: date | None = None
    flare: bool = False  # temporary mid-period rise; see FLARE_THRESHOLD
    series: list[SeriesPoint]


class SymptomTrendsResponse(BaseModel):
    start: date
    end: date
    symptoms: list[SymptomTrend]


class MedicationAdherence(BaseModel):
    medication_id: int
    name: str
    category: str
    dose: float
    unit: str
    times_of_day: list[str]
    expected_doses: int
    taken_doses: int
    adherence_pct: float | None
    missed_days: list[date]


class DailyAdherence(BaseModel):
    date: date
    expected: int
    taken: int
    adherence_pct: float


class SpacingWarning(BaseModel):
    date: date
    thyroid_med: str
    thyroid_taken_at: datetime
    other_med: str
    other_taken_at: datetime
    hours_apart: float


class AdherenceResponse(BaseModel):
    start: date
    end: date
    overall_pct: float | None
    medications: list[MedicationAdherence]
    daily: list[DailyAdherence]
    spacing_warnings: list[SpacingWarning]


class LabPoint(BaseModel):
    date: date
    value: float
    unit: str | None
    reference_low: float | None = None
    reference_high: float | None = None
    out_of_range: bool | None = None


class LabTrend(BaseModel):
    test: str
    label: str
    latest: LabPoint | None
    series: list[LabPoint]


class LabTrendsResponse(BaseModel):
    start: date
    end: date
    labs: list[LabTrend]


# --------------------------------------------------------------------- helpers
def date_range(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def _slope_per_week(points: list[tuple[date, float]]) -> float | None:
    """Least-squares slope of value vs. day, scaled to points per week."""
    if len(points) < MIN_POINTS_FOR_TREND:
        return None
    x0 = points[0][0]
    xs = [(d - x0).days for d, _ in points]
    ys = [v for _, v in points]
    mx, my = mean(xs), mean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    slope_per_day = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return round(slope_per_day * 7, 2)


def _direction(slope: float | None, first_week: float | None, last_week: float | None) -> str:
    # Lower severity is better, so going down means "improving".
    if slope is None:
        return "insufficient_data"
    if slope <= -TREND_THRESHOLD_PER_WEEK:
        return "improving"
    if slope >= TREND_THRESHOLD_PER_WEEK:
        return "worsening"
    if first_week is not None and last_week is not None:
        delta = last_week - first_week
        if delta <= -TREND_THRESHOLD_WEEK_DELTA:
            return "improving"
        if delta >= TREND_THRESHOLD_WEEK_DELTA:
            return "worsening"
    return "stable"


def _window_avg(points: list[tuple[date, float]], lo: date, hi: date) -> float | None:
    vals = [v for d, v in points if lo <= d <= hi]
    return round(mean(vals), 2) if vals else None


# ---------------------------------------------------------------- symptom trends
# A symptom stays "tracked" (blank check-in days count as not noticed) while it was
# rated within this many days. Matches how long the app keeps it on the check-in form.
TRACKING_WINDOW_DAYS = 14


def symptom_trends(
    session: Session,
    patient_id: int,
    start: date,
    end: date,
    symptoms: list[str] | None = None,
) -> SymptomTrendsResponse:
    """Per-symptom series over the period.

    The scale is 1-10 and patients leave a symptom blank when they didn't notice it.
    So on a day the patient did a check-in (rated anything), a tracked symptom that
    was left blank counts as 0 = not noticed. Without this, a symptom that clears up
    would just stop appearing, and its improvement would never show.
    Days with no check-in at all stay as missing data.

    A symptom counts as tracked from the first day it was ever rated, and stays
    tracked through any check-in within TRACKING_WINDOW_DAYS of its latest rating.
    """
    lookback = start - timedelta(days=TRACKING_WINDOW_DAYS)
    logs = session.exec(
        select(SymptomLog).where(
            SymptomLog.patient_id == patient_id,
            SymptomLog.logged_on >= lookback,
            SymptomLog.logged_on <= end,
        ).order_by(SymptomLog.logged_on)
    ).all()
    # Earliest-ever rating per symptom (may be before the lookback window).
    first_seen = dict(session.exec(
        select(SymptomLog.symptom, func.min(SymptomLog.logged_on))
        .where(SymptomLog.patient_id == patient_id, SymptomLog.logged_on <= end)
        .group_by(SymptomLog.symptom)
    ).all())

    checkin_days = sorted({l.logged_on for l in logs if start <= l.logged_on <= end})
    rated: dict[str, dict[date, float]] = defaultdict(dict)
    for log in logs:
        rated[log.symptom][log.logged_on] = float(log.severity)

    wanted = {catalog.normalize_symptom_key(x) for x in symptoms} if symptoms else None
    trends: list[SymptomTrend] = []
    for key, day_map in rated.items():
        if wanted is not None and key not in wanted:
            continue
        rated_days = sorted(day_map)
        points: list[tuple[date, float]] = []
        for d in checkin_days:
            if d < first_seen.get(key, d):
                continue  # not tracking this symptom yet
            if d in day_map:
                points.append((d, day_map[d]))
                continue
            last_rating = max((r for r in rated_days if r <= d), default=None)
            if last_rating is not None and (d - last_rating).days <= TRACKING_WINDOW_DAYS:
                points.append((d, 0.0))  # checked in, left blank -> not noticed
        noticed = [v for _, v in points if v > 0]
        if not noticed and not any(start <= d <= end for d in rated_days):
            continue  # nothing to report for this symptom in the period
        if not points:
            continue

        values = [v for _, v in points]
        series = []
        for d, v in points:
            window = [val for dd, val in points if d - timedelta(days=6) <= dd <= d]
            series.append(SeriesPoint(date=d, value=v, noticed=v > 0, rolling_avg_7d=round(mean(window), 2)))
        slope = _slope_per_week(points)
        first_wk = _window_avg(points, start, start + timedelta(days=6))
        last_wk = _window_avg(points, end - timedelta(days=6), end)
        # Only full 7-day windows count toward the peak, so one bad first day isn't a "peak".
        full = [p for p in series if p.date >= start + timedelta(days=6)]
        peak = max(full, key=lambda p: p.rolling_avg_7d) if full else None
        flare = bool(
            peak and first_wk is not None and last_wk is not None
            and peak.rolling_avg_7d >= max(first_wk, last_wk) + FLARE_THRESHOLD
        )
        trends.append(
            SymptomTrend(
                symptom=key,
                label=catalog.symptom_label(key),
                category=catalog.symptom_category(key),
                days_tracked=len(points),
                days_noticed=len(noticed),
                average=round(mean(values), 2),
                average_when_noticed=round(mean(noticed), 2) if noticed else None,
                max=int(max(values)),
                min=int(min(values)),
                first_week_avg=first_wk,
                last_week_avg=last_wk,
                slope_per_week=slope,
                direction=_direction(slope, first_wk, last_wk),
                peak_rolling_avg=peak.rolling_avg_7d if peak else None,
                peak_date=peak.date if peak else None,
                flare=flare,
                series=series,
            )
        )
    # Most burdensome first: that's what the doctor will want to see.
    trends.sort(key=lambda t: (-t.average, t.label))
    return SymptomTrendsResponse(start=start, end=end, symptoms=trends)


# -------------------------------------------------------------------- adherence
def _med_active_days(med: Medication, start: date, end: date, today: date) -> list[date]:
    lo = max(start, med.start_date or med.created_at.date())
    hi = min(end, med.end_date or end, today)
    return date_range(lo, hi) if lo <= hi else []


def adherence(
    session: Session, patient_id: int, start: date, end: date, today: date | None = None
) -> AdherenceResponse:
    today = today or date.today()
    meds = session.exec(select(Medication).where(Medication.patient_id == patient_id)).all()
    doses = session.exec(
        select(DoseLog).where(
            DoseLog.patient_id == patient_id,
            DoseLog.taken_at >= datetime.combine(start, time.min),
            DoseLog.taken_at <= datetime.combine(end, time.max),
        ).order_by(DoseLog.taken_at)
    ).all()

    taken_by_med_day: dict[tuple[int, date], int] = defaultdict(int)
    for d in doses:
        if d.status == DoseStatus.taken:
            taken_by_med_day[(d.medication_id, d.taken_at.date())] += 1

    daily_expected: dict[date, int] = defaultdict(int)
    daily_taken: dict[date, int] = defaultdict(int)
    med_results: list[MedicationAdherence] = []

    for med in meds:
        per_day = len(med.times_of_day or [])
        if per_day == 0:
            # As-needed meds have no schedule to adhere to; just report usage.
            total_taken = sum(v for (mid, _), v in taken_by_med_day.items() if mid == med.id)
            if total_taken or med.active:
                med_results.append(_med_row(med, 0, total_taken, None, []))
            continue
        days = _med_active_days(med, start, end, today)
        if not days:
            continue  # not on this medication during the window
        expected = taken = 0
        missed: list[date] = []
        for day in days:
            t = min(taken_by_med_day.get((med.id, day), 0), per_day)
            expected += per_day
            taken += t
            daily_expected[day] += per_day
            daily_taken[day] += t
            if t < per_day:
                missed.append(day)
        pct = round(100 * taken / expected, 1) if expected else None
        med_results.append(_med_row(med, expected, taken, pct, missed))

    daily = [
        DailyAdherence(
            date=day,
            expected=daily_expected[day],
            taken=daily_taken[day],
            adherence_pct=round(100 * daily_taken[day] / daily_expected[day], 1),
        )
        for day in sorted(daily_expected)
        if daily_expected[day]
    ]
    total_expected = sum(daily_expected.values())
    overall = round(100 * sum(daily_taken.values()) / total_expected, 1) if total_expected else None

    return AdherenceResponse(
        start=start,
        end=end,
        overall_pct=overall,
        medications=med_results,
        daily=daily,
        spacing_warnings=spacing_warnings(meds, doses),
    )


def _med_row(med: Medication, expected: int, taken: int, pct: float | None, missed: list[date]) -> MedicationAdherence:
    return MedicationAdherence(
        medication_id=med.id,
        name=med.name,
        category=med.category.value if hasattr(med.category, "value") else str(med.category),
        dose=med.dose,
        unit=med.unit,
        times_of_day=med.times_of_day or [],
        expected_doses=expected,
        taken_doses=taken,
        adherence_pct=pct,
        missed_days=missed,
    )


def spacing_warnings(meds: list[Medication], doses: list[DoseLog]) -> list[SpacingWarning]:
    """Flag thyroid hormone doses taken within N hours of a calcium dose.

    Calcium binds levothyroxine in the gut and can reduce absorption, so this is a
    common thing for endocrinologists to ask about when TSH drifts.
    """
    by_id = {m.id: m for m in meds}
    thyroid = [d for d in doses if d.status == DoseStatus.taken and _cat(by_id.get(d.medication_id)) == MedicationCategory.thyroid_hormone]
    calcium = [d for d in doses if d.status == DoseStatus.taken and _cat(by_id.get(d.medication_id)) == MedicationCategory.calcium]
    limit = catalog.THYROID_CALCIUM_SEPARATION_HOURS
    out: list[SpacingWarning] = []
    for t in thyroid:
        for c in calcium:
            hours = abs((c.taken_at - t.taken_at).total_seconds()) / 3600
            if hours < limit:
                out.append(
                    SpacingWarning(
                        date=t.taken_at.date(),
                        thyroid_med=by_id[t.medication_id].name,
                        thyroid_taken_at=t.taken_at,
                        other_med=by_id[c.medication_id].name,
                        other_taken_at=c.taken_at,
                        hours_apart=round(hours, 1),
                    )
                )
    return out


def _cat(med: Medication | None) -> MedicationCategory | None:
    if med is None:
        return None
    return MedicationCategory(med.category)


# ------------------------------------------------------------------------- labs
def lab_trends(session: Session, patient_id: int, start: date, end: date) -> LabTrendsResponse:
    rows = session.exec(
        select(LabResult).where(
            LabResult.patient_id == patient_id,
            LabResult.collected_on >= start,
            LabResult.collected_on <= end,
        ).order_by(LabResult.collected_on)
    ).all()
    grouped: dict[str, list[LabPoint]] = defaultdict(list)
    for r in rows:
        test_value = r.test.value if hasattr(r.test, "value") else str(r.test)
        key = r.test_name if test_value == "other" and r.test_name else test_value
        out = None
        if r.reference_low is not None or r.reference_high is not None:
            out = (r.reference_low is not None and r.value < r.reference_low) or (
                r.reference_high is not None and r.value > r.reference_high
            )
        grouped[key].append(
            LabPoint(
                date=r.collected_on,
                value=r.value,
                unit=r.unit or catalog.LAB_TESTS.get(test_value, {}).get("default_unit"),
                reference_low=r.reference_low,
                reference_high=r.reference_high,
                out_of_range=out,
            )
        )
    labs = [
        LabTrend(
            test=key,
            label=catalog.LAB_TESTS[key]["label"] if key in catalog.LAB_TESTS else key,
            latest=pts[-1],
            series=pts,
        )
        for key, pts in grouped.items()
    ]
    order = list(catalog.LAB_TESTS)
    labs.sort(key=lambda l: order.index(l.test) if l.test in order else len(order))
    return LabTrendsResponse(start=start, end=end, labs=labs)
