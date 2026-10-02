"""Pinned-SDK probe reusing the existing transport fakes, with outbound I/O denied."""
import json
import logging

import pytest

from .test_voice_trial_corrections import _CONNECTION_SCRIPT, _run_case


def test_native_sdk_redaction_preserves_original_records_and_cause_chain():
    import sys
    import voice_provider_diagnostics
    for name in ("livekit.plugins.google", "livekit.agents"):
        records, logger = [], logging.getLogger(name)

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = Capture()
        logger.addHandler(handler)
        try:
            try:
                raise ValueError("CANARY-cause")
            except ValueError as cause:
                raise RuntimeError("CANARY-error") from cause
        except RuntimeError as error:
            original = logging.LogRecord(name, logging.ERROR, "sdk.py", 1,
                                         "CANARY-message", (), sys.exc_info())
            original.payload = "CANARY-extra"
            logging.Formatter().format(original)
            saved = dict(original.__dict__)
            logger.handle(original)
            logger.removeHandler(handler)
            assert original.__dict__ == saved
            assert original.exc_info[1] is error and str(error.__cause__) == "CANARY-cause"
            assert records and records[0] is not original
            assert "CANARY" not in str(records[0].__dict__)
            assert "RuntimeError" in records[0].getMessage()

_PROBE = r"""
import logging, socket
from livekit import rtc
from google.genai import errors, types
CASE = '__CASE__'
CANARY = 'CANARY-CONTENT-NEVER-LOG'
CODES = {'close': 1000, 'reject': 429, 'bool-code': True, 'big-code': 99999, 'text-code': CANARY}
ERROR = errors.APIError(CODES[CASE], {'message': CANARY}) if CASE in CODES else RuntimeError(CANARY)
CANCEL = asyncio.CancelledError(CANARY)
frames, media, responses, exits, closed = [], [], [], [], []
sent, delivered, finished, iterator_closed = (asyncio.Event() for _ in range(4))
class Handler(logging.Handler):
    def emit(self, record):
        if record.msg == 'voice_provider_diag %s':
            print('DIAG ' + record.getMessage().split(' ', 1)[1], flush=True)
log = logging.getLogger('think-partner-dev')
log.setLevel(logging.INFO)
log.addHandler(Handler())
original_push = ra.RealtimeSession.push_audio
original_event = ra.RealtimeSession._send_client_event
original_generation = ra.RealtimeSession._is_new_generation
def push(self, frame):
    frames.append(frame)
    return original_push(self, frame)
def event(self, value):
    if isinstance(value, types.LiveClientRealtimeInput):
        media.extend(value.media_chunks or [])
    return original_event(self, value)
def generation(self, response):
    responses.append(response)
    return original_generation(self, response)
ra.RealtimeSession.push_audio = push
ra.RealtimeSession._send_client_event = event
ra.RealtimeSession._is_new_generation = generation
response = types.LiveServerMessage(server_content=types.LiveServerContent(
    model_turn=types.Content(parts=[
        types.Part(text=CANARY),
        types.Part(inline_data=types.Blob(data=b'\0' * 960, mime_type='audio/pcm')),
    ]), turn_complete=CASE != 'partial',
    input_transcription=types.Transcription(text=CANARY, finished=CASE != 'partial')))
async def send(self, **kwargs):
    if CASE == 'cancel' or CASE in CODES:
        raise CANCEL if CASE == 'cancel' else ERROR
    assert kwargs['audio'].data is media[0].data, 'submitted PCM bytes identity changed'
    assert kwargs['audio'].mime_type == 'audio/pcm;rate=16000'
    sent.set()
    return response
async def receive(self):
    try:
        if CASE == 'cancel' or CASE in CODES:
            raise CANCEL if CASE == 'cancel' else ERROR
        yield response
        delivered.set()
        await finished.wait()
    finally:
        closed.append('iterator')
        iterator_closed.set()
async def close(self):
    closed.append('provider')
    finished.set()
async def enter(self):
    COUNTER[0] += 1
    if CASE == 'connect-fails':
        raise ERROR
    return FakeSession()
async def exit(self, *args):
    exits.append(args)
    return False
FakeSession.send_realtime_input = send
FakeSession.receive = receive
FakeSession.close = close
FakeConn.__aenter__ = enter
FakeConn.__aexit__ = exit
async def probe():
    try:
        socket.getaddrinfo('offline-test.invalid', 443)
        raise AssertionError('network denial missing')
    except RuntimeError:
        pass
    with socket.socket() as sock:
        try:
            sock.connect(('203.0.113.1', 443))
        except RuntimeError:
            pass
        else:
            raise AssertionError('outbound socket denial missing')
    if CASE == 'cancel' or CASE in CODES:
        from voice_connection_guard import _SingleConnectLive
        from voice_provider_diagnostics import ProviderDiagnostics
        async with _SingleConnectLive(FakeLive(), ProviderDiagnostics()).connect() as provider:
            for operation in (provider.send_realtime_input(), anext(provider.receive())):
                try:
                    await operation
                except BaseException as error:
                    assert error is (CANCEL if CASE == 'cancel' else ERROR), 'error identity changed'
            raise CANCEL if CASE == 'cancel' else ERROR
    session = build(True).session()
    if CASE == 'connect-fails':
        try:
            await asyncio.wait_for(session._main_atask, 2)
        except Exception as error:
            assert type(error).__name__ == 'APIConnectionError'
            assert error.__cause__ is ERROR
        else:
            raise AssertionError('connection failure swallowed')
    else:
        frame = rtc.AudioFrame.create(16000, 1, 800)
        session.push_audio(frame)
        await asyncio.wait_for(sent.wait(), 2)
        await asyncio.wait_for(delivered.wait(), 2)
        assert frames == [frame] and frames[0] is frame
        assert responses[0] is response, 'provider response identity changed'
        await session.aclose()
        await asyncio.wait_for(iterator_closed.wait(), 2)
        assert closed.count('iterator') == 1 and 'provider' in closed
        assert len(exits) == 1, 'connection context cleanup changed'
        assert COUNTER[0] == 1

try:
    asyncio.run(probe())
except BaseException as error:
    assert (CASE == 'cancel' or CASE in CODES) and error is (CANCEL if CASE == 'cancel' else ERROR)
    assert exits[0][1] is error and closed == ['iterator'] and COUNTER[0] == 1
print('RESULT preserved=true', flush=True)
"""


