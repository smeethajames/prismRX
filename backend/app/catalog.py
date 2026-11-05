"""Thyroid-specific reference data: symptoms, common medications, and lab tests.

The mobile app should fetch these from /api/v1/catalog/* to build pickers, so the
lists can evolve server-side without an app release. Patients may also log custom
symptom keys that are not in this catalog.
"""

from typing import TypedDict


class SymptomInfo(TypedDict):
    label: str
    category: str
    description: str


SYMPTOM_CATEGORIES: dict[str, str] = {
    "hypothyroid": "Possible under-replacement (low thyroid hormone)",
    "hyperthyroid": "Possible over-replacement (high thyroid hormone)",
    "hypocalcemia": "Possible low calcium (parathyroid-related)",
    "surgical": "Neck / surgical site",
    "general": "General wellbeing",
}

SYMPTOMS: dict[str, SymptomInfo] = {
    # Under-replacement
    "fatigue": {"label": "Fatigue", "category": "hypothyroid", "description": "Tiredness or low energy"},
    "cold_intolerance": {"label": "Feeling cold", "category": "hypothyroid", "description": "Sensitivity to cold"},
    "weight_gain": {"label": "Weight gain", "category": "hypothyroid", "description": "Unexplained weight gain"},
    "brain_fog": {"label": "Brain fog", "category": "hypothyroid", "description": "Trouble concentrating or remembering"},
    "constipation": {"label": "Constipation", "category": "hypothyroid", "description": "Slow or difficult bowel movements"},
    "dry_skin": {"label": "Dry skin", "category": "hypothyroid", "description": "Dry or rough skin"},
    "hair_loss": {"label": "Hair thinning", "category": "hypothyroid", "description": "Hair loss or thinning"},
    "low_mood": {"label": "Low mood", "category": "hypothyroid", "description": "Sadness or depressed mood"},
    "joint_pain": {"label": "Joint / muscle aches", "category": "hypothyroid", "description": "Aches or stiffness"},
    # Over-replacement
    "palpitations": {"label": "Palpitations", "category": "hyperthyroid", "description": "Racing or pounding heartbeat"},
    "anxiety": {"label": "Anxiety", "category": "hyperthyroid", "description": "Nervousness or restlessness"},
    "insomnia": {"label": "Trouble sleeping", "category": "hyperthyroid", "description": "Difficulty falling or staying asleep"},
    "heat_intolerance": {"label": "Feeling hot / sweating", "category": "hyperthyroid", "description": "Sensitivity to heat"},
    "tremor": {"label": "Shaky hands", "category": "hyperthyroid", "description": "Tremor"},
    # Low calcium
    "tingling": {"label": "Tingling / numbness", "category": "hypocalcemia", "description": "Around the mouth, fingers or toes"},
    "muscle_cramps": {"label": "Muscle cramps / spasms", "category": "hypocalcemia", "description": "Cramping or twitching"},
    # Surgical site
    "hoarseness": {"label": "Hoarse voice", "category": "surgical", "description": "Voice changes or weakness"},
    "swallowing_difficulty": {"label": "Trouble swallowing", "category": "surgical", "description": "Tightness or difficulty swallowing"},
    "neck_pain": {"label": "Neck pain / tightness", "category": "surgical", "description": "Pain or stiffness at the incision"},
    # General
    "headache": {"label": "Headache", "category": "general", "description": "Head pain"},
}

# Symptom keys that, at higher severities, are worth raising with the care team
# promptly. Used only to flag observations in reports - never as a diagnosis.
FLAG_SEVERITY_THRESHOLD = 7
HYPOCALCEMIA_SYMPTOMS = {k for k, v in SYMPTOMS.items() if v["category"] == "hypocalcemia"}


class MedicationInfo(TypedDict):
    name: str
    category: str
    typical_unit: str
    tip: str


MEDICATIONS: list[MedicationInfo] = [
    {"name": "Levothyroxine", "category": "thyroid_hormone", "typical_unit": "mcg",
     "tip": "Usually taken on an empty stomach, 30-60 min before food, and apart from calcium/iron."},
    {"name": "Liothyronine (T3)", "category": "thyroid_hormone", "typical_unit": "mcg",
     "tip": "Sometimes added to levothyroxine; follow your prescriber's schedule."},
    {"name": "Calcium carbonate", "category": "calcium", "typical_unit": "mg",
     "tip": "Commonly separated from thyroid hormone by about 4 hours."},
    {"name": "Calcium citrate", "category": "calcium", "typical_unit": "mg",
     "tip": "Commonly separated from thyroid hormone by about 4 hours."},
    {"name": "Calcitriol", "category": "vitamin_d", "typical_unit": "mcg",
     "tip": "Active vitamin D, often prescribed after parathyroid disruption."},
    {"name": "Vitamin D3", "category": "vitamin_d", "typical_unit": "IU", "tip": ""},
]

# Minimum separation (hours) between thyroid hormone and calcium doses before the
# report flags it. A common guideline; the patient's own care team has the final say.
THYROID_CALCIUM_SEPARATION_HOURS = 4.0


class LabInfo(TypedDict):
    label: str
    default_unit: str


LAB_TESTS: dict[str, LabInfo] = {
    "tsh": {"label": "TSH", "default_unit": "mIU/L"},
    "free_t4": {"label": "Free T4", "default_unit": "ng/dL"},
    "free_t3": {"label": "Free T3", "default_unit": "pg/mL"},
    "thyroglobulin": {"label": "Thyroglobulin (Tg)", "default_unit": "ng/mL"},
    "tg_antibodies": {"label": "Tg antibodies", "default_unit": "IU/mL"},
    "calcium": {"label": "Calcium", "default_unit": "mg/dL"},
    "pth": {"label": "PTH", "default_unit": "pg/mL"},
    "vitamin_d": {"label": "Vitamin D (25-OH)", "default_unit": "ng/mL"},
}


def symptom_label(key: str) -> str:
    info = SYMPTOMS.get(key)
    return info["label"] if info else key.replace("_", " ").capitalize()


def symptom_category(key: str) -> str:
    info = SYMPTOMS.get(key)
    return info["category"] if info else "custom"


def normalize_symptom_key(raw: str) -> str:
    return "_".join(raw.strip().lower().replace("-", " ").split())
