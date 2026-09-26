"""Offline review tests for the dev-only voice agent — no network, no model.

Everything here runs against the installed livekit-agents 1.2.12.
The realtime provider plugin may be present in the local venv;
construction paths that need it stay deterministic by forcing absence
via monkeypatch or stubbing the pinned ``beta`` namespace, so results
hold with the plugin both present and absent.
"""

import asyncio
import os
import pathlib
import sys
import types

import pytest

livekit_agents = pytest.importorskip(
    "livekit.agents",
    reason="voice draft needs livekit-agents (local .venv only, not requirements.lock)",
)

import voice_agent_dev
from voice_agent_dev import (
    AGENT_INSTRUCTIONS,
    AGENT_NAME,
    GOOGLE_API_KEY_ENV,
    REALTIME_MODEL_ID,
    REALTIME_VOICE,
    build_realtime_model,
    build_room_input_options,
    build_room_output_options,
    build_worker_options,
    entrypoint,
)

JS_AGENT_NAME = "think-partner-dev"  # must match VOICE_AGENT_NAME (mobile/lib/voice-config.ts)


def test_agent_name_matches_phone_dispatch_contract():
    assert AGENT_NAME == JS_AGENT_NAME
    assert AGENT_NAME == "think-partner-dev"


def test_realtime_model_reports_missing_plugin_without_secrets(monkeypatch):
    # Deterministic whether or not the optional plugin is installed:
    # force the pinned `beta` import to fail, then construction must
    # refuse with an actionable, secret-free message.
    monkeypatch.setitem(sys.modules, "livekit.plugins.google.beta", None)
    monkeypatch.delenv(GOOGLE_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError) as excinfo:
        build_realtime_model()
    message = str(excinfo.value)
    assert "livekit-plugins-google" in message
    assert GOOGLE_API_KEY_ENV == "GOOGLE_API_KEY"
    assert "GOOGLE_API_KEY" in message or "plugin" in message


def _install_google_realtime_stub(monkeypatch, captured):
    """Stub the pinned plugin namespace (offline stand-in, NOT the real SDK).

    Proves our call shape (model/voice/instructions kwargs). The real
    1.2.9 RealtimeModel signature acceptance is verified separately
    against the installed wheel (see pinned-instructions test) — server
    acceptance still needs the live trial.
    """

    class FakeRealtimeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    realtime_mod = types.ModuleType("livekit.plugins.google.beta.realtime")
    realtime_mod.RealtimeModel = FakeRealtimeModel
    monkeypatch.setitem(
        sys.modules, "livekit.plugins.google.beta.realtime", realtime_mod
    )
    for name in (
        "livekit.plugins",
        "livekit.plugins.google",
        "livekit.plugins.google.beta",
    ):
        if name not in sys.modules or sys.modules[name] is None:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))


