"""Offline regression tests for trial corrections 2 and 4.

Correction 2: the dev trial disables provider redials via the pinned
SDK's ``conn_options`` (``APIConnectOptions(max_retry=0)``).
Correction 4: room-deletion failures carry content-free diagnostics
(exception type + symbolic SDK code, never message content).

Fast in-process tests use namespace stubs (same pattern as
test_voice_agent_dev.py, duplicated here to avoid restructuring it).
Real-SDK behavior runs in fresh subprocesses: no network, no worker,
no room — the fake Live client never leaves the process.
"""

import asyncio
import logging
import os
import pathlib
import subprocess
import sys
import types

import pytest

livekit_agents = pytest.importorskip(
    "livekit.agents",
    reason="voice draft needs livekit-agents (local .venv only, not requirements.lock)",
)

import voice_agent_dev  # noqa: E402
from voice_agent_dev import (  # noqa: E402
    GOOGLE_API_KEY_ENV,
    _delete_trial_room,
    build_realtime_model,
)

BACKEND_DIR = pathlib.Path(voice_agent_dev.__file__).parent


def _install_google_realtime_stub(monkeypatch, captured):
    """Copied stand-in for the pinned plugin namespace (see
    test_voice_agent_dev.py): proves our constructor call shape
    without the real SDK."""

    class FakeRealtimeModel:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def session(self):
            # A real RealtimeModel has this factory (the dev worker
            # wraps it with the connection guard); the stub only
            # records constructor kwargs.
            raise AssertionError("stub model must not create a provider session")

    realtime_mod = types.ModuleType("livekit.plugins.google.beta.realtime")
    realtime_mod.RealtimeModel = FakeRealtimeModel
    for name in (
        "livekit.plugins",
        "livekit.plugins.google",
        "livekit.plugins.google.beta",
    ):
        if name not in sys.modules or sys.modules[name] is None:
            monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(
        sys.modules, "livekit.plugins.google.beta.realtime", realtime_mod
    )
    # Shadow the attribute binding too: once the real plugin has been
    # imported in-process, `from ...beta import realtime` resolves via
    # the parent attribute without consulting sys.modules. raising=False
    # keeps this usable when the real package was never imported here.
    monkeypatch.setattr(
        sys.modules["livekit.plugins.google.beta"], "realtime", realtime_mod, raising=False
    )


