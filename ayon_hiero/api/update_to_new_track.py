import hiero.core
import hiero.ui


def update_to_new_track(track_item, new_version_bin_item):
    """Update a track item by creating a new track and placing the new version there.

    Args:
        track_item (hiero.core.TrackItem): The existing track item to update.
        new_version_bin_item (hiero.core.BinItem): The bin item representing the new version.

    Returns:
        hiero.core.TrackItem: The newly created track item.
    """
    sequence = track_item.parentSequence()
    if not sequence:
        raise ValueError("Track item has no parent sequence")

    original_track = track_item.parentTrack()
    if not original_track:
        raise ValueError("Track item has no parent track")

    # Determine the index for the new track (insert after the original track)
    video_tracks = list(sequence.videoTracks())
    if original_track in video_tracks:
        track_index = video_tracks.index(original_track) + 1
    else:
        # Fallback: add at the end
        track_index = len(video_tracks)

    # Create a new video track with a descriptive name
    new_track_name = "Updated - " + original_track.name()
    new_track = hiero.core.VideoTrack(new_track_name)
    sequence.addTrack(new_track, track_index)

    # Create a new track item from the new version
    new_track_item = hiero.core.TrackItem(track_item.name() + "_updated")
    new_track_item.setSource(new_version_bin_item)

    # Copy timing info from the original track item
    new_track_item.setTimelineIn(track_item.timelineIn())
    new_track_item.setTimelineOut(track_item.timelineOut())
    new_track_item.setTimecodeStart(track_item.timecodeStart())
    new_track_item.setPlaybackSpeed(track_item.playbackSpeed())

    # Set source range to the full clip (or copy original source range for consistency)
    # For a typical update, we want the full source range of the new version
    if hasattr(new_version_bin_item, 'duration'):
        new_track_item.setSourceIn(0)
        new_track_item.setSourceOut(new_version_bin_item.duration() - 1)
    else:
        # Fallback: copy original source in/out
        new_track_item.setSourceIn(track_item.sourceIn())
        new_track_item.setSourceOut(track_item.sourceOut())

    new_track.addTrackItem(new_track_item)

    return new_track_item