def test_realtime_model_reports_missing_key_without_value(monkeypatch):
    # Plugin import succeeds (stubbed) but no key is set: must refuse by
    # env-var NAME, never echoing a value.
    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.delenv(GOOGLE_API_KEY_ENV, raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        build_realtime_model()
    assert os.environ.get(GOOGLE_API_KEY_ENV) is None
    assert captured == {}


def test_realtime_model_uses_shared_instructions(monkeypatch):
    # The model must receive the single AGENT_INSTRUCTIONS source, with
    # the spec model id and voice — verified through the stubbed
    # constructor kwargs.
    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    build_realtime_model()
    assert captured["model"] == REALTIME_MODEL_ID
    assert captured["voice"] == REALTIME_VOICE
    assert captured["instructions"] == AGENT_INSTRUCTIONS


def test_google_key_env_name_only():
    # The test asserts on the variable NAME so a real key value can never
    # appear in an assertion or failure dump.
    assert GOOGLE_API_KEY_ENV == "GOOGLE_API_KEY"


def test_room_input_is_audio_only_with_cleanup():
    opts = build_room_input_options()
    assert opts.audio_enabled is True
    assert opts.video_enabled is False
    assert opts.text_enabled is False
    assert opts.close_on_disconnect is True
    # Single deletion owner: the SDK must NOT issue its own delete on
    # session close (it only queues an un-awaited task); our entrypoint
    # awaits the one explicit ctx.delete_room() instead. Leaving this
    # True would issue duplicate deletes per close in production.
    assert opts.delete_room_on_close is False


def test_closing_started_session_issues_exactly_one_delete(monkeypatch):
    # A started session that ends (phone End here) must produce exactly
    # one awaited delete: no SDK-owned second request, no missing owner.
    # Note: these fakes run no SDK RoomIO, so the "no second request"
    # half rests on delete_room_on_close=False plus the installed
    # room_io source (which only deletes when that flag is True); the
    # fake run proves the one explicit ctx.delete_room() is awaited.
    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _trigger_after_listen():
            await asyncio.sleep(0.02)
            ctx.room.trigger_disconnect()

        trigger = asyncio.create_task(_trigger_after_listen())
        await entrypoint(ctx, time_limit_s=120.0)
        await trigger
        return ctx, sessions[0]

    ctx, session = asyncio.run(_run())
    assert session.aclose_calls == 1
    assert ctx.delete_room_calls == [ctx.room.name]
    assert len(ctx.delete_room_calls) == 1, "exactly one delete per closed session"


def test_room_output_disables_transcripts():
    opts = build_room_output_options()
    assert opts.audio_enabled is True
    assert opts.transcription_enabled is False
    assert opts.sync_transcription is False


def test_worker_is_named_explicit_dispatch_only():
    # Explicit dispatch only: agent_name pins this worker. No
    # concurrency limit is claimed here — LiveKit load_threshold is a
    # CPU-load availability signal, not a single-job admission
    # mechanism (see WorkerOptions docs in livekit-agents 1.2.12).
    worker = build_worker_options()
    assert worker.agent_name == AGENT_NAME
    assert worker.load_threshold != 1.0, (
        "must not pin load_threshold=1.0 as a single-job claim"
    )


def test_source_contains_no_recording_or_upload_wiring():
    source = pathlib.Path(voice_agent_dev.__file__).read_text(encoding="utf-8")
    for banned in (
        "egress",
        "Egress",
        "set_tracer_provider",
        "transcription_enabled=True",
        "sync_transcription=True",
        "video_enabled=True",
        "capture_run=True",
    ):
        assert banned not in source, banned
    assert "transcription_enabled=False" in source
    assert "sync_transcription=False" in source


def test_instructions_are_voice_only_and_nonempty():
    assert len(AGENT_INSTRUCTIONS) > 50
    lowered = AGENT_INSTRUCTIONS.lower()
    assert "no camera" in lowered
    assert "voice-only" in lowered
    assert "hinglish" in lowered


def test_model_id_is_the_spec_candidate():
    # Spec names Gemini 3.8 Live; Google changelog 2026-09-15 confirms
    # 'gemini-3.8-live' GA. The pinned plugin passes any model string
    # through (verified in the 1.2.9 wheel source), so the ID is
    # selected explicitly here. Runtime acceptance still needs the
    # live trial.
    assert REALTIME_MODEL_ID == "gemini-3.8-live"


def test_realtime_import_targets_the_pinned_beta_namespace():
    # livekit-plugins-google==1.2.9 ships realtime under
    # livekit/plugins/google/beta/realtime (wheel source); the
    # top-level path belongs to newer releases and must not be used
    # with this pin.
    source = pathlib.Path(voice_agent_dev.__file__).read_text(encoding="utf-8")
    assert "from livekit.plugins.google.beta import realtime" in source
    assert "from livekit.plugins.google import realtime" not in source


def test_old_preview_default_is_not_selected():
    source = pathlib.Path(voice_agent_dev.__file__).read_text(encoding="utf-8")
    assert 'REALTIME_MODEL_ID = "gemini-2.5' not in source


class _FakeRoom:
    name = "test-room"

    def __init__(self):
        self._disconnect_cbs = []
        self.off_calls = []
        # Real rtc.Room does NOT replay a past disconnect to a late
        # listener: a listener registered after the disconnect never
        # fires. Model that here via an explicit connected flag instead
        # of invoking the callback inside on().
        self._connected = True

    def isconnected(self):
        return self._connected

    def on(self, event, callback=None):
        assert event == "disconnected"
        if callback is not None:
            self._disconnect_cbs.append(callback)
        return callback

    def off(self, event, callback):
        self.off_calls.append(event)
        if callback in self._disconnect_cbs:
            self._disconnect_cbs.remove(callback)

    def trigger_disconnect(self):
        self._connected = False
        for cb in list(self._disconnect_cbs):
            cb("remote-disconnect")
        self._disconnect_cbs = []


class _FakeCtx:
    """Offline JobContext stand-in: records connect/shutdown/delete, no network."""

    def __init__(self):
        self.room = _FakeRoom()
        self.connect_calls = 0
        self.shutdown_calls = []
        self.delete_room_calls = []

    async def connect(self):
        self.connect_calls += 1

    def shutdown(self, reason=""):
        self.shutdown_calls.append(reason)

    def delete_room(self):
        self.delete_room_calls.append(self.room.name)
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        fut.set_result(None)
        return fut


class _FakeSession:
    """Offline AgentSession stand-in: records start kwargs and aclose.

    ``aclose`` is async here exactly like the real 1.2.12 method
    (source-verified coroutine): its body — and hence the call count —
    only runs when awaited, so asserting the count proves awaiting,
    not merely calling.
    """

    def __init__(
        self, llm=None, fail_start=False, fail_aclose=False, hang_aclose=False
    ):
        self.llm = llm
        self.fail_start = fail_start
        self.fail_aclose = fail_aclose
        self.hang_aclose = hang_aclose
        self.agent = None
        self.start_kwargs = None
        self.aclose_calls = 0
        self._close_cbs = []
        self.close_off_calls = []

    async def start(self, agent, **kwargs):
        self.agent = agent
        self.start_kwargs = kwargs
        if self.fail_start:
            raise RuntimeError("boom-start")
        return None

    async def aclose(self):
        self.aclose_calls += 1
        if self.hang_aclose:
            await asyncio.sleep(5.0)
        if self.fail_aclose:
            raise RuntimeError("boom-close")

    def on(self, event, callback=None):
        # Minimal EventEmitter surface the entrypoint uses ("close").
        # The real AgentSession emits "close" when it shuts down,
        # including participant-triggered closes via _close_soon.
        assert event == "close"
        if callback is not None:
            self._close_cbs.append(callback)
        return callback

    def off(self, event, callback):
        assert event == "close"
        self.close_off_calls.append(event)
        if callback in self._close_cbs:
            self._close_cbs.remove(callback)

    def emit_close(self, event="session-closed"):
        for cb in list(self._close_cbs):
            cb(event)
        self._close_cbs = []


def test_entrypoint_releases_room_when_model_build_fails(monkeypatch):
    # Failure BEFORE any session exists: connect happened, so shutdown
    # must release the room connection and the error must propagate.
    ctx = _FakeCtx()

    def _boom():
        raise RuntimeError("no plugin (forced)")

    # Prereq gate must pass so the test reaches model construction.
    # Stubbed (not ambient) so this holds with the plugin present or absent.
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "build_realtime_model", _boom)
    with pytest.raises(RuntimeError, match="no plugin"):
        asyncio.run(entrypoint(ctx))
    assert ctx.connect_calls == 1
    assert ctx.shutdown_calls == ["dev trial setup failed"]


