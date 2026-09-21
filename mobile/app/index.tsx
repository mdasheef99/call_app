import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import Constants from "expo-constants";
import { getVoiceBackendStatus } from "../lib/voice";

const API_URL =
  process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

type CallSimState = "idle" | "simulated-active";

export default function HomeScreen() {
  const [apiHealth, setApiHealth] = useState<string>("checking…");
  const [callSim, setCallSim] = useState<CallSimState>("idle");
  const voice = getVoiceBackendStatus();

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/health`)
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((j) => {
        if (!cancelled) setApiHealth(`ok (${j.version ?? "unknown"})`);
      })
      .catch(() => {
        if (!cancelled) setApiHealth("unreachable (start backend first)");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <View style={styles.container}>
      <StatusBar style="auto" />
      <Text style={styles.title}>Voice Thinking Partner</Text>
      <Text style={styles.subtitle}>Foundation milestone — UI shell only</Text>

      <View style={styles.card}>
        <Text style={styles.row}>Backend: {apiHealth}</Text>
        <Text style={styles.row}>API URL: {API_URL}</Text>
        <Text style={styles.row}>Voice: {voice}</Text>
        <Text style={styles.row}>
          App: {Constants.expoConfig?.version ?? "0.0.1"}
        </Text>
      </View>

      <Pressable
        style={styles.button}
        onPress={() =>
          setCallSim((s) => (s === "idle" ? "simulated-active" : "idle"))
        }
      >
        <Text style={styles.buttonText}>
          {callSim === "idle" ? "Start simulated call" : "End simulated call"}
        </Text>
      </Pressable>
      <Text style={styles.warning}>
        {callSim === "idle"
          ? "SIMULATED UI ONLY — no microphone, no voice connection."
          : "SIMULATED CALL ACTIVE (UI state only) — no audio is sent or received."}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 12, justifyContent: "center" },
  title: { fontSize: 24, fontWeight: "700" },
  subtitle: { fontSize: 14, opacity: 0.7 },
  card: { borderWidth: 1, borderRadius: 8, padding: 12, gap: 4 },
  row: { fontSize: 14 },
  button: {
    backgroundColor: "#111",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
  },
  buttonText: { color: "#fff", fontWeight: "600" },
  warning: { fontSize: 12, opacity: 0.7 },
});
