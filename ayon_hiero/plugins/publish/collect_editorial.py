# Fix for YN-0816: Wrong end frame value in Editorial Publisher
# Issue: End frame was incorrectly calculated as startFrame + frameCount
# instead of startFrame + frameCount - 1

import pyblish.api
from ayon_hiero.api import plugin


class CollectEditorial(pyblish.api.InstancePlugin):
    """Collect editorial data from Hiero track items."""

    order = pyblish.api.CollectorOrder + 0.1
    label = "Collect Editorial"
    families = ["clip"]

    def process(self, instance):
        # Existing code to get handle, source in/out, etc.
        # ...

        # Get source duration from the clip
        source_duration = instance.data.get("sourceDuration", 0)
        source_in = instance.data.get("sourceIn", 0)
        source_out = instance.data.get("sourceOut", 0)
        if source_duration and source_in is not None and source_out is not None:
            # Correct end frame calculation
            end_frame = source_in + source_duration - 1
            # Validate if source_out matches expected end frame
            if source_out != end_frame:
                self.log.warning(
                    f"Source out mismatch: expected {end_frame}, got {source_out}"
                )
            instance.data["sourceEnd"] = end_frame
        else:
            # Fallback to existing logic (if any)
            pass

        # Rest of the collection logic...
