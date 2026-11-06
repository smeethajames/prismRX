import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/**
 * Typed client for the PrismRX FastAPI backend.
 * Types come from `npm run api:types`, which reads backend/openapi.json.
 * Regenerate after any backend change.
 *
 * Base URL by environment:
 *   web / iOS simulator   http://127.0.0.1:8000
 *   Android emulator      http://10.0.2.2:8000
 *   physical phone        http://<your computer's LAN IP>:8000  (run uvicorn with --host 0.0.0.0)
 */
export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

// Until accounts exist, the app acts as one patient, chosen in .env.local.
export const PATIENT_ID = Number(process.env.EXPO_PUBLIC_PATIENT_ID ?? "1");

export const api = createClient<paths>({ baseUrl: API_URL });

export type Schemas = components["schemas"];
export type DaySchedule = Schemas["DaySchedule"];
export type DoseSlot = Schemas["DoseSlot"];
export type AsNeededMed = Schemas["AsNeededMed"];
export type SymptomLog = Schemas["SymptomLogRead"];
export type Patient = Schemas["PatientRead"];

// The catalog endpoints return plain dicts (no response model), so they're typed by hand here.
export type CatalogSymptom = { key: string; label: string; category: string; description: string };
export type SymptomCategory = { key: string; label: string; symptoms: CatalogSymptom[] };

/** Unwraps an openapi-fetch result: returns the data or throws a readable error. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    const detail = (result.error as { detail?: unknown } | undefined)?.detail;
    throw new Error(
      `API ${result.response.status}: ${typeof detail === "string" ? detail : JSON.stringify(detail ?? result.error)}`,
    );
  }
  return result.data;
}
