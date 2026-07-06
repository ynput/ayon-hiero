import hiero.core
from ayon_core.pipeline import InventoryAction
from ayon_hiero.api import plugin


class UpdateToNewTrack(InventoryAction):
    """Update outdated versions to a new track instead of replacing in-place."""

    label = "Update to new track"
    description = "Updates selected clips to latest version and places them on a new track."
    icon = "step-forward"
    order = 100

    @classmethod
    def is_compatible(cls, containers):
        return all(
            container.get("productType") in ["render", "plate", "review", "source"]
            for container in containers
        )

    @classmethod
    def process(cls, containers, **kwargs):
        from ayon_hiero.api.lib import (
            get_current_project,
            get_current_sequence,
        )

        project = get_current_project()
        sequence = get_current_sequence()
        if not sequence:
            raise RuntimeError("No active sequence found.")

        # Group containers by track
        track_map = {}
        for container in containers:
            track_item = container.get("_trackItem")
            if not track_item:
                continue
            track = track_item.parent()
            if track not in track_map:
                track_map[track] = []
            track_map[track].append((track_item, container))

        # For each track, update clips by creating a new track
        for track, items in track_map.items():
            # Determine new track name
            new_track_name = f"{track.name()} (updated)"
            # Create new track
            new_track = hiero.core.VideoTrack(new_track_name)
            sequence.addTrack(new_track)

            for track_item, container in items:
                # Get updated representation (you may need to resolve via AYON API)
                # For this example, we assume an `update_to_latest` method exists
                updated_container = container.update_to_latest()  # placeholder

                # Create new track item from updated media
                updated_item = plugin.create_track_item(
                    sequence,
                    new_track,
                    track_item.name(),
                    updated_container,
                    track_in=track_item.timelineIn(),
                    track_out=track_item.timelineOut(),
                )
                # Optionally copy other attributes (source in/out, etc.)
                updated_item.setSourceIn(track_item.sourceIn())
                updated_item.setSourceOut(track_item.sourceOut())

            # Remove original track? Or keep? For now, keep it.

        print("Update complete. New tracks created for updated versions.")


# Register action
import ayon_core.pipeline as pipeline
pipeline.register_inventory_action(UpdateToNewTrack)
