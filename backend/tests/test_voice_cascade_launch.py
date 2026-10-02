"""SDD §§3/6/8/11: one admission, explicit startup and protected cleanup.

Tests name the breaks: replenished reservation, unbound/repeated job entry,
implicit startup, leaked SDK error text and cleanup masking cancellation.
Network denial is installed by conftest before any SDK import.
"""
import asyncio
import importlib
import importlib.util
import io
import logging
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from types import SimpleNamespace
from unittest.mock import patch

KEYS = {name: "dummy" for name in (
    "GOOGLE_API_KEY", "SARVAM_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET")}


def launcher():
    assert importlib.util.find_spec("voice_cascade_launch") is not None, "controlled launcher missing"
    return importlib.import_module("voice_cascade_launch")


class Request:
    def __init__(self, *, name="think-partner-dev", job="job-a", room="room-a", hold=None, failure=None):
        self.agent_name, self.id, self.room = name, job, SimpleNamespace(name=room)
        self.hold, self.failure, self.calls = hold, failure, []
        self.entered = asyncio.Event()

    async def accept(self):
        self.calls.append("accept")
        self.entered.set()
        if self.hold is not None:
            await self.hold.wait()
        if self.failure is not None:
            raise self.failure

    async def reject(self):
        self.calls.append("reject")


class AdmissionCase(unittest.IsolatedAsyncioTestCase):
    async def test_protected_admission_log_drives_exact_room_cutoff(self):
        from trial_cutoff_guard import CutoffGuard, owned_rooms_from_dispatch_log
        from tests.test_trial_cutoff_guard import FakeClock, FakeRoomApi
        module, root, output = launcher(), logging.getLogger(), io.StringIO()
        previous, level = root.handlers[:], root.level
        sink = logging.StreamHandler(output)
        sink.setFormatter(logging.Formatter("%(correlation_id)s %(message)s"))
        module.config.protect_handlers((sink,), "trial-probe")
        root.handlers[:] = [sink]
        root.setLevel(logging.INFO)
        room = 'room-"quoted\\name'
        try:
            logging.getLogger("livekit.worker").info("CANARY-sdk", extra={"payload": "CANARY-extra"})
            gate = module.SingleTrial((sink,), 45)
            await gate.on_request(Request(room=room))
            await gate.on_request(Request(job="rejected", room="foreign-room"))
        finally:
            root.handlers[:] = previous
            root.setLevel(level)
        text = output.getvalue()
        self.assertNotIn("CANARY", text)
        owned = owned_rooms_from_dispatch_log(text, "think-partner-dev")
        self.assertEqual(owned, {room})
        api, clock = FakeRoomApi([[room, "foreign-room"]] * 4), FakeClock()
        summary = await CutoffGuard(owned, cutoff_s=1).run(
            api, poll_s=1, wait_s=5, clock=clock, sleep=clock.sleep)
        self.assertEqual(api.deletes, [room])
        self.assertTrue(summary["all_owned_closed"])
        self.assertEqual(summary["unmatched"], ["foreign-room"])

    async def test_reservation_precedes_held_accept_and_never_replenishes(self):
        module, release = launcher(), asyncio.Event()
        gate = module.SingleTrial((), 45)
        first = Request(hold=release)
        pending = asyncio.create_task(gate.on_request(first))
        await first.entered.wait()
        second = Request(job="job-b", room="room-b")
        await gate.on_request(second)
        self.assertEqual(second.calls, ["reject"])
        release.set()
        await pending
        third = Request(job="job-c", room="room-c")
        await gate.on_request(third)
        self.assertEqual((first.calls, third.calls), (["accept"], ["reject"]))

    async def test_wrong_name_or_blank_identity_is_rejected_without_consuming_valid_job(self):
        gate = launcher().SingleTrial((), 45)
        for request in (Request(name=""), Request(name="other"), Request(job=""), Request(room="")):
            await gate.on_request(request)
            self.assertEqual(request.calls, ["reject"])
        valid = Request()
        await gate.on_request(valid)
        self.assertEqual(valid.calls, ["accept"])

    async def test_failed_or_cancelled_accept_does_not_reopen_admission(self):
        for failure in (ValueError("CANARY-accept"), asyncio.CancelledError()):
            gate = launcher().SingleTrial((), 45)
            with self.assertRaises(type(failure)) as caught:
                await gate.on_request(Request(failure=failure))
            self.assertIs(caught.exception, failure)
            second = Request(job="job-b")
            await gate.on_request(second)
            self.assertEqual(second.calls, ["reject"])

    async def test_only_the_reserved_job_room_runs_once(self):
        module, stopped, entered = launcher(), [], []
        gate = module.SingleTrial(("sink",), 45)
        await gate.on_request(Request())

        async def delegate(ctx, **kwargs):
            entered.append((ctx.job.id, kwargs))

        with patch.object(module.cascade, "entrypoint", new=delegate):
            for job, room in (("wrong", "room-a"), ("job-a", "wrong")):
                ctx = SimpleNamespace(job=SimpleNamespace(id=job), room=SimpleNamespace(name=room), shutdown=stopped.append)
                with self.assertRaises(RuntimeError):
                    await gate.entrypoint(ctx)
            ctx = SimpleNamespace(job=SimpleNamespace(id="job-a"), room=SimpleNamespace(name="room-a"), shutdown=stopped.append)
            await gate.entrypoint(ctx)
            with self.assertRaises(RuntimeError):
                await gate.entrypoint(ctx)
        self.assertEqual(entered, [("job-a", {"handlers": ("sink",), "time_limit_s": 45})])
        self.assertEqual(len(stopped), 3)

    async def test_no_approval_or_invalid_duration_reaches_preparation(self):
        module = launcher()
        with patch.object(module, "prepare_server", side_effect=AssertionError("startup")):
            with self.assertRaises(RuntimeError):
                await module.run_worker()
            for seconds in (0, -1, 121, float("nan"), float("inf"), True):
                with self.assertRaises(ValueError):
                    await module.run_worker(approved=True, time_limit_s=seconds)

    async def test_failed_accept_cannot_later_enter_the_reserved_job(self):
        module, stopped = launcher(), []
        for failure in (ValueError("synthetic"), asyncio.CancelledError()):
            gate = module.SingleTrial((), 45)
            with self.assertRaises(type(failure)):
                await gate.on_request(Request(failure=failure))
            ctx = SimpleNamespace(job=SimpleNamespace(id="job-a"), room=SimpleNamespace(name="room-a"), shutdown=stopped.append)
            with patch.object(module.cascade, "entrypoint", side_effect=AssertionError("late startup")):
                with self.assertRaises(RuntimeError):
                    await gate.entrypoint(ctx)
        self.assertEqual(len(stopped), 2)

    async def test_logging_level_change_invalidates_cached_child_levels(self):
        module, root, child = launcher(), logging.getLogger(), logging.getLogger("livekit.cache-probe")
        old_level = root.level
        root.setLevel(logging.DEBUG)
        self.assertTrue(child.isEnabledFor(logging.DEBUG))

        def prepare(handlers, seconds):
            self.assertFalse(child.isEnabledFor(logging.DEBUG))
            raise RuntimeError("synthetic bootstrap failure")

        try:
            with patch.object(module.config, "check_profile"), patch.dict(os.environ, KEYS), \
                 patch.object(module, "prepare_server", side_effect=prepare):
                with self.assertRaises(RuntimeError):
                    await module.run_worker(approved=True, time_limit_s=45)
            self.assertTrue(child.isEnabledFor(logging.DEBUG))
        finally:
            root.setLevel(old_level)

    async def test_run_cleanup_preserves_failure_and_cancellation_with_protected_sink(self):
        module, root = launcher(), logging.getLogger()
        previous, level = root.handlers[:], root.level
        for failure in (RuntimeError("CANARY-run"), asyncio.CancelledError()):
            calls, output = [], io.StringIO()

            class Server:
                async def run(self, *, devmode):
                    calls.append(("run", devmode))
                    logging.getLogger("livekit.worker").error("CANARY-payload", exc_info=(type(failure), failure, None))
                    asyncio.get_running_loop().call_exception_handler(
                        {"message": "CANARY-background", "exception": failure})
                    raise failure

                async def aclose(self):
                    calls.append("close")
                    raise ValueError("CANARY-close")

            def prepare(handlers, seconds):
                calls.append("prepare")
                logging.getLogger("livekit.worker").warning("CANARY-bootstrap")
                self.assertEqual(len(root.handlers), 1)
                self.assertTrue(root.handlers[0].filters)
                return Server()

            with patch.object(module.config, "check_profile"), patch.dict(os.environ, KEYS), \
                 patch.object(module, "prepare_server", side_effect=prepare), redirect_stderr(output):
                with self.assertRaises(type(failure)) as caught:
                    await module.run_worker(approved=True, time_limit_s=45)
            self.assertIs(caught.exception, failure)
            self.assertEqual(calls, ["prepare", ("run", True), "close"])
            self.assertNotIn("CANARY", output.getvalue())
            self.assertIn("ValueError", output.getvalue())
            self.assertIn("correlation=cascade-bootstrap", output.getvalue())
            self.assertEqual((root.handlers, root.level), (previous, level))


