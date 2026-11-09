"""`ExtractProductResources` publish plugin in a real Hiero session.

The plugin runs on a plate instance with the data the Hiero and ayon-core
collectors provide. The parity tests run ayon-core's
`CollectOTIOProductResources` on the same shot first and compare the
rendered representation with the original media one.
"""

import importlib.util
import os
import re

import pytest
from conftest import load_publish_plugin

FRAME_RE = re.compile(r"\.(\d+)\.\w+$")
ORIGINAL = {
    "name": "exr",
    "ext": "exr",
    "files": ["plate.1011.exr"],
    "stagingDir": "/media",
    "tags": [],
}


def _output(**kwargs):
    output = {
        "repre_name": "plate_exr",
        "tags": [],
        "custom_tags": [],
        "file_type": "exr",
        "codec_properties": [
            {"name": "datatype", "value": "16 bit half"},
            {"name": "compression", "value": "Zip (1 scanline)"},
        ],
        "colorspace": "",
        "with_handles": True,
        "include_effects": False,
    }
    output.update(kwargs)
    return output


def _profile(outputs, **kwargs):
    profile = {
        "name": "Plate #1",
        "task_types": [],
        "task_names": [],
        "product_base_type": "plate",
        "keep_original_representation": False,
        "plate": outputs,
    }
    profile.update(kwargs)
    return profile


def _run(instance, profiles, render_submission="Single Render Process"):
    plugin_class = load_publish_plugin(
        "extract_product_resources.py",
        "ExtractProductResources",
        profiles=profiles,
        render_submission=render_submission,
    )
    plugin_class().process(instance)
    return instance.data["representations"]


def _by_name(representations):
    return {repre["name"]: repre for repre in representations}


def test_no_matching_profile_keeps_original(make_shot, plate_instance):
    instance = plate_instance(make_shot(), representations=[dict(ORIGINAL)])
    profiles = [_profile([_output()], task_types=["Compositing"])]

    representations = _run(instance, profiles)

    assert representations == [ORIGINAL]
    assert not os.path.exists(instance.data["stagingDir"])


def test_profile_replaces_original(make_shot, plate_instance):
    instance = plate_instance(make_shot(), representations=[dict(ORIGINAL)])

    representations = _run(instance, [_profile([_output()])])

    assert [repre["name"] for repre in representations] == ["plate_exr"]


def test_profile_keeps_original(make_shot, plate_instance):
    instance = plate_instance(make_shot(), representations=[dict(ORIGINAL)])
    profiles = [
        _profile([_output()], keep_original_representation=True),
    ]

    representations = _run(instance, profiles)

    assert [repre["name"] for repre in representations] == [
        "exr",
        "plate_exr",
    ]


def test_profile_without_outputs_raises(make_shot, plate_instance):
    from ayon_core.pipeline import PublishError

    instance = plate_instance(make_shot(), representations=[dict(ORIGINAL)])

    with pytest.raises(PublishError):
        _run(instance, [_profile([])])


def test_representation_fields(make_shot, plate_instance):
    instance = plate_instance(make_shot())
    outputs = [_output(tags=["passing"], custom_tags=["plates"])]

    (repre,) = _run(instance, [_profile(outputs)])

    assert repre["name"] == repre["outputName"] == "plate_exr"
    assert repre["ext"] == "exr"
    assert (repre["frameStart"], repre["frameEnd"]) == (991, 1060)
    assert len(repre["files"]) == 70
    assert all(
        os.path.isfile(os.path.join(repre["stagingDir"], filename))
        for filename in repre["files"]
    )
    assert repre["tags"] == ["passing"]
    assert repre["custom_tags"] == ["plates"]
    assert repre["colorspaceData"]["colorspace"] == "scene_linear"


def test_output_colorspace_on_representation(make_shot, plate_instance):
    instance = plate_instance(make_shot())

    (repre,) = _run(instance, [_profile([_output(colorspace="sRGB")])])

    assert repre["colorspaceData"]["colorspace"] == "sRGB"


def test_empty_representation_name_uses_extension(make_shot, plate_instance):
    instance = plate_instance(make_shot())
    output = _output(repre_name="", file_type="jpeg", codec_properties=[])

    (repre,) = _run(instance, [_profile([output])])

    assert repre["name"] == repre["ext"] == "jpg"


def test_name_clash_with_kept_original_raises(make_shot, plate_instance):
    from ayon_core.pipeline import PublishError

    instance = plate_instance(make_shot(), representations=[dict(ORIGINAL)])
    profiles = [
        _profile([_output(repre_name="")], keep_original_representation=True),
    ]

    with pytest.raises(PublishError, match="'exr'"):
        _run(instance, profiles)
    assert not os.path.exists(instance.data["stagingDir"])


def test_version_handles_follow_rendered_files(make_shot, plate_instance):
    instance = plate_instance(
        make_shot(), versionData={"handleStart": 10, "handleEnd": 10}
    )

    _run(instance, [_profile([_output(with_handles=False)])])

    version_data = instance.data["versionData"]
    assert (version_data["handleStart"], version_data["handleEnd"]) == (0, 0)
    assert (instance.data["handleStart"], instance.data["handleEnd"]) == (
        0,
        0,
    )


def test_version_handles_kept_with_original(make_shot, plate_instance):
    instance = plate_instance(
        make_shot(),
        versionData={"handleStart": 10, "handleEnd": 10},
        representations=[dict(ORIGINAL)],
    )
    profiles = [
        _profile(
            [_output(with_handles=False)], keep_original_representation=True
        ),
    ]

    _run(instance, profiles)

    version_data = instance.data["versionData"]
    assert (version_data["handleStart"], version_data["handleEnd"]) == (
        10,
        10,
    )


