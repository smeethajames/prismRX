import os

# Keep tests off the real database file (the app lifespan calls init_db()).
os.environ["PRISMRX_DATABASE_URL"] = "sqlite://"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.database import get_session
from app.main import app


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s


@pytest.fixture
def client(engine):
    def _session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def patient_id(client) -> int:
    r = client.post("/api/v1/patients", json={
        "name": "Test Patient",
        "surgery_type": "total_thyroidectomy",
        "surgery_date": "2026-09-01",
    })
    assert r.status_code == 201
    return r.json()["id"]
