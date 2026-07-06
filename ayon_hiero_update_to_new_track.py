import hiero.core
import pyblish.api


def create_new_track(track_name, sequence):
    """Create a new video track with the given name in the sequence."""
    # Check if track already exists
    for existing_track in sequence.videoTracks():
        if existing_track.name() == track_name:
            return existing_track
    # Create new track
    new_track = hiero.core.VideoTrack(track_name)
    sequence.addVideoTrack(new_track)
    return new_track


def update_clip_to_new_track(clip_item, new_track_name_suffix="_Updated"):
    """
    Update a loaded clip to its latest version and place it on a new track.
    The new track name is derived from the original track with a suffix.
    """
    track = clip_item.parent()
    if not isinstance(track, hiero.core.VideoTrack):
        return

    sequence = track.parent()
    new_track_name = track.name() + new_track_name_suffix
    new_track = create_new_track(new_track_name, sequence)

    # Get the clip's source media
    clip = clip_item.source()
    if not clip:
        return

    # Determine latest version of this clip (simplified: assume versionable media)
    # In AYON, versions are managed via tags or metadata
    # We'll find the latest published version of the same source
    # Placeholder: Here we would query AYON database for latest version.
    # For now we assume the clip's media has a version property.
    # actual implementation should use AYON API
    # For demonstration, we just use the same clip with a new version number

    # Create a new clip with updated version (simulate)
    # In real code, this would create a new Clip from the latest publish
    media_source = clip.mediaSource()
    if media_source:
        # This is just a placeholder - real code would replace with new version
        new_media_source = media_source  # keep same for now
        new_clip = hiero.core.Clip(new_media_source)
        new_clip_item = hiero.core.TrackItem(new_clip, clip_item.timelineIn(), clip_item.timelineOut())
        new_clip_item.setSourceTimecode(clip_item.sourceTimecode())
        new_clip_item.setSourceDuration(clip_item.sourceDuration())
        new_track.addTrackItem(new_clip_item)

    # Optional: update the metadata tag to mark updated version
    # If you want to keep the old clip, do nothing. This keeps old version on old track.


def update_selected_to_new_track(selection=None, new_track_suffix="_Updated"):
    """
    Process all selected/outdated clips and move their latest version to a new track.
    """
    if selection is None:
        selection = hiero.ui.activeView().selection()
    for clip_item in selection:
        update_clip_to_new_track(clip_item, new_track_suffix)


# Hook into the update mechanism (e.g., via pyblish plugin)
class UpdateToNewTrackPlugin(pyblish.api.Action):
    """Update selected clips to latest version on a new track."""
    label = "Update to New Track"
    icon = "add-track"
    on = "trackitem"

    def process(self, context, plugin):
        selection = context.selection
        update_selected_to_new_track(selection)


if __name__ == "__main__":
    # For testing: run on currently selected items
    update_selected_to_new_track()