def test_entrypoint_closes_partly_started_session_when_start_fails(monkeypatch):
    # Failure AFTER the session object exists: the partly started
    # session must be awaited-closed AND the room connection released.
    # The stub's aclose is a coroutine like the real one, so
    # aclose_calls == 1 proves it was awaited (an un-awaited coroutine
    # body never runs).
    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm, fail_start=True)
        sessions.append(session)
        return session

    # Prereq gate must pass so the test reaches session start.
    # Stubbed (not ambient) so this holds with the plugin present or absent.
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(
        voice_agent_dev, "build_realtime_model", lambda: object()
    )
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    with pytest.raises(RuntimeError, match="boom-start"):
        asyncio.run(entrypoint(ctx))
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.connect_calls == 1
    assert ctx.shutdown_calls == ["dev trial setup failed"]


def test_entrypoint_shutdown_runs_when_aclose_fails(monkeypatch):
    # Cleanup failure must not mask the original setup error: aclose
    # is awaited (call count proves it) even though it raises, shutdown
    # still releases the room, and the original boom-start — not the
    # boom-close — reaches the caller.
    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm, fail_start=True, fail_aclose=True)
        sessions.append(session)
        return session

    # Prereq gate must pass so the test reaches session start.
    # Stubbed (not ambient) so this holds with the plugin present or absent.
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")

    monkeypatch.setattr(
        voice_agent_dev, "build_realtime_model", lambda: object()
    )
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    with pytest.raises(RuntimeError, match="boom-start"):
        asyncio.run(entrypoint(ctx))
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.connect_calls == 1
    assert ctx.shutdown_calls == ["dev trial setup failed"]


