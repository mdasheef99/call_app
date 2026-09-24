/**
 * Regression tests for the actual native audio-test lifecycle
 * (`lib/voice.native.ts`) driven by mocked LiveKit room events.
 *
 * Covers the unexpected-disconnect corrections: cleanup after a remote
 * disconnect, disconnect during Start, exactly-once teardown under
 * concurrent End / Mute-in-flight races, truthful participant count
 * before connection, and connected/"live" only after mic publish.
 */
import "./helpers/livekit-mock";
import test from "node:test";
import assert from "node:assert/strict";
import {
  FakeRoom,
  RoomEvent,
  audioSession,
  flush,
  resetLiveKitMock,
  timeline,
} from "./helpers/livekit-mock";
import { startVoiceTest } from "../lib/voice.native";
import type { VoiceTestStatus } from "../lib/voice";

function collect() {
  const statuses: VoiceTestStatus[] = [];
  return {
    statuses,
    push: (status: VoiceTestStatus) => {
      statuses.push(status);
      timeline.push(`status:${status.state}`);
    },
    last: () => statuses[statuses.length - 1],
  };
}

test("unexpected disconnect after connection releases resources and reports error, not ended", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");
  assert.equal(rec.last()?.state, "connected");

  const stopsBefore = audioSession.stopCalls;
  const removesBefore = room.removeAllListenersCalls;
  room.emit(RoomEvent.Disconnected);
  await flush();

  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.equal(last?.participantCount, 0);
  assert.equal(room.micCalls[room.micCalls.length - 1], false, "mic disabled on cleanup");
  assert.equal(audioSession.stopCalls, stopsBefore + 1, "audio session stopped on cleanup");
  assert.ok(room.removeAllListenersCalls > removesBefore, "listeners removed on cleanup");
  assert.ok(room.disconnectCalls >= 1, "room disconnect attempted on cleanup");

  // End after an unexpected disconnect must not fake "ended" or re-clean.
  await handle.end();
  await flush();
  assert.equal(rec.last()?.state, "error", "error status survives End");
  assert.equal(audioSession.stopCalls, stopsBefore + 1, "cleanup ran exactly once");
  assert.equal(room.removeAllListenersCalls, removesBefore + 1, "listeners removed exactly once");
});

test("connected status (and live mic display) appears only after mic publish", async () => {
  resetLiveKitMock();
  const rec = collect();
  await startVoiceTest(rec.push);
  assert.ok(
    timeline.indexOf("mic:true") < timeline.indexOf("status:connected"),
    `expected mic publish before connected status, got: ${timeline.join(" -> ")}`
  );
  const prePublish = rec.statuses.filter(
    (s) => s.state === "requesting" || s.state === "connecting"
  );
  assert.ok(prePublish.length >= 2, "requesting/connecting observed before connected");
});

test("disconnect during Start rejects instead of returning a successful handle", async () => {
  resetLiveKitMock();
  const rec = collect();
  const hold = FakeRoom.armHoldConnect();
  const startPromise = startVoiceTest(rec.push);
  await hold.entered;
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded before connect");
  room.emit(RoomEvent.Disconnected);
  await flush();
  hold.release();
  await assert.rejects(startPromise, /Disconnected unexpectedly/);
  await flush();

  const last = rec.last();
  assert.equal(last?.state, "error");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.ok(audioSession.stopCalls >= 1, "audio session stopped");
  assert.ok(room.removeAllListenersCalls >= 1, "listeners removed");
  assert.ok(!room.micCalls.includes(true), "microphone never published");

  // Truthful counts before connection: no room during token mint/setup.
  const requesting = rec.statuses.find((s) => s.state === "requesting");
  const connecting = rec.statuses.find((s) => s.state === "connecting");
  assert.equal(requesting?.participantCount, 0, "participantCount 0 while requesting");
  assert.equal(connecting?.participantCount, 0, "participantCount 0 while connecting pre-room");
});

test("concurrent and repeated Ends run teardown exactly once", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  await Promise.all([handle.end(), handle.end()]);
  await handle.end();
  await flush();

  assert.equal(rec.last()?.state, "ended");
  assert.equal(audioSession.stopCalls, 1, "audio session stopped exactly once");
  assert.equal(room.disconnectCalls, 1, "room disconnected exactly once");
  assert.equal(room.removeAllListenersCalls, 1, "listeners removed exactly once");
  assert.equal(
    room.micCalls.filter((enabled) => enabled === false).length,
    1,
    "mic disabled exactly once"
  );
});

test("End racing an in-flight Mute reports honestly and cleans once", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  // Call 1 = publish; call 2 = the mute toggle (held); call 3 = teardown.
  const hold = room.holdMicCall(2);
  const mutePromise = handle.setMuted(true);
  await flush();
  await handle.end();
  await flush();
  hold.release();
  await assert.rejects(mutePromise, /Session ended while changing mute/);
  await flush();

  assert.equal(rec.last()?.state, "ended", "End's terminal state stands");
  assert.equal(audioSession.stopCalls, 1, "cleanup ran once despite the mute race");
});

test("End waits for an in-flight unexpected-disconnect cleanup", async () => {
  resetLiveKitMock();
  const rec = collect();
  const handle = await startVoiceTest(rec.push);
  const room = FakeRoom.last;
  assert.ok(room, "room instance recorded");

  // Call 1 = publish; call 2 = the cleanup's mic release (held), so the
  // unexpected-disconnect cleanup stalls in flight right after `settled`.
  const hold = room.holdMicCall(2);
  room.emit(RoomEvent.Disconnected);
  await flush();
  assert.equal(audioSession.stopCalls, 0, "cleanup still in flight at the mic release");

  let endSettled = false;
  const endPromise = handle.end().then(() => {
    endSettled = true;
  });
  await flush();
  assert.equal(endSettled, false, "End must wait until in-flight cleanup finishes");

  hold.release();
  await endPromise;
  await flush();
  assert.equal(endSettled, true, "End resolves after cleanup completes");

  const last = rec.last();
  assert.equal(last?.state, "error", "terminal status is error, never a false ended");
  assert.equal(last?.errorMessage, "Disconnected unexpectedly.");
  assert.ok(
    !rec.statuses.some((s) => s.state === "ended"),
    "no ended status is ever emitted after an unexpected disconnect"
  );
  assert.equal(
    room.micCalls.filter((enabled) => enabled === false).length,
    1,
    "mic released exactly once"
  );
  assert.equal(audioSession.stopCalls, 1, "audio session stopped exactly once");
  assert.equal(room.removeAllListenersCalls, 1, "listeners removed exactly once");
});
