import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import type { SymptomCategory } from "@/api/client";
import { colors, radius, space, text } from "@/theme";

import { Button } from "./Button";
import { SeverityScale } from "./SeverityScale";

export type Entry = { severity: number | null; notes: string };
export type Entries = Record<string, Entry>;

export function SymptomCheckIn({
  catalog,
  tracked,
  entries,
  onChange,
  onTrack,
  onSave,
  saving,
  dirty,
  savedAt,
}: {
  catalog: SymptomCategory[];
  tracked: string[];
  entries: Entries;
  onChange: (key: string, entry: Entry) => void;
  onTrack: (key: string) => void;
  onSave: () => void;
  saving: boolean;
  dirty: boolean;
  savedAt: string | null;
}) {
  const [adding, setAdding] = useState(false);
  const [noteOpen, setNoteOpen] = useState<Record<string, boolean>>({});

  const labels = useMemo(() => {
    const m: Record<string, string> = {};
    catalog.forEach((c) => c.symptoms.forEach((s) => (m[s.key] = s.label)));
    return m;
  }, [catalog]);
  const label = (k: string) => labels[k] ?? k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());

  const filled = tracked.filter((k) => entries[k]?.severity != null).length;

  return (
    <View style={{ gap: space.lg }}>
      <Text style={text.label}>
        Rate each symptom from 0 (none) to 10 (worst). Leave blank if you didn&apos;t notice it.
      </Text>

      {tracked.map((key) => {
        const entry = entries[key] ?? { severity: null, notes: "" };
        const showNote = noteOpen[key] || !!entry.notes;
        return (
          <View key={key} style={{ gap: space.sm }}>
            <View style={styles.symptomHeader}>
              <Text style={[text.body, { fontWeight: "600", flex: 1 }]}>{label(key)}</Text>
              {!showNote ? (
                <Pressable
                  onPress={() => setNoteOpen((o) => ({ ...o, [key]: true }))}
                  accessibilityRole="button"
                  accessibilityLabel={`Add a note for ${label(key)}`}
                  hitSlop={8}
                >
                  <Text style={styles.link}>+ Note</Text>
                </Pressable>
              ) : null}
            </View>
            <SeverityScale
              label={label(key)}
              value={entry.severity}
              onChange={(severity) => onChange(key, { ...entry, severity })}
            />
            {showNote ? (
              <TextInput
                value={entry.notes}
                onChangeText={(notes) => onChange(key, { ...entry, notes })}
                placeholder="What happened? (shows up in your doctor report)"
                placeholderTextColor={colors.textMuted}
                accessibilityLabel={`Note for ${label(key)}`}
                multiline
                maxLength={1000}
                style={styles.input}
              />
            ) : null}
          </View>
        );
      })}

      {adding ? (
        <View style={{ gap: space.md }}>
          {catalog.map((cat) => {
            const options = cat.symptoms.filter((s) => !tracked.includes(s.key));
            if (!options.length) return null;
            return (
              <View key={cat.key} style={{ gap: space.sm }}>
                <Text style={text.label}>{cat.label}</Text>
                <View style={styles.chips}>
                  {options.map((s) => (
                    <Pressable
                      key={s.key}
                      onPress={() => onTrack(s.key)}
                      accessibilityRole="button"
                      accessibilityLabel={`Track ${s.label}`}
                      style={styles.chip}
                    >
                      <Text style={styles.chipText}>+ {s.label}</Text>
                    </Pressable>
                  ))}
                </View>
              </View>
            );
          })}
          <Button label="Done adding" variant="ghost" onPress={() => setAdding(false)} />
        </View>
      ) : (
        <Button label="+ Add a symptom" variant="secondary" onPress={() => setAdding(true)} />
      )}

      <View style={styles.footer}>
        <Text style={[text.small, { flex: 1 }]}>
          {dirty ? `${filled} of ${tracked.length} rated · not saved` : savedAt ? `Saved at ${savedAt}` : ""}
        </Text>
        <Button label="Save check-in" onPress={onSave} busy={saving} disabled={!dirty || filled === 0} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  symptomHeader: { flexDirection: "row", alignItems: "center" },
  link: { color: colors.primary, fontSize: 14, fontWeight: "600" },
  input: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: space.md,
    minHeight: 60,
    fontSize: 15,
    color: colors.text,
    backgroundColor: colors.background,
    textAlignVertical: "top",
  },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: space.sm },
  chip: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.pill,
    paddingHorizontal: space.md,
    paddingVertical: space.sm,
    backgroundColor: colors.surface,
  },
  chipText: { fontSize: 14, color: colors.text },
  footer: {
    flexDirection: "row",
    alignItems: "center",
    gap: space.md,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    paddingTop: space.md,
  },
});
