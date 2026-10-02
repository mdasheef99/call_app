"""Development-only one-human-to-one-AI voice agent (review draft, NOT live).

Scope: a minimal LiveKit Agents (1.2.12) worker for a separately approved,
short, owner-run phone trial. One human talks to one AI in a fresh room
per Start. No second human, no group calling, no camera, no recording.

How it starts (explicit dispatch only): the phone's audio-test screen
passes ``agentName=AGENT_NAME`` in its development-token fetch when the
owner taps Start. The token server embeds a named room dispatch, so this
worker joins that room and no other. Nothing auto-starts: with no
dispatch there is no job, and the worker idles.

Privacy disables verified against livekit-agents 1.2.12 (see tests):
- No recording calls anywhere in this file (audio, transcript,
  trace, and log uploads stay off by never invoking them).
- ``transcription_enabled=False, sync_transcription=False`` so no
  transcript text is forwarded to room participants.
- Telemetry stays in-process (no tracer provider or exporter configured).
- Logging uses stdlib-style ``agents.log.logger`` with identifiers and
  error text only — never conversation content (spec P12).

Model: Google Gemini Live (realtime speech-to-speech) via the
``livekit-plugins-google`` realtime model, imported lazily so this module
imports and unit-tests WITHOUT the plugin installed. Trial additionally
needs (separate approvals, never committed): installing
'livekit-plugins-google==1.2.9' (exact pin reviewed against the 1.2.9
wheel source),
a ``GOOGLE_API_KEY``, and worker credentials (``LIVEKIT_URL``,
``LIVEKIT_API_KEY``, ``LIVEKIT_API_SECRET``) in the trial shell only.

Run (trial only, owner approval required):
    python voice_agent_dev.py dev
"""

from __future__ import annotations

import asyncio  # Existing dev-module access; lifecycle shares this module object.
import logging
import os

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RoomInputOptions,
    RoomOutputOptions,
    WorkerOptions,
    cli,
)
from livekit.agents.types import APIConnectOptions

from voice_connection_guard import allow_single_provider_connection
from voice_provider_bootstrap import (
    ensure_google_plugin_initialized,
    is_google_plugin_registered,
)

from voice_trial_config import (
    AGENT_NAME, AGENT_INSTRUCTIONS, GOOGLE_API_KEY_ENV, CALL_TIME_LIMIT_S, CLEANUP_TIMEOUT_S,
)
from voice_trial_cleanup import _delete_trial_room  # Preserve the existing dev-module export.
from voice_trial_lifecycle import run_trial

logger = logging.getLogger("think-partner-dev")

# Spec candidate, confirmed: Google changelog 2026-09-15 lists
# 'Gemini 3.8 Live (gemini-3.8-live)' as GA — the default option for
# low-latency voice-agent dialogue — with model page
# ai.google.dev/gemini-api/docs/models/gemini-3.8-live.
# Source/API-level support in the pinned livekit-plugins-google==1.2.9
# verified from the 1.2.9 wheel itself (model is a free string passed
# through to the Live API). RUNTIME compatibility (server acceptance
# via the 1.2.9-era google-genai SDK) remains UNPROVEN without a live
# call — do not claim it works until the phone trial.
REALTIME_MODEL_ID = "gemini-3.8-live"
REALTIME_VOICE = "Puck"

def check_trial_prerequisites() -> None:
    """Refuse to join any room when provider configuration is missing.

    Runs BEFORE ``ctx.connect()`` so a misconfigured trial never
    appears in a room. Names only what is missing (plugin package
    and/or env-var name) — never values.

    Importability is deliberately not enough: a Google plugin import
    that fails off the main thread (the pinned SDK's
    ``Plugin.register_plugin`` raises there) still leaves the
    ``beta.realtime`` submodule cached, so a later import "succeeds"
    while nothing is registered. The registration check is what keeps
    that state from admitting a job.
    """
    missing = []
    try:
        # Same from-import shape as build_realtime_model below, so the
        # check and the construction agree (a from-import always
        # consults the parent package, unlike a bare submodule lookup).
        from livekit.plugins.google.beta import realtime as _realtime_check  # noqa: F401
    except ImportError:
        missing.append("livekit-plugins-google (1.2.x line)")
    else:
        if not is_google_plugin_registered():
            missing.append(
                "livekit-plugins-google registered on the main thread "
                "(start the worker as `python voice_agent_dev.py dev`)"
            )
    if not os.environ.get(GOOGLE_API_KEY_ENV):
        missing.append(GOOGLE_API_KEY_ENV)
    if missing:
        raise RuntimeError(
            "Trial prerequisite missing: "
            + "; ".join(missing)
            + " — refusing to join a room."
        )


