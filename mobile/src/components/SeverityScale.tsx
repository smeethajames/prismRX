import { Pressable, StyleSheet, Text, View } from "react-native";

import { colors, radius, space } from "@/theme";

const LEVELS = Array.from({ length: 11 }, (_, i) => i);

/** 0-10 severity picker. Tapping the selected value again clears it. */
export function SeverityScale({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number | null;
  onChange: (v: number | null) => void;
}) {
  return (
    <View accessibilityRole="radiogroup" accessibilityLabel={`${label} severity, 0 to 10`}>
      <View style={styles.row}>
        {LEVELS.map((n) => {
          const selected = value === n;
          return (
            <Pressable
              key={n}
              onPress={() => onChange(selected ? null : n)}
              accessibilityRole="radio"
              accessibilityState={{ selected }}
              accessibilityLabel={`${label} ${n}`}
              style={[styles.cell, selected && styles.cellSelected]}
            >
              <Text style={[styles.num, selected && styles.numSelected]}>{n}</Text>
            </Pressable>
          );
        })}
      </View>
      <View style={styles.ends}>
        <Text style={styles.endLabel}>None</Text>
        <Text style={styles.endLabel}>Worst</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: 3 },
  cell: {
    flex: 1,
    minHeight: 36,
    borderRadius: radius.sm,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surface,
  },
  cellSelected: { backgroundColor: colors.primary, borderColor: colors.primary },
  num: { fontSize: 14, fontWeight: "600", color: colors.textSecondary },
  numSelected: { color: colors.primaryText },
  ends: { flexDirection: "row", justifyContent: "space-between", marginTop: space.xs },
  endLabel: { fontSize: 11, color: colors.textMuted },
});
