import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import type { AsNeededMed, DoseSlot } from "@/api/client";
import { formatClock, formatTime } from "@/lib/dates";
import { colors, radius, space, text } from "@/theme";

import { Button } from "./Button";

type Actions = {
  onTake: (medicationId: number) => Promise<void>;
  onSkip: (medicationId: number) => Promise<void>;
  onUndo: (doseLogId: number) => Promise<void>;
};

const STATUS: Record<DoseSlot["status"], { label: string; fg: string; bg: string }> = {
  taken: { label: "Taken", fg: colors.good, bg: colors.goodSoft },
  skipped: { label: "Skipped", fg: colors.textSecondary, bg: colors.neutralSoft },
  missed: { label: "Missed", fg: colors.critical, bg: colors.criticalSoft },
  overdue: { label: "Overdue", fg: colors.warning, bg: colors.warningSoft },
  upcoming: { label: "Due", fg: colors.primary, bg: colors.primarySoft },
};

function StatusPill({ status }: { status: DoseSlot["status"] }) {
  const s = STATUS[status];
  return (
    <View style={[styles.pill, { backgroundColor: s.bg }]}>
      <Text style={[styles.pillText, { color: s.fg }]}>{s.label}</Text>
    </View>
  );
}

function SlotRow({ slot, actions }: { slot: DoseSlot; actions: Actions }) {
  const [busy, setBusy] = useState<"take" | "skip" | "undo" | null>(null);
  const run = (kind: "take" | "skip" | "undo", fn: () => Promise<void>) => async () => {
    setBusy(kind);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  };
  const logged = slot.status === "taken" || slot.status === "skipped";
  const doseText = `${slot.dose} ${slot.unit}`;

  return (
    <View style={styles.row}>
      <View style={styles.rowTop}>
        <Text style={styles.time}>{formatTime(slot.scheduled_time)}</Text>
        <View style={{ flex: 1 }}>
          <Text style={text.body}>
            <Text style={{ fontWeight: "600" }}>{slot.name}</Text> · {doseText}
          </Text>
          {slot.instructions ? <Text style={text.small}>{slot.instructions}</Text> : null}
        </View>
        <StatusPill status={slot.status} />
      </View>

      {slot.timing_note ? (
        <View style={styles.note} accessibilityRole="alert">
          <Text style={[text.small, { color: colors.warning }]}>⚠ {slot.timing_note}</Text>
        </View>
      ) : null}

      <View style={styles.actions}>
        {logged ? (
          <>
            <Text style={[text.label, { flex: 1 }]}>
              {slot.status === "taken" && slot.taken_at ? `Logged at ${formatClock(slot.taken_at)}` : "Marked as skipped"}
            </Text>
            <Button
              label="Undo"
              variant="ghost"
              busy={busy === "undo"}
              onPress={run("undo", () => actions.onUndo(slot.dose_log_id!))}
              accessibilityLabel={`Undo ${slot.name} ${formatTime(slot.scheduled_time)}`}
            />
          </>
        ) : (
          <>
            <View style={{ flex: 1 }}>
              <Button
                label="Took it"
                busy={busy === "take"}
                disabled={!!busy}
                onPress={run("take", () => actions.onTake(slot.medication_id))}
                accessibilityLabel={`Mark ${slot.name} ${doseText} at ${formatTime(slot.scheduled_time)} as taken`}
              />
            </View>
            <Button
              label="Skip"
              variant="secondary"
              busy={busy === "skip"}
              disabled={!!busy}
              onPress={run("skip", () => actions.onSkip(slot.medication_id))}
              accessibilityLabel={`Skip ${slot.name} at ${formatTime(slot.scheduled_time)}`}
            />
          </>
        )}
      </View>
    </View>
  );
}

function AsNeededRow({ med, onTake }: { med: AsNeededMed; onTake: (id: number) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  return (
    <View style={[styles.row, styles.rowTop]}>
      <View style={{ flex: 1 }}>
        <Text style={text.body}>
          <Text style={{ fontWeight: "600" }}>{med.name}</Text> · {med.dose} {med.unit}
        </Text>
        <Text style={text.small}>
          {med.instructions ? `${med.instructions} · ` : ""}
          {med.taken_today ? `${med.taken_today} taken today` : "None today"}
        </Text>
      </View>
      <Button
        label="Log dose"
        variant="secondary"
        busy={busy}
        onPress={async () => {
          setBusy(true);
          try {
            await onTake(med.medication_id);
          } finally {
            setBusy(false);
          }
        }}
        accessibilityLabel={`Log a dose of ${med.name}`}
      />
    </View>
  );
}

export function DoseList({ slots, asNeeded, ...actions }: { slots: DoseSlot[]; asNeeded: AsNeededMed[] } & Actions) {
  if (!slots.length && !asNeeded.length) {
    return <Text style={text.label}>No medications scheduled today.</Text>;
  }
  return (
    <View style={{ gap: space.sm }}>
      {slots.map((s) => (
        <SlotRow key={`${s.medication_id}-${s.scheduled_time}`} slot={s} actions={actions} />
      ))}
      {asNeeded.length ? <Text style={[text.label, { marginTop: space.sm }]}>As needed</Text> : null}
      {asNeeded.map((m) => (
        <AsNeededRow key={m.medication_id} med={m} onTake={actions.onTake} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: space.md,
    gap: space.sm,
  },
  rowTop: { flexDirection: "row", alignItems: "center", gap: space.md },
  time: { width: 64, fontSize: 14, fontWeight: "600", color: colors.textSecondary },
  pill: { paddingHorizontal: space.sm, paddingVertical: 3, borderRadius: radius.pill },
  pillText: { fontSize: 12, fontWeight: "700" },
  note: { backgroundColor: colors.warningSoft, borderRadius: radius.sm, padding: space.sm },
  actions: { flexDirection: "row", alignItems: "center", gap: space.sm },
});
