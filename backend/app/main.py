"""Minimal FastAPI foundation for Voice Thinking Partner prototype.

Scope: health + status only. No auth, DB, voice, memory, or analytics yet.
"""

from datetime import datetime, timezone
import platform
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

APP_NAME = "voice-thinking-partner-api"
APP_VERSION = "0.0.1-foundation"

# Local web-preview origins only (Expo `npx expo start --web` defaults).
# Phone/dev-build traffic goes through the FastAPI host directly, not a
# browser, so no wildcard is used here.
LOCAL_PREVIEW_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]

app = FastAPI(title=APP_NAME, version=APP_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_PREVIEW_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe used by tests and the mobile web preview."""
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
    }


@app.get("/v1/status")
def status() -> dict:
    """Meaningful foundation endpoint: build/runtime info, no business logic yet."""
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "scope": "foundation-only",
        "voice_enabled": False,
        "database_enabled": False,
        "auth_enabled": False,
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "runtime": sys.version.split(" ")[0],
    }
