""" compatibility OpenTimelineIO 0.12.0 and newer
"""

import os
import re
import opentimelineio as otio
from . import utils
import hiero.core
import hiero.ui


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


class CTX:
    project_fps = None
    timeline = None
    include_tags = True


def flatten(list_):
    for item_ in list_:
        if isinstance(item_, (list, tuple)):
            for sub_item in flatten(item_):
                yield sub_item
        else:
            yield item_


def create_otio_rational_time(frame, fps):
    return otio.opentime.RationalTime(
        float(frame),
        float(fps)
    )


def create_otio_time_range(start_frame, frame_duration, fps):
    return otio.opentime.TimeRange(
        start_time=create_otio_rational_time(start_frame, fps),
        duration=create_otio_rational_time(frame_duration, fps)
    )


def _get_metadata(item):
    if hasattr(item, 'metadata'):
        return {key: value for key, value in dict(item.metadata()).items()}
    return {}


def create_time_effects(otio_clip, track_item):
    # get all subtrack items
    subTrackItems = flatten(track_item.parent().subTrackItems())
    speed = track_item.playbackSpeed()

    otio_effect = None
    # retime on track item
    if speed != 1.:
        # make effect
        otio_effect = otio.schema.LinearTimeWarp()
        otio_effect.name = "Speed"
        otio_effect.time_scalar = speed

    # freeze frame effect
    if speed == 0.:
        otio_effect = otio.schema.FreezeFrame()
        otio_effect.name = "FreezeFrame"

    if otio_effect:
        # add otio effect to clip effects
        otio_clip.effects.append(otio_effect)

    # loop through and get all Timewarps
    for effect in subTrackItems:
        if ((track_item not in effect.linkedItems())
                and (len(effect.linkedItems()) > 0)):
            continue
        # avoid all effect which are not TimeWarp and disabled
        if "TimeWarp" not in effect.name():
            continue

        if not effect.isEnabled():
            continue

        node = effect.node()
        name = node["name"].value()

        # solve effect class as effect name
        _name = effect.name()
        if "_" in _name:
            effect_name = re.sub(r"(?:_)[_0-9]+", "", _name)  # more numbers
        else:
            effect_name = re.sub(r"\d+", "", _name)  # one number

        metadata = {}
        # add knob to metadata
        for knob in ["lookup", "length"]:
            value = node[knob].value()
            animated = node[knob].isAnimated()
            if animated:
                value = [
                    ((node[knob].getValueAt(i)) - i)
                    for i in range(
                        track_item.timelineIn(), track_item.timelineOut() + 1)
                ]

            metadata[knob] = value

        # make effect
        otio_effect = otio.schema.TimeEffect()
        otio_effect.name = name
        otio_effect.effect_name = effect_name
        otio_effect.metadata.update(metadata)

        # add otio effect to clip effects
        otio_clip.effects.append(otio_effect)


def create_otio_reference(clip):
    metadata = _get_metadata(clip)
    media_source = clip.mediaSource()

    # get file info for path and start frame
    file_info = media_source.fileinfos().pop()
    start_frame = file_info.startFrame()
    timecode_start = media_source.timecodeStart()
    path = file_info.filename()

    # get padding and other file infos
    padding = media_source.filenamePadding()
    file_head = media_source.filenameHead()
    is_sequence = not media_source.singleFile()
    frame_duration = media_source.duration()
    fps = utils.get_rate(clip) or CTX.project_fps
    extension = os.path.splitext(path)[-1]

    if is_sequence:
        metadata.update({
            "isSequence": True,
            "padding": padding
        })

    # add resolution metadata
    metadata.update({
        "ayon.source.colorspace": clip.sourceMediaColourTransform(),
        "ayon.source.width": int(media_source.width()),
        "ayon.source.height": int(media_source.height()),
        "ayon.source.pixelAspect": float(media_source.pixelAspect())
    })

    otio_ex_ref_item = None

    if is_sequence:
        # if it is file sequence try to create `ImageSequenceReference`
        # the OTIO might not be compatible so return nothing and do it old way
        try:
            dirname = os.path.dirname(path)
            otio_ex_ref_item = otio.schema.ImageSequenceReference(
                target_url_base=dirname + os.sep,
                name_prefix=file_head,
                name_suffix=extension,
                start_frame=start_frame,
                frame_zero_padding=padding,
                rate=fps,
                available_range=create_otio_time_range(
                    timecode_start,
                    frame_duration,
                    fps
                )
            )
        except AttributeError:
            pass

    if not otio_ex_ref_item:
        reformat_path = utils.get_reformated_path(path, padded=False)
        # in case old OTIO or video file create `ExternalReference`
        otio_ex_ref_item = otio.schema.ExternalReference(
            target_url=reformat_path,
            available_range=create_otio_time_range(
                timecode_start,
                frame_duration,
                fps
            )
        )

    # add metadata to otio item
    add_otio_metadata(otio_ex_ref_item, media_source, **metadata)

    return otio_ex_ref_item


