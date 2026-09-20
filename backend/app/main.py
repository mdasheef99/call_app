"""Minimal FastAPI foundation for Voice Thinking Partner prototype.

Scope: health + status only. No auth, DB, voice, memory, or analytics yet.
"""

from datetime import datetime, timezone
import platform
import sys

from fastapi import FastAPI

APP_NAME = "voice-thinking-partner-api"
APP_VERSION = "0.0.1-foundation"

app = FastAPI(title=APP_NAME, version=APP_VERSION)


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