def test_review_tag_adds_review_family(make_shot, plate_instance):
    instance = plate_instance(make_shot())

    _run(instance, [_profile([_output(tags=["review"])])])

    assert "review" in instance.data["families"]


def test_without_handles(make_shot, plate_instance):
    instance = plate_instance(make_shot())

    (repre,) = _run(instance, [_profile([_output(with_handles=False)])])

    assert (repre["frameStart"], repre["frameEnd"]) == (1001, 1050)
    assert len(repre["files"]) == 50


def test_two_outputs(make_shot, plate_instance):
    instance = plate_instance(make_shot())
    outputs = [
        _output(),
        _output(repre_name="proxy", file_type="mov", codec_properties=[]),
    ]

    representations = _by_name(_run(instance, [_profile(outputs)]))

    assert set(representations) == {"plate_exr", "proxy"}
    proxy = representations["proxy"]
    assert proxy["ext"] == "mov"
    assert isinstance(proxy["files"], str)
    assert os.path.isfile(os.path.join(proxy["stagingDir"], proxy["files"]))
    assert proxy["stagingDir"] != representations["plate_exr"]["stagingDir"]


def test_offline_media_raises_publish_error(
    make_shot, plate_instance, tmp_path
):
    from ayon_core.pipeline import PublishError

    item = make_shot(media=str(tmp_path / "missing" / "plate.1001.exr"))
    instance = plate_instance(item)

    with pytest.raises(PublishError, match="offline"):
        _run(instance, [_profile([_output()])])


def _collect_original_media(instance):
    """Run ayon-core's `CollectOTIOProductResources` on the instance."""
    import ayon_core
    from ayon_hiero.api.otio import hiero_export

    item = instance.data["trackItem"]
    otio_timeline = hiero_export.create_otio_timeline(
        sequence=item.parent().parent()
    )
    otio_clip = next(
        clip
        for track in otio_timeline.tracks
        for clip in track
        if getattr(clip, "media_reference", None) is not None
        and clip.name == item.name()
    )
    instance.data["otioClip"] = otio_clip

    path = os.path.join(
        os.path.dirname(ayon_core.__file__),
        "plugins",
        "publish",
        "collect_otio_product_resources.py",
    )
    spec = importlib.util.spec_from_file_location("_core_collector", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.CollectOTIOProductResources().process(instance)
    (original,) = instance.data["representations"]
    return dict(original)


@pytest.mark.parametrize(
    "shot",
    [
        pytest.param({}, id="plain"),
        pytest.param(
            {"source_in": 20, "source_out": 59, "speed": 2.0}, id="retimed"
        ),
    ],
)
def test_same_frames_as_original_media(
    make_shot, plate_instance, source_frame, shot
):
    instance = plate_instance(make_shot(**shot))
    original = _collect_original_media(instance)
    profiles = [_profile([_output()], keep_original_representation=True)]

    rendered = _by_name(_run(instance, profiles))["plate_exr"]

    details = (
        f"original {original['frameStart']}-{original['frameEnd']} "
        f"{original['files'][0]}..{original['files'][-1]}, rendered "
        f"{rendered['frameStart']}-{rendered['frameEnd']}, "
        f"versionData {instance.data['versionData']}"
    )
    assert (rendered["frameStart"], rendered["frameEnd"]) == (
        original["frameStart"],
        original["frameEnd"],
    ), details
    assert len(rendered["files"]) == len(original["files"]), details
    first = os.path.join(rendered["stagingDir"], rendered["files"][0])
    last = os.path.join(rendered["stagingDir"], rendered["files"][-1])
    original_first = int(FRAME_RE.search(original["files"][0]).group(1))
    original_last = int(FRAME_RE.search(original["files"][-1]).group(1))
    assert (source_frame(first), source_frame(last)) == (
        original_first,
        original_last,
    ), details


@pytest.mark.parametrize(
    "shot",
    [
        pytest.param({}, id="plain"),
        pytest.param(
            {"source_in": 20, "source_out": 59, "speed": 2.0}, id="retimed"
        ),
    ],
)
def test_same_frames_as_original_movie(
    make_shot, plate_instance, frame_coded_movie, movie_frame, shot
):
    item = make_shot(media=frame_coded_movie, **shot)
    instance = plate_instance(item)
    original = _collect_original_media(instance)
    # ayon-core trims the movie to this range, counted from its first
    # frame; without a trim range the whole movie is published
    trim = instance.data.get("otioTrimmingRange")
    if trim is None:
        trim_start = 0
        trim_duration = (
            instance.data["otioClip"].available_range().duration.to_frames()
        )
    else:
        trim_start = trim.start_time.to_frames()
        trim_duration = trim.duration.to_frames()
    # Written in the movie's colourspace, so the gray levels round-trip
    output = _output(colorspace=item.sourceMediaColourTransform())
    profiles = [_profile([output], keep_original_representation=True)]

    rendered = _by_name(_run(instance, profiles))["plate_exr"]

    details = (
        f"original {original['frameStart']}-{original['frameEnd']}, "
        f"trim {trim_start}+{trim_duration}, rendered "
        f"{rendered['frameStart']}-{rendered['frameEnd']} "
        f"({len(rendered['files'])} files), "
        f"versionData {instance.data['versionData']}"
    )
    assert (rendered["frameStart"], rendered["frameEnd"]) == (
        original["frameStart"],
        original["frameEnd"],
    ), details
    assert len(rendered["files"]) == trim_duration, details
    first = os.path.join(rendered["stagingDir"], rendered["files"][0])
    last = os.path.join(rendered["stagingDir"], rendered["files"][-1])
    assert (movie_frame(first), movie_frame(last)) == (
        trim_start,
        trim_start + trim_duration - 1,
    ), details
