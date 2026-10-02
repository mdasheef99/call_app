"""Offline Google wire contract (Specification §7.1); no provider calls."""
import asyncio
import base64
import json
from types import SimpleNamespace

import pytest
pytest.importorskip("google.genai", reason="optional voice-development dependencies")
from google.genai import live, types

from voice_google_audio import audio_input_connection
from voice_connection_guard import _SingleConnectLive, ProviderReconnectBlocked
from voice_provider_diagnostics import ProviderDiagnostics


class Sink:
    def __init__(self):
        self.messages = []

    async def send(self, text):
        self.messages.append(json.loads(text))


class Context:
    def __init__(self, provider):
        self.provider, self.exits = provider, []

    async def __aenter__(self):
        return self.provider

    async def __aexit__(self, *args):
        self.exits.append(args)
        return False


def test_pcm_uses_audio_field_and_explicit_rate_without_mutating_source():
    async def run():
        sink = Sink()
        provider = live.AsyncSession(SimpleNamespace(vertexai=False), sink)
        original_send = provider.send_realtime_input
        blob = types.Blob(data=b"\x00\x01" * 800, mime_type="audio/pcm")
        context = Context(provider)
        connector = _SingleConnectLive(SimpleNamespace(connect=lambda: context), ProviderDiagnostics())
        async with connector.connect() as wrapped:
            assert wrapped is provider
            await wrapped.send_realtime_input(media=blob)
            await wrapped.send_realtime_input(activity_end=types.ActivityEnd())
            await wrapped.send_realtime_input(media=types.Blob(data=b"image", mime_type="image/jpeg"))
            await wrapped.send_realtime_input(audio=blob)
        payload = sink.messages[0]["realtime_input"]
        assert set(payload) == {"audio"}
        assert payload["audio"]["mimeType"] == "audio/pcm;rate=16000"
        assert payload["audio"]["data"] == base64.b64encode(blob.data).decode()
        assert blob.mime_type == "audio/pcm"
        assert "activityEnd" in sink.messages[1]["realtime_input"]
        assert "mediaChunks" in sink.messages[2]["realtime_input"]
        assert sink.messages[3]["realtime_input"]["audio"]["mimeType"] == "audio/pcm"
        assert provider.send_realtime_input == original_send
        assert len(context.exits) == 1
        with pytest.raises(ProviderReconnectBlocked):
            connector.connect()
    asyncio.run(run())


@pytest.mark.parametrize("error_type", [RuntimeError, asyncio.CancelledError])
def test_audio_wrapper_preserves_bytes_error_identity_and_context_cleanup(error_type):
    async def run():
        error = error_type("synthetic")
        blob = types.Blob(data=b"pcm", mime_type="audio/pcm")
        async def send(**kwargs):
            assert kwargs["audio"].data is blob.data
            raise error
        provider = SimpleNamespace(send_realtime_input=send)
        context = Context(provider)
        with pytest.raises(error_type) as raised:
            async with audio_input_connection(context) as wrapped:
                await wrapped.send_realtime_input(media=blob)
        assert raised.value is error
        assert context.exits[0][1] is error
        assert provider.send_realtime_input is send
    asyncio.run(run())
