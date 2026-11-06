import { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  api,
  type DaySchedule,
  type Patient,
  PATIENT_ID,
  type SymptomCategory,
  unwrap,
} from "@/api/client";
import { Button } from "@/components/Button";
import { Card } from "@/components/Card";
import { DoseList } from "@/components/DoseList";
import { type Entries, type Entry, SymptomCheckIn } from "@/components/SymptomCheckIn";
import { addDays, daysBetween, formatLongDate, localDate, localDateTime } from "@/lib/dates";
import { colors, space, text } from "@/theme";

// Shown for brand-new patients who haven't logged anything yet.
const DEFAULT_TRACKED = ["fatigue", "tingling", "neck_pain", "hoarseness", "palpitations", "brain_fog"];
const RECENT_DAYS = 14;

const path = { params: { path: { patient_id: PATIENT_ID } } };

type Loaded = {
  patient: Patient;
  catalog: SymptomCategory[];
  schedule: DaySchedule;
  tracked: string[];
  todays: Entries;
};

function fetchSchedule(day: string): Promise<DaySchedule> {
  return api
    .GET("/api/v1/patients/{patient_id}/schedule", {
      params: { path: { patient_id: PATIENT_ID }, query: { date: day } },
    })
    .then(unwrap);
}

/** Everything the Today screen needs. Pure (no React state), so it's easy to test and reuse. */
async function fetchToday(today: string): Promise<Loaded> {
  const [patient, cat, recent, schedule] = await Promise.all([
    api.GET("/api/v1/patients/{patient_id}", path).then(unwrap),
    api.GET("/api/v1/catalog/symptoms").then(unwrap) as Promise<{ categories: SymptomCategory[] }>,
    api
      .GET("/api/v1/patients/{patient_id}/symptoms", {
        params: { path: { patient_id: PATIENT_ID }, query: { start: addDays(today, -RECENT_DAYS), limit: 1000 } },
      })
      .then(unwrap),
    fetchSchedule(today),
  ]);

  // Pre-fill anything already logged today, and track what this patient has been logging lately.
  const todays: Entries = {};
  recent
    .filter((l) => l.logged_on === today)
    .forEach((l) => {
      todays[l.symptom] = { severity: l.severity, notes: l.notes ?? "" };
    });
  const recentKeys = Array.from(new Set(recent.map((l) => l.symptom)));
  const order = cat.categories.flatMap((c) => c.symptoms.map((s) => s.key));
  const rank = (k: string) => (order.indexOf(k) === -1 ? order.length : order.indexOf(k));
  const tracked = (recentKeys.length ? recentKeys : DEFAULT_TRACKED).sort((a, b) => rank(a) - rank(b));

  return { patient, catalog: cat.categories, schedule, tracked, todays };
}

