"""SDD §§4/6/8: wrong profile, unregistered plugin and missing keys fail closed.

Pure stdlib; constructor/transport/lifecycle conformance lives in the isolated
profile checks. Breaks caught: importing SDKs before profile validation, accepting
an import without registration, threaded bootstrap, or an unprotected owned sink.
"""
import importlib
import importlib.util
import io
import logging
import os
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

PINS = {"livekit-agents": "1.8.3", "livekit-plugins-google": "1.8.3",
        "livekit-plugins-sarvam": "1.8.3", "google-genai": "2.13.0", "pydantic": "2.12.5"}


def config():
    assert importlib.util.find_spec("voice_cascade_config") is not None, "cascade configuration missing"
    return importlib.import_module("voice_cascade_config")


class CascadeConfigurationCase(unittest.TestCase):
    def profile(self, module):
        return patch.object(module.metadata, "version", side_effect=PINS.__getitem__)

    def test_wrong_python_and_each_wrong_pin_refuse_before_sdk_import(self):
        module = config()
        with self.profile(module), patch.object(module.sys, "version_info", (3, 11, 0)):
            with self.assertRaises(RuntimeError):
                module.check_profile()
        for package in PINS:
            bad = dict(PINS, **{package: "0.0.0"})
            with patch.object(module.metadata, "version", side_effect=bad.__getitem__), \
                 patch.object(module.importlib, "import_module", side_effect=AssertionError("SDK import")):
                with self.assertRaises(RuntimeError) as caught:
                    module.initialize_plugins()
                self.assertIn(package, str(caught.exception))

    def test_absent_distribution_reports_its_name_only(self):
        module = config()
        with patch.object(module.metadata, "version", side_effect=module.metadata.PackageNotFoundError("CANARY")):
            with self.assertRaises(RuntimeError) as caught:
                module.check_profile()
        self.assertIn("livekit-agents", str(caught.exception))
        self.assertNotIn("CANARY", str(caught.exception))

    def test_exact_profile_is_accepted_without_importing_sdk(self):
        module = config()
        with self.profile(module), patch.object(module.importlib, "import_module", side_effect=AssertionError("SDK import")):
            module.check_profile()

    def test_threaded_bootstrap_refuses_before_any_sdk_import(self):
        module, errors = config(), []

        def run():
            try:
                module.initialize_plugins()
            except RuntimeError as error:
                errors.append(error)

        with self.profile(module), patch.object(module.importlib, "import_module", side_effect=AssertionError("SDK import")):
            thread = threading.Thread(target=run)
            thread.start()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIn("main thread", str(errors[0]))

    def test_import_without_selected_registration_is_not_admitted(self):
        module = config()
        agents = SimpleNamespace(Plugin=SimpleNamespace(registered_plugins=[]))
        with self.profile(module), patch.object(module.importlib, "import_module", return_value=agents), \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "CANARY-google", "SARVAM_API_KEY": "CANARY-sarvam"}):
            with self.assertRaises(RuntimeError):
                module.initialize_plugins()
            with self.assertRaises(RuntimeError):
                module.check_trial_prerequisites()

    def test_each_missing_key_refuses_without_rendering_any_key(self):
        module = config()
        agents = SimpleNamespace(Plugin=SimpleNamespace(registered_plugins=[
            SimpleNamespace(package="livekit.plugins.google"), SimpleNamespace(package="livekit.plugins.sarvam")]))
        for missing in ("GOOGLE_API_KEY", "SARVAM_API_KEY"):
            values = {"GOOGLE_API_KEY": "CANARY-google", "SARVAM_API_KEY": "CANARY-sarvam"}
            values[missing] = ""
            with self.profile(module), patch.object(module.importlib, "import_module", return_value=agents), \
                 patch.dict(os.environ, values):
                with self.assertRaises(RuntimeError) as caught:
                    module.check_trial_prerequisites()
            self.assertIn(missing, str(caught.exception))
            self.assertNotIn("CANARY", str(caught.exception))

    def test_owned_sink_replacement_is_idempotent_and_scrubs_full_record(self):
        module, out = config(), io.StringIO()
        handler = logging.StreamHandler(out)
        handler.setFormatter(logging.Formatter("%(correlation_id)s %(message)s",
                             defaults={"correlation_id": "bootstrap"}))
        module.protect_handlers([handler], "bootstrap")
        value = logging.LogRecord("livekit.plugins.sarvam.log", logging.ERROR,
                                  "sdk.py", 4, "CANARY-message", (), None)
        value.payload = "CANARY-extra"
        original_remove = handler.removeFilter

        def remove_and_emit(previous):
            original_remove(previous)
            handler.handle(value)  # a server log interleaves before replacement

        with patch.object(handler, "removeFilter", side_effect=remove_and_emit):
            module.protect_handlers([handler], "trial-42")
        handler.handle(value)
        self.assertEqual(len(handler.filters), 1)
        self.assertIn("trial-42", out.getvalue())
        self.assertNotIn("CANARY", out.getvalue())
        self.assertEqual(value.payload, "CANARY-extra")


if __name__ == "__main__":
    unittest.main()
