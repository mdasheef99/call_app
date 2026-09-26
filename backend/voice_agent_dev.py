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

import asyncio
import inspect
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

logger = logging.getLogger("think-partner-dev")

# Must match VOICE_AGENT_NAME in mobile/lib/voice-config.ts. The phone
# requests this exact name in its token fetch; the worker only accepts
# jobs dispatched to it.
AGENT_NAME = "think-partner-dev"

# Spec v1: one AI voice — warm, concise, curious, willing to challenge
# assumptions. Voice-only meeting-prep partner; no camera, no actions.
# Single instruction source: both the Agent and the realtime model use
# this text (spec: Indian English/Hinglish, interruption-friendly,
# uncertainty preserved for names/numbers).
AGENT_INSTRUCTIONS = (
    "You are a thinking partner for preparing customer meetings. "
    "Be warm, concise, and curious, and willing to challenge assumptions. "
    "Understand and respond in Indian English/Hinglish. "
    "Keep replies short enough to interrupt. "
    "If a name or number is unclear, say so instead of guessing. "
    "This is a voice-only test call: no camera, no actions, no recap."
)

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

GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"

# Development call-duration bound for the later <=2-minute trial.
# Active-job deadline covering setup awaits (connect, session start)
# and the post-start wait: slow awaits are interrupted via
# asyncio.timeout so the active job stays bounded even if the phone
# never Ends. Synchronous model construction is NOT preemptible by
# asyncio.timeout — it runs to completion once started (a fast local
# constructor: import plus object creation, no I/O), with its elapsed
# time still counting against the deadline at the next await. Bounded
# cleanup runs outside the deadline (see CLEANUP_TIMEOUT_S), so total
# wall-clock can exceed CALL_TIME_LIMIT_S; neither step proves phone
# mic release, which needs the live trial.
CALL_TIME_LIMIT_S = 120.0

# Bounded cleanup budget for each awaited step (session close, room
# deletion). Keeps a hanging provider/SDK call from hanging the job.
CLEANUP_TIMEOUT_S = 10.0


