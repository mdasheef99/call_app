"""Main-thread bootstrap for the optional Google realtime plugin.

Why this exists: on Windows the LiveKit worker runs jobs on threads
(livekit-agents 1.2.12 defaults to the THREAD executor there), while
``Plugin.register_plugin`` raises off the main thread. Importing
``livekit.plugins.google`` lazily inside a job therefore fails the
first job deterministically — and worse, the failed import leaves the
``beta.realtime`` submodules cached, so later jobs in the same process
import "successfully" without the plugin ever registering (observed
2026-09-28).

The worker calls ``ensure_google_plugin_initialized()`` once on the
main thread before serving jobs. Importing this module never requires
the plugin: absence stays a supported configuration that jobs refuse
loudly via ``check_trial_prerequisites``.
"""

from __future__ import annotations

import logging
import threading

logger = logging.getLogger("think-partner-dev")

# Package marker the real GooglePlugin registers with (it passes
# ``__package__`` to ``Plugin.__init__``). Matched exactly so a
# nonempty generic registry — or a bare cached submodule — never
# counts as Google initialization.
GOOGLE_PLUGIN_PACKAGE = "livekit.plugins.google"


def is_google_plugin_registered() -> bool:
    """True only when the Google plugin completed registration."""
    from livekit.agents import Plugin

    return any(
        getattr(plugin, "package", "") == GOOGLE_PLUGIN_PACKAGE
        for plugin in Plugin.registered_plugins
    )


def ensure_google_plugin_initialized() -> bool:
    """Import the optional Google plugin on the calling (main) thread.

    Returns True when the plugin imported AND registered. Returns
    False (fail-closed, never raises for absence) when called off the
    main thread, when the plugin is not installed, or when the import
    did not register — e.g. only a cached submodule from a failed
    threaded import is present. A False here means trial jobs will
    keep refusing before connect, exactly like a missing plugin.
    """
    if threading.current_thread() is not threading.main_thread():
        logger.warning(
            "google plugin init requires the main thread; trial jobs will refuse"
        )
        return False
    try:
        # Same pinned-namespace import shape as the worker below, so
        # the check and the construction agree.
        from livekit.plugins.google.beta import realtime  # noqa: F401
    except ImportError:
        logger.warning("google plugin not installed; trial jobs will refuse")
        return False
    if not is_google_plugin_registered():
        logger.warning(
            "google plugin import did not register; trial jobs will refuse"
        )
        return False
    return True
