from ayon_hiero.api import lib
from ayon_hiero.api.pipeline import get_current_project


def update_version_to_new_track(clip, version, new_track_name=None):
    """Updates the version of a clip by creating a new track and placing the updated version there.

    Args:
        clip (hiero.core.TrackItem): The original clip to update.
        version (dict): The version data containing media info.
        new_track_name (str, optional): Name for the new track. Defaults to original track name + '_updated'.
    """
    import hiero.core

    project = get_current_project()
    if not project:
        raise RuntimeError("No current project found.")

    sequence = clip.parent()
    if not isinstance(sequence, hiero.core.Sequence):
        raise RuntimeError("Clip must be in a sequence.")

    original_track = clip.parentTrack()
    if new_track_name is None:
        new_track_name = f"{original_track.name()}_updated"

    # Find or create the new track
    new_track = None
    for track in sequence.videoTracks():
        if track.name() == new_track_name:
            new_track = track
            break

    if new_track is None:
        new_track = hiero.core.VideoTrack(new_track_name)
        # Insert after original track to keep order
        track_index = list(sequence.videoTracks()).index(original_track) + 1
        sequence.addTrack(new_track, track_index)

    # Create the new clip with updated version
    # This assumes we have a function to create a clip from version data
    new_clip = lib.create_clip_from_version(version)
    if not new_clip:
        raise RuntimeError("Failed to create clip from version.")

    # Copy timing from original clip
    new_clip.setTimelineIn(clip.timelineIn())
    new_clip.setTimelineOut(clip.timelineOut())
    new_clip.setTimecodeStart(clip.timecodeStart())

    # Add clip to new track
    new_track.addSubTrackItem(new_clip)

    return new_clip


def update_version_in_place(clip, version):
    """Legacy update: replaces the clip's source media with the new version."""
    # Existing update logic here
    pass


def update_selected_versions(selection, update_to_new_track=False):
    """Update selected versions, optionally placing updated clips on new tracks.

    Args:
        selection (list): List of tuples (clip, version_data).
        update_to_new_track (bool): If True, create new tracks for updated versions.
    """
    import hiero.core

    with hiero.core.events.willSaveSoon.ignore():
        for clip, version in selection:
            if update_to_new_track:
                update_version_to_new_track(clip, version)
            else:
                update_version_in_place(clip, version)
