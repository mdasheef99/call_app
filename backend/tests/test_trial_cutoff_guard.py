"""Offline tests for the external trial cutoff guard.

The 2026-09-28 monitor exited on two simultaneous rooms before
capturing one (``unexpected_multiple_rooms``), so its timed cutoff was
never exercised. The corrected guard must track every owned room on
independent deadlines, never let unmatched rooms disable timers, and
never claim cleanup without a confirming poll.

Ownership comes ONLY from exact test-worker dispatch records (room
names); participant names or room prefixes alone are insufficient and
must never select a room for deletion. Fake API adapter only — no
network, no rooms, no workers.
"""

import asyncio
import contextlib

import pytest

import trial_cutoff_guard as guard_module
from trial_cutoff_guard import (
    CutoffGuard,
    RoomView,
    owned_rooms_from_dispatch_log,
)


@contextlib.contextmanager
def _granted_timeouts():
    """Record the timeout the guard hands to ``asyncio.wait_for``.

    Lets a test assert the budget the guard decided to allow without
    sleeping: the fake clock and the granted values are compared, so no
    millisecond timing is involved.
    """
    granted = []
    real = asyncio.wait_for

    async def spy(awaitable, timeout):
        granted.append(timeout)
        return await real(awaitable, timeout=timeout)

    asyncio.wait_for = spy
    try:
        yield granted
    finally:
        asyncio.wait_for = real


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


class FakeRoomApi:
    """Scripted rooms per poll; deletes recorded and simulated.

    delete_behavior: "remove" drops the name from later polls (server
    confirms disappearance), "keep" leaves it (unconfirmed), "raise"
    raises a Twirp-shaped error on delete, "not_found" raises the
    server's already-gone response. Only the script decides what later
    polls report, so "keep" also models delayed deletion propagation.

    list_fail_polls: poll indexes where list_rooms fails once. A failed
    request must never be read as "the room is gone".
    """

    def __init__(self, script, delete_behavior="remove", list_fail_polls=()):
        self._script = [list(poll) for poll in script]
        self._delete_behavior = delete_behavior
        self._list_fail = set(list_fail_polls)
        self._poll = 0
        self.deletes = []

    async def list_rooms(self):
        current = self._poll
        index = min(current, len(self._script) - 1)
        self._poll += 1
        if current in self._list_fail:
            self._list_fail.discard(current)
            raise FakeApiError("list transport failed", "unavailable")
        return [
            RoomView(name=name, sid="sid-" + name, num_participants=1)
            for name in self._script[index]
        ]

    async def delete_room(self, name):
        self.deletes.append(name)
        if self._delete_behavior == "raise":
            raise FakeApiError("boom", "internal")
        if self._delete_behavior == "not_found":
            raise FakeApiError("room does not exist", "not_found")
        if self._delete_behavior == "remove":
            for poll in self._script:
                if name in poll:
                    poll.remove(name)


class FakeApiError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


def _run(guard, api, clock, poll_s=1.0, wait_s=30.0, **kwargs):
    return asyncio.run(
        guard.run(
            api,
            poll_s=poll_s,
            wait_s=wait_s,
            clock=clock,
            sleep=clock.sleep,
            **kwargs,
        )
    )


def test_dispatch_log_yields_exact_owned_names():
    log = (
        '2026-09-28 16:25:07,661 - INFO livekit.agents - received job request '
        '{"job_id": "AJ_LKuA3SMiHsqo", "dispatch_id": "AD_BDoSwYxZfqGi", '
        '"room_name": "sbx-ym2qjd-6gDdSC5v9qkNB9JuPwai3C", '
        '"agent_name": "think-partner-dev", "resuming": false}\n'
        '2026-09-28 16:25:26,598 - INFO livekit.agents - received job request '
        '{"job_id": "AJ_KkrqtApJWupC", "dispatch_id": "AD_q7o4E7MQ6du6", '
        '"room_name": "sbx-ym2qjd-997UxjvEj7NTjw5vpxANLh", '
        '"agent_name": "think-partner-dev", "resuming": false}\n'
        'noise line without a dispatch\n'
        'received job request {"room_name": "other-room", "agent_name": "other-agent"}\n'
    )
    owned = owned_rooms_from_dispatch_log(log, "think-partner-dev")
    assert owned == {
        "sbx-ym2qjd-6gDdSC5v9qkNB9JuPwai3C",
        "sbx-ym2qjd-997UxjvEj7NTjw5vpxANLh",
    }


def test_owned_room_deleted_at_cutoff_and_verified():
    owned = {"room-a"}
    api = FakeRoomApi([[], ["room-a"], ["room-a"], ["room-a"]])
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock)
    assert api.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True
    assert summary["unmatched"] == []


