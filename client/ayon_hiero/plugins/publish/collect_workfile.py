import pyblish.api

import hiero


class CollectWorkfile(pyblish.api.ContextPlugin):
    """Collect the current working file into context"""

    label = "Collect Workfile"
    hosts = ["hiero"]
    order = pyblish.api.CollectorOrder - 0.5

    def process(self, context):

        active_timeline = hiero.ui.activeSequence()
        project = active_timeline.project()

        current_file = project.path()

        context.data["currentFile"] = current_file
