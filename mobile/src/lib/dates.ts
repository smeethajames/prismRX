// The backend stores device-local times without a timezone, so we send local
// wall-clock strings here, never `toISOString()` (which converts to UTC).

const pad = (n: number) => String(n).padStart(2, "0");

/** "YYYY-MM-DD" in local time */
export function localDate(d = new Date()): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "YYYY-MM-DDTHH:mm:ss" in local time */
export function localDateTime(d = new Date()): string {
  return `${localDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return localDate(new Date(y, m - 1, d + days));
}

/** "06:30" -> "6:30 AM" */
export function formatTime(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const suffix = h >= 12 ? "PM" : "AM";
  return `${h % 12 || 12}:${pad(m)} ${suffix}`;
}

/** "2026-11-06T06:41:12" -> "6:41 AM" */
export function formatClock(isoDateTime: string): string {
  return formatTime(isoDateTime.slice(11, 16));
}

export function formatLongDate(isoDate: string): string {
  const [y, m, d] = isoDate.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

export function daysBetween(fromIso: string, toIso: string): number {
  const [a, b] = [fromIso, toIso].map((s) => {
    const [y, m, d] = s.split("-").map(Number);
    return Date.UTC(y, m - 1, d);
  });
  return Math.round((b - a) / 86_400_000);
}
