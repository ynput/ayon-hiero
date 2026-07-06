import hiero.core
import hiero.ui
from ayon_api import get_project, get_representation_by_id

class UpdateToNewTrackAction(hiero.ui.Action):
    def __init__(self):
        super().__init__("Update to New Track")
        self.setShortcut("Ctrl+Shift+U")
        self.setMenu("AYON")

    def isCompatible(self, selection):
        return len(selection) > 0 and all(
            isinstance(item, hiero.core.TrackItem) for item in selection
        )

    def execute(self, selection):
        project = hiero.core.projects()[-1]
        seq = project.activeSequence()
        if not seq:
            return

        for track_item in selection:
            # Get source media info
            source = track_item.source()
            if not source:
                continue
            # Assume source has ayon metadata
            representation_id = source.metadata().get("ayon.representationId")
            if not representation_id:
                continue

            # Fetch latest version representation from AYON
            project_name = source.metadata().get("ayon.projectName")
            if not project_name:
                continue
            project_entity = get_project(project_name)
            latest_rep = self._get_latest_representation(project_entity, representation_id)
            if not latest_rep or latest_rep["id"] == representation_id:
                continue

            # Create new track named after latest version
            new_track_name = f"Updated v{latest_rep['version']}"
            new_track = seq.createVideoTrack(new_track_name)
            # Clone item properties from original
            new_item = hiero.core.TrackItem(
                track_item.name(),
                track_item.source(),
                track_item.timelineIn(),
                track_item.timelineOut()
            )
            # Set new source media
            new_source = hiero.core.MediaSource(latest_rep["path"])
            new_item.setSource(new_source)
            # Add to new track at same position
            seq.addTrackItem(new_item, new_track)

    def _get_latest_representation(self, project, current_rep_id):
        # Simplified: query AYON for latest version of the same product
        # In practice use ayon_api.get_representations or similar
        # For demonstration, we assume we can get latest by filtering
        # This would require proper AYON API calls
        return None

action = UpdateToNewTrackAction()
hiero.ui.registerAction(action)