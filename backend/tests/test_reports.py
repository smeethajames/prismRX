import random
from datetime import date, timedelta

from app.services import charts
from app.services.report_pdf import render_pdf
from app.services.summary import build_summary
from scripts.seed_demo import DAYS, seed

TODAY = date(2026, 11, 5)


def _demo(session):
    patient = seed(session, today=TODAY, rng=random.Random(1))
    return patient, build_summary(session, patient, TODAY - timedelta(days=DAYS - 1), TODAY)


def test_summary_contents(session):
    _, report = _demo(session)
    assert report.days_in_period == DAYS
    assert report.days_since_surgery == 60
    assert report.symptoms.symptoms, "expected symptom trends"
    by_key = {s.symptom: s for s in report.symptoms.symptoms}
    assert by_key["fatigue"].direction == "improving"
    assert report.adherence.overall_pct is not None
    assert {l.test for l in report.labs.labs} == {"tsh", "thyroglobulin", "calcium"}
    assert any("adherence" in o for o in report.observations)


def test_charts_render(session):
    _, report = _demo(session)
    for name, fn in charts.CHARTS.items():
        png = fn(report)
        assert png and png.startswith(b"\x89PNG"), name


def test_pdf_render(session):
    _, report = _demo(session)
    pdf = render_pdf(report)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 20_000


def test_pdf_with_no_data(client, patient_id):
    r = client.get(f"/api/v1/patients/{patient_id}/reports/pdf", params={"days": 30})
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert client.get(f"/api/v1/patients/{patient_id}/reports/charts/symptoms.png").status_code == 404


def test_report_endpoints(client, session):
    patient, _ = _demo(session)
    params = {"start": str(TODAY - timedelta(days=DAYS - 1)), "end": str(TODAY)}
    base = f"/api/v1/patients/{patient.id}"
    s = client.get(f"{base}/reports/summary", params=params)
    assert s.status_code == 200 and s.json()["observations"]
    p = client.get(f"{base}/reports/pdf", params={**params, "download": True})
    assert p.status_code == 200 and "attachment" in p.headers["content-disposition"]
    c = client.get(f"{base}/reports/charts/heatmap.png", params=params)
    assert c.status_code == 200 and c.headers["content-type"] == "image/png"


def test_ref_range_formatting():
    from app.services.report_pdf import _ref_range

    assert _ref_range(0.4, 4.0) == "0.4 - 4"
    assert _ref_range(None, 4.0) == "< 4"
    assert _ref_range(30.0, None) == "> 30"
    assert _ref_range(None, None) == "-"


def test_lab_chart_includes_every_test(session, monkeypatch):
    """All lab tests get a panel (previously only the first 4 did)."""
    from app.models import LabResult, LabTest, Patient

    p = Patient(name="Labs")
    session.add(p)
    session.flush()
    tests = [t for t in LabTest if t != LabTest.other]
    for t in tests:
        session.add(LabResult(patient_id=p.id, test=t, value=1.0, collected_on=TODAY))
    session.commit()
    report = build_summary(session, p, TODAY - timedelta(days=29), TODAY)
    assert len(report.labs.labs) == len(tests)

    panels = []
    real_subplots = charts.plt.subplots

    def spy(nrows, ncols, **kw):
        panels.append(nrows * ncols)
        return real_subplots(nrows, ncols, **kw)

    monkeypatch.setattr(charts.plt, "subplots", spy)
    assert charts.lab_chart(report).startswith(b"\x89PNG")
    assert panels[0] >= len(tests)