def test_entrypoint_phone_end_closes_session_and_disables_capture(
    monkeypatch,
):
    # Bounded-call contract: when the room ends (phone End), entrypoint
    # returns after await-closing the session and releasing the room —
    # it never leaves a session running. capture_run=False is still
    # passed explicitly rather than relying on the SDK default.
    # Realistic: the disconnect fires AFTER the wait listener is
    # registered (no replay for late listeners).
    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _trigger_after_listen():
            await asyncio.sleep(0.02)
            ctx.room.trigger_disconnect()

        trigger = asyncio.create_task(_trigger_after_listen())
        await entrypoint(ctx)
        await trigger
        return ctx, sessions[0]

    ctx, session = asyncio.run(_run())
    assert session.aclose_calls == 1
    assert len(ctx.shutdown_calls) == 1
    assert ctx.shutdown_calls[0] == "dev trial call ended"
    assert len(ctx.delete_room_calls) == 1, "room deletion must be awaited"
    assert session.start_kwargs["capture_run"] is False
    assert session.start_kwargs["room"] is ctx.room
    assert session.agent.instructions == AGENT_INSTRUCTIONS


def test_entrypoint_cancellation_during_connect_releases_room(monkeypatch):
    import asyncio as _asyncio

    ctx = _FakeCtx()
    orig_connect = ctx.connect

    async def _cancelled():
        raise _asyncio.CancelledError("cancel-connect")

    ctx.connect = _cancelled  # type: ignore[method-assign]
    # Prereq gate must pass so the test reaches connect.
    # Stubbed (not ambient) so this holds with the plugin present or absent.
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    with monkeypatch.context() as m:
        m.setattr(voice_agent_dev, "build_realtime_model", lambda: object())
        try:
            asyncio.run(entrypoint(ctx))
        except BaseException as exc:
            assert isinstance(exc, _asyncio.CancelledError)
        else:
            raise AssertionError("CancelledError must propagate")
    assert ctx.shutdown_calls == ["dev trial cancelled"]


