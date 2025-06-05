from pyblish import api
import json


class CollectClipTagTasks(api.InstancePlugin):
    """Collect Tags from selected track items."""

    order = api.CollectorOrder - 0.077
    label = "Collect Tag Tasks"
    hosts = ["hiero"]
    families = ["shot"]

    def process(self, instance):
        # gets tags
        tags = instance.data["tags"]

        tasks = {}
        for tag in tags:

            t_metadata = dict(tag.metadata())
            if t_metadata.get("tag.json_metadata"):
                metadata = json.loads(t_metadata["tag.json_metadata"])
                product_type = metadata.get("productType")
                if product_type == "task":
                    task_type = metadata.get("type")
                    task_name = t_metadata.get("tag.label", "")
                    tasks[task_name] = {"type": task_type}
            else:
                # backward compatiblity for older tags
                t_product_type = t_metadata.get("tag.productType")
                if t_product_type is None:
                    t_product_type = t_metadata.get("tag.family", "")

                # gets only task product type tags and collect labels
                if "task" in t_product_type:
                    t_task_name = t_metadata.get("tag.label", "")
                    t_task_type = t_metadata.get("tag.type", "")
                    tasks[t_task_name] = {"type": t_task_type}

        instance.data["tasks"] = tasks

        self.log.info("Collected Tasks from Tags: `{}`".format(
            instance.data["tasks"]))
        return
