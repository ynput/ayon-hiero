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


def _write_frame_coded_sequence(folder, oiiotool, timecode=None):
    attributes = []
    if timecode:
        attributes = ["--attrib:type=timecode", "smpte:TimeCode", timecode]
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
            *attributes,
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
def frame_coded_sequence(tmp_path_factory, oiiotool):
    """First file of an EXR sequence 1001-1100 with frame-coded pixels."""
    return _write_frame_coded_sequence(
        tmp_path_factory.mktemp("media"), oiiotool
    )


@pytest.fixture(scope="session")
def timecoded_sequence(tmp_path_factory, oiiotool):
    """`frame_coded_sequence` with an embedded timecode of 01:00:00:00.

    Hiero starts the clip's timecode, and the OTIO available range, there
    and not at the first file frame, as camera plates do.
    """
    return _write_frame_coded_sequence(
        tmp_path_factory.mktemp("timecoded_media"),
        oiiotool,
        timecode="01:00:00:00",
    )


@pytest.fixture(scope="session")
def frame_coded_movie(tmp_path_factory, oiiotool):
    """Lossless 8-bit mov with 100 frames; gray level is 2 * frame index."""
    ffmpeg = _tool("FFMPEG", "ffmpeg")
    folder = tmp_path_factory.mktemp("movie")
    subprocess.run(
        [
            oiiotool,
            "--frames",
            "0-99",
            "--pattern",
            "constant:color={FRAME_NUMBER*2/255},{FRAME_NUMBER*2/255},"
            "{FRAME_NUMBER*2/255}",
            "320x180",
            "3",
            "-d",
            "uint8",
            "-o",
            str(folder / "frame.#.png"),
        ],
        check=True,
        capture_output=True,
    )
    movie = folder / "plate.mov"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-framerate",
            "24",
            "-start_number",
            "0",
            "-i",
            str(folder / "frame.%04d.png"),
            "-c:v",
            "png",
            "-pix_fmt",
            "rgb24",
            str(movie),
        ],
        check=True,
        capture_output=True,
    )
    return str(movie)


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


@pytest.fixture(scope="session")
def movie_frame(pixel_average):
    """Return the frame index coded in an image rendered from the movie.

    The image must be written in the movie's colourspace.
    """

    def _movie_frame(path):
        red = pixel_average(path)[0]
        return int(round(red * 255 / 2))

    return _movie_frame


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


PUBLISH_PLUGINS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "client",
    "ayon_hiero",
    "plugins",
    "publish",
)


def load_publish_plugin(filename, class_name, **attributes):
    """Load a publish plugin class from its file, with `attributes` set.

    The attributes are set on a subclass, the way settings are applied,
    so tests do not change the plugin for each other.
    """
    import importlib.util

    path = os.path.join(PUBLISH_PLUGINS_DIR, filename)
    spec = importlib.util.spec_from_file_location(
        f"_ayon_hiero_tests_{class_name}", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    plugin_class = getattr(module, class_name)
    return type(class_name, (plugin_class,), dict(attributes))


class StubTemplateItem:
    def __init__(self, template):
        self.template = template


class StubAnatomy:
    """Anatomy with one publish path template, enough for collectors."""

    publish_template = (
        "{root[work]}/{project[name]}/{folder[name]}/publish/"
        "{product[name]}/v{version:0>3}/"
        "{product[name]}_v{version:0>3}.{frame}.{ext}"
    )

    def get_template_item(self, *_args, **_kwargs):
        return StubTemplateItem(self.publish_template)


@pytest.fixture
def plate_instance(tmp_path):
    """Factory for a plate instance with the data collectors provide.

    The context has the colorspace settings cached
    (`imageioSettings`), so colorspace data is set without a server.
    """
    import pyblish.api

    def _plate_instance(
        track_item,
        task_type="Edit",
        task_name="edit",
        handles=10,
        **data,
    ):
        context = pyblish.api.Context()
        context.data.update(
            {
                "projectName": "ayon_tests",
                "hostName": "hiero",
                "anatomy": StubAnatomy(),
                "project_settings": {
                    "core": {
                        "tools": {
                            "publish": {
                                "template_name_profiles": [],
                                "hero_template_name_profiles": [],
                            }
                        }
                    }
                },
                "imageioSettings": (
                    {
                        "path": "/configs/config.ocio",
                        "template": "/configs/config.ocio",
                    },
                    {},
                ),
            }
        )
        instance = context.create_instance("plateMain")
        instance.data.update(
            {
                "productName": "plateMain",
                "productType": "plate",
                "productBaseType": "plate",
                "family": "plate",
                "families": ["plate", "clip"],
                "trackItem": track_item,
                "frameStart": 1001,
                "handleStart": handles,
                "handleEnd": handles,
                "versionData": {},
                "anatomyData": {
                    "task": {"name": task_name, "type": task_type},
                },
                "stagingDir": str(tmp_path / "staging"),
                "representations": [],
            }
        )
        instance.data.update(data)
        return instance

    return _plate_instance