def get_marker_color(tag):
    icon = tag.icon()
    pat = r'icons:Tag(?P<color>\w+)\.\w+'

    res = re.search(pat, icon)
    if res:
        color = res.groupdict().get('color')
        if color.lower() in MARKER_COLOR_MAP:
            return MARKER_COLOR_MAP[color.lower()]

    return otio.schema.MarkerColor.RED


def create_otio_markers(otio_item, item):
    for tag in item.tags():
        if not tag.visible():
            continue

        if tag.name() == 'Copy':
            # Hiero adds this tag to a lot of clips
            continue

        frame_rate = utils.get_rate(item) or CTX.project_fps

        marked_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(
                tag.inTime(),
                frame_rate
            ),
            duration=otio.opentime.RationalTime(
                int(tag.metadata().dict().get('tag.length', '0')),
                frame_rate
            )
        )
        # add tag metadata but remove "tag." string
        metadata = {}

        for key, value in tag.metadata().dict().items():
            _key = key.replace("tag.", "")

            metadata.update({_key: value})

        # Store the source item for future import assignment
        metadata['hiero_source_type'] = item.__class__.__name__

        marker = otio.schema.Marker(
            name=tag.name(),
            color=get_marker_color(tag),
            marked_range=marked_range,
            metadata=metadata
        )

        otio_item.markers.append(marker)


def create_otio_clip(track_item):
    clip = track_item.source()
    speed = track_item.playbackSpeed()
    # flip if speed is in minus
    source_in = track_item.sourceIn() if speed > 0 else track_item.sourceOut()

    duration = int(track_item.duration())

    fps = utils.get_rate(track_item) or CTX.project_fps
    name = track_item.name()

    media_reference = create_otio_reference(clip)
    available_start = media_reference.available_range.start_time
    source_in_offset = otio.opentime.RationalTime(
        source_in,
        available_start.rate
    )
    src_in = available_start + source_in_offset
    conformed_src_in = src_in.rescaled_to(fps)

    source_range = create_otio_time_range(
        conformed_src_in.value,  # no rounding to preserve accuracy
        duration,
        fps
    )

    otio_clip = otio.schema.Clip(
        name=name,
        source_range=source_range,
        media_reference=media_reference
    )

    # Add tags as markers
    if CTX.include_tags:
        create_otio_markers(otio_clip, track_item)
        create_otio_markers(otio_clip, track_item.source())

    # only if video
    if not clip.mediaSource().hasAudio():
        # Add effects to clips
        create_time_effects(otio_clip, track_item)

    return otio_clip


def create_otio_gap(gap_start, clip_start, tl_start_frame, fps):
    return otio.schema.Gap(
        source_range=create_otio_time_range(
            gap_start,
            (clip_start - tl_start_frame) - gap_start,
            fps
        )
    )


