"""Single provider connection for the supervised dev trial.

Why: ``APIConnectOptions(max_retry=0)`` only bounds the path where a
connection attempt RAISES (livekit-plugins-google 1.2.9
``realtime_api.py`` checks it in its exception handler). An ESTABLISHED
session that fails to send or receive does not raise there: the task
swallows the error, asks for a restart, and the ``while`` loop opens
another connection immediately — no backoff, no retry counter. Offline
against the pinned wheels that produced 3,787 connect attempts in 1.5
seconds with ``max_retry`` already 0.

The dev trial must not be able to dial the provider again by itself, so
this guard caps the session at ONE connection: the first
``live.connect()`` observes counters while retaining the provider session
and delegating context cleanup, and any later attempt
raises before a socket is opened. With ``max_retry=0`` the pinned SDK
turns that into a terminal ``APIConnectionError`` instead of a redial.

Private-interface reliance, verified against the pinned wheels
(livekit-agents 1.2.12, livekit-plugins-google 1.2.9, google-genai):
``RealtimeModel.session()`` is the plugin's public factory (the only
thing ``agent_activity`` calls) but the guard reaches through
``RealtimeSession._client`` to the genai client's ``aio.live``. In
1.2.9 ``self._client`` is read at exactly one place — the
``async with self._client.aio.live.connect(...)`` in ``_main_task`` —
so this covers the plugin's whole use of the client. Everything is
attached to the one model instance the trial builds: no class, module,
or process-wide patching, and no installed file is modified.
"""

from __future__ import annotations

from voice_provider_diagnostics import ProviderDiagnostics
from voice_google_audio import audio_input_connection


class ProviderReconnectBlocked(RuntimeError):
    """Raised instead of a second automatic provider connection."""


class _SingleConnectLive:
    """``client.aio.live`` stand-in that permits one connect call."""

    def __init__(self, live, diagnostics):
        self._live = live
        self.diagnostics = diagnostics
        self.attempts = 0

    def connect(self, *args, **kwargs):
        self.attempts += 1
        self.diagnostics.emit("connection_attempted")
        try:
            if self.attempts > 1:
                raise ProviderReconnectBlocked(
                    "dev trial permits one provider connection; "
                    "an automatic reconnect was refused"
                )
            return audio_input_connection(
                self.diagnostics.connection(self._live.connect(*args, **kwargs))
            )
        except BaseException as error:
            self.diagnostics.emit("connection_failed", error)
            raise

    def __getattr__(self, name):
        return getattr(self._live, name)


class _SingleConnectAio:
    """``client.aio`` stand-in exposing the guarded ``live``."""

    def __init__(self, aio, live):
        self._aio = aio
        self.live = live

    def __getattr__(self, name):
        return getattr(self._aio, name)


class _SingleConnectClient:
    """``RealtimeSession._client`` stand-in; forwards everything else."""

    def __init__(self, client, live):
        self._client = client
        self.aio = _SingleConnectAio(client.aio, live)

    def __getattr__(self, name):
        return getattr(self._client, name)


def allow_single_provider_connection(model):
    """Cap every session of ``model`` at one provider connection.

    Returns the same model with its ``session()`` factory wrapped, so
    the caller keeps a normal ``RealtimeModel`` (model, voice and
    instructions untouched) and the guard is installed before the
    session's main task first runs.
    """
    create_session = model.session

    def _guarded_session():
        session = create_session()
        diagnostics = ProviderDiagnostics()
        diagnostics.attach_input(session)
        session._client = _SingleConnectClient(
            session._client, _SingleConnectLive(session._client.aio.live, diagnostics)
        )
        return session

    model.session = _guarded_session
    return model
