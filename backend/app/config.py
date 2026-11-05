"""Runtime settings, read from environment variables (prefix PRISMRX_)."""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL: str = os.getenv(
    "PRISMRX_DATABASE_URL", f"sqlite:///{(BACKEND_DIR / 'prismrx.db').as_posix()}"
)

# Comma-separated list. "*" is fine for local mobile development (Expo / Flutter);
# lock this down before deploying anywhere public.
CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("PRISMRX_CORS_ORIGINS", "*").split(",") if o.strip()
]

# Default lookback window for trends and reports when no dates are given.
DEFAULT_PERIOD_DAYS: int = int(os.getenv("PRISMRX_DEFAULT_PERIOD_DAYS", "30"))