def test_entrypoint_cancellation_during_start_closes_session(monkeypatch):
    import asyncio as _asyncio

    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm)
        orig_start = session.start

        async def _cancelled_start(agent, **kwargs):
            raise _asyncio.CancelledError("cancel-start")

        session.start = _cancelled_start  # type: ignore[method-assign]
        sessions.append(session)
        return session

    # Prereq gate must pass so the test reaches session start.
    # Stubbed (not ambient) so this holds with the plugin present or absent.
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")

    monkeypatch.setattr(
        voice_agent_dev, "build_realtime_model", lambda: object()
    )
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    try:
        asyncio.run(entrypoint(ctx))
    except BaseException as exc:
        assert isinstance(exc, _asyncio.CancelledError)
    else:
        raise AssertionError("CancelledError must propagate")
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial cancelled"]


def test_entrypoint_refuses_to_join_when_plugin_missing(monkeypatch):
    # Provider config must be verified BEFORE ctx.connect(): with the
    # plugin absent, no room may be joined and the refusal must name
    # the missing piece without values. Every refused job still
    # finalizes via ctx.shutdown() so the worker does not warn about
    # a job that neither connected nor shut down.
    monkeypatch.setitem(sys.modules, "livekit.plugins.google.beta", None)
    monkeypatch.delenv(GOOGLE_API_KEY_ENV, raising=False)
    ctx = _FakeCtx()
    with pytest.raises(RuntimeError, match="livekit-plugins-google"):
        asyncio.run(entrypoint(ctx))
    assert ctx.connect_calls == 0, "must not join a room without provider config"
    assert ctx.shutdown_calls == ["dev trial prereq missing"]


def test_entrypoint_refuses_to_join_when_key_missing(monkeypatch):
    # Plugin importable (stubbed) but no key: same pre-connect refusal,
    # naming only the variable name. Shutdown still finalizes the job.
    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.delenv(GOOGLE_API_KEY_ENV, raising=False)
    ctx = _FakeCtx()
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        asyncio.run(entrypoint(ctx))
    assert ctx.connect_calls == 0, "must not join a room without provider config"
    assert ctx.shutdown_calls == ["dev trial prereq missing"]
    assert captured == {}


def _run_entrypoint_with_successful_start(monkeypatch, ctx, time_limit_s):
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm)
        sessions.append(session)
        return session

    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    asyncio.run(entrypoint(ctx, time_limit_s=time_limit_s))
    assert len(sessions) == 1
    return ctx, sessions[0]


def test_entrypoint_time_limit_closes_session_and_room(monkeypatch):
    # The dev call is bounded: when the limit expires with the room
    # still up, the Gemini session is awaited-closed and the room
    # deletion is awaited (bounded) — and the timeout is a normal end,
    # not an error. Phone mic release on the resulting disconnect is
    # NOT proven offline.
    ctx = _FakeCtx()
    _, session = _run_entrypoint_with_successful_start(
        monkeypatch, ctx, time_limit_s=0.05
    )
    assert ctx.connect_calls == 1
    assert session.aclose_calls == 1, "timeout must await-close the session"
    assert ctx.shutdown_calls == ["dev trial time limit reached"]
    assert len(ctx.delete_room_calls) == 1, "timeout must await room deletion"


def test_entrypoint_phone_end_before_limit_closes_session(monkeypatch):
    # Phone Ends first (room disconnects before the limit): entrypoint
    # returns promptly and still closes the session and releases the job.
    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _trigger_after_listen():
            await asyncio.sleep(0.02)
            ctx.room.trigger_disconnect()

        trigger = asyncio.create_task(_trigger_after_listen())
        await entrypoint(ctx, time_limit_s=120.0)
        await trigger
        return ctx, sessions[0]

    ctx, session = asyncio.run(_run())
    assert session.aclose_calls == 1
    assert len(ctx.shutdown_calls) == 1
    assert ctx.shutdown_calls[0] == "dev trial call ended"
    assert len(ctx.delete_room_calls) == 1
    assert ctx.room.off_calls == ["disconnected"], "listener must be removed"


