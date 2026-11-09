import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ayon_hiero.api import lib

import hiero.core

DEFAULT_SUBMISSION = "Single Render Process"


class RenderError(Exception):
    """A track item could not be rendered."""


@dataclass
class RenderResult:
    """Files rendered by `render_track_item`.

    Attributes:
        files (list[str]): Rendered files, sorted.
        is_sequence (bool): Files are an image sequence, not one movie.
        frame_start (int): First frame, handles included.
        frame_end (int): Last frame, handles included.
        handle_start (int): Handle frames rendered before the cut in.
        handle_end (int): Handle frames rendered after the cut out.
        colorspace (str): Colorspace the files are written in.
    """

    files: List[str] = field(default_factory=list)
    is_sequence: bool = True
    frame_start: int = 0
    frame_end: int = 0
    handle_start: int = 0
    handle_end: int = 0
    colorspace: str = ""


def _media_path(track_item) -> str:
    try:
        return track_item.source().mediaSource().firstpath()
    except Exception:
        return ""


# Project LUT setting the Write node uses for a 'default' colourspace, by
# file type and data type; the same table as Hiero's exporters.
_DEFAULT_LUT_BY_FILE_TYPE = {
    "cin": "Log",
    "dpx": {
        "8 bit": "8Bit",
        "10 bit": "Log",
        "12 bit": "16Bit",
        "16 bit": "16Bit",
    },
    "exr": "Float",
    "ffmpeg": "8Bit",
    "hdr": "Float",
    "jpeg": "8Bit",
    "mov": "8Bit",
    "pic": "8Bit",
    "png": "8Bit",
    "sgi": {"8 bit": "8Bit", "16 bit": "16Bit"},
    "targa": "8Bit",
    "tiff": {"8 bit": "8Bit", "16 bit": "16Bit", "32 bit float": "Float"},
}


def _codec_datatype(preset, file_type: str) -> Optional[str]:
    """Data type set on the preset, or the codec's default one."""
    value = preset.properties().get(file_type, {}).get("datatype")
    if value:
        return str(value)
    options = preset.codecProperties().get("datatype")
    if not options or isinstance(options, str):
        return options
    options = list(options)
    for option in options:
        if type(option).__name__ == "Default":
            return str(option.value())
    return str(options[0]) if options else None


def _default_output_colorspace(project, preset, file_type: str) -> str:
    """Colorspace Hiero writes when no output colourspace is set.

    Hiero writes the project's LUT settings into the Root node of the
    render script, and the Write node picks one by file and data type.
    """
    lut_key = _DEFAULT_LUT_BY_FILE_TYPE.get(file_type, "8Bit")
    if isinstance(lut_key, dict):
        lut_key = lut_key.get(_codec_datatype(preset, file_type), "8Bit")
    return getattr(project, f"lutSetting{lut_key}")()


