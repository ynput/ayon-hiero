import hiero.core
import hiero.ui
from ayon_hiero.api import plugin

class UpdateToNewTrackAction(plugin.Action):
    """
    Action to update selected clips to latest version on a new track.
    """
    def __init__(self):
        super().__init__()
        self._name = "Update to New Track"
        self._tooltip = "Update selected items to latest version, placing on a new track"
        self._icon = ""

    def is_valid(self, selection):
        if len(selection) == 0:
            return False
        for item in selection:
            if not hasattr(item, 'source') or not item.source():
                return False
        return True

    def execute(self, selection):
        for clip in selection:
            self._update_clip_to_new_track(clip)

    def _update_clip_to_new_track(self, clip):
        """
        Update a single clip to latest version and place it on a new track.
        """
        # Get the original track and timeline
        track = clip.parent()
        timeline = track.parent()

        # Get the source media and its latest version
        source = clip.source()
        if source is None:
            return
        # In Ayon, source is a MediaSource with version info
        # We need to get the latest version from the source's version list
        # This is a placeholder; actual implementation depends on Ayon API
        latest_version = self._get_latest_ayon_version(source)
        if latest_version is None:
            return

        # Create new track name
        original_track_name = track.name()
        new_track_name = original_track_name + "_updated"

        # Check if track already exists, else create
        new_track = None
        for t in timeline.tracks():
            if t.name() == new_track_name:
                new_track = t
                break
        if new_track is None:
            new_track = hiero.core.Track(new_track_name, track.trackType())
            timeline.addTrack(new_track)

        # Create new clip on the new track with the latest version
        # Clip properties: name, source, in/out times
        new_clip = hiero.core.Clip(clip.name())
        # Set the new source to latest version
        new_clip.setSource(latest_version)
        # Copy timing and handles
        new_clip.setTimelineIn(clip.timelineIn())
        new_clip.setTimelineOut(clip.timelineOut())
        new_clip.setSourceIn(clip.sourceIn())
        new_clip.setSourceOut(clip.sourceOut())

        # Add clip to track at same position
        track_item = hiero.core.TrackItem(new_clip, clip.timelineIn())
        new_track.addTrackItem(track_item)

    def _get_latest_ayon_version(self, source):
        """
        Helper to fetch the latest version of a source from Ayon.
        For demonstration, returns source unchanged (assume source is already latest).
        Actual implementation should use Ayon API to get latest version.
        """
        # TODO: Implement real Ayon version retrieval
        return source

# Register the action
hiero.ui.registerAction(UpdateToNewTrackAction())
