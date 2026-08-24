import pyblish.api
from ayon_core.pipeline import registered_host


class CollectCurrentFile(pyblish.api.ContextPlugin):
    """Collect the current working file into context"""

    label = "Collect Current File"
    hosts = ["hiero"]
    order = pyblish.api.CollectorOrder - 0.5

    def process(self, context):
        host = registered_host()
        context.data["currentFile"] = host.get_current_workfile()
