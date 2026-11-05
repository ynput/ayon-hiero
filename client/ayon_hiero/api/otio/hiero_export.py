"""Hiero sequence to OTIO timeline.

The host only reads Hiero objects (track items, media sources, tags, soft
effects) and turns them into specs. `ayon_editorial.otio` builds the OTIO
objects: timeline, tracks, gaps, clips, references, markers and retime
effects.
"""

from typing import List, Optional
import os
import re

import hiero.core
import hiero.ui
import opentimelineio as otio
from ayon_editorial.otio import effects
from ayon_editorial.otio.builder import (
    GAP_RECORD,
    ClipSpec,
    MarkerSpec,
    MediaSpec,
    SequenceSpec,
    SpeedEffectSpec,
    TimelineBuilder,
    TimeWarpEffectSpec,
    write_to_file,  # noqa: F401 (public, used by the exporter task)
)
from ayon_editorial.otio.time import create_time_range

from . import utils

# Kept for the exporter UI/task, which set it; the export always adds tags.
include_tags = True

# Public name used by the old publish workflow
create_otio_time_range = create_time_range

TRACK_TYPE_MAP = {
    hiero.core.VideoTrack: otio.schema.TrackKind.Video,
    hiero.core.AudioTrack: otio.schema.TrackKind.Audio
}
MARKER_COLOR_MAP = {
    "magenta": otio.schema.MarkerColor.MAGENTA,
    "red": otio.schema.MarkerColor.RED,
    "yellow": otio.schema.MarkerColor.YELLOW,
    "green": otio.schema.MarkerColor.GREEN,
    "cyan": otio.schema.MarkerColor.CYAN,
    "blue": otio.schema.MarkerColor.BLUE,
}


def flatten(list_):
    for item_ in list_:
        if isinstance(item_, (list, tuple)):
            for sub_item in flatten(item_):
                yield sub_item
        else:
            yield item_


def _get_metadata(item):
    if hasattr(item, "metadata"):
        return {key: value for key, value in dict(item.metadata()).items()}
    return {}


def get_marker_color(tag):
    icon = tag.icon()
    res = re.search(r"icons:Tag(?P<color>\w+)\.\w+", icon)
    if res:
        color = res.groupdict().get("color")
        if color.lower() in MARKER_COLOR_MAP:
            return MARKER_COLOR_MAP[color.lower()]

    return otio.schema.MarkerColor.RED


def get_marker_specs(item, project_fps) -> List[MarkerSpec]:
    """Read the visible tags of a track, track item or clip."""
    specs = []
    for tag in item.tags():
        if not tag.visible():
            continue

        if tag.name() == "Copy":
            # Hiero adds this tag to a lot of clips
            continue

        tag_data = tag.metadata().dict()
        # tag metadata without the "tag." prefix
        metadata = {
            key.replace("tag.", ""): value
            for key, value in tag_data.items()
        }
        # Store the source item for future import assignment
        metadata["hiero_source_type"] = item.__class__.__name__

        specs.append(MarkerSpec(
            name=tag.name(),
            start=tag.inTime(),
            duration=int(tag_data.get("tag.length", "0")),
            color=get_marker_color(tag),
            metadata=metadata,
            rate=utils.get_rate(item) or project_fps,
        ))
    return specs


def _knob_value(knob, track_item):
    """Knob value, or the per frame offset of an animated one."""
    if not knob.isAnimated():
        return knob.value()
    first = track_item.timelineIn()
    return effects.lookup_from_frames(
        [
            knob.getValueAt(frame)
            for frame in range(first, track_item.timelineOut() + 1)
        ],
        first,
    )


def get_effect_specs(track_item) -> list:
    """Read the speed of a track item and its TimeWarp soft effects."""
    specs = [SpeedEffectSpec(track_item.playbackSpeed())]

    for effect in flatten(track_item.parent().subTrackItems()):
        linked_items = effect.linkedItems()
        if track_item not in linked_items and len(linked_items) > 0:
            continue

        # avoid all effect which are not TimeWarp and disabled
        if "TimeWarp" not in effect.name():
            continue

        if not effect.isEnabled():
            continue

        node = effect.node()
        specs.append(TimeWarpEffectSpec(
            lookup=_knob_value(node["lookup"], track_item),
            name=node["name"].value(),
            effect_name=effects.timewarp_effect_name(effect.name()),
            metadata={"length": _knob_value(node["length"], track_item)},
        ))
    return specs