def _create_otio_timeline():
    project = CTX.timeline.project()
    metadata = _get_metadata(CTX.timeline)

    metadata.update({
        "openpype.timeline.width": int(CTX.timeline.format().width()),
        "openpype.timeline.height": int(CTX.timeline.format().height()),
        "openpype.timeline.pixelAspect": int(CTX.timeline.format().pixelAspect()),  # noqa
        "openpype.project.useOCIOEnvironmentOverride": project.useOCIOEnvironmentOverride(),  # noqa
        "openpype.project.lutSetting16Bit": project.lutSetting16Bit(),
        "openpype.project.lutSetting8Bit": project.lutSetting8Bit(),
        "openpype.project.lutSettingFloat": project.lutSettingFloat(),
        "openpype.project.lutSettingLog": project.lutSettingLog(),
        "openpype.project.lutSettingViewer": project.lutSettingViewer(),
        "openpype.project.lutSettingWorkingSpace": project.lutSettingWorkingSpace(),  # noqa
        "openpype.project.lutUseOCIOForExport": project.lutUseOCIOForExport(),
        "openpype.project.ocioConfigName": project.ocioConfigName(),
        "openpype.project.ocioConfigPath": project.ocioConfigPath()
    })

    start_time = create_otio_rational_time(
        CTX.timeline.timecodeStart(), CTX.project_fps)

    return otio.schema.Timeline(
        name=CTX.timeline.name(),
        global_start_time=start_time,
        metadata=metadata
    )


def create_otio_track(track_type, track_name):
    return otio.schema.Track(
        name=track_name,
        kind=TRACK_TYPE_MAP[track_type]
    )


def add_otio_gap(track_item, otio_track, prev_out):
    gap_length = track_item.timelineIn() - prev_out
    if prev_out != 0:
        gap_length -= 1

    gap = otio.opentime.TimeRange(
        duration=otio.opentime.RationalTime(
            gap_length,
            CTX.project_fps
        )
    )
    otio_gap = otio.schema.Gap(source_range=gap)
    otio_track.append(otio_gap)


def add_otio_metadata(otio_item, media_source, **kwargs):
    metadata = _get_metadata(media_source)

    # add additional metadata from kwargs
    if kwargs:
        metadata.update(kwargs)

    # add metadata to otio item metadata
    for key, value in metadata.items():
        otio_item.metadata.update({key: value})


def create_otio_timeline():

    # get current timeline
    CTX.timeline = hiero.ui.activeSequence()
    CTX.project_fps = CTX.timeline.framerate().toFloat()

    # convert timeline to otio
    otio_timeline = _create_otio_timeline()

    # loop all defined track types
    for track in CTX.timeline.items():
        # skip if track is disabled
        if not track.isEnabled():
            continue

        # convert track to otio
        otio_track = create_otio_track(
            type(track), track.name())

        for itemindex, track_item in enumerate(track):
            # Add Gap if needed
            if itemindex == 0:
                # if it is first track item at track then add
                # it to previous item
                prev_item = track_item

            else:
                # get previous item
                prev_item = track_item.parent().items()[itemindex - 1]

            # calculate clip frame range difference from each other
            clip_diff = track_item.timelineIn() - prev_item.timelineOut()

            # add gap if first track item is not starting
            # at first timeline frame
            if itemindex == 0 and track_item.timelineIn() > 0:
                add_otio_gap(track_item, otio_track, 0)

            # or add gap if following track items are having
            # frame range differences from each other
            elif itemindex and clip_diff != 1:
                add_otio_gap(track_item, otio_track, prev_item.timelineOut())

            # create otio clip and add it to track
            otio_clip = create_otio_clip(track_item)
            otio_track.append(otio_clip)

        # Add tags as markers
        if CTX.include_tags:
            create_otio_markers(otio_track, track)

        # add track to otio timeline
        otio_timeline.tracks.append(otio_track)

    return otio_timeline


def write_to_file(otio_timeline, path):
    otio.adapters.write_to_file(otio_timeline, path)
