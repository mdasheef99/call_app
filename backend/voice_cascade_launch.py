"""One isolated, operator-approved cascade worker (SDD §§3/4/6/8/11).

Default CLI checks local profile/key presence only; it never starts a worker.
Live opt-in is not evidence of entitlement/preflight or human authorization.
One lifetime admission per process; other workers/accounts remain external gates.
No env-file loading, SDK CLI, watch/reload or idle shutdown timer. Operator owns
the approved cutoff/room guard and PID stop. Async close is not a hard stop.
"""
import asyncio
import logging
import math
import os
import sys
import threading

import voice_cascade_dev as cascade
from voice_cascade_dev import config
from voice_trial_config import AGENT_NAME, CALL_TIME_LIMIT_S, CLEANUP_TIMEOUT_S


def check_environment() -> None:
    for name in ("LIVEKIT_AGENT_NAME_OVERRIDE", "LIVEKIT_WORKER_TOKEN", "LIVEKIT_AGENT_DEPLOYMENT"):
        if os.environ.get(name):  # the SDK treats even whitespace as an override
            raise RuntimeError("Cascade refuses registration override: " + name)
    names = ("GOOGLE_API_KEY", "SARVAM_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")
    missing = [name for name in names if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Cascade prerequisite missing: " + ", ".join(missing))


class SingleTrial:
    """Reserve before accept; never replenish after failure, cancellation or End."""

    def __init__(self, handlers, time_limit_s):
        self.handlers, self.time_limit_s = tuple(handlers), time_limit_s
        self._claim, self._started = None, False
        self._lock = threading.Lock()  # request loop and Windows job thread

    async def on_request(self, request) -> None:
        with self._lock:
            allowed = (self._claim is None and request.agent_name == AGENT_NAME
                       and bool(request.id) and bool(request.room.name))
            if allowed:
                self._claim = (request.id, request.room.name)
        if allowed:
            logging.getLogger("think-partner-dev.dispatch").info(
                "trial admission", extra={"trial_room_name": self._claim[1]})
            try:
                await request.accept()
            except BaseException:
                with self._lock:
                    self._started = True  # revoke a late assignment; keep reservation spent
                raise
        else:
            await request.reject()

    async def entrypoint(self, ctx) -> None:
        with self._lock:
            allowed = self._claim == (ctx.job.id, ctx.room.name) and not self._started
            if allowed:
                self._started = True
        if not allowed:
            ctx.shutdown("dev trial admission refused")
            raise RuntimeError("Unreserved or repeated cascade job")
        await cascade.entrypoint(ctx, handlers=self.handlers, time_limit_s=self.time_limit_s)


def prepare_server(handlers, time_limit_s):
    """Main-thread bootstrap plus public server construction; no run or sockets."""
    options = cascade.prepare_worker(handlers)
    config.check_trial_prerequisites()
    from livekit.agents import AgentServer, JobExecutorType
    gate = SingleTrial(handlers, time_limit_s)
    options.entrypoint_fnc, options.request_fnc = gate.entrypoint, gate.on_request
    options.job_executor_type, options.num_idle_processes = JobExecutorType.THREAD, 0
    options.max_retry, options.host, options.port = 0, "127.0.0.1", 0
    return AgentServer.from_server_options(options)


async def run_worker(*, approved=False, time_limit_s=CALL_TIME_LIMIT_S) -> None:
    """Call only after separate approval/preflight, inside the isolated process."""
    if approved is not True:
        raise RuntimeError("A separately approved trial is required")
    if (isinstance(time_limit_s, bool) or not isinstance(time_limit_s, (int, float))
            or not math.isfinite(time_limit_s) or not 0 < time_limit_s <= CALL_TIME_LIMIT_S):
        raise ValueError("Trial duration must be positive and within the active deadline")
    config.check_profile()
    check_environment()
    root = logging.getLogger()
    previous, level = root.handlers[:], root.level
    sink = logging.StreamHandler(sys.stderr)
    sink.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s correlation=%(correlation_id)s %(message)s",
        defaults={"correlation_id": "cascade-bootstrap"}))
    config.protect_handlers((sink,), "cascade-bootstrap")
    root.handlers[:] = [sink]
    root.setLevel(logging.INFO)
    try:
        server = prepare_server((sink,), time_limit_s)
        try:
            await server.run(devmode=True)
        finally:
            primary = sys.exception()
            try:
                await asyncio.wait_for(server.aclose(), CLEANUP_TIMEOUT_S)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger("think-partner-dev").error("worker cleanup failed", exc_info=True)
                if primary is None:
                    raise
    finally:
        root.handlers[:] = previous
        root.setLevel(level)
        sink.close()


def main(argv=None) -> int:
    """No secret arguments, raw error messages or automatic start/retry."""
    argv = sys.argv[1:] if argv is None else argv
    try:
        if argv in ([], ["--check"]):
            config.check_profile()
            check_environment()
            print("Local profile/key checks passed; entitlement/live preflight/approval not verified.")
        elif len(argv) == 2 and argv[0] == "--start-approved-trial":
            asyncio.run(run_worker(approved=True, time_limit_s=float(argv[1])))
        else:
            raise ValueError("Use --check or --start-approved-trial <active-seconds>")
        return 0
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("cascade_launcher_stopped error_type=cancelled", file=sys.stderr)
        return 130
    except Exception as error:
        print("cascade_launcher_failed error_type=" + type(error).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
