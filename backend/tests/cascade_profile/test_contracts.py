"""Candidate-only SDK contracts (SDD §§4/6/8/11); no server/provider startup.

Native discovery skips this profile. Its CI job first enforces the exact pins;
denial precedes SDK imports here, independent of pytest/conftest or credentials.
"""
import asyncio
import importlib.metadata as metadata
import io
import logging
import os
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
from tests.network_block import deny_outbound
deny_outbound()
import voice_cascade_config as config

KEYS = {name: "dummy" for name in (
    "GOOGLE_API_KEY", "SARVAM_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")}


class CandidateContracts(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        try:
            config.check_profile()
        except RuntimeError as error:
            raise unittest.SkipTest("requires isolated candidate profile") from error

    async def asyncSetUp(self):
        self.root = logging.getLogger()
        self.previous, self.level = self.root.handlers[:], self.root.level
        self.sink = logging.StreamHandler(io.StringIO())
        config.protect_handlers((self.sink,), "contract-probe")
        self.root.handlers[:] = [self.sink]
        self.root.setLevel(logging.INFO)
        config.initialize_plugins()

    async def asyncTearDown(self):
        self.root.handlers[:] = self.previous
        self.root.setLevel(self.level)
        self.sink.close()

    async def test_committed_profile_matches_every_installed_runtime_pin(self):
        pins = (BACKEND / "requirements-voice-cascade.lock").read_text(encoding="utf-8")
        for line in pins.splitlines():
            if line and not line.startswith("#"):
                package, version = line.split("==")
                self.assertEqual(metadata.version(package), version, package)
        self.assertTrue(all(f"{name}=={value}" in pins for name, value in config.PINS.items()))

    async def test_real_factory_forces_recording_off_and_closes_its_components(self):
        from livekit.agents import AgentSession
        from livekit.plugins import google, sarvam
        with patch.dict(os.environ, KEYS, clear=True):
            session = await config.build_session()
        try:
            self.assertIsInstance(session.stt, sarvam.STTRealtime)
            self.assertIsInstance(session.llm, google.LLM)
            self.assertIsInstance(session.tts, sarvam.TTS)
            self.assertEqual(session.conn_options.max_unrecoverable_errors, 0)
            for name in ("stt_conn_options", "llm_conn_options", "tts_conn_options"):
                self.assertEqual(getattr(session.conn_options, name).max_retry, 0)
            with patch.object(AgentSession, "start", new=AsyncMock()) as start:
                await session.start(None, record=True, capture_run=True, session_host=True)
            self.assertEqual(start.call_args.kwargs,
                             dict(record=False, capture_run=False, session_host=False))
        finally:
            await asyncio.wait_for(session.aclose(), 5)
        await asyncio.wait_for(session.aclose(), 5)

    async def test_close_attempts_all_owners_and_retry_only_the_failed_owner(self):
        from livekit.agents import AgentSession
        from voice_cascade_session import CascadeSession
        for failure in (ValueError("CANARY-close"), asyncio.CancelledError("CANARY-cancel")):
            owners = [SimpleNamespace(aclose=AsyncMock()) for _ in range(3)]
            session = CascadeSession(llm=owners[0], tts=owners[1], stt=owners[2], vad=None)
            close = AsyncMock(side_effect=[failure, None])
            with patch.object(AgentSession, "aclose", new=close):
                with self.assertRaises(type(failure)) as caught:
                    await session.aclose()
                self.assertIs(caught.exception, failure)
                for owner in owners:
                    owner.aclose.assert_awaited_once()
                await session.aclose()
            self.assertEqual(close.await_count, 2)
            for owner in owners:
                owner.aclose.assert_awaited_once()

    async def test_partial_construction_cleanup_preserves_primary_or_cancellation(self):
        from livekit.plugins import google, sarvam
        import voice_cascade_session as adapter
        for failure in (ValueError("CANARY-constructor"), asyncio.CancelledError("CANARY-cancel")):
            owners = [SimpleNamespace(aclose=AsyncMock()) for _ in range(3)]
            with patch.dict(os.environ, KEYS, clear=True), \
                 patch.object(sarvam, "STTRealtime", return_value=owners[0]), \
                 patch.object(sarvam, "TTS", return_value=owners[1]), \
                 patch.object(google, "LLM", return_value=owners[2]), \
                 patch.object(adapter, "CascadeSession", side_effect=failure):
                with self.assertRaises(type(failure)) as caught:
                    await config.build_session()
            self.assertIs(caught.exception, failure)
            for owner in owners:
                owner.aclose.assert_awaited_once()

    async def test_entrypoint_refusal_and_audio_only_setup_keep_single_cleanup(self):
        from livekit import rtc
        from livekit.agents import JobContext
        from livekit.agents.voice.events import CloseEvent, CloseReason
        import voice_cascade_dev as dev
        calls, forwarded = [], []
        room = rtc.EventEmitter()
        room.name, room.isconnected = "contract-room", lambda: True
        ctx = SimpleNamespace(room=room, connect=AsyncMock(side_effect=lambda: calls.append("connect")),
                              delete_room=AsyncMock(side_effect=lambda: calls.append("delete")),
                              shutdown=lambda reason: calls.append(reason), _shutdown_callbacks=[])
        ctx.add_shutdown_callback = lambda callback: JobContext.add_shutdown_callback(ctx, callback)
        with patch.dict(os.environ, {**KEYS, "GOOGLE_API_KEY": ""}, clear=True):
            with self.assertRaises(RuntimeError):
                await dev.entrypoint(ctx, handlers=(self.sink,))
        self.assertEqual(calls, ["dev trial prereq missing"])
        calls.clear()

        class Session(rtc.EventEmitter):
            async def start(self, agent, **kwargs):
                forwarded.append(kwargs)
                self.emit("close", CloseEvent(reason=CloseReason.USER_INITIATED))

            async def aclose(self):
                calls.append("close")

        with patch.dict(os.environ, KEYS, clear=True), \
             patch.object(config, "build_session", new=AsyncMock(return_value=Session())):
            await dev.entrypoint(ctx, handlers=(self.sink,))
        self.assertEqual(calls, ["connect", "close", "delete", "dev trial call ended"])
        inputs, outputs = forwarded[0]["room_input_options"], forwarded[0]["room_output_options"]
        self.assertEqual((inputs.audio_enabled, inputs.video_enabled, inputs.text_enabled,
                          inputs.close_on_disconnect, inputs.delete_room_on_close),
                         (True, False, False, True, False))
        self.assertEqual((outputs.audio_enabled, outputs.transcription_enabled, outputs.sync_transcription),
                         (True, False, False))
        self.assertFalse(forwarded[0]["capture_run"])

    async def test_public_server_wiring_and_real_job_request_use_single_admission(self):
        from livekit.agents import AgentServer, JobRequest
        from livekit.protocol import agent, models
        import voice_cascade_launch as launch
        observed, decisions = [], []
        register = AgentServer.rtc_session

        def bind(instance, func=None, **kwargs):
            observed.append((func, kwargs))
            return register(instance, func, **kwargs)

        with patch.dict(os.environ, KEYS, clear=True), patch.object(AgentServer, "rtc_session", new=bind):
            options = launch.cascade.prepare_worker((self.sink,))
            self.assertEqual(options.agent_name, "think-partner-dev")
            server = launch.prepare_server((self.sink,), 45)
        self.assertIsInstance(server, AgentServer)
        # Constructor only; never run a server or invent pre-run aclose behavior.
        callback = observed[0][1]["on_request"]
        for job_id in ("first", "second"):
            job = agent.Job(id=job_id, agent_name="think-partner-dev", room=models.Room(name="contract-room"))
            request = JobRequest(job=job, on_accept=AsyncMock(side_effect=lambda _: decisions.append("accept")),
                                 on_reject=AsyncMock(side_effect=lambda _: decisions.append("reject")))
            await callback(request)
        self.assertEqual(decisions, ["accept", "reject"])


if __name__ == "__main__":
    config.check_profile()  # direct invocation must not silently skip a wrong profile
    unittest.main()
