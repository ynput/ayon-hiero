import pyblish.api
from ayon_core.pipeline import publish
from ayon_hiero.api import plugin


class ExtractEditorial(publish.Extractor):
    """Extract editorial data from Hiero timeline."""

    label = "Extract Editorial"
    order = pyblish.api.ExtractorOrder
    families = ["clip"]
    hosts = ["hiero"]

    def process(self, instance):
        # ... existing code ...

        # Calculate source end frame correctly
        handle_start = instance.data.get("handleStart", 0)
        handle_end = instance.data.get("handleEnd", 0)
        source_duration = instance.data.get("sourceDuration", 0)
        source_in = instance.data.get("sourceIn", 0)
        source_out = instance.data.get("sourceOut", 0)

        # Original problematic line: end_frame = source_in + source_duration + handle_end
        # Fix: end_frame should be source_out + handle_end (source_out already includes source_in + duration - 1)
        # But if source_out is not set, compute from source_in + (source_duration - 1) + handle_end
        if source_out is not None:
            frame_end = source_out + handle_end
        else:
            frame_end = source_in + source_duration - 1 + handle_end

        instance.data["frameStart"] = source_in - handle_start
        instance.data["frameEnd"] = frame_end

        # ... rest of processing ...
