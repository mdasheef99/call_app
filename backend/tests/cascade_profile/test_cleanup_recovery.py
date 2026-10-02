"""SDD §§6/8/11: failed cascade owners survive until job shutdown cleanup.

Real entrypoint/lifecycle/ownership and SDK callback registration; external
provider construction, RoomIO and close effects use controlled doubles only.
"""
import asyncio
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.network_block import deny_outbound
deny_outbound()
from tests.cascade_profile import test_contracts as contracts
import voice_cascade_config as config


class Owner:
    def __init__(self, failures=()):
        self.failures = list(failures)
        self.calls, self.closed = 0, False

    async def aclose(self):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        self.closed = True


async def start_and_end(session, agent, **kwargs):
    from livekit.agents.voice.events import CloseEvent, CloseReason
    session.emit("close", CloseEvent(reason=CloseReason.USER_INITIATED))


class CleanupRecovery(unittest.IsolatedAsyncioTestCase):
    setUpClass = classmethod(contracts.CandidateContracts.setUpClass.__func__)
    asyncSetUp = contracts.CandidateContracts.asyncSetUp
    asyncTearDown = contracts.CandidateContracts.asyncTearDown

    def context(self):
        from livekit import rtc
        from livekit.agents import JobContext
        room = rtc.EventEmitter()
        room.name, room.isconnected = "cleanup-room", lambda: True
        calls = []
        ctx = SimpleNamespace(room=room, connect=AsyncMock(), delete_room=AsyncMock(),
                              shutdown=lambda reason: calls.append(reason), _shutdown_callbacks=[])
        ctx.add_shutdown_callback = MethodType(JobContext.add_shutdown_callback, ctx)
        return ctx, calls

    def providers(self, owners):
        from livekit.plugins import google, sarvam
        return (patch.dict("os.environ", contracts.KEYS, clear=True),
                patch.object(sarvam, "STTRealtime", return_value=owners[0]),
                patch.object(sarvam, "TTS", return_value=owners[1]),
                patch.object(google, "LLM", return_value=owners[2]))

    async def test_phone_end_retries_failed_owner_through_registered_shutdown(self):
        from livekit.agents import AgentSession
        import voice_cascade_dev as dev
        ctx, reasons = self.context()
        owners = [Owner(), Owner(), Owner([ValueError("CANARY-close")])]
        env, stt, tts, llm = self.providers(owners)
        with env, stt as s, tts as t, llm as l, \
             patch.object(AgentSession, "start", new=start_and_end), \
             patch.object(AgentSession, "aclose", new=AsyncMock()) as core:
            await dev.entrypoint(ctx, handlers=(self.sink,))
            self.assertFalse(owners[2].closed)
            self.assertEqual(len(ctx._shutdown_callbacks), 1, "failed cleanup lost its job retry")
            await ctx._shutdown_callbacks[0](reasons[0])
            self.assertTrue(all(owner.closed for owner in owners))
            self.assertEqual([owner.calls for owner in owners], [1, 1, 2])
            self.assertEqual(core.await_count, 1)
            self.assertEqual((s.call_count, t.call_count, l.call_count), (1, 1, 1))
        ctx.delete_room.assert_awaited_once()
        self.assertEqual(reasons, ["dev trial call ended"])

    async def test_partial_construction_retains_failed_owner_before_factory_returns(self):
        from livekit.plugins import google
        import voice_cascade_dev as dev
        ctx, reasons = self.context()
        owners = [Owner([ValueError("CANARY-close")]), Owner(), Owner()]
        failure = RuntimeError("CANARY-constructor")
        env, stt, tts, llm = self.providers(owners)
        with env, stt, tts, llm, patch.object(google, "LLM", side_effect=failure):
            with self.assertRaises(RuntimeError) as caught:
                await dev.entrypoint(ctx, handlers=(self.sink,))
            self.assertIs(caught.exception, failure)
            self.assertFalse(owners[0].closed)
            self.assertEqual(len(ctx._shutdown_callbacks), 1, "partial cleanup lost its job retry")
            await ctx._shutdown_callbacks[0](reasons[0])
        self.assertTrue(owners[0].closed and owners[1].closed)
        self.assertEqual([owner.calls for owner in owners], [2, 1, 0])
        ctx.delete_room.assert_awaited_once()
        self.assertEqual(reasons, ["dev trial setup failed"])

    async def test_shutdown_during_partial_cleanup_never_closes_one_owner_concurrently(self):
        from livekit.plugins import google
        import voice_cascade_dev as dev
        ctx, _ = self.context()
        owners = [Owner([ValueError("CANARY-close")]), Owner(), Owner()]
        entered, release = asyncio.Event(), asyncio.Event()
        original, attempts = owners[0].aclose, []

        async def held_close():
            attempts.append("close")
            if len(attempts) == 1:
                entered.set()
                await release.wait()
            await original()

        owners[0].aclose = held_close
        failure = RuntimeError("CANARY-constructor")
        env, stt, tts, llm = self.providers(owners)
        with env, stt, tts, llm, patch.object(google, "LLM", side_effect=failure):
            construction = asyncio.create_task(dev.entrypoint(ctx, handlers=(self.sink,)))
            shutdown = None
            try:
                await asyncio.wait_for(entered.wait(), 2)
                shutdown = asyncio.create_task(ctx._shutdown_callbacks[0]("operator stop"))
                for _ in range(5):
                    await asyncio.sleep(0)
                self.assertEqual(len(attempts), 1, "shutdown raced the initial close")
            finally:
                release.set()
                outcomes = await asyncio.gather(construction, *([shutdown] if shutdown else []),
                                                return_exceptions=True)
        self.assertIs(outcomes[0], failure)
        self.assertIsNone(outcomes[1])
        self.assertTrue(owners[0].closed and owners[1].closed)
        self.assertEqual([owner.calls for owner in owners], [2, 1, 0])
        ctx.delete_room.assert_awaited_once()

    async def test_shutdown_failure_and_cancellation_preserve_identity_and_failed_owner(self):
        from livekit.agents import AgentSession
        import voice_cascade_dev as dev
        for failure in (ValueError("CANARY-retry"), asyncio.CancelledError("CANARY-cancel")):
            with self.subTest(error=type(failure).__name__):
                ctx, _ = self.context()
                owners = [Owner(), Owner(), Owner([ValueError("CANARY-initial"), failure])]
                env, stt, tts, llm = self.providers(owners)
                with env, stt, tts, llm, patch.object(AgentSession, "start", new=start_and_end), \
                     patch.object(AgentSession, "aclose", new=AsyncMock()):
                    await dev.entrypoint(ctx, handlers=(self.sink,))
                    callback = ctx._shutdown_callbacks[0]
                    with self.assertRaises(type(failure)) as caught:
                        await callback("call ended")
                    self.assertIs(caught.exception, failure)
                    self.assertFalse(owners[2].closed)
                    await callback("explicit cleanup retry")
                self.assertTrue(all(owner.closed for owner in owners))
                self.assertEqual([owner.calls for owner in owners], [1, 1, 3])
                ctx.delete_room.assert_awaited_once()
                self.assertNotIn("CANARY", self.sink.stream.getvalue())
                self.assertIn(type(failure).__name__, self.sink.stream.getvalue())

    async def test_shutdown_retry_requests_cancellation_of_a_hanging_close(self):
        from livekit.agents import AgentSession
        import voice_cascade_dev as dev
        ctx, _ = self.context()
        owners = [Owner(), Owner(), Owner([ValueError("CANARY-initial")])]
        entered = asyncio.Event()

        async def held_close():
            entered.set()
            await asyncio.Future()

        env, stt, tts, llm = self.providers(owners)
        with env, stt, tts, llm, patch.object(AgentSession, "start", new=start_and_end), \
             patch.object(AgentSession, "aclose", new=AsyncMock()):
            await dev.entrypoint(ctx, handlers=(self.sink,))
            owners[2].aclose = held_close
            with patch.object(config, "CLEANUP_TIMEOUT_S", 0.01):
                task = asyncio.create_task(ctx._shutdown_callbacks[0]("call ended"))
                try:
                    await asyncio.wait_for(entered.wait(), 2)
                    with self.assertRaises(TimeoutError):
                        await asyncio.wait_for(asyncio.shield(task), 0.5)
                    self.assertTrue(task.done(), "only the test's timeout fired")
                finally:
                    if not task.done():
                        task.cancel()
                    await asyncio.gather(task, return_exceptions=True)
            self.assertFalse(owners[2].closed)


if __name__ == "__main__":
    config.check_profile()
    unittest.main()
