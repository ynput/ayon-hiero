"""Run pytest inside Hiero, started by `tests/run_hiero_tests.py`.

Hiero runs this file on startup (`--script`). Settings come from the
environment, because Nuke takes some flags after `--script` as its own:

    HIERO_TEST_PATHS   paths added to `sys.path` (os.pathsep separated)
    HIERO_PYTEST_ARGS  JSON list of pytest arguments
    HIERO_PYTEST_LOG   file pytest writes its output to; Hiero does not pass
                       Python's stdout to the console
    HIERO_TEST_RESULT  JSON file with the pytest exit code

Hiero is closed with `os._exit()`, after the Frame Server is stopped.
Otherwise its worker processes keep running.
"""

import json
import os
import sys
import time
import traceback


def _stop_frame_server():
    try:
        import hiero.ui
        from qtpy import QtWidgets

        frame_server = hiero.ui.nuke_bridge.FnNsFrameServer
        frame_server.stopServer(None)
        deadline = time.time() + 10
        while time.time() < deadline and frame_server.isServerRunning(
            timeout=0.2
        ):
            QtWidgets.QApplication.processEvents()
            time.sleep(0.2)
    except Exception:
        traceback.print_exc()


def main():
    exitcode = 3
    log_path = os.environ.get("HIERO_PYTEST_LOG")
    log_stream = None
    if log_path:
        log_stream = open(log_path, "w", buffering=1)
        sys.stdout = log_stream
        sys.stderr = log_stream

    try:
        paths = os.environ.get("HIERO_TEST_PATHS", "").split(os.pathsep)
        for path in reversed(paths):
            if path and path not in sys.path:
                sys.path.insert(0, path)

        import pytest

        args = json.loads(os.environ.get("HIERO_PYTEST_ARGS") or "[]")
        exitcode = int(pytest.main(args + ["-p", "no:cacheprovider"]))
    except BaseException:
        traceback.print_exc()
    finally:
        _stop_frame_server()
        result_path = os.environ.get("HIERO_TEST_RESULT")
        if result_path:
            with open(result_path, "w") as stream:
                json.dump({"exitcode": exitcode}, stream)
        if log_stream:
            log_stream.flush()
        os._exit(exitcode)


main()
