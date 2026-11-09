"""Fixtures for the tests that run inside Hiero.

The test media is an EXR sequence 1001-1100 whose red channel holds the
frame number, `(frame - 1000) / 1000`, so every test can check which source
frame was rendered into which output frame (`source_frame`).
"""

import itertools
import os
import re
import shutil
import subprocess
import time

import pytest

try:
    import hiero.core  # noqa: F401
except ImportError:
    # Not inside Hiero: nothing here can run.
    collect_ignore_glob = ["test_*.py"]

MEDIA_FIRST_FRAME = 1001
MEDIA_LAST_FRAME = 1100

_counter = itertools.count(1)


def _tool(env_name, name):
    path = os.environ.get(env_name) or shutil.which(name)
    if not path:
        pytest.skip(f"`{name}` not found, set {env_name}")
    return path


@pytest.fixture(scope="session")
def oiiotool():
    return _tool("OIIOTOOL", "oiiotool")


@pytest.fixture(scope="session")
def ffprobe():
    return _tool("FFPROBE", "ffprobe")


@pytest.fixture(scope="session")
def frame_coded_sequence(tmp_path_factory, oiiotool):
    """First file of an EXR sequence 1001-1100 with frame-coded pixels."""
    folder = tmp_path_factory.mktemp("media")
    subprocess.run(
        [
            oiiotool,
            "--frames",
            f"{MEDIA_FIRST_FRAME}-{MEDIA_LAST_FRAME}",
            "--pattern",
            "constant:color={(FRAME_NUMBER-1000)/1000},0.25,0.5",
            "320x180",
            "3",
            "-d",
            "half",
            "-o",
            str(folder / "plate.#.exr"),
        ],
        check=True,
        capture_output=True,
    )
    files = sorted(folder.glob("plate.*.exr"))
    assert len(files) == MEDIA_LAST_FRAME - MEDIA_FIRST_FRAME + 1
    return str(files[0])


@pytest.fixture(scope="session")
def pixel_average(oiiotool):
    """Return the average RGB of an image file."""
    avg_re = re.compile(r"Stats Avg:\s+([-\d.e]+)\s+([-\d.e]+)\s+([-\d.e]+)")

    def _pixel_average(path):
        output = subprocess.run(
            [oiiotool, "-v", "--stats", str(path)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        match = avg_re.search(output)
        assert match, output
        return tuple(float(value) for value in match.groups())

    return _pixel_average


@pytest.fixture(scope="session")
def source_frame(pixel_average):
    """Return the source frame number coded in a rendered image."""

    def _source_frame(path):
        red = pixel_average(path)[0]
        return int(round(red * 1000)) + 1000

    return _source_frame


@pytest.fixture
def project():
    import hiero.core

    project = hiero.core.newProject(f"ayon_tests_{next(_counter)}")
    yield project
    project.close()


@pytest.fixture
def make_shot(project, frame_coded_sequence):
    """Factory for a shot on a new sequence of the test project.

    `source_in` / `source_out` are frames of the clip, counted from 0, so
    0 is media frame 1001.
    """
    import hiero.core

    def _make_shot(
        source_in=20,
        source_out=69,
        timeline_in=0,
        speed=None,
        name="sh010",
        media=None,
    ):
        clip = hiero.core.Clip(
            hiero.core.MediaSource(media or frame_coded_sequence)
        )
        project.clipsBin().addItem(hiero.core.BinItem(clip))
        sequence = hiero.core.Sequence(f"seq_{next(_counter)}")
        project.clipsBin().addItem(hiero.core.BinItem(sequence))
        track = hiero.core.VideoTrack("V1")
        sequence.addTrack(track)

        item = track.createTrackItem(name)
        item.setSource(clip)
        duration = source_out - source_in + 1
        item.setTimelineIn(timeline_in)
        item.setTimelineOut(timeline_in + duration - 1)
        item.setSourceIn(source_in)
        item.setSourceOut(source_out)
        track.addItem(item)
        if speed is not None:
            item.setPlaybackSpeed(speed)
        return item

    return _make_shot


@pytest.fixture(scope="session")
def frame_server():
    """Wait until the Hiero Frame Server runs, skip when it does not."""
    import hiero.ui
    from qtpy import QtWidgets

    server = hiero.ui.nuke_bridge.FnNsFrameServer
    deadline = time.time() + 120
    while time.time() < deadline and not server.isServerRunning():
        QtWidgets.QApplication.processEvents()
        time.sleep(0.2)
    if not server.isServerRunning():
        pytest.skip("Frame Server did not start")
    return server
