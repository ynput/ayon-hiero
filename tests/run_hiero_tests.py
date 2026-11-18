"""Run the tests in `tests/hiero` inside a Hiero session.

Hiero has no terminal mode, so the tests run in a normal Hiero session
started with `--hiero -q --script tests/hiero/bootstrap.py`. A Hiero window
opens for the duration of the run.

Usage:
    ayon run tests/run_hiero_tests.py [--app PATH] [--core PATH] [-- PYTEST ARGS]
    python tests/run_hiero_tests.py ...  (without the AYON launcher)

Only the standard library is used, so any Python 3.9+ runs this file.
See `tests/README.md`.
"""

import argparse
import glob
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
HIERO_TESTS_DIR = os.path.join(TESTS_DIR, "hiero")
BOOTSTRAP = os.path.join(HIERO_TESTS_DIR, "bootstrap.py")
REQUIREMENTS = os.path.join(TESTS_DIR, "requirements-hiero.txt")
DEPS_ROOT = os.path.join(TESTS_DIR, ".deps")
RESULTS_DIR = os.path.join(TESTS_DIR, ".results")

# Python version of each supported Nuke/Hiero major version
PYTHON_BY_NUKE_MAJOR = {14: "3.9", 15: "3.10", 16: "3.11", 17: "3.11"}

_EXECUTABLE_RE = re.compile(r"^Nuke(\d+)\.(\d+)(\.exe)?$")


def _log(message):
    print(f"[run_hiero_tests] {message}", flush=True)


def _install_roots():
    system = platform.system()
    if system == "Darwin":
        return ["/Applications"]
    if system == "Windows":
        return [
            os.environ.get("PROGRAMFILES", r"C:\Program Files"),
        ]
    return ["/usr/local", "/opt"]


def _find_executable_in(path):
    """Return the Nuke executable for a file, `.app` bundle or folder."""
    if os.path.isfile(path):
        return path

    candidates = []
    patterns = (
        os.path.join(path, "Contents", "MacOS", "Nuke*"),
        os.path.join(path, "*.app", "Contents", "MacOS", "Nuke*"),
        os.path.join(path, "Nuke*"),
    )
    for pattern in patterns:
        for candidate in glob.glob(pattern):
            if os.path.isfile(candidate) and _EXECUTABLE_RE.match(
                os.path.basename(candidate)
            ):
                candidates.append(candidate)
    return sorted(candidates)[-1] if candidates else None


def _nuke_version(executable):
    match = _EXECUTABLE_RE.match(os.path.basename(executable))
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def find_hiero_executable(app_path=None):
    """Find the Nuke executable used to start Hiero.

    Order: `--app`, `AYON_HIERO_EXECUTABLE`, the newest Nuke 16 or 17
    install in the usual install folder of the platform.
    """
    for path in (app_path, os.environ.get("AYON_HIERO_EXECUTABLE")):
        if not path:
            continue
        executable = _find_executable_in(path)
        if not executable:
            raise SystemExit(f"No Nuke executable found in '{path}'.")
        return executable

    found = []
    for root in _install_roots():
        for folder in glob.glob(os.path.join(root, "Nuke1[67]*")):
            executable = _find_executable_in(folder)
            if executable:
                found.append((_nuke_version(executable), executable))
    if not found:
        raise SystemExit(
            "No Hiero found. Pass --app or set AYON_HIERO_EXECUTABLE."
        )
    return sorted(found)[-1][1]


def find_ayon_core_client(core_path=None):
    """Find the `client` folder of an ayon-core checkout.

    Order: `--core`, `AYON_CORE_ROOT`, the ayon-core of the AYON launcher
    this runs in (`ayon run`), an `ayon-core` folder next to this repository
    or next to any of its parent folders (worktrees).
    """
    for path in (core_path, os.environ.get("AYON_CORE_ROOT")):
        if path:
            client = os.path.join(path, "client")
            if not os.path.isdir(os.path.join(client, "ayon_core")):
                raise SystemExit(f"'{path}' is not an ayon-core checkout.")
            return client

    spec = importlib.util.find_spec("ayon_core")
    if spec and spec.submodule_search_locations:
        return os.path.dirname(list(spec.submodule_search_locations)[0])

    current = REPO_ROOT
    while True:
        parent = os.path.dirname(current)
        if parent == current:
            break
        client = os.path.join(parent, "ayon-core", "client")
        if os.path.isdir(os.path.join(client, "ayon_core")):
            return client
        current = parent
    raise SystemExit(
        "No ayon-core checkout found. Pass --core or set AYON_CORE_ROOT."
    )


