"""Write the OpenAPI schema to backend/openapi.json for mobile client codegen.

    python -m scripts.export_openapi
"""

import json
from pathlib import Path

from app.main import app

out = Path(__file__).resolve().parent.parent / "openapi.json"
out.write_text(json.dumps(app.openapi(), indent=2))
print(f"Wrote {out}")
