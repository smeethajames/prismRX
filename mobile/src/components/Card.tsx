import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { colors, radius, space, text } from "@/theme";

export function Card({ title, aside, children }: { title: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={text.heading} accessibilityRole="header">
          {title}
        </Text>
        {aside}
      </View>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.lg,
    borderWidth: 1,
    borderColor: colors.border,
    padding: space.lg,
    gap: space.md,
  },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
});
