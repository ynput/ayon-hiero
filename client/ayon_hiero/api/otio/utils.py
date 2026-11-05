import re
import json


def get_reformated_path(path, padded=True):
    """
    Return fixed python expression path

    Args:
        path (str): path url or simple file name

    Returns:
        type: string with reformatted path

    Example:
        get_reformated_path("plate.[0001-1008].exr") > plate.%04d.exr

    """
    if "%" in path:
        padding_pattern = r"(\d+)"
        padding = int(re.findall(padding_pattern, path).pop())
        num_pattern = r"(%\d+d)"
        if padded:
            path = re.sub(num_pattern, "%0{}d".format(padding), path)
        else:
            path = re.sub(num_pattern, "%d", path)
    return path


def get_rate(item):
    if not hasattr(item, 'framerate'):
        return None

    num, den = item.framerate().toRational()

    try:
        rate = float(num) / float(den)
    except ZeroDivisionError:
        return None

    if rate.is_integer():
        return rate

    return round(rate, 4)


def get_marker_from_clip_index(otio_timeline, clip_index):
    """
    Args:
        otio_timeline (otio.Timeline): The otio timeline to inspect
        clip_index (int): The clip index metadata to retrieve.

    Returns:
        tuple(otio.Clip, otio.Marker): The associated clip and marker
            or (None, None)
    """
    try:  # opentimelineio >= 0.16.0
        all_clips = otio_timeline.find_clips()
    except AttributeError:  # legacy
        all_clips = otio_timeline.each_clip()

    # Retrieve otioClip from parent context otioTimeline
    # See collect_current_project
    for otio_clip in all_clips:
        for marker in otio_clip.markers:

            try:
                json_metadata = marker.metadata["json_metadata"]
            except KeyError:
                continue

            else:
                metadata = json.loads(json_metadata)
                if metadata.get("clip_index") == clip_index:
                    return otio_clip, marker

    return None, None
