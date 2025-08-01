import pyblish.api
from ayon_core.pipeline import PublishError
from ayon_hiero.api import lib

class CollectEditorialPackages(pyblish.api.InstancePlugin):
    """Collect all Editorial Packages."""

    order = pyblish.api.CollectorOrder - 0.49
    label = "Collect Editorial Package Instances"
    families = ["editorial_pkg"]

    def process(self, instance: pyblish.api.Instance):
        current_project = lib.get_current_project()
        all_sequences = current_project.sequences()
        hiero_sequence_guid = instance.data["guid"]

        hiero_sequence = None
        for sequence in all_sequences:
            if sequence.guid() == hiero_sequence_guid:
                hiero_sequence = sequence
                instance.data["hiero_sequence"] = sequence
                break

        if not hiero_sequence:
            raise PublishError(f"Cannot retrieve sequence from {hiero_sequence}.")

        self.log.debug(f"Editorial Package: {instance.data}")
