"""Stock-session privacy and provider ownership; SDD §§6/8/9/11.

No audio loop, native Live hooks, context replacement or business persistence.
Close waits request cancellation; they do not establish a wall-clock/provider stop.
"""
import asyncio
from livekit.agents import AgentSession
from voice_trial_config import CLEANUP_TIMEOUT_S


async def close_owned(owners: list, session_close=None) -> None:
    """Try every owner; retain failed owners for retry and propagate cancellation."""
    failure = None
    for owner in tuple(owners):
        close = session_close if owner is None else owner.aclose
        try:
            await asyncio.wait_for(close(), CLEANUP_TIMEOUT_S)
        except BaseException as error:
            if failure is None or isinstance(error, asyncio.CancelledError):
                failure = error
        else:
            owners.remove(owner)
    if failure is not None:
        raise failure


class CascadeSession(AgentSession):
    """Own the core session plus the three components the core does not close."""

    def __init__(self, *, stt, llm, tts, **kwargs):
        super().__init__(stt=stt, llm=llm, tts=tts, **kwargs)
        self._cascade_owners = [None, llm, tts, stt]
        self._cascade_close_lock = asyncio.Lock()

    async def start(self, agent, **kwargs):
        kwargs.update(record=False, capture_run=False, session_host=False)
        return await super().start(agent, **kwargs)

    async def aclose(self) -> None:
        async with self._cascade_close_lock:
            await close_owned(self._cascade_owners, super().aclose)