def check_trial_prerequisites() -> None:
    """Refuse to join any room when provider configuration is missing.

    Runs BEFORE ``ctx.connect()`` so a misconfigured trial never
    appears in a room. Names only what is missing (plugin package
    and/or env-var name) — never values.
    """
    missing = []
    try:
        # Same from-import shape as build_realtime_model below, so the
        # check and the construction agree (a from-import always
        # consults the parent package, unlike a bare submodule lookup).
        from livekit.plugins.google.beta import realtime as _realtime_check  # noqa: F401
    except ImportError:
        missing.append("livekit-plugins-google (1.2.x line)")
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
    return google_realtime.RealtimeModel(
        model=REALTIME_MODEL_ID,
        voice=REALTIME_VOICE,
        instructions=AGENT_INSTRUCTIONS,
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


async def _close_trial_session(session: AgentSession, room_name: str) -> None:
    """Await-close a session on a bounded budget without masking cancellation."""
    try:
        await asyncio.wait_for(session.aclose(), timeout=CLEANUP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("session cleanup timed out for room %s", room_name)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("session cleanup failed for room %s", room_name)


async def _delete_trial_room(ctx: JobContext, room_name: str) -> None:
    """Await room deletion on a bounded budget.

    Single owner (livekit-agents 1.2.12): ``delete_room_on_close`` is
    False, so the SDK queues no delete of its own on session close;
    this helper's explicit ``ctx.delete_room()`` is the only delete
    request per job. A successful await only proves the delete API
    call completed — it does NOT prove phone mic release.
    """
    try:
        result = ctx.delete_room()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("room deletion request failed for room %s", room_name)
        return
    try:
        if inspect.isawaitable(result):
            await asyncio.wait_for(result, timeout=CLEANUP_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning("room deletion timed out for room %s", room_name)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("room deletion failed for room %s", room_name)


async def _finish_trial_call(
    ctx: JobContext, session: AgentSession | None, room_name: str, reason: str
) -> None:
    """One awaited, bounded cleanup path: close, delete, shutdown.

    Shutdown always runs, even when cleanup is cancelled; cancellation
    is then re-raised so it still propagates to the caller.
    """
    pending_cancel: BaseException | None = None
    if session is not None:
        try:
            await _close_trial_session(session, room_name)
        except asyncio.CancelledError as exc:
            pending_cancel = exc
    try:
        await _delete_trial_room(ctx, room_name)
    except asyncio.CancelledError as exc:
        if pending_cancel is None:
            pending_cancel = exc
    try:
        ctx.shutdown(reason=reason)
    except Exception:
        logger.warning("context shutdown failed for room %s", room_name)
    if pending_cancel is not None:
        raise pending_cancel


def _room_is_connected(room) -> bool:
    fn = getattr(room, "isconnected", None)
    if fn is None:
        return True
    try:
        return bool(fn() if callable(fn) else fn)
    except Exception:
        return True


def _close_event_metadata(event) -> tuple[str | None, str | None]:
    """Content-free close metadata: reason value + error type name only.

    The SDK emits a ``CloseEvent`` (reason + error object) on "close";
    older fakes may pass a plain marker instead. Never touches the error
    message or any payload — only the reason value and the error's type
    name, so no conversation content can leak into logs or exceptions.
    Returns (reason_value, error_type_name), either of which may be None.
    """
    reason = getattr(event, "reason", None)
    if reason is None:
        return None, None
    reason_value = getattr(reason, "value", reason)
    try:
        reason_value = str(reason_value)
    except Exception:
        return None, None
    error = getattr(event, "error", None)
    error_type = type(error).__name__ if error is not None else None
    return reason_value, error_type


async def _wait_for_call_end(room, sess_closed) -> tuple[str, str | None, str | None]:
    """Wait for a participant-triggered end: room disconnect OR session close.

    No inner timeout — the caller's overall deadline bounds this await.
    The session "close" listener is registered by the caller BEFORE
    session.start() so an early close is never missed; the room
    listener registers here (rooms never replay disconnects, so an
    already-disconnected room is detected via isconnected()). Returns
    (outcome, close_reason, close_error_type) where outcome is
    "session-closed" or "disconnected"; the close event itself is
    preserved (not reduced to a string) so the caller can tell a
    participant Phone End from a CloseReason.ERROR failure.
    Verified against livekit-agents 1.2.12: ``rtc.Room`` emits
    "disconnected" and ``AgentSession`` (an EventEmitter) emits "close"
    with a CloseEvent(reason, error) (rtc/room.py, rtc/event_emitter.py,
    voice/agent_session.py, voice/events.py). Listeners are always removed.
    """
    loop = asyncio.get_running_loop()
    room_gone: asyncio.Future[str] = loop.create_future()

    def _on_disconnected(*args) -> None:
        if not room_gone.done():
            room_gone.set_result("disconnected")

    room.on("disconnected", _on_disconnected)
    try:
        if not _room_is_connected(room):
            return "disconnected", None, None
        if sess_closed.done():
            return "session-closed", *_close_event_metadata(sess_closed.result())
        await asyncio.wait(
            [room_gone, sess_closed], return_when=asyncio.FIRST_COMPLETED
        )
        if sess_closed.done():
            return "session-closed", *_close_event_metadata(sess_closed.result())
        return "disconnected", None, None
    finally:
        try:
            room.off("disconnected", _on_disconnected)
        except Exception:
            logger.warning("room listener removal failed")


async def entrypoint(ctx: JobContext, *, time_limit_s: float = CALL_TIME_LIMIT_S) -> None:
    """One dispatched job = one trial call. Ends promptly on phone End.

    The entrypoint waits for EITHER the room's "disconnected" event OR
    the AgentSession "close" event (registered BEFORE session.start so
    an early close is never missed): a human Phone End closes the
    session via the SDK's own close_on_disconnect path while the agent
    room may stay connected, and that session close now ends the wait
    instead of stalling until the deadline. A single explicit
    ``ctx.delete_room()`` remains the only delete owner (SDK
    auto-delete stays off).
    Active deadline: setup awaits (connect, session start) and the
    end-wait run inside ``asyncio.timeout(time_limit_s)``. Expiry is
    decided by the timeout scope itself (``expired()``), never by
    comparing the wall clock, which gives exactly two cases:
    (1) ``expired()`` is False — the TimeoutError came from
    connect/start, not from this deadline (including one raised just
    before the deadline fires). It is preserved as the real error,
    logged as a setup failure, cleaned up with the setup-failed
    reason, and re-raised.
    (2) ``expired()`` is True — the deadline itself fired, so the call
    is reported as a deadline and ends gracefully with the
    time-limit-reached reason even if connect/start caught the
    cancellation and converted it into its own TimeoutError. The
    scope, not the clock, is the sole authority on which case applies.
    Synchronous model construction cannot be preempted by the timeout;
    it runs to completion (fast local constructor) with its time
    counting against the deadline at the next await. The session close
    event's reason is preserved: a participant Phone End stays a normal
    end, while a CloseReason.ERROR close is a failure (content-free
    reason + error-type metadata, never conversation content) that
    raises instead of reporting success. Cancellation is labeled as
    cancelled (not setup-failed) and still propagates. Failure guarantee
    (this function's own code, covered offline): any partly created
    session is await-closed on a bounded budget, the one explicit room
    deletion is awaited on a bounded budget, and the synchronous
    ``ctx.shutdown()`` (source-verified) still runs before the error
    propagates. Awaited
    deletion only proves the delete API call completed — phone mic
    release is NOT proven offline and needs the live trial.
    """
    try:
        check_trial_prerequisites()
    except Exception:
        logger.exception(
            "dev trial prereq missing for room %s", ctx.room.name
        )
        try:
            ctx.shutdown(reason="dev trial prereq missing")
        except Exception:
            logger.warning(
                "context shutdown failed for room %s", ctx.room.name
            )
        raise
    logger.info("accepting dispatched job for room %s", ctx.room.name)
    session: AgentSession | None = None
    loop = asyncio.get_running_loop()
    try:
        async with asyncio.timeout(time_limit_s) as timeout_scope:
            await ctx.connect()
            # Sync: runs to completion, not preemptible (see note above).
            model = build_realtime_model()
            session = AgentSession(llm=model)
            sess_closed: asyncio.Future = loop.create_future()

            def _on_sess_close(*args) -> None:
                if not sess_closed.done():
                    sess_closed.set_result(args[0] if args else None)

            # BEFORE start: the SDK may schedule a close during start
            # (participant already gone) that fires before start
            # returns — registering now means it cannot be missed.
            session.on("close", _on_sess_close)
            try:
                agent = Agent(instructions=AGENT_INSTRUCTIONS)
                await session.start(
                    agent,
                    room=ctx.room,
                    room_input_options=build_room_input_options(),
                    room_output_options=build_room_output_options(),
                    capture_run=False,
                )
                logger.info("session started for room %s", ctx.room.name)
                outcome, close_reason, close_error_type = await _wait_for_call_end(
                    ctx.room, sess_closed
                )
            finally:
                try:
                    session.off("close", _on_sess_close)
                except Exception:
                    logger.warning(
                        "session listener removal failed for room %s",
                        ctx.room.name,
                    )
    except TimeoutError:
        if timeout_scope.expired():
            logger.info(
                "dev trial time limit reached for room %s", ctx.room.name
            )
            await _finish_trial_call(
                ctx, session, ctx.room.name, reason="dev trial time limit reached"
            )
            logger.info("session ended for room %s", ctx.room.name)
            return
        # Case 1: the scope did NOT expire, so this TimeoutError came
        # from connect/start (even if raised only just before the
        # deadline). Preserve the real error as a setup failure.
        # Case 2 (expired() True, above) already returned: when the
        # deadline itself fired, a connect/start that converted the
        # cancellation into a TimeoutError is still a deadline.
        logger.exception(
            "dev trial setup failed for room %s", ctx.room.name
        )
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial setup failed"
        )
        raise
    except asyncio.CancelledError:
        logger.warning("dev trial cancelled for room %s", ctx.room.name)
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial cancelled"
        )
        raise
    except BaseException:
        logger.exception("dev trial setup failed for room %s", ctx.room.name)
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial setup failed"
        )
        raise
    if close_reason == "error":
        logger.error(
            "dev trial session error for room %s (reason=%s error_type=%s)",
            ctx.room.name,
            close_reason,
            close_error_type,
        )
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial session error"
        )
        raise RuntimeError(
            f"dev trial session error: reason={close_reason} "
            f"error_type={close_error_type}"
        )
    await _finish_trial_call(
        ctx, session, ctx.room.name, reason="dev trial call ended"
    )
    logger.info("session ended for room %s", ctx.room.name)


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
    cli.run_app(build_worker_options())
