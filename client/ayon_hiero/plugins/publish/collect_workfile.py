import os

import pyblish.api

import hiero


class CollectWorkfile(pyblish.api.InstancePlugin):
    """Collect the current working file into context"""

    label = "Collect Workfile"
    families = ["workfile"]
    hosts = ["hiero"]
    order = pyblish.api.CollectorOrder - 0.49    

    def process(self, instance):

        active_timeline = hiero.ui.activeSequence()
        project = active_timeline.project()

        current_file = project.path()

        instance.context.data["currentFile"] = current_file
