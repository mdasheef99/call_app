import { useEffect, useRef, useState } from "react";
import { AppState, Pressable, StyleSheet, Text, View } from "react-native";
import * as Linking from "expo-linking";
import {
  getVoiceTestInitialStatus,
  startVoiceTest,
} from "../lib/voice";
import type { VoiceTestStatus } from "../lib/voice";
import { VoiceTestSession } from "../lib/voice-session";
import { VOICE_TEST_TOKEN_SERVER_ID_ENV } from "../lib/voice-config";

export default function VoiceTestScreen() {
  const [status, setStatus] = useState<VoiceTestStatus>(() => getVoiceTestInitialStatus());
  const [busy, setBusy] = useState(false);
  const sessionRef = useRef<VoiceTestSession | null>(null);
  const statusRef = useRef(status);
  statusRef.current = status;

  useEffect(() => {
    // Created on mount (not during render) so re-renders never orphan a
    // session. Disposal releases the mic/audio session; a Start that is
    // still pending is disposed when it completes.
    const session = new VoiceTestSession(
      {
        startVoiceTest,
        getAppState: () => AppState.currentState,
        addAppStateListener: (onChange) => {
          const subscription = AppState.addEventListener("change", onChange);
          return () => subscription.remove();
        },
      },
      setStatus
    );
    sessionRef.current = session;
    return () => {
      session.dispose();
      if (sessionRef.current === session) sessionRef.current = null;
    };
  }, []);

  const onStart = async () => {
    const session = sessionRef.current;
    if (!session || busy) return;
    setBusy(true);
    try {
      await session.start();
    } catch {
      // Terminal state (denied/error/needs-config) or a mute/end failure
      // was already reported through the status callback.
    } finally {
      setBusy(false);
    }
  };

  const onToggleMute = async () => {
    const session = sessionRef.current;
    if (!session || busy) return;
    setBusy(true);
    try {
      await session.setMuted(!statusRef.current.muted);
    } catch {
      // Failure stays visible through the status callback; the session
      // keeps running so the microphone state is never hidden.
    } finally {
      setBusy(false);
    }
  };

  const onEnd = async () => {
    // End never waits for Mute: it runs even while another op is pending.
    const session = sessionRef.current;
    if (!session) return;
    try {
      await session.end();
    } catch {
      // Teardown failure is reported through the status callback as
      // error (never a false "ended").
    }
  };

  const state = status.state;
  const active = state === "connected" || state === "reconnecting";
  const canStart = !busy && (state === "idle" || state === "ended" || state === "error" || state === "denied");

  return (
    <View style={styles.container}>
      <Text style={styles.title}>LiveKit Audio Test</Text>
      <Text style={styles.subtitle}>
        Development experiment only — microphone test, not a product call. No camera, no recording.
      </Text>

      <View style={styles.card}>
        <Text style={styles.row}>State: {describeState(state)}</Text>
        <Text style={styles.row}>Microphone: {status.muted ? "muted" : "live"}</Text>
        <Text style={styles.row}>Participants: {status.participantCount}</Text>
        {status.errorMessage ? <Text style={styles.error}>Error: {status.errorMessage}</Text> : null}
      </View>

      {state === "unsupported" ? (
        <Text style={styles.warning}>Not available in the web preview — use the Android development build.</Text>
      ) : null}

      {state === "needs-config" ? (
        <Text style={styles.warning}>
          Not configured. Set {VOICE_TEST_TOKEN_SERVER_ID_ENV} in mobile/.env (development-only token-server ID
          — never commit it, never use it for pilot builds), then reload. Tokens are minted on demand and expire
          after about 15 minutes.
        </Text>
      ) : null}

      {state === "denied" ? (
        <View style={styles.card}>
          <Text style={styles.row}>Microphone permission was denied, so no audio is sent.</Text>
          <Pressable style={styles.button} onPress={() => Linking.openSettings()}>
            <Text style={styles.buttonText}>Open system settings</Text>
          </Pressable>
        </View>
      ) : null}

      {canStart ? (
        <Pressable style={styles.button} onPress={onStart}>
          <Text style={styles.buttonText}>Start audio test</Text>
        </Pressable>
      ) : null}

      {active ? (
        <View style={styles.rowButtons}>
          <Pressable style={styles.button} onPress={onToggleMute}>
            <Text style={styles.buttonText}>{status.muted ? "Unmute" : "Mute"}</Text>
          </Pressable>
          <Pressable style={styles.button} onPress={onEnd}>
            <Text style={styles.buttonText}>End</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

function describeState(state: VoiceTestStatus["state"]): string {
  switch (state) {
    case "unsupported":
      return "unsupported (web preview)";
    case "needs-config":
      return "needs configuration";
    case "idle":
      return "idle";
    case "requesting":
      return "requesting microphone…";
    case "connecting":
      return "connecting…";
    case "connected":
      return "connected";
    case "reconnecting":
      return "reconnecting…";
    case "denied":
      return "microphone denied";
    case "error":
      return "error";
    case "ended":
      return "ended";
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, gap: 12, justifyContent: "center" },
  title: { fontSize: 24, fontWeight: "700" },
  subtitle: { fontSize: 14, opacity: 0.7 },
  card: { borderWidth: 1, borderRadius: 8, padding: 12, gap: 4 },
  row: { fontSize: 14 },
  rowButtons: { flexDirection: "row", gap: 12 },
  button: {
    backgroundColor: "#111",
    borderRadius: 8,
    padding: 12,
    alignItems: "center",
    flex: 1,
  },
  buttonText: { color: "#fff", fontWeight: "600" },
  warning: { fontSize: 12, opacity: 0.7 },
  error: { fontSize: 14, color: "#a00" },
});
