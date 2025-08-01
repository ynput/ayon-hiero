from typing import Optional

from ayon_hiero.api import lib

import hiero.core


def render_sequence_as_quicktime(
        output_path: str,
        sequence: Optional[hiero.core.Sequence] = None,
        export_audio: Optional[bool] = True,
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
      "colorspace" : "default",
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
