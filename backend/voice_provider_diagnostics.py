"""Content-free provider-path counters (Specification v1.0.1 P12, §§6/7.1).
Pinned seams: plugin 1.2.9 push_audio/_client; google-genai 2.8.0
send_realtime_input/receive. A completed send is not a server acknowledgement.
Opened means context entry, not verified model acceptance or conversation.
Counts and transcription/model-turn flags do not prove user-turn detection or playback.
"""
import json
import logging
import time
import uuid


class _GoogleLogPrivacy(logging.Filter):
    """P12/§6: replace native SDK error records before handlers format them."""

    def filter(self, record):
        error = record.exc_info[1] if record.exc_info else getattr(record, "error", None)
        if record.levelno < logging.WARNING and not (
            record.exc_info or record.exc_text or record.stack_info or error is not None
        ):
            return True
        # AgentSession DEBUG close records carry the failure in extra.error.
        error = getattr(error, "error", error)
        safe = logging.LogRecord(
            record.name, record.levelno, record.pathname, record.lineno,
            "google_sdk_event event=%s:%s error_type=%s",
            (record.funcName, record.lineno,
             type(error).__name__ if error is not None else "none"),
            exc_info=None, func=record.funcName)
        for name in ("created", "msecs", "relativeCreated", "process", "thread"):
            setattr(safe, name, getattr(record, name))
        safe.processName = safe.threadName = None
        return safe


for _name in ("livekit.plugins.google", "livekit.agents"):
    logging.getLogger(_name).addFilter(_GoogleLogPrivacy())


class ProviderDiagnostics:
    def __init__(self):
        self.id = uuid.uuid4().hex
        self.counts = dict(input_frames=0, submitted_chunks=0, submitted_bytes=0,
                           returned_chunks=0, returned_bytes=0)

    def emit(self, event, error=None):
        record = dict(id=self.id, timestamp=time.time(), event=event, **self.counts)
        try:
            if error is not None:
                record["error_type"] = type(error).__name__
                code = vars(error).get("code")
                if type(code) is int and (100 <= code <= 599 or 1000 <= code <= 1015):
                    record["error_code"] = code
            logging.getLogger("think-partner-dev").info(
                "voice_provider_diag %s", json.dumps(record)
            )
        except Exception:
            pass  # Diagnostics must not change transport behavior.

    def attach_input(self, session):
        push = session.push_audio

        def push_audio(frame):
            self.counts["input_frames"] += 1
            if self.counts["input_frames"] == 1:
                self.emit("plugin_input")
            return push(frame)

        session.push_audio = push_audio

    def audio(self, kind, blob):
        if blob is None or not (getattr(blob, "mime_type", None) or "").startswith("audio/"):
            return
        self.counts[kind + "_chunks"] += 1
        self.counts[kind + "_bytes"] += len(blob.data or b"")
        if self.counts[kind + "_chunks"] == 1:
            self.emit(kind)

    def attach_provider(self, provider):
        send, receive = provider.send_realtime_input, provider.receive

        async def send_realtime_input(*args, **kwargs):
            try:
                result = await send(*args, **kwargs)
            except BaseException as error:
                self.emit("send_failed", error)
                raise
            self.audio("submitted", kwargs.get("audio", kwargs.get("media")))
            return result

        async def receive_audio(*args, **kwargs):
            source = receive(*args, **kwargs)
            try:
                async for response in source:
                    content = response.server_content
                    if content and content.input_transcription is not None:
                        self.emit("input_transcription_finished" if content.input_transcription.finished else "input_transcription")
                    if content and content.turn_complete:
                        self.emit("turn_complete")
                    if content and content.model_turn:
                        for part in content.model_turn.parts or []:
                            self.audio("returned", part.inline_data)
                    yield response
            except BaseException as error:
                self.emit("receive_failed", error)
                raise
            finally:
                await source.aclose()

        provider.send_realtime_input = send_realtime_input
        provider.receive = receive_audio
        return send, receive

    def connection(self, context):
        return _ObservedConnection(context, self)


class _ObservedConnection:
    def __init__(self, context, diagnostics):
        self.context, self.diagnostics = context, diagnostics

    async def __aenter__(self):
        try:
            self.provider = await self.context.__aenter__()
        except BaseException as error:
            self.diagnostics.emit("connection_failed", error)
            raise
        self.saved = self.diagnostics.attach_provider(self.provider)
        self.diagnostics.emit("connection_opened")
        return self.provider

    async def __aexit__(self, *args):
        try:
            return await self.context.__aexit__(*args)
        finally:
            self.provider.send_realtime_input, self.provider.receive = self.saved
            self.diagnostics.emit("connection_exit", args[1])
