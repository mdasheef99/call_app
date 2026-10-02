"""Awaited dev-trial close/delete/shutdown, extracted without policy changes.

SDD §§6/9/11; Spec P02. Timeouts request cancellation; SDK calls that resist
cancellation can outlive them. Room deletion is not evidence of phone mic release.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
from livekit import api as livekit_api
from livekit.agents import AgentSession, JobContext
from voice_trial_config import CLEANUP_TIMEOUT_S

logger = logging.getLogger("think-partner-dev")

_SDK_ERROR_CODES = frozenset(
    value
    for value in vars(livekit_api.twirp_client.ServerErrorCode).values()
    if isinstance(value, str)
)



async def _close_trial_session(session: AgentSession, room_name: str, *, timeout_s: float = CLEANUP_TIMEOUT_S) -> None:
    """Await-close a session on a bounded budget without masking cancellation."""
    try:
        await asyncio.wait_for(session.aclose(), timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning("session cleanup timed out for room %s", room_name)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("session cleanup failed for room %s", room_name)



def _deletion_error_diagnostic(error: BaseException) -> str:
    """Content-free deletion-failure metadata for logs.

    Returns the exception type name plus the SDK's error code, but only
    when that code is one the SDK itself defines
    (``livekit.api.twirp_client.ServerErrorCode``). Matching against the
    recognized set — not against a token shape — is what keeps an
    arbitrary or credential-shaped value on the same attribute out of
    the logs. Never touches the exception message, traceback, or any
    payload; unrecognized codes fall back to the type name alone.
    """
    code = getattr(error, "code", None)
    if isinstance(code, str) and code in _SDK_ERROR_CODES:
        return f"type={type(error).__name__} code={code}"
    return f"type={type(error).__name__}"



async def _delete_trial_room(ctx: JobContext, room_name: str, *, timeout_s: float = CLEANUP_TIMEOUT_S) -> None:
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
    except Exception as error:
        logger.warning(
            "room deletion request failed for room %s (%s)",
            room_name,
            _deletion_error_diagnostic(error),
        )
        return
    try:
        if inspect.isawaitable(result):
            await asyncio.wait_for(result, timeout=timeout_s)
    except asyncio.TimeoutError:
        logger.warning("room deletion timed out for room %s", room_name)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        logger.warning(
            "room deletion failed for room %s (%s)",
            room_name,
            _deletion_error_diagnostic(error),
        )



async def _finish_trial_call(
    ctx: JobContext, session: AgentSession | None, room_name: str, reason: str,
    *, cleanup_timeout_s: float = CLEANUP_TIMEOUT_S,
) -> None:
    """One awaited, bounded cleanup path: close, delete, shutdown.

    Shutdown always runs, even when cleanup is cancelled; cancellation
    is then re-raised so it still propagates to the caller.
    """
    pending_cancel: BaseException | None = None
    if session is not None:
        try:
            await _close_trial_session(session, room_name, timeout_s=cleanup_timeout_s)
        except asyncio.CancelledError as exc:
            pending_cancel = exc
    try:
        await _delete_trial_room(ctx, room_name, timeout_s=cleanup_timeout_s)
    except asyncio.CancelledError as exc:
        if pending_cancel is None:
            pending_cancel = exc
    try:
        ctx.shutdown(reason=reason)
    except Exception:
        logger.warning("context shutdown failed for room %s", room_name)
    if pending_cancel is not None:
        raise pending_cancel
