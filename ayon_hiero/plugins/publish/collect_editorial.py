import pyblish.api

class CollectEditorial(pyblish.api.InstancePlugin):
    """Collect editorial data from Hiero clips."""

    order = pyblish.api.CollectorOrder
    label = "Collect Editorial"
    families = ["clip"]

    def process(self, instance):
        import hiero.core

        clip = instance.data.get("clip")
        if clip is None:
            return

        # Get source in/out frames
        source_in = int(clip.sourceIn())
        source_out = int(clip.sourceOut())

        # Fix: sourceOut is exclusive in Hiero, so end frame is source_out - 1
        instance.data["frameStart"] = source_in
        instance.data["frameEnd"] = source_out - 1

        # Also store original for debugging
        instance.data["sourceIn"] = source_in
        instance.data["sourceOut"] = source_out
