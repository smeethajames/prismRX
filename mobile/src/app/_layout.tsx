import { Tabs } from "expo-router";
import { StatusBar } from "expo-status-bar";

import { colors } from "@/theme";

export default function RootLayout() {
  return (
    <>
      <StatusBar style="dark" />
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.primary,
          tabBarInactiveTintColor: colors.textSecondary,
          tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
          tabBarIconStyle: { display: "none" }, // text-only tabs until icons are designed
          tabBarLabelStyle: { fontSize: 14, fontWeight: "600" },
        }}
      >
        <Tabs.Screen name="index" options={{ title: "Today" }} />
        <Tabs.Screen name="trends" options={{ title: "Trends" }} />
        <Tabs.Screen name="report" options={{ title: "Report" }} />
      </Tabs>
    </>
  );
}
