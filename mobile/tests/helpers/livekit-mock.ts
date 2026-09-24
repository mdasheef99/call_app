/**
 * LiveKit stand-ins for Node regression tests (no real SDK ever loads).
 *
 * `voice.native.ts` imports livekit-client and @livekit/react-native at
 * module scope; this module intercepts Module._load so those packages
 * (and registerGlobals side effects) stay out of the test process while
 * the actual lifecycle code runs against fake rooms and events.
 *
 * Import this module BEFORE importing ../lib/voice.native so the patch
 * is installed when that module evaluates.
 */
import { Module } from "node:module";

type Listener = (...args: unknown[]) => void;

export const RoomEvent = {
  Connected: "connected",
  Reconnecting: "reconnecting",
  Reconnected: "reconnected",
  ParticipantConnected: "participantConnected",
  ParticipantDisconnected: "participantDisconnected",
  Disconnected: "disconnected",
} as const;

/** Shared ordered log: mic calls and status emissions, for ordering asserts. */
export const timeline: string[] = [];

export const audioSession = {
  configureCalls: 0,
  startCalls: 0,
  stopCalls: 0,
};

type ConnectHold = { used: boolean; markEntered: () => void; gate: Promise<void> };
type MicHold = { used: boolean; gate: Promise<void> };

export class FakeRoom {
  static last: FakeRoom | null = null;
  static holdConnect: ConnectHold | null = null;

  readonly remoteParticipants = new Map<string, unknown>();
  connectCalls = 0;
  disconnectCalls = 0;
  removeAllListenersCalls = 0;
  readonly micCalls: boolean[] = [];
  private readonly listeners = new Map<string, Set<Listener>>();
  private readonly micHolds = new Map<number, MicHold>();

  readonly localParticipant = {
    setMicrophoneEnabled: async (enabled: boolean): Promise<void> => {
      const call = this.micCalls.length + 1;
      this.micCalls.push(enabled);
      timeline.push(`mic:${String(enabled)}`);
      const hold = this.micHolds.get(call);
      if (hold && !hold.used) {
        hold.used = true;
        await hold.gate;
      }
    },
  };

  constructor() {
    FakeRoom.last = this;
  }

  static armHoldConnect(): { entered: Promise<void>; release: () => void } {
    let markEntered!: () => void;
    let release!: () => void;
    const entered = new Promise<void>((resolve) => {
      markEntered = resolve;
    });
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    FakeRoom.holdConnect = { used: false, markEntered, gate };
    return { entered, release };
  }

  /** Hold the next setMicrophoneEnabled call (1-based call number). */
  holdMicCall(call: number): { release: () => void } {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    this.micHolds.set(call, { used: false, gate });
    return { release };
  }

  on(event: string, listener: Listener): this {
    let set = this.listeners.get(event);
    if (!set) {
      set = new Set();
      this.listeners.set(event, set);
    }
    set.add(listener);
    return this;
  }

  emit(event: string, ...args: unknown[]): void {
    const set = this.listeners.get(event);
    if (!set) return;
    for (const listener of [...set]) listener(...args);
  }

  async connect(_serverUrl: string, _participantToken: string): Promise<void> {
    this.connectCalls += 1;
    const hold = FakeRoom.holdConnect;
    if (hold && !hold.used) {
      hold.used = true;
      hold.markEntered();
      await hold.gate;
    }
    this.emit(RoomEvent.Connected);
  }

  async disconnect(_closeOutputs?: boolean): Promise<void> {
    this.disconnectCalls += 1;
    // Real LiveKit emits Disconnected for a local disconnect too; the
    // lifecycle code must ignore it once its own teardown set `settled`.
    this.emit(RoomEvent.Disconnected);
  }

  removeAllListeners(): void {
    this.removeAllListenersCalls += 1;
    this.listeners.clear();
  }
}

const livekitClientMock = {
  Room: FakeRoom,
  RoomEvent,
  TokenSource: {
    developmentTokenServer(_tokenServerId: string) {
      return {
        fetch: async (_options: unknown) => ({
          serverUrl: "wss://example.invalid",
          participantToken: "development-token",
        }),
      };
    },
  },
};

const reactNativeMock = {
  registerGlobals: () => undefined,
  AudioSession: {
    configureAudio: async (_options: unknown) => {
      audioSession.configureCalls += 1;
    },
    startAudioSession: async () => {
      audioSession.startCalls += 1;
    },
    stopAudioSession: async () => {
      audioSession.stopCalls += 1;
    },
  },
  AndroidAudioTypePresets: { communication: {} },
};

type LoadFn = (request: string, parent: unknown, isMain: boolean) => unknown;
const moduleLoader = Module as unknown as { _load: LoadFn };
const originalLoad = moduleLoader._load;
moduleLoader._load = function (request: string, parent: unknown, isMain: boolean): unknown {
  if (request === "livekit-client") return livekitClientMock;
  if (request === "@livekit/react-native") return reactNativeMock;
  return originalLoad.call(this, request, parent, isMain);
};

// Development-only config so startVoiceTest passes the configured check.
// The value is a dummy: the mocked token source never validates it.
process.env.EXPO_PUBLIC_LIVEKIT_TOKEN_SERVER_ID = "test-token-server-id";

export function resetLiveKitMock(): void {
  FakeRoom.last = null;
  FakeRoom.holdConnect = null;
  audioSession.configureCalls = 0;
  audioSession.startCalls = 0;
  audioSession.stopCalls = 0;
  timeline.length = 0;
}

/** Drain chained microtasks/immediates started by cleanup paths. */
export function flush(): Promise<void> {
  return new Promise<void>((resolve) => {
    setImmediate(() => setImmediate(resolve));
  });
}
