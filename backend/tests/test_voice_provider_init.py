"""Offline regression tests for main-thread Google plugin initialization.

The dev worker runs jobs on threads under Windows (livekit-agents 1.2.12
defaults to the THREAD executor there), while the Google plugin must
register on the main thread. A lazy per-job import therefore fails the
first job and leaves cached submodules that let later jobs import
"successfully" without registration (observed 2026-09-28).

These tests use fresh subprocesses with the REAL installed plugin so no
in-process import state leaks between cases. No network, no worker, no
room, no Google session is constructed here — only imports, the
startup-wiring function, and offline model construction. Subprocesses
scrub GOOGLE_API_KEY except where a dummy offline value is required.
"""

import os
import pathlib
import subprocess
import sys

import pytest

livekit_agents = pytest.importorskip(
    "livekit.agents",
    reason="voice draft needs livekit-agents (local .venv only, not requirements.lock)",
)

import voice_agent_dev  # noqa: E402  (safe: imports livekit.agents only, never the plugin)

BACKEND_DIR = pathlib.Path(voice_agent_dev.__file__).parent


def _run_case(script, timeout_s=120):
    """Run a fresh interpreter in backend/ with credentials scrubbed."""
    script = "from tests.network_block import deny_outbound; deny_outbound()\n" + script
    env = dict(os.environ)
    env.pop("GOOGLE_API_KEY", None)
    proc = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    return proc


def _result_lines(proc):
    assert proc.returncode == 0, f"case crashed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr[-2000:]}"
    values = {}
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT "):
            key, _, value = line[len("RESULT "):].partition("=")
            values[key.strip()] = value.strip()
    return values


def test_startup_wiring_initializes_before_threaded_job_work():
    # Correct startup: main-thread ensure() succeeds with the plugin
    # really registered, and a job-thread style import plus the
    # prerequisite/model-access paths then work (mirrors a Windows
    # THREAD-executor job after proper initialization).
    proc = _run_case(
        "import os, threading\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "import voice_provider_bootstrap as b\n"
        "import voice_agent_dev as v\n"
        "ensure = b.ensure_google_plugin_initialized()\n"
        "registered = b.is_google_plugin_registered()\n"
        "outcome = []\n"
        "def job():\n"
        "    try:\n"
        "        from livekit.plugins.google.beta import realtime\n"
        "        v.check_trial_prerequisites()\n"
        "        model = v.build_realtime_model()\n"
        "        outcome.append('ok:' + type(model).__name__)\n"
        "    except Exception as error:\n"
        "        outcome.append(type(error).__name__ + ':' + str(error))\n"
        "t = threading.Thread(target=job)\n"
        "t.start()\n"
        "t.join()\n"
        "print('RESULT ensure=' + str(ensure))\n"
        "print('RESULT registered=' + str(registered))\n"
        "print('RESULT thread=' + outcome[0])\n"
    )
    values = _result_lines(proc)
    assert values["ensure"] == "True"
    assert values["registered"] == "True"
    assert values["thread"] == "ok:RealtimeModel", values["thread"]


def test_failed_first_import_cache_cannot_count_as_initialized():
    # Poisoned state: a threaded import fails first (the 2026-09-28
    # first-job failure). The startup wiring must NOT bless the process
    # afterwards — a cached realtime submodule alone is not
    # initialization, and Google remains unregistered.
    proc = _run_case(
        "import threading\n"
        "def job():\n"
        "    try:\n"
        "        from livekit.plugins.google.beta import realtime\n"
        "    except Exception:\n"
        "        pass\n"
        "t = threading.Thread(target=job)\n"
        "t.start()\n"
        "t.join()\n"
        "import voice_provider_bootstrap as b\n"
        "print('RESULT ensure=' + str(b.ensure_google_plugin_initialized()))\n"
        "print('RESULT registered=' + str(b.is_google_plugin_registered()))\n"
    )
    values = _result_lines(proc)
    assert values["ensure"] == "False"
    assert values["registered"] == "False"


def test_plugin_absent_still_refuses_without_install_changes():
    # Optional-plugin compatibility without touching the venv: block the
    # plugin via a meta-path finder, then startup must report
    # not-initialized and the prereq gate must still refuse (no connect).
    proc = _run_case(
        "import sys\n"
        "class Blocker:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'livekit.plugins.google' or name.startswith('livekit.plugins.google.'):\n"
        "            raise ImportError('blocked-offline:' + name)\n"
        "        return None\n"
        "sys.meta_path.insert(0, Blocker())\n"
        "import voice_provider_bootstrap as b\n"
        "print('RESULT ensure=' + str(b.ensure_google_plugin_initialized()))\n"
        "import voice_agent_dev as v\n"
        "try:\n"
        "    v.check_trial_prerequisites()\n"
        "    print('RESULT prereq=passed-UNEXPECTED')\n"
        "except RuntimeError:\n"
        "    print('RESULT prereq=refused')\n"
    )
    values = _result_lines(proc)
    assert values["ensure"] == "False"
    assert values["prereq"] == "refused"


def test_bootstrap_targets_the_pinned_beta_namespace():
    # Same namespace pin as the worker: realtime lives under the beta
    # namespace in livekit-plugins-google==1.2.9.
    source = (BACKEND_DIR / "voice_provider_bootstrap.py").read_text(encoding="utf-8")
    assert "from livekit.plugins.google.beta import realtime" in source
    assert "from livekit.plugins.google import realtime" not in source


