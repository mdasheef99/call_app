/**
 * Microphone display contract: `describeMicrophone` reports live/muted
 * only in connected/reconnecting and off everywhere else, identically
 * in the shared contract and the native/web platform mirrors.
 */
import "./helpers/livekit-mock";
import test from "node:test";
import assert from "node:assert/strict";
import { describeMicrophone, type VoiceTestState, type VoiceTestStatus } from "../lib/voice";
import { describeMicrophone as describeNative } from "../lib/voice.native";
import { describeMicrophone as describeWeb } from "../lib/voice.web";

const states: VoiceTestState[] = [
  "unsupported",
  "needs-config",
  "idle",
  "requesting",
  "connecting",
  "connected",
  "reconnecting",
  "denied",
  "error",
  "ended",
];

function status(state: VoiceTestState, muted: boolean): VoiceTestStatus {
  return { state, muted, participantCount: 0, errorMessage: null };
}

test("microphone label: live/muted only when connected or reconnecting", () => {
  for (const state of states) {
    const publishing = state === "connected" || state === "reconnecting";
    assert.equal(
      describeMicrophone(status(state, false)),
      publishing ? "live" : "off",
      `${state}, not muted`
    );
    assert.equal(
      describeMicrophone(status(state, true)),
      publishing ? "muted" : "off",
      `${state}, muted`
    );
  }
});

test("native and web mirrors agree with the shared contract", () => {
  for (const state of states) {
    for (const muted of [false, true]) {
      const value = status(state, muted);
      assert.equal(describeNative(value), describeMicrophone(value), `native ${state}`);
      assert.equal(describeWeb(value), describeMicrophone(value), `web ${state}`);
    }
  }
});
