"""One shared development-trial lifecycle (SDD §§3/5/6/9/11).

The selected configuration supplies construction and admission; this module owns
setup/end/deadline observation and invokes the single awaited cleanup owner.
Extracted from the verified native 1.2.12 path. Other SDK profiles need conformance
before activation. No provider adapter, model, registry, retry or storage here.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from collections.abc import Awaitable, Callable
from livekit.agents import Agent, AgentSession, JobContext, RoomInputOptions, RoomOutputOptions
from voice_trial_cleanup import _finish_trial_call
from voice_trial_config import CALL_TIME_LIMIT_S, CLEANUP_TIMEOUT_S

logger = logging.getLogger("think-partner-dev")

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



async def run_trial(
    ctx: JobContext, *,
    check_prerequisites: Callable[[], None],
    build_session: Callable[[], AgentSession | Awaitable[AgentSession]],
    build_agent: Callable[[], Agent],
    build_room_input_options: Callable[[], RoomInputOptions],
    build_room_output_options: Callable[[], RoomOutputOptions],
    time_limit_s: float = CALL_TIME_LIMIT_S,
    cleanup_timeout_s: float = CLEANUP_TIMEOUT_S,
) -> None:
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
        check_prerequisites()
    except Exception as error:
        logger.error(
            "dev trial prereq missing for room %s (error_type=%s)",
            ctx.room.name, type(error).__name__,
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
            # Sync native construction remains non-preemptible; optional async
            # factories own partial-construction cleanup inside the same deadline.
            constructed = build_session()
            session = await constructed if inspect.isawaitable(constructed) else constructed
            sess_closed: asyncio.Future = loop.create_future()

            def _on_sess_close(*args) -> None:
                if not sess_closed.done():
                    sess_closed.set_result(args[0] if args else None)

            # BEFORE start: the SDK may schedule a close during start
            # (participant already gone) that fires before start
            # returns — registering now means it cannot be missed.
            session.on("close", _on_sess_close)
            try:
                agent = build_agent()
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
    except TimeoutError as error:
        if timeout_scope.expired():
            logger.info(
                "dev trial time limit reached for room %s", ctx.room.name
            )
            await _finish_trial_call(
                ctx, session, ctx.room.name, reason="dev trial time limit reached",
                cleanup_timeout_s=cleanup_timeout_s,
            )
            logger.info("session ended for room %s", ctx.room.name)
            return
        # Case 1: the scope did NOT expire, so this TimeoutError came
        # from connect/start (even if raised only just before the
        # deadline). Preserve the real error as a setup failure.
        # Case 2 (expired() True, above) already returned: when the
        # deadline itself fired, a connect/start that converted the
        # cancellation into a TimeoutError is still a deadline.
        logger.error(
            "dev trial setup failed for room %s (error_type=%s)",
            ctx.room.name, type(error).__name__,
        )
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial setup failed",
            cleanup_timeout_s=cleanup_timeout_s,
        )
        raise
    except asyncio.CancelledError:
        logger.warning("dev trial cancelled for room %s", ctx.room.name)
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial cancelled",
            cleanup_timeout_s=cleanup_timeout_s,
        )
        raise
    except BaseException as error:
        logger.error("dev trial setup failed for room %s (error_type=%s)",
                     ctx.room.name, type(error).__name__)
        await _finish_trial_call(
            ctx, session, ctx.room.name, reason="dev trial setup failed",
            cleanup_timeout_s=cleanup_timeout_s,
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
            ctx, session, ctx.room.name, reason="dev trial session error",
            cleanup_timeout_s=cleanup_timeout_s,
        )
        raise RuntimeError(
            f"dev trial session error: reason={close_reason} "
            f"error_type={close_error_type}"
        )
    await _finish_trial_call(
        ctx, session, ctx.room.name, reason="dev trial call ended",
        cleanup_timeout_s=cleanup_timeout_s,
    )
    logger.info("session ended for room %s", ctx.room.name)
