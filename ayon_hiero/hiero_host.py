import hiero.core
import hiero.ui
from ayon_core.pipeline import inventory


def update_to_new_track(clip, new_version):
    """
    Update a clip by adding a new version on a new track,
    preserving the original clip.
    """
    track = clip.parent()
    sequence = track.parent()
    
    # Determine new track name
    base_name = track.name()
    new_track_name = f"{base_name}_updated"
    
    # Find or create the new track
    new_track = None
    for t in sequence.videoTracks():
        if t.name() == new_track_name:
            new_track = t
            break
    if new_track is None:
        new_track = hiero.core.VideoTrack(new_track_name)
        # Insert new track directly below the original track
        track_index = sequence.videoTracks().index(track)
        sequence.insertTrack(new_track, track_index + 1)
    
    # Copy clip to new track
    new_clip = new_track.copyTrackItem(clip, hiero.core.TrackItem.kVideo)
    
    # Update the new clip with the new version
    # Assuming there is a function to replace version on a clip
    inventory.update_version_on_clip(new_clip, new_version)
    
    # Optionally, remove the track if it's empty after update?
    # Not needed - we keep the original track as is.


def update_selected_versions_with_new_track():
    """
    Action to update selected outdated clips to new track.
    """
    selection = hiero.ui.selection()
    if not selection:
        return
    for item in selection:
        if isinstance(item, hiero.core.TrackItem) and item.isVideo():
            clip = item
            # Get latest version for the clip's product
            # This is simplified - actual implementation would use the inventory manager
            product_id = clip.source().metadata().get("ayon_product_id")
            if not product_id:
                continue
            # Fetch latest version info
            latest_version = inventory.get_latest_version(product_id)
            if not latest_version:
                continue
            # Check if current version is outdated
            current_version_id = clip.source().metadata().get("ayon_version_id")
            if current_version_id == latest_version["id"]:
                continue
            # Update to new track
            update_to_new_track(clip, latest_version)
