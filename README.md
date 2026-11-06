# PrismRX

PrismRX helps thyroid cancer and post-thyroidectomy patients track daily symptoms, medications and labs, then turns that data into a summary report they can bring to their doctor.

This repo holds two parts:

- **`backend/`**: a FastAPI service with trend analytics and a PDF report that includes charts.
- **`mobile/`**: an Expo (React Native + TypeScript) app. The **Today** screen works: mark doses taken or skipped, and do the daily symptom check-in. **Trends** and **Report** are placeholders for now.

```
prismRX/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, catalog endpoints
│   │   ├── catalog.py         # Thyroid-specific symptoms, meds, lab tests
│   │   ├── models.py          # SQLModel tables + request/response schemas
│   │   ├── deps.py            # DB session, patient lookup, date-period parsing
│   │   ├── routers/           # patients, symptoms, medications/doses, labs, insights
│   │   └── services/
│   │       ├── trends.py      # symptom trends, adherence, dose-timing flags, labs
│   │       ├── summary.py     # doctor report (JSON) + plain-language observations
│   │       ├── schedule.py    # today's dose slots + status (Today screen)
│   │       ├── charts.py      # matplotlib charts (PNG)
│   │       └── report_pdf.py  # ReportLab PDF
│   ├── scripts/
│   │   ├── seed_demo.py       # 45 days of realistic demo data
│   │   └── export_openapi.py  # writes openapi.json for client codegen
│   └── tests/
└── mobile/                    # Expo app (SDK 58, Expo Router)
    └── src/
        ├── app/               # screens: index (Today), trends, report, _layout (tabs)
        ├── api/               # typed client (openapi-fetch) + generated schema.d.ts
        ├── components/        # DoseList, SymptomCheckIn, SeverityScale, Card, Button
        ├── lib/dates.ts       # local-time helpers (the backend stores local wall-clock time)
        └── theme.ts           # placeholder design tokens
```

## Quick start

Requires Python 3.11+.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt

python -m scripts.seed_demo --pdf   # demo patient (id=1) + reports_out/demo-summary.pdf
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Interactive API docs: http://localhost:8000/docs
- Demo report: http://localhost:8000/api/v1/patients/1/reports/pdf?days=45
- Tests: `pytest`

Configuration uses environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `PRISMRX_DATABASE_URL` | `sqlite:///backend/prismrx.db` | Any SQLAlchemy URL. Use Postgres when you deploy. |
| `PRISMRX_CORS_ORIGINS` | `*` | Comma-separated allowed origins |
| `PRISMRX_DEFAULT_PERIOD_DAYS` | `30` | Default trend/report window |

## What gets tracked

| Data | Notes |
|---|---|
| **Patient profile** | Diagnosis, surgery type and date, radioactive iodine (RAI) date, care team. "Days since surgery" appears on the report. |
| **Symptoms** | Severity from 1 (low) to 10 (worst), one reading per symptom per day. A symptom the patient didn't notice is left blank; there is no 0. The catalog has 20 thyroid-specific symptoms in five groups: possible under-replacement, possible over-replacement, low calcium, surgical site, and general. Custom symptoms are also accepted. |
| **Medications** | Dose, unit, scheduled times (`"HH:MM"`), category (`thyroid_hormone`, `calcium`, `vitamin_d`, `other`), start and end dates. |
| **Dose logs** | Each dose is marked `taken`, `skipped` or `missed` with a timestamp. Adherence is calculated against the schedule. |
| **Labs** | TSH, free T4/T3, thyroglobulin, Tg antibodies, calcium, PTH and vitamin D, with optional reference ranges. |

**Thyroid-specific insight:** the backend flags any day when thyroid hormone was logged less than 4 hours from a calcium supplement. Calcium can reduce levothyroxine absorption, and endocrinologists often ask about this when TSH moves.

## API overview (`/api/v1`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/catalog/symptoms` · `/catalog/medications` · `/catalog/labs` | Data for the app's pickers |
| POST/GET/PATCH/DELETE | `/patients[/{id}]` | Patient profile |
| POST | `/patients/{id}/check-ins` | **Main mobile flow:** save a whole day's symptom form. Re-submitting updates the day. |
| POST/GET/PATCH/DELETE | `/patients/{id}/symptoms[/{log_id}]` | Individual symptom logs |
| CRUD | `/patients/{id}/medications[/{med_id}]` | Medications |
| POST/GET/DELETE | `/patients/{id}/doses[/{dose_id}]` | Pill intake log |
| POST/GET/DELETE | `/patients/{id}/labs[/{lab_id}]` | Lab results |
| GET | `/patients/{id}/schedule?date=` | One day's dose slots: taken / skipped / missed / overdue / upcoming, plus as-needed meds and calcium-timing notes |
| GET | `/patients/{id}/trends/symptoms` | Daily series, 7-day rolling average, stats, direction (improving / worsening / stable) |
| GET | `/patients/{id}/trends/adherence` | Adherence per medication and per day, plus dose-timing flags |
| GET | `/patients/{id}/trends/labs` | Lab series and latest values with out-of-range flags |
| GET | `/patients/{id}/reports/summary` | The full doctor report as JSON, for an in-app preview |
| GET | `/patients/{id}/reports/pdf` | Printable PDF with charts (`?download=true` for an attachment) |
| GET | `/patients/{id}/reports/charts/{symptoms\|heatmap\|adherence\|labs}.png` | One chart as a static PNG |