@pytest.mark.parametrize("case", ["flow", "partial", "connect-fails", "cancel",
                                 "close", "reject", "bool-code", "big-code", "text-code"])
def test_diagnostics_preserve_the_pinned_audio_path(case):
    script = _CONNECTION_SCRIPT.format(scenario="healthy", guarded=True)
    script = script.rsplit("asyncio.run(main())", 1)[0] + _PROBE.replace("__CASE__", case)
    proc = _run_case(script)
    assert proc.returncode == 0, proc.stderr[-2000:]
    assert "RESULT preserved=true" in proc.stdout
    assert "CANARY-CONTENT-NEVER-LOG" not in proc.stdout + proc.stderr
    assert "Traceback (most recent call last)" not in proc.stdout + proc.stderr
    records = [json.loads(line[5:]) for line in proc.stdout.splitlines() if line.startswith("DIAG ")]
    assert records, "missing diagnostics"
    allowed = {"id", "timestamp", "event", "error_type", "error_code", "input_frames",
               "submitted_chunks", "submitted_bytes", "returned_chunks", "returned_bytes"}
    assert all(set(record) <= allowed and isinstance(record["timestamp"], float) for record in records)
    assert len({record["id"] for record in records}) == 1
    events = [record["event"] for record in records]
    assert "connection_attempted" in events
    if case in ("flow", "partial"):
        assert "connection_opened" in events
        assert ("turn_complete" in events) is (case == "flow")
        assert ("input_transcription_finished" if case == "flow" else "input_transcription") in events
        final = records[-1]
        assert (final["input_frames"], final["submitted_chunks"], final["submitted_bytes"]) == (1, 1, 1600)
        assert (final["returned_chunks"], final["returned_bytes"]) == (1, 960)
    elif case == "connect-fails":
        assert "connection_opened" not in events
        assert records[-1]["error_type"] == "RuntimeError"
    else:
        assert "send_failed" in events and "receive_failed" in events
        expected_type = "CancelledError" if case == "cancel" else "APIError"
        assert any(record.get("error_type") == expected_type for record in records)
        expected_code = {"close": 1000, "reject": 429}.get(case)
        assert all(record.get("error_code") == expected_code for record in records if "error_type" in record)
