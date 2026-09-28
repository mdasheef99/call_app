"""External cutoff guard for the supervised dev-trial call.

Operational helper for a separately approved trial: it watches the
room list, requests deletion of owned test rooms at their cutoff, and
verifies their disappearance. It never creates rooms, starts workers,
or retries calls.

Ownership comes ONLY from exact test-worker dispatch records (room
names parsed from the worker log). Participant names, identities, and
room prefixes alone are insufficient and are never used to select a
room for deletion; unmatched rooms are reported, never deleted.

Multiple rooms never disable timers: every owned room has an
independent deadline measured from its own first sighting, and an
unmatched crowd changes nothing about owned-room handling. Rooms may
be adopted mid-run (``discover_owned``) so monitoring can be armed
before Start.

Closure is only ever reported from a SUCCESSFUL room listing. A failed
or timed-out request is recorded and discarded — never read as "the
room is gone" — and exactly one delete request is issued per owned
room. A delete response (including ``not_found``) is never itself
proof of closure: a later successful listing that no longer shows the
room is what verifies it, and the summary records whether the room
vanished on its own (normal worker cleanup) or after our fallback
cutoff delete. Nothing is promised about how long deletion takes to
propagate.

Every API await is capped to the remaining overall budget (never more
than ``api_timeout_s``) and the deadline is checked with fresh time
after each await; poll sleeps are capped the same way. The cap is a
request for cancellation, not a bound: ``asyncio.wait_for`` can only
report a timeout once the awaited call actually STOPS, so a transport
that suppresses cancellation while still yielding — or that never yields
— can outlive its cap and is then NOT reported as a timeout. No
wall-clock guarantee is claimed against cancellation-resistant or
non-yielding code.

The room API is duck-typed (``list_rooms`` / ``delete_room``) so the
core stays independently testable with a fake adapter;
``trial_cutoff_guard_run`` supplies the adapter and operator entry
point for the real LiveKit client.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field

#: Planned per-room cutoff from first sighting (mirrors the approved
#: trial's human stop bound; the API round-trip is extra).
CUTOFF_SECONDS = 55.0

#: Requested outer bound for the whole guard run (a call that resists
#: cancellation can exceed it; see the module docstring).
WAIT_SECONDS = 180.0

#: Budget for each individual room API call.
API_TIMEOUT_S = 5.0

_DISPATCH_ROOM_RE = re.compile(r'"room_name":\s*"([^"]+)"')
_DISPATCH_AGENT_RE = re.compile(r'"agent_name":\s*"([^"]+)"')

#: States from which a successful listing showing absence may verify
#: closure. ``unseen`` is excluded: a room never observed in a
#: successful listing was never proven to exist.
_CLOSABLE = ("seen", "delete-requested", "delete-unconfirmed")


@dataclass(frozen=True)
class RoomView:
    """Minimal room snapshot the guard needs (names only matter)."""

    name: str
    sid: str
    num_participants: int = 0


def owned_rooms_from_dispatch_log(log_text: str, agent_name: str) -> set[str]:
    """Extract exact owned room names for one named worker.

    Only lines carrying a ``received job request`` dispatch for the
    given agent name contribute; anything else (other agents, noise)
    is ignored. Returns exact names — never prefixes.
    """
    owned: set[str] = set()
    for line in log_text.splitlines():
        if "received job request" not in line:
            continue
        agent_match = _DISPATCH_AGENT_RE.search(line)
        if agent_match is None or agent_match.group(1) != agent_name:
            continue
        room_match = _DISPATCH_ROOM_RE.search(line)
        if room_match is not None:
            owned.add(room_match.group(1))
    return owned


@dataclass
class _OwnedState:
    status: str = "unseen"
    seen_at: float | None = None
    delete_requested_at: float | None = None
    delete_error: str | None = None

    @property
    def closure(self) -> str | None:
        if self.status != "verified-closed":
            return None
        return "post-cutoff-delete" if self.delete_requested_at else "natural"


@dataclass
class CutoffGuard:
    """Tracks owned rooms to verified closure; reports everything else."""

    owned: set[str] = field(default_factory=set)
    cutoff_s: float = CUTOFF_SECONDS
    api_timeout_s: float = API_TIMEOUT_S

    async def _list_rooms(self, api, timeout) -> tuple[list | None, str | None]:
        """One bounded room listing.

        Returns ``(rooms, None)`` on success or ``(None, error_type)``
        when the request failed, or when the bounded wait reported a
        timeout. A call that outlives its cap by resisting cancellation
        is not bounded by anything Python can enforce (see module
        docstring).
        """
        try:
            return (
                await asyncio.wait_for(api.list_rooms(), timeout=timeout),
                None,
            )
        except Exception as error:
            return None, type(error).__name__

    def _adopt(self, discover_owned, states) -> None:
        """Adopt rooms discovered after arming (e.g. after Start)."""
        if discover_owned is None:
            return
        for name in discover_owned():
            if name not in states:
                states[name] = _OwnedState()
                self.owned.add(name)

    async def _reconcile(
        self, name, state, present, now, api, api_errors, delete_timeout
    ) -> None:
        """Advance one owned room from a SUCCESSFUL listing."""
        if name in present:
            if (
                state.status == "seen"
                and state.seen_at is not None
                and now - state.seen_at >= self.cutoff_s
            ):
                # Exactly one fallback delete request per owned room.
                state.status = "delete-requested"
                state.delete_requested_at = now
                try:
                    await asyncio.wait_for(
                        api.delete_room(name), timeout=delete_timeout
                    )
                except Exception as error:
                    # Includes not_found: the response is not proof of
                    # closure, and a later listing still decides.
                    api_errors.append(type(error).__name__)
                    state.delete_error = type(error).__name__
                    state.status = "delete-unconfirmed"
            return
        if state.status in _CLOSABLE:
            state.status = "verified-closed"

    async def run(
        self,
        api,
        *,
        poll_s: float = 1.0,
        wait_s: float = WAIT_SECONDS,
        clock=time.monotonic,
        sleep=asyncio.sleep,
        discover_owned=None,
    ) -> dict:
        """Poll until all owned rooms are verified closed or time runs out.

        Returns a summary that never claims more than observed:
        per-owned-room status (``unseen`` / ``seen`` /
        ``delete-requested`` / ``verified-closed`` /
        ``delete-unconfirmed``) with how closure was reached, the
        unmatched room names seen, API error type names, and completion
        flags.
        """
        started = clock()
        states = {name: _OwnedState() for name in self.owned}
        unmatched: set[str] = set()
        api_errors: list[str] = []

        if not states and discover_owned is None:
            # Nothing owned and nothing to discover: report the baseline
            # crowd once. No room was tracked, so no deadline elapsed.
            remaining = wait_s - (clock() - started)
            timeout = (
                min(self.api_timeout_s, remaining)
                if remaining > 0
                else self.api_timeout_s
            )
            rooms, error_type = await self._list_rooms(api, timeout)
            if error_type is not None:
                api_errors.append(error_type)
            else:
                for room in rooms:
                    unmatched.add(room.name)
            return self._summary(states, unmatched, api_errors, started, False)

        while True:
            self._adopt(discover_owned, states)
            remaining = wait_s - (clock() - started)
            if remaining <= 0:
                return self._summary(states, unmatched, api_errors, started, True)
            rooms, error_type = await self._list_rooms(
                api, min(self.api_timeout_s, remaining)
            )
            now = clock()
            if error_type is not None:
                # A failed or timed-out request proves nothing about
                # presence or absence; record it and poll again.
                api_errors.append(error_type)
                # Ownership may have arrived during the failed request:
                # adopt afterwards so a newly owned room stays monitored.
                self._adopt(discover_owned, states)
            else:
                present = {room.name for room in rooms}
                for name in present:
                    if name in states:
                        state = states[name]
                        if state.status == "unseen":
                            state.status = "seen"
                            state.seen_at = now
                    else:
                        unmatched.add(name)
                for name, state in states.items():
                    # Re-read the clock per room: an earlier deletion may
                    # have consumed the overall budget, and a room with
                    # nothing left is not deleted at all.
                    delete_now = clock()
                    remaining = wait_s - (delete_now - started)
                    if remaining <= 0:
                        break
                    await self._reconcile(
                        name, state, present, delete_now, api, api_errors,
                        min(self.api_timeout_s, remaining),
                    )
                # Ownership may have arrived during the awaited request:
                # a newly owned active room stays monitored instead of
                # exiting as unmatched. Genuinely unmatched rooms are
                # still never deleted.
                adopted_before = set(states)
                self._adopt(discover_owned, states)
                for name in set(states) - adopted_before:
                    # Exact dispatch ownership wins over the crowd label
                    # from this same listing.
                    unmatched.discard(name)
                    if name in present:
                        states[name].status = "seen"
                        states[name].seen_at = now
                    # Newly adopted rooms seen absent in this same
                    # successful listing stay unseen: absence without a
                    # prior presence never verifies closure.
                # A room adopted above that was already gone stays
                # unseen, so completion still requires observing it.
            if states and all(
                s.status == "verified-closed" for s in states.values()
            ):
                return self._summary(states, unmatched, api_errors, started, False)
            if clock() - started >= wait_s:
                return self._summary(states, unmatched, api_errors, started, True)
            remaining = wait_s - (clock() - started)
            if remaining <= 0:
                return self._summary(states, unmatched, api_errors, started, True)
            await sleep(min(poll_s, remaining))

    def _summary(self, states, unmatched, api_errors, started, deadline_exceeded):
        owned = {}
        for name in sorted(states):
            state = states[name]
            # At the overall deadline a delete we could not confirm reads
            # as unconfirmed, never as closed.
            status = state.status
            if deadline_exceeded and status == "delete-requested":
                status = "delete-unconfirmed"
            owned[name] = {
                "status": status,
                "closure": state.closure,
                "delete_error": state.delete_error,
                "seen_at": None
                if state.seen_at is None
                else round(state.seen_at - started, 1),
                "delete_requested_at": None
                if state.delete_requested_at is None
                else round(state.delete_requested_at - started, 1),
            }
        return {
            "owned": owned,
            "unmatched": sorted(unmatched),
            "api_errors": list(api_errors),
            "all_owned_closed": bool(states)
            and all(s.status == "verified-closed" for s in states.values()),
            "deadline_exceeded": deadline_exceeded,
        }
