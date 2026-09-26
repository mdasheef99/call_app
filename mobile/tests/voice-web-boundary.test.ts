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
  // Match import statements only: comments may name the modules to
  // explain the boundary (as lib/voice.ts does).
  const importRe = /^\s*import\s+[^;]*$/gm;
  for (const file of ["lib/voice.ts", "lib/voice.web.ts", "lib/voice-session.ts"]) {
    const src = srcOf(...file.split("/"));
    const imports = src.match(importRe) ?? [];
    for (const line of imports) {
      assert.ok(!line.includes("livekit-client"), `${file} must not import livekit-client: ${line}`);
      assert.ok(!line.includes("@livekit/react-native"), `${file} must not import @livekit/react-native: ${line}`);
      assert.ok(!line.includes("react-native-webrtc"), `${file} must not import react-native-webrtc: ${line}`);
    }
  }
});

test("web platform module never touches the env-bearing config", () => {
  const src = srcOf("lib", "voice.web.ts");
  assert.ok(!src.includes("voice-config"), "voice.web.ts must not import voice-config");
  assert.ok(!src.includes("process.env"), "voice.web.ts must not read process.env");
});
