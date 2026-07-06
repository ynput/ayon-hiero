import hiero.core
from ayon_hiero.api import lib
from ayon_core.pipeline import inventory


class UpdateToNewTrack(object):
    """Update loaded versions to a new track instead of replacing existing."""

    def __init__(self, project, sequence, items):
        self.project = project
        self.sequence = sequence
        self.items = items

    def process(self):
        """Perform update to new track."""
        # Group items by their original track to create new tracks
        track_groups = {}
        for item in self.items:
            track = item.parent()
            if track not in track_groups:
                track_groups[track] = []
            track_groups[track].append(item)

        new_tracks = []
        for original_track, items in track_groups.items():
            # Create a new track with suffix '_updated'
            track_name = original_track.name() + "_updated"
            new_track = hiero.core.Track(track_name, original_track.trackType())
            self.sequence.addTrack(new_track)
            new_tracks.append(new_track)

            # Add updated versions as new clips on the new track
            for item in items:
                # Get new version information
                version_entity = lib.get_version_entity(item)
                new_version = inventory.get_latest_version(version_entity)
                if not new_version:
                    continue

                # Create new clip from representative
                rep = new_version.get_representation(
                    name="hiero"
                ) or new_version.get_representation(name="render")
                if not rep:
                    continue

                clip = hiero.core.Clip(rep.path)
                clip_item = new_track.addTrackItem(
                    item.name(),
                    item.timelineIn(),
                    item.timelineOut()
                )
                clip_item.setSource(clip)
                # Retain source in/out if possible
                clip_item.setSourceIn(item.sourceIn())
                clip_item.setSourceOut(item.sourceOut())

                # Set media source to new version
                lib.set_media_source(clip_item, new_version)

        return new_tracks


def update_to_new_track(selection):
    """Entry point called from inventory manager."""
    project = hiero.core.project_from_selection(selection)
    sequence = project.activeSequence()
    if not sequence:
        return

    items = selection
    updater = UpdateToNewTrack(project, sequence, items)
    tracks = updater.process()
    for track in tracks:
        print(f"Created track: {track.name()}")