Every trends and reports endpoint accepts a time window in one of two ways: `?start=YYYY-MM-DD&end=YYYY-MM-DD`, or `?days=7|30|90` (counted back from `end`, which defaults to today).

### The PDF report contains

1. Patient header: diagnosis, surgery, days since surgery, check-in coverage
2. Key observations: factual, plain-language bullets with no clinical interpretation
3. A symptom severity chart (7-day rolling averages) and a day-by-day heatmap
4. A symptom table: average, maximum, first week vs. last week, trend
5. A daily adherence chart against a 90% line, and a medication table
6. A table of days when doses were taken too close together
7. Lab charts (one panel per test, with the reference range shaded) and a lab table
8. Patient notes and entries rated 7 or higher
9. A disclaimer

## Mobile frontend

**Recommendation: Expo (React Native + TypeScript).**

| | Expo | Flutter |
|---|---|---|
| API client from this backend | `openapi-typescript` / `orval` generate typed hooks from `openapi.json` | `openapi-generator` (dart-dio); workable, but more ceremony |
| Charts | `victory-native`, `react-native-gifted-charts` | `fl_chart` (excellent) |
| Pill reminders | `expo-notifications` (local scheduled notifications) | `flutter_local_notifications` |
| Share PDF with doctor | `expo-file-system` + `expo-sharing` (download `/reports/pdf`, then open the share sheet) | `share_plus` |
| Iteration speed | Expo Go on a phone, OTA updates via EAS | Hot reload is great; no OTA by default |
| Web version for free | Yes (`expo start --web`) | Yes, but heavier |
| Hiring and design handoff | Larger pool of JS/TS developers, easy Figma-to-React workflow | Smaller pool |

Either works. Expo wins for an MVP because of typed client generation from the OpenAPI schema, OTA updates while you iterate on UX, and the JS ecosystem. Flutter is the better choice if you want pixel-identical custom UI on both platforms and are comfortable with Dart.

### Running the mobile app

Requires **Node 22.13+** (Expo SDK 58) and the backend running.

```bash
cd mobile
npm install
cp .env.example .env.local      # set EXPO_PUBLIC_API_URL and EXPO_PUBLIC_PATIENT_ID
npx expo start                  # press w for web, or scan the QR code with Expo Go
```

Until there are accounts, the app acts as the one patient set in `EXPO_PUBLIC_PATIENT_ID`. After any backend API change, regenerate the typed client:

```bash
cd backend && python -m scripts.export_openapi && cd ../mobile && npm run api:types
```

Before calling a change done, run `npm run typecheck` and `npx expo lint`.

- Run uvicorn with `--host 0.0.0.0` so phones on your network can reach it.
- **Android emulator:** use `http://10.0.2.2:8000`. **iOS simulator:** `http://127.0.0.1:8000`. **Physical device:** `http://<your-LAN-IP>:8000`.
- On Windows, call `127.0.0.1` rather than `localhost` from scripts and tools. `localhost` can add about 2 seconds per request while the IPv6 lookup times out.
- Draw charts natively from the `/trends/*` JSON so they stay interactive. Use `/reports/pdf` only for sharing.

Suggested screens: **Today** (check-in form + "mark dose taken"), **Meds**, **Labs**, **Trends** (7/30/90-day toggle), and **Report** (preview from `/reports/summary`, share the PDF).

## Before real patients use it (not in the MVP)

- **Authentication and authorization.** No auth yet; `deps.get_patient` is where ownership checks belong. Consider Supabase, Auth0, Clerk, or FastAPI with OAuth2/JWT.
- **HIPAA.** Patient health information needs encryption at rest and in transit, audit logs, a BAA with your host, and data export and deletion.
- **Migrations.** Add Alembic before changing the schema on a real database. Right now `create_all` runs at startup.
- **Time zones.** Dose times are stored as naive device-local time. Store the user's time zone on the profile if users travel.
- **Clinical review.** The symptom catalog, the 4-hour spacing rule and the report wording should be reviewed by an endocrinologist.

> PrismRX organizes patient-reported data for conversations with a care team. It does not diagnose or give medical advice.