def render_track_item(
    track_item: hiero.core.TrackItem,
    output_dir: str,
    name: str,
    file_type: str,
    codec_properties: Optional[Dict[str, Any]] = None,
    colorspace: Optional[str] = None,
    frame_start: int = 1001,
    handle_start: int = 0,
    handle_end: int = 0,
    include_effects: bool = False,
    submission: str = DEFAULT_SUBMISSION,
    source_range: Optional[Tuple[int, int]] = None,
) -> RenderResult:
    """Render the source media range of a track item with Hiero's exporter.

    The track item is rendered by a `TranscodeExporter` task, run by the
    export queue synchronously, so the files exist when this returns.
    Retimes are never baked: the item's source range is rendered, or
    `source_range` for an image sequence.

    Handles are clamped to the media available around the cut. Hiero
    renders one handle length on both ends, so an image sequence gets the
    longer one and the extra frames are removed, and a movie gets the
    shorter one. `handle_start` / `handle_end` of the result say what the
    files have.

    Args:
        track_item: Track item to render.
        output_dir: Folder for the rendered files; created when missing.
        name: File name without frame number and extension.
        file_type: Hiero file type, e.g. 'exr', 'dpx', 'jpeg', 'mov'.
        codec_properties: Hiero codec settings of the file type, as in
            the export dialog, e.g. `{"compression": "DWAA"}`.
        colorspace: Output colourspace. Empty writes Hiero's default for
            the file type.
        frame_start: Frame number of the cut in.
        handle_start: Wanted source frames before the cut in.
        handle_end: Wanted source frames after the cut out.
        include_effects: Bake soft effects of the track item.
        submission: Hiero render submission, 'Single Render Process' or
            'Frame Server'.
        source_range: First and last source frame of the cut, relative
            to the clip start, when it differs from the item's, e.g. the
            range ayon-core computes for a retimed clip. Movies always
            render the item's source range.

    Returns:
        RenderResult: What was rendered.

    Raises:
        RenderError: The media is offline, the settings are not valid or
            Hiero did not render every expected file.
    """
    from hiero.core import ItemWrapper
    from hiero.exporters.FnShotProcessor import ShotProcessorPreset
    from hiero.exporters.FnTranscodeExporter import TranscodePreset

    if not track_item.isMediaPresent():
        raise RenderError(
            f"Media of '{track_item.name()}' is offline, nothing to render:"
            f" '{_media_path(track_item)}'"
        )

    codec_properties = dict(codec_properties or {})
    preset = TranscodePreset(
        f"ayon_{name}",
        {"file_type": file_type, file_type: dict(codec_properties)},
    )
    try:
        codec_settings = preset.codecSettings()
    except KeyError:
        raise RenderError(f"Hiero cannot render file type '{file_type}'.")
    is_video = bool(codec_settings["isVideo"])
    extension = preset.extension()

    preset.properties().update(
        {
            "includeEffects": bool(include_effects),
            "keepNukeScript": False,
        }
    )
    if colorspace:
        preset.properties().update(
            {
                # 'colourspace' is the key of Hiero 14 and older
                "colourspace": colorspace,
                "colorspace": colorspace,
                "transformType": "colorspace",
            }
        )

    # Source frames of the cut, relative to the clip start. With a retime
    # this is not the timeline duration.
    item_in = int(min(track_item.sourceIn(), track_item.sourceOut()))
    item_out = int(max(track_item.sourceIn(), track_item.sourceOut()))
    source_in, source_out = item_in, item_out
    if source_range is not None and not is_video:
        source_in, source_out = (int(frame) for frame in source_range)
    cut_frame_end = frame_start + (source_out - source_in)

    # Handles clamped to the media available around the cut, in source
    # frames ('handleInLength()' counts timeline frames)
    clip_last = int(track_item.source().duration()) - 1
    head = max(0, min(int(handle_start), source_in))
    tail = max(0, min(int(handle_end), clip_last - source_out))

    # Hiero renders the item's source range with one handle length on
    # both ends, with black frames where there is no media. An image
    # sequence gets enough to cover the wanted range and loses the extra
    # frames afterwards, a movie gets the shorter handle.
    if is_video:
        cut_handles = min(head, tail)
    else:
        cut_handles = max(
            0,
            item_in - (source_in - head),
            (source_out + tail) - item_out,
        )
    # Number the files so that 'source_in' lands on 'frame_start'
    first_frame = frame_start - (source_in - (item_in - cut_handles))

    if is_video:
        file_template = f"{name}.{{ext}}"
    else:
        file_template = f"{name}.####.{{ext}}"
    os.makedirs(output_dir, exist_ok=True)
    processor_preset = ShotProcessorPreset(
        f"ayon_{name}",
        {
            "exportRoot": output_dir,
            "exportTemplate": ((file_template, preset),),
            "cutLength": True,
            "cutUseHandles": cut_handles > 0,
            "cutHandles": cut_handles,
            "includeRetimes": False,
            "startFrameSource": "Custom",
            "startFrameIndex": first_frame,
        },
    )

    # The exporter tags the track item it renders; keep the timeline as it is
    tag_names_before = {tag.name() for tag in track_item.tags()}
    try:
        hiero.core.taskRegistry.createAndExecuteProcessor(
            processor_preset,
            [ItemWrapper(track_item)],
            submissionName=submission,
            synchronous=True,
        )
    except RuntimeError as exc:
        raise RenderError(
            f"Hiero failed to render '{track_item.name()}': {exc}"
        ) from exc
    finally:
        for tag in list(track_item.tags()):
            if tag.name() not in tag_names_before:
                track_item.removeTag(tag)

    if is_video:
        files = [os.path.join(output_dir, f"{name}.{extension}")]
        missing = [path for path in files if not os.path.isfile(path)]
        result_head = result_tail = cut_handles
    else:
        expected = range(frame_start - head, cut_frame_end + tail + 1)
        frame_re = re.compile(
            rf"^{re.escape(name)}\.(\d+)\.{re.escape(extension)}$"
        )
        by_frame = {}
        for filename in os.listdir(output_dir):
            match = frame_re.match(filename)
            if match:
                by_frame[int(match.group(1))] = os.path.join(
                    output_dir, filename
                )
        # Remove handle frames rendered beyond the wanted handles
        for frame, path in list(by_frame.items()):
            if frame not in expected:
                os.remove(path)
                by_frame.pop(frame)
        files = [by_frame[frame] for frame in expected if frame in by_frame]
        missing = [frame for frame in expected if frame not in by_frame]
        result_head, result_tail = head, tail

    if missing:
        raise RenderError(
            f"Hiero did not render {len(missing)} expected file(s) of"
            f" '{track_item.name()}' into '{output_dir}', first missing:"
            f" {missing[0]}"
        )

    return RenderResult(
        files=files,
        is_sequence=not is_video,
        frame_start=frame_start - result_head,
        frame_end=cut_frame_end + result_tail,
        handle_start=result_head,
        handle_end=result_tail,
        colorspace=colorspace
        or _default_output_colorspace(track_item.project(), preset, file_type),
    )


