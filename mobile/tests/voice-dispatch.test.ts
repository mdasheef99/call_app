/**
 * Explicit named dispatch: tapping Start is the ONLY path that requests
 * an agent. The token fetch must carry the exact agent name the dev
 * worker accepts (backend/voice_agent_dev.py AGENT_NAME); the
 * needs-config path must never reach the token server at all.
 */
import "./helpers/livekit-mock";
import test from "node:test";
import assert from "node:assert/strict";
import {
  fetchCalls,
  lastFetchOptions,
  resetLiveKitMock,
} from "./helpers/livekit-mock";
import { VOICE_AGENT_NAME } from "../lib/voice-config";
import { startVoiceTest } from "../lib/voice.native";
import fs from "node:fs";
import path from "node:path";

test("dispatch contract: agent name matches the dev worker", () => {
  assert.equal(VOICE_AGENT_NAME, "think-partner-dev");
});

test("Start requests exactly one named dispatch", async () => {
  resetLiveKitMock();
  const seen: string[] = [];
  const handle = await startVoiceTest((s) => {
    seen.push(s.state);
  });
  assert.equal(fetchCalls, 1);
  assert.equal(lastFetchOptions?.["agentName"], "think-partner-dev");
  assert.equal(lastFetchOptions?.["participantName"], "voice-spike");
  assert.ok(seen.includes("connected"));
  await handle.end();
});

test("needs-config never touches the token server", async () => {
  resetLiveKitMock();
  const saved = process.env.EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID;
  delete process.env.EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID;
  try {
    await assert.rejects(() => startVoiceTest(() => undefined));
  } finally {
    process.env.EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID = saved;
  }
  assert.equal(fetchCalls, 0);
  assert.equal(lastFetchOptions, null);
});

test("config uses static Expo env reference for packaged bundles", () => {
  const candidates = [
    path.join(__dirname, "..", "lib", "voice-config.js"),
    path.join(__dirname, "..", "..", "lib", "voice-config.ts"),
  ];
  const found = candidates.find((p) => fs.existsSync(p));
  assert.ok(found, "voice-config source found");
  const src = fs.readFileSync(found!, "utf-8");
  assert.ok(
    src.includes("process.env.EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID"),
    "must use dot-notation for Metro inlining"
  );
});
