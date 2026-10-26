import pyblish.api

from ayon_core.pipeline import PublishError
from ayon_hiero.api import lib

import hiero


class CollectEditorialPackages(pyblish.api.InstancePlugin):
    """Collect all Editorial Packages."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Editorial Package Instances"
    families = ["editorial_pkg"]

    def process(self, instance: pyblish.api.Instance):
        current_project = lib.get_current_project()
        all_sequences = current_project.sequences()
        hiero_sequence_guid = instance.data["guid"]
        review_switch = instance.data["creator_attributes"].get(
            "review")
        if review_switch and "review" not in instance.data["families"]:
            instance.data["families"].append("review")

        hiero_sequence = None
        for sequence in all_sequences:
            if sequence.guid() == hiero_sequence_guid:
                hiero_sequence = sequence
                instance.data["hiero_sequence"] = sequence
                break

        if not hiero_sequence:
            raise PublishError(f"Cannot retrieve sequence from {hiero_sequence}.")

        # Collect colorspace from the sequence clips
        colorspaces = set()
        for track in sequence.videoTracks():
            if not track.isEnabled():
                continue

            for track_item in track.items():
                if (
                    not isinstance(track_item, hiero.core.TrackItem)
                    or not track_item.isEnabled()
                ):
                    continue

                colorspaces.add(track_item.sourceMediaColourTransform())

        if len(colorspaces) == 1:
            colorspace = colorspaces.pop()
            instance.data["colorspace"] = colorspace
            version_data = instance.data.setdefault("versionData", {})
            version_data["colorSpace"] = colorspace
            self.log.debug(
                "Collected colorspace from sequence: %s",
                colorspace,
            )

        elif colorspaces:
            self.log.warning(
                "Incoming sequence clips have mixed colorspaces %r.",
                colorspaces,
            )

        self.log.debug(f"Editorial Package: {instance.data}")
