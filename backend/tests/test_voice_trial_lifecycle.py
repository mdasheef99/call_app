"""Shared trial seam: admission, construction ordering and awaited cleanup.

SDD §§5/6/9/11; Spec P02. Existing ctx/session fakes perform no network.
The native worker's unchanged suite covers deadline, cancellation and error-close.
"""
import asyncio
import importlib
import importlib.util
from types import SimpleNamespace

import pytest

pytest.importorskip("livekit.agents")
from tests.test_voice_agent_dev import _FakeCtx, _FakeSession


def _run_trial():
    assert importlib.util.find_spec("voice_trial_lifecycle") is not None, (
        "shared trial lifecycle seam is not available"
    )
    return importlib.import_module("voice_trial_lifecycle").run_trial


def _factories(build_session):
    return dict(
        check_prerequisites=lambda: None,
        build_session=build_session,
        build_agent=object,
        build_room_input_options=object,
        build_room_output_options=object,
    )


def test_shared_admission_refuses_before_connect_or_construction():
    run = _run_trial()
    ctx = _FakeCtx()
    failure = RuntimeError("synthetic missing prerequisite")

    def refuse():
        raise failure

    def forbidden():
        raise AssertionError("factory ran before admission")

    factories = _factories(forbidden)
    factories["check_prerequisites"] = refuse
    with pytest.raises(RuntimeError) as caught:
        asyncio.run(run(ctx, **factories))
    assert caught.value is failure
    assert ctx.connect_calls == 0
    assert ctx.delete_room_calls == []
    assert ctx.shutdown_calls == ["dev trial prereq missing"]


def test_shared_factory_starts_after_connect_and_keeps_early_close():
    run = _run_trial()
    ctx = _FakeCtx()
    agent, input_options, output_options = object(), object(), object()

    class EarlyClose(_FakeSession):
        async def start(self, agent, **kwargs):
            await super().start(agent, **kwargs)
            self.emit_close(SimpleNamespace(reason="user_initiated", error=None))

    async def exercise():
        session = EarlyClose()

        def construct():
            assert ctx.connect_calls == 1
            return session

        factories = _factories(construct)
        factories.update(build_agent=lambda: agent,
                         build_room_input_options=lambda: input_options,
                         build_room_output_options=lambda: output_options)
        await run(ctx, **factories)
        return session

    session = asyncio.run(exercise())
    assert session.agent is agent
    assert session.start_kwargs == dict(room=ctx.room, room_input_options=input_options,
                                       room_output_options=output_options, capture_run=False)
    assert session.aclose_calls == 1
    assert session.close_off_calls == ["close"]
    assert ctx.room.off_calls == ["disconnected"]
    assert ctx.delete_room_calls == ["test-room"]
    assert ctx.shutdown_calls == ["dev trial call ended"]


def test_shared_factory_failure_deletes_once_and_preserves_exception():
    run = _run_trial()
    ctx = _FakeCtx()
    failure = ValueError("synthetic constructor failure")

    def fail():
        raise failure

    with pytest.raises(ValueError) as caught:
        asyncio.run(run(ctx, **_factories(fail)))
    assert caught.value is failure
    assert ctx.connect_calls == 1
    assert ctx.delete_room_calls == ["test-room"]
    assert ctx.shutdown_calls == ["dev trial setup failed"]


def test_async_factory_is_awaited_after_connect_and_uses_the_same_cleanup():
    run, ctx = _run_trial(), _FakeCtx()

    class EarlyClose(_FakeSession):
        async def start(self, agent, **kwargs):
            await super().start(agent, **kwargs)
            self.emit_close(SimpleNamespace(reason="user_initiated", error=None))

    async def exercise():
        session = EarlyClose()

        async def construct():
            assert ctx.connect_calls == 1
            await asyncio.sleep(0)
            return session

        await run(ctx, **_factories(construct))
        return session

    session = asyncio.run(exercise())
    assert session.aclose_calls == 1
    assert ctx.delete_room_calls == ["test-room"]
    assert ctx.shutdown_calls == ["dev trial call ended"]


def test_async_factory_failure_keeps_original_error_and_room_cleanup(caplog):
    run, ctx = _run_trial(), _FakeCtx()
    failure = ValueError("synthetic async constructor failure")

    async def fail():
        await asyncio.sleep(0)
        raise failure

    with pytest.raises(ValueError) as caught:
        asyncio.run(run(ctx, **_factories(fail)))
    assert caught.value is failure
    assert ctx.delete_room_calls == ["test-room"]
    assert ctx.shutdown_calls == ["dev trial setup failed"]
    assert "session cleanup failed" not in caplog.text  # no session was constructed


def test_async_factory_cancellation_has_no_false_session_cleanup(caplog):
    run, ctx = _run_trial(), _FakeCtx()

    async def exercise():
        entered = asyncio.Event()

        async def construct():
            entered.set()
            await asyncio.Future()

        task = asyncio.create_task(run(ctx, **_factories(construct)))
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert ctx.delete_room_calls == ["test-room"]
    assert ctx.shutdown_calls == ["dev trial cancelled"]
    assert "session cleanup failed" not in caplog.text


@pytest.mark.parametrize("phase", ["prerequisite", "setup", "timeout"])
def test_native_failures_do_not_log_error_or_cause_content(phase, caplog):
    run, ctx = _run_trial(), _FakeCtx()
    failure = TimeoutError("CANARY-error") if phase == "timeout" else ValueError("CANARY-error")
    cause = RuntimeError("CANARY-cause")

    def fail():
        raise failure from cause

    factories = _factories(fail)
    if phase == "prerequisite":
        factories["check_prerequisites"] = fail
    with pytest.raises(type(failure)) as caught:
        asyncio.run(run(ctx, **factories))
    assert caught.value is failure and failure.__cause__ is cause
    assert "CANARY" not in caplog.text
    assert type(failure).__name__ in caplog.text
    assert all(record.exc_info is None for record in caplog.records)
