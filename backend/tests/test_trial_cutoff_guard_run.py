"""Offline tests for the cutoff guard's operator entry point.

No network, no rooms, no worker, no credentials. The adapter is driven
against a fake LiveKit client that returns REAL protocol
request/response objects, so the translation the installed SDK
actually requires is covered rather than assumed.
"""

import asyncio
import contextlib
import json
import tempfile
from pathlib import Path

import pytest

pytest.importorskip(
    "livekit.api", reason="voice draft needs livekit-agents (local .venv only)"
)

from livekit import api as livekit_api  # noqa: E402
from livekit.protocol.models import Room  # noqa: E402

import trial_cutoff_guard_run as guard_run  # noqa: E402

DISPATCH_LINE = (
    'received job request {"job_id": "AJ_1", "dispatch_id": "AD_1", '
    '"room_name": "%s", "agent_name": "think-partner-dev", "resuming": false}\n'
)


@contextlib.contextmanager
def _worker_log(text=""):
    """A temporary worker log, disposed of afterwards."""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "worker.out.log"
        path.write_text(text, encoding="utf-8")
        yield path


class FakeRoomService:
    """``client.room`` stand-in speaking the real request/response types."""

    def __init__(self, script, on_poll=None, delete_behavior="remove"):
        self._script = [list(poll) for poll in script]
        self._on_poll = on_poll
        self._delete_behavior = delete_behavior
        self._poll = 0
        self.deletes = []
        self.seen_requests = []

    async def list_rooms(self, request):
        assert isinstance(request, livekit_api.ListRoomsRequest)
        self.seen_requests.append(request)
        if self._on_poll is not None:
            self._on_poll(self._poll)
        index = min(self._poll, len(self._script) - 1)
        self._poll += 1
        return livekit_api.ListRoomsResponse(
            rooms=[
                Room(name=name, sid="RM_" + name, num_participants=1)
                for name in self._script[index]
            ]
        )

    async def delete_room(self, request):
        assert isinstance(request, livekit_api.DeleteRoomRequest)
        self.deletes.append(request.room)
        if self._delete_behavior == "remove":
            for poll in self._script:
                if request.room in poll:
                    poll.remove(request.room)


class FakeLiveKitClient:
    def __init__(self, script, **kwargs):
        self.room = FakeRoomService(script, **kwargs)
        self.closed = False

    async def aclose(self):
        self.closed = True


def test_adapter_speaks_the_installed_sdk_types():
    client = FakeLiveKitClient([["room-a", "stranger"]])
    adapter = guard_run.LiveKitRoomApi(client)
    rooms = asyncio.run(adapter.list_rooms())
    assert [room.name for room in rooms] == ["room-a", "stranger"]
    assert rooms[0].sid == "RM_room-a"
    assert rooms[0].num_participants == 1
    asyncio.run(adapter.delete_room("room-a"))
    assert client.room.deletes == ["room-a"]
    assert isinstance(client.room.seen_requests[0], livekit_api.ListRoomsRequest)


def test_driver_arms_before_start_and_adopts_a_later_dispatch():
    # Armed with no dispatch yet: ownership arrives mid-run from the
    # worker log and the adopted room still gets its own cutoff.
    with _worker_log() as log:

        def _dispatch_on_second_poll(poll):
            if poll == 1:
                log.write_text(DISPATCH_LINE % "room-a", encoding="utf-8")

        client = FakeLiveKitClient(
            [[], ["room-a"], ["room-a"], ["room-a"], ["room-a"], ["room-a"]],
            on_poll=_dispatch_on_second_poll,
        )
        summary = asyncio.run(
            guard_run.run_guard(
                log_path=str(log),
                agent_name="think-partner-dev",
                client=client,
                poll_s=0.01,
                cutoff_s=0.03,
                wait_s=3.0,
            )
        )
    assert client.room.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["owned"]["room-a"]["closure"] == "post-cutoff-delete"
    assert summary["all_owned_closed"] is True
    assert client.closed is True


def test_driver_reports_worker_closure_separately_from_its_own_delete():
    # The worker closed the room before the cutoff: the guard verifies
    # closure from the listing and never spends a delete request.
    with _worker_log(DISPATCH_LINE % "room-a") as log:
        client = FakeLiveKitClient([[], ["room-a"], ["room-a"], []])
        summary = asyncio.run(
            guard_run.run_guard(
                log_path=str(log),
                agent_name="think-partner-dev",
                client=client,
                poll_s=0.01,
                cutoff_s=0.03,
                wait_s=3.0,
            )
        )
    assert client.room.deletes == []
    assert summary["owned"]["room-a"]["closure"] == "natural"
    assert summary["all_owned_closed"] is True


def test_driver_never_deletes_an_unmatched_room():
    with _worker_log(DISPATCH_LINE % "room-a") as log:
        client = FakeLiveKitClient(
            [
                [],
                ["room-a", "stranger"],
                ["room-a", "stranger"],
                ["room-a", "stranger"],
            ]
        )
        summary = asyncio.run(
            guard_run.run_guard(
                log_path=str(log),
                agent_name="think-partner-dev",
                client=client,
                poll_s=0.01,
                cutoff_s=0.02,
                wait_s=3.0,
            )
        )
    assert client.room.deletes == ["room-a"]
    assert summary["unmatched"] == ["stranger"]
    assert summary["all_owned_closed"] is True