def test_startup_initializes_plugin_before_serving():
    # Proves the actual startup ordering: the optional plugin is
    # initialized on the main thread BEFORE the worker is told to serve,
    # so no job thread can be the first importer. cli.run_app is
    # replaced by a spy, so no worker, room, or connection exists.
    proc = _run_case(
        "import runpy\n"
        "import livekit.agents.cli as cli_mod\n"
        "import voice_provider_bootstrap as b\n"
        "import voice_agent_dev as v\n"
        "order = []\n"
        "def _spy(options, **kwargs):\n"
        "    order.append('run_app:' + options.agent_name)\n"
        "cli_mod.run_app = _spy\n"
        "b.ensure_google_plugin_initialized = lambda: order.append('ensure') or True\n"
        "runpy.run_module('voice_agent_dev', run_name='__main__')\n"
        "print('RESULT order=' + ','.join(order))\n"
    )
    values = _result_lines(proc)
    assert values["order"] == "ensure,run_app:think-partner-dev", values["order"]


def test_default_dev_cli_keeps_bootstrap_in_job_serving_process():
    # Exercise the real Click dev command and run_dev routing, stopping
    # before Worker construction. A watcher child loses __main__ bootstrap.
    proc = _run_case(
        "import os, runpy, sys, threading\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "from livekit.agents.cli import _run\n"
        "from livekit.agents.cli import watcher\n"
        "def reject_watcher(*args, **kwargs):\n"
        "    raise AssertionError('watcher would bypass main-thread bootstrap')\n"
        "watcher.WatchServer = reject_watcher\n"
        "def serve(args):\n"
        "    import voice_agent_dev as v\n"
        "    outcome = []\n"
        "    def job():\n"
        "        try:\n"
        "            v.check_trial_prerequisites()\n"
        "            outcome.append('ok')\n"
        "        except Exception as error:\n"
        "            outcome.append(type(error).__name__)\n"
        "    t = threading.Thread(target=job); t.start(); t.join()\n"
        "    print('RESULT thread=' + outcome[0])\n"
        "    print('RESULT watch=' + str(args.watch))\n"
        "_run.run_worker = serve\n"
        "sys.argv = ['voice_agent_dev.py', 'dev']\n"
        "runpy.run_module('voice_agent_dev', run_name='__main__')\n"
    )
    values = _result_lines(proc)
    assert values["watch"] == "False"
    assert values["thread"] == "ok"


def test_unregistered_plugin_is_refused_before_connect():
    # Importable is not the same as registered: with registration
    # suppressed the import succeeds, so only an explicit registration
    # check can keep the job out of a room. The entrypoint must refuse
    # BEFORE ctx.connect() and still finalize the job.
    proc = _run_case(
        "import asyncio, os\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "from livekit.agents import Plugin\n"
        "Plugin.register_plugin = classmethod(lambda cls, plugin: None)\n"
        "from livekit.plugins.google.beta import realtime\n"
        "import voice_agent_dev as v\n"
        "registered = any(\n"
        "    getattr(p, 'package', '') == 'livekit.plugins.google'\n"
        "    for p in Plugin.registered_plugins\n"
        ")\n"
        "print('RESULT registered=' + str(registered))\n"
        "try:\n"
        "    v.check_trial_prerequisites()\n"
        "    print('RESULT prereq=accepted')\n"
        "except RuntimeError as error:\n"
        "    print('RESULT prereq=refused:' + str(error))\n"
        "class Room:\n"
        "    name = 'test-room'\n"
        "class Ctx:\n"
        "    def __init__(self):\n"
        "        self.room = Room()\n"
        "        self.connects = 0\n"
        "        self.shutdowns = []\n"
        "    async def connect(self):\n"
        "        self.connects += 1\n"
        "    def shutdown(self, reason=''):\n"
        "        self.shutdowns.append(reason)\n"
        "ctx = Ctx()\n"
        "try:\n"
        "    asyncio.run(v.entrypoint(ctx))\n"
        "except RuntimeError:\n"
        "    pass\n"
        "print('RESULT connects=' + str(ctx.connects))\n"
        "print('RESULT shutdowns=' + ','.join(ctx.shutdowns))\n"
    )
    values = _result_lines(proc)
    assert values["registered"] == "False"
    assert values["prereq"].startswith("refused:"), values["prereq"]
    assert "livekit-plugins-google" in values["prereq"]
    assert values["connects"] == "0", "must not join a room when unregistered"
    assert values["shutdowns"] == "dev trial prereq missing"


def test_failed_threaded_import_cannot_admit_a_job():
    # The 2026-09-28 first-dispatch failure, end to end: a threaded
    # import fails yet leaves the realtime submodule cached, so the
    # import alone would admit the job. The registration check is what
    # refuses it before connect.
    proc = _run_case(
        "import threading\n"
        "def job():\n"
        "    try:\n"
        "        from livekit.plugins.google.beta import realtime\n"
        "    except Exception:\n"
        "        pass\n"
        "t = threading.Thread(target=job)\n"
        "t.start()\n"
        "t.join()\n"
        "import sys\n"
        "print('RESULT cached=' + str('livekit.plugins.google.beta.realtime' in sys.modules))\n"
        "import os\n"
        "os.environ['GOOGLE_API_KEY'] = 'dummy-offline-key'\n"
        "import voice_agent_dev as v\n"
        "try:\n"
        "    v.check_trial_prerequisites()\n"
        "    print('RESULT prereq=accepted')\n"
        "except RuntimeError as error:\n"
        "    print('RESULT prereq=refused:' + str(error))\n"
    )
    values = _result_lines(proc)
    assert values["cached"] == "True", "the poisoned cache is what made this unsafe"
    assert values["prereq"].startswith("refused:"), values["prereq"]