def test_multiple_rooms_never_disable_timers_or_cleanup():
    # Regression for the 2026-09-28 monitor exit: an unmatched room
    # present from the start must not stop the owned room's cutoff.
    # The owned room stays listed until the guard deletes it, so the
    # timer (not an accidental disappearance) is what ends the run.
    owned = {"room-a"}
    api = FakeRoomApi(
        [
            [],
            ["room-a", "stranger"],
            ["room-a", "stranger"],
            ["room-a", "stranger"],
        ]
    )
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock)
    assert api.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["unmatched"] == ["stranger"]


def test_prefix_and_participant_lookalikes_are_never_deleted():
    # A room sharing the owned prefix is NOT owned: exact dispatch
    # names only. (The guard never even sees participant names.)
    owned = {"sbx-ym2qjd-6gDdSC5v9qkNB9JuPwai3C"}
    api = FakeRoomApi(
        [[], ["sbx-ym2qjd-6gDdSC5v9qkNB9JuPwai3C", "sbx-ym2qjd-other"]]
    )
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=100.0), api, clock, wait_s=3.0)
    assert api.deletes == []
    assert summary["unmatched"] == ["sbx-ym2qjd-other"]
    assert summary["owned"]["sbx-ym2qjd-6gDdSC5v9qkNB9JuPwai3C"]["status"] == "seen"


def test_owned_rooms_have_independent_deadlines():
    owned = {"room-a", "room-b"}
    api = FakeRoomApi(
        [
            [],
            ["room-a"],
            ["room-a"],
            ["room-a", "room-b"],
            ["room-a", "room-b"],
            ["room-b"],
            [],
        ]
    )
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock)
    assert api.deletes == ["room-a", "room-b"]
    requested = {
        name: info["delete_requested_at"]
        for name, info in summary["owned"].items()
    }
    assert requested["room-b"] > requested["room-a"]
    assert summary["all_owned_closed"] is True


def test_delete_error_is_visible_and_never_verified():
    owned = {"room-a"}
    api = FakeRoomApi([[], ["room-a"], ["room-a"]], delete_behavior="raise")
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock, wait_s=5.0)
    assert api.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "delete-unconfirmed"
    assert summary["all_owned_closed"] is False
    assert summary["api_errors"] == ["FakeApiError"]


def test_room_surviving_delete_is_unconfirmed_not_verified():
    # A room that keeps being listed after the cutoff delete is never
    # verified closed: the guard keeps waiting (delete-requested) and
    # reports delete-unconfirmed when the overall deadline elapses. It
    # must NOT issue a second delete for the same room.
    owned = {"room-a"}
    api = FakeRoomApi([[], ["room-a"], ["room-a"]], delete_behavior="keep")
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock, wait_s=5.0)
    assert api.deletes == ["room-a"], "one delete request per owned room"
    assert summary["owned"]["room-a"]["status"] == "delete-unconfirmed"
    assert summary["all_owned_closed"] is False


def test_unseen_owned_room_reported_without_deletes():
    owned = {"room-a"}
    api = FakeRoomApi([[], []])
    clock = FakeClock()
    summary = _run(CutoffGuard(owned, cutoff_s=2.0), api, clock, wait_s=3.0)
    assert api.deletes == []
    assert summary["owned"]["room-a"]["status"] == "unseen"
    assert summary["all_owned_closed"] is False
    assert summary["deadline_exceeded"] is True


# --- Confirmed 2026-09-28 follow-up defects ---------------------------


def test_empty_ownership_reports_baseline_instead_of_crashing():
    # Nothing owned yet (armed before Start): the run must return the
    # baseline rooms as unmatched, not raise while summarizing.
    api = FakeRoomApi([["other-room"]])
    summary = _run(CutoffGuard(set(), cutoff_s=2.0), api, FakeClock())
    assert summary["unmatched"] == ["other-room"]
    assert summary["owned"] == {}
    assert summary["all_owned_closed"] is False
    assert summary["deadline_exceeded"] is False


def test_failed_poll_never_implies_the_room_is_gone():
    # A list_rooms failure after the cutoff delete must be discarded:
    # the guard never treats a failed request as absence, so closure is
    # not verified from a request that returned nothing.
    api = FakeRoomApi(
        [[], ["room-a"], ["room-a"], ["room-a"], ["room-a"]],
        delete_behavior="keep",
        list_fail_polls={4},
    )
    summary = _run(CutoffGuard({"room-a"}, cutoff_s=2.0), api, FakeClock(), wait_s=8.0)
    assert summary["api_errors"] == ["FakeApiError"]
    assert summary["owned"]["room-a"]["status"] != "verified-closed"
    assert summary["all_owned_closed"] is False