def build_realtime_model():
    """Construct the Gemini Live realtime model (lazy plugin import).

    Raises RuntimeError naming exactly what is missing (plugin package
    and/or env var name). Never prints secret values.

    Import path note: in the pinned livekit-plugins-google==1.2.9 the
    realtime model lives under the ``beta`` namespace (verified from
    the 1.2.9 wheel: ``livekit/plugins/google/beta/realtime/``). The
    top-level ``livekit.plugins.google.realtime`` path belongs to newer
    plugin releases — do not use it with this pin.

    Instructions note: the model receives AGENT_INSTRUCTIONS (the same
    text as the Agent). The installed 1.2.9 RealtimeModel signature
    accepts an ``instructions`` keyword (verified via inspect against
    the installed wheel); server acceptance of ``gemini-3.8-live``
    still needs the live trial.
    """
    try:
        from livekit.plugins.google.beta import realtime as google_realtime
    except ImportError as exc:
        raise RuntimeError(
            "Trial prerequisite missing: install 'livekit-plugins-google' "
            "(1.2.x line, separate approval) — no realtime plugin is "
            "installed in this environment."
        ) from exc
    if not os.environ.get(GOOGLE_API_KEY_ENV):
        raise RuntimeError(
            "Trial prerequisite missing: set the "
            f"{GOOGLE_API_KEY_ENV} environment variable in the trial shell "
            "(dev-only key, never committed)."
        )
    return allow_single_provider_connection(
        google_realtime.RealtimeModel(
            model=REALTIME_MODEL_ID,
            voice=REALTIME_VOICE,
            instructions=AGENT_INSTRUCTIONS,
            # First of the two no-automatic-retry guards: the pinned
            # SDK consults this only when a connection attempt RAISES.
            conn_options=APIConnectOptions(max_retry=0),
        )
    )


def build_room_input_options() -> RoomInputOptions:
    """Human audio in, nothing else. Video and text off; End cleans everything.

    Single deletion owner: ``delete_room_on_close`` stays False so the
    SDK never queues its own un-awaited delete on session close; the
    entrypoint awaits the one explicit ``ctx.delete_room()`` instead.
    """
    return RoomInputOptions(
        audio_enabled=True,
        video_enabled=False,
        text_enabled=False,
        close_on_disconnect=True,
        delete_room_on_close=False,
    )


def build_room_output_options() -> RoomOutputOptions:
    """AI audio out. Transcripts never forwarded to the room."""
    return RoomOutputOptions(
        audio_enabled=True,
        transcription_enabled=False,
        sync_transcription=False,
    )


async def entrypoint(ctx: JobContext, *, time_limit_s: float = CALL_TIME_LIMIT_S) -> None:
    """Native factory bindings; lifecycle owns ordering, end and cleanup.

    Resolve bindings at call time, retaining the existing dev entrypoint and native
    configuration. No cascade imports or change to the reviewed native wrappers.
    """
    await run_trial(
        ctx,
        check_prerequisites=check_trial_prerequisites,
        build_session=lambda: AgentSession(llm=build_realtime_model()),
        build_agent=lambda: Agent(instructions=AGENT_INSTRUCTIONS),
        build_room_input_options=build_room_input_options,
        build_room_output_options=build_room_output_options,
        time_limit_s=time_limit_s,
        cleanup_timeout_s=CLEANUP_TIMEOUT_S,
    )

def build_worker_options() -> WorkerOptions:
    """Named worker for explicit dispatch only.

    No concurrency limit is claimed here: LiveKit ``load_threshold``
    is a CPU-load availability signal, not a single-job admission
    mechanism, so this worker leaves it at the SDK default.
    """
    return WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name=AGENT_NAME,
    )


if __name__ == "__main__":
    # Main-thread plugin import before any job thread starts: on
    # Windows jobs run on threads where registration raises, so a
    # lazy per-job import would fail the first job and poison the
    # import cache for later ones. The result decides what the worker
    # logs, and admission itself is enforced per job by
    # check_trial_prerequisites(), so a plugin-absent environment
    # still starts and every job refuses before connect.
    if ensure_google_plugin_initialized():
        logger.info("google plugin registered on the main thread")
    else:
        logger.warning(
            "google plugin not ready; trial jobs will refuse before connect"
        )
    cli.run_app(build_worker_options(), hot_reload=False)
