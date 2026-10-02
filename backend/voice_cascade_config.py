"""One fixed isolated cascade profile; SDD §§3/4/6/8, Spec P12/§6.

No SDK imports, environment-file loading or logging mutations on import.
Keys/registration establish local prerequisites, never provider entitlement.
"""
import asyncio
import importlib
from importlib import metadata
import logging
import os
import sys
import threading

from voice_cascade_privacy import CascadeLogPrivacy
from voice_trial_config import CLEANUP_TIMEOUT_S, GOOGLE_API_KEY_ENV

PINS = {"livekit-agents": "1.8.3", "livekit-plugins-google": "1.8.3",
        "livekit-plugins-sarvam": "1.8.3", "google-genai": "2.13.0", "pydantic": "2.12.5"}
PACKAGES = ("livekit.plugins.google", "livekit.plugins.sarvam")


def check_profile() -> None:
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError("Cascade requires the tested Python 3.13 profile")
    for package, wanted in PINS.items():
        try:
            installed = metadata.version(package)
        except metadata.PackageNotFoundError:
            installed = None
        if installed != wanted:
            raise RuntimeError(f"Cascade requires isolated {package}=={wanted}") from None


def protect_handlers(handlers, correlation_id: str) -> None:
    handlers = tuple(dict.fromkeys(handlers))
    if not handlers:
        raise RuntimeError("Cascade requires an explicitly controlled logging sink")
    for handler in handlers:
        guards = [guard for guard in tuple(handler.filters)
                  if isinstance(guard, CascadeLogPrivacy)]
        if guards:
            for guard in guards:
                guard.correlation_id = correlation_id  # keep protection installed
        else:
            handler.addFilter(CascadeLogPrivacy(correlation_id))


def _require_registrations() -> None:
    registered = {plugin.package for plugin in
                  importlib.import_module("livekit.agents").Plugin.registered_plugins}
    if not all(package in registered for package in PACKAGES):
        raise RuntimeError("Cascade Google/Sarvam plugins must be registered on the main thread")


def initialize_plugins() -> None:
    check_profile()
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Cascade initialization requires the main thread")
    for package in PACKAGES:
        importlib.import_module(package)
    _require_registrations()


def check_trial_prerequisites() -> None:
    check_profile()
    missing = [name for name in (GOOGLE_API_KEY_ENV, "SARVAM_API_KEY")
               if not os.environ.get(name, "").strip()]
    if missing:
        raise RuntimeError("Cascade prerequisite missing: " + ", ".join(missing))
    _require_registrations()


async def build_session(*, register_cleanup=None):
    """Retain partial/full owners in the job's shutdown cleanup (SDD §6)."""
    check_trial_prerequisites()
    from google.genai import types
    from livekit.agents import APIConnectOptions
    from livekit.agents.voice.agent_session import SessionConnectOptions
    from livekit.plugins import google, sarvam
    from voice_cascade_session import CascadeSession, close_owned

    owners = []
    session = None
    cleanup_lock = asyncio.Lock()

    async def close_remaining():
        # SDK shutdown callbacks may run while construction cleanup is held.
        async with cleanup_lock:
            if session is None:
                await close_owned(owners)
            else:
                await session.aclose()

    async def retry_cleanup():
        try:
            await asyncio.wait_for(close_remaining(), CLEANUP_TIMEOUT_S)
        except BaseException:
            # The entrypoint protects the owned sink before this factory runs.
            logging.getLogger("think-partner-dev").error(
                "cascade shutdown cleanup incomplete", exc_info=True)
            raise

    if register_cleanup is not None:
        register_cleanup(retry_cleanup)
    try:
        stt = sarvam.STTRealtime(api_key=os.environ["SARVAM_API_KEY"], language="auto",
                mode="codemix", stream_type="balanced", endpointing="vad",
                encoding="linear16", sample_rate=16000)
        owners.append(stt)
        tts = sarvam.TTS(api_key=os.environ["SARVAM_API_KEY"], model="bulbul:v3",
                speaker="shubh", target_language_code="en-IN", speech_sample_rate=24000,
                num_channels=1, output_audio_codec="mp3", pace=1.0)
        owners.append(tts)
        llm = google.LLM(api_key=os.environ[GOOGLE_API_KEY_ENV], model="gemini-3.1-flash-lite",
                vertexai=False, http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1)))
        owners.append(llm)
        no_retry = APIConnectOptions(max_retry=0)
        session = CascadeSession(stt=stt, llm=llm, tts=tts, vad=None,
                turn_handling={"turn_detection": "stt"}, conn_options=SessionConnectOptions(
                    stt_conn_options=no_retry, llm_conn_options=no_retry, tts_conn_options=no_retry,
                    max_unrecoverable_errors=0))
        return session
    except BaseException:
        try:
            await close_remaining()
        except asyncio.CancelledError:
            raise
        except BaseException as cleanup_error:
            logging.getLogger("think-partner-dev").error(
                "cascade construction cleanup incomplete (%s)", type(cleanup_error).__name__)
        raise
