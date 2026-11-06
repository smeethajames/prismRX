from datetime import date, datetime

from app.services.schedule import day_schedule

API = "/api/v1"


def _meds(client, pid):
    post = lambda body: client.post(f"{API}/patients/{pid}/medications", json=body).json()  # noqa: E731
    levo = post({"name": "Levothyroxine", "category": "thyroid_hormone", "dose": 100, "unit": "mcg",
                 "times_of_day": ["06:30"], "start_date": "2026-10-01"})
    cal = post({"name": "Calcium", "category": "calcium", "dose": 500, "unit": "mg",
                "times_of_day": ["08:00", "18:00"], "start_date": "2026-10-01"})
    prn = post({"name": "Ibuprofen", "dose": 400, "unit": "mg", "times_of_day": [], "start_date": "2026-10-01"})
    ended = post({"name": "Calcitriol", "category": "vitamin_d", "dose": 0.25, "times_of_day": ["08:00"],
                  "start_date": "2026-09-01", "end_date": "2026-09-30", "active": False})
    return levo, cal, prn, ended


def test_schedule_statuses(client, engine, patient_id):
    from sqlmodel import Session

    levo, cal, prn, _ = _meds(client, patient_id)
    url = f"{API}/patients/{patient_id}/doses"
    client.post(url, json={"medication_id": levo["id"], "taken_at": "2026-10-10T06:40:00"})
    client.post(url, json={"medication_id": cal["id"], "taken_at": "2026-10-10T08:05:00", "status": "skipped"})
    client.post(url, json={"medication_id": prn["id"], "taken_at": "2026-10-10T13:00:00"})

    with Session(engine) as s:
        # 10:00 on that day: the 18:00 calcium dose is still upcoming
        sched = day_schedule(s, patient_id, date(2026, 10, 10), now=datetime(2026, 10, 10, 10, 0))
        by = {(x.name, x.scheduled_time): x for x in sched.slots}
        assert [x.scheduled_time for x in sched.slots] == ["06:30", "08:00", "18:00"]
        assert by[("Levothyroxine", "06:30")].status == "taken"
        assert by[("Calcium", "08:00")].status == "skipped"
        assert by[("Calcium", "18:00")].status == "upcoming"
        assert (sched.taken, sched.total) == (1, 3)
        assert sched.as_needed[0].taken_today == 1
        # Calcitriol ended in September, so it isn't on the schedule
        assert "Calcitriol" not in {x.name for x in sched.slots}
        # 08:00 calcium is 1.5 h after 06:30 levothyroxine -> note; 18:00 is fine
        assert by[("Calcium", "08:00")].timing_note
        assert by[("Calcium", "18:00")].timing_note is None

        late = day_schedule(s, patient_id, date(2026, 10, 10), now=datetime(2026, 10, 10, 20, 0))
        assert {x.scheduled_time: x.status for x in late.slots}["18:00"] == "overdue"

        past = day_schedule(s, patient_id, date(2026, 10, 9), now=datetime(2026, 10, 10, 10, 0))
        assert {x.status for x in past.slots} == {"missed"}


def test_schedule_endpoint(client, patient_id):
    _meds(client, patient_id)
    r = client.get(f"{API}/patients/{patient_id}/schedule", params={"date": "2026-10-10"})
    assert r.status_code == 200
    body = r.json()
    assert body["date"] == "2026-10-10" and body["total"] == 3
