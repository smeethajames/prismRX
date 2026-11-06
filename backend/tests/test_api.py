from datetime import date, timedelta

API = "/api/v1"


def test_health_and_catalog(client):
    assert client.get("/health").json()["status"] == "ok"
    cats = client.get(f"{API}/catalog/symptoms").json()["categories"]
    keys = {s["key"] for c in cats for s in c["symptoms"]}
    assert {"fatigue", "tingling", "palpitations"} <= keys
    assert any(m["name"] == "Levothyroxine" for m in client.get(f"{API}/catalog/medications").json()["medications"])


def test_patient_crud(client, patient_id):
    r = client.patch(f"{API}/patients/{patient_id}", json={"diagnosis": "Papillary thyroid carcinoma"})
    assert r.json()["diagnosis"] == "Papillary thyroid carcinoma"
    assert client.get(f"{API}/patients/999").status_code == 404
    assert client.delete(f"{API}/patients/{patient_id}").status_code == 204
    assert client.get(f"{API}/patients/{patient_id}").status_code == 404


def test_symptom_validation_and_normalization(client, patient_id):
    url = f"{API}/patients/{patient_id}/symptoms"
    assert client.post(url, json={"symptom": "fatigue", "severity": 11, "logged_on": "2026-10-01"}).status_code == 422
    r = client.post(url, json={"symptom": "  Muscle Cramps ", "severity": 4, "logged_on": "2026-10-01"})
    assert r.status_code == 201
    assert r.json()["symptom"] == "muscle_cramps"


def test_check_in_upserts_same_day(client, patient_id):
    url = f"{API}/patients/{patient_id}/check-ins"
    body = {"logged_on": "2026-10-01", "entries": [{"symptom": "fatigue", "severity": 6},
                                                   {"symptom": "tingling", "severity": 3}]}
    assert client.post(url, json=body).status_code == 201
    body["entries"][0]["severity"] = 2
    client.post(url, json=body)
    logs = client.get(f"{API}/patients/{patient_id}/symptoms").json()
    assert len(logs) == 2
    assert next(l for l in logs if l["symptom"] == "fatigue")["severity"] == 2


