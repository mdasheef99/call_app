"""Prepared cascade job entrypoint only (SDD §§3/4/6/8).

No CLI launcher/worker startup. A future separately approved launcher must protect
all owned SDK logging sinks, keep watch/reload off and run only one named engine.
Do not pass these options to a CLI that adds an unprotected handler. D2 access,
D6 and the trial preflight/approval remain external gates, not checked by keys.
"""
from functools import partial
import logging
from uuid import uuid4

import voice_cascade_config as config
from voice_trial_config import AGENT_NAME, AGENT_INSTRUCTIONS, CALL_TIME_LIMIT_S, CLEANUP_TIMEOUT_S


async def entrypoint(ctx, *, handlers=(), time_limit_s=CALL_TIME_LIMIT_S) -> None:
    try:
        config.check_profile()
        config.protect_handlers((*handlers, *logging.getLogger().handlers), uuid4().hex)
    except BaseException:
        ctx.shutdown("dev trial prereq missing")
        raise
    from livekit.agents import Agent, RoomInputOptions, RoomOutputOptions
    from voice_trial_lifecycle import run_trial

    await run_trial(ctx, check_prerequisites=config.check_trial_prerequisites,
            build_session=lambda: config.build_session(register_cleanup=ctx.add_shutdown_callback),
            build_agent=lambda: Agent(instructions=AGENT_INSTRUCTIONS),
            build_room_input_options=lambda: RoomInputOptions(audio_enabled=True, video_enabled=False,
                text_enabled=False, close_on_disconnect=True, delete_room_on_close=False),
            build_room_output_options=lambda: RoomOutputOptions(audio_enabled=True,
                transcription_enabled=False, sync_transcription=False),
            time_limit_s=time_limit_s, cleanup_timeout_s=CLEANUP_TIMEOUT_S)


def prepare_worker(handlers):
    """Bootstrap on the main thread; return options without running any worker."""
    config.check_profile()
    handlers = tuple(handlers)
    config.protect_handlers(handlers, "cascade-bootstrap")
    config.initialize_plugins()
    from livekit.agents import WorkerOptions
    return WorkerOptions(entrypoint_fnc=partial(entrypoint, handlers=handlers), agent_name=AGENT_NAME)