def test_other_workers_rooms_are_never_owned():
    with _worker_log(
        'received job request {"room_name": "other-room", '
        '"agent_name": "some-other-agent"}\n'
    ) as log:
        client = FakeLiveKitClient([["other-room"]])
        summary = asyncio.run(
            guard_run.run_guard(
                log_path=str(log),
                agent_name="think-partner-dev",
                client=client,
                poll_s=0.01,
                cutoff_s=0.02,
                wait_s=0.2,
            )
        )
    assert client.room.deletes == []
    assert summary["owned"] == {}
    assert summary["unmatched"] == ["other-room"]


def test_missing_credentials_are_named_never_valued(monkeypatch):
    for name in guard_run.CREDENTIAL_ENV:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIVEKIT_URL", "should-not-be-used")
    with pytest.raises(SystemExit) as excinfo:
        guard_run.build_client()
    message = str(excinfo.value)
    assert "LIVEKIT_API_KEY" in message
    assert "LIVEKIT_API_SECRET" in message
    assert "should-not-be-used" not in message


def test_main_prints_summary_and_signals_unresolved_closure(capsys):
    with _worker_log(DISPATCH_LINE % "room-a") as log:
        # The room survives the cutoff delete and never closes: the run
        # must end unresolved and say so through the exit code, not a
        # success claim.
        client = FakeLiveKitClient([["room-a"]], delete_behavior="keep")
        code = guard_run.main(
            [
                "--log",
                str(log),
                "--poll",
                "0.01",
                "--cutoff",
                "0.02",
                "--wait",
                "0.1",
            ],
            client=client,
        )
    summary = json.loads(capsys.readouterr().out)
    assert code == 1
    assert summary["all_owned_closed"] is False
    assert summary["deadline_exceeded"] is True
    assert client.room.deletes == ["room-a"]


def test_driver_shutdown_is_bounded_when_close_hangs():
    # A wedged SDK close must not hang the driver: the run still
    # returns its room summary instead of stalling in aclose().
    class _HangCloseClient(FakeLiveKitClient):
        async def aclose(self):
            await asyncio.sleep(3600)

    with _worker_log("") as log:
        summary = asyncio.run(
            asyncio.wait_for(
                guard_run.run_guard(
                    log_path=str(log),
                    agent_name="think-partner-dev",
                    client=_HangCloseClient([[]]),
                    poll_s=0.01,
                    cutoff_s=100.0,
                    wait_s=0.05,
                    api_timeout_s=0.05,
                ),
                timeout=5.0,
            )
        )
    assert summary["owned"] == {}
    assert summary["deadline_exceeded"] is True
    assert summary["client_close"] == "TimeoutError", summary


def test_failed_client_close_is_reported_not_swallowed():
    # Every owned room was verified closed, but the SDK client did not
    # close. The summary must say so instead of leaving the operator
    # with a clean-looking success.
    class _FailingCloseClient(FakeLiveKitClient):
        async def aclose(self):
            raise RuntimeError("close transport blew up")

    with _worker_log(DISPATCH_LINE % "room-a") as log:
        client = _FailingCloseClient([[], ["room-a"], []])
        summary = asyncio.run(
            guard_run.run_guard(
                log_path=str(log),
                agent_name="think-partner-dev",
                client=client,
                poll_s=0.01,
                cutoff_s=0.02,
                wait_s=3.0,
            )
        )
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True
    assert client.closed is False
    assert summary["client_close"] == "RuntimeError", summary


def test_unclosed_client_fails_the_exit_code(capsys):
    # The exit code is the operator's only signal from a script run, so
    # an unclosed client must make it non-zero even when every owned
    # room was verified closed.
    class _FailingCloseClient(FakeLiveKitClient):
        async def aclose(self):
            raise RuntimeError("close transport blew up")

    with _worker_log(DISPATCH_LINE % "room-a") as log:
        code = guard_run.main(
            [
                "--log",
                str(log),
                "--poll",
                "0.01",
                "--cutoff",
                "0.02",
                "--wait",
                "2.0",
            ],
            client=_FailingCloseClient([[], ["room-a"], []]),
        )
    summary = json.loads(capsys.readouterr().out)
    assert summary["all_owned_closed"] is True
    assert summary["client_close"] == "RuntimeError", summary
    assert code == 1
    # The positive case stays a success, so the condition is not simply
    # always non-zero.
    with _worker_log(DISPATCH_LINE % "room-a") as log:
        ok_client = FakeLiveKitClient([[], ["room-a"], []])
        ok_code = guard_run.main(
            [
                "--log",
                str(log),
                "--poll",
                "0.01",
                "--cutoff",
                "0.02",
                "--wait",
                "2.0",
            ],
            client=ok_client,
        )
    ok_summary = json.loads(capsys.readouterr().out)
    assert ok_summary["client_close"] == "ok", ok_summary
    assert ok_client.closed is True
    assert ok_code == 0