def _run_case(script, timeout_s=120):
    env = dict(os.environ)
    env.pop("GOOGLE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    return proc


def _result_lines(proc):
    assert proc.returncode == 0, f"case crashed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr[-2000:]}"
    values = {}
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            key, _, value = line[len("RESULT "):].partition("=")
            values[key.strip()] = value.strip()
    return values


def test_realtime_model_disables_provider_retries(monkeypatch):
    # The dev trial must not redial the provider: conn_options carries
    # max_retry=0 through our constructor call shape.
    captured = {}
    _install_google_realtime_stub(monkeypatch, captured)
    monkeypatch.setenv(GOOGLE_API_KEY_ENV, "dummy-offline-key")
    build_realtime_model()
    assert captured["conn_options"].max_retry == 0


def test_real_model_stores_zero_retry_option():
    # The pinned SDK accepts and retains our value (guards against the
    # kwarg being swallowed or renamed by the plugin). Real class,
    # dummy key, offline construction only — no session, no network.
    proc = _run_case(
        "import os\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "import voice_agent_dev as v\n"
        "model = v.build_realtime_model()\n"
        "print('RESULT cls=' + type(model).__name__)\n"
        "print('RESULT max_retry=' + str(model._opts.conn_options.max_retry))\n"
    )
    values = _result_lines(proc)
    assert values["cls"] == "RealtimeModel"
    assert values["max_retry"] == "0"


def test_connect_failure_makes_no_second_attempt():
    # Established session whose first provider send fails: with
    # max_retry=0 the real session task must surface
    # APIConnectionError after exactly one connection — no redial.
    # (Pre-change defaults make 1+3 attempts with backoff sleeps.)
    proc = _run_case(
        "import asyncio\n"
        "import os\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "from types import SimpleNamespace\n"
        "import voice_agent_dev as v\n"
        "class FakeSession:\n"
        "    async def send_client_content(self, turns=None, turn_complete=True):\n"
        "        raise RuntimeError('boom-send-established')\n"
        "    async def receive(self):\n"
        "        while True:\n"
        "            await asyncio.sleep(3600)\n"
        "        yield\n"
        "    async def close(self):\n"
        "        return None\n"
        "class FakeConn:\n"
        "    def __init__(self, counter):\n"
        "        self.counter = counter\n"
        "    async def __aenter__(self):\n"
        "        self.counter[0] += 1\n"
        "        return FakeSession()\n"
        "    async def __aexit__(self, *args):\n"
        "        return False\n"
        "class FakeLive:\n"
        "    def __init__(self, counter):\n"
        "        self.counter = counter\n"
        "    def connect(self, model=None, config=None):\n"
        "        return FakeConn(self.counter)\n"
        "async def main():\n"
        "    model = v.build_realtime_model()\n"
        "    sess = model.session()\n"
        "    sess._chat_ctx.add_message(role='user', content=['hello'])\n"
        "    counter = [0]\n"
        "    sess._client = SimpleNamespace(aio=SimpleNamespace(live=FakeLive(counter)))\n"
        "    task = sess._main_atask\n"
        "    try:\n"
        "        await asyncio.wait_for(task, timeout=20)\n"
        "    except BaseException as error:\n"
        "        print('RESULT terminal=' + type(error).__name__)\n"
        "    print('RESULT connects=' + str(counter[0]))\n"
        "asyncio.run(main())\n"
    )
    values = _result_lines(proc)
    assert values["connects"] == "1"
    assert values["terminal"] == "APIConnectionError"


# Correction 3: one provider connection per trial session. The fake
# transport is injected at ``genai.Client`` so the guard under test
# stays in the path (replacing the session's client afterwards would
# remove it).
_CONNECTION_SCRIPT = """
import asyncio
import os
os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'
from types import SimpleNamespace

import livekit.plugins.google.beta.realtime.realtime_api as ra

SCENARIO = {scenario!r}
GUARDED = {guarded!r}
COUNTER = [0]


class FakeSession:
    async def send_client_content(self, turns=None, turn_complete=True):
        # Initial chat replay uses turn_complete=False and succeeds;
        # the established send path (via _msg_ch, turn_complete=True)
        # is what the send-fails case exercises (realtime_api _send_task,
        # which marks restart instead of raising).
        if SCENARIO == 'send-fails' and turn_complete:
            raise RuntimeError('established-send-failure')
        return None

    async def receive(self):
        if SCENARIO == 'receive-fails':
            raise RuntimeError('established-receive-failure')
        await asyncio.sleep(3600)
        yield

    async def close(self):
        return None


class FakeConn:
    async def __aenter__(self):
        COUNTER[0] += 1
        return FakeSession()

    async def __aexit__(self, *args):
        return False


class FakeLive:
    def connect(self, model=None, config=None):
        return FakeConn()


ra.genai.Client = lambda **kwargs: SimpleNamespace(
    aio=SimpleNamespace(live=FakeLive())
)


def build(guarded):
    if guarded:
        import voice_agent_dev as v

        return v.build_realtime_model()
    from livekit.agents.types import APIConnectOptions
    from livekit.plugins.google.beta import realtime

    import voice_agent_dev as v

    return realtime.RealtimeModel(
        model=v.REALTIME_MODEL_ID,
        voice=v.REALTIME_VOICE,
        instructions=v.AGENT_INSTRUCTIONS,
        conn_options=APIConnectOptions(max_retry=0),
    )


async def main():
    session = build(GUARDED).session()
    if SCENARIO == 'send-fails':
        # Trigger the established _send_task via _msg_ch, not the
        # initial _chat_ctx replay (realtime_api.py initial send uses
        # turn_complete=False and succeeds with this fake).
        session.generate_reply()
    else:
        # Give the session something to send, so the initial replay
        # succeeds and the receive path is exercised.
        session._chat_ctx.add_message(role='user', content=['hello'])
    try:
        await asyncio.wait_for(asyncio.shield(session._main_atask), timeout=0.6)
    except asyncio.TimeoutError:
        print('RESULT still-running=true', flush=True)
    except BaseException as error:
        print('RESULT terminal=' + type(error).__name__, flush=True)
    print('RESULT connects=' + str(COUNTER[0]), flush=True)


asyncio.run(main())
"""


def _connection_case(scenario, guarded):
    return _result_lines(
        _run_case(
            _CONNECTION_SCRIPT.format(scenario=scenario, guarded=guarded)
        )
    )


@pytest.mark.parametrize("scenario", ["send-fails", "receive-fails"])
def test_established_failure_never_dials_the_provider_again(scenario):
    # max_retry=0 is not enough on its own: the pinned SDK swallows an
    # established send/receive failure and reconnects in a tight loop
    # without consulting it. The trial path must still end after one
    # connection, with the SDK's own terminal error.
    values = _connection_case(scenario, guarded=True)
    assert values["connects"] == "1", values
    assert values["terminal"] == "APIConnectionError", values


def test_normal_startup_keeps_receive_loop_alive():
    # The guard must not break the ordinary path: one connection, the
    # receive loop still running, no error raised. Claims connection
    # plus receive-loop liveness only, not frame delivery.
    values = _connection_case("healthy", guarded=True)
    assert values["connects"] == "1", values
    assert values["still-running"] == "true", values
    assert values.get("terminal") is None, values


def test_unguarded_sdk_would_reconnect_repeatedly():
    # Why the guard exists, pinned so nobody removes it believing
    # max_retry=0 is enough: with the same fake transport and the same
    # established receive failure, an unguarded model dials again and
    # again inside the same 0.6 s window.
    values = _connection_case("receive-fails", guarded=False)
    assert int(values["connects"]) > 5, values


def test_connection_guard_permits_only_the_first_attempt():
    # The guard in isolation: the wrapped live object is called once
    # and never again, and unrelated attributes still pass through.
    from voice_connection_guard import (
        ProviderReconnectBlocked,
        allow_single_provider_connection,
    )

    class FakeLive:
        def __init__(self):
            self.calls = 0
            self.marker = "passthrough"

        def connect(self, *args, **kwargs):
            self.calls += 1
            return "context-manager"

    class FakeAio:
        def __init__(self, live):
            self.live = live

    class FakeClient:
        def __init__(self, live):
            self.aio = FakeAio(live)
            self.other = "kept"

    class FakeSession:
        def __init__(self):
            self.live = FakeLive()
            self._client = FakeClient(self.live)

    class FakeModel:
        def __init__(self):
            self.sessions = []

        def session(self):
            session = FakeSession()
            self.sessions.append(session)
            return session

    model = allow_single_provider_connection(FakeModel())
    session = model.session()
    live = session._client.aio.live
    assert live.connect() == "context-manager"
    assert session.live.calls == 1
    assert live.marker == "passthrough"
    assert session._client.other == "kept"
    with pytest.raises(ProviderReconnectBlocked):
        live.connect()
    assert session.live.calls == 1, "the second attempt must not reach the client"


class _FakeApiError(Exception):
    """Twirp-style SDK error shape: symbolic code plus a message that
    must never reach logs."""

    def __init__(self, message, code):
        super().__init__(message)
        self.code = code


class _FailingDeleteCtx:
    """JobContext stand-in whose delete path raises on demand."""

    def __init__(self, room_name, failure):
        self.room_name = room_name
        self._failure = failure

    def delete_room(self):
        raise self._failure


class _FailingAwaitDeleteCtx:
    """delete_room() returns an awaitable that raises when awaited."""

    def __init__(self, room_name, failure):
        self.room_name = room_name
        self._failure = failure

    def delete_room(self):
        async def _raise():
            raise self._failure

        return _raise()


def test_deletion_request_failure_logs_code_not_content(caplog):
    canary = "CANARY-PROVIDER-TEXT-MUST-NOT-LEAK"
    ctx = _FailingDeleteCtx("test-room", _FakeApiError(canary, "not_found"))
    with caplog.at_level(logging.WARNING, logger="think-partner-dev"):
        asyncio.run(_delete_trial_room(ctx, "test-room"))
    assert canary not in caplog.text
    assert "not_found" in caplog.text
    assert "FakeApiError" in caplog.text


def test_deletion_result_failure_logs_code_not_content(caplog):
    canary = "CANARY-AWAIT-TEXT-MUST-NOT-LEAK"
    ctx = _FailingAwaitDeleteCtx("test-room", _FakeApiError(canary, "unavailable"))
    with caplog.at_level(logging.WARNING, logger="think-partner-dev"):
        asyncio.run(_delete_trial_room(ctx, "test-room"))
    assert canary not in caplog.text
    assert "unavailable" in caplog.text
    assert "FakeApiError" in caplog.text


def test_deletion_failure_without_code_logs_type_only(caplog):
    canary = "CANARY-PLAIN-TEXT-MUST-NOT-LEAK"
    ctx = _FailingDeleteCtx("test-room", RuntimeError(canary))
    with caplog.at_level(logging.WARNING, logger="think-partner-dev"):
        asyncio.run(_delete_trial_room(ctx, "test-room"))
    assert canary not in caplog.text
    assert "RuntimeError" in caplog.text


def test_deletion_failure_logs_no_unrecognized_code(caplog):
    # Shape matching is not recognition: a token-shaped value on an
    # error's ``code`` attribute is not one of the SDK's own error
    # codes, so it must not be logged at all.
    canary_code = "AIzaSyA1B2C3D4E5F6G7H8I9J0KLMNOPQRSTU"
    ctx = _FailingDeleteCtx("test-room", _FakeApiError("CANARY", canary_code))
    with caplog.at_level(logging.WARNING, logger="think-partner-dev"):
        asyncio.run(_delete_trial_room(ctx, "test-room"))
    assert canary_code not in caplog.text
    assert "code=" not in caplog.text
    assert "FakeApiError" in caplog.text