export default function TodayScreen() {
  const today = localDate();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [schedule, setSchedule] = useState<DaySchedule | null>(null);
  const [catalog, setCatalog] = useState<SymptomCategory[]>([]);
  const [tracked, setTracked] = useState<string[]>([]);
  const [entries, setEntries] = useState<Entries>({});
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadSchedule = useCallback(async () => setSchedule(await fetchSchedule(today)), [today]);

  const apply = useCallback((d: Loaded) => {
    setError(null);
    setPatient(d.patient);
    setCatalog(d.catalog);
    setSchedule(d.schedule);
    setTracked(d.tracked);
    setEntries(d.todays);
    setDirty(false);
    setSavedAt(Object.keys(d.todays).length ? "earlier today" : null);
    setLoading(false);
    setRefreshing(false);
  }, []);

  const fail = useCallback((e: unknown) => {
    setError(e instanceof Error ? e.message : String(e));
    setLoading(false);
    setRefreshing(false);
  }, []);

  const loadAll = useCallback(() => fetchToday(today).then(apply, fail), [today, apply, fail]);

  useEffect(() => {
    let active = true; // ignore results that arrive after the screen unmounts
    fetchToday(today).then(
      (d) => active && apply(d),
      (e) => active && fail(e),
    );
    return () => {
      active = false;
    };
  }, [today, apply, fail]);

  const logDose = async (medicationId: number, status: "taken" | "skipped") => {
    try {
      unwrap(
        await api.POST("/api/v1/patients/{patient_id}/doses", {
          ...path,
          body: { medication_id: medicationId, status, taken_at: localDateTime() },
        }),
      );
      await loadSchedule();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const undoDose = async (doseLogId: number) => {
    try {
      const r = await api.DELETE("/api/v1/patients/{patient_id}/doses/{dose_id}", {
        params: { path: { patient_id: PATIENT_ID, dose_id: doseLogId } },
      });
      if (!r.response.ok) throw new Error(`API ${r.response.status}: could not undo`);
      await loadSchedule();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const saveCheckIn = async () => {
    const rated = Object.entries(entries).filter(([, e]) => e.severity != null);
    if (!rated.length) return;
    setSaving(true);
    try {
      unwrap(
        await api.POST("/api/v1/patients/{patient_id}/check-ins", {
          ...path,
          body: {
            logged_on: today,
            entries: rated.map(([symptom, e]) => ({
              symptom,
              severity: e.severity!,
              notes: e.notes.trim() || null,
            })),
          },
        }),
      );
      setDirty(false);
      setSavedAt(new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={[styles.root, styles.center]}>
        <ActivityIndicator color={colors.primary} />
      </View>
    );
  }

  const daysPostOp = patient?.surgery_date ? daysBetween(patient.surgery_date, today) : null;

  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              loadAll();
            }}
          />
        }
      >
        <View>
          <Text style={text.small}>{formatLongDate(today)}</Text>
          <Text style={text.title} accessibilityRole="header">
            Today
          </Text>
          {patient ? (
            <Text style={text.label}>
              {patient.name}
              {daysPostOp != null && daysPostOp >= 0 ? ` · Day ${daysPostOp} after surgery` : ""}
            </Text>
          ) : null}
        </View>

        {error ? (
          <View style={styles.error} accessibilityRole="alert">
            <Text style={[text.body, { color: colors.critical }]}>Something went wrong: {error}</Text>
            <Text style={text.small}>Is the backend running and is EXPO_PUBLIC_API_URL correct?</Text>
            <View style={{ alignSelf: "flex-start", marginTop: space.sm }}>
              <Button label="Try again" variant="secondary" onPress={loadAll} />
            </View>
          </View>
        ) : null}

        {schedule ? (
          <Card
            title="Medications"
            aside={<Text style={text.label}>{schedule.total ? `${schedule.taken} of ${schedule.total} taken` : ""}</Text>}
          >
            <DoseList
              slots={schedule.slots}
              asNeeded={schedule.as_needed}
              onTake={(id) => logDose(id, "taken")}
              onSkip={(id) => logDose(id, "skipped")}
              onUndo={undoDose}
            />
          </Card>
        ) : null}

        {catalog.length ? (
          <Card title="How are you feeling?">
            <SymptomCheckIn
              catalog={catalog}
              tracked={tracked}
              entries={entries}
              onChange={(key: string, entry: Entry) => {
                setEntries((prev) => ({ ...prev, [key]: entry }));
                setDirty(true);
              }}
              onTrack={(key) => setTracked((t) => (t.includes(key) ? t : [...t, key]))}
              onSave={saveCheckIn}
              saving={saving}
              dirty={dirty}
              savedAt={savedAt}
            />
          </Card>
        ) : null}

        <Text style={[text.small, { textAlign: "center" }]}>
          PrismRX organizes what you log for conversations with your care team. It is not medical advice.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  center: { alignItems: "center", justifyContent: "center" },
  content: { padding: space.lg, gap: space.lg, paddingBottom: space.xl * 2 },
  error: {
    backgroundColor: colors.criticalSoft,
    borderRadius: 10,
    padding: space.md,
    gap: space.xs,
  },
});
