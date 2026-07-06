import hiero.core
import hiero.ui

# Ensure the module is reloadable
import importlib
importlib.reload(hiero.core)
importlib.reload(hiero.ui)

def create_track(sequence, track_name):
    """Create a new video track with given name if it doesn't exist."""
    for track in sequence.videoTracks():
        if track.name() == track_name:
            return track
    new_track = hiero.core.VideoTrack(track_name)
    sequence.addVideoTrack(new_track)
    return new_track

def duplicate_track_item_to_track(track_item, target_track):
    """Duplicate a TrackItem onto a given track, preserving timing."""
    source = track_item.source()
    new_item = hiero.core.TrackItem(source, track_item.name())
    new_item.setTimelineIn(track_item.timelineIn())
    new_item.setTimelineOut(track_item.timelineOut())
    new_item.setSourceIn(track_item.sourceIn())
    new_item.setSourceOut(track_item.sourceOut())
    target_track.addTrackItem(new_item)
    return new_item

def update_to_new_track_version(track_item, version):
    """Update a TrackItem to a given version on a new track.
    The original TrackItem remains untouched.
    """
    sequence = track_item.parentSequence()
    if not sequence:
        hiero.core.log.warning("TrackItem has no parent sequence.")
        return

    # Ensure we have a target track for updated versions
    target_track_name = "Updated Versions"
    target_track = create_track(sequence, target_track_name)

    # Duplicate the track item to the target track
    new_item = duplicate_track_item_to_track(track_item, target_track)

    # Update the new item to the specified version
    # Assuming version is a hiero.core.Version object
    new_item.setSourceVersion(version)
    hiero.core.log.info(f"Updated {track_item.name()} to version {version.versionNumber()} on track '{target_track_name}'.")

def update_selection_to_new_track(selection=None):
    """For each selected track item, update it to the latest version on a new track."""
    if selection is None:
        selection = hiero.ui.getTimelineEditor(hiero.ui.activeView()).selection()

    if not selection:
        hiero.core.log.warning("No items selected.")
        return

    # Get the selected track items (could be clips or gaps)
    track_items = [item for item in selection if isinstance(item, hiero.core.TrackItem) and item.isClip()]

    if not track_items:
        hiero.core.log.warning("No clip items selected.")
        return

    for track_item in track_items:
        # Get latest version for the clip
        # We need to fetch available versions from the source media
        clip = track_item.source()
        if not clip:
            continue
        # Assuming we have a method to get latest version - placeholder
        # In real AYON integration, we'd use the version manager
        versions = clip.versions()
        if not versions:
            hiero.core.log.warning(f"No versions for {clip.name()}.")
            continue
        latest_version = versions[-1]  # Assuming last is newest
        update_to_new_track_version(track_item, latest_version)

# Optional: Add a menu action (uncomment for testing)
# action = hiero.ui.createMenuAction("Update to New Track", update_selection_to_new_track)
# hiero.ui.insertMenuAction(action, "Tools")

# For direct use in Inventory Manager or script:
# from yn_0854_update_to_new_track import update_selection_to_new_track
# call it with selected items from inventory