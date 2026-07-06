import hiero.core
import hiero.ui
from ayon_hiero.api.update_to_new_track import update_to_new_track


def update_selected_to_new_track():
    """Action: update selected track items by placing new versions on new tracks."""
    selection = hiero.ui.activeView().selection()
    track_items = [item for item in selection if isinstance(item, hiero.core.TrackItem)]
    if not track_items:
        hiero.ui.showWarning("No track items selected")
        return

    for track_item in track_items:
        # Determine the new version bin item. This logic depends on how versions are tracked.
        # For this plugin, we assume the track item has metadata pointing to the latest version.
        # A real implementation would interact with AYON API to get the latest version.
        # Here we use a placeholder.
        new_version_bin_item = _get_latest_version_from_metadata(track_item)
        if new_version_bin_item is None:
            continue
        try:
            update_to_new_track(track_item, new_version_bin_item)
        except Exception as e:
            hiero.ui.showWarning("Update failed: {}".format(str(e)))


def _get_latest_version_from_metadata(track_item):
    """Placeholder: retrieve the latest version bin item from the track item's metadata.
    This should be replaced with actual AYON logic."""
    # Example: assume metadata stores a tag with version data
    # tag = track_item.tags()['ayon_version'] ...
    # return ayon_api.get_version_bin_item(...)
    return None


# Register the action in Hiero menu
from ayon_hiero.api import menu
menu.add_action("Update to New Track", update_selected_to_new_track)