def render_sequence_as_quicktime(
        output_path: str,
        sequence: Optional[hiero.core.Sequence] = None,
        export_audio: Optional[bool] = True,
        colorspace: Optional[str] = None,
    ):
    project = lib.get_current_project()
    if not sequence:
        sequence = lib.get_current_sequence()
    elif sequence not in project.sequences():
        raise ValueError(f"Unknown sequence to render {sequence}.")

    # https://learn.foundry.com/hiero/developers/latest/HieroPythonDevGuide/quick_export.html
    h264_export = {
      "Audio Codec" : "linear PCM (wav)",
      "B Frames" : "0",
      "Bit Depth" : "32 bit(float)",
      "Bitrate" : "28000.0",
      "Bitrate Tolerance" : "0",
      "Codec" : "H.264",
      "Codec Profile" : "High 4:2:0 8-bit",
      "Data Range" : "Video Range",
      "Fast Start" : "True",
      "Format_height" : "720",
      "Format_name" : "HD_720",
      "Format_pixelAspect" : "1.0",
      "Format_width" : "1280",
      "GOP Size" : "12",
      "Include Audio" : "True" if export_audio else "False",
      "Include Annotations": "False",
      "Output Channels" : "stereo",
      "Quality" : "High",
      "Quantizer Max" : "3",
      "Quantizer Min" : "1",
      "Reformat" : "Custom",
      "Sample Rate" : "48000 Hz",
      "Views" : "main",
      "Write Timecode" : "True",
      "YCbCr Matrix" : "Auto",
      "center" : "True",
      "colorspace" : colorspace or "default",
      "ocioDisplay" : "default",
      "ocioView" : "sRGB",
      "resize" : "width",
      "transformType" : "colorspace"
    }

    try:
        # Only available since 16.0
        from hiero.core import TimelineDirectExport
    except ImportError as error:
        raise NotImplementedError(
            "This feature require Hiero 16.0 or above."
            ) from error

    exportObj = TimelineDirectExport()
    exportObj.exportSequence(
        sequence,
        output_path,
        h264_export
    )
