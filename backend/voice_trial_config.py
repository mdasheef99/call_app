"""Common dev-trial identity/instructions/defaults (SDD §§5/6/9).

No SDK or provider imports. These values preserve the native trial contract;
operator-selected configurations share them without importing native adapters.
"""
AGENT_NAME = "think-partner-dev"


AGENT_INSTRUCTIONS = (
    "You are a thinking partner for preparing customer meetings. "
    "Be warm, concise, and curious, and willing to challenge assumptions. "
    "Understand and respond in Indian English/Hinglish. "
    "Keep replies short enough to interrupt. "
    "If a name or number is unclear, say so instead of guessing. "
    "This is a voice-only test call: no camera, no actions, no recap."
)


GOOGLE_API_KEY_ENV = "GOOGLE_API_KEY"


CALL_TIME_LIMIT_S = 120.0


CLEANUP_TIMEOUT_S = 10.0
