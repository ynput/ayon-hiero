import hiero.core
from ayon_hiero.api import plugin

class UpdateToNewTrackPlugin(plugin.UpdatePlugin):
    """Update clip to latest version but place on a new track."""

    def update(self, clip, version_entity, project_entity, **kwargs):
        """Override default update to create a new track for the updated version."""
        # Get current track item and track
        track_item = clip
        track = track_item.parent()
        track_name = track.name()

        # Create new track with a meaningful name
        new_track_name = f"{track_name} - Updated {version_entity['version']}"
        sequence = track.parent()
        new_track = hiero.core.Track(new_track_name)
        sequence.addTrack(new_track)

        # Create new clip from version
        representations = version_entity.get('representations', [])
        if not representations:
            raise ValueError("No representations found for new version")
        # Assume first representation is the media to use
        rep = representations[0]
        # Build media source path
        # This is simplified; actual implementation may use AYON API to resolve
        media_path = rep.get('path', '')
        if not media_path:
            # Fallback: use version['data']['path'] or similar
            media_path = version_entity['data']['path']

        # Create TimelineItem from media
        new_track_item = hiero.core.TrackItem(f"{clip.name()} v{version_entity['version']}")
        # Copy timing properties from source clip
        new_track_item.setTimelineIn(track_item.timelineIn())
        new_track_item.setTimelineOut(track_item.timelineOut())
        new_track_item.setSourceIn(track_item.sourceIn())
        new_track_item.setSourceOut(track_item.sourceOut())
        # Add media
        media = hiero.core.MediaSource(media_path)
        new_track_item.setMedia(media)
        new_track.addItem(new_track_item)

        return new_track_item