def test_symptom_trend_direction(client, patient_id):
    start = date(2026, 10, 1)
    for i in range(14):
        client.post(f"{API}/patients/{patient_id}/check-ins", json={
            "logged_on": str(start + timedelta(days=i)),
            "entries": [{"symptom": "fatigue", "severity": max(0, 8 - i // 2)},
                        {"symptom": "palpitations", "severity": max(1, min(10, i // 2))},
                        {"symptom": "headache", "severity": 3}],
        })
    r = client.get(f"{API}/patients/{patient_id}/trends/symptoms",
                   params={"start": "2026-10-01", "end": "2026-10-14"}).json()
    by_key = {s["symptom"]: s for s in r["symptoms"]}
    assert by_key["fatigue"]["direction"] == "improving"
    assert by_key["palpitations"]["direction"] == "worsening"
    assert by_key["headache"]["direction"] == "stable"
    assert by_key["fatigue"]["days_noticed"] == by_key["fatigue"]["days_tracked"] == 14
    assert len(by_key["fatigue"]["series"]) == 14


def _setup_meds(client, pid):
    levo = client.post(f"{API}/patients/{pid}/medications", json={
        "name": "Levothyroxine", "category": "thyroid_hormone", "dose": 100, "unit": "mcg",
        "times_of_day": ["07:00"], "start_date": "2026-10-01"}).json()
    cal = client.post(f"{API}/patients/{pid}/medications", json={
        "name": "Calcium carbonate", "category": "calcium", "dose": 500, "unit": "mg",
        "times_of_day": ["12:00", "18:00"], "start_date": "2026-10-01"}).json()
    return levo, cal


def test_medication_time_validation(client, patient_id):
    r = client.post(f"{API}/patients/{patient_id}/medications",
                    json={"name": "X", "dose": 1, "times_of_day": ["7am"]})
    assert r.status_code == 422


def test_adherence_and_spacing(client, patient_id):
    levo, cal = _setup_meds(client, patient_id)
    url = f"{API}/patients/{patient_id}/doses"
    # Day 1: everything taken, calcium at 12:00 (5h after levo -> fine)
    client.post(url, json={"medication_id": levo["id"], "taken_at": "2026-10-01T07:00:00"})
    client.post(url, json={"medication_id": cal["id"], "taken_at": "2026-10-01T12:00:00"})
    client.post(url, json={"medication_id": cal["id"], "taken_at": "2026-10-01T18:00:00"})
    # Day 2: levo taken, calcium taken at 08:30 (1.5h after -> flagged), evening missed
    client.post(url, json={"medication_id": levo["id"], "taken_at": "2026-10-02T07:00:00"})
    client.post(url, json={"medication_id": cal["id"], "taken_at": "2026-10-02T08:30:00"})
    client.post(url, json={"medication_id": cal["id"], "taken_at": "2026-10-02T18:00:00", "status": "skipped"})

    r = client.get(f"{API}/patients/{patient_id}/trends/adherence",
                   params={"start": "2026-10-01", "end": "2026-10-02"}).json()
    meds = {m["name"]: m for m in r["medications"]}
    assert meds["Levothyroxine"]["adherence_pct"] == 100.0
    assert meds["Calcium carbonate"]["taken_doses"] == 3
    assert meds["Calcium carbonate"]["expected_doses"] == 4
    assert meds["Calcium carbonate"]["missed_days"] == ["2026-10-02"]
    assert r["overall_pct"] == round(100 * 5 / 6, 1)
    assert len(r["spacing_warnings"]) == 1
    assert r["spacing_warnings"][0]["hours_apart"] == 1.5


def test_dose_for_other_patients_med_rejected(client, patient_id):
    levo, _ = _setup_meds(client, patient_id)
    other = client.post(f"{API}/patients", json={"name": "Other"}).json()["id"]
    r = client.post(f"{API}/patients/{other}/doses",
                    json={"medication_id": levo["id"], "taken_at": "2026-10-01T07:00:00"})
    assert r.status_code == 404


def test_labs_default_unit_and_range(client, patient_id):
    r = client.post(f"{API}/patients/{patient_id}/labs", json={
        "test": "tsh", "value": 5.2, "collected_on": "2026-10-05", "reference_low": 0.4, "reference_high": 4.0})
    assert r.json()["unit"] == "mIU/L"
    t = client.get(f"{API}/patients/{patient_id}/trends/labs",
                   params={"start": "2026-10-01", "end": "2026-10-31"}).json()
    assert t["labs"][0]["latest"]["out_of_range"] is True
    assert client.post(f"{API}/patients/{patient_id}/labs",
                       json={"test": "other", "value": 1, "collected_on": "2026-10-05"}).status_code == 422


def test_period_validation(client, patient_id):
    url = f"{API}/patients/{patient_id}/trends/symptoms"
    assert client.get(url, params={"start": "2026-10-10", "end": "2026-10-01"}).status_code == 422
    r = client.get(url, params={"days": 7, "end": "2026-10-07"}).json()
    assert r["start"] == "2026-10-01"


def test_mid_period_flare_detected(client, patient_id):
    # Low at the start and end, spike in the middle: start-vs-end trend is "stable",
    # but the flare must still be reported.
    start = date(2026, 10, 1)
    for i in range(30):
        sev = 8 if 12 <= i <= 18 else 2
        client.post(f"{API}/patients/{patient_id}/check-ins", json={
            "logged_on": str(start + timedelta(days=i)), "entries": [{"symptom": "fatigue", "severity": sev}]})
    r = client.get(f"{API}/patients/{patient_id}/trends/symptoms",
                   params={"start": "2026-10-01", "end": "2026-10-30"}).json()
    fatigue = r["symptoms"][0]
    assert fatigue["direction"] == "stable"
    assert fatigue["flare"] is True
    assert fatigue["peak_rolling_avg"] == 8.0
    assert fatigue["peak_date"] == "2026-10-19"
    summary = client.get(f"{API}/patients/{patient_id}/reports/summary",
                         params={"start": "2026-10-01", "end": "2026-10-30"}).json()
    assert any("flare" in o for o in summary["observations"])


def test_steady_symptom_is_not_a_flare(client, patient_id):
    start = date(2026, 10, 1)
    for i in range(20):
        client.post(f"{API}/patients/{patient_id}/check-ins", json={
            "logged_on": str(start + timedelta(days=i)), "entries": [{"symptom": "headache", "severity": 4}]})
    r = client.get(f"{API}/patients/{patient_id}/trends/symptoms",
                   params={"start": "2026-10-01", "end": "2026-10-20"}).json()
    assert r["symptoms"][0]["flare"] is False


def test_all_notes_kept_in_summary(client, patient_id):
    start = date(2026, 1, 1)
    for i in range(40):
        client.post(f"{API}/patients/{patient_id}/symptoms", json={
            "symptom": "fatigue", "severity": 3, "logged_on": str(start + timedelta(days=i)), "notes": f"note {i}"})
    s = client.get(f"{API}/patients/{patient_id}/reports/summary",
                   params={"start": "2026-01-01", "end": "2026-02-09"}).json()
    assert len(s["notable_entries"]) == 40
    assert s["notable_entries"][0]["notes"] == "note 0"


def test_severity_zero_rejected_for_new_entries(client, patient_id):
    """The scale is 1-10; a symptom that wasn't noticed is left out, not logged as 0."""
    base = f"{API}/patients/{patient_id}"
    assert client.post(f"{base}/symptoms", json={"symptom": "fatigue", "severity": 0,
                                                 "logged_on": "2026-10-01"}).status_code == 422
    assert client.post(f"{base}/check-ins", json={"logged_on": "2026-10-01", "entries": [
        {"symptom": "fatigue", "severity": 0}]}).status_code == 422
    log = client.post(f"{base}/symptoms", json={"symptom": "fatigue", "severity": 1,
                                                "logged_on": "2026-10-01"}).json()
    assert client.patch(f"{base}/symptoms/{log['id']}", json={"severity": 0}).status_code == 422


def test_legacy_zero_entries_still_load(client, session, patient_id):
    """Entries stored before the 1-10 change may hold 0; reading them must not break."""
    from app.models import SymptomLog

    session.add(SymptomLog(patient_id=patient_id, symptom="tingling", severity=0, logged_on=date(2026, 9, 1)))
    session.commit()
    r = client.get(f"{API}/patients/{patient_id}/symptoms")
    assert r.status_code == 200 and r.json()[0]["severity"] == 0
    assert client.get(f"{API}/patients/{patient_id}/reports/pdf",
                      params={"start": "2026-09-01", "end": "2026-09-30"}).status_code == 200


def _checkin(client, pid, day, **ratings):
    r = client.post(f"{API}/patients/{pid}/check-ins", json={
        "logged_on": str(day), "entries": [{"symptom": k, "severity": v} for k, v in ratings.items()]})
    assert r.status_code == 201


def _trend(client, pid, start, end):
    r = client.get(f"{API}/patients/{pid}/trends/symptoms", params={"start": str(start), "end": str(end)}).json()
    return {s["symptom"]: s for s in r["symptoms"]}


def test_blank_on_checkin_day_counts_as_not_noticed(client, patient_id):
    """Tingling clears up after a week: the blanks must show as improvement, not vanish."""
    start = date(2026, 10, 1)
    for i in range(14):
        ratings = {"fatigue": 4}
        if i < 7:
            ratings["tingling"] = 5
        _checkin(client, patient_id, start + timedelta(days=i), **ratings)
    t = _trend(client, patient_id, start, start + timedelta(days=13))["tingling"]
    assert (t["days_noticed"], t["days_tracked"]) == (7, 14)
    assert t["average_when_noticed"] == 5.0
    assert t["average"] == 2.5
    assert t["last_week_avg"] == 0.0
    assert t["direction"] == "improving"
    blanks = [p for p in t["series"] if not p["noticed"]]
    assert len(blanks) == 7 and all(p["value"] == 0 for p in blanks)


def test_days_without_checkin_stay_missing(client, patient_id):
    start = date(2026, 10, 1)
    for i in (0, 1, 5, 6):  # no check-in on days 2-4
        _checkin(client, patient_id, start + timedelta(days=i), fatigue=6)
    t = _trend(client, patient_id, start, start + timedelta(days=6))["fatigue"]
    assert t["days_tracked"] == 4
    assert [p["date"] for p in t["series"]] == ["2026-10-01", "2026-10-02", "2026-10-06", "2026-10-07"]


def test_symptom_not_zero_filled_before_first_rating(client, patient_id):
    """A symptom first noticed mid-period wasn't 'not noticed' before the patient tracked it."""
    start = date(2026, 10, 1)
    for i in range(10):
        ratings = {"fatigue": 3}
        if i >= 6:
            ratings["palpitations"] = 6
        _checkin(client, patient_id, start + timedelta(days=i), **ratings)
    t = _trend(client, patient_id, start, start + timedelta(days=9))["palpitations"]
    assert t["days_tracked"] == 4 and t["average"] == 6.0


def test_tracking_stops_after_window(client, patient_id):
    """Blanks count as not noticed only within 14 days of the last rating."""
    start = date(2026, 10, 1)
    _checkin(client, patient_id, start, fatigue=3, hoarseness=4)
    for i in range(1, 30):
        _checkin(client, patient_id, start + timedelta(days=i), fatigue=3)
    t = _trend(client, patient_id, start, start + timedelta(days=29))["hoarseness"]
    assert t["days_tracked"] == 15  # the rated day + 14 days of "not noticed"
    assert t["days_noticed"] == 1


def test_symptom_filter_uses_all_checkins(client, patient_id):
    start = date(2026, 10, 1)
    _checkin(client, patient_id, start, fatigue=3, tingling=5)
    _checkin(client, patient_id, start + timedelta(days=1), fatigue=3)
    r = client.get(f"{API}/patients/{patient_id}/trends/symptoms",
                   params={"start": "2026-10-01", "end": "2026-10-02", "symptom": "tingling"}).json()
    assert [s["symptom"] for s in r["symptoms"]] == ["tingling"]
    assert r["symptoms"][0]["days_tracked"] == 2
