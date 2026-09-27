/**
 * Web-bundle boundary: the web preview must never inline the
 * development token-server ID.
 *
 * `lib/voice-config.ts` reads `process.env.EXPO_PUBLIC_*`, which Metro
 * inlines by value at bundle time — so any web-reachable import of it
 * would bake the real ID into the web output. The web screen therefore
 * keeps its own display-only copy of the variable NAME and never
 * imports the env-bearing module; web/shared modules never import
 * native-only LiveKit packages either.
 */
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

function srcOf(...parts: string[]): string {
  return fs.readFileSync(path.join(__dirname, "..", "..", ...parts), "utf-8");
}

test("web screen has no import path to the env-bearing token-server config", () => {
  const src = srcOf("app", "voice-test.tsx");
  assert.ok(
    !src.includes("voice-config"),
    "voice-test.tsx must not import ../lib/voice-config (Metro would inline the token-server ID value into the web bundle)"
  );
  assert.ok(
    !src.includes("process.env"),
    "voice-test.tsx must not read process.env (values inline into the web bundle)"
  );
});

test("web/shared modules never import native-only LiveKit packages", () => {
  // Match single-line import statements (including semicolon-terminated
  // and side-effect forms); a separate whole-text check below covers
  // multiline imports whose module clause sits on a later line.
  // Comments may name the modules to explain the boundary (as
  // lib/voice.ts does), so only import statements are matched.
  const importLineRe = /^\s*import\b.*$/gm;
  const forbidden = ["livekit-client", "@livekit/react-native", "react-native-webrtc"];
  const fromRe = (mod: string) =>
    new RegExp(`from\\s+["']${mod.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}["']`);
  for (const file of ["lib/voice.ts", "lib/voice.web.ts", "lib/voice-session.ts", "lib/voice-session-base.ts", "lib/voice-session-start.ts", "lib/voice-shared-gate.ts"]) {
    const src = srcOf(...file.split("/"));
    const imports = src.match(importLineRe) ?? [];
    for (const line of imports) {
      for (const mod of forbidden) {
        assert.ok(!line.includes(mod), `${file} must not import ${mod}: ${line}`);
      }
    }
    for (const mod of forbidden) {
      assert.ok(!fromRe(mod).test(src), `${file} must not import ${mod} (including multiline)`);
    }
  }
});

test("web platform module never touches the env-bearing config", () => {
  const src = srcOf("lib", "voice.web.ts");
  assert.ok(!src.includes("voice-config"), "voice.web.ts must not import voice-config");
  assert.ok(!src.includes("process.env"), "voice.web.ts must not read process.env");
});

test("import scanner detects semicolon-terminated, multiline, and side-effect forbidden imports", () => {
  // Probe the scanner's pattern against synthetic forbidden imports: each
  // form must be detected without editing any source file. Mirrors the
  // guard above (line scan plus whole-text from-clause check).
  const importLineRe = /^\s*import\b.*$/gm;
  const forbidden = ["livekit-client", "@livekit/react-native", "react-native-webrtc"];
  const escaped = (mod: string) => mod.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const detected = (sample: string) => {
    const lines = sample.match(importLineRe) ?? [];
    if (lines.some((line) => forbidden.some((mod) => line.includes(mod)))) return true;
    return forbidden.some((mod) => new RegExp(`from\\s+["']${escaped(mod)}["']`).test(sample));
  };
  const samples = [
    `import { Room } from "livekit-client";`,
    `import {\n  Room\n} from "livekit-client";`,
    `import "livekit-client";`,
    `import "@livekit/react-native";`,
    `import { AudioSession } from "react-native-webrtc";`,
  ];
  for (const sample of samples) {
    assert.ok(detected(sample), `scanner must detect: ${JSON.stringify(sample)}`);
  }
});
