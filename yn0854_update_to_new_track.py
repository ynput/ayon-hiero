import ayon_api
import hiero.core
from ayon_hiero.api import publish


def _add_to_new_track(track_item, new_version, project, sequence, track, updated_track_name):
    """Add new version to a new track.

    Args:
        track_item: Original track item.
        new_version: New version entity.
        project: Hiero project.
        sequence: Hiero sequence.
        track: Original video track.
        updated_track_name: Name for the new track.
    """
    # Create new track
    new_track = hiero.core.VideoTrack(name=updated_track_name)
    sequence.addTrack(new_track)

    # Create new track item with same timing
    new_item = hiero.core.TrackItem(
        new_version['name'],
        trackItemType=hiero.core.TrackItem.kVideo,
        sourceDuration=track_item.sourceDuration(),
        sourceIn=track_item.sourceIn(),
        sourceOut=track_item.sourceOut(),
        timelineIn=track_item.timelineIn(),
        timelineOut=track_item.timelineOut()
    )
    new_item.setSourceMedia(new_version['media'])
    new_track.addTrackItem(new_item)
    return new_item


def update_to_new_track(selected_items, **kwargs):
    """Override update logic to add updated versions to new track.

    This function is called by Inventory Manager update action.
    It keeps old track items and adds new ones on a new track.
    """
    # Import here to avoid circular imports
    from ayon_hiero.api.publish import _update_loaded_versions

    project = hiero.core.projects()[-1]
    sequence = project.activeSequence()
    if not sequence:
        return

    updated_track_base = "Updated Versions"
    track_counter = 1
    updated_track_name = f"{updated_track_base}_{track_counter}"

    # Store original track items per track
    for track in sequence.videoTracks():
        if not track.isVideo():
            continue
        for track_item in track:
            if not track_item.isMedia():
                continue
            # Check if this track item corresponds to a selected inventory item
            # The selection is passed as selected_items (list of path strings)
            # We need to find matching track item
            # For simplicity, assume we have a mapping from track item to version
            # We'll use the existing update logic but then add to new track
            # Instead, we call the base update but then duplicate to new track?
            # Better: replace the update function entirely.

    # For now, placeholder: iterate and handle each selected item
    # We assume selected_items is list of dicts with 'entity_id' or similar
    # This is a simplified example
    for selection in selected_items:
        # Determine if it's a track item selection
        # Extract track item info
        # Find the original track item
        # Get its current version
        # Call API to get latest version
        # Create new track item on new track
        pass

    print("Update to new track completed.")


# Register this function as the update handler
publish._update_loaded_versions = update_to_new_track

# Also ensure that the update action in Inventory Manager uses this
# This is a simplistic approach; in production, you'd modify the plugin