def ensure_dependencies(python_version):
    """Install the test dependencies for Hiero's Python into a folder."""
    with open(REQUIREMENTS, "rb") as stream:
        requirements_hash = hashlib.sha256(stream.read()).hexdigest()

    target = os.path.join(DEPS_ROOT, "py" + python_version.replace(".", ""))
    stamp = os.path.join(target, ".requirements.sha256")
    if os.path.exists(stamp):
        with open(stamp) as stream:
            if stream.read().strip() == requirements_hash:
                return target

    uv = shutil.which("uv")
    if not uv:
        raise SystemExit("`uv` is needed to install the test dependencies.")
    if os.path.isdir(target):
        shutil.rmtree(target)
    _log(f"Installing test dependencies for Python {python_version}")
    subprocess.run(
        [
            uv,
            "pip",
            "install",
            "--quiet",
            "--python",
            python_version,
            "--target",
            target,
            "-r",
            REQUIREMENTS,
        ],
        check=True,
    )
    with open(stamp, "w") as stream:
        stream.write(requirements_hash)
    return target


def _stream_log(log_path, position):
    """Print what was added to the log file since `position`."""
    try:
        with open(log_path, "r", errors="replace") as stream:
            stream.seek(position)
            chunk = stream.read()
            position = stream.tell()
    except OSError:
        return position
    if chunk:
        sys.stdout.write(chunk)
        sys.stdout.flush()
    return position


def _kill_process_group(process):
    """Stop processes Hiero left behind (POSIX only)."""
    if os.name != "posix":
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def run(executable, test_paths, pytest_args, timeout):
    os.makedirs(RESULTS_DIR, exist_ok=True)
    run_dir = tempfile.mkdtemp(prefix="hiero_tests_")
    log_path = os.path.join(run_dir, "pytest.log")
    result_path = os.path.join(run_dir, "result.json")

    env = dict(os.environ)
    env.update(
        {
            "HIERO_TEST_PATHS": os.pathsep.join(test_paths),
            "HIERO_PYTEST_ARGS": json.dumps(pytest_args),
            "HIERO_PYTEST_LOG": log_path,
            "HIERO_TEST_RESULT": result_path,
        }
    )
    command = [executable, "--hiero", "-q", "--script", BOOTSTRAP]
    _log("Starting: " + " ".join(command))
    hiero_output = open(os.path.join(run_dir, "hiero.log"), "w")
    process = subprocess.Popen(
        command,
        cwd=REPO_ROOT,
        env=env,
        stdout=hiero_output,
        stderr=subprocess.STDOUT,
        start_new_session=(os.name == "posix"),
    )

    position = 0
    deadline = time.time() + timeout
    try:
        while process.poll() is None:
            position = _stream_log(log_path, position)
            if time.time() > deadline:
                _log(f"Timed out after {timeout} s, stopping Hiero.")
                process.kill()
                break
            time.sleep(0.5)
        process.wait()
    finally:
        _stream_log(log_path, position)
        hiero_output.close()
        _kill_process_group(process)

    if not os.path.exists(result_path):
        _log(
            "Hiero exited without a test result (return code "
            f"{process.returncode}). Hiero output: "
            + os.path.join(run_dir, "hiero.log")
        )
        return 3

    with open(result_path) as stream:
        result = json.load(stream)
    exitcode = int(result["exitcode"])
    _log(f"pytest exit code {exitcode}, logs in {run_dir}")
    return exitcode


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    pytest_args = []
    if "--" in argv:
        index = argv.index("--")
        argv, pytest_args = argv[:index], argv[index + 1 :]

    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app", help="Nuke executable, .app or folder")
    parser.add_argument("--core", help="ayon-core checkout")
    parser.add_argument(
        "--python",
        help="Python version of the Hiero build (detected from --app)",
    )
    parser.add_argument(
        "--timeout", type=int, default=1800, help="seconds (default 1800)"
    )
    args = parser.parse_args(argv)

    executable = find_hiero_executable(args.app)
    version = _nuke_version(executable)
    python_version = args.python or PYTHON_BY_NUKE_MAJOR.get(
        version[0] if version else None
    )
    if not python_version:
        raise SystemExit("Unknown Hiero Python version, pass --python.")

    core_client = find_ayon_core_client(args.core)
    test_paths = [
        ensure_dependencies(python_version),
        core_client,
        os.path.join(core_client, "ayon_core", "vendor", "python"),
        os.path.join(REPO_ROOT, "client"),
    ]

    app_tag = os.path.basename(executable).replace(".exe", "")
    junit = os.path.join(RESULTS_DIR, f"junit-{app_tag}.xml")
    if not pytest_args:
        pytest_args = [HIERO_TESTS_DIR]
    pytest_args = pytest_args + ["--junitxml", junit]
    return run(executable, test_paths, pytest_args, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