def test_entrypoint_detects_disconnect_before_listener(monkeypatch):
    # Real rooms do not replay a past disconnect to a late listener.
    # If the room drops between session.start and wait-listener
    # registration, entrypoint must end promptly as a normal call end,
    # not wait out the full time limit.
    import time as _time

    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm)

        orig_start = session.start

        async def _start_and_drop(agent, **kwargs):
            await orig_start(agent, **kwargs)
            ctx.room.trigger_disconnect()

        session.start = _start_and_drop  # type: ignore[method-assign]
        sessions.append(session)
        return session

    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    start = _time.monotonic()
    asyncio.run(entrypoint(ctx, time_limit_s=0.4))
    elapsed = _time.monotonic() - start
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial call ended"], (
        "pre-listener disconnect is a normal end, not a timeout"
    )
    assert elapsed < 0.3, f"must not wait full limit, took {elapsed:.3f}s"


def test_entrypoint_deadline_includes_setup(monkeypatch):
    # A hanging setup (connect) must be interrupted by the overall
    # deadline: no session is started and the job ends as a timeout.
    import time as _time

    ctx = _FakeCtx()
    sessions = []

    async def _slow_connect():
        ctx.connect_calls += 1
        await asyncio.sleep(0.3)

    ctx.connect = _slow_connect  # type: ignore[method-assign]

    def _make_session(llm=None):
        session = _FakeSession(llm=llm)
        sessions.append(session)
        return session

    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    start = _time.monotonic()
    asyncio.run(entrypoint(ctx, time_limit_s=0.05))
    elapsed = _time.monotonic() - start
    assert sessions == [], "timed-out setup must not start a session"
    assert ctx.shutdown_calls == ["dev trial time limit reached"]
    assert elapsed < 0.25, f"setup must be interrupted, took {elapsed:.3f}s"


def test_entrypoint_cleanup_is_bounded_when_aclose_hangs(monkeypatch):
    # One awaited, bounded cleanup path: a hanging aclose must not hang
    # the job forever.
    monkeypatch.setattr(voice_agent_dev, "CLEANUP_TIMEOUT_S", 0.05)
    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm, hang_aclose=True)
        sessions.append(session)
        return session

    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    import time as _time

    start = _time.monotonic()
    asyncio.run(entrypoint(ctx, time_limit_s=0.05))
    elapsed = _time.monotonic() - start
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial time limit reached"]
    assert len(ctx.delete_room_calls) == 1
    assert elapsed < 1.0, f"cleanup must be bounded, took {elapsed:.3f}s"


def test_entrypoint_cancellation_during_wait_propagates(monkeypatch):
    # Cancelling the wait must propagate CancelledError (not convert to
    # timeout) after finalizing the job.
    import asyncio as _asyncio

    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
        task = _asyncio.create_task(entrypoint(ctx, time_limit_s=120.0))
        await _asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except BaseException as exc:
            assert isinstance(exc, _asyncio.CancelledError)
        else:
            raise AssertionError("CancelledError must propagate")
        assert len(sessions) == 1
        assert sessions[0].aclose_calls == 1
        assert ctx.shutdown_calls == ["dev trial cancelled"]
        return ctx

    asyncio.run(_run())


def test_pinned_realtime_model_accepts_instructions():
    # Corrects the stale "cannot be proven" note: the installed
    # livekit-plugins-google==1.2.9 RealtimeModel signature accepts an
    # instructions keyword (verified here). Server acceptance of
    # gemini-3.8-live still needs the live trial.
    import inspect as _inspect

    realtime = pytest.importorskip(
        "livekit.plugins.google.beta.realtime",
        reason="pinned google plugin required for this check",
    )
    sig = _inspect.signature(realtime.RealtimeModel.__init__)
    assert "instructions" in sig.parameters


