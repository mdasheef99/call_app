"""Spec P12/§6; SDD §8: protect sink records, not only rendered stdout.

Breaks caught: raw SDK text/extras/cached traces forwarded, descendant bypass,
lost severity/code/timing, mutation of caller error/record, unrelated suppression.
Pure stdlib; existing conftest installs network denial before SDK imports.
"""
import importlib
import importlib.util
import io
import logging
import sys
import unittest


def privacy():
    assert importlib.util.find_spec("voice_cascade_privacy") is not None, (
        "cascade sink privacy control is missing"
    )
    return importlib.import_module("voice_cascade_privacy").CascadeLogPrivacy("trial-17")


def record(name="livekit.plugins.sarvam.log", level=logging.ERROR, **fields):
    value = logging.LogRecord(name, level, "provider.py", 27,
                              "CANARY-message %s", ("CANARY-argument",), None,
                              func="provider_hook")
    value.__dict__.update(fields)
    return value


class Records(logging.Handler):
    def __init__(self):
        super().__init__()
        self.values = []

    def emit(self, value):
        self.values.append(value)


class CascadePrivacyCase(unittest.TestCase):
    def test_all_sdk_levels_and_descendants_are_content_free_at_every_sink(self):
        guard, saved, out, err = privacy(), Records(), io.StringIO(), io.StringIO()
        sinks = (saved, logging.StreamHandler(out), logging.StreamHandler(err))
        for sink in sinks:
            sink.addFilter(guard)
        names = ("livekit.agents", "livekit.plugins.sarvam.log.child",
                 "livekit.plugins.google", "google_genai.models", "google.genai.models",
                 "httpx", "httpcore.connection", "aiohttp.client", "think-partner-dev")
        for name in names:
            for level in (logging.DEBUG, logging.INFO, logging.WARNING,
                          logging.ERROR, logging.CRITICAL):
                value = record(name, level, raw_data={"text": "CANARY-transcript"},
                               audio=b"CANARY-audio", key="CANARY-key")
                for sink in sinks:
                    sink.handle(value)
        self.assertEqual(len(saved.values), 45)
        payload = str([value.__dict__ for value in saved.values]) + out.getvalue() + err.getvalue()
        self.assertNotIn("CANARY", payload)
        self.assertEqual([value.levelno for value in saved.values[:5]], [10, 20, 30, 40, 50])
        self.assertTrue(all(value.name in names for value in saved.values))

    def test_cached_text_stacks_extras_and_cause_are_removed_without_mutation(self):
        guard = privacy()
        try:
            try:
                raise RuntimeError("CANARY-cause")
            except RuntimeError as cause:
                raise ValueError("CANARY-error") from cause
        except ValueError as error:
            value = record(exc_info=sys.exc_info(), stack_info="CANARY-stack",
                           nested={"prompt": "CANARY-prompt"}, error=error)
            logging.Formatter().format(value)  # populate real cached traceback text
            original = dict(value.__dict__)
            result = guard.filter(value)
            self.assertIsInstance(result, logging.LogRecord)
            self.assertIsNot(result, value)
            self.assertNotIn("CANARY", str(result.__dict__))
            self.assertIn("ValueError", result.getMessage())
            self.assertEqual(value.__dict__, original)
            self.assertIs(value.exc_info[1], error)
            self.assertEqual(str(error.__cause__), "CANARY-cause")

    def test_unrelated_logger_is_forwarded_unchanged(self):
        guard = privacy()
        value = record("application.other")
        self.assertIs(guard.filter(value), value)
        self.assertEqual(value.getMessage(), "CANARY-message CANARY-argument")

    def test_numeric_codes_are_preserved_but_arbitrary_error_fields_are_not(self):
        guard = privacy()
        for code, expected in ((429, "429"), (1008, "1008"), (0, "none"),
                               ("CANARY-code", "none"), (True, "none")):
            with self.subTest(code=code):
                failure = RuntimeError("CANARY-error")
                failure.code = code
                result = guard.filter(record(exc_info=(RuntimeError, failure, None)))
                self.assertNotIn("CANARY", str(result.__dict__))
                self.assertIn("code=" + expected, result.getMessage())

    def test_sanitization_does_not_render_original_message_arguments(self):
        guard = privacy()

        class Forbidden:
            def __str__(self):
                raise AssertionError("provider payload was rendered")

        value = record(args=(Forbidden(),))
        self.assertIn("cascade_sdk_event", guard.filter(value).getMessage())

    def test_correlation_timing_and_source_survive_sanitization(self):
        guard = privacy()
        value = record(created=123.5, msecs=500.0, relativeCreated=77.0)
        result = guard.filter(value)
        self.assertEqual((result.created, result.msecs, result.relativeCreated), (123.5, 500.0, 77.0))
        self.assertEqual((result.pathname, result.lineno, result.funcName),
                         ("provider.py", 27, "provider_hook"))
        self.assertEqual(result.correlation_id, "trial-17")


if __name__ == "__main__":
    unittest.main()
