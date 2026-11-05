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
                        {"symptom": "palpitations", "severity": min(10, i // 2)},
                        {"symptom": "headache", "severity": 3}],
        })
    r = client.get(f"{API}/patients/{patient_id}/trends/symptoms",
                   params={"start": "2026-10-01", "end": "2026-10-14"}).json()
    by_key = {s["symptom"]: s for s in r["symptoms"]}
    assert by_key["fatigue"]["direction"] == "improving"
    assert by_key["palpitations"]["direction"] == "worsening"
    assert by_key["headache"]["direction"] == "stable"
    assert by_key["fatigue"]["days_logged"] == 14
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