def test_phone_end_closes_session_without_room_disconnect(monkeypatch):
    # A human Phone End must terminate the job promptly even when the
    # agent room stays connected: the SDK closes the session itself on
    # participant disconnect (close_on_disconnect), so the entrypoint
    # waits for the AgentSession "close" event too. No room
    # "disconnected" event is faked here — the room stays connected.
    import time as _time

    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _participant_end_after_start():
            await asyncio.sleep(0.02)
            assert ctx.room.isconnected(), "room must stay connected in this test"
            sessions[0].emit_close()

        trigger = asyncio.create_task(_participant_end_after_start())
        start = _time.monotonic()
        await entrypoint(ctx, time_limit_s=0.4)
        elapsed = _time.monotonic() - start
        await trigger
        return ctx, sessions[0], elapsed

    ctx, session, elapsed = asyncio.run(_run())
    assert ctx.room.isconnected(), "room never disconnected"
    assert session.aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial call ended"], (
        "participant-triggered session close is a normal end, not a timeout"
    )
    assert len(ctx.delete_room_calls) == 1, "single delete owner retained"
    assert session.close_off_calls == ["close"], "session listener removed"
    assert elapsed < 0.3, f"must end promptly, took {elapsed:.3f}s"


def test_connect_timeout_error_is_setup_failure_not_deadline(monkeypatch):
    # A TimeoutError raised BY connect/start well before the deadline is
    # a setup failure: it must be preserved and logged as such, not
    # mistaken for the worker deadline expiring.
    ctx = _FakeCtx()

    async def _timeout_connect():
        ctx.connect_calls += 1
        raise TimeoutError("boom-connect-timeout")

    ctx.connect = _timeout_connect  # type: ignore[method-assign]
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    with pytest.raises(TimeoutError, match="boom-connect-timeout"):
        asyncio.run(entrypoint(ctx, time_limit_s=120.0))
    assert ctx.shutdown_calls == ["dev trial setup failed"]
    assert len(ctx.delete_room_calls) == 1


def test_start_timeout_error_is_setup_failure_not_deadline(monkeypatch):
    ctx = _FakeCtx()
    sessions = []

    def _make_session(llm=None):
        session = _FakeSession(llm=llm)

        async def _timeout_start(agent, **kwargs):
            session.agent = agent
            session.start_kwargs = kwargs
            raise TimeoutError("boom-start-timeout")

        session.start = _timeout_start  # type: ignore[method-assign]
        sessions.append(session)
        return session

    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)
    with pytest.raises(TimeoutError, match="boom-start-timeout"):
        asyncio.run(entrypoint(ctx, time_limit_s=120.0))
    assert len(sessions) == 1
    assert sessions[0].aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial setup failed"]
    assert len(ctx.delete_room_calls) == 1


def test_dev_call_time_limit_is_two_minutes():
    # The bound appropriate for the later <=2-minute trial, in one place.
    assert voice_agent_dev.CALL_TIME_LIMIT_S == 120.0


def test_sdk_timeout_is_setup_failure_while_scope_unexpired(monkeypatch):
    # Unexpired branch only: when the timeout scope has NOT expired, a
    # TimeoutError raised BY connect/start is a setup failure — preserved,
    # logged as such, and never mistaken for deadline expiry. A
    # never-expiring scope stands in for the window where the SDK error
    # wins just before the deadline fires. The mirror case (the scope
    # itself expired) is covered separately with a real asyncio.timeout
    # in test_expired_deadline_wins_when_connect_converts_cancel_to_timeout.
    import asyncio as _asyncio

    class _NeverExpiringTimeout:
        def __init__(self, delay):
            self._delay = delay

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def expired(self):
            return False

    monkeypatch.setattr(
        voice_agent_dev.asyncio, "timeout", _NeverExpiringTimeout
    )
    ctx = _FakeCtx()

    async def _late_timeout_connect():
        ctx.connect_calls += 1
        await _asyncio.sleep(0.15)
        raise TimeoutError("boom-late-sdk-timeout")

    ctx.connect = _late_timeout_connect  # type: ignore[method-assign]
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    with pytest.raises(TimeoutError, match="boom-late-sdk-timeout"):
        asyncio.run(entrypoint(ctx, time_limit_s=0.05))
    assert ctx.shutdown_calls == ["dev trial setup failed"]
    assert len(ctx.delete_room_calls) == 1


