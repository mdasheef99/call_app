"""Operator entry point for the supervised dev-trial cutoff guard.

Turns the guard core (``trial_cutoff_guard``) into something an
operator can actually run, and adapts the installed LiveKit SDK to the
duck-typed room API the core expects. Run it BEFORE tapping Start:

    $ $env:LIVEKIT_URL=...; $env:LIVEKIT_API_KEY=...; $env:LIVEKIT_API_SECRET=...
    $ .\\backend\\.venv\\Scripts\\python.exe trial_cutoff_guard_run.py --log worker.out.log

Credentials come from the trial-shell environment only — names are
listed when one is missing, values are never printed and no credential
file is read. The worker log is re-read on every poll, so a room
dispatched after monitoring was armed is adopted with its own cutoff.

The summary states, per owned room, whether closure came from the
worker's own cleanup (``natural``) or after the guard's fallback cutoff
delete (``post-cutoff-delete``). Unmatched rooms are reported and never
deleted. Exit code 0 only when every owned room was verified closed
and the SDK client actually closed (``client_close`` is ``ok``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from livekit import api as livekit_api

from trial_cutoff_guard import (
    API_TIMEOUT_S,
    CUTOFF_SECONDS,
    WAIT_SECONDS,
    CutoffGuard,
    RoomView,
    owned_rooms_from_dispatch_log,
)
from voice_agent_dev import AGENT_NAME

CREDENTIAL_ENV = ("LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")


class LiveKitRoomApi:
    """Adapter from the installed SDK to the guard's duck-typed API.

    ``RoomService`` takes request objects and returns response objects;
    the guard wants a plain list of names and a delete by name. The
    translation lives here so the core keeps working with a fake.
    """

    def __init__(self, client):
        self._client = client

    async def list_rooms(self) -> list[RoomView]:
        response = await self._client.room.list_rooms(
            livekit_api.ListRoomsRequest()
        )
        return [
            RoomView(
                name=room.name,
                sid=room.sid,
                num_participants=room.num_participants,
            )
            for room in response.rooms
        ]

    async def delete_room(self, name: str) -> None:
        await self._client.room.delete_room(
            livekit_api.DeleteRoomRequest(room=name)
        )

    async def aclose(self) -> None:
        await self._client.aclose()


def build_client():
    """LiveKitAPI from trial-shell variables, or SystemExit naming them."""
    missing = [name for name in CREDENTIAL_ENV if not os.environ.get(name)]
    if missing:
        raise SystemExit(
            "missing trial-shell variables (set values in the shell, "
            "never on the command line): " + ", ".join(missing)
        )
    return livekit_api.LiveKitAPI(
        os.environ["LIVEKIT_URL"],
        os.environ["LIVEKIT_API_KEY"],
        os.environ["LIVEKIT_API_SECRET"],
    )


def read_owned_rooms(log_path: str, agent_name: str) -> set[str]:
    """Owned room names from the worker log, re-read on every poll.

    A log that does not exist yet (monitoring armed before Start) or
    cannot be read yields no ownership yet rather than failing the run.
    """
    try:
        text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()
    return owned_rooms_from_dispatch_log(text, agent_name)


async def run_guard(
    *,
    log_path: str,
    agent_name: str = AGENT_NAME,
    client=None,
    poll_s: float = 1.0,
    cutoff_s: float = CUTOFF_SECONDS,
    wait_s: float = WAIT_SECONDS,
    api_timeout_s: float = API_TIMEOUT_S,
) -> dict:
    """Watch from arming until every owned room is verified closed.

    Driver shutdown gets its own finite budget (``api_timeout_s``) and
    its outcome is REPORTED as ``client_close`` (``ok``, or the error
    type name), never folded into the room evidence: the room summary
    still says only what listings observed. No hard wall-clock
    guarantee is claimed against SDK code that never yields.
    """
    adapter = LiveKitRoomApi(client if client is not None else build_client())
    guard = CutoffGuard(set(), cutoff_s=cutoff_s, api_timeout_s=api_timeout_s)
    try:
        summary = await guard.run(
            adapter,
            poll_s=poll_s,
            wait_s=wait_s,
            discover_owned=lambda: read_owned_rooms(log_path, agent_name),
        )
    finally:
        summary_close = await _close_client(adapter, api_timeout_s)
    summary["client_close"] = summary_close
    return summary


async def _close_client(adapter, timeout_s: float) -> str:
    """Bounded client shutdown reported, never raised.

    A wedged or failing close leaves the SDK client open, so it must
    reach the operator's summary and exit code instead of being
    swallowed. Cancellation is a BaseException and still propagates.
    """
    try:
        await asyncio.wait_for(adapter.aclose(), timeout=timeout_s)
    except Exception as error:
        return type(error).__name__
    return "ok"


def main(argv=None, *, client=None) -> int:
    parser = argparse.ArgumentParser(
        description="Watch and bound the dev-trial room (offline core)."
    )
    parser.add_argument(
        "--log", required=True, help="worker log file to take dispatch ownership from"
    )
    parser.add_argument(
        "--agent",
        default=AGENT_NAME,
        help="named worker whose dispatches this trial owns",
    )
    parser.add_argument("--poll", type=float, default=1.0)
    parser.add_argument("--cutoff", type=float, default=CUTOFF_SECONDS)
    parser.add_argument("--wait", type=float, default=WAIT_SECONDS)
    args = parser.parse_args(argv)
    summary = asyncio.run(
        run_guard(
            log_path=args.log,
            agent_name=args.agent,
            client=client,
            poll_s=args.poll,
            cutoff_s=args.cutoff,
            wait_s=args.wait,
        )
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    # Exit 0 means the whole watch completed: every owned room verified
    # closed AND the SDK client actually closed.
    return 0 if summary["all_owned_closed"] and summary["client_close"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
