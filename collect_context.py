import pyblish.api
import ayon_api

class CollectEditorialContext(pyblish.api.ContextPlugin):
    order = pyblish.api.CollectorOrder
    label = "Collect Editorial Context"

    def process(self, context):
        for instance in context:
            if instance.data.get("family") != "editorial":
                continue
            # Fix off-by-one error in end frame calculation
            handle_start = instance.data.get("handleStart", 0)
            handle_end = instance.data.get("handleEnd", 0)
            source_duration = instance.data.get("sourceDuration")
            if source_duration is not None:
                # Ensure end frame does not exceed start + duration - 1
                instance.data["frameEnd"] = instance.data["frameStart"] + source_duration - 1 + handle_start + handle_end