def test_expired_deadline_wins_when_connect_converts_cancel_to_timeout(
    monkeypatch,
):
    # Mirror case, with the REAL asyncio.timeout (not a stub): the
    # deadline fires, connect() catches the resulting cancellation and
    # converts it into its own TimeoutError — the shape an SDK timeout
    # takes when it swallows the cancel. Because the scope itself
    # expired, that is reported as a DEADLINE, not a setup failure: the
    # call ends gracefully (nothing raised) with the time-limit reason,
    # and cleanup still runs exactly once. Pinned deliberately: it
    # documents that the scope, not the error's origin, decides.
    ctx = _FakeCtx()

    async def _convert_cancel_to_timeout():
        ctx.connect_calls += 1
        try:
            await asyncio.sleep(5.0)
        except asyncio.CancelledError:
            raise TimeoutError("sdk-timeout-from-cancelled-await")

    ctx.connect = _convert_cancel_to_timeout  # type: ignore[method-assign]
    _install_google_realtime_stub(monkeypatch, {})
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    # No exception may escape: an expired deadline is a graceful end.
    asyncio.run(entrypoint(ctx, time_limit_s=0.05))
    assert ctx.connect_calls == 1
    assert ctx.shutdown_calls == ["dev trial time limit reached"]
    assert len(ctx.delete_room_calls) == 1, "exactly one room deletion"


def test_session_close_reason_error_is_failure_not_success(monkeypatch):
    # A session "close" carrying CloseReason.ERROR is a provider/model
    # failure: cleanup still runs once, but the job must raise with
    # content-free metadata (reason + error type only), never report a
    # successful call end. The fake error message below is canary text
    # that must NOT leak into the raised error.
    class _CanaryError(Exception):
        pass

    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _error_close_after_start():
            await asyncio.sleep(0.02)
            sessions[0].emit_close(
                types.SimpleNamespace(
                    reason="error",
                    error=_CanaryError("CANARY-CONTENT-MUST-NOT-LEAK"),
                )
            )

        trigger = asyncio.create_task(_error_close_after_start())
        with pytest.raises(RuntimeError) as excinfo:
            await entrypoint(ctx, time_limit_s=120.0)
        await trigger
        return ctx, sessions[0], excinfo.value

    ctx, session, raised = asyncio.run(_run())
    assert session.aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial session error"]
    assert len(ctx.delete_room_calls) == 1
    assert session.close_off_calls == ["close"], "session listener removed"
    message = str(raised)
    assert "CANARY-CONTENT-MUST-NOT-LEAK" not in message
    assert "_CanaryError" in message


def test_session_close_reason_participant_disconnect_is_normal_end(
    monkeypatch,
):
    # A session "close" carrying the participant-disconnected reason
    # (the SDK's own close_on_disconnect path on a human Phone End) is
    # a normal end even though the room never emitted "disconnected".
    async def _run():
        ctx = _FakeCtx()
        sessions = []

        def _make_session(llm=None):
            session = _FakeSession(llm=llm)
            sessions.append(session)
            return session

        captured = {}
        _install_google_realtime_stub(monkeypatch, captured)
        monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
        monkeypatch.setattr(voice_agent_dev, "AgentSession", _make_session)

        async def _participant_end_after_start():
            await asyncio.sleep(0.02)
            sessions[0].emit_close(
                types.SimpleNamespace(
                    reason="participant_disconnected", error=None
                )
            )

        trigger = asyncio.create_task(_participant_end_after_start())
        await entrypoint(ctx, time_limit_s=120.0)
        await trigger
        return ctx, sessions[0]

    ctx, session = asyncio.run(_run())
    assert session.aclose_calls == 1
    assert ctx.shutdown_calls == ["dev trial call ended"]
    assert len(ctx.delete_room_calls) == 1
