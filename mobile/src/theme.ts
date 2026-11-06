// Placeholder design tokens. Swap in the real design system when UX design lands.
export const colors = {
  background: "#f6f5f2",
  surface: "#ffffff",
  border: "#e4e3df",
  text: "#0b0b0b",
  textSecondary: "#52514e",
  textMuted: "#7a7975",
  primary: "#2a78d6",
  primaryText: "#ffffff",
  primarySoft: "#e3eefb",
  // Status colors always appear with a text label, never color alone.
  good: "#0f7b3f",
  goodSoft: "#e2f4e9",
  warning: "#9a5b00",
  warningSoft: "#fdf1dc",
  critical: "#b42318",
  criticalSoft: "#fde8e6",
  neutralSoft: "#efeeea",
};

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24 };
export const radius = { sm: 6, md: 10, lg: 14, pill: 999 };
export const text = {
  title: { fontSize: 26, fontWeight: "700" as const, color: colors.text },
  heading: { fontSize: 18, fontWeight: "700" as const, color: colors.text },
  body: { fontSize: 15, color: colors.text },
  label: { fontSize: 13, color: colors.textSecondary },
  small: { fontSize: 12, color: colors.textMuted },
};
