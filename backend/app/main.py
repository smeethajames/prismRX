from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__, catalog, config
from .database import init_db
from .routers import insights, labs, medications, patients, symptoms


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="PrismRX API",
    version=__version__,
    description=(
        "Symptom, medication, and lab tracking for thyroid cancer / post-thyroidectomy "
        "patients, with trend analytics and doctor-ready PDF reports."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials="*" not in config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

catalog_router = APIRouter(prefix="/catalog", tags=["catalog"])


@catalog_router.get("/symptoms")
def symptom_catalog():
    """Symptom picker data, grouped by category."""
    return {
        "categories": [
            {
                "key": cat,
                "label": label,
                "symptoms": [{"key": k, **v} for k, v in catalog.SYMPTOMS.items() if v["category"] == cat],
            }
            for cat, label in catalog.SYMPTOM_CATEGORIES.items()
        ]
    }


@catalog_router.get("/medications")
def medication_catalog():
    return {"medications": catalog.MEDICATIONS}


@catalog_router.get("/labs")
def lab_catalog():
    return {"labs": [{"key": k, **v} for k, v in catalog.LAB_TESTS.items()]}


api = APIRouter(prefix="/api/v1")
for r in (catalog_router, patients.router, symptoms.router, medications.router, labs.router, insights.router):
    api.include_router(r)
app.include_router(api)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__}
