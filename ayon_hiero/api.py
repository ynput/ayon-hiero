# Original file with modifications for update to new track
import hiero.core
from ayon_core.pipeline import get_current_project_settings
from ayon_hiero.update_to_new_track import update_to_new_track

# ... existing imports and code ...

def update_container(container, update_data=None):
    """Update a container to a new version.

    If the setting 'create_new_track_on_update' is enabled, the new version
    is placed on a new track instead of replacing the existing clip.
    """
    # Check setting
    settings = get_current_project_settings()
    hiero_settings = settings.get("hiero", {})
    create_new_track = hiero_settings.get("create_new_track_on_update", True)

    if create_new_track:
        # Get the new representation from update_data
        if not update_data or "representation" not in update_data:
            raise ValueError("Missing representation data for update")
        new_rep = update_data["representation"]
        # Call new track function
        update_to_new_track(container, new_rep)
        # Do not modify original container
        return True
    else:
        # Original update logic (in-place)
        # ... existing code to update container ...
        pass