def test_natural_closure_is_verified_without_a_fallback_delete():
    # The worker deleted the room itself before our cutoff: absence in a
    # successful poll is closure, and the guard must not spend a delete
    # request on an already-gone room.
    api = FakeRoomApi([[], ["room-a"], ["room-a"], []])
    summary = _run(CutoffGuard({"room-a"}, cutoff_s=3.0), api, FakeClock(), wait_s=8.0)
    assert api.deletes == []
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["owned"]["room-a"]["closure"] == "natural"
    assert summary["all_owned_closed"] is True


def test_delayed_disappearance_after_delete_is_still_verified():
    # LiveKit deletion is asynchronous: the room may still be listed for
    # a poll or two. That must not end verification.
    api = FakeRoomApi(
        [[], ["room-a"], ["room-a"], ["room-a"], ["room-a"], []],
        delete_behavior="keep",
    )
    summary = _run(CutoffGuard({"room-a"}, cutoff_s=2.0), api, FakeClock(), wait_s=10.0)
    assert api.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["owned"]["room-a"]["closure"] == "post-cutoff-delete"
    assert summary["all_owned_closed"] is True


def test_not_found_delete_still_requires_verification():
    # A not_found delete response is not proof of closure by itself, but
    # it must not block it either: the next successful poll showing the
    # room absent verifies closure.
    api = FakeRoomApi(
        [[], ["room-a"], ["room-a"], ["room-a"], []],
        delete_behavior="not_found",
    )
    summary = _run(CutoffGuard({"room-a"}, cutoff_s=2.0), api, FakeClock(), wait_s=10.0)
    assert summary["api_errors"] == ["FakeApiError"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True


def test_delete_error_then_disappearance_still_verifies():
    # A transient delete failure must not make the room permanently
    # unresolvable: a later successful poll showing absence verifies it.
    api = FakeRoomApi(
        [[], ["room-a"], ["room-a"], ["room-a"], []],
        delete_behavior="raise",
    )
    summary = _run(CutoffGuard({"room-a"}, cutoff_s=2.0), api, FakeClock(), wait_s=10.0)
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True


class _HangingApi:
    """API whose calls never return (transport wedged)."""

    async def list_rooms(self):
        return [RoomView(name="room-a", sid="sid-room-a")]

    async def delete_room(self, name):
        await asyncio.sleep(3600)


def test_hanging_api_call_cannot_stall_the_guard():
    # Every API await has a finite budget, so a wedged request is
    # reported as an error instead of outliving the overall deadline.
    guard = CutoffGuard({"room-a"}, cutoff_s=0.0, api_timeout_s=0.05)
    summary = asyncio.run(
        asyncio.wait_for(
            guard.run(_HangingApi(), poll_s=0.01, wait_s=0.2), timeout=5.0
        )
    )
    assert summary["api_errors"] == ["TimeoutError"]
    assert summary["owned"]["room-a"]["status"] == "delete-unconfirmed"
    assert summary["all_owned_closed"] is False


def test_rooms_discovered_after_arming_get_their_own_deadline():
    # Arming before Start: ownership arrives later from the worker
    # dispatch log, and a room adopted mid-run still gets its own
    # cutoff measured from its own first sighting.
    api = FakeRoomApi(
        [[], [], ["room-a"], ["room-a"], ["room-a"], []]
    )
    clock = FakeClock()
    guard = CutoffGuard(set(), cutoff_s=2.0)

    def _discover():
        return {"room-a"} if clock.now >= 1002.0 else set()

    summary = _run(guard, api, clock, wait_s=20.0, discover_owned=_discover)
    assert api.deletes == ["room-a"]
    assert summary["owned"]["room-a"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True
    assert summary["deadline_exceeded"] is False


def test_ownership_arriving_during_list_stays_monitored():
    # Room A owned and observed; during the next held list request
    # dispatch discovery gains room B and the response shows A absent
    # and B present. B must stay monitored, never exit as unmatched.
    discovered = {"room-a"}

    class _DuringListApi(FakeRoomApi):
        async def list_rooms(self):
            rooms = await super().list_rooms()
            if self._poll == 2:
                discovered.add("room-b")
            return rooms

    api = _DuringListApi([["room-a"], ["room-b"], ["room-b"], []])
    clock = FakeClock()
    guard = CutoffGuard(set(discovered.copy()), cutoff_s=100.0)
    summary = _run(
        guard, api, clock, wait_s=20.0, discover_owned=lambda: set(discovered)
    )
    assert "room-b" in summary["owned"], summary
    assert "room-b" not in summary["unmatched"], summary
    assert summary["owned"]["room-b"]["status"] == "verified-closed"
    assert summary["all_owned_closed"] is True


def test_deadline_uses_fresh_time_after_awaited_request():
    # 5 s elapse inside the first awaited request with wait_s=2:
    # the deadline must be seen without an extra sleep/poll.
    polls = {"n": 0}

    class _AdvancingApi:
        async def list_rooms(self):
            polls["n"] += 1
            clock.now += 5.0
            return []

        async def delete_room(self, name):
            pass

    clock = FakeClock()
    guard = CutoffGuard({"room-a"}, cutoff_s=100.0)
    summary = _run(guard, api=_AdvancingApi(), clock=clock, wait_s=2.0)
    assert summary["deadline_exceeded"] is True
    assert polls["n"] == 1, "stale pre-await timestamp caused an extra poll"


def test_poll_sleep_is_capped_to_remaining_budget():
    # poll_s=10 with wait_s=2 must not sleep past the overall deadline.
    clock = FakeClock()

    class _SteadyApi:
        async def list_rooms(self):
            return []

        async def delete_room(self, name):
            pass

    guard = CutoffGuard({"room-a"}, cutoff_s=100.0)
    summary = _run(
        guard, api=_SteadyApi(), clock=clock, poll_s=10.0, wait_s=2.0
    )
    assert summary["deadline_exceeded"] is True
    assert clock.now - 1000.0 <= 2.0, clock.now


class _TwoRoomBudgetApi:
    """Two owned rooms, each room listing and the FIRST delete burn
    scripted time.

    ``list_burn`` is charged on every listing and ``delete_burn`` on the
    first delete only, so a test can leave budget for the second room or
    consume all of it. ``states`` is keyed from a set, so which room is
    reconciled first is not fixed: nothing here may depend on it.
    """

    def __init__(self, list_burn=0.0, delete_burn=0.0):
        self.list_burn = list_burn
        self.delete_burn = delete_burn
        self.deletes = []
        self._clock = None

    def bind(self, clock):
        self._clock = clock
        return self

    async def list_rooms(self):
        self._clock.now += self.list_burn
        return [
            RoomView(name="room-a", sid="sid-room-a"),
            RoomView(name="room-b", sid="sid-room-b"),
        ]

    async def delete_room(self, name):
        self.deletes.append(name)
        if len(self.deletes) == 1:
            self._clock.now += self.delete_burn


def test_no_api_call_starts_once_the_overall_budget_is_gone():
    # 3 s overall budget, the listing burns 1 s, the first delete burns
    # the remaining 2 s. The second room has no budget left, so no
    # further API call may start and the room must be reported as never
    # deleted rather than as a completed cleanup.
    clock = FakeClock()
    api = _TwoRoomBudgetApi(list_burn=1.0, delete_burn=2.0).bind(clock)
    with _granted_timeouts() as granted:
        summary = _run(
            CutoffGuard({"room-a", "room-b"}, cutoff_s=0.0),
            api,
            clock,
            poll_s=1.0,
            wait_s=3.0,
        )
    assert len(api.deletes) == 1, "no API call with zero budget remaining"
    # listing (3 s of budget), then the one delete (2 s left) - and
    # nothing more, because the next room has no budget at all.
    assert granted == [3.0, 2.0], granted
    # Whichever room lost the race is reported as never deleted, not as
    # cleaned up. ``states`` comes from a set, so it is not room-a.
    skipped = next(n for n in ("room-a", "room-b") if n not in api.deletes)
    assert summary["owned"][skipped]["status"] == "seen"
    assert summary["owned"][skipped]["delete_requested_at"] is None
    assert summary["deadline_exceeded"] is True
    assert summary["all_owned_closed"] is False


def test_each_delete_is_clamped_to_the_budget_left_at_that_moment():
    # Same shape, but the first delete consumes only 0.5 s of the 2 s
    # that remained, so the second room's delete must be clamped to the
    # 1.5 s actually left, not to the value computed before the loop.
    clock = FakeClock()
    api = _TwoRoomBudgetApi(list_burn=1.0, delete_burn=0.5).bind(clock)
    with _granted_timeouts() as granted:
        summary = _run(
            CutoffGuard({"room-a", "room-b"}, cutoff_s=0.0),
            api,
            clock,
            poll_s=1.0,
            wait_s=3.0,
        )
    assert sorted(api.deletes) == ["room-a", "room-b"]
    # The delete timeouts are the 2nd and 3rd bounded calls; the list
    # calls bracket them.
    assert granted[1:3] == [2.0, 1.5], granted
    # Both rooms were asked to delete; the deadline reports an
    # unconfirmed delete rather than a closure for either of them.
    for name in ("room-a", "room-b"):
        assert summary["owned"][name]["delete_requested_at"] is not None, name
        assert summary["owned"][name]["status"] == "delete-unconfirmed", name
    assert summary["deadline_exceeded"] is True
    assert summary["all_owned_closed"] is False