class LaunchChecks(unittest.TestCase):
    def test_shell_overrides_refuse_instead_of_changing_registration(self):
        module = launcher()
        for name in ("LIVEKIT_AGENT_NAME_OVERRIDE", "LIVEKIT_WORKER_TOKEN", "LIVEKIT_AGENT_DEPLOYMENT"):
            with self.subTest(name=name), patch.dict(os.environ, {**KEYS, name: " "}):
                with self.assertRaises(RuntimeError) as caught:
                    module.check_environment()
                self.assertIn(name, str(caught.exception))

    def test_missing_environment_keys_reports_names_not_values(self):
        module = launcher()
        for missing in KEYS:
            values = dict(KEYS, **{missing: ""})
            with patch.dict(os.environ, values):
                with self.assertRaises(RuntimeError) as caught:
                    module.check_environment()
            self.assertIn(missing, str(caught.exception))
            self.assertNotIn("dummy", str(caught.exception))

    def test_default_command_checks_without_sdk_or_worker_startup(self):
        module, output = launcher(), io.StringIO()
        with patch.object(module.config, "check_profile"), patch.dict(os.environ, KEYS), \
             patch.object(module, "run_worker", side_effect=AssertionError("implicit startup")), redirect_stdout(output):
            self.assertEqual(module.main([]), 0)
        self.assertIn("not verified", output.getvalue())

    def test_cli_errors_and_cancel_are_content_free(self):
        module, output = launcher(), io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(module.main(["--watch", "CANARY-argument"]), 2)
        with patch.object(module.config, "check_profile", side_effect=RuntimeError("CANARY-profile")), redirect_stderr(output):
            self.assertEqual(module.main([]), 2)
        with patch.object(module.config, "check_profile", side_effect=KeyboardInterrupt()), redirect_stderr(output):
            self.assertEqual(module.main([]), 130)
        self.assertNotIn("CANARY", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())


if __name__ == "__main__":
    unittest.main()
