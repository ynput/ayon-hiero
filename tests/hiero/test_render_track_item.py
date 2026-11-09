"""`ayon_hiero.api.rendering.render_track_item` in a real Hiero session.

The default shot uses clip frames 20-69 (media 1021-1070) on timeline
frames 0-49. Outputs start at frame 1001 at the cut in, so with 10 frames
of handles the files are 0991-1060 and hold media frames 1011-1080.
"""

import os
import re
import subprocess

import pytest

from ayon_hiero.api import rendering

SUBMISSIONS = [
    "Single Render Process",
    pytest.param("Frame Server", marks=pytest.mark.frameserver),
]
EXR_PROPERTIES = {"datatype": "16 bit half", "compression": "Zip (1 scanline)"}
FRAME_RE = re.compile(r"\.(\d+)\.\w+$")


def _render(item, tmp_path, **kwargs):
    options = {
        "name": "plate",
        "file_type": "exr",
        "codec_properties": EXR_PROPERTIES,
        "frame_start": 1001,
        "handle_start": 10,
        "handle_end": 10,
    }
    options.update(kwargs)
    return rendering.render_track_item(
        item, str(tmp_path / "render"), **options
    )


def _frame(path):
    return int(FRAME_RE.search(path).group(1))


def _use_submission(request, submission):
    if submission == "Frame Server":
        request.getfixturevalue("frame_server")


@pytest.mark.parametrize("submission", SUBMISSIONS)
def test_returns_when_all_files_exist(
    request, make_shot, tmp_path, submission
):
    _use_submission(request, submission)
    result = _render(make_shot(), tmp_path, submission=submission)

    assert len(result.files) == 70
    assert all(os.path.isfile(path) for path in result.files)


def test_frames_with_handles(make_shot, tmp_path, source_frame):
    result = _render(make_shot(), tmp_path)

    frames = [_frame(path) for path in result.files]
    assert frames == list(range(991, 1061))
    assert (result.frame_start, result.frame_end) == (991, 1060)
    assert (result.handle_start, result.handle_end) == (10, 10)
    by_frame = dict(zip(frames, result.files))
    assert source_frame(by_frame[991]) == 1011
    assert source_frame(by_frame[1001]) == 1021
    assert source_frame(by_frame[1050]) == 1070
    assert source_frame(by_frame[1060]) == 1080


def test_frames_without_handles(make_shot, tmp_path, source_frame):
    result = _render(make_shot(), tmp_path, handle_start=0, handle_end=0)

    assert [_frame(path) for path in result.files] == list(range(1001, 1051))
    assert source_frame(result.files[0]) == 1021
    assert source_frame(result.files[-1]) == 1070


def test_different_head_and_tail_handles(make_shot, tmp_path, source_frame):
    result = _render(make_shot(), tmp_path, handle_start=5, handle_end=10)

    assert [_frame(path) for path in result.files] == list(range(996, 1061))
    assert (result.handle_start, result.handle_end) == (5, 10)
    assert source_frame(result.files[0]) == 1016
    assert source_frame(result.files[-1]) == 1080


def test_handles_clamped_to_available_media(make_shot, tmp_path, source_frame):
    # 3 frames of media before the cut in, 4 after the cut out
    result = _render(make_shot(source_in=3, source_out=95), tmp_path)

    assert (result.handle_start, result.handle_end) == (3, 4)
    frames = [_frame(path) for path in result.files]
    assert frames == list(range(998, 1001 + 93 + 4))
    assert source_frame(result.files[0]) == 1001
    assert source_frame(result.files[-1]) == 1100


@pytest.mark.parametrize("submission", SUBMISSIONS)
def test_movie_output(request, make_shot, tmp_path, ffprobe, submission):
    _use_submission(request, submission)
    result = _render(
        make_shot(),
        tmp_path,
        file_type="mov",
        codec_properties={},
        submission=submission,
    )

    assert not result.is_sequence
    assert len(result.files) == 1
    assert result.files[0].endswith(".mov")
    output = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-count_frames",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=nb_read_frames",
            "-of",
            "csv=p=0",
            result.files[0],
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert int(output.strip()) == 70


def test_linear_exr_keeps_pixel_values(
    project, make_shot, tmp_path, pixel_average, frame_coded_sequence
):
    result = _render(make_shot(), tmp_path)

    assert result.colorspace == project.lutSettingFloat()
    source = frame_coded_sequence.replace(".1001.", ".1021.")
    by_frame = {_frame(path): path for path in result.files}
    assert pixel_average(by_frame[1001]) == pytest.approx(
        pixel_average(source), abs=1e-4
    )


def test_output_colorspace_is_applied(make_shot, tmp_path, pixel_average):
    result = _render(make_shot(), tmp_path, colorspace="sRGB")

    assert result.colorspace == "sRGB"
    # linear 0.25 and 0.5 encoded with the sRGB curve
    _, green, blue = pixel_average(result.files[0])
    assert green == pytest.approx(0.537, abs=0.01)
    assert blue == pytest.approx(0.735, abs=0.01)


def test_offline_media_raises(make_shot, tmp_path):
    item = make_shot(media=str(tmp_path / "missing" / "plate.1001.exr"))

    with pytest.raises(rendering.RenderError, match="offline"):
        _render(item, tmp_path)


def _add_grade(item):
    effect = item.parentTrack().createEffect("Grade", trackItem=item)
    effect.node()["white"].setValue(2.0)
    return effect


def test_effects_not_baked_by_default(make_shot, tmp_path, pixel_average):
    item = make_shot()
    _add_grade(item)

    result = _render(item, tmp_path)

    assert pixel_average(result.files[0])[1] == pytest.approx(0.25, abs=1e-3)


def test_effects_baked_with_include_effects(
    make_shot, tmp_path, pixel_average
):
    item = make_shot()
    _add_grade(item)

    result = _render(item, tmp_path, include_effects=True)

    assert pixel_average(result.files[0])[1] == pytest.approx(0.5, abs=1e-3)


def test_output_folder_holds_only_rendered_files(make_shot, tmp_path):
    result = _render(make_shot(), tmp_path)

    on_disk = sorted(
        os.path.join(root, name)
        for root, _, names in os.walk(str(tmp_path / "render"))
        for name in names
    )
    assert on_disk == sorted(result.files)


def test_retimed_shot_renders_source_range(make_shot, tmp_path, source_frame):
    # Retimes are not baked: the source range of the item is rendered and
    # handles count source frames. At 2x Hiero keeps the timeline range
    # 0-39 and stretches the source range to 20-98.
    item = make_shot(source_in=20, source_out=59, speed=2.0)
    assert (int(item.sourceIn()), int(item.sourceOut())) == (20, 98)

    result = _render(item, tmp_path)

    # 10 frames of media before the cut in, 1 after the cut out
    assert (result.handle_start, result.handle_end) == (10, 1)
    frames = [_frame(path) for path in result.files]
    assert frames == list(range(991, 1001 + 78 + 1 + 1))
    assert source_frame(result.files[0]) == 1011
    assert source_frame(result.files[-1]) == 1100


def test_track_item_tags_unchanged(make_shot, tmp_path):
    item = make_shot()
    tags_before = sorted(tag.name() for tag in item.tags())

    _render(item, tmp_path)

    assert sorted(tag.name() for tag in item.tags()) == tags_before
