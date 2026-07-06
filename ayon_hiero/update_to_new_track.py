import hiero.core
import hiero.ui
from ayon_hiero import lib as hiero_lib
from ayon_core.pipeline import get_current_project_settings

def update_to_new_track(container, new_representation):
    """Create a new track with updated version of the clip."""
    # Get original track item
    track_item = container["_track_item"]
    track = track_item.parent()
    sequence = track.parent()

    # Get media from new representation
    media_info = hiero_lib.get_media_for_representation(new_representation)
    if not media_info:
        raise ValueError("Cannot get media from new representation")

    # Create new track name
    original_name = track.name()
    new_track_name = f"{original_name}_updated"

    # Check if track already exists, if so use it, else create
    new_track = None
    for t in sequence.videoTracks():
        if t.name() == new_track_name:
            new_track = t
            break
    if new_track is None:
        new_track = hiero.core.VideoTrack(new_track_name)
        sequence.addTrack(new_track)

    # Determine position and duration from original clip
    source_in = track_item.sourceIn()
    source_out = track_item.sourceOut()
    timeline_in = track_item.timelineIn()
    timeline_out = track_item.timelineOut()

    # Create new clip
    new_clip = hiero.core.Clip(media_info["path"])
    new_track_item = new_track.createTrackItem(str(track_item.name()))
    new_track_item.setSource(new_clip)
    new_track_item.setTimelineIn(timeline_in)
    new_track_item.setTimelineOut(timeline_out)
    new_track_item.setSourceIn(source_in)
    new_track_item.setSourceOut(source_out)

    # Add to timeline
    new_track.addTrackItem(new_track_item)

    # Copy additional attributes like speed if needed
    # (attributes from original can be copied here)

    return True
