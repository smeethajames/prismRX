import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";

import { colors, radius, space } from "@/theme";

type Variant = "primary" | "secondary" | "ghost";

export function Button({
  label,
  onPress,
  variant = "primary",
  disabled,
  busy,
  accessibilityLabel,
}: {
  label: string;
  onPress: () => void;
  variant?: Variant;
  disabled?: boolean;
  busy?: boolean;
  accessibilityLabel?: string;
}) {
  const inactive = disabled || busy;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      accessibilityRole="button"
      accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: !!inactive, busy: !!busy }}
      hitSlop={6}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        inactive && styles.disabled,
        pressed && !inactive && { opacity: 0.75 },
      ]}
    >
      {busy ? (
        <ActivityIndicator size="small" color={variant === "primary" ? colors.primaryText : colors.primary} />
      ) : (
        <Text style={[styles.label, variant === "primary" ? styles.labelPrimary : styles.labelOther]}>{label}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 40,
    paddingHorizontal: space.md,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  primary: { backgroundColor: colors.primary },
  secondary: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border },
  ghost: { backgroundColor: "transparent" },
  disabled: { opacity: 0.45 },
  label: { fontSize: 15, fontWeight: "600" },
  labelPrimary: { color: colors.primaryText },
  labelOther: { color: colors.primary },
});