def get_media_spec(clip, project_fps) -> MediaSpec:
    media_source = clip.mediaSource()

    # get file info for path and start frame
    file_info = media_source.fileinfos().pop()
    path = file_info.filename()
    fps = utils.get_rate(clip) or project_fps

    metadata = _get_metadata(media_source)
    metadata.update(_get_metadata(clip))

    sequence = None
    if not media_source.singleFile():
        padding = media_source.filenamePadding()
        metadata.update({"isSequence": True, "padding": padding})
        sequence = SequenceSpec(
            target_url_base=os.path.dirname(path) + os.sep,
            name_prefix=media_source.filenameHead(),
            name_suffix=os.path.splitext(path)[-1],
            start_frame=file_info.startFrame(),
            padding=padding,
        )

    # add resolution metadata
    metadata.update({
        "ayon.source.colorspace": clip.sourceMediaColourTransform(),
        "ayon.source.width": int(media_source.width()),
        "ayon.source.height": int(media_source.height()),
        "ayon.source.pixelAspect": float(media_source.pixelAspect())
    })

    return MediaSpec(
        target_url=utils.get_reformated_path(path, padded=False),
        available_start=media_source.timecodeStart(),
        available_duration=media_source.duration(),
        rate=fps,
        metadata=metadata,
        sequence=sequence,
    )


def get_clip_spec(track_item, project_fps) -> ClipSpec:
    clip = track_item.source()
    speed = track_item.playbackSpeed()
    # flip if speed is in minus
    source_in = track_item.sourceIn() if speed > 0 else track_item.sourceOut()

    markers = get_marker_specs(track_item, project_fps)
    markers += get_marker_specs(clip, project_fps)

    # time effects only if video
    has_audio = clip.mediaSource().hasAudio()
    return ClipSpec(
        name=track_item.name(),
        source_offset=source_in,
        duration=int(track_item.duration()),
        media=get_media_spec(clip, project_fps),
        rate=utils.get_rate(track_item) or project_fps,
        record_in=track_item.timelineIn(),
        record_out=track_item.timelineOut(),
        markers=markers,
        effects=[] if has_audio else get_effect_specs(track_item),
    )


def _get_timeline_metadata(sequence) -> dict:
    project = sequence.project()
    sequence_format = sequence.format()
    metadata = _get_metadata(sequence)
    metadata.update({
        "ayon.timeline.width": int(sequence_format.width()),
        "ayon.timeline.height": int(sequence_format.height()),
        "ayon.timeline.pixelAspect": int(sequence_format.pixelAspect()),
        "ayon.project.useOCIOEnvironmentOverride": project.useOCIOEnvironmentOverride(),  # noqa
        "ayon.project.lutSetting16Bit": project.lutSetting16Bit(),
        "ayon.project.lutSetting8Bit": project.lutSetting8Bit(),
        "ayon.project.lutSettingFloat": project.lutSettingFloat(),
        "ayon.project.lutSettingLog": project.lutSettingLog(),
        "ayon.project.lutSettingViewer": project.lutSettingViewer(),
        "ayon.project.lutSettingWorkingSpace": project.lutSettingWorkingSpace(),  # noqa
        "ayon.project.lutUseOCIOForExport": project.lutUseOCIOForExport(),
        "ayon.project.ocioConfigName": project.ocioConfigName(),
        "ayon.project.ocioConfigPath": project.ocioConfigPath()
    })
    return metadata


def create_otio_timeline(
    sequence: Optional[hiero.core.Sequence] = None,
) -> otio.schema.Timeline:
    sequence = sequence or hiero.ui.activeSequence()
    project_fps = sequence.framerate().toFloat()

    builder = TimelineBuilder(
        sequence.name(),
        project_fps,
        sequence.timecodeStart(),
        _get_timeline_metadata(sequence),
        gap_mode=GAP_RECORD,
        sequence_fallback_padded=False,
    )

    for track in sequence.items():
        # skip if track is disabled
        if not track.isEnabled():
            continue

        track_builder = builder.add_track(
            track.name(),
            TRACK_TYPE_MAP[type(track)],
            get_marker_specs(track, project_fps),
        )
        for track_item in track:
            track_builder.append_clip(get_clip_spec(track_item, project_fps))

    return builder.build()
