"""Content-free cascade log sinks (Spec P12/§6; SDD §8).

Attach to EVERY owned logging handler before cascade SDK construction. Python
3.12+ handler filters support replacement records, including descendant loggers.
No import-time logging changes. This protects opted-in sinks, not arbitrary
handlers, provider retention, externally configured exporters or raw print().
"""
import json
import logging
from voice_trial_config import AGENT_NAME

_NAMES = ("livekit", "google_genai", "google.genai", "httpx", "httpcore",
          "aiohttp", "think-partner-dev", "asyncio")


class CascadeLogPrivacy(logging.Filter):
    """Keep source/severity/timing/type/code; never render or mutate payloads."""

    def __init__(self, correlation_id: str):
        super().__init__()
        self.correlation_id = correlation_id

    def filter(self, record: logging.LogRecord) -> logging.LogRecord:
        if not any(record.name == name or record.name.startswith(name + ".")
                   for name in _NAMES):
            return record
        error = record.exc_info[1] if record.exc_info else None
        fields = vars(error) if error is not None else {}
        code = fields.get("status_code", fields.get("code"))
        if type(code) is not int or not (100 <= code <= 599 or 1000 <= code <= 1015):
            code = "none"
        message = "cascade_sdk_event source=%s:%s error_type=%s code=%s"
        args = (record.funcName, record.lineno,
                type(error).__name__ if error is not None else "none", code)
        room = vars(record).get("trial_room_name")
        if record.name == "think-partner-dev.dispatch" and type(room) is str and room:
            # Deliberate admission metadata only; never pass through SDK extras.
            message = "received job request %s"
            args = (json.dumps({"agent_name": AGENT_NAME, "room_name": room}),)
        safe = logging.LogRecord(
            record.name, record.levelno, record.pathname, record.lineno,
            message, args,
            exc_info=None, func=record.funcName,
        )
        for name in ("created", "msecs", "relativeCreated", "process", "thread"):
            setattr(safe, name, getattr(record, name))
        safe.processName = safe.threadName = None
        safe.correlation_id = self.correlation_id
        return safe
