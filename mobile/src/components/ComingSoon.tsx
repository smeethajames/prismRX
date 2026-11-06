import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, space, text } from "@/theme";

export function ComingSoon({ title, body }: { title: string; body: string }) {
  return (
    <SafeAreaView style={styles.root} edges={["top"]}>
      <View style={styles.inner}>
        <Text style={text.title}>{title}</Text>
        <Text style={[text.body, { color: colors.textSecondary, marginTop: space.sm }]}>{body}</Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  inner: { padding: space.lg },
});
